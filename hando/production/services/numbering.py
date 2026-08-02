from django.db import transaction
from django.utils import timezone

from production.models import ProductionOrderSequence
from production.models import SalesOrderSequence


@transaction.atomic
def next_sales_order_number():
    year = timezone.localdate().year
    sequence, _ = SalesOrderSequence.objects.select_for_update().get_or_create(year=year)
    sequence.current += 1
    sequence.save(update_fields=["current"])
    return f"PED-{year}-{sequence.current:06d}"


@transaction.atomic
def next_production_order_number():
    year = timezone.localdate().year
    sequence, _ = ProductionOrderSequence.objects.select_for_update().get_or_create(year=year)
    sequence.current += 1
    sequence.save(update_fields=["current"])
    return f"OP-{year}-{sequence.current:06d}"
