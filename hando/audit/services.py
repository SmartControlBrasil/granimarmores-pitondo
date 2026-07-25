# ruff: noqa: PLR0913
from django.utils import timezone

from audit.models import AuditEvent

SENSITIVE_FIELDS = {
    "password",
    "password1",
    "password2",
    "old_password",
    "new_password",
    "token",
    "csrfmiddlewaretoken",
    "sessionid",
    "cookie",
    "authorization",
    "secret",
    "api_key",
    "access_token",
    "refresh_token",
}


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def safe_metadata(data):
    if not data:
        return {}
    cleaned = {}
    for key, value in data.items():
        key_lower = str(key).lower()
        if key_lower in SENSITIVE_FIELDS or any(
            part in key_lower for part in ["password", "token", "secret", "cookie"]
        ):
            continue
        cleaned[str(key)] = value
    return cleaned


def safe_changes(before, after):
    changes = {}
    for key, old in before.items():
        if key.lower() in SENSITIVE_FIELDS:
            continue
        new = after.get(key)
        if old != new:
            changes[key] = {"from": old, "to": new}
    return {"changes": changes} if changes else {}


def record_audit_event(
    *,
    request=None,
    user=None,
    event_type,
    module,
    action,
    obj=None,
    status="success",
    description="",
    metadata=None,
):
    if request is not None:
        user = user or (
            request.user
            if getattr(request, "user", None) and request.user.is_authenticated
            else None
        )
        session_key = request.session.session_key or ""
        ip_address = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:2000]
        request_method = getattr(request, "method", None) or ""
        request_path = (getattr(request, "path", None) or "")[:500]
    else:
        session_key = ""
        ip_address = None
        user_agent = ""
        request_method = ""
        request_path = ""
    object_type = obj.__class__.__name__ if obj is not None else ""
    object_id = str(getattr(obj, "pk", "") or "") if obj is not None else ""
    object_repr = str(obj)[:255] if obj is not None else ""
    return AuditEvent.objects.create(
        occurred_at=timezone.now(),
        user=user,
        session_key=session_key,
        event_type=event_type,
        module=module,
        action=action,
        object_type=object_type,
        object_id=object_id,
        object_repr=object_repr,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        request_method=request_method,
        request_path=request_path,
        status=status,
        metadata=safe_metadata(metadata or {}),
    )
