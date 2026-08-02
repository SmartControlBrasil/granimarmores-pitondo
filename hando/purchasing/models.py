from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import AuditableModel
from core.models import TimeStampedModel


class RequestType(models.TextChoices):
    MATERIAL = "material", "Material"
    SLAB = "slab", "Chapa"
    TOOL = "tool", "Ferramenta"
    CONSUMABLE = "consumable", "Consumível"
    SERVICE = "service", "Serviço"
    MAINTENANCE = "maintenance", "Manutenção"
    OTHER = "other", "Outro"


class RequestStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    SUBMITTED = "submitted", "Enviada"
    UNDER_REVIEW = "under_review", "Em análise"
    APPROVED = "approved", "Aprovada"
    REJECTED = "rejected", "Rejeitada"
    PARTIALLY_QUOTED = "partially_quoted", "Parcialmente cotada"
    QUOTED = "quoted", "Cotada"
    ORDERED = "ordered", "Pedida"
    PARTIALLY_RECEIVED = "partially_received", "Parcialmente recebida"
    RECEIVED = "received", "Recebida"
    CANCELLED = "cancelled", "Cancelada"


class Priority(models.TextChoices):
    LOW = "low", "Baixa"
    NORMAL = "normal", "Normal"
    HIGH = "high", "Alta"
    CRITICAL = "critical", "Crítica"


class SourceType(models.TextChoices):
    MANUAL = "manual", "Manual"
    PRODUCTION_PIECE = "production_piece", "Peça de produção"
    PRODUCTION_ORDER = "production_order", "Ordem de produção"
    STOCK_NEED = "stock_need", "Necessidade de estoque"
    AFTER_SALES = "after_sales", "Assistência"
    MAINTENANCE = "maintenance", "Manutenção"


class ItemType(models.TextChoices):
    MATERIAL = "material", "Material"
    SLAB = "slab", "Chapa"
    SERVICE = "service", "Serviço"
    TOOL = "tool", "Ferramenta"
    CONSUMABLE = "consumable", "Consumível"
    OTHER = "other", "Outro"


class QuotationStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    REQUESTED = "requested", "Solicitada"
    RECEIVED = "received", "Recebida"
    UNDER_ANALYSIS = "under_analysis", "Em análise"
    SELECTED = "selected", "Selecionada"
    REJECTED = "rejected", "Rejeitada"
    EXPIRED = "expired", "Vencida"
    CANCELLED = "cancelled", "Cancelada"


class PurchaseOrderStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    APPROVED = "approved", "Aprovado"
    SENT = "sent", "Enviado"
    CONFIRMED = "confirmed", "Confirmado"
    PARTIALLY_RECEIVED = "partially_received", "Parcialmente recebido"
    RECEIVED = "received", "Recebido"
    CLOSED = "closed", "Encerrado"
    CANCELLED = "cancelled", "Cancelado"
    REJECTED = "rejected", "Rejeitado"


class ReceiptStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    UNDER_INSPECTION = "under_inspection", "Em inspeção"
    ACCEPTED = "accepted", "Aceito"
    ACCEPTED_WITH_DIVERGENCE = "accepted_with_divergence", "Aceito com divergência"
    REJECTED = "rejected", "Rejeitado"
    CANCELLED = "cancelled", "Cancelado"


class ReceiptCondition(models.TextChoices):
    ACCEPTED = "accepted", "Aceito"
    DAMAGED = "damaged", "Avariado"
    WRONG_MATERIAL = "wrong_material", "Material incorreto"
    WRONG_DIMENSION = "wrong_dimension", "Dimensão incorreta"
    QUANTITY_SHORTAGE = "quantity_shortage", "Falta de quantidade"
    QUANTITY_EXCESS = "quantity_excess", "Excesso de quantidade"
    QUALITY_ISSUE = "quality_issue", "Problema de qualidade"
    OTHER = "other", "Outro"


class DivergenceSeverity(models.TextChoices):
    LOW = "low", "Baixa"
    MEDIUM = "medium", "Média"
    HIGH = "high", "Alta"
    CRITICAL = "critical", "Crítica"


class DivergenceStatus(models.TextChoices):
    OPEN = "open", "Aberta"
    UNDER_ANALYSIS = "under_analysis", "Em análise"
    ACCEPTED = "accepted", "Aceita"
    SUPPLIER_CONTACTED = "supplier_contacted", "Fornecedor contatado"
    REPLACEMENT_EXPECTED = "replacement_expected", "Aguardando substituição"
    CREDIT_EXPECTED = "credit_expected", "Aguardando crédito"
    RESOLVED = "resolved", "Resolvida"
    CANCELLED = "cancelled", "Cancelada"


class ReturnStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    APPROVED = "approved", "Aprovada"
    SENT = "sent", "Enviada"
    COMPLETED = "completed", "Concluída"
    CANCELLED = "cancelled", "Cancelada"


class PurchasingSequence(models.Model):
    kind = models.CharField(max_length=40)
    year = models.PositiveIntegerField()
    current = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kind", "year"], name="unique_purchasing_seq_kind_year"),
        ]


class PurchaseRequest(TimeStampedModel, AuditableModel):
    number = models.CharField(max_length=32, unique=True)
    request_type = models.CharField(max_length=20, choices=RequestType.choices, default=RequestType.MATERIAL)
    status = models.CharField(max_length=30, choices=RequestStatus.choices, default=RequestStatus.DRAFT)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="purchase_requests_made",
    )
    requested_for_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_requests_for",
    )
    production_order = models.ForeignKey(
        "production.ProductionOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_requests",
    )
    production_piece = models.ForeignKey(
        "production.ProductionPiece",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_requests",
    )
    sales_order = models.ForeignKey(
        "production.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_requests",
    )
    cost_center = models.ForeignKey(
        "finance.CostCenter",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_requests",
    )
    source_type = models.CharField(max_length=30, choices=SourceType.choices, default=SourceType.MANUAL)
    source_id = models.PositiveIntegerField(null=True, blank=True)
    required_date = models.DateField(null=True, blank=True)
    justification = models.TextField()
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_requests_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_requests_rejected",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    selection_justification = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["requested_by", "status"]),
        ]

    def __str__(self):
        return self.number


class PurchaseRequestItem(TimeStampedModel):
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name="items",
    )
    item_type = models.CharField(max_length=20, choices=ItemType.choices, default=ItemType.MATERIAL)
    material = models.ForeignKey(
        "materials.Material",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_request_items",
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=40, default="un")
    estimated_unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    required_date = models.DateField(null=True, blank=True)
    preferred_supplier = models.ForeignKey(
        "materials.MaterialSupplier",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="preferred_request_items",
    )
    technical_specification = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=30, default="open")

    class Meta:
        ordering = ["id"]

    def clean(self):
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError({"quantity": "Quantidade deve ser positiva."})
        if not self.material_id and not (self.technical_specification or "").strip():
            raise ValidationError(
                {"technical_specification": "Especificação técnica obrigatória para itens não cadastrados."},
            )


class SupplierQuotation(TimeStampedModel, AuditableModel):
    number = models.CharField(max_length=32, unique=True)
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.PROTECT,
        related_name="quotations",
    )
    supplier = models.ForeignKey(
        "materials.MaterialSupplier",
        on_delete=models.PROTECT,
        related_name="quotations",
    )
    status = models.CharField(max_length=30, choices=QuotationStatus.choices, default=QuotationStatus.DRAFT)
    quotation_date = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    delivery_days = models.PositiveIntegerField(default=0)
    freight_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    payment_term_text = models.CharField(max_length=180, blank=True)
    payment_method = models.ForeignKey(
        "finance.PaymentMethod",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supplier_quotations",
    )
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotations_received",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.number


class SupplierQuotationItem(TimeStampedModel):
    quotation = models.ForeignKey(SupplierQuotation, on_delete=models.CASCADE, related_name="items")
    request_item = models.ForeignKey(
        PurchaseRequestItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotation_items",
    )
    supplier_code = models.CharField(max_length=80, blank=True)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=40, default="un")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    freight_share = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    delivery_days = models.PositiveIntegerField(default=0)
    brand = models.CharField(max_length=120, blank=True)
    batch = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    is_selected = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]


class PurchaseOrder(TimeStampedModel, AuditableModel):
    number = models.CharField(max_length=32, unique=True)
    supplier = models.ForeignKey(
        "materials.MaterialSupplier",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_orders",
    )
    quotation = models.ForeignKey(
        SupplierQuotation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_orders",
    )
    status = models.CharField(
        max_length=30,
        choices=PurchaseOrderStatus.choices,
        default=PurchaseOrderStatus.DRAFT,
    )
    order_date = models.DateField()
    expected_delivery_date = models.DateField(null=True, blank=True)
    delivery_location = models.ForeignKey(
        "materials.StockLocation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_orders",
    )
    payment_term = models.ForeignKey(
        "finance.PaymentTerm",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_orders",
    )
    payment_method = models.ForeignKey(
        "finance.PaymentMethod",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_orders",
    )
    cost_center = models.ForeignKey(
        "finance.CostCenter",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_orders",
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    freight_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    additional_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True)
    supplier_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    cancel_reason = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_orders_approved",
    )
    payable = models.ForeignKey(
        "finance.AccountsPayable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_orders",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "expected_delivery_date"]),
            models.Index(fields=["supplier", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_request", "supplier"],
                condition=Q(purchase_request__isnull=False)
                & ~Q(status__in=["cancelled", "rejected"]),
                name="unique_active_po_per_request_supplier",
            ),
        ]

    def __str__(self):
        return self.number

    @property
    def received_quantity_total(self):
        return sum((i.received_quantity for i in self.items.all()), Decimal("0"))

    @property
    def ordered_quantity_total(self):
        return sum((i.ordered_quantity for i in self.items.all()), Decimal("0"))


class PurchaseOrderItem(TimeStampedModel):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    request_item = models.ForeignKey(
        PurchaseRequestItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="order_items",
    )
    quotation_item = models.ForeignKey(
        SupplierQuotationItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="order_items",
    )
    item_type = models.CharField(max_length=20, choices=ItemType.choices, default=ItemType.MATERIAL)
    material = models.ForeignKey(
        "materials.Material",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_order_items",
    )
    description = models.CharField(max_length=255)
    ordered_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    received_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0.000"))
    cancelled_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0.000"))
    unit = models.CharField(max_length=40, default="un")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    thickness = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    width = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    expected_area = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["id"]

    @property
    def outstanding_quantity(self):
        return self.ordered_quantity - self.received_quantity - self.cancelled_quantity


class PurchaseReceipt(TimeStampedModel, AuditableModel):
    number = models.CharField(max_length=32, unique=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="receipts")
    status = models.CharField(max_length=30, choices=ReceiptStatus.choices, default=ReceiptStatus.DRAFT)
    received_at = models.DateTimeField()
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="purchase_receipts",
    )
    delivery_document = models.CharField(max_length=120, blank=True)
    supplier_document = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    stock_location = models.ForeignKey(
        "materials.StockLocation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_receipts",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.number


class PurchaseReceiptItem(TimeStampedModel):
    receipt = models.ForeignKey(PurchaseReceipt, on_delete=models.CASCADE, related_name="items")
    purchase_order_item = models.ForeignKey(
        PurchaseOrderItem,
        on_delete=models.PROTECT,
        related_name="receipt_items",
    )
    received_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0.000"))
    accepted_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0.000"))
    rejected_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0.000"))
    unit = models.CharField(max_length=40, default="un")
    actual_unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    width = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    thickness = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    area = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    batch = models.CharField(max_length=80, blank=True)
    supplier_code = models.CharField(max_length=80, blank=True)
    condition = models.CharField(
        max_length=30,
        choices=ReceiptCondition.choices,
        default=ReceiptCondition.ACCEPTED,
    )
    divergence_type = models.CharField(max_length=40, blank=True)
    divergence_notes = models.TextField(blank=True)
    stock_entered = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]


class PurchaseReceiptSlab(TimeStampedModel):
    receipt_item = models.ForeignKey(
        PurchaseReceiptItem,
        on_delete=models.PROTECT,
        related_name="slabs",
    )
    slab = models.OneToOneField(
        "materials.MaterialSlab",
        on_delete=models.PROTECT,
        related_name="purchase_receipt_link",
    )


class PurchaseReceiptDivergence(TimeStampedModel, AuditableModel):
    receipt = models.ForeignKey(PurchaseReceipt, on_delete=models.CASCADE, related_name="divergences")
    receipt_item = models.ForeignKey(
        PurchaseReceiptItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="divergences",
    )
    divergence_type = models.CharField(max_length=40, choices=ReceiptCondition.choices)
    severity = models.CharField(
        max_length=20,
        choices=DivergenceSeverity.choices,
        default=DivergenceSeverity.MEDIUM,
    )
    description = models.TextField()
    expected_value = models.CharField(max_length=120, blank=True)
    received_value = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=30,
        choices=DivergenceStatus.choices,
        default=DivergenceStatus.OPEN,
    )
    resolution = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_divergences_resolved",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class PurchaseReturn(TimeStampedModel, AuditableModel):
    number = models.CharField(max_length=32, unique=True)
    supplier = models.ForeignKey(
        "materials.MaterialSupplier",
        on_delete=models.PROTECT,
        related_name="purchase_returns",
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="returns",
    )
    receipt = models.ForeignKey(
        PurchaseReceipt,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="returns",
    )
    status = models.CharField(max_length=20, choices=ReturnStatus.choices, default=ReturnStatus.DRAFT)
    return_date = models.DateField()
    reason = models.TextField()
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_returns_approved",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.number


class PurchaseReturnItem(TimeStampedModel):
    purchase_return = models.ForeignKey(PurchaseReturn, on_delete=models.CASCADE, related_name="items")
    receipt_item = models.ForeignKey(
        PurchaseReceiptItem,
        on_delete=models.PROTECT,
        related_name="return_items",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    slab = models.ForeignKey(
        "materials.MaterialSlab",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchase_return_items",
    )
    notes = models.TextField(blank=True)
    stock_exited = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
