from django.contrib import admin

from audit.models import AuditEvent
from audit.models import UserSessionLog


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = [
        "occurred_at",
        "user",
        "event_type",
        "module",
        "action",
        "status",
        "object_repr",
    ]
    list_filter = ["event_type", "module", "status", "occurred_at"]
    search_fields = ["object_repr", "description", "request_path", "user__username"]
    readonly_fields = [field.name for field in AuditEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and obj is None

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(UserSessionLog)
class UserSessionLogAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "session_key",
        "login_at",
        "logout_at",
        "is_active",
        "logout_reason",
    ]
    list_filter = ["is_active", "logout_reason", "login_at"]
    search_fields = ["user__username", "session_key"]
