# ruff: noqa: EM101, TRY003
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import AuditableModel
from core.models import SoftDeleteModel
from core.models import TimeStampedModel


class CaseType(models.TextChoices):
    POST_DELIVERY_FOLLOW_UP = "post_delivery_follow_up", "Acompanhamento pós-entrega"
    POST_INSTALLATION_FOLLOW_UP = "post_installation_follow_up", "Acompanhamento pós-instalação"
    INSTALLATION_PENDING = "installation_pending", "Pendência de instalação"
    CUSTOMER_COMPLAINT = "customer_complaint", "Reclamação"
    TECHNICAL_ASSISTANCE = "technical_assistance", "Assistência técnica"
    WARRANTY_REQUEST = "warranty_request", "Solicitação de garantia"
    DAMAGE_REPORT = "damage_report", "Avaria"
    MEASUREMENT_ISSUE = "measurement_issue", "Problema de medição"
    MATERIAL_ISSUE = "material_issue", "Problema de material"
    FINISH_ISSUE = "finish_issue", "Problema de acabamento"
    INSTALLATION_ISSUE = "installation_issue", "Problema de instalação"
    DELIVERY_ISSUE = "delivery_issue", "Problema de entrega"
    REWORK_REQUEST = "rework_request", "Solicitação de retrabalho"
    RETURN_VISIT = "return_visit", "Retorno técnico"
    OTHER = "other", "Outro"


class CaseStatus(models.TextChoices):
    NEW = "new", "Novo"
    TRIAGE = "triage", "Em triagem"
    ASSIGNED = "assigned", "Atribuído"
    AWAITING_CUSTOMER = "awaiting_customer", "Aguardando cliente"
    VISIT_SCHEDULED = "visit_scheduled", "Visita agendada"
    UNDER_ANALYSIS = "under_analysis", "Em análise"
    AWAITING_MATERIAL = "awaiting_material", "Aguardando material"
    IN_PROGRESS = "in_progress", "Em andamento"
    RESOLVED = "resolved", "Resolvido"
    CLOSED = "closed", "Fechado"
    REJECTED = "rejected", "Rejeitado"
    CANCELLED = "cancelled", "Cancelado"


class CasePriority(models.TextChoices):
    LOW = "low", "Baixa"
    NORMAL = "normal", "Normal"
    HIGH = "high", "Alta"
    URGENT = "urgent", "Urgente"


class CaseSeverity(models.TextChoices):
    COSMETIC = "cosmetic", "Cosmético"
    MINOR = "minor", "Leve"
    MODERATE = "moderate", "Moderado"
    MAJOR = "major", "Grave"
    CRITICAL = "critical", "Crítico"


class RootCause(models.TextChoices):
    INSTALLATION_ERROR = "installation_error", "Erro de instalação"
    MEASUREMENT_ERROR = "measurement_error", "Erro de medição"
    MATERIAL_DEFECT = "material_defect", "Defeito de material"
    MANUFACTURING_ERROR = "manufacturing_error", "Erro de fabricação"
    TRANSPORT_DAMAGE = "transport_damage", "Avaria no transporte"
    CUSTOMER_MISUSE = "customer_misuse", "Uso inadequado pelo cliente"
    STRUCTURAL_ISSUE = "structural_issue", "Problema estrutural"
    SUPPLIER_ISSUE = "supplier_issue", "Problema de fornecedor"
    NATURAL_VARIATION = "natural_variation", "Variação natural"
    MAINTENANCE_NEEDED = "maintenance_needed", "Necessita manutenção"
    NOT_IDENTIFIED = "not_identified", "Não identificado"
    OTHER = "other", "Outro"


class Responsibility(models.TextChoices):
    COMPANY = "company", "Empresa"
    CUSTOMER = "customer", "Cliente"
    SUPPLIER = "supplier", "Fornecedor"
    SHARED = "shared", "Compartilhada"
    UNDETERMINED = "undetermined", "Indeterminada"


class WarrantyEligibility(models.TextChoices):
    ELIGIBLE = "eligible", "Elegível"
    NOT_ELIGIBLE = "not_eligible", "Não elegível"
    MANUAL_REVIEW = "manual_review", "Análise manual"


class WarrantyStatus(models.TextChoices):
    ACTIVE = "active", "Ativa"
    EXPIRED = "expired", "Expirada"
    SUSPENDED = "suspended", "Suspensa"
    CANCELLED = "cancelled", "Cancelada"


class CoverageType(models.TextChoices):
    MATERIAL = "material", "Material"
    WORKMANSHIP = "workmanship", "Mão de obra"
    INSTALLATION = "installation", "Instalação"
    SEALANT = "sealant", "Vedação"
    ACCESSORY = "accessory", "Acessório"
    CUSTOM = "custom", "Personalizada"


class WarrantyStartsFrom(models.TextChoices):
    DELIVERY = "delivery", "Entrega"
    INSTALLATION = "installation", "Instalação"
    ORDER_COMPLETION = "order_completion", "Conclusão do pedido"
    MANUAL = "manual", "Manual"


class HistoryAction(models.TextChoices):
    CREATED = "created", "Criado"
    TRIAGED = "triaged", "Triado"
    ASSIGNED = "assigned", "Atribuído"
    STATUS_CHANGED = "status_changed", "Status alterado"
    VISIT_SCHEDULED = "visit_scheduled", "Visita agendada"
    DIAGNOSIS_ADDED = "diagnosis_added", "Diagnóstico registrado"
    WARRANTY_EVALUATED = "warranty_evaluated", "Garantia avaliada"
    MATERIAL_REQUESTED = "material_requested", "Material solicitado"
    WORK_STARTED = "work_started", "Atendimento iniciado"
    RESOLVED = "resolved", "Resolvido"
    CLOSED = "closed", "Fechado"
    REOPENED = "reopened", "Reaberto"
    REJECTED = "rejected", "Rejeitado"
    CANCELLED = "cancelled", "Cancelado"
    CUSTOMER_CONTACTED = "customer_contacted", "Cliente contatado"


class InteractionType(models.TextChoices):
    NOTE = "note", "Observação"
    PHONE = "phone", "Telefone"
    WHATSAPP = "whatsapp", "WhatsApp"
    EMAIL = "email", "E-mail"
    MEETING = "meeting", "Reunião"
    TECHNICAL_VISIT = "technical_visit", "Visita técnica"
    CUSTOMER_FEEDBACK = "customer_feedback", "Feedback do cliente"
    RESOLUTION_UPDATE = "resolution_update", "Atualização de resolução"
    OTHER = "other", "Outro"


class AttachmentType(models.TextChoices):
    PHOTO = "photo", "Foto"
    VIDEO = "video", "Vídeo"
    DOCUMENT = "document", "Documento"
    INVOICE = "invoice", "Nota / fatura"
    TECHNICAL_REPORT = "technical_report", "Laudo técnico"
    CUSTOMER_MESSAGE = "customer_message", "Mensagem do cliente"
    BEFORE = "before", "Antes"
    AFTER = "after", "Depois"
    OTHER = "other", "Outro"


class PendingStatus(models.TextChoices):
    OPEN = "open", "Aberta"
    SCHEDULED = "scheduled", "Agendada"
    IN_PROGRESS = "in_progress", "Em andamento"
    RESOLVED = "resolved", "Resolvida"
    CANCELLED = "cancelled", "Cancelada"


class SurveyType(models.TextChoices):
    POST_DELIVERY = "post_delivery", "Pós-entrega"
    POST_INSTALLATION = "post_installation", "Pós-instalação"
    AFTER_ASSISTANCE = "after_assistance", "Pós-assistência"
    GENERAL = "general", "Geral"


class SurveyStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    SENT_MANUALLY = "sent_manually", "Solicitada manualmente"
    RESPONDED = "responded", "Respondida"
    DECLINED = "declined", "Recusada"
    CANCELLED = "cancelled", "Cancelada"


class ReviewRequestStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    REQUESTED = "requested", "Solicitada"
    COMPLETED = "completed", "Concluída"
    DECLINED = "declined", "Recusada"
    CANCELLED = "cancelled", "Cancelada"


class ConsentStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    GRANTED = "granted", "Concedida"
    DENIED = "denied", "Negada"
    REVOKED = "revoked", "Revogada"


class ConsentScope(models.TextChoices):
    WEBSITE = "website", "Site"
    SOCIAL_MEDIA = "social_media", "Redes sociais"
    PORTFOLIO = "portfolio", "Portfólio"
    ADVERTISING = "advertising", "Publicidade"
    INTERNAL = "internal", "Uso interno"
    ALL = "all", "Todos"
    CUSTOM = "custom", "Personalizado"


class ReferralStatus(models.TextChoices):
    REGISTERED = "registered", "Registrada"
    CONTACTED = "contacted", "Contatada"
    CONVERTED = "converted", "Convertida"
    DECLINED = "declined", "Recusada"
    INVALID = "invalid", "Inválida"


class ReworkOrigin(models.TextChoices):
    PRODUCTION_INTERNAL = "production_internal", "Produção interna"
    AFTER_SALES = "after_sales", "Pós-venda"
    QUALITY_REJECTION = "quality_rejection", "Reprovação de qualidade"


TECHNICAL_CASE_TYPES = {
    CaseType.TECHNICAL_ASSISTANCE,
    CaseType.WARRANTY_REQUEST,
    CaseType.DAMAGE_REPORT,
    CaseType.MEASUREMENT_ISSUE,
    CaseType.MATERIAL_ISSUE,
    CaseType.FINISH_ISSUE,
    CaseType.INSTALLATION_ISSUE,
    CaseType.DELIVERY_ISSUE,
    CaseType.REWORK_REQUEST,
    CaseType.RETURN_VISIT,
    CaseType.INSTALLATION_PENDING,
}

OPEN_CASE_STATUSES = {
    CaseStatus.NEW,
    CaseStatus.TRIAGE,
    CaseStatus.ASSIGNED,
    CaseStatus.AWAITING_CUSTOMER,
    CaseStatus.VISIT_SCHEDULED,
    CaseStatus.UNDER_ANALYSIS,
    CaseStatus.AWAITING_MATERIAL,
    CaseStatus.IN_PROGRESS,
    CaseStatus.RESOLVED,
}


class AfterSalesCaseSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)


class WarrantySequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)


class WarrantyPolicy(TimeStampedModel, AuditableModel, SoftDeleteModel):
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    coverage_type = models.CharField(max_length=30, choices=CoverageType.choices)
    duration_days = models.PositiveIntegerField(null=True, blank=True)
    starts_from = models.CharField(
        max_length=30,
        choices=WarrantyStartsFrom.choices,
        default=WarrantyStartsFrom.MANUAL,
    )
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    terms = models.TextField(blank=True)
    exclusions = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class WarrantyRecord(TimeStampedModel, AuditableModel):
    number = models.CharField(max_length=40, unique=True, blank=True)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="warranties",
    )
    sales_order = models.ForeignKey(
        "production.SalesOrder",
        on_delete=models.PROTECT,
        related_name="warranties",
    )
    installation_schedule = models.ForeignKey(
        "production.InstallationSchedule",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="warranties",
    )
    policy = models.ForeignKey(
        WarrantyPolicy,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="warranties",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=WarrantyStatus.choices,
        default=WarrantyStatus.ACTIVE,
    )
    coverage_type = models.CharField(max_length=30, choices=CoverageType.choices)
    coverage_description = models.TextField(blank=True)
    exclusions = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return self.number or f"Garantia {self.pk}"

    def is_within_period(self, at_date=None):
        at_date = at_date or timezone.localdate()
        if self.status != WarrantyStatus.ACTIVE:
            return False
        if at_date < self.start_date:
            return False
        if self.end_date and at_date > self.end_date:
            return False
        return True


class AfterSalesCase(TimeStampedModel, AuditableModel):
    code = models.CharField(max_length=30, unique=True, blank=True)
    case_type = models.CharField(max_length=40, choices=CaseType.choices)
    status = models.CharField(
        max_length=30,
        choices=CaseStatus.choices,
        default=CaseStatus.NEW,
    )
    priority = models.CharField(
        max_length=20,
        choices=CasePriority.choices,
        default=CasePriority.NORMAL,
    )
    severity = models.CharField(
        max_length=20,
        choices=CaseSeverity.choices,
        default=CaseSeverity.MINOR,
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="after_sales_cases",
    )
    sales_order = models.ForeignKey(
        "production.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="after_sales_cases",
    )
    delivery_schedule = models.ForeignKey(
        "production.DeliverySchedule",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="after_sales_cases",
    )
    installation_schedule = models.ForeignKey(
        "production.InstallationSchedule",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="after_sales_cases",
    )
    production_order = models.ForeignKey(
        "production.ProductionOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="after_sales_cases",
    )
    rework_production_order = models.ForeignKey(
        "production.ProductionOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="after_sales_rework_cases",
    )
    rework_origin = models.CharField(
        max_length=30,
        choices=ReworkOrigin.choices,
        blank=True,
    )
    estimated_rework_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    reported_at = models.DateTimeField(null=True, blank=True)
    reported_by_name = models.CharField(max_length=160, blank=True)
    reported_by_phone = models.CharField(max_length=40, blank=True)
    reported_channel = models.CharField(max_length=40, blank=True)
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="after_sales_cases_assigned",
    )
    assigned_salesperson = models.ForeignKey(
        "salespeople.Salesperson",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="after_sales_cases",
    )
    subject = models.CharField(max_length=220)
    description = models.TextField()
    technical_diagnosis = models.TextField(blank=True)
    resolution = models.TextField(blank=True)
    root_cause = models.CharField(max_length=40, choices=RootCause.choices, blank=True)
    root_cause_notes = models.TextField(blank=True)
    responsibility = models.CharField(
        max_length=30,
        choices=Responsibility.choices,
        blank=True,
    )
    responsibility_notes = models.TextField(blank=True)
    warranty = models.ForeignKey(
        WarrantyRecord,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cases",
    )
    warranty_eligible = models.CharField(
        max_length=20,
        choices=WarrantyEligibility.choices,
        blank=True,
    )
    warranty_decision_notes = models.TextField(blank=True)
    customer_notified = models.BooleanField(default=False)
    next_action_at = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    reject_reason = models.TextField(blank=True)
    cancel_reason = models.TextField(blank=True)
    closing_notes = models.TextField(blank=True)
    material_request_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-opened_at"]
        indexes = [
            models.Index(fields=["status", "opened_at"]),
            models.Index(fields=["case_type", "status"]),
            models.Index(fields=["assigned_user", "status"]),
            models.Index(fields=["priority", "severity"]),
        ]

    def __str__(self):
        return f"{self.code} — {self.subject}"

    def delete(self, *args, **kwargs):
        raise ValidationError("Casos de pós-venda não podem ser excluídos.")


class AfterSalesCaseHistory(models.Model):
    case = models.ForeignKey(
        AfterSalesCase,
        on_delete=models.CASCADE,
        related_name="history",
    )
    action = models.CharField(max_length=40, choices=HistoryAction.choices)
    old_status = models.CharField(max_length=30, blank=True)
    new_status = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="after_sales_history",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.pk and AfterSalesCaseHistory.objects.filter(pk=self.pk).exists():
            raise ValueError("Histórico de pós-venda é imutável.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Histórico de pós-venda não pode ser excluído.")


class AfterSalesInteraction(models.Model):
    case = models.ForeignKey(
        AfterSalesCase,
        on_delete=models.CASCADE,
        related_name="interactions",
    )
    interaction_type = models.CharField(max_length=30, choices=InteractionType.choices)
    contact_channel = models.CharField(max_length=40, blank=True)
    description = models.TextField()
    occurred_at = models.DateTimeField(default=timezone.now)
    next_action_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="after_sales_interactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]


def after_sales_attachment_path(instance, filename):
    return f"after_sales/{instance.case_id}/{filename}"


class AfterSalesAttachment(models.Model):
    case = models.ForeignKey(
        AfterSalesCase,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to=after_sales_attachment_path, blank=True)
    media_asset = models.ForeignKey(
        "media_library.MediaAsset",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="after_sales_attachments",
    )
    attachment_type = models.CharField(
        max_length=30,
        choices=AttachmentType.choices,
        default=AttachmentType.OTHER,
    )
    description = models.CharField(max_length=220, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="after_sales_attachments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class InstallationPendingItem(TimeStampedModel, AuditableModel):
    installation_schedule = models.ForeignKey(
        "production.InstallationSchedule",
        on_delete=models.CASCADE,
        related_name="pending_items",
    )
    sales_order = models.ForeignKey(
        "production.SalesOrder",
        on_delete=models.CASCADE,
        related_name="installation_pending_items",
    )
    description = models.TextField()
    priority = models.CharField(
        max_length=20,
        choices=CasePriority.choices,
        default=CasePriority.NORMAL,
    )
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="installation_pending_items",
    )
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=PendingStatus.choices,
        default=PendingStatus.OPEN,
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_installation_pending_items",
    )
    resolution = models.TextField(blank=True)
    after_sales_case = models.ForeignKey(
        AfterSalesCase,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pending_items",
    )

    class Meta:
        ordering = ["due_date", "-created_at"]


class CustomerSatisfactionSurvey(TimeStampedModel, AuditableModel):
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="satisfaction_surveys",
    )
    sales_order = models.ForeignKey(
        "production.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="satisfaction_surveys",
    )
    after_sales_case = models.ForeignKey(
        AfterSalesCase,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="satisfaction_surveys",
    )
    survey_type = models.CharField(max_length=30, choices=SurveyType.choices)
    status = models.CharField(
        max_length=20,
        choices=SurveyStatus.choices,
        default=SurveyStatus.PENDING,
    )
    requested_at = models.DateTimeField(default=timezone.now)
    responded_at = models.DateTimeField(null=True, blank=True)
    overall_score = models.PositiveSmallIntegerField(null=True, blank=True)
    service_score = models.PositiveSmallIntegerField(null=True, blank=True)
    quality_score = models.PositiveSmallIntegerField(null=True, blank=True)
    delivery_score = models.PositiveSmallIntegerField(null=True, blank=True)
    installation_score = models.PositiveSmallIntegerField(null=True, blank=True)
    comments = models.TextField(blank=True)
    would_recommend = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]

    def clean(self):
        for field in [
            "overall_score",
            "service_score",
            "quality_score",
            "delivery_score",
            "installation_score",
        ]:
            value = getattr(self, field)
            if value is not None and (value < 1 or value > 5):
                raise ValidationError({field: "Nota deve estar entre 1 e 5."})
        if not self.sales_order_id and not self.after_sales_case_id:
            raise ValidationError("Pesquisa deve vincular pedido ou caso.")


class ReviewRequest(TimeStampedModel, AuditableModel):
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="review_requests",
    )
    sales_order = models.ForeignKey(
        "production.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="review_requests",
    )
    requested_at = models.DateTimeField(default=timezone.now)
    channel = models.CharField(max_length=40, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ReviewRequestStatus.choices,
        default=ReviewRequestStatus.PENDING,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]


class MediaUsageConsent(TimeStampedModel, AuditableModel):
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="media_consents",
    )
    sales_order = models.ForeignKey(
        "production.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_consents",
    )
    consent_status = models.CharField(
        max_length=20,
        choices=ConsentStatus.choices,
        default=ConsentStatus.PENDING,
    )
    consent_scope = models.CharField(
        max_length=30,
        choices=ConsentScope.choices,
        default=ConsentScope.INTERNAL,
    )
    authorized_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    authorized_by_name = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="media_consents_recorded",
    )

    class Meta:
        ordering = ["-created_at"]


class CustomerReferral(TimeStampedModel, AuditableModel):
    referring_customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="referrals_made",
    )
    sales_order = models.ForeignKey(
        "production.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referrals",
    )
    referred_name = models.CharField(max_length=180)
    referred_phone = models.CharField(max_length=40, blank=True)
    referred_email = models.EmailField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=ReferralStatus.choices,
        default=ReferralStatus.REGISTERED,
    )
    notes = models.TextField(blank=True)
    converted_lead = models.ForeignKey(
        "commercial.Lead",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_referrals",
    )

    class Meta:
        ordering = ["-created_at"]
