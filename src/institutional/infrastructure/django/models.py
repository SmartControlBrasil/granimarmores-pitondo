"""
Models persistentes do módulo institucional.

As regras centrais do negócio devem permanecer em domain/.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


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
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_contact_requests",
        verbose_name="responsável",
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
        permissions = [
            ("assign_contactrequest", "Pode atribuir solicitações de contato"),
        ]

    def __str__(self):
        return f"{self.nome} - {self.telefone}"


class ContactRequestNote(models.Model):
    contact_request = models.ForeignKey(
        ContactRequest,
        on_delete=models.CASCADE,
        related_name="notes",
        verbose_name="solicitação",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contact_request_notes",
        verbose_name="autor",
    )
    content = models.TextField("observação")
    created_at = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "observação interna"
        verbose_name_plural = "observações internas"

    def __str__(self):
        return f"Nota de {self.author or 'sistema'} em {self.created_at:%d/%m/%Y}"


class ContactRequestAuditLog(models.Model):
    class Action(models.TextChoices):
        LEAD_CREATED = "lead_created", "Lead criado"
        STATUS_CHANGED = "status_changed", "Status alterado"
        ASSIGNED = "assigned", "Responsável atribuído"
        NOTE_ADDED = "note_added", "Observação adicionada"

    contact_request = models.ForeignKey(
        ContactRequest,
        on_delete=models.CASCADE,
        related_name="audit_logs",
        verbose_name="solicitação",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contact_request_audit_logs",
        verbose_name="usuário",
    )
    action = models.CharField("ação", max_length=40, choices=Action.choices)
    previous_value = models.TextField("valor anterior", blank=True)
    new_value = models.TextField("valor novo", blank=True)
    source = models.CharField("origem", max_length=80, blank=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "histórico da solicitação"
        verbose_name_plural = "históricos das solicitações"

    def __str__(self):
        return f"{self.get_action_display()} - {self.contact_request_id}"



class Opportunity(models.Model):
    class Stage(models.TextChoices):
        QUALIFICATION = "qualification", "Qualificação"
        QUOTATION = "quotation", "Orçamento"
        QUOTATION_SENT = "quotation_sent", "Orçamento enviado"
        NEGOTIATION = "negotiation", "Negociação"
        WON = "won", "Ganho"
        LOST = "lost", "Perdido"

    class LostReason(models.TextChoices):
        PRICE = "price", "Preço"
        DEADLINE = "deadline", "Prazo"
        COMPETITION = "competition", "Concorrência"
        CUSTOMER_GAVE_UP = "customer_gave_up", "Cliente desistiu"
        NO_RESPONSE = "no_response", "Sem retorno"
        TECHNICALLY_UNFEASIBLE = "technically_unfeasible", "Inviável tecnicamente"
        OTHER = "other", "Outro"

    contact_request = models.OneToOneField(ContactRequest, on_delete=models.PROTECT, related_name="opportunity", verbose_name="lead de origem")
    title = models.CharField("título/projeto", max_length=160)
    customer_name = models.CharField("cliente", max_length=160)
    customer_email = models.EmailField("e-mail", blank=True)
    customer_phone = models.CharField("telefone", max_length=40)
    city = models.CharField("cidade", max_length=120)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_opportunities", verbose_name="responsável")
    stage = models.CharField("etapa", max_length=30, choices=Stage.choices, default=Stage.QUALIFICATION)
    estimated_value = models.DecimalField("valor estimado", max_digits=12, decimal_places=2, default=0)
    probability = models.PositiveSmallIntegerField("probabilidade", default=20, validators=[MinValueValidator(0), MaxValueValidator(100)])
    expected_close_date = models.DateField("previsão de fechamento", null=True, blank=True)
    notes = models.TextField("observações", blank=True)
    lost_reason = models.CharField("motivo da perda", max_length=40, choices=LostReason.choices, blank=True)
    lost_notes = models.TextField("observações da perda", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_opportunities", verbose_name="criado por")
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "oportunidade comercial"
        verbose_name_plural = "oportunidades comerciais"

    def __str__(self):
        return f"{self.customer_name} - {self.title}"


class OpportunityAuditLog(models.Model):
    class Action(models.TextChoices):
        OPPORTUNITY_CREATED = "opportunity_created", "Oportunidade criada"
        STAGE_CHANGED = "stage_changed", "Etapa alterada"
        RESPONSIBLE_CHANGED = "responsible_changed", "Responsável alterado"
        ESTIMATED_VALUE_CHANGED = "estimated_value_changed", "Valor estimado alterado"
        QUOTE_CREATED = "quote_created", "Orçamento criado"
        QUOTE_SENT = "quote_sent", "Orçamento enviado"
        QUOTE_ACCEPTED = "quote_accepted", "Orçamento aceito"
        QUOTE_REJECTED = "quote_rejected", "Orçamento rejeitado"
        QUOTE_DOCUMENT_GENERATED = "quote_document_generated", "Documento de orçamento gerado"
        QUOTE_DOCUMENT_VOIDED = "quote_document_voided", "Documento de orçamento anulado"
        QUOTE_DELIVERY_REQUESTED = "quote_delivery_requested", "Envio de orçamento solicitado"
        QUOTE_SEND_FAILED = "quote_send_failed", "Envio de orçamento falhou"
        QUOTE_RESENT = "quote_resent", "Orçamento reenviado"
        QUOTE_REVISION_CREATED = "quote_revision_created", "Revisão de orçamento criada"

    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="audit_logs", verbose_name="oportunidade")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="opportunity_audit_logs", verbose_name="usuário")
    action = models.CharField("ação", max_length=50, choices=Action.choices)
    previous_value = models.TextField("valor anterior", blank=True)
    new_value = models.TextField("valor novo", blank=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "histórico da oportunidade"
        verbose_name_plural = "históricos das oportunidades"

    def __str__(self):
        return f"{self.get_action_display()} - {self.opportunity_id}"


class QuoteSequence(models.Model):
    year = models.PositiveIntegerField("ano", unique=True)
    next_number = models.PositiveIntegerField("próximo número", default=1)

    class Meta:
        verbose_name = "sequência de orçamento"
        verbose_name_plural = "sequências de orçamento"

    def __str__(self):
        return f"{self.year}: {self.next_number}"


class Quote(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        READY = "ready", "Pronto"
        SENT = "sent", "Enviado"
        ACCEPTED = "accepted", "Aceito"
        REJECTED = "rejected", "Rejeitado"
        EXPIRED = "expired", "Expirado"
        CANCELLED = "cancelled", "Cancelado"

    opportunity = models.ForeignKey(Opportunity, on_delete=models.PROTECT, related_name="quotes", verbose_name="oportunidade")
    number = models.CharField("número", max_length=20)
    revision = models.PositiveIntegerField("revisão", default=0)
    status = models.CharField("status", max_length=20, choices=Status.choices, default=Status.DRAFT)
    subtotal = models.DecimalField("subtotal", max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField("desconto", max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField("total", max_digits=12, decimal_places=2, default=0)
    validity_date = models.DateField("validade", null=True, blank=True)
    notes = models.TextField("observações", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_quotes", verbose_name="criado por")
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["-created_at", "-revision"]
        constraints = [models.UniqueConstraint(fields=["number", "revision"], name="unique_quote_number_revision")]
        verbose_name = "orçamento"
        verbose_name_plural = "orçamentos"

    def __str__(self):
        return f"{self.number} rev. {self.revision}"


class QuoteItem(models.Model):
    class Unit(models.TextChoices):
        UNIT = "un", "un"
        METER = "m", "m"
        SQUARE_METER = "m2", "m²"
        CUBIC_METER = "m3", "m³"
        SERVICE = "service", "serviço"

    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="items", verbose_name="orçamento")
    description = models.CharField("descrição", max_length=255)
    quantity = models.DecimalField("quantidade", max_digits=10, decimal_places=3, validators=[MinValueValidator(0.001)])
    unit = models.CharField("unidade", max_length=20, choices=Unit.choices, default=Unit.UNIT)
    unit_price = models.DecimalField("preço unitário", max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    total = models.DecimalField("total", max_digits=12, decimal_places=2, default=0)
    position = models.PositiveIntegerField("ordem", default=0)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = "item de orçamento"
        verbose_name_plural = "itens de orçamento"

    def __str__(self):
        return self.description


def quote_document_upload_to(instance, filename):
    year = instance.generated_at.year if instance.generated_at else timezone.localdate().year
    return f"quotes/{year}/{instance.quote.number}/{filename}"


class QuoteDocument(models.Model):
    class Status(models.TextChoices):
        GENERATED = "generated", "Gerado"
        SENT = "sent", "Enviado"
        VOID = "void", "Anulado"

    quote = models.ForeignKey(Quote, on_delete=models.PROTECT, related_name="documents", verbose_name="orçamento")
    revision = models.PositiveIntegerField("revisão")
    document_number = models.CharField("documento", max_length=40)
    status = models.CharField("status", max_length=20, choices=Status.choices, default=Status.GENERATED)
    snapshot_data = models.JSONField("snapshot")
    snapshot_fingerprint = models.CharField("fingerprint", max_length=64)
    file = models.FileField("arquivo", upload_to=quote_document_upload_to, blank=True)
    checksum = models.CharField("checksum SHA-256", max_length=64, blank=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="generated_quote_documents", verbose_name="gerado por")
    generated_at = models.DateTimeField("gerado em", auto_now_add=True)
    sent_at = models.DateTimeField("enviado em", null=True, blank=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]
        constraints = [
            models.UniqueConstraint(fields=["quote", "revision", "snapshot_fingerprint"], name="unique_quote_document_snapshot"),
        ]
        verbose_name = "documento de orçamento"
        verbose_name_plural = "documentos de orçamento"

    def __str__(self):
        return self.document_number


class QuoteDelivery(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "E-mail"
        WHATSAPP = "whatsapp", "WhatsApp"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        SENT = "sent", "Enviado"
        FAILED = "failed", "Falhou"
        CANCELLED = "cancelled", "Cancelado"

    quote = models.ForeignKey(Quote, on_delete=models.PROTECT, related_name="deliveries", verbose_name="orçamento")
    document = models.ForeignKey(QuoteDocument, on_delete=models.PROTECT, related_name="deliveries", verbose_name="documento")
    channel = models.CharField("canal", max_length=20, choices=Channel.choices, default=Channel.EMAIL)
    recipient = models.EmailField("destinatário")
    status = models.CharField("status", max_length=20, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="requested_quote_deliveries", verbose_name="solicitado por")
    requested_at = models.DateTimeField("solicitado em", auto_now_add=True)
    sent_at = models.DateTimeField("enviado em", null=True, blank=True)
    error_message = models.TextField("erro", blank=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        ordering = ["-requested_at"]
        verbose_name = "entrega de orçamento"
        verbose_name_plural = "entregas de orçamento"

    def __str__(self):
        return f"{self.document} - {self.recipient}"
