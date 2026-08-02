# ruff: noqa: PLR0913
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone

from access_control.services.authorization import require_permission
from access_control.services.authorization import user_has_permission
from commercial.lead_conversion import convert_lead_to_new_customer
from commercial.lead_conversion import create_lead
from commercial.lead_conversion import create_quote_from_lead
from commercial.lead_conversion import find_customer_matches
from commercial.lead_conversion import link_lead_to_customer
from commercial.lead_conversion import update_lead
from commercial.lead_dashboard import build_commercial_dashboard_context
from commercial.lead_dashboard import build_funnel_context
from commercial.lead_forms import LeadActivityForm
from commercial.lead_forms import LeadAssignForm
from commercial.lead_forms import LeadConvertLinkForm
from commercial.lead_forms import LeadForm
from commercial.lead_forms import LeadLossForm
from commercial.lead_forms import LeadReopenForm
from commercial.lead_forms import LeadStatusForm
from commercial.lead_forms import LeadTaskForm
from commercial.lead_models import Lead
from commercial.lead_models import LeadActivityType
from commercial.lead_models import LeadStatus
from commercial.lead_models import LeadTask
from commercial.lead_models import LeadTaskStatus
from commercial.lead_models import LOSS_STATUSES
from commercial.lead_models import TERMINAL_STATUSES
from commercial.lead_queries import can_access_lead
from commercial.lead_queries import leads_queryset_for_user
from commercial.lead_tasks import cancel_lead_task
from commercial.lead_tasks import complete_lead_task
from commercial.lead_tasks import create_lead_task
from commercial.lead_tasks import reopen_lead_task
from commercial.lead_workflow import assign_lead_salesperson
from commercial.lead_workflow import change_lead_status
from commercial.lead_workflow import register_lead_activity
from commercial.lead_workflow import reopen_lead
from commercial.models import CommercialPartner
from commercial.models import CommercialSource
from commercial.models import ContactChannel
from commercial.models import ProjectType
from customers.models import Customer
from salespeople.models import Salesperson


def _get_lead_or_403(user, pk):
    lead = get_object_or_404(Lead, pk=pk)
    if not can_access_lead(user, lead):
        raise PermissionDenied("Você não tem acesso a este lead.")
    return lead


def _apply_lead_filters(qs, request):
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(code__icontains=search)
            | Q(name__icontains=search)
            | Q(company_name__icontains=search)
            | Q(email__icontains=search)
            | Q(phone__icontains=search),
        )
    for field, param in [
        ("status", "status"),
        ("priority", "priority"),
        ("commercial_source_id", "source"),
        ("contact_channel_id", "channel"),
        ("project_type_id", "project_type"),
        ("partner_id", "partner"),
        ("service_region_id", "region"),
        ("assigned_salesperson_id", "salesperson"),
    ]:
        value = request.GET.get(param, "").strip()
        if value.isdigit():
            qs = qs.filter(**{field: int(value)})
    city = request.GET.get("city", "").strip()
    state = request.GET.get("state", "").strip()
    if city:
        qs = qs.filter(city__icontains=city)
    if state:
        qs = qs.filter(state__iexact=state)
    if request.GET.get("unassigned") == "1":
        qs = qs.filter(assigned_salesperson__isnull=True)
    if request.GET.get("sem_contato") == "1":
        qs = qs.filter(first_contact_at__isnull=True).exclude(status__in=TERMINAL_STATUSES)
    if request.GET.get("overdue_followup") == "1":
        qs = qs.filter(next_follow_up_at__lt=timezone.now()).exclude(status__in=TERMINAL_STATUSES)
    if request.GET.get("won") == "1":
        qs = qs.filter(status=LeadStatus.WON)
    if request.GET.get("lost") == "1":
        qs = qs.filter(status__in=LOSS_STATUSES)
    shortcut = request.GET.get("shortcut", "")
    user = request.user
    if shortcut == "mine" and hasattr(user, "salesperson"):
        qs = qs.filter(assigned_salesperson__user=user)
    return qs.order_by("-created_at")


@require_permission("leads.view")
def lead_list(request):
    qs = _apply_lead_filters(leads_queryset_for_user(request.user), request)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "commercial/leads/list.html",
        {
            "page_title": "Leads",
            "page_obj": page_obj,
            "search": request.GET.get("q", ""),
            "statuses": LeadStatus.choices,
            "sources": CommercialSource.objects.filter(is_active=True),
            "channels": ContactChannel.objects.filter(is_active=True),
            "project_types": ProjectType.objects.filter(is_active=True),
            "partners": CommercialPartner.objects.filter(is_active=True),
            "salespeople": Salesperson.objects.filter(is_active=True),
        },
    )


@require_permission("leads.create")
def lead_create(request):
    form = LeadForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            lead = create_lead(form=form, actor=request.user, request=request)
        except ValidationError as exc:
            messages.error(request, exc.message if hasattr(exc, "message") else str(exc))
        else:
            messages.success(request, "Lead criado com sucesso.")
            return redirect("leads:detail", pk=lead.pk)
    return render(
        request,
        "commercial/leads/form.html",
        {"page_title": "Novo lead", "form": form},
    )


@require_permission("leads.view")
def lead_detail(request, pk):
    lead = _get_lead_or_403(request.user, pk)
    tasks = list(lead.tasks.select_related("assigned_to", "created_by"))
    task_groups = {
        "overdue": [t for t in tasks if t.is_overdue],
        "pending": [t for t in tasks if t.status == LeadTaskStatus.PENDING],
        "in_progress": [t for t in tasks if t.status == LeadTaskStatus.IN_PROGRESS],
        "completed": [t for t in tasks if t.status == LeadTaskStatus.COMPLETED][:10],
        "cancelled": [t for t in tasks if t.status == LeadTaskStatus.CANCELLED][:10],
    }
    return render(
        request,
        "commercial/leads/detail.html",
        {
            "page_title": lead.code,
            "lead": lead,
            "activities": lead.activities.select_related("created_by")[:30],
            "quotes": lead.quotes.all()[:20],
            "task_groups": task_groups,
            "customer_matches": find_customer_matches(
                email=lead.email,
                phone=lead.phone,
                whatsapp=lead.whatsapp,
            ) if not lead.converted_customer_id else [],
            "assign_form": LeadAssignForm(initial={"assigned_salesperson": lead.assigned_salesperson}),
            "status_form": LeadStatusForm(initial={"new_status": lead.status}),
            "activity_form": LeadActivityForm(),
            "task_form": LeadTaskForm(initial={"assigned_to": request.user}),
            "loss_form": LeadLossForm(),
            "reopen_form": LeadReopenForm(),
            "convert_form": LeadConvertLinkForm(),
            "statuses": LeadStatus.choices,
        },
    )


@require_permission("leads.update")
def lead_update(request, pk):
    lead = _get_lead_or_403(request.user, pk)
    form = LeadForm(request.POST or None, instance=lead)
    if request.method == "POST" and form.is_valid():
        try:
            update_lead(lead=lead, form=form, actor=request.user, request=request)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Lead atualizado com sucesso.")
            return redirect("leads:detail", pk=lead.pk)
    return render(
        request,
        "commercial/leads/form.html",
        {"page_title": f"Editar {lead.code}", "form": form, "lead": lead},
    )


@require_permission("leads.view")
def lead_funnel(request):
    return render(
        request,
        "commercial/leads/funnel.html",
        {"page_title": "Funil Comercial", **build_funnel_context(user=request.user)},
    )


@login_required
def commercial_dashboard(request):
    if not (
        user_has_permission(request.user, "leads.view")
        or user_has_permission(request.user, "leads.view_all")
    ):
        raise PermissionDenied
    return render(
        request,
        "commercial/leads/dashboard.html",
        {
            "page_title": "Dashboard Comercial",
            **build_commercial_dashboard_context(user=request.user, request=request),
        },
    )


@require_permission("leads.assign")
def lead_assign(request, pk):
    lead = _get_lead_or_403(request.user, pk)
    form = LeadAssignForm(request.POST)
    if request.method == "POST" and form.is_valid():
        try:
            assign_lead_salesperson(
                lead=lead,
                salesperson=form.cleaned_data["assigned_salesperson"],
                actor=request.user,
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Responsável atualizado.")
    return redirect("leads:detail", pk=lead.pk)


@require_permission("leads.change_status")
def lead_change_status(request, pk):
    lead = _get_lead_or_403(request.user, pk)
    form = LeadStatusForm(request.POST)
    if request.method == "POST" and form.is_valid():
        try:
            change_lead_status(
                lead=lead,
                new_status=form.cleaned_data["new_status"],
                actor=request.user,
                request=request,
                loss_reason=form.cleaned_data.get("loss_reason"),
                loss_notes=form.cleaned_data.get("loss_notes", ""),
                override_reason=form.cleaned_data.get("override_reason", ""),
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Status atualizado.")
    return redirect("leads:detail", pk=lead.pk)


@require_permission("lead_activities.create")
def lead_add_activity(request, pk):
    lead = _get_lead_or_403(request.user, pk)
    form = LeadActivityForm(request.POST)
    if request.method == "POST" and form.is_valid():
        register_lead_activity(
            lead=lead,
            actor=request.user,
            activity_type=form.cleaned_data["activity_type"],
            title=form.cleaned_data["title"],
            description=form.cleaned_data["description"],
            next_action_at=form.cleaned_data.get("next_action_at"),
            request=request,
        )
        messages.success(request, "Atividade registrada.")
    return redirect("leads:detail", pk=lead.pk)


@require_permission("lead_tasks.create")
def lead_add_task(request, pk):
    lead = _get_lead_or_403(request.user, pk)
    form = LeadTaskForm(request.POST)
    if request.method == "POST" and form.is_valid():
        create_lead_task(
            lead=lead,
            title=form.cleaned_data["title"],
            description=form.cleaned_data["description"],
            assigned_to=form.cleaned_data["assigned_to"],
            due_at=form.cleaned_data["due_at"],
            priority=form.cleaned_data["priority"],
            actor=request.user,
            request=request,
        )
        messages.success(request, "Tarefa criada.")
    return redirect("leads:detail", pk=lead.pk)


@require_permission("lead_tasks.complete")
def lead_complete_task(request, pk, task_pk):
    lead = _get_lead_or_403(request.user, pk)
    task = get_object_or_404(LeadTask, pk=task_pk, lead=lead)
    if request.method == "POST":
        complete_lead_task(task=task, actor=request.user, request=request)
        messages.success(request, "Tarefa concluída.")
    return redirect("leads:detail", pk=lead.pk)


@require_permission("lead_tasks.cancel")
def lead_cancel_task(request, pk, task_pk):
    lead = _get_lead_or_403(request.user, pk)
    task = get_object_or_404(LeadTask, pk=task_pk, lead=lead)
    if request.method == "POST":
        cancel_lead_task(task=task, actor=request.user, request=request)
        messages.success(request, "Tarefa cancelada.")
    return redirect("leads:detail", pk=lead.pk)


@require_permission("lead_tasks.reopen")
def lead_reopen_task(request, pk, task_pk):
    lead = _get_lead_or_403(request.user, pk)
    task = get_object_or_404(LeadTask, pk=task_pk, lead=lead)
    if request.method == "POST":
        reopen_lead_task(task=task, actor=request.user, request=request)
        messages.success(request, "Tarefa reaberta.")
    return redirect("leads:detail", pk=lead.pk)


@require_permission("leads.convert")
def lead_convert_new(request, pk):
    lead = _get_lead_or_403(request.user, pk)
    if request.method == "POST":
        try:
            customer = convert_lead_to_new_customer(lead=lead, actor=request.user, request=request)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Cliente {customer.name} criado.")
            return redirect("customers:detail", pk=customer.pk)
    return redirect("leads:detail", pk=lead.pk)


@require_permission("leads.convert")
def lead_convert_link(request, pk):
    lead = _get_lead_or_403(request.user, pk)
    form = LeadConvertLinkForm(request.POST)
    if request.method == "POST" and form.is_valid():
        customer_id = form.cleaned_data.get("customer_id")
        if customer_id:
            customer = get_object_or_404(Customer, pk=customer_id)
            try:
                link_lead_to_customer(
                    lead=lead,
                    customer=customer,
                    actor=request.user,
                    request=request,
                )
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, "Lead vinculado ao cliente.")
                return redirect("customers:detail", pk=customer.pk)
    return redirect("leads:detail", pk=lead.pk)


@require_permission("quotes.create")
def lead_create_quote(request, pk):
    lead = _get_lead_or_403(request.user, pk)
    if request.method == "POST":
        try:
            quote = create_quote_from_lead(lead=lead, actor=request.user, request=request)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Orçamento criado.")
            return redirect("quotes:detail", pk=quote.pk)
    return redirect("leads:detail", pk=lead.pk)


@require_permission("leads.mark_won")
def lead_mark_won(request, pk):
    lead = _get_lead_or_403(request.user, pk)
    if request.method == "POST":
        try:
            change_lead_status(
                lead=lead,
                new_status=LeadStatus.WON,
                actor=request.user,
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Lead marcado como ganho.")
    return redirect("leads:detail", pk=lead.pk)


@require_permission("leads.mark_lost")
def lead_mark_lost(request, pk):
    lead = _get_lead_or_403(request.user, pk)
    form = LeadLossForm(request.POST)
    if request.method == "POST" and form.is_valid():
        try:
            change_lead_status(
                lead=lead,
                new_status=LeadStatus.LOST,
                actor=request.user,
                request=request,
                loss_reason=form.cleaned_data["loss_reason"],
                loss_notes=form.cleaned_data.get("loss_notes", ""),
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Lead marcado como perdido.")
    return redirect("leads:detail", pk=lead.pk)


@require_permission("leads.reopen")
def lead_reopen_view(request, pk):
    lead = _get_lead_or_403(request.user, pk)
    form = LeadReopenForm(request.POST)
    if request.method == "POST" and form.is_valid():
        try:
            reopen_lead(lead=lead, actor=request.user, reason=form.cleaned_data["reason"], request=request)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Lead reaberto.")
    return redirect("leads:detail", pk=lead.pk)
