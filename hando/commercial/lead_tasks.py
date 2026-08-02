# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from commercial.lead_models import LeadTask
from commercial.lead_models import LeadTaskStatus
from commercial.lead_queries import can_access_lead


@transaction.atomic
def create_lead_task(*, lead, title, description, assigned_to, due_at, actor, priority="normal", request=None):
    if not can_access_lead(actor, lead):
        raise PermissionDenied("Você não tem acesso a este lead.")
    if not user_has_permission(actor, "lead_tasks.create"):
        raise PermissionDenied("Sem permissão para criar tarefa.")
    task = LeadTask.objects.create(
        lead=lead,
        title=title,
        description=description or "",
        assigned_to=assigned_to,
        due_at=due_at,
        priority=priority,
        created_by=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="commercial",
        action="lead_task_created",
        obj=lead,
        metadata={"task_id": task.pk},
    )
    return task


@transaction.atomic
def complete_lead_task(*, task, actor, request=None):
    lead = task.lead
    if not can_access_lead(actor, lead):
        raise PermissionDenied("Você não tem acesso a este lead.")
    if not user_has_permission(actor, "lead_tasks.complete"):
        raise PermissionDenied("Sem permissão para concluir tarefa.")
    if task.status == LeadTaskStatus.COMPLETED:
        return task
    task.status = LeadTaskStatus.COMPLETED
    task.completed_at = timezone.now()
    task.completed_by = actor
    task.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commercial",
        action="lead_task_completed",
        obj=lead,
        metadata={"task_id": task.pk},
    )
    return task


@transaction.atomic
def cancel_lead_task(*, task, actor, request=None):
    lead = task.lead
    if not can_access_lead(actor, lead):
        raise PermissionDenied("Você não tem acesso a este lead.")
    if not user_has_permission(actor, "lead_tasks.cancel"):
        raise PermissionDenied("Sem permissão para cancelar tarefa.")
    task.status = LeadTaskStatus.CANCELLED
    task.cancelled_at = timezone.now()
    task.cancelled_by = actor
    task.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commercial",
        action="lead_task_cancelled",
        obj=lead,
        metadata={"task_id": task.pk},
    )
    return task


@transaction.atomic
def reopen_lead_task(*, task, actor, request=None):
    lead = task.lead
    if not can_access_lead(actor, lead):
        raise PermissionDenied("Você não tem acesso a este lead.")
    if not user_has_permission(actor, "lead_tasks.reopen"):
        raise PermissionDenied("Sem permissão para reabrir tarefa.")
    task.status = LeadTaskStatus.PENDING
    task.completed_at = None
    task.completed_by = None
    task.cancelled_at = None
    task.cancelled_by = None
    task.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commercial",
        action="lead_task_reopened",
        obj=lead,
        metadata={"task_id": task.pk},
    )
    return task
