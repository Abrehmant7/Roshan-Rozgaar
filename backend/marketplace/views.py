from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.api import ApiError, IsCustomer, IsWorker, StandardPagination

from . import access, selectors
from .models import JobRequest
from .serializers import (
    DiscoveryQuerySerializer,
    JobRequestCreateSerializer,
    JobRequestSerializer,
    worker_summary,
)

JOB_RELATED = ["trade", "service_area", "specialty", "customer"]


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
        qs = JobRequest.objects.filter(customer=request.user).select_related(*JOB_RELATED)
        return _paginate(
            self, request, qs,
            lambda jobs: JobRequestSerializer(jobs, many=True, context={"relation": access.OWNER}).data,
        )

    def post(self, request):
        serializer = JobRequestCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        job = serializer.save()
        data = JobRequestSerializer(job, context={"relation": access.OWNER}).data
        return Response(data, status=status.HTTP_201_CREATED)


class JobRequestDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        job, rel = _visible_job(request.user, pk)
        return Response(JobRequestSerializer(job, context={"relation": rel}).data)


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
        qs = access.board_queryset(profile).select_related(*JOB_RELATED)
        return _paginate(
            self, request, qs,
            lambda jobs: JobRequestSerializer(jobs, many=True, context={"relation": access.ELIGIBLE_WORKER}).data,
        )
