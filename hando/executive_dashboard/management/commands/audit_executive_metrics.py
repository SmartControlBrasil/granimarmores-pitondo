from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models import Q

from after_sales.models import AfterSalesCase
from after_sales.models import CaseStatus
from after_sales.models import ConsentStatus
from after_sales.models import PendingStatus
from commercial.lead_models import Lead
from commercial.lead_models import LeadStatus
from commercial.performance_definitions import CLOSED_SALE_QUOTE_STATUS
from production.models import InstallationSchedule
from production.models import ProductionOrder
from production.models import ProductionOrderStatus
from production.models import ProductionPieceStatus
from production.models import SalesOrder
from production.models import SalesOrderStatus
from production.models import ScheduleStatus
from quotes.models import Quote
from quotes.models import QuoteStatus


class Command(BaseCommand):
    help = "Audita inconsistências que afetam métricas do painel executivo (somente leitura)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--start", type=str, default="")
        parser.add_argument("--end", type=str, default="")
        parser.add_argument(
            "--domain",
            type=str,
            default="all",
            help="all|commercial|production|stock|after_sales|media",
        )

    def handle(self, *args, **options):
        domain = options["domain"]
        findings = []

        if domain in {"all", "commercial"}:
            accepted = Quote.objects.filter(status=CLOSED_SALE_QUOTE_STATUS)
            no_order = accepted.annotate(oc=Count("sales_orders")).filter(oc=0)
            findings.append(("Vendas aceitas sem pedido", no_order.count()))

            orders_bad_quote = SalesOrder.objects.exclude(
                quote__status__in=[QuoteStatus.ACCEPTED, QuoteStatus.CONVERTED],
            ).exclude(status=SalesOrderStatus.CANCELLED)
            findings.append(("Pedidos sem orçamento aceito/convertido", orders_bad_quote.count()))

            won_total = Lead.objects.filter(status=LeadStatus.WON).count()
            won_with_accept = (
                Lead.objects.filter(
                    status=LeadStatus.WON,
                    quotes__status__in=[QuoteStatus.ACCEPTED, QuoteStatus.CONVERTED],
                )
                .distinct()
                .count()
            )
            findings.append(("Leads ganhos sem aceite", max(won_total - won_with_accept, 0)))

        if domain in {"all", "production"}:
            completed = ProductionOrder.objects.filter(status=ProductionOrderStatus.COMPLETED)
            incomplete_pieces = completed.filter(
                pieces__status__in=[
                    ProductionPieceStatus.PENDING,
                    ProductionPieceStatus.IN_PROGRESS,
                    ProductionPieceStatus.REWORK,
                ],
            ).distinct()
            findings.append(("Ordens concluídas com peças incompletas", incomplete_pieces.count()))

            bad_install = InstallationSchedule.objects.filter(
                status=ScheduleStatus.COMPLETED,
            ).exclude(
                sales_order__status__in=[
                    SalesOrderStatus.INSTALLED,
                    SalesOrderStatus.COMPLETED,
                    SalesOrderStatus.DELIVERED,
                ],
            )
            findings.append(("Instalação concluída com pedido incompleto", bad_install.count()))

        if domain in {"all", "stock"}:
            from materials.models import MaterialSlab

            negative = MaterialSlab.objects.filter(
                Q(available_area__lt=0) | Q(reserved_area__lt=0) | Q(consumed_area__lt=0),
            )
            findings.append(("Chapas com área negativa", negative.count()))

        if domain in {"all", "after_sales"}:
            closed_open_pending = (
                AfterSalesCase.objects.filter(
                    status__in=[CaseStatus.CLOSED, CaseStatus.RESOLVED],
                )
                .filter(
                    sales_order__installation_pending_items__status__in=[
                        PendingStatus.OPEN,
                        PendingStatus.SCHEDULED,
                    ],
                )
                .distinct()
            )
            findings.append(("Casos fechados/resolvidos com pendência aberta", closed_open_pending.count()))

        if domain in {"all", "media"}:
            try:
                from media_library.models import MediaAsset
                from media_library.models import MediaVisibility

                public_no_consent = (
                    MediaAsset.objects.filter(visibility=MediaVisibility.PUBLIC)
                    .exclude(consent__consent_status=ConsentStatus.GRANTED)
                    .count()
                )
            except Exception:
                public_no_consent = 0
            findings.append(("Mídia pública sem consentimento válido", public_no_consent))

        self.stdout.write(self.style.NOTICE("Auditoria de métricas executivas (dry-run)"))
        for label, count in findings:
            style = self.style.WARNING if count else self.style.SUCCESS
            self.stdout.write(style(f"- {label}: {count}"))
        self.stdout.write(self.style.SUCCESS("Concluído. Nenhuma correção automática aplicada."))
