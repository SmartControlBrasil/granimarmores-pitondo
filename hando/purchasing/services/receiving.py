# ruff: noqa: PLR0913
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit_event
from materials.models import MaterialSlab
from materials.services.stock_operations import block_slab
from materials.services.stock_operations import receive_slab
from materials.stock_models import StockMovement
from purchasing.models import DivergenceSeverity
from purchasing.models import DivergenceStatus
from purchasing.models import ItemType
from purchasing.models import PurchaseOrderStatus
from purchasing.models import PurchaseReceipt
from purchasing.models import PurchaseReceiptDivergence
from purchasing.models import PurchaseReceiptItem
from purchasing.models import PurchaseReceiptSlab
from purchasing.models import PurchaseReturn
from purchasing.models import PurchaseReturnItem
from purchasing.models import ReceiptCondition
from purchasing.models import ReceiptStatus
from purchasing.models import RequestStatus
from purchasing.models import ReturnStatus
from purchasing.services.numbering import next_receipt_number
from purchasing.services.numbering import next_return_number
from purchasing.services.purchase_orders import refresh_purchase_order_receipt_status


RECEIVABLE_PO_STATUSES = {
    PurchaseOrderStatus.APPROVED,
    PurchaseOrderStatus.SENT,
    PurchaseOrderStatus.CONFIRMED,
    PurchaseOrderStatus.PARTIALLY_RECEIVED,
}


@transaction.atomic
def create_receipt(*, purchase_order, items, actor, data=None, request=None, allow_excess=False):
    data = data or {}
    if purchase_order.status not in RECEIVABLE_PO_STATUSES:
        raise ValidationError("Pedido não está apto para recebimento.")
    if not items:
        raise ValidationError("Informe itens recebidos.")

    receipt = PurchaseReceipt(
        number=next_receipt_number(),
        purchase_order=purchase_order,
        status=ReceiptStatus.UNDER_INSPECTION,
        received_at=data.get("received_at") or timezone.now(),
        received_by=actor,
        delivery_document=data.get("delivery_document") or "",
        supplier_document=data.get("supplier_document") or "",
        notes=data.get("notes") or "",
        stock_location=data.get("stock_location") or purchase_order.delivery_location,
        created_by=actor,
        updated_by=actor,
    )
    receipt.save()

    for raw in items:
        poi = raw["purchase_order_item"]
        if poi.purchase_order_id != purchase_order.id:
            raise ValidationError("Item não pertence ao pedido.")
        received_qty = Decimal(str(raw["received_quantity"]))
        if received_qty < 0:
            raise ValidationError("Quantidade recebida não pode ser negativa.")
        if received_qty <= 0:
            continue
        outstanding = poi.outstanding_quantity
        if received_qty > outstanding and not allow_excess:
            raise ValidationError(
                f"Recebimento de '{poi.description}' ultrapassa o saldo do pedido.",
            )
        accepted = Decimal(str(raw.get("accepted_quantity", received_qty)))
        rejected = Decimal(str(raw.get("rejected_quantity", "0")))
        if accepted < 0 or rejected < 0:
            raise ValidationError("Quantidades não podem ser negativas.")
        if accepted + rejected > received_qty:
            raise ValidationError("Aceito + rejeitado não pode ultrapassar o recebido.")
        condition = raw.get("condition") or ReceiptCondition.ACCEPTED
        div_notes = (raw.get("divergence_notes") or "").strip()
        div_type = raw.get("divergence_type") or ""
        if condition != ReceiptCondition.ACCEPTED and not div_notes:
            raise ValidationError("Divergência exige observação.")

        PurchaseReceiptItem.objects.create(
            receipt=receipt,
            purchase_order_item=poi,
            received_quantity=received_qty,
            accepted_quantity=accepted,
            rejected_quantity=rejected,
            unit=poi.unit,
            actual_unit_cost=Decimal(str(raw.get("actual_unit_cost") or poi.unit_price)),
            width=raw.get("width"),
            height=raw.get("height"),
            thickness=raw.get("thickness"),
            area=raw.get("area"),
            batch=raw.get("batch") or "",
            supplier_code=raw.get("supplier_code") or "",
            condition=condition,
            divergence_type=div_type or (condition if condition != ReceiptCondition.ACCEPTED else ""),
            divergence_notes=div_notes,
        )

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="purchasing",
        action="create_receipt",
        obj=receipt,
        description=f"Criou recebimento {receipt.number}",
        metadata={"override_excess": allow_excess},
    )
    return receipt


@transaction.atomic
def accept_receipt(*, receipt, actor, request=None):
    if receipt.status not in {ReceiptStatus.UNDER_INSPECTION, ReceiptStatus.DRAFT}:
        raise ValidationError("Recebimento não está em inspeção.")

    has_divergence = False
    for item in receipt.items.select_related("purchase_order_item", "purchase_order_item__material"):
        poi = item.purchase_order_item
        if item.condition != ReceiptCondition.ACCEPTED or item.rejected_quantity > 0:
            has_divergence = True
            PurchaseReceiptDivergence.objects.create(
                receipt=receipt,
                receipt_item=item,
                divergence_type=item.divergence_type or item.condition,
                severity=(
                    DivergenceSeverity.CRITICAL
                    if item.condition in {ReceiptCondition.DAMAGED, ReceiptCondition.WRONG_MATERIAL}
                    else DivergenceSeverity.MEDIUM
                ),
                description=item.divergence_notes or item.get_condition_display(),
                expected_value=str(poi.ordered_quantity),
                received_value=str(item.received_quantity),
                status=DivergenceStatus.OPEN,
                created_by=actor,
                updated_by=actor,
            )

        if item.accepted_quantity > 0 and not item.stock_entered:
            _enter_stock_for_item(receipt=receipt, item=item, actor=actor, request=request)

        poi.received_quantity = (poi.received_quantity or Decimal("0")) + item.accepted_quantity
        poi.save(update_fields=["received_quantity", "updated_at"])

    receipt.status = (
        ReceiptStatus.ACCEPTED_WITH_DIVERGENCE if has_divergence else ReceiptStatus.ACCEPTED
    )
    receipt.updated_by = actor
    receipt.save(update_fields=["status", "updated_by", "updated_at"])

    po = receipt.purchase_order
    refresh_purchase_order_receipt_status(po)
    pr = po.purchase_request
    if pr:
        if po.status == PurchaseOrderStatus.RECEIVED:
            siblings = pr.purchase_orders.exclude(
                status__in=[PurchaseOrderStatus.CANCELLED, PurchaseOrderStatus.REJECTED],
            )
            if all(s.status == PurchaseOrderStatus.RECEIVED for s in siblings):
                pr.status = RequestStatus.RECEIVED
            else:
                pr.status = RequestStatus.PARTIALLY_RECEIVED
        else:
            pr.status = RequestStatus.PARTIALLY_RECEIVED
        pr.save(update_fields=["status", "updated_at"])

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="purchasing",
        action="accept_receipt",
        obj=receipt,
        description=f"Aceitou recebimento {receipt.number}",
    )
    return receipt


def _enter_stock_for_item(*, receipt, item, actor, request=None):
    poi = item.purchase_order_item
    if poi.item_type != ItemType.SLAB and not (
        poi.material_id and getattr(poi.material, "unit", "") in {"sheet", "m2"}
    ):
        # Sem estoque quantitativo genérico: registro documental apenas.
        item.stock_entered = True
        item.save(update_fields=["stock_entered", "updated_at"])
        return

    if not poi.material_id:
        raise ValidationError(f"Item '{poi.description}' tipo chapa exige material cadastrado.")
    location = receipt.stock_location or receipt.purchase_order.delivery_location
    if not location:
        raise ValidationError("Informe localização de entrada para chapas.")

    units = int(item.accepted_quantity)
    if units <= 0:
        item.stock_entered = True
        item.save(update_fields=["stock_entered", "updated_at"])
        return

    width = item.width or poi.width
    height = item.height or poi.height
    thickness = item.thickness or poi.thickness
    if not width or not height or not thickness:
        raise ValidationError("Dimensões reais são obrigatórias para entrada de chapas.")

    for _ in range(units):
        slab = receive_slab(
            material=poi.material,
            width=width,
            height=height,
            thickness=thickness,
            supplier=receipt.purchase_order.supplier,
            location=location,
            cost_value=item.actual_unit_cost,
            actor=actor,
            batch=item.batch,
            notes=f"Recebimento {receipt.number}",
            request=request,
        )
        PurchaseReceiptSlab.objects.create(receipt_item=item, slab=slab)
        # Movimento já criado por receive_slab; vínculo documental em PurchaseReceiptSlab.
        record_audit_event(
            request=request,
            user=actor,
            event_type="create",
            module="purchasing",
            action="slab_entered_from_receipt",
            obj=slab,
            metadata={"receipt": receipt.number, "receipt_item": item.pk},
        )

    item.stock_entered = True
    item.save(update_fields=["stock_entered", "updated_at"])


@transaction.atomic
def reject_receipt(*, receipt, actor, reason, request=None):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Motivo da rejeição é obrigatório.")
    if receipt.status not in {ReceiptStatus.UNDER_INSPECTION, ReceiptStatus.DRAFT}:
        raise ValidationError("Recebimento não pode ser rejeitado neste status.")
    if receipt.items.filter(stock_entered=True).exists():
        raise ValidationError("Recebimento com entrada de estoque não pode ser rejeitado.")
    receipt.status = ReceiptStatus.REJECTED
    receipt.notes = (receipt.notes + f"\nRejeição: {reason}").strip()
    receipt.updated_by = actor
    receipt.save(update_fields=["status", "notes", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="purchasing",
        action="reject_receipt",
        obj=receipt,
        metadata={"reason": reason[:500]},
    )
    return receipt


@transaction.atomic
def create_and_complete_return(*, supplier, receipt, items, actor, reason, notes="", request=None):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Motivo da devolução é obrigatório.")
    if not items:
        raise ValidationError("Informe itens para devolução.")

    ret = PurchaseReturn(
        number=next_return_number(),
        supplier=supplier,
        purchase_order=receipt.purchase_order if receipt else None,
        receipt=receipt,
        status=ReturnStatus.APPROVED,
        return_date=timezone.localdate(),
        reason=reason,
        notes=notes,
        created_by=actor,
        updated_by=actor,
        approved_by=actor,
    )
    ret.save()

    for raw in items:
        receipt_item = raw["receipt_item"]
        qty = Decimal(str(raw["quantity"]))
        if qty <= 0:
            raise ValidationError("Quantidade de devolução deve ser positiva.")
        slab = raw.get("slab")
        ri = PurchaseReturnItem(
            purchase_return=ret,
            receipt_item=receipt_item,
            quantity=qty,
            slab=slab,
            notes=raw.get("notes") or "",
        )
        ri.save()
        if slab:
            if slab.reserved_area > 0 or slab.consumed_area > 0:
                raise ValidationError(
                    f"Chapa {slab.slab_code} reservada/consumida não pode ser devolvida.",
                )
            block_slab(
                slab=slab,
                reason=f"Devolução {ret.number}: {reason}",
                actor=actor,
                request=request,
            )
            # Zera disponibilidade para refletir saída operacional.
            slab = MaterialSlab.objects.select_for_update().get(pk=slab.pk)
            prev = slab.available_area
            slab.available_area = Decimal("0.0000")
            slab.status = MaterialSlab.Status.DISCARDED
            slab.updated_by = actor
            slab.save()
            StockMovement.objects.create(
                slab=slab,
                movement_type=StockMovement.MovementType.SCRAP,
                quantity_area=prev,
                previous_available_area=prev,
                new_available_area=Decimal("0.0000"),
                reference_type="purchase_return",
                reference_id=str(ret.pk),
                description=f"Devolução ao fornecedor {ret.number}",
                occurred_at=timezone.now(),
                created_by=actor,
            )
            ri.stock_exited = True
            ri.save(update_fields=["stock_exited", "updated_at"])

    ret.status = ReturnStatus.COMPLETED
    ret.save(update_fields=["status", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="purchasing",
        action="complete_purchase_return",
        obj=ret,
        description=f"Devolução {ret.number}",
    )
    return ret
