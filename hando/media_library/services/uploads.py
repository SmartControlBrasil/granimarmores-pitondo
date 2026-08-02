# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from media_library.models import HistoryAction
from media_library.models import LinkTargetType
from media_library.models import MediaAsset
from media_library.models import MediaAssetHistory
from media_library.models import MediaAssetLink
from media_library.models import MediaStatus
from media_library.models import MediaVisibility
from media_library.services.numbering import next_media_code
from media_library.services.validation import generate_thumbnail_bytes
from media_library.services.validation import safe_filename
from media_library.services.validation import validate_upload_file


CONTEXT_FIELDS = {
    "customer": LinkTargetType.CUSTOMER,
    "lead": LinkTargetType.LEAD,
    "quote": LinkTargetType.QUOTE,
    "sales_order": LinkTargetType.SALES_ORDER,
    "production_order": LinkTargetType.PRODUCTION_ORDER,
    "production_piece": LinkTargetType.PRODUCTION_PIECE,
    "production_stage": LinkTargetType.PRODUCTION_STAGE,
    "material": LinkTargetType.MATERIAL,
    "slab": LinkTargetType.SLAB,
    "delivery_schedule": LinkTargetType.DELIVERY,
    "installation_schedule": LinkTargetType.INSTALLATION,
    "after_sales_case": LinkTargetType.AFTER_SALES_CASE,
    "warranty": LinkTargetType.WARRANTY,
}


def _add_history(*, asset, action, actor, description=""):
    return MediaAssetHistory.objects.create(
        asset=asset,
        action=action,
        description=description,
        actor=actor,
    )


def _has_context(kwargs):
    return any(kwargs.get(field) for field in CONTEXT_FIELDS) or kwargs.get("category")


def _link_contexts(asset, actor, kwargs):
    for field, target_type in CONTEXT_FIELDS.items():
        obj = kwargs.get(field)
        if obj is None:
            continue
        MediaAssetLink.objects.get_or_create(
            asset=asset,
            target_type=target_type,
            target_id=obj.pk,
            defaults={"created_by": actor},
        )


@transaction.atomic
def upload_media_asset(
    *,
    actor,
    uploaded_file,
    title="",
    description="",
    alt_text="",
    category=None,
    tags=None,
    capture_date=None,
    consent=None,
    reuse_duplicate=False,
    request=None,
    **context,
):
    if not user_has_permission(actor, "media_assets.upload"):
        raise PermissionDenied("Sem permissão para upload de mídia.")
    if not _has_context({**context, "category": category}):
        raise ValidationError("Informe categoria ou ao menos um vínculo operacional.")

    meta = validate_upload_file(uploaded_file)
    existing = MediaAsset.objects.filter(
        checksum=meta["checksum"],
    ).exclude(status=MediaStatus.DELETED).order_by("id").first()

    if existing and reuse_duplicate:
        _link_contexts(existing, actor, context)
        for field in CONTEXT_FIELDS:
            if context.get(field) and not getattr(existing, f"{field}_id", None):
                setattr(existing, field, context[field])
        if category and not existing.category_id:
            existing.category = category
        existing.updated_by = actor
        existing.save()
        if tags:
            existing.tags.add(*tags)
        _add_history(
            asset=existing,
            action=HistoryAction.DUPLICATE_DETECTED,
            actor=actor,
            description="Reutilizado arquivo existente (mesmo checksum).",
        )
        record_audit_event(
            request=request,
            user=actor,
            event_type="update",
            module="media_library",
            action="media_duplicate_reused",
            obj=existing,
        )
        return existing, True

    code = next_media_code()
    stored = safe_filename(meta["stored_filename"])
    asset = MediaAsset(
        code=code,
        original_filename=meta["original_filename"],
        stored_filename=stored,
        media_type=meta["media_type"],
        mime_type=meta["mime_type"],
        file_size=meta["file_size"],
        checksum=meta["checksum"],
        width=meta["width"],
        height=meta["height"],
        title=title or meta["original_filename"][:220],
        description=description,
        alt_text=alt_text,
        status=MediaStatus.UPLOADED,
        visibility=MediaVisibility.PRIVATE,
        capture_date=capture_date,
        uploaded_at=timezone.now(),
        uploaded_by=actor,
        category=category,
        consent=consent,
        created_by=actor,
        updated_by=actor,
        duplicate_of=existing,
    )
    for field in CONTEXT_FIELDS:
        if context.get(field) is not None:
            setattr(asset, field, context[field])

    uploaded_file.seek(0)
    asset.file.save(stored, uploaded_file, save=False)
    asset.save()

    if meta["media_type"] == "image":
        thumb = generate_thumbnail_bytes(uploaded_file)
        if thumb is not None:
            asset.thumbnail.save(f"thumb_{code}.jpg", ContentFile(thumb.read()), save=True)
            _add_history(
                asset=asset,
                action=HistoryAction.THUMBNAIL_GENERATED,
                actor=actor,
                description="Miniatura gerada",
            )

    if tags:
        asset.tags.set(tags)
    _link_contexts(asset, actor, context)
    _add_history(asset=asset, action=HistoryAction.UPLOADED, actor=actor, description="Upload realizado")
    if existing:
        _add_history(
            asset=asset,
            action=HistoryAction.DUPLICATE_DETECTED,
            actor=actor,
            description=f"Checksum idêntico a {existing.code}",
        )

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="media_library",
        action="media_uploaded",
        obj=asset,
        metadata={"code": asset.code, "duplicate": bool(existing)},
    )
    return asset, bool(existing)


def upload_multiple_media_assets(*, actor, files, common_context, request=None, reuse_duplicate=False):
    if not user_has_permission(actor, "media_assets.upload"):
        raise PermissionDenied("Sem permissão para upload de mídia.")
    from django.conf import settings

    max_files = int(getattr(settings, "MEDIA_LIBRARY_MAX_FILES_PER_BATCH", 20))
    if len(files) > max_files:
        raise ValidationError(f"Limite de {max_files} arquivos por lote.")

    results = []
    for uploaded in files:
        try:
            asset, is_dup = upload_media_asset(
                actor=actor,
                uploaded_file=uploaded,
                request=request,
                reuse_duplicate=reuse_duplicate,
                **common_context,
            )
            results.append({"ok": True, "asset": asset, "duplicate": is_dup, "name": uploaded.name})
        except (ValidationError, PermissionDenied) as exc:
            results.append({"ok": False, "error": str(exc), "name": getattr(uploaded, "name", "")})
    return results
