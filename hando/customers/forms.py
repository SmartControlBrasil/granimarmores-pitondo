from django import forms

from hando.forms import BootstrapFormMixin

from commercial.models import CommercialPartner
from commercial.models import CommercialSource
from commercial.models import ContactChannel
from commercial.models import ProjectType
from customers.models import Customer


class CustomerForm(BootstrapFormMixin, forms.ModelForm):
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
            "commercial_source",
            "partner",
            "project_type_interest",
            "preferred_contact_channel",
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
            "commercial_source": "Origem comercial",
            "partner": "Parceiro comercial",
            "project_type_interest": "Tipo de projeto de interesse",
            "preferred_contact_channel": "Canal de contato preferido",
            "notes": "Observações",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["commercial_source"].queryset = CommercialSource.objects.filter(
            is_active=True,
        )
        self.fields["partner"].queryset = CommercialPartner.objects.filter(is_active=True)
        self.fields["project_type_interest"].queryset = ProjectType.objects.filter(
            is_active=True,
        )
        self.fields["preferred_contact_channel"].queryset = ContactChannel.objects.filter(
            is_active=True,
        )
