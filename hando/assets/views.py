from django.core.paginator import Paginator
from django.shortcuts import render

from access_control.services.authorization import require_permission
from assets.models import Asset


@require_permission("assets.view")
def list_view(request):
    qs = Asset.objects.all().order_by("name")
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request, "assets/list.html", {"page_title": "Ativos", "page_obj": page_obj},
    )
