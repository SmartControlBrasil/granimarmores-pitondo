# ruff: noqa: PLR2004, SLF001
from contextvars import ContextVar

from django.utils import timezone

from audit.models import UserSessionLog
from audit.services import get_client_ip

current_user = ContextVar("current_user", default=None)
current_request = ContextVar("current_request", default=None)


def get_current_user():
    return current_user.get()


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token_user = current_user.set(getattr(request, "user", None))
        token_request = current_request.set(request)
        if getattr(request, "user", None) and request.user.is_authenticated:
            request.user._erp_current_request = request
            self._update_last_activity(request)
        try:
            return self.get_response(request)
        finally:
            current_user.reset(token_user)
            current_request.reset(token_request)

    def _update_last_activity(self, request):
        session_key = request.session.session_key
        if not session_key:
            return
        now = timezone.now()
        log = UserSessionLog.objects.filter(
            user=request.user,
            session_key=session_key,
            is_active=True,
        ).first()
        if not log:
            UserSessionLog.objects.create(
                user=request.user,
                session_key=session_key,
                login_at=now,
                last_activity_at=now,
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:2000],
            )
            return
        if (now - log.last_activity_at).total_seconds() >= 300:
            log.last_activity_at = now
            log.save(update_fields=["last_activity_at"])
