from django.db import transaction
from django.utils import timezone

from after_sales.models import AfterSalesCaseSequence
from after_sales.models import WarrantySequence


@transaction.atomic
def next_case_code(*, year=None):
    year = year or timezone.localdate().year
    seq, _ = AfterSalesCaseSequence.objects.select_for_update().get_or_create(
        year=year,
        defaults={"last_number": 0},
    )
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return f"POS-{year}-{seq.last_number:06d}"


@transaction.atomic
def next_warranty_number(*, year=None):
    year = year or timezone.localdate().year
    seq, _ = WarrantySequence.objects.select_for_update().get_or_create(
        year=year,
        defaults={"last_number": 0},
    )
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return f"GAR-{year}-{seq.last_number:06d}"
