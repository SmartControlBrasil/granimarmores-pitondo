from django import forms

from customers.models import Customer


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "customer_type",
            "name",
            "trade_name",
            "document",
            "email",
            "phone",
            "mobile_phone",
            "assigned_salesperson",
            "notes",
        ]
