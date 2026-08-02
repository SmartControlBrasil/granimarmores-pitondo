from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg
from django.db.models import Count
from django.db.models import Q
from django.utils import timezone

from access_control.models import DataScope
from access_control.services.authorization import get_user_scope
from production.models import DeliverySchedule
from production.models import InstallationSchedule
from production.models import PieceStageStatus
from production.models import ProductionOrder
from production.models import ProductionOrderStatus
from production.models import ProductionPiece
from production.models import ProductionPieceStage
from production.models import ProductionPieceStatus
from production.models import ProductionStage
from production.models import QualityInspectionStatus
from production.models import SalesOrder
from production.models import SalesOrderStatus
from production.models import ScheduleStatus
from production.models import TERMINAL_ORDER_STATUSES


def sales_orders_queryset_for_user(user):
    qs = SalesOrder.objects.select_related(
        "customer",
        "salesperson",
        "salesperson__user",
        "quote",
        "lead",
    )
    scope = get_user_scope(user, "quote")
    if user.is_superuser or scope == DataScope.ALL:
        return qs
    if scope == DataScope.TEAM:
        salesperson = getattr(user, "salesperson", None)
        if salesperson:
            return qs.filter(
                Q(salesperson=salesperson) | Q(salesperson__manager=salesperson),
            )
        return qs.filter(created_by=user)
    if scope == DataScope.OWN:
        return qs.filter(Q(salesperson__user=user) | Q(created_by=user))
    return qs.none()


def can_access_sales_order(user, order):
    return sales_orders_queryset_for_user(user).filter(pk=order.pk).exists()


def production_orders_queryset_for_user(user):
    qs = ProductionOrder.objects.select_related(
        "sales_order",
        "sales_order__customer",
        "sales_order__salesperson",
        "responsible",
    )
    order_ids = sales_orders_queryset_for_user(user).values_list("pk", flat=True)
    return qs.filter(sales_order_id__in=order_ids)


def can_access_production_order(user, production_order):
    return production_orders_queryset_for_user(user).filter(pk=production_order.pk).exists()


def calculate_piece_progress(piece):
    stages = piece.stages.filter(is_required=True)
    total = stages.count()
    if total == 0:
        return Decimal("0")
    done = stages.filter(
        status__in={PieceStageStatus.COMPLETED, PieceStageStatus.SKIPPED},
    ).count()
    return Decimal(done * 100 / total).quantize(Decimal("0.01"))


def calculate_order_progress(production_order):
    pieces = production_order.pieces.all()
    if not pieces:
        return Decimal("0")
    total = Decimal("0")
    for piece in pieces:
        total += calculate_piece_progress(piece)
    return (total / len(pieces)).quantize(Decimal("0.01"))


def is_sales_order_overdue(order, *, today=None):
    today = today or timezone.localdate()
    if order.status in TERMINAL_ORDER_STATUSES:
        return False
    if not order.promised_date:
        return False
    return order.promised_date < today


def is_production_order_overdue(production_order, *, today=None):
    today = today or timezone.localdate()
    if production_order.status in {
        ProductionOrderStatus.COMPLETED,
        ProductionOrderStatus.CANCELLED,
    }:
        return False
    if not production_order.planned_end_date:
        return False
    return production_order.planned_end_date < today


def overdue_sales_orders(*, user=None, today=None):
    today = today or timezone.localdate()
    qs = sales_orders_queryset_for_user(user) if user else SalesOrder.objects.all()
    return qs.exclude(status__in=TERMINAL_ORDER_STATUSES).filter(
        promised_date__lt=today,
        promised_date__isnull=False,
    )


def overdue_production_orders(*, user=None, today=None):
    today = today or timezone.localdate()
    qs = production_orders_queryset_for_user(user) if user else ProductionOrder.objects.all()
    return qs.exclude(
        status__in={ProductionOrderStatus.COMPLETED, ProductionOrderStatus.CANCELLED},
    ).filter(planned_end_date__lt=today, planned_end_date__isnull=False)


def dashboard_metrics(*, user=None, start=None, end=None):
    today = timezone.localdate()
    start = start or today - timedelta(days=30)
    end = end or today

    orders_qs = sales_orders_queryset_for_user(user) if user else SalesOrder.objects.all()
    prod_qs = production_orders_queryset_for_user(user) if user else ProductionOrder.objects.all()
    pieces_qs = ProductionPiece.objects.filter(production_order__in=prod_qs)

    cut_stages = ProductionStage.objects.filter(slug__in=["corte"]).values_list("pk", flat=True)
    finish_stages = ProductionStage.objects.filter(slug__in=["acabamento"]).values_list("pk", flat=True)
    polish_stages = ProductionStage.objects.filter(slug__in=["polimento"]).values_list("pk", flat=True)

    return {
        "orders_technical_review": orders_qs.filter(status=SalesOrderStatus.TECHNICAL_REVIEW).count(),
        "orders_awaiting_measurement": orders_qs.filter(
            status=SalesOrderStatus.AWAITING_MEASUREMENT,
        ).count(),
        "orders_ready_for_production": orders_qs.filter(
            status=SalesOrderStatus.READY_FOR_PRODUCTION,
        ).count(),
        "production_open": prod_qs.exclude(
            status__in={ProductionOrderStatus.COMPLETED, ProductionOrderStatus.CANCELLED},
        ).count(),
        "production_in_progress": prod_qs.filter(status=ProductionOrderStatus.IN_PROGRESS).count(),
        "production_on_hold": prod_qs.filter(status=ProductionOrderStatus.ON_HOLD).count(),
        "pieces_in_cut": ProductionPieceStage.objects.filter(
            stage_id__in=cut_stages,
            status=PieceStageStatus.IN_PROGRESS,
            piece__production_order__in=prod_qs,
        ).count(),
        "pieces_in_finish": ProductionPieceStage.objects.filter(
            stage_id__in=finish_stages,
            status=PieceStageStatus.IN_PROGRESS,
            piece__production_order__in=prod_qs,
        ).count(),
        "pieces_in_polish": ProductionPieceStage.objects.filter(
            stage_id__in=polish_stages,
            status=PieceStageStatus.IN_PROGRESS,
            piece__production_order__in=prod_qs,
        ).count(),
        "awaiting_quality": pieces_qs.filter(status=ProductionPieceStatus.QUALITY_CONTROL).count(),
        "rejected_pieces": pieces_qs.filter(status=ProductionPieceStatus.REWORK).count(),
        "rework_count": pieces_qs.filter(status=ProductionPieceStatus.REWORK).count(),
        "ready_for_delivery": orders_qs.filter(status=SalesOrderStatus.READY_FOR_DELIVERY).count(),
        "deliveries_scheduled": DeliverySchedule.objects.filter(
            sales_order__in=orders_qs,
            status=ScheduleStatus.SCHEDULED,
        ).count(),
        "installations_scheduled": InstallationSchedule.objects.filter(
            sales_order__in=orders_qs,
            status=ScheduleStatus.SCHEDULED,
        ).count(),
        "orders_overdue": overdue_sales_orders(user=user).count(),
        "production_overdue": overdue_production_orders(user=user).count(),
        "completed_in_period": prod_qs.filter(
            status=ProductionOrderStatus.COMPLETED,
            actual_end_at__date__gte=start,
            actual_end_at__date__lte=end,
        ).count(),
        "avg_stage_minutes": ProductionPieceStage.objects.filter(
            piece__production_order__in=prod_qs,
            status=PieceStageStatus.COMPLETED,
            started_at__isnull=False,
            completed_at__isnull=False,
        ).annotate(
            duration=Count("id"),
        ).aggregate(avg=Avg("duration"))["avg"],
        "stage_bottlenecks": list(
            ProductionPieceStage.objects.filter(
                piece__production_order__in=prod_qs,
                status__in={PieceStageStatus.IN_PROGRESS, PieceStageStatus.BLOCKED},
            )
            .values("stage__name")
            .annotate(total=Count("id"))
            .order_by("-total")[:5],
        ),
        "deliveries_today": DeliverySchedule.objects.filter(
            sales_order__in=orders_qs,
            scheduled_date=today,
            status__in={ScheduleStatus.SCHEDULED, ScheduleStatus.PENDING},
        ).count(),
        "installations_today": InstallationSchedule.objects.filter(
            sales_order__in=orders_qs,
            scheduled_date=today,
            status__in={ScheduleStatus.SCHEDULED, ScheduleStatus.PENDING},
        ).count(),
        "inspections_rejected": pieces_qs.filter(
            inspections__status=QualityInspectionStatus.REJECTED,
        ).distinct().count(),
    }


def board_data(*, user=None, limit=50):
    prod_qs = production_orders_queryset_for_user(user) if user else ProductionOrder.objects.all()
    prod_qs = prod_qs.exclude(
        status__in={ProductionOrderStatus.COMPLETED, ProductionOrderStatus.CANCELLED},
    ).select_related("sales_order", "sales_order__customer")

    columns = {}
    active_stages = ProductionStage.objects.filter(is_active=True).order_by("display_order")
    for stage in active_stages:
        column_key = stage.board_column or stage.slug
        columns.setdefault(column_key, {"label": stage.name, "cards": []})

    columns.setdefault("waiting", {"label": "Aguardando", "cards": []})
    columns.setdefault("done", {"label": "Concluído", "cards": []})

    for production in prod_qs[:limit]:
        current_stage = (
            ProductionPieceStage.objects.filter(
                piece__production_order=production,
                status__in={
                    PieceStageStatus.IN_PROGRESS,
                    PieceStageStatus.READY,
                    PieceStageStatus.BLOCKED,
                },
            )
            .select_related("stage", "piece")
            .order_by("sequence")
            .first()
        )
        if not current_stage:
            column_key = "waiting"
            stage_label = "Aguardando"
        else:
            column_key = current_stage.stage.board_column or current_stage.stage.slug
            stage_label = current_stage.stage.name
            columns.setdefault(column_key, {"label": stage_label, "cards": []})

        card = {
            "production_order": production,
            "piece": current_stage.piece if current_stage else None,
            "stage": stage_label,
            "customer": production.sales_order.customer,
            "priority": production.priority,
            "overdue": is_production_order_overdue(production),
            "progress": calculate_order_progress(production),
        }
        if len(columns[column_key]["cards"]) < limit:
            columns[column_key]["cards"].append(card)

    return columns
