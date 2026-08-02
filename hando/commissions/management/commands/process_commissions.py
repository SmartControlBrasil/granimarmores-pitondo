from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date

from commissions.models import CommissionEvent
from commissions.models import EventType
from commissions.services.provisioning import provision_commission
from commissions.services.provisioning import release_commission_for_receivable_payment
from finance.models import PaymentStatus
from finance.models import ReceivablePayment
from quotes.models import Quote
from quotes.models import QuoteStatus


class Command(BaseCommand):
    help = "Processa provisionamentos e liberações de comissão (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--start", type=str, default="")
        parser.add_argument("--end", type=str, default="")
        parser.add_argument("--salesperson", type=int, default=0)
        parser.add_argument("--partner", type=int, default=0)
        parser.add_argument("--event-type", type=str, default="")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        quotes = Quote.objects.filter(status=QuoteStatus.ACCEPTED).select_related(
            "salesperson",
            "partner",
        )
        if options["start"]:
            quotes = quotes.filter(accepted_at__date__gte=parse_date(options["start"]))
        if options["end"]:
            quotes = quotes.filter(accepted_at__date__lte=parse_date(options["end"]))
        if options["salesperson"]:
            quotes = quotes.filter(salesperson_id=options["salesperson"])
        if options["partner"]:
            quotes = quotes.filter(partner_id=options["partner"])

        self.stdout.write(f"Vendas elegíveis analisadas: {quotes.count()}")
        provisioned = 0
        released = 0
        actor = None
        if not dry:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            actor = (
                User.objects.filter(is_superuser=True).first()
                or User.objects.filter(is_staff=True).first()
                or User.objects.filter(is_active=True).first()
            )
            if not actor:
                self.stdout.write(self.style.ERROR("Nenhum usuário ator disponível."))
                return

        for quote in quotes.iterator():
            order = quote.sales_orders.exclude(status="cancelled").first()
            if dry:
                exists = CommissionEvent.objects.filter(
                    event_type=EventType.PROVISION,
                    quote=quote,
                ).exclude(status__in=["reversed", "cancelled"]).exists()
                if not exists:
                    provisioned += 1
                continue
            created = provision_commission(
                quote=quote,
                sales_order=order,
                actor=actor,
                trigger="quote_accepted",
            )
            provisioned += len(created)

        payments = ReceivablePayment.objects.filter(status=PaymentStatus.CONFIRMED)
        if options["start"]:
            payments = payments.filter(payment_date__gte=parse_date(options["start"]))
        if options["end"]:
            payments = payments.filter(payment_date__lte=parse_date(options["end"]))

        for payment in payments.select_related("installment__receivable").iterator():
            if dry:
                exists = CommissionEvent.objects.filter(
                    event_type=EventType.RELEASE,
                    receivable_payment=payment,
                ).exclude(status__in=["reversed", "cancelled"]).exists()
                if not exists and payment.installment.receivable.quote_id:
                    released += 1
                continue
            created = release_commission_for_receivable_payment(payment=payment, actor=actor)
            released += len(created)

        prefix = "Dry-run: " if dry else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}provisionamentos={provisioned} liberações={released}",
            ),
        )
