"""Query building blocks shared by discovery, quotes, bookings and dashboards."""

from django.db.models import Exists, OuterRef, Prefetch, Value

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
    """{user_id: {"rating_avg", "review_count", "completed_jobs"}} — filled in by Phase 6."""
    return {uid: {"rating_avg": None, "review_count": 0, "completed_jobs": 0} for uid in user_ids}


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
    return with_public_prefetch(qs.order_by("-matches_specialty", "pk"))
