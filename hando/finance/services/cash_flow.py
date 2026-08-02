from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from finance.models import EXPENSE_MOVEMENT_TYPES
from finance.models import INCOME_MOVEMENT_TYPES
from finance.models import FinancialMovement
from finance.models import MovementType
from finance.models import PayableInstallment
from finance.models import ReceivableInstallment
from finance.models import TERMINAL_INSTALLMENT_STATUSES
from finance.services.balances import account_balance


def _movement_totals(*, start, end, account=None):
    qs = FinancialMovement.objects.filter(movement_date__gte=start, movement_date__lte=end)
    if account:
        qs = qs.filter(financial_account=account)
    income = qs.filter(movement_type__in=INCOME_MOVEMENT_TYPES).aggregate(t=Sum("amount"))["t"] or Decimal(
        "0.00",
    )
    expense = qs.filter(movement_type__in=EXPENSE_MOVEMENT_TYPES).aggregate(t=Sum("amount"))["t"] or Decimal(
        "0.00",
    )
    # estornos: reverter sinal
    for mov in qs.filter(movement_type=MovementType.REVERSAL).select_related("reversal_of"):
        if mov.reversal_of_id and mov.reversal_of.movement_type in EXPENSE_MOVEMENT_TYPES:
            income += mov.amount
        else:
            expense += mov.amount
    return income, expense


def _forecast_totals(*, start, end):
    recv = ReceivableInstallment.objects.filter(
        due_date__gte=start,
        due_date__lte=end,
    ).exclude(status__in=TERMINAL_INSTALLMENT_STATUSES)
    pay = PayableInstallment.objects.filter(
        due_date__gte=start,
        due_date__lte=end,
    ).exclude(status__in=TERMINAL_INSTALLMENT_STATUSES)
    entries = recv.aggregate(t=Sum("outstanding_amount"))["t"] or Decimal("0.00")
    exits = pay.aggregate(t=Sum("outstanding_amount"))["t"] or Decimal("0.00")
    return entries, exits


def cash_flow_summary(*, start, end, account=None):
    day_before = start - timedelta(days=1)
    if account:
        opening = account_balance(account=account, until_date=day_before)
    else:
        from finance.models import FinancialAccount

        opening = sum(
            (account_balance(account=a, until_date=day_before) for a in FinancialAccount.objects.filter(is_active=True)),
            Decimal("0.00"),
        )
    realized_in, realized_out = _movement_totals(start=start, end=end, account=account)
    forecast_in, forecast_out = _forecast_totals(start=start, end=end)
    realized_balance = opening + realized_in - realized_out
    projected_balance = realized_balance + forecast_in - forecast_out

    today = timezone.localdate()
    overdue_recv = ReceivableInstallment.objects.filter(
        due_date__lt=today,
        outstanding_amount__gt=0,
    ).exclude(status__in=TERMINAL_INSTALLMENT_STATUSES)
    overdue_pay = PayableInstallment.objects.filter(
        due_date__lt=today,
        outstanding_amount__gt=0,
    ).exclude(status__in=TERMINAL_INSTALLMENT_STATUSES)

    return {
        "opening_balance": opening,
        "realized_in": realized_in,
        "realized_out": realized_out,
        "realized_balance": realized_balance,
        "forecast_in": forecast_in,
        "forecast_out": forecast_out,
        "projected_balance": projected_balance,
        "overdue_receivable": overdue_recv.aggregate(t=Sum("outstanding_amount"))["t"] or Decimal("0.00"),
        "overdue_payable": overdue_pay.aggregate(t=Sum("outstanding_amount"))["t"] or Decimal("0.00"),
        "overdue_receivable_count": overdue_recv.count(),
        "overdue_payable_count": overdue_pay.count(),
    }


def daily_cash_flow(*, start, end, account=None):
    summary = cash_flow_summary(start=start, end=end, account=account)
    rows = []
    running = summary["opening_balance"]
    day = start
    while day <= end:
        rin, rout = _movement_totals(start=day, end=day, account=account)
        fin, fout = _forecast_totals(start=day, end=day)
        projected = running + rin - rout + fin - fout
        realized_end = running + rin - rout
        rows.append(
            {
                "date": day,
                "opening": running,
                "forecast_in": fin,
                "forecast_out": fout,
                "realized_in": rin,
                "realized_out": rout,
                "realized_balance": realized_end,
                "projected_balance": projected,
            },
        )
        running = realized_end
        day += timedelta(days=1)
    return {"summary": summary, "rows": rows}
