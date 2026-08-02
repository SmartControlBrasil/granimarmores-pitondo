# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit_event
from audit.services import safe_changes
from commercial.lead_models import Lead
from commercial.lead_models import LeadActivityType
from commercial.lead_models import LeadStatus
from commercial.lead_numbering import next_lead_code
from commercial.lead_queries import can_access_lead
from commercial.lead_workflow import register_lead_activity
from customers.models import Customer


def validate_lead_contact(*, email="", phone="", whatsapp=""):
    if not any([(email or "").strip(), (phone or "").strip(), (whatsapp or "").strip()]):
        raise ValidationError(
            "Informe pelo menos um contato: telefone, WhatsApp ou e-mail.",
        )


def find_customer_matches(*, email="", phone="", whatsapp=""):
    from customers.models import only_digits

    qs = Customer.objects.filter(is_active=True)
    matches = Customer.objects.none()
    email = (email or "").strip()
    phone_digits = only_digits(phone)
    whatsapp_digits = only_digits(whatsapp)
    if email:
        matches = matches | qs.filter(email__iexact=email)
    if phone_digits:
        matches = matches | qs.filter(phone__icontains=phone_digits[-8:])
    if whatsapp_digits:
        matches = matches | qs.filter(mobile_phone__icontains=whatsapp_digits[-8:])
    return matches.distinct()[:10]


@transaction.atomic
def create_lead(*, form, actor, request=None):
    lead = form.save(commit=False)
    validate_lead_contact(email=lead.email, phone=lead.phone, whatsapp=lead.whatsapp)
    if lead.external_source and lead.external_id:
        if Lead.objects.filter(
            external_source=lead.external_source,
            external_id=lead.external_id,
        ).exists():
            raise ValidationError("Lead externo já cadastrado.")
    lead.code = next_lead_code()
    lead.created_by = actor
    lead.updated_by = actor
    lead.save()
    register_lead_activity(
        lead=lead,
        actor=actor,
        activity_type=LeadActivityType.NOTE,
        title="Lead criado",
        description=f"Lead {lead.code} registrado no CRM.",
        request=request,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="commercial",
        action="lead_created",
        obj=lead,
    )
    return lead


@transaction.atomic
def update_lead(*, lead, form, actor, request=None):
    if not can_access_lead(actor, lead):
        raise PermissionDenied("Você não tem acesso a este lead.")
    before = {
        "name": lead.name,
        "email": lead.email,
        "phone": lead.phone,
        "estimated_value": str(lead.estimated_value),
    }
    lead = form.save(commit=False)
    validate_lead_contact(email=lead.email, phone=lead.phone, whatsapp=lead.whatsapp)
    lead.updated_by = actor
    lead.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commercial",
        action="lead_updated",
        obj=lead,
        metadata=safe_changes(before, {"name": lead.name, "email": lead.email}),
    )
    return lead


@transaction.atomic
def convert_lead_to_new_customer(*, lead, actor, request=None):
    from access_control.services.authorization import user_has_permission

    if not user_has_permission(actor, "leads.convert"):
        raise PermissionDenied("Sem permissão para converter lead.")
    if not can_access_lead(actor, lead):
        raise PermissionDenied("Você não tem acesso a este lead.")
    if lead.converted_customer_id:
        raise ValidationError("Lead já convertido.")
    customer = Customer.objects.create(
        customer_type=Customer.CustomerType.COMPANY
        if lead.company_name
        else Customer.CustomerType.INDIVIDUAL,
        name=lead.company_name or lead.name,
        trade_name=lead.name if lead.company_name else "",
        email=lead.email,
        phone=lead.phone,
        mobile_phone=lead.whatsapp or lead.phone,
        commercial_source=lead.commercial_source,
        preferred_contact_channel=lead.contact_channel,
        partner=lead.partner,
        project_type_interest=lead.project_type,
        notes=f"Convertido do lead {lead.code}. {lead.project_description}".strip(),
        created_by=actor,
        updated_by=actor,
    )
    lead.converted_customer = customer
    lead.updated_by = actor
    lead.save(update_fields=["converted_customer", "updated_by", "updated_at"])
    register_lead_activity(
        lead=lead,
        actor=actor,
        activity_type=LeadActivityType.CONVERSION,
        title="Convertido em cliente",
        description=f"Vinculado ao cliente {customer.name}.",
        request=request,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commercial",
        action="lead_converted_new_customer",
        obj=lead,
        metadata={"customer_id": customer.pk},
    )
    return customer


@transaction.atomic
def link_lead_to_customer(*, lead, customer, actor, request=None):
    from access_control.services.authorization import user_has_permission

    if not user_has_permission(actor, "leads.convert"):
        raise PermissionDenied("Sem permissão para converter lead.")
    if not can_access_lead(actor, lead):
        raise PermissionDenied("Você não tem acesso a este lead.")
    if lead.converted_customer_id:
        raise ValidationError("Lead já convertido.")
    lead.converted_customer = customer
    lead.updated_by = actor
    lead.save(update_fields=["converted_customer", "updated_by", "updated_at"])
    register_lead_activity(
        lead=lead,
        actor=actor,
        activity_type=LeadActivityType.CONVERSION,
        title="Vinculado a cliente existente",
        description=f"Vinculado ao cliente {customer.name}.",
        request=request,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commercial",
        action="lead_linked_existing_customer",
        obj=lead,
        metadata={"customer_id": customer.pk},
    )
    return customer


@transaction.atomic
def create_quote_from_lead(*, lead, actor, request=None):
    from access_control.services.authorization import user_has_permission
    from django.utils import timezone as tz

    from quotes.models import Quote
    from quotes.services.numbering import next_quote_number

    if not can_access_lead(actor, lead):
        raise PermissionDenied("Você não tem acesso a este lead.")
    if not lead.converted_customer_id:
        raise ValidationError("Converta o lead em cliente antes de criar orçamento.")
    if not user_has_permission(actor, "quotes.create"):
        raise PermissionDenied("Sem permissão para criar orçamento.")
    salesperson = lead.assigned_salesperson
    if not salesperson:
        salesperson = getattr(actor, "salesperson", None)
    if not salesperson:
        raise ValidationError("Lead sem vendedor responsável.")

    quote = Quote(
        customer=lead.converted_customer,
        salesperson=salesperson,
        lead=lead,
        commercial_source=lead.commercial_source,
        partner=lead.partner,
        project_type=lead.project_type,
        valid_until=tz.localdate(),
        created_by=actor,
        updated_by=actor,
    )
    quote.number = next_quote_number()
    quote.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="quotes",
        action="quote_created_from_lead",
        obj=quote,
        metadata={"lead_id": lead.pk},
    )
    register_lead_activity(
        lead=lead,
        actor=actor,
        activity_type=LeadActivityType.PROPOSAL,
        title="Orçamento criado",
        description=f"Orçamento {quote.number} vinculado ao lead.",
        request=request,
    )
    return quote
