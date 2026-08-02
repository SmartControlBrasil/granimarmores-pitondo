# ruff: noqa: EM101, TRY003
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from core.models import AuditableModel
from core.models import SoftDeleteModel
from core.models import TimeStampedModel
from materials.models import validate_non_negative


class ChannelGroup(models.TextChoices):
    ORGANIC = "organic", "Orgânico"
    SOCIAL = "social", "Redes sociais"
    REFERRAL = "referral", "Indicação"
    PARTNER = "partner", "Parceiro"
    PAID = "paid", "Pago"
    DIRECT = "direct", "Direto"
    OFFLINE = "offline", "Offline"
    OTHER = "other", "Outro"


class PartnerType(models.TextChoices):
    ARCHITECT = "architect", "Arquiteto"
    DESIGNER = "designer", "Designer de interiores"
    ENGINEER = "engineer", "Engenheiro"
    CONSTRUCTION_COMPANY = "construction_company", "Construtora"
    CARPENTRY = "carpentry", "Marcenaria"
    PLANNED_FURNITURE_STORE = "planned_furniture_store", "Loja de móveis planejados"
    RENOVATION_COMPANY = "renovation_company", "Empresa de reforma"
    REAL_ESTATE = "real_estate", "Imobiliária"
    BROKER = "broker", "Corretor"
    INVESTOR = "investor", "Investidor"
    INDEPENDENT_REFERRER = "independent_referrer", "Indicador independente"
    OTHER = "other", "Outro"


class LossCategory(models.TextChoices):
    PRICE = "price", "Preço"
    DEADLINE = "deadline", "Prazo"
    COMPETITOR = "competitor", "Concorrente"
    NO_RESPONSE = "no_response", "Sem resposta"
    PROJECT_CANCELLED = "project_cancelled", "Projeto cancelado"
    MATERIAL_UNAVAILABLE = "material_unavailable", "Material indisponível"
    OUTSIDE_SERVICE_AREA = "outside_service_area", "Fora da área"
    TECHNICAL_INFEASIBILITY = "technical_infeasibility", "Inviabilidade técnica"
    CREDIT_OR_PAYMENT = "credit_or_payment", "Pagamento ou crédito"
    DUPLICATE = "duplicate", "Cadastro duplicado"
    OTHER = "other", "Outro"


class CommercialSource(TimeStampedModel, AuditableModel, SoftDeleteModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    channel_group = models.CharField(max_length=20, choices=ChannelGroup.choices)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "origem comercial"
        verbose_name_plural = "origens comerciais"
        indexes = [
            models.Index(fields=["is_active"], name="commercial_source_active_idx"),
            models.Index(fields=["channel_group"], name="commercial_source_group_idx"),
        ]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        if self.customers.exists() or self.quotes.exists():
            raise ValidationError("Origem comercial em uso não pode ser excluída.")
        return super().delete(*args, **kwargs)


class ProjectType(TimeStampedModel, AuditableModel, SoftDeleteModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    requires_measurement = models.BooleanField(default=True)
    allows_installation = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "tipo de projeto"
        verbose_name_plural = "tipos de projeto"
        indexes = [
            models.Index(fields=["is_active"], name="commercial_projtype_active_idx"),
        ]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        if (
            self.customer_interests.exists()
            or self.quotes.exists()
        ):
            raise ValidationError("Tipo de projeto em uso não pode ser excluído.")
        return super().delete(*args, **kwargs)


class CommercialPartner(TimeStampedModel, AuditableModel, SoftDeleteModel):
    partner_type = models.CharField(max_length=40, choices=PartnerType.choices)
    name = models.CharField(max_length=180)
    trade_name = models.CharField(max_length=180, blank=True)
    document = models.CharField(max_length=20, blank=True)
    contact_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    mobile_phone = models.CharField(max_length=30, blank=True)
    website = models.URLField(blank=True)
    postal_code = models.CharField(max_length=12, blank=True)
    street = models.CharField(max_length=180, blank=True)
    number = models.CharField(max_length=30, blank=True)
    complement = models.CharField(max_length=120, blank=True)
    district = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=2, blank=True)
    notes = models.TextField(blank=True)
    assigned_salesperson = models.ForeignKey(
        "salespeople.Salesperson",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commercial_partners",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "parceiro comercial"
        verbose_name_plural = "parceiros comerciais"
        indexes = [
            models.Index(fields=["is_active"], name="commercial_partner_active_idx"),
            models.Index(fields=["partner_type"], name="commercial_partner_type_idx"),
            models.Index(fields=["city", "state"], name="commercial_partner_city_idx"),
        ]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        if self.customers.exists() or self.quotes.exists():
            raise ValidationError("Parceiro comercial em uso não pode ser excluído.")
        return super().delete(*args, **kwargs)


class LossReason(TimeStampedModel, AuditableModel, SoftDeleteModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=40, choices=LossCategory.choices)
    requires_notes = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "motivo de perda"
        verbose_name_plural = "motivos de perda"
        indexes = [
            models.Index(fields=["is_active"], name="commercial_loss_active_idx"),
            models.Index(fields=["category"], name="commercial_loss_category_idx"),
        ]

    def __str__(self):
        return self.name


class ServiceRegion(TimeStampedModel, AuditableModel, SoftDeleteModel):
    name = models.CharField(max_length=120)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=2)
    district = models.CharField(max_length=120, blank=True)
    postal_code_start = models.CharField(max_length=12, blank=True)
    postal_code_end = models.CharField(max_length=12, blank=True)
    service_enabled = models.BooleanField(default=True)
    travel_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    minimum_order_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    estimated_travel_minutes = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "região de atendimento"
        verbose_name_plural = "regiões de atendimento"
        indexes = [
            models.Index(fields=["city", "state"], name="commercial_region_city_idx"),
            models.Index(
                fields=["service_enabled", "is_active"],
                name="commercial_region_service_idx",
            ),
        ]

    def __str__(self):
        return self.name


class ContactChannel(TimeStampedModel, AuditableModel, SoftDeleteModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "canal de contato"
        verbose_name_plural = "canais de contato"
        indexes = [
            models.Index(fields=["is_active"], name="commercial_channel_active_idx"),
        ]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        if self.customers.exists():
            raise ValidationError("Canal de contato em uso não pode ser excluído.")
        return super().delete(*args, **kwargs)


from commercial.lead_models import Lead  # noqa: E402,F401
from commercial.lead_models import LeadActivity  # noqa: E402,F401
from commercial.lead_models import LeadSequence  # noqa: E402,F401
from commercial.lead_models import LeadTask  # noqa: E402,F401
