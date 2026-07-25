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
            "state_registration",
            "municipal_registration",
            "email",
            "phone",
            "mobile_phone",
            "website",
            "assigned_salesperson",
            "notes",
        ]
        labels = {
            "customer_type": "Tipo",
            "name": "Nome/Razão social",
            "trade_name": "Nome fantasia",
            "document": "CPF/CNPJ",
            "state_registration": "Inscrição estadual",
            "municipal_registration": "Inscrição municipal",
            "email": "Email",
            "phone": "Telefone",
            "mobile_phone": "Celular",
            "website": "Site",
            "assigned_salesperson": "Vendedor responsável",
            "notes": "Observações",
        }
