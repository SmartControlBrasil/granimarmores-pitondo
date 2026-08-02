# ruff: noqa: PLR0913
import hashlib

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from documents.models import DocumentVersion
from documents.models import VersionStatus
from documents.services.placeholders import sanitize_html_fragment


def _checksum(content: str, media_asset=None) -> str:
    if media_asset and getattr(media_asset, "checksum", ""):
        return media_asset.checksum
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


@transaction.atomic
def create_version(
    *,
    document,
    actor,
    content="",
    change_summary="",
    media_asset=None,
    request=None,
):
    if not user_has_permission(actor, "documents.update") and not user_has_permission(
        actor,
        "documents.create",
    ):
        raise PermissionDenied("Sem permissão.")
    last = document.versions.aggregate(v=Max("version_number"))["v"] or 0
    safe_content = sanitize_html_fragment(content or "")
    version = DocumentVersion(
        document=document,
        version_number=last + 1,
        status=VersionStatus.DRAFT,
        content=safe_content,
        rendered_content=safe_content,
        media_asset=media_asset,
        checksum=_checksum(safe_content, media_asset),
        change_summary=change_summary or "",
        created_by=actor,
    )
    version.save()
    if document.current_version_id and document.current_version.status == VersionStatus.APPROVED:
        previous = document.current_version
        previous.status = VersionStatus.SUPERSEDED
        previous.save(update_fields=["status", "updated_at"])
    document.current_version = version
    document.updated_by = actor
    document.save(update_fields=["current_version", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="documents",
        action="create_document_version",
        obj=version,
    )
    return version


@transaction.atomic
def edit_draft_version(*, version, content, actor, request=None):
    if version.status != VersionStatus.DRAFT:
        raise ValidationError("Somente versão em rascunho pode ser editada. Crie nova versão.")
    if not user_has_permission(actor, "documents.update"):
        raise PermissionDenied("Sem permissão.")
    safe = sanitize_html_fragment(content or "")
    version.content = safe
    version.rendered_content = safe
    version.checksum = _checksum(safe, version.media_asset)
    version.save(update_fields=["content", "rendered_content", "checksum", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="documents",
        action="edit_document_version",
        obj=version,
    )
    return version
