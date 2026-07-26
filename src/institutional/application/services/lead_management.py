from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction

from src.institutional.application.services.access_policy import assignable_users_queryset
from src.institutional.application.services.access_policy import can_add_note
from src.institutional.application.services.access_policy import can_assign_lead
from src.institutional.application.services.access_policy import can_change_lead
from src.institutional.application.services.access_policy import get_visible_contact_requests
from src.institutional.infrastructure.django.models import ContactRequest
from src.institutional.infrastructure.django.models import ContactRequestAuditLog
from src.institutional.infrastructure.django.models import ContactRequestNote


def create_audit_log(
    *,
    contact_request,
    action,
    actor=None,
    previous_value="",
    new_value="",
    source="",
):
    return ContactRequestAuditLog.objects.create(
        contact_request=contact_request,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        previous_value=previous_value or "",
        new_value=new_value or "",
        source=source or "",
    )


def record_lead_created(contact_request, *, source="public-site"):
    return create_audit_log(
        contact_request=contact_request,
        action=ContactRequestAuditLog.Action.LEAD_CREATED,
        source=source,
        new_value=contact_request.status,
    )


@transaction.atomic
def change_contact_status(*, contact_request_id, status, actor):
    valid_statuses = {choice for choice, _ in ContactRequest.Status.choices}
    if status not in valid_statuses:
        raise ValidationError("Status inválido.")

    contact_request = get_visible_contact_requests(actor).select_for_update().get(
        pk=contact_request_id,
    )
    if not can_change_lead(actor, contact_request):
        raise PermissionDenied("Você não tem permissão para executar esta ação.")
    previous_status = contact_request.status
    if previous_status == status:
        return contact_request

    contact_request.status = status
    contact_request.save(update_fields=["status", "updated_at"])
    create_audit_log(
        contact_request=contact_request,
        actor=actor,
        action=ContactRequestAuditLog.Action.STATUS_CHANGED,
        previous_value=previous_status,
        new_value=status,
    )
    return contact_request


@transaction.atomic
def assign_contact_request(*, contact_request_id, assigned_to_id, actor):
    contact_request = get_visible_contact_requests(actor).select_for_update().get(
        pk=contact_request_id,
    )
    if not can_assign_lead(actor, contact_request):
        raise PermissionDenied("Você não tem permissão para executar esta ação.")
    previous = contact_request.assigned_to
    assigned_to = None
    if assigned_to_id:
        user_model = get_user_model()
        try:
            assigned_to = assignable_users_queryset(user_model).get(pk=assigned_to_id)
        except user_model.DoesNotExist as exc:
            raise ValidationError("Responsável inválido.") from exc

    if previous == assigned_to:
        return contact_request

    contact_request.assigned_to = assigned_to
    contact_request.save(update_fields=["assigned_to", "updated_at"])
    create_audit_log(
        contact_request=contact_request,
        actor=actor,
        action=ContactRequestAuditLog.Action.ASSIGNED,
        previous_value=previous.get_username() if previous else "",
        new_value=assigned_to.get_username() if assigned_to else "",
    )
    return contact_request


@transaction.atomic
def add_contact_note(*, contact_request_id, content, actor):
    cleaned_content = (content or "").strip()
    if not cleaned_content:
        raise ValidationError("Informe uma observação.")

    contact_request = get_visible_contact_requests(actor).select_for_update().get(
        pk=contact_request_id,
    )
    if not can_add_note(actor, contact_request):
        raise PermissionDenied("Você não tem permissão para executar esta ação.")
    note = ContactRequestNote.objects.create(
        contact_request=contact_request,
        author=actor,
        content=cleaned_content,
    )
    create_audit_log(
        contact_request=contact_request,
        actor=actor,
        action=ContactRequestAuditLog.Action.NOTE_ADDED,
        new_value=str(note.pk),
    )
    return note
