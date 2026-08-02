# ruff: noqa: PLR0913
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.db.models import Sum
from django.utils import timezone

from audit.services import record_audit_event
from commissions.models import CommissionEvent
from commissions.models import EventStatus
from commissions.models import EventType
from commissions.models import TriggerType
from commissions.services.calculation import calculate_commission_amount
from commissions.services.calculation import check_policy_restrictions
from commissions.services.calculation import resolve_basis_amount
from commissions.services.numbering import next_event_number
from commissions.services.policies import find_applicable_policy
from quotes.models import QuoteStatus


def _sum_amount(qs):
    return qs.aggregate(v=Sum("commission_amount"))["v"] or Decimal("0.00")


def _create_event(**kwargs):
    event = CommissionEvent(number=next_event_number(), **kwargs)
    event.save()
    return event


def sale_q(*, quote=None, sales_order=None):
    q = Q()
    if sales_order:
        q |= Q(sales_order=sales_order)
    if quote:
        q |= Q(quote=quote)
    return q


@transaction.atomic
def provision_commission(*, quote=None, sales_order=None, actor, request=None, trigger=None):
    if sales_order and not quote:
        quote = sales_order.quote
    if not quote and not sales_order:
        raise ValidationError("Informe orçamento ou pedido.")
    if quote and quote.status != QuoteStatus.ACCEPTED:
        raise ValidationError("Somente venda aceita (orçamento aceito) gera comissão.")

    trigger = trigger or TriggerType.QUOTE_ACCEPTED
    today = timezone.localdate()
    salesperson = (sales_order.salesperson if sales_order else None) or getattr(quote, "salesperson", None)
    partner = getattr(quote, "partner", None) if quote else None

    created = []
    targets = []
    if salesperson:
        targets.append(("salesperson", salesperson, None))
    if partner and getattr(partner, "is_active", True):
        targets.append(("commercial_partner", None, partner))
    if not targets:
        return []

    for target_key, sp, pt in targets:
        policy, rule = find_applicable_policy(
            trigger_type=trigger,
            target=target_key,
            on_date=today,
            salesperson=sp,
            partner=pt,
            quote=quote,
        )
        if not policy:
            continue
        if check_policy_restrictions(policy=policy, quote=quote):
            continue

        source_type = "sales_order" if sales_order else "quote"
        source_id = sales_order.pk if sales_order else quote.pk
        exists = CommissionEvent.objects.filter(
            event_type=EventType.PROVISION,
            source_type=source_type,
            source_id=source_id,
            beneficiary_type=target_key,
        ).exclude(status__in=[EventStatus.REVERSED, EventStatus.CANCELLED])
        if sp:
            exists = exists.filter(salesperson=sp)
        if pt:
            exists = exists.filter(commercial_partner=pt)
        if exists.exists():
            continue

        basis = resolve_basis_amount(policy=policy, quote=quote, sales_order=sales_order)
        if basis <= 0:
            continue
        amount, rate = calculate_commission_amount(policy=policy, rule=rule, basis_amount=basis)
        if amount <= 0:
            continue

        status = EventStatus.PENDING_APPROVAL if policy.requires_approval else EventStatus.PROVISIONED
        available_date = None
        if not policy.release_only_after_payment and not policy.requires_approval:
            status = EventStatus.AVAILABLE
            available_date = today

        event = _create_event(
            beneficiary_type=target_key,
            salesperson=sp,
            commercial_partner=pt,
            beneficiary_name_snapshot=(sp.display_name if sp else pt.name),
            beneficiary_document_snapshot=("" if sp else (pt.document or "")),
            event_type=EventType.PROVISION,
            status=status,
            source_type=source_type,
            source_id=source_id,
            quote=quote,
            sales_order=sales_order,
            policy=policy,
            rule=rule,
            calculation_basis_amount=basis,
            commission_rate=rate,
            commission_amount=amount,
            eligible_amount=amount,
            event_date=today,
            competence_date=today,
            available_date=available_date,
            description=f"Provisionamento — {quote.number if quote else source_id}",
            metadata={"trigger": trigger},
            created_by=actor,
        )
        created.append(event)
        record_audit_event(
            request=request,
            user=actor,
            event_type="create",
            module="commissions",
            action="provision_commission",
            obj=event,
            description=f"Provisionou {event.number} ({amount})",
        )
    return created


@transaction.atomic
def release_commission_for_receivable_payment(*, payment, actor, request=None):
    if payment.status != "confirmed":
        return []
    receivable = payment.installment.receivable
    quote = receivable.quote
    sales_order = receivable.sales_order
    if not quote and not sales_order:
        return []

    provisions = list(
        CommissionEvent.objects.filter(
            event_type=EventType.PROVISION,
        )
        .filter(sale_q(quote=quote, sales_order=sales_order))
        .exclude(status__in=[EventStatus.REVERSED, EventStatus.CANCELLED]),
    )
    if not provisions:
        provisions = provision_commission(
            quote=quote,
            sales_order=sales_order,
            actor=actor,
            request=request,
            trigger=TriggerType.PAYMENT_RECEIVED,
        )

    order_total = Decimal("0")
    if sales_order:
        order_total = Decimal(str(sales_order.total or "0"))
    elif quote:
        order_total = Decimal(str(quote.grand_total or "0"))
    if order_total <= 0:
        return []

    payment_amount = Decimal(str(payment.amount))
    today = timezone.localdate()
    created = []

    for provision in provisions:
        if CommissionEvent.objects.filter(
            event_type=EventType.RELEASE,
            source_type="receivable_payment",
            source_id=payment.pk,
            beneficiary_type=provision.beneficiary_type,
            salesperson=provision.salesperson,
            commercial_partner=provision.commercial_partner,
        ).exclude(status__in=[EventStatus.REVERSED, EventStatus.CANCELLED]).exists():
            continue

        ratio = payment_amount / order_total
        release_amount = (provision.commission_amount * ratio).quantize(Decimal("0.01"))
        already = _sum_amount(
            CommissionEvent.objects.filter(
                event_type=EventType.RELEASE,
                beneficiary_type=provision.beneficiary_type,
                salesperson=provision.salesperson,
                commercial_partner=provision.commercial_partner,
            )
            .filter(sale_q(quote=quote, sales_order=sales_order))
            .exclude(status__in=[EventStatus.REVERSED, EventStatus.CANCELLED]),
        )
        max_release = provision.commission_amount - already
        if max_release <= 0:
            continue
        release_amount = min(release_amount, max_release)
        if release_amount <= 0:
            continue

        event = _create_event(
            beneficiary_type=provision.beneficiary_type,
            salesperson=provision.salesperson,
            commercial_partner=provision.commercial_partner,
            beneficiary_name_snapshot=provision.beneficiary_name_snapshot,
            beneficiary_document_snapshot=provision.beneficiary_document_snapshot,
            event_type=EventType.RELEASE,
            status=EventStatus.AVAILABLE,
            source_type="receivable_payment",
            source_id=payment.pk,
            quote=quote,
            sales_order=sales_order,
            receivable=receivable,
            receivable_payment=payment,
            policy=provision.policy,
            rule=provision.rule,
            calculation_basis_amount=payment_amount,
            commission_rate=provision.commission_rate,
            commission_amount=release_amount,
            eligible_amount=release_amount,
            event_date=today,
            competence_date=today,
            available_date=today,
            description=f"Liberação por recebimento {payment.number}",
            metadata={"provision": provision.number, "ratio": str(ratio)},
            created_by=actor,
        )
        created.append(event)
        if provision.status in {EventStatus.PROVISIONED, EventStatus.APPROVED, EventStatus.BLOCKED}:
            provision.status = EventStatus.AVAILABLE
            provision.available_date = today
            provision.save(update_fields=["status", "available_date", "updated_at"])
        record_audit_event(
            request=request,
            user=actor,
            event_type="create",
            module="commissions",
            action="release_commission",
            obj=event,
        )
    return created
