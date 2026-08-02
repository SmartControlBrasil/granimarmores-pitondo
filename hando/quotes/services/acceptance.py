# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from commercial.lead_models import LeadActivityType
from commercial.lead_models import LeadStatus
from commercial.lead_workflow import change_lead_status
from commercial.lead_workflow import register_lead_activity
from commercial.performance_score_hooks import score_quote_accepted
from production.models import SalesOrder
from production.models import SalesOrderStatus
from quotes.models import QuoteAcceptance
from quotes.models import QuoteAcceptanceStatus
from quotes.models import QuoteStatus
from quotes.services.workflow import change_status


ACCEPTABLE_STATUSES = {QuoteStatus.SENT, QuoteStatus.VIEWED}


@transaction.atomic
def accept_quote(
    *,
    quote,
    actor,
    accepted_at=None,
    customer_name="",
    customer_document="",
    acceptance_notes="",
    acceptance_channel=None,
    request=None,
    create_order=True,
):
    if not user_has_permission(actor, "quotes.accept"):
        raise PermissionDenied("Sem permissão para aceitar orçamento.")

    if quote.status in {QuoteStatus.DRAFT, QuoteStatus.CANCELLED, QuoteStatus.REJECTED}:
        raise ValidationError("Orçamento não pode ser aceito neste estado.")
    if quote.status == QuoteStatus.ACCEPTED:
        existing = SalesOrder.objects.filter(quote=quote).exclude(
            status=SalesOrderStatus.CANCELLED,
        ).first()
        return existing

    if quote.status == QuoteStatus.EXPIRED:
        if not user_has_permission(actor, "quotes.accept_expired"):
            raise ValidationError("Orçamento expirado exige permissão especial.")
    elif quote.status not in ACCEPTABLE_STATUSES:
        raise ValidationError(
            "Somente orçamentos enviados ou visualizados podem ser aceitos.",
        )

    if quote.valid_until and quote.valid_until < timezone.localdate():
        if quote.status != QuoteStatus.EXPIRED and not user_has_permission(
            actor,
            "quotes.accept_expired",
        ):
            raise ValidationError("Orçamento fora da validade.")

    now = accepted_at or timezone.now()
    if quote.status != QuoteStatus.ACCEPTED:
        change_status(
            quote=quote,
            target_status=QuoteStatus.ACCEPTED,
            actor=actor,
            request=request,
        )

    QuoteAcceptance.objects.filter(quote=quote, is_current=True).update(is_current=False)
    acceptance = QuoteAcceptance.objects.create(
        quote=quote,
        status=QuoteAcceptanceStatus.ACCEPTED,
        accepted_at=now,
        customer_name=(customer_name or quote.customer.name)[:160],
        customer_document=(customer_document or "")[:40],
        contact_channel=acceptance_channel,
        notes=acceptance_notes or "",
        recorded_by=actor,
        is_current=True,
    )
    quote.accepted_at = now
    quote.accepted_by_name = acceptance.customer_name
    quote.accepted_by_document = acceptance.customer_document
    quote.updated_by = actor
    quote.save(update_fields=[
        "accepted_at",
        "accepted_by_name",
        "accepted_by_document",
        "updated_by",
        "updated_at",
    ])

    if quote.lead_id:
        lead = quote.lead
        if lead.status not in {LeadStatus.WON, LeadStatus.LOST, LeadStatus.DISQUALIFIED}:
            try:
                change_lead_status(
                    lead=lead,
                    new_status=LeadStatus.WON,
                    actor=actor,
                    request=request,
                )
            except (ValidationError, PermissionDenied):
                register_lead_activity(
                    lead=lead,
                    actor=actor,
                    activity_type=LeadActivityType.NOTE,
                    title="Orçamento aceito",
                    description=f"Orçamento {quote.number} aceito pelo cliente.",
                    request=request,
                )

    score_quote_accepted(quote=quote, actor=actor, request=request)
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="quotes",
        action="quote_accepted",
        obj=quote,
        metadata={"acceptance_id": acceptance.pk, "customer_name": acceptance.customer_name},
    )

    if create_order:
        from production.services.orders import create_sales_order_from_quote

        return create_sales_order_from_quote(quote=quote, actor=actor, request=request)
    return acceptance


@transaction.atomic
def refuse_quote(
    *,
    quote,
    actor,
    loss_reason,
    notes="",
    acceptance_channel=None,
    request=None,
):
    if not user_has_permission(actor, "quotes.refuse"):
        raise PermissionDenied("Sem permissão para recusar orçamento.")
    if not loss_reason:
        raise ValidationError("Motivo de perda é obrigatório.")
    if loss_reason.requires_notes and not (notes or "").strip():
        raise ValidationError("Este motivo exige observação.")
    if quote.status in {QuoteStatus.DRAFT, QuoteStatus.CANCELLED, QuoteStatus.ACCEPTED}:
        raise ValidationError("Orçamento não pode ser recusado neste estado.")

    now = timezone.now()
    QuoteAcceptance.objects.filter(quote=quote, is_current=True).update(is_current=False)
    acceptance = QuoteAcceptance.objects.create(
        quote=quote,
        status=QuoteAcceptanceStatus.REFUSED,
        rejected_at=now,
        notes=notes or "",
        loss_reason=loss_reason,
        contact_channel=acceptance_channel,
        recorded_by=actor,
        is_current=True,
    )
    quote.updated_by = actor
    quote.save(update_fields=["updated_by", "updated_at"])

    if quote.lead_id:
        lead = quote.lead
        if lead.status not in {LeadStatus.LOST, LeadStatus.DISQUALIFIED, LeadStatus.WON}:
            try:
                change_lead_status(
                    lead=lead,
                    new_status=LeadStatus.LOST,
                    actor=actor,
                    request=request,
                    loss_reason=loss_reason,
                    loss_notes=notes,
                )
            except (ValidationError, PermissionDenied):
                register_lead_activity(
                    lead=lead,
                    actor=actor,
                    activity_type=LeadActivityType.LOSS,
                    title="Orçamento recusado",
                    description=notes or loss_reason.name,
                    request=request,
                )

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="quotes",
        action="quote_refused",
        obj=quote,
        metadata={"acceptance_id": acceptance.pk, "loss_reason_id": loss_reason.pk},
    )
    return acceptance
