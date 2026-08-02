# ruff: noqa: EM101, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from media_library.models import HistoryAction
from media_library.models import MediaAssetHistory
from media_library.models import MediaStatus
from media_library.models import MediaVisibility


def _history(asset, action, actor, description=""):
    MediaAssetHistory.objects.create(
        asset=asset,
        action=action,
        description=description,
        actor=actor,
    )


def _has_operational_links(asset):
    return any(
        [
            asset.customer_id,
            asset.sales_order_id,
            asset.production_order_id,
            asset.production_piece_id,
            asset.after_sales_case_id,
            asset.warranty_id,
            asset.installation_schedule_id,
            asset.delivery_schedule_id,
            asset.links.exists(),
        ],
    )


@transaction.atomic
def archive_media_asset(*, asset, actor, reason="", request=None):
    if not user_has_permission(actor, "media_assets.archive"):
        raise PermissionDenied("Sem permissão para arquivar.")
    if asset.status == MediaStatus.DELETED:
        raise ValidationError("Mídia já excluída.")
    asset.status = MediaStatus.ARCHIVED
    asset.archive_reason = reason
    if asset.visibility == MediaVisibility.PUBLIC_APPROVED:
        asset.visibility = MediaVisibility.INTERNAL
    asset.updated_by = actor
    asset.save()
    _history(asset, HistoryAction.ARCHIVED, actor, reason or "Arquivado")
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="media_library",
        action="media_archived",
        obj=asset,
    )
    return asset


@transaction.atomic
def request_media_deletion(*, asset, actor, reason, request=None):
    if not user_has_permission(actor, "media_assets.request_delete"):
        raise PermissionDenied("Sem permissão para solicitar exclusão.")
    if not reason.strip():
        raise ValidationError("Motivo obrigatório.")
    if _has_operational_links(asset) and not user_has_permission(actor, "media_assets.view_all"):
        raise ValidationError(
            "Mídia com vínculo operacional exige permissão elevada para solicitar exclusão.",
        )
    if asset.after_sales_case_id or asset.warranty_id:
        # Preserva evidências de assistência/garantia — apenas marca pedido
        pass
    asset.deletion_requested = True
    asset.deletion_reason = reason.strip()
    asset.deletion_requested_at = timezone.now()
    asset.deletion_requested_by = actor
    asset.status = MediaStatus.DELETED
    asset.updated_by = actor
    asset.save()
    _history(asset, HistoryAction.DELETION_REQUESTED, actor, reason.strip())
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="media_library",
        action="media_deletion_requested",
        obj=asset,
        metadata={"reason": reason[:500]},
    )
    return asset
