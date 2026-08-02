from datetime import timedelta
from decimal import Decimal

from django.db.models import Count
from django.db.models import Q
from django.db.models import Sum
from django.utils import timezone

from materials.models import Material
from materials.models import MaterialSlab
from materials.stock_models import SlabLoss
from materials.stock_models import SlabReservation
from materials.stock_models import StockInventory
from production.models import ProductionPiece
from production.models import ProductionPieceStatus


def parse_stock_period(request):
    period = request.GET.get("period", "month")
    now = timezone.now()
    if period == "week":
        start = now - timedelta(days=7)
    elif period == "year":
        start = now - timedelta(days=365)
    else:
        start = now - timedelta(days=30)
    return start, now, period


def stock_dashboard_metrics(*, request=None, start=None, end=None, material_id=None, location_id=None, supplier_id=None, status=None):
    start = start or (timezone.now() - timedelta(days=30))
    end = end or timezone.now()

    slab_qs = MaterialSlab.objects.filter(is_active=True)
    if material_id:
        slab_qs = slab_qs.filter(material_id=material_id)
    if location_id:
        slab_qs = slab_qs.filter(stock_location_id=location_id)
    if supplier_id:
        slab_qs = slab_qs.filter(supplier_ref_id=supplier_id)
    if status:
        slab_qs = slab_qs.filter(status=status)

    aggregates = slab_qs.aggregate(
        total_slabs=Count("pk"),
        available_slabs=Count("pk", filter=Q(status=MaterialSlab.Status.AVAILABLE)),
        total_available_area=Sum("available_area"),
        total_reserved_area=Sum("reserved_area"),
        total_consumed_area=Sum("consumed_area"),
        total_lost_area=Sum("lost_area"),
        blocked_slabs=Count("pk", filter=Q(status=MaterialSlab.Status.BLOCKED)),
        no_location=Count("pk", filter=Q(stock_location__isnull=True)),
    )

    consumed_period = SlabReservation.objects.filter(
        consumed_at__gte=start,
        consumed_at__lte=end,
    ).aggregate(total=Sum("consumed_area"))["total"] or Decimal("0.0000")

    lost_period = SlabLoss.objects.filter(
        occurred_at__gte=start,
        occurred_at__lte=end,
    ).aggregate(total=Sum("area"))["total"] or Decimal("0.0000")

    remnants = MaterialSlab.objects.filter(
        is_remnant=True,
        is_active=True,
        available_area__gt=0,
        status=MaterialSlab.Status.AVAILABLE,
    ).count()

    active_reservations = SlabReservation.objects.filter(
        status__in=[
            SlabReservation.Status.ACTIVE,
            SlabReservation.Status.PARTIALLY_CONSUMED,
        ],
    ).count()

    pieces_waiting = ProductionPiece.objects.filter(
        status__in=[
            ProductionPieceStatus.PENDING,
            ProductionPieceStatus.IN_PROGRESS,
            ProductionPieceStatus.READY,
        ],
    ).exclude(
        slab_reservations__status__in=[
            SlabReservation.Status.ACTIVE,
            SlabReservation.Status.PARTIALLY_CONSUMED,
        ],
    ).distinct().count()

    materials_without_stock = Material.objects.filter(
        is_active=True,
        is_stock_controlled=True,
    ).exclude(
        slabs__available_area__gt=0,
        slabs__is_active=True,
    ).count()

    open_inventories = StockInventory.objects.filter(
        status__in=[StockInventory.Status.DRAFT, StockInventory.Status.IN_PROGRESS],
    ).count()

    by_material = (
        slab_qs.values("material__name", "material_id")
        .annotate(
            slabs=Count("pk"),
            available=Sum("available_area"),
        )
        .order_by("-available")[:10]
    )
    by_location = (
        slab_qs.values("stock_location__name", "stock_location_id")
        .annotate(slabs=Count("pk"), available=Sum("available_area"))
        .order_by("-available")[:10]
    )
    by_supplier = (
        slab_qs.values("supplier_ref__name", "supplier_ref_id")
        .annotate(slabs=Count("pk"), available=Sum("available_area"))
        .order_by("-available")[:10]
    )
    by_status = (
        slab_qs.values("status")
        .annotate(count=Count("pk"))
        .order_by("status")
    )
    losses_by_reason = (
        SlabLoss.objects.filter(occurred_at__gte=start, occurred_at__lte=end)
        .values("loss_reason")
        .annotate(total=Sum("area"))
        .order_by("-total")
    )

    alerts = build_stock_alerts()

    return {
        **aggregates,
        "consumed_period": consumed_period,
        "lost_period": lost_period,
        "remnants_available": remnants,
        "active_reservations": active_reservations,
        "pieces_waiting_reservation": pieces_waiting,
        "materials_without_stock": materials_without_stock,
        "open_inventories": open_inventories,
        "by_material": list(by_material),
        "by_location": list(by_location),
        "by_supplier": list(by_supplier),
        "by_status": list(by_status),
        "losses_by_reason": list(losses_by_reason),
        "alerts": alerts,
    }


def build_stock_alerts():
    alerts = []

    no_loc = MaterialSlab.objects.filter(
        is_active=True,
        stock_location__isnull=True,
        location_text="",
    ).exclude(status=MaterialSlab.Status.DISCARDED).count()
    if no_loc:
        alerts.append({"level": "warning", "message": f"{no_loc} chapa(s) sem localização"})

    blocked = MaterialSlab.objects.filter(status=MaterialSlab.Status.BLOCKED, is_active=True).count()
    if blocked:
        alerts.append({"level": "info", "message": f"{blocked} chapa(s) bloqueada(s)"})

    inconsistent = MaterialSlab.objects.filter(is_active=True).extra(
        where=["available_area + reserved_area + consumed_area + lost_area > total_area + 0.0001"],
    ).count()
    if inconsistent:
        alerts.append({"level": "danger", "message": f"{inconsistent} chapa(s) com áreas inconsistentes"})

    orphan_reservations = SlabReservation.objects.filter(
        status=SlabReservation.Status.ACTIVE,
        production_piece__status__in=[
            ProductionPieceStatus.CANCELLED,
            ProductionPieceStatus.COMPLETED,
        ],
    ).count()
    if orphan_reservations:
        alerts.append({"level": "warning", "message": f"{orphan_reservations} reserva(s) em peça encerrada"})

    consumed_available = MaterialSlab.objects.filter(
        status=MaterialSlab.Status.AVAILABLE,
        consumed_area__gt=0,
    ).count()
    if consumed_available:
        alerts.append({"level": "warning", "message": f"{consumed_available} chapa(s) consumidas marcadas disponíveis"})

    remnant_no_loc = MaterialSlab.objects.filter(
        is_remnant=True,
        is_active=True,
        stock_location__isnull=True,
        available_area__gt=0,
    ).count()
    if remnant_no_loc:
        alerts.append({"level": "warning", "message": f"{remnant_no_loc} sobra(s) sem localização"})

    open_inv = StockInventory.objects.filter(
        status=StockInventory.Status.IN_PROGRESS,
    ).count()
    if open_inv:
        alerts.append({"level": "info", "message": f"{open_inv} inventário(s) em andamento"})

    return alerts


def main_dashboard_stock_summary():
    return {
        "pieces_without_slab": ProductionPiece.objects.filter(
            status__in=[
                ProductionPieceStatus.PENDING,
                ProductionPieceStatus.IN_PROGRESS,
                ProductionPieceStatus.READY,
            ],
        ).exclude(
            slab_reservations__status__in=[
                SlabReservation.Status.ACTIVE,
                SlabReservation.Status.PARTIALLY_CONSUMED,
            ],
        ).distinct().count(),
        "active_reservations": SlabReservation.objects.filter(
            status__in=[
                SlabReservation.Status.ACTIVE,
                SlabReservation.Status.PARTIALLY_CONSUMED,
            ],
        ).count(),
        "blocked_slabs": MaterialSlab.objects.filter(
            status=MaterialSlab.Status.BLOCKED,
            is_active=True,
        ).count(),
        "open_inventories": StockInventory.objects.filter(
            status=StockInventory.Status.IN_PROGRESS,
        ).count(),
    }
