# ruff: noqa: PLR0913
from decimal import ROUND_HALF_UP
from decimal import Decimal

MONEY = Decimal("0.01")
AREA = Decimal("0.0001")
PERCENT = Decimal("0.01")


def d(value):
    return Decimal(str(value or "0"))


def money(value):
    return d(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def percentage(value):
    return d(value).quantize(PERCENT, rounding=ROUND_HALF_UP)


def area_from_mm(width_mm, length_mm, quantity=Decimal("1")):
    return (d(width_mm) * d(length_mm) * d(quantity) / Decimal("1000000")).quantize(
        AREA,
        rounding=ROUND_HALF_UP,
    )


def apply_loss(quantity, loss_percentage):
    return d(quantity) * (Decimal("1") + d(loss_percentage) / Decimal("100"))


def calculate_line(quantity, unit_price, discount_percentage=Decimal("0")):
    subtotal = d(quantity) * d(unit_price)
    discount = subtotal * d(discount_percentage) / Decimal("100")
    return money(max(Decimal("0"), subtotal - discount))


def margin_percentage(gross_profit, grand_total):
    if d(grand_total) == 0:
        return Decimal("0.00")
    return percentage(d(gross_profit) / d(grand_total) * Decimal("100"))


def calculate_item(item):
    measurement_area = (
        sum((m.area_m2 for m in item.measurements.all()), Decimal("0"))
        if item.pk
        else Decimal("0")
    )
    base_area = measurement_area or area_from_mm(
        item.width_mm,
        item.length_mm,
        item.quantity,
    )
    if item.unit == "m2":
        priced_quantity = apply_loss(base_area, item.loss_percentage)
        item.area_m2 = base_area
    else:
        priced_quantity = apply_loss(item.quantity, item.loss_percentage)
        item.area_m2 = base_area if base_area else Decimal("0.0000")
    item.subtotal = calculate_line(
        priced_quantity,
        item.unit_price,
        item.discount_percentage,
    )
    item.total_cost = money(priced_quantity * item.unit_cost)
    item.gross_profit = money(item.subtotal - item.total_cost)
    item.gross_margin_percentage = margin_percentage(item.gross_profit, item.subtotal)
    return item


def calculate_measurement(measurement):
    measurement.area_m2 = area_from_mm(
        measurement.width_mm,
        measurement.length_mm,
        measurement.quantity,
    )
    return measurement


def calculate_finish(finish):
    finish.subtotal = calculate_line(finish.quantity, finish.unit_price)
    return finish


def calculate_service(service):
    service.subtotal = calculate_line(service.quantity, service.unit_price)
    return service


def calculate_quote(quote):
    items_subtotal = (
        sum((item.subtotal for item in quote.items.all()), Decimal("0"))
        if quote.pk
        else Decimal("0")
    )
    finishes_subtotal = Decimal("0")
    item_cost = Decimal("0")
    finish_cost = Decimal("0")
    if quote.pk:
        for item in quote.items.all():
            finishes_subtotal += sum(
                (finish.subtotal for finish in item.finishes.all()),
                Decimal("0"),
            )
            item_cost += item.total_cost
            finish_cost += sum(
                (finish.unit_cost * finish.quantity for finish in item.finishes.all()),
                Decimal("0"),
            )
    service_subtotal = (
        sum((service.subtotal for service in quote.services.all()), Decimal("0"))
        if quote.pk
        else Decimal("0")
    )
    service_cost = (
        sum(
            (service.unit_cost * service.quantity for service in quote.services.all()),
            Decimal("0"),
        )
        if quote.pk
        else Decimal("0")
    )
    quote.subtotal = money(
        items_subtotal
        + finishes_subtotal
        + service_subtotal
        + quote.shipping_value
        + quote.installation_value
        + quote.other_value,
    )
    if quote.discount_type == "percentage":
        quote.discount_total = money(
            quote.subtotal * quote.discount_value / Decimal("100"),
        )
    elif quote.discount_type == "fixed":
        quote.discount_total = money(min(quote.subtotal, quote.discount_value))
    else:
        quote.discount_total = Decimal("0.00")
    taxable = max(Decimal("0"), quote.subtotal - quote.discount_total)
    quote.tax_total = money(taxable * quote.tax_percentage / Decimal("100"))
    quote.grand_total = money(max(Decimal("0"), taxable + quote.tax_total))
    quote.total_cost = money(item_cost + finish_cost + service_cost)
    quote.gross_profit = money(quote.grand_total - quote.total_cost)
    quote.gross_margin_percentage = margin_percentage(
        quote.gross_profit,
        quote.grand_total,
    )
    return quote
