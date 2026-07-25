from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import AuditableModel
from core.models import TimeStampedModel


class Salesperson(TimeStampedModel, AuditableModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="salesperson",
    )
    code = models.CharField(max_length=40, unique=True)
    display_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    hire_date = models.DateField(null=True, blank=True)
    termination_date = models.DateField(null=True, blank=True)
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    manager = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="team_members",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_name"]
        verbose_name = "vendedor"
        verbose_name_plural = "vendedores"

    def __str__(self):
        return self.display_name

    def clean(self):
        if self.manager_id and self.manager_id == self.pk:
            raise ValidationError(
                {"manager": "O vendedor não pode ser seu próprio gestor."},
            )
