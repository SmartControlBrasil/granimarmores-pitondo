from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import AuditableModel
from core.models import TimeStampedModel


class UserProfile(TimeStampedModel, AuditableModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    full_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    job_title = models.CharField(max_length=120, blank=True)
    employee_code = models.CharField(max_length=60, blank=True, unique=True, null=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True)
    must_change_password = models.BooleanField(default=False)
    last_password_change_at = models.DateTimeField(null=True, blank=True)
    is_operational_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["user__username"]
        verbose_name = "perfil de usuário"
        verbose_name_plural = "perfis de usuários"

    def __str__(self):
        return self.full_name or self.user.get_username()

    def mark_password_changed(self):
        self.last_password_change_at = timezone.now()
        self.must_change_password = False
        self.save(
            update_fields=[
                "last_password_change_at",
                "must_change_password",
                "updated_at",
            ],
        )
