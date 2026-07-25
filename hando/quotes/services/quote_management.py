# ruff: noqa: EM101, TRY003, PLR0913
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit_event
from audit.services import safe_changes
from quotes.models import QuoteStatus
from quotes.services.calculation import calculate_finish
from quotes.services.calculation import calculate_item
from quotes.services.calculation import calculate_measurement
from quotes.services.calculation import calculate_quote
from quotes.services.calculation import calculate_service
from quotes.services.numbering import next_quote_number
from quotes.services.versioning import create_version

LOCKED_STATUSES = {
    QuoteStatus.SENT,
    QuoteStatus.VIEWED,
    QuoteStatus.ACCEPTED,
    QuoteStatus.CANCELLED,
    QuoteStatus.CONVERTED,
}


def assert_quote_editable(quote):
    if quote.status in LOCKED_STATUSES:
        raise PermissionDenied(
            (
                "Orçamento enviado, aceito, convertido ou cancelado "
                "não pode ser alterado diretamente."
            ),
        )


def _snapshot_quote_values(quote):
    return {
        "status": quote.status,
        "subtotal": quote.subtotal,
        "grand_total": quote.grand_total,
        "gross_margin_percentage": quote.gross_margin_percentage,
    }


@transaction.atomic
def save_quote(*, form, actor, request=None):
    quote = form.save(commit=False)
    creating = quote.pk is None
    before = _snapshot_quote_values(quote) if quote.pk else {}
    if creating:
        quote.number = next_quote_number()
        quote.created_by = actor
    else:
        assert_quote_editable(quote)
    quote.updated_by = actor
    if not quote.valid_until:
        quote.valid_until = timezone.localdate()
    quote.save()
    calculate_quote(quote)
    quote.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="create" if creating else "update",
        module="quotes",
        action="quote_created" if creating else "quote_updated",
        obj=quote,
        metadata=safe_changes(before, _snapshot_quote_values(quote)),
    )
    return quote


@transaction.atomic
def save_quote_item(*, quote, form, actor, request=None):
    assert_quote_editable(quote)
    item = form.save(commit=False)
    item.quote = quote
    if item.material:
        if not item.material.is_active:
            raise ValidationError(
                "Material inativo não pode entrar em novo orçamento comum.",
            )
        item.material_code_snapshot = item.material.code
        item.material_name_snapshot = item.material.name
        item.unit = item.unit or item.material.unit
        if not item.unit_cost:
            item.unit_cost = item.material.cost_price
        if not item.unit_price:
            item.unit_price = item.material.sale_price
        if not item.loss_percentage:
            item.loss_percentage = item.material.loss_percentage
        item.thickness_mm = item.thickness_mm or item.material.thickness_mm
        if item.unit_price < item.material.minimum_sale_price:
            item.needs_price_approval = True
            if not item.below_minimum_reason:
                raise ValidationError("Preço abaixo do mínimo exige justificativa.")
    if not item.pk:
        item.created_by = actor
    item.updated_by = actor
    item.full_clean()
    calculate_item(item)
    item.save()
    calculate_quote(quote)
    quote.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="configuration",
        module="quotes",
        action="quote_item_added" if form.instance.pk is None else "quote_item_updated",
        obj=quote,
        metadata={
            "quote_number": quote.number,
            "item": str(item),
            "new_total": str(quote.grand_total),
        },
    )
    return item


@transaction.atomic
def save_measurement(*, item, form, actor=None, request=None):
    assert_quote_editable(item.quote)
    measurement = form.save(commit=False)
    measurement.quote_item = item
    calculate_measurement(measurement)
    measurement.save()
    calculate_item(item)
    item.save()
    calculate_quote(item.quote)
    item.quote.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="configuration",
        module="quotes",
        action="quote_item_updated",
        obj=item.quote,
        metadata={"measurement": measurement.label},
    )
    return measurement


@transaction.atomic
def save_item_finish(*, item, form, actor=None, request=None):
    assert_quote_editable(item.quote)
    finish = form.save(commit=False)
    finish.quote_item = item
    finish.description_snapshot = finish.finish_type.name
    finish.unit = finish.finish_type.unit
    if not finish.unit_cost:
        finish.unit_cost = finish.finish_type.cost_price
    if not finish.unit_price:
        finish.unit_price = finish.finish_type.sale_price
    calculate_finish(finish)
    finish.save()
    calculate_quote(item.quote)
    item.quote.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="configuration",
        module="quotes",
        action="quote_item_updated",
        obj=item.quote,
        metadata={"finish": finish.description_snapshot},
    )
    return finish


@transaction.atomic
def save_quote_service(*, quote, form, actor=None, request=None):
    assert_quote_editable(quote)
    service_line = form.save(commit=False)
    service_line.quote = quote
    service_line.description_snapshot = service_line.service.name
    service_line.unit = service_line.service.unit
    if not service_line.unit_cost:
        service_line.unit_cost = service_line.service.cost_price
    if not service_line.unit_price:
        service_line.unit_price = service_line.service.sale_price
    calculate_service(service_line)
    service_line.save()
    calculate_quote(quote)
    quote.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="configuration",
        module="quotes",
        action="quote_item_added",
        obj=quote,
        metadata={"service": service_line.description_snapshot},
    )
    return service_line


@transaction.atomic
def remove_quote_item(*, item, actor, request=None):
    quote = item.quote
    assert_quote_editable(quote)
    description = str(item)
    item.delete()
    calculate_quote(quote)
    quote.save()
    if quote.current_version:
        create_version(quote=quote, actor=actor, request=request, status=quote.status)
    record_audit_event(
        request=request,
        user=actor,
        event_type="delete",
        module="quotes",
        action="quote_item_removed",
        obj=quote,
        metadata={"item": description, "new_total": str(quote.grand_total)},
    )
    return quote
