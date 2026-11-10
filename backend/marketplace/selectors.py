"""Query building blocks shared by discovery, quotes, bookings and dashboards."""

from django.db.models import Avg, Count, Exists, F, OuterRef, Prefetch, Subquery, Value

from catalog.models import ServiceArea, Specialty, Trade
from workers.models import WorkerProfile


def with_public_prefetch(qs):
    return qs.prefetch_related(
        Prefetch("trades", queryset=Trade.objects.filter(is_active=True), to_attr="active_trades"),
        Prefetch(
            "specialties",
            queryset=Specialty.objects.filter(is_active=True, trade__is_active=True),
            to_attr="active_specialties",
        ),
        Prefetch("service_areas", queryset=ServiceArea.objects.filter(is_active=True), to_attr="active_areas"),
    )


def worker_stats(user_ids):
    """{user_id: {"rating_avg", "review_count", "completed_jobs"}} from real reviews and
    COMPLETED bookings. A worker with no reviews gets rating_avg=None, review_count=0."""
    from .models import Booking, BookingStatus, Review

    ids = list(user_ids)
    stats = {uid: {"rating_avg": None, "review_count": 0, "completed_jobs": 0} for uid in ids}
    for row in Review.objects.filter(worker_id__in=ids).values("worker_id").annotate(a=Avg("rating"), n=Count("id")):
        stats[row["worker_id"]].update(rating_avg=round(float(row["a"]), 2), review_count=row["n"])
    done = (Booking.objects.filter(worker_id__in=ids, status=BookingStatus.COMPLETED)
            .values("worker_id").annotate(n=Count("id")))
    for row in done:
        stats[row["worker_id"]]["completed_jobs"] = row["n"]
    return stats


def covering(job):
    """Q-filter for worker profiles that still offer this job's trade in its service area
    (both catalog entries active). Used for quote acceptance and quote display."""
    through = WorkerProfile
    return Exists(through.trades.through.objects.filter(
        workerprofile_id=OuterRef("pk"), trade_id=job.trade_id, trade__is_active=True)) & Exists(
        through.service_areas.through.objects.filter(
            workerprofile_id=OuterRef("pk"), servicearea_id=job.service_area_id, servicearea__is_active=True))


def eligible_worker_ids(job, user_ids):
    """Workers who could be booked for `job` right now: available AND still covering it."""
    return set(WorkerProfile.objects.available().filter(covering(job), user_id__in=list(user_ids))
               .values_list("pk", flat=True))


def _rating_subquery():
    from .models import Review

    return Subquery(
        Review.objects.filter(worker_id=OuterRef("pk")).values("worker_id")
        .annotate(a=Avg("rating")).values("a")[:1]
    )


def discover(trade, service_area, specialty=None):
    """Available workers for a trade + area. Specialty matches rank first; generalists stay in."""
    through = WorkerProfile
    qs = WorkerProfile.objects.available().filter(
        Exists(through.trades.through.objects.filter(workerprofile_id=OuterRef("pk"), trade_id=trade.id)),
        Exists(through.service_areas.through.objects.filter(
            workerprofile_id=OuterRef("pk"), servicearea_id=service_area.id)),
    )
    if specialty is not None:
        qs = qs.annotate(matches_specialty=Exists(through.specialties.through.objects.filter(
            workerprofile_id=OuterRef("pk"), specialty_id=specialty.id)))
    else:
        qs = qs.annotate(matches_specialty=Value(False))
    qs = qs.annotate(rating_avg=_rating_subquery())
    # specialty match first, then rating (unrated last), then a stable tie-break
    return with_public_prefetch(qs.order_by("-matches_specialty", F("rating_avg").desc(nulls_last=True), "pk"))
