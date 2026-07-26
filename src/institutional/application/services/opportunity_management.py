from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from src.institutional.application.services.access_policy import can_change_opportunity
from src.institutional.application.services.access_policy import can_convert_lead_to_opportunity
from src.institutional.application.services.access_policy import get_visible_contact_requests
from src.institutional.application.services.access_policy import get_visible_opportunities
from src.institutional.application.services.access_policy import get_visible_quotes
from src.institutional.application.services.access_policy import is_administrator
from src.institutional.application.services.access_policy import is_sales_manager
from src.institutional.infrastructure.django.models import ContactRequest
from src.institutional.infrastructure.django.models import Opportunity
from src.institutional.infrastructure.django.models import OpportunityAuditLog
from src.institutional.infrastructure.django.models import Quote
from src.institutional.infrastructure.django.models import QuoteItem
from src.institutional.infrastructure.django.models import QuoteSequence

STAGE_DEFAULT_PROBABILITY = {
    Opportunity.Stage.QUALIFICATION: 20,
    Opportunity.Stage.QUOTATION: 40,
    Opportunity.Stage.QUOTATION_SENT: 55,
    Opportunity.Stage.NEGOTIATION: 70,
    Opportunity.Stage.WON: 100,
    Opportunity.Stage.LOST: 0,
}

VALID_QUOTE_TRANSITIONS = {
    Quote.Status.DRAFT: {Quote.Status.READY, Quote.Status.CANCELLED},
    Quote.Status.READY: {Quote.Status.DRAFT, Quote.Status.CANCELLED},
    Quote.Status.SENT: {Quote.Status.ACCEPTED, Quote.Status.REJECTED, Quote.Status.EXPIRED, Quote.Status.CANCELLED},
    Quote.Status.REJECTED: {Quote.Status.CANCELLED},
    Quote.Status.EXPIRED: {Quote.Status.CANCELLED},
    Quote.Status.ACCEPTED: set(),
    Quote.Status.CANCELLED: set(),
}

EDITABLE_QUOTE_STATUSES = {Quote.Status.DRAFT, Quote.Status.READY}


def create_opportunity_audit_log(*, opportunity, action, actor=None, previous_value="", new_value=""):
    return OpportunityAuditLog.objects.create(
        opportunity=opportunity,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        previous_value=previous_value or "",
        new_value=new_value or "",
    )


@transaction.atomic
def create_opportunity_from_lead(*, contact_request_id, actor, assigned_to=None):
    lead = get_visible_contact_requests(actor).select_for_update().get(pk=contact_request_id)
    if not can_convert_lead_to_opportunity(actor, lead):
        raise PermissionDenied("Você não tem permissão para converter este lead.")
    responsible = assigned_to or lead.assigned_to
    if responsible is None:
        raise ValidationError("Defina um responsável para criar a oportunidade.")
    if lead.assigned_to_id and responsible.pk != lead.assigned_to_id and not (is_administrator(actor) or is_sales_manager(actor)):
        raise PermissionDenied("Você não pode alterar o responsável nesta conversão.")
    try:
        opportunity, created = Opportunity.objects.get_or_create(
            contact_request=lead,
            defaults={
                "title": lead.ambiente or f"Projeto de {lead.nome}",
                "customer_name": lead.nome,
                "customer_email": lead.email,
                "customer_phone": lead.telefone,
                "city": lead.cidade,
                "assigned_to": responsible,
                "probability": STAGE_DEFAULT_PROBABILITY[Opportunity.Stage.QUALIFICATION],
                "created_by": actor,
            },
        )
    except IntegrityError as exc:
        raise ValidationError("Este lead já possui oportunidade.") from exc
    if not created:
        raise ValidationError("Este lead já possui oportunidade.")
    create_opportunity_audit_log(
        opportunity=opportunity,
        actor=actor,
        action=OpportunityAuditLog.Action.OPPORTUNITY_CREATED,
        new_value=str(opportunity.pk),
    )
    return opportunity


@transaction.atomic
def change_opportunity_stage(*, opportunity_id, stage, actor, lost_reason="", lost_notes=""):
    valid_stages = {choice for choice, _ in Opportunity.Stage.choices}
    if stage not in valid_stages:
        raise ValidationError("Etapa inválida.")
    opportunity = get_visible_opportunities(actor).select_for_update().get(pk=opportunity_id)
    if not can_change_opportunity(actor, opportunity):
        raise PermissionDenied("Você não tem permissão para alterar esta oportunidade.")
    if stage == Opportunity.Stage.LOST and not lost_reason:
        raise ValidationError("Informe o motivo da perda.")
    if stage == Opportunity.Stage.WON and not opportunity.quotes.filter(status=Quote.Status.ACCEPTED).exists():
        if not ((is_administrator(actor) or is_sales_manager(actor)) and lost_notes.strip()):
            raise ValidationError("Para marcar como ganho, aceite um orçamento ou informe uma justificativa gerencial.")
    previous = opportunity.stage
    if previous == stage:
        return opportunity
    opportunity.stage = stage
    if stage in {Opportunity.Stage.WON, Opportunity.Stage.LOST}:
        opportunity.probability = STAGE_DEFAULT_PROBABILITY[stage]
    if stage == Opportunity.Stage.LOST:
        opportunity.lost_reason = lost_reason
        opportunity.lost_notes = lost_notes.strip()
    else:
        opportunity.lost_reason = ""
        opportunity.lost_notes = ""
    opportunity.save(update_fields=["stage", "probability", "lost_reason", "lost_notes", "updated_at"])
    create_opportunity_audit_log(
        opportunity=opportunity,
        actor=actor,
        action=OpportunityAuditLog.Action.STAGE_CHANGED,
        previous_value=previous,
        new_value=stage,
    )
    return opportunity


def _next_quote_number():
    year = timezone.localdate().year
    sequence, _ = QuoteSequence.objects.get_or_create(year=year, defaults={"next_number": 1})
    sequence = QuoteSequence.objects.select_for_update().get(pk=sequence.pk)
    current = sequence.next_number
    sequence.next_number = current + 1
    sequence.save(update_fields=["next_number"])
    return f"ORC-{year}-{current:06d}"


@transaction.atomic
def create_quote(*, opportunity_id, actor, validity_date=None, notes=""):
    opportunity = get_visible_opportunities(actor).select_for_update().get(pk=opportunity_id)
    if not can_change_opportunity(actor, opportunity):
        raise PermissionDenied("Você não tem permissão para criar orçamento nesta oportunidade.")
    quote = Quote.objects.create(
        opportunity=opportunity,
        number=_next_quote_number(),
        revision=0,
        validity_date=validity_date,
        notes=notes.strip(),
        created_by=actor,
    )
    create_opportunity_audit_log(
        opportunity=opportunity,
        actor=actor,
        action=OpportunityAuditLog.Action.QUOTE_CREATED,
        new_value=quote.number,
    )
    return quote


@transaction.atomic
def create_quote_revision(*, quote_id, actor):
    source = get_visible_quotes(actor).select_for_update().get(pk=quote_id)
    if not can_change_opportunity(actor, source.opportunity):
        raise PermissionDenied("Você não tem permissão para revisar este orçamento.")
    latest = Quote.objects.select_for_update().filter(number=source.number).aggregate(max_revision=Max("revision"))["max_revision"] or 0
    quote = Quote.objects.create(
        opportunity=source.opportunity,
        number=source.number,
        revision=latest + 1,
        validity_date=source.validity_date,
        notes=source.notes,
        created_by=actor,
    )
    for item in source.items.all():
        QuoteItem.objects.create(
            quote=quote,
            description=item.description,
            quantity=item.quantity,
            unit=item.unit,
            unit_price=item.unit_price,
            total=item.total,
            position=item.position,
        )
    recalculate_quote(quote=quote, discount_amount=source.discount_amount)
    create_opportunity_audit_log(
        opportunity=quote.opportunity,
        actor=actor,
        action=OpportunityAuditLog.Action.QUOTE_REVISION_CREATED,
        new_value=f"{quote.number} rev. {quote.revision}",
    )
    return quote


def recalculate_quote(*, quote, discount_amount=None):
    subtotal = Decimal("0.00")
    for item in quote.items.all():
        item.total = (item.quantity * item.unit_price).quantize(Decimal("0.01"))
        item.save(update_fields=["total"])
        subtotal += item.total
    discount = quote.discount_amount if discount_amount is None else discount_amount
    discount = Decimal(discount or 0).quantize(Decimal("0.01"))
    if discount < 0:
        raise ValidationError("O desconto não pode ser negativo.")
    if discount > subtotal:
        raise ValidationError("O desconto não pode ser maior que o subtotal.")
    quote.subtotal = subtotal.quantize(Decimal("0.01"))
    quote.discount_amount = discount
    quote.total = (quote.subtotal - discount).quantize(Decimal("0.01"))
    quote.save(update_fields=["subtotal", "discount_amount", "total", "updated_at"])
    return quote


@transaction.atomic
def update_quote_financials(*, quote_id, actor, discount_amount, validity_date, notes, items_data):
    quote = get_visible_quotes(actor).select_for_update().get(pk=quote_id)
    if not can_change_opportunity(actor, quote.opportunity):
        raise PermissionDenied("Você não tem permissão para alterar este orçamento.")
    if quote.status not in EDITABLE_QUOTE_STATUSES:
        raise ValidationError("Este orçamento não permite edição financeira.")
    quote.validity_date = validity_date
    quote.notes = notes.strip()
    quote.save(update_fields=["validity_date", "notes", "updated_at"])
    keep_ids = []
    existing = {item.pk: item for item in quote.items.select_for_update()}
    for position, data in enumerate(items_data, start=1):
        description = (data.get("description") or "").strip()
        if not description:
            continue
        quantity = Decimal(data.get("quantity") or 0)
        unit_price = Decimal(data.get("unit_price") or 0)
        if quantity <= 0:
            raise ValidationError("A quantidade deve ser maior que zero.")
        if unit_price < 0:
            raise ValidationError("O preço não pode ser negativo.")
        item_id = data.get("id")
        if item_id:
            item = existing.get(int(item_id))
            if item is None:
                raise PermissionDenied("Item inválido para este orçamento.")
        else:
            item = QuoteItem(quote=quote)
        item.description = description
        item.quantity = quantity
        item.unit = data.get("unit") or QuoteItem.Unit.UNIT
        item.unit_price = unit_price
        item.position = position
        item.save()
        keep_ids.append(item.pk)
    quote.items.exclude(pk__in=keep_ids).delete()
    return recalculate_quote(quote=quote, discount_amount=discount_amount)


@transaction.atomic
def change_quote_status(*, quote_id, status, actor):
    valid_statuses = {choice for choice, _ in Quote.Status.choices}
    if status not in valid_statuses:
        raise ValidationError("Status inválido.")
    quote = get_visible_quotes(actor).select_for_update().get(pk=quote_id)
    if not can_change_opportunity(actor, quote.opportunity):
        raise PermissionDenied("Você não tem permissão para alterar este orçamento.")
    previous = quote.status
    if previous == status:
        return quote
    if status not in VALID_QUOTE_TRANSITIONS[previous]:
        raise ValidationError("Transição de status inválida.")
    if status == Quote.Status.ACCEPTED and Quote.objects.filter(number=quote.number, status=Quote.Status.ACCEPTED).exclude(pk=quote.pk).exists():
        raise ValidationError("Já existe uma revisão aceita para este orçamento.")
    quote.status = status
    quote.save(update_fields=["status", "updated_at"])
    action = None
    if status == Quote.Status.SENT:
        action = OpportunityAuditLog.Action.QUOTE_SENT
    elif status == Quote.Status.ACCEPTED:
        action = OpportunityAuditLog.Action.QUOTE_ACCEPTED
    elif status == Quote.Status.REJECTED:
        action = OpportunityAuditLog.Action.QUOTE_REJECTED
    if action:
        create_opportunity_audit_log(
            opportunity=quote.opportunity,
            actor=actor,
            action=action,
            previous_value=previous,
            new_value=status,
        )
    if status == Quote.Status.ACCEPTED:
        opportunity = Opportunity.objects.select_for_update().get(pk=quote.opportunity_id)
        old_stage = opportunity.stage
        opportunity.stage = Opportunity.Stage.WON
        opportunity.probability = 100
        opportunity.save(update_fields=["stage", "probability", "updated_at"])
        create_opportunity_audit_log(
            opportunity=opportunity,
            actor=actor,
            action=OpportunityAuditLog.Action.STAGE_CHANGED,
            previous_value=old_stage,
            new_value=Opportunity.Stage.WON,
        )
    return quote
