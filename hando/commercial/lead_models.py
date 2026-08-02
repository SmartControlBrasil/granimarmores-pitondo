# ruff: noqa: EM101, TRY003
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import AuditableModel
from core.models import TimeStampedModel
from materials.models import validate_non_negative


class LeadSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    current = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Sequência leads {self.year}: {self.current}"


class LeadStatus(models.TextChoices):
    NEW = "new", "Novo"
    TRIAGE = "triage", "Triagem"
    ASSIGNED = "assigned", "Atribuído"
    CONTACTED = "contacted", "Contato realizado"
    QUALIFIED = "qualified", "Qualificado"
    MEASUREMENT_SCHEDULED = "measurement_scheduled", "Medição agendada"
    MEASUREMENT_COMPLETED = "measurement_completed", "Medição concluída"
    QUOTE_PREPARATION = "quote_preparation", "Preparação de orçamento"
    QUOTE_SENT = "quote_sent", "Orçamento enviado"
    NEGOTIATION = "negotiation", "Negociação"
    WON = "won", "Ganho"
    LOST = "lost", "Perdido"
    DISQUALIFIED = "disqualified", "Desqualificado"


class LeadPriority(models.TextChoices):
    LOW = "low", "Baixa"
    NORMAL = "normal", "Normal"
    HIGH = "high", "Alta"
    URGENT = "urgent", "Urgente"


class LeadActivityType(models.TextChoices):
    NOTE = "note", "Observação"
    CALL = "call", "Ligação"
    WHATSAPP = "whatsapp", "WhatsApp"
    EMAIL = "email", "E-mail"
    MEETING = "meeting", "Reunião"
    SITE_VISIT = "site_visit", "Visita"
    MEASUREMENT = "measurement", "Medição"
    PROPOSAL = "proposal", "Proposta"
    FOLLOW_UP = "follow_up", "Follow-up"
    STATUS_CHANGE = "status_change", "Mudança de status"
    ASSIGNMENT = "assignment", "Atribuição"
    CONVERSION = "conversion", "Conversão"
    LOSS = "loss", "Perda"
    REOPENING = "reopening", "Reabertura"
    OTHER = "other", "Outro"


class LeadTaskStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    IN_PROGRESS = "in_progress", "Em andamento"
    COMPLETED = "completed", "Concluída"
    CANCELLED = "cancelled", "Cancelada"


TERMINAL_STATUSES = {
    LeadStatus.WON,
    LeadStatus.LOST,
    LeadStatus.DISQUALIFIED,
}

LOSS_STATUSES = {LeadStatus.LOST, LeadStatus.DISQUALIFIED}


class Lead(TimeStampedModel, AuditableModel):
    code = models.CharField(max_length=20, unique=True, blank=True)
    name = models.CharField(max_length=180)
    company_name = models.CharField(max_length=180, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    whatsapp = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=2, blank=True)
    district = models.CharField(max_length=120, blank=True)
    project_description = models.TextField(blank=True)
    estimated_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    commercial_source = models.ForeignKey(
        "commercial.CommercialSource",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads",
    )
    contact_channel = models.ForeignKey(
        "commercial.ContactChannel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads",
    )
    project_type = models.ForeignKey(
        "commercial.ProjectType",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads",
    )
    partner = models.ForeignKey(
        "commercial.CommercialPartner",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads",
    )
    service_region = models.ForeignKey(
        "commercial.ServiceRegion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads",
    )
    assigned_salesperson = models.ForeignKey(
        "salespeople.Salesperson",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads",
    )
    status = models.CharField(
        max_length=40,
        choices=LeadStatus.choices,
        default=LeadStatus.NEW,
    )
    priority = models.CharField(
        max_length=20,
        choices=LeadPriority.choices,
        default=LeadPriority.NORMAL,
    )
    probability = models.PositiveSmallIntegerField(default=10)
    first_contact_at = models.DateTimeField(null=True, blank=True)
    last_contact_at = models.DateTimeField(null=True, blank=True)
    next_follow_up_at = models.DateTimeField(null=True, blank=True)
    won_at = models.DateTimeField(null=True, blank=True)
    lost_at = models.DateTimeField(null=True, blank=True)
    loss_reason = models.ForeignKey(
        "commercial.LossReason",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads",
    )
    loss_notes = models.TextField(blank=True)
    converted_customer = models.ForeignKey(
        "customers.Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_leads",
    )
    external_source = models.CharField(max_length=80, blank=True)
    external_id = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "lead"
        verbose_name_plural = "leads"
        indexes = [
            models.Index(fields=["status"], name="commercial_lead_status_idx"),
            models.Index(fields=["assigned_salesperson"], name="commercial_lead_sales_idx"),
            models.Index(fields=["commercial_source"], name="commercial_lead_source_idx"),
            models.Index(fields=["priority"], name="commercial_lead_priority_idx"),
            models.Index(fields=["next_follow_up_at"], name="commercial_lead_follow_idx"),
            models.Index(fields=["created_at"], name="commercial_lead_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(probability__gte=0, probability__lte=100),
                name="commercial_lead_probability_range",
            ),
            models.UniqueConstraint(
                fields=["external_source", "external_id"],
                condition=models.Q(external_source__gt="", external_id__gt=""),
                name="commercial_lead_external_unique",
            ),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        if not any([self.phone.strip(), self.whatsapp.strip(), self.email.strip()]):
            raise ValidationError(
                "Informe pelo menos um contato: telefone, WhatsApp ou e-mail.",
            )
        if self.status == LeadStatus.WON and not self.won_at:
            raise ValidationError("Lead ganho deve possuir data de ganho.")
        if self.status in LOSS_STATUSES and not self.lost_at:
            raise ValidationError("Lead perdido/desqualificado deve possuir data de perda.")
        if self.status == LeadStatus.WON and self.lost_at:
            raise ValidationError("Lead ganho não pode possuir data de perda.")
        if self.status in LOSS_STATUSES and self.won_at:
            raise ValidationError("Lead perdido não pode possuir data de ganho.")


class LeadActivity(models.Model):
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    activity_type = models.CharField(max_length=30, choices=LeadActivityType.choices)
    title = models.CharField(max_length=180)
    description = models.TextField()
    contact_channel = models.ForeignKey(
        "commercial.ContactChannel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_activities",
    )
    occurred_at = models.DateTimeField()
    next_action_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lead_activities_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-created_at"]
        verbose_name = "atividade do lead"
        verbose_name_plural = "atividades do lead"

    def __str__(self):
        return f"{self.lead.code} - {self.title}"


class LeadTask(TimeStampedModel):
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lead_tasks_assigned",
    )
    due_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=LeadTaskStatus.choices,
        default=LeadTaskStatus.PENDING,
    )
    priority = models.CharField(
        max_length=20,
        choices=LeadPriority.choices,
        default=LeadPriority.NORMAL,
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_tasks_completed",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_tasks_cancelled",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lead_tasks_created",
    )

    class Meta:
        ordering = ["due_at"]
        verbose_name = "tarefa do lead"
        verbose_name_plural = "tarefas do lead"
        indexes = [
            models.Index(fields=["status", "due_at"], name="commercial_leadtask_due_idx"),
        ]

    def __str__(self):
        return f"{self.lead.code} - {self.title}"

    @property
    def is_overdue(self):
        from django.utils import timezone

        if self.status in {LeadTaskStatus.COMPLETED, LeadTaskStatus.CANCELLED}:
            return False
        return self.due_at < timezone.now()
