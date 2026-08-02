# ruff: noqa: PLR0913
from decimal import Decimal

from django.db.models import Q
from django.db.models import Sum
from django.utils import timezone

from access_control.services.authorization import get_user_role
from access_control.services.authorization import user_has_permission
from finance.models import AccountsPayable
from finance.models import AccountsReceivable
from finance.models import FinancialMovement
from finance.models import ReceivableInstallment
from finance.models import ReceivablePayment
from finance.models import TERMINAL_INSTALLMENT_STATUSES
from finance.models import TERMINAL_TITLE_STATUSES
from finance.models import TitleStatus
from finance.services.cash_flow import cash_flow_summary


def receivables_queryset_for_user(user):
    qs = AccountsReceivable.objects.select_related(
        "customer",
        "sales_order",
        "sales_order__salesperson",
        "quote",
        "category",
        "cost_center",
        "payment_term",
    )
    if not user_has_permission(user, "accounts_receivable.view"):
        return qs.none()
    role = get_user_role(user)
    if user.is_superuser or (role and role.has_full_access):
        return qs
    if user_has_permission(user, "finance_values.view") and user_has_permission(
        user,
        "finance_cash_flow.view",
    ):
        return qs
    salesperson = getattr(user, "salesperson", None)
    if salesperson:
        if user_has_permission(user, "sales_performance.view_all"):
            from salespeople.models import Salesperson

            team_ids = list(
                Salesperson.objects.filter(Q(pk=salesperson.pk) | Q(manager=salesperson)).values_list(
                    "pk",
                    flat=True,
                ),
            )
            return qs.filter(sales_order__salesperson_id__in=team_ids)
        return qs.filter(sales_order__salesperson=salesperson)
    return qs


def payables_queryset_for_user(user):
    if not (
        user_has_permission(user, "accounts_payable.view")
        or user_has_permission(user, "finance_values.view")
    ):
        return AccountsPayable.objects.none()
    # vendedor/produção sem despesas gerais
    if user_has_permission(user, "accounts_payable.view"):
        return AccountsPayable.objects.select_related(
            "material_supplier",
            "category",
            "cost_center",
        )
    return AccountsPayable.objects.none()


def filter_receivables(qs, params):
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(customer__name__icontains=q)
            | Q(sales_order__number__icontains=q)
            | Q(description__icontains=q),
        )
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("customer"):
        qs = qs.filter(customer_id=params["customer"])
    if params.get("category"):
        qs = qs.filter(category_id=params["category"])
    if params.get("cost_center"):
        qs = qs.filter(cost_center_id=params["cost_center"])
    if params.get("overdue") == "1":
        qs = qs.filter(
            due_date__lt=timezone.localdate(),
            outstanding_amount__gt=0,
        ).exclude(status__in=TERMINAL_TITLE_STATUSES)
    if params.get("open") == "1":
        qs = qs.filter(status__in=[TitleStatus.OPEN, TitleStatus.PARTIALLY_PAID, TitleStatus.OVERDUE])
    if params.get("paid") == "1":
        qs = qs.filter(status=TitleStatus.PAID)
    return qs


def filter_payables(qs, params):
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(supplier_name__icontains=q)
            | Q(description__icontains=q),
        )
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("category"):
        qs = qs.filter(category_id=params["category"])
    if params.get("cost_center"):
        qs = qs.filter(cost_center_id=params["cost_center"])
    if params.get("overdue") == "1":
        qs = qs.filter(
            due_date__lt=timezone.localdate(),
            outstanding_amount__gt=0,
        ).exclude(status__in=TERMINAL_TITLE_STATUSES)
    if params.get("open") == "1":
        qs = qs.filter(status__in=[TitleStatus.OPEN, TitleStatus.PARTIALLY_PAID, TitleStatus.OVERDUE])
    if params.get("paid") == "1":
        qs = qs.filter(status=TitleStatus.PAID)
    return qs


def overdue_receivable_installments():
    today = timezone.localdate()
    return (
        ReceivableInstallment.objects.filter(
            due_date__lt=today,
            outstanding_amount__gt=0,
        )
        .exclude(status__in=TERMINAL_INSTALLMENT_STATUSES)
        .select_related("receivable", "receivable__customer", "receivable__sales_order")
    )


def overdue_buckets(qs):
    today = timezone.localdate()
    buckets = {
        "1-7": Decimal("0.00"),
        "8-15": Decimal("0.00"),
        "16-30": Decimal("0.00"),
        "31-60": Decimal("0.00"),
        "61-90": Decimal("0.00"),
        "90+": Decimal("0.00"),
    }
    counts = {k: 0 for k in buckets}
    for inst in qs:
        days = (today - inst.due_date).days
        if days <= 7:
            key = "1-7"
        elif days <= 15:
            key = "8-15"
        elif days <= 30:
            key = "16-30"
        elif days <= 60:
            key = "31-60"
        elif days <= 90:
            key = "61-90"
        else:
            key = "90+"
        buckets[key] += inst.outstanding_amount
        counts[key] += 1
    return [{"label": k, "amount": buckets[k], "count": counts[k]} for k in buckets]


def finance_dashboard_metrics(*, user, start, end):
    recv = receivables_queryset_for_user(user)
    pay = payables_queryset_for_user(user)
    open_recv = recv.filter(
        status__in=[TitleStatus.OPEN, TitleStatus.PARTIALLY_PAID, TitleStatus.OVERDUE],
    )
    open_pay = pay.filter(
        status__in=[TitleStatus.OPEN, TitleStatus.PARTIALLY_PAID, TitleStatus.OVERDUE],
    )
    received = ReceivablePayment.objects.filter(
        status="confirmed",
        payment_date__gte=start,
        payment_date__lte=end,
        installment__receivable__in=recv,
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0.00")
    paid = Decimal("0.00")
    if pay.exists() or user_has_permission(user, "accounts_payable.view"):
        from finance.models import PayablePayment

        paid = PayablePayment.objects.filter(
            status="confirmed",
            payment_date__gte=start.date() if hasattr(start, "date") else start,
            payment_date__lte=end.date() if hasattr(end, "date") else end,
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0.00")

    start_d = start.date() if hasattr(start, "hour") else start
    end_d = end.date() if hasattr(end, "hour") else end
    flow = cash_flow_summary(start=start_d, end=end_d)
    overdue_qs = overdue_receivable_installments().filter(receivable__in=recv)

    avg_days = None
    payments = ReceivablePayment.objects.filter(
        status="confirmed",
        payment_date__gte=start_d,
        payment_date__lte=end_d,
    ).select_related("installment")[:200]
    delays = [
        (p.payment_date - p.installment.due_date).days
        for p in payments
        if p.installment_id
    ]
    if delays:
        avg_days = round(sum(delays) / len(delays), 1)

    return {
        "open_receivables": open_recv.count(),
        "open_receivable_amount": open_recv.aggregate(t=Sum("outstanding_amount"))["t"] or Decimal("0.00"),
        "received_period": received,
        "overdue_amount": overdue_qs.aggregate(t=Sum("outstanding_amount"))["t"] or Decimal("0.00"),
        "overdue_count": overdue_qs.count(),
        "open_payables": open_pay.count(),
        "open_payable_amount": open_pay.aggregate(t=Sum("outstanding_amount"))["t"] or Decimal("0.00"),
        "paid_period": paid,
        "overdue_payable": flow["overdue_payable"],
        "realized_balance": flow["realized_balance"],
        "projected_balance": flow["projected_balance"],
        "forecast_in": flow["forecast_in"],
        "forecast_out": flow["forecast_out"],
        "avg_collection_days": avg_days,
        "delinquent_customers": overdue_qs.values("receivable__customer_id").distinct().count(),
        "income_by_category": list(
            FinancialMovement.objects.filter(
                movement_type="income",
                movement_date__gte=start_d,
                movement_date__lte=end_d,
            )
            .values("category__name")
            .annotate(total=Sum("amount"))
            .order_by("-total")[:10],
        ),
        "expense_by_category": list(
            FinancialMovement.objects.filter(
                movement_type="expense",
                movement_date__gte=start_d,
                movement_date__lte=end_d,
            )
            .values("category__name")
            .annotate(total=Sum("amount"))
            .order_by("-total")[:10],
        ),
        "expense_by_cost_center": list(
            FinancialMovement.objects.filter(
                movement_type="expense",
                movement_date__gte=start_d,
                movement_date__lte=end_d,
            )
            .values("cost_center__name")
            .annotate(total=Sum("amount"))
            .order_by("-total")[:10],
        ),
        "overdue_buckets": overdue_buckets(overdue_qs[:500]),
        "ticket_received": (
            (received / Decimal(max(ReceivablePayment.objects.filter(
                status="confirmed",
                payment_date__gte=start_d,
                payment_date__lte=end_d,
            ).count(), 1))).quantize(Decimal("0.01"))
            if received
            else Decimal("0.00")
        ),
    }


def main_dashboard_finance_summary(user):
    if not (
        user_has_permission(user, "finance_dashboard.view")
        or user_has_permission(user, "finance_values.view")
    ):
        return None
    today = timezone.localdate()
    start = today.replace(day=1)
    metrics = finance_dashboard_metrics(user=user, start=start, end=today)
    return {
        "overdue_count": metrics["overdue_count"],
        "open_receivable_amount": metrics["open_receivable_amount"],
        "open_payable_amount": metrics["open_payable_amount"],
        "projected_balance": metrics["projected_balance"],
    }


def executive_finance_metrics(*, user, start, end):
    if not (
        user_has_permission(user, "executive_dashboard.view_finance")
        or user_has_permission(user, "executive_dashboard.view")
        or user_has_permission(user, "finance_values.view")
    ):
        return {}
    return finance_dashboard_metrics(user=user, start=start, end=end)
