from django.core.management.base import BaseCommand
from django.utils import timezone

from purchasing.models import PurchaseOrder
from purchasing.models import PurchaseOrderStatus


class Command(BaseCommand):
    help = "Identifica pedidos atrasados (status operacional; sem cobrança automática)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        today = timezone.localdate()
        qs = PurchaseOrder.objects.filter(expected_delivery_date__lt=today).exclude(
            status__in=[
                PurchaseOrderStatus.RECEIVED,
                PurchaseOrderStatus.CLOSED,
                PurchaseOrderStatus.CANCELLED,
                PurchaseOrderStatus.REJECTED,
            ],
        )
        self.stdout.write(f"Pedidos atrasados: {qs.count()}")
        for po in qs[:100]:
            self.stdout.write(
                f"- {po.number} previsão {po.expected_delivery_date} status={po.status}",
            )
        if options["dry_run"]:
            self.stdout.write("Dry-run: nenhum status alterado.")
        else:
            self.stdout.write("Nenhuma alteração automática aplicada nesta fase.")
