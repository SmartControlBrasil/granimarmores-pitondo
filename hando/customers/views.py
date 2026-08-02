# ruff: noqa: EM101, TRY003
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from access_control.models import DataScope
from access_control.services.authorization import can_access_object
from access_control.services.authorization import get_user_scope
from access_control.services.authorization import require_permission
from audit.models import AuditEvent
from commercial.models import CommercialPartner
from commercial.models import CommercialSource
from customers.forms import CustomerForm
from customers.models import Customer
from customers.services import create_customer
from customers.services import set_customer_active
from customers.services import update_customer


def scoped_customers(user):
    qs = Customer.objects.select_related("assigned_salesperson", "created_by")
    scope = get_user_scope(user, "customer")
    if user.is_superuser or scope == DataScope.ALL:
        return qs
    if scope == DataScope.OWN:
        return qs.filter(assigned_salesperson__user=user)
    return qs.none()


def _get_scoped_customer(user, pk):
    customer = get_object_or_404(
        Customer.objects.select_related("assigned_salesperson"),
        pk=pk,
    )
    if not can_access_object(user, customer, "view"):
        raise PermissionDenied("Você não tem acesso a este cliente.")
    return customer


@require_permission("customers.view")
def customer_list(request):
    qs = scoped_customers(request.user).select_related(
        "assigned_salesperson",
        "commercial_source",
        "partner",
    ).order_by("name")
    search = request.GET.get("q", "").strip()
    source_id = request.GET.get("source", "").strip()
    partner_id = request.GET.get("partner", "").strip()
    if search:
        qs = qs.filter(name__icontains=search)
    if source_id.isdigit():
        qs = qs.filter(commercial_source_id=int(source_id))
    if partner_id.isdigit():
        qs = qs.filter(partner_id=int(partner_id))
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "customers/customer_list.html",
        {
            "page_title": "Clientes",
            "page_obj": page_obj,
            "search": search,
            "sources": CommercialSource.objects.filter(is_active=True).order_by("name"),
            "partners": CommercialPartner.objects.filter(is_active=True).order_by("name"),
            "selected_source": source_id,
            "selected_partner": partner_id,
        },
    )


@require_permission("customers.view")
def customer_detail(request, pk):
    customer = _get_scoped_customer(request.user, pk)
    customer = Customer.objects.select_related(
        "assigned_salesperson",
        "commercial_source",
        "partner",
        "project_type_interest",
        "preferred_contact_channel",
    ).get(pk=customer.pk)
    recent_events = AuditEvent.objects.filter(
        object_type="Customer",
        object_id=str(customer.pk),
    )[:10]
    return render(
        request,
        "customers/customer_detail.html",
        {
            "page_title": customer.name,
            "customer": customer,
            "recent_events": recent_events,
        },
    )


@require_permission("customers.create")
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer = create_customer(form=form, actor=request.user, request=request)
        messages.success(request, "Cliente criado com sucesso.")
        return redirect("customers:detail", pk=customer.pk)
    return render(
        request,
        "customers/customer_form.html",
        {"page_title": "Novo cliente", "form": form},
    )


@require_permission("customers.update")
def customer_update(request, pk):
    customer = _get_scoped_customer(request.user, pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        try:
            customer = update_customer(
                customer=customer,
                form=form,
                actor=request.user,
                request=request,
            )
        except PermissionDenied as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Cliente atualizado com sucesso.")
            return redirect("customers:detail", pk=customer.pk)
    return render(
        request,
        "customers/customer_form.html",
        {"page_title": f"Editar {customer.name}", "form": form, "customer": customer},
    )


@require_permission("customers.deactivate")
def customer_deactivate(request, pk):
    customer = _get_scoped_customer(request.user, pk)
    if request.method == "POST":
        try:
            set_customer_active(
                customer=customer,
                is_active=False,
                actor=request.user,
                request=request,
            )
        except PermissionDenied as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Cliente desativado com sucesso.")
        return redirect("customers:detail", pk=customer.pk)
    return render(
        request,
        "erp/confirm_action.html",
        {"page_title": "Desativar cliente", "message": f"Desativar {customer.name}?"},
    )


@require_permission("customers.update")
def customer_activate(request, pk):
    customer = _get_scoped_customer(request.user, pk)
    if request.method == "POST":
        set_customer_active(
            customer=customer,
            is_active=True,
            actor=request.user,
            request=request,
        )
        messages.success(request, "Cliente reativado com sucesso.")
        return redirect("customers:detail", pk=customer.pk)
    return render(
        request,
        "erp/confirm_action.html",
        {"page_title": "Reativar cliente", "message": f"Reativar {customer.name}?"},
    )


@require_permission("customers.view")
def customer_history(request, pk):
    customer = _get_scoped_customer(request.user, pk)
    qs = AuditEvent.objects.filter(object_type="Customer", object_id=str(customer.pk))
    page_obj = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "audit/audit_list.html",
        {"page_title": f"Histórico de {customer.name}", "page_obj": page_obj},
    )
