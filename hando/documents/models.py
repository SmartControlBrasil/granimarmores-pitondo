from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import AuditableModel
from core.models import TimeStampedModel


class DocumentCategory(models.TextChoices):
    COMMERCIAL = "commercial", "Comercial"
    CONTRACT = "contract", "Contrato"
    TECHNICAL = "technical", "Técnico"
    OPERATIONAL = "operational", "Operacional"
    FINANCIAL = "financial", "Financeiro"
    SUPPLIER = "supplier", "Fornecedor"
    WARRANTY = "warranty", "Garantia"
    CONSENT = "consent", "Consentimento"
    INTERNAL = "internal", "Interno"
    OTHER = "other", "Outro"


class TemplateStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    UNDER_REVIEW = "under_review", "Em revisão"
    APPROVED = "approved", "Aprovado"
    INACTIVE = "inactive", "Inativo"
    ARCHIVED = "archived", "Arquivado"


class ContentFormat(models.TextChoices):
    HTML = "html", "HTML"
    PLAIN_TEXT = "plain_text", "Texto"
    UPLOADED_FILE = "uploaded_file", "Arquivo"


class DocumentStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    UNDER_REVIEW = "under_review", "Em revisão"
    APPROVED = "approved", "Aprovado"
    SENT = "sent", "Enviado"
    VIEWED = "viewed", "Visualizado"
    ACCEPTED = "accepted", "Aceito"
    SIGNED = "signed", "Assinado"
    ACTIVE = "active", "Ativo"
    EXPIRED = "expired", "Vencido"
    REJECTED = "rejected", "Rejeitado"
    CANCELLED = "cancelled", "Cancelado"
    TERMINATED = "terminated", "Encerrado"
    ARCHIVED = "archived", "Arquivado"


class Confidentiality(models.TextChoices):
    PUBLIC_INTERNAL = "public_internal", "Interno amplo"
    INTERNAL = "internal", "Interno"
    RESTRICTED = "restricted", "Restrito"
    CONFIDENTIAL = "confidential", "Confidencial"


class VersionStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    UNDER_REVIEW = "under_review", "Em revisão"
    APPROVED = "approved", "Aprovado"
    SUPERSEDED = "superseded", "Substituído"
    REJECTED = "rejected", "Rejeitado"
    ARCHIVED = "archived", "Arquivado"


class ReviewStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    APPROVED = "approved", "Aprovado"
    CHANGES_REQUESTED = "changes_requested", "Alterações solicitadas"
    REJECTED = "rejected", "Rejeitado"
    CANCELLED = "cancelled", "Cancelado"


class ApprovalStepStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    APPROVED = "approved", "Aprovado"
    REJECTED = "rejected", "Rejeitado"
    SKIPPED = "skipped", "Ignorado"
    CANCELLED = "cancelled", "Cancelado"


class SendChannel(models.TextChoices):
    EMAIL = "email", "E-mail"
    WHATSAPP = "whatsapp", "WhatsApp"
    PRINTED = "printed", "Impresso"
    IN_PERSON = "in_person", "Presencial"
    PORTAL = "portal", "Portal"
    OTHER = "other", "Outro"


class AcceptanceType(models.TextChoices):
    CUSTOMER = "customer_acceptance", "Aceite do cliente"
    SUPPLIER = "supplier_acceptance", "Aceite do fornecedor"
    INTERNAL = "internal_acceptance", "Aceite interno"
    DELIVERY = "delivery_acceptance", "Aceite de entrega"
    INSTALLATION = "installation_acceptance", "Aceite de instalação"
    OTHER = "other", "Outro"


class AcceptanceStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    ACCEPTED = "accepted", "Aceito"
    REJECTED = "rejected", "Rejeitado"
    REVOKED = "revoked", "Revogado"
    CANCELLED = "cancelled", "Cancelado"


class SignatureType(models.TextChoices):
    WET = "wet_signature", "Assinatura manuscrita"
    MANUAL = "manual_confirmation", "Confirmação manual"
    UPLOADED = "uploaded_signed_copy", "Cópia assinada anexada"
    ELECTRONIC_EXTERNAL = "electronic_external", "Assinatura eletrônica externa"
    OTHER = "other", "Outro"


class AttachmentType(models.TextChoices):
    IDENTITY = "identity", "Identidade"
    PROOF = "proof", "Comprovante"
    PLAN = "plan", "Planta"
    MEMORIAL = "memorial", "Memorial"
    PROPOSAL = "proposal", "Proposta"
    REPORT = "report", "Relatório"
    PHOTO = "photo", "Foto"
    SIGNED = "signed", "Documento assinado"
    ADDENDUM = "addendum", "Aditivo"
    OTHER = "other", "Outro"


class RelationshipType(models.TextChoices):
    AMENDMENT = "amendment", "Aditivo"
    REPLACEMENT = "replacement", "Substituição"
    RENEWAL = "renewal", "Renovação"
    CANCELLATION_TERM = "cancellation_term", "Termo de cancelamento"
    ATTACHMENT = "attachment", "Anexo"
    REFERENCE = "reference", "Referência"


class DocumentSequence(models.Model):
    kind = models.CharField(max_length=40)
    year = models.PositiveIntegerField()
    current = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kind", "year"], name="unique_document_seq_kind_year"),
        ]


class DocumentType(TimeStampedModel):
    name = models.CharField(max_length=160)
    code = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=30,
        choices=DocumentCategory.choices,
        default=DocumentCategory.OTHER,
    )
    requires_internal_approval = models.BooleanField(default=True)
    requires_customer_acceptance = models.BooleanField(default=False)
    requires_signature = models.BooleanField(default=False)
    has_validity = models.BooleanField(default=False)
    default_validity_days = models.PositiveIntegerField(null=True, blank=True)
    allows_renewal = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        if self.documents.exists() or self.templates.exists():
            raise ValidationError("Tipo de documento em uso não pode ser excluído.")
        return super().delete(*args, **kwargs)


class DocumentTemplate(TimeStampedModel, AuditableModel):
    name = models.CharField(max_length=180)
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name="templates",
    )
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=TemplateStatus.choices,
        default=TemplateStatus.DRAFT,
    )
    content_format = models.CharField(
        max_length=20,
        choices=ContentFormat.choices,
        default=ContentFormat.PLAIN_TEXT,
    )
    body = models.TextField(blank=True)
    header = models.TextField(blank=True)
    footer = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} v{self.version}"


class ManagedDocument(TimeStampedModel, AuditableModel):
    number = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=220)
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name="documents",
    )
    template = models.ForeignKey(
        DocumentTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documents",
    )
    status = models.CharField(
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.DRAFT,
    )
    customer = models.ForeignKey(
        "customers.Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_documents",
    )
    lead = models.ForeignKey(
        "commercial.Lead",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_documents",
    )
    quote = models.ForeignKey(
        "quotes.Quote",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_documents",
    )
    sales_order = models.ForeignKey(
        "production.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_documents",
    )
    production_order = models.ForeignKey(
        "production.ProductionOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_documents",
    )
    purchase_order = models.ForeignKey(
        "purchasing.PurchaseOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_documents",
    )
    supplier = models.ForeignKey(
        "materials.MaterialSupplier",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_documents",
    )
    after_sales_case = models.ForeignKey(
        "after_sales.AfterSalesCase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_documents",
    )
    warranty = models.ForeignKey(
        "after_sales.WarrantyRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_documents",
    )
    effective_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    renewal_date = models.DateField(null=True, blank=True)
    requires_acceptance = models.BooleanField(default=False)
    requires_signature = models.BooleanField(default=False)
    confidentiality = models.CharField(
        max_length=20,
        choices=Confidentiality.choices,
        default=Confidentiality.INTERNAL,
    )
    current_version = models.ForeignKey(
        "DocumentVersion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_managed_documents",
    )
    responsible_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="responsible_managed_documents",
    )
    notes = models.TextField(blank=True)
    context_justification = models.CharField(max_length=255, blank=True)
    renewed_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="renewals",
    )
    cancel_reason = models.TextField(blank=True)
    terminate_reason = models.TextField(blank=True)
    terminated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["expiration_date"]),
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["supplier", "status"]),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    def clean(self):
        has_context = any(
            [
                self.customer_id,
                self.lead_id,
                self.quote_id,
                self.sales_order_id,
                self.production_order_id,
                self.purchase_order_id,
                self.supplier_id,
                self.after_sales_case_id,
                self.warranty_id,
                (self.context_justification or "").strip(),
            ],
        )
        if not has_context:
            raise ValidationError(
                "Informe um contexto (cliente, pedido, fornecedor etc.) ou justificativa.",
            )
        if self.expiration_date and self.effective_date:
            if self.expiration_date < self.effective_date:
                raise ValidationError({"expiration_date": "Vencimento anterior à vigência."})

    def delete(self, *args, **kwargs):
        if self.versions.exists():
            raise ValidationError("Documento com versões não pode ser apagado.")
        return super().delete(*args, **kwargs)


class DocumentVersion(TimeStampedModel):
    document = models.ForeignKey(
        ManagedDocument,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=VersionStatus.choices,
        default=VersionStatus.DRAFT,
    )
    content = models.TextField(blank=True)
    rendered_content = models.TextField(blank=True)
    media_asset = models.ForeignKey(
        "media_library.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="document_versions",
    )
    checksum = models.CharField(max_length=64, blank=True)
    change_summary = models.CharField(max_length=255, blank=True)
    missing_placeholders = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="document_versions_created",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="document_versions_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "version_number"],
                name="unique_document_version_number",
            ),
        ]

    IMMUTABLE_WHEN_APPROVED = (
        "content",
        "rendered_content",
        "media_asset_id",
        "checksum",
        "version_number",
    )

    def save(self, *args, **kwargs):
        if self.pk:
            previous = DocumentVersion.objects.filter(pk=self.pk).first()
            if previous and previous.status == VersionStatus.APPROVED:
                update_fields = kwargs.get("update_fields")
                status_transition_only = update_fields is not None and set(update_fields) <= {
                    "status",
                    "updated_at",
                }
                if not status_transition_only:
                    for field in self.IMMUTABLE_WHEN_APPROVED:
                        if getattr(previous, field) != getattr(self, field):
                            raise ValidationError("Versão aprovada é imutável.")
                if self.status not in {
                    VersionStatus.APPROVED,
                    VersionStatus.SUPERSEDED,
                    VersionStatus.ARCHIVED,
                }:
                    raise ValidationError("Status inválido para versão aprovada.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Versão de documento não pode ser apagada.")

    def __str__(self):
        return f"{self.document.number} v{self.version_number}"


class DocumentReview(TimeStampedModel):
    document_version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="document_reviews",
    )
    status = models.CharField(
        max_length=30,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    decision = models.CharField(max_length=40, blank=True)
    comments = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class DocumentApprovalStep(TimeStampedModel):
    document = models.ForeignKey(
        ManagedDocument,
        on_delete=models.CASCADE,
        related_name="approval_steps",
    )
    document_version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.CASCADE,
        related_name="approval_steps",
    )
    sequence = models.PositiveIntegerField(default=1)
    approver_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="document_approval_steps",
    )
    approver_role = models.ForeignKey(
        "access_control.AccessRole",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="document_approval_steps",
    )
    approver_name_snapshot = models.CharField(max_length=180, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ApprovalStepStatus.choices,
        default=ApprovalStepStatus.PENDING,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["sequence", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["document_version", "sequence"],
                name="unique_doc_approval_step_sequence",
            ),
        ]


class DocumentSendRecord(TimeStampedModel):
    document = models.ForeignKey(
        ManagedDocument,
        on_delete=models.CASCADE,
        related_name="send_records",
    )
    document_version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.CASCADE,
        related_name="send_records",
    )
    channel = models.CharField(max_length=20, choices=SendChannel.choices)
    recipient_name = models.CharField(max_length=180, blank=True)
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=40, blank=True)
    sent_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="document_sends_recorded",
    )


class DocumentViewRecord(TimeStampedModel):
    document = models.ForeignKey(
        ManagedDocument,
        on_delete=models.CASCADE,
        related_name="view_records",
    )
    document_version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.CASCADE,
        related_name="view_records",
    )
    viewed_at = models.DateTimeField()
    viewer_name = models.CharField(max_length=180, blank=True)
    channel = models.CharField(max_length=20, choices=SendChannel.choices, default=SendChannel.OTHER)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="document_views_recorded",
    )


class DocumentAcceptance(TimeStampedModel):
    document = models.ForeignKey(
        ManagedDocument,
        on_delete=models.CASCADE,
        related_name="acceptances",
    )
    document_version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.PROTECT,
        related_name="acceptances",
    )
    acceptance_type = models.CharField(
        max_length=40,
        choices=AcceptanceType.choices,
        default=AcceptanceType.CUSTOMER,
    )
    status = models.CharField(
        max_length=20,
        choices=AcceptanceStatus.choices,
        default=AcceptanceStatus.PENDING,
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    accepted_by_name = models.CharField(max_length=180, blank=True)
    accepted_by_document = models.CharField(max_length=40, blank=True)
    channel = models.CharField(max_length=20, choices=SendChannel.choices, default=SendChannel.OTHER)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="document_acceptances_recorded",
    )

    def delete(self, *args, **kwargs):
        raise ValidationError("Aceite documental não pode ser apagado.")


class DocumentSignatureRecord(TimeStampedModel):
    document = models.ForeignKey(
        ManagedDocument,
        on_delete=models.CASCADE,
        related_name="signatures",
    )
    document_version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.PROTECT,
        related_name="signatures",
    )
    signer_name = models.CharField(max_length=180)
    signer_document = models.CharField(max_length=40, blank=True)
    signer_role = models.CharField(max_length=120, blank=True)
    signature_type = models.CharField(
        max_length=40,
        choices=SignatureType.choices,
        default=SignatureType.MANUAL,
    )
    signed_at = models.DateTimeField()
    channel = models.CharField(max_length=20, choices=SendChannel.choices, default=SendChannel.OTHER)
    evidence_asset = models.ForeignKey(
        "media_library.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="document_signature_evidences",
    )
    external_provider = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="document_signatures_recorded",
    )


class DocumentAttachment(TimeStampedModel):
    document = models.ForeignKey(
        ManagedDocument,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    document_version = models.ForeignKey(
        DocumentVersion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attachments",
    )
    media_asset = models.ForeignKey(
        "media_library.MediaAsset",
        on_delete=models.PROTECT,
        related_name="document_attachments",
    )
    attachment_type = models.CharField(
        max_length=30,
        choices=AttachmentType.choices,
        default=AttachmentType.OTHER,
    )
    description = models.CharField(max_length=255, blank=True)
    is_required = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="document_attachments_created",
    )


class DocumentRelationship(TimeStampedModel):
    from_document = models.ForeignKey(
        ManagedDocument,
        on_delete=models.CASCADE,
        related_name="relationships_from",
    )
    to_document = models.ForeignKey(
        ManagedDocument,
        on_delete=models.CASCADE,
        related_name="relationships_to",
    )
    relationship_type = models.CharField(
        max_length=30,
        choices=RelationshipType.choices,
    )
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="document_relationships_created",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["from_document", "to_document", "relationship_type"],
                name="unique_document_relationship",
            ),
            models.CheckConstraint(
                condition=~Q(from_document=models.F("to_document")),
                name="document_relationship_not_self",
            ),
        ]
