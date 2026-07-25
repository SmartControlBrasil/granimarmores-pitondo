from django.contrib import admin

from fleet.models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = [
        "plate",
        "brand",
        "model",
        "odometer",
        "status",
        "responsible_user",
        "is_active",
    ]
    list_filter = ["status", "fuel_type", "is_active"]
    search_fields = ["plate", "renavam", "chassis", "brand", "model"]
