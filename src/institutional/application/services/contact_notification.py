import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


def notify_contact_request(contact_request):
    recipient = getattr(settings, "CONTACT_NOTIFICATION_EMAIL", "")
    if not recipient:
        logger.info(
            "Notificação de contato não enviada: CONTACT_NOTIFICATION_EMAIL vazio.",
            extra={"contact_request_id": contact_request.pk},
        )
        return False

    subject = f"Nova solicitação de orçamento - {contact_request.nome}"
    message = render_to_string(
        "institutional/emails/contact_request.txt",
        {"contact": contact_request},
    )

    try:
        sent = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001
        contact_request.notification_error = str(exc)[:1000]
        contact_request.save(update_fields=["notification_error", "updated_at"])
        logger.exception(
            "Falha ao enviar notificação de contato.",
            extra={"contact_request_id": contact_request.pk},
        )
        return False

    if sent:
        contact_request.notification_sent_at = timezone.now()
        contact_request.notification_error = ""
        contact_request.save(
            update_fields=[
                "notification_sent_at",
                "notification_error",
                "updated_at",
            ],
        )
        return True

    contact_request.notification_error = "Backend de email não confirmou envio."
    contact_request.save(update_fields=["notification_error", "updated_at"])
    return False
