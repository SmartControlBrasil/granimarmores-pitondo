from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from production.models import DeliverySchedule
from production.models import InstallationSchedule
from scheduling.models import OperationalEvent
from scheduling.services.events import sync_event_from_delivery
from scheduling.services.events import sync_event_from_installation

User = get_user_model()


class Command(BaseCommand):
    help = "Sincroniza DeliverySchedule/InstallationSchedule com OperationalEvent."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--user", type=int, help="ID do usuário ator da sincronização")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        actor = None
        if options.get("user"):
            actor = User.objects.filter(pk=options["user"]).first()
        if actor is None:
            actor = User.objects.filter(is_superuser=True).first() or User.objects.filter(
                is_active=True,
            ).first()
        if actor is None:
            self.stderr.write("Nenhum usuário disponível para sincronização.")
            return

        created = skipped = 0
        for delivery in DeliverySchedule.objects.all():
            if OperationalEvent.objects.filter(delivery_schedule=delivery).exists():
                skipped += 1
                continue
            if dry_run:
                self.stdout.write(f"[dry-run] Criaria evento para entrega #{delivery.pk}")
                created += 1
                continue
            sync_event_from_delivery(delivery=delivery, actor=actor)
            created += 1

        for installation in InstallationSchedule.objects.all():
            if OperationalEvent.objects.filter(installation_schedule=installation).exists():
                skipped += 1
                continue
            if dry_run:
                self.stdout.write(f"[dry-run] Criaria evento para instalação #{installation.pk}")
                created += 1
                continue
            sync_event_from_installation(installation=installation, actor=actor)
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Sincronização: {created} criados/previstos, {skipped} já existentes.",
            ),
        )
