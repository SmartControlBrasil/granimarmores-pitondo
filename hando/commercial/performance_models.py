# ruff: noqa: EM101, TRY003
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import AuditableModel
from core.models import TimeStampedModel
from materials.models import validate_non_negative
from materials.models import validate_percentage


class GoalPeriodType(models.TextChoices):
    WEEKLY = "weekly", "Semanal"
    MONTHLY = "monthly", "Mensal"
    QUARTERLY = "quarterly", "Trimestral"
    YEARLY = "yearly", "Anual"
    CUSTOM = "custom", "Personalizado"


class SalesGoal(TimeStampedModel, AuditableModel):
    salesperson = models.ForeignKey(
        "salespeople.Salesperson",
        on_delete=models.PROTECT,
        related_name="sales_goals",
    )
    period_type = models.CharField(max_length=20, choices=GoalPeriodType.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    lead_goal = models.PositiveIntegerField(default=0)
    contact_goal = models.PositiveIntegerField(default=0)
    quote_goal = models.PositiveIntegerField(default=0)
    won_lead_goal = models.PositiveIntegerField(default=0)
    sales_value_goal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[validate_non_negative],
    )
    conversion_goal = models.PositiveSmallIntegerField(
        default=0,
        validators=[validate_percentage],
    )
    response_time_goal_minutes = models.PositiveIntegerField(default=0)
    follow_up_compliance_goal = models.PositiveSmallIntegerField(
        default=0,
        validators=[validate_percentage],
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-start_date", "salesperson__display_name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="sales_goal_valid_date_range",
            ),
            models.UniqueConstraint(
                fields=["salesperson", "period_type", "start_date", "end_date"],
                condition=models.Q(is_active=True),
                name="unique_active_sales_goal_period",
            ),
        ]
        indexes = [
            models.Index(fields=["salesperson", "is_active"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self):
        return f"Meta {self.salesperson} ({self.start_date} — {self.end_date})"

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError("Data final não pode ser anterior à inicial.")
        if self.conversion_goal > 100 or self.follow_up_compliance_goal > 100:
            raise ValidationError("Metas percentuais devem estar entre 0 e 100.")


class SalesScorePolicy(TimeStampedModel, AuditableModel):
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    valid_from = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    points_lead_created = models.IntegerField(default=0)
    points_first_contact = models.IntegerField(default=10)
    points_lead_qualified = models.IntegerField(default=5)
    points_measurement_completed = models.IntegerField(default=5)
    points_quote_created = models.IntegerField(default=0)
    points_quote_sent = models.IntegerField(default=20)
    points_follow_up_completed = models.IntegerField(default=10)
    points_lead_won = models.IntegerField(default=50)
    points_sales_value_factor = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=Decimal("0.0000"),
    )
    penalty_overdue_follow_up = models.PositiveIntegerField(default=5)
    penalty_unattended_lead = models.PositiveIntegerField(default=10)
    penalty_lost_without_reason = models.PositiveIntegerField(default=10)
    maximum_daily_score = models.PositiveIntegerField(
        default=0,
        help_text="0 = sem limite diário",
    )

    class Meta:
        ordering = ["-valid_from", "-pk"]
        verbose_name_plural = "Políticas de score comercial"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valid_until__isnull=True)
                | models.Q(valid_until__gte=models.F("valid_from")),
                name="score_policy_valid_date_range",
            ),
        ]

    def __str__(self):
        status = "ativa" if self.is_active else "inativa"
        return f"{self.name} ({status})"

    def clean(self):
        if self.valid_until and self.valid_until < self.valid_from:
            raise ValidationError("Vigência final inválida.")
        if self.is_active:
            overlap = SalesScorePolicy.objects.filter(is_active=True).exclude(pk=self.pk)
            for other in overlap:
                if self._overlaps(other):
                    raise ValidationError(
                        f"Sobreposição com política ativa: {other.name}.",
                    )

    def _overlaps(self, other):
        self_end = self.valid_until or timezone.localdate().replace(year=9999)
        other_end = other.valid_until or timezone.localdate().replace(year=9999)
        return self.valid_from <= other_end and other.valid_from <= self_end


class ScoreEventType(models.TextChoices):
    LEAD_CREATED = "lead_created", "Lead criado"
    FIRST_CONTACT = "first_contact", "Primeiro contato"
    LEAD_QUALIFIED = "lead_qualified", "Lead qualificado"
    MEASUREMENT_COMPLETED = "measurement_completed", "Medição concluída"
    QUOTE_CREATED = "quote_created", "Orçamento criado"
    QUOTE_SENT = "quote_sent", "Orçamento enviado"
    FOLLOW_UP_COMPLETED = "follow_up_completed", "Follow-up concluído"
    LEAD_WON = "lead_won", "Lead ganho"
    SALES_VALUE_BONUS = "sales_value_bonus", "Bônus por valor vendido"
    OVERDUE_FOLLOW_UP_PENALTY = "overdue_follow_up_penalty", "Follow-up vencido"
    UNATTENDED_LEAD_PENALTY = "unattended_lead_penalty", "Lead sem resposta"
    LOST_WITHOUT_REASON_PENALTY = "lost_without_reason_penalty", "Perda sem motivo"
    MANUAL_ADJUSTMENT = "manual_adjustment", "Ajuste manual"


class SalesScoreEvent(models.Model):
    salesperson = models.ForeignKey(
        "salespeople.Salesperson",
        on_delete=models.PROTECT,
        related_name="score_events",
    )
    event_type = models.CharField(max_length=40, choices=ScoreEventType.choices)
    points = models.IntegerField()
    reference_type = models.CharField(max_length=40, blank=True)
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    reference_label = models.CharField(max_length=200, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    period_date = models.DateField(default=timezone.localdate)
    description = models.TextField(blank=True)
    policy = models.ForeignKey(
        SalesScorePolicy,
        on_delete=models.PROTECT,
        related_name="events",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_score_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-pk"]
        indexes = [
            models.Index(fields=["salesperson", "period_date"]),
            models.Index(fields=["event_type", "occurred_at"]),
            models.Index(fields=["reference_type", "reference_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["salesperson", "event_type", "reference_type", "reference_id"],
                condition=models.Q(reference_id__isnull=False),
                name="unique_score_event_reference",
            ),
        ]

    def __str__(self):
        sign = "+" if self.points >= 0 else ""
        return f"{self.salesperson} {sign}{self.points} ({self.get_event_type_display()})"
