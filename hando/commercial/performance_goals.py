# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from audit.services import safe_changes
from commercial.performance_models import SalesGoal


@transaction.atomic
def create_sales_goal(*, form, actor, request=None):
    if not user_has_permission(actor, "sales_goals.create"):
        raise PermissionDenied("Sem permissão para criar meta.")
    goal = form.save(commit=False)
    goal.created_by = actor
    goal.updated_by = actor
    goal.full_clean()
    goal.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="commercial",
        action="sales_goal_created",
        obj=goal,
    )
    return goal


@transaction.atomic
def update_sales_goal(*, goal, form, actor, request=None):
    if not user_has_permission(actor, "sales_goals.update"):
        raise PermissionDenied("Sem permissão para alterar meta.")
    before = {
        "lead_goal": goal.lead_goal,
        "won_lead_goal": goal.won_lead_goal,
        "sales_value_goal": str(goal.sales_value_goal),
    }
    goal = form.save(commit=False)
    goal.updated_by = actor
    goal.full_clean()
    goal.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commercial",
        action="sales_goal_updated",
        obj=goal,
        metadata=safe_changes(before, {"lead_goal": goal.lead_goal}),
    )
    return goal


@transaction.atomic
def deactivate_sales_goal(*, goal, actor, request=None):
    if not user_has_permission(actor, "sales_goals.deactivate"):
        raise PermissionDenied("Sem permissão para desativar meta.")
    if not goal.is_active:
        return goal
    goal.is_active = False
    goal.updated_by = actor
    goal.save(update_fields=["is_active", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="commercial",
        action="sales_goal_deactivated",
        obj=goal,
    )
    return goal
