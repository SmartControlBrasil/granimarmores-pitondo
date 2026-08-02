# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from media_library.models import HistoryAction
from media_library.models import MediaAssetHistory
from media_library.models import MediaReview
from media_library.models import MediaStatus
from media_library.models import TechnicalReviewStatus


def _history(asset, action, actor, description=""):
    MediaAssetHistory.objects.create(
        asset=asset,
        action=action,
        description=description,
        actor=actor,
    )


@transaction.atomic
def classify_media_asset(*, asset, actor, category, tags=None, title="", description="", alt_text="", request=None):
    if not user_has_permission(actor, "media_assets.classify"):
        raise PermissionDenied("Sem permissão para classificar mídia.")
    if asset.status in {MediaStatus.DELETED, MediaStatus.ARCHIVED}:
        raise ValidationError("Mídia arquivada ou excluída.")
    if not category:
        raise ValidationError("Categoria obrigatória.")
    asset.category = category
    if title:
        asset.title = title
    if description:
        asset.description = description
    if alt_text:
        asset.alt_text = alt_text
    if asset.status == MediaStatus.UPLOADED:
        asset.status = MediaStatus.CLASSIFIED
    asset.updated_by = actor
    asset.save()
    if tags is not None:
        asset.tags.set(tags)
    _history(asset, HistoryAction.CLASSIFIED, actor, f"Categoria: {category.name}")
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="media_library",
        action="media_classified",
        obj=asset,
    )
    return asset


@transaction.atomic
def review_media_asset(*, asset, actor, decision, reason="", notes="", request=None):
    if not user_has_permission(actor, "media_assets.review"):
        raise PermissionDenied("Sem permissão para revisar mídia.")
    if decision not in {
        TechnicalReviewStatus.APPROVED,
        TechnicalReviewStatus.REJECTED,
        TechnicalReviewStatus.PENDING,
    }:
        raise ValidationError("Decisão de revisão inválida.")
    if decision == TechnicalReviewStatus.REJECTED and not reason.strip():
        raise ValidationError("Rejeição exige motivo.")

    MediaReview.objects.create(
        asset=asset,
        decision=decision,
        reason=reason,
        notes=notes,
        reviewer=actor,
    )
    asset.technical_review_status = decision
    if decision == TechnicalReviewStatus.APPROVED:
        asset.status = MediaStatus.APPROVED
        action = HistoryAction.APPROVED
    elif decision == TechnicalReviewStatus.REJECTED:
        asset.status = MediaStatus.REJECTED
        asset.reject_reason = reason
        action = HistoryAction.REJECTED
    else:
        asset.status = MediaStatus.UNDER_REVIEW
        action = HistoryAction.REVIEWED
    asset.updated_by = actor
    asset.save()
    _history(asset, action, actor, reason or notes or decision)
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="media_library",
        action="media_reviewed",
        obj=asset,
        metadata={"decision": decision},
    )
    return asset
