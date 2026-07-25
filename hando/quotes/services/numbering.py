from django.db import transaction
from django.utils import timezone

from quotes.models import QuoteSequence


@transaction.atomic
def next_quote_number():
    year = timezone.localdate().year
    sequence, _ = QuoteSequence.objects.select_for_update().get_or_create(year=year)
    sequence.current += 1
    sequence.save(update_fields=["current"])
    return f"ORC-{year}-{sequence.current:06d}"
