# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from production.models import ProductionLogType
from production.models import ProductionPieceStatus
from production.models import QualityChecklist
from production.models import QualityChecklistItem
from production.models import QualityInspection
from production.models import QualityInspectionResult
from production.models import QualityInspectionStatus
from production.services.logging import add_production_log
from production.services.work_orders import record_rework


@transaction.atomic
def create_inspection(*, production_order, actor, piece=None, request=None):
    if not user_has_permission(actor, "quality_inspections.create"):
        raise PermissionDenied("Sem permissão para criar inspeção.")

    checklist = QualityChecklist.objects.filter(is_active=True).first()
    inspection = QualityInspection.objects.create(
        production_order=production_order,
        piece=piece,
        inspector=actor,
        status=QualityInspectionStatus.PENDING,
    )
    if checklist:
        for item in checklist.items.all():
            QualityInspectionResult.objects.create(
                inspection=inspection,
                checklist_item=item,
                passed=False,
            )

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="production",
        action="quality_inspection_created",
        obj=inspection,
    )
    return inspection


@transaction.atomic
def approve_inspection(*, inspection, actor, results=None, notes="", request=None):
    if not user_has_permission(actor, "quality_inspections.approve"):
        raise PermissionDenied("Sem permissão para aprovar inspeção.")
    if inspection.status != QualityInspectionStatus.PENDING:
        raise ValidationError("Inspeção já finalizada.")

    if results:
        for result_id, passed in results.items():
            QualityInspectionResult.objects.filter(
                inspection=inspection,
                pk=result_id,
            ).update(passed=passed)

    required_failed = inspection.results.filter(
        checklist_item__is_required=True,
        passed=False,
    ).exists()
    if required_failed:
        raise ValidationError("Itens obrigatórios não conferidos.")

    inspection.status = QualityInspectionStatus.APPROVED
    inspection.notes = notes or ""
    inspection.inspected_at = timezone.now()
    inspection.save(update_fields=["status", "notes", "inspected_at", "updated_at"])

    if inspection.piece_id:
        inspection.piece.status = ProductionPieceStatus.APPROVED
        inspection.piece.save(update_fields=["status", "updated_at"])

    add_production_log(
        production_order=inspection.production_order,
        piece=inspection.piece,
        log_type=ProductionLogType.QUALITY,
        description="Inspeção aprovada.",
        actor=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="quality_inspection_approved",
        obj=inspection,
    )
    return inspection


@transaction.atomic
def reject_inspection(*, inspection, actor, notes="", create_rework=True, request=None):
    if not user_has_permission(actor, "quality_inspections.reject"):
        raise PermissionDenied("Sem permissão para reprovar inspeção.")
    if not notes.strip():
        raise ValidationError("Observação obrigatória na reprovação.")
    if inspection.status != QualityInspectionStatus.PENDING:
        raise ValidationError("Inspeção já finalizada.")

    inspection.status = QualityInspectionStatus.REJECTED
    inspection.notes = notes.strip()
    inspection.inspected_at = timezone.now()
    inspection.save(update_fields=["status", "notes", "inspected_at", "updated_at"])

    if inspection.piece_id:
        inspection.piece.status = ProductionPieceStatus.REWORK
        inspection.piece.save(update_fields=["status", "updated_at"])
        if create_rework:
            record_rework(
                piece=inspection.piece,
                actor=actor,
                reason=notes.strip(),
                request=request,
            )

    add_production_log(
        production_order=inspection.production_order,
        piece=inspection.piece,
        log_type=ProductionLogType.QUALITY,
        description=f"Inspeção reprovada: {notes.strip()}",
        actor=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="quality_inspection_rejected",
        obj=inspection,
        metadata={"notes": notes[:500]},
    )
    return inspection
