# ruff: noqa: EM101, PLR0913, TRY003
from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from audit.services import record_audit_event
from commercial.performance_definitions import DEFAULT_POLICY_VALUES
from commercial.performance_models import SalesScoreEvent
from commercial.performance_models import SalesScorePolicy
from commercial.performance_models import ScoreEventType


def get_active_score_policy(*, at_date=None):
    at_date = at_date or timezone.localdate()
    policy = (
        SalesScorePolicy.objects.filter(is_active=True, valid_from__lte=at_date)
        .order_by("-valid_from")
        .first()
    )
    if policy and policy.valid_until and policy.valid_until < at_date:
        return None
    return policy


def get_policy_points(policy, event_type):
    mapping = {
        ScoreEventType.LEAD_CREATED: policy.points_lead_created,
        ScoreEventType.FIRST_CONTACT: policy.points_first_contact,
        ScoreEventType.LEAD_QUALIFIED: policy.points_lead_qualified,
        ScoreEventType.MEASUREMENT_COMPLETED: policy.points_measurement_completed,
        ScoreEventType.QUOTE_CREATED: policy.points_quote_created,
        ScoreEventType.QUOTE_SENT: policy.points_quote_sent,
        ScoreEventType.FOLLOW_UP_COMPLETED: policy.points_follow_up_completed,
        ScoreEventType.LEAD_WON: policy.points_lead_won,
        ScoreEventType.OVERDUE_FOLLOW_UP_PENALTY: -int(policy.penalty_overdue_follow_up),
        ScoreEventType.UNATTENDED_LEAD_PENALTY: -int(policy.penalty_unattended_lead),
        ScoreEventType.LOST_WITHOUT_REASON_PENALTY: -int(policy.penalty_lost_without_reason),
    }
    return mapping.get(event_type, 0)


def _daily_positive_total(*, salesperson, period_date):
    return (
        SalesScoreEvent.objects.filter(
            salesperson=salesperson,
            period_date=period_date,
            points__gt=0,
        ).aggregate(total=Sum("points"))["total"]
        or 0
    )


def _apply_daily_cap(*, salesperson, period_date, points, policy):
    if points <= 0 or not policy.maximum_daily_score:
        return points
    current = _daily_positive_total(salesperson=salesperson, period_date=period_date)
    remaining = policy.maximum_daily_score - current
    if remaining <= 0:
        return 0
    return min(points, remaining)


def event_exists(*, salesperson, event_type, reference_type, reference_id):
    if reference_id is None:
        return False
    return SalesScoreEvent.objects.filter(
        salesperson=salesperson,
        event_type=event_type,
        reference_type=reference_type,
        reference_id=reference_id,
    ).exists()


@transaction.atomic
def record_score_event(
    *,
    salesperson,
    event_type,
    points=None,
    reference_type="",
    reference_id=None,
    reference_label="",
    occurred_at=None,
    description="",
    actor=None,
    request=None,
    policy=None,
    skip_if_exists=True,
):
    if not salesperson or not salesperson.is_active:
        return None

    occurred_at = occurred_at or timezone.now()
    period_date = timezone.localdate(occurred_at)
    policy = policy or get_active_score_policy(at_date=period_date)
    if not policy:
        return None

    if skip_if_exists and reference_id is not None:
        if event_exists(
            salesperson=salesperson,
            event_type=event_type,
            reference_type=reference_type,
            reference_id=reference_id,
        ):
            return None

    if points is None:
        points = get_policy_points(policy, event_type)
    if points == 0:
        return None

    if event_type != ScoreEventType.MANUAL_ADJUSTMENT and points > 0:
        points = _apply_daily_cap(
            salesperson=salesperson,
            period_date=period_date,
            points=points,
            policy=policy,
        )
        if points == 0:
            return None

    event = SalesScoreEvent.objects.create(
        salesperson=salesperson,
        event_type=event_type,
        points=points,
        reference_type=reference_type,
        reference_id=reference_id,
        reference_label=reference_label,
        occurred_at=occurred_at,
        period_date=period_date,
        description=description,
        policy=policy,
        created_by=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="commercial",
        action="score_event_created",
        obj=event,
        metadata={
            "event_type": event_type,
            "points": points,
            "salesperson_id": salesperson.pk,
        },
    )
    return event


@transaction.atomic
def record_manual_score_adjustment(
    *,
    salesperson,
    points,
    adjustment_date,
    justification,
    actor,
    request=None,
):
    if not (justification or "").strip():
        raise ValidationError("Justificativa é obrigatória para ajuste manual.")
    if points == 0:
        raise ValidationError("Informe pontos positivos ou negativos.")
    policy = get_active_score_policy(at_date=adjustment_date)
    if not policy:
        raise ValidationError("Nenhuma política de score ativa.")
    occurred_at = timezone.make_aware(datetime.combine(adjustment_date, datetime.min.time()))
    event = SalesScoreEvent.objects.create(
        salesperson=salesperson,
        event_type=ScoreEventType.MANUAL_ADJUSTMENT,
        points=points,
        reference_type="manual",
        reference_id=None,
        reference_label=justification[:200],
        occurred_at=occurred_at,
        period_date=adjustment_date,
        description=justification,
        policy=policy,
        created_by=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commercial",
        action="score_manual_adjustment",
        obj=event,
        metadata={"points": points, "justification": justification[:500]},
    )
    return event


def record_sales_value_bonus(*, salesperson, quote, actor=None, request=None):
    policy = get_active_score_policy()
    if not policy or not policy.points_sales_value_factor:
        return None
    bonus = int(Decimal(quote.grand_total) * policy.points_sales_value_factor)
    if bonus <= 0:
        return None
    return record_score_event(
        salesperson=salesperson,
        event_type=ScoreEventType.SALES_VALUE_BONUS,
        points=bonus,
        reference_type="quote",
        reference_id=quote.pk,
        reference_label=quote.number,
        occurred_at=quote.accepted_at or timezone.now(),
        description=f"Bônus por venda {quote.number}",
        actor=actor,
        request=request,
    )


def create_default_score_policy(*, actor=None):
    defaults = {**DEFAULT_POLICY_VALUES, "is_active": True}
    existing = SalesScorePolicy.objects.filter(name=defaults["name"]).first()
    if existing:
        return existing, False
    policy = SalesScorePolicy.objects.create(
        **defaults,
        created_by=actor,
        updated_by=actor,
    )
    return policy, True


def activate_score_policy(*, policy, actor, request=None):
    for other in SalesScorePolicy.objects.filter(is_active=True).exclude(pk=policy.pk):
        if policy._overlaps(other):
            raise ValidationError(f"Conflito de vigência com {other.name}.")
    policy.is_active = True
    policy.updated_by = actor
    policy.save(update_fields=["is_active", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commercial",
        action="score_policy_activated",
        obj=policy,
    )
    return policy
