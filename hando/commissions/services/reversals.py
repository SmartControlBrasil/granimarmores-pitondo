# ruff: noqa: PLR0913
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit_event
from commissions.models import CommissionEvent
from commissions.models import EventStatus
from commissions.models import EventType
from commissions.models import ReversalReason
from commissions.services.numbering import next_event_number
from commissions.services.provisioning import sale_q


@transaction.atomic
def reverse_commission_event(*, event, actor, reason, request=None, reason_code=None):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Motivo do estorno é obrigatório.")
    if event.status in {EventStatus.REVERSED, EventStatus.CANCELLED}:
        raise ValidationError("Evento já estornado/cancelado.")
    if event.event_type == EventType.REVERSAL:
        raise ValidationError("Não é possível estornar um estorno.")
    if event.reversals.exclude(status=EventStatus.CANCELLED).exists():
        raise ValidationError("Estorno já registrado para este evento.")

    today = timezone.localdate()
    reversal = CommissionEvent(
        number=next_event_number(),
        beneficiary_type=event.beneficiary_type,
        salesperson=event.salesperson,
        commercial_partner=event.commercial_partner,
        beneficiary_name_snapshot=event.beneficiary_name_snapshot,
        beneficiary_document_snapshot=event.beneficiary_document_snapshot,
        event_type=EventType.REVERSAL,
        status=EventStatus.REVERSED,
        source_type=event.source_type,
        source_id=event.source_id,
        quote=event.quote,
        sales_order=event.sales_order,
        receivable=event.receivable,
        receivable_payment=event.receivable_payment,
        policy=event.policy,
        rule=event.rule,
        calculation_basis_amount=event.calculation_basis_amount,
        commission_rate=event.commission_rate,
        commission_amount=event.commission_amount,
        eligible_amount=event.commission_amount,
        event_date=today,
        competence_date=today,
        description=f"Estorno de {event.number}: {reason}",
        metadata={
            "reason": reason,
            "reason_code": reason_code or ReversalReason.MANUAL_CORRECTION,
            "original": event.number,
        },
        reversal_of=event,
        created_by=actor,
    )
    reversal.save()
    event.status = EventStatus.REVERSED
    event.save(update_fields=["status", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commissions",
        action="reverse_commission_event",
        obj=reversal,
        metadata={"reason": reason[:500]},
    )
    return reversal


@transaction.atomic
def reverse_releases_for_receivable_payment(*, payment, actor, reason, request=None):
    releases = CommissionEvent.objects.filter(
        event_type=EventType.RELEASE,
        receivable_payment=payment,
    ).exclude(status__in=[EventStatus.REVERSED, EventStatus.CANCELLED])
    result = []
    for event in releases:
        result.append(
            reverse_commission_event(
                event=event,
                actor=actor,
                reason=reason or "Recebimento estornado",
                reason_code=ReversalReason.PAYMENT_REVERSED,
                request=request,
            ),
        )
    return result


@transaction.atomic
def cancel_commissions_for_sale(*, quote=None, sales_order=None, actor, reason, request=None):
    reason = (reason or "").strip() or "Venda/pedido cancelado"
    events = CommissionEvent.objects.filter(
        event_type__in=[EventType.PROVISION, EventType.RELEASE],
    ).filter(sale_q(quote=quote, sales_order=sales_order)).exclude(
        status__in=[EventStatus.REVERSED, EventStatus.CANCELLED],
    )
    result = []
    for event in events:
        if event.status == EventStatus.PAID:
            # chargeback
            cb = CommissionEvent(
                number=next_event_number(),
                beneficiary_type=event.beneficiary_type,
                salesperson=event.salesperson,
                commercial_partner=event.commercial_partner,
                beneficiary_name_snapshot=event.beneficiary_name_snapshot,
                beneficiary_document_snapshot=event.beneficiary_document_snapshot,
                event_type=EventType.CHARGEBACK,
                status=EventStatus.AVAILABLE,
                source_type=event.source_type,
                source_id=event.source_id,
                quote=event.quote,
                sales_order=event.sales_order,
                policy=event.policy,
                calculation_basis_amount=event.calculation_basis_amount,
                commission_rate=event.commission_rate,
                commission_amount=event.commission_amount,
                eligible_amount=event.commission_amount,
                event_date=timezone.localdate(),
                competence_date=timezone.localdate(),
                description=f"Chargeback {event.number}: {reason}",
                metadata={"reason": reason, "original": event.number},
                reversal_of=event,
                created_by=actor,
            )
            cb.save()
            result.append(cb)
            record_audit_event(
                request=request,
                user=actor,
                event_type="create",
                module="commissions",
                action="commission_chargeback",
                obj=cb,
            )
        else:
            result.append(
                reverse_commission_event(
                    event=event,
                    actor=actor,
                    reason=reason,
                    reason_code=ReversalReason.SALE_CANCELLED,
                    request=request,
                ),
            )
    return result


@transaction.atomic
def create_manual_adjustment(
    *,
    beneficiary_type,
    amount,
    direction,
    competence_date,
    reason,
    actor,
    salesperson=None,
    commercial_partner=None,
    reference="",
    request=None,
):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Justificativa obrigatória.")
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValidationError("Valor do ajuste deve ser positivo.")
    if direction not in {"positive", "negative"}:
        raise ValidationError("Direção inválida.")
    if beneficiary_type == "salesperson" and not salesperson:
        raise ValidationError("Vendedor obrigatório.")
    if beneficiary_type == "commercial_partner" and not commercial_partner:
        raise ValidationError("Parceiro obrigatório.")

    event_type = (
        EventType.ADJUSTMENT_POSITIVE if direction == "positive" else EventType.ADJUSTMENT_NEGATIVE
    )
    today = timezone.localdate()
    name = salesperson.display_name if salesperson else commercial_partner.name
    event = CommissionEvent(
        number=next_event_number(),
        beneficiary_type=beneficiary_type,
        salesperson=salesperson,
        commercial_partner=commercial_partner,
        beneficiary_name_snapshot=name,
        beneficiary_document_snapshot=(
            "" if salesperson else (commercial_partner.document or "")
        ),
        event_type=event_type,
        status=EventStatus.AVAILABLE if direction == "positive" else EventStatus.AVAILABLE,
        source_type="manual_adjustment",
        source_id=0,
        calculation_basis_amount=amount,
        commission_rate=Decimal("0"),
        commission_amount=amount,
        eligible_amount=amount,
        event_date=today,
        competence_date=competence_date or today,
        available_date=today,
        description=reason,
        metadata={"direction": direction, "reference": reference},
        created_by=actor,
    )
    # source_id 0 with unique constraint may collide — use timestamp id workaround
    event.source_id = int(timezone.now().timestamp())
    event.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="commissions",
        action="adjust_commission",
        obj=event,
        metadata={"reason": reason[:500]},
    )
    return event
