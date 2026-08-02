from django import forms

from hando.forms import BootstrapFormMixin
from quotes.models import CommercialPolicy
from quotes.models import Quote
from quotes.models import QuoteDelivery
from quotes.models import QuoteItem
from quotes.models import QuoteItemFinish
from quotes.models import QuoteItemMeasurement
from quotes.models import QuoteService


class CommercialPolicyForm(BootstrapFormMixin, forms.ModelForm):
    field_widths = {
        "minimum_margin_percentage": "col-md-6",
        "salesperson_max_discount_percentage": "col-md-6",
        "manager_max_discount_percentage": "col-md-6",
        "approval_required_above": "col-md-6",
        "quote_default_validity_days": "col-md-6",
        "allow_price_below_minimum": "col-md-6",
        "is_active": "col-md-6",
    }

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
        labels = {
            "minimum_margin_percentage": "Margem mínima (%)",
            "salesperson_max_discount_percentage": "Desconto máx. vendedor (%)",
            "manager_max_discount_percentage": "Desconto máx. gestor (%)",
            "approval_required_above": "Aprovação acima de (R$)",
            "quote_default_validity_days": "Validade padrão (dias)",
            "allow_price_below_minimum": "Permitir preço abaixo do mínimo",
            "is_active": "Ativa",
        }


class QuoteForm(BootstrapFormMixin, forms.ModelForm):
    field_widths = {
        "customer": "col-md-6",
        "salesperson": "col-md-6",
        "project_type": "col-md-4",
        "commercial_source": "col-md-4",
        "partner": "col-md-4",
        "valid_until": "col-md-4",
        "expected_delivery_days": "col-md-4",
        "payment_terms": "col-md-4",
        "internal_notes": "col-md-6",
        "customer_notes": "col-md-6",
        "discount_type": "col-md-4",
        "discount_value": "col-md-4",
        "tax_percentage": "col-md-4",
        "shipping_value": "col-md-4",
        "installation_value": "col-md-4",
        "other_value": "col-md-4",
    }

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
            "customer": "Cliente",
            "salesperson": "Vendedor",
            "project_type": "Tipo de projeto",
            "commercial_source": "Origem comercial",
            "partner": "Parceiro comercial",
            "valid_until": "Válido até",
            "expected_delivery_days": "Prazo de entrega (dias)",
            "payment_terms": "Condições de pagamento",
            "internal_notes": "Observações internas",
            "customer_notes": "Observações para o cliente",
            "discount_type": "Tipo de desconto",
            "discount_value": "Valor do desconto",
            "shipping_value": "Frete / transporte",
            "installation_value": "Instalação",
            "other_value": "Outros valores",
            "tax_percentage": "Impostos (%)",
        }
        widgets = {
            "valid_until": forms.DateInput(attrs={"type": "date"}),
            "internal_notes": forms.Textarea(attrs={"rows": 3}),
            "customer_notes": forms.Textarea(attrs={"rows": 3}),
        }

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


class QuoteItemForm(BootstrapFormMixin, forms.ModelForm):
    field_widths = {
        "material": "col-md-6",
        "description": "col-md-6",
        "quantity": "col-md-3",
        "unit": "col-md-3",
        "width_mm": "col-md-2",
        "length_mm": "col-md-2",
        "thickness_mm": "col-md-2",
        "unit_cost": "col-md-3",
        "unit_price": "col-md-3",
        "loss_percentage": "col-md-3",
        "discount_percentage": "col-md-3",
        "position": "col-md-3",
        "selected_slab": "col-md-5",
        "below_minimum_reason": "col-md-4",
        "notes": "col-12",
    }

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
        labels = {
            "material": "Material",
            "description": "Descrição",
            "quantity": "Quantidade",
            "unit": "Unidade",
            "width_mm": "Largura (mm)",
            "length_mm": "Comprimento (mm)",
            "thickness_mm": "Espessura (mm)",
            "unit_cost": "Custo unitário",
            "unit_price": "Preço unitário",
            "loss_percentage": "Perda (%)",
            "discount_percentage": "Desconto (%)",
            "below_minimum_reason": "Motivo abaixo do mínimo",
            "position": "Posição",
            "notes": "Observações",
            "selected_slab": "Chapa selecionada",
        }


class QuoteItemMeasurementForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = QuoteItemMeasurement
        fields = ["label", "width_mm", "length_mm", "quantity", "notes", "position"]


class QuoteItemFinishForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = QuoteItemFinish
        fields = ["finish_type", "quantity", "unit_cost", "unit_price", "position"]


class QuoteServiceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = QuoteService
        fields = ["service", "quantity", "unit_cost", "unit_price", "position"]


class QuoteSubmitForApprovalForm(BootstrapFormMixin, forms.Form):
    manual_approval = forms.BooleanField(
        label="Solicitar aprovação manual",
        required=False,
    )


class QuoteApprovalForm(BootstrapFormMixin, forms.Form):
    note = forms.CharField(
        label="Observação do aprovador",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class QuoteRejectionForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(
        label="Motivo da rejeição",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class QuoteCancellationForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(
        label="Motivo do cancelamento",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class QuoteSendForm(BootstrapFormMixin, forms.Form):
    channel = forms.ChoiceField(choices=QuoteDelivery.Channel.choices, label="Canal")
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
