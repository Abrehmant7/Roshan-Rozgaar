"""Worker onboarding: ID scan -> one-time proof -> profile.

Account authentication is separate: workers sign up themselves
(POST /api/v1/auth/register/worker/) or use staff-provisioned accounts. The scan
only verifies identity for the profile, always against the FICTIONAL registry.
"""

import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import ErrorDetail, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from config.api import ApiError, IsWorker, conflict

from . import identity
from .models import ScanProof, WorkerProfile
from .ocr import MOCK_AUTO_ORDER, MOCK_CARDS, OcrFailure, detect_image_type, read_card

logger = logging.getLogger(__name__)
from .serializers import WorkerProfileWriteSerializer, profile_payload


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _get_profile(user):
    try:
        return WorkerProfile.objects.get(user=user)
    except WorkerProfile.DoesNotExist:
        raise ApiError(
            "No worker profile yet. Scan your ID card to create one.",
            "profile_not_found",
            status.HTTP_404_NOT_FOUND,
        ) from None


def _first_free_mock_card(user):
    """Mock mode without a fixture keyword: the first fictional card not linked to
    another worker (keeps the demo flow working for newly signed-up workers)."""
    taken = set(WorkerProfile.objects.exclude(user=user).values_list("identity_digest", flat=True))
    for key in MOCK_AUTO_ORDER:
        if identity.identity_digest(MOCK_CARDS[key]) not in taken:
            return MOCK_CARDS[key]
    return MOCK_CARDS[MOCK_AUTO_ORDER[0]]  # all taken -> 409 identity_in_use below


def _field_error(field, message, code):
    return ValidationError({field: [ErrorDetail(message, code=code)]})


class ScanView(APIView):
    """POST multipart `image` (JPEG/PNG/WebP, <= OCR_MAX_IMAGE_BYTES)."""

    permission_classes = [IsWorker]
    parser_classes = [MultiPartParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ocr_scan"

    def post(self, request):
        upload = request.FILES.get("image")
        if upload is None:
            raise _field_error("image", "Upload a photo of your ID card.", "required")
        if upload.size > settings.OCR_MAX_IMAGE_BYTES:
            limit_mb = settings.OCR_MAX_IMAGE_BYTES // (1024 * 1024)
            raise _field_error("image", f"Photo is too large (max {limit_mb} MB).", "too_large")
        kind = detect_image_type(upload.read(16))
        if kind is None:
            raise _field_error("image", "Use a JPEG, PNG or WebP photo.", "unsupported_format")
        upload.seek(0)
        data = upload.read()
        try:
            result = read_card(data, kind, upload.name)
        except OcrFailure as failure:
            # Only the stable code is logged: never the image, the ID or the API key.
            logger.warning("ID scan failed: %s (mode=%s)", failure.code, settings.OCR_MODE)
            raise ApiError(failure.message, failure.code, failure.status,
                           retryable=failure.retryable, mode=settings.OCR_MODE) from None
        finally:
            del data  # the image is never stored

        digits = _first_free_mock_card(request.user) if result.auto else result.id_number
        if digits is None:
            raise ApiError(
                "No ID number found. Retake the photo in good light with the whole card visible.",
                "id_not_found",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                retryable=True,
                mode=result.mode,
            )
        record = identity.lookup(digits)
        if record is None:
            raise ApiError(
                "This ID number is not in the fictional demo registry.",
                "id_not_registered",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                retryable=True,
                mode=result.mode,
            )
        digest = identity.identity_digest(digits)
        if WorkerProfile.objects.filter(identity_digest=digest).exclude(user=request.user).exists():
            raise conflict("This ID card is already linked to another worker account.", "identity_in_use")

        token = secrets.token_urlsafe(32)
        proof = ScanProof.objects.create(
            user=request.user,
            token_hash=_hash_token(token),
            identity_digest=digest,
            verified_name=record["name_en"],
            id_masked=identity.mask_cnic(digits),
            simulated=result.simulated,
            expires_at=timezone.now() + timedelta(seconds=settings.SCAN_PROOF_TTL_SECONDS),
        )
        del digits
        return Response(
            {
                "mode": result.mode,
                "simulated": result.simulated,  # True when the OCR itself was the mock
                "registry": identity.REGISTRY_KIND,  # always "fictional": not a real identity check
                "identity": {
                    "name_en": record["name_en"],
                    "name_ur": record["name_ur"],
                    "id_masked": proof.id_masked,
                },
                "scan_proof": token,
                "expires_at": serializers.DateTimeField().to_representation(proof.expires_at),
            },
            status=status.HTTP_201_CREATED,
        )


def _consume_proof(user, token):
    """Lock, validate and consume a scan proof. Raises field errors on `scan_proof`."""
    proof = (
        ScanProof.objects.select_for_update()
        .filter(token_hash=_hash_token(token), user=user)
        .first()
    )
    if proof is None:
        raise _field_error("scan_proof", "Scan proof is not valid. Scan your ID card again.", "invalid")
    if proof.used_at is not None:
        raise _field_error("scan_proof", "Scan proof was already used. Scan your ID card again.", "used")
    if proof.expires_at <= timezone.now():
        raise _field_error("scan_proof", "Scan proof expired. Scan your ID card again.", "expired")
    proof.used_at = timezone.now()
    proof.save(update_fields=["used_at"])
    return proof


class WorkerMeView(APIView):
    permission_classes = [IsWorker]

    def get(self, request):
        return Response(profile_payload(_get_profile(request.user)))

    def put(self, request):
        serializer = WorkerProfileWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        token = data.pop("scan_proof", None)

        try:
            with transaction.atomic():
                profile = WorkerProfile.objects.select_for_update().filter(user=request.user).first()
                created = profile is None
                if created and not token:
                    raise _field_error(
                        "scan_proof", "Scan your ID card first; new profiles need a scan proof.", "required"
                    )
                if created:
                    profile = WorkerProfile(user=request.user)
                if token:
                    proof = _consume_proof(request.user, token)
                    profile.verified_name = proof.verified_name
                    profile.id_masked = proof.id_masked
                    profile.identity_digest = proof.identity_digest
                    profile.identity_simulated = proof.simulated
                    profile.verified_at = timezone.now()
                profile.display_name = data["display_name"]
                profile.experience_years = data["experience_years"]
                profile.accepting_jobs = data["accepting_jobs"]
                profile.save()
                profile.trades.set(data["trades"])
                profile.specialties.set(data["specialties"])
                profile.service_areas.set(data["service_areas"])
        except IntegrityError:
            raise conflict(
                "This ID card is already linked to another worker account.", "identity_in_use"
            ) from None

        return Response(
            profile_payload(profile), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class AvailabilitySerializer(serializers.Serializer):
    accepting_jobs = serializers.BooleanField()


class AvailabilityView(APIView):
    """PATCH {"accepting_jobs": bool} — the only field a worker toggles day to day."""

    permission_classes = [IsWorker]

    def patch(self, request):
        serializer = AvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = _get_profile(request.user)
        profile.accepting_jobs = serializer.validated_data["accepting_jobs"]
        profile.save(update_fields=["accepting_jobs", "updated_at"])
        return Response(
            {"accepting_jobs": profile.accepting_jobs, "is_available": profile.is_available}
        )
