from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models import Sum
from django.utils import timezone

from commissions.models import CommissionEvent
from commissions.models import CommissionSettlement
from commissions.models import EventStatus
from commissions.models import EventType
from finance.models import AccountsPayable
from finance.models import PaymentStatus
from finance.models import ReceivablePayment


class Command(BaseCommand):
    help = "Audita consistência de comissões (somente relatório)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        issues = []
        for ev in CommissionEvent.objects.filter(event_type=EventType.PROVISION):
            if not ev.quote_id and not ev.sales_order_id:
                issues.append(f"Comissão {ev.number} sem venda")
            if not ev.policy_id and ev.event_type == EventType.PROVISION:
                issues.append(f"Comissão {ev.number} sem política")

        dups = (
            CommissionEvent.objects.exclude(status__in=["reversed", "cancelled"])
            .exclude(event_type__in=["reversal", "adjustment_positive", "adjustment_negative"])
            .values("event_type", "source_type", "source_id", "beneficiary_type", "salesperson_id")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
        )
        for d in dups[:20]:
            issues.append(f"Evento duplicado: {d}")

        for provision in CommissionEvent.objects.filter(event_type=EventType.PROVISION).exclude(
            status__in=["reversed", "cancelled"],
        ):
            released = (
                CommissionEvent.objects.filter(
                    event_type=EventType.RELEASE,
                    quote=provision.quote,
                    sales_order=provision.sales_order,
                    salesperson=provision.salesperson,
                    commercial_partner=provision.commercial_partner,
                )
                .exclude(status__in=["reversed", "cancelled"])
                .aggregate(v=Sum("commission_amount"))["v"]
                or 0
            )
            if released > provision.commission_amount:
                issues.append(f"Liberação acima do provisionado em {provision.number}")

        for s in CommissionSettlement.objects.exclude(status="cancelled"):
            if s.paid_amount > s.net_amount:
                issues.append(f"Pagamento acima do disponível em {s.number}")
            paid_events = CommissionEvent.objects.filter(
                event_type=EventType.PAYMENT,
                settlement=s,
            ).exclude(status="reversed")
            if paid_events.exists() and s.status == "draft":
                issues.append(f"Pagamento sem fechamento coerente em {s.number}")

        dup_payables = (
            AccountsPayable.objects.exclude(status="cancelled")
            .filter(reference_type="commission_settlement")
            .values("reference_id")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
        )
        for d in dup_payables:
            issues.append(f"AP duplicada para fechamento id={d['reference_id']}")

        for payment in ReceivablePayment.objects.filter(status=PaymentStatus.REVERSED):
            releases = CommissionEvent.objects.filter(
                event_type=EventType.RELEASE,
                receivable_payment=payment,
            ).exclude(status__in=[EventStatus.REVERSED, EventStatus.CANCELLED])
            if releases.exists():
                issues.append(
                    f"Recebimento estornado {payment.number} sem estorno de comissão",
                )

        self.stdout.write(f"Auditoria de comissões — {timezone.now():%Y-%m-%d %H:%M}")
        if options["dry_run"]:
            self.stdout.write("Dry-run: nenhuma correção automática.")
        if not issues:
            self.stdout.write(self.style.SUCCESS("Nenhuma inconsistência encontrada."))
        else:
            self.stdout.write(self.style.WARNING(f"{len(issues)} inconsistência(s):"))
            for issue in issues:
                self.stdout.write(f"- {issue}")
