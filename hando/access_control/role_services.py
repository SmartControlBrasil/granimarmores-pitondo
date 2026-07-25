# ruff: noqa: EM101, TRY003
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.text import slugify

from access_control.models import AccessPermission
from access_control.models import RolePermission
from access_control.services.authorization import get_user_role
from audit.services import record_audit_event
from audit.services import safe_changes


def actor_can_manage_role(actor, role):
    if actor.is_superuser:
        return True
    actor_role = get_user_role(actor)
    if not actor_role:
        return False
    if actor_role.has_full_access:
        return True
    return actor_role.hierarchy_level < role.hierarchy_level


def assert_actor_can_manage_role(actor, role):
    if role and not actor_can_manage_role(actor, role):
        raise PermissionDenied(
            "Você não pode gerenciar um cargo igual ou superior ao seu.",
        )


def _role_snapshot(role):
    return {
        "name": role.name,
        "slug": role.slug,
        "hierarchy_level": role.hierarchy_level,
        "has_full_access": role.has_full_access,
        "customer_scope": role.customer_scope,
        "quote_scope": role.quote_scope,
        "asset_scope": role.asset_scope,
        "maintenance_scope": role.maintenance_scope,
        "is_active": role.is_active,
    }


@transaction.atomic
def create_role(*, form, actor, request=None):
    role = form.save(commit=False)
    if not role.slug:
        role.slug = slugify(role.name)
    assert_actor_can_manage_role(actor, role)
    role.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="configuration",
        module="access_control",
        action="create_role",
        obj=role,
        metadata=_role_snapshot(role),
    )
    return role


@transaction.atomic
def update_role(*, role, form, actor, request=None):
    assert_actor_can_manage_role(actor, role)
    before = _role_snapshot(role)
    role = form.save(commit=False)
    if (
        role.is_system
        and role.has_full_access is False
        and before["has_full_access"] is True
    ):
        raise PermissionDenied(
            "Não remova acesso total de um cargo de sistema administrativo aqui.",
        )
    assert_actor_can_manage_role(actor, role)
    role.save()
    after = _role_snapshot(role)
    record_audit_event(
        request=request,
        user=actor,
        event_type="configuration",
        module="access_control",
        action="update_role",
        obj=role,
        metadata=safe_changes(before, after),
    )
    return role


@transaction.atomic
def set_role_active(*, role, is_active, actor, request=None):
    assert_actor_can_manage_role(actor, role)
    if role.is_system and not is_active:
        raise PermissionDenied("Cargos de sistema não podem ser desativados pela tela.")
    before = {"is_active": role.is_active}
    role.is_active = is_active
    role.save(update_fields=["is_active", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="reactivate" if is_active else "deactivate",
        module="access_control",
        action="activate_role" if is_active else "deactivate_role",
        obj=role,
        metadata=safe_changes(before, {"is_active": role.is_active}),
    )
    return role


@transaction.atomic
def update_permission_matrix(*, role, form, actor, request=None):
    assert_actor_can_manage_role(actor, role)
    permissions = AccessPermission.objects.filter(is_active=True).order_by(
        "module",
        "code",
    )
    before = {
        item.permission.code: item.allowed
        for item in RolePermission.objects.filter(role=role).select_related(
            "permission",
        )
    }
    for permission in permissions:
        allowed = bool(form.cleaned_data.get(f"permission_{permission.pk}"))
        RolePermission.objects.update_or_create(
            role=role,
            permission=permission,
            defaults={"allowed": allowed},
        )
    after = {
        item.permission.code: item.allowed
        for item in RolePermission.objects.filter(role=role).select_related(
            "permission",
        )
    }
    record_audit_event(
        request=request,
        user=actor,
        event_type="configuration",
        module="access_control",
        action="update_permission_matrix",
        obj=role,
        metadata=safe_changes(before, after),
    )
