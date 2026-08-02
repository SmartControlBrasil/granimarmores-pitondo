from django import forms

from hando.forms import BootstrapFormMixin
from django.contrib.auth import get_user_model

from customers.models import Customer
from fleet.models import Vehicle
from salespeople.models import Salesperson
from scheduling.models import ConfirmationChannel
from scheduling.models import EventPriority
from scheduling.models import EventType
from scheduling.models import MeasurementType
from scheduling.models import OperationalEvent

User = get_user_model()


class OperationalEventForm(BootstrapFormMixin, forms.ModelForm):
    override_conflicts = forms.BooleanField(required=False, label="Permitir conflito (override)")
    override_reason = forms.CharField(
        required=False,
        label="Justificativa do override",
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    measurement_type = forms.ChoiceField(
        choices=MeasurementType.choices,
        required=False,
        label="Tipo de medição",
    )

    class Meta:
        model = OperationalEvent
        fields = [
            "event_type",
            "title",
            "description",
            "start_at",
            "end_at",
            "all_day",
            "priority",
            "assigned_user",
            "assigned_salesperson",
            "external_responsible",
            "customer",
            "lead",
            "quote",
            "sales_order",
            "production_order",
            "production_piece",
            "vehicle",
            "address",
            "district",
            "city",
            "state",
            "postal_code",
            "contact_name",
            "contact_phone",
            "internal_notes",
        ]
        widgets = {
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description": forms.Textarea(attrs={"rows": 2}),
            "internal_notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_user"].queryset = User.objects.filter(is_active=True).order_by(
            "username",
        )
        self.fields["assigned_salesperson"].queryset = Salesperson.objects.filter(is_active=True)
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True)
        self.fields["vehicle"].queryset = Vehicle.objects.filter(is_active=True)
        self.fields["priority"].choices = EventPriority.choices
        self.fields["event_type"].choices = EventType.choices


class RescheduleForm(BootstrapFormMixin, forms.Form):
    new_start_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    new_end_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))
    override_conflicts = forms.BooleanField(required=False, label="Override de conflito")


class CancelEventForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(label="Motivo", widget=forms.Textarea(attrs={"rows": 3}))


class CompleteEventForm(BootstrapFormMixin, forms.Form):
    completion_notes = forms.CharField(
        required=False,
        label="Observações de conclusão",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class ConfirmEventForm(BootstrapFormMixin, forms.Form):
    channel = forms.ChoiceField(choices=ConfirmationChannel.choices)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class LeadScheduleForm(BootstrapFormMixin, forms.Form):
    event_type = forms.ChoiceField(
        choices=[
            (EventType.COMMERCIAL_FOLLOW_UP, "Agendar contato"),
            (EventType.CUSTOMER_MEETING, "Agendar reunião"),
            (EventType.TECHNICAL_VISIT, "Agendar visita"),
            (EventType.MEASUREMENT, "Agendar medição"),
        ],
    )
    title = forms.CharField(max_length=220)
    start_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    end_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    assigned_user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    override_conflicts = forms.BooleanField(required=False)
    override_reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class OrderScheduleForm(BootstrapFormMixin, forms.Form):
    event_type = forms.ChoiceField(
        choices=[
            (EventType.MEASUREMENT, "Agendar medição"),
            (EventType.DELIVERY, "Agendar entrega"),
            (EventType.INSTALLATION, "Agendar instalação"),
            (EventType.TECHNICAL_ASSISTANCE, "Agendar retorno técnico"),
        ],
    )
    title = forms.CharField(max_length=220)
    start_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    end_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    assigned_user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
    )
    vehicle = forms.ModelChoiceField(queryset=Vehicle.objects.filter(is_active=True), required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    override_conflicts = forms.BooleanField(required=False)
    override_reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
