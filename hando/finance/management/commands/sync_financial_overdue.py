from django.core.management.base import BaseCommand
from django.utils import timezone

from finance.models import InstallmentStatus
from finance.models import PayableInstallment
from finance.models import ReceivableInstallment
from finance.models import TERMINAL_INSTALLMENT_STATUSES
from finance.models import TitleStatus
from finance.services.balances import recalculate_title_from_installments


class Command(BaseCommand):
    help = "Sincroniza status operacional de parcelas vencidas (sem cobrança)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **options):
        dry = options["dry_run"]
        today = timezone.localdate()
        recv = ReceivableInstallment.objects.filter(
            due_date__lt=today,
            outstanding_amount__gt=0,
        ).exclude(status__in=TERMINAL_INSTALLMENT_STATUSES | {InstallmentStatus.OVERDUE})
        pay = PayableInstallment.objects.filter(
            due_date__lt=today,
            outstanding_amount__gt=0,
        ).exclude(status__in=TERMINAL_INSTALLMENT_STATUSES | {InstallmentStatus.OVERDUE})

        self.stdout.write(f"Parcelas a receber a marcar vencidas: {recv.count()}")
        self.stdout.write(f"Parcelas a pagar a marcar vencidas: {pay.count()}")
        if dry:
            self.stdout.write(self.style.WARNING("Dry-run: nenhuma alteração."))
            return

        titles = set()
        for inst in recv.iterator():
            inst.status = InstallmentStatus.OVERDUE
            inst.save(update_fields=["status", "updated_at"])
            titles.add(("r", inst.receivable_id))
        for inst in pay.iterator():
            inst.status = InstallmentStatus.OVERDUE
            inst.save(update_fields=["status", "updated_at"])
            titles.add(("p", inst.payable_id))

        from finance.models import AccountsPayable
        from finance.models import AccountsReceivable

        for kind, pk in titles:
            if kind == "r":
                title = AccountsReceivable.objects.get(pk=pk)
                if title.status not in {
                    TitleStatus.CANCELLED,
                    TitleStatus.RENEGOTIATED,
                    TitleStatus.WRITTEN_OFF,
                    TitleStatus.PAID,
                }:
                    recalculate_title_from_installments(title)
                    title.save(update_fields=["status", "paid_amount", "outstanding_amount", "updated_at"])
            else:
                title = AccountsPayable.objects.get(pk=pk)
                if title.status not in {
                    TitleStatus.CANCELLED,
                    TitleStatus.RENEGOTIATED,
                    TitleStatus.WRITTEN_OFF,
                    TitleStatus.PAID,
                }:
                    recalculate_title_from_installments(title)
                    title.save(update_fields=["status", "paid_amount", "outstanding_amount", "updated_at"])
        self.stdout.write(self.style.SUCCESS("Sincronização concluída."))
