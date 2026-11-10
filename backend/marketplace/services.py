"""State transitions for quotes, bookings and arrival PINs.

Every transition runs in a PostgreSQL transaction and re-reads state after
taking row locks. Lock order is always: JobRequest -> WorkerProfile -> Booking.

Errors that must persist something (failed PIN attempts, expired PIN revocation)
return from the atomic block first and raise afterwards, so the write commits.
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework import status

from config.api import ApiError, conflict
from workers.models import WorkerProfile

from . import access, selectors
from .models import ArrivalPin, Booking, BookingStatus, JobRequest, Quote, Report, Review


def _not_found():
    return ApiError("Not found.", "not_found", status.HTTP_404_NOT_FOUND)


def _worker_unavailable():
    return conflict(
        "This worker is not available right now (busy, paused, or profile incomplete).", "worker_unavailable"
    )


# ------------------------------------------------------------------ quotes ---

def submit_quote(worker, job_id, amount, message=""):
    """Returns (quote, created). Identical retries return the existing quote."""
    with transaction.atomic():
        job = JobRequest.objects.select_for_update().filter(pk=job_id).first()
        if job is None:
            raise _not_found()
        existing = Quote.objects.filter(job=job, worker=worker).first()
        if access.relation(worker, job) != access.ELIGIBLE_WORKER:
            if existing is not None and job.booking_or_none is not None:
                raise conflict("This request is no longer open.", "request_not_open")
            raise _not_found()
        if existing is not None:
            if existing.amount == amount and existing.message == message:
                return existing, False
            raise conflict("You already sent a quote for this request.", "quote_exists", quote_id=existing.pk)
        if not WorkerProfile.objects.available().filter(user=worker).exists():
            raise _worker_unavailable()
        try:
            with transaction.atomic():
                quote = Quote.objects.create(job=job, worker=worker, amount=amount, message=message)
        except IntegrityError:
            raise conflict("You already sent a quote for this request.", "quote_exists") from None
        return quote, True


# ---------------------------------------------------------------- bookings ---

def accept_quote(customer, quote_id):
    """Returns (booking, created). A same-quote retry returns the existing booking."""
    with transaction.atomic():
        quote = Quote.objects.filter(pk=quote_id, job__customer=customer).first()
        if quote is None:
            raise _not_found()
        # Lock order: request, then worker.
        job = JobRequest.objects.select_for_update().get(pk=quote.job_id)
        WorkerProfile.objects.select_for_update().filter(user_id=quote.worker_id).first()

        existing = Booking.objects.filter(job=job).first()
        if existing is not None:
            if existing.quote_id == quote.pk:
                return existing, False
            raise conflict("Another quote was already accepted for this request.", "request_already_booked")
        if not WorkerProfile.objects.available().filter(user_id=quote.worker_id).exists():
            raise _worker_unavailable()
        # Re-read the profile's coverage under the lock: the worker may have dropped
        # this trade or area after quoting.
        if not WorkerProfile.objects.filter(selectors.covering(job), user_id=quote.worker_id).exists():
            raise conflict(
                "This worker no longer offers this trade in this service area.", "worker_not_eligible"
            )
        try:
            with transaction.atomic():
                booking = Booking.objects.create(
                    job=job, quote=quote, worker_id=quote.worker_id, customer=customer, amount=quote.amount
                )
        except IntegrityError:  # constraint backstop for any race the locks did not cover
            raise _worker_unavailable() from None
        return booking, True


def _locked_booking(pk, **owner):
    booking = Booking.objects.select_for_update().filter(pk=pk, **owner).first()
    if booking is None:
        raise _not_found()
    return booking


def _wrong_status(booking):
    return conflict(f"Not allowed while the booking is {booking.status}.", "invalid_booking_status",
                    status=booking.status)


# ------------------------------------------------------------- arrival PIN ---

def _pin_digest(booking_id, pin):
    return salted_hmac("roshan_rozgar.arrival_pin", f"{booking_id}:{pin}", algorithm="sha256").hexdigest()


def live_pin(booking):
    return booking.pins.filter(consumed_at__isnull=True, revoked_at__isnull=True).first()


def issue_pin(customer, booking_id):
    """Returns (pin, ArrivalPin). The plain PIN exists only in this response."""
    now = timezone.now()
    with transaction.atomic():
        booking = _locked_booking(booking_id, customer=customer)
        if booking.status != BookingStatus.BOOKED:
            raise _wrong_status(booking)
        window_start = now - timedelta(seconds=settings.PIN_ISSUE_WINDOW_SECONDS)
        if booking.pins.filter(created_at__gte=window_start).count() >= settings.PIN_ISSUE_LIMIT:
            raise ApiError("Too many PINs issued. Wait a few minutes and try again.", "pin_issue_throttled",
                           status.HTTP_429_TOO_MANY_REQUESTS)
        booking.pins.filter(consumed_at__isnull=True, revoked_at__isnull=True).update(revoked_at=now)
        pin = f"{secrets.randbelow(1_000_000):06d}"
        record = ArrivalPin.objects.create(
            booking=booking, digest=_pin_digest(booking.pk, pin),
            expires_at=now + timedelta(seconds=settings.PIN_TTL_SECONDS),
        )
    return pin, record


def check_in(worker, booking_id, pin):
    now = timezone.now()
    error = None
    with transaction.atomic():
        booking = _locked_booking(booking_id, worker=worker)
        if booking.status != BookingStatus.BOOKED:
            raise _wrong_status(booking)
        record = live_pin(booking)
        if record is None:
            raise conflict("Ask the customer to share a new arrival PIN.", "no_active_pin")
        if record.expires_at <= now:
            record.revoked_at = now
            record.save(update_fields=["revoked_at"])
            error = conflict("This PIN has expired. Ask the customer for a new one.", "pin_expired")
        elif not constant_time_compare(record.digest, _pin_digest(booking.pk, pin)):
            record.failed_attempts += 1
            remaining = settings.PIN_MAX_ATTEMPTS - record.failed_attempts
            if remaining <= 0:
                record.revoked_at = now
                error = conflict("Too many wrong tries. Ask the customer for a new PIN.", "pin_locked")
            else:
                error = ApiError("Wrong PIN.", "pin_incorrect", status.HTTP_400_BAD_REQUEST,
                                 attempts_remaining=remaining)
            record.save(update_fields=["failed_attempts", "revoked_at"])
        else:
            record.consumed_at = now
            record.save(update_fields=["consumed_at"])
            booking.status = BookingStatus.IN_PROGRESS
            booking.checked_in_at = now
            booking.save(update_fields=["status", "checked_in_at", "updated_at"])
    if error is not None:
        raise error  # raised after commit so the attempt counter / revocation persists
    return booking


def complete(worker, booking_id):
    """Idempotent: completing an already-completed booking returns it unchanged."""
    with transaction.atomic():
        booking = _locked_booking(booking_id, worker=worker)
        if booking.status == BookingStatus.COMPLETED:
            return booking
        if booking.status != BookingStatus.IN_PROGRESS:
            raise conflict("Check in with the customer's PIN before completing.", "check_in_required")
        booking.status = BookingStatus.COMPLETED
        booking.completed_at = timezone.now()
        booking.save(update_fields=["status", "completed_at", "updated_at"])
    return booking


# ------------------------------------------------------ reviews / reports ---

def create_review(customer, booking_id, rating, text="", tags=()):
    with transaction.atomic():
        booking = _locked_booking(booking_id, customer=customer)
        if booking.status != BookingStatus.COMPLETED:
            raise conflict("You can review only after the job is completed.", "booking_not_completed")
        if Review.objects.filter(booking=booking).exists():
            raise conflict("You already reviewed this job.", "review_exists")
        try:
            with transaction.atomic():
                return Review.objects.create(
                    booking=booking, customer_id=booking.customer_id, worker_id=booking.worker_id,
                    rating=rating, text=text, tags=list(tags),
                )
        except IntegrityError:
            raise conflict("You already reviewed this job.", "review_exists") from None


def create_report(user, booking_id, reason, details=""):
    booking = Booking.objects.filter(pk=booking_id).first()
    if booking is None or user.id not in (booking.customer_id, booking.worker_id):
        raise _not_found()
    subject_id = booking.worker_id if user.id == booking.customer_id else booking.customer_id
    try:
        with transaction.atomic():
            return Report.objects.create(
                booking=booking, reporter=user, subject_id=subject_id, reason=reason, details=details
            )
    except IntegrityError:
        raise conflict("You already reported this booking. Staff will review it.", "report_exists") from None
