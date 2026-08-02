from decimal import Decimal

from django.db.models import Count
from django.db.models import Q
from django.db.models import Sum
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from finance.models import AccountsPayable
from materials.stock_models import MaterialSupplier
from production.models import ProductionPiece
from purchasing.models import DivergenceSeverity
from purchasing.models import DivergenceStatus
from purchasing.models import PurchaseOrder
from purchasing.models import PurchaseOrderStatus
from purchasing.models import PurchaseReceipt
from purchasing.models import PurchaseReceiptDivergence
from purchasing.models import PurchaseRequest
from purchasing.models import PurchaseReturn
from purchasing.models import ReceiptStatus
from purchasing.models import RequestStatus
from purchasing.models import ReturnStatus
from purchasing.models import SupplierQuotation


def _has_purchasing_full(user):
    return user_has_permission(user, "purchasing_dashboard.view") or user_has_permission(
        user,
        "purchase_orders.view",
    )


def purchase_requests_queryset_for_user(user):
    qs = PurchaseRequest.objects.select_related(
        "requested_by",
        "cost_center",
        "production_order",
        "production_piece",
    )
    if user_has_permission(user, "purchase_requests.view") and (
        getattr(user, "is_superuser", False)
        or user_has_permission(user, "purchasing_dashboard.view")
        or user_has_permission(user, "purchase_orders.approve")
    ):
        return qs
    if user_has_permission(user, "purchase_requests.view"):
        return qs.filter(Q(requested_by=user) | Q(requested_for_user=user) | Q(created_by=user))
    return qs.none()


def purchase_orders_queryset_for_user(user):
    qs = PurchaseOrder.objects.select_related("supplier", "purchase_request", "payable")
    if user_has_permission(user, "purchase_orders.view"):
        return qs
    if user_has_permission(user, "purchasing_generate_payable"):
        return qs.exclude(status__in=[PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.CANCELLED])
    return qs.none()


def quotations_queryset_for_user(user):
    if user_has_permission(user, "supplier_quotations.view"):
        return SupplierQuotation.objects.select_related("supplier", "purchase_request")
    return SupplierQuotation.objects.none()


def receipts_queryset_for_user(user):
    if user_has_permission(user, "purchase_receipts.view"):
        return PurchaseReceipt.objects.select_related("purchase_order", "purchase_order__supplier")
    return PurchaseReceipt.objects.none()


def filter_purchase_requests(qs, params):
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(justification__icontains=q))
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("priority"):
        qs = qs.filter(priority=params["priority"])
    if params.get("request_type"):
        qs = qs.filter(request_type=params["request_type"])
    return qs


def filter_purchase_orders(qs, params):
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(supplier__name__icontains=q))
    if params.get("status"):
        qs = qs.filter(status=params["status"])
    if params.get("supplier"):
        qs = qs.filter(supplier_id=params["supplier"])
    return qs


def purchasing_dashboard_metrics(*, user, start, end):
    reqs = purchase_requests_queryset_for_user(user)
    orders = purchase_orders_queryset_for_user(user)
    receipts = receipts_queryset_for_user(user)
    today = timezone.localdate()

    open_requests = reqs.exclude(
        status__in=[
            RequestStatus.CANCELLED,
            RequestStatus.REJECTED,
            RequestStatus.RECEIVED,
        ],
    ).count()
    awaiting_approval = reqs.filter(status__in=[RequestStatus.SUBMITTED, RequestStatus.UNDER_REVIEW]).count()
    awaiting_quote = reqs.filter(status=RequestStatus.APPROVED).count()
    quotes_received = SupplierQuotation.objects.filter(
        quotation_date__gte=start,
        quotation_date__lte=end,
    ).count()
    open_orders = orders.exclude(
        status__in=[
            PurchaseOrderStatus.CANCELLED,
            PurchaseOrderStatus.CLOSED,
            PurchaseOrderStatus.RECEIVED,
        ],
    ).count()
    delayed_orders = orders.filter(
        expected_delivery_date__lt=today,
    ).exclude(
        status__in=[
            PurchaseOrderStatus.RECEIVED,
            PurchaseOrderStatus.CLOSED,
            PurchaseOrderStatus.CANCELLED,
        ],
    ).count()
    partial_orders = orders.filter(status=PurchaseOrderStatus.PARTIALLY_RECEIVED).count()
    inspection = receipts.filter(status=ReceiptStatus.UNDER_INSPECTION).count()
    open_div = PurchaseReceiptDivergence.objects.filter(
        status__in=[DivergenceStatus.OPEN, DivergenceStatus.UNDER_ANALYSIS],
    ).count()
    open_returns = PurchaseReturn.objects.exclude(
        status__in=[ReturnStatus.COMPLETED, ReturnStatus.CANCELLED],
    ).count()

    can_values = user_has_permission(user, "purchasing_values.view") or user_has_permission(
        user,
        "purchasing_costs.view",
    )
    purchased = (
        orders.filter(order_date__gte=start, order_date__lte=end).aggregate(v=Sum("total_amount"))["v"]
        or Decimal("0")
    )
    awaiting_receipt = (
        orders.filter(
            status__in=[
                PurchaseOrderStatus.APPROVED,
                PurchaseOrderStatus.SENT,
                PurchaseOrderStatus.CONFIRMED,
                PurchaseOrderStatus.PARTIALLY_RECEIVED,
            ],
        ).aggregate(v=Sum("total_amount"))["v"]
        or Decimal("0")
    )

    pieces_without_slab = ProductionPiece.objects.filter(slab__isnull=True).count()
    critical_without_purchase = pieces_without_slab  # proxy simples

    pos_without_payable = orders.filter(
        status__in=[PurchaseOrderStatus.RECEIVED, PurchaseOrderStatus.PARTIALLY_RECEIVED],
        payable__isnull=True,
    ).count()

    top_suppliers = list(
        orders.filter(order_date__gte=start, order_date__lte=end)
        .values("supplier__name")
        .annotate(total=Sum("total_amount"), qty=Count("id"))
        .order_by("-total")[:8],
    )
    by_cost_center = list(
        orders.filter(order_date__gte=start, order_date__lte=end)
        .values("cost_center__name")
        .annotate(total=Sum("total_amount"))
        .order_by("-total")[:8],
    )

    return {
        "open_requests": open_requests,
        "awaiting_approval": awaiting_approval,
        "awaiting_quote": awaiting_quote,
        "quotes_received": quotes_received,
        "open_orders": open_orders,
        "delayed_orders": delayed_orders,
        "partial_orders": partial_orders,
        "inspection_receipts": inspection,
        "open_divergences": open_div,
        "open_returns": open_returns,
        "purchased_amount": purchased if can_values else None,
        "awaiting_receipt_amount": awaiting_receipt if can_values else None,
        "pieces_without_slab": pieces_without_slab,
        "critical_without_purchase": critical_without_purchase,
        "orders_without_payable": pos_without_payable,
        "top_suppliers": top_suppliers if can_values else [],
        "by_cost_center": by_cost_center if can_values else [],
        "can_values": can_values,
    }


def purchasing_alerts(*, user):
    today = timezone.localdate()
    alerts = []
    pieces = ProductionPiece.objects.filter(slab__isnull=True)[:20]
    for piece in pieces:
        has_req = PurchaseRequest.objects.filter(
            production_piece=piece,
        ).exclude(status__in=[RequestStatus.CANCELLED, RequestStatus.REJECTED]).exists()
        if not has_req:
            alerts.append(
                {
                    "level": "warning",
                    "code": "piece_without_request",
                    "message": f"Peça #{piece.pk} sem chapa e sem solicitação de compra",
                },
            )
    for pr in PurchaseRequest.objects.filter(status=RequestStatus.APPROVED)[:20]:
        if not pr.quotations.exists():
            alerts.append(
                {
                    "level": "info",
                    "code": "approved_without_quote",
                    "message": f"Solicitação {pr.number} aprovada sem cotação",
                },
            )
    for q in SupplierQuotation.objects.filter(valid_until__isnull=False, valid_until__lte=today).exclude(
        status__in=["cancelled", "expired", "selected"],
    )[:10]:
        alerts.append(
            {
                "level": "warning",
                "code": "quote_expiring",
                "message": f"Cotação {q.number} vence em {q.valid_until}",
            },
        )
    delayed = PurchaseOrder.objects.filter(expected_delivery_date__lt=today).exclude(
        status__in=["received", "closed", "cancelled"],
    )[:10]
    for po in delayed:
        alerts.append(
            {
                "level": "danger",
                "code": "order_delayed",
                "message": f"Pedido {po.number} atrasado (previsão {po.expected_delivery_date})",
            },
        )
    for d in PurchaseReceiptDivergence.objects.filter(
        severity=DivergenceSeverity.CRITICAL,
        status__in=[DivergenceStatus.OPEN, DivergenceStatus.UNDER_ANALYSIS],
    )[:10]:
        alerts.append(
            {
                "level": "danger",
                "code": "critical_divergence",
                "message": f"Divergência crítica no recebimento {d.receipt.number}",
            },
        )
    for po in PurchaseOrder.objects.filter(
        status=PurchaseOrderStatus.RECEIVED,
        payable__isnull=True,
    )[:10]:
        alerts.append(
            {
                "level": "warning",
                "code": "received_without_payable",
                "message": f"Pedido {po.number} recebido sem conta a pagar",
            },
        )
    # duplicidade de AP
    from django.db.models import Count as DjCount

    dupes = (
        AccountsPayable.objects.exclude(status="cancelled")
        .filter(reference_type="purchase_order")
        .values("reference_id")
        .annotate(c=DjCount("id"))
        .filter(c__gt=1)[:5]
    )
    for d in dupes:
        alerts.append(
            {
                "level": "danger",
                "code": "duplicate_payable",
                "message": f"Conta a pagar duplicada para pedido id={d['reference_id']}",
            },
        )
    return alerts[:40]


def main_dashboard_purchasing_summary(user):
    if not (
        user_has_permission(user, "purchasing_dashboard.view")
        or user_has_permission(user, "purchase_requests.approve")
        or user_has_permission(user, "purchase_orders.view")
    ):
        return None
    today = timezone.localdate()
    return {
        "awaiting_approval": PurchaseRequest.objects.filter(
            status__in=[RequestStatus.SUBMITTED, RequestStatus.UNDER_REVIEW],
        ).count(),
        "delayed_orders": PurchaseOrder.objects.filter(expected_delivery_date__lt=today)
        .exclude(status__in=["received", "closed", "cancelled"])
        .count(),
        "inspection_receipts": PurchaseReceipt.objects.filter(
            status=ReceiptStatus.UNDER_INSPECTION,
        ).count(),
        "critical_divergences": PurchaseReceiptDivergence.objects.filter(
            severity=DivergenceSeverity.CRITICAL,
            status__in=[DivergenceStatus.OPEN, DivergenceStatus.UNDER_ANALYSIS],
        ).count(),
    }


def executive_purchasing_metrics(*, user, start, end):
    if not (
        user_has_permission(user, "executive_dashboard.view_purchasing")
        or user_has_permission(user, "executive_dashboard.view")
        or user_has_permission(user, "purchasing_values.view")
    ):
        return {}
    metrics = purchasing_dashboard_metrics(user=user, start=start, end=end)
    return {
        "purchased_amount": metrics.get("purchased_amount") or Decimal("0"),
        "delayed_orders": metrics["delayed_orders"],
        "open_divergences": metrics["open_divergences"],
        "top_suppliers": metrics.get("top_suppliers") or [],
        "by_cost_center": metrics.get("by_cost_center") or [],
        "pieces_without_slab": metrics["pieces_without_slab"],
    }


def supplier_history(*, supplier):
    return {
        "orders": PurchaseOrder.objects.filter(supplier=supplier).order_by("-order_date")[:20],
        "quotations": SupplierQuotation.objects.filter(supplier=supplier).order_by("-quotation_date")[:20],
        "receipts": PurchaseReceipt.objects.filter(purchase_order__supplier=supplier).order_by("-received_at")[
            :20
        ],
        "divergences": PurchaseReceiptDivergence.objects.filter(
            receipt__purchase_order__supplier=supplier,
        ).order_by("-created_at")[:20],
        "returns": PurchaseReturn.objects.filter(supplier=supplier).order_by("-return_date")[:20],
    }


def active_suppliers():
    return MaterialSupplier.objects.filter(is_active=True).order_by("name")
