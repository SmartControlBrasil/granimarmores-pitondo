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


ACTIVE_ORDER_STATUSES = [
    "draft",
    "confirmed",
    "technical_review",
    "awaiting_measurement",
    "ready_for_production",
    "in_production",
    "quality_control",
    "ready_for_delivery",
    "scheduled",
    "delivered",
    "installed",
    "on_hold",
]


class SalesOrderSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    current = models.PositiveIntegerField(default=0)


class ProductionOrderSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    current = models.PositiveIntegerField(default=0)


class SalesOrderStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    CONFIRMED = "confirmed", "Confirmado"
    TECHNICAL_REVIEW = "technical_review", "Revisão técnica"
    AWAITING_MEASUREMENT = "awaiting_measurement", "Aguardando medição"
    READY_FOR_PRODUCTION = "ready_for_production", "Pronto para produção"
    IN_PRODUCTION = "in_production", "Em produção"
    QUALITY_CONTROL = "quality_control", "Controle de qualidade"
    READY_FOR_DELIVERY = "ready_for_delivery", "Pronto para entrega"
    SCHEDULED = "scheduled", "Agendado"
    DELIVERED = "delivered", "Entregue"
    INSTALLED = "installed", "Instalado"
    COMPLETED = "completed", "Concluído"
    ON_HOLD = "on_hold", "Em espera"
    CANCELLED = "cancelled", "Cancelado"


TERMINAL_ORDER_STATUSES = {
    SalesOrderStatus.COMPLETED,
    SalesOrderStatus.CANCELLED,
}


class ProductionOrderStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    PLANNED = "planned", "Planejada"
    RELEASED = "released", "Liberada"
    IN_PROGRESS = "in_progress", "Em andamento"
    ON_HOLD = "on_hold", "Pausada"
    QUALITY_CONTROL = "quality_control", "Qualidade"
    COMPLETED = "completed", "Concluída"
    CANCELLED = "cancelled", "Cancelada"


class ProductionPieceStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    READY = "ready", "Pronta"
    IN_PROGRESS = "in_progress", "Em andamento"
    ON_HOLD = "on_hold", "Pausada"
    QUALITY_CONTROL = "quality_control", "Qualidade"
    APPROVED = "approved", "Aprovada"
    REWORK = "rework", "Retrabalho"
    COMPLETED = "completed", "Concluída"
    CANCELLED = "cancelled", "Cancelada"


class PieceStageStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    READY = "ready", "Pronta"
    IN_PROGRESS = "in_progress", "Em andamento"
    BLOCKED = "blocked", "Bloqueada"
    COMPLETED = "completed", "Concluída"
    SKIPPED = "skipped", "Pulada"
    CANCELLED = "cancelled", "Cancelada"


class ScheduleStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    SCHEDULED = "scheduled", "Agendado"
    IN_TRANSIT = "in_transit", "Em trânsito"
    COMPLETED = "completed", "Concluído"
    FAILED = "failed", "Falhou"
    CANCELLED = "cancelled", "Cancelado"
    RESCHEDULED = "rescheduled", "Reagendado"


class SalesOrder(TimeStampedModel, AuditableModel):
    number = models.CharField(max_length=20, unique=True, blank=True)
    quote = models.ForeignKey(
        "quotes.Quote",
        on_delete=models.PROTECT,
        related_name="sales_orders",
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="sales_orders",
    )
    lead = models.ForeignKey(
        "commercial.Lead",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_orders",
    )
    salesperson = models.ForeignKey(
        "salespeople.Salesperson",
        on_delete=models.PROTECT,
        related_name="sales_orders",
    )
    status = models.CharField(
        max_length=30,
        choices=SalesOrderStatus.choices,
        default=SalesOrderStatus.DRAFT,
    )
    order_date = models.DateField(default=timezone.localdate)
    promised_date = models.DateField(null=True, blank=True)
    installation_required = models.BooleanField(default=False)
    delivery_required = models.BooleanField(default=True)
    delivery_address = models.CharField(max_length=255, blank=True)
    delivery_city = models.CharField(max_length=120, blank=True)
    delivery_state = models.CharField(max_length=2, blank=True)
    delivery_postal_code = models.CharField(max_length=12, blank=True)
    customer_notes = models.TextField(blank=True)
    commercial_notes = models.TextField(blank=True)
    technical_notes = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    additional_costs = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    hold_reason = models.TextField(blank=True)
    cancel_reason = models.TextField(blank=True)
    previous_status = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["number"]),
            models.Index(fields=["status"]),
            models.Index(fields=["promised_date"]),
            models.Index(fields=["customer"]),
            models.Index(fields=["salesperson"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["quote"],
                condition=~models.Q(status=SalesOrderStatus.CANCELLED),
                name="unique_active_sales_order_per_quote",
            ),
        ]

    def __str__(self):
        return self.number or f"Pedido {self.pk}"


class SalesOrderItem(TimeStampedModel):
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="items")
    quote_item_id = models.PositiveIntegerField(null=True, blank=True)
    description = models.CharField(max_length=220)
    project_type_name = models.CharField(max_length=160, blank=True)
    material = models.ForeignKey(
        "materials.Material",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    material_name_snapshot = models.CharField(max_length=180, blank=True)
    finish_name_snapshot = models.CharField(max_length=180, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal("1.000"))
    unit = models.CharField(max_length=20, choices=Unit.choices, default=Unit.M2)
    width = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    height = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    depth = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    area = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0000"))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    technical_notes = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["position", "id"]


class SalesOrderItemMeasurement(models.Model):
    order_item = models.ForeignKey(
        SalesOrderItem,
        on_delete=models.CASCADE,
        related_name="measurements",
    )
    label = models.CharField(max_length=120)
    width = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    height = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    area = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0000"))
    notes = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["position", "id"]


class ProductionOrder(TimeStampedModel, AuditableModel):
    number = models.CharField(max_length=20, unique=True, blank=True)
    sales_order = models.OneToOneField(
        SalesOrder,
        on_delete=models.PROTECT,
        related_name="production_order",
    )
    status = models.CharField(
        max_length=20,
        choices=ProductionOrderStatus.choices,
        default=ProductionOrderStatus.DRAFT,
    )
    priority = models.CharField(max_length=20, default="normal")
    planned_start_date = models.DateField(null=True, blank=True)
    planned_end_date = models.DateField(null=True, blank=True)
    actual_start_at = models.DateTimeField(null=True, blank=True)
    actual_end_at = models.DateTimeField(null=True, blank=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="production_orders_responsible",
    )
    production_notes = models.TextField(blank=True)
    technical_notes = models.TextField(blank=True)
    hold_reason = models.TextField(blank=True)
    cancel_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["number"]),
            models.Index(fields=["status"]),
            models.Index(fields=["planned_end_date"]),
        ]

    def __str__(self):
        return self.number or f"OP {self.pk}"


class ProductionStage(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_required = models.BooleanField(default=True)
    default_duration_minutes = models.PositiveIntegerField(default=0)
    requires_quality_check = models.BooleanField(default=False)
    allows_photos = models.BooleanField(default=False)
    board_column = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class ProductionPiece(TimeStampedModel):
    production_order = models.ForeignKey(
        ProductionOrder,
        on_delete=models.CASCADE,
        related_name="pieces",
    )
    order_item = models.ForeignKey(
        SalesOrderItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="production_pieces",
    )
    code = models.CharField(max_length=40)
    description = models.CharField(max_length=220)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal("1.000"))
    material = models.ForeignKey(
        "materials.Material",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    material_name_snapshot = models.CharField(max_length=180, blank=True)
    slab = models.ForeignKey(
        "materials.MaterialSlab",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    finish_name_snapshot = models.CharField(max_length=180, blank=True)
    width = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    height = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    depth = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    area = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    edge_details = models.TextField(blank=True)
    cutout_details = models.TextField(blank=True)
    sink_details = models.TextField(blank=True)
    technical_drawing_reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ProductionPieceStatus.choices,
        default=ProductionPieceStatus.PENDING,
    )
    priority = models.CharField(max_length=20, default="normal")
    planned_start_date = models.DateField(null=True, blank=True)
    planned_end_date = models.DateField(null=True, blank=True)
    actual_start_at = models.DateTimeField(null=True, blank=True)
    actual_end_at = models.DateTimeField(null=True, blank=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="production_pieces_responsible",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["production_order", "code"],
                name="unique_piece_code_per_order",
            ),
        ]

    def __str__(self):
        return f"{self.production_order.number} - {self.code}"


class ProductionPieceStage(TimeStampedModel):
    piece = models.ForeignKey(
        ProductionPiece,
        on_delete=models.CASCADE,
        related_name="stages",
    )
    stage = models.ForeignKey(ProductionStage, on_delete=models.PROTECT)
    sequence = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=PieceStageStatus.choices,
        default=PieceStageStatus.PENDING,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_piece_stages",
    )
    planned_start_at = models.DateTimeField(null=True, blank=True)
    planned_end_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_piece_stages",
    )
    notes = models.TextField(blank=True)
    is_required = models.BooleanField(default=True)
    skip_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["piece", "sequence"],
                name="unique_piece_stage_sequence",
            ),
        ]


class ProductionLogType(models.TextChoices):
    NOTE = "note", "Observação"
    START = "start", "Início"
    PAUSE = "pause", "Pausa"
    RESUME = "resume", "Retomada"
    COMPLETION = "completion", "Conclusão"
    MEASUREMENT = "measurement", "Medição"
    MATERIAL_CHANGE = "material_change", "Alteração de material"
    ISSUE = "issue", "Problema"
    REWORK = "rework", "Retrabalho"
    QUALITY = "quality", "Qualidade"
    DELIVERY = "delivery", "Entrega"
    INSTALLATION = "installation", "Instalação"
    OTHER = "other", "Outro"


class ProductionLog(models.Model):
    production_order = models.ForeignKey(
        ProductionOrder,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    piece = models.ForeignKey(
        ProductionPiece,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    piece_stage = models.ForeignKey(
        ProductionPieceStage,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="logs",
    )
    log_type = models.CharField(max_length=30, choices=ProductionLogType.choices)
    description = models.TextField()
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    quantity_processed = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[validate_non_negative],
    )
    quantity_rejected = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[validate_non_negative],
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class QualityChecklist(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class QualityChecklistItem(models.Model):
    checklist = models.ForeignKey(
        QualityChecklist,
        on_delete=models.CASCADE,
        related_name="items",
    )
    label = models.CharField(max_length=180)
    display_order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order"]


class QualityInspectionStatus(models.TextChoices):
    PENDING = "pending", "Pendente"
    APPROVED = "approved", "Aprovada"
    REJECTED = "rejected", "Reprovada"
    APPROVED_WITH_NOTES = "approved_with_notes", "Aprovada com ressalvas"


class QualityInspection(TimeStampedModel):
    production_order = models.ForeignKey(
        ProductionOrder,
        on_delete=models.CASCADE,
        related_name="inspections",
    )
    piece = models.ForeignKey(
        ProductionPiece,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="inspections",
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quality_inspections",
    )
    inspected_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=30,
        choices=QualityInspectionStatus.choices,
        default=QualityInspectionStatus.PENDING,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-inspected_at"]


class QualityInspectionResult(models.Model):
    inspection = models.ForeignKey(
        QualityInspection,
        on_delete=models.CASCADE,
        related_name="results",
    )
    checklist_item = models.ForeignKey(
        QualityChecklistItem,
        on_delete=models.PROTECT,
    )
    passed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)


class DeliverySchedule(TimeStampedModel, AuditableModel):
    sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    scheduled_date = models.DateField()
    scheduled_time_start = models.TimeField(null=True, blank=True)
    scheduled_time_end = models.TimeField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=2, blank=True)
    postal_code = models.CharField(max_length=12, blank=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="delivery_schedules",
    )
    vehicle = models.ForeignKey(
        "fleet.Vehicle",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="delivery_schedules",
    )
    status = models.CharField(
        max_length=20,
        choices=ScheduleStatus.choices,
        default=ScheduleStatus.PENDING,
    )
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_deliveries",
    )

    class Meta:
        ordering = ["scheduled_date"]


class InstallationSchedule(TimeStampedModel, AuditableModel):
    sales_order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name="installations",
    )
    scheduled_date = models.DateField()
    scheduled_time_start = models.TimeField(null=True, blank=True)
    scheduled_time_end = models.TimeField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=2, blank=True)
    postal_code = models.CharField(max_length=12, blank=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="installation_schedules",
    )
    vehicle = models.ForeignKey(
        "fleet.Vehicle",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="installation_schedules",
    )
    status = models.CharField(
        max_length=20,
        choices=ScheduleStatus.choices,
        default=ScheduleStatus.PENDING,
    )
    notes = models.TextField(blank=True)
    result_notes = models.TextField(blank=True)
    return_required = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_installations",
    )

    class Meta:
        ordering = ["scheduled_date"]
