# ruff: noqa: PLR0913
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from documents.models import DocumentRelationship
from documents.models import DocumentStatus
from documents.models import RelationshipType
from documents.models import VersionStatus
from documents.services.documents import create_managed_document


def warning_days():
    return int(getattr(settings, "DOCUMENT_EXPIRATION_WARNING_DAYS", 30))


@transaction.atomic
def cancel_document(*, document, actor, reason, request=None):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Motivo obrigatório.")
    if not user_has_permission(actor, "documents.cancel"):
        raise PermissionDenied("Sem permissão.")
    if document.status in {DocumentStatus.CANCELLED, DocumentStatus.TERMINATED}:
        raise ValidationError("Documento já encerrado/cancelado.")
    document.status = DocumentStatus.CANCELLED
    document.cancel_reason = reason
    document.updated_by = actor
    document.save(update_fields=["status", "cancel_reason", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="documents",
        action="cancel_document",
        obj=document,
        metadata={"reason": reason[:500]},
    )
    return document


@transaction.atomic
def terminate_document(*, document, actor, reason, terminated_at=None, request=None):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Motivo obrigatório.")
    if not user_has_permission(actor, "documents.terminate"):
        raise PermissionDenied("Sem permissão.")
    document.status = DocumentStatus.TERMINATED
    document.terminate_reason = reason
    document.terminated_at = terminated_at or timezone.now()
    document.updated_by = actor
    document.save(
        update_fields=["status", "terminate_reason", "terminated_at", "updated_by", "updated_at"],
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="documents",
        action="terminate_document",
        obj=document,
        metadata={"reason": reason[:500]},
    )
    return document


@transaction.atomic
def renew_document(*, document, actor, expiration_date=None, request=None):
    if not user_has_permission(actor, "documents.renew"):
        raise PermissionDenied("Sem permissão.")
    if not document.document_type.allows_renewal:
        raise ValidationError("Tipo de documento não permite renovação.")
    if document.status in {DocumentStatus.CANCELLED, DocumentStatus.TERMINATED}:
        raise ValidationError("Documento encerrado não pode ser renovado.")
    content = ""
    media_asset = None
    if document.current_version:
        content = document.current_version.rendered_content or document.current_version.content
        media_asset = document.current_version.media_asset
    new_doc = create_managed_document(
        data={
            "title": f"{document.title} (Renovação)",
            "document_type": document.document_type,
            "template": document.template,
            "customer": document.customer,
            "lead": document.lead,
            "quote": document.quote,
            "sales_order": document.sales_order,
            "production_order": document.production_order,
            "purchase_order": document.purchase_order,
            "supplier": document.supplier,
            "after_sales_case": document.after_sales_case,
            "warranty": document.warranty,
            "effective_date": timezone.localdate(),
            "expiration_date": expiration_date,
            "requires_acceptance": document.requires_acceptance,
            "requires_signature": document.requires_signature,
            "confidentiality": document.confidentiality,
            "responsible_user": document.responsible_user,
            "notes": f"Renovação de {document.number}",
            "context_justification": document.context_justification or f"Renovação de {document.number}",
        },
        actor=actor,
        request=request,
        initial_content=content,
        media_asset=media_asset,
    )
    new_doc.renewed_from = document
    new_doc.save(update_fields=["renewed_from", "updated_at"])
    DocumentRelationship.objects.create(
        from_document=document,
        to_document=new_doc,
        relationship_type=RelationshipType.RENEWAL,
        notes=f"Renovação gerada em {timezone.localdate()}",
        created_by=actor,
    )
    document.renewal_date = timezone.localdate()
    document.updated_by = actor
    document.save(update_fields=["renewal_date", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="documents",
        action="renew_document",
        obj=new_doc,
        metadata={"from": document.number},
    )
    return new_doc


@transaction.atomic
def link_documents(*, from_document, to_document, relationship_type, actor, notes="", request=None):
    if from_document.pk == to_document.pk:
        raise ValidationError("Relacionamento inválido.")
    rel = DocumentRelationship.objects.create(
        from_document=from_document,
        to_document=to_document,
        relationship_type=relationship_type,
        notes=notes or "",
        created_by=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="documents",
        action="link_documents",
        obj=rel,
    )
    return rel


@transaction.atomic
def sync_document_statuses(*, dry_run=False):
    from documents.models import ManagedDocument

    today = timezone.localdate()
    to_expire = ManagedDocument.objects.filter(
        status=DocumentStatus.ACTIVE,
        expiration_date__isnull=False,
        expiration_date__lt=today,
    )
    warning_until = today + timedelta(days=warning_days())
    expiring_soon = ManagedDocument.objects.filter(
        status=DocumentStatus.ACTIVE,
        expiration_date__isnull=False,
        expiration_date__gte=today,
        expiration_date__lte=warning_until,
    )
    report = {
        "to_expire": list(to_expire.values_list("number", flat=True)),
        "expiring_soon": list(expiring_soon.values_list("number", flat=True)),
        "updated": 0,
    }
    if dry_run:
        return report
    updated = to_expire.update(status=DocumentStatus.EXPIRED)
    report["updated"] = updated
    return report
