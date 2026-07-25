# ruff: noqa: BLE001, EM101, PLR0911, S110, SLF001, TRY003
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.utils import timezone

from access_control.models import UserAccess

RESOURCE_SCOPE_FIELDS = {
    "customer": "customer_scope",
    "customers": "customer_scope",
    "quote": "quote_scope",
    "quotes": "quote_scope",
    "asset": "asset_scope",
    "assets": "asset_scope",
    "maintenance": "maintenance_scope",
}


def _request_cache(user):
    request = getattr(user, "_erp_current_request", None)
    if request is None:
        return None
    if not hasattr(request, "_erp_auth_cache"):
        request._erp_auth_cache = {}
    return request._erp_auth_cache


def get_user_access(user):
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return None
    cache = _request_cache(user)
    key = f"access:{user.pk}"
    if cache is not None and key in cache:
        return cache[key]
    now = timezone.now()
    access = (
        UserAccess.objects.select_related("role", "manager")
        .filter(user=user, is_active=True, valid_from__lte=now)
        .filter(role__is_active=True)
        .filter(valid_until__isnull=True)[:1]
    )
    access = (
        access[0]
        if access
        else (
            UserAccess.objects.select_related("role", "manager")
            .filter(
                user=user,
                is_active=True,
                valid_from__lte=now,
                valid_until__gt=now,
                role__is_active=True,
            )
            .first()
        )
    )
    if cache is not None:
        cache[key] = access
    return access


def get_user_role(user):
    access = get_user_access(user)
    return access.role if access else None


def user_has_permission(user, permission_code):
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    if user.is_superuser:
        return True
    role = get_user_role(user)
    if not role:
        return False
    if role.has_full_access:
        return True
    cache = _request_cache(user)
    key = f"perm:{user.pk}:{permission_code}"
    if cache is not None and key in cache:
        return cache[key]
    allowed = role.role_permissions.filter(
        permission__code=permission_code,
        permission__is_active=True,
        allowed=True,
    ).exists()
    if cache is not None:
        cache[key] = allowed
    return allowed


def get_user_scope(user, resource):
    role = get_user_role(user)
    if not role:
        return None
    field = RESOURCE_SCOPE_FIELDS.get(resource, f"{resource}_scope")
    return getattr(role, field, None)


def can_access_object(user, obj, action="view"):
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    if user.is_superuser:
        return True
    role = get_user_role(user)
    if not role:
        return False
    if role.has_full_access:
        return True
    module = obj._meta.model_name
    plural = {"customer": "customers", "vehicle": "vehicles"}.get(module, f"{module}s")
    permission_code = f"{plural}.{action}"
    own_permission = f"{plural}.{action}_own"
    if not (
        user_has_permission(user, permission_code)
        or user_has_permission(user, own_permission)
    ):
        return False
    scope = get_user_scope(user, module)
    if scope == "all":
        return True
    owner = getattr(obj, "created_by", None) or getattr(obj, "responsible_user", None)
    salesperson = getattr(obj, "assigned_salesperson", None)
    if scope == "own" or user_has_permission(user, own_permission):
        if owner and owner == user:
            return True
        if salesperson and getattr(salesperson, "user_id", None) == user.id:
            return True
    return False


def render_403(request):
    return render(request, "403.html", status=403)


def require_permission(permission_code):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if user_has_permission(request.user, permission_code):
                return view_func(request, *args, **kwargs)
            try:
                from audit.services import record_audit_event

                record_audit_event(
                    request=request,
                    event_type="authorization",
                    module="access_control",
                    action=permission_code,
                    status="denied",
                    description="Acesso bloqueado por permissão insuficiente.",
                )
            except Exception:
                pass
            return render_403(request)

        return wrapper

    return decorator


class PermissionRequiredMixin:
    permission_required = None

    def dispatch(self, request, *args, **kwargs):
        if not self.permission_required:
            raise PermissionDenied("permission_required não configurado.")
        if not user_has_permission(request.user, self.permission_required):
            return render_403(request)
        return super().dispatch(request, *args, **kwargs)
