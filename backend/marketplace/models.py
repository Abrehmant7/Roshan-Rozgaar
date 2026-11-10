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


# (key, English, Urdu) — stable keys; labels are display copy only.
REVIEW_TAGS = [
    ("on_time", "On time", "وقت پر آئے"),
    ("fair_price", "Fair price", "مناسب قیمت"),
    ("quality_work", "Quality work", "عمدہ کام"),
    ("clean_work", "Clean work", "صاف ستھرا کام"),
    ("polite", "Polite", "خوش اخلاق"),
    ("would_hire_again", "Would hire again", "دوبارہ بلائیں گے"),
]
REVIEW_TAG_KEYS = {key for key, _, _ in REVIEW_TAGS}


class Review(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.PROTECT, related_name="review")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviews_given")
    worker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviews_received")
    rating = models.PositiveSmallIntegerField()
    text = models.TextField(max_length=500, blank=True)
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_to_5"),
        ]

    def __str__(self):
        return f"{self.rating}/5 for booking #{self.booking_id}"


class ReportReason(models.TextChoices):
    NO_SHOW = "no_show", "Did not show up"
    UNSAFE = "unsafe", "Unsafe behaviour"
    HARASSMENT = "harassment", "Harassment or abuse"
    FRAUD = "fraud", "Fraud or overcharging"
    POOR_WORK = "poor_work", "Poor or damaging work"
    PAYMENT = "payment_dispute", "Payment dispute"
    OTHER = "other", "Other"


REPORT_REASON_UR = {
    "no_show": "نہیں آئے",
    "unsafe": "غیر محفوظ رویہ",
    "harassment": "بدتمیزی یا ہراسانی",
    "fraud": "دھوکہ یا زیادہ پیسے",
    "poor_work": "خراب یا نقصان دہ کام",
    "payment_dispute": "ادائیگی کا جھگڑا",
    "other": "کچھ اور",
}


class ReportStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    RESOLVED = "RESOLVED", "Resolved"
    DISMISSED = "DISMISSED", "Dismissed"


class Report(models.Model):
    """Private report by one booking participant about the other. Staff-only beyond the reporter."""

    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reports_filed")
    subject = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reports_received")
    reason = models.CharField(max_length=32, choices=ReportReason.choices)
    details = models.TextField(max_length=1000, blank=True)
    status = models.CharField(max_length=16, choices=ReportStatus.choices, default=ReportStatus.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    resolution_note = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["booking", "reporter"], name="one_report_per_participant_per_booking"),
        ]

    def __str__(self):
        return f"Report #{self.pk} ({self.get_reason_display()}, {self.status})"
