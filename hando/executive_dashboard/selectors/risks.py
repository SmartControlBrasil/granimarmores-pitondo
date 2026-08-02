from django.db.models import Q
from django.utils import timezone

from after_sales.models import AfterSalesCase
from after_sales.models import CaseSeverity
from after_sales.models import CaseStatus
from after_sales.models import InstallationPendingItem
from after_sales.models import OPEN_CASE_STATUSES
from after_sales.models import PendingStatus
from materials.stock_models import SlabReservation
from production.models import ProductionOrderStatus
from production.models import ProductionPiece
from production.models import QualityInspectionStatus
from production.models import SalesOrder
from production.models import SalesOrderStatus
from production.models import ScheduleStatus


RISK_ATTENTION = "Atenção"
RISK_HIGH = "Alto risco"
RISK_CRITICAL = "Crítico"
RISK_NONE = "Sem risco identificado"


def orders_at_risk(*, limit=40, filters=None):
    filters = filters or {}
    today = timezone.localdate()
    qs = (
        SalesOrder.objects.exclude(
            status__in=[SalesOrderStatus.COMPLETED, SalesOrderStatus.CANCELLED],
        )
        .select_related("customer", "salesperson", "production_order")
        .prefetch_related("deliveries", "installations", "after_sales_cases", "installation_pending_items")
    )
    if filters.get("salesperson"):
        qs = qs.filter(salesperson_id=filters["salesperson"])
    if filters.get("order_status"):
        qs = qs.filter(status=filters["order_status"])

    active_piece_ids = set(
        SlabReservation.objects.filter(
            status__in=["active", "partially_consumed"],
        ).values_list("production_piece_id", flat=True),
    )

    rows = []
    for order in qs[:200]:
        reasons = []
        score = 0
        if order.promised_date and order.promised_date < today:
            reasons.append("Prazo vencido")
            score += 3
        elif order.promised_date and (order.promised_date - today).days <= 3:
            reasons.append("Prazo próximo")
            score += 1

        prod = getattr(order, "production_order", None)
        if prod:
            if prod.status == ProductionOrderStatus.ON_HOLD:
                reasons.append("Ordem pausada")
                score += 2
            if prod.status == ProductionOrderStatus.DRAFT and order.promised_date:
                if (order.promised_date - today).days <= 7:
                    reasons.append("Produção não iniciada próxima ao prazo")
                    score += 2
            pieces = ProductionPiece.objects.filter(production_order=prod)
            missing_slab = pieces.exclude(pk__in=active_piece_ids).exists()
            if missing_slab:
                reasons.append("Peça sem chapa")
                score += 2
            if pieces.filter(inspections__status=QualityInspectionStatus.REJECTED).exists():
                reasons.append("Inspeção rejeitada")
                score += 2
            if pieces.filter(piece_stages__status="blocked").exists():
                reasons.append("Etapa bloqueada")
                score += 2

        if not order.deliveries.filter(
            status__in=[ScheduleStatus.SCHEDULED, ScheduleStatus.COMPLETED, ScheduleStatus.IN_TRANSIT],
        ).exists() and order.status in {
            SalesOrderStatus.READY_FOR_DELIVERY,
            SalesOrderStatus.IN_PRODUCTION,
        }:
            reasons.append("Entrega não agendada")
            score += 1

        if order.installation_required and not order.installations.filter(
            status__in=[ScheduleStatus.SCHEDULED, ScheduleStatus.COMPLETED],
        ).exists():
            reasons.append("Instalação não agendada")
            score += 1

        if order.installation_pending_items.filter(
            status__in=[PendingStatus.OPEN, PendingStatus.SCHEDULED],
            priority__in=["high", "urgent"],
        ).exists():
            reasons.append("Pendência crítica de instalação")
            score += 2

        if order.after_sales_cases.filter(
            status__in=OPEN_CASE_STATUSES,
            severity=CaseSeverity.CRITICAL,
        ).exists():
            reasons.append("Assistência crítica aberta")
            score += 3

        if not reasons:
            level = RISK_NONE
        elif score >= 5:
            level = RISK_CRITICAL
        elif score >= 3:
            level = RISK_HIGH
        else:
            level = RISK_ATTENTION

        if reasons:
            rows.append(
                {
                    "order": order,
                    "level": level,
                    "score": score,
                    "reasons": reasons,
                },
            )

    order_map = {RISK_CRITICAL: 0, RISK_HIGH: 1, RISK_ATTENTION: 2, RISK_NONE: 3}
    rows.sort(key=lambda r: (order_map.get(r["level"], 9), -r["score"]))
    return rows[:limit]


def build_executive_alerts(*, user, domains):
    alerts = []
    commercial = domains.get("commercial") or {}
    production = domains.get("production") or {}
    schedule = domains.get("schedule") or {}
    after_sales = domains.get("after_sales") or {}
    stock = domains.get("stock") or {}
    media = domains.get("media") or {}
    bottlenecks = domains.get("bottlenecks") or {}

    def add(level, message, url_name, query=""):
        alerts.append({"level": level, "message": message, "url_name": url_name, "query": query})

    if commercial.get("leads_no_contact"):
        add("warning", f"{commercial['leads_no_contact']} lead(s) sem contato", "leads:list", "sem_contato=1")
    if commercial.get("leads_no_owner"):
        add("warning", f"{commercial['leads_no_owner']} lead(s) sem responsável", "leads:list", "unassigned=1")
    if production.get("orders_overdue") or production.get("overdue_orders"):
        n = production.get("orders_overdue") or production.get("overdue_orders")
        add("danger", f"{n} pedido(s) atrasado(s)", "operacao:order_list", "overdue=1")
    if production.get("production_on_hold") or production.get("orders_paused"):
        n = production.get("orders_paused") or production.get("production_on_hold")
        add("warning", f"{n} ordem(ns) pausada(s)", "producao:production_list", "status=on_hold")
    if bottlenecks.get("pieces_without_slab"):
        add("warning", f"{bottlenecks['pieces_without_slab']} peça(s) sem chapa", "stock:reservation_list", "")
    if production.get("inspections_rejected"):
        add("danger", f"{production['inspections_rejected']} inspeção(ões) rejeitada(s)", "producao:production_list", "status=quality_control")
    if schedule.get("conflicts"):
        add("danger", f"{schedule['conflicts']} conflito(s) de agenda", "scheduling:event_list", "conflict=1")
    if after_sales.get("critical"):
        add("danger", f"{after_sales['critical']} caso(s) crítico(s) pós-venda", "after_sales:case_list", "critical=1")
    if after_sales.get("overdue_pending"):
        add("warning", f"{after_sales['overdue_pending']} pendência(s) vencida(s)", "after_sales:pending_list", "open=1")
    if stock.get("blocked_slabs"):
        add("info", f"{stock['blocked_slabs']} chapa(s) bloqueada(s)", "stock:slab_list", "blocked=1")
    if media and media.get("under_review"):
        add("info", f"{media['under_review']} mídia(s) em revisão", "media_library:review_queue", "")
    return alerts
