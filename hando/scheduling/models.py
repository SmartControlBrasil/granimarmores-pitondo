# ruff: noqa: EM101, TRY003
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import AuditableModel
from core.models import TimeStampedModel


class EventType(models.TextChoices):
    COMMERCIAL_FOLLOW_UP = "commercial_follow_up", "Follow-up comercial"
    CUSTOMER_MEETING = "customer_meeting", "Reunião com cliente"
    TECHNICAL_VISIT = "technical_visit", "Visita técnica"
    MEASUREMENT = "measurement", "Medição"
    QUOTE_PRESENTATION = "quote_presentation", "Apresentação de orçamento"
    PRODUCTION_TASK = "production_task", "Tarefa de produção"
    MATERIAL_PICKUP = "material_pickup", "Retirada de material"
    DELIVERY = "delivery", "Entrega"
    INSTALLATION = "installation", "Instalação"
    QUALITY_RETURN = "quality_return", "Retorno de qualidade"
    TECHNICAL_ASSISTANCE = "technical_assistance", "Assistência técnica"
    REWORK_VISIT = "rework_visit", "Visita de retrabalho"
    INTERNAL_MEETING = "internal_meeting", "Reunião interna"
    OTHER = "other", "Outro"


class EventStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    SCHEDULED = "scheduled", "Agendado"
    CONFIRMED = "confirmed", "Confirmado"
    IN_PROGRESS = "in_progress", "Em andamento"
    COMPLETED = "completed", "Concluído"
    CANCELLED = "cancelled", "Cancelado"
    RESCHEDULED = "rescheduled", "Reagendado"
    NO_SHOW = "no_show", "Não comparecimento"
    BLOCKED = "blocked", "Bloqueado"


class EventPriority(models.TextChoices):
    LOW = "low", "Baixa"
    NORMAL = "normal", "Normal"
    HIGH = "high", "Alta"
    URGENT = "urgent", "Urgente"


class ConfirmationStatus(models.TextChoices):
    PENDING = "pending", "Não confirmado"
    CONFIRMED = "confirmed", "Confirmado"
    ATTEMPTED = "attempted", "Tentativa registrada"
    DECLINED = "declined", "Recusado"


class ConfirmationChannel(models.TextChoices):
    PHONE = "phone", "Telefone"
    WHATSAPP = "whatsapp", "WhatsApp"
    EMAIL = "email", "E-mail"
    IN_PERSON = "in_person", "Presencial"
    OTHER = "other", "Outro"


class HistoryAction(models.TextChoices):
    CREATED = "created", "Criado"
    SCHEDULED = "scheduled", "Agendado"
    CONFIRMED = "confirmed", "Confirmado"
    STARTED = "started", "Iniciado"
    COMPLETED = "completed", "Concluído"
    CANCELLED = "cancelled", "Cancelado"
    RESCHEDULED = "rescheduled", "Reagendado"
    BLOCKED = "blocked", "Bloqueado"
    UNBLOCKED = "unblocked", "Desbloqueado"
    ASSIGNMENT_CHANGED = "assignment_changed", "Responsável alterado"
    VEHICLE_CHANGED = "vehicle_changed", "Veículo alterado"
    CONFLICT_OVERRIDDEN = "conflict_overridden", "Conflito sobrescrito"
    NO_SHOW = "no_show", "Não comparecimento"
    CONFIRMATION_ATTEMPTED = "confirmation_attempted", "Tentativa de confirmação"


class MeasurementType(models.TextChoices):
    INITIAL = "initial", "Inicial"
    FINAL = "final", "Final"
    CONFIRMATION = "confirmation", "Confirmação"
    REWORK = "rework", "Retrabalho"


OPERATIONAL_EVENT_TYPES = {
    EventType.TECHNICAL_VISIT,
    EventType.MEASUREMENT,
    EventType.DELIVERY,
    EventType.INSTALLATION,
    EventType.QUALITY_RETURN,
    EventType.TECHNICAL_ASSISTANCE,
    EventType.REWORK_VISIT,
    EventType.MATERIAL_PICKUP,
    EventType.PRODUCTION_TASK,
}

ADDRESS_REQUIRED_TYPES = {
    EventType.TECHNICAL_VISIT,
    EventType.MEASUREMENT,
    EventType.DELIVERY,
    EventType.INSTALLATION,
    EventType.QUALITY_RETURN,
    EventType.TECHNICAL_ASSISTANCE,
    EventType.REWORK_VISIT,
}

ACTIVE_CONFLICT_STATUSES = {
    EventStatus.DRAFT,
    EventStatus.SCHEDULED,
    EventStatus.CONFIRMED,
    EventStatus.IN_PROGRESS,
    EventStatus.RESCHEDULED,
    EventStatus.BLOCKED,
}


class OperationalEventSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "sequência de eventos"
        verbose_name_plural = "sequências de eventos"


class OperationalEvent(TimeStampedModel, AuditableModel):
    code = models.CharField(max_length=30, unique=True, blank=True)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
        default=EventStatus.SCHEDULED,
    )
    priority = models.CharField(
        max_length=20,
        choices=EventPriority.choices,
        default=EventPriority.NORMAL,
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)
    all_day = models.BooleanField(default=False)
    timezone = models.CharField(max_length=64, default="America/Sao_Paulo")

    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="operational_events_assigned",
    )
    assigned_salesperson = models.ForeignKey(
        "salespeople.Salesperson",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="operational_events",
    )
    external_responsible = models.CharField(max_length=160, blank=True)

    customer = models.ForeignKey(
        "customers.Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operational_events",
    )
    lead = models.ForeignKey(
        "commercial.Lead",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operational_events",
    )
    quote = models.ForeignKey(
        "quotes.Quote",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operational_events",
    )
    sales_order = models.ForeignKey(
        "production.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operational_events",
    )
    production_order = models.ForeignKey(
        "production.ProductionOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operational_events",
    )
    production_piece = models.ForeignKey(
        "production.ProductionPiece",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operational_events",
    )
    delivery_schedule = models.OneToOneField(
        "production.DeliverySchedule",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operational_event",
    )
    installation_schedule = models.OneToOneField(
        "production.InstallationSchedule",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operational_event",
    )
    vehicle = models.ForeignKey(
        "fleet.Vehicle",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operational_events",
    )

    address = models.CharField(max_length=255, blank=True)
    district = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=2, blank=True)
    postal_code = models.CharField(max_length=12, blank=True)
    contact_name = models.CharField(max_length=160, blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)

    confirmation_status = models.CharField(
        max_length=20,
        choices=ConfirmationStatus.choices,
        default=ConfirmationStatus.PENDING,
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operational_events_confirmed",
    )
    confirmation_channel = models.CharField(
        max_length=20,
        choices=ConfirmationChannel.choices,
        blank=True,
    )
    confirmation_notes = models.TextField(blank=True)

    internal_notes = models.TextField(blank=True)
    completion_notes = models.TextField(blank=True)
    cancel_reason = models.TextField(blank=True)
    block_reason = models.TextField(blank=True)
    conflict_override_reason = models.TextField(blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["start_at", "code"]
        indexes = [
            models.Index(fields=["start_at", "end_at"]),
            models.Index(fields=["status", "start_at"]),
            models.Index(fields=["event_type", "start_at"]),
            models.Index(fields=["assigned_user", "start_at"]),
            models.Index(fields=["assigned_salesperson", "start_at"]),
            models.Index(fields=["city", "start_at"]),
        ]

    def __str__(self):
        return f"{self.code} — {self.title}"

    def clean(self):
        if not self.start_at:
            raise ValidationError({"start_at": "Início obrigatório."})
        if self.all_day:
            if self.end_at and self.end_at.date() < self.start_at.date():
                raise ValidationError({"end_at": "Fim não pode ser anterior ao início."})
        else:
            if not self.end_at:
                raise ValidationError({"end_at": "Fim obrigatório para eventos com horário."})
            if self.end_at < self.start_at:
                raise ValidationError({"end_at": "Fim não pode ser anterior ao início."})
        if timezone.is_naive(self.start_at):
            raise ValidationError({"start_at": "Datetime deve ser timezone-aware."})
        if self.end_at and timezone.is_naive(self.end_at):
            raise ValidationError({"end_at": "Datetime deve ser timezone-aware."})

    @property
    def is_active_for_conflict(self):
        return self.status in ACTIVE_CONFLICT_STATUSES

    @property
    def is_overdue(self):
        if self.status in {
            EventStatus.COMPLETED,
            EventStatus.CANCELLED,
            EventStatus.NO_SHOW,
        }:
            return False
        end = self.end_at or self.start_at
        return end < timezone.now()


class OperationalEventHistory(models.Model):
    event = models.ForeignKey(
        OperationalEvent,
        on_delete=models.CASCADE,
        related_name="history",
    )
    action = models.CharField(max_length=40, choices=HistoryAction.choices)
    old_start_at = models.DateTimeField(null=True, blank=True)
    old_end_at = models.DateTimeField(null=True, blank=True)
    new_start_at = models.DateTimeField(null=True, blank=True)
    new_end_at = models.DateTimeField(null=True, blank=True)
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operational_event_history",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.pk and OperationalEventHistory.objects.filter(pk=self.pk).exists():
            raise ValueError("Histórico operacional é imutável.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Histórico operacional não pode ser excluído.")


class MeasurementAppointment(TimeStampedModel, AuditableModel):
    event = models.OneToOneField(
        OperationalEvent,
        on_delete=models.CASCADE,
        related_name="measurement",
    )
    measurement_type = models.CharField(
        max_length=20,
        choices=MeasurementType.choices,
        default=MeasurementType.INITIAL,
    )
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="measurement_appointments",
    )
    required_documents = models.TextField(blank=True)
    customer_confirmed = models.BooleanField(default=False)
    measurement_completed = models.BooleanField(default=False)
    measurement_notes = models.TextField(blank=True)
    textual_measurements = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Medição {self.event.code}"
