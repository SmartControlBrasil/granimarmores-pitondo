from decimal import Decimal

from django.db.models import Count
from django.db.models import Q
from django.db.models import Sum
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from commissions.models import CommissionEvent
from commissions.models import CommissionPolicy
from commissions.models import CommissionSettlement
from commissions.models import EventStatus
from commissions.models import EventType
from commissions.models import SettlementStatus
from quotes.models import Quote
from quotes.models import QuoteStatus
from salespeople.models import Salesperson


def _salesperson_for_user(user):
    return getattr(user, "salesperson", None)


def events_queryset_for_user(user):
    qs = CommissionEvent.objects.select_related(
        "salesperson",
        "commercial_partner",
        "policy",
        "quote",
        "sales_order",
    )
    if user_has_permission(user, "commission_events.view") or user_has_permission(
        user,
        "commission_dashboard.view",
    ):
        return qs
    if user_has_permission(user, "commission_events.view_own"):
        sp = _salesperson_for_user(user)
        if sp:
            return qs.filter(salesperson=sp)
    return qs.none()


def settlements_queryset_for_user(user):
    qs = CommissionSettlement.objects.select_related("salesperson", "commercial_partner", "payable")
    if user_has_permission(user, "commission_settlements.view"):
        return qs
    if user_has_permission(user, "commission_events.view_own"):
        sp = _salesperson_for_user(user)
        if sp:
            return qs.filter(salesperson=sp)
    return qs.none()


def beneficiary_balance(*, salesperson=None, partner=None):
    qs = CommissionEvent.objects.exclude(status__in=[EventStatus.REVERSED, EventStatus.CANCELLED])
    if salesperson:
        qs = qs.filter(salesperson=salesperson)
    if partner:
        qs = qs.filter(commercial_partner=partner)

    def _sum(event_types):
        return qs.filter(event_type__in=event_types).aggregate(v=Sum("commission_amount"))["v"] or Decimal(
            "0.00",
        )

    provisioned = _sum([EventType.PROVISION])
    released = _sum([EventType.RELEASE, EventType.ADJUSTMENT_POSITIVE])
    paid = _sum([EventType.PAYMENT])
    reversed_amt = _sum([EventType.REVERSAL, EventType.ADJUSTMENT_NEGATIVE, EventType.CHARGEBACK])
    available = released - paid - _sum([EventType.ADJUSTMENT_NEGATIVE, EventType.CHARGEBACK])
    if available < 0:
        available = Decimal("0.00")
    blocked = qs.filter(status=EventStatus.BLOCKED).aggregate(v=Sum("commission_amount"))["v"] or Decimal(
        "0.00",
    )
    return {
        "provisioned": provisioned,
        "available": available,
        "paid": paid,
        "reversed": reversed_amt,
        "blocked": blocked,
        "balance": available,
    }


def commission_dashboard_metrics(*, user, start, end):
    can_values = user_has_permission(user, "commission_values.view") or user_has_permission(
        user,
        "commission_dashboard.view",
    )
    events = events_queryset_for_user(user).filter(event_date__gte=start, event_date__lte=end)

    def _sum(qs):
        return qs.aggregate(v=Sum("commission_amount"))["v"] or Decimal("0.00")

    provisioned = _sum(events.filter(event_type=EventType.PROVISION))
    available = _sum(events.filter(event_type=EventType.RELEASE, status=EventStatus.AVAILABLE))
    pending_approval = events.filter(status=EventStatus.PENDING_APPROVAL).count()
    paid = _sum(events.filter(event_type=EventType.PAYMENT))
    reversed_amt = _sum(events.filter(event_type=EventType.REVERSAL))
    blocked = events.filter(status=EventStatus.BLOCKED).count()
    open_balance = available

    settlements_pending = settlements_queryset_for_user(user).filter(
        status__in=[SettlementStatus.UNDER_REVIEW, SettlementStatus.DRAFT],
    ).count()
    settlements_no_payable = settlements_queryset_for_user(user).filter(
        status=SettlementStatus.APPROVED,
        payable__isnull=True,
    ).count()

    accepted = Quote.objects.filter(
        status=QuoteStatus.ACCEPTED,
        accepted_at__date__gte=start,
        accepted_at__date__lte=end,
    )
    without_policy = 0
    for q in accepted[:200]:
        if not CommissionEvent.objects.filter(quote=q, event_type=EventType.PROVISION).exists():
            without_policy += 1

    by_salesperson = list(
        events.filter(event_type=EventType.PROVISION)
        .values("salesperson__display_name")
        .annotate(total=Sum("commission_amount"))
        .order_by("-total")[:10],
    )
    by_partner = list(
        events.filter(event_type=EventType.PROVISION, commercial_partner__isnull=False)
        .values("commercial_partner__name")
        .annotate(total=Sum("commission_amount"))
        .order_by("-total")[:10],
    )

    return {
        "provisioned": provisioned if can_values else None,
        "available": available if can_values else None,
        "pending_approval": pending_approval,
        "paid": paid if can_values else None,
        "reversed": reversed_amt if can_values else None,
        "open_balance": open_balance if can_values else None,
        "blocked": blocked,
        "settlements_pending": settlements_pending,
        "settlements_no_payable": settlements_no_payable,
        "sales_without_policy": without_policy,
        "by_salesperson": by_salesperson if can_values else [],
        "by_partner": by_partner if can_values else [],
        "can_values": can_values,
        "salespeople_with_commission": events.filter(salesperson__isnull=False)
        .values("salesperson")
        .distinct()
        .count(),
        "partners_with_commission": events.filter(commercial_partner__isnull=False)
        .values("commercial_partner")
        .distinct()
        .count(),
    }


def main_dashboard_commissions_summary(user):
    sp = _salesperson_for_user(user)
    if user_has_permission(user, "commission_events.view_own") and sp and not user_has_permission(
        user,
        "commission_dashboard.view",
    ):
        bal = beneficiary_balance(salesperson=sp)
        last = (
            CommissionSettlement.objects.filter(salesperson=sp)
            .exclude(status=SettlementStatus.CANCELLED)
            .order_by("-created_at")
            .first()
        )
        return {
            "mode": "salesperson",
            "available": bal["available"],
            "provisioned": bal["provisioned"],
            "last_settlement": last.number if last else "—",
        }
    if user_has_permission(user, "commission_dashboard.view") or user_has_permission(
        user,
        "commission_settlements.approve",
    ):
        today = timezone.localdate()
        start = today.replace(day=1)
        pending = CommissionSettlement.objects.filter(
            status__in=[SettlementStatus.UNDER_REVIEW, SettlementStatus.DRAFT],
        ).count()
        open_available = (
            CommissionEvent.objects.filter(
                event_type=EventType.RELEASE,
                status=EventStatus.AVAILABLE,
            ).aggregate(v=Sum("commission_amount"))["v"]
            or Decimal("0.00")
        )
        without = 0
        for q in Quote.objects.filter(status=QuoteStatus.ACCEPTED, accepted_at__date__gte=start)[:100]:
            if not CommissionEvent.objects.filter(quote=q, event_type=EventType.PROVISION).exists():
                without += 1
        return {
            "mode": "manager",
            "pending_commission": open_available,
            "settlements_pending": pending,
            "sales_without_policy": without,
        }
    return None


def executive_commission_metrics(*, user, start, end):
    if not (
        user_has_permission(user, "executive_dashboard.view_commissions")
        or user_has_permission(user, "executive_dashboard.view")
        or user_has_permission(user, "commission_values.view")
    ):
        return {}
    m = commission_dashboard_metrics(user=user, start=start, end=end)
    return {
        "provisioned": m.get("provisioned") or Decimal("0"),
        "available": m.get("available") or Decimal("0"),
        "paid": m.get("paid") or Decimal("0"),
        "reversed": m.get("reversed") or Decimal("0"),
        "sales_without_policy": m.get("sales_without_policy") or 0,
        "settlements_pending": m.get("settlements_pending") or 0,
    }


def policies_queryset():
    return CommissionPolicy.objects.prefetch_related("tiers", "rules").order_by("priority", "name")
