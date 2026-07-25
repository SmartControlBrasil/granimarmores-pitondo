import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditEvent(models.Model):
    class EventType(models.TextChoices):
        AUTHENTICATION = "authentication", "Autenticação"
        AUTHORIZATION = "authorization", "Autorização"
        CREATE = "create", "Criação"
        UPDATE = "update", "Alteração"
        DEACTIVATE = "deactivate", "Desativação"
        REACTIVATE = "reactivate", "Reativação"
        DELETE = "delete", "Exclusão"
        VIEW = "view", "Visualização"
        EXPORT = "export", "Exportação"
        PRINT = "print", "Impressão"
        APPROVE = "approve", "Aprovação"
        SEND = "send", "Envio"
        CANCEL = "cancel", "Cancelamento"
        MAINTENANCE = "maintenance", "Manutenção"
        CONFIGURATION = "configuration", "Configuração"

    class Status(models.TextChoices):
        SUCCESS = "success", "Sucesso"
        DENIED = "denied", "Negado"
        FAILED = "failed", "Falhou"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
    )
    session_key = models.CharField(max_length=80, blank=True)
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    module = models.CharField(max_length=80)
    action = models.CharField(max_length=80)
    object_type = models.CharField(max_length=120, blank=True)
    object_id = models.CharField(max_length=120, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_method = models.CharField(max_length=12, blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SUCCESS,
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name = "evento de auditoria"
        verbose_name_plural = "eventos de auditoria"

    def __str__(self):
        return f"{self.occurred_at:%Y-%m-%d %H:%M} {self.module}.{self.action}"

    def save(self, *args, **kwargs):
        if self.pk and AuditEvent.objects.filter(pk=self.pk).exists():
            raise ValueError("Eventos de auditoria são append-only.")
        from audit.services import safe_metadata

        self.metadata = safe_metadata(self.metadata)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Eventos de auditoria não podem ser excluídos pela aplicação.")


class UserSessionLog(models.Model):
    class LogoutReason(models.TextChoices):
        MANUAL = "manual", "Manual"
        EXPIRED = "expired", "Expirada"
        REVOKED = "revoked", "Revogada"
        PASSWORD_CHANGED = "password_changed", "Senha alterada"
        USER_DEACTIVATED = "user_deactivated", "Usuário desativado"
        UNKNOWN = "unknown", "Desconhecida"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="session_logs",
    )
    session_key = models.CharField(max_length=80, db_index=True)
    login_at = models.DateTimeField(default=timezone.now)
    logout_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    logout_reason = models.CharField(
        max_length=30, choices=LogoutReason.choices, blank=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-login_at"]
        indexes = [models.Index(fields=["session_key", "is_active"])]
        verbose_name = "sessão de usuário"
        verbose_name_plural = "sessões de usuários"

    def __str__(self):
        return f"{self.user} - {self.session_key}"

    def close(self, reason=LogoutReason.UNKNOWN):
        self.is_active = False
        self.logout_at = timezone.now()
        self.logout_reason = reason
        self.save(update_fields=["is_active", "logout_at", "logout_reason"])
