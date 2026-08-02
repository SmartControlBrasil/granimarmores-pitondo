from django import forms

from commercial.models import ContactChannel
from commercial.models import LossReason
from production.models import DeliverySchedule
from production.models import InstallationSchedule
from production.models import ProductionOrder
from production.models import SalesOrder
from production.models import SalesOrderStatus


class AcceptQuoteForm(forms.Form):
    customer_name = forms.CharField(max_length=160, label="Nome do cliente")
    customer_document = forms.CharField(max_length=40, required=False, label="Documento")
    acceptance_channel = forms.ModelChoiceField(
        queryset=ContactChannel.objects.filter(is_active=True),
        required=False,
        label="Canal de aceite",
    )
    acceptance_notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Observações",
    )


class RefuseQuoteForm(forms.Form):
    loss_reason = forms.ModelChoiceField(
        queryset=LossReason.objects.filter(is_active=True),
        label="Motivo de perda",
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        label="Observações",
    )
    acceptance_channel = forms.ModelChoiceField(
        queryset=ContactChannel.objects.filter(is_active=True),
        required=False,
        label="Canal de contato",
    )


class SalesOrderForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = [
            "promised_date",
            "delivery_required",
            "installation_required",
            "delivery_address",
            "delivery_city",
            "delivery_state",
            "delivery_postal_code",
            "customer_notes",
            "commercial_notes",
            "technical_notes",
        ]
        widgets = {"promised_date": forms.DateInput(attrs={"type": "date"})}


class SalesOrderStatusForm(forms.Form):
    new_status = forms.ChoiceField(choices=SalesOrderStatus.choices, label="Novo status")
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
        label="Motivo",
    )


class SalesOrderHoldForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Motivo da pausa")


class SalesOrderCancelForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Motivo do cancelamento")


class ProductionOrderForm(forms.ModelForm):
    class Meta:
        model = ProductionOrder
        fields = [
            "priority",
            "planned_start_date",
            "planned_end_date",
            "responsible",
            "production_notes",
            "technical_notes",
        ]
        widgets = {
            "planned_start_date": forms.DateInput(attrs={"type": "date"}),
            "planned_end_date": forms.DateInput(attrs={"type": "date"}),
        }


class ProductionActionForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
        label="Motivo / observação",
    )


class DeliveryScheduleForm(forms.ModelForm):
    class Meta:
        model = DeliverySchedule
        fields = [
            "scheduled_date",
            "scheduled_time_start",
            "scheduled_time_end",
            "address",
            "city",
            "state",
            "postal_code",
            "responsible",
            "vehicle",
            "notes",
        ]
        widgets = {
            "scheduled_date": forms.DateInput(attrs={"type": "date"}),
            "scheduled_time_start": forms.TimeInput(attrs={"type": "time"}),
            "scheduled_time_end": forms.TimeInput(attrs={"type": "time"}),
        }


class InstallationScheduleForm(forms.ModelForm):
    class Meta:
        model = InstallationSchedule
        fields = [
            "scheduled_date",
            "scheduled_time_start",
            "scheduled_time_end",
            "address",
            "city",
            "state",
            "postal_code",
            "responsible",
            "vehicle",
            "notes",
        ]
        widgets = {
            "scheduled_date": forms.DateInput(attrs={"type": "date"}),
            "scheduled_time_start": forms.TimeInput(attrs={"type": "time"}),
            "scheduled_time_end": forms.TimeInput(attrs={"type": "time"}),
        }


class InstallationCompleteForm(forms.Form):
    result_notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Resultado")
    return_required = forms.BooleanField(required=False, label="Necessita retorno")


class QualityInspectionForm(forms.Form):
    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False, label="Observações")


class StageSkipForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), label="Justificativa")


class AssignSlabForm(forms.Form):
    slab = forms.ModelChoiceField(queryset=None, label="Chapa")

    def __init__(self, *args, material=None, **kwargs):
        super().__init__(*args, **kwargs)
        from materials.models import MaterialSlab

        qs = MaterialSlab.objects.filter(is_active=True)
        if material:
            qs = qs.filter(material=material)
        self.fields["slab"].queryset = qs
