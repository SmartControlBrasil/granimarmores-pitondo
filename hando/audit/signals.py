from django.contrib.auth.signals import user_logged_in
from django.contrib.auth.signals import user_logged_out
from django.contrib.auth.signals import user_login_failed
from django.dispatch import receiver
from django.utils import timezone

from audit.models import UserSessionLog
from audit.services import get_client_ip
from audit.services import record_audit_event


@receiver(user_logged_in)
def log_user_login(request, user, **kwargs):
    if request.session.session_key is None:
        request.session.save()
    UserSessionLog.objects.update_or_create(
        user=user,
        session_key=request.session.session_key,
        is_active=True,
        defaults={
            "login_at": timezone.now(),
            "last_activity_at": timezone.now(),
            "ip_address": get_client_ip(request),
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:2000],
        },
    )
    record_audit_event(
        request=request,
        user=user,
        event_type="authentication",
        module="accounts",
        action="login",
        status="success",
    )


@receiver(user_logged_out)
def log_user_logout(request, user, **kwargs):
    if user and request.session.session_key:
        UserSessionLog.objects.filter(
            user=user, session_key=request.session.session_key, is_active=True,
        ).update(
            is_active=False,
            logout_at=timezone.now(),
            logout_reason="manual",
        )
    record_audit_event(
        request=request,
        user=user,
        event_type="authentication",
        module="accounts",
        action="logout",
        status="success",
    )


@receiver(user_login_failed)
def log_user_login_failed(request, credentials, **kwargs):
    record_audit_event(
        request=request,
        event_type="authentication",
        module="accounts",
        action="login",
        status="failed",
    )
