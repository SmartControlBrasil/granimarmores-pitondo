from django import forms

from hando.forms import BootstrapFormMixin
from django.utils import timezone

from commercial.lead_models import Lead
from commercial.lead_models import LeadActivityType
from commercial.lead_models import LeadPriority
from commercial.lead_models import LeadStatus
from commercial.lead_models import LeadTask
from commercial.models import CommercialPartner
from commercial.models import CommercialSource
from commercial.models import ContactChannel
from commercial.models import LossReason
from commercial.models import ProjectType
from commercial.models import ServiceRegion
from commercial.lead_conversion import validate_lead_contact
from salespeople.models import Salesperson


class LeadForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            "name",
            "company_name",
            "email",
            "phone",
            "whatsapp",
            "city",
            "state",
            "district",
            "project_description",
            "commercial_source",
            "contact_channel",
            "project_type",
            "partner",
            "service_region",
            "assigned_salesperson",
            "priority",
            "estimated_value",
            "probability",
            "next_follow_up_at",
            "external_source",
            "external_id",
        ]
        widgets = {
            "next_follow_up_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "project_description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["commercial_source"].queryset = CommercialSource.objects.filter(is_active=True)
        self.fields["contact_channel"].queryset = ContactChannel.objects.filter(is_active=True)
        self.fields["project_type"].queryset = ProjectType.objects.filter(is_active=True)
        self.fields["partner"].queryset = CommercialPartner.objects.filter(is_active=True)
        self.fields["service_region"].queryset = ServiceRegion.objects.filter(is_active=True)
        self.fields["assigned_salesperson"].queryset = Salesperson.objects.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        validate_lead_contact(
            email=cleaned.get("email", ""),
            phone=cleaned.get("phone", ""),
            whatsapp=cleaned.get("whatsapp", ""),
        )
        probability = cleaned.get("probability")
        if probability is not None and (probability < 0 or probability > 100):
            raise forms.ValidationError("Probabilidade deve estar entre 0 e 100.")
        ext_source = (cleaned.get("external_source") or "").strip()
        ext_id = (cleaned.get("external_id") or "").strip()
        if ext_source and ext_id:
            qs = Lead.objects.filter(external_source=ext_source, external_id=ext_id)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Lead externo já cadastrado.")
        return cleaned


class LeadAssignForm(BootstrapFormMixin, forms.Form):
    assigned_salesperson = forms.ModelChoiceField(
        queryset=Salesperson.objects.filter(is_active=True),
        required=False,
        label="Vendedor responsável",
    )


class LeadStatusForm(BootstrapFormMixin, forms.Form):
    new_status = forms.ChoiceField(choices=LeadStatus.choices, label="Novo status")
    override_reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    loss_reason = forms.ModelChoiceField(
        queryset=LossReason.objects.filter(is_active=True),
        required=False,
        label="Motivo de perda",
    )
    loss_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


class LeadActivityForm(BootstrapFormMixin, forms.Form):
    activity_type = forms.ChoiceField(choices=LeadActivityType.choices, label="Tipo")
    title = forms.CharField(max_length=180)
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))
    next_action_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))


class LeadTaskForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = LeadTask
        fields = ["title", "description", "assigned_to", "due_at", "priority"]
        widgets = {"due_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class LeadConvertLinkForm(BootstrapFormMixin, forms.Form):
    customer_id = forms.IntegerField(required=False)


class LeadLossForm(BootstrapFormMixin, forms.Form):
    loss_reason = forms.ModelChoiceField(queryset=LossReason.objects.filter(is_active=True))
    loss_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


class LeadReopenForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
