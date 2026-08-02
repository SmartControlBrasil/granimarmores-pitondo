# ruff: noqa: PLR0913
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit_event
from finance.models import AccountsPayable
from finance.models import InstallmentStatus
from finance.models import PayableInstallment
from finance.models import TitleStatus
from finance.services.balances import recalculate_title_from_installments
from finance.services.installments import build_installment_plan
from finance.services.numbering import next_payable_number


@transaction.atomic
def create_payable(*, data, actor, request=None, payment_term=None, first_due_date=None):
    amount = data["original_amount"]
    if amount <= 0:
        raise ValidationError("Valor deve ser positivo.")
    today = timezone.localdate()
    term = payment_term or data.get("payment_term")
    if term:
        plan = build_installment_plan(
            payment_term=term,
            total=amount,
            base_date=data.get("issue_date") or today,
            first_due_date=first_due_date or data.get("due_date"),
        )
    else:
        plan = [{"sequence": 1, "due_date": data["due_date"], "amount": amount}]

    supplier_name = data.get("supplier_name") or ""
    material_supplier = data.get("material_supplier")
    if material_supplier and not supplier_name:
        supplier_name = material_supplier.name

    payable = AccountsPayable(
        number=next_payable_number(),
        supplier_name=supplier_name,
        material_supplier=material_supplier,
        description=data["description"],
        category=data.get("category"),
        cost_center=data.get("cost_center"),
        issue_date=data.get("issue_date") or today,
        due_date=plan[0]["due_date"],
        original_amount=amount,
        discount_amount=data.get("discount_amount") or Decimal("0.00"),
        outstanding_amount=amount,
        status=TitleStatus.OPEN,
        reference_type=data.get("reference_type") or "",
        reference_id=data.get("reference_id"),
        notes=data.get("notes") or "",
        created_by=actor,
        updated_by=actor,
    )
    payable.outstanding_amount = payable.net_amount
    payable.save()
    for item in plan:
        PayableInstallment.objects.create(
            payable=payable,
            sequence=item["sequence"],
            due_date=item["due_date"],
            original_amount=item["amount"],
            outstanding_amount=item["amount"],
            status=InstallmentStatus.OPEN,
        )
    recalculate_title_from_installments(payable)
    payable.save(update_fields=["paid_amount", "outstanding_amount", "status", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="finance",
        action="create_payable",
        obj=payable,
        description=f"Criou conta a pagar {payable.number}",
    )
    return payable


@transaction.atomic
def cancel_payable(*, payable, actor, reason, request=None):
    if not reason:
        raise ValidationError("Motivo de cancelamento é obrigatório.")
    if payable.paid_amount > 0:
        raise ValidationError("Título com pagamentos não pode ser cancelado. Use estorno.")
    payable.status = TitleStatus.CANCELLED
    payable.cancel_reason = reason
    payable.outstanding_amount = Decimal("0.00")
    payable.updated_by = actor
    payable.save(
        update_fields=[
            "status",
            "cancel_reason",
            "outstanding_amount",
            "updated_by",
            "updated_at",
        ],
    )
    payable.installments.update(
        status=InstallmentStatus.CANCELLED,
        outstanding_amount=Decimal("0.00"),
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="finance",
        action="cancel_payable",
        obj=payable,
        description=f"Cancelou conta a pagar {payable.number}",
        metadata={"reason": reason},
    )
    return payable
