from django.db import transaction
from django.utils import timezone

from documents.models import DocumentSequence


@transaction.atomic
def next_document_number() -> str:
    year = timezone.localdate().year
    sequence, _ = DocumentSequence.objects.select_for_update().get_or_create(
        kind="document",
        year=year,
    )
    sequence.current += 1
    sequence.save(update_fields=["current"])
    return f"DOC-{year}-{sequence.current:06d}"
