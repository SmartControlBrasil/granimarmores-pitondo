# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from audit.services import safe_changes
from commercial.lead_models import Lead
from commercial.lead_models import LeadActivity
from commercial.lead_models import LeadActivityType
from commercial.lead_models import LeadStatus
from commercial.lead_models import LOSS_STATUSES
from commercial.lead_models import TERMINAL_STATUSES
from commercial.lead_queries import can_access_lead


ALLOWED_TRANSITIONS = {
    LeadStatus.NEW: {LeadStatus.TRIAGE},
    LeadStatus.TRIAGE: {LeadStatus.ASSIGNED},
    LeadStatus.ASSIGNED: {LeadStatus.CONTACTED},
    LeadStatus.CONTACTED: {LeadStatus.QUALIFIED, LeadStatus.DISQUALIFIED},
    LeadStatus.QUALIFIED: {
        LeadStatus.MEASUREMENT_SCHEDULED,
        LeadStatus.QUOTE_PREPARATION,
        LeadStatus.LOST,
    },
    LeadStatus.MEASUREMENT_SCHEDULED: {LeadStatus.MEASUREMENT_COMPLETED},
    LeadStatus.MEASUREMENT_COMPLETED: {LeadStatus.QUOTE_PREPARATION},
    LeadStatus.QUOTE_PREPARATION: {LeadStatus.QUOTE_SENT},
    LeadStatus.QUOTE_SENT: {LeadStatus.NEGOTIATION, LeadStatus.WON, LeadStatus.LOST},
    LeadStatus.NEGOTIATION: {LeadStatus.WON, LeadStatus.LOST},
}


def _validate_loss(*, lead, loss_reason, loss_notes):
    if not loss_reason:
        raise ValidationError("Motivo de perda é obrigatório.")
    if loss_reason.requires_notes and not (loss_notes or "").strip():
        raise ValidationError("Este motivo de perda exige observação.")


def _create_activity(*, lead, actor, activity_type, title, description, occurred_at=None, next_action_at=None):
    return LeadActivity.objects.create(
        lead=lead,
        activity_type=activity_type,
        title=title,
        description=description,
        occurred_at=occurred_at or timezone.now(),
        next_action_at=next_action_at,
        created_by=actor,
    )


def _snapshot_status(lead):
    return {
        "status": lead.status,
        "won_at": lead.won_at,
        "lost_at": lead.lost_at,
        "loss_reason_id": lead.loss_reason_id,
    }


@transaction.atomic
def change_lead_status(
    *,
    lead,
    new_status,
    actor,
    request=None,
    loss_reason=None,
    loss_notes="",
    override_reason="",
):
    if not can_access_lead(actor, lead):
        raise PermissionDenied("Você não tem acesso a este lead.")
    if not user_has_permission(actor, "leads.change_status"):
        raise PermissionDenied("Sem permissão para alterar status do lead.")

    old_status = lead.status
    if old_status == new_status:
        return lead

    allowed = ALLOWED_TRANSITIONS.get(old_status, set())
    override = user_has_permission(actor, "leads.override_status")
    if new_status not in allowed:
        if not override:
            raise ValidationError(
                f"Transição inválida de {lead.get_status_display()} "
                f"para {dict(LeadStatus.choices).get(new_status, new_status)}.",
            )
        if not (override_reason or "").strip():
            raise ValidationError("Override de status exige justificativa.")

    if new_status in LOSS_STATUSES:
        if not user_has_permission(actor, "leads.mark_lost"):
            raise PermissionDenied("Sem permissão para marcar perda.")
        _validate_loss(lead=lead, loss_reason=loss_reason, loss_notes=loss_notes)
        lead.loss_reason = loss_reason
        lead.loss_notes = loss_notes or ""
        lead.lost_at = timezone.now()
        lead.won_at = None
    elif new_status == LeadStatus.WON:
        if not user_has_permission(actor, "leads.mark_won"):
            raise PermissionDenied("Sem permissão para marcar ganho.")
        lead.won_at = timezone.now()
        lead.lost_at = None
        lead.loss_reason = None
        lead.loss_notes = ""
    elif new_status == LeadStatus.CONTACTED:
        now = timezone.now()
        if not lead.first_contact_at:
            lead.first_contact_at = now
        lead.last_contact_at = now
    elif new_status in {LeadStatus.ASSIGNED} and lead.status in {LeadStatus.NEW, LeadStatus.TRIAGE}:
        if not lead.assigned_salesperson_id:
            raise ValidationError("Atribua um vendedor antes de avançar para atribuído.")

    before = _snapshot_status(lead)
    lead.status = new_status
    lead.updated_by = actor
    lead.save()
    activity = _create_activity(
        lead=lead,
        actor=actor,
        activity_type=LeadActivityType.STATUS_CHANGE,
        title=f"Status alterado para {lead.get_status_display()}",
        description=(
            f"De {dict(LeadStatus.choices).get(old_status, old_status)} "
            f"para {lead.get_status_display()}."
            + (f" Justificativa: {override_reason}" if override_reason else "")
        ),
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commercial",
        action="lead_status_changed",
        obj=lead,
        metadata=safe_changes(
            before,
            {**_snapshot_status(lead), "activity_id": activity.pk},
        ),
    )
    return lead


@transaction.atomic
def assign_lead_salesperson(*, lead, salesperson, actor, request=None):
    if not can_access_lead(actor, lead):
        raise PermissionDenied("Você não tem acesso a este lead.")
    if not user_has_permission(actor, "leads.assign"):
        raise PermissionDenied("Sem permissão para atribuir lead.")
    if salesperson and not salesperson.is_active:
        raise ValidationError("Vendedor inativo não pode receber leads.")

    previous = lead.assigned_salesperson
    lead.assigned_salesperson = salesperson
    lead.updated_by = actor
    if lead.status in {LeadStatus.NEW, LeadStatus.TRIAGE} and salesperson:
        lead.status = LeadStatus.ASSIGNED
    elif lead.status == LeadStatus.NEW and not salesperson:
        lead.status = LeadStatus.TRIAGE
    lead.save()

    _create_activity(
        lead=lead,
        actor=actor,
        activity_type=LeadActivityType.ASSIGNMENT,
        title="Responsável atualizado",
        description=(
            f"De {previous.display_name if previous else 'nenhum'} "
            f"para {salesperson.display_name if salesperson else 'nenhum'}."
        ),
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commercial",
        action="lead_assigned",
        obj=lead,
        metadata={
            "previous_salesperson_id": previous.pk if previous else None,
            "new_salesperson_id": salesperson.pk if salesperson else None,
        },
    )
    return lead


@transaction.atomic
def reopen_lead(*, lead, actor, reason, request=None):
    if not can_access_lead(actor, lead):
        raise PermissionDenied("Você não tem acesso a este lead.")
    if not user_has_permission(actor, "leads.reopen"):
        raise PermissionDenied("Sem permissão para reabrir lead.")
    if lead.status not in TERMINAL_STATUSES:
        raise ValidationError("Somente leads encerrados podem ser reabertos.")
    if not (reason or "").strip():
        raise ValidationError("Informe o motivo da reabertura.")

    before = _snapshot_status(lead)
    lead.status = LeadStatus.QUALIFIED if lead.converted_customer_id else LeadStatus.CONTACTED
    lead.won_at = None
    lead.lost_at = None
    lead.loss_reason = None
    lead.loss_notes = ""
    lead.updated_by = actor
    lead.save()
    _create_activity(
        lead=lead,
        actor=actor,
        activity_type=LeadActivityType.REOPENING,
        title="Lead reaberto",
        description=reason,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commercial",
        action="lead_reopened",
        obj=lead,
        metadata=safe_changes(before, _snapshot_status(lead)),
    )
    return lead


@transaction.atomic
def register_lead_activity(
    *,
    lead,
    actor,
    activity_type,
    title,
    description,
    request=None,
    contact_channel=None,
    next_action_at=None,
):
    if not can_access_lead(actor, lead):
        raise PermissionDenied("Você não tem acesso a este lead.")
    if not user_has_permission(actor, "lead_activities.create"):
        raise PermissionDenied("Sem permissão para registrar atividade.")

    now = timezone.now()
    activity = _create_activity(
        lead=lead,
        actor=actor,
        activity_type=activity_type,
        title=title,
        description=description,
        occurred_at=now,
        next_action_at=next_action_at,
    )
    if activity_type in {
        LeadActivityType.CALL,
        LeadActivityType.WHATSAPP,
        LeadActivityType.EMAIL,
        LeadActivityType.MEETING,
        LeadActivityType.SITE_VISIT,
    }:
        if not lead.first_contact_at:
            lead.first_contact_at = now
        lead.last_contact_at = now
    if next_action_at:
        lead.next_follow_up_at = next_action_at
    lead.updated_by = actor
    lead.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commercial",
        action="lead_activity_created",
        obj=lead,
        metadata={"activity_id": activity.pk, "activity_type": activity_type},
    )
    return activity
