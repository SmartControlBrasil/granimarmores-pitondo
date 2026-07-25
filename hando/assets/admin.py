from django.contrib import admin

from assets.models import Asset
from assets.models import AssetCategory
from assets.models import AssetDocument


class AssetDocumentInline(admin.TabularInline):
    model = AssetDocument
    extra = 0


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    search_fields = ["name"]


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = [
        "asset_code",
        "name",
        "category",
        "status",
        "responsible_user",
        "is_active",
    ]
    list_filter = ["category", "status", "is_active", "requires_maintenance"]
    search_fields = ["asset_code", "name", "serial_number"]
    inlines = [AssetDocumentInline]
