from datetime import timedelta
from decimal import Decimal
from decimal import ROUND_HALF_UP

from django.core.exceptions import ValidationError

from finance.models import PaymentTerm


TWOPLACES = Decimal("0.01")


def _q(value):
    return Decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def build_installment_plan(*, payment_term: PaymentTerm, total: Decimal, base_date, first_due_date=None):
    if total <= 0:
        raise ValidationError("Valor total deve ser positivo.")
    total = _q(total)
    rules = list(payment_term.rules.order_by("sequence"))
    plan = []

    if rules:
        percents = sum((r.percent for r in rules), Decimal("0"))
        if _q(percents) != Decimal("100.00"):
            raise ValidationError("Soma dos percentuais da condição deve ser 100%.")
        allocated = Decimal("0.00")
        for idx, rule in enumerate(rules):
            if idx == 0 and first_due_date:
                due = first_due_date
            else:
                due = base_date + timedelta(days=rule.days_after_order)
            if idx == len(rules) - 1:
                amount = _q(total - allocated)
            else:
                amount = _q(total * rule.percent / Decimal("100"))
                allocated += amount
            if amount <= 0:
                raise ValidationError("Parcela não pode ser zero ou negativa.")
            plan.append({"sequence": rule.sequence, "due_date": due, "amount": amount})
        return plan

    count = max(int(payment_term.installment_count or 1), 1)
    first_due = first_due_date or (base_date + timedelta(days=payment_term.first_due_days))

    if payment_term.down_payment_percent and payment_term.down_payment_percent > 0 and count > 1:
        down = _q(total * payment_term.down_payment_percent / Decimal("100"))
        rest = _q(total - down)
        plan.append({"sequence": 1, "due_date": first_due, "amount": down})
        remaining_count = count - 1
        base_amount = _q(rest / Decimal(remaining_count))
        allocated = Decimal("0.00")
        for i in range(remaining_count):
            due = first_due + timedelta(days=payment_term.interval_days * (i + 1))
            if i == remaining_count - 1:
                amount = _q(rest - allocated)
            else:
                amount = base_amount
                allocated += amount
            plan.append({"sequence": i + 2, "due_date": due, "amount": amount})
        return plan

    base_amount = _q(total / Decimal(count))
    allocated = Decimal("0.00")
    for i in range(count):
        due = first_due + timedelta(days=payment_term.interval_days * i)
        if i == count - 1:
            amount = _q(total - allocated)
        else:
            amount = base_amount
            allocated += amount
        plan.append({"sequence": i + 1, "due_date": due, "amount": amount})
    return plan
