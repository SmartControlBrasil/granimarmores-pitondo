# ruff: noqa: PERF401
import json
from decimal import Decimal

from django.db import transaction

from audit.services import record_audit_event
from quotes.models import QuoteVersion


def _decimal(value):
    if isinstance(value, Decimal):
        return str(value)
    return value


def build_snapshot(quote):
    items = []
    for item in quote.items.select_related("material").prefetch_related(
        "measurements",
        "finishes__finish_type",
    ):
        items.append(
            {
                "description": item.description,
                "material_code": item.material_code_snapshot,
                "material_name": item.material_name_snapshot,
                "quantity": str(item.quantity),
                "unit": item.unit,
                "area_m2": str(item.area_m2),
                "unit_price": str(item.unit_price),
                "subtotal": str(item.subtotal),
                "measurements": [
                    {
                        "label": m.label,
                        "width_mm": str(m.width_mm),
                        "length_mm": str(m.length_mm),
                        "quantity": str(m.quantity),
                        "area_m2": str(m.area_m2),
                    }
                    for m in item.measurements.all()
                ],
                "finishes": [
                    {
                        "description": f.description_snapshot,
                        "quantity": str(f.quantity),
                        "unit_price": str(f.unit_price),
                        "subtotal": str(f.subtotal),
                    }
                    for f in item.finishes.all()
                ],
            },
        )
    services = [
        {
            "description": s.description_snapshot,
            "quantity": str(s.quantity),
            "unit_price": str(s.unit_price),
            "subtotal": str(s.subtotal),
        }
        for s in quote.services.select_related("service")
    ]
    return json.loads(
        json.dumps(
            {
                "number": quote.number,
                "customer": str(quote.customer),
                "customer_email": quote.customer.email,
                "salesperson": str(quote.salesperson),
                "status": quote.status,
                "valid_until": quote.valid_until.isoformat()
                if quote.valid_until
                else "",
                "payment_terms": quote.payment_terms,
                "customer_notes": quote.customer_notes,
                "items": items,
                "services": services,
                "subtotal": str(quote.subtotal),
                "discount_total": str(quote.discount_total),
                "tax_total": str(quote.tax_total),
                "grand_total": str(quote.grand_total),
                "total_cost": str(quote.total_cost),
                "gross_profit": str(quote.gross_profit),
                "gross_margin_percentage": str(quote.gross_margin_percentage),
            },
            default=_decimal,
        ),
    )


@transaction.atomic
def create_version(*, quote, actor=None, request=None, status=None):
    version_number = quote.versions.count() + 1
    version = QuoteVersion.objects.create(
        quote=quote,
        version_number=version_number,
        status=status or quote.status,
        snapshot=build_snapshot(quote),
        subtotal=quote.subtotal,
        discount_total=quote.discount_total,
        tax_total=quote.tax_total,
        grand_total=quote.grand_total,
        total_cost=quote.total_cost,
        gross_profit=quote.gross_profit,
        gross_margin_percentage=quote.gross_margin_percentage,
        created_by=actor,
    )
    quote.current_version = version.version_number
    quote.save(update_fields=["current_version", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="configuration",
        module="quotes",
        action="quote_version_created",
        obj=quote,
        metadata={"quote_number": quote.number, "version": version.version_number},
    )
    return version
