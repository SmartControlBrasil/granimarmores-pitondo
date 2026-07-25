from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import AuditableModel
from core.models import TimeStampedModel


class DataScope(models.TextChoices):
    OWN = "own", "Próprios"
    TEAM = "team", "Equipe"
    DEPARTMENT = "department", "Departamento"
    ALL = "all", "Todos"


class AccessRole(TimeStampedModel, AuditableModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True, max_length=140)
    description = models.TextField(blank=True)
    hierarchy_level = models.PositiveIntegerField(default=100)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    has_full_access = models.BooleanField(default=False)
    customer_scope = models.CharField(
        max_length=20, choices=DataScope.choices, default=DataScope.OWN,
    )
    quote_scope = models.CharField(
        max_length=20, choices=DataScope.choices, default=DataScope.OWN,
    )
    asset_scope = models.CharField(
        max_length=20, choices=DataScope.choices, default=DataScope.OWN,
    )
    maintenance_scope = models.CharField(
        max_length=20, choices=DataScope.choices, default=DataScope.OWN,
    )

    class Meta:
        ordering = ["hierarchy_level", "name"]
        verbose_name = "cargo de acesso"
        verbose_name_plural = "cargos de acesso"

    def __str__(self):
        return self.name


class AccessPermission(models.Model):
    code = models.CharField(max_length=120, unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    module = models.CharField(max_length=80)
    action = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["module", "code"]
        verbose_name = "permissão"
        verbose_name_plural = "permissões"

    def __str__(self):
        return self.code


class RolePermission(models.Model):
    role = models.ForeignKey(
        AccessRole, on_delete=models.CASCADE, related_name="role_permissions",
    )
    permission = models.ForeignKey(
        AccessPermission, on_delete=models.CASCADE, related_name="role_permissions",
    )
    allowed = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"], name="unique_role_permission",
            ),
        ]
        verbose_name = "permissão do cargo"
        verbose_name_plural = "permissões dos cargos"

    def __str__(self):
        return f"{self.role} - {self.permission}: {self.allowed}"


class UserAccess(TimeStampedModel, AuditableModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="access_assignments",
    )
    role = models.ForeignKey(
        AccessRole, on_delete=models.PROTECT, related_name="user_assignments",
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_access_assignments",
    )
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_active=True),
                name="unique_active_access_per_user",
            ),
        ]
        verbose_name = "acesso do usuário"
        verbose_name_plural = "acessos dos usuários"

    def __str__(self):
        return f"{self.user} - {self.role}"

    def clean(self):
        errors = {}
        if self.manager_id and self.user_id and self.manager_id == self.user_id:
            errors["manager"] = "O usuário não pode ser seu próprio gestor."
        if self.role_id and not self.role.is_active:
            errors["role"] = "Não é permitido vincular cargo inativo."
        if self.valid_until and self.valid_from and self.valid_until <= self.valid_from:
            errors["valid_until"] = "A vigência final deve ser posterior ao início."
        if errors:
            raise ValidationError(errors)

    @property
    def is_current(self):
        now = timezone.now()
        return (
            self.is_active
            and self.valid_from <= now
            and (self.valid_until is None or self.valid_until > now)
        )
