from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import AuditableModel
from core.models import TimeStampedModel


class MaintenanceType(models.TextChoices):
    PREVENTIVE = "preventive", "Preventiva"
    PREDICTIVE = "predictive", "Preditiva"
    INSPECTION = "inspection", "Inspeção"
    LEGAL = "legal", "Legal"
    CALIBRATION = "calibration", "Calibração"
    CLEANING = "cleaning", "Limpeza"
    LUBRICATION = "lubrication", "Lubrificação"


class UsageUnit(models.TextChoices):
    KM = "km", "Km"
    HOURS = "hours", "Horas"
    CYCLES = "cycles", "Ciclos"
    DAYS = "days", "Dias"
    MONTHS = "months", "Meses"


class MaintenanceTargetMixin(models.Model):
    asset = models.ForeignKey(
        "assets.Asset", null=True, blank=True, on_delete=models.CASCADE,
    )
    vehicle = models.ForeignKey(
        "fleet.Vehicle", null=True, blank=True, on_delete=models.CASCADE,
    )

    class Meta:
        abstract = True

    def clean_target(self):
        if bool(self.asset_id) == bool(self.vehicle_id):
            raise ValidationError("Informe exatamente um ativo ou um veículo.")


class MaintenancePlan(TimeStampedModel, AuditableModel, MaintenanceTargetMixin):
    name = models.CharField(max_length=160)
    maintenance_type = models.CharField(max_length=20, choices=MaintenanceType.choices)
    interval_days = models.PositiveIntegerField(null=True, blank=True)
    interval_usage = models.PositiveIntegerField(null=True, blank=True)
    usage_unit = models.CharField(max_length=20, choices=UsageUnit.choices, blank=True)
    last_performed_date = models.DateField(null=True, blank=True)
    last_performed_usage = models.PositiveIntegerField(null=True, blank=True)
    next_due_date = models.DateField(null=True, blank=True)
    next_due_usage = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["next_due_date", "name"]
        verbose_name = "plano de manutenção"
        verbose_name_plural = "planos de manutenção"

    def __str__(self):
        return self.name

    def clean(self):
        self.clean_target()


class MaintenanceOrder(TimeStampedModel, AuditableModel, MaintenanceTargetMixin):
    class Status(models.TextChoices):
        OPEN = "open", "Aberta"
        SCHEDULED = "scheduled", "Agendada"
        IN_PROGRESS = "in_progress", "Em andamento"
        WAITING_PARTS = "waiting_parts", "Aguardando peças"
        COMPLETED = "completed", "Concluída"
        CANCELLED = "cancelled", "Cancelada"

    class Priority(models.TextChoices):
        LOW = "low", "Baixa"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Alta"
        CRITICAL = "critical", "Crítica"

    number = models.CharField(max_length=40, unique=True)
    plan = models.ForeignKey(
        MaintenancePlan,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    maintenance_type = models.CharField(max_length=20, choices=MaintenanceType.choices)
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.NORMAL,
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN,
    )
    opened_at = models.DateTimeField(default=timezone.now)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_maintenance_orders",
    )
    cancellation_reason = models.TextField(blank=True)
    reported_problem = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)
    service_performed = models.TextField(blank=True)
    supplier = models.CharField(max_length=160, blank=True)
    responsible_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="maintenance_orders",
    )
    usage_at_service = models.PositiveIntegerField(null=True, blank=True)
    labor_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    parts_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    other_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    total_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )

    class Meta:
        ordering = ["-opened_at"]
        verbose_name = "ordem de manutenção"
        verbose_name_plural = "ordens de manutenção"

    def __str__(self):
        return self.number

    def clean(self):
        self.clean_target()
        if self.status == self.Status.CANCELLED and not self.cancellation_reason:
            raise ValidationError(
                {"cancellation_reason": "Cancelamento exige justificativa."},
            )
        if self.pk:
            old = MaintenanceOrder.objects.filter(pk=self.pk).values("status").first()
            if (
                old
                and old["status"] == self.Status.COMPLETED
                and self.status == self.Status.COMPLETED
            ):
                raise ValidationError(
                    "Ordens concluídas não podem ser alteradas por usuário comum.",
                )

    def save(self, *args, **kwargs):
        self.total_cost = (
            (self.labor_cost or Decimal("0.00"))
            + (self.parts_cost or Decimal("0.00"))
            + (self.other_cost or Decimal("0.00"))
        )
        super().save(*args, **kwargs)

    def complete(self, user):
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.completed_by = user
        self.save(
            update_fields=[
                "status",
                "completed_at",
                "completed_by",
                "total_cost",
                "updated_at",
            ],
        )


class MaintenancePart(models.Model):
    maintenance_order = models.ForeignKey(
        MaintenanceOrder, on_delete=models.CASCADE, related_name="parts",
    )
    description = models.CharField(max_length=180)
    part_number = models.CharField(max_length=80, blank=True)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("1.00"),
    )
    unit_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )
    total_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
    )

    def save(self, *args, **kwargs):
        self.total_cost = (self.quantity or Decimal("0.00")) * (
            self.unit_cost or Decimal("0.00")
        )
        super().save(*args, **kwargs)


class MaintenanceAttachment(models.Model):
    maintenance_order = models.ForeignKey(
        MaintenanceOrder, on_delete=models.CASCADE, related_name="attachments",
    )
    file = models.FileField(upload_to="maintenance-attachments/")
    description = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
    )
