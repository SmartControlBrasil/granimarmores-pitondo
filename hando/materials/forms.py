from django import forms

from materials.models import AdditionalService
from materials.models import FinishType
from materials.models import Material
from materials.models import MaterialCategory
from materials.models import MaterialSlab


class MaterialCategoryForm(forms.ModelForm):
    class Meta:
        model = MaterialCategory
        fields = ["name", "slug", "description", "is_active"]


class MaterialForm(forms.ModelForm):
    price_change_reason = forms.CharField(
        label="Justificativa de alteração de preço",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    class Meta:
        model = Material
        fields = [
            "code",
            "name",
            "category",
            "description",
            "brand",
            "origin",
            "color",
            "finish",
            "thickness_mm",
            "unit",
            "cost_price",
            "sale_price",
            "minimum_sale_price",
            "loss_percentage",
            "default_margin_percentage",
            "is_stock_controlled",
            "is_active",
        ]

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk:
            old = Material.objects.get(pk=self.instance.pk)
            if old.minimum_sale_price != cleaned.get(
                "minimum_sale_price",
            ) and not cleaned.get("price_change_reason"):
                self.add_error(
                    "price_change_reason",
                    "Alteração de preço mínimo exige justificativa.",
                )
        return cleaned


class MaterialPriceChangeForm(forms.Form):
    price_type = forms.ChoiceField(
        choices=[
            ("cost", "Custo"),
            ("sale", "Venda"),
            ("minimum_sale", "Venda mínima"),
        ],
    )
    new_value = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2)
    reason = forms.CharField(
        label="Justificativa",
        widget=forms.Textarea(attrs={"rows": 2}),
    )


class MaterialSlabForm(forms.ModelForm):
    class Meta:
        model = MaterialSlab
        fields = [
            "material",
            "slab_code",
            "external_code",
            "lot_number",
            "batch",
            "supplier_ref",
            "supplier_name",
            "width_mm",
            "height_mm",
            "thickness_mm",
            "cost_value",
            "stock_location",
            "location_text",
            "rack",
            "position",
            "status",
            "notes",
            "is_active",
        ]


class FinishTypeForm(forms.ModelForm):
    class Meta:
        model = FinishType
        fields = [
            "code",
            "name",
            "description",
            "unit",
            "cost_price",
            "sale_price",
            "is_active",
        ]


class AdditionalServiceForm(forms.ModelForm):
    class Meta:
        model = AdditionalService
        fields = [
            "code",
            "name",
            "description",
            "unit",
            "cost_price",
            "sale_price",
            "is_active",
        ]
