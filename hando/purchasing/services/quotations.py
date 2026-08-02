# ruff: noqa: PLR0913
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from audit.services import record_audit_event
from purchasing.models import QuotationStatus
from purchasing.models import RequestStatus
from purchasing.models import SupplierQuotation
from purchasing.models import SupplierQuotationItem
from purchasing.services.numbering import next_quotation_number


def _line_total(*, quantity, unit_price, discount_amount, freight_share, tax_amount):
    return (quantity * unit_price) - discount_amount + freight_share + tax_amount


@transaction.atomic
def create_quotation(*, purchase_request, supplier, data, items, actor, request=None):
    if purchase_request.status in {
        RequestStatus.DRAFT,
        RequestStatus.REJECTED,
        RequestStatus.CANCELLED,
    }:
        raise ValidationError("Solicitação não permite cotação neste status.")
    if not supplier:
        raise ValidationError("Fornecedor é obrigatório.")
    if not items:
        raise ValidationError("Informe ao menos um item cotado.")

    freight = Decimal(str(data.get("freight_amount") or "0"))
    discount = Decimal(str(data.get("discount_amount") or "0"))
    if freight < 0 or discount < 0:
        raise ValidationError("Valores não podem ser negativos.")

    quotation = SupplierQuotation(
        number=next_quotation_number(),
        purchase_request=purchase_request,
        supplier=supplier,
        status=QuotationStatus.RECEIVED,
        quotation_date=data.get("quotation_date") or timezone.localdate(),
        valid_until=data.get("valid_until"),
        delivery_days=int(data.get("delivery_days") or 0),
        freight_amount=freight,
        discount_amount=discount,
        payment_term_text=data.get("payment_term_text") or "",
        payment_method=data.get("payment_method"),
        notes=data.get("notes") or "",
        received_by=actor,
        created_by=actor,
        updated_by=actor,
    )
    quotation.save()

    total = Decimal("0.00")
    for raw in items:
        qty = Decimal(str(raw["quantity"]))
        price = Decimal(str(raw.get("unit_price") or "0"))
        if qty <= 0:
            raise ValidationError("Quantidade cotada deve ser positiva.")
        if price < 0:
            raise ValidationError("Preço não pode ser negativo.")
        line_discount = Decimal(str(raw.get("discount_amount") or "0"))
        freight_share = Decimal(str(raw.get("freight_share") or "0"))
        tax = Decimal(str(raw.get("tax_amount") or "0"))
        line_total = _line_total(
            quantity=qty,
            unit_price=price,
            discount_amount=line_discount,
            freight_share=freight_share,
            tax_amount=tax,
        )
        SupplierQuotationItem.objects.create(
            quotation=quotation,
            request_item=raw.get("request_item"),
            supplier_code=raw.get("supplier_code") or "",
            description=(raw.get("description") or "").strip() or "Item",
            quantity=qty,
            unit=raw.get("unit") or "un",
            unit_price=price,
            discount_amount=line_discount,
            freight_share=freight_share,
            tax_amount=tax,
            total_amount=line_total,
            delivery_days=int(raw.get("delivery_days") or quotation.delivery_days),
            brand=raw.get("brand") or "",
            batch=raw.get("batch") or "",
            notes=raw.get("notes") or "",
        )
        total += line_total

    quotation.total_amount = total + freight - discount
    if quotation.total_amount < 0:
        raise ValidationError("Total da cotação não pode ser negativo.")
    quotation.save(update_fields=["total_amount", "updated_at"])

    _refresh_request_quote_status(purchase_request)
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="purchasing",
        action="create_quotation",
        obj=quotation,
        description=f"Registrou cotação {quotation.number}",
    )
    return quotation


def _refresh_request_quote_status(purchase_request):
    if purchase_request.status in {
        RequestStatus.ORDERED,
        RequestStatus.PARTIALLY_RECEIVED,
        RequestStatus.RECEIVED,
        RequestStatus.CANCELLED,
        RequestStatus.REJECTED,
    }:
        return
    quotes = purchase_request.quotations.exclude(
        status__in=[QuotationStatus.CANCELLED, QuotationStatus.REJECTED, QuotationStatus.EXPIRED],
    )
    if not quotes.exists():
        return
    request_items = purchase_request.items.count()
    covered = (
        SupplierQuotationItem.objects.filter(quotation__in=quotes, request_item__isnull=False)
        .values("request_item")
        .distinct()
        .count()
    )
    if covered >= request_items and request_items > 0:
        purchase_request.status = RequestStatus.QUOTED
    else:
        purchase_request.status = RequestStatus.PARTIALLY_QUOTED
    purchase_request.save(update_fields=["status", "updated_at"])


def compare_quotations(*, purchase_request):
    quotations = list(
        purchase_request.quotations.exclude(
            status__in=[QuotationStatus.CANCELLED, QuotationStatus.EXPIRED],
        )
        .select_related("supplier")
        .prefetch_related("items"),
    )
    rows = []
    for req_item in purchase_request.items.all():
        offers = []
        for q in quotations:
            for qi in q.items.all():
                if qi.request_item_id == req_item.id:
                    offers.append(
                        {
                            "quotation": q,
                            "item": qi,
                            "supplier": q.supplier,
                            "unit_price": qi.unit_price,
                            "freight": qi.freight_share or q.freight_amount,
                            "discount": qi.discount_amount,
                            "total": qi.total_amount,
                            "delivery_days": qi.delivery_days or q.delivery_days,
                            "payment_term": q.payment_term_text,
                            "valid_until": q.valid_until,
                            "notes": qi.notes or q.notes,
                        },
                    )
        best_price = min((o["unit_price"] for o in offers), default=None)
        best_total = min((o["total"] for o in offers), default=None)
        best_days = min((o["delivery_days"] for o in offers), default=None)
        rows.append(
            {
                "request_item": req_item,
                "offers": offers,
                "best_price": best_price,
                "best_total": best_total,
                "best_days": best_days,
                "preferred_supplier_id": req_item.preferred_supplier_id,
            },
        )
    return {
        "quotations": quotations,
        "rows": rows,
        "lowest_total_quotation_id": (
            min(quotations, key=lambda q: q.total_amount).id if quotations else None
        ),
    }


def quotation_totals_by_supplier(purchase_request):
    return (
        purchase_request.quotations.exclude(status=QuotationStatus.CANCELLED)
        .values("supplier_id", "supplier__name")
        .annotate(total=Sum("total_amount"))
        .order_by("total")
    )
