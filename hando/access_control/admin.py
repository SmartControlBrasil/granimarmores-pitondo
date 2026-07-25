from django.contrib import admin

from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.models import RolePermission
from access_control.models import UserAccess


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 0


@admin.register(AccessRole)
class AccessRoleAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "slug",
        "hierarchy_level",
        "has_full_access",
        "is_system",
        "is_active",
    ]
    list_filter = ["has_full_access", "is_system", "is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [RolePermissionInline]


@admin.register(AccessPermission)
class AccessPermissionAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "module", "action", "is_active"]
    list_filter = ["module", "action", "is_active"]
    search_fields = ["code", "name", "description"]


@admin.register(UserAccess)
class UserAccessAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "manager", "is_active", "valid_from", "valid_until"]
    list_filter = ["role", "is_active"]
    search_fields = ["user__username", "user__email", "role__name"]
