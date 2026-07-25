from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.shortcuts import render

from access_control.services.authorization import require_permission
from audit.models import UserSessionLog

User = get_user_model()


@require_permission("users.view")
def user_list(request):
    qs = User.objects.all().order_by("username")
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/user_list.html",
        {"page_title": "Usuários", "page_obj": page_obj},
    )


@require_permission("users.view")
def session_list(request):
    qs = UserSessionLog.objects.select_related("user").all()
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/session_list.html",
        {"page_title": "Sessões de usuários", "page_obj": page_obj},
    )
