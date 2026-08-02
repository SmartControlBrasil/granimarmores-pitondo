# ruff: noqa: PLR0913
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from documents.models import AcceptanceStatus
from documents.models import DocumentAcceptance
from documents.models import DocumentSendRecord
from documents.models import DocumentSignatureRecord
from documents.models import DocumentStatus
from documents.models import DocumentViewRecord
from documents.models import VersionStatus


def _require_approved_version(document):
    version = document.current_version
    if not version or version.status != VersionStatus.APPROVED:
        raise ValidationError("É necessária versão aprovada.")
    return version


@transaction.atomic
def register_document_send(*, document, actor, data, request=None):
    if not user_has_permission(actor, "documents.send"):
        raise PermissionDenied("Sem permissão.")
    version = _require_approved_version(document)
    if document.status not in {
        DocumentStatus.APPROVED,
        DocumentStatus.SENT,
        DocumentStatus.VIEWED,
        DocumentStatus.ACCEPTED,
        DocumentStatus.SIGNED,
        DocumentStatus.ACTIVE,
    }:
        raise ValidationError("Documento precisa estar aprovado para registrar envio.")
    record = DocumentSendRecord.objects.create(
        document=document,
        document_version=version,
        channel=data["channel"],
        recipient_name=data.get("recipient_name") or "",
        recipient_email=data.get("recipient_email") or "",
        recipient_phone=data.get("recipient_phone") or "",
        sent_at=data.get("sent_at") or timezone.now(),
        notes=data.get("notes") or "",
        recorded_by=actor,
    )
    if document.status in {DocumentStatus.APPROVED, DocumentStatus.VIEWED}:
        document.status = DocumentStatus.SENT
        document.updated_by = actor
        document.save(update_fields=["status", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="documents",
        action="register_document_send",
        obj=record,
    )
    return record


@transaction.atomic
def register_document_view(*, document, actor, data, request=None):
    if not user_has_permission(actor, "documents.update") and not user_has_permission(
        actor,
        "documents.send",
    ):
        raise PermissionDenied("Sem permissão.")
    version = document.current_version
    if not version:
        raise ValidationError("Documento sem versão.")
    record = DocumentViewRecord.objects.create(
        document=document,
        document_version=version,
        viewed_at=data.get("viewed_at") or timezone.now(),
        viewer_name=data.get("viewer_name") or "",
        channel=data.get("channel") or "other",
        notes=data.get("notes") or "",
        recorded_by=actor,
    )
    if document.status in {DocumentStatus.SENT, DocumentStatus.APPROVED}:
        document.status = DocumentStatus.VIEWED
        document.updated_by = actor
        document.save(update_fields=["status", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="documents",
        action="register_document_view",
        obj=record,
    )
    return record


@transaction.atomic
def register_document_acceptance(*, document, actor, data, request=None):
    if not user_has_permission(actor, "documents.accept"):
        raise PermissionDenied("Sem permissão.")
    version = _require_approved_version(document)
    accepted = bool(data.get("accepted", True))
    if not accepted and not (data.get("notes") or "").strip():
        raise ValidationError("Rejeição exige motivo.")
    acceptance = DocumentAcceptance(
        document=document,
        document_version=version,
        acceptance_type=data.get("acceptance_type") or "customer_acceptance",
        status=AcceptanceStatus.ACCEPTED if accepted else AcceptanceStatus.REJECTED,
        accepted_at=timezone.now() if accepted else None,
        rejected_at=None if accepted else timezone.now(),
        accepted_by_name=data.get("accepted_by_name") or "",
        accepted_by_document=data.get("accepted_by_document") or "",
        channel=data.get("channel") or "other",
        notes=data.get("notes") or "",
        recorded_by=actor,
    )
    if request is not None:
        acceptance.ip_address = request.META.get("REMOTE_ADDR")
        acceptance.user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:255]
    acceptance.save()
    if accepted:
        document.status = DocumentStatus.ACCEPTED
        if not document.requires_signature:
            document.status = DocumentStatus.ACTIVE
            if not document.effective_date:
                document.effective_date = timezone.localdate()
    else:
        document.status = DocumentStatus.REJECTED
    document.updated_by = actor
    document.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="documents",
        action="accept_document" if accepted else "reject_document_acceptance",
        obj=acceptance,
    )
    return acceptance


@transaction.atomic
def revoke_document_acceptance(*, acceptance, actor, reason, request=None):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Motivo obrigatório.")
    if not user_has_permission(actor, "documents.reject_acceptance"):
        raise PermissionDenied("Sem permissão.")
    if acceptance.status != AcceptanceStatus.ACCEPTED:
        raise ValidationError("Somente aceite ativo pode ser revogado.")
    acceptance.status = AcceptanceStatus.REVOKED
    acceptance.notes = (acceptance.notes + f"\nRevogação: {reason}").strip()
    acceptance.save(update_fields=["status", "notes", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="documents",
        action="revoke_document_acceptance",
        obj=acceptance,
        metadata={"reason": reason[:500]},
    )
    return acceptance


@transaction.atomic
def register_document_signature(*, document, actor, data, request=None):
    if not user_has_permission(actor, "documents.register_signature"):
        raise PermissionDenied("Sem permissão.")
    version = _require_approved_version(document)
    if not (data.get("signer_name") or "").strip():
        raise ValidationError("Nome do signatário obrigatório.")
    signature = DocumentSignatureRecord.objects.create(
        document=document,
        document_version=version,
        signer_name=data["signer_name"].strip(),
        signer_document=data.get("signer_document") or "",
        signer_role=data.get("signer_role") or "",
        signature_type=data.get("signature_type") or "manual_confirmation",
        signed_at=data.get("signed_at") or timezone.now(),
        channel=data.get("channel") or "other",
        evidence_asset=data.get("evidence_asset"),
        external_provider=data.get("external_provider") or "",
        notes=data.get("notes") or "",
        recorded_by=actor,
    )
    document.status = DocumentStatus.SIGNED
    if document.requires_acceptance:
        has_acceptance = document.acceptances.filter(status=AcceptanceStatus.ACCEPTED).exists()
        if has_acceptance or not document.requires_acceptance:
            document.status = DocumentStatus.ACTIVE
    else:
        document.status = DocumentStatus.ACTIVE
    if not document.effective_date:
        document.effective_date = timezone.localdate()
    document.updated_by = actor
    document.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="documents",
        action="register_document_signature",
        obj=signature,
    )
    return signature
