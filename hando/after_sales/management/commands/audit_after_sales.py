from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from after_sales.models import AfterSalesCase
from after_sales.models import CaseStatus
from after_sales.models import ConsentStatus
from after_sales.models import CustomerReferral
from after_sales.models import CustomerSatisfactionSurvey
from after_sales.models import InstallationPendingItem
from after_sales.models import MediaUsageConsent
from after_sales.models import OPEN_CASE_STATUSES
from after_sales.models import PendingStatus
from after_sales.models import ReferralStatus
from after_sales.models import WarrantyRecord
from after_sales.models import WarrantyStatus
from scheduling.models import EventStatus
from scheduling.models import OperationalEvent


class Command(BaseCommand):
    help = "Audita inconsistências do módulo de pós-venda (somente relatório)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--start", type=str, default="")
        parser.add_argument("--end", type=str, default="")
        parser.add_argument("--status", type=str, default="")
        parser.add_argument("--responsible", type=int, default=0)

    def handle(self, *args, **options):
        qs = AfterSalesCase.objects.all()
        if options["start"]:
            qs = qs.filter(opened_at__date__gte=parse_date(options["start"]))
        if options["end"]:
            qs = qs.filter(opened_at__date__lte=parse_date(options["end"]))
        if options["status"]:
            qs = qs.filter(status=options["status"])
        if options["responsible"]:
            qs = qs.filter(assigned_user_id=options["responsible"])

        findings = []
        now = timezone.now()

        no_owner = qs.filter(
            status__in=OPEN_CASE_STATUSES,
            assigned_user__isnull=True,
            assigned_salesperson__isnull=True,
        ).count()
        if no_owner:
            findings.append(f"{no_owner} caso(s) sem responsável")

        overdue = qs.filter(next_action_at__lt=now).exclude(
            status__in=[CaseStatus.CLOSED, CaseStatus.CANCELLED, CaseStatus.REJECTED],
        ).count()
        if overdue:
            findings.append(f"{overdue} caso(s) com próxima ação vencida")

        resolved_open = qs.filter(status=CaseStatus.RESOLVED).count()
        if resolved_open:
            findings.append(f"{resolved_open} caso(s) resolvido(s) não fechado(s)")

        closed_with_pending = 0
        for case in qs.filter(status=CaseStatus.CLOSED).prefetch_related("pending_items")[:200]:
            if case.pending_items.filter(
                status__in=[PendingStatus.OPEN, PendingStatus.SCHEDULED, PendingStatus.IN_PROGRESS],
            ).exists():
                closed_with_pending += 1
        if closed_with_pending:
            findings.append(f"{closed_with_pending} caso(s) fechado(s) com pendência aberta")

        divergent_events = OperationalEvent.objects.filter(
            after_sales_case__isnull=False,
        ).exclude(
            status__in=[EventStatus.COMPLETED, EventStatus.CANCELLED, EventStatus.NO_SHOW],
        ).filter(
            after_sales_case__status__in=[CaseStatus.CLOSED, CaseStatus.CANCELLED],
        ).count()
        if divergent_events:
            findings.append(f"{divergent_events} evento(s) técnico(s) divergente(s) do caso")

        bad_warranties = WarrantyRecord.objects.filter(
            status=WarrantyStatus.ACTIVE,
            end_date__lt=timezone.localdate(),
        ).count()
        if bad_warranties:
            findings.append(f"{bad_warranties} garantia(s) ativa(s) com fim vencido")

        dup_surveys = (
            CustomerSatisfactionSurvey.objects.values("customer_id", "sales_order_id", "survey_type")
            .annotate(total=Count("id"))
            .filter(total__gt=1, sales_order_id__isnull=False)
            .count()
        )
        if dup_surveys:
            findings.append(f"{dup_surveys} grupo(s) de pesquisas potencialmente duplicadas")

        invalid_consents = MediaUsageConsent.objects.filter(
            Q(consent_status=ConsentStatus.GRANTED, authorized_at__isnull=True)
            | Q(consent_status=ConsentStatus.REVOKED, revoked_at__isnull=True),
        ).count()
        if invalid_consents:
            findings.append(f"{invalid_consents} consentimento(s) inconsistente(s)")

        converted_no_lead = CustomerReferral.objects.filter(
            status=ReferralStatus.CONVERTED,
            converted_lead__isnull=True,
        ).count()
        if converted_no_lead:
            findings.append(f"{converted_no_lead} indicação(ões) convertida(s) sem lead")

        overdue_pending = InstallationPendingItem.objects.filter(
            status__in=[PendingStatus.OPEN, PendingStatus.SCHEDULED],
            due_date__lt=timezone.localdate(),
        ).count()
        if overdue_pending:
            findings.append(f"{overdue_pending} pendência(s) de instalação vencida(s)")

        if not findings:
            self.stdout.write(self.style.SUCCESS("Nenhuma inconsistência encontrada."))
            return

        self.stdout.write(self.style.WARNING("Auditoria pós-venda (dry-run — sem correção):"))
        for item in findings:
            self.stdout.write(f" - {item}")
