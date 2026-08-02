# ruff: noqa: EM101, PLR0913, TRY003
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from production.models import SalesOrder
from production.models import SalesOrderItem
from production.models import SalesOrderItemMeasurement
from production.models import SalesOrderStatus
from production.services.numbering import next_sales_order_number
from quotes.models import QuoteStatus


@transaction.atomic
def create_sales_order_from_quote(*, quote, actor, request=None):
    if quote.status != QuoteStatus.ACCEPTED:
        raise ValidationError("Pedido exige orçamento aceito.")
    if not user_has_permission(actor, "sales_orders.create"):
        raise PermissionDenied("Sem permissão para criar pedido.")

    existing = SalesOrder.objects.filter(quote=quote).exclude(
        status=SalesOrderStatus.CANCELLED,
    ).first()
    if existing:
        return existing

    customer = quote.customer
    order = SalesOrder(
        number=next_sales_order_number(),
        quote=quote,
        customer=customer,
        lead=quote.lead,
        salesperson=quote.salesperson,
        status=SalesOrderStatus.CONFIRMED,
        subtotal=quote.subtotal,
        discount=quote.discount_total,
        additional_costs=quote.shipping_value + quote.installation_value + quote.other_value,
        total=quote.grand_total,
        customer_notes=quote.customer_notes or "",
        commercial_notes=quote.internal_notes or "",
        delivery_required=True,
        installation_required=quote.installation_value > 0,
        created_by=actor,
        updated_by=actor,
    )
    order.save()

    for item in quote.items.prefetch_related("measurements", "finishes").order_by("position"):
        finish_names = ", ".join(f.description_snapshot or str(f.finish_type) for f in item.finishes.all())
        order_item = SalesOrderItem.objects.create(
            order=order,
            quote_item_id=item.pk,
            description=item.description or item.material_name_snapshot or "Item",
            project_type_name=quote.project_type.name if quote.project_type_id else "",
            material=item.material,
            material_name_snapshot=item.material_name_snapshot,
            finish_name_snapshot=finish_names[:180],
            quantity=item.quantity,
            unit=item.unit,
            width=item.width_mm,
            height=item.length_mm,
            depth=item.thickness_mm,
            area=item.area_m2 if item.area_m2 else Decimal("0.0000"),
            unit_price=item.unit_price,
            discount=Decimal("0.00"),
            total=item.subtotal,
            technical_notes=item.notes or "",
            position=item.position,
        )
        for measurement in item.measurements.all():
            SalesOrderItemMeasurement.objects.create(
                order_item=order_item,
                label=measurement.label,
                width=measurement.width_mm,
                height=measurement.length_mm,
                area=measurement.area_m2,
                notes=measurement.notes or "",
                position=measurement.position,
            )

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="production",
        action="sales_order_created",
        obj=order,
        metadata={"quote_number": quote.number},
    )
    return order
