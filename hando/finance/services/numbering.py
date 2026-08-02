from django.db import transaction
from django.utils import timezone

from finance.models import FinanceSequence


@transaction.atomic
def next_finance_number(kind: str, prefix: str) -> str:
    year = timezone.localdate().year
    sequence, _ = FinanceSequence.objects.select_for_update().get_or_create(
        kind=kind,
        year=year,
    )
    sequence.current += 1
    sequence.save(update_fields=["current"])
    return f"{prefix}-{year}-{sequence.current:06d}"


def next_receivable_number():
    return next_finance_number("receivable", "REC")


def next_receivable_payment_number():
    return next_finance_number("receivable_payment", "RCB")


def next_payable_number():
    return next_finance_number("payable", "PAG")


def next_payable_payment_number():
    return next_finance_number("payable_payment", "PGT")


def next_movement_number():
    return next_finance_number("movement", "MOV")
