from datetime import datetime
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_date

from commercial.performance_score_processor import process_penalties
from salespeople.models import Salesperson


class Command(BaseCommand):
    help = "Processa penalidades comerciais de forma idempotente."

    def add_arguments(self, parser):
        parser.add_argument("--start", dest="start", default=None)
        parser.add_argument("--end", dest="end", default=None)
        parser.add_argument("--salesperson", dest="salesperson_id", default=None, type=int)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        start = self._parse_dt(options.get("start"), end_of_day=False)
        end = self._parse_dt(options.get("end"), end_of_day=True) or timezone.now()
        if not start:
            start = end - timedelta(days=30)

        salesperson = None
        sp_id = options.get("salesperson_id")
        if sp_id:
            salesperson = Salesperson.objects.filter(pk=sp_id).first()
            if not salesperson:
                self.stderr.write(self.style.ERROR("Vendedor não encontrado."))
                return

        result = process_penalties(
            start=start,
            end=end,
            salesperson=salesperson,
            dry_run=options.get("dry_run"),
        )
        mode = "DRY-RUN" if options.get("dry_run") else "EXECUTADO"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: {result['created']} eventos, {result['skipped']} ignorados.",
            ),
        )
        for line in result["details"][:50]:
            self.stdout.write(f"  - {line}")

    def _parse_dt(self, value, *, end_of_day):
        if not value:
            return None
        parsed = parse_date(value)
        if not parsed:
            return None
        dt = datetime.combine(parsed, datetime.max.time() if end_of_day else datetime.min.time())
        return timezone.make_aware(dt)
