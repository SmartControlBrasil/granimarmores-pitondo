# ruff: noqa: EM101, TRY003
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import AuditableModel
from core.models import SoftDeleteModel
from core.models import TimeStampedModel

MAX_PERCENTAGE = 100


class Unit(models.TextChoices):
    M2 = "m2", "m²"
    LINEAR_METER = "linear_meter", "Metro linear"
    UNIT = "unit", "Unidade"
    KG = "kg", "Kg"
    SHEET = "sheet", "Chapa"
    SERVICE = "service", "Serviço"


def validate_percentage(value):
    if value is not None and (value < 0 or value > MAX_PERCENTAGE):
        raise ValidationError("Percentual deve estar entre 0 e 100.")


def validate_non_negative(value):
    if value is not None and value < 0:
        raise ValidationError("Valor não pode ser negativo.")


class MaterialCategory(TimeStampedModel, AuditableModel, SoftDeleteModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "categoria de material"
        verbose_name_plural = "categorias de materiais"

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        if self.materials.exists():
            raise ValidationError("Categoria utilizada não pode ser excluída.")
        return super().delete(*args, **kwargs)


class Material(TimeStampedModel, AuditableModel, SoftDeleteModel):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=180)
    category = models.ForeignKey(
        MaterialCategory,
        on_delete=models.PROTECT,
        related_name="materials",
    )
    description = models.TextField(blank=True)
    brand = models.CharField(max_length=120, blank=True)
    origin = models.CharField(max_length=120, blank=True)
    color = models.CharField(max_length=80, blank=True)
    finish = models.CharField(max_length=80, blank=True)
    thickness_mm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    unit = models.CharField(max_length=20, choices=Unit.choices, default=Unit.M2)
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    sale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    minimum_sale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    loss_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_percentage],
    )
    default_margin_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_percentage],
    )
    is_stock_controlled = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        verbose_name = "material"
        verbose_name_plural = "materiais"

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        if self.minimum_sale_price > self.sale_price:
            raise ValidationError(
                {
                    "minimum_sale_price": (
                        "Preço mínimo não pode superar o preço de venda sem "
                        "aprovação administrativa."
                    ),
                },
            )

    def delete(self, *args, **kwargs):
        try:
            from quotes.models import QuoteItem

            if QuoteItem.objects.filter(material=self).exists():
                raise ValidationError(
                    "Material utilizado em orçamento não pode ser excluído.",
                )
        except ImportError:
            pass
        return super().delete(*args, **kwargs)


class MaterialPriceHistory(models.Model):
    class PriceType(models.TextChoices):
        COST = "cost", "Custo"
        SALE = "sale", "Venda"
        MINIMUM_SALE = "minimum_sale", "Venda mínima"

    material = models.ForeignKey(
        Material,
        on_delete=models.CASCADE,
        related_name="price_history",
    )
    price_type = models.CharField(max_length=20, choices=PriceType.choices)
    old_value = models.DecimalField(max_digits=12, decimal_places=2)
    new_value = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True)
    changed_at = models.DateTimeField(default=timezone.now)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return (
            f"{self.material} {self.price_type}: {self.old_value} -> {self.new_value}"
        )

    def save(self, *args, **kwargs):
        if self.pk and MaterialPriceHistory.objects.filter(pk=self.pk).exists():
            raise ValueError("Histórico de preço é append-only.")
        if self.price_type == self.PriceType.MINIMUM_SALE and not self.reason:
            raise ValidationError(
                {"reason": "Alteração de preço mínimo exige justificativa."},
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Histórico de preço não pode ser excluído pela aplicação.")


class MaterialSlab(TimeStampedModel, AuditableModel, SoftDeleteModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Disponível"
        PARTIALLY_RESERVED = "partially_reserved", "Parcialmente reservada"
        FULLY_RESERVED = "fully_reserved", "Totalmente reservada"
        IN_USE = "in_use", "Em uso"
        PARTIALLY_CONSUMED = "partially_consumed", "Parcialmente consumida"
        CONSUMED = "consumed", "Consumida"
        BLOCKED = "blocked", "Bloqueada"
        DAMAGED = "damaged", "Danificada"
        DISCARDED = "discarded", "Descartada"
        INVENTORY_ADJUSTMENT = "inventory_adjustment", "Ajuste de inventário"
        # legado — migrado automaticamente
        RESERVED = "reserved", "Reservada (legado)"
        USED = "used", "Utilizada (legado)"

    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="slabs",
    )
    slab_code = models.CharField(max_length=60, unique=True)
    external_code = models.CharField(max_length=80, blank=True)
    parent_slab = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="remnants",
    )
    is_remnant = models.BooleanField(default=False)
    lot_number = models.CharField(max_length=80, blank=True)
    batch = models.CharField(max_length=80, blank=True)
    bundle = models.CharField(max_length=80, blank=True)
    serial_number = models.CharField(max_length=80, blank=True)
    supplier_name = models.CharField(max_length=160, blank=True)
    supplier_ref = models.ForeignKey(
        "materials.MaterialSupplier",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="slabs",
    )
    width_mm = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[validate_non_negative],
    )
    height_mm = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[validate_non_negative],
    )
    thickness_mm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    total_area = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0000"),
    )
    available_area = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0000"),
    )
    reserved_area = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0000"),
    )
    consumed_area = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0000"),
    )
    lost_area = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0000"),
    )
    cost_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    stock_location = models.ForeignKey(
        "materials.StockLocation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="slabs",
    )
    location_text = models.CharField(max_length=160, blank=True)
    rack = models.CharField(max_length=80, blank=True)
    position = models.CharField(max_length=80, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    block_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["slab_code"]

    @property
    def code(self):
        return self.slab_code

    @property
    def area_m2(self):
        return self.total_area

    @property
    def location(self):
        if self.stock_location_id:
            return str(self.stock_location)
        return self.location_text

    @property
    def supplier(self):
        if self.supplier_ref_id:
            return str(self.supplier_ref)
        return self.supplier_name

    def compute_total_area(self):
        if self.width_mm > 0 and self.height_mm > 0:
            return (self.width_mm * self.height_mm / Decimal("1000000")).quantize(
                Decimal("0.0001"),
            )
        return self.total_area

    def cost_per_m2(self):
        if self.total_area <= 0:
            return Decimal("0.00")
        return (self.cost_value / self.total_area).quantize(Decimal("0.01"))

    def estimated_consumed_cost(self):
        return (self.consumed_area * self.cost_per_m2()).quantize(Decimal("0.01"))

    def clean(self):
        areas = self.reserved_area + self.consumed_area + self.lost_area
        if areas > self.total_area:
            raise ValidationError("Soma das áreas não pode ultrapassar a área total.")
        if self.available_area < 0:
            raise ValidationError({"available_area": "Área disponível não pode ser negativa."})
        if self.width_mm <= 0 or self.height_mm <= 0:
            raise ValidationError("Largura e altura devem ser positivas.")
        if self.thickness_mm < 0:
            raise ValidationError({"thickness_mm": "Espessura não pode ser negativa."})

    def delete(self, *args, **kwargs):
        from materials.stock_models import StockMovement

        if StockMovement.objects.filter(slab=self).exists():
            raise ValidationError("Chapa com movimentações não pode ser excluída.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return self.slab_code


from materials.stock_models import (  # noqa: E402, F401
    MaterialSupplier,
    SlabLoss,
    SlabReservation,
    SlabSequence,
    StockInventory,
    StockInventoryItem,
    StockLocation,
    StockMovement,
)


class FinishType(TimeStampedModel, AuditableModel, SoftDeleteModel):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    unit = models.CharField(
        max_length=20,
        choices=[
            (Unit.LINEAR_METER, "Metro linear"),
            (Unit.UNIT, "Unidade"),
            (Unit.M2, "m²"),
            (Unit.SERVICE, "Serviço"),
        ],
        default=Unit.LINEAR_METER,
    )
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    sale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AdditionalService(TimeStampedModel, AuditableModel, SoftDeleteModel):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    unit = models.CharField(
        max_length=20,
        choices=[
            (Unit.LINEAR_METER, "Metro linear"),
            (Unit.UNIT, "Unidade"),
            (Unit.M2, "m²"),
            (Unit.SERVICE, "Serviço"),
        ],
        default=Unit.SERVICE,
    )
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    sale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
