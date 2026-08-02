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
from commercial.models import ChannelGroup
from commercial.models import CommercialSource
from commercial.models import ContactChannel
from commercial.models import LossCategory
from commercial.models import LossReason
from commercial.models import ProjectType

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

MATERIAL_CATEGORIES = [
    "Granito",
    "Mármore",
    "Quartzito",
    "Quartzo industrializado",
    "Porcelanato",
    "Ultracompacto",
    "Revestimento",
    "Insumo",
    "Outros",
]

FINISH_TYPES = [
    "Polido",
    "Escovado",
    "Levigado",
    "Boleado",
    "Meia esquadria",
    "Saia",
    "Frontão",
    "Rodabanca",
    "Canal úmido",
    "Furo de cuba",
    "Furo de torneira",
    "Recorte de cooktop",
]
ADDITIONAL_SERVICES = [
    "Medição técnica",
    "Transporte",
    "Instalação",
    "Remoção de bancada",
    "Descarte",
    "Içamento",
    "Visita adicional",
    "Impermeabilização",
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

COMMERCIAL_SOURCE_SEEDS = [
    ("Google orgânico", ChannelGroup.ORGANIC, 10),
    ("Google Meu Negócio", ChannelGroup.ORGANIC, 20),
    ("Instagram", ChannelGroup.SOCIAL, 30),
    ("Facebook", ChannelGroup.SOCIAL, 40),
    ("WhatsApp direto", ChannelGroup.DIRECT, 50),
    ("Indicação", ChannelGroup.REFERRAL, 60),
    ("Cliente antigo", ChannelGroup.REFERRAL, 70),
    ("Arquiteto parceiro", ChannelGroup.PARTNER, 80),
    ("Construtora parceira", ChannelGroup.PARTNER, 90),
    ("Marcenaria parceira", ChannelGroup.PARTNER, 100),
    ("Loja de planejados", ChannelGroup.PARTNER, 110),
    ("Tráfego pago", ChannelGroup.PAID, 120),
    ("Acesso direto", ChannelGroup.DIRECT, 130),
    ("Outro", ChannelGroup.OTHER, 999),
]

CONTACT_CHANNEL_SEEDS = [
    ("WhatsApp", 10),
    ("Telefone", 20),
    ("E-mail", 30),
    ("Formulário do site", 40),
    ("Instagram", 50),
    ("Atendimento presencial", 60),
    ("Lívia", 70),
    ("Outro", 999),
]

PROJECT_TYPE_SEEDS = [
    ("Pia de cozinha", True, True, 10),
    ("Bancada", True, True, 20),
    ("Lavatório", True, True, 30),
    ("Escada", True, True, 40),
    ("Soleira", True, True, 50),
    ("Peitoril", True, True, 60),
    ("Área gourmet", True, True, 70),
    ("Balcão", True, True, 80),
    ("Mesa", True, True, 90),
    ("Revestimento", True, True, 100),
    ("Projeto comercial", True, True, 110),
    ("Restauração", True, False, 120),
    ("Manutenção e polimento", False, False, 130),
    ("Outro projeto sob medida", True, True, 999),
]

LOSS_REASON_SEEDS = [
    ("Preço", LossCategory.PRICE, 10),
    ("Prazo", LossCategory.DEADLINE, 20),
    ("Escolheu concorrente", LossCategory.COMPETITOR, 30),
    ("Cliente não respondeu", LossCategory.NO_RESPONSE, 40),
    ("Projeto cancelado", LossCategory.PROJECT_CANCELLED, 50),
    ("Material indisponível", LossCategory.MATERIAL_UNAVAILABLE, 60),
    ("Fora da área de atendimento", LossCategory.OUTSIDE_SERVICE_AREA, 70),
    ("Inviabilidade técnica", LossCategory.TECHNICAL_INFEASIBILITY, 80),
    ("Condição de pagamento", LossCategory.CREDIT_OR_PAYMENT, 90),
    ("Cadastro duplicado", LossCategory.DUPLICATE, 100),
    ("Outro", LossCategory.OTHER, 999),
]

COMMERCIAL_MASTER_VIEW = [
    "commercial_sources.view",
    "project_types.view",
    "commercial_partners.view",
    "loss_reasons.view",
    "service_regions.view",
    "contact_channels.view",
]

COMMERCIAL_MASTER_EDIT = [
    *COMMERCIAL_MASTER_VIEW,
    "commercial_sources.create",
    "commercial_sources.update",
    "commercial_sources.deactivate",
    "project_types.create",
    "project_types.update",
    "project_types.deactivate",
    "commercial_partners.create",
    "commercial_partners.update",
    "commercial_partners.deactivate",
    "loss_reasons.create",
    "loss_reasons.update",
    "loss_reasons.deactivate",
    "service_regions.create",
    "service_regions.update",
    "service_regions.deactivate",
    "contact_channels.create",
    "contact_channels.update",
    "contact_channels.deactivate",
]

SYSTEM_ROLE_PERMISSIONS = {
    "Gestor Comercial": COMMERCIAL_MASTER_EDIT,
    "Vendedor": COMMERCIAL_MASTER_VIEW,
    "Operacional": ["project_types.view", "service_regions.view"],
}


def _assign_role_permissions(role, codes):
    for code in codes:
        permission = AccessPermission.objects.filter(code=code).first()
        if permission:
            RolePermission.objects.get_or_create(
                role=role,
                permission=permission,
                defaults={"allowed": True},
            )


def _seed_commercial_sources():
    created = updated = 0
    for name, group, order in COMMERCIAL_SOURCE_SEEDS:
        slug = slugify(name)
        _, was_created = CommercialSource.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "channel_group": group,
                "display_order": order,
                "is_active": True,
            },
        )
        created += int(was_created)
        updated += int(not was_created)
    return created, updated


def _seed_contact_channels():
    created = updated = 0
    for name, order in CONTACT_CHANNEL_SEEDS:
        slug = slugify(name)
        _, was_created = ContactChannel.objects.update_or_create(
            slug=slug,
            defaults={"name": name, "display_order": order, "is_active": True},
        )
        created += int(was_created)
        updated += int(not was_created)
    return created, updated


def _seed_project_types():
    created = updated = 0
    for name, requires_measurement, allows_installation, order in PROJECT_TYPE_SEEDS:
        slug = slugify(name)
        _, was_created = ProjectType.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "requires_measurement": requires_measurement,
                "allows_installation": allows_installation,
                "display_order": order,
                "is_active": True,
            },
        )
        created += int(was_created)
        updated += int(not was_created)
    return created, updated


def _seed_loss_reasons():
    created = updated = 0
    for name, category, order in LOSS_REASON_SEEDS:
        slug = slugify(name)
        _, was_created = LossReason.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "category": category,
                "display_order": order,
                "is_active": True,
            },
        )
        created += int(was_created)
        updated += int(not was_created)
    return created, updated


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

        for role_name, codes in SYSTEM_ROLE_PERMISSIONS.items():
            role = roles.get(role_name)
            if role:
                _assign_role_permissions(role, codes)

        source_created, source_updated = _seed_commercial_sources()
        channel_created, channel_updated = _seed_contact_channels()
        project_created, project_updated = _seed_project_types()
        loss_created, loss_updated = _seed_loss_reasons()

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
                "Fundação ERP pronta. "
                f"Permissões novas: {created_permissions}. "
                f"Origens: +{source_created}/~{source_updated}. "
                f"Canais: +{channel_created}/~{channel_updated}. "
                f"Tipos: +{project_created}/~{project_updated}. "
                f"Motivos: +{loss_created}/~{loss_updated}.",
            ),
        )
