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
        RESERVED = "reserved", "Reservada"
        USED = "used", "Utilizada"
        DAMAGED = "damaged", "Danificada"
        DISCARDED = "discarded", "Descartada"

    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="slabs",
    )
    slab_code = models.CharField(max_length=60, unique=True)
    lot_number = models.CharField(max_length=80, blank=True)
    supplier = models.CharField(max_length=160, blank=True)
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
    area_m2 = models.DecimalField(
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
    location = models.CharField(max_length=160, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["slab_code"]

    def save(self, *args, **kwargs):
        self.area_m2 = (self.width_mm * self.height_mm / Decimal("1000000")).quantize(
            Decimal("0.0001"),
        )
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.slab_code


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
