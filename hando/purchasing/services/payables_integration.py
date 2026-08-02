# ruff: noqa: PLR0913
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit_event
from finance.models import AccountsPayable
from finance.models import CategoryType
from finance.models import FinancialCategory
from finance.services.payables import create_payable
from purchasing.models import PurchaseOrderStatus
from purchasing.models import ReceiptStatus


def purchasing_payable_trigger():
    return getattr(settings, "PURCHASING_PAYABLE_TRIGGER", "receipt")


@transaction.atomic
def generate_payable_from_purchase_order(
    *,
    purchase_order,
    actor,
    due_date,
    payment_term=None,
    request=None,
):
    if purchase_order.status in {
        PurchaseOrderStatus.DRAFT,
        PurchaseOrderStatus.CANCELLED,
        PurchaseOrderStatus.REJECTED,
    }:
        raise ValidationError("Pedido não aprovado para geração financeira.")

    trigger = purchasing_payable_trigger()
    if trigger == "receipt":
        accepted = purchase_order.receipts.filter(
            status__in=[ReceiptStatus.ACCEPTED, ReceiptStatus.ACCEPTED_WITH_DIVERGENCE],
        ).exists()
        if not accepted:
            raise ValidationError("É necessário recebimento aceito para gerar conta a pagar.")
    elif trigger == "manual":
        pass
    # purchase_order: permite após aprovação

    if purchase_order.payable_id:
        raise ValidationError("Pedido já possui conta a pagar vinculada.")
    existing = AccountsPayable.objects.filter(
        reference_type="purchase_order",
        reference_id=purchase_order.pk,
    ).exclude(status="cancelled")
    if existing.exists():
        raise ValidationError("Já existe conta a pagar para este pedido.")

    category = FinancialCategory.objects.filter(
        code="compra-de-material",
        category_type=CategoryType.EXPENSE,
        is_active=True,
    ).first()

    payable = create_payable(
        data={
            "material_supplier": purchase_order.supplier,
            "supplier_name": purchase_order.supplier.name,
            "description": f"Compra {purchase_order.number}",
            "category": category,
            "cost_center": purchase_order.cost_center,
            "issue_date": timezone.localdate(),
            "due_date": due_date,
            "original_amount": purchase_order.total_amount,
            "reference_type": "purchase_order",
            "reference_id": purchase_order.pk,
            "notes": f"Gerado a partir do pedido {purchase_order.number}",
        },
        actor=actor,
        request=request,
        payment_term=payment_term or purchase_order.payment_term,
        first_due_date=due_date,
    )
    purchase_order.payable = payable
    purchase_order.updated_by = actor
    purchase_order.save(update_fields=["payable", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="purchasing",
        action="generate_payable_from_po",
        obj=purchase_order,
        metadata={"payable": payable.number},
    )
    return payable
