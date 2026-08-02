from django import forms

from hando.forms import BootstrapFormMixin

from commercial.performance_models import GoalPeriodType
from commercial.performance_models import SalesGoal
from commercial.performance_models import SalesScorePolicy
from salespeople.models import Salesperson


class SalesGoalForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SalesGoal
        fields = [
            "salesperson",
            "period_type",
            "start_date",
            "end_date",
            "lead_goal",
            "contact_goal",
            "quote_goal",
            "won_lead_goal",
            "sales_value_goal",
            "conversion_goal",
            "response_time_goal_minutes",
            "follow_up_compliance_goal",
            "notes",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name not in self.Meta.widgets:
                css = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
                field.widget.attrs.setdefault("class", css)
        self.fields["salesperson"].queryset = Salesperson.objects.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            raise forms.ValidationError("Data final não pode ser anterior à inicial.")
        salesperson = cleaned.get("salesperson")
        period_type = cleaned.get("period_type")
        if salesperson and start and end:
            qs = SalesGoal.objects.filter(
                salesperson=salesperson,
                period_type=period_type,
                start_date=start,
                end_date=end,
                is_active=True,
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Meta ativa duplicada para este vendedor e período.")
        return cleaned


class SalesScorePolicyForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = SalesScorePolicy
        fields = [
            "name",
            "description",
            "valid_from",
            "valid_until",
            "is_active",
            "points_lead_created",
            "points_first_contact",
            "points_lead_qualified",
            "points_measurement_completed",
            "points_quote_created",
            "points_quote_sent",
            "points_follow_up_completed",
            "points_lead_won",
            "points_sales_value_factor",
            "penalty_overdue_follow_up",
            "penalty_unattended_lead",
            "penalty_lost_without_reason",
            "maximum_daily_score",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "valid_from": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "valid_until": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name not in self.Meta.widgets:
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        valid_from = cleaned.get("valid_from")
        valid_until = cleaned.get("valid_until")
        if valid_from and valid_until and valid_until < valid_from:
            raise forms.ValidationError("Vigência final inválida.")
        return cleaned


class ManualScoreAdjustmentForm(BootstrapFormMixin, forms.Form):
    salesperson = forms.ModelChoiceField(
        queryset=Salesperson.objects.filter(is_active=True),
        label="Vendedor",
    )
    points = forms.IntegerField(label="Pontos (+ ou -)")
    adjustment_date = forms.DateField(
        label="Data",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    justification = forms.CharField(
        label="Justificativa",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )
    reference = forms.CharField(
        required=False,
        label="Referência opcional",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["salesperson"].widget.attrs["class"] = "form-select"
