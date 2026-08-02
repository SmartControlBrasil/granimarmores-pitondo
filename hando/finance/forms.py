from django import forms
from django.utils import timezone

from customers.models import Customer
from finance.models import AccountsPayable
from finance.models import AccountsReceivable
from finance.models import CategoryType
from finance.models import CostCenter
from finance.models import FinancialAccount
from finance.models import FinancialCategory
from finance.models import PaymentMethod
from finance.models import PaymentTerm
from hando.forms import BootstrapFormMixin
from materials.stock_models import MaterialSupplier
from production.models import SalesOrder


class FinancialCategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FinancialCategory
        fields = [
            "name",
            "code",
            "category_type",
            "parent",
            "description",
            "display_order",
            "is_active",
        ]


class CostCenterForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CostCenter
        fields = ["name", "code", "description", "parent", "is_active"]


class PaymentMethodForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PaymentMethod
        fields = [
            "name",
            "code",
            "method_type",
            "requires_reference",
            "allows_installments",
            "maximum_installments",
            "notes",
            "is_active",
        ]


class PaymentTermForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PaymentTerm
        fields = [
            "name",
            "description",
            "installment_count",
            "down_payment_percent",
            "first_due_days",
            "interval_days",
            "is_custom",
            "is_active",
        ]


class FinancialAccountForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FinancialAccount
        fields = [
            "name",
            "account_type",
            "bank_name",
            "branch",
            "account_reference",
            "initial_balance",
            "notes",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.initial_balance_locked:
            self.fields["initial_balance"].disabled = True


class ReceivableForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AccountsReceivable
        fields = [
            "customer",
            "sales_order",
            "description",
            "category",
            "cost_center",
            "payment_term",
            "issue_date",
            "due_date",
            "original_amount",
            "discount_amount",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True)
        self.fields["sales_order"].queryset = SalesOrder.objects.select_related("customer")
        self.fields["category"].queryset = FinancialCategory.objects.filter(
            is_active=True,
            category_type=CategoryType.INCOME,
        )
        self.fields["cost_center"].queryset = CostCenter.objects.filter(is_active=True)
        self.fields["payment_term"].queryset = PaymentTerm.objects.filter(is_active=True)


class PayableForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AccountsPayable
        fields = [
            "supplier_name",
            "material_supplier",
            "description",
            "category",
            "cost_center",
            "issue_date",
            "due_date",
            "original_amount",
            "discount_amount",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["material_supplier"].queryset = MaterialSupplier.objects.filter(is_active=True)
        self.fields["category"].queryset = FinancialCategory.objects.filter(
            is_active=True,
            category_type=CategoryType.EXPENSE,
        )
        self.fields["cost_center"].queryset = CostCenter.objects.filter(is_active=True)


class ReceivePaymentForm(BootstrapFormMixin, forms.Form):
    installment = forms.ModelChoiceField(queryset=None)
    payment_date = forms.DateField(initial=timezone.localdate)
    amount = forms.DecimalField(min_value=0.01, max_digits=14, decimal_places=2)
    payment_method = forms.ModelChoiceField(queryset=PaymentMethod.objects.filter(is_active=True))
    financial_account = forms.ModelChoiceField(queryset=FinancialAccount.objects.filter(is_active=True))
    reference = forms.CharField(required=False, max_length=120)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, receivable=None, **kwargs):
        super().__init__(*args, **kwargs)
        if receivable:
            self.fields["installment"].queryset = receivable.installments.exclude(
                status__in=["paid", "cancelled", "renegotiated"],
            )
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-control"


class PayExpenseForm(BootstrapFormMixin, forms.Form):
    installment = forms.ModelChoiceField(queryset=None)
    payment_date = forms.DateField(initial=timezone.localdate)
    amount = forms.DecimalField(min_value=0.01, max_digits=14, decimal_places=2)
    payment_method = forms.ModelChoiceField(queryset=PaymentMethod.objects.filter(is_active=True))
    financial_account = forms.ModelChoiceField(queryset=FinancialAccount.objects.filter(is_active=True))
    reference = forms.CharField(required=False, max_length=120)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, payable=None, **kwargs):
        super().__init__(*args, **kwargs)
        if payable:
            self.fields["installment"].queryset = payable.installments.exclude(
                status__in=["paid", "cancelled", "renegotiated"],
            )
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-control"


class CancelForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))


class ReversePaymentForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))


class GenerateReceivableForm(BootstrapFormMixin, forms.Form):
    payment_term = forms.ModelChoiceField(
        queryset=PaymentTerm.objects.filter(is_active=True),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    first_due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    category = forms.ModelChoiceField(
        queryset=FinancialCategory.objects.filter(is_active=True, category_type=CategoryType.INCOME),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cost_center = forms.ModelChoiceField(
        queryset=CostCenter.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class TransferForm(BootstrapFormMixin, forms.Form):
    source_account = forms.ModelChoiceField(queryset=FinancialAccount.objects.filter(is_active=True))
    destination_account = forms.ModelChoiceField(queryset=FinancialAccount.objects.filter(is_active=True))
    amount = forms.DecimalField(min_value=0.01, max_digits=14, decimal_places=2)
    movement_date = forms.DateField(initial=timezone.localdate)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class AdjustmentForm(BootstrapFormMixin, forms.Form):
    account = forms.ModelChoiceField(queryset=FinancialAccount.objects.filter(is_active=True))
    direction = forms.ChoiceField(choices=[("in", "Entrada"), ("out", "Saída")])
    amount = forms.DecimalField(min_value=0.01, max_digits=14, decimal_places=2)
    movement_date = forms.DateField(initial=timezone.localdate)
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    category = forms.ModelChoiceField(
        queryset=FinancialCategory.objects.filter(is_active=True),
        required=False,
    )
    cost_center = forms.ModelChoiceField(
        queryset=CostCenter.objects.filter(is_active=True),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
