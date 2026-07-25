from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import AuditableModel
from core.models import SoftDeleteModel
from core.models import TimeStampedModel


class Vehicle(TimeStampedModel, AuditableModel, SoftDeleteModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Ativo"
        MAINTENANCE = "maintenance", "Em manutenção"
        INACTIVE = "inactive", "Inativo"
        SOLD = "sold", "Vendido"
        ACCIDENT = "accident", "Sinistro"

    class FuelType(models.TextChoices):
        GASOLINE = "gasoline", "Gasolina"
        ETHANOL = "ethanol", "Etanol"
        FLEX = "flex", "Flex"
        DIESEL = "diesel", "Diesel"
        ELECTRIC = "electric", "Elétrico"
        HYBRID = "hybrid", "Híbrido"
        OTHER = "other", "Outro"

    asset_code = models.CharField(max_length=60, unique=True)
    plate = models.CharField(max_length=10, unique=True)
    renavam = models.CharField(max_length=20, unique=True, null=True, blank=True)
    chassis = models.CharField(max_length=40, unique=True, null=True, blank=True)
    brand = models.CharField(max_length=80)
    model = models.CharField(max_length=100)
    manufacture_year = models.PositiveIntegerField(null=True, blank=True)
    model_year = models.PositiveIntegerField(null=True, blank=True)
    fuel_type = models.CharField(
        max_length=20, choices=FuelType.choices, default=FuelType.FLEX,
    )
    color = models.CharField(max_length=50, blank=True)
    odometer = models.PositiveIntegerField(default=0)
    acquisition_date = models.DateField(null=True, blank=True)
    acquisition_value = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    responsible_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="responsible_vehicles",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE,
    )
    licensing_expiration = models.DateField(null=True, blank=True)
    insurance_expiration = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["plate"]
        verbose_name = "veículo"
        verbose_name_plural = "veículos"

    def __str__(self):
        return f"{self.plate} - {self.brand} {self.model}"

    def clean(self):
        if self.pk:
            old = Vehicle.objects.filter(pk=self.pk).values("odometer").first()
            if old and self.odometer < old["odometer"]:
                raise ValidationError(
                    {
                        "odometer": "O odômetro não pode diminuir sem fluxo administrativo auditado.",
                    },
                )
        if self.plate:
            self.plate = self.plate.upper().replace("-", "")
