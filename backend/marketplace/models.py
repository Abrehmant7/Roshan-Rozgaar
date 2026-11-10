from django.conf import settings
from django.db import models
from django.db.models import Q

from catalog.models import ServiceArea, Specialty, Trade

from .media import private_storage, voice_note_path

OPEN = "OPEN"  # display status of a request with no booking (not stored)


class JobRequestQuerySet(models.QuerySet):
    def open(self):
        """Requests with no booking yet."""
        return self.filter(booking__isnull=True)


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


class BookingStatus(models.TextChoices):
    BOOKED = "BOOKED", "Booked"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    COMPLETED = "COMPLETED", "Completed"


ACTIVE_STATUSES = [BookingStatus.BOOKED, BookingStatus.IN_PROGRESS]


class Quote(models.Model):
    job = models.ForeignKey(JobRequest, on_delete=models.CASCADE, related_name="quotes")
    worker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quotes")
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="PKR")
    message = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["amount", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["job", "worker"], name="one_quote_per_worker_per_request"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="quote_amount_positive"),
        ]

    def __str__(self):
        return f"Quote #{self.pk}: PKR {self.amount} for request #{self.job_id}"


class Booking(models.Model):
    job = models.OneToOneField(JobRequest, on_delete=models.PROTECT, related_name="booking")
    quote = models.OneToOneField(Quote, on_delete=models.PROTECT, related_name="booking")
    worker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="worker_bookings")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="customer_bookings")
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Agreed price in PKR, copied from the quote.")
    status = models.CharField(max_length=16, choices=BookingStatus.choices, default=BookingStatus.BOOKED)
    booked_at = models.DateTimeField(auto_now_add=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-booked_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["worker"],
                condition=Q(status__in=["BOOKED", "IN_PROGRESS"]),
                name="one_active_booking_per_worker",
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="booking_amount_positive"),
        ]

    def __str__(self):
        return f"Booking #{self.pk} ({self.status})"


class ArrivalPin(models.Model):
    """One-time check-in code. Only a server-keyed digest is stored."""

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="pins")
    digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["booking"],
                condition=Q(consumed_at__isnull=True, revoked_at__isnull=True),
                name="one_live_pin_per_booking",
            )
        ]
