from django.db import transaction
from django.utils import timezone

from purchasing.models import PurchasingSequence


@transaction.atomic
def next_purchasing_number(kind: str, prefix: str) -> str:
    year = timezone.localdate().year
    sequence, _ = PurchasingSequence.objects.select_for_update().get_or_create(
        kind=kind,
        year=year,
    )
    sequence.current += 1
    sequence.save(update_fields=["current"])
    return f"{prefix}-{year}-{sequence.current:06d}"


def next_request_number():
    return next_purchasing_number("purchase_request", "SC")


def next_quotation_number():
    return next_purchasing_number("supplier_quotation", "COT")


def next_purchase_order_number():
    return next_purchasing_number("purchase_order", "PC")


def next_receipt_number():
    return next_purchasing_number("purchase_receipt", "RCM")


def next_return_number():
    return next_purchasing_number("purchase_return", "DEV")
