from django.apps import AppConfig


class InstitutionalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "src.institutional.infrastructure.django"
    label = "institutional"
    verbose_name = "Site Institucional"
