from django.contrib import admin

from salespeople.models import Salesperson


@admin.register(Salesperson)
class SalespersonAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "display_name",
        "user",
        "manager",
        "commission_percentage",
        "is_active",
    ]
    list_filter = ["is_active"]
    search_fields = ["code", "display_name", "email"]
