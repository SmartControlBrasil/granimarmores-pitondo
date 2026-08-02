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

AFTER_SALES_VIEW = [
    "after_sales_dashboard.view",
    "after_sales_cases.view",
    "installation_pending_items.view",
    "warranties.view",
    "customer_satisfaction.view",
    "review_requests.view",
    "media_usage_consents.view",
    "customer_referrals.view",
]

AFTER_SALES_SELLER = [
    *AFTER_SALES_VIEW,
    "after_sales_cases.create",
    "after_sales_cases.update",
    "customer_satisfaction.create",
    "customer_satisfaction.update",
    "review_requests.create",
    "review_requests.update",
    "media_usage_consents.create",
    "customer_referrals.create",
    "customer_referrals.convert",
]

AFTER_SALES_MANAGER = [
    *AFTER_SALES_SELLER,
    "after_sales_cases.view_all",
    "after_sales_cases.assign",
    "after_sales_cases.change_status",
    "after_sales_cases.close",
    "after_sales_cases.reopen",
    "after_sales_cases.reject",
    "after_sales_cases.cancel",
    "warranties.create",
    "warranties.update",
    "installation_pending_items.create",
    "installation_pending_items.update",
    "media_usage_consents.update",
    "customer_referrals.update",
]

AFTER_SALES_OPERATIONS = [
    *AFTER_SALES_VIEW,
    "after_sales_cases.view_all",
    "after_sales_cases.create",
    "after_sales_cases.update",
    "after_sales_cases.assign",
    "after_sales_cases.change_status",
    "after_sales_cases.diagnose",
    "after_sales_cases.resolve",
    "after_sales_cases.close",
    "after_sales_cases.reopen",
    "installation_pending_items.create",
    "installation_pending_items.update",
    "warranties.view",
]

AFTER_SALES_PRODUCTION = [
    "after_sales_cases.view",
    "after_sales_cases.diagnose",
    "after_sales_cases.update",
    "installation_pending_items.view",
]

MEDIA_VIEW = [
    "media_dashboard.view",
    "media_assets.view",
    "media_collections.view",
    "media_portfolio.view",
]

MEDIA_SELLER = [
    *MEDIA_VIEW,
    "media_assets.upload",
    "media_assets.classify",
    "media_collections.create",
    "media_collections.update",
]

MEDIA_MANAGER = [
    *MEDIA_SELLER,
    "media_assets.view_all",
    "media_assets.update",
    "media_assets.review",
    "media_assets.approve",
    "media_assets.reject",
    "media_assets.archive",
    "media_portfolio.approve",
    "media_publication_candidates.view",
    "media_publication_candidates.create",
    "media_publication_candidates.update",
    "media_private_files.view",
]

MEDIA_OPERATIONS = [
    *MEDIA_VIEW,
    "media_assets.upload",
    "media_assets.classify",
    "media_assets.update",
    "media_private_files.view",
]

MEDIA_CATEGORY_SEEDS = [
    ("Antes da obra", "antes-da-obra", True, True, 10),
    ("Durante a produção", "durante-a-producao", False, False, 20),
    ("Material", "material", False, True, 30),
    ("Chapa", "chapa", False, False, 40),
    ("Corte", "corte", False, False, 50),
    ("Acabamento", "acabamento", False, False, 60),
    ("Polimento", "polimento", False, False, 70),
    ("Qualidade", "qualidade", False, False, 80),
    ("Peça concluída", "peca-concluida", False, True, 90),
    ("Entrega", "entrega", True, False, 100),
    ("Instalação", "instalacao", True, True, 110),
    ("Obra concluída", "obra-concluida", True, True, 120),
    ("Depois da obra", "depois-da-obra", True, True, 130),
    ("Pendência", "pendencia", False, False, 140),
    ("Assistência técnica", "assistencia-tecnica", False, False, 150),
    ("Garantia", "garantia", False, False, 160),
    ("Retrabalho", "retrabalho", False, False, 170),
    ("Portfólio", "portfolio", True, True, 180),
    ("Documento técnico", "documento-tecnico", False, False, 190),
    ("Outro", "outro", False, False, 200),
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
] + STOCK_COMMERCIAL_VIEW + SCHEDULE_MANAGER + AFTER_SALES_MANAGER + MEDIA_MANAGER

ORDERS_SELLER = [
    "quotes.accept",
    "quotes.refuse",
    "sales_orders.view",
    "production_orders.view",
    "production_dashboard.view",
    "deliveries.view",
    "installations.view",
] + STOCK_SELLER_VIEW + SCHEDULE_SELLER + AFTER_SALES_SELLER + MEDIA_SELLER

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
] + SCHEDULE_OPERATIONS + AFTER_SALES_OPERATIONS + AFTER_SALES_PRODUCTION + MEDIA_OPERATIONS

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

EXECUTIVE_FULL = [
    "executive_dashboard.view",
    "executive_dashboard.view_commercial",
    "executive_dashboard.view_sales_values",
    "executive_dashboard.view_production",
    "executive_dashboard.view_stock",
    "executive_dashboard.view_stock_costs",
    "executive_dashboard.view_schedule",
    "executive_dashboard.view_after_sales",
    "executive_dashboard.view_quality",
    "executive_dashboard.view_audit",
    "executive_dashboard.view_finance",
    "executive_dashboard.export",
    "executive_dashboard.print",
]

EXECUTIVE_COMMERCIAL = [
    "executive_dashboard.view_commercial",
    "executive_dashboard.view_sales_values",
    "executive_dashboard.view_production",
    "executive_dashboard.view_schedule",
    "executive_dashboard.view_after_sales",
    "executive_dashboard.view_finance",
    "executive_dashboard.export",
    "executive_dashboard.print",
]

FINANCE_FULL = [
    "finance_dashboard.view",
    "accounts_receivable.view",
    "accounts_receivable.create",
    "accounts_receivable.update",
    "accounts_receivable.cancel",
    "accounts_receivable.receive",
    "accounts_receivable.reverse_payment",
    "accounts_receivable.renegotiate",
    "accounts_payable.view",
    "accounts_payable.create",
    "accounts_payable.update",
    "accounts_payable.cancel",
    "accounts_payable.pay",
    "accounts_payable.reverse_payment",
    "financial_movements.view",
    "financial_movements.adjust",
    "financial_movements.transfer",
    "financial_accounts.view",
    "financial_accounts.create",
    "financial_accounts.update",
    "financial_categories.view",
    "financial_categories.create",
    "financial_categories.update",
    "cost_centers.view",
    "cost_centers.create",
    "cost_centers.update",
    "payment_methods.view",
    "payment_methods.create",
    "payment_methods.update",
    "payment_terms.view",
    "payment_terms.create",
    "payment_terms.update",
    "finance_cash_flow.view",
    "finance_overdue.view",
    "finance_values.view",
    "finance_export",
]

FINANCE_COMMERCIAL = [
    "finance_dashboard.view",
    "accounts_receivable.view",
    "accounts_receivable.create",
    "finance_overdue.view",
    "payment_terms.view",
    "payment_methods.view",
]

FINANCE_SELLER = [
    "accounts_receivable.view",
]

PURCHASING_FULL = [
    "purchasing_dashboard.view",
    "purchase_requests.view",
    "purchase_requests.create",
    "purchase_requests.update",
    "purchase_requests.submit",
    "purchase_requests.approve",
    "purchase_requests.reject",
    "purchase_requests.cancel",
    "supplier_quotations.view",
    "supplier_quotations.create",
    "supplier_quotations.update",
    "supplier_quotations.cancel",
    "purchase_orders.view",
    "purchase_orders.create",
    "purchase_orders.update",
    "purchase_orders.approve",
    "purchase_orders.cancel",
    "purchase_receipts.view",
    "purchase_receipts.create",
    "purchase_receipts.inspect",
    "purchase_receipts.accept",
    "purchase_receipts.reject",
    "purchase_receipts.override_quantity",
    "purchase_divergences.view",
    "purchase_divergences.update",
    "purchase_returns.view",
    "purchase_returns.create",
    "purchase_returns.approve",
    "purchasing_values.view",
    "purchasing_costs.view",
    "purchasing_generate_payable",
    "executive_dashboard.view_purchasing",
]

PURCHASING_OPERATIONS = [
    "purchasing_dashboard.view",
    "purchase_requests.view",
    "purchase_requests.create",
    "purchase_requests.submit",
    "supplier_quotations.view",
    "purchase_orders.view",
    "purchase_receipts.view",
    "purchase_receipts.create",
    "purchase_receipts.inspect",
    "purchase_receipts.accept",
    "purchase_divergences.view",
    "purchase_returns.view",
    "purchase_returns.create",
]

PURCHASING_FINANCE = [
    "purchase_orders.view",
    "purchase_receipts.view",
    "purchasing_generate_payable",
    "purchasing_values.view",
]

COMMISSIONS_MANAGER = [
    "commission_dashboard.view",
    "commission_policies.view",
    "commission_policies.create",
    "commission_policies.update",
    "commission_policies.activate",
    "commission_events.view",
    "commission_events.adjust",
    "commission_events.reverse",
    "commission_settlements.view",
    "commission_settlements.create",
    "commission_settlements.approve",
    "commission_settlements.cancel",
    "commission_values.view",
    "commission_partner_values.view",
    "executive_dashboard.view_commissions",
]

COMMISSIONS_SELLER = [
    "commission_events.view_own",
]

COMMISSIONS_FINANCE = [
    "commission_settlements.view",
    "commission_settlements.generate_payable",
    "commission_payments.view",
    "commission_payments.create",
    "commission_payments.reverse",
    "commission_values.view",
]

DOCUMENTS_MANAGER = [
    "document_dashboard.view",
    "documents.view",
    "documents.view_all",
    "documents.create",
    "documents.update",
    "documents.submit_review",
    "documents.approve",
    "documents.reject",
    "documents.send",
    "documents.accept",
    "documents.reject_acceptance",
    "documents.register_signature",
    "documents.cancel",
    "documents.terminate",
    "documents.renew",
    "documents.archive",
    "documents.print",
    "documents.export",
    "document_templates.view",
    "document_templates.create",
    "document_templates.update",
    "document_templates.approve",
    "document_templates.deactivate",
    "document_types.view",
    "document_types.create",
    "document_types.update",
    "document_reviews.view",
    "document_reviews.decide",
    "document_confidential.view",
    "executive_dashboard.view_documents",
]

DOCUMENTS_SELLER = [
    "documents.view",
    "documents.create",
    "documents.update",
    "documents.send",
    "documents.print",
    "document_templates.view",
    "document_types.view",
]

DOCUMENTS_OPERATIONS = [
    "documents.view",
    "documents.create",
    "documents.update",
    "documents.print",
    "document_types.view",
]

DOCUMENT_TYPE_SEEDS = [
    ("Proposta Comercial", "proposta-comercial", "commercial", 10, True, False, False, False, None, False),
    ("Contrato de Prestação de Serviços", "contrato-prestacao-servicos", "contract", 20, True, True, True, True, 365, True),
    ("Termo de Aceite", "termo-de-aceite", "commercial", 30, True, True, False, False, None, False),
    ("Termo de Entrega", "termo-de-entrega", "operational", 40, True, True, False, False, None, False),
    ("Termo de Instalação", "termo-de-instalacao", "operational", 50, True, True, False, False, None, False),
    ("Autorização de Uso de Imagem", "autorizacao-uso-imagem", "consent", 60, True, True, False, True, 730, False),
    ("Relatório Técnico", "relatorio-tecnico", "technical", 70, True, False, False, False, None, False),
    ("Laudo de Inspeção", "laudo-de-inspecao", "technical", 80, True, False, False, False, None, False),
    ("Documento de Garantia", "documento-de-garantia", "warranty", 90, True, False, False, True, 365, False),
    ("Contrato de Fornecedor", "contrato-de-fornecedor", "supplier", 100, True, True, True, True, 365, True),
    ("Documento Interno", "documento-interno", "internal", 110, False, False, False, False, None, False),
]

EXECUTIVE_OPERATIONS = [
    "executive_dashboard.view_production",
    "executive_dashboard.view_stock",
    "executive_dashboard.view_quality",
    "executive_dashboard.view_schedule",
    "executive_dashboard.export",
]

SYSTEM_ROLE_PERMISSIONS = {
    "Gestor Comercial": COMMERCIAL_MASTER_EDIT
    + LEADS_MANAGER
    + PERFORMANCE_MANAGER
    + ORDERS_MANAGER
    + EXECUTIVE_COMMERCIAL
    + FINANCE_COMMERCIAL
    + COMMISSIONS_MANAGER
    + DOCUMENTS_MANAGER,
    "Vendedor": COMMERCIAL_MASTER_VIEW
    + LEADS_SELLER
    + PERFORMANCE_SELLER
    + ORDERS_SELLER
    + FINANCE_SELLER
    + COMMISSIONS_SELLER
    + DOCUMENTS_SELLER,
    "Operacional": ["project_types.view", "service_regions.view", "leads.view"]
    + PRODUCTION_OPERATIONS
    + STOCK_OPERATIONS
    + EXECUTIVE_OPERATIONS
    + PURCHASING_OPERATIONS
    + DOCUMENTS_OPERATIONS,
}

FINANCE_CATEGORY_SEEDS = [
    ("Venda de peças", "venda-de-pecas", "income", 10),
    ("Instalação", "instalacao", "income", 20),
    ("Medição técnica", "medicao-tecnica", "income", 30),
    ("Transporte", "transporte-receita", "income", 40),
    ("Manutenção", "manutencao-receita", "income", 50),
    ("Restauração", "restauracao", "income", 60),
    ("Outras receitas", "outras-receitas", "income", 70),
    ("Compra de material", "compra-de-material", "expense", 110),
    ("Comissões Comerciais", "comissoes-comerciais", "expense", 115),
    ("Frete", "frete", "expense", 120),
    ("Combustível", "combustivel", "expense", 130),
    ("Ferramentas", "ferramentas", "expense", 140),
    ("Manutenção", "manutencao-despesa", "expense", 150),
    ("Terceiros", "terceiros", "expense", 160),
    ("Aluguel", "aluguel", "expense", 170),
    ("Energia", "energia", "expense", 180),
    ("Marketing", "marketing-despesa", "expense", 190),
    ("Despesas administrativas", "despesas-administrativas", "expense", 200),
    ("Outras despesas", "outras-despesas", "expense", 210),
]

COST_CENTER_SEEDS = [
    ("Comercial", "comercial"),
    ("Produção", "producao"),
    ("Instalação", "instalacao"),
    ("Entrega", "entrega"),
    ("Administrativo", "administrativo"),
    ("Marketing", "marketing"),
    ("Manutenção", "manutencao"),
]

PAYMENT_METHOD_SEEDS = [
    ("Dinheiro", "dinheiro", "cash", False, False, 1),
    ("PIX", "pix", "pix", True, False, 1),
    ("Transferência bancária", "transferencia", "bank_transfer", True, False, 1),
    ("Cartão de crédito", "cartao-credito", "credit_card", True, True, 12),
    ("Cartão de débito", "cartao-debito", "debit_card", True, False, 1),
    ("Cheque", "cheque", "check", True, False, 1),
    ("Boleto (manual)", "boleto-manual", "boleto_manual", True, True, 12),
    ("Outro", "outro", "other", False, False, 1),
]

PAYMENT_TERM_SEEDS = [
    ("À vista", "Pagamento integral na emissão", 1, "0", 0, 0, False),
    ("50% entrada + 50% na entrega", "Metade na emissão e metade na entrega", 2, "50", 0, 30, False),
    ("30% entrada + 70% na instalação", "Entrada e saldo na instalação", 2, "30", 0, 45, False),
    ("2 parcelas", "Duas parcelas iguais", 2, "0", 0, 30, False),
    ("3 parcelas", "Três parcelas iguais", 3, "0", 0, 30, False),
    ("Personalizada", "Condição sob medida", 1, "0", 0, 0, True),
]


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


def _seed_document_types():
    from documents.models import DocumentType

    created = updated = 0
    for (
        name,
        code,
        category,
        order,
        requires_approval,
        requires_acceptance,
        requires_signature,
        has_validity,
        validity_days,
        allows_renewal,
    ) in DOCUMENT_TYPE_SEEDS:
        _, was_created = DocumentType.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "category": category,
                "display_order": order,
                "requires_internal_approval": requires_approval,
                "requires_customer_acceptance": requires_acceptance,
                "requires_signature": requires_signature,
                "has_validity": has_validity,
                "default_validity_days": validity_days,
                "allows_renewal": allows_renewal,
                "is_active": True,
                "description": "",
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


def _seed_media_categories():
    from media_library.models import MediaCategory

    created = updated = 0
    for name, slug, requires_consent, portfolio, order in MEDIA_CATEGORY_SEEDS:
        _, was_created = MediaCategory.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "display_order": order,
                "requires_consent": requires_consent,
                "is_portfolio_eligible": portfolio,
                "is_active": True,
            },
        )
        created += int(was_created)
        updated += int(not was_created)
    return created, updated


def _seed_finance_masters():
    from decimal import Decimal

    from finance.models import CostCenter
    from finance.models import FinancialCategory
    from finance.models import PaymentMethod
    from finance.models import PaymentTerm

    cat_c = cat_u = 0
    for name, code, ctype, order in FINANCE_CATEGORY_SEEDS:
        _, created = FinancialCategory.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "category_type": ctype,
                "display_order": order,
                "is_active": True,
            },
        )
        cat_c += int(created)
        cat_u += int(not created)

    cc_c = cc_u = 0
    for name, code in COST_CENTER_SEEDS:
        _, created = CostCenter.objects.update_or_create(
            code=code,
            defaults={"name": name, "is_active": True},
        )
        cc_c += int(created)
        cc_u += int(not created)

    pm_c = pm_u = 0
    for name, code, mtype, req_ref, allows, max_inst in PAYMENT_METHOD_SEEDS:
        _, created = PaymentMethod.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "method_type": mtype,
                "requires_reference": req_ref,
                "allows_installments": allows,
                "maximum_installments": max_inst,
                "is_active": True,
            },
        )
        pm_c += int(created)
        pm_u += int(not created)

    pt_c = pt_u = 0
    for name, desc, count, down, first, interval, custom in PAYMENT_TERM_SEEDS:
        _, created = PaymentTerm.objects.update_or_create(
            name=name,
            defaults={
                "description": desc,
                "installment_count": count,
                "down_payment_percent": Decimal(down),
                "first_due_days": first,
                "interval_days": interval,
                "is_custom": custom,
                "is_active": True,
            },
        )
        pt_c += int(created)
        pt_u += int(not created)
    return (cat_c, cat_u, cc_c, cc_u, pm_c, pm_u, pt_c, pt_u)


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
        media_cat_created, media_cat_updated = _seed_media_categories()
        (
            fin_cat_c,
            fin_cat_u,
            fin_cc_c,
            fin_cc_u,
            fin_pm_c,
            fin_pm_u,
            fin_pt_c,
            fin_pt_u,
        ) = _seed_finance_masters()
        doc_type_c, doc_type_u = _seed_document_types()

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
                f"Itens checklist qualidade novos: {quality_items}. "
                f"Categorias mídia: +{media_cat_created}/~{media_cat_updated}. "
                f"Financeiro cat:+{fin_cat_c}/~{fin_cat_u} "
                f"centros:+{fin_cc_c}/~{fin_cc_u} "
                f"formas:+{fin_pm_c}/~{fin_pm_u} "
                f"condições:+{fin_pt_c}/~{fin_pt_u}. "
                f"Tipos documento:+{doc_type_c}/~{doc_type_u}."
                f"{policy_note}"
            ),
        )
