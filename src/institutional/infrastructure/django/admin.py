from django.contrib import admin

from src.institutional.infrastructure.django.models import ContactRequest


@admin.register(ContactRequest)
class ContactRequestAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "telefone",
        "email",
        "cidade",
        "ambiente",
        "status",
        "created_at",
    )
    list_filter = ("status", "created_at", "cidade")
    search_fields = ("nome", "telefone", "email")
    readonly_fields = (
        "source_path",
        "ip_address",
        "user_agent",
        "notification_sent_at",
        "notification_error",
        "created_at",
        "updated_at",
    )
