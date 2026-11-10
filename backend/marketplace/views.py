from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.api import ApiError, IsCustomer, IsWorker, StandardPagination

from django.db.models import Count, Prefetch

from . import access, selectors, services
from .models import Booking, JobRequest, Quote
from .serializers import (
    CheckInSerializer,
    DiscoveryQuerySerializer,
    JobRequestCreateSerializer,
    JobRequestSerializer,
    QuoteCreateSerializer,
    booking_payload,
    iso,
    public_workers,
    quote_payload,
    worker_summary,
)

JOB_RELATED = ["trade", "service_area", "specialty", "customer", "booking"]


def _not_found():
    # Same answer for "does not exist" and "not yours" so IDs cannot be probed.
    return ApiError("Not found.", "not_found", status.HTTP_404_NOT_FOUND)


def _paginate(view, request, queryset, to_data):
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request, view=view)
    return paginator.get_paginated_response(to_data(page))


def _visible_job(user, pk):
    job = JobRequest.objects.select_related(*JOB_RELATED).filter(pk=pk).first()
    rel = access.relation(user, job) if job else None
    if rel is None:
        raise _not_found()
    return job, rel


def _require_profile(user):
    profile = access.complete_profile(user)
    if profile is None:
        raise ApiError(
            "Finish your worker profile first.", "profile_incomplete", status.HTTP_403_FORBIDDEN
        )
    return profile


class WorkerDiscoveryView(APIView):
    """GET /api/v1/workers/?trade=<id>&service_area=<id>[&specialty=<id>]"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = DiscoveryQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        qs = selectors.discover(**query.validated_data)

        def to_data(profiles):
            stats = selectors.worker_stats([p.pk for p in profiles])
            out = []
            for p in profiles:
                p.available_now = True  # discover() only returns available workers
                out.append(worker_summary(p, stats[p.pk]))
            return out

        return _paginate(self, request, qs, to_data)


class JobRequestListCreateView(APIView):
    """GET own requests (customer) / POST a new request (customer)."""

    permission_classes = [IsCustomer]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        qs = (JobRequest.objects.filter(customer=request.user).select_related(*JOB_RELATED)
              .annotate(quote_count=Count("quotes")).order_by("-created_at", "-id"))
        return _paginate(
            self, request, qs,
            lambda jobs: JobRequestSerializer(jobs, many=True, context={"relation": access.OWNER}).data,
        )

    def post(self, request):
        serializer = JobRequestCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        job = serializer.save()
        data = JobRequestSerializer(job, context={"relation": access.OWNER, "detail": True}).data
        return Response(data, status=status.HTTP_201_CREATED)


class JobRequestDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        job, rel = _visible_job(request.user, pk)
        context = {"relation": rel, "user": request.user, "detail": True}
        return Response(JobRequestSerializer(job, context=context).data)


class VoiceNoteView(APIView):
    """Streams the private voice note to the owner, eligible workers (while open)
    and the assigned worker (after booking)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        job, _ = _visible_job(request.user, pk)
        missing = ApiError("This request has no voice note.", "voice_note_missing", status.HTTP_404_NOT_FOUND)
        if not job.voice_note:
            raise missing
        try:
            handle = job.voice_note.open("rb")
        except (FileNotFoundError, OSError):
            raise missing from None
        ext = job.voice_note.name.rsplit(".", 1)[-1]
        response = FileResponse(handle, content_type=job.voice_note_type or "application/octet-stream",
                                as_attachment=False, filename=f"voice-note-{job.pk}.{ext}")
        response["Cache-Control"] = "private, no-store"
        return response


class JobBoardView(APIView):
    """GET /api/v1/job-board/ — open requests matching the worker's trades and areas."""

    permission_classes = [IsWorker]

    def get(self, request):
        profile = _require_profile(request.user)
        mine = Prefetch("quotes", queryset=Quote.objects.filter(worker=request.user), to_attr="my_quotes")
        qs = access.board_queryset(profile).select_related(*JOB_RELATED).prefetch_related(mine)
        context = {"relation": access.ELIGIBLE_WORKER, "user": request.user}
        response = _paginate(self, request, qs, lambda jobs: JobRequestSerializer(jobs, many=True, context=context).data)
        response.data["worker_is_available"] = profile.is_available
        return response


# ------------------------------------------------------- quotes / bookings ---

class JobQuotesView(APIView):
    """GET: the owner sees every quote, a worker only their own. POST: a worker quotes."""

    def get_permissions(self):
        return [IsWorker()] if self.request.method == "POST" else [IsAuthenticated()]

    def get(self, request, pk):
        job, rel = _visible_job(request.user, pk)
        quotes = job.quotes.all() if rel == access.OWNER else job.quotes.filter(worker=request.user)
        quotes = list(quotes.select_related("job__booking"))
        cards = public_workers({q.worker_id for q in quotes})
        return Response([quote_payload(q, cards.get(q.worker_id)) for q in quotes])

    def post(self, request, pk):
        serializer = QuoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quote, created = services.submit_quote(request.user, pk, **serializer.validated_data)
        return Response(quote_payload(quote), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class MyQuotesView(APIView):
    """GET /api/v1/quotes/ - the worker's own quotes, newest first."""

    permission_classes = [IsWorker]

    def get(self, request):
        qs = (Quote.objects.filter(worker=request.user)
              .select_related("job__trade", "job__service_area", "job__booking").order_by("-created_at", "-id"))

        def to_data(quotes):
            out = []
            for q in quotes:
                data = quote_payload(q)
                data["job_summary"] = {"id": q.job_id, "status": q.job.status,
                                       "trade": q.job.trade_id, "service_area": q.job.service_area_id}
                out.append(data)
            return out

        return _paginate(self, request, qs, to_data)


class AcceptQuoteView(APIView):
    permission_classes = [IsCustomer]

    def post(self, request, pk):
        booking, created = services.accept_quote(request.user, pk)
        booking = _visible_booking(request.user, booking.pk)
        return Response(booking_payload(booking, request.user),
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


BOOKING_RELATED = ["job__trade", "job__service_area", "job__specialty", "job__customer", "job__booking", "customer"]


def _visible_booking(user, pk):
    booking = Booking.objects.select_related(*BOOKING_RELATED).filter(pk=pk).first()
    if booking is None or user.id not in (booking.customer_id, booking.worker_id):
        raise _not_found()
    return booking


class BookingListView(APIView):
    """GET /api/v1/bookings/[?status=BOOKED,IN_PROGRESS,COMPLETED] - the viewer's own bookings."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        field = "worker" if request.user.role == "worker" else "customer"
        qs = Booking.objects.filter(**{field: request.user}).select_related(*BOOKING_RELATED)
        wanted = request.query_params.get("status")
        if wanted:
            qs = qs.filter(status__in=[s.strip().upper() for s in wanted.split(",")])
        return _paginate(self, request, qs, lambda rows: [booking_payload(b, request.user) for b in rows])


class BookingDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        return Response(booking_payload(_visible_booking(request.user, pk), request.user))


class IssuePinView(APIView):
    """Customer only. The PIN appears in this response and nowhere else."""

    permission_classes = [IsCustomer]

    def post(self, request, pk):
        pin, record = services.issue_pin(request.user, pk)
        booking = _visible_booking(request.user, pk)
        return Response({"pin": pin, "expires_at": iso(record.expires_at),
                         "booking": booking_payload(booking, request.user)}, status=status.HTTP_201_CREATED)


class CheckInView(APIView):
    permission_classes = [IsWorker]

    def post(self, request, pk):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.check_in(request.user, pk, serializer.validated_data["pin"])
        return Response(booking_payload(_visible_booking(request.user, pk), request.user))


class CompleteView(APIView):
    permission_classes = [IsWorker]

    def post(self, request, pk):
        services.complete(request.user, pk)
        return Response(booking_payload(_visible_booking(request.user, pk), request.user))
