# ruff: noqa: PLR0913
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from audit.services import record_audit_event
from audit.services import safe_changes
from commercial.models import CommercialPartner
from commercial.models import CommercialSource
from commercial.models import ContactChannel
from commercial.models import LossReason
from commercial.models import ProjectType
from commercial.models import ServiceRegion


def _ensure_slug(instance, *, slug_field="slug", name_field="name"):
    current_slug = getattr(instance, slug_field)
    if not current_slug:
        base = slugify(getattr(instance, name_field)) or "item"
        slug = base
        counter = 1
        model = instance.__class__
        while model.objects.filter(**{slug_field: slug}).exclude(pk=instance.pk).exists():
            counter += 1
            slug = f"{base}-{counter}"
        setattr(instance, slug_field, slug)


def _snapshot(instance, fields):
    return {field: getattr(instance, field) for field in fields}


def _save_master(*, form, actor, request, module, action_prefix, slug_fields=None):
    obj = form.save(commit=False)
    if slug_fields:
        _ensure_slug(obj, slug_field=slug_fields)
    creating = obj.pk is None
    before = _snapshot(obj, form.changed_data) if obj.pk else {}
    if creating:
        obj.created_by = actor
    obj.updated_by = actor
    obj.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="create" if creating else "update",
        module=module,
        action=f"{action_prefix}_created" if creating else f"{action_prefix}_updated",
        obj=obj,
        metadata=safe_changes(before, _snapshot(obj, form.changed_data)) if not creating else None,
    )
    return obj


@transaction.atomic
def save_commercial_source(*, form, actor, request=None):
    return _save_master(
        form=form,
        actor=actor,
        request=request,
        module="commercial",
        action_prefix="commercial_source",
        slug_fields="slug",
    )


@transaction.atomic
def save_project_type(*, form, actor, request=None):
    return _save_master(
        form=form,
        actor=actor,
        request=request,
        module="commercial",
        action_prefix="project_type",
        slug_fields="slug",
    )


@transaction.atomic
def save_commercial_partner(*, form, actor, request=None):
    return _save_master(
        form=form,
        actor=actor,
        request=request,
        module="commercial",
        action_prefix="commercial_partner",
    )


@transaction.atomic
def save_loss_reason(*, form, actor, request=None):
    return _save_master(
        form=form,
        actor=actor,
        request=request,
        module="commercial",
        action_prefix="loss_reason",
        slug_fields="slug",
    )


@transaction.atomic
def save_service_region(*, form, actor, request=None):
    return _save_master(
        form=form,
        actor=actor,
        request=request,
        module="commercial",
        action_prefix="service_region",
    )


@transaction.atomic
def save_contact_channel(*, form, actor, request=None):
    return _save_master(
        form=form,
        actor=actor,
        request=request,
        module="commercial",
        action_prefix="contact_channel",
        slug_fields="slug",
    )


@transaction.atomic
def set_master_active(*, obj, is_active, actor, request=None, action_prefix="master"):
    before = {"is_active": obj.is_active}
    if is_active:
        obj.reactivate(actor)
    else:
        obj.deactivate(actor)
    record_audit_event(
        request=request,
        user=actor,
        event_type="reactivate" if is_active else "deactivate",
        module="commercial",
        action=f"{action_prefix}_activated" if is_active else f"{action_prefix}_deactivated",
        obj=obj,
        metadata=safe_changes(before, {"is_active": obj.is_active}),
    )
    return obj


def try_delete_master(*, obj, actor, request=None, action_prefix="master"):
    try:
        obj.delete()
    except ValidationError as exc:
        record_audit_event(
            request=request,
            user=actor,
            event_type="configuration",
            module="commercial",
            action=f"{action_prefix}_delete_blocked",
            obj=obj,
            status="denied",
            description=str(exc.message if hasattr(exc, "message") else exc),
        )
        raise
    record_audit_event(
        request=request,
        user=actor,
        event_type="configuration",
        module="commercial",
        action=f"{action_prefix}_deleted",
        obj=obj,
    )


MODEL_REGISTRY = {
    "source": (CommercialSource, "commercial_sources", "commercial_source"),
    "project_type": (ProjectType, "project_types", "project_type"),
    "partner": (CommercialPartner, "commercial_partners", "commercial_partner"),
    "loss_reason": (LossReason, "loss_reasons", "loss_reason"),
    "region": (ServiceRegion, "service_regions", "service_region"),
    "channel": (ContactChannel, "contact_channels", "contact_channel"),
}

SAVE_HANDLERS = {
    "source": save_commercial_source,
    "project_type": save_project_type,
    "partner": save_commercial_partner,
    "loss_reason": save_loss_reason,
    "region": save_service_region,
    "channel": save_contact_channel,
}
