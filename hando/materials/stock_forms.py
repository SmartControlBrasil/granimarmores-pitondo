from django import forms

from hando.forms import BootstrapFormMixin

from materials.models import Material
from materials.models import MaterialSlab
from materials.stock_models import MaterialSupplier
from materials.stock_models import SlabLoss
from materials.stock_models import SlabReservation
from materials.stock_models import StockInventory
from materials.stock_models import StockLocation


class MaterialSupplierForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MaterialSupplier
        fields = [
            "name",
            "trade_name",
            "document",
            "contact_name",
            "phone",
            "email",
            "city",
            "state",
            "notes",
            "is_active",
        ]


class StockLocationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StockLocation
        fields = [
            "name",
            "code",
            "description",
            "location_type",
            "parent",
            "display_order",
            "is_active",
        ]


class SlabReceiveForm(BootstrapFormMixin, forms.Form):
    material = forms.ModelChoiceField(queryset=Material.objects.filter(is_active=True))
    width = forms.DecimalField(label="Largura (mm)", min_value=0.01, max_digits=10, decimal_places=2)
    height = forms.DecimalField(label="Altura (mm)", min_value=0.01, max_digits=10, decimal_places=2)
    thickness = forms.DecimalField(label="Espessura (mm)", min_value=0, max_digits=8, decimal_places=2)
    supplier = forms.ModelChoiceField(
        queryset=MaterialSupplier.objects.filter(is_active=True),
        required=False,
    )
    location = forms.ModelChoiceField(
        queryset=StockLocation.objects.filter(is_active=True),
        required=False,
    )
    cost_value = forms.DecimalField(label="Custo", min_value=0, max_digits=12, decimal_places=2)
    external_code = forms.CharField(required=False)
    batch = forms.CharField(required=False)
    bundle = forms.CharField(required=False)
    serial_number = forms.CharField(required=False)
    lot_number = forms.CharField(required=False)
    rack = forms.CharField(required=False)
    position = forms.CharField(required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class SlabTransferForm(BootstrapFormMixin, forms.Form):
    destination = forms.ModelChoiceField(queryset=StockLocation.objects.filter(is_active=True))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class SlabBlockForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(label="Motivo", widget=forms.Textarea(attrs={"rows": 3}))


class SlabAdjustForm(BootstrapFormMixin, forms.Form):
    new_available_area = forms.DecimalField(label="Nova área disponível (m²)", max_digits=10, decimal_places=4)
    reason = forms.CharField(label="Justificativa", widget=forms.Textarea(attrs={"rows": 3}))


class SlabReservationForm(BootstrapFormMixin, forms.Form):
    slab = forms.ModelChoiceField(queryset=MaterialSlab.objects.none())
    reserved_area = forms.DecimalField(label="Área reservada (m²)", max_digits=10, decimal_places=4, min_value=0.0001)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, piece=None, **kwargs):
        super().__init__(*args, **kwargs)
        if piece:
            from materials.services.stock_operations import compatible_slabs_for_piece

            self.fields["slab"].queryset = compatible_slabs_for_piece(piece=piece)


class SlabConsumptionForm(BootstrapFormMixin, forms.Form):
    consumed_area = forms.DecimalField(label="Área consumida (m²)", max_digits=10, decimal_places=4, min_value=0.0001)
    lost_area = forms.DecimalField(label="Área perdida (m²)", max_digits=10, decimal_places=4, min_value=0, required=False, initial=0)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    remnant_width = forms.DecimalField(label="Sobra largura (mm)", required=False, max_digits=10, decimal_places=2)
    remnant_height = forms.DecimalField(label="Sobra altura (mm)", required=False, max_digits=10, decimal_places=2)


class SlabLossForm(BootstrapFormMixin, forms.Form):
    area = forms.DecimalField(label="Área (m²)", max_digits=10, decimal_places=4, min_value=0.0001)
    loss_reason = forms.ChoiceField(choices=SlabLoss.LossReason.choices)
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class StockInventoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StockInventory
        fields = ["location", "notes"]


class StockInventoryItemForm(BootstrapFormMixin, forms.Form):
    counted_area = forms.DecimalField(label="Área contada (m²)", max_digits=10, decimal_places=4, min_value=0)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class MaterialSlabEditForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MaterialSlab
        fields = [
            "external_code",
            "lot_number",
            "batch",
            "bundle",
            "serial_number",
            "supplier_ref",
            "supplier_name",
            "rack",
            "position",
            "stock_location",
            "location_text",
            "notes",
            "is_active",
        ]
