from django.core.paginator import Paginator
from django.shortcuts import render

from access_control.services.authorization import require_permission
from maintenance.models import MaintenanceOrder
from maintenance.models import MaintenancePlan


@require_permission("maintenance.view")
def order_list(request):
    page_obj = Paginator(MaintenanceOrder.objects.all(), 20).get_page(
        request.GET.get("page"),
    )
    return render(
        request,
        "maintenance/order_list.html",
        {"page_title": "Ordens de manutenção", "page_obj": page_obj},
    )


@require_permission("maintenance.view")
def plan_list(request):
    page_obj = Paginator(MaintenancePlan.objects.all(), 20).get_page(
        request.GET.get("page"),
    )
    return render(
        request,
        "maintenance/plan_list.html",
        {"page_title": "Planos preventivos", "page_obj": page_obj},
    )
