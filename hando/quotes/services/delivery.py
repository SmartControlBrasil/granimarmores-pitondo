# ruff: noqa: EM101, TRY003, PLR0913
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit_event
from quotes.models import QuoteDelivery
from quotes.models import QuoteStatus
from quotes.services.pdf import generate_quote_pdf
from quotes.services.workflow import change_status


@transaction.atomic
def send_quote(
    *,
    quote,
    version,
    channel,
    recipient,
    subject,
    message,
    actor,
    request=None,
):
    if channel == QuoteDelivery.Channel.WHATSAPP:
        raise ValidationError("WhatsApp não está configurado nesta etapa.")
    if not recipient:
        raise ValidationError("Destinatário é obrigatório.")
    if not version.pdf_file:
        generate_quote_pdf(version=version, actor=actor, request=request)
    delivery = QuoteDelivery.objects.create(
        quote=quote,
        quote_version=version,
        channel=channel,
        recipient=recipient,
        subject=subject,
        message=message[:500],
        sent_by=actor,
    )
    try:
        if channel == QuoteDelivery.Channel.EMAIL:
            email = EmailMessage(subject=subject, body=message, to=[recipient])
            version.pdf_file.open("rb")
            email.attach(
                version.pdf_file.name.split("/")[-1],
                version.pdf_file.read(),
                "application/pdf",
            )
            email.send(fail_silently=False)
        delivery.status = QuoteDelivery.Status.SENT
        delivery.sent_at = timezone.now()
        delivery.save(update_fields=["status", "sent_at"])
        if quote.status == QuoteStatus.APPROVED:
            change_status(
                quote=quote,
                target_status=QuoteStatus.SENT,
                actor=actor,
                request=request,
                metadata={"version": version.version_number},
            )
        version.sent_at = timezone.now()
        version.sent_by = actor
        version.save_base(raw=True, update_fields=["sent_at", "sent_by"])
        record_audit_event(
            request=request,
            user=actor,
            event_type="send",
            module="quotes",
            action="quote_sent",
            obj=quote,
            metadata={
                "quote_number": quote.number,
                "version": version.version_number,
                "channel": channel,
                "recipient": recipient,
            },
        )
        from commercial.performance_score_hooks import score_quote_sent

        score_quote_sent(quote=quote, actor=actor, request=request)
    except Exception as exc:
        delivery.status = QuoteDelivery.Status.FAILED
        delivery.error_message = str(exc)[:500]
        delivery.save(update_fields=["status", "error_message"])
        record_audit_event(
            request=request,
            user=actor,
            event_type="send",
            module="quotes",
            action="quote_send_failed",
            obj=quote,
            status="failed",
            metadata={
                "quote_number": quote.number,
                "version": version.version_number,
                "channel": channel,
            },
        )
        raise
    return delivery
