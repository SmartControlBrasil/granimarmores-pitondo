# ruff: noqa: EM101, TRY003
from django.contrib import messages
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from access_control.models import UserAccess
from access_control.services.authorization import get_user_role
from accounts.models import UserProfile
from audit.models import UserSessionLog
from audit.services import record_audit_event
from audit.services import safe_changes


def _role_is_manageable(actor, role):
    if actor.is_superuser:
        return True
    actor_role = get_user_role(actor)
    if not actor_role:
        return False
    if actor_role.has_full_access:
        return True
    return actor_role.hierarchy_level < role.hierarchy_level


def _assert_manageable_role(actor, role):
    if role and not _role_is_manageable(actor, role):
        raise PermissionDenied(
            "Você não pode atribuir ou gerenciar um cargo igual ou superior ao seu.",
        )


def _assert_last_admin_safe(user):
    access = UserAccess.objects.filter(
        user=user,
        is_active=True,
        role__has_full_access=True,
        role__is_active=True,
    ).first()
    if not access:
        return
    remaining = UserAccess.objects.filter(
        is_active=True,
        role__has_full_access=True,
        role__is_active=True,
        user__is_active=True,
    ).exclude(user=user)
    if not remaining.exists():
        raise PermissionDenied(
            "Não é permitido desativar o último usuário com acesso total.",
        )


def _profile_values(cleaned_data):
    return {
        "full_name": cleaned_data.get("full_name", ""),
        "phone": cleaned_data.get("phone", ""),
        "job_title": cleaned_data.get("job_title", ""),
        "employee_code": cleaned_data.get("employee_code") or None,
        "is_operational_active": cleaned_data.get("is_operational_active", True),
        "must_change_password": cleaned_data.get("must_change_password", False),
    }


@transaction.atomic
def create_managed_user(*, form, actor, request=None):
    user = form.save(commit=False)
    user.set_password(form.cleaned_data["password1"])
    user.save()
    profile_values = _profile_values(form.cleaned_data)
    UserProfile.objects.update_or_create(user=user, defaults=profile_values)
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="accounts",
        action="create_user",
        obj=user,
        metadata={"username": user.username, "email": user.email},
    )
    return user


@transaction.atomic
def update_managed_user(*, user, form, actor, request=None):
    before = {
        "username": user.username,
        "name": user.name,
        "email": user.email,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
    }
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile_before = {
        "full_name": profile.full_name,
        "phone": profile.phone,
        "job_title": profile.job_title,
        "employee_code": profile.employee_code,
        "is_operational_active": profile.is_operational_active,
        "must_change_password": profile.must_change_password,
    }
    if user == actor and form.cleaned_data.get("is_active") is False:
        raise PermissionDenied("Você não pode desativar seu próprio usuário.")
    if user.is_active and form.cleaned_data.get("is_active") is False:
        _assert_last_admin_safe(user)
    user = form.save()
    profile_values = _profile_values(form.cleaned_data)
    for field, value in profile_values.items():
        setattr(profile, field, value)
    profile.updated_by = actor
    profile.save()
    after = {
        "username": user.username,
        "name": user.name,
        "email": user.email,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
    }
    metadata = safe_changes(before | profile_before, after | profile_values)
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="accounts",
        action="update_user",
        obj=user,
        metadata=metadata,
    )
    return user


def _manager_chain_contains_user(manager, user):
    seen = set()
    current = manager
    while current and current.pk not in seen:
        if current == user:
            return True
        seen.add(current.pk)
        access = UserAccess.objects.filter(user=current, is_active=True).first()
        current = access.manager if access else None
    return False


@transaction.atomic
def assign_user_access(*, user, form, actor, request=None):
    role = form.cleaned_data["role"]
    manager = form.cleaned_data.get("manager")
    _assert_manageable_role(actor, role)
    if manager and manager == user:
        raise PermissionDenied("O gestor não pode ser o próprio usuário.")
    if manager and _manager_chain_contains_user(manager, user):
        raise PermissionDenied("A cadeia de gestores não pode formar ciclo.")
    current = UserAccess.objects.filter(user=user, is_active=True).first()
    before = {
        "role": current.role.slug if current else "",
        "manager": current.manager_id if current else None,
    }
    if current:
        current.is_active = False
        current.valid_until = timezone.now()
        current.save(update_fields=["is_active", "valid_until", "updated_at"])
    access = form.save(commit=False)
    access.user = user
    access.is_active = True
    access.save()
    after = {"role": access.role.slug, "manager": access.manager_id}
    record_audit_event(
        request=request,
        user=actor,
        event_type="configuration",
        module="access_control",
        action="assign_user_access",
        obj=user,
        metadata=safe_changes(before, after),
    )
    return access


@transaction.atomic
def deactivate_user(user, actor=None, request=None):
    if actor and user == actor:
        raise PermissionDenied("Você não pode desativar seu próprio usuário.")
    _assert_last_admin_safe(user)
    user.is_active = False
    user.save(update_fields=["is_active"])
    UserProfile.objects.update_or_create(
        user=user,
        defaults={"is_operational_active": False, "updated_by": actor},
    )
    UserAccess.objects.filter(user=user, is_active=True).update(
        is_active=False,
        valid_until=timezone.now(),
    )
    revoked = revoke_user_sessions(
        user=user,
        actor=actor,
        request=request,
        reason=UserSessionLog.LogoutReason.USER_DEACTIVATED,
        audit=False,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="deactivate",
        module="accounts",
        action="deactivate_user",
        obj=user,
        metadata={"revoked_sessions": revoked},
    )
    return user


@transaction.atomic
def reactivate_user(user, actor=None, request=None):
    user.is_active = True
    user.save(update_fields=["is_active"])
    UserProfile.objects.update_or_create(
        user=user,
        defaults={"is_operational_active": True, "updated_by": actor},
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="reactivate",
        module="accounts",
        action="reactivate_user",
        obj=user,
    )
    return user


@transaction.atomic
def reset_user_password(*, user, form, actor, request=None):
    user.set_password(form.cleaned_data["password1"])
    user.save(update_fields=["password"])
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.must_change_password = form.cleaned_data.get("must_change_password", True)
    profile.save(update_fields=["must_change_password", "updated_at"])
    revoked = 0
    if form.cleaned_data.get("revoke_sessions"):
        revoked = revoke_user_sessions(
            user=user,
            actor=actor,
            request=request,
            reason=UserSessionLog.LogoutReason.PASSWORD_CHANGED,
            audit=False,
        )
    record_audit_event(
        request=request,
        user=actor,
        event_type="configuration",
        module="accounts",
        action="reset_password",
        obj=user,
        metadata={"revoked_sessions": revoked},
    )
    return user


@transaction.atomic
def revoke_user_sessions(
    *,
    user,
    actor=None,
    request=None,
    reason=UserSessionLog.LogoutReason.REVOKED,
    audit=True,
):
    active_logs = UserSessionLog.objects.filter(user=user, is_active=True)
    session_keys = list(active_logs.values_list("session_key", flat=True))
    for log in active_logs:
        log.close(reason=reason)
    Session.objects.filter(session_key__in=session_keys).delete()
    if audit:
        record_audit_event(
            request=request,
            user=actor,
            event_type="configuration",
            module="accounts",
            action="revoke_sessions",
            obj=user,
            metadata={"revoked_sessions": len(session_keys), "reason": reason},
        )
    return len(session_keys)


def add_permission_error(request, exc):
    messages.error(request, str(exc) or "Ação não permitida.")
