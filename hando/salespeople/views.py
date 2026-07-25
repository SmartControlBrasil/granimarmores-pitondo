from django.core.paginator import Paginator
from django.shortcuts import render

from access_control.services.authorization import require_permission
from salespeople.models import Salesperson


@require_permission("salespeople.view")
def list_view(request):
    qs = Salesperson.objects.all().order_by("display_name")
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "salespeople/list.html",
        {"page_title": "Vendedores", "page_obj": page_obj},
    )
