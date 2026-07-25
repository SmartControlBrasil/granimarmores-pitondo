from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import RolePermission
from access_control.models import UserAccess
from access_control.permissions import PERMISSIONS
from assets.models import AssetCategory

INITIAL_ROLES = [
    {
        "name": "Administrativo",
        "hierarchy_level": 1,
        "has_full_access": True,
        "is_system": True,
        "scope": DataScope.ALL,
    },
    {
        "name": "Gestor Comercial",
        "hierarchy_level": 20,
        "has_full_access": False,
        "is_system": True,
        "scope": DataScope.TEAM,
    },
    {
        "name": "Vendedor",
        "hierarchy_level": 50,
        "has_full_access": False,
        "is_system": True,
        "scope": DataScope.OWN,
    },
    {
        "name": "Operacional",
        "hierarchy_level": 60,
        "has_full_access": False,
        "is_system": True,
        "scope": DataScope.OWN,
    },
    {
        "name": "Consulta",
        "hierarchy_level": 90,
        "has_full_access": False,
        "is_system": True,
        "scope": DataScope.OWN,
    },
]

ASSET_CATEGORIES = [
    "Máquinas",
    "Equipamentos",
    "Móveis",
    "Informática",
    "Ferramentas",
    "Instalações",
    "Outros",
]


class Command(BaseCommand):
    help = "Cria cargos, permissões e dados iniciais da fundação ERP."

    def add_arguments(self, parser):
        parser.add_argument("--admin-username", dest="admin_username", default=None)

    @transaction.atomic
    def handle(self, *args, **options):
        created_permissions = 0
        for code, name, module, action in PERMISSIONS:
            _, created = AccessPermission.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "module": module,
                    "action": action,
                    "is_active": True,
                },
            )
            created_permissions += int(created)

        roles = {}
        for item in INITIAL_ROLES:
            scope = item["scope"]
            role, _ = AccessRole.objects.update_or_create(
                slug=slugify(item["name"]),
                defaults={
                    "name": item["name"],
                    "hierarchy_level": item["hierarchy_level"],
                    "has_full_access": item["has_full_access"],
                    "is_system": item["is_system"],
                    "is_active": True,
                    "customer_scope": scope,
                    "quote_scope": scope,
                    "asset_scope": scope,
                    "maintenance_scope": scope,
                },
            )
            roles[item["name"]] = role

        admin_role = roles["Administrativo"]
        for permission in AccessPermission.objects.all():
            RolePermission.objects.update_or_create(
                role=admin_role,
                permission=permission,
                defaults={"allowed": True},
            )

        for category in ASSET_CATEGORIES:
            AssetCategory.objects.get_or_create(
                name=category,
                defaults={"is_active": True},
            )

        user_model = get_user_model()
        admin_username = options.get("admin_username")
        if admin_username:
            user = user_model.objects.get(username=admin_username)
        else:
            user = user_model.objects.filter(is_superuser=True).order_by("id").first()
        if user:
            UserAccess.objects.update_or_create(
                user=user,
                is_active=True,
                defaults={"role": admin_role, "valid_from": timezone.now()},
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Fundação ERP pronta. Permissões novas: {created_permissions}.",
            ),
        )
