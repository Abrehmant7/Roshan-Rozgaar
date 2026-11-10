from django.conf import settings
from django.db import models
from django.db.models import Q

from catalog.models import ServiceArea, Specialty, Trade

from .media import private_storage, voice_note_path

OPEN = "OPEN"  # display status of a request with no booking (not stored)


class JobRequestQuerySet(models.QuerySet):
    def open(self):
        """Requests with no booking yet."""
        return self.all()  # Phase 5: .filter(booking__isnull=True)


class JobRequest(models.Model):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_requests"
    )
    trade = models.ForeignKey(Trade, on_delete=models.PROTECT, related_name="job_requests")
    service_area = models.ForeignKey(ServiceArea, on_delete=models.PROTECT, related_name="job_requests")
    specialty = models.ForeignKey(
        Specialty, on_delete=models.PROTECT, null=True, blank=True, related_name="job_requests"
    )
    description = models.TextField(max_length=1000, blank=True)
    # Private: shown only to the owner and, after acceptance, the assigned worker.
    address_details = models.TextField(max_length=300, blank=True)
    voice_note = models.FileField(storage=private_storage, upload_to=voice_note_path, blank=True, max_length=200)
    voice_note_type = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = JobRequestQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["trade", "service_area", "-created_at"])]
        constraints = [
            models.CheckConstraint(
                condition=~Q(description="") | ~Q(voice_note=""),
                name="jobrequest_has_description_or_voice_note",
            )
        ]

    def __str__(self):
        return f"#{self.pk} {self.trade} in {self.service_area}"

    @property
    def booking_or_none(self):
        return getattr(self, "booking", None)

    @property
    def status(self) -> str:
        booking = self.booking_or_none
        return booking.status if booking else OPEN
