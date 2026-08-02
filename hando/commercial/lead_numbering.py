from django.db import transaction
from django.utils import timezone

from commercial.lead_models import LeadSequence


@transaction.atomic
def next_lead_code():
    year = timezone.localdate().year
    sequence, _ = LeadSequence.objects.select_for_update().get_or_create(year=year)
    sequence.current += 1
    sequence.save(update_fields=["current"])
    return f"LEAD-{year}-{sequence.current:06d}"
