"""Who may see what. Every view goes through these helpers so the rules live in one place."""

from workers.models import WorkerProfile

from .models import JobRequest

OWNER = "owner"
ASSIGNED_WORKER = "assigned_worker"
ELIGIBLE_WORKER = "eligible_worker"


def complete_profile(user):
    """The signed-in worker's onboarded profile, or None."""
    if not user.is_authenticated or user.role != "worker":
        return None
    return WorkerProfile.objects.complete().filter(user=user).first()


def board_queryset(profile):
    """Open requests in the worker's active trades and active service areas."""
    return JobRequest.objects.open().filter(
        trade__in=profile.trades.filter(is_active=True).values("id"),
        service_area__in=profile.service_areas.filter(is_active=True).values("id"),
    )


def relation(user, job):
    """How `user` relates to `job`: OWNER, ASSIGNED_WORKER, ELIGIBLE_WORKER or None.

    - the owner always sees everything;
    - once booked, only the assigned worker (not other quoters) keeps access;
    - while open, any onboarded worker covering the trade and area can view it.
    """
    if not user.is_authenticated:
        return None
    if job.customer_id == user.id:
        return OWNER
    booking = job.booking_or_none
    if booking is not None:
        return ASSIGNED_WORKER if booking.worker_id == user.id else None
    profile = complete_profile(user)
    if profile and board_queryset(profile).filter(pk=job.pk).exists():
        return ELIGIBLE_WORKER
    return None
