from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from access_control.services.authorization import require_permission
from audit.models import AuditEvent
from salespeople.forms import SalespersonForm
from salespeople.models import Salesperson
from salespeople.services import create_salesperson
from salespeople.services import set_salesperson_active
from salespeople.services import update_salesperson


@require_permission("salespeople.view")
def list_view(request):
    qs = Salesperson.objects.select_related("user", "manager").order_by("display_name")
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(display_name__icontains=search)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "salespeople/list.html",
        {"page_title": "Vendedores", "page_obj": page_obj, "search": search},
    )


@require_permission("salespeople.view")
def detail_view(request, pk):
    salesperson = get_object_or_404(
        Salesperson.objects.select_related("user", "manager"),
        pk=pk,
    )
    recent_events = AuditEvent.objects.filter(
        object_type="Salesperson",
        object_id=str(salesperson.pk),
    )[:10]
    return render(
        request,
        "salespeople/detail.html",
        {
            "page_title": salesperson.display_name,
            "salesperson": salesperson,
            "recent_events": recent_events,
        },
    )


@require_permission("salespeople.create")
def create_view(request):
    form = SalespersonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            salesperson = create_salesperson(
                form=form,
                actor=request.user,
                request=request,
            )
        except PermissionDenied as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Vendedor criado com sucesso.")
            return redirect("salespeople:detail", pk=salesperson.pk)
    return render(
        request,
        "salespeople/form.html",
        {"page_title": "Novo vendedor", "form": form},
    )


@require_permission("salespeople.update")
def update_view(request, pk):
    salesperson = get_object_or_404(Salesperson, pk=pk)
    form = SalespersonForm(request.POST or None, instance=salesperson)
    if request.method == "POST" and form.is_valid():
        try:
            salesperson = update_salesperson(
                salesperson=salesperson,
                form=form,
                actor=request.user,
                request=request,
            )
        except PermissionDenied as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Vendedor atualizado com sucesso.")
            return redirect("salespeople:detail", pk=salesperson.pk)
    return render(
        request,
        "salespeople/form.html",
        {"page_title": f"Editar {salesperson.display_name}", "form": form},
    )


@require_permission("salespeople.deactivate")
def deactivate_view(request, pk):
    salesperson = get_object_or_404(Salesperson, pk=pk)
    if request.method == "POST":
        set_salesperson_active(
            salesperson=salesperson,
            is_active=False,
            actor=request.user,
            request=request,
        )
        messages.success(request, "Vendedor desativado com sucesso.")
        return redirect("salespeople:detail", pk=salesperson.pk)
    return render(
        request,
        "erp/confirm_action.html",
        {
            "page_title": "Desativar vendedor",
            "message": f"Desativar {salesperson.display_name}?",
        },
    )


@require_permission("salespeople.update")
def activate_view(request, pk):
    salesperson = get_object_or_404(Salesperson, pk=pk)
    if request.method == "POST":
        set_salesperson_active(
            salesperson=salesperson,
            is_active=True,
            actor=request.user,
            request=request,
        )
        messages.success(request, "Vendedor reativado com sucesso.")
        return redirect("salespeople:detail", pk=salesperson.pk)
    return render(
        request,
        "erp/confirm_action.html",
        {
            "page_title": "Reativar vendedor",
            "message": f"Reativar {salesperson.display_name}?",
        },
    )


@require_permission("salespeople.view")
def history_view(request, pk):
    salesperson = get_object_or_404(Salesperson, pk=pk)
    qs = AuditEvent.objects.filter(
        object_type="Salesperson",
        object_id=str(salesperson.pk),
    )
    page_obj = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "audit/audit_list.html",
        {
            "page_title": f"Histórico de {salesperson.display_name}",
            "page_obj": page_obj,
        },
    )
