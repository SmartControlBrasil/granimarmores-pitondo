from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditableModel(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_%(class)s_set",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_%(class)s_set",
    )

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    is_active = models.BooleanField(default=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="deactivated_%(class)s_set",
    )

    class Meta:
        abstract = True

    def deactivate(self, user=None):
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.deactivated_by = user
        self.save(
            update_fields=[
                "is_active",
                "deactivated_at",
                "deactivated_by",
                "updated_at",
            ],
        )

    def reactivate(self, user=None):
        self.is_active = True
        self.deactivated_at = None
        self.deactivated_by = None
        self.save(
            update_fields=[
                "is_active",
                "deactivated_at",
                "deactivated_by",
                "updated_at",
            ],
        )
