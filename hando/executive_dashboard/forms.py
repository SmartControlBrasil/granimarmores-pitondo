from django import forms

from commercial.models import CommercialSource
from commercial.models import ProjectType
from materials.models import Material
from production.models import ProductionStage
from production.models import SalesOrderStatus
from after_sales.models import CaseStatus
from salespeople.models import Salesperson
from executive_dashboard.services.periods import PERIOD_CHOICES


class ExecutiveFilterForm(forms.Form):
    period = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        required=False,
        initial="30d",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    start = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}))
    end = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}))
    salesperson = forms.ModelChoiceField(
        queryset=Salesperson.objects.filter(is_active=True),
        required=False,
        empty_label="Todos os vendedores",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    commercial_source = forms.ModelChoiceField(
        queryset=CommercialSource.objects.filter(is_active=True),
        required=False,
        empty_label="Todas as origens",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    project_type = forms.ModelChoiceField(
        queryset=ProjectType.objects.filter(is_active=True),
        required=False,
        empty_label="Todos os tipos",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    city = forms.CharField(
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "Cidade"}),
    )
    material = forms.ModelChoiceField(
        queryset=Material.objects.filter(is_active=True),
        required=False,
        empty_label="Todos os materiais",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    production_responsible = forms.IntegerField(required=False, widget=forms.HiddenInput())
    production_stage = forms.ModelChoiceField(
        queryset=ProductionStage.objects.filter(is_active=True),
        required=False,
        empty_label="Todas as etapas",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    order_status = forms.ChoiceField(
        choices=[("", "Todos os status")] + list(SalesOrderStatus.choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    after_sales_status = forms.ChoiceField(
        choices=[("", "Todos os status")] + list(CaseStatus.choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
