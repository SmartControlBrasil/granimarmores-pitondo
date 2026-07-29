import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.validators import EmailValidator
from django.core.validators import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit_event
from customers.models import Customer
from customers.models import only_digits


logger = logging.getLogger(__name__)


REQUIRED_FIELDS = {
    "nome": "nome",
    "telefone": "telefone",
    "cidade": "cidade",
    "ambiente": "tipo de ambiente",
    "mensagem": "descrição do projeto",
}


class PublicContactValidationError(ValueError):
    pass


class PublicContactIdentityConflict(PublicContactValidationError):
    pass


@dataclass(frozen=True)
class PublicContactRequest:
    nome: str
    telefone: str
    email: str
    cidade: str
    ambiente: str
    mensagem: str


def validate_public_contact_request(post_data):
    missing = [
        label
        for field, label in REQUIRED_FIELDS.items()
        if not post_data.get(field, "").strip()
    ]
    if missing:
        raise PublicContactValidationError(
            "Preencha os campos obrigatórios para solicitar a avaliação.",
        )
    if not post_data.get("privacidade"):
        raise PublicContactValidationError(
            "Confirme o consentimento para contato antes de enviar.",
        )

    email = post_data.get("email", "").strip()
    if email:
        try:
            EmailValidator()(email)
        except ValidationError as exc:
            raise PublicContactValidationError("Informe um e-mail válido.") from exc

    return PublicContactRequest(
        nome=post_data.get("nome", "").strip(),
        telefone=post_data.get("telefone", "").strip(),
        email=email,
        cidade=post_data.get("cidade", "").strip(),
        ambiente=post_data.get("ambiente", "").strip(),
        mensagem=post_data.get("mensagem", "").strip(),
    )


def _find_customer_by_phone(phone):
    phone_digits = only_digits(phone)
    if not phone_digits:
        return None
    for customer in Customer.objects.filter(is_active=True).only(
        "id",
        "phone",
        "mobile_phone",
    ):
        if phone_digits in {
            only_digits(customer.phone),
            only_digits(customer.mobile_phone),
        }:
            return customer
    return None


def _find_customer_by_email(email):
    if not email:
        return None
    return (
        Customer.objects.filter(is_active=True, email__iexact=email)
        .order_by("created_at")
        .first()
    )


def _find_existing_customer(contact_request):
    phone_customer = _find_customer_by_phone(contact_request.telefone)
    email_customer = _find_customer_by_email(contact_request.email)

    if (
        phone_customer is not None
        and email_customer is not None
        and phone_customer.pk != email_customer.pk
    ):
        raise PublicContactIdentityConflict(
            "Não foi possível validar os dados informados. Entre em contato por telefone.",
        )

    return phone_customer or email_customer


def _request_notes(contact_request):
    submitted_at = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S %Z")
    lines = [
        "[Site institucional] Solicitação de orçamento",
        f"Recebida em: {submitted_at}",
        f"Nome: {contact_request.nome}",
        f"Telefone/WhatsApp: {contact_request.telefone}",
        f"E-mail: {contact_request.email or 'Não informado'}",
        f"Cidade: {contact_request.cidade}",
        f"Tipo de ambiente: {contact_request.ambiente}",
        "Descrição do projeto:",
        contact_request.mensagem,
    ]
    return "\n".join(lines)


def _metadata(contact_request, *, notification_sent=None):
    metadata = {
        "origin": "Site institucional",
        "source": "Formulário de contato",
        "request_type": "Solicitação de orçamento",
        "name": contact_request.nome,
        "phone": contact_request.telefone,
        "email": contact_request.email,
        "phone_digits": only_digits(contact_request.telefone),
        "city": contact_request.cidade,
        "environment": contact_request.ambiente,
    }
    if notification_sent is not None:
        metadata["notification_sent"] = notification_sent
    return metadata


@transaction.atomic
def persist_public_contact_request(contact_request, *, request=None):
    customer = _find_existing_customer(contact_request)
    created = customer is None
    request_notes = _request_notes(contact_request)

    if created:
        customer = Customer(
            customer_type=Customer.CustomerType.INDIVIDUAL,
            name=contact_request.nome,
            email=contact_request.email,
            mobile_phone=contact_request.telefone,
            notes=request_notes,
        )
    else:
        if not customer.email and contact_request.email:
            customer.email = contact_request.email
        if not customer.mobile_phone:
            customer.mobile_phone = contact_request.telefone
        if request_notes not in customer.notes:
            customer.notes = "\n\n".join(
                part for part in [customer.notes.strip(), request_notes] if part
            )

    customer.full_clean()
    customer.save()

    record_audit_event(
        request=request,
        event_type="create" if created else "update",
        module="customers",
        action="public_contact_received" if created else "public_contact_deduplicated",
        obj=customer,
        metadata=_metadata(contact_request),
    )
    return customer, created


def record_public_contact_identity_conflict(contact_request, *, request=None):
    record_audit_event(
        request=request,
        event_type="configuration",
        module="customers",
        action="public_contact_identity_conflict",
        status="failed",
        metadata=_metadata(contact_request),
    )


def send_public_contact_notification(customer, contact_request, *, request=None):
    subject = (
        "Nova solicitação de orçamento pelo site - "
        f"{contact_request.nome} - {contact_request.ambiente}"
    )
    body = "\n".join(
        [
            "Nova solicitação de orçamento pelo site da Granimármores Pitondo",
            "",
            f"Cliente no painel: {customer.name} (ID {customer.pk})",
            f"Nome: {contact_request.nome}",
            f"Telefone / WhatsApp: {contact_request.telefone}",
            f"E-mail: {contact_request.email or 'Não informado'}",
            f"Cidade: {contact_request.cidade}",
            f"Ambiente: {contact_request.ambiente}",
            "",
            "Descrição do projeto:",
            contact_request.mensagem,
            "",
            "Origem:",
            "Site institucional",
        ],
    )
    reply_to = [contact_request.email] if contact_request.email else None

    try:
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.CONTACT_RECIPIENT_EMAIL],
            reply_to=reply_to,
        )
        email.send(fail_silently=False)
    except Exception:
        logger.exception(
            "Falha ao enviar notificação de contato público",
            extra={"customer_id": customer.pk},
        )
        record_audit_event(
            request=request,
            event_type="send",
            module="customers",
            action="public_contact_notification",
            obj=customer,
            status="failed",
            metadata=_metadata(contact_request, notification_sent=False),
        )
        return False

    record_audit_event(
        request=request,
        event_type="send",
        module="customers",
        action="public_contact_notification",
        obj=customer,
        metadata=_metadata(contact_request, notification_sent=True),
    )
    return True
