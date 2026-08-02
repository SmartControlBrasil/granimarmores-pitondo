from decimal import Decimal

from django import forms

from finance.models import CostCenter
from finance.models import PaymentMethod
from finance.models import PaymentTerm
from materials.models import Material
from materials.stock_models import MaterialSupplier
from materials.stock_models import StockLocation
from purchasing.models import ItemType
from purchasing.models import Priority
from purchasing.models import PurchaseOrder
from purchasing.models import PurchaseRequest
from purchasing.models import ReceiptCondition
from purchasing.models import RequestType
from purchasing.models import SourceType
from purchasing.models import SupplierQuotation


class _StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = (css + " form-control").strip()
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = (css + " form-select").strip()


class PurchaseRequestForm(_StyledModelForm):
    class Meta:
        model = PurchaseRequest
        fields = [
            "request_type",
            "priority",
            "cost_center",
            "required_date",
            "justification",
            "notes",
            "source_type",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cost_center"].queryset = CostCenter.objects.filter(is_active=True)
        self.fields["cost_center"].required = False
        self.fields["required_date"].required = False
        self.fields["notes"].required = False


class PurchaseRequestItemForm(forms.Form):
    item_type = forms.ChoiceField(choices=ItemType.choices, initial=ItemType.MATERIAL)
    material = forms.ModelChoiceField(
        queryset=Material.objects.filter(is_active=True),
        required=False,
    )
    description = forms.CharField(max_length=255)
    quantity = forms.DecimalField(min_value=Decimal("0.001"), max_digits=12, decimal_places=3)
    unit = forms.CharField(max_length=40, initial="un")
    estimated_unit_cost = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        max_digits=12,
        decimal_places=2,
        initial=Decimal("0"),
    )
    technical_specification = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    preferred_supplier = forms.ModelChoiceField(
        queryset=MaterialSupplier.objects.filter(is_active=True),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-control"
            if isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs["class"] = "form-select"


class RejectForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))


class CancelForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))


class QuotationForm(_StyledModelForm):
    class Meta:
        model = SupplierQuotation
        fields = [
            "purchase_request",
            "supplier",
            "quotation_date",
            "valid_until",
            "delivery_days",
            "freight_amount",
            "discount_amount",
            "payment_term_text",
            "payment_method",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = MaterialSupplier.objects.filter(is_active=True)
        self.fields["purchase_request"].queryset = PurchaseRequest.objects.exclude(
            status__in=["cancelled", "rejected", "draft"],
        )
        self.fields["payment_method"].queryset = PaymentMethod.objects.filter(is_active=True)
        self.fields["payment_method"].required = False
        self.fields["valid_until"].required = False
        self.fields["notes"].required = False


class QuotationItemForm(forms.Form):
    request_item_id = forms.IntegerField(required=False)
    description = forms.CharField(max_length=255)
    quantity = forms.DecimalField(min_value=Decimal("0.001"), max_digits=12, decimal_places=3)
    unit = forms.CharField(max_length=40, initial="un")
    unit_price = forms.DecimalField(min_value=Decimal("0"), max_digits=12, decimal_places=2)
    delivery_days = forms.IntegerField(required=False, min_value=0, initial=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class SelectionForm(forms.Form):
    quotation_item_ids = forms.TypedMultipleChoiceField(
        coerce=int,
        required=True,
        widget=forms.CheckboxSelectMultiple,
    )
    justification = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}))

    def __init__(self, *args, choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        if choices is not None:
            self.fields["quotation_item_ids"].choices = choices


class ReceiptCreateForm(forms.Form):
    delivery_document = forms.CharField(required=False, max_length=120)
    supplier_document = forms.CharField(required=False, max_length=120)
    stock_location = forms.ModelChoiceField(
        queryset=StockLocation.objects.filter(is_active=True),
        required=False,
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    allow_excess = forms.BooleanField(required=False, label="Permitir excesso (override)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "allow_excess":
                continue
            field.widget.attrs["class"] = "form-control"
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"


class ReceiptItemForm(forms.Form):
    purchase_order_item_id = forms.IntegerField(widget=forms.HiddenInput)
    received_quantity = forms.DecimalField(min_value=Decimal("0"), max_digits=12, decimal_places=3)
    accepted_quantity = forms.DecimalField(min_value=Decimal("0"), max_digits=12, decimal_places=3)
    rejected_quantity = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        max_digits=12,
        decimal_places=3,
        initial=Decimal("0"),
    )
    actual_unit_cost = forms.DecimalField(required=False, min_value=Decimal("0"), max_digits=12, decimal_places=2)
    width = forms.DecimalField(required=False, min_value=Decimal("0"), max_digits=10, decimal_places=2)
    height = forms.DecimalField(required=False, min_value=Decimal("0"), max_digits=10, decimal_places=2)
    thickness = forms.DecimalField(required=False, min_value=Decimal("0"), max_digits=10, decimal_places=2)
    batch = forms.CharField(required=False, max_length=80)
    condition = forms.ChoiceField(choices=ReceiptCondition.choices, initial=ReceiptCondition.ACCEPTED)
    divergence_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 1}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "purchase_order_item_id":
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


class PurchaseOrderEditForm(_StyledModelForm):
    class Meta:
        model = PurchaseOrder
        fields = [
            "expected_delivery_date",
            "delivery_location",
            "payment_term",
            "payment_method",
            "notes",
            "internal_notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["delivery_location"].queryset = StockLocation.objects.filter(is_active=True)
        self.fields["payment_term"].queryset = PaymentTerm.objects.filter(is_active=True)
        self.fields["payment_method"].queryset = PaymentMethod.objects.filter(is_active=True)


class ReturnForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}))
    receipt_item_id = forms.IntegerField()
    quantity = forms.DecimalField(min_value=Decimal("0.001"), max_digits=12, decimal_places=3)
    slab_id = forms.IntegerField(required=False)


# Keep imports used by views for convenience
RequestType = RequestType
Priority = Priority
SourceType = SourceType
