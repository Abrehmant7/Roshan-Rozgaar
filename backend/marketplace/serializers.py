from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from catalog.api import ServiceAreaSerializer, TradeSerializer
from catalog.models import ServiceArea, Specialty, Trade

from . import access
from .media import AUDIO_TYPES, detect_audio_type
from .models import REPORT_REASON_UR, REVIEW_TAG_KEYS, REVIEW_TAGS, JobRequest, ReportReason


class SpecialtyBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ["id", "slug", "name_en", "name_ur"]


# ---------------------------------------------------------------- workers ---

def _ids(objs):
    return sorted(o.id for o in objs)


def worker_summary(profile, stats=None):
    """Public view of a worker (discovery, quotes, bookings).

    Expects `active_trades`, `active_specialties`, `active_areas` prefetched
    (see selectors.with_public_prefetch). `stats` comes from selectors.worker_stats.
    """
    stats = stats or {}
    data = {
        "id": profile.pk,
        "display_name": profile.display_name,
        "experience_years": profile.experience_years,
        "trades": _ids(profile.active_trades),
        "specialties": _ids(profile.active_specialties),
        "service_areas": _ids(profile.active_areas),
        "verified": True,
        "verification_simulated": profile.identity_simulated,
        "rating": {"average": stats.get("rating_avg"), "count": stats.get("review_count", 0)},
        "completed_jobs": stats.get("completed_jobs", 0),
    }
    if hasattr(profile, "matches_specialty"):
        data["matches_specialty"] = bool(profile.matches_specialty)
    if hasattr(profile, "available_now"):
        data["is_available"] = bool(profile.available_now)
    return data


class DiscoveryQuerySerializer(serializers.Serializer):
    trade = serializers.PrimaryKeyRelatedField(queryset=Trade.objects.filter(is_active=True))
    service_area = serializers.PrimaryKeyRelatedField(queryset=ServiceArea.objects.filter(is_active=True))
    specialty = serializers.PrimaryKeyRelatedField(
        queryset=Specialty.objects.filter(is_active=True), required=False, allow_null=True
    )

    def validate(self, attrs):
        specialty = attrs.get("specialty")
        if specialty and specialty.trade_id != attrs["trade"].id:
            raise serializers.ValidationError({"specialty": ["This specialty does not belong to the selected trade."]})
        return attrs


# ----------------------------------------------------------- job requests ---

class JobRequestCreateSerializer(serializers.Serializer):
    """POST /api/v1/job-requests/ as JSON or multipart (multipart needed for `voice_note`)."""

    trade = serializers.PrimaryKeyRelatedField(queryset=Trade.objects.filter(is_active=True))
    service_area = serializers.PrimaryKeyRelatedField(queryset=ServiceArea.objects.filter(is_active=True))
    specialty = serializers.PrimaryKeyRelatedField(
        queryset=Specialty.objects.filter(is_active=True), required=False, allow_null=True
    )
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    address_details = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    voice_note = serializers.FileField(required=False, allow_null=True, allow_empty_file=False)

    def validate_voice_note(self, upload):
        if upload is None:
            return None
        if upload.size > settings.VOICE_NOTE_MAX_BYTES:
            limit = settings.VOICE_NOTE_MAX_BYTES // (1024 * 1024)
            raise serializers.ValidationError(ErrorDetail(f"Voice note is too large (max {limit} MB).", "too_large"))
        kind = detect_audio_type(upload.read(16))
        upload.seek(0)
        if kind is None:
            raise serializers.ValidationError(
                ErrorDetail("Unsupported audio. Use WebM, Ogg, MP4/M4A, MP3, AAC or WAV.", "unsupported_format")
            )
        upload.name = f"voice.{kind}"
        upload.audio_kind = kind
        return upload

    def validate(self, attrs):
        specialty = attrs.get("specialty")
        if specialty and specialty.trade_id != attrs["trade"].id:
            raise serializers.ValidationError({"specialty": ["This specialty does not belong to the selected trade."]})
        attrs["description"] = attrs.get("description", "").strip()
        if not attrs["description"] and not attrs.get("voice_note"):
            raise serializers.ValidationError(
                {"description": [ErrorDetail("Describe the job or record a voice note.", "description_or_voice_required")]}
            )
        return attrs

    def create(self, validated_data):
        voice = validated_data.pop("voice_note", None)
        job = JobRequest(customer=self.context["request"].user, **validated_data)
        if voice is not None:
            job.voice_note = voice
            job.voice_note_type = AUDIO_TYPES[voice.audio_kind]
        job.save()
        return job


class JobRequestSerializer(serializers.ModelSerializer):
    """Read shape. Private fields appear only for the owner and the assigned worker.

    context: {"relation": access.OWNER | ASSIGNED_WORKER | ELIGIBLE_WORKER}
    """

    status = serializers.CharField(read_only=True)
    trade = TradeSerializer(read_only=True)
    service_area = ServiceAreaSerializer(read_only=True)
    specialty = SpecialtyBriefSerializer(read_only=True)
    has_voice_note = serializers.SerializerMethodField()
    voice_note_url = serializers.SerializerMethodField()

    class Meta:
        model = JobRequest
        fields = [
            "id", "status", "trade", "service_area", "specialty", "description",
            "has_voice_note", "voice_note_url", "created_at",
        ]

    def get_has_voice_note(self, job):
        return bool(job.voice_note)

    def get_voice_note_url(self, job):
        return f"/api/v1/job-requests/{job.pk}/voice-note/" if job.voice_note else None

    def to_representation(self, job):
        data = super().to_representation(job)
        rel = self.context.get("relation")
        user = self.context.get("user")
        data["viewer"] = rel
        if rel in (access.OWNER, access.ASSIGNED_WORKER):
            data["address_details"] = job.address_details
            data["customer"] = {"id": job.customer_id, "username": job.customer.username}
        booking = job.booking_or_none
        data["booking"] = booking_brief(booking) if booking and rel != access.ELIGIBLE_WORKER else None
        if rel == access.OWNER:
            if self.context.get("detail"):
                quotes = list(job.quotes.all())
                cards = public_workers({q.worker_id for q in quotes})
                data["quotes"] = [quote_payload(q, cards.get(q.worker_id)) for q in quotes]
            data["quote_count"] = getattr(job, "quote_count", None)
            if data["quote_count"] is None:
                data["quote_count"] = job.quotes.count()
        elif user is not None:
            prefetched = getattr(job, "my_quotes", None)  # set by the job board's Prefetch
            if prefetched is None:
                mine = job.quotes.filter(worker=user).first()
            else:
                mine = prefetched[0] if prefetched else None
            data["my_quote"] = quote_payload(mine) if mine else None
        return data


# ------------------------------------------------------- quotes / bookings ---

def iso(value):
    return serializers.DateTimeField().to_representation(value) if value else None


def money(value):
    return f"{value:.2f}"


def public_workers(user_ids):
    """{user_id: worker_summary} with stats and live availability, in 3 queries + stats."""
    from workers.models import WorkerProfile

    from . import selectors

    ids = list(user_ids)
    if not ids:
        return {}
    profiles = selectors.with_public_prefetch(WorkerProfile.objects.filter(user_id__in=ids))
    available = set(WorkerProfile.objects.available().filter(user_id__in=ids).values_list("pk", flat=True))
    stats = selectors.worker_stats(ids)
    cards = {}
    for profile in profiles:
        profile.available_now = profile.pk in available
        cards[profile.pk] = worker_summary(profile, stats.get(profile.pk))
    return cards


def quote_status(quote):
    booking = quote.job.booking_or_none
    if booking is None:
        return "PENDING"
    return "ACCEPTED" if booking.quote_id == quote.pk else "NOT_SELECTED"


def quote_payload(quote, worker_card=None):
    data = {
        "id": quote.pk,
        "job_request": quote.job_id,
        "amount": money(quote.amount),
        "currency": "PKR",
        "message": quote.message,
        "status": quote_status(quote),
        "created_at": iso(quote.created_at),
    }
    if worker_card is not None:
        data["worker"] = worker_card
    return data


def booking_brief(booking):
    return {"id": booking.pk, "status": booking.status, "amount": money(booking.amount), "currency": "PKR"}


class QuoteCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("1"), max_value=Decimal("10000000"),
        help_text="PKR, as a decimal string such as \"1500.00\"",
    )
    message = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class CheckInSerializer(serializers.Serializer):
    pin = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "Enter the 6-digit PIN."})


def booking_actions(booking, viewer_role, has_review, has_my_report):
    """What the viewer may do right now. React renders controls from this list only."""
    from .models import BookingStatus

    actions = []
    if viewer_role == "customer":
        if booking.status == BookingStatus.BOOKED:
            actions.append("issue_pin")
        if booking.status == BookingStatus.COMPLETED and not has_review:
            actions.append("review")
    else:
        if booking.status == BookingStatus.BOOKED:
            actions.append("check_in")
        elif booking.status == BookingStatus.IN_PROGRESS:
            actions.append("complete")
    if not has_my_report:
        actions.append("report")
    return actions


def review_payload(review, include_booking=False):
    data = {
        "id": review.pk,
        "rating": review.rating,
        "text": review.text,
        "tags": review.tags,
        "created_at": iso(review.created_at),
    }
    if include_booking:
        data["booking"] = review.booking_id
    return data


def report_payload(report):
    return {
        "id": report.pk,
        "booking": report.booking_id,
        "reason": report.reason,
        "details": report.details,
        "status": report.status,
        "created_at": iso(report.created_at),
    }


class ReviewCreateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    text = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    tags = serializers.ListField(child=serializers.CharField(), required=False, default=list, max_length=6)

    def validate_tags(self, tags):
        unknown = sorted(set(tags) - REVIEW_TAG_KEYS)
        if unknown:
            raise serializers.ValidationError(f"Unknown tags: {', '.join(unknown)}.")
        return list(dict.fromkeys(tags))


class ReportCreateSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(choices=ReportReason.choices)
    details = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


def review_tags():
    return [{"key": k, "name_en": en, "name_ur": ur} for k, en, ur in REVIEW_TAGS]


def report_reasons():
    return [{"key": k, "name_en": label, "name_ur": REPORT_REASON_UR[k]} for k, label in ReportReason.choices]


def booking_payload(booking, user):
    from .services import live_pin

    viewer_role = "customer" if booking.customer_id == user.id else "worker"
    relation = access.OWNER if viewer_role == "customer" else access.ASSIGNED_WORKER
    review = getattr(booking, "review", None)
    my_report = booking.reports.filter(reporter=user).first()
    pin = live_pin(booking) if booking.status == "BOOKED" else None
    pin_info = None
    if pin is not None and pin.expires_at > timezone.now():
        pin_info = {
            "expires_at": iso(pin.expires_at),
            "attempts_remaining": settings.PIN_MAX_ATTEMPTS - pin.failed_attempts,
        }
    return {
        "id": booking.pk,
        "status": booking.status,
        "amount": money(booking.amount),
        "currency": "PKR",
        "quote_id": booking.quote_id,
        "booked_at": iso(booking.booked_at),
        "checked_in_at": iso(booking.checked_in_at),
        "completed_at": iso(booking.completed_at),
        "viewer": viewer_role,
        "actions": booking_actions(booking, viewer_role, review is not None, my_report is not None),
        "review": review_payload(review) if review else None,
        "my_report": {"id": my_report.pk, "status": my_report.status} if my_report else None,
        "active_pin": pin_info,  # never contains the PIN itself
        "worker": public_workers([booking.worker_id]).get(booking.worker_id),
        "customer": {"id": booking.customer_id, "username": booking.customer.username},
        "job_request": JobRequestSerializer(booking.job, context={"relation": relation, "user": user}).data,
    }
