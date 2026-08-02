from django.db import transaction
from django.utils import timezone

from scheduling.models import OperationalEventSequence


@transaction.atomic
def next_event_code(*, year=None):
    year = year or timezone.localdate().year
    seq, _ = OperationalEventSequence.objects.select_for_update().get_or_create(
        year=year,
        defaults={"last_number": 0},
    )
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return f"AGE-{year}-{seq.last_number:06d}"
