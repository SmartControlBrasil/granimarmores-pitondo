from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_date

from finance.models import AccountsPayable
from purchasing.models import PurchaseOrder
from purchasing.models import PurchaseOrderItem
from purchasing.models import PurchaseReceipt
from purchasing.models import PurchaseReceiptDivergence
from purchasing.models import PurchaseReceiptSlab
from purchasing.models import PurchaseReturnItem
from purchasing.models import ReceiptStatus


class Command(BaseCommand):
    help = "Audita consistência operacional do módulo de compras (somente relatório)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--start", type=str, default="")
        parser.add_argument("--end", type=str, default="")
        parser.add_argument("--supplier", type=int, default=0)
        parser.add_argument("--status", type=str, default="")

    def handle(self, *args, **options):
        issues = []
        orders = PurchaseOrder.objects.all()
        if options["start"]:
            orders = orders.filter(order_date__gte=parse_date(options["start"]))
        if options["end"]:
            orders = orders.filter(order_date__lte=parse_date(options["end"]))
        if options["supplier"]:
            orders = orders.filter(supplier_id=options["supplier"])
        if options["status"]:
            orders = orders.filter(status=options["status"])

        for po in orders.iterator():
            if not po.supplier_id:
                issues.append(f"Pedido {po.number} sem fornecedor")
            if not po.purchase_request_id:
                issues.append(f"Pedido {po.number} sem solicitação")

        for item in PurchaseOrderItem.objects.select_related("purchase_order"):
            if item.received_quantity > item.ordered_quantity + item.cancelled_quantity:
                issues.append(
                    f"Item {item.pk} do pedido {item.purchase_order.number} recebeu acima do pedido",
                )

        for receipt in PurchaseReceipt.objects.filter(
            status__in=[ReceiptStatus.ACCEPTED, ReceiptStatus.ACCEPTED_WITH_DIVERGENCE],
        ):
            for ri in receipt.items.filter(stock_entered=True):
                if ri.purchase_order_item.item_type == "slab" and not ri.slabs.exists():
                    issues.append(
                        f"Recebimento {receipt.number} item {ri.pk} marcado com estoque sem chapa",
                    )

        for link in PurchaseReceiptSlab.objects.select_related("slab", "receipt_item__receipt"):
            if not link.slab_id:
                issues.append(f"Vínculo de chapa inválido id={link.pk}")

        for po in orders.filter(status="received", payable__isnull=True):
            issues.append(f"Pedido {po.number} recebido sem conta a pagar")

        dupes = (
            AccountsPayable.objects.exclude(status="cancelled")
            .filter(reference_type="purchase_order")
            .values("reference_id")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
        )
        for d in dupes:
            issues.append(f"Conta a pagar duplicada para pedido id={d['reference_id']}")

        for div in PurchaseReceiptDivergence.objects.filter(status="open"):
            if div.receipt.purchase_order.status == "closed":
                issues.append(
                    f"Divergência aberta {div.pk} em pedido fechado {div.receipt.purchase_order.number}",
                )

        for ri in PurchaseReturnItem.objects.filter(slab__isnull=False, stock_exited=False):
            issues.append(f"Devolução item {ri.pk} com chapa sem saída de estoque")

        self.stdout.write(f"Auditoria compras — {timezone.now():%Y-%m-%d %H:%M}")
        self.stdout.write(f"Pedidos analisados: {orders.count()}")
        if options["dry_run"]:
            self.stdout.write("Dry-run: nenhuma correção automática (política do comando).")
        if not issues:
            self.stdout.write(self.style.SUCCESS("Nenhuma inconsistência encontrada."))
        else:
            self.stdout.write(self.style.WARNING(f"{len(issues)} inconsistência(s):"))
            for issue in issues:
                self.stdout.write(f"- {issue}")
