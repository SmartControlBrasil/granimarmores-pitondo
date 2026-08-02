from django import forms
from django.contrib.auth import get_user_model

from after_sales.models import AfterSalesAttachment
from after_sales.models import AfterSalesCase
from after_sales.models import AttachmentType
from after_sales.models import CasePriority
from after_sales.models import CaseSeverity
from after_sales.models import CaseStatus
from after_sales.models import CaseType
from after_sales.models import ConsentScope
from after_sales.models import ConsentStatus
from after_sales.models import CoverageType
from after_sales.models import CustomerReferral
from after_sales.models import CustomerSatisfactionSurvey
from after_sales.models import InstallationPendingItem
from after_sales.models import InteractionType
from after_sales.models import MediaUsageConsent
from after_sales.models import Responsibility
from after_sales.models import ReviewRequest
from after_sales.models import ReviewRequestStatus
from after_sales.models import RootCause
from after_sales.models import SurveyType
from after_sales.models import WarrantyEligibility
from after_sales.models import WarrantyRecord
from customers.models import Customer
from production.models import InstallationSchedule
from production.models import ProductionOrder
from production.models import SalesOrder
from salespeople.models import Salesperson

User = get_user_model()


class AfterSalesCaseCreateForm(forms.ModelForm):
    allow_without_order = forms.BooleanField(
        required=False,
        label="Abrir sem pedido (exceção autorizada)",
    )

    class Meta:
        model = AfterSalesCase
        fields = [
            "customer",
            "sales_order",
            "delivery_schedule",
            "installation_schedule",
            "case_type",
            "subject",
            "description",
            "priority",
            "severity",
            "reported_by_name",
            "reported_by_phone",
            "reported_channel",
            "next_action_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True)
        self.fields["sales_order"].queryset = SalesOrder.objects.select_related("customer")
        self.fields["sales_order"].required = False
        self.fields["delivery_schedule"].required = False
        self.fields["installation_schedule"].required = False
        self.fields["next_action_at"].required = False


class AssignCaseForm(forms.Form):
    assigned_user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        label="Responsável",
    )
    assigned_salesperson = forms.ModelChoiceField(
        queryset=Salesperson.objects.filter(is_active=True),
        required=False,
        label="Vendedor",
    )


class InteractionForm(forms.Form):
    interaction_type = forms.ChoiceField(choices=InteractionType.choices)
    contact_channel = forms.CharField(required=False, max_length=40)
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    next_action_at = forms.DateTimeField(required=False)


class DiagnosisForm(forms.Form):
    technical_diagnosis = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    root_cause = forms.ChoiceField(choices=[("", "—")] + list(RootCause.choices), required=False)
    root_cause_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    responsibility = forms.ChoiceField(
        choices=[("", "—")] + list(Responsibility.choices),
        required=False,
    )
    responsibility_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ResolveCaseForm(forms.Form):
    resolution = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    root_cause = forms.ChoiceField(choices=[("", "—")] + list(RootCause.choices), required=False)
    responsibility = forms.ChoiceField(
        choices=[("", "—")] + list(Responsibility.choices),
        required=False,
    )
    customer_notified = forms.BooleanField(required=False, label="Cliente notificado")


class CloseCaseForm(forms.Form):
    closing_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ReasonForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), label="Motivo / justificativa")


class ChangeStatusForm(forms.Form):
    new_status = forms.ChoiceField(
        choices=[
            c
            for c in CaseStatus.choices
            if c[0]
            not in {
                CaseStatus.RESOLVED,
                CaseStatus.CLOSED,
                CaseStatus.REJECTED,
                CaseStatus.CANCELLED,
            }
        ],
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ScheduleVisitForm(forms.Form):
    start_at = forms.DateTimeField()
    end_at = forms.DateTimeField(required=False)
    title = forms.CharField(required=False, max_length=220)
    address = forms.CharField(required=False, max_length=255)
    city = forms.CharField(required=False, max_length=120)
    state = forms.CharField(required=False, max_length=2)
    contact_phone = forms.CharField(required=False, max_length=40)
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class WarrantyForm(forms.ModelForm):
    class Meta:
        model = WarrantyRecord
        fields = [
            "customer",
            "sales_order",
            "installation_schedule",
            "policy",
            "start_date",
            "end_date",
            "coverage_type",
            "coverage_description",
            "exclusions",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True)
        self.fields["sales_order"].queryset = SalesOrder.objects.all()
        self.fields["installation_schedule"].required = False
        self.fields["policy"].required = False
        self.fields["end_date"].required = False


class WarrantyDecisionForm(forms.Form):
    decision = forms.ChoiceField(choices=WarrantyEligibility.choices)
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))
    warranty = forms.ModelChoiceField(queryset=WarrantyRecord.objects.all(), required=False)


class InstallationPendingForm(forms.ModelForm):
    create_case = forms.BooleanField(required=False, label="Criar caso de pós-venda")

    class Meta:
        model = InstallationPendingItem
        fields = [
            "installation_schedule",
            "description",
            "priority",
            "responsible",
            "due_date",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["installation_schedule"].queryset = InstallationSchedule.objects.select_related(
            "sales_order",
        )
        self.fields["responsible"].queryset = User.objects.filter(is_active=True)
        self.fields["responsible"].required = False
        self.fields["due_date"].required = False


class ResolvePendingForm(forms.Form):
    resolution = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))


class SatisfactionSurveyForm(forms.ModelForm):
    class Meta:
        model = CustomerSatisfactionSurvey
        fields = ["customer", "sales_order", "after_sales_case", "survey_type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True)
        self.fields["sales_order"].required = False
        self.fields["after_sales_case"].required = False


class SurveyResponseForm(forms.Form):
    overall_score = forms.IntegerField(min_value=1, max_value=5, required=False)
    service_score = forms.IntegerField(min_value=1, max_value=5, required=False)
    quality_score = forms.IntegerField(min_value=1, max_value=5, required=False)
    delivery_score = forms.IntegerField(min_value=1, max_value=5, required=False)
    installation_score = forms.IntegerField(min_value=1, max_value=5, required=False)
    comments = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    would_recommend = forms.NullBooleanField(required=False)


class ReviewRequestForm(forms.ModelForm):
    class Meta:
        model = ReviewRequest
        fields = ["customer", "sales_order", "channel", "notes", "status"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True)
        self.fields["sales_order"].required = False
        self.fields["status"].choices = ReviewRequestStatus.choices


class MediaConsentForm(forms.ModelForm):
    class Meta:
        model = MediaUsageConsent
        fields = [
            "customer",
            "sales_order",
            "consent_status",
            "consent_scope",
            "authorized_by_name",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True)
        self.fields["sales_order"].required = False


class ReferralForm(forms.ModelForm):
    class Meta:
        model = CustomerReferral
        fields = [
            "referring_customer",
            "sales_order",
            "referred_name",
            "referred_phone",
            "referred_email",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["referring_customer"].queryset = Customer.objects.filter(is_active=True)
        self.fields["sales_order"].required = False
        self.fields["referred_email"].required = False


class MaterialRequestForm(forms.Form):
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), label="Solicitação de material")


class ReworkLinkForm(forms.Form):
    production_order = forms.ModelChoiceField(
        queryset=ProductionOrder.objects.all(),
        required=False,
    )
    estimated_cost = forms.DecimalField(required=False, max_digits=12, decimal_places=2)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = AfterSalesAttachment
        fields = ["file", "attachment_type", "description"]

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f:
            return f
        name = f.name.lower()
        banned = (".exe", ".bat", ".cmd", ".sh", ".msi", ".js", ".vbs", ".dll")
        if any(name.endswith(ext) for ext in banned):
            raise forms.ValidationError("Tipo de arquivo não permitido.")
        if f.size > 15 * 1024 * 1024:
            raise forms.ValidationError("Arquivo maior que 15 MB.")
        return f


class CaseFilterForm(forms.Form):
    q = forms.CharField(required=False)
    status = forms.ChoiceField(choices=[("", "Status")] + list(CaseStatus.choices), required=False)
    case_type = forms.ChoiceField(choices=[("", "Tipo")] + list(CaseType.choices), required=False)
    priority = forms.ChoiceField(choices=[("", "Prioridade")] + list(CasePriority.choices), required=False)
    severity = forms.ChoiceField(choices=[("", "Severidade")] + list(CaseSeverity.choices), required=False)
