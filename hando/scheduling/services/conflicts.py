# ruff: noqa: EM101, PLR0913, TRY003
from django.db.models import Q
from django.utils import timezone

from scheduling.models import ACTIVE_CONFLICT_STATUSES
from scheduling.models import EventStatus
from scheduling.models import OperationalEvent


def _effective_end(start_at, end_at, all_day=False):
    if end_at:
        return end_at
    if all_day:
        return timezone.localtime(start_at).replace(
            hour=23,
            minute=59,
            second=59,
            microsecond=0,
        )
    return start_at


def ranges_overlap(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


def check_schedule_conflicts(
    *,
    start_at,
    end_at,
    assigned_user=None,
    assigned_salesperson=None,
    vehicle=None,
    exclude_event=None,
    all_day=False,
):
    end_at = _effective_end(start_at, end_at, all_day=all_day)
    qs = OperationalEvent.objects.filter(status__in=ACTIVE_CONFLICT_STATUSES)
    if exclude_event and exclude_event.pk:
        qs = qs.exclude(pk=exclude_event.pk)

    conflicts = []
    filters = Q()
    if assigned_user:
        filters |= Q(assigned_user=assigned_user)
    if assigned_salesperson:
        filters |= Q(assigned_salesperson=assigned_salesperson)
    if vehicle:
        filters |= Q(vehicle=vehicle)
    if not filters:
        return []

    candidates = qs.filter(filters).select_related(
        "assigned_user",
        "assigned_salesperson",
        "vehicle",
    )
    for event in candidates:
        other_end = _effective_end(event.start_at, event.end_at, all_day=event.all_day)
        if ranges_overlap(start_at, end_at, event.start_at, other_end):
            reason_parts = []
            if assigned_user and event.assigned_user_id == getattr(assigned_user, "pk", None):
                reason_parts.append("usuário")
            if assigned_salesperson and event.assigned_salesperson_id == getattr(
                assigned_salesperson,
                "pk",
                None,
            ):
                reason_parts.append("vendedor")
            if vehicle and event.vehicle_id == getattr(vehicle, "pk", None):
                reason_parts.append("veículo")
            conflicts.append(
                {
                    "event": event,
                    "reasons": reason_parts or ["sobreposição"],
                    "message": (
                        f"Conflito com {event.code} ({', '.join(reason_parts) or 'agenda'})"
                    ),
                },
            )
    return conflicts
