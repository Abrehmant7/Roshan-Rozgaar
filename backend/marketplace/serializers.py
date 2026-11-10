from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from catalog.api import ServiceAreaSerializer, TradeSerializer
from catalog.models import ServiceArea, Specialty, Trade

from . import access
from .media import AUDIO_TYPES, detect_audio_type
from .models import JobRequest


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
        data["viewer"] = rel
        if rel in (access.OWNER, access.ASSIGNED_WORKER):
            data["address_details"] = job.address_details
            data["customer"] = {"id": job.customer_id, "username": job.customer.username}
        return data
