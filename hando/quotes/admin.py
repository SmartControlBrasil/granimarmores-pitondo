# ruff: noqa: SLF001
from django.contrib import admin

from quotes.models import CommercialPolicy
from quotes.models import Quote
from quotes.models import QuoteDelivery
from quotes.models import QuoteItem
from quotes.models import QuoteItemFinish
from quotes.models import QuoteItemMeasurement
from quotes.models import QuoteSequence
from quotes.models import QuoteService
from quotes.models import QuoteVersion


class QuoteItemInline(admin.TabularInline):
    model = QuoteItem
    extra = 0


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "customer",
        "salesperson",
        "status",
        "grand_total",
        "current_version",
    ]
    list_filter = ["status", "salesperson"]
    search_fields = ["number", "customer__name", "salesperson__display_name"]
    inlines = [QuoteItemInline]


@admin.register(QuoteVersion)
class QuoteVersionAdmin(admin.ModelAdmin):
    list_display = ["quote", "version_number", "status", "grand_total", "pdf_hash"]
    readonly_fields = [field.name for field in QuoteVersion._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(CommercialPolicy)
admin.site.register(QuoteSequence)
admin.site.register(QuoteItemMeasurement)
admin.site.register(QuoteItemFinish)
admin.site.register(QuoteService)
admin.site.register(QuoteDelivery)
