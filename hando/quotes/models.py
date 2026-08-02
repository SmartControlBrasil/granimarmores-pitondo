# ruff: noqa: EM101, TRY003
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import AuditableModel
from core.models import TimeStampedModel
from materials.models import Unit
from materials.models import validate_non_negative
from materials.models import validate_percentage

MAX_PERCENTAGE = 100


class DiscountType(models.TextChoices):
    NONE = "none", "Sem desconto"
    PERCENTAGE = "percentage", "Percentual"
    FIXED = "fixed", "Valor fixo"


class QuoteStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    UNDER_REVIEW = "under_review", "Em revisão"
    PENDING_APPROVAL = "pending_approval", "Aguardando aprovação"
    APPROVED = "approved", "Aprovado"
    REJECTED = "rejected", "Rejeitado"
    SENT = "sent", "Enviado"
    VIEWED = "viewed", "Visualizado"
    ACCEPTED = "accepted", "Aceito"
    EXPIRED = "expired", "Expirado"
    CANCELLED = "cancelled", "Cancelado"
    CONVERTED = "converted", "Convertido"


class QuoteSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    current = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Sequência {self.year}: {self.current}"


class CommercialPolicy(TimeStampedModel, AuditableModel):
    minimum_margin_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("20.00"),
        validators=[validate_percentage],
    )
    salesperson_max_discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("5.00"),
        validators=[validate_percentage],
    )
    manager_max_discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[validate_percentage],
    )
    approval_required_above = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("50000.00"),
        validators=[validate_non_negative],
    )
    quote_default_validity_days = models.PositiveIntegerField(default=15)
    allow_price_below_minimum = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name="unique_active_commercial_policy",
            ),
        ]

    def __str__(self):
        return (
            "Política comercial ativa"
            if self.is_active
            else f"Política comercial {self.pk}"
        )


class Quote(TimeStampedModel, AuditableModel):
    number = models.CharField(max_length=20, unique=True, blank=True)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="quotes",
    )
    salesperson = models.ForeignKey(
        "salespeople.Salesperson",
        on_delete=models.PROTECT,
        related_name="quotes",
    )
    project_type = models.ForeignKey(
        "commercial.ProjectType",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotes",
    )
    commercial_source = models.ForeignKey(
        "commercial.CommercialSource",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotes",
    )
    partner = models.ForeignKey(
        "commercial.CommercialPartner",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotes",
    )
    lead = models.ForeignKey(
        "commercial.Lead",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotes",
    )
    status = models.CharField(
        max_length=30,
        choices=QuoteStatus.choices,
        default=QuoteStatus.DRAFT,
    )
    current_version = models.PositiveIntegerField(default=0)
    valid_until = models.DateField()
    expected_delivery_days = models.PositiveIntegerField(default=0)
    payment_terms = models.CharField(max_length=255, blank=True)
    internal_notes = models.TextField(blank=True)
    customer_notes = models.TextField(blank=True)
    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.NONE,
    )
    discount_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    shipping_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    installation_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    other_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    tax_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_percentage],
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    discount_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    tax_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    grand_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    gross_profit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    gross_margin_percentage = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    requires_approval = models.BooleanField(default=False)
    approval_reasons = models.JSONField(default=list, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_quotes",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rejected_quotes",
    )
    rejection_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cancelled_quotes",
    )
    cancellation_reason = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_quotes",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by_name = models.CharField(max_length=160, blank=True)
    accepted_by_document = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.number or f"Orçamento {self.pk}"

    def clean(self):
        if (
            self.discount_type == DiscountType.PERCENTAGE
            and self.discount_value > MAX_PERCENTAGE
        ):
            raise ValidationError(
                {"discount_value": "Desconto percentual deve estar entre 0 e 100."},
            )
        if (
            self.valid_until
            and self.created_at
            and self.valid_until < timezone.localdate(self.created_at)
        ):
            raise ValidationError(
                {"valid_until": "Validade não pode ser anterior à criação."},
            )
        if self.grand_total < 0:
            raise ValidationError({"grand_total": "Total geral não pode ser negativo."})

    def delete(self, *args, **kwargs):
        raise ValidationError("Orçamentos não podem ser excluídos; use cancelamento.")


class QuoteVersion(models.Model):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    status = models.CharField(max_length=30, choices=QuoteStatus.choices)
    snapshot = models.JSONField(default=dict)
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    discount_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    tax_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    grand_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    gross_profit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    gross_margin_percentage = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    pdf_file = models.FileField(upload_to="quotes/pdf/", blank=True)
    pdf_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_quote_versions",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_quote_versions",
    )

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["quote", "version_number"],
                name="unique_quote_version",
            ),
        ]

    def __str__(self):
        return f"{self.quote.number} v{self.version_number}"

    def save(self, *args, **kwargs):
        if self.pk and QuoteVersion.objects.filter(pk=self.pk).exists():
            raise ValueError("Versões de orçamento são imutáveis.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Versões de orçamento não podem ser excluídas.")


class QuoteItem(TimeStampedModel, AuditableModel):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="items")
    material = models.ForeignKey(
        "materials.Material",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="quote_items",
    )
    material_code_snapshot = models.CharField(max_length=40, blank=True)
    material_name_snapshot = models.CharField(max_length=180, blank=True)
    description = models.CharField(max_length=220, blank=True)
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal("1.000"),
    )
    unit = models.CharField(max_length=20, choices=Unit.choices, default=Unit.M2)
    width_mm = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    length_mm = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    area_m2 = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0000"),
    )
    thickness_mm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    unit_price = models.DecimalField(
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
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_percentage],
    )
    below_minimum_reason = models.TextField(blank=True)
    needs_price_approval = models.BooleanField(default=False)
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    gross_profit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    gross_margin_percentage = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    position = models.PositiveIntegerField(default=1)
    notes = models.TextField(blank=True)
    selected_slab = models.ForeignKey(
        "materials.MaterialSlab",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quote_items",
    )

    class Meta:
        ordering = ["position", "id"]

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError({"quantity": "Quantidade deve ser positiva."})
        if not self.material and not self.description:
            raise ValidationError(
                {"description": "Descrição é obrigatória para item especial."},
            )

    def __str__(self):
        return self.description or self.material_name_snapshot or "Item"


class QuoteItemMeasurement(models.Model):
    quote_item = models.ForeignKey(
        QuoteItem,
        on_delete=models.CASCADE,
        related_name="measurements",
    )
    label = models.CharField(max_length=120)
    width_mm = models.DecimalField(max_digits=10, decimal_places=2)
    length_mm = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal("1.000"),
    )
    area_m2 = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0000"),
    )
    notes = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.label} - {self.quote_item}"


class QuoteItemFinish(models.Model):
    quote_item = models.ForeignKey(
        QuoteItem,
        on_delete=models.CASCADE,
        related_name="finishes",
    )
    finish_type = models.ForeignKey("materials.FinishType", on_delete=models.PROTECT)
    description_snapshot = models.CharField(max_length=180, blank=True)
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal("1.000"),
    )
    unit = models.CharField(
        max_length=20,
        choices=Unit.choices,
        default=Unit.LINEAR_METER,
    )
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    position = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.description_snapshot or self.finish_type} - {self.quote_item}"


class QuoteService(models.Model):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="services")
    service = models.ForeignKey("materials.AdditionalService", on_delete=models.PROTECT)
    description_snapshot = models.CharField(max_length=180, blank=True)
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal("1.000"),
    )
    unit = models.CharField(max_length=20, choices=Unit.choices, default=Unit.SERVICE)
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    position = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.description_snapshot or self.service} - {self.quote}"


class QuoteDelivery(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"
        MANUAL = "manual", "Manual"
        PRINT = "print", "Impressão"
        DOWNLOAD = "download", "Download"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        SENT = "sent", "Enviado"
        FAILED = "failed", "Falhou"
        DELIVERED = "delivered", "Entregue"
        VIEWED = "viewed", "Visualizado"

    quote = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    quote_version = models.ForeignKey(
        QuoteVersion,
        on_delete=models.PROTECT,
        related_name="deliveries",
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    recipient = models.CharField(max_length=255)
    subject = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    provider_message_id = models.CharField(max_length=120, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-sent_at", "-id"]

    def __str__(self):
        return f"{self.quote} - {self.channel} - {self.status}"
