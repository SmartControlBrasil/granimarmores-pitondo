from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.template import TemplateDoesNotExist

from access_control.services.authorization import user_has_permission
from assets.models import Asset
from audit.models import AuditEvent
from audit.models import UserSessionLog
from customers.models import Customer
from fleet.models import Vehicle
from maintenance.models import MaintenanceOrder
from maintenance.models import MaintenancePlan
from salespeople.models import Salesperson


@login_required
def root_page_view(request):
    user = request.user
    User = get_user_model()
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
            User.objects.filter(is_active=True).count(),
            "user",
            "success",
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
    for label, permission, value, icon, color in card_specs:
        if user_has_permission(user, permission):
            cards.append({"label": label, "value": value, "icon": icon, "color": color})
    context = {
        "cards": cards,
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
