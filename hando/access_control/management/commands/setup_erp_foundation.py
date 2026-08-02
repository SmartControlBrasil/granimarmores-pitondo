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

LEADS_SELLER = [
    "leads.view",
    "leads.create",
    "leads.update",
    "leads.change_status",
    "leads.convert",
    "leads.mark_won",
    "leads.mark_lost",
    "lead_activities.view",
    "lead_activities.create",
    "lead_tasks.view",
    "lead_tasks.create",
    "lead_tasks.complete",
]

LEADS_MANAGER = [
    *LEADS_SELLER,
    "leads.view_all",
    "leads.view_unassigned",
    "leads.assign",
    "leads.override_status",
    "leads.reopen",
    "lead_tasks.update",
    "lead_tasks.cancel",
    "lead_tasks.reopen",
    "lead_tasks.reassign",
]

PERFORMANCE_SELLER = [
    "sales_performance.view_own",
    "sales_ranking.view",
    "sales_score_events.view",
]

PERFORMANCE_MANAGER = [
    *PERFORMANCE_SELLER,
    "sales_performance.view_all",
    "sales_goals.view",
    "sales_goals.create",
    "sales_goals.update",
    "sales_goals.deactivate",
    "sales_score_events.view",
]

STOCK_VIEW = [
    "stock_dashboard.view",
    "slabs.view",
    "slab_reservations.view",
    "slab_remnants.view",
    "stock_movements.view",
    "stock_locations.view",
    "material_suppliers.view",
    "stock_inventory.view",
]

STOCK_COMMERCIAL_VIEW = [
    "stock_dashboard.view",
    "slabs.view",
    "slab_reservations.view",
]

STOCK_SELLER_VIEW = [
    "slabs.view",
]

STOCK_OPERATIONS = [
    *STOCK_VIEW,
    "slabs.create",
    "slabs.transfer",
    "slab_reservations.reserve",
    "slab_reservations.release",
    "slab_consumption.consume",
    "slab_losses.create",
    "slab_remnants.create",
    "slab_remnants.update",
    "stock_inventory.inventory",
    "slab_reservations.override_cut",
]

STOCK_MANAGER = [
    *STOCK_OPERATIONS,
    "slabs.block",
    "slabs.unblock",
    "slabs.update",
    "stock_locations.create",
    "stock_locations.update",
    "material_suppliers.create",
    "material_suppliers.update",
    "stock_inventory.create",
    "stock_inventory.approve_inventory",
    "stock_adjustments.execute",
    "stock_costs.view",
]

SCHEDULE_VIEW = [
    "operational_events.view",
    "schedule_dashboard.view",
    "schedule_calendar.view",
    "schedule_measurements.view",
]

SCHEDULE_SELLER = [
    *SCHEDULE_VIEW,
    "operational_events.create",
    "operational_events.confirm",
    "operational_events.complete",
    "operational_events.reschedule",
    "operational_events.cancel",
    "schedule_measurements.create",
]

SCHEDULE_MANAGER = [
    *SCHEDULE_SELLER,
    "operational_events.view_all",
    "operational_events.update",
    "operational_events.assign",
    "operational_events.start",
    "operational_events.override_conflict",
    "schedule_measurements.update",
]

SCHEDULE_OPERATIONS = [
    *SCHEDULE_VIEW,
    "operational_events.view_all",
    "operational_events.create",
    "operational_events.update",
    "operational_events.assign",
    "operational_events.confirm",
    "operational_events.start",
    "operational_events.complete",
    "operational_events.reschedule",
    "operational_events.cancel",
    "schedule_measurements.create",
    "schedule_measurements.update",
]

ORDERS_MANAGER = [
    "quotes.accept",
    "quotes.refuse",
    "quotes.accept_expired",
    "sales_orders.view",
    "sales_orders.create",
    "sales_orders.update",
    "sales_orders.change_status",
    "sales_orders.cancel",
    "production_orders.view",
    "production_dashboard.view",
    "deliveries.view",
    "deliveries.schedule",
    "deliveries.complete",
    "installations.view",
    "installations.schedule",
    "installations.complete",
] + STOCK_COMMERCIAL_VIEW + SCHEDULE_MANAGER

ORDERS_SELLER = [
    "quotes.accept",
    "quotes.refuse",
    "sales_orders.view",
    "production_orders.view",
    "production_dashboard.view",
    "deliveries.view",
    "installations.view",
] + STOCK_SELLER_VIEW + SCHEDULE_SELLER

PRODUCTION_OPERATIONS = [
    "sales_orders.view",
    "production_orders.view",
    "production_orders.create",
    "production_orders.update",
    "production_orders.change_status",
    "production_orders.start",
    "production_orders.pause",
    "production_orders.complete",
    "production_orders.cancel",
    "production_orders.assign",
    "production_pieces.view",
    "production_pieces.create",
    "production_pieces.update",
    "production_stages.view",
    "production_stages.create",
    "production_stages.update",
    "production_stages.start",
    "production_stages.complete",
    "production_stages.skip",
    "production_logs.view",
    "production_logs.create",
    "quality_inspections.view",
    "quality_inspections.create",
    "quality_inspections.inspect",
    "quality_inspections.approve",
    "quality_inspections.reject",
    "deliveries.view",
    "installations.view",
    "production_dashboard.view",
] + SCHEDULE_OPERATIONS

PRODUCTION_STAGE_SEEDS = [
    ("Medição final", "medicao-final", "waiting", 10),
    ("Conferência técnica", "conferencia-tecnica", "conferencia", 20),
    ("Separação do material", "separacao-material", "material", 30),
    ("Corte", "corte", "corte", 40),
    ("Acabamento", "acabamento", "acabamento", 50),
    ("Polimento", "polimento", "polimento", 60),
    ("Furação", "furacao", "furacao", 70),
    ("Colagem de cuba", "colagem-cuba", "furacao", 80),
    ("Conferência de qualidade", "conferencia-qualidade", "qualidade", 90, True),
    ("Liberação para entrega", "liberacao-entrega", "pronto", 100),
    ("Entrega", "entrega", "entrega", 110),
    ("Instalação", "instalacao", "instalacao", 120),
    ("Finalização", "finalizacao", "concluido", 130),
]

QUALITY_CHECKLIST_ITEMS = [
    "Medidas conferidas",
    "Material conferido",
    "Acabamento conferido",
    "Bordas conferidas",
    "Recortes conferidos",
    "Furações conferidas",
    "Cuba conferida",
    "Polimento aprovado",
    "Peça limpa",
    "Peça identificada",
    "Embalagem aprovada",
    "Fotos registradas",
]

SYSTEM_ROLE_PERMISSIONS = {
    "Gestor Comercial": COMMERCIAL_MASTER_EDIT + LEADS_MANAGER + PERFORMANCE_MANAGER + ORDERS_MANAGER,
    "Vendedor": COMMERCIAL_MASTER_VIEW + LEADS_SELLER + PERFORMANCE_SELLER + ORDERS_SELLER,
    "Operacional": ["project_types.view", "service_regions.view", "leads.view"] + PRODUCTION_OPERATIONS + STOCK_OPERATIONS,
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


def _seed_production_stages():
    from production.models import ProductionStage

    created = updated = 0
    for row in PRODUCTION_STAGE_SEEDS:
        name, slug, board_column, order = row[:4]
        requires_qc = row[4] if len(row) > 4 else False
        _, was_created = ProductionStage.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "board_column": board_column,
                "display_order": order,
                "is_active": True,
                "is_required": True,
                "requires_quality_check": requires_qc,
            },
        )
        created += int(was_created)
        updated += int(not was_created)
    return created, updated


def _seed_quality_checklist():
    from production.models import QualityChecklist
    from production.models import QualityChecklistItem

    checklist, _ = QualityChecklist.objects.update_or_create(
        slug="padrao",
        defaults={"name": "Checklist padrão de qualidade", "is_active": True},
    )
    created = 0
    for order, label in enumerate(QUALITY_CHECKLIST_ITEMS, start=1):
        _, was_created = QualityChecklistItem.objects.update_or_create(
            checklist=checklist,
            label=label,
            defaults={"display_order": order, "is_required": True},
        )
        created += int(was_created)
    return created


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
        stage_created, stage_updated = _seed_production_stages()
        quality_items = _seed_quality_checklist()

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

        from commercial.performance_score import create_default_score_policy

        _, policy_created = create_default_score_policy(actor=user)

        policy_note = f" Política score: {'criada' if policy_created else 'existente'}."
        self.stdout.write(
            self.style.SUCCESS(
                "Fundação ERP pronta. "
                f"Permissões novas: {created_permissions}. "
                f"Origens: +{source_created}/~{source_updated}. "
                f"Canais: +{channel_created}/~{channel_updated}. "
                f"Tipos: +{project_created}/~{project_updated}. "
                f"Motivos: +{loss_created}/~{loss_updated}. "
                f"Etapas produção: +{stage_created}/~{stage_updated}. "
                f"Itens checklist qualidade novos: {quality_items}."
                f"{policy_note}"
            ),
        )
