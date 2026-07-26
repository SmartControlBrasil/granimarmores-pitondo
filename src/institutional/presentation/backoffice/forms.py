from django import forms
from django.contrib.auth import get_user_model

from src.institutional.application.services.access_policy import assignable_users_queryset
from src.institutional.infrastructure.django.models import ContactRequest
from src.institutional.infrastructure.django.models import Opportunity
from src.institutional.infrastructure.django.models import Quote
from src.institutional.infrastructure.django.models import QuoteItem


class LeadStatusForm(forms.Form):
    status = forms.ChoiceField(choices=ContactRequest.Status.choices)


class LeadAssignForm(forms.Form):
    assigned_to = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
        empty_label="Sem responsável",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = assignable_users_queryset(get_user_model())


class LeadNoteForm(forms.Form):
    content = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows": 4}),
        max_length=4000,
    )



class LeadConvertForm(forms.Form):
    assigned_to = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
        empty_label="Usar responsável atual",
    )

    def __init__(self, *args, require_assigned=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = assignable_users_queryset(get_user_model())
        self.fields["assigned_to"].required = require_assigned
        if require_assigned:
            self.fields["assigned_to"].empty_label = "Selecione um responsável"


class OpportunityStageForm(forms.Form):
    stage = forms.ChoiceField(choices=Opportunity.Stage.choices)
    lost_reason = forms.ChoiceField(choices=Opportunity.LostReason.choices, required=False)
    lost_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}), max_length=2000)


class QuoteForm(forms.Form):
    validity_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    discount_amount = forms.DecimalField(required=False, min_value=0, max_digits=12, decimal_places=2, initial=0)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}), max_length=4000)


class QuoteStatusForm(forms.Form):
    status = forms.ChoiceField(choices=Quote.Status.choices)


class QuoteItemForm(forms.Form):
    id = forms.IntegerField(required=False)
    description = forms.CharField(required=False, max_length=255)
    quantity = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=3)
    unit = forms.ChoiceField(choices=QuoteItem.Unit.choices, required=False)
    unit_price = forms.DecimalField(required=False, min_value=0, max_digits=12, decimal_places=2)


QuoteItemFormSet = forms.formset_factory(QuoteItemForm, extra=3, can_delete=False)


class QuoteSendForm(forms.Form):
    recipient = forms.EmailField(required=True)
    allow_resend = forms.BooleanField(required=False)
