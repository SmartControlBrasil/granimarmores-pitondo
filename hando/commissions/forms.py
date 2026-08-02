from decimal import Decimal

from django import forms
from django.utils import timezone

from commercial.models import CommercialPartner
from commissions.models import CalculationBasis
from commissions.models import CommissionPolicy
from commissions.models import CommissionTarget
from commissions.models import CommissionType
from commissions.models import TriggerType
from finance.models import FinancialAccount
from finance.models import PaymentMethod
from finance.models import PaymentTerm
from salespeople.models import Salesperson


class _Styled(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-control"
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"


class CommissionPolicyForm(_Styled):
    class Meta:
        model = CommissionPolicy
        fields = [
            "name",
            "description",
            "commission_target",
            "calculation_basis",
            "trigger_type",
            "valid_from",
            "valid_until",
            "priority",
            "requires_approval",
            "release_only_after_payment",
            "minimum_margin_percent",
            "maximum_discount_percent",
            "notes",
        ]
        widgets = {
            "valid_from": forms.DateInput(attrs={"type": "date"}),
            "valid_until": forms.DateInput(attrs={"type": "date"}),
        }


class TierForm(forms.Form):
    sequence = forms.IntegerField(min_value=1, initial=1)
    minimum_value = forms.DecimalField(min_value=Decimal("0"), initial=Decimal("0"))
    maximum_value = forms.DecimalField(required=False, min_value=Decimal("0"))
    commission_type = forms.ChoiceField(choices=CommissionType.choices, initial=CommissionType.PERCENTAGE)
    commission_value = forms.DecimalField(min_value=Decimal("0"), initial=Decimal("0"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs["class"] = "form-control"
            if isinstance(f.widget, forms.Select):
                f.widget.attrs["class"] = "form-select"


class AdjustmentForm(forms.Form):
    beneficiary_type = forms.ChoiceField(
        choices=[("salesperson", "Vendedor"), ("commercial_partner", "Parceiro")],
    )
    salesperson = forms.ModelChoiceField(queryset=Salesperson.objects.filter(is_active=True), required=False)
    commercial_partner = forms.ModelChoiceField(
        queryset=CommercialPartner.objects.filter(is_active=True),
        required=False,
    )
    amount = forms.DecimalField(min_value=Decimal("0.01"))
    direction = forms.ChoiceField(choices=[("positive", "Positivo"), ("negative", "Negativo")])
    competence_date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))
    reference = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in {"reason", "competence_date"}:
                continue
            field.widget.attrs["class"] = "form-control"
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"


class ReverseForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))


class SettlementForm(forms.Form):
    beneficiary_type = forms.ChoiceField(
        choices=[("salesperson", "Vendedor"), ("commercial_partner", "Parceiro")],
    )
    salesperson = forms.ModelChoiceField(queryset=Salesperson.objects.filter(is_active=True), required=False)
    commercial_partner = forms.ModelChoiceField(
        queryset=CommercialPartner.objects.filter(is_active=True),
        required=False,
    )
    period_start = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    period_end = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in {"period_start", "period_end", "notes"}:
                continue
            field.widget.attrs["class"] = "form-control"
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"


class GeneratePayableForm(forms.Form):
    due_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    payment_term = forms.ModelChoiceField(
        queryset=PaymentTerm.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class PaymentForm(forms.Form):
    amount = forms.DecimalField(min_value=Decimal("0.01"))
    payment_date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    payment_method = forms.ModelChoiceField(
        queryset=PaymentMethod.objects.filter(is_active=True),
        required=False,
    )
    financial_account = forms.ModelChoiceField(
        queryset=FinancialAccount.objects.filter(is_active=True),
        required=False,
    )
    reference = forms.CharField(required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.DateInput):
                field.widget.attrs.setdefault("class", "form-control")
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"


class SimulatorForm(forms.Form):
    value = forms.DecimalField(min_value=Decimal("0.01"), label="Valor da venda")
    margin = forms.DecimalField(required=False, min_value=Decimal("0"), label="Margem %")
    discount = forms.DecimalField(required=False, min_value=Decimal("0"), label="Desconto R$")
    trigger_type = forms.ChoiceField(choices=TriggerType.choices, initial=TriggerType.QUOTE_ACCEPTED)
    target = forms.ChoiceField(
        choices=[("salesperson", "Vendedor"), ("commercial_partner", "Parceiro")],
        initial="salesperson",
    )
    salesperson = forms.ModelChoiceField(queryset=Salesperson.objects.filter(is_active=True), required=False)
    commercial_partner = forms.ModelChoiceField(
        queryset=CommercialPartner.objects.filter(is_active=True),
        required=False,
    )
    on_date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "on_date":
                continue
            field.widget.attrs["class"] = "form-control"
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
