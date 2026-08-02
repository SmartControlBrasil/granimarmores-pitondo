# ruff: noqa: DJ001
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import AuditableModel
from core.models import SoftDeleteModel
from core.models import TimeStampedModel


class CategoryType(models.TextChoices):
    INCOME = "income", "Receita"
    EXPENSE = "expense", "Despesa"
    TRANSFER = "transfer", "Transferência"
    ADJUSTMENT = "adjustment", "Ajuste"


class MethodType(models.TextChoices):
    CASH = "cash", "Dinheiro"
    PIX = "pix", "PIX"
    BANK_TRANSFER = "bank_transfer", "Transferência bancária"
    CREDIT_CARD = "credit_card", "Cartão de crédito"
    DEBIT_CARD = "debit_card", "Cartão de débito"
    CHECK = "check", "Cheque"
    BOLETO_MANUAL = "boleto_manual", "Boleto (manual)"
    OTHER = "other", "Outro"


class AccountType(models.TextChoices):
    CASH = "cash", "Caixa"
    BANK_ACCOUNT = "bank_account", "Conta bancária"
    DIGITAL_ACCOUNT = "digital_account", "Conta digital"
    CREDIT_CARD_CLEARING = "credit_card_clearing", "Clearing cartão"
    OTHER = "other", "Outro"


class TitleStatus(models.TextChoices):
    DRAFT = "draft", "Rascunho"
    OPEN = "open", "Aberto"
    PARTIALLY_PAID = "partially_paid", "Parcialmente pago"
    PAID = "paid", "Pago"
    OVERDUE = "overdue", "Vencido"
    CANCELLED = "cancelled", "Cancelado"
    RENEGOTIATED = "renegotiated", "Renegociado"
    WRITTEN_OFF = "written_off", "Baixa contábil"


class InstallmentStatus(models.TextChoices):
    OPEN = "open", "Aberta"
    PARTIALLY_PAID = "partially_paid", "Parcialmente paga"
    PAID = "paid", "Paga"
    OVERDUE = "overdue", "Vencida"
    CANCELLED = "cancelled", "Cancelada"
    RENEGOTIATED = "renegotiated", "Renegociada"


class PaymentStatus(models.TextChoices):
    CONFIRMED = "confirmed", "Confirmado"
    REVERSED = "reversed", "Estornado"
    CANCELLED = "cancelled", "Cancelado"


class MovementType(models.TextChoices):
    INCOME = "income", "Entrada"
    EXPENSE = "expense", "Saída"
    TRANSFER_IN = "transfer_in", "Transferência entrada"
    TRANSFER_OUT = "transfer_out", "Transferência saída"
    OPENING_BALANCE = "opening_balance", "Saldo inicial"
    ADJUSTMENT_IN = "adjustment_in", "Ajuste entrada"
    ADJUSTMENT_OUT = "adjustment_out", "Ajuste saída"
    REVERSAL = "reversal", "Estorno"


INCOME_MOVEMENT_TYPES = {
    MovementType.INCOME,
    MovementType.TRANSFER_IN,
    MovementType.OPENING_BALANCE,
    MovementType.ADJUSTMENT_IN,
}

EXPENSE_MOVEMENT_TYPES = {
    MovementType.EXPENSE,
    MovementType.TRANSFER_OUT,
    MovementType.ADJUSTMENT_OUT,
}

TERMINAL_TITLE_STATUSES = {
    TitleStatus.PAID,
    TitleStatus.CANCELLED,
    TitleStatus.RENEGOTIATED,
    TitleStatus.WRITTEN_OFF,
}

TERMINAL_INSTALLMENT_STATUSES = {
    InstallmentStatus.PAID,
    InstallmentStatus.CANCELLED,
    InstallmentStatus.RENEGOTIATED,
}

POSITIVE = MinValueValidator(Decimal("0.01"))
NON_NEGATIVE = MinValueValidator(Decimal("0.00"))


class FinanceSequence(models.Model):
    kind = models.CharField(max_length=20)
    year = models.PositiveIntegerField()
    current = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("kind", "year")]

    def __str__(self):
        return f"{self.kind}-{self.year}: {self.current}"


class FinancialCategory(TimeStampedModel, AuditableModel, SoftDeleteModel):
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=60, unique=True)
    category_type = models.CharField(max_length=20, choices=CategoryType.choices)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "financial categories"

    def __str__(self):
        return self.name


class CostCenter(TimeStampedModel, AuditableModel, SoftDeleteModel):
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=60, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PaymentMethod(TimeStampedModel, AuditableModel, SoftDeleteModel):
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=60, unique=True)
    method_type = models.CharField(max_length=30, choices=MethodType.choices)
    requires_reference = models.BooleanField(default=False)
    allows_installments = models.BooleanField(default=False)
    maximum_installments = models.PositiveSmallIntegerField(default=1)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PaymentTerm(TimeStampedModel, AuditableModel, SoftDeleteModel):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    installment_count = models.PositiveSmallIntegerField(default=1)
    down_payment_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    first_due_days = models.PositiveIntegerField(default=0)
    interval_days = models.PositiveIntegerField(default=30)
    is_custom = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PaymentTermInstallmentRule(models.Model):
    payment_term = models.ForeignKey(
        PaymentTerm,
        on_delete=models.CASCADE,
        related_name="rules",
    )
    sequence = models.PositiveSmallIntegerField()
    percent = models.DecimalField(max_digits=5, decimal_places=2, validators=[NON_NEGATIVE])
    days_after_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sequence"]
        unique_together = [("payment_term", "sequence")]

    def __str__(self):
        return f"{self.payment_term} #{self.sequence}"


class FinancialAccount(TimeStampedModel, AuditableModel, SoftDeleteModel):
    name = models.CharField(max_length=120)
    account_type = models.CharField(max_length=30, choices=AccountType.choices)
    bank_name = models.CharField(max_length=120, blank=True)
    branch = models.CharField(max_length=40, blank=True)
    account_reference = models.CharField(max_length=80, blank=True)
    initial_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    initial_balance_locked = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AccountsReceivable(TimeStampedModel, AuditableModel):
    number = models.CharField(max_length=30, unique=True, blank=True)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="receivables",
    )
    sales_order = models.ForeignKey(
        "production.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="receivables",
    )
    quote = models.ForeignKey(
        "quotes.Quote",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="receivables",
    )
    description = models.CharField(max_length=255)
    category = models.ForeignKey(
        FinancialCategory,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="receivables",
    )
    cost_center = models.ForeignKey(
        CostCenter,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="receivables",
    )
    payment_term = models.ForeignKey(
        PaymentTerm,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="receivables",
    )
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    original_amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[POSITIVE])
    discount_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    interest_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    penalty_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    adjustment_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    paid_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    outstanding_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    status = models.CharField(max_length=20, choices=TitleStatus.choices, default=TitleStatus.OPEN)
    cancel_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-issue_date", "-id"]
        indexes = [
            models.Index(fields=["status", "due_date"]),
            models.Index(fields=["customer", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["sales_order"],
                condition=Q(sales_order__isnull=False)
                & ~Q(status__in=["cancelled", "renegotiated", "written_off"]),
                name="unique_active_receivable_per_sales_order",
            ),
        ]

    def __str__(self):
        return self.number or f"Receivable #{self.pk}"

    @property
    def net_amount(self):
        return (
            self.original_amount
            - self.discount_amount
            + self.interest_amount
            + self.penalty_amount
            + self.adjustment_amount
        )


class ReceivableInstallment(TimeStampedModel):
    receivable = models.ForeignKey(
        AccountsReceivable,
        on_delete=models.CASCADE,
        related_name="installments",
    )
    sequence = models.PositiveSmallIntegerField()
    due_date = models.DateField()
    original_amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[POSITIVE])
    discount_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    interest_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    penalty_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    paid_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    outstanding_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    status = models.CharField(
        max_length=20,
        choices=InstallmentStatus.choices,
        default=InstallmentStatus.OPEN,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["sequence"]
        unique_together = [("receivable", "sequence")]

    def __str__(self):
        return f"{self.receivable.number}-{self.sequence}"


class ReceivablePayment(TimeStampedModel, AuditableModel):
    number = models.CharField(max_length=30, unique=True, blank=True)
    installment = models.ForeignKey(
        ReceivableInstallment,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[POSITIVE])
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name="receivable_payments",
    )
    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="receivable_payments",
    )
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.CONFIRMED,
    )
    reverse_reason = models.TextField(blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reversed_receivable_payments",
    )

    class Meta:
        ordering = ["-payment_date", "-id"]

    def __str__(self):
        return self.number or f"RCB #{self.pk}"


class AccountsPayable(TimeStampedModel, AuditableModel):
    number = models.CharField(max_length=30, unique=True, blank=True)
    supplier_name = models.CharField(max_length=180)
    material_supplier = models.ForeignKey(
        "materials.MaterialSupplier",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payables",
    )
    description = models.CharField(max_length=255)
    category = models.ForeignKey(
        FinancialCategory,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payables",
    )
    cost_center = models.ForeignKey(
        CostCenter,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payables",
    )
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    original_amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[POSITIVE])
    discount_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    interest_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    penalty_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    adjustment_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    paid_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    outstanding_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    status = models.CharField(max_length=20, choices=TitleStatus.choices, default=TitleStatus.OPEN)
    reference_type = models.CharField(max_length=80, blank=True)
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-issue_date", "-id"]
        indexes = [
            models.Index(fields=["status", "due_date"]),
        ]

    def __str__(self):
        return self.number or f"Payable #{self.pk}"

    @property
    def net_amount(self):
        return (
            self.original_amount
            - self.discount_amount
            + self.interest_amount
            + self.penalty_amount
            + self.adjustment_amount
        )


class PayableInstallment(TimeStampedModel):
    payable = models.ForeignKey(
        AccountsPayable,
        on_delete=models.CASCADE,
        related_name="installments",
    )
    sequence = models.PositiveSmallIntegerField()
    due_date = models.DateField()
    original_amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[POSITIVE])
    discount_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    interest_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    penalty_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    paid_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    outstanding_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[NON_NEGATIVE],
    )
    status = models.CharField(
        max_length=20,
        choices=InstallmentStatus.choices,
        default=InstallmentStatus.OPEN,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["sequence"]
        unique_together = [("payable", "sequence")]

    def __str__(self):
        return f"{self.payable.number}-{self.sequence}"


class PayablePayment(TimeStampedModel, AuditableModel):
    number = models.CharField(max_length=30, unique=True, blank=True)
    installment = models.ForeignKey(
        PayableInstallment,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[POSITIVE])
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name="payable_payments",
    )
    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="payable_payments",
    )
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.CONFIRMED,
    )
    reverse_reason = models.TextField(blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reversed_payable_payments",
    )

    class Meta:
        ordering = ["-payment_date", "-id"]

    def __str__(self):
        return self.number or f"PGT #{self.pk}"


class FinancialMovement(models.Model):
    """Ledger imutável — sem updated_at de edição."""

    number = models.CharField(max_length=30, unique=True, blank=True)
    movement_type = models.CharField(max_length=30, choices=MovementType.choices)
    financial_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    category = models.ForeignKey(
        FinancialCategory,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    cost_center = models.ForeignKey(
        CostCenter,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[POSITIVE])
    movement_date = models.DateField()
    description = models.CharField(max_length=255)
    reference_type = models.CharField(max_length=80, blank=True)
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    source_receivable_payment = models.ForeignKey(
        ReceivablePayment,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    source_payable_payment = models.ForeignKey(
        PayablePayment,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movements",
    )
    reversal_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversals",
    )
    transfer_group = models.CharField(max_length=40, blank=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_financial_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["movement_date", "id"]
        indexes = [
            models.Index(fields=["movement_date", "movement_type"]),
            models.Index(fields=["financial_account", "movement_date"]),
        ]

    def __str__(self):
        return self.number or f"MOV #{self.pk}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Movimento financeiro é imutável.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Movimento financeiro não pode ser apagado.")

    @property
    def signed_amount(self):
        if self.movement_type in EXPENSE_MOVEMENT_TYPES or (
            self.movement_type == MovementType.REVERSAL
            and self.reversal_of_id
            and self.reversal_of.movement_type in INCOME_MOVEMENT_TYPES
        ):
            return -self.amount
        if self.movement_type == MovementType.REVERSAL and self.reversal_of_id:
            # estorno de saída = entrada
            if self.reversal_of.movement_type in EXPENSE_MOVEMENT_TYPES:
                return self.amount
        if self.movement_type in INCOME_MOVEMENT_TYPES:
            return self.amount
        return self.amount
