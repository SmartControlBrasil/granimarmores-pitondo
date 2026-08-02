from django import forms

from hando.forms import BootstrapFormMixin
from salespeople.models import Salesperson


class SalespersonForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Salesperson
        fields = [
            "user",
            "code",
            "display_name",
            "phone",
            "email",
            "hire_date",
            "termination_date",
            "commission_percentage",
            "manager",
            "is_active",
        ]
        labels = {
            "user": "Usuário vinculado",
            "code": "Código",
            "display_name": "Nome de exibição",
            "phone": "Telefone",
            "email": "Email",
            "hire_date": "Data de admissão",
            "termination_date": "Data de desligamento",
            "commission_percentage": "Comissão (%)",
            "manager": "Gestor comercial",
            "is_active": "Ativo",
        }
        widgets = {
            "hire_date": forms.DateInput(attrs={"type": "date"}),
            "termination_date": forms.DateInput(attrs={"type": "date"}),
        }
