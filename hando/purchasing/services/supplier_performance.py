from decimal import Decimal

from django.db.models import Avg
from django.db.models import Count
from django.db.models import Sum
from django.utils import timezone

from purchasing.models import PurchaseOrder
from purchasing.models import PurchaseOrderStatus
from purchasing.models import PurchaseReceipt
from purchasing.models import PurchaseReceiptDivergence
from purchasing.models import PurchaseReturn
from purchasing.models import ReceiptStatus
from purchasing.models import SupplierQuotation


def supplier_performance(*, supplier, start=None, end=None):
    orders = PurchaseOrder.objects.filter(supplier=supplier).exclude(
        status__in=[PurchaseOrderStatus.CANCELLED, PurchaseOrderStatus.REJECTED],
    )
    receipts = PurchaseReceipt.objects.filter(purchase_order__supplier=supplier)
    divergences = PurchaseReceiptDivergence.objects.filter(receipt__purchase_order__supplier=supplier)
    returns = PurchaseReturn.objects.filter(supplier=supplier)
    quotations = SupplierQuotation.objects.filter(supplier=supplier)

    if start:
        orders = orders.filter(order_date__gte=start)
        receipts = receipts.filter(received_at__date__gte=start)
        divergences = divergences.filter(created_at__date__gte=start)
        returns = returns.filter(return_date__gte=start)
        quotations = quotations.filter(quotation_date__gte=start)
    if end:
        orders = orders.filter(order_date__lte=end)
        receipts = receipts.filter(received_at__date__lte=end)
        divergences = divergences.filter(created_at__date__lte=end)
        returns = returns.filter(return_date__lte=end)
        quotations = quotations.filter(quotation_date__lte=end)

    order_count = orders.count()
    purchased = orders.aggregate(v=Sum("total_amount"))["v"] or Decimal("0")
    avg_promised = quotations.aggregate(v=Avg("delivery_days"))["v"] or 0

    delayed = 0
    on_time = 0
    delay_days_total = 0
    today = timezone.localdate()
    for po in orders.exclude(expected_delivery_date=None):
        last_receipt = (
            po.receipts.filter(
                status__in=[ReceiptStatus.ACCEPTED, ReceiptStatus.ACCEPTED_WITH_DIVERGENCE],
            )
            .order_by("-received_at")
            .first()
        )
        if last_receipt:
            delta = (last_receipt.received_at.date() - po.expected_delivery_date).days
            if delta > 0:
                delayed += 1
                delay_days_total += delta
            else:
                on_time += 1
        elif po.expected_delivery_date < today and po.status not in {
            PurchaseOrderStatus.RECEIVED,
            PurchaseOrderStatus.CLOSED,
        }:
            delayed += 1

    complete_receipts = receipts.filter(status=ReceiptStatus.ACCEPTED).count()
    rejected_receipts = receipts.filter(status=ReceiptStatus.REJECTED).count()
    div_count = divergences.count()
    ret_count = returns.count()
    delivered = on_time + delayed
    on_time_pct = (Decimal(on_time) / Decimal(delivered) * 100) if delivered else Decimal("0")
    conforming = complete_receipts
    inspected = receipts.exclude(status__in=[ReceiptStatus.DRAFT, ReceiptStatus.CANCELLED]).count()
    conformity_pct = (Decimal(conforming) / Decimal(inspected) * 100) if inspected else Decimal("0")

    materials = (
        orders.values("items__material__name")
        .annotate(total=Count("items__id"))
        .order_by("-total")[:10]
    )

    return {
        "orders": order_count,
        "purchased_amount": purchased,
        "avg_promised_days": avg_promised,
        "avg_delay_days": (Decimal(delay_days_total) / Decimal(delayed)) if delayed else Decimal("0"),
        "complete_receipts": complete_receipts,
        "divergences": div_count,
        "rejected_receipts": rejected_receipts,
        "returns": ret_count,
        "on_time_percent": on_time_pct.quantize(Decimal("0.01")),
        "conformity_percent": conformity_pct.quantize(Decimal("0.01")),
        "materials": list(materials),
    }
