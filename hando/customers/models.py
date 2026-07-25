# ruff: noqa: EM101, TRY003
import re

from django.core.exceptions import ValidationError
from django.db import models

from core.models import AuditableModel
from core.models import SoftDeleteModel
from core.models import TimeStampedModel


def only_digits(value):
    return re.sub(r"\D", "", value or "")


def validate_cpf_cnpj(value):
    digits = only_digits(value)
    if digits and len(digits) not in (11, 14):
        raise ValidationError("Informe um CPF ou CNPJ válido.")


class Customer(TimeStampedModel, AuditableModel, SoftDeleteModel):
    class CustomerType(models.TextChoices):
        INDIVIDUAL = "individual", "Pessoa física"
        COMPANY = "company", "Pessoa jurídica"

    customer_type = models.CharField(max_length=20, choices=CustomerType.choices)
    name = models.CharField(max_length=180)
    trade_name = models.CharField(max_length=180, blank=True)
    document = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        validators=[validate_cpf_cnpj],
    )
    state_registration = models.CharField(max_length=40, blank=True)
    municipal_registration = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    mobile_phone = models.CharField(max_length=30, blank=True)
    website = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    assigned_salesperson = models.ForeignKey(
        "salespeople.Salesperson",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="customers",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"

    def __str__(self):
        return self.name

    def clean(self):
        if self.document:
            self.document = only_digits(self.document)
            validate_cpf_cnpj(self.document)

    def save(self, *args, **kwargs):
        if self.document:
            self.document = only_digits(self.document)
        super().save(*args, **kwargs)


class CustomerAddress(models.Model):
    class AddressType(models.TextChoices):
        MAIN = "main", "Principal"
        BILLING = "billing", "Cobrança"
        DELIVERY = "delivery", "Entrega"
        WORKSITE = "worksite", "Obra"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    address_type = models.CharField(
        max_length=20,
        choices=AddressType.choices,
        default=AddressType.MAIN,
    )
    postal_code = models.CharField(max_length=12, blank=True)
    street = models.CharField(max_length=180)
    number = models.CharField(max_length=30, blank=True)
    complement = models.CharField(max_length=120, blank=True)
    district = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=2)
    country = models.CharField(max_length=80, default="Brasil")
    is_primary = models.BooleanField(default=False)

    class Meta:
        verbose_name = "endereço do cliente"
        verbose_name_plural = "endereços dos clientes"

    def __str__(self):
        return f"{self.street}, {self.number} - {self.city}/{self.state}"
