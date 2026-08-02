from django.db import transaction
from django.utils import timezone

from commissions.models import CommissionSequence


@transaction.atomic
def next_commission_number(kind: str, prefix: str) -> str:
    year = timezone.localdate().year
    sequence, _ = CommissionSequence.objects.select_for_update().get_or_create(
        kind=kind,
        year=year,
    )
    sequence.current += 1
    sequence.save(update_fields=["current"])
    return f"{prefix}-{year}-{sequence.current:06d}"


def next_event_number():
    return next_commission_number("event", "COM")


def next_settlement_number():
    return next_commission_number("settlement", "FEC")


def next_payment_number():
    return next_commission_number("payment", "PCM")
