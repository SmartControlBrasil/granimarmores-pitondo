# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from production.models import PieceStageStatus
from production.models import ProductionLogType
from production.models import ProductionPieceStage
from production.services.logging import add_production_log


def _activate_next_stage(piece_stage):
    next_stage = (
        ProductionPieceStage.objects.filter(
            piece=piece_stage.piece,
            sequence__gt=piece_stage.sequence,
            status=PieceStageStatus.PENDING,
        )
        .order_by("sequence")
        .first()
    )
    if next_stage:
        next_stage.status = PieceStageStatus.READY
        next_stage.save(update_fields=["status", "updated_at"])


@transaction.atomic
def start_stage(*, piece_stage, actor, request=None):
    if not user_has_permission(actor, "production_stages.start"):
        raise PermissionDenied("Sem permissão para iniciar etapa.")
    if piece_stage.status not in {PieceStageStatus.READY, PieceStageStatus.PENDING}:
        raise ValidationError("Etapa não está pronta para início.")

    in_progress = ProductionPieceStage.objects.filter(
        piece=piece_stage.piece,
        status=PieceStageStatus.IN_PROGRESS,
    ).exclude(pk=piece_stage.pk).exists()
    if in_progress:
        raise ValidationError("Outra etapa já está em andamento nesta peça.")

    now = timezone.now()
    piece_stage.status = PieceStageStatus.IN_PROGRESS
    piece_stage.started_at = now
    piece_stage.assigned_to = actor
    piece_stage.save(update_fields=["status", "started_at", "assigned_to", "updated_at"])

    add_production_log(
        production_order=piece_stage.piece.production_order,
        piece=piece_stage.piece,
        piece_stage=piece_stage,
        log_type=ProductionLogType.START,
        description=f"Início: {piece_stage.stage.name}",
        actor=actor,
        started_at=now,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="piece_stage_started",
        obj=piece_stage,
    )
    return piece_stage


@transaction.atomic
def complete_stage(*, piece_stage, actor, request=None, notes=""):
    if not user_has_permission(actor, "production_stages.complete"):
        raise PermissionDenied("Sem permissão para concluir etapa.")
    if piece_stage.status != PieceStageStatus.IN_PROGRESS:
        raise ValidationError("Etapa não está em andamento.")

    now = timezone.now()
    piece_stage.status = PieceStageStatus.COMPLETED
    piece_stage.completed_at = now
    piece_stage.completed_by = actor
    if notes:
        piece_stage.notes = notes
    piece_stage.save(update_fields=[
        "status",
        "completed_at",
        "completed_by",
        "notes",
        "updated_at",
    ])

    _activate_next_stage(piece_stage)

    add_production_log(
        production_order=piece_stage.piece.production_order,
        piece=piece_stage.piece,
        piece_stage=piece_stage,
        log_type=ProductionLogType.COMPLETION,
        description=f"Conclusão: {piece_stage.stage.name}",
        actor=actor,
        ended_at=now,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="piece_stage_completed",
        obj=piece_stage,
    )
    return piece_stage


@transaction.atomic
def block_stage(*, piece_stage, actor, reason, request=None):
    if not user_has_permission(actor, "production_stages.update"):
        raise PermissionDenied("Sem permissão para bloquear etapa.")
    if not reason.strip():
        raise ValidationError("Motivo obrigatório para bloqueio.")

    piece_stage.status = PieceStageStatus.BLOCKED
    piece_stage.notes = reason.strip()
    piece_stage.save(update_fields=["status", "notes", "updated_at"])

    add_production_log(
        production_order=piece_stage.piece.production_order,
        piece=piece_stage.piece,
        piece_stage=piece_stage,
        log_type=ProductionLogType.ISSUE,
        description=reason.strip(),
        actor=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="piece_stage_blocked",
        obj=piece_stage,
        metadata={"reason": reason[:500]},
    )
    return piece_stage


@transaction.atomic
def skip_stage(*, piece_stage, actor, reason, request=None):
    if not user_has_permission(actor, "production_stages.skip"):
        raise PermissionDenied("Sem permissão para pular etapa.")
    if piece_stage.is_required and not user_has_permission(actor, "production_stages.skip"):
        raise PermissionDenied("Etapa obrigatória exige permissão especial.")
    if not reason.strip():
        raise ValidationError("Justificativa obrigatória para pular etapa.")
    if piece_stage.status in {PieceStageStatus.COMPLETED, PieceStageStatus.SKIPPED}:
        raise ValidationError("Etapa já encerrada.")

    piece_stage.status = PieceStageStatus.SKIPPED
    piece_stage.skip_reason = reason.strip()
    piece_stage.completed_by = actor
    piece_stage.completed_at = timezone.now()
    piece_stage.save(update_fields=[
        "status",
        "skip_reason",
        "completed_by",
        "completed_at",
        "updated_at",
    ])

    _activate_next_stage(piece_stage)

    add_production_log(
        production_order=piece_stage.piece.production_order,
        piece=piece_stage.piece,
        piece_stage=piece_stage,
        log_type=ProductionLogType.NOTE,
        description=f"Etapa pulada: {reason.strip()}",
        actor=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="piece_stage_skipped",
        obj=piece_stage,
        metadata={"reason": reason[:500]},
    )
    return piece_stage
