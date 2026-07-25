from django.contrib import admin

from maintenance.models import MaintenanceAttachment
from maintenance.models import MaintenanceOrder
from maintenance.models import MaintenancePart
from maintenance.models import MaintenancePlan


class MaintenancePartInline(admin.TabularInline):
    model = MaintenancePart
    extra = 0


class MaintenanceAttachmentInline(admin.TabularInline):
    model = MaintenanceAttachment
    extra = 0


@admin.register(MaintenancePlan)
class MaintenancePlanAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "maintenance_type",
        "asset",
        "vehicle",
        "next_due_date",
        "is_active",
    ]
    list_filter = ["maintenance_type", "is_active"]
    search_fields = ["name"]


@admin.register(MaintenanceOrder)
class MaintenanceOrderAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "maintenance_type",
        "priority",
        "status",
        "asset",
        "vehicle",
        "total_cost",
    ]
    list_filter = ["maintenance_type", "priority", "status"]
    search_fields = ["number", "reported_problem", "service_performed"]
    inlines = [MaintenancePartInline, MaintenanceAttachmentInline]
