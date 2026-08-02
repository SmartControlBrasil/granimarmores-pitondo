# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from after_sales.models import AfterSalesCase
from after_sales.models import AfterSalesCaseHistory
from after_sales.models import AfterSalesInteraction
from after_sales.models import CaseStatus
from after_sales.models import HistoryAction
from after_sales.models import InteractionType
from after_sales.models import OPEN_CASE_STATUSES
from after_sales.models import PendingStatus
from after_sales.models import Responsibility
from after_sales.models import ReworkOrigin
from after_sales.models import RootCause
from after_sales.models import TECHNICAL_CASE_TYPES
from after_sales.services.numbering import next_case_code
from audit.services import record_audit_event


def _add_history(*, case, action, actor, description="", old_status="", new_status=""):
    return AfterSalesCaseHistory.objects.create(
        case=case,
        action=action,
        old_status=old_status or "",
        new_status=new_status or "",
        description=description,
        actor=actor,
    )


@transaction.atomic
def open_after_sales_case(
    *,
    actor,
    customer,
    subject,
    description,
    case_type,
    sales_order=None,
    delivery_schedule=None,
    installation_schedule=None,
    production_order=None,
    priority="normal",
    severity="minor",
    assigned_user=None,
    assigned_salesperson=None,
    reported_by_name="",
    reported_by_phone="",
    reported_channel="",
    next_action_at=None,
    allow_without_order=False,
    request=None,
):
    if not user_has_permission(actor, "after_sales_cases.create"):
        raise PermissionDenied("Sem permissão para abrir caso de pós-venda.")
    if not customer:
        raise ValidationError("Cliente obrigatório.")
    if not sales_order:
        if not allow_without_order:
            raise ValidationError(
                "Caso exige pedido vinculado, salvo exceção autorizada (allow_without_order).",
            )
        if not user_has_permission(actor, "after_sales_cases.view_all"):
            raise ValidationError("Abertura sem pedido exige autorização (visão geral).")
    if sales_order and sales_order.customer_id != customer.pk:
        raise ValidationError("Cliente do caso deve coincidir com o do pedido.")

    case = AfterSalesCase.objects.create(
        code=next_case_code(),
        case_type=case_type,
        status=CaseStatus.NEW,
        priority=priority,
        severity=severity,
        customer=customer,
        sales_order=sales_order,
        delivery_schedule=delivery_schedule,
        installation_schedule=installation_schedule,
        production_order=production_order or getattr(sales_order, "production_order", None),
        assigned_user=assigned_user,
        assigned_salesperson=assigned_salesperson or getattr(sales_order, "salesperson", None),
        subject=subject,
        description=description,
        reported_by_name=reported_by_name,
        reported_by_phone=reported_by_phone,
        reported_channel=reported_channel,
        reported_at=timezone.now(),
        next_action_at=next_action_at,
        created_by=actor,
        updated_by=actor,
    )
    if assigned_user:
        case.status = CaseStatus.ASSIGNED
        case.save(update_fields=["status", "updated_at"])

    _add_history(
        case=case,
        action=HistoryAction.CREATED,
        actor=actor,
        description="Caso aberto",
        new_status=case.status,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="after_sales",
        action="case_opened",
        obj=case,
        metadata={"code": case.code},
    )
    return case


@transaction.atomic
def triage_case(*, case, actor, notes="", request=None):
    if not user_has_permission(actor, "after_sales_cases.change_status"):
        raise PermissionDenied("Sem permissão para triar caso.")
    if case.status != CaseStatus.NEW:
        raise ValidationError("Somente casos novos podem ser triados.")
    old = case.status
    case.status = CaseStatus.TRIAGE
    case.updated_by = actor
    if not case.first_response_at:
        case.first_response_at = timezone.now()
    case.save()
    _add_history(case=case, action=HistoryAction.TRIAGED, actor=actor, description=notes, old_status=old, new_status=case.status)
    record_audit_event(request=request, user=actor, event_type="update", module="after_sales", action="case_triaged", obj=case)
    return case


@transaction.atomic
def assign_case(*, case, actor, assigned_user=None, assigned_salesperson=None, request=None):
    if not user_has_permission(actor, "after_sales_cases.assign"):
        raise PermissionDenied("Sem permissão para atribuir caso.")
    if not assigned_user and not assigned_salesperson:
        raise ValidationError("Informe responsável.")
    old = case.status
    case.assigned_user = assigned_user
    case.assigned_salesperson = assigned_salesperson
    if case.status in {CaseStatus.NEW, CaseStatus.TRIAGE}:
        case.status = CaseStatus.ASSIGNED
    case.updated_by = actor
    if not case.first_response_at:
        case.first_response_at = timezone.now()
    case.save()
    _add_history(
        case=case,
        action=HistoryAction.ASSIGNED,
        actor=actor,
        description=f"Atribuído a {assigned_user or assigned_salesperson}",
        old_status=old,
        new_status=case.status,
    )
    record_audit_event(request=request, user=actor, event_type="update", module="after_sales", action="case_assigned", obj=case)
    return case


@transaction.atomic
def add_interaction(*, case, actor, interaction_type, description, contact_channel="", next_action_at=None, request=None):
    if not user_has_permission(actor, "after_sales_cases.update"):
        raise PermissionDenied("Sem permissão para registrar interação.")
    interaction = AfterSalesInteraction.objects.create(
        case=case,
        interaction_type=interaction_type,
        contact_channel=contact_channel,
        description=description,
        next_action_at=next_action_at,
        created_by=actor,
    )
    if next_action_at:
        case.next_action_at = next_action_at
    if not case.first_response_at:
        case.first_response_at = timezone.now()
    if case.status == CaseStatus.AWAITING_CUSTOMER and interaction_type != InteractionType.NOTE:
        case.status = CaseStatus.IN_PROGRESS
    case.updated_by = actor
    case.save()
    _add_history(
        case=case,
        action=HistoryAction.CUSTOMER_CONTACTED,
        actor=actor,
        description=description[:500],
        old_status=case.status,
        new_status=case.status,
    )
    record_audit_event(request=request, user=actor, event_type="create", module="after_sales", action="case_interaction", obj=case)
    return interaction


@transaction.atomic
def add_diagnosis(*, case, actor, technical_diagnosis, root_cause="", root_cause_notes="", responsibility="", responsibility_notes="", request=None):
    if not user_has_permission(actor, "after_sales_cases.diagnose"):
        raise PermissionDenied("Sem permissão para diagnosticar.")
    if not technical_diagnosis.strip():
        raise ValidationError("Diagnóstico obrigatório.")
    if root_cause == RootCause.OTHER and not root_cause_notes.strip():
        raise ValidationError("Causa 'Outro' exige descrição.")
    old = case.status
    case.technical_diagnosis = technical_diagnosis.strip()
    case.root_cause = root_cause
    case.root_cause_notes = root_cause_notes
    case.responsibility = responsibility
    case.responsibility_notes = responsibility_notes
    if case.status in {CaseStatus.ASSIGNED, CaseStatus.TRIAGE, CaseStatus.NEW}:
        case.status = CaseStatus.UNDER_ANALYSIS
    case.updated_by = actor
    case.save()
    _add_history(case=case, action=HistoryAction.DIAGNOSIS_ADDED, actor=actor, description=technical_diagnosis[:500], old_status=old, new_status=case.status)
    record_audit_event(request=request, user=actor, event_type="update", module="after_sales", action="case_diagnosed", obj=case)
    return case


@transaction.atomic
def start_case_work(*, case, actor, request=None):
    if not user_has_permission(actor, "after_sales_cases.change_status"):
        raise PermissionDenied("Sem permissão para iniciar atendimento.")
    if case.status in {CaseStatus.CLOSED, CaseStatus.CANCELLED, CaseStatus.REJECTED}:
        raise ValidationError("Caso encerrado.")
    old = case.status
    case.status = CaseStatus.IN_PROGRESS
    case.updated_by = actor
    case.save()
    _add_history(case=case, action=HistoryAction.WORK_STARTED, actor=actor, description="Atendimento iniciado", old_status=old, new_status=case.status)
    record_audit_event(request=request, user=actor, event_type="update", module="after_sales", action="case_started", obj=case)
    return case


@transaction.atomic
def resolve_after_sales_case(
    *,
    case,
    actor,
    resolution,
    root_cause="",
    responsibility="",
    customer_notified=False,
    request=None,
):
    if not user_has_permission(actor, "after_sales_cases.resolve"):
        raise PermissionDenied("Sem permissão para resolver caso.")
    if case.status in {CaseStatus.CLOSED, CaseStatus.CANCELLED}:
        raise ValidationError("Caso já encerrado.")
    if not resolution.strip():
        raise ValidationError("Resolução obrigatória.")
    if case.case_type in TECHNICAL_CASE_TYPES:
        root_cause = root_cause or case.root_cause
        if not root_cause:
            raise ValidationError("Causa raiz obrigatória para casos técnicos.")
        if root_cause == RootCause.OTHER and not case.root_cause_notes and not case.technical_diagnosis:
            raise ValidationError("Causa 'Outro' exige descrição.")
        responsibility = responsibility or case.responsibility
        if not responsibility:
            raise ValidationError("Responsabilidade obrigatória para casos técnicos.")

    old = case.status
    case.resolution = resolution.strip()
    if root_cause:
        case.root_cause = root_cause
    if responsibility:
        case.responsibility = responsibility
    case.customer_notified = customer_notified
    case.status = CaseStatus.RESOLVED
    case.resolved_at = timezone.now()
    case.updated_by = actor
    case.save()
    _add_history(case=case, action=HistoryAction.RESOLVED, actor=actor, description=resolution[:500], old_status=old, new_status=case.status)
    AfterSalesInteraction.objects.create(
        case=case,
        interaction_type=InteractionType.RESOLUTION_UPDATE,
        description=resolution.strip(),
        created_by=actor,
    )
    record_audit_event(request=request, user=actor, event_type="update", module="after_sales", action="case_resolved", obj=case)
    return case


@transaction.atomic
def close_after_sales_case(*, case, actor, closing_notes="", request=None):
    if not user_has_permission(actor, "after_sales_cases.close"):
        raise PermissionDenied("Sem permissão para fechar caso.")
    if case.status != CaseStatus.RESOLVED:
        raise ValidationError("Caso deve estar resolvido para fechar.")
    if case.status == CaseStatus.CLOSED:
        raise ValidationError("Caso já fechado.")

    open_pending = case.pending_items.filter(
        status__in=[PendingStatus.OPEN, PendingStatus.SCHEDULED, PendingStatus.IN_PROGRESS],
    ).exists()
    if open_pending:
        raise ValidationError("Existem pendências abertas vinculadas ao caso.")

    from scheduling.models import EventStatus
    from scheduling.models import OperationalEvent

    active_events = OperationalEvent.objects.filter(
        after_sales_case=case,
    ).exclude(
        status__in=[EventStatus.COMPLETED, EventStatus.CANCELLED, EventStatus.NO_SHOW],
    ).exists()
    if active_events:
        raise ValidationError("Existem eventos técnicos ativos relacionados ao caso.")

    old = case.status
    case.status = CaseStatus.CLOSED
    case.closed_at = timezone.now()
    case.closing_notes = closing_notes
    case.updated_by = actor
    case.save()
    _add_history(case=case, action=HistoryAction.CLOSED, actor=actor, description=closing_notes or "Caso fechado", old_status=old, new_status=case.status)
    record_audit_event(request=request, user=actor, event_type="update", module="after_sales", action="case_closed", obj=case)
    return case


@transaction.atomic
def reopen_case(*, case, actor, reason, request=None):
    if not user_has_permission(actor, "after_sales_cases.reopen"):
        raise PermissionDenied("Sem permissão para reabrir caso.")
    if not reason.strip():
        raise ValidationError("Justificativa obrigatória.")
    if case.status not in {CaseStatus.CLOSED, CaseStatus.RESOLVED, CaseStatus.REJECTED}:
        raise ValidationError("Caso não está em estado reabrível.")
    old = case.status
    case.status = CaseStatus.IN_PROGRESS
    case.closed_at = None
    case.updated_by = actor
    case.save()
    _add_history(case=case, action=HistoryAction.REOPENED, actor=actor, description=reason.strip(), old_status=old, new_status=case.status)
    record_audit_event(request=request, user=actor, event_type="update", module="after_sales", action="case_reopened", obj=case, metadata={"reason": reason[:500]})
    return case


@transaction.atomic
def reject_case(*, case, actor, reason, request=None):
    if not user_has_permission(actor, "after_sales_cases.reject"):
        raise PermissionDenied("Sem permissão para rejeitar caso.")
    if not reason.strip():
        raise ValidationError("Motivo obrigatório.")
    old = case.status
    case.status = CaseStatus.REJECTED
    case.reject_reason = reason.strip()
    case.closed_at = timezone.now()
    case.updated_by = actor
    case.save()
    _add_history(case=case, action=HistoryAction.REJECTED, actor=actor, description=reason.strip(), old_status=old, new_status=case.status)
    record_audit_event(request=request, user=actor, event_type="update", module="after_sales", action="case_rejected", obj=case)
    return case


@transaction.atomic
def cancel_case(*, case, actor, reason, request=None):
    if not user_has_permission(actor, "after_sales_cases.cancel"):
        raise PermissionDenied("Sem permissão para cancelar caso.")
    if not reason.strip():
        raise ValidationError("Motivo obrigatório.")
    if case.status == CaseStatus.CLOSED:
        raise ValidationError("Caso fechado não pode ser cancelado.")
    old = case.status
    case.status = CaseStatus.CANCELLED
    case.cancel_reason = reason.strip()
    case.closed_at = timezone.now()
    case.updated_by = actor
    case.save()
    _add_history(case=case, action=HistoryAction.CANCELLED, actor=actor, description=reason.strip(), old_status=old, new_status=case.status)
    record_audit_event(request=request, user=actor, event_type="update", module="after_sales", action="case_cancelled", obj=case)
    return case


@transaction.atomic
def request_material(*, case, actor, notes, request=None):
    if not user_has_permission(actor, "after_sales_cases.update"):
        raise PermissionDenied("Sem permissão.")
    if not notes.strip():
        raise ValidationError("Descrição da solicitação obrigatória.")
    old = case.status
    case.material_request_notes = notes.strip()
    case.status = CaseStatus.AWAITING_MATERIAL
    case.updated_by = actor
    case.save()
    _add_history(case=case, action=HistoryAction.MATERIAL_REQUESTED, actor=actor, description=notes.strip(), old_status=old, new_status=case.status)
    record_audit_event(request=request, user=actor, event_type="update", module="after_sales", action="case_material_requested", obj=case)
    return case


@transaction.atomic
def link_rework(*, case, actor, production_order=None, estimated_cost=None, notes="", request=None):
    if not user_has_permission(actor, "after_sales_cases.update"):
        raise PermissionDenied("Sem permissão.")
    case.rework_production_order = production_order
    case.rework_origin = ReworkOrigin.AFTER_SALES
    case.estimated_rework_cost = estimated_cost
    case.updated_by = actor
    case.save()
    _add_history(case=case, action=HistoryAction.STATUS_CHANGED, actor=actor, description=notes or "Retrabalho vinculado", old_status=case.status, new_status=case.status)
    record_audit_event(request=request, user=actor, event_type="update", module="after_sales", action="case_rework_linked", obj=case)
    return case


@transaction.atomic
def change_case_status(*, case, actor, new_status, notes="", request=None):
    if not user_has_permission(actor, "after_sales_cases.change_status"):
        raise PermissionDenied("Sem permissão para alterar status.")
    blocked = {
        CaseStatus.RESOLVED,
        CaseStatus.CLOSED,
        CaseStatus.REJECTED,
        CaseStatus.CANCELLED,
    }
    if new_status in blocked:
        raise ValidationError("Use a ação específica para resolver, fechar, rejeitar ou cancelar.")
    if case.status in blocked:
        raise ValidationError("Caso encerrado: use reabertura se necessário.")
    if new_status not in CaseStatus.values:
        raise ValidationError("Status inválido.")
    if new_status == case.status:
        raise ValidationError("Status já está aplicado.")
    old = case.status
    case.status = new_status
    case.updated_by = actor
    case.save(update_fields=["status", "updated_by", "updated_at"])
    _add_history(
        case=case,
        action=HistoryAction.STATUS_CHANGED,
        actor=actor,
        description=notes or f"Status alterado para {new_status}",
        old_status=old,
        new_status=case.status,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="after_sales",
        action="case_status_changed",
        obj=case,
        metadata={"old": old, "new": new_status},
    )
    return case


@transaction.atomic
def schedule_case_visit(*, case, actor, start_at, end_at, title="", request=None, **event_kwargs):
    if not user_has_permission(actor, "after_sales_cases.update"):
        raise PermissionDenied("Sem permissão para agendar visita.")
    from scheduling.models import EventType
    from scheduling.services.events import create_operational_event

    event = create_operational_event(
        actor=actor,
        title=title or f"Visita técnica — {case.code}",
        event_type=EventType.TECHNICAL_ASSISTANCE,
        start_at=start_at,
        end_at=end_at,
        assigned_user=event_kwargs.get("assigned_user") or case.assigned_user or actor,
        customer=case.customer,
        sales_order=case.sales_order,
        address=event_kwargs.get("address") or (case.sales_order.delivery_address if case.sales_order else ""),
        city=event_kwargs.get("city") or (case.sales_order.delivery_city if case.sales_order else ""),
        state=event_kwargs.get("state") or (case.sales_order.delivery_state if case.sales_order else ""),
        contact_name=event_kwargs.get("contact_name") or str(case.customer),
        contact_phone=event_kwargs.get("contact_phone") or "",
        description=event_kwargs.get("description") or case.subject,
        override_conflicts=event_kwargs.get("override_conflicts", False),
        override_reason=event_kwargs.get("override_reason", ""),
        request=request,
        skip_permission_check=False,
    )
    event.after_sales_case = case
    event.save(update_fields=["after_sales_case", "updated_at"])

    old = case.status
    case.status = CaseStatus.VISIT_SCHEDULED
    case.next_action_at = start_at
    case.updated_by = actor
    case.save()
    _add_history(case=case, action=HistoryAction.VISIT_SCHEDULED, actor=actor, description=event.code, old_status=old, new_status=case.status)
    record_audit_event(request=request, user=actor, event_type="update", module="after_sales", action="case_visit_scheduled", obj=case, metadata={"event": event.code})
    return event
