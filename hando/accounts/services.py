from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from audit.models import UserSessionLog
from audit.services import record_audit_event


@transaction.atomic
def deactivate_user(user, *, actor=None, request=None):
    user.is_active = False
    user.save(update_fields=["is_active"])
    UserSessionLog.objects.filter(user=user, is_active=True).update(
        is_active=False,
        logout_at=timezone.now(),
        logout_reason="user_deactivated",
    )
    # Database-backed sessions are opaque; clear matching logged sessions when possible.
    for session_key in UserSessionLog.objects.filter(user=user).values_list(
        "session_key", flat=True,
    ):
        Session.objects.filter(session_key=session_key).delete()
    record_audit_event(
        request=request,
        user=actor,
        event_type="deactivate",
        module="accounts",
        action="deactivate_user",
        obj=user,
    )
    return user
