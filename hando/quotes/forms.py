from django import forms

from quotes.models import CommercialPolicy
from quotes.models import Quote
from quotes.models import QuoteDelivery
from quotes.models import QuoteItem
from quotes.models import QuoteItemFinish
from quotes.models import QuoteItemMeasurement
from quotes.models import QuoteService


class CommercialPolicyForm(forms.ModelForm):
    class Meta:
        model = CommercialPolicy
        fields = [
            "minimum_margin_percentage",
            "salesperson_max_discount_percentage",
            "manager_max_discount_percentage",
            "approval_required_above",
            "quote_default_validity_days",
            "allow_price_below_minimum",
            "is_active",
        ]


class QuoteForm(forms.ModelForm):
    class Meta:
        model = Quote
        fields = [
            "customer",
            "salesperson",
            "project_type",
            "commercial_source",
            "partner",
            "valid_until",
            "expected_delivery_days",
            "payment_terms",
            "internal_notes",
            "customer_notes",
            "discount_type",
            "discount_value",
            "shipping_value",
            "installation_value",
            "other_value",
            "tax_percentage",
        ]
        labels = {
            "project_type": "Tipo de projeto",
            "commercial_source": "Origem comercial",
            "partner": "Parceiro comercial",
        }
        widgets = {"valid_until": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from commercial.models import CommercialPartner
        from commercial.models import CommercialSource
        from commercial.models import ProjectType

        self.fields["commercial_source"].queryset = CommercialSource.objects.filter(
            is_active=True,
        )
        self.fields["partner"].queryset = CommercialPartner.objects.filter(is_active=True)
        self.fields["project_type"].queryset = ProjectType.objects.filter(is_active=True)


class QuoteItemForm(forms.ModelForm):
    class Meta:
        model = QuoteItem
        fields = [
            "material",
            "description",
            "quantity",
            "unit",
            "width_mm",
            "length_mm",
            "thickness_mm",
            "unit_cost",
            "unit_price",
            "loss_percentage",
            "discount_percentage",
            "below_minimum_reason",
            "position",
            "notes",
            "selected_slab",
        ]


class QuoteItemMeasurementForm(forms.ModelForm):
    class Meta:
        model = QuoteItemMeasurement
        fields = ["label", "width_mm", "length_mm", "quantity", "notes", "position"]


class QuoteItemFinishForm(forms.ModelForm):
    class Meta:
        model = QuoteItemFinish
        fields = ["finish_type", "quantity", "unit_cost", "unit_price", "position"]


class QuoteServiceForm(forms.ModelForm):
    class Meta:
        model = QuoteService
        fields = ["service", "quantity", "unit_cost", "unit_price", "position"]


class QuoteSubmitForApprovalForm(forms.Form):
    manual_approval = forms.BooleanField(
        label="Solicitar aprovação manual",
        required=False,
    )


class QuoteApprovalForm(forms.Form):
    note = forms.CharField(
        label="Observação do aprovador",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class QuoteRejectionForm(forms.Form):
    reason = forms.CharField(
        label="Motivo da rejeição",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class QuoteCancellationForm(forms.Form):
    reason = forms.CharField(
        label="Motivo do cancelamento",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class QuoteSendForm(forms.Form):
    channel = forms.ChoiceField(choices=QuoteDelivery.Channel.choices)
    recipient = forms.EmailField(label="Destinatário")
    subject = forms.CharField(label="Assunto", max_length=255)
    message = forms.CharField(
        label="Mensagem",
        widget=forms.Textarea(attrs={"rows": 5}),
    )

    def clean_channel(self):
        channel = self.cleaned_data["channel"]
        if channel == QuoteDelivery.Channel.WHATSAPP:
            message = "WhatsApp não está configurado nesta etapa."
            raise forms.ValidationError(message)
        return channel
