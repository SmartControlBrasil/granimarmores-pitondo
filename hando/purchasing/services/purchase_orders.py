# ruff: noqa: PLR0913
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit_event
from purchasing.models import PurchaseOrder
from purchasing.models import PurchaseOrderItem
from purchasing.models import PurchaseOrderStatus
from purchasing.models import QuotationStatus
from purchasing.models import RequestStatus
from purchasing.models import SupplierQuotationItem
from purchasing.services.numbering import next_purchase_order_number


@transaction.atomic
def approve_purchase_selection(
    *,
    purchase_request,
    selections,
    actor,
    justification="",
    request=None,
):
    """
    selections: list of dicts {quotation_item_id} or SupplierQuotationItem instances.
    Gera um pedido de compra por fornecedor.
    """
    if purchase_request.status not in {
        RequestStatus.APPROVED,
        RequestStatus.QUOTED,
        RequestStatus.PARTIALLY_QUOTED,
    }:
        raise ValidationError("Solicitação precisa estar aprovada/cotada para seleção.")
    if purchase_request.purchase_orders.exclude(
        status__in=[PurchaseOrderStatus.CANCELLED, PurchaseOrderStatus.REJECTED],
    ).exists():
        raise ValidationError("Já existem pedidos ativos para esta solicitação.")

    item_ids = []
    for sel in selections:
        if isinstance(sel, SupplierQuotationItem):
            item_ids.append(sel.pk)
        else:
            item_ids.append(int(sel["quotation_item_id"] if isinstance(sel, dict) else sel))

    q_items = list(
        SupplierQuotationItem.objects.select_related("quotation", "quotation__supplier", "request_item")
        .filter(pk__in=item_ids, quotation__purchase_request=purchase_request)
        .exclude(
            quotation__status__in=[
                QuotationStatus.CANCELLED,
                QuotationStatus.EXPIRED,
                QuotationStatus.REJECTED,
            ],
        ),
    )
    if not q_items or len(q_items) != len(set(item_ids)):
        raise ValidationError("Seleção inválida ou cotação indisponível.")

    by_supplier = defaultdict(list)
    for qi in q_items:
        by_supplier[qi.quotation.supplier_id].append(qi)

    comparison_lowest = None
    quotes = purchase_request.quotations.exclude(
        status__in=[QuotationStatus.CANCELLED, QuotationStatus.EXPIRED],
    )
    if quotes.exists():
        comparison_lowest = min(quotes, key=lambda q: q.total_amount)

    selected_quote_ids = {qi.quotation_id for qi in q_items}
    if comparison_lowest and comparison_lowest.id not in selected_quote_ids:
        if not (justification or "").strip():
            raise ValidationError(
                "Justificativa obrigatória quando a seleção não é o menor custo total.",
            )

    purchase_request.selection_justification = (justification or "").strip()
    purchase_request.updated_by = actor
    purchase_request.save(update_fields=["selection_justification", "updated_by", "updated_at"])

    orders = []
    for supplier_id, items in by_supplier.items():
        quotation = items[0].quotation
        order = _create_order_from_items(
            purchase_request=purchase_request,
            supplier=quotation.supplier,
            quotation=quotation,
            items=items,
            actor=actor,
            request=request,
        )
        orders.append(order)
        for qi in items:
            qi.is_selected = True
            qi.save(update_fields=["is_selected", "updated_at"])
        quotation.status = QuotationStatus.SELECTED
        quotation.updated_by = actor
        quotation.save(update_fields=["status", "updated_by", "updated_at"])

    purchase_request.status = RequestStatus.ORDERED
    purchase_request.save(update_fields=["status", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="purchasing",
        action="approve_purchase_selection",
        obj=purchase_request,
        metadata={"orders": [o.number for o in orders], "justification": justification[:500]},
    )
    return orders


def _create_order_from_items(*, purchase_request, supplier, quotation, items, actor, request=None):
    today = timezone.localdate()
    subtotal = sum((i.total_amount for i in items), Decimal("0.00"))
    order = PurchaseOrder(
        number=next_purchase_order_number(),
        supplier=supplier,
        purchase_request=purchase_request,
        quotation=quotation,
        status=PurchaseOrderStatus.APPROVED,
        order_date=today,
        expected_delivery_date=(
            today + timedelta(days=quotation.delivery_days) if quotation.delivery_days else None
        ),
        payment_method=quotation.payment_method,
        cost_center=purchase_request.cost_center,
        subtotal=subtotal,
        discount_amount=quotation.discount_amount,
        freight_amount=quotation.freight_amount,
        total_amount=subtotal + quotation.freight_amount - quotation.discount_amount,
        notes=quotation.notes,
        approved_by=actor,
        created_by=actor,
        updated_by=actor,
    )
    order.save()
    for qi in items:
        req_item = qi.request_item
        PurchaseOrderItem.objects.create(
            purchase_order=order,
            request_item=req_item,
            quotation_item=qi,
            item_type=(req_item.item_type if req_item else "material"),
            material=req_item.material if req_item else None,
            description=qi.description,
            ordered_quantity=qi.quantity,
            unit=qi.unit,
            unit_price=qi.unit_price,
            discount_amount=qi.discount_amount,
            total_amount=qi.total_amount,
            notes=qi.notes,
        )
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="purchasing",
        action="create_purchase_order",
        obj=order,
        description=f"Criou pedido {order.number}",
    )
    return order


@transaction.atomic
def approve_purchase_order(*, purchase_order, actor, request=None):
    if purchase_order.status != PurchaseOrderStatus.DRAFT:
        raise ValidationError("Somente rascunhos podem ser aprovados.")
    purchase_order.status = PurchaseOrderStatus.APPROVED
    purchase_order.approved_by = actor
    purchase_order.updated_by = actor
    purchase_order.save(update_fields=["status", "approved_by", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="purchasing",
        action="approve_purchase_order",
        obj=purchase_order,
    )
    return purchase_order


@transaction.atomic
def cancel_purchase_order(*, purchase_order, actor, reason, request=None):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Motivo de cancelamento é obrigatório.")
    if purchase_order.receipts.exclude(status="cancelled").exists():
        raise ValidationError("Pedido com recebimentos não pode ser cancelado. Use devolução.")
    purchase_order.status = PurchaseOrderStatus.CANCELLED
    purchase_order.cancel_reason = reason
    purchase_order.updated_by = actor
    purchase_order.save(update_fields=["status", "cancel_reason", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="purchasing",
        action="cancel_purchase_order",
        obj=purchase_order,
        metadata={"reason": reason[:500]},
    )
    return purchase_order


def refresh_purchase_order_receipt_status(purchase_order):
    items = list(purchase_order.items.all())
    if not items:
        return purchase_order
    total_ordered = sum((i.ordered_quantity - i.cancelled_quantity for i in items), Decimal("0"))
    total_received = sum((i.received_quantity for i in items), Decimal("0"))
    if total_received <= 0:
        return purchase_order
    if total_received >= total_ordered:
        purchase_order.status = PurchaseOrderStatus.RECEIVED
    else:
        purchase_order.status = PurchaseOrderStatus.PARTIALLY_RECEIVED
    purchase_order.save(update_fields=["status", "updated_at"])
    return purchase_order
