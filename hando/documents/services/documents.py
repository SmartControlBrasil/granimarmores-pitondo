# ruff: noqa: PLR0913
import hashlib
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from documents.models import ContentFormat
from documents.models import DocumentStatus
from documents.models import DocumentTemplate
from documents.models import DocumentType
from documents.models import ManagedDocument
from documents.models import TemplateStatus
from documents.models import VersionStatus
from documents.services.numbering import next_document_number
from documents.services.placeholders import build_context_values
from documents.services.placeholders import render_placeholders
from documents.services.placeholders import sanitize_html_fragment
from documents.services.versions import create_version


@transaction.atomic
def create_document_type(*, data, actor, request=None):
    if not user_has_permission(actor, "document_types.create"):
        raise PermissionDenied("Sem permissão.")
    obj = DocumentType(**data)
    obj.full_clean()
    obj.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="documents",
        action="create_document_type",
        obj=obj,
    )
    return obj


@transaction.atomic
def create_document_template(*, data, actor, request=None):
    if not user_has_permission(actor, "document_templates.create"):
        raise PermissionDenied("Sem permissão.")
    template = DocumentTemplate(
        **data,
        created_by=actor,
        updated_by=actor,
    )
    if template.content_format == ContentFormat.HTML:
        template.body = sanitize_html_fragment(template.body)
        template.header = sanitize_html_fragment(template.header)
        template.footer = sanitize_html_fragment(template.footer)
    template.full_clean()
    template.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="documents",
        action="create_document_template",
        obj=template,
    )
    return template


@transaction.atomic
def approve_document_template(*, template, actor, request=None):
    if not user_has_permission(actor, "document_templates.approve"):
        raise PermissionDenied("Sem permissão.")
    if template.status == TemplateStatus.APPROVED:
        return template
    template.status = TemplateStatus.APPROVED
    template.is_active = True
    template.updated_by = actor
    template.save(update_fields=["status", "is_active", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="documents",
        action="approve_document_template",
        obj=template,
    )
    return template


@transaction.atomic
def create_managed_document(
    *,
    data,
    actor,
    request=None,
    initial_content="",
    media_asset=None,
):
    if not user_has_permission(actor, "documents.create"):
        raise PermissionDenied("Sem permissão.")
    document = ManagedDocument(
        number=next_document_number(),
        title=data["title"],
        document_type=data["document_type"],
        template=data.get("template"),
        status=DocumentStatus.DRAFT,
        customer=data.get("customer"),
        lead=data.get("lead"),
        quote=data.get("quote"),
        sales_order=data.get("sales_order"),
        production_order=data.get("production_order"),
        purchase_order=data.get("purchase_order"),
        supplier=data.get("supplier"),
        after_sales_case=data.get("after_sales_case"),
        warranty=data.get("warranty"),
        effective_date=data.get("effective_date"),
        expiration_date=data.get("expiration_date"),
        requires_acceptance=bool(
            data.get("requires_acceptance", data["document_type"].requires_customer_acceptance),
        ),
        requires_signature=bool(
            data.get("requires_signature", data["document_type"].requires_signature),
        ),
        confidentiality=data.get("confidentiality") or "internal",
        owner=actor,
        responsible_user=data.get("responsible_user") or actor,
        notes=data.get("notes") or "",
        context_justification=data.get("context_justification") or "",
        created_by=actor,
        updated_by=actor,
    )
    if document.document_type.has_validity and not document.expiration_date:
        days = document.document_type.default_validity_days
        if days:
            document.expiration_date = timezone.localdate() + timedelta(days=days)
    document.full_clean()
    document.save()
    version = create_version(
        document=document,
        content=initial_content or "",
        actor=actor,
        change_summary="Versão inicial",
        media_asset=media_asset,
        request=request,
    )
    document.current_version = version
    document.save(update_fields=["current_version", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="documents",
        action="create_document",
        obj=document,
    )
    return document


@transaction.atomic
def create_document_from_template(
    *,
    template,
    actor,
    title=None,
    customer=None,
    lead=None,
    quote=None,
    sales_order=None,
    production_order=None,
    purchase_order=None,
    supplier=None,
    after_sales_case=None,
    warranty=None,
    context_justification="",
    request=None,
):
    if not template.is_active or template.status != TemplateStatus.APPROVED:
        raise ValidationError("Modelo precisa estar ativo e aprovado.")
    if not user_has_permission(actor, "documents.create"):
        raise PermissionDenied("Sem permissão.")

    values = build_context_values(
        quote=quote,
        sales_order=sales_order,
        customer=customer,
        supplier=supplier,
    )
    header, miss_h = render_placeholders(template.header, values)
    body, miss_b = render_placeholders(template.body, values)
    footer, miss_f = render_placeholders(template.footer, values)
    missing = sorted(set(miss_h + miss_b + miss_f))
    if template.content_format == ContentFormat.HTML:
        content = sanitize_html_fragment(f"{header}\n{body}\n{footer}".strip())
    else:
        content = f"{header}\n{body}\n{footer}".strip()

    document = create_managed_document(
        data={
            "title": title or f"{template.document_type.name} — {template.name}",
            "document_type": template.document_type,
            "template": template,
            "customer": customer,
            "lead": lead,
            "quote": quote,
            "sales_order": sales_order,
            "production_order": production_order,
            "purchase_order": purchase_order,
            "supplier": supplier,
            "after_sales_case": after_sales_case,
            "warranty": warranty,
            "context_justification": context_justification,
        },
        actor=actor,
        request=request,
        initial_content=content,
    )
    version = document.current_version
    version.missing_placeholders = missing
    version.rendered_content = content
    version.checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
    version.save(update_fields=["missing_placeholders", "rendered_content", "checksum", "updated_at"])
    return document


@transaction.atomic
def update_document_metadata(*, document, data, actor, request=None):
    if not user_has_permission(actor, "documents.update"):
        raise PermissionDenied("Sem permissão.")
    if document.status in {
        DocumentStatus.CANCELLED,
        DocumentStatus.TERMINATED,
        DocumentStatus.ARCHIVED,
    }:
        raise ValidationError("Documento encerrado não pode ser alterado.")
    for field in (
        "title",
        "responsible_user",
        "notes",
        "effective_date",
        "expiration_date",
        "confidentiality",
        "context_justification",
    ):
        if field in data:
            setattr(document, field, data[field])
    document.updated_by = actor
    document.full_clean()
    document.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="documents",
        action="update_document",
        obj=document,
    )
    return document
