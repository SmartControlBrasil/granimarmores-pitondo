from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from finance.models import EXPENSE_MOVEMENT_TYPES
from finance.models import INCOME_MOVEMENT_TYPES
from finance.models import FinancialMovement
from finance.models import InstallmentStatus
from finance.models import MovementType
from finance.models import TitleStatus


def recalculate_installment_status(installment, *, today=None):
    today = today or timezone.localdate()
    if installment.status in {
        InstallmentStatus.CANCELLED,
        InstallmentStatus.RENEGOTIATED,
    }:
        return installment
    outstanding = installment.outstanding_amount
    paid = installment.paid_amount
    if outstanding <= 0 and paid > 0:
        installment.status = InstallmentStatus.PAID
        installment.outstanding_amount = Decimal("0.00")
    elif paid > 0:
        installment.status = InstallmentStatus.PARTIALLY_PAID
    elif installment.due_date < today and outstanding > 0:
        installment.status = InstallmentStatus.OVERDUE
    else:
        installment.status = InstallmentStatus.OPEN
    return installment


def recalculate_title_from_installments(title, *, installments_attr="installments"):
    installments = list(getattr(title, installments_attr).all())
    if not installments:
        title.paid_amount = Decimal("0.00")
        title.outstanding_amount = title.net_amount
        if title.status not in {
            TitleStatus.CANCELLED,
            TitleStatus.RENEGOTIATED,
            TitleStatus.WRITTEN_OFF,
            TitleStatus.DRAFT,
        }:
            title.status = TitleStatus.OPEN
        return title

    paid = sum((i.paid_amount for i in installments), Decimal("0.00"))
    outstanding = sum((i.outstanding_amount for i in installments), Decimal("0.00"))
    title.paid_amount = paid
    title.outstanding_amount = outstanding

    if title.status in {
        TitleStatus.CANCELLED,
        TitleStatus.RENEGOTIATED,
        TitleStatus.WRITTEN_OFF,
        TitleStatus.DRAFT,
    }:
        return title

    today = timezone.localdate()
    if outstanding <= 0 and paid > 0:
        title.status = TitleStatus.PAID
    elif paid > 0:
        title.status = TitleStatus.PARTIALLY_PAID
    elif title.due_date < today and outstanding > 0:
        title.status = TitleStatus.OVERDUE
    else:
        title.status = TitleStatus.OPEN
    return title


def account_balance(*, account, until_date=None):
    qs = FinancialMovement.objects.filter(financial_account=account)
    if until_date:
        qs = qs.filter(movement_date__lte=until_date)
    income = qs.filter(movement_type__in=INCOME_MOVEMENT_TYPES).aggregate(t=Sum("amount"))["t"] or Decimal(
        "0.00",
    )
    expense = qs.filter(movement_type__in=EXPENSE_MOVEMENT_TYPES).aggregate(t=Sum("amount"))["t"] or Decimal(
        "0.00",
    )
    # reversals: signed via related original
    reversals = qs.filter(movement_type=MovementType.REVERSAL).select_related("reversal_of")
    rev_in = Decimal("0.00")
    rev_out = Decimal("0.00")
    for mov in reversals:
        if mov.reversal_of_id and mov.reversal_of.movement_type in EXPENSE_MOVEMENT_TYPES:
            rev_in += mov.amount
        else:
            rev_out += mov.amount
    return income + rev_in - expense - rev_out
