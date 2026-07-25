from django.core.paginator import Paginator
from django.shortcuts import render

from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.services.authorization import require_permission


@require_permission("roles.view")
def role_list(request):
    page_obj = Paginator(AccessRole.objects.all(), 20).get_page(request.GET.get("page"))
    return render(
        request,
        "access_control/role_list.html",
        {"page_title": "Cargos e níveis de acesso", "page_obj": page_obj},
    )


@require_permission("roles.view")
def permission_list(request):
    page_obj = Paginator(AccessPermission.objects.all(), 30).get_page(
        request.GET.get("page"),
    )
    return render(
        request,
        "access_control/permission_list.html",
        {"page_title": "Permissões", "page_obj": page_obj},
    )
