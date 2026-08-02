from django.db.models import Count

from audit.models import AuditEvent
from audit.models import UserSessionLog


def governance_metrics(*, start, end):
    events = AuditEvent.objects.filter(occurred_at__gte=start, occurred_at__lte=end)
    logins = UserSessionLog.objects.filter(login_at__gte=start, login_at__lte=end)
    return {
        "audit_events": events.count(),
        "logins": logins.count(),
        "active_users": events.values("user_id").distinct().count(),
        "by_module": list(
            events.values("module").annotate(total=Count("id")).order_by("-total")[:10],
        ),
        "by_user": list(
            events.exclude(user__isnull=True)
            .values("user__username")
            .annotate(total=Count("id"))
            .order_by("-total")[:10],
        ),
        "critical_actions": events.filter(
            action__in=[
                "override",
                "cancel",
                "reopen",
                "status_changed",
                "permission",
                "score_adjusted",
                "stock_adjust",
            ],
        ).count()
        or events.filter(event_type="authorization").count(),
        "permission_changes": events.filter(
            module="access_control",
        ).count(),
    }
