from django.core.management.base import BaseCommand
from django.utils import timezone

from production.selectors import overdue_production_orders
from production.selectors import overdue_sales_orders


class Command(BaseCommand):
    help = "Identifica pedidos e ordens de produção atrasadas."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        today = timezone.localdate()
        orders = list(overdue_sales_orders(today=today))
        productions = list(overdue_production_orders(today=today))
        self.stdout.write(f"Data de referência: {today}")
        self.stdout.write(f"Pedidos atrasados: {len(orders)}")
        for order in orders[:20]:
            self.stdout.write(f"  - {order.number} (prazo {order.promised_date})")
        self.stdout.write(f"Ordens atrasadas: {len(productions)}")
        for production in productions[:20]:
            self.stdout.write(
                f"  - {production.number} (fim planejado {production.planned_end_date})",
            )
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry-run: nenhuma alteração persistida."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Atrasos calculados em tempo real (sem flags persistidas).",
                ),
            )
