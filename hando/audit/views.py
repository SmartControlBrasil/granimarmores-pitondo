from django.core.paginator import Paginator
from django.shortcuts import render

from access_control.services.authorization import require_permission
from audit.models import AuditEvent


@require_permission("audit.view")
def audit_list(request):
    qs = AuditEvent.objects.select_related("user").all()
    page_obj = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "audit/audit_list.html",
        {"page_title": "Auditoria", "page_obj": page_obj},
    )
