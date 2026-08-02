from django.db.models import Count
from django.db.models import Q
from django.utils import timezone

from production.models import PieceStageStatus
from production.models import ProductionOrder
from production.models import ProductionOrderStatus
from production.models import ProductionPiece
from production.models import ProductionPieceStage
from production.models import ProductionPieceStatus
from production.models import ProductionStage
from production.models import QualityInspection
from production.models import QualityInspectionStatus
from production.models import SalesOrder
from production.models import SalesOrderStatus
from production.selectors import dashboard_metrics
from production.selectors import overdue_production_orders
from production.selectors import overdue_sales_orders


def production_metrics(*, user, start, end, filters=None):
    filters = filters or {}
    # dashboard_metrics espera datas date; converter
    start_date = timezone.localdate(start) if hasattr(start, "hour") else start
    end_date = timezone.localdate(end) if hasattr(end, "hour") else end
    base = dashboard_metrics(user=user, start=start_date, end=end_date)

    orders = SalesOrder.objects.all()
    prod = ProductionOrder.objects.select_related("sales_order", "responsible")
    if filters.get("salesperson"):
        orders = orders.filter(salesperson_id=filters["salesperson"])
        prod = prod.filter(sales_order__salesperson_id=filters["salesperson"])
    if filters.get("order_status"):
        orders = orders.filter(status=filters["order_status"])
    if filters.get("production_responsible"):
        prod = prod.filter(responsible_id=filters["production_responsible"])
    if filters.get("material"):
        prod = prod.filter(pieces__material_id=filters["material"]).distinct()

    pieces = ProductionPiece.objects.filter(production_order__in=prod)
    stages = ProductionPieceStage.objects.filter(piece__in=pieces)

    if filters.get("production_stage"):
        stages = stages.filter(stage_id=filters["production_stage"])

    base.update(
        {
            "orders_paused": prod.filter(status=ProductionOrderStatus.ON_HOLD).count(),
            "pieces_ready": pieces.filter(status=ProductionPieceStatus.READY).count(),
            "by_stage": list(
                stages.filter(
                    status__in={
                        PieceStageStatus.PENDING,
                        PieceStageStatus.IN_PROGRESS,
                        PieceStageStatus.BLOCKED,
                    },
                )
                .values("stage__name")
                .annotate(total=Count("id"))
                .order_by("-total")[:10],
            ),
            "by_responsible": list(
                prod.exclude(responsible__isnull=True)
                .values("responsible__username")
                .annotate(total=Count("id"))
                .order_by("-total")[:10],
            ),
            "by_priority": list(
                prod.values("priority").annotate(total=Count("id")).order_by("-total"),
            ),
            "overdue_orders": overdue_sales_orders(user=user).count(),
            "overdue_production": overdue_production_orders(user=user).count(),
        },
    )
    return base


def production_bottlenecks(*, user=None, filters=None):
    filters = filters or {}
    stages = ProductionPieceStage.objects.select_related("stage", "piece").filter(
        status__in={
            PieceStageStatus.PENDING,
            PieceStageStatus.IN_PROGRESS,
            PieceStageStatus.BLOCKED,
        },
    )
    if filters.get("production_stage"):
        stages = stages.filter(stage_id=filters["production_stage"])

    rows = []
    for stage in ProductionStage.objects.filter(is_active=True):
        qs = stages.filter(stage=stage)
        volume = qs.count()
        blocked = qs.filter(status=PieceStageStatus.BLOCKED).count()
        # Tempo médio só com started_at/completed_at — para fila aberta, não inventar
        overdue = qs.filter(
            piece__production_order__planned_end_date__lt=timezone.localdate(),
        ).count()
        if volume or blocked:
            rows.append(
                {
                    "stage": stage.name,
                    "volume": volume,
                    "blocked": blocked,
                    "overdue": overdue,
                    "avg_hours": None,
                },
            )
    rows.sort(key=lambda r: (r["blocked"], r["overdue"], r["volume"]), reverse=True)

    from materials.stock_models import SlabReservation

    pieces_with_active = SlabReservation.objects.filter(
        status__in=["active", "partially_consumed"],
    ).values_list("production_piece_id", flat=True)
    pieces_without_slab = (
        ProductionPiece.objects.exclude(pk__in=pieces_with_active)
        .exclude(
            production_order__status__in=[
                ProductionOrderStatus.COMPLETED,
                ProductionOrderStatus.CANCELLED,
            ],
        )
        .count()
    )

    paused = ProductionOrder.objects.filter(status=ProductionOrderStatus.ON_HOLD).count()
    return {
        "stages": rows[:8],
        "pieces_without_slab": pieces_without_slab,
        "paused_orders": paused,
        "no_responsible": ProductionOrder.objects.filter(
            responsible__isnull=True,
        )
        .exclude(
            status__in=[ProductionOrderStatus.COMPLETED, ProductionOrderStatus.CANCELLED],
        )
        .count(),
    }


def quality_metrics(*, start, end):
    inspections = QualityInspection.objects.filter(created_at__gte=start, created_at__lte=end)
    total = inspections.count()
    approved = inspections.filter(status=QualityInspectionStatus.APPROVED).count()
    approved_notes = 0
    if hasattr(QualityInspectionStatus, "APPROVED_WITH_NOTES"):
        approved_notes = inspections.filter(
            status=QualityInspectionStatus.APPROVED_WITH_NOTES,
        ).count()
    rejected = inspections.filter(status=QualityInspectionStatus.REJECTED).count()
    from commercial.performance_metrics import safe_rate

    return {
        "inspections": total,
        "approved": approved,
        "approved_with_notes": approved_notes,
        "rejected": rejected,
        "approval_rate": safe_rate(approved + approved_notes, total),
        "rework_pieces": ProductionPiece.objects.filter(
            status=ProductionPieceStatus.REWORK,
        ).count(),
        "by_status": list(inspections.values("status").annotate(total=Count("id"))),
    }
