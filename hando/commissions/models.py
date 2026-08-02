from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import AuditableModel
from core.models import TimeStampedModel


class CommissionTarget(models.TextChoices):
    SALESPERSON = "salesperson", "Vendedor"
    COMMERCIAL_PARTNER = "commercial_partner", "Parceiro"
    BOTH = "both", "Ambos"


class CalculationBasis(models.TextChoices):
    GROSS_ORDER_VALUE = "gross_order_value", "Valor bruto do pedido"
    NET_ORDER_VALUE = "net_order_value", "Valor líquido do pedido"
    RECEIVED_VALUE = "received_value", "Valor recebido"
    ITEM_VALUE = "item_value", "Valor de itens"
    SERVICE_VALUE = "service_value", "Valor de serviços"
    MARGIN_VALUE = "margin_value", "Valor da margem"
    CUSTOM = "custom", "Personalizado"


class TriggerType(models.TextChoices):
    QUOTE_ACCEPTED = "quote_accepted", "Orçamento aceito"
    ORDER_CONFIRMED = "order_confirmed", "Pedido confirmado"
    RECEIVABLE_GENERATED = "receivable_generated", "Conta a receber gerada"
    PAYMENT_RECEIVED = "payment_received", "Recebimento"
    ORDER_COMPLETED = "order_completed", "Pedido concluído"
    MANUAL = "manual", "Manual"


class CommissionType(models.TextChoices):
    PERCENTAGE = "percentage", "Percentual"
    FIXED_AMOUNT = "fixed_amount", "Valor fixo"
    PERCENTAGE_OVER_MARGIN = "percentage_over_margin", "Percentual sobre margem"


class BeneficiaryType(models.TextChoices):
    SALESPERSON = "salesperson", "Vendedor"
    COMMERCIAL_PARTNER = "commercial_partner", "Parceiro"


class EventType(models.TextChoices):
    PROVISION = "provision", "Provisionamento"
    RELEASE = "release", "Liberação"
    PAYMENT = "payment", "Pagamento"
    REVERSAL = "reversal", "Estorno"
    ADJUSTMENT_POSITIVE = "adjustment_positive", "Ajuste positivo"
    ADJUSTMENT_NEGATIVE = "adjustment_negative", "Ajuste negativo"
    CANCELLATION = "cancellation", "Cancelamento"
    CHARGEBACK = "chargeback", "Chargeback"


class EventStatus(models.TextChoices):
    PROVISIONED = "provisioned", "Provisionada"
    PENDING_APPROVAL = "pending_approval", "Aguardando aprovação"
    APPROVED = "approved", "Aprovada"
    AVAILABLE = "available", "Disponível"
    PARTIALLY_PAID = "partially_paid", "Parcialmente paga"
    PAID = "paid", "Paga"
    REVERSED = "reversed", "Estornada"
    CANCELLED = "cancelled", "Cancelada"
    BLOCKED = "blocked", "Bloqueada"


class SettlementStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    UNDER_REVIEW = "under_review", "Em análise"
    APPROVED = "approved", "Aprovado"
    PARTIALLY_PAID = "partially_paid", "Parcialmente pago"
    PAID = "paid", "Pago"
    CLOSED = "closed", "Encerrado"
    CANCELLED = "cancelled", "Cancelado"


class PaymentStatus(models.TextChoices):
    CONFIRMED = "confirmed", "Confirmado"
    REVERSED = "reversed", "Estornado"
    CANCELLED = "cancelled", "Cancelado"


class ReversalReason(models.TextChoices):
    PAYMENT_REVERSED = "payment_reversed", "Recebimento estornado"
    ORDER_CANCELLED = "order_cancelled", "Pedido cancelado"
    SALE_CANCELLED = "sale_cancelled", "Venda cancelada"
    CUSTOMER_REFUND = "customer_refund", "Estorno ao cliente"
    CALCULATION_ERROR = "calculation_error", "Erro de cálculo"
    DUPLICATE = "duplicate", "Duplicidade"
    MANUAL_CORRECTION = "manual_correction", "Correção manual"
    OTHER = "other", "Outro"


class CommissionSequence(models.Model):
    kind = models.CharField(max_length=40)
    year = models.PositiveIntegerField()
    current = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kind", "year"], name="unique_commission_seq_kind_year"),
        ]


class CommissionPolicy(TimeStampedModel, AuditableModel):
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    commission_target = models.CharField(
        max_length=30,
        choices=CommissionTarget.choices,
        default=CommissionTarget.SALESPERSON,
    )
    calculation_basis = models.CharField(
        max_length=30,
        choices=CalculationBasis.choices,
        default=CalculationBasis.NET_ORDER_VALUE,
    )
    trigger_type = models.CharField(
        max_length=30,
        choices=TriggerType.choices,
        default=TriggerType.QUOTE_ACCEPTED,
    )
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=100)
    requires_approval = models.BooleanField(default=False)
    release_only_after_payment = models.BooleanField(default=True)
    minimum_margin_percent = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    maximum_discount_percent = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["priority", "-valid_from", "name"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.priority is not None and self.priority < 0:
            raise ValidationError({"priority": "Prioridade não pode ser negativa."})
        if self.valid_until and self.valid_from and self.valid_until < self.valid_from:
            raise ValidationError({"valid_until": "Vigência final anterior ao início."})


class CommissionPolicyTier(TimeStampedModel):
    policy = models.ForeignKey(CommissionPolicy, on_delete=models.CASCADE, related_name="tiers")
    sequence = models.PositiveIntegerField()
    minimum_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    maximum_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    commission_type = models.CharField(
        max_length=30,
        choices=CommissionType.choices,
        default=CommissionType.PERCENTAGE,
    )
    commission_value = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("0"))
    applies_to_excess = models.BooleanField(default=False)

    class Meta:
        ordering = ["sequence", "minimum_value"]
        unique_together = [("policy", "sequence")]

    def clean(self):
        if self.commission_type == CommissionType.PERCENTAGE and (
            self.commission_value < 0 or self.commission_value > 100
        ):
            raise ValidationError({"commission_value": "Percentual deve estar entre 0 e 100."})
        if self.commission_value < 0:
            raise ValidationError({"commission_value": "Valor não pode ser negativo."})
        if self.maximum_value is not None and self.maximum_value < self.minimum_value:
            raise ValidationError({"maximum_value": "Máximo menor que o mínimo."})


class CommissionRule(TimeStampedModel):
    policy = models.ForeignKey(CommissionPolicy, on_delete=models.CASCADE, related_name="rules")
    name = models.CharField(max_length=160)
    priority = models.PositiveIntegerField(default=10)
    salesperson = models.ForeignKey(
        "salespeople.Salesperson",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="commission_rules",
    )
    commercial_partner = models.ForeignKey(
        "commercial.CommercialPartner",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="commission_rules",
    )
    project_type = models.ForeignKey(
        "commercial.ProjectType",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commission_rules",
    )
    commercial_source = models.ForeignKey(
        "commercial.CommercialSource",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commission_rules",
    )
    minimum_order_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    maximum_discount_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    minimum_margin_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    override_commission_type = models.CharField(
        max_length=30,
        choices=CommissionType.choices,
        blank=True,
    )
    override_commission_value = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["priority", "id"]


class CommissionEvent(TimeStampedModel):
    number = models.CharField(max_length=32, unique=True)
    beneficiary_type = models.CharField(max_length=30, choices=BeneficiaryType.choices)
    salesperson = models.ForeignKey(
        "salespeople.Salesperson",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="commission_events",
    )
    commercial_partner = models.ForeignKey(
        "commercial.CommercialPartner",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="commission_events",
    )
    beneficiary_name_snapshot = models.CharField(max_length=180, blank=True)
    beneficiary_document_snapshot = models.CharField(max_length=40, blank=True)
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    status = models.CharField(max_length=30, choices=EventStatus.choices, default=EventStatus.PROVISIONED)
    source_type = models.CharField(max_length=40)
    source_id = models.PositiveIntegerField()
    quote = models.ForeignKey(
        "quotes.Quote",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commission_events",
    )
    sales_order = models.ForeignKey(
        "production.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commission_events",
    )
    receivable = models.ForeignKey(
        "finance.AccountsReceivable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commission_events",
    )
    receivable_payment = models.ForeignKey(
        "finance.ReceivablePayment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commission_events",
    )
    policy = models.ForeignKey(
        CommissionPolicy,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    rule = models.ForeignKey(
        CommissionRule,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    calculation_basis_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    commission_rate = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal("0"))
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    eligible_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    event_date = models.DateField()
    competence_date = models.DateField()
    available_date = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    reversal_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversals",
    )
    settlement = models.ForeignKey(
        "CommissionSettlement",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commission_events_created",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "status"]),
            models.Index(fields=["salesperson", "status"]),
            models.Index(fields=["commercial_partner", "status"]),
            models.Index(fields=["source_type", "source_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["event_type", "source_type", "source_id", "beneficiary_type", "salesperson"],
                condition=Q(salesperson__isnull=False)
                & ~Q(status__in=["reversed", "cancelled"])
                & ~Q(event_type__in=["reversal", "adjustment_positive", "adjustment_negative"]),
                name="unique_active_commission_event_salesperson",
            ),
            models.UniqueConstraint(
                fields=["event_type", "source_type", "source_id", "beneficiary_type", "commercial_partner"],
                condition=Q(commercial_partner__isnull=False)
                & ~Q(status__in=["reversed", "cancelled"])
                & ~Q(event_type__in=["reversal", "adjustment_positive", "adjustment_negative"]),
                name="unique_active_commission_event_partner",
            ),
        ]

    def __str__(self):
        return self.number

    IMMUTABLE_FIELDS = (
        "number",
        "beneficiary_type",
        "salesperson_id",
        "commercial_partner_id",
        "event_type",
        "source_type",
        "source_id",
        "calculation_basis_amount",
        "commission_rate",
        "commission_amount",
        "eligible_amount",
        "policy_id",
        "rule_id",
    )

    def save(self, *args, **kwargs):
        if self.pk:
            previous = CommissionEvent.objects.filter(pk=self.pk).values(*self.IMMUTABLE_FIELDS).first()
            if previous:
                for field in self.IMMUTABLE_FIELDS:
                    if previous[field] != getattr(self, field):
                        raise ValidationError("Valores do evento de comissão são imutáveis.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Evento de comissão não pode ser apagado.")


class CommissionSettlement(TimeStampedModel, AuditableModel):
    number = models.CharField(max_length=32, unique=True)
    period_start = models.DateField()
    period_end = models.DateField()
    beneficiary_type = models.CharField(max_length=30, choices=BeneficiaryType.choices)
    salesperson = models.ForeignKey(
        "salespeople.Salesperson",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="commission_settlements",
    )
    commercial_partner = models.ForeignKey(
        "commercial.CommercialPartner",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="commission_settlements",
    )
    status = models.CharField(max_length=30, choices=SettlementStatus.choices, default=SettlementStatus.DRAFT)
    provisioned_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    available_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    reversed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commission_settlements_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commission_settlements_closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    payable = models.ForeignKey(
        "finance.AccountsPayable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commission_settlements",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.number


class CommissionSettlementItem(TimeStampedModel):
    settlement = models.ForeignKey(CommissionSettlement, on_delete=models.CASCADE, related_name="items")
    commission_event = models.ForeignKey(
        CommissionEvent,
        on_delete=models.PROTECT,
        related_name="settlement_items",
    )
    included_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=30, default="included")
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [("settlement", "commission_event")]


class CommissionPayment(TimeStampedModel):
    number = models.CharField(max_length=32, unique=True)
    settlement = models.ForeignKey(CommissionSettlement, on_delete=models.PROTECT, related_name="payments")
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.ForeignKey(
        "finance.PaymentMethod",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commission_payments",
    )
    financial_account = models.ForeignKey(
        "finance.FinancialAccount",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commission_payments",
    )
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.CONFIRMED)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commission_payments_created",
    )

    class Meta:
        ordering = ["-created_at"]
