# ruff: noqa: EM101, TRY003
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import AuditableModel
from core.models import SoftDeleteModel
from core.models import TimeStampedModel
from materials.models import validate_non_negative


class MaterialSupplier(TimeStampedModel, AuditableModel, SoftDeleteModel):
    name = models.CharField(max_length=180)
    trade_name = models.CharField(max_length=180, blank=True)
    document = models.CharField(max_length=20, blank=True)
    contact_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=2, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "fornecedor de material"
        verbose_name_plural = "fornecedores de material"

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        from materials.models import MaterialSlab

        if MaterialSlab.objects.filter(supplier_ref=self).exists():
            raise ValidationError("Fornecedor com chapas não pode ser excluído.")
        return super().delete(*args, **kwargs)


class StockLocation(TimeStampedModel, AuditableModel, SoftDeleteModel):
    class LocationType(models.TextChoices):
        WAREHOUSE = "warehouse", "Galpão"
        YARD = "yard", "Pátio"
        RACK = "rack", "Cavalete"
        SHELF = "shelf", "Prateleira"
        PRODUCTION_AREA = "production_area", "Área de produção"
        QUARANTINE = "quarantine", "Quarentena"
        SCRAP = "scrap", "Sucata"
        OTHER = "other", "Outro"

    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40, unique=True)
    description = models.TextField(blank=True)
    location_type = models.CharField(
        max_length=30,
        choices=LocationType.choices,
        default=LocationType.WAREHOUSE,
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "localização de estoque"
        verbose_name_plural = "localizações de estoque"

    def __str__(self):
        return f"{self.code} — {self.name}"

    def delete(self, *args, **kwargs):
        from materials.models import MaterialSlab

        if MaterialSlab.objects.filter(stock_location=self).exists():
            raise ValidationError("Localização em uso não pode ser excluída.")
        if StockInventory.objects.filter(location=self).exists():
            raise ValidationError("Localização com inventário não pode ser excluída.")
        return super().delete(*args, **kwargs)


class SlabSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "sequência de chapas"
        verbose_name_plural = "sequências de chapas"


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        ENTRY = "entry", "Entrada"
        TRANSFER = "transfer", "Transferência"
        RESERVATION = "reservation", "Reserva"
        RESERVATION_RELEASE = "reservation_release", "Liberação de reserva"
        CONSUMPTION = "consumption", "Consumo"
        LOSS = "loss", "Perda"
        SCRAP = "scrap", "Descarte"
        INVENTORY_INCREASE = "inventory_increase", "Ajuste inventário (+)"
        INVENTORY_DECREASE = "inventory_decrease", "Ajuste inventário (-)"
        RETURN_TO_STOCK = "return_to_stock", "Retorno ao estoque"
        BLOCK = "block", "Bloqueio"
        UNBLOCK = "unblock", "Desbloqueio"

    slab = models.ForeignKey(
        "materials.MaterialSlab",
        on_delete=models.PROTECT,
        related_name="movements",
    )
    movement_type = models.CharField(max_length=30, choices=MovementType.choices)
    quantity_area = models.DecimalField(max_digits=10, decimal_places=4)
    previous_available_area = models.DecimalField(max_digits=10, decimal_places=4)
    new_available_area = models.DecimalField(max_digits=10, decimal_places=4)
    source_location = models.ForeignKey(
        StockLocation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="movements_from",
    )
    destination_location = models.ForeignKey(
        StockLocation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="movements_to",
    )
    reference_type = models.CharField(max_length=60, blank=True)
    reference_id = models.CharField(max_length=60, blank=True)
    description = models.TextField(blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stock_movements_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-pk"]
        indexes = [
            models.Index(fields=["reference_type", "reference_id"]),
            models.Index(fields=["slab", "movement_type"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["movement_type", "reference_type", "reference_id"],
                condition=models.Q(reference_type__gt=""),
                name="unique_stock_movement_reference",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and StockMovement.objects.filter(pk=self.pk).exists():
            raise ValueError("Movimentação de estoque é imutável.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Movimentação de estoque não pode ser excluída.")

    def __str__(self):
        return f"{self.slab_id} {self.movement_type} {self.quantity_area}m²"


class SlabReservation(TimeStampedModel, AuditableModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Ativa"
        RELEASED = "released", "Liberada"
        PARTIALLY_CONSUMED = "partially_consumed", "Parcialmente consumida"
        CONSUMED = "consumed", "Consumida"
        CANCELLED = "cancelled", "Cancelada"

    slab = models.ForeignKey(
        "materials.MaterialSlab",
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    production_order = models.ForeignKey(
        "production.ProductionOrder",
        on_delete=models.PROTECT,
        related_name="slab_reservations",
    )
    production_piece = models.ForeignKey(
        "production.ProductionPiece",
        on_delete=models.PROTECT,
        related_name="slab_reservations",
    )
    reserved_area = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[validate_non_negative],
    )
    consumed_area = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0000"),
        validators=[validate_non_negative],
    )
    lost_area = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0000"),
        validators=[validate_non_negative],
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    reserved_at = models.DateTimeField(default=timezone.now)
    released_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="slab_reservations_released",
    )

    class Meta:
        ordering = ["-reserved_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["slab", "production_piece"],
                condition=models.Q(status="active"),
                name="unique_active_slab_piece_reservation",
            ),
        ]

    def __str__(self):
        return f"Reserva {self.slab} — {self.production_piece}"


class SlabLoss(models.Model):
    class LossReason(models.TextChoices):
        CUTTING_LOSS = "cutting_loss", "Perda de corte"
        BREAKAGE = "breakage", "Quebra"
        DEFECT = "defect", "Defeito"
        MEASUREMENT_ERROR = "measurement_error", "Erro de medição"
        HANDLING_DAMAGE = "handling_damage", "Avaria no manuseio"
        QUALITY_REJECTION = "quality_rejection", "Reprovação de qualidade"
        UNUSABLE_REMNANT = "unusable_remnant", "Sobra inutilizável"
        OTHER = "other", "Outro"

    slab = models.ForeignKey(
        "materials.MaterialSlab",
        on_delete=models.PROTECT,
        related_name="losses",
    )
    production_piece = models.ForeignKey(
        "production.ProductionPiece",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="slab_losses",
    )
    reservation = models.ForeignKey(
        SlabReservation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="losses",
    )
    area = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[validate_non_negative],
    )
    loss_reason = models.CharField(max_length=40, choices=LossReason.choices)
    description = models.TextField(blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="slab_losses_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]

    def clean(self):
        if self.loss_reason == self.LossReason.OTHER and not self.description.strip():
            raise ValidationError(
                {"description": "Descrição obrigatória para motivo 'Outro'."},
            )


class StockInventory(TimeStampedModel, AuditableModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        IN_PROGRESS = "in_progress", "Em andamento"
        COMPLETED = "completed", "Concluído"
        CANCELLED = "cancelled", "Cancelado"

    number = models.CharField(max_length=30, unique=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    location = models.ForeignKey(
        StockLocation,
        on_delete=models.PROTECT,
        related_name="inventories",
    )
    notes = models.TextField(blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_inventories_completed",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "inventário de estoque"
        verbose_name_plural = "inventários de estoque"

    def __str__(self):
        return self.number


class StockInventoryItem(models.Model):
    class ItemStatus(models.TextChoices):
        PENDING = "pending", "Pendente"
        COUNTED = "counted", "Contado"
        ADJUSTED = "adjusted", "Ajustado"
        SKIPPED = "skipped", "Ignorado"

    inventory = models.ForeignKey(
        StockInventory,
        on_delete=models.CASCADE,
        related_name="items",
    )
    slab = models.ForeignKey(
        "materials.MaterialSlab",
        on_delete=models.PROTECT,
        related_name="inventory_items",
    )
    expected_area = models.DecimalField(max_digits=10, decimal_places=4)
    counted_area = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
    )
    difference_area = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=ItemStatus.choices,
        default=ItemStatus.PENDING,
    )
    notes = models.TextField(blank=True)
    counted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inventory_items_counted",
    )
    counted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["slab__slab_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["inventory", "slab"],
                name="unique_inventory_slab",
            ),
        ]
