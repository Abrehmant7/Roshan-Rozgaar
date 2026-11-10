from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Exists, OuterRef

from catalog.models import ServiceArea, Specialty, Trade

# Booking statuses that make a worker busy. Defined here (not imported from the
# marketplace app) so availability has a single definition without import cycles.
ACTIVE_BOOKING_STATUSES = ("BOOKED", "IN_PROGRESS")


class WorkerProfileQuerySet(models.QuerySet):
    def complete(self):
        """Onboarded: active worker account with >=1 active trade and >=1 active area."""
        trades = WorkerProfile.trades.through.objects.filter(
            workerprofile_id=OuterRef("pk"), trade__is_active=True
        )
        areas = WorkerProfile.service_areas.through.objects.filter(
            workerprofile_id=OuterRef("pk"), servicearea__is_active=True
        )
        return self.filter(user__is_active=True, user__role="worker").filter(Exists(trades), Exists(areas))

    def available(self):
        """THE availability rule used by discovery, quoting and booking:
        complete profile + accepting jobs + no active booking."""
        return self.complete().filter(accepting_jobs=True).exclude(
            user__worker_bookings__status__in=ACTIVE_BOOKING_STATUSES
        )


class WorkerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="worker_profile",
        limit_choices_to={"role": "worker"},
    )
    display_name = models.CharField(max_length=100)
    experience_years = models.PositiveSmallIntegerField(validators=[MaxValueValidator(60)])
    trades = models.ManyToManyField(Trade, related_name="workers")
    specialties = models.ManyToManyField(Specialty, blank=True, related_name="workers")
    service_areas = models.ManyToManyField(ServiceArea, related_name="workers")
    accepting_jobs = models.BooleanField(default=True)

    # Result of the ID scan. The raw number and the image are never stored.
    verified_name = models.CharField(max_length=100)
    id_masked = models.CharField(max_length=20)
    identity_digest = models.CharField(max_length=64, unique=True, editable=False)
    identity_simulated = models.BooleanField(
        default=False, help_text="Verified through the mock OCR path with fictional fixtures."
    )
    verified_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = WorkerProfileQuerySet.as_manager()

    class Meta:
        ordering = ["display_name", "pk"]

    def __str__(self):
        return f"{self.display_name} ({self.user.username})"

    @property
    def is_complete(self) -> bool:
        return WorkerProfile.objects.complete().filter(pk=self.pk).exists()

    @property
    def is_available(self) -> bool:
        return WorkerProfile.objects.available().filter(pk=self.pk).exists()


class ScanProof(models.Model):
    """Short-lived, single-use proof that this worker just passed an ID scan.

    Only a SHA-256 of the token is stored; the token itself is shown once.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scan_proofs")
    token_hash = models.CharField(max_length=64, unique=True)
    identity_digest = models.CharField(max_length=64)
    verified_name = models.CharField(max_length=100)
    id_masked = models.CharField(max_length=20)
    simulated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
