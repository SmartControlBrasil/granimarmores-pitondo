from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import redirect
from django.shortcuts import render

from access_control.models import DataScope
from access_control.services.authorization import get_user_scope
from access_control.services.authorization import require_permission
from audit.services import record_audit_event
from customers.forms import CustomerForm
from customers.models import Customer


def scoped_customers(user):
    qs = Customer.objects.select_related("assigned_salesperson", "created_by")
    scope = get_user_scope(user, "customer")
    if user.is_superuser or scope == DataScope.ALL:
        return qs
    if scope == DataScope.OWN:
        return qs.filter(assigned_salesperson__user=user)
    return qs.none()


@require_permission("customers.view")
def customer_list(request):
    qs = scoped_customers(request.user).order_by("name")
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(name__icontains=search)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "customers/customer_list.html",
        {"page_title": "Clientes", "page_obj": page_obj, "search": search},
    )


@require_permission("customers.create")
@transaction.atomic
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer = form.save(commit=False)
        customer.created_by = request.user
        customer.updated_by = request.user
        customer.save()
        form.save_m2m()
        record_audit_event(
            request=request,
            event_type="create",
            module="customers",
            action="create",
            obj=customer,
        )
        messages.success(request, "Cliente criado com sucesso.")
        return redirect("customers:list")
    return render(
        request,
        "customers/customer_form.html",
        {"page_title": "Novo cliente", "form": form},
    )
