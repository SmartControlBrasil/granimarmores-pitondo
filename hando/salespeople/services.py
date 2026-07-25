# ruff: noqa: EM101, TRY003
from django.core.exceptions import PermissionDenied
from django.db import transaction

from audit.services import record_audit_event
from audit.services import safe_changes


def _snapshot(salesperson):
    return {
        "user": salesperson.user_id,
        "code": salesperson.code,
        "display_name": salesperson.display_name,
        "phone": salesperson.phone,
        "email": salesperson.email,
        "hire_date": str(salesperson.hire_date or ""),
        "termination_date": str(salesperson.termination_date or ""),
        "commission_percentage": str(salesperson.commission_percentage),
        "manager": salesperson.manager_id,
        "is_active": salesperson.is_active,
    }


def _manager_chain_contains(salesperson, manager):
    seen = set()
    current = manager
    while current and current.pk not in seen:
        if current == salesperson:
            return True
        seen.add(current.pk)
        current = current.manager
    return False


def _assert_no_cycle(salesperson, manager):
    if salesperson.pk and manager and _manager_chain_contains(salesperson, manager):
        raise PermissionDenied("A cadeia de gestores comerciais não pode formar ciclo.")


@transaction.atomic
def create_salesperson(*, form, actor, request=None):
    salesperson = form.save(commit=False)
    _assert_no_cycle(salesperson, salesperson.manager)
    salesperson.created_by = actor
    salesperson.updated_by = actor
    salesperson.save()
    form.save_m2m()
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="salespeople",
        action="create",
        obj=salesperson,
    )
    return salesperson


@transaction.atomic
def update_salesperson(*, salesperson, form, actor, request=None):
    before = _snapshot(salesperson)
    salesperson = form.save(commit=False)
    _assert_no_cycle(salesperson, salesperson.manager)
    salesperson.updated_by = actor
    salesperson.save()
    form.save_m2m()
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="salespeople",
        action="update",
        obj=salesperson,
        metadata=safe_changes(before, _snapshot(salesperson)),
    )
    return salesperson


@transaction.atomic
def set_salesperson_active(*, salesperson, is_active, actor, request=None):
    before = {"is_active": salesperson.is_active}
    salesperson.is_active = is_active
    salesperson.updated_by = actor
    salesperson.save(update_fields=["is_active", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="reactivate" if is_active else "deactivate",
        module="salespeople",
        action="activate" if is_active else "deactivate",
        obj=salesperson,
        metadata=safe_changes(before, {"is_active": salesperson.is_active}),
    )
    return salesperson
