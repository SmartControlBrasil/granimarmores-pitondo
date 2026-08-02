# ruff: noqa: PLR0913
import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone

from access_control.services.authorization import require_permission
from access_control.services.authorization import user_has_permission
from customers.models import Customer
from fleet.models import Vehicle
from salespeople.models import Salesperson
from scheduling.forms import CancelEventForm
from scheduling.forms import CompleteEventForm
from scheduling.forms import ConfirmEventForm
from scheduling.forms import LeadScheduleForm
from scheduling.forms import OperationalEventForm
from scheduling.forms import OrderScheduleForm
from scheduling.forms import RescheduleForm
from scheduling.models import EventStatus
from scheduling.models import EventType
from scheduling.models import MeasurementAppointment
from scheduling.models import OperationalEvent
from scheduling.selectors import calendar_events_payload
from scheduling.selectors import events_queryset_for_user
from scheduling.selectors import filter_events
from scheduling.selectors import parse_period
from scheduling.selectors import schedule_dashboard_metrics
from scheduling.services.conflicts import check_schedule_conflicts
from scheduling.services.events import cancel_event
from scheduling.services.events import complete_event
from scheduling.services.events import confirm_event
from scheduling.services.events import create_operational_event
from scheduling.services.events import mark_no_show
from scheduling.services.events import register_confirmation_attempt
from scheduling.services.events import reschedule_event
from scheduling.services.events import start_event

User = get_user_model()


def _parse_form_datetime(value):
    if value is None:
        return None
    if timezone.is_naive(value):
        return timezone.make_aware(value)
    return value


@require_permission("schedule_dashboard.view")
def schedule_dashboard(request):
    start, end, period = parse_period(request)
    metrics = schedule_dashboard_metrics(
        user=request.user,
        start=start,
        end=end,
        assigned_user=request.GET.get("assigned_user") or None,
        event_type=request.GET.get("event_type") or None,
        city=request.GET.get("city") or None,
    )
    return render(
        request,
        "scheduling/dashboard.html",
        {
            "page_title": "Dashboard da Agenda",
            "metrics": metrics,
            "period": period,
            "users": User.objects.filter(is_active=True),
            "event_types": EventType.choices,
        },
    )


@require_permission("schedule_calendar.view")
def calendar_month(request):
    qs = filter_events(events_queryset_for_user(request.user), request.GET)
    return render(
        request,
        "scheduling/calendar_month.html",
        {
            "page_title": "Agenda — Mês",
            "events_json": json.dumps(calendar_events_payload(qs)),
            "initial_view": "dayGridMonth",
            "event_types": EventType.choices,
            "users": User.objects.filter(is_active=True),
            "salespeople": Salesperson.objects.filter(is_active=True),
        },
    )


@require_permission("schedule_calendar.view")
def calendar_week(request):
    qs = filter_events(events_queryset_for_user(request.user), request.GET)
    return render(
        request,
        "scheduling/calendar_week.html",
        {
            "page_title": "Agenda — Semana",
            "events_json": json.dumps(calendar_events_payload(qs)),
            "initial_view": "timeGridWeek",
            "event_types": EventType.choices,
        },
    )


@require_permission("schedule_calendar.view")
def calendar_today(request):
    today = timezone.localdate()
    qs = events_queryset_for_user(request.user).filter(start_at__date=today)
    overdue = events_queryset_for_user(request.user).filter(
        end_at__lt=timezone.now(),
    ).exclude(
        status__in=[EventStatus.COMPLETED, EventStatus.CANCELLED, EventStatus.NO_SHOW],
    )
    return render(
        request,
        "scheduling/calendar_today.html",
        {
            "page_title": "Agenda — Hoje",
            "events": qs.order_by("start_at"),
            "overdue": overdue.order_by("start_at")[:20],
            "can_confirm": user_has_permission(request.user, "operational_events.confirm"),
            "can_start": user_has_permission(request.user, "operational_events.start"),
            "can_complete": user_has_permission(request.user, "operational_events.complete"),
        },
    )


@require_permission("operational_events.view")
def event_list(request):
    qs = filter_events(events_queryset_for_user(request.user), request.GET).order_by("start_at")
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "scheduling/event_list.html",
        {
            "page_title": "Eventos",
            "page_obj": page_obj,
            "event_types": EventType.choices,
            "status_choices": EventStatus.choices,
            "users": User.objects.filter(is_active=True),
            "salespeople": Salesperson.objects.filter(is_active=True),
            "vehicles": Vehicle.objects.filter(is_active=True),
        },
    )


@require_permission("operational_events.view")
def event_detail(request, pk):
    event = get_object_or_404(events_queryset_for_user(request.user), pk=pk)
    conflicts = check_schedule_conflicts(
        start_at=event.start_at,
        end_at=event.end_at,
        assigned_user=event.assigned_user,
        assigned_salesperson=event.assigned_salesperson,
        vehicle=event.vehicle,
        exclude_event=event,
        all_day=event.all_day,
    )
    return render(
        request,
        "scheduling/event_detail.html",
        {
            "page_title": event.code,
            "event": event,
            "history": event.history.select_related("actor")[:50],
            "conflicts": conflicts,
            "measurement": getattr(event, "measurement", None),
            "can_confirm": user_has_permission(request.user, "operational_events.confirm"),
            "can_start": user_has_permission(request.user, "operational_events.start"),
            "can_complete": user_has_permission(request.user, "operational_events.complete"),
            "can_reschedule": user_has_permission(request.user, "operational_events.reschedule"),
            "can_cancel": user_has_permission(request.user, "operational_events.cancel"),
        },
    )


@require_permission("operational_events.create")
def event_create(request):
    form = OperationalEventForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            event = create_operational_event(
                actor=request.user,
                title=data["title"],
                event_type=data["event_type"],
                start_at=_parse_form_datetime(data["start_at"]),
                end_at=_parse_form_datetime(data.get("end_at")),
                all_day=data.get("all_day") or False,
                priority=data.get("priority") or "normal",
                description=data.get("description") or "",
                assigned_user=data.get("assigned_user"),
                assigned_salesperson=data.get("assigned_salesperson"),
                external_responsible=data.get("external_responsible") or "",
                customer=data.get("customer"),
                lead=data.get("lead"),
                quote=data.get("quote"),
                sales_order=data.get("sales_order"),
                production_order=data.get("production_order"),
                production_piece=data.get("production_piece"),
                vehicle=data.get("vehicle"),
                address=data.get("address") or "",
                district=data.get("district") or "",
                city=data.get("city") or "",
                state=data.get("state") or "",
                postal_code=data.get("postal_code") or "",
                contact_name=data.get("contact_name") or "",
                contact_phone=data.get("contact_phone") or "",
                internal_notes=data.get("internal_notes") or "",
                override_conflicts=data.get("override_conflicts") or False,
                override_reason=data.get("override_reason") or "",
                measurement_type=data.get("measurement_type") or None,
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Evento {event.code} criado.")
            return redirect("scheduling:event_detail", pk=event.pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Novo evento", "form": form, "cancel_url": "scheduling:event_list"},
    )


def _action_view(request, pk, form_class, service_fn, success_msg, title, **extra):
    event = get_object_or_404(events_queryset_for_user(request.user), pk=pk)
    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            service_fn(event=event, actor=request.user, request=request, **form.cleaned_data, **extra)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, success_msg)
            return redirect("scheduling:event_detail", pk=pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": title, "form": form, "cancel_url": "scheduling:event_detail", "object_pk": pk},
    )


@require_permission("operational_events.confirm")
def event_confirm(request, pk):
    return _action_view(
        request,
        pk,
        ConfirmEventForm,
        confirm_event,
        "Evento confirmado.",
        "Confirmar evento",
    )


@require_permission("operational_events.confirm")
def event_confirm_attempt(request, pk):
    return _action_view(
        request,
        pk,
        ConfirmEventForm,
        register_confirmation_attempt,
        "Tentativa registrada.",
        "Registrar tentativa de confirmação",
    )


@require_permission("operational_events.start")
def event_start(request, pk):
    event = get_object_or_404(events_queryset_for_user(request.user), pk=pk)
    if request.method == "POST":
        try:
            start_event(event=event, actor=request.user, request=request)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Evento iniciado.")
        return redirect("scheduling:event_detail", pk=pk)
    return render(
        request,
        "erp/confirm_action.html",
        {"page_title": "Iniciar evento", "message": f"Iniciar {event.code}?"},
    )


@require_permission("operational_events.complete")
def event_complete(request, pk):
    return _action_view(
        request,
        pk,
        CompleteEventForm,
        complete_event,
        "Evento concluído.",
        "Concluir evento",
    )


@require_permission("operational_events.cancel")
def event_cancel(request, pk):
    return _action_view(
        request,
        pk,
        CancelEventForm,
        cancel_event,
        "Evento cancelado.",
        "Cancelar evento",
    )


@require_permission("operational_events.reschedule")
def event_reschedule(request, pk):
    event = get_object_or_404(events_queryset_for_user(request.user), pk=pk)
    form = RescheduleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            reschedule_event(
                event=event,
                new_start_at=_parse_form_datetime(data["new_start_at"]),
                new_end_at=_parse_form_datetime(data["new_end_at"]),
                actor=request.user,
                reason=data["reason"],
                override_conflicts=data.get("override_conflicts") or False,
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Evento reagendado.")
            return redirect("scheduling:event_detail", pk=pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Reagendar", "form": form, "cancel_url": "scheduling:event_detail", "object_pk": pk},
    )


@require_permission("operational_events.complete")
def event_no_show(request, pk):
    event = get_object_or_404(events_queryset_for_user(request.user), pk=pk)
    if request.method == "POST":
        mark_no_show(event=event, actor=request.user, notes=request.POST.get("notes", ""), request=request)
        messages.success(request, "Não comparecimento registrado.")
        return redirect("scheduling:event_detail", pk=pk)
    return render(
        request,
        "erp/confirm_action.html",
        {"page_title": "Registrar no-show", "message": f"Registrar falta em {event.code}?"},
    )


@require_permission("schedule_measurements.view")
def measurement_list(request):
    qs = MeasurementAppointment.objects.select_related("event", "technician").order_by(
        "-event__start_at",
    )
    if not user_has_permission(request.user, "operational_events.view_all"):
        qs = qs.filter(event__in=events_queryset_for_user(request.user))
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "scheduling/measurement_list.html",
        {"page_title": "Medições", "page_obj": page_obj},
    )


@require_permission("operational_events.create")
def lead_schedule(request, pk):
    from commercial.lead_models import Lead
    from commercial.lead_queries import leads_queryset_for_user

    lead = get_object_or_404(leads_queryset_for_user(request.user), pk=pk)
    form = LeadScheduleForm(
        request.POST or None,
        initial={
            "title": f"{lead.code} — {lead.name}",
            "assigned_user": request.user.pk,
        },
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            event = create_operational_event(
                actor=request.user,
                title=data["title"],
                event_type=data["event_type"],
                start_at=_parse_form_datetime(data["start_at"]),
                end_at=_parse_form_datetime(data["end_at"]),
                assigned_user=data.get("assigned_user") or request.user,
                assigned_salesperson=lead.assigned_salesperson,
                customer=lead.converted_customer,
                lead=lead,
                address=(lead.district or lead.city or "A definir"),
                city=lead.city or "A definir",
                state=lead.state or "",
                district=lead.district or "",
                postal_code="",
                contact_name=lead.name or "",
                contact_phone=lead.phone or lead.whatsapp or "",
                description=lead.project_description or "",
                internal_notes=data.get("notes") or "",
                override_conflicts=data.get("override_conflicts") or False,
                override_reason=data.get("override_reason") or "",
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Evento {event.code} agendado.")
            return redirect("scheduling:event_detail", pk=event.pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": f"Agendar — {lead.code}", "form": form, "cancel_url": "leads:detail", "object_pk": pk},
    )


@require_permission("operational_events.create")
def order_schedule(request, pk):
    from production.models import SalesOrder
    from production.selectors import can_access_sales_order
    from production.services.delivery_ops import schedule_delivery
    from production.services.delivery_ops import schedule_installation

    order = get_object_or_404(SalesOrder, pk=pk)
    if not can_access_sales_order(request.user, order):
        raise PermissionDenied("Sem acesso ao pedido.")
    form = OrderScheduleForm(
        request.POST or None,
        initial={
            "title": f"{order.number} — {order.customer}",
            "assigned_user": request.user.pk,
        },
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        start = _parse_form_datetime(data["start_at"])
        end = _parse_form_datetime(data["end_at"])
        try:
            if data["event_type"] == EventType.DELIVERY:
                delivery = schedule_delivery(
                    sales_order=order,
                    actor=request.user,
                    scheduled_date=timezone.localtime(start).date(),
                    scheduled_time_start=timezone.localtime(start).time(),
                    scheduled_time_end=timezone.localtime(end).time(),
                    responsible=data.get("assigned_user") or request.user,
                    vehicle=data.get("vehicle"),
                    notes=data.get("notes") or "",
                    request=request,
                )
                event = delivery.operational_event
            elif data["event_type"] == EventType.INSTALLATION:
                installation = schedule_installation(
                    sales_order=order,
                    actor=request.user,
                    scheduled_date=timezone.localtime(start).date(),
                    scheduled_time_start=timezone.localtime(start).time(),
                    scheduled_time_end=timezone.localtime(end).time(),
                    responsible=data.get("assigned_user") or request.user,
                    vehicle=data.get("vehicle"),
                    notes=data.get("notes") or "",
                    request=request,
                )
                event = installation.operational_event
            else:
                event = create_operational_event(
                    actor=request.user,
                    title=data["title"],
                    event_type=data["event_type"],
                    start_at=start,
                    end_at=end,
                    assigned_user=data.get("assigned_user") or request.user,
                    customer=order.customer,
                    sales_order=order,
                    vehicle=data.get("vehicle"),
                    address=order.delivery_address,
                    city=order.delivery_city,
                    state=order.delivery_state,
                    postal_code=order.delivery_postal_code,
                    contact_name=str(order.customer),
                    internal_notes=data.get("notes") or "",
                    override_conflicts=data.get("override_conflicts") or False,
                    override_reason=data.get("override_reason") or "",
                    request=request,
                )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Evento {event.code} agendado.")
            return redirect("scheduling:event_detail", pk=event.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": f"Agendar — {order.number}",
            "form": form,
            "cancel_url": "operacao:order_detail",
            "object_pk": pk,
        },
    )
