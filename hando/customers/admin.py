from django.contrib import admin

from customers.models import Customer
from customers.models import CustomerAddress


class CustomerAddressInline(admin.TabularInline):
    model = CustomerAddress
    extra = 0


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "customer_type",
        "document",
        "assigned_salesperson",
        "is_active",
    ]
    list_filter = ["customer_type", "is_active"]
    search_fields = ["name", "trade_name", "document", "email"]
    inlines = [CustomerAddressInline]
