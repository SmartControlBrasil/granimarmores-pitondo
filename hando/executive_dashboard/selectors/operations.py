from django.db.models import Count
from django.utils import timezone

from production.models import DeliverySchedule
from production.models import InstallationSchedule
from production.models import ScheduleStatus
from scheduling.models import EventStatus
from scheduling.models import EventType
from scheduling.models import OperationalEvent
from scheduling.selectors import schedule_dashboard_metrics


def schedule_metrics(*, user, start, end, filters=None):
    filters = filters or {}
    metrics = schedule_dashboard_metrics(
        user=user,
        start=start,
        end=end,
        assigned_user=filters.get("production_responsible"),
        city=filters.get("city"),
    )
    qs = OperationalEvent.objects.filter(start_at__gte=start, start_at__lte=end)
    if filters.get("city"):
        qs = qs.filter(city__icontains=filters["city"])
    metrics["by_type"] = list(qs.values("event_type").annotate(total=Count("id")).order_by("-total")[:10])
    metrics["by_status"] = list(qs.values("status").annotate(total=Count("id")))
    metrics["cancelled"] = qs.filter(status=EventStatus.CANCELLED).count()
    metrics["rescheduled"] = qs.filter(status=EventStatus.RESCHEDULED).count()
    metrics["no_show"] = qs.filter(status=EventStatus.NO_SHOW).count()
    metrics["technical_visits"] = qs.filter(
        event_type__in=[EventType.TECHNICAL_VISIT, EventType.TECHNICAL_ASSISTANCE],
    ).count()
    return metrics


def delivery_installation_metrics(*, start, end, filters=None):
    filters = filters or {}
    deliveries = DeliverySchedule.objects.filter(
        scheduled_date__gte=timezone.localdate(start),
        scheduled_date__lte=timezone.localdate(end),
    )
    installations = InstallationSchedule.objects.filter(
        scheduled_date__gte=timezone.localdate(start),
        scheduled_date__lte=timezone.localdate(end),
    )
    if filters.get("city"):
        deliveries = deliveries.filter(city__icontains=filters["city"])
        installations = installations.filter(city__icontains=filters["city"])
    if filters.get("salesperson"):
        deliveries = deliveries.filter(sales_order__salesperson_id=filters["salesperson"])
        installations = installations.filter(sales_order__salesperson_id=filters["salesperson"])

    from commercial.performance_metrics import safe_rate

    d_total = deliveries.count() or 0
    i_total = installations.count() or 0
    d_completed = deliveries.filter(status=ScheduleStatus.COMPLETED).count()
    i_completed = installations.filter(status=ScheduleStatus.COMPLETED).count()
    return {
        "deliveries_scheduled": deliveries.filter(
            status__in=[ScheduleStatus.SCHEDULED, ScheduleStatus.PENDING],
        ).count(),
        "deliveries_completed": d_completed,
        "deliveries_rescheduled": deliveries.filter(status=ScheduleStatus.RESCHEDULED).count(),
        "deliveries_failed": deliveries.filter(status=ScheduleStatus.FAILED).count(),
        "deliveries_completion_rate": safe_rate(d_completed, d_total),
        "installations_scheduled": installations.filter(
            status__in=[ScheduleStatus.SCHEDULED, ScheduleStatus.PENDING],
        ).count(),
        "installations_completed": i_completed,
        "installations_with_return": installations.filter(return_required=True).count(),
        "installations_completion_rate": safe_rate(i_completed, i_total),
        "installations_rescheduled": installations.filter(status=ScheduleStatus.RESCHEDULED).count(),
    }
