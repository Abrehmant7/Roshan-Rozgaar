from rest_framework import serializers

from catalog.models import ServiceArea, Specialty, Trade

from .models import WorkerProfile


def _active_ids(manager):
    return sorted(manager.filter(is_active=True).values_list("id", flat=True))


class WorkerProfileWriteSerializer(serializers.Serializer):
    """PUT /api/v1/workers/me/ — full replacement of the editable fields."""

    display_name = serializers.CharField(max_length=100)
    experience_years = serializers.IntegerField(min_value=0, max_value=60)
    trades = serializers.PrimaryKeyRelatedField(
        queryset=Trade.objects.filter(is_active=True), many=True, allow_empty=False
    )
    specialties = serializers.PrimaryKeyRelatedField(
        queryset=Specialty.objects.filter(is_active=True, trade__is_active=True),
        many=True,
        required=False,
    )
    service_areas = serializers.PrimaryKeyRelatedField(
        queryset=ServiceArea.objects.filter(is_active=True), many=True, allow_empty=False
    )
    accepting_jobs = serializers.BooleanField(required=False, default=True)
    scan_proof = serializers.CharField(required=False, write_only=True, max_length=200)

    def validate(self, attrs):
        attrs["trades"] = list(dict.fromkeys(attrs["trades"]))
        attrs["service_areas"] = list(dict.fromkeys(attrs["service_areas"]))
        specialties = list(dict.fromkeys(attrs.get("specialties", [])))
        trade_ids = {t.id for t in attrs["trades"]}
        stray = [s.id for s in specialties if s.trade_id not in trade_ids]
        if stray:
            raise serializers.ValidationError(
                {"specialties": [f"Specialty {sid} does not belong to a selected trade." for sid in stray]}
            )
        attrs["specialties"] = specialties
        return attrs


def profile_payload(profile: WorkerProfile) -> dict:
    """Private view of a worker's own profile."""
    return {
        "id": profile.pk,
        "display_name": profile.display_name,
        "experience_years": profile.experience_years,
        "trades": _active_ids(profile.trades),
        "specialties": sorted(
            profile.specialties.filter(is_active=True, trade__is_active=True).values_list("id", flat=True)
        ),
        "service_areas": _active_ids(profile.service_areas),
        "accepting_jobs": profile.accepting_jobs,
        "is_complete": profile.is_complete,
        "is_available": profile.is_available,
        "verification": {
            "name": profile.verified_name,
            "id_masked": profile.id_masked,
            "verified_at": serializers.DateTimeField().to_representation(profile.verified_at),
            "simulated": profile.identity_simulated,
            "registry": "fictional",
        },
        "created_at": serializers.DateTimeField().to_representation(profile.created_at),
        "updated_at": serializers.DateTimeField().to_representation(profile.updated_at),
    }
