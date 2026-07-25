from django.core.paginator import Paginator
from django.shortcuts import render

from access_control.services.authorization import require_permission
from fleet.models import Vehicle


@require_permission("vehicles.view")
def list_view(request):
    qs = Vehicle.objects.all().order_by("plate")
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request, "fleet/list.html", {"page_title": "Veículos", "page_obj": page_obj},
    )
