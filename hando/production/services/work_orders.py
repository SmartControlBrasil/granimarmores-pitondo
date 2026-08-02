# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from production.models import PieceStageStatus
from production.models import ProductionLogType
from production.models import ProductionOrder
from production.models import ProductionOrderStatus
from production.models import ProductionPiece
from production.models import ProductionPieceStage
from production.models import ProductionPieceStatus
from production.models import ProductionStage
from production.models import SalesOrderStatus
from production.services.logging import add_production_log
from production.services.numbering import next_production_order_number


@transaction.atomic
def create_production_order(*, sales_order, actor, request=None, priority="normal", planned_start_date=None, planned_end_date=None):
    if not user_has_permission(actor, "production_orders.create"):
        raise PermissionDenied("Sem permissão para criar ordem de produção.")
    if sales_order.status not in {
        SalesOrderStatus.CONFIRMED,
        SalesOrderStatus.TECHNICAL_REVIEW,
        SalesOrderStatus.AWAITING_MEASUREMENT,
        SalesOrderStatus.READY_FOR_PRODUCTION,
        SalesOrderStatus.IN_PRODUCTION,
    }:
        raise ValidationError("Pedido não está em estado válido para ordem de produção.")

    existing = ProductionOrder.objects.filter(sales_order=sales_order).exclude(
        status=ProductionOrderStatus.CANCELLED,
    ).first()
    if existing:
        return existing

    order = ProductionOrder.objects.create(
        number=next_production_order_number(),
        sales_order=sales_order,
        status=ProductionOrderStatus.DRAFT,
        priority=priority,
        planned_start_date=planned_start_date,
        planned_end_date=planned_end_date,
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="production",
        action="production_order_created",
        obj=order,
        metadata={"sales_order_number": sales_order.number},
    )
    return order


@transaction.atomic
def release_production_order(*, production_order, actor, request=None, responsible=None):
    if not user_has_permission(actor, "production_orders.change_status"):
        raise PermissionDenied("Sem permissão para liberar ordem.")
    if production_order.status != ProductionOrderStatus.DRAFT:
        raise ValidationError("Somente ordens em rascunho podem ser liberadas.")
    if not production_order.pieces.exists():
        raise ValidationError("Ordem exige peças antes da liberação.")

    production_order.status = ProductionOrderStatus.RELEASED
    if responsible:
        production_order.responsible = responsible
    production_order.updated_by = actor
    production_order.save(update_fields=["status", "responsible", "updated_by", "updated_at"])

    add_production_log(
        production_order=production_order,
        log_type=ProductionLogType.NOTE,
        description="Ordem liberada para produção.",
        actor=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="production_order_released",
        obj=production_order,
    )
    return production_order


@transaction.atomic
def start_production_order(*, production_order, actor, request=None):
    if not user_has_permission(actor, "production_orders.start"):
        raise PermissionDenied("Sem permissão para iniciar ordem.")
    if production_order.status not in {ProductionOrderStatus.RELEASED, ProductionOrderStatus.PLANNED}:
        raise ValidationError("Ordem não está liberada para início.")
    if not production_order.pieces.exists():
        raise ValidationError("Ordem exige peças antes do início.")

    now = timezone.now()
    production_order.status = ProductionOrderStatus.IN_PROGRESS
    production_order.actual_start_at = production_order.actual_start_at or now
    production_order.updated_by = actor
    production_order.save(update_fields=["status", "actual_start_at", "updated_by", "updated_at"])

    sales_order = production_order.sales_order
    if sales_order.status == SalesOrderStatus.READY_FOR_PRODUCTION:
        sales_order.status = SalesOrderStatus.IN_PRODUCTION
        sales_order.updated_by = actor
        sales_order.save(update_fields=["status", "updated_by", "updated_at"])

    add_production_log(
        production_order=production_order,
        log_type=ProductionLogType.START,
        description="Ordem de produção iniciada.",
        actor=actor,
        started_at=now,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="production_order_started",
        obj=production_order,
    )
    return production_order


@transaction.atomic
def pause_production_order(*, production_order, actor, reason, request=None):
    if not user_has_permission(actor, "production_orders.pause"):
        raise PermissionDenied("Sem permissão para pausar ordem.")
    if production_order.status not in {
        ProductionOrderStatus.IN_PROGRESS,
        ProductionOrderStatus.RELEASED,
    }:
        raise ValidationError("Ordem não pode ser pausada neste estado.")
    if not reason.strip():
        raise ValidationError("Motivo obrigatório para pausa.")

    production_order.status = ProductionOrderStatus.ON_HOLD
    production_order.hold_reason = reason.strip()
    production_order.updated_by = actor
    production_order.save(update_fields=["status", "hold_reason", "updated_by", "updated_at"])

    add_production_log(
        production_order=production_order,
        log_type=ProductionLogType.PAUSE,
        description=reason.strip(),
        actor=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="production_order_paused",
        obj=production_order,
        metadata={"reason": reason[:500]},
    )
    return production_order


@transaction.atomic
def resume_production_order(*, production_order, actor, request=None):
    if not user_has_permission(actor, "production_orders.start"):
        raise PermissionDenied("Sem permissão para retomar ordem.")
    if production_order.status != ProductionOrderStatus.ON_HOLD:
        raise ValidationError("Ordem não está pausada.")

    production_order.status = ProductionOrderStatus.IN_PROGRESS
    production_order.hold_reason = ""
    production_order.updated_by = actor
    production_order.save(update_fields=["status", "hold_reason", "updated_by", "updated_at"])

    add_production_log(
        production_order=production_order,
        log_type=ProductionLogType.RESUME,
        description="Ordem retomada.",
        actor=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="production_order_resumed",
        obj=production_order,
    )
    return production_order


def _all_required_stages_complete(production_order):
    if not ProductionPieceStage.objects.filter(piece__production_order=production_order).exists():
        return False
    incomplete = ProductionPieceStage.objects.filter(
        piece__production_order=production_order,
        is_required=True,
    ).exclude(status__in={PieceStageStatus.COMPLETED, PieceStageStatus.SKIPPED})
    return not incomplete.exists()


@transaction.atomic
def complete_production_order(*, production_order, actor, request=None):
    if not user_has_permission(actor, "production_orders.complete"):
        raise PermissionDenied("Sem permissão para concluir ordem.")
    if production_order.status not in {
        ProductionOrderStatus.IN_PROGRESS,
        ProductionOrderStatus.QUALITY_CONTROL,
    }:
        raise ValidationError("Ordem não está em andamento.")
    if not _all_required_stages_complete(production_order):
        raise ValidationError("Etapas obrigatórias pendentes.")

    now = timezone.now()
    production_order.status = ProductionOrderStatus.COMPLETED
    production_order.actual_end_at = now
    production_order.updated_by = actor
    production_order.save(update_fields=["status", "actual_end_at", "updated_by", "updated_at"])

    add_production_log(
        production_order=production_order,
        log_type=ProductionLogType.COMPLETION,
        description="Ordem de produção concluída.",
        actor=actor,
        ended_at=now,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="production_order_completed",
        obj=production_order,
    )
    return production_order


@transaction.atomic
def cancel_production_order(*, production_order, actor, reason, request=None):
    if not user_has_permission(actor, "production_orders.cancel"):
        raise PermissionDenied("Sem permissão para cancelar ordem.")
    if not reason.strip():
        raise ValidationError("Motivo obrigatório para cancelamento.")
    if production_order.status == ProductionOrderStatus.COMPLETED:
        raise ValidationError("Ordem concluída não pode ser cancelada.")

    production_order.status = ProductionOrderStatus.CANCELLED
    production_order.cancel_reason = reason.strip()
    production_order.updated_by = actor
    production_order.save(update_fields=["status", "cancel_reason", "updated_by", "updated_at"])

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="production_order_cancelled",
        obj=production_order,
        metadata={"reason": reason[:500]},
    )
    return production_order


@transaction.atomic
def generate_pieces_from_order(*, production_order, actor, request=None):
    if not user_has_permission(actor, "production_pieces.create"):
        raise PermissionDenied("Sem permissão para gerar peças.")
    if production_order.pieces.exists():
        raise ValidationError("Peças já geradas para esta ordem.")

    sales_order = production_order.sales_order
    created = []
    for index, item in enumerate(sales_order.items.order_by("position"), start=1):
        code = f"P{index:03d}"
        piece = ProductionPiece.objects.create(
            production_order=production_order,
            order_item=item,
            code=code,
            description=item.description,
            quantity=item.quantity,
            material=item.material,
            material_name_snapshot=item.material_name_snapshot,
            finish_name_snapshot=item.finish_name_snapshot,
            width=item.width,
            height=item.height,
            depth=item.depth,
            area=item.area,
            status=ProductionPieceStatus.PENDING,
        )
        created.append(piece)

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="production",
        action="production_pieces_generated",
        obj=production_order,
        metadata={"count": len(created)},
    )
    return created


@transaction.atomic
def generate_piece_stages(*, piece, actor, request=None):
    if not user_has_permission(actor, "production_stages.create"):
        raise PermissionDenied("Sem permissão para gerar etapas.")
    if piece.stages.exists():
        raise ValidationError("Etapas já existem para esta peça.")

    stages = ProductionStage.objects.filter(is_active=True).order_by("display_order")
    created = []
    for sequence, stage in enumerate(stages, start=1):
        piece_stage = ProductionPieceStage.objects.create(
            piece=piece,
            stage=stage,
            sequence=sequence,
            status=PieceStageStatus.PENDING if sequence > 1 else PieceStageStatus.READY,
            is_required=stage.is_required,
        )
        created.append(piece_stage)

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="production",
        action="piece_stages_generated",
        obj=piece,
        metadata={"count": len(created)},
    )
    return created


@transaction.atomic
def assign_slab(*, piece, slab, actor, request=None):
    if not user_has_permission(actor, "production_pieces.update"):
        raise PermissionDenied("Sem permissão para associar chapa.")
    piece.slab = slab
    piece.save(update_fields=["slab", "updated_at"])
    add_production_log(
        production_order=piece.production_order,
        piece=piece,
        log_type=ProductionLogType.MATERIAL_CHANGE,
        description=f"Chapa associada: {slab}",
        actor=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="piece_slab_assigned",
        obj=piece,
        metadata={"slab_id": slab.pk},
    )
    return piece


@transaction.atomic
def record_rework(*, piece, actor, reason, request=None):
    if not user_has_permission(actor, "production_pieces.update"):
        raise PermissionDenied("Sem permissão para registrar retrabalho.")
    if not reason.strip():
        raise ValidationError("Motivo obrigatório para retrabalho.")

    piece.status = ProductionPieceStatus.REWORK
    piece.save(update_fields=["status", "updated_at"])
    add_production_log(
        production_order=piece.production_order,
        piece=piece,
        log_type=ProductionLogType.REWORK,
        description=reason.strip(),
        actor=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="piece_rework",
        obj=piece,
        metadata={"reason": reason[:500]},
    )
    return piece
