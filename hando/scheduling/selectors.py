# ruff: noqa: PLR0913
from datetime import datetime
from datetime import timedelta

from django.conf import settings
from django.db.models import Count
from django.db.models import Q
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from scheduling.models import ACTIVE_CONFLICT_STATUSES
from scheduling.models import ConfirmationStatus
from scheduling.models import EventStatus
from scheduling.models import EventType
from scheduling.models import OperationalEvent
from scheduling.services.conflicts import check_schedule_conflicts


def events_queryset_for_user(user):
    qs = OperationalEvent.objects.select_related(
        "assigned_user",
        "assigned_salesperson",
        "customer",
        "lead",
        "sales_order",
        "vehicle",
        "delivery_schedule",
        "installation_schedule",
    )
    if user_has_permission(user, "operational_events.view_all"):
        return qs
    if not user_has_permission(user, "operational_events.view"):
        return qs.none()
    salesperson = getattr(user, "salesperson", None)
    filters = Q(assigned_user=user) | Q(created_by=user)
    if salesperson:
        filters |= Q(assigned_salesperson=salesperson)
    return qs.filter(filters)


def filter_events(qs, params):
    if params.get("event_type"):
        qs = qs.filter(event_type=params["event_type"])
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("priority"):
        qs = qs.filter(priority=params["priority"])
    if params.get("assigned_user"):
        qs = qs.filter(assigned_user_id=params["assigned_user"])
    if params.get("salesperson"):
        qs = qs.filter(assigned_salesperson_id=params["salesperson"])
    if params.get("vehicle"):
        qs = qs.filter(vehicle_id=params["vehicle"])
    if params.get("customer"):
        qs = qs.filter(customer_id=params["customer"])
    if params.get("city"):
        qs = qs.filter(city__icontains=params["city"])
    if params.get("unconfirmed") == "1":
        qs = qs.filter(confirmation_status=ConfirmationStatus.PENDING).exclude(
            status__in=[EventStatus.COMPLETED, EventStatus.CANCELLED],
        )
    if params.get("overdue") == "1":
        now = timezone.now()
        qs = qs.filter(end_at__lt=now).exclude(
            status__in=[EventStatus.COMPLETED, EventStatus.CANCELLED, EventStatus.NO_SHOW],
        )
    if params.get("delivery") == "1":
        qs = qs.filter(event_type=EventType.DELIVERY)
    if params.get("installation") == "1":
        qs = qs.filter(event_type=EventType.INSTALLATION)
    if params.get("measurement") == "1":
        qs = qs.filter(event_type=EventType.MEASUREMENT)
    start = params.get("start")
    end = params.get("end")
    if start:
        qs = qs.filter(start_at__date__gte=start)
    if end:
        qs = qs.filter(start_at__date__lte=end)
    return qs


def calendar_events_payload(qs):
    payload = []
    for event in qs:
        color = {
            "urgent": "event-danger border-danger",
            "high": "event-warning border-warning",
            "normal": "event-primary border-primary",
            "low": "event-secondary border-secondary",
        }.get(event.priority, "event-primary border-primary")
        payload.append(
            {
                "id": event.pk,
                "title": f"{event.start_at.strftime('%H:%M')} {event.title}",
                "start": event.start_at.isoformat(),
                "end": (event.end_at or event.start_at).isoformat(),
                "allDay": event.all_day,
                "url": f"/painel/agenda/eventos/{event.pk}/",
                "className": color,
                "extendedProps": {
                    "code": event.code,
                    "type": event.get_event_type_display(),
                    "status": event.get_status_display(),
                    "priority": event.get_priority_display(),
                    "responsible": str(event.assigned_user or event.assigned_salesperson or "—"),
                    "customer": str(event.customer or "—"),
                },
            },
        )
    return payload


def schedule_dashboard_metrics(*, user, start=None, end=None, assigned_user=None, event_type=None, city=None):
    now = timezone.now()
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    qs = events_queryset_for_user(user)
    if start:
        qs = qs.filter(start_at__gte=start)
    if end:
        qs = qs.filter(start_at__lte=end)
    if assigned_user:
        qs = qs.filter(assigned_user_id=assigned_user)
    if event_type:
        qs = qs.filter(event_type=event_type)
    if city:
        qs = qs.filter(city__icontains=city)

    warning_hours = getattr(settings, "AGENDA_CONFIRMATION_WARNING_HOURS", 24)
    confirm_deadline = now + timedelta(hours=warning_hours)

    today_qs = qs.filter(start_at__date=today)
    return {
        "today": today_qs.count(),
        "tomorrow": qs.filter(start_at__date=tomorrow).count(),
        "unconfirmed": qs.filter(
            confirmation_status=ConfirmationStatus.PENDING,
            start_at__lte=confirm_deadline,
        ).exclude(status__in=[EventStatus.COMPLETED, EventStatus.CANCELLED]).count(),
        "overdue": qs.filter(end_at__lt=now).exclude(
            status__in=[EventStatus.COMPLETED, EventStatus.CANCELLED, EventStatus.NO_SHOW],
        ).count(),
        "in_progress": qs.filter(status=EventStatus.IN_PROGRESS).count(),
        "measurements": qs.filter(event_type=EventType.MEASUREMENT).count(),
        "deliveries": qs.filter(event_type=EventType.DELIVERY).count(),
        "installations": qs.filter(event_type=EventType.INSTALLATION).count(),
        "visits": qs.filter(event_type=EventType.TECHNICAL_VISIT).count(),
        "cancelled": qs.filter(status=EventStatus.CANCELLED).count(),
        "rescheduled": qs.filter(status=EventStatus.RESCHEDULED).count(),
        "no_show": qs.filter(status=EventStatus.NO_SHOW).count(),
        "by_city": list(
            qs.exclude(city="")
            .values("city")
            .annotate(total=Count("id"))
            .order_by("-total")[:10],
        ),
        "by_responsible": list(
            qs.filter(assigned_user__isnull=False)
            .values("assigned_user__username")
            .annotate(total=Count("id"))
            .order_by("-total")[:10],
        ),
        "completion_rate": _rate(qs.filter(status=EventStatus.COMPLETED).count(), qs.count()),
        "cancellation_rate": _rate(qs.filter(status=EventStatus.CANCELLED).count(), qs.count()),
        "no_show_rate": _rate(qs.filter(status=EventStatus.NO_SHOW).count(), qs.count()),
        "conflicts": count_active_conflicts(qs),
        "alerts": build_schedule_alerts(user),
    }


def _rate(part, total):
    if not total:
        return 0
    return round((part / total) * 100, 1)


def count_active_conflicts(qs):
    active = list(qs.filter(status__in=ACTIVE_CONFLICT_STATUSES)[:200])
    seen = set()
    count = 0
    for event in active:
        conflicts = check_schedule_conflicts(
            start_at=event.start_at,
            end_at=event.end_at,
            assigned_user=event.assigned_user,
            assigned_salesperson=event.assigned_salesperson,
            vehicle=event.vehicle,
            exclude_event=event,
            all_day=event.all_day,
        )
        for item in conflicts:
            key = tuple(sorted((event.pk, item["event"].pk)))
            if key not in seen:
                seen.add(key)
                count += 1
    return count


def build_schedule_alerts(user):
    alerts = []
    qs = events_queryset_for_user(user).exclude(
        status__in=[EventStatus.COMPLETED, EventStatus.CANCELLED],
    )
    now = timezone.now()
    warning_hours = getattr(settings, "AGENDA_CONFIRMATION_WARNING_HOURS", 24)

    no_resp = qs.filter(assigned_user__isnull=True, assigned_salesperson__isnull=True).count()
    if no_resp:
        alerts.append({"level": "warning", "message": f"{no_resp} evento(s) sem responsável"})

    from scheduling.models import ADDRESS_REQUIRED_TYPES

    no_addr = qs.filter(event_type__in=ADDRESS_REQUIRED_TYPES).filter(
        Q(address="") | Q(city=""),
    ).count()
    if no_addr:
        alerts.append({"level": "warning", "message": f"{no_addr} evento(s) sem endereço"})

    overdue = qs.filter(end_at__lt=now).count()
    if overdue:
        alerts.append({"level": "danger", "message": f"{overdue} evento(s) atrasado(s)"})

    unconfirmed = qs.filter(
        confirmation_status=ConfirmationStatus.PENDING,
        start_at__lte=now + timedelta(hours=warning_hours),
        start_at__gte=now,
    ).count()
    if unconfirmed:
        alerts.append(
            {
                "level": "info",
                "message": f"{unconfirmed} evento(s) não confirmado(s) próximos",
            },
        )

    delivery_no_vehicle = qs.filter(event_type=EventType.DELIVERY, vehicle__isnull=True).count()
    if delivery_no_vehicle:
        alerts.append(
            {
                "level": "info",
                "message": f"{delivery_no_vehicle} entrega(s) sem veículo",
            },
        )

    conflicts = count_active_conflicts(qs)
    if conflicts:
        alerts.append({"level": "danger", "message": f"{conflicts} conflito(s) de agenda"})

    return alerts


def main_dashboard_schedule_summary(user):
    today = timezone.localdate()
    qs = events_queryset_for_user(user)
    now = timezone.now()
    return {
        "today": qs.filter(start_at__date=today).count(),
        "unconfirmed": qs.filter(
            confirmation_status=ConfirmationStatus.PENDING,
        ).exclude(status__in=[EventStatus.COMPLETED, EventStatus.CANCELLED]).count(),
        "conflicts": count_active_conflicts(
            qs.filter(start_at__date__gte=today - timedelta(days=1), start_at__date__lte=today + timedelta(days=7)),
        ),
        "deliveries_today": qs.filter(
            event_type=EventType.DELIVERY,
            start_at__date=today,
        ).count(),
        "installations_today": qs.filter(
            event_type=EventType.INSTALLATION,
            start_at__date=today,
        ).count(),
    }


def parse_period(request):
    period = request.GET.get("period", "month")
    now = timezone.now()
    today = timezone.localdate()
    if period == "today":
        start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        end = timezone.make_aware(datetime.combine(today, datetime.max.time()))
    elif period == "7d":
        start = now - timedelta(days=7)
        end = now + timedelta(days=7)
    elif period == "30d":
        start = now - timedelta(days=30)
        end = now + timedelta(days=30)
    elif period == "custom":
        start_s = request.GET.get("start")
        end_s = request.GET.get("end")
        start = timezone.make_aware(datetime.fromisoformat(start_s)) if start_s else now - timedelta(days=30)
        end = timezone.make_aware(datetime.fromisoformat(end_s)) if end_s else now
    else:
        start = now - timedelta(days=15)
        end = now + timedelta(days=45)
    return start, end, period
