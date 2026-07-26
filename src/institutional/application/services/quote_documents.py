import hashlib
import json
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image
from reportlab.platypus import Paragraph
from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Spacer
from reportlab.platypus import Table
from reportlab.platypus import TableStyle

from src.institutional.application.services.access_policy import can_change_opportunity
from src.institutional.application.services.access_policy import get_visible_quote_documents
from src.institutional.application.services.access_policy import get_visible_quotes
from src.institutional.application.services.opportunity_management import create_opportunity_audit_log
from src.institutional.application.services.opportunity_management import recalculate_quote
from src.institutional.infrastructure.django.models import Opportunity
from src.institutional.infrastructure.django.models import OpportunityAuditLog
from src.institutional.infrastructure.django.models import Quote
from src.institutional.infrastructure.django.models import QuoteDelivery
from src.institutional.infrastructure.django.models import QuoteDocument


def _money(value):
    return f"{value:.2f}"


def document_filename(quote):
    return f"{quote.number}-R{quote.revision:02d}.pdf"


def build_quote_snapshot(quote):
    quote = Quote.objects.select_related("opportunity", "opportunity__contact_request", "opportunity__assigned_to").prefetch_related("items").get(pk=quote.pk)
    recalculate_quote(quote=quote)
    opportunity = quote.opportunity
    return {
        "company": {
            "name": settings.COMPANY_NAME,
            "document": settings.COMPANY_DOCUMENT,
            "phone": settings.COMPANY_PHONE,
            "email": settings.COMPANY_EMAIL,
            "address": settings.COMPANY_ADDRESS,
            "website": settings.COMPANY_WEBSITE,
            "logo_static_path": settings.COMPANY_LOGO_STATIC_PATH,
        },
        "quote": {
            "id": quote.pk,
            "number": quote.number,
            "revision": quote.revision,
            "status": quote.status,
            "issued_at": timezone.localdate().isoformat(),
            "validity_date": quote.validity_date.isoformat() if quote.validity_date else "",
            "subtotal": _money(quote.subtotal),
            "discount_amount": _money(quote.discount_amount),
            "total": _money(quote.total),
            "notes": quote.notes,
        },
        "customer": {
            "name": opportunity.customer_name,
            "phone": opportunity.customer_phone,
            "email": opportunity.customer_email,
            "city": opportunity.city,
        },
        "project": {
            "title": opportunity.title,
            "source_environment": opportunity.contact_request.ambiente,
            "source_message": opportunity.contact_request.mensagem,
        },
        "items": [
            {
                "description": item.description,
                "quantity": str(item.quantity),
                "unit": item.get_unit_display(),
                "unit_price": _money(item.unit_price),
                "total": _money(item.total),
                "position": item.position,
            }
            for item in quote.items.all()
        ],
    }


def snapshot_fingerprint(snapshot):
    payload = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def render_quote_preview_html(*, quote):
    snapshot = build_quote_snapshot(quote)
    return render_to_string("backoffice/quotes/pdf.html", {"snapshot": snapshot})


def _pdf_paragraph(text, style):
    return Paragraph(str(text or "").replace("\n", "<br/>"), style)


def render_quote_pdf_bytes(snapshot):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    styles = getSampleStyleSheet()
    story = []
    company = snapshot["company"]
    quote = snapshot["quote"]
    logo_path = finders.find(company.get("logo_static_path") or "")
    if logo_path:
        try:
            story.append(Image(logo_path, width=45 * mm, height=20 * mm, kind="proportional"))
        except Exception:
            pass
    story.append(_pdf_paragraph(f"<b>{company['name']}</b>", styles["Title"]))
    lines = [company.get("document"), company.get("phone"), company.get("email"), company.get("address"), company.get("website")]
    story.append(_pdf_paragraph(" | ".join([line for line in lines if line]), styles["Normal"]))
    story.append(Spacer(1, 8))
    story.append(_pdf_paragraph(f"<b>Orçamento {quote['number']} - Revisão {quote['revision']:02d}</b>", styles["Heading2"]))
    story.append(_pdf_paragraph(f"Emissão: {quote['issued_at']} | Validade: {quote['validity_date'] or '-'}", styles["Normal"]))
    story.append(Spacer(1, 8))
    customer = snapshot["customer"]
    story.append(_pdf_paragraph("<b>Cliente</b>", styles["Heading3"]))
    story.append(_pdf_paragraph(f"{customer['name']} | {customer['phone']} | {customer.get('email') or '-'} | {customer['city']}", styles["Normal"]))
    project = snapshot["project"]
    story.append(_pdf_paragraph("<b>Projeto</b>", styles["Heading3"]))
    story.append(_pdf_paragraph(f"{project['title']} - {project['source_environment']}", styles["Normal"]))
    story.append(Spacer(1, 8))
    data = [["Descrição", "Qtd.", "Un.", "Unitário", "Total"]]
    for item in snapshot["items"]:
        data.append([_pdf_paragraph(item["description"], styles["BodyText"]), item["quantity"], item["unit"], f"R$ {item['unit_price']}", f"R$ {item['total']}"])
    table = Table(data, colWidths=[78 * mm, 22 * mm, 18 * mm, 30 * mm, 30 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))
    story.append(table)
    story.append(Spacer(1, 8))
    totals = [["Subtotal", f"R$ {quote['subtotal']}"], ["Desconto", f"R$ {quote['discount_amount']}"], ["Total", f"R$ {quote['total']}"]]
    totals_table = Table(totals, colWidths=[130 * mm, 48 * mm])
    totals_table.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold")]))
    story.append(totals_table)
    if quote.get("notes"):
        story.append(Spacer(1, 8))
        story.append(_pdf_paragraph("<b>Condições e observações</b>", styles["Heading3"]))
        story.append(_pdf_paragraph(quote["notes"], styles["Normal"]))
    story.append(Spacer(1, 10))
    story.append(_pdf_paragraph(f"Documento: {quote['number']}-R{quote['revision']:02d}", styles["Italic"]))
    doc.build(story)
    return buffer.getvalue()


@transaction.atomic
def generate_quote_document(*, quote_id, actor):
    quote = get_visible_quotes(actor).select_for_update().get(pk=quote_id)
    if not can_change_opportunity(actor, quote.opportunity):
        raise PermissionDenied("Você não tem permissão para gerar PDF deste orçamento.")
    if quote.status != Quote.Status.READY:
        raise ValidationError("Marque o orçamento como pronto antes de gerar o PDF.")
    snapshot = build_quote_snapshot(quote)
    fingerprint = snapshot_fingerprint(snapshot)
    existing = quote.documents.filter(revision=quote.revision, snapshot_fingerprint=fingerprint).exclude(status=QuoteDocument.Status.VOID).first()
    if existing:
        return existing
    pdf_bytes = render_quote_pdf_bytes(snapshot)
    checksum = hashlib.sha256(pdf_bytes).hexdigest()
    document = QuoteDocument.objects.create(
        quote=quote,
        revision=quote.revision,
        document_number=f"{quote.number}-R{quote.revision:02d}",
        snapshot_data=snapshot,
        snapshot_fingerprint=fingerprint,
        checksum=checksum,
        generated_by=actor,
    )
    document.file.save(document_filename(quote), ContentFile(pdf_bytes), save=True)
    create_opportunity_audit_log(
        opportunity=quote.opportunity,
        actor=actor,
        action=OpportunityAuditLog.Action.QUOTE_DOCUMENT_GENERATED,
        new_value=document.document_number,
    )
    return document


@transaction.atomic
def void_quote_document(*, document_id, actor):
    document = get_visible_quote_documents(actor).select_for_update().get(pk=document_id)
    if not can_change_opportunity(actor, document.quote.opportunity):
        raise PermissionDenied("Você não tem permissão para anular este documento.")
    if document.status == QuoteDocument.Status.SENT:
        raise ValidationError("Documento enviado não pode ser anulado nesta fase.")
    if document.status != QuoteDocument.Status.VOID:
        document.status = QuoteDocument.Status.VOID
        document.save(update_fields=["status"])
        create_opportunity_audit_log(
            opportunity=document.quote.opportunity,
            actor=actor,
            action=OpportunityAuditLog.Action.QUOTE_DOCUMENT_VOIDED,
            new_value=document.document_number,
        )
    return document


@transaction.atomic
def send_quote_by_email(*, quote_id, document_id, recipient, actor, allow_resend=False):
    quote = get_visible_quotes(actor).select_for_update().get(pk=quote_id)
    document = quote.documents.select_for_update().get(pk=document_id)
    if not can_change_opportunity(actor, quote.opportunity):
        raise PermissionDenied("Você não tem permissão para enviar este orçamento.")
    if quote.status != Quote.Status.READY and not (allow_resend and quote.status == Quote.Status.SENT):
        raise ValidationError("Somente orçamento pronto pode ser enviado, salvo reenvio confirmado de orçamento já enviado.")
    if document.status == QuoteDocument.Status.VOID:
        raise ValidationError("Documento anulado não pode ser enviado.")
    if document.revision != quote.revision:
        raise ValidationError("Documento não pertence à revisão atual do orçamento.")
    if quote.deliveries.filter(document=document, recipient=recipient, status=QuoteDelivery.Status.SENT).exists() and not allow_resend:
        raise ValidationError("Este documento já foi enviado para este destinatário. Confirme reenvio explicitamente.")
    is_resend = quote.deliveries.filter(document=document, recipient=recipient, status=QuoteDelivery.Status.SENT).exists()
    delivery = QuoteDelivery.objects.create(quote=quote, document=document, recipient=recipient, requested_by=actor)
    create_opportunity_audit_log(
        opportunity=quote.opportunity,
        actor=actor,
        action=OpportunityAuditLog.Action.QUOTE_DELIVERY_REQUESTED,
        new_value=recipient,
    )
    try:
        subject = render_to_string("institutional/emails/quote_email_subject.txt", {"quote": quote, "document": document}).strip().replace("\n", " ")
        body = render_to_string("institutional/emails/quote_email.txt", {"quote": quote, "document": document})
        email = EmailMessage(subject=subject, body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient])
        with document.file.open("rb") as pdf_file:
            email.attach(Path(document.file.name).name, pdf_file.read(), "application/pdf")
        email.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001 - error is sanitized for operators.
        delivery.status = QuoteDelivery.Status.FAILED
        delivery.error_message = str(exc)[:500]
        delivery.save(update_fields=["status", "error_message"])
        create_opportunity_audit_log(
            opportunity=quote.opportunity,
            actor=actor,
            action=OpportunityAuditLog.Action.QUOTE_SEND_FAILED,
            new_value=recipient,
        )
        return delivery
    now = timezone.now()
    delivery.status = QuoteDelivery.Status.SENT
    delivery.sent_at = now
    delivery.save(update_fields=["status", "sent_at"])
    document.status = QuoteDocument.Status.SENT
    document.sent_at = now
    document.save(update_fields=["status", "sent_at"])
    previous_status = quote.status
    if quote.status != Quote.Status.SENT:
        quote.status = Quote.Status.SENT
        quote.save(update_fields=["status", "updated_at"])
    opportunity = Opportunity.objects.select_for_update().get(pk=quote.opportunity_id)
    old_stage = opportunity.stage
    if opportunity.stage not in {Opportunity.Stage.WON, Opportunity.Stage.LOST}:
        opportunity.stage = Opportunity.Stage.QUOTATION_SENT
        opportunity.save(update_fields=["stage", "updated_at"])
    create_opportunity_audit_log(
        opportunity=quote.opportunity,
        actor=actor,
        action=OpportunityAuditLog.Action.QUOTE_RESENT if is_resend else OpportunityAuditLog.Action.QUOTE_SENT,
        previous_value=previous_status,
        new_value=recipient,
    )
    if old_stage != opportunity.stage:
        create_opportunity_audit_log(
            opportunity=opportunity,
            actor=actor,
            action=OpportunityAuditLog.Action.STAGE_CHANGED,
            previous_value=old_stage,
            new_value=opportunity.stage,
        )
    return delivery
