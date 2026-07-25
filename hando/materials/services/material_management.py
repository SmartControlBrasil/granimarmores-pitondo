# ruff: noqa: PLR0913
from django.db import transaction

from audit.services import record_audit_event
from audit.services import safe_changes
from materials.models import MaterialPriceHistory


def _price_snapshot(material):
    return {
        "cost_price": material.cost_price,
        "sale_price": material.sale_price,
        "minimum_sale_price": material.minimum_sale_price,
    }


def _record_price_changes(material, before, actor, reason, request=None):
    mapping = {
        "cost_price": "cost",
        "sale_price": "sale",
        "minimum_sale_price": "minimum_sale",
    }
    for field, price_type in mapping.items():
        old = before.get(field)
        new = getattr(material, field)
        if old != new:
            MaterialPriceHistory.objects.create(
                material=material,
                price_type=price_type,
                old_value=old,
                new_value=new,
                reason=reason,
                changed_by=actor,
            )
            record_audit_event(
                request=request,
                user=actor,
                event_type="configuration",
                module="materials",
                action="material_price_changed",
                obj=material,
                metadata={
                    "price_type": price_type,
                    "old_value": str(old),
                    "new_value": str(new),
                },
            )


@transaction.atomic
def save_category(*, form, actor, request=None):
    category = form.save(commit=False)
    if not category.pk:
        category.created_by = actor
    category.updated_by = actor
    category.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="configuration",
        module="materials",
        action="material_category_saved",
        obj=category,
    )
    return category


@transaction.atomic
def set_active(*, obj, is_active, actor, request=None, action_prefix="material"):
    before = {"is_active": obj.is_active}
    if is_active:
        obj.reactivate(actor)
    else:
        obj.deactivate(actor)
    record_audit_event(
        request=request,
        user=actor,
        event_type="reactivate" if is_active else "deactivate",
        module="materials",
        action=f"{action_prefix}_{'activated' if is_active else 'deactivated'}",
        obj=obj,
        metadata=safe_changes(before, {"is_active": obj.is_active}),
    )
    return obj


@transaction.atomic
def save_material(*, form, actor, request=None):
    before = {}
    if form.instance.pk:
        before = _price_snapshot(type(form.instance).objects.get(pk=form.instance.pk))
    material = form.save(commit=False)
    if not material.pk:
        material.created_by = actor
    material.updated_by = actor
    material.full_clean()
    material.save()
    reason = form.cleaned_data.get("price_change_reason", "")
    if before:
        _record_price_changes(material, before, actor, reason, request=request)
        action = "material_updated"
        event_type = "update"
    else:
        action = "material_created"
        event_type = "create"
    record_audit_event(
        request=request,
        user=actor,
        event_type=event_type,
        module="materials",
        action=action,
        obj=material,
    )
    return material


@transaction.atomic
def save_priced_model(*, form, actor, request=None, module_action):
    obj = form.save(commit=False)
    if not obj.pk:
        obj.created_by = actor
    obj.updated_by = actor
    obj.full_clean()
    obj.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="configuration",
        module="materials",
        action=module_action,
        obj=obj,
    )
    return obj
