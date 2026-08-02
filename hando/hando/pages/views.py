from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.template import TemplateDoesNotExist
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from assets.models import Asset
from audit.models import AuditEvent
from audit.models import UserSessionLog
from commercial.lead_models import Lead
from commercial.lead_models import LeadStatus
from commercial.lead_models import TERMINAL_STATUSES
from commercial.lead_queries import leads_queryset_for_user
from commercial.performance_metrics import active_goal_for_salesperson
from commercial.performance_metrics import compute_salesperson_metrics
from commercial.performance_metrics import team_summary
from commercial.performance_period import parse_performance_period
from commercial.performance_ranking import build_ranking
from customers.models import Customer
from fleet.models import Vehicle
from maintenance.models import MaintenanceOrder
from maintenance.models import MaintenancePlan
from production.models import DeliverySchedule
from production.models import InstallationSchedule
from production.models import ProductionOrder
from production.models import ProductionOrderStatus
from production.models import ProductionPieceStatus
from production.models import SalesOrder
from production.models import SalesOrderStatus
from production.selectors import overdue_production_orders
from production.selectors import sales_orders_queryset_for_user
from materials.stock_selectors import main_dashboard_stock_summary
from quotes.models import Quote
from salespeople.models import Salesperson


@login_required
def root_page_view(request):
    user = request.user
    user_model = get_user_model()
    cards = []
    card_specs = [
        (
            "Clientes ativos",
            "customers.view",
            Customer.objects.filter(is_active=True).count(),
            "users",
            "primary",
        ),
        (
            "Vendedores ativos",
            "salespeople.view",
            Salesperson.objects.filter(is_active=True).count(),
            "user-check",
            "secondary",
        ),
        (
            "Usuários ativos",
            "users.view",
            user_model.objects.filter(is_active=True).count(),
            "user",
            "success",
        ),
        (
            "Orçamentos em rascunho",
            "quotes.view",
            Quote.objects.filter(status="draft").count(),
            "file-text",
            "primary",
        ),
        (
            "Aguardando aprovação",
            "quotes.approve",
            Quote.objects.filter(status="pending_approval").count(),
            "clock",
            "warning",
        ),
        (
            "Aprovados",
            "quotes.view",
            Quote.objects.filter(status="approved").count(),
            "check-circle",
            "success",
        ),
        (
            "Enviados",
            "quotes.view",
            Quote.objects.filter(status="sent").count(),
            "send",
            "info",
        ),
        (
            "Ativos cadastrados",
            "assets.view",
            Asset.objects.filter(is_active=True).count(),
            "package",
            "warning",
        ),
        (
            "Veículos ativos",
            "vehicles.view",
            Vehicle.objects.filter(is_active=True).count(),
            "truck",
            "info",
        ),
        (
            "Manutenções abertas",
            "maintenance.view",
            MaintenanceOrder.objects.exclude(
                status__in=["completed", "cancelled"],
            ).count(),
            "tool",
            "danger",
        ),
        (
            "Manutenções vencidas",
            "maintenance.view",
            MaintenancePlan.objects.filter(
                is_active=True,
                next_due_date__lt=__import__(
                    "django.utils.timezone",
                ).utils.timezone.localdate(),
            ).count(),
            "alert-triangle",
            "danger",
        ),
        (
            "Sessões ativas",
            "audit.view",
            UserSessionLog.objects.filter(is_active=True).count(),
            "activity",
            "dark",
        ),
    ]
    open_leads = leads_queryset_for_user(user).exclude(status__in=TERMINAL_STATUSES)
    now = timezone.now()
    lead_specs = [
        ("Leads novos", "leads.view", open_leads.filter(status=LeadStatus.NEW).count(), "inbox", "primary"),
        ("Leads sem vendedor", "leads.view", open_leads.filter(assigned_salesperson__isnull=True).count(), "user-x", "warning"),
        ("Follow-ups vencidos", "leads.view", open_leads.filter(next_follow_up_at__lt=now).count(), "clock", "danger"),
        ("Negociações abertas", "leads.view", open_leads.filter(status=LeadStatus.NEGOTIATION).count(), "trending-up", "info"),
    ]
    production_specs = [
        (
            "Pedidos aguardando produção",
            "sales_orders.view",
            sales_orders_queryset_for_user(user).filter(
                status=SalesOrderStatus.READY_FOR_PRODUCTION,
            ).count(),
            "shopping-cart",
            "warning",
        ),
        (
            "Ordens em andamento",
            "production_orders.view",
            ProductionOrder.objects.filter(status=ProductionOrderStatus.IN_PROGRESS).count(),
            "cpu",
            "info",
        ),
        (
            "Ordens atrasadas",
            "production_orders.view",
            overdue_production_orders(user=user).count(),
            "alert-circle",
            "danger",
        ),
        (
            "Peças aguardando qualidade",
            "quality_inspections.view",
            ProductionOrder.objects.filter(
                pieces__status=ProductionPieceStatus.QUALITY_CONTROL,
            ).distinct().count(),
            "check-square",
            "warning",
        ),
        (
            "Entregas de hoje",
            "deliveries.view",
            DeliverySchedule.objects.filter(scheduled_date=timezone.localdate()).count(),
            "truck",
            "primary",
        ),
        (
            "Instalações de hoje",
            "installations.view",
            InstallationSchedule.objects.filter(scheduled_date=timezone.localdate()).count(),
            "tool",
            "secondary",
        ),
    ]
    card_specs.extend(lead_specs)
    card_specs.extend(production_specs)
    for label, permission, value, icon, color in card_specs:
        if user_has_permission(user, permission):
            cards.append({"label": label, "value": value, "icon": icon, "color": color})
    lead_links = []
    if user_has_permission(user, "leads.view"):
        lead_links = [
            {"label": "Dashboard Comercial", "url_name": "leads:dashboard"},
            {"label": "Funil Comercial", "url_name": "leads:funnel"},
        ]

    performance_summary = None
    if user_has_permission(user, "sales_performance.view_own") or user_has_permission(
        user,
        "sales_performance.view_all",
    ):
        class _Req:
            GET = {"period": "month"}

        start, end, _ = parse_performance_period(_Req())
        performance_summary = {"links": []}
        if user_has_permission(user, "sales_performance.view_own"):
            salesperson = getattr(user, "salesperson", None)
            if salesperson:
                metrics = compute_salesperson_metrics(
                    salesperson=salesperson,
                    start=start,
                    end=end,
                )
                goal = active_goal_for_salesperson(salesperson=salesperson)
                performance_summary["seller"] = {
                    "score": metrics["total_score"],
                    "goal_label": goal.period_type if goal else "Sem meta",
                    "overdue_followups": metrics["followups_overdue"],
                }
                performance_summary["links"].append(
                    {"label": "Meu Desempenho", "url_name": "leads:my_performance"},
                )
        if user_has_permission(user, "sales_performance.view_all"):
            summary = team_summary(user=user, start=start, end=end)
            ranking = build_ranking(user=user, start=start, end=end)
            top = ranking["rows"][0] if ranking["rows"] else None
            performance_summary["manager"] = {
                "team_score": summary["total_score"],
                "goals_at_risk": summary["goals_at_risk"],
                "top_seller": top["salesperson"].display_name if top else "-",
            }
            performance_summary["links"].append(
                {"label": "Desempenho da Equipe", "url_name": "leads:team_performance"},
            )
        if user_has_permission(user, "sales_ranking.view"):
            performance_summary["links"].append(
                {"label": "Ranking", "url_name": "leads:ranking"},
            )

    stock_summary = None
    if user_has_permission(user, "slabs.view") or user_has_permission(user, "stock_dashboard.view"):
        stock_summary = main_dashboard_stock_summary()

    context = {
        "cards": cards,
        "lead_links": lead_links,
        "performance_summary": performance_summary,
        "stock_summary": stock_summary,
        "latest_events": AuditEvent.objects.select_related("user")[:8]
        if user_has_permission(user, "audit.view")
        else [],
        "next_maintenance": MaintenancePlan.objects.filter(is_active=True).order_by(
            "next_due_date",
        )[:8]
        if user_has_permission(user, "maintenance.view")
        else [],
        "critical_orders": MaintenanceOrder.objects.filter(priority="critical").exclude(
            status__in=["completed", "cancelled"],
        )[:8]
        if user_has_permission(user, "maintenance.view")
        else [],
        "latest_sessions": UserSessionLog.objects.select_related("user")[:8]
        if user_has_permission(user, "audit.view")
        else [],
    }
    return render(request, "pages/index.html", context)


def dynamic_pages_view(request, template_name):
    try:
        return render(request, f"pages/{template_name}.html")
    except TemplateDoesNotExist:
        return render(request, "pages/error-404.html")
