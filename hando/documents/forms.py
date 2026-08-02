from django import forms

from hando.forms import BootstrapFormMixin

from documents.models import AcceptanceType
from documents.models import Confidentiality
from documents.models import DocumentTemplate
from documents.models import DocumentType
from documents.models import ManagedDocument
from documents.models import SendChannel
from documents.models import SignatureType
from documents.services.placeholders import PLACEHOLDER_WHITELIST


class DocumentTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DocumentType
        fields = [
            "name",
            "code",
            "description",
            "category",
            "requires_internal_approval",
            "requires_customer_acceptance",
            "requires_signature",
            "has_validity",
            "default_validity_days",
            "allows_renewal",
            "is_active",
            "display_order",
        ]


class DocumentTemplateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DocumentTemplate
        fields = [
            "name",
            "document_type",
            "description",
            "content_format",
            "body",
            "header",
            "footer",
            "valid_from",
            "valid_until",
            "is_active",
        ]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 12}),
            "header": forms.Textarea(attrs={"rows": 3}),
            "footer": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["document_type"].queryset = DocumentType.objects.filter(is_active=True)


class ManagedDocumentForm(BootstrapFormMixin, forms.ModelForm):
    initial_content = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 10}),
        label="Conteúdo inicial",
    )

    class Meta:
        model = ManagedDocument
        fields = [
            "title",
            "document_type",
            "template",
            "customer",
            "lead",
            "quote",
            "sales_order",
            "purchase_order",
            "supplier",
            "after_sales_case",
            "warranty",
            "effective_date",
            "expiration_date",
            "requires_acceptance",
            "requires_signature",
            "confidentiality",
            "responsible_user",
            "notes",
            "context_justification",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["document_type"].queryset = DocumentType.objects.filter(is_active=True)
        self.fields["template"].queryset = DocumentTemplate.objects.filter(
            is_active=True,
            status="approved",
        )
        self.fields["template"].required = False


class VersionContentForm(BootstrapFormMixin, forms.Form):
    content = forms.CharField(widget=forms.Textarea(attrs={"rows": 14}), label="Conteúdo")
    change_summary = forms.CharField(required=False, max_length=255, label="Resumo da alteração")


class ReviewDecisionForm(BootstrapFormMixin, forms.Form):
    comments = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


class SendRecordForm(BootstrapFormMixin, forms.Form):
    channel = forms.ChoiceField(choices=SendChannel.choices)
    recipient_name = forms.CharField(required=False, max_length=180)
    recipient_email = forms.EmailField(required=False)
    recipient_phone = forms.CharField(required=False, max_length=40)
    sent_at = forms.DateTimeField(required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ViewRecordForm(BootstrapFormMixin, forms.Form):
    viewer_name = forms.CharField(required=False, max_length=180)
    channel = forms.ChoiceField(choices=SendChannel.choices, initial=SendChannel.OTHER)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class AcceptanceForm(BootstrapFormMixin, forms.Form):
    accepted = forms.BooleanField(required=False, initial=True, label="Aceito")
    acceptance_type = forms.ChoiceField(choices=AcceptanceType.choices)
    accepted_by_name = forms.CharField(max_length=180)
    accepted_by_document = forms.CharField(required=False, max_length=40)
    channel = forms.ChoiceField(choices=SendChannel.choices)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class SignatureForm(BootstrapFormMixin, forms.Form):
    signer_name = forms.CharField(max_length=180)
    signer_document = forms.CharField(required=False, max_length=40)
    signer_role = forms.CharField(required=False, max_length=120)
    signature_type = forms.ChoiceField(choices=SignatureType.choices)
    channel = forms.ChoiceField(choices=SendChannel.choices)
    external_provider = forms.CharField(required=False, max_length=120)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ReasonForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Motivo")


class RenewForm(BootstrapFormMixin, forms.Form):
    expiration_date = forms.DateField(required=False, label="Novo vencimento")


class FromTemplateForm(BootstrapFormMixin, forms.Form):
    template = forms.ModelChoiceField(queryset=DocumentTemplate.objects.none())
    title = forms.CharField(required=False, max_length=220)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["template"].queryset = DocumentTemplate.objects.filter(
            is_active=True,
            status="approved",
        )


def placeholder_help_text():
    return ", ".join(f"{{{{ {name} }}}}" for name in sorted(PLACEHOLDER_WHITELIST))
