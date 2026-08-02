from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models import F
from django.db.models import Sum

from finance.models import AccountsReceivable
from finance.models import FinancialMovement
from finance.models import PayablePayment
from finance.models import PaymentStatus
from finance.models import ReceivablePayment
from finance.models import TitleStatus


class Command(BaseCommand):
    help = "Audita inconsistências financeiras (somente leitura)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--start", type=str, default="")
        parser.add_argument("--end", type=str, default="")
        parser.add_argument("--type", type=str, default="all")

    def handle(self, *args, **options):
        findings = []
        paid_with_balance = AccountsReceivable.objects.filter(
            status=TitleStatus.PAID,
            outstanding_amount__gt=0,
        ).count()
        findings.append(("Títulos pagos com saldo", paid_with_balance))

        open_without_balance = AccountsReceivable.objects.filter(
            status__in=[TitleStatus.OPEN, TitleStatus.OVERDUE],
            outstanding_amount=0,
            paid_amount=0,
        ).count()
        findings.append(("Títulos abertos sem saldo/pagamento", open_without_balance))

        overpaid = ReceivablePayment.objects.filter(
            status=PaymentStatus.CONFIRMED,
            amount__gt=F("installment__original_amount"),
        ).count()
        findings.append(("Recebimentos acima do valor da parcela", overpaid))

        recv_no_mov = 0
        for p in ReceivablePayment.objects.filter(status=PaymentStatus.CONFIRMED)[:500]:
            if not FinancialMovement.objects.filter(source_receivable_payment=p).exists():
                recv_no_mov += 1
        findings.append(("Recebimentos sem movimento", recv_no_mov))

        pay_no_mov = 0
        for p in PayablePayment.objects.filter(status=PaymentStatus.CONFIRMED)[:500]:
            if not FinancialMovement.objects.filter(source_payable_payment=p).exists():
                pay_no_mov += 1
        findings.append(("Pagamentos sem movimento", pay_no_mov))

        dup_orders = (
            AccountsReceivable.objects.exclude(
                status__in=[TitleStatus.CANCELLED, TitleStatus.RENEGOTIATED, TitleStatus.WRITTEN_OFF],
            )
            .exclude(sales_order__isnull=True)
            .values("sales_order")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .count()
        )
        findings.append(("Pedidos com título duplicado ativo", dup_orders))

        self.stdout.write(self.style.NOTICE("Auditoria financeira (dry-run)"))
        for label, count in findings:
            style = self.style.WARNING if count else self.style.SUCCESS
            self.stdout.write(style(f"- {label}: {count}"))
        self.stdout.write(self.style.SUCCESS("Concluído. Nenhuma correção automática."))
