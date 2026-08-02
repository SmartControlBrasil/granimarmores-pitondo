"""Integração de pontuação com eventos do CRM e orçamentos."""
from commercial.lead_models import LeadStatus
from commercial.performance_models import ScoreEventType
from commercial.performance_score import record_sales_value_bonus
from commercial.performance_score import record_score_event


def _salesperson_for_lead(lead):
    return lead.assigned_salesperson if lead.assigned_salesperson_id else None


def score_lead_created(*, lead, actor=None, request=None):
    salesperson = _salesperson_for_lead(lead)
    if not salesperson:
        return None
    return record_score_event(
        salesperson=salesperson,
        event_type=ScoreEventType.LEAD_CREATED,
        reference_type="lead",
        reference_id=lead.pk,
        reference_label=lead.code,
        occurred_at=lead.created_at,
        description=f"Lead {lead.code} criado",
        actor=actor,
        request=request,
    )


def score_first_contact(*, lead, actor=None, request=None, occurred_at=None):
    salesperson = _salesperson_for_lead(lead)
    if not salesperson:
        return None
    return record_score_event(
        salesperson=salesperson,
        event_type=ScoreEventType.FIRST_CONTACT,
        reference_type="lead",
        reference_id=lead.pk,
        reference_label=lead.code,
        occurred_at=occurred_at or lead.first_contact_at,
        description=f"Primeiro contato — {lead.code}",
        actor=actor,
        request=request,
    )


def score_lead_qualified(*, lead, actor=None, request=None):
    salesperson = _salesperson_for_lead(lead)
    if not salesperson:
        return None
    return record_score_event(
        salesperson=salesperson,
        event_type=ScoreEventType.LEAD_QUALIFIED,
        reference_type="lead",
        reference_id=lead.pk,
        reference_label=lead.code,
        description=f"Lead qualificado — {lead.code}",
        actor=actor,
        request=request,
    )


def score_measurement_completed(*, lead, actor=None, request=None):
    salesperson = _salesperson_for_lead(lead)
    if not salesperson:
        return None
    return record_score_event(
        salesperson=salesperson,
        event_type=ScoreEventType.MEASUREMENT_COMPLETED,
        reference_type="lead",
        reference_id=lead.pk,
        reference_label=lead.code,
        description=f"Medição concluída — {lead.code}",
        actor=actor,
        request=request,
    )


def score_lead_won(*, lead, actor=None, request=None):
    salesperson = _salesperson_for_lead(lead)
    if not salesperson:
        return None
    return record_score_event(
        salesperson=salesperson,
        event_type=ScoreEventType.LEAD_WON,
        reference_type="lead",
        reference_id=lead.pk,
        reference_label=lead.code,
        occurred_at=lead.won_at,
        description=f"Lead ganho — {lead.code}",
        actor=actor,
        request=request,
    )


def score_quote_created(*, quote, actor=None, request=None):
    if not quote.salesperson_id:
        return None
    return record_score_event(
        salesperson=quote.salesperson,
        event_type=ScoreEventType.QUOTE_CREATED,
        reference_type="quote",
        reference_id=quote.pk,
        reference_label=quote.number,
        description=f"Orçamento {quote.number} criado",
        actor=actor,
        request=request,
    )


def score_quote_sent(*, quote, actor=None, request=None):
    if not quote.salesperson_id:
        return None
    return record_score_event(
        salesperson=quote.salesperson,
        event_type=ScoreEventType.QUOTE_SENT,
        reference_type="quote",
        reference_id=quote.pk,
        reference_label=quote.number,
        occurred_at=quote.sent_at,
        description=f"Orçamento {quote.number} enviado",
        actor=actor,
        request=request,
    )


def score_follow_up_completed(*, task, actor=None, request=None):
    lead = task.lead
    salesperson = _salesperson_for_lead(lead)
    if not salesperson:
        return None
    if task.completed_at and task.completed_at > task.due_at:
        return None
    return record_score_event(
        salesperson=salesperson,
        event_type=ScoreEventType.FOLLOW_UP_COMPLETED,
        reference_type="lead_task",
        reference_id=task.pk,
        reference_label=task.title[:200],
        occurred_at=task.completed_at,
        description=f"Follow-up concluído — {lead.code}",
        actor=actor,
        request=request,
    )


def score_quote_accepted(*, quote, actor=None, request=None):
    if not quote.salesperson_id:
        return None
    record_sales_value_bonus(
        salesperson=quote.salesperson,
        quote=quote,
        actor=actor,
        request=request,
    )
    won_recorded = False
    if quote.lead_id:
        won_recorded = score_lead_won(lead=quote.lead, actor=actor, request=request) is not None
    if not won_recorded:
        record_score_event(
            salesperson=quote.salesperson,
            event_type=ScoreEventType.LEAD_WON,
            reference_type="quote",
            reference_id=quote.pk,
            reference_label=quote.number,
            occurred_at=quote.accepted_at,
            description=f"Orçamento aceito — {quote.number}",
            actor=actor,
            request=request,
        )
    return None


def on_lead_status_changed(*, lead, old_status, new_status, actor=None, request=None):
    if new_status == LeadStatus.CONTACTED:
        score_first_contact(lead=lead, actor=actor, request=request)
    elif new_status == LeadStatus.QUALIFIED:
        score_lead_qualified(lead=lead, actor=actor, request=request)
    elif new_status == LeadStatus.MEASUREMENT_COMPLETED:
        score_measurement_completed(lead=lead, actor=actor, request=request)
    elif new_status == LeadStatus.WON:
        score_lead_won(lead=lead, actor=actor, request=request)


def on_lead_activity_contact(*, lead, actor=None, request=None, occurred_at=None):
    if lead.first_contact_at:
        score_first_contact(lead=lead, actor=actor, request=request, occurred_at=occurred_at)
