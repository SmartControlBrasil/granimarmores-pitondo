# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from media_library.models import BeforeAfterPair
from media_library.models import CollectionStatus
from media_library.models import HistoryAction
from media_library.models import MediaAssetHistory
from media_library.models import MediaCollection
from media_library.models import MediaCollectionItem
from media_library.models import MediaStatus
from media_library.models import MediaType
from media_library.models import MediaVisibility
from media_library.models import PublicationCandidate
from media_library.models import PublicationStatus
from media_library.models import TechnicalReviewStatus
from media_library.services.consent import consent_allows_scope
from media_library.services.consent import evaluate_media_consent
from media_library.services.numbering import next_collection_code
from after_sales.models import ConsentScope


def _history(asset, action, actor, description=""):
    MediaAssetHistory.objects.create(
        asset=asset,
        action=action,
        description=description,
        actor=actor,
    )


@transaction.atomic
def approve_for_portfolio(*, asset, actor, notes="", request=None):
    if not (
        user_has_permission(actor, "media_portfolio.approve")
        or user_has_permission(actor, "media_assets.approve")
    ):
        raise PermissionDenied("Sem permissão para aprovar portfólio.")
    if asset.status in {MediaStatus.DELETED, MediaStatus.ARCHIVED, MediaStatus.REJECTED}:
        raise ValidationError("Mídia não elegível para portfólio.")
    if asset.technical_review_status != TechnicalReviewStatus.APPROVED:
        raise ValidationError("Aprovação técnica obrigatória.")
    if asset.media_type != MediaType.IMAGE:
        raise ValidationError("Somente imagens entram no portfólio nesta fase.")
    if not asset.alt_text.strip():
        raise ValidationError("Alt text obrigatório para portfólio.")
    if not (asset.title or "").strip():
        raise ValidationError("Título ou legenda obrigatório.")
    if not (
        asset.sales_order_id
        or asset.material_id
        or asset.installation_schedule_id
        or asset.production_order_id
    ):
        raise ValidationError("Vínculo com obra ou material obrigatório.")
    if not consent_allows_scope(asset, ConsentScope.PORTFOLIO):
        raise ValidationError(
            f"Consentimento insuficiente ({evaluate_media_consent(asset)}).",
        )

    asset.is_portfolio_approved = True
    asset.portfolio_approved_at = timezone.now()
    asset.portfolio_approved_by = actor
    asset.visibility = MediaVisibility.PORTFOLIO_CANDIDATE
    asset.status = MediaStatus.APPROVED
    asset.updated_by = actor
    asset.save()
    _history(asset, HistoryAction.PORTFOLIO_APPROVED, actor, notes or "Aprovado para portfólio")
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="media_library",
        action="media_portfolio_approved",
        obj=asset,
    )
    return asset


@transaction.atomic
def remove_from_portfolio(*, asset, actor, notes="", request=None):
    if not (
        user_has_permission(actor, "media_portfolio.approve")
        or user_has_permission(actor, "media_assets.approve")
    ):
        raise PermissionDenied("Sem permissão.")
    asset.is_portfolio_approved = False
    if asset.visibility in {
        MediaVisibility.PORTFOLIO_CANDIDATE,
        MediaVisibility.PUBLIC_APPROVED,
    }:
        asset.visibility = MediaVisibility.INTERNAL
    asset.updated_by = actor
    asset.save()
    _history(asset, HistoryAction.PORTFOLIO_REMOVED, actor, notes or "Removido do portfólio")
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="media_library",
        action="media_portfolio_removed",
        obj=asset,
    )
    return asset


@transaction.atomic
def create_collection(*, actor, name, collection_type, description="", **links):
    if not user_has_permission(actor, "media_collections.create"):
        raise PermissionDenied("Sem permissão para criar coleção.")
    collection = MediaCollection.objects.create(
        code=next_collection_code(),
        name=name,
        description=description,
        collection_type=collection_type,
        status=CollectionStatus.DRAFT,
        customer=links.get("customer"),
        sales_order=links.get("sales_order"),
        production_order=links.get("production_order"),
        after_sales_case=links.get("after_sales_case"),
        created_by=actor,
        updated_by=actor,
    )
    return collection


@transaction.atomic
def add_asset_to_collection(*, collection, asset, actor, caption="", is_cover=False, display_order=0):
    if not user_has_permission(actor, "media_collections.update"):
        raise PermissionDenied("Sem permissão.")
    item, _ = MediaCollectionItem.objects.update_or_create(
        collection=collection,
        asset=asset,
        defaults={
            "caption": caption,
            "is_cover": is_cover,
            "display_order": display_order,
        },
    )
    if is_cover:
        MediaCollectionItem.objects.filter(collection=collection).exclude(pk=item.pk).update(is_cover=False)
        collection.cover_asset = asset
        collection.updated_by = actor
        collection.save(update_fields=["cover_asset", "updated_by", "updated_at"])
    return item


@transaction.atomic
def create_before_after_pair(
    *,
    actor,
    before_asset,
    after_asset,
    title,
    description="",
    collection=None,
    customer=None,
    sales_order=None,
    approved_for_portfolio=False,
    request=None,
):
    if not user_has_permission(actor, "media_collections.create"):
        raise PermissionDenied("Sem permissão.")
    pair = BeforeAfterPair(
        before_asset=before_asset,
        after_asset=after_asset,
        title=title,
        description=description,
        collection=collection,
        customer=customer or before_asset.customer or after_asset.customer,
        sales_order=sales_order or before_asset.sales_order or after_asset.sales_order,
        approved_for_portfolio=False,
        created_by=actor,
        updated_by=actor,
    )
    pair.full_clean()
    pair.save()
    if approved_for_portfolio:
        if not (
            consent_allows_scope(before_asset, ConsentScope.PORTFOLIO)
            and consent_allows_scope(after_asset, ConsentScope.PORTFOLIO)
        ):
            raise ValidationError("Consentimento insuficiente para antes/depois público.")
        pair.approved_for_portfolio = True
        pair.save(update_fields=["approved_for_portfolio", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="media_library",
        action="before_after_created",
        obj=pair,
    )
    return pair


@transaction.atomic
def create_publication_candidate(*, actor, asset, channel, caption="", notes="", planned_date=None, request=None):
    if not user_has_permission(actor, "media_publication_candidates.create"):
        raise PermissionDenied("Sem permissão.")
    if asset.status == MediaStatus.REJECTED:
        raise ValidationError("Mídia rejeitada não pode ser candidata.")
    candidate = PublicationCandidate.objects.create(
        asset=asset,
        channel=channel,
        status=PublicationStatus.CANDIDATE,
        caption=caption,
        notes=notes,
        planned_date=planned_date,
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="media_library",
        action="publication_candidate_created",
        obj=candidate,
    )
    return candidate
