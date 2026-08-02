# ruff: noqa: EM101, TRY003
from django.core.exceptions import PermissionDenied
from django.db import transaction

from access_control.services.authorization import can_access_object
from audit.services import record_audit_event
from audit.services import safe_changes


def _snapshot(customer):
    return {
        "customer_type": customer.customer_type,
        "name": customer.name,
        "trade_name": customer.trade_name,
        "document": customer.document,
        "email": customer.email,
        "phone": customer.phone,
        "mobile_phone": customer.mobile_phone,
        "assigned_salesperson": customer.assigned_salesperson_id,
        "commercial_source": customer.commercial_source_id,
        "partner": customer.partner_id,
        "project_type_interest": customer.project_type_interest_id,
        "preferred_contact_channel": customer.preferred_contact_channel_id,
        "is_active": customer.is_active,
    }


@transaction.atomic
def create_customer(*, form, actor, request=None):
    customer = form.save(commit=False)
    customer.created_by = actor
    customer.updated_by = actor
    customer.save()
    form.save_m2m()
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="customers",
        action="create",
        obj=customer,
    )
    return customer


@transaction.atomic
def update_customer(*, customer, form, actor, request=None):
    if not can_access_object(actor, customer, "update"):
        raise PermissionDenied("Você não tem acesso a este cliente.")
    before = _snapshot(customer)
    customer = form.save(commit=False)
    customer.updated_by = actor
    customer.save()
    form.save_m2m()
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="customers",
        action="update",
        obj=customer,
        metadata=safe_changes(before, _snapshot(customer)),
    )
    return customer


@transaction.atomic
def set_customer_active(*, customer, is_active, actor, request=None):
    if not can_access_object(actor, customer, "update"):
        raise PermissionDenied("Você não tem acesso a este cliente.")
    before = {"is_active": customer.is_active}
    if is_active:
        customer.reactivate(actor)
    else:
        customer.deactivate(actor)
    record_audit_event(
        request=request,
        user=actor,
        event_type="reactivate" if is_active else "deactivate",
        module="customers",
        action="activate" if is_active else "deactivate",
        obj=customer,
        metadata=safe_changes(before, {"is_active": customer.is_active}),
    )
    return customer
