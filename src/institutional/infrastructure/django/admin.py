from django.contrib import admin

from src.institutional.infrastructure.django.models import ContactRequest
from src.institutional.infrastructure.django.models import ContactRequestAuditLog
from src.institutional.infrastructure.django.models import ContactRequestNote
from src.institutional.infrastructure.django.models import Opportunity
from src.institutional.infrastructure.django.models import OpportunityAuditLog
from src.institutional.infrastructure.django.models import Quote
from src.institutional.infrastructure.django.models import QuoteItem
from src.institutional.infrastructure.django.models import QuoteDocument
from src.institutional.infrastructure.django.models import QuoteDelivery
from src.institutional.infrastructure.django.models import QuoteSequence


class ContactRequestNoteInline(admin.TabularInline):
    model = ContactRequestNote
    extra = 0
    readonly_fields = ("author", "content", "created_at")
    can_delete = False


class ContactRequestAuditLogInline(admin.TabularInline):
    model = ContactRequestAuditLog
    extra = 0
    readonly_fields = (
        "actor",
        "action",
        "previous_value",
        "new_value",
        "source",
        "created_at",
    )
    can_delete = False


@admin.register(ContactRequest)
class ContactRequestAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "telefone",
        "email",
        "cidade",
        "ambiente",
        "status",
        "assigned_to",
        "created_at",
    )
    list_filter = ("status", "created_at", "cidade", "assigned_to")
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
    inlines = (ContactRequestNoteInline, ContactRequestAuditLogInline)


@admin.register(ContactRequestNote)
class ContactRequestNoteAdmin(admin.ModelAdmin):
    list_display = ("contact_request", "author", "created_at")
    list_filter = ("created_at", "author")
    search_fields = ("contact_request__nome", "content", "author__username")
    readonly_fields = ("created_at",)


@admin.register(ContactRequestAuditLog)
class ContactRequestAuditLogAdmin(admin.ModelAdmin):
    list_display = ("contact_request", "actor", "action", "created_at")
    list_filter = ("action", "created_at", "actor")
    search_fields = ("contact_request__nome", "actor__username")
    readonly_fields = (
        "contact_request",
        "actor",
        "action",
        "previous_value",
        "new_value",
        "source",
        "created_at",
    )



class QuoteItemInline(admin.TabularInline):
    model = QuoteItem
    extra = 0
    readonly_fields = ("total",)


class OpportunityAuditLogInline(admin.TabularInline):
    model = OpportunityAuditLog
    extra = 0
    readonly_fields = ("actor", "action", "previous_value", "new_value", "created_at")
    can_delete = False


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ("customer_name", "title", "stage", "assigned_to", "estimated_value", "probability", "updated_at")
    list_filter = ("stage", "assigned_to", "city", "created_at")
    search_fields = ("customer_name", "customer_phone", "customer_email", "title")
    readonly_fields = ("created_at", "updated_at")
    inlines = (OpportunityAuditLogInline,)


@admin.register(OpportunityAuditLog)
class OpportunityAuditLogAdmin(admin.ModelAdmin):
    list_display = ("opportunity", "actor", "action", "created_at")
    list_filter = ("action", "created_at", "actor")
    search_fields = ("opportunity__customer_name", "actor__username")
    readonly_fields = ("opportunity", "actor", "action", "previous_value", "new_value", "created_at")


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ("number", "revision", "opportunity", "status", "subtotal", "discount_amount", "total", "updated_at")
    list_filter = ("status", "created_at", "validity_date")
    search_fields = ("number", "opportunity__customer_name", "opportunity__title")
    readonly_fields = ("subtotal", "total", "created_at", "updated_at")
    inlines = (QuoteItemInline,)


@admin.register(QuoteItem)
class QuoteItemAdmin(admin.ModelAdmin):
    list_display = ("quote", "description", "quantity", "unit", "unit_price", "total", "position")
    search_fields = ("quote__number", "description")
    readonly_fields = ("total",)


@admin.register(QuoteSequence)
class QuoteSequenceAdmin(admin.ModelAdmin):
    list_display = ("year", "next_number")


@admin.register(QuoteDocument)
class QuoteDocumentAdmin(admin.ModelAdmin):
    list_display = ("document_number", "quote", "revision", "status", "generated_by", "generated_at", "sent_at")
    list_filter = ("status", "generated_at", "sent_at")
    search_fields = ("document_number", "quote__number", "quote__opportunity__customer_name", "checksum")
    readonly_fields = ("quote", "revision", "document_number", "status", "snapshot_data", "snapshot_fingerprint", "file", "checksum", "generated_by", "generated_at", "sent_at", "created_at")


@admin.register(QuoteDelivery)
class QuoteDeliveryAdmin(admin.ModelAdmin):
    list_display = ("quote", "document", "channel", "recipient", "status", "requested_by", "requested_at", "sent_at")
    list_filter = ("channel", "status", "requested_at", "sent_at")
    search_fields = ("quote__number", "document__document_number", "recipient")
    readonly_fields = ("quote", "document", "channel", "recipient", "status", "requested_by", "requested_at", "sent_at", "error_message", "created_at")
