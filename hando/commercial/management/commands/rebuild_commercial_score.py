from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_date

from commercial.lead_models import Lead
from commercial.lead_models import LeadStatus
from commercial.lead_models import LeadTask
from commercial.lead_models import LeadTaskStatus
from commercial.performance_models import ScoreEventType
from commercial.performance_score import record_score_event
from commercial.performance_score_hooks import score_first_contact
from commercial.performance_score_hooks import score_lead_created
from commercial.performance_score_hooks import score_lead_qualified
from commercial.performance_score_hooks import score_lead_won
from commercial.performance_score_hooks import score_quote_created
from commercial.performance_score_hooks import score_quote_sent
from commercial.performance_score_processor import process_penalties
from quotes.models import Quote
from quotes.models import QuoteStatus
from salespeople.models import Salesperson


class Command(BaseCommand):
    help = "Reconstrói eventos de score a partir de dados reais (requer período)."

    def add_arguments(self, parser):
        parser.add_argument("--start", required=True)
        parser.add_argument("--end", required=True)
        parser.add_argument("--salesperson", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Obrigatório para execução real (sem dry-run).",
        )

    def handle(self, *args, **options):
        start = self._parse_dt(options["start"], end_of_day=False)
        end = self._parse_dt(options["end"], end_of_day=True)
        if not start or not end:
            self.stderr.write(self.style.ERROR("Informe --start e --end válidos (YYYY-MM-DD)."))
            return

        dry_run = options.get("dry_run")
        if not dry_run and not options.get("confirm"):
            self.stderr.write(
                self.style.ERROR("Use --dry-run para diagnóstico ou --confirm para executar."),
            )
            return

        salesperson = None
        if options.get("salesperson"):
            salesperson = Salesperson.objects.filter(pk=options["salesperson"]).first()

        created = 0
        report = []

        lead_qs = Lead.objects.filter(
            created_at__gte=start,
            created_at__lte=end,
            assigned_salesperson__isnull=False,
        )
        if salesperson:
            lead_qs = lead_qs.filter(assigned_salesperson=salesperson)

        for lead in lead_qs.select_related("assigned_salesperson"):
            if dry_run:
                report.append(f"lead_created: {lead.code}")
                created += 1
            elif score_lead_created(lead=lead):
                created += 1
            if lead.first_contact_at and start <= lead.first_contact_at <= end:
                if dry_run:
                    report.append(f"first_contact: {lead.code}")
                    created += 1
                elif score_first_contact(lead=lead, occurred_at=lead.first_contact_at):
                    created += 1
            if lead.status == LeadStatus.QUALIFIED:
                if dry_run:
                    report.append(f"qualified: {lead.code}")
                    created += 1
                elif score_lead_qualified(lead=lead):
                    created += 1
            if lead.status == LeadStatus.WON and lead.won_at and start <= lead.won_at <= end:
                if dry_run:
                    report.append(f"won: {lead.code}")
                    created += 1
                elif score_lead_won(lead=lead):
                    created += 1

        quote_qs = Quote.objects.filter(
            salesperson__isnull=False,
            created_at__gte=start,
            created_at__lte=end,
        )
        if salesperson:
            quote_qs = quote_qs.filter(salesperson=salesperson)
        for quote in quote_qs.select_related("salesperson"):
            if dry_run:
                report.append(f"quote_created: {quote.number}")
                created += 1
            elif score_quote_created(quote=quote):
                created += 1
            if quote.sent_at and start <= quote.sent_at <= end:
                if dry_run:
                    report.append(f"quote_sent: {quote.number}")
                    created += 1
                elif score_quote_sent(quote=quote):
                    created += 1

        task_qs = LeadTask.objects.filter(
            status=LeadTaskStatus.COMPLETED,
            completed_at__gte=start,
            completed_at__lte=end,
            lead__assigned_salesperson__isnull=False,
        ).select_related("lead", "lead__assigned_salesperson")
        if salesperson:
            task_qs = task_qs.filter(lead__assigned_salesperson=salesperson)
        for task in task_qs:
            if task.completed_at and task.completed_at <= task.due_at:
                if dry_run:
                    report.append(f"follow_up: task {task.pk}")
                    created += 1
                else:
                    from commercial.performance_score_hooks import score_follow_up_completed

                    if score_follow_up_completed(task=task):
                        created += 1

        penalties = process_penalties(
            start=start,
            end=end,
            salesperson=salesperson,
            dry_run=dry_run,
        )
        created += penalties["created"]
        report.extend(penalties["details"])

        mode = "DRY-RUN" if dry_run else "REBUILD"
        self.stdout.write(self.style.SUCCESS(f"{mode}: {created} eventos processados/identificados."))
        for line in report[:100]:
            self.stdout.write(f"  - {line}")

    def _parse_dt(self, value, *, end_of_day):
        parsed = parse_date(value)
        if not parsed:
            return None
        dt = datetime.combine(parsed, datetime.max.time() if end_of_day else datetime.min.time())
        return timezone.make_aware(dt)
