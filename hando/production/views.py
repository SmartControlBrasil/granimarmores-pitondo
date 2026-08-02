# ruff: noqa: PLR0913
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from access_control.services.authorization import require_permission
from production.forms import DeliveryScheduleForm
from production.forms import InstallationCompleteForm
from production.forms import InstallationScheduleForm
from production.forms import ProductionActionForm
from production.forms import ProductionOrderForm
from production.forms import SalesOrderCancelForm
from production.forms import SalesOrderForm
from production.forms import SalesOrderHoldForm
from production.forms import SalesOrderStatusForm
from production.models import DeliverySchedule
from production.models import InstallationSchedule
from production.models import ProductionOrder
from production.models import ProductionOrderStatus
from production.models import ProductionPieceStage
from production.models import ProductionStage
from production.models import SalesOrder
from production.models import SalesOrderStatus
from production.models import TERMINAL_ORDER_STATUSES
from production.selectors import board_data
from production.selectors import calculate_order_progress
from production.selectors import can_access_production_order
from production.selectors import can_access_sales_order
from production.selectors import dashboard_metrics
from production.selectors import is_production_order_overdue
from production.selectors import is_sales_order_overdue
from production.selectors import production_orders_queryset_for_user
from production.selectors import sales_orders_queryset_for_user
from production.services.delivery_ops import complete_delivery
from production.services.delivery_ops import complete_installation
from production.services.delivery_ops import schedule_delivery
from production.services.delivery_ops import schedule_installation
from production.services.order_workflow import change_order_status
from production.services.work_orders import cancel_production_order
from production.services.work_orders import complete_production_order
from production.services.work_orders import create_production_order
from production.services.work_orders import generate_piece_stages
from production.services.work_orders import generate_pieces_from_order
from production.services.work_orders import pause_production_order
from production.services.work_orders import release_production_order
from production.services.work_orders import resume_production_order
from production.services.work_orders import start_production_order


def _order_or_403(request, pk):
    order = get_object_or_404(
        SalesOrder.objects.select_related("customer", "salesperson", "quote", "lead"),
        pk=pk,
    )
    if not can_access_sales_order(request.user, order):
        raise PermissionDenied("Você não tem acesso a este pedido.")
    return order


def _production_or_403(request, pk):
    production = get_object_or_404(
        ProductionOrder.objects.select_related("sales_order", "sales_order__customer"),
        pk=pk,
    )
    if not can_access_production_order(request.user, production):
        raise PermissionDenied("Você não tem acesso a esta ordem de produção.")
    return production


@require_permission("sales_orders.view")
def order_list(request):
    qs = sales_orders_queryset_for_user(request.user).order_by("-created_at")
    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    overdue = request.GET.get("overdue", "").strip()
    if search:
        qs = qs.filter(Q(number__icontains=search) | Q(customer__name__icontains=search))
    if status:
        qs = qs.filter(status=status)
    if overdue == "1":
        from django.utils import timezone

        today = timezone.localdate()
        qs = qs.exclude(status__in=TERMINAL_ORDER_STATUSES).filter(
            promised_date__lt=today,
            promised_date__isnull=False,
        )
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "production/order_list.html",
        {
            "page_title": "Pedidos",
            "page_obj": page_obj,
            "search": search,
            "status": status,
            "statuses": SalesOrderStatus.choices,
            "overdue": overdue,
        },
    )


@require_permission("sales_orders.view")
def order_detail(request, pk):
    order = _order_or_403(request, pk)
    production = getattr(order, "production_order", None)
    return render(
        request,
        "production/order_detail.html",
        {
            "page_title": order.number,
            "order": order,
            "items": order.items.prefetch_related("measurements"),
            "production": production,
            "deliveries": order.deliveries.all(),
            "installations": order.installations.all(),
            "overdue": is_sales_order_overdue(order),
            "status_form": SalesOrderStatusForm(),
            "hold_form": SalesOrderHoldForm(),
            "cancel_form": SalesOrderCancelForm(),
        },
    )


@require_permission("sales_orders.update")
def order_update(request, pk):
    order = _order_or_403(request, pk)
    form = SalesOrderForm(request.POST or None, instance=order)
    if request.method == "POST" and form.is_valid():
        order = form.save(commit=False)
        order.updated_by = request.user
        order.save()
        messages.success(request, "Pedido atualizado.")
        return redirect("operacao:order_detail", pk=order.pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": f"Editar {order.number}", "form": form, "cancel_url": "operacao:order_list"},
    )


@require_permission("sales_orders.change_status")
def order_change_status(request, pk):
    order = _order_or_403(request, pk)
    form = SalesOrderStatusForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            change_order_status(
                order=order,
                new_status=form.cleaned_data["new_status"],
                actor=request.user,
                reason=form.cleaned_data.get("reason", ""),
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Status atualizado.")
    return redirect("operacao:order_detail", pk=pk)


@require_permission("sales_orders.change_status")
def order_hold(request, pk):
    order = _order_or_403(request, pk)
    form = SalesOrderHoldForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            change_order_status(
                order=order,
                new_status=SalesOrderStatus.ON_HOLD,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Pedido em espera.")
    return redirect("operacao:order_detail", pk=pk)


@require_permission("sales_orders.cancel")
def order_cancel(request, pk):
    order = _order_or_403(request, pk)
    form = SalesOrderCancelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            change_order_status(
                order=order,
                new_status=SalesOrderStatus.CANCELLED,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Pedido cancelado.")
    return redirect("operacao:order_detail", pk=pk)


@require_permission("production_orders.create")
def order_create_production(request, pk):
    order = _order_or_403(request, pk)
    if request.method == "POST":
        try:
            production = create_production_order(sales_order=order, actor=request.user, request=request)
            pieces = generate_pieces_from_order(production_order=production, actor=request.user, request=request)
            for piece in pieces:
                generate_piece_stages(piece=piece, actor=request.user, request=request)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Ordem de produção criada.")
            return redirect("producao:production_detail", pk=production.pk)
    return redirect("operacao:order_detail", pk=pk)


@require_permission("production_orders.view")
def production_list(request):
    qs = production_orders_queryset_for_user(request.user).order_by("-created_at")
    status = request.GET.get("status", "").strip()
    overdue = request.GET.get("overdue", "").strip()
    if status:
        qs = qs.filter(status=status)
    if overdue == "1":
        from django.utils import timezone

        today = timezone.localdate()
        qs = qs.exclude(
            status__in={ProductionOrderStatus.COMPLETED, ProductionOrderStatus.CANCELLED},
        ).filter(planned_end_date__lt=today, planned_end_date__isnull=False)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    progress_map = {p.pk: calculate_order_progress(p) for p in page_obj}
    return render(
        request,
        "production/production_list.html",
        {"page_title": "Ordens de produção", "page_obj": page_obj, "progress_map": progress_map},
    )


@require_permission("production_orders.view")
def production_detail(request, pk):
    production = _production_or_403(request, pk)
    pieces = production.pieces.prefetch_related("stages__stage", "slab")
    return render(
        request,
        "production/production_detail.html",
        {
            "page_title": production.number,
            "production": production,
            "pieces": pieces,
            "logs": production.logs.select_related("created_by")[:20],
            "inspections": production.inspections.all()[:10],
            "progress": calculate_order_progress(production),
            "overdue": is_production_order_overdue(production),
            "action_form": ProductionActionForm(),
        },
    )


@require_permission("production_orders.update")
def production_update(request, pk):
    production = _production_or_403(request, pk)
    form = ProductionOrderForm(request.POST or None, instance=production)
    if request.method == "POST" and form.is_valid():
        production = form.save(commit=False)
        production.updated_by = request.user
        production.save()
        messages.success(request, "Ordem atualizada.")
        return redirect("producao:production_detail", pk=production.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": f"Editar {production.number}",
            "form": form,
            "cancel_url": "producao:production_list",
        },
    )


def _production_action(view_name, service_fn, success_msg):
    @require_permission("production_orders.change_status")
    def view(request, pk):
        production = _production_or_403(request, pk)
        form = ProductionActionForm(request.POST or None)
        if request.method == "POST":
            try:
                if service_fn.__name__ in {"pause_production_order", "cancel_production_order"}:
                    service_fn(
                        production_order=production,
                        actor=request.user,
                        reason=form.data.get("reason", ""),
                        request=request,
                    )
                else:
                    service_fn(production_order=production, actor=request.user, request=request)
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, success_msg)
        return redirect("producao:production_detail", pk=pk)

    view.__name__ = view_name
    return view


production_release = _production_action("production_release", release_production_order, "Ordem liberada.")
production_start = _production_action("production_start", start_production_order, "Ordem iniciada.")
production_pause = _production_action("production_pause", pause_production_order, "Ordem pausada.")
production_resume = _production_action("production_resume", resume_production_order, "Ordem retomada.")
production_complete = _production_action("production_complete", complete_production_order, "Ordem concluída.")
production_cancel = _production_action("production_cancel", cancel_production_order, "Ordem cancelada.")


@require_permission("production_dashboard.view")
def production_dashboard(request):
    metrics = dashboard_metrics(user=request.user)
    return render(
        request,
        "production/dashboard.html",
        {"page_title": "Dashboard de Produção", "metrics": metrics},
    )


@require_permission("production_orders.view")
def production_board(request):
    columns = board_data(user=request.user)
    return render(
        request,
        "production/board.html",
        {"page_title": "Quadro de Produção", "columns": columns},
    )


@require_permission("production_orders.view")
def production_order_board(request, pk):
    production = _production_or_403(request, pk)
    columns = board_data(user=request.user, limit=20)
    return render(
        request,
        "production/board.html",
        {
            "page_title": f"Quadro — {production.number}",
            "columns": columns,
            "production": production,
        },
    )


@require_permission("deliveries.view")
def delivery_list(request):
    order_ids = sales_orders_queryset_for_user(request.user).values_list("pk", flat=True)
    qs = DeliverySchedule.objects.filter(sales_order_id__in=order_ids).select_related("sales_order")
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "production/delivery_list.html",
        {"page_title": "Entregas", "page_obj": page_obj},
    )


@require_permission("deliveries.schedule")
def delivery_schedule(request, pk):
    order = _order_or_403(request, pk)
    form = DeliveryScheduleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            schedule_delivery(
                sales_order=order,
                actor=request.user,
                request=request,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Entrega agendada.")
            return redirect("operacao:order_detail", pk=pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Agendar entrega", "form": form, "cancel_url": "production:order_detail"},
    )


@require_permission("deliveries.complete")
def delivery_complete(request, pk, delivery_pk):
    order = _order_or_403(request, pk)
    delivery = get_object_or_404(DeliverySchedule, pk=delivery_pk, sales_order=order)
    if request.method == "POST":
        try:
            complete_delivery(delivery=delivery, actor=request.user, request=request)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Entrega concluída.")
    return redirect("operacao:order_detail", pk=pk)


@require_permission("installations.view")
def installation_list(request):
    order_ids = sales_orders_queryset_for_user(request.user).values_list("pk", flat=True)
    qs = InstallationSchedule.objects.filter(sales_order_id__in=order_ids).select_related("sales_order")
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "production/installation_list.html",
        {"page_title": "Instalações", "page_obj": page_obj},
    )


@require_permission("installations.schedule")
def installation_schedule(request, pk):
    order = _order_or_403(request, pk)
    form = InstallationScheduleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            schedule_installation(
                sales_order=order,
                actor=request.user,
                request=request,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Instalação agendada.")
            return redirect("operacao:order_detail", pk=pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Agendar instalação", "form": form, "cancel_url": "production:order_detail"},
    )


@require_permission("installations.complete")
def installation_complete(request, pk, installation_pk):
    order = _order_or_403(request, pk)
    installation = get_object_or_404(InstallationSchedule, pk=installation_pk, sales_order=order)
    form = InstallationCompleteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            complete_installation(
                installation=installation,
                actor=request.user,
                request=request,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Instalação concluída.")
            return redirect("operacao:order_detail", pk=pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Concluir instalação", "form": form, "cancel_url": "production:order_detail"},
    )


@require_permission("production_stages.view")
def stage_list(request):
    qs = ProductionStage.objects.all().order_by("display_order")
    page_obj = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "production/stage_list.html",
        {"page_title": "Etapas produtivas", "page_obj": page_obj},
    )


@require_permission("production_pieces.view")
def piece_stage_list(request):
    order_ids = production_orders_queryset_for_user(request.user).values_list("pk", flat=True)
    qs = ProductionPieceStage.objects.filter(
        piece__production_order_id__in=order_ids,
    ).select_related("piece", "stage", "assigned_to")
    page_obj = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "production/piece_stage_list.html",
        {"page_title": "Peças em produção", "page_obj": page_obj},
    )
