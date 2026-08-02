from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from scheduling.models import ACTIVE_CONFLICT_STATUSES
from scheduling.models import ADDRESS_REQUIRED_TYPES
from scheduling.models import EventStatus
from scheduling.models import OperationalEvent
from scheduling.services.conflicts import check_schedule_conflicts


class Command(BaseCommand):
    help = "Audita inconsistências da agenda operacional."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--start")
        parser.add_argument("--end")
        parser.add_argument("--responsible", type=int)
        parser.add_argument("--vehicle", type=int)

    def handle(self, *args, **options):
        qs = OperationalEvent.objects.all()
        if options["start"]:
            qs = qs.filter(start_at__gte=parse_datetime(options["start"]))
        if options["end"]:
            qs = qs.filter(start_at__lte=parse_datetime(options["end"]))
        if options["responsible"]:
            qs = qs.filter(assigned_user_id=options["responsible"])
        if options["vehicle"]:
            qs = qs.filter(vehicle_id=options["vehicle"])

        issues = []
        for event in qs.iterator():
            if not event.assigned_user_id and not event.assigned_salesperson_id:
                issues.append(f"{event.code}: sem responsável")
            if event.event_type in ADDRESS_REQUIRED_TYPES and (
                not event.address or not event.city
            ):
                issues.append(f"{event.code}: sem endereço")
            if event.is_overdue:
                issues.append(f"{event.code}: atrasado")
            if event.status == EventStatus.CANCELLED and not event.cancel_reason:
                issues.append(f"{event.code}: cancelado sem motivo")
            if event.delivery_schedule_id:
                delivery = event.delivery_schedule
                if delivery.scheduled_date != event.start_at.date():
                    issues.append(f"{event.code}: entrega divergente da data do evento")
            if event.installation_schedule_id:
                installation = event.installation_schedule
                if installation.scheduled_date != event.start_at.date():
                    issues.append(f"{event.code}: instalação divergente da data do evento")

            if event.status in ACTIVE_CONFLICT_STATUSES:
                conflicts = check_schedule_conflicts(
                    start_at=event.start_at,
                    end_at=event.end_at,
                    assigned_user=event.assigned_user,
                    assigned_salesperson=event.assigned_salesperson,
                    vehicle=event.vehicle,
                    exclude_event=event,
                    all_day=event.all_day,
                )
                for item in conflicts:
                    if item["event"].pk > event.pk:
                        issues.append(f"{event.code} x {item['event'].code}: conflito")

        if not issues:
            self.stdout.write(self.style.SUCCESS("Nenhuma inconsistência encontrada."))
            return
        for issue in issues:
            self.stdout.write(self.style.WARNING(issue))
        self.stdout.write(f"Total: {len(issues)} (dry-run; sem correção automática).")
