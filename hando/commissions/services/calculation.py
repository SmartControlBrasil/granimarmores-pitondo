from decimal import Decimal

from django.core.exceptions import ValidationError

from commissions.models import CalculationBasis
from commissions.models import CommissionType


def resolve_basis_amount(*, policy, quote=None, sales_order=None, received_amount=None):
    basis = policy.calculation_basis
    if basis == CalculationBasis.RECEIVED_VALUE:
        return Decimal(str(received_amount or "0"))
    if sales_order:
        if basis == CalculationBasis.GROSS_ORDER_VALUE:
            return Decimal(str(sales_order.subtotal or sales_order.total or "0"))
        return Decimal(str(sales_order.total or "0"))
    if quote:
        if basis == CalculationBasis.GROSS_ORDER_VALUE:
            return Decimal(str(getattr(quote, "subtotal", None) or quote.grand_total or "0"))
        if basis == CalculationBasis.MARGIN_VALUE:
            return Decimal(str(getattr(quote, "gross_profit", None) or "0"))
        if basis == CalculationBasis.SERVICE_VALUE:
            return Decimal(str(getattr(quote, "services_total", None) or "0"))
        return Decimal(str(quote.grand_total or "0"))
    return Decimal("0.00")


def _tier_matches(tier, basis_amount):
    lo = tier.minimum_value
    hi = tier.maximum_value
    if basis_amount < lo:
        return False
    if hi is None:
        return True
    return basis_amount <= hi


def calculate_commission_amount(*, policy, rule, basis_amount):
    basis_amount = Decimal(str(basis_amount or "0"))
    if basis_amount < 0:
        raise ValidationError("Base de cálculo não pode ser negativa.")

    if rule and rule.override_commission_type and rule.override_commission_value is not None:
        ctype = rule.override_commission_type
        cvalue = Decimal(str(rule.override_commission_value))
        if ctype == CommissionType.FIXED_AMOUNT:
            return cvalue, Decimal("0")
        return (basis_amount * cvalue / Decimal("100")).quantize(Decimal("0.01")), cvalue

    tiers = list(policy.tiers.order_by("sequence", "minimum_value"))
    if not tiers:
        return Decimal("0.00"), Decimal("0")

    # Faixas clássicas: uma faixa correspondente ao valor total
    for tier in tiers:
        if not _tier_matches(tier, basis_amount):
            continue
        if tier.commission_type == CommissionType.FIXED_AMOUNT:
            return tier.commission_value, Decimal("0")
        rate = tier.commission_value
        return (basis_amount * rate / Decimal("100")).quantize(Decimal("0.01")), rate

    return Decimal("0.00"), Decimal("0")


def check_policy_restrictions(*, policy, quote=None):
    reasons = []
    if not quote:
        return reasons
    margin = getattr(quote, "gross_margin_percentage", None)
    if policy.minimum_margin_percent is not None and margin is not None:
        if Decimal(str(margin)) < policy.minimum_margin_percent:
            reasons.append(
                f"Margem {margin}% abaixo do mínimo {policy.minimum_margin_percent}%",
            )
    discount = getattr(quote, "discount_total", None) or Decimal("0")
    grand = getattr(quote, "grand_total", None) or Decimal("0")
    if policy.maximum_discount_percent is not None and grand > 0:
        pct = (Decimal(discount) / Decimal(grand)) * Decimal("100")
        if pct > policy.maximum_discount_percent:
            reasons.append(
                f"Desconto {pct.quantize(Decimal('0.01'))}% acima do máximo "
                f"{policy.maximum_discount_percent}%",
            )
    return reasons


def simulate_commission(
    *,
    value,
    trigger_type="quote_accepted",
    target="salesperson",
    on_date=None,
    salesperson=None,
    partner=None,
    margin=None,
    discount=None,
    quote=None,
):
    from commissions.services.policies import find_applicable_policy

    class _FakeQuote:
        def __init__(self):
            self.grand_total = Decimal(str(value))
            self.subtotal = Decimal(str(value))
            self.gross_profit = Decimal("0")
            self.gross_margin_percentage = Decimal(str(margin or "0"))
            self.discount_total = Decimal(str(discount or "0"))
            self.project_type_id = None
            self.commercial_source_id = None

    fake = quote or _FakeQuote()
    if quote is None:
        if margin is not None:
            fake.gross_margin_percentage = Decimal(str(margin))
            fake.gross_profit = Decimal(str(value)) * Decimal(str(margin)) / Decimal("100")
        if discount is not None:
            fake.discount_total = Decimal(str(discount))

    policy, rule = find_applicable_policy(
        trigger_type=trigger_type,
        target=target,
        on_date=on_date,
        salesperson=salesperson,
        partner=partner,
        quote=fake,
    )
    if not policy:
        return {
            "eligible": False,
            "reason": "Nenhuma política vigente encontrada",
            "policy": None,
            "amount": Decimal("0.00"),
        }
    reasons = check_policy_restrictions(policy=policy, quote=fake)
    if reasons:
        return {
            "eligible": False,
            "reason": "; ".join(reasons),
            "policy": policy,
            "rule": rule,
            "amount": Decimal("0.00"),
        }
    basis = resolve_basis_amount(policy=policy, quote=fake, received_amount=value)
    amount, rate = calculate_commission_amount(policy=policy, rule=rule, basis_amount=basis)
    return {
        "eligible": True,
        "reason": "",
        "policy": policy,
        "rule": rule,
        "basis": basis,
        "rate": rate,
        "amount": amount,
        "release_only_after_payment": policy.release_only_after_payment,
        "requires_approval": policy.requires_approval,
    }
