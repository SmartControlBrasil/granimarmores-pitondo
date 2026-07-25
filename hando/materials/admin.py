from django.contrib import admin

from materials.models import AdditionalService
from materials.models import FinishType
from materials.models import Material
from materials.models import MaterialCategory
from materials.models import MaterialPriceHistory
from materials.models import MaterialSlab


@admin.register(MaterialCategory)
class MaterialCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active"]
    search_fields = ["name", "slug"]


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "category", "unit", "sale_price", "is_active"]
    list_filter = ["category", "unit", "is_active"]
    search_fields = ["code", "name", "brand", "color"]


@admin.register(MaterialPriceHistory)
class MaterialPriceHistoryAdmin(admin.ModelAdmin):
    list_display = [
        "material",
        "price_type",
        "old_value",
        "new_value",
        "changed_at",
        "changed_by",
    ]
    readonly_fields = [
        "material",
        "price_type",
        "old_value",
        "new_value",
        "reason",
        "changed_at",
        "changed_by",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MaterialSlab)
class MaterialSlabAdmin(admin.ModelAdmin):
    list_display = [
        "slab_code",
        "material",
        "lot_number",
        "area_m2",
        "status",
        "is_active",
    ]
    search_fields = ["slab_code", "lot_number", "material__name"]


admin.site.register(FinishType)
admin.site.register(AdditionalService)
