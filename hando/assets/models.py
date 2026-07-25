from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import AuditableModel
from core.models import SoftDeleteModel
from core.models import TimeStampedModel


class AssetCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "categoria de ativo"
        verbose_name_plural = "categorias de ativos"

    def __str__(self):
        return self.name


class Asset(TimeStampedModel, AuditableModel, SoftDeleteModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Ativo"
        INACTIVE = "inactive", "Inativo"
        MAINTENANCE = "maintenance", "Em manutenção"
        LOANED = "loaned", "Emprestado"
        DISPOSED = "disposed", "Baixado"
        LOST = "lost", "Perdido"

    asset_code = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=160)
    category = models.ForeignKey(
        AssetCategory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assets",
    )
    description = models.TextField(blank=True)
    manufacturer = models.CharField(max_length=120, blank=True)
    model = models.CharField(max_length=120, blank=True)
    serial_number = models.CharField(max_length=120, blank=True)
    acquisition_date = models.DateField(null=True, blank=True)
    acquisition_value = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    current_value = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    location = models.CharField(max_length=160, blank=True)
    responsible_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="responsible_assets",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE,
    )
    requires_maintenance = models.BooleanField(default=False)
    warranty_expiration = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "ativo"
        verbose_name_plural = "ativos"

    def __str__(self):
        return f"{self.asset_code} - {self.name}"


class AssetDocument(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=80)
    file = models.FileField(upload_to="asset-documents/")
    description = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = "documento do ativo"
        verbose_name_plural = "documentos dos ativos"
