# ruff: noqa: PLR0913
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from audit.services import record_audit_event
from commissions.models import CommissionPolicy
from commissions.models import CommissionPolicyTier
from commissions.models import CommissionRule
from commissions.models import CommissionType


@transaction.atomic
def create_policy(*, data, tiers=None, rules=None, actor, request=None):
    policy = CommissionPolicy(
        name=data["name"],
        description=data.get("description") or "",
        commission_target=data.get("commission_target") or "salesperson",
        calculation_basis=data.get("calculation_basis") or "net_order_value",
        trigger_type=data.get("trigger_type") or "quote_accepted",
        valid_from=data["valid_from"],
        valid_until=data.get("valid_until"),
        is_active=data.get("is_active", True),
        priority=int(data.get("priority") or 100),
        requires_approval=bool(data.get("requires_approval", False)),
        release_only_after_payment=bool(data.get("release_only_after_payment", True)),
        minimum_margin_percent=data.get("minimum_margin_percent"),
        maximum_discount_percent=data.get("maximum_discount_percent"),
        notes=data.get("notes") or "",
        created_by=actor,
        updated_by=actor,
    )
    policy.full_clean()
    overlaps = detect_policy_overlaps(policy)
    if overlaps:
        raise ValidationError(
            f"Política sobreposta com: {', '.join(p.name for p in overlaps)}",
        )
    policy.save()
    for tier in tiers or []:
        add_tier(policy=policy, data=tier)
    for rule in rules or []:
        add_rule(policy=policy, data=rule, actor=actor)
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="commissions",
        action="create_policy",
        obj=policy,
    )
    return policy


def detect_policy_overlaps(policy, *, exclude_pk=None):
    qs = CommissionPolicy.objects.filter(
        is_active=True,
        commission_target=policy.commission_target,
        trigger_type=policy.trigger_type,
    )
    if exclude_pk or policy.pk:
        qs = qs.exclude(pk=exclude_pk or policy.pk)
    start = policy.valid_from
    end = policy.valid_until
    overlaps = []
    for other in qs:
        other_end = other.valid_until
        if end and other.valid_from > end:
            continue
        if other_end and other_end < start:
            continue
        if other.priority == policy.priority:
            overlaps.append(other)
    return overlaps


def add_tier(*, policy, data):
    tier = CommissionPolicyTier(
        policy=policy,
        sequence=int(data["sequence"]),
        minimum_value=Decimal(str(data.get("minimum_value") or "0")),
        maximum_value=data.get("maximum_value"),
        commission_type=data.get("commission_type") or CommissionType.PERCENTAGE,
        commission_value=Decimal(str(data.get("commission_value") or "0")),
        applies_to_excess=bool(data.get("applies_to_excess", False)),
    )
    if tier.maximum_value is not None:
        tier.maximum_value = Decimal(str(tier.maximum_value))
    tier.full_clean()
    _validate_tier_no_overlap(policy, tier)
    tier.save()
    return tier


def _validate_tier_no_overlap(policy, tier):
    for other in policy.tiers.exclude(pk=tier.pk):
        a0, a1 = tier.minimum_value, tier.maximum_value
        b0, b1 = other.minimum_value, other.maximum_value
        a1 = a1 if a1 is not None else Decimal("999999999")
        b1 = b1 if b1 is not None else Decimal("999999999")
        if a0 <= b1 and b0 <= a1 and not (a1 == b0 or b1 == a0):
            # allow touching boundaries: max == next min
            if a1 == b0 or b1 == a0:
                continue
            if a0 < b1 and b0 < a1:
                raise ValidationError("Faixas de comissão não podem se sobrepor.")


def add_rule(*, policy, data, actor=None):
    rule = CommissionRule(
        policy=policy,
        name=data["name"],
        priority=int(data.get("priority") or 10),
        salesperson=data.get("salesperson"),
        commercial_partner=data.get("commercial_partner"),
        project_type=data.get("project_type"),
        commercial_source=data.get("commercial_source"),
        minimum_order_value=data.get("minimum_order_value"),
        maximum_discount_percent=data.get("maximum_discount_percent"),
        minimum_margin_percent=data.get("minimum_margin_percent"),
        override_commission_type=data.get("override_commission_type") or "",
        override_commission_value=data.get("override_commission_value"),
        is_active=data.get("is_active", True),
        notes=data.get("notes") or "",
    )
    rule.save()
    return rule


@transaction.atomic
def activate_policy(*, policy, actor, request=None):
    policy.is_active = True
    policy.updated_by = actor
    overlaps = detect_policy_overlaps(policy)
    if overlaps:
        raise ValidationError(
            f"Não é possível ativar: sobreposição com {', '.join(p.name for p in overlaps)}",
        )
    policy.save(update_fields=["is_active", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commissions",
        action="activate_policy",
        obj=policy,
    )
    return policy


@transaction.atomic
def deactivate_policy(*, policy, actor, request=None):
    policy.is_active = False
    policy.updated_by = actor
    policy.save(update_fields=["is_active", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commissions",
        action="deactivate_policy",
        obj=policy,
    )
    return policy


def find_applicable_policy(
    *,
    trigger_type,
    target,
    on_date=None,
    salesperson=None,
    partner=None,
    quote=None,
):
    on_date = on_date or timezone.localdate()
    qs = CommissionPolicy.objects.filter(
        is_active=True,
        trigger_type=trigger_type,
        valid_from__lte=on_date,
    ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=on_date))
    if target == "salesperson":
        qs = qs.filter(commission_target__in=["salesperson", "both"])
    elif target == "commercial_partner":
        qs = qs.filter(commission_target__in=["commercial_partner", "both"])
    qs = qs.order_by("priority", "-valid_from")

    # Precedence: salesperson-specific rule → partner/project → general
    best = None
    best_rule = None
    best_score = -1
    for policy in qs:
        rule, score = _match_rule(policy, salesperson=salesperson, partner=partner, quote=quote)
        if score > best_score:
            best = policy
            best_rule = rule
            best_score = score
        elif score == best_score and best and policy.priority < best.priority:
            best = policy
            best_rule = rule
    return best, best_rule


def _match_rule(policy, *, salesperson=None, partner=None, quote=None):
    rules = list(policy.rules.filter(is_active=True).order_by("priority"))
    if not rules:
        return None, 0
    project_type_id = getattr(quote, "project_type_id", None) if quote else None
    source_id = getattr(quote, "commercial_source_id", None) if quote else None
    discount = getattr(quote, "discount_total", None)
    grand = getattr(quote, "grand_total", None) or Decimal("0")
    discount_pct = None
    if grand and discount is not None and grand > 0:
        discount_pct = (Decimal(discount) / Decimal(grand)) * Decimal("100")
    margin = getattr(quote, "gross_margin_percentage", None)

    best_rule = None
    best_score = -1
    for rule in rules:
        score = 1
        if rule.salesperson_id:
            if not salesperson or rule.salesperson_id != salesperson.pk:
                continue
            score += 100
        if rule.commercial_partner_id:
            if not partner or rule.commercial_partner_id != partner.pk:
                continue
            score += 80
        if rule.project_type_id:
            if project_type_id != rule.project_type_id:
                continue
            score += 40
        if rule.commercial_source_id:
            if source_id != rule.commercial_source_id:
                continue
            score += 30
        if rule.minimum_order_value is not None and grand < rule.minimum_order_value:
            continue
        if rule.maximum_discount_percent is not None and discount_pct is not None:
            if discount_pct > rule.maximum_discount_percent:
                continue
        if rule.minimum_margin_percent is not None and margin is not None:
            if Decimal(str(margin)) < rule.minimum_margin_percent:
                continue
        if score > best_score:
            best_score = score
            best_rule = rule
    return best_rule, max(best_score, 0)
