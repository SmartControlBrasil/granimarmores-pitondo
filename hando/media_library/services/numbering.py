from django.db import transaction
from django.utils import timezone

from media_library.models import MediaAssetSequence
from media_library.models import MediaCollectionSequence


@transaction.atomic
def next_media_code(*, year=None):
    year = year or timezone.localdate().year
    seq, _ = MediaAssetSequence.objects.select_for_update().get_or_create(
        year=year,
        defaults={"last_number": 0},
    )
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return f"MID-{year}-{seq.last_number:06d}"


@transaction.atomic
def next_collection_code(*, year=None):
    year = year or timezone.localdate().year
    seq, _ = MediaCollectionSequence.objects.select_for_update().get_or_create(
        year=year,
        defaults={"last_number": 0},
    )
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return f"COL-{year}-{seq.last_number:06d}"
