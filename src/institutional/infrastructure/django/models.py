"""
Models persistentes do módulo institucional.

As regras centrais do negócio devem permanecer em domain/.
"""

from django.db import models


class ContactRequest(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Novo"
        CONTACTED = "contacted", "Contatado"
        QUALIFIED = "qualified", "Qualificado"
        CLOSED = "closed", "Fechado"
        DISCARDED = "discarded", "Descartado"

    nome = models.CharField("nome", max_length=160)
    email = models.EmailField("e-mail", blank=True)
    telefone = models.CharField("telefone", max_length=40)
    cidade = models.CharField("cidade", max_length=120)
    ambiente = models.CharField("ambiente/projeto", max_length=80)
    medidas = models.TextField("medidas/informações técnicas", blank=True)
    mensagem = models.TextField("mensagem")
    status = models.CharField(
        "status",
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )
    source_path = models.CharField("origem", max_length=255, blank=True)
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.TextField("user-agent", blank=True)
    notification_sent_at = models.DateTimeField(
        "notificação enviada em",
        null=True,
        blank=True,
    )
    notification_error = models.TextField("erro de notificação", blank=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "solicitação de contato"
        verbose_name_plural = "solicitações de contato"

    def __str__(self):
        return f"{self.nome} - {self.telefone}"
