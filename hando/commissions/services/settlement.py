# ruff: noqa: PLR0913
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from audit.services import record_audit_event
from commissions.models import CommissionEvent
from commissions.models import CommissionPayment
from commissions.models import CommissionSettlement
from commissions.models import CommissionSettlementItem
from commissions.models import EventStatus
from commissions.models import EventType
from commissions.models import PaymentStatus
from commissions.models import SettlementStatus
from commissions.services.numbering import next_event_number
from commissions.services.numbering import next_payment_number
from commissions.services.numbering import next_settlement_number
from finance.models import CategoryType
from finance.models import FinancialCategory
from finance.models import MovementType
from finance.services.numbering import next_movement_number
from finance.services.payables import create_payable
from finance.models import FinancialMovement


@transaction.atomic
def create_settlement(
    *,
    beneficiary_type,
    period_start,
    period_end,
    actor,
    salesperson=None,
    commercial_partner=None,
    event_ids=None,
    notes="",
    request=None,
):
    if period_end < period_start:
        raise ValidationError("Período inválido.")
    if beneficiary_type == "salesperson" and not salesperson:
        raise ValidationError("Vendedor obrigatório.")
    if beneficiary_type == "commercial_partner" and not commercial_partner:
        raise ValidationError("Parceiro obrigatório.")

    qs = CommissionEvent.objects.filter(
        beneficiary_type=beneficiary_type,
        event_type__in=[EventType.RELEASE, EventType.ADJUSTMENT_POSITIVE],
        status=EventStatus.AVAILABLE,
        competence_date__gte=period_start,
        competence_date__lte=period_end,
        settlement__isnull=True,
    )
    if salesperson:
        qs = qs.filter(salesperson=salesperson)
    if commercial_partner:
        qs = qs.filter(commercial_partner=commercial_partner)
    if event_ids:
        qs = qs.filter(pk__in=event_ids)

    events = list(qs.select_for_update())
    if not events:
        raise ValidationError("Nenhum evento disponível para o período.")

    # subtract negative adjustments in period
    negatives = CommissionEvent.objects.filter(
        beneficiary_type=beneficiary_type,
        event_type__in=[EventType.ADJUSTMENT_NEGATIVE, EventType.CHARGEBACK],
        status=EventStatus.AVAILABLE,
        competence_date__gte=period_start,
        competence_date__lte=period_end,
        settlement__isnull=True,
    )
    if salesperson:
        negatives = negatives.filter(salesperson=salesperson)
    if commercial_partner:
        negatives = negatives.filter(commercial_partner=commercial_partner)
    neg_events = list(negatives.select_for_update())

    available = sum((e.commission_amount for e in events), Decimal("0.00"))
    reversed_amt = sum((e.commission_amount for e in neg_events), Decimal("0.00"))
    net = available - reversed_amt
    if net <= 0:
        raise ValidationError("Saldo líquido do fechamento deve ser positivo.")

    settlement = CommissionSettlement(
        number=next_settlement_number(),
        period_start=period_start,
        period_end=period_end,
        beneficiary_type=beneficiary_type,
        salesperson=salesperson,
        commercial_partner=commercial_partner,
        status=SettlementStatus.UNDER_REVIEW,
        provisioned_amount=Decimal("0.00"),
        available_amount=available,
        paid_amount=Decimal("0.00"),
        reversed_amount=reversed_amt,
        net_amount=net,
        notes=notes or "",
        created_by=actor,
        updated_by=actor,
    )
    settlement.save()

    for event in events + neg_events:
        included = event.commission_amount
        if event.settlement_id:
            raise ValidationError(f"Evento {event.number} já está em outro fechamento.")
        CommissionSettlementItem.objects.create(
            settlement=settlement,
            commission_event=event,
            included_amount=included,
        )
        event.settlement = settlement
        event.save(update_fields=["settlement", "updated_at"])

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="commissions",
        action="create_settlement",
        obj=settlement,
    )
    return settlement


@transaction.atomic
def approve_settlement(*, settlement, actor, request=None):
    if settlement.status not in {SettlementStatus.DRAFT, SettlementStatus.UNDER_REVIEW}:
        raise ValidationError("Fechamento não está aguardando aprovação.")
    settlement.status = SettlementStatus.APPROVED
    settlement.approved_by = actor
    settlement.approved_at = timezone.now()
    settlement.updated_by = actor
    settlement.save(
        update_fields=["status", "approved_by", "approved_at", "updated_by", "updated_at"],
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commissions",
        action="approve_settlement",
        obj=settlement,
    )
    return settlement


@transaction.atomic
def cancel_settlement(*, settlement, actor, reason, request=None):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Motivo obrigatório.")
    if settlement.status in {SettlementStatus.PAID, SettlementStatus.CLOSED}:
        raise ValidationError("Fechamento pago/encerrado não pode ser cancelado.")
    if settlement.payable_id:
        raise ValidationError("Cancele a conta a pagar vinculada antes.")
    for item in settlement.items.select_related("commission_event"):
        ev = item.commission_event
        ev.settlement = None
        ev.save(update_fields=["settlement", "updated_at"])
    settlement.status = SettlementStatus.CANCELLED
    settlement.notes = (settlement.notes + f"\nCancelamento: {reason}").strip()
    settlement.updated_by = actor
    settlement.save(update_fields=["status", "notes", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commissions",
        action="cancel_settlement",
        obj=settlement,
        metadata={"reason": reason[:500]},
    )
    return settlement


@transaction.atomic
def generate_payable_from_settlement(*, settlement, actor, due_date, payment_term=None, request=None):
    if settlement.status != SettlementStatus.APPROVED:
        raise ValidationError("Fechamento precisa estar aprovado.")
    if settlement.payable_id:
        raise ValidationError("Fechamento já possui conta a pagar.")
    category = FinancialCategory.objects.filter(
        code="comissoes-comerciais",
        category_type=CategoryType.EXPENSE,
        is_active=True,
    ).first()
    from finance.models import CostCenter

    cost_center = CostCenter.objects.filter(code="comercial", is_active=True).first()
    if settlement.salesperson:
        supplier_name = settlement.salesperson.display_name
    else:
        supplier_name = settlement.commercial_partner.name

    payable = create_payable(
        data={
            "supplier_name": supplier_name,
            "description": f"Comissões {settlement.number}",
            "category": category,
            "cost_center": cost_center,
            "issue_date": timezone.localdate(),
            "due_date": due_date,
            "original_amount": settlement.net_amount,
            "reference_type": "commission_settlement",
            "reference_id": settlement.pk,
            "notes": f"Fechamento {settlement.number}",
        },
        actor=actor,
        request=request,
        payment_term=payment_term,
        first_due_date=due_date,
    )
    settlement.payable = payable
    settlement.updated_by = actor
    settlement.save(update_fields=["payable", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="commissions",
        action="generate_payable_from_settlement",
        obj=settlement,
        metadata={"payable": payable.number},
    )
    return payable


@transaction.atomic
def register_commission_payment(
    *,
    settlement,
    amount,
    payment_date,
    actor,
    payment_method=None,
    financial_account=None,
    reference="",
    notes="",
    request=None,
):
    if settlement.status not in {
        SettlementStatus.APPROVED,
        SettlementStatus.PARTIALLY_PAID,
    }:
        raise ValidationError("Fechamento não está aprovado para pagamento.")
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValidationError("Valor deve ser positivo.")
    outstanding = settlement.net_amount - settlement.paid_amount
    if amount > outstanding:
        raise ValidationError("Valor supera o saldo do fechamento.")

    payment = CommissionPayment(
        number=next_payment_number(),
        settlement=settlement,
        payment_date=payment_date,
        amount=amount,
        payment_method=payment_method,
        financial_account=financial_account,
        reference=reference or "",
        notes=notes or "",
        status=PaymentStatus.CONFIRMED,
        created_by=actor,
    )
    payment.save()

    settlement.paid_amount += amount
    if settlement.paid_amount >= settlement.net_amount:
        settlement.status = SettlementStatus.PAID
    else:
        settlement.status = SettlementStatus.PARTIALLY_PAID
    settlement.updated_by = actor
    settlement.save(update_fields=["paid_amount", "status", "updated_by", "updated_at"])

    # payment event on ledger
    CommissionEvent(
        number=next_event_number(),
        beneficiary_type=settlement.beneficiary_type,
        salesperson=settlement.salesperson,
        commercial_partner=settlement.commercial_partner,
        beneficiary_name_snapshot=(
            settlement.salesperson.display_name
            if settlement.salesperson
            else settlement.commercial_partner.name
        ),
        event_type=EventType.PAYMENT,
        status=EventStatus.PAID,
        source_type="commission_payment",
        source_id=payment.pk,
        calculation_basis_amount=amount,
        commission_amount=amount,
        eligible_amount=amount,
        event_date=payment_date,
        competence_date=payment_date,
        description=f"Pagamento {payment.number} — {settlement.number}",
        settlement=settlement,
        created_by=actor,
    ).save()

    if financial_account:
        FinancialMovement.objects.create(
            number=next_movement_number(),
            movement_type=MovementType.EXPENSE,
            financial_account=financial_account,
            amount=amount,
            movement_date=payment_date,
            description=f"Pagamento de comissão {payment.number}",
            reference_type="commission_payment",
            reference_id=payment.pk,
            created_by=actor,
        )

    # mark release events as paid when fully settled
    if settlement.status == SettlementStatus.PAID:
        for item in settlement.items.select_related("commission_event"):
            ev = item.commission_event
            if ev.event_type == EventType.RELEASE and ev.status == EventStatus.AVAILABLE:
                ev.status = EventStatus.PAID
                ev.save(update_fields=["status", "updated_at"])

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="commissions",
        action="register_commission_payment",
        obj=payment,
    )
    return payment
