# ruff: noqa: PLR0913
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit_event
from purchasing.models import PurchaseRequest
from purchasing.models import PurchaseRequestItem
from purchasing.models import RequestStatus
from purchasing.models import SourceType
from purchasing.services.numbering import next_request_number


EDITABLE_STATUSES = {RequestStatus.DRAFT, RequestStatus.SUBMITTED, RequestStatus.UNDER_REVIEW}


@transaction.atomic
def create_purchase_request(*, data, items, actor, request=None):
    justification = (data.get("justification") or "").strip()
    if not justification:
        raise ValidationError("Justificativa é obrigatória.")
    if not items:
        raise ValidationError("Informe ao menos um item.")

    pr = PurchaseRequest(
        number=next_request_number(),
        request_type=data.get("request_type") or "material",
        status=RequestStatus.DRAFT,
        priority=data.get("priority") or "normal",
        requested_by=actor,
        requested_for_user=data.get("requested_for_user"),
        production_order=data.get("production_order"),
        production_piece=data.get("production_piece"),
        sales_order=data.get("sales_order"),
        cost_center=data.get("cost_center"),
        source_type=data.get("source_type") or SourceType.MANUAL,
        source_id=data.get("source_id"),
        required_date=data.get("required_date"),
        justification=justification,
        notes=data.get("notes") or "",
        created_by=actor,
        updated_by=actor,
    )
    if pr.production_piece_id and not pr.source_id:
        pr.source_type = SourceType.PRODUCTION_PIECE
        pr.source_id = pr.production_piece_id
    elif pr.production_order_id and not pr.source_id:
        pr.source_type = SourceType.PRODUCTION_ORDER
        pr.source_id = pr.production_order_id
    pr.save()

    for raw in items:
        _create_item(pr, raw)

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="purchasing",
        action="create_purchase_request",
        obj=pr,
        description=f"Criou solicitação {pr.number}",
    )
    return pr


def _create_item(pr, raw):
    quantity = Decimal(str(raw["quantity"]))
    if quantity <= 0:
        raise ValidationError("Quantidade do item deve ser positiva.")
    description = (raw.get("description") or "").strip()
    if not description:
        raise ValidationError("Descrição do item é obrigatória.")
    material = raw.get("material")
    tech = (raw.get("technical_specification") or "").strip()
    if not material and not tech:
        raise ValidationError("Especificação técnica obrigatória para itens sem material cadastrado.")
    item = PurchaseRequestItem(
        purchase_request=pr,
        item_type=raw.get("item_type") or "material",
        material=material,
        description=description,
        quantity=quantity,
        unit=raw.get("unit") or "un",
        estimated_unit_cost=Decimal(str(raw.get("estimated_unit_cost") or "0")),
        required_date=raw.get("required_date"),
        preferred_supplier=raw.get("preferred_supplier"),
        technical_specification=tech,
        notes=raw.get("notes") or "",
    )
    item.full_clean()
    item.save()
    return item


@transaction.atomic
def submit_purchase_request(*, purchase_request, actor, request=None):
    if purchase_request.status != RequestStatus.DRAFT:
        raise ValidationError("Somente rascunhos podem ser enviados.")
    if not purchase_request.items.exists():
        raise ValidationError("Solicitação sem itens.")
    purchase_request.status = RequestStatus.SUBMITTED
    purchase_request.updated_by = actor
    purchase_request.save(update_fields=["status", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="purchasing",
        action="submit_purchase_request",
        obj=purchase_request,
    )
    return purchase_request


@transaction.atomic
def approve_purchase_request(*, purchase_request, actor, request=None):
    if purchase_request.status not in {RequestStatus.SUBMITTED, RequestStatus.UNDER_REVIEW}:
        raise ValidationError("Solicitação não está aguardando aprovação.")
    purchase_request.status = RequestStatus.APPROVED
    purchase_request.approved_by = actor
    purchase_request.approved_at = timezone.now()
    purchase_request.updated_by = actor
    purchase_request.save(
        update_fields=["status", "approved_by", "approved_at", "updated_by", "updated_at"],
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="purchasing",
        action="approve_purchase_request",
        obj=purchase_request,
    )
    return purchase_request


@transaction.atomic
def reject_purchase_request(*, purchase_request, actor, reason, request=None):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Motivo da rejeição é obrigatório.")
    if purchase_request.status not in {
        RequestStatus.SUBMITTED,
        RequestStatus.UNDER_REVIEW,
        RequestStatus.APPROVED,
    }:
        raise ValidationError("Solicitação não pode ser rejeitada neste status.")
    purchase_request.status = RequestStatus.REJECTED
    purchase_request.rejected_by = actor
    purchase_request.rejected_at = timezone.now()
    purchase_request.rejection_reason = reason
    purchase_request.updated_by = actor
    purchase_request.save(
        update_fields=[
            "status",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "updated_by",
            "updated_at",
        ],
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="purchasing",
        action="reject_purchase_request",
        obj=purchase_request,
        metadata={"reason": reason[:500]},
    )
    return purchase_request


@transaction.atomic
def cancel_purchase_request(*, purchase_request, actor, reason, request=None):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Motivo do cancelamento é obrigatório.")
    if purchase_request.status in {RequestStatus.RECEIVED, RequestStatus.CANCELLED}:
        raise ValidationError("Solicitação não pode ser cancelada.")
    if purchase_request.purchase_orders.exclude(status__in=["cancelled", "rejected"]).exists():
        raise ValidationError("Cancele os pedidos de compra vinculados antes.")
    purchase_request.status = RequestStatus.CANCELLED
    purchase_request.notes = (purchase_request.notes + f"\nCancelamento: {reason}").strip()
    purchase_request.updated_by = actor
    purchase_request.save(update_fields=["status", "notes", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="purchasing",
        action="cancel_purchase_request",
        obj=purchase_request,
        metadata={"reason": reason[:500]},
    )
    return purchase_request
