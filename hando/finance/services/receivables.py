# ruff: noqa: PLR0913
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit_event
from finance.models import AccountsReceivable
from finance.models import FinancialCategory
from finance.models import InstallmentStatus
from finance.models import PaymentTerm
from finance.models import ReceivableInstallment
from finance.models import TitleStatus
from finance.services.balances import recalculate_title_from_installments
from finance.services.installments import build_installment_plan
from finance.services.numbering import next_receivable_number
from production.models import SalesOrder
from production.models import SalesOrderStatus
from quotes.models import QuoteStatus


@transaction.atomic
def generate_receivable_from_order(
    *,
    sales_order: SalesOrder,
    payment_term: PaymentTerm,
    actor,
    first_due_date=None,
    category=None,
    cost_center=None,
    description="",
    request=None,
):
    if sales_order.status == SalesOrderStatus.CANCELLED:
        raise ValidationError("Pedido cancelado não gera contas a receber.")
    quote = sales_order.quote
    if not quote or quote.status != QuoteStatus.ACCEPTED:
        raise ValidationError("Somente pedidos com orçamento aceito geram contas a receber.")
    if sales_order.total <= 0:
        raise ValidationError("Pedido sem valor congelado positivo.")

    exists = AccountsReceivable.objects.filter(sales_order=sales_order).exclude(
        status__in=[TitleStatus.CANCELLED, TitleStatus.RENEGOTIATED, TitleStatus.WRITTEN_OFF],
    ).exists()
    if exists:
        raise ValidationError("Já existe conta a receber ativa para este pedido.")

    if category is None:
        category = FinancialCategory.objects.filter(
            code="venda-de-pecas",
            is_active=True,
        ).first()

    today = timezone.localdate()
    plan = build_installment_plan(
        payment_term=payment_term,
        total=sales_order.total,
        base_date=sales_order.order_date or today,
        first_due_date=first_due_date,
    )
    due_date = plan[0]["due_date"] if plan else today

    receivable = AccountsReceivable(
        number=next_receivable_number(),
        customer=sales_order.customer,
        sales_order=sales_order,
        quote=quote,
        description=description or f"Recebível do pedido {sales_order.number}",
        category=category,
        cost_center=cost_center,
        payment_term=payment_term,
        issue_date=today,
        due_date=due_date,
        original_amount=sales_order.total,
        outstanding_amount=sales_order.total,
        status=TitleStatus.OPEN,
        created_by=actor,
        updated_by=actor,
    )
    receivable.save()

    for item in plan:
        ReceivableInstallment.objects.create(
            receivable=receivable,
            sequence=item["sequence"],
            due_date=item["due_date"],
            original_amount=item["amount"],
            outstanding_amount=item["amount"],
            status=InstallmentStatus.OPEN,
        )

    recalculate_title_from_installments(receivable)
    receivable.due_date = receivable.installments.order_by("due_date").first().due_date
    receivable.save(
        update_fields=[
            "paid_amount",
            "outstanding_amount",
            "status",
            "due_date",
            "updated_at",
            "updated_by",
        ],
    )

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="finance",
        action="generate_receivable_from_order",
        obj=receivable,
        description=f"Gerou recebível {receivable.number} a partir do pedido {sales_order.number}",
        metadata={"sales_order": sales_order.pk, "installments": len(plan)},
    )
    return receivable


@transaction.atomic
def create_manual_receivable(*, data, actor, request=None, installment_count=1, first_due_date=None):
    payment_term = data.get("payment_term")
    amount = data["original_amount"]
    today = timezone.localdate()
    if payment_term:
        plan = build_installment_plan(
            payment_term=payment_term,
            total=amount,
            base_date=data.get("issue_date") or today,
            first_due_date=first_due_date or data.get("due_date"),
        )
    else:
        plan = [
            {
                "sequence": 1,
                "due_date": data["due_date"],
                "amount": amount,
            },
        ]

    receivable = AccountsReceivable(
        number=next_receivable_number(),
        customer=data["customer"],
        sales_order=data.get("sales_order"),
        quote=data.get("quote"),
        description=data["description"],
        category=data.get("category"),
        cost_center=data.get("cost_center"),
        payment_term=payment_term,
        issue_date=data.get("issue_date") or today,
        due_date=plan[0]["due_date"],
        original_amount=amount,
        discount_amount=data.get("discount_amount") or Decimal("0.00"),
        outstanding_amount=amount,
        status=TitleStatus.OPEN,
        notes=data.get("notes") or "",
        created_by=actor,
        updated_by=actor,
    )
    receivable.outstanding_amount = receivable.net_amount
    receivable.save()
    for item in plan:
        ReceivableInstallment.objects.create(
            receivable=receivable,
            sequence=item["sequence"],
            due_date=item["due_date"],
            original_amount=item["amount"],
            outstanding_amount=item["amount"],
            status=InstallmentStatus.OPEN,
        )
    recalculate_title_from_installments(receivable)
    receivable.save(update_fields=["paid_amount", "outstanding_amount", "status", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="finance",
        action="create_receivable",
        obj=receivable,
        description=f"Criou recebível {receivable.number}",
    )
    return receivable


@transaction.atomic
def cancel_receivable(*, receivable, actor, reason, request=None):
    if not reason:
        raise ValidationError("Motivo de cancelamento é obrigatório.")
    if receivable.paid_amount > 0:
        raise ValidationError("Título com recebimentos não pode ser cancelado. Use estorno.")
    if receivable.status == TitleStatus.CANCELLED:
        raise ValidationError("Título já cancelado.")
    receivable.status = TitleStatus.CANCELLED
    receivable.cancel_reason = reason
    receivable.outstanding_amount = Decimal("0.00")
    receivable.updated_by = actor
    receivable.save(
        update_fields=[
            "status",
            "cancel_reason",
            "outstanding_amount",
            "updated_by",
            "updated_at",
        ],
    )
    receivable.installments.exclude(status=InstallmentStatus.CANCELLED).update(
        status=InstallmentStatus.CANCELLED,
        outstanding_amount=Decimal("0.00"),
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="finance",
        action="cancel_receivable",
        obj=receivable,
        description=f"Cancelou recebível {receivable.number}",
        metadata={"reason": reason},
    )
    return receivable
