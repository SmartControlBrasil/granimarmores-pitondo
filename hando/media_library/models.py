# ruff: noqa: EM101, TRY003
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from core.models import AuditableModel
from core.models import SoftDeleteModel
from core.models import TimeStampedModel


class MediaType(models.TextChoices):
    IMAGE = "image", "Imagem"
    VIDEO = "video", "Vídeo"
    DOCUMENT = "document", "Documento"
    TECHNICAL_DRAWING = "technical_drawing", "Desenho técnico"
    MEASUREMENT_FILE = "measurement_file", "Arquivo de medição"
    QUALITY_REPORT = "quality_report", "Relatório de qualidade"
    CUSTOMER_MESSAGE = "customer_message", "Mensagem do cliente"
    INVOICE_REFERENCE = "invoice_reference", "Referência de fatura"
    OTHER = "other", "Outro"


class MediaStatus(models.TextChoices):
    UPLOADED = "uploaded", "Enviado"
    CLASSIFIED = "classified", "Classificado"
    UNDER_REVIEW = "under_review", "Em revisão"
    APPROVED = "approved", "Aprovado"
    REJECTED = "rejected", "Rejeitado"
    ARCHIVED = "archived", "Arquivado"
    DELETED = "deleted", "Excluído"


class MediaVisibility(models.TextChoices):
    PRIVATE = "private", "Privado"
    INTERNAL = "internal", "Interno"
    CUSTOMER_RELATED = "customer_related", "Relacionado ao cliente"
    PORTFOLIO_CANDIDATE = "portfolio_candidate", "Candidato a portfólio"
    PUBLIC_APPROVED = "public_approved", "Aprovado para uso público"


class TechnicalReviewStatus(models.TextChoices):
    PENDING = "technical_pending", "Pendente"
    APPROVED = "technical_approved", "Aprovado"
    REJECTED = "technical_rejected", "Rejeitado"


class CollectionType(models.TextChoices):
    CUSTOMER_PROJECT = "customer_project", "Projeto do cliente"
    PRODUCTION = "production", "Produção"
    INSTALLATION = "installation", "Instalação"
    BEFORE_AFTER = "before_after", "Antes e depois"
    PORTFOLIO = "portfolio", "Portfólio"
    AFTER_SALES = "after_sales", "Pós-venda"
    MATERIAL_CATALOG = "material_catalog", "Catálogo de materiais"
    CUSTOM = "custom", "Personalizado"


class CollectionStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    ACTIVE = "active", "Ativo"
    UNDER_REVIEW = "under_review", "Em revisão"
    APPROVED = "approved", "Aprovado"
    ARCHIVED = "archived", "Arquivado"


class PublicationChannel(models.TextChoices):
    WEBSITE = "website", "Site"
    BLOG = "blog", "Blog"
    INSTAGRAM = "instagram", "Instagram"
    FACEBOOK = "facebook", "Facebook"
    PORTFOLIO = "portfolio", "Portfólio"
    GOOGLE_BUSINESS_PROFILE = "google_business_profile", "Google Meu Negócio (planejamento)"
    OTHER = "other", "Outro"


class PublicationStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    CANDIDATE = "candidate", "Candidato"
    SCHEDULED = "scheduled", "Planejado"
    CANCELLED = "cancelled", "Cancelado"
    COMPLETED_MANUAL = "completed_manual", "Concluído manualmente"


class LinkTargetType(models.TextChoices):
    CUSTOMER = "customer", "Cliente"
    LEAD = "lead", "Lead"
    QUOTE = "quote", "Orçamento"
    SALES_ORDER = "sales_order", "Pedido"
    PRODUCTION_ORDER = "production_order", "Ordem de produção"
    PRODUCTION_PIECE = "production_piece", "Peça"
    PRODUCTION_STAGE = "production_stage", "Etapa"
    MATERIAL = "material", "Material"
    SLAB = "slab", "Chapa"
    DELIVERY = "delivery_schedule", "Entrega"
    INSTALLATION = "installation_schedule", "Instalação"
    AFTER_SALES_CASE = "after_sales_case", "Pós-venda"
    WARRANTY = "warranty", "Garantia"


class HistoryAction(models.TextChoices):
    UPLOADED = "uploaded", "Upload"
    DUPLICATE_DETECTED = "duplicate_detected", "Duplicidade detectada"
    CLASSIFIED = "classified", "Classificado"
    UPDATED = "updated", "Atualizado"
    LINKED = "linked", "Vinculado"
    UNLINKED = "unlinked", "Desvinculado"
    REVIEWED = "reviewed", "Revisado"
    APPROVED = "approved", "Aprovado"
    REJECTED = "rejected", "Rejeitado"
    PORTFOLIO_APPROVED = "portfolio_approved", "Aprovado para portfólio"
    PORTFOLIO_REMOVED = "portfolio_removed", "Removido do portfólio"
    ARCHIVED = "archived", "Arquivado"
    DELETION_REQUESTED = "deletion_requested", "Exclusão solicitada"
    THUMBNAIL_GENERATED = "thumbnail_generated", "Miniatura gerada"


class MediaAssetSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)


class MediaCollectionSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)


class MediaCategory(TimeStampedModel, SoftDeleteModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    requires_consent = models.BooleanField(default=False)
    is_portfolio_eligible = models.BooleanField(default=False)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)


class MediaTag(TimeStampedModel, SoftDeleteModel):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:100]
        super().save(*args, **kwargs)


def media_asset_upload_to(instance, filename):
    now = timezone.now()
    code = instance.code or "pending"
    return f"library/{now.year:04d}/{now.month:02d}/{code}/{filename}"


def media_thumbnail_upload_to(instance, filename):
    now = timezone.now()
    code = instance.code or "pending"
    return f"library/{now.year:04d}/{now.month:02d}/{code}/thumbs/{filename}"


class MediaAsset(TimeStampedModel, AuditableModel):
    code = models.CharField(max_length=30, unique=True, blank=True)
    file = models.FileField(upload_to=media_asset_upload_to)
    thumbnail = models.ImageField(upload_to=media_thumbnail_upload_to, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    stored_filename = models.CharField(max_length=255, blank=True)
    media_type = models.CharField(max_length=40, choices=MediaType.choices, default=MediaType.IMAGE)
    mime_type = models.CharField(max_length=120, blank=True)
    file_size = models.PositiveBigIntegerField(default=0)
    checksum = models.CharField(max_length=64, blank=True, db_index=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    title = models.CharField(max_length=220, blank=True)
    description = models.TextField(blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=30,
        choices=MediaStatus.choices,
        default=MediaStatus.UPLOADED,
    )
    visibility = models.CharField(
        max_length=30,
        choices=MediaVisibility.choices,
        default=MediaVisibility.PRIVATE,
    )
    technical_review_status = models.CharField(
        max_length=30,
        choices=TechnicalReviewStatus.choices,
        default=TechnicalReviewStatus.PENDING,
    )
    capture_date = models.DateField(null=True, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_media_assets",
    )
    category = models.ForeignKey(
        MediaCategory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assets",
    )
    tags = models.ManyToManyField(MediaTag, blank=True, related_name="assets")
    customer = models.ForeignKey(
        "customers.Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_assets",
    )
    lead = models.ForeignKey(
        "commercial.Lead",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_assets",
    )
    quote = models.ForeignKey(
        "quotes.Quote",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_assets",
    )
    sales_order = models.ForeignKey(
        "production.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_assets",
    )
    production_order = models.ForeignKey(
        "production.ProductionOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_assets",
    )
    production_piece = models.ForeignKey(
        "production.ProductionPiece",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_assets",
    )
    production_stage = models.ForeignKey(
        "production.ProductionStage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_assets",
    )
    material = models.ForeignKey(
        "materials.Material",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_assets",
    )
    slab = models.ForeignKey(
        "materials.MaterialSlab",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_assets",
    )
    delivery_schedule = models.ForeignKey(
        "production.DeliverySchedule",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_assets",
    )
    installation_schedule = models.ForeignKey(
        "production.InstallationSchedule",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_assets",
    )
    after_sales_case = models.ForeignKey(
        "after_sales.AfterSalesCase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_assets",
    )
    warranty = models.ForeignKey(
        "after_sales.WarrantyRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_assets",
    )
    consent = models.ForeignKey(
        "after_sales.MediaUsageConsent",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_assets",
    )
    duplicate_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="duplicates",
    )
    is_portfolio_approved = models.BooleanField(default=False)
    portfolio_approved_at = models.DateTimeField(null=True, blank=True)
    portfolio_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="portfolio_approved_media",
    )
    reject_reason = models.TextField(blank=True)
    archive_reason = models.TextField(blank=True)
    deletion_requested = models.BooleanField(default=False)
    deletion_reason = models.TextField(blank=True)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    deletion_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_deletion_requests",
    )

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["status", "uploaded_at"]),
            models.Index(fields=["visibility", "status"]),
            models.Index(fields=["media_type", "status"]),
            models.Index(fields=["is_portfolio_approved", "status"]),
        ]

    def __str__(self):
        return self.code or f"Mídia {self.pk}"

    def soft_delete(self):
        self.status = MediaStatus.DELETED
        self.save(update_fields=["status", "updated_at"])


class MediaAssetLink(models.Model):
    asset = models.ForeignKey(MediaAsset, on_delete=models.CASCADE, related_name="links")
    target_type = models.CharField(max_length=40, choices=LinkTargetType.choices)
    target_id = models.PositiveIntegerField()
    notes = models.CharField(max_length=220, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("asset", "target_type", "target_id")]
        indexes = [models.Index(fields=["target_type", "target_id"])]


class MediaAssetHistory(models.Model):
    asset = models.ForeignKey(MediaAsset, on_delete=models.CASCADE, related_name="history")
    action = models.CharField(max_length=40, choices=HistoryAction.choices)
    description = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.pk and MediaAssetHistory.objects.filter(pk=self.pk).exists():
            raise ValueError("Histórico de mídia é imutável.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Histórico de mídia não pode ser excluído.")


class MediaReview(models.Model):
    asset = models.ForeignKey(MediaAsset, on_delete=models.CASCADE, related_name="reviews")
    decision = models.CharField(max_length=30, choices=TechnicalReviewStatus.choices)
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="media_reviews",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class MediaCollection(TimeStampedModel, AuditableModel):
    code = models.CharField(max_length=30, unique=True, blank=True)
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    collection_type = models.CharField(max_length=40, choices=CollectionType.choices)
    status = models.CharField(
        max_length=30,
        choices=CollectionStatus.choices,
        default=CollectionStatus.DRAFT,
    )
    customer = models.ForeignKey(
        "customers.Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_collections",
    )
    sales_order = models.ForeignKey(
        "production.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_collections",
    )
    production_order = models.ForeignKey(
        "production.ProductionOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_collections",
    )
    after_sales_case = models.ForeignKey(
        "after_sales.AfterSalesCase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_collections",
    )
    cover_asset = models.ForeignKey(
        MediaAsset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cover_for_collections",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class MediaCollectionItem(models.Model):
    collection = models.ForeignKey(
        MediaCollection,
        on_delete=models.CASCADE,
        related_name="items",
    )
    asset = models.ForeignKey(
        MediaAsset,
        on_delete=models.CASCADE,
        related_name="collection_items",
    )
    display_order = models.PositiveIntegerField(default=0)
    caption = models.CharField(max_length=255, blank=True)
    is_cover = models.BooleanField(default=False)

    class Meta:
        ordering = ["display_order", "id"]
        unique_together = [("collection", "asset")]


class BeforeAfterPair(TimeStampedModel, AuditableModel):
    collection = models.ForeignKey(
        MediaCollection,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="before_after_pairs",
    )
    before_asset = models.ForeignKey(
        MediaAsset,
        on_delete=models.PROTECT,
        related_name="before_pairs",
    )
    after_asset = models.ForeignKey(
        MediaAsset,
        on_delete=models.PROTECT,
        related_name="after_pairs",
    )
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    approved_for_portfolio = models.BooleanField(default=False)
    customer = models.ForeignKey(
        "customers.Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="before_after_pairs",
    )
    sales_order = models.ForeignKey(
        "production.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="before_after_pairs",
    )

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        if self.before_asset_id and self.after_asset_id and self.before_asset_id == self.after_asset_id:
            raise ValidationError("Antes e depois devem ser imagens diferentes.")
        if self.before_asset_id and self.before_asset.media_type != MediaType.IMAGE:
            raise ValidationError("Imagem 'antes' inválida.")
        if self.after_asset_id and self.after_asset.media_type != MediaType.IMAGE:
            raise ValidationError("Imagem 'depois' inválida.")


class PublicationCandidate(TimeStampedModel, AuditableModel):
    asset = models.ForeignKey(
        MediaAsset,
        on_delete=models.CASCADE,
        related_name="publication_candidates",
    )
    channel = models.CharField(max_length=40, choices=PublicationChannel.choices)
    status = models.CharField(
        max_length=30,
        choices=PublicationStatus.choices,
        default=PublicationStatus.CANDIDATE,
    )
    planned_date = models.DateField(null=True, blank=True)
    caption = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_publication_candidates",
    )

    class Meta:
        ordering = ["-created_at"]
