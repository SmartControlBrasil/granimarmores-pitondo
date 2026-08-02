# ruff: noqa: PT009, S106
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import RolePermission
from access_control.models import UserAccess
from after_sales.models import AfterSalesCase
from after_sales.models import AfterSalesCaseHistory
from after_sales.models import CaseStatus
from after_sales.models import CaseType
from after_sales.models import ConsentStatus
from after_sales.models import CustomerReferral
from after_sales.models import CustomerSatisfactionSurvey
from after_sales.models import InstallationPendingItem
from after_sales.models import MediaUsageConsent
from after_sales.models import PendingStatus
from after_sales.models import ReferralStatus
from after_sales.models import Responsibility
from after_sales.models import ReviewRequest
from after_sales.models import RootCause
from after_sales.models import SurveyStatus
from after_sales.models import WarrantyEligibility
from after_sales.models import WarrantyRecord
from after_sales.models import WarrantyStatus
from after_sales.selectors import after_sales_dashboard_metrics
from after_sales.selectors import build_after_sales_alerts
from after_sales.selectors import cases_queryset_for_user
from after_sales.services.cases import add_diagnosis
from after_sales.services.cases import add_interaction
from after_sales.services.cases import assign_case
from after_sales.services.cases import cancel_case
from after_sales.services.cases import change_case_status
from after_sales.services.cases import close_after_sales_case
from after_sales.services.cases import link_rework
from after_sales.services.cases import open_after_sales_case
from after_sales.services.cases import reject_case
from after_sales.services.cases import reopen_case
from after_sales.services.cases import request_material
from after_sales.services.cases import resolve_after_sales_case
from after_sales.services.cases import schedule_case_visit
from after_sales.services.cases import start_case_work
from after_sales.services.cases import triage_case
from after_sales.services.follow_up import create_installation_pending
from after_sales.services.follow_up import resolve_installation_pending
from after_sales.services.numbering import next_case_code
from after_sales.services.satisfaction import convert_referral_to_lead
from after_sales.services.satisfaction import create_referral
from after_sales.services.satisfaction import create_review_request
from after_sales.services.satisfaction import create_satisfaction_survey
from after_sales.services.satisfaction import record_media_consent
from after_sales.services.satisfaction import register_survey_response
from after_sales.services.satisfaction import revoke_media_consent
from after_sales.services.warranties import create_warranty_record
from after_sales.services.warranties import decide_warranty_eligibility
from after_sales.services.warranties import evaluate_warranty_eligibility
from commercial.lead_models import Lead
from commercial.models import ChannelGroup
from commercial.models import CommercialSource
from customers.models import Customer
from production.models import InstallationSchedule
from production.models import SalesOrder
from quotes.models import Quote
from quotes.models import QuoteItem
from quotes.models import QuoteStatus
from commercial.performance_score import create_default_score_policy
from quotes.services.acceptance import accept_quote
from salespeople.models import Salesperson
from scheduling.models import EventType


User = get_user_model()


class AfterSalesMixin:
    _counter = 0

    def setUp(self):
        AfterSalesMixin._counter += 1
        n = AfterSalesMixin._counter
        self.role = AccessRole.objects.create(
            name="Administrativo",
            slug=f"admin-as-{n}",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
            quote_scope=DataScope.ALL,
        )
        self.user = User.objects.create_user(f"asadmin{n}", password="pass")
        UserAccess.objects.create(user=self.user, role=self.role)
        self.tech = User.objects.create_user(f"astech{n}", password="pass")
        UserAccess.objects.create(user=self.tech, role=self.role)
        create_default_score_policy(actor=self.user)
        self.salesperson = Salesperson.objects.create(
            code=f"AS{n}",
            display_name=f"Vendedor AS {n}",
            user=self.user,
        )
        self.customer = Customer.objects.create(
            customer_type="individual",
            name=f"Cliente AS {n}",
            assigned_salesperson=self.salesperson,
        )
        self.quote = Quote.objects.create(
            number=f"ORC-AS-{n:03d}",
            customer=self.customer,
            salesperson=self.salesperson,
            status=QuoteStatus.SENT,
            subtotal=Decimal("1000.00"),
            grand_total=Decimal("1000.00"),
            valid_until=timezone.localdate() + timedelta(days=10),
            created_by=self.user,
        )
        QuoteItem.objects.create(
            quote=self.quote,
            description="Bancada",
            quantity=Decimal("1"),
            unit_price=Decimal("1000.00"),
            subtotal=Decimal("1000.00"),
        )
        self.order = accept_quote(quote=self.quote, actor=self.user)
        self.installation = InstallationSchedule.objects.create(
            sales_order=self.order,
            scheduled_date=timezone.localdate(),
            address="Rua Teste 100",
            city="Criciúma",
            state="SC",
            created_by=self.user,
        )

    def _open_case(self, **kwargs):
        defaults = {
            "actor": self.user,
            "customer": self.customer,
            "sales_order": self.order,
            "subject": "Problema teste",
            "description": "Descrição do caso",
            "case_type": CaseType.TECHNICAL_ASSISTANCE,
        }
        defaults.update(kwargs)
        return open_after_sales_case(**defaults)


class AfterSalesCoreTests(AfterSalesMixin, TestCase):
    def test_open_and_numbering(self):
        case = self._open_case()
        self.assertTrue(case.code.startswith("POS-"))
        self.assertEqual(case.status, CaseStatus.NEW)
        self.assertTrue(AfterSalesCaseHistory.objects.filter(case=case, action="created").exists())
        c2 = self._open_case(subject="Segundo")
        self.assertNotEqual(case.code, c2.code)
        year = timezone.localdate().year
        self.assertEqual(next_case_code()[:9], f"POS-{year}-")

    def test_order_required(self):
        with self.assertRaises(ValidationError):
            open_after_sales_case(
                actor=self.user,
                customer=self.customer,
                subject="Sem pedido",
                description="x",
                case_type=CaseType.OTHER,
            )
        case = open_after_sales_case(
            actor=self.user,
            customer=self.customer,
            subject="Exceção",
            description="x",
            case_type=CaseType.OTHER,
            allow_without_order=True,
        )
        self.assertIsNone(case.sales_order_id)

    def test_triage_assign_status(self):
        case = self._open_case()
        triage_case(case=case, actor=self.user)
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.TRIAGE)
        assign_case(case=case, actor=self.user, assigned_user=self.tech)
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.ASSIGNED)
        change_case_status(case=case, actor=self.user, new_status=CaseStatus.AWAITING_CUSTOMER)
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.AWAITING_CUSTOMER)
        with self.assertRaises(ValidationError):
            change_case_status(case=case, actor=self.user, new_status=CaseStatus.CLOSED)

    def test_warranty_eligibility_paths(self):
        case = self._open_case(case_type=CaseType.MATERIAL_ISSUE)
        decision, _ = evaluate_warranty_eligibility(case=case, actor=self.user)
        self.assertEqual(decision, WarrantyEligibility.NOT_ELIGIBLE)
        warranty = create_warranty_record(
            actor=self.user,
            customer=self.customer,
            sales_order=self.order,
            start_date=timezone.localdate() - timedelta(days=10),
            end_date=timezone.localdate() + timedelta(days=100),
            coverage_type="material",
        )
        decision, _ = evaluate_warranty_eligibility(case=case, actor=self.user)
        self.assertEqual(decision, WarrantyEligibility.ELIGIBLE)
        warranty.end_date = timezone.localdate() - timedelta(days=1)
        warranty.save()
        decision, _ = evaluate_warranty_eligibility(case=case, actor=self.user)
        self.assertEqual(decision, WarrantyEligibility.NOT_ELIGIBLE)
        create_warranty_record(
            actor=self.user,
            customer=self.customer,
            sales_order=self.order,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=30),
            coverage_type="installation",
        )
        case.case_type = CaseType.MATERIAL_ISSUE
        case.save()
        decision, _ = evaluate_warranty_eligibility(case=case, actor=self.user)
        self.assertEqual(decision, WarrantyEligibility.MANUAL_REVIEW)
        decide_warranty_eligibility(
            case=case,
            actor=self.user,
            decision=WarrantyEligibility.ELIGIBLE,
            notes="Aprovado após análise",
            warranty=warranty,
        )
        case.refresh_from_db()
        self.assertEqual(case.warranty_eligible, WarrantyEligibility.ELIGIBLE)

    def test_diagnosis_resolve_close_reopen(self):
        case = self._open_case()
        assign_case(case=case, actor=self.user, assigned_user=self.tech)
        add_diagnosis(
            case=case,
            actor=self.user,
            technical_diagnosis="Falha de vedação",
            root_cause=RootCause.INSTALLATION_ERROR,
            responsibility=Responsibility.COMPANY,
        )
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.UNDER_ANALYSIS)
        with self.assertRaises(ValidationError):
            resolve_after_sales_case(case=case, actor=self.user, resolution="")
        resolve_after_sales_case(
            case=case,
            actor=self.user,
            resolution="Reaplicação de silicone",
            root_cause=RootCause.INSTALLATION_ERROR,
            responsibility=Responsibility.COMPANY,
            customer_notified=True,
        )
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.RESOLVED)
        with self.assertRaises(ValidationError):
            close_after_sales_case(case=self._open_case(subject="outro"), actor=self.user)
        close_after_sales_case(case=case, actor=self.user, closing_notes="Ok")
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.CLOSED)
        with self.assertRaises(ValidationError):
            close_after_sales_case(case=case, actor=self.user)
        reopen_case(case=case, actor=self.user, reason="Cliente retornou")
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.IN_PROGRESS)

    def test_reject_cancel_require_reason(self):
        case = self._open_case()
        with self.assertRaises(ValidationError):
            reject_case(case=case, actor=self.user, reason="")
        reject_case(case=case, actor=self.user, reason="Fora do escopo")
        case2 = self._open_case(subject="cancel")
        cancel_case(case=case2, actor=self.user, reason="Duplicado")
        case2.refresh_from_db()
        self.assertEqual(case2.status, CaseStatus.CANCELLED)

    def test_visit_event_and_interaction(self):
        case = self._open_case()
        start = timezone.now() + timedelta(hours=2)
        end = start + timedelta(hours=1)
        event = schedule_case_visit(
            case=case,
            actor=self.user,
            start_at=start,
            end_at=end,
            address="Rua Teste 100",
            city="Criciúma",
            state="SC",
        )
        self.assertEqual(event.event_type, EventType.TECHNICAL_ASSISTANCE)
        self.assertEqual(event.after_sales_case_id, case.pk)
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.VISIT_SCHEDULED)
        add_interaction(
            case=case,
            actor=self.user,
            interaction_type="phone",
            description="Cliente contatado",
        )
        case.refresh_from_db()
        self.assertIsNotNone(case.first_response_at)

    def test_pending_rework_material(self):
        item, case = create_installation_pending(
            actor=self.user,
            installation_schedule=self.installation,
            description="Ajuste de rodabanca",
            create_case=True,
        )
        self.assertEqual(item.status, PendingStatus.OPEN)
        self.assertIsNotNone(case)
        with self.assertRaises(ValidationError):
            create_installation_pending(
                actor=self.user,
                installation_schedule=self.installation,
                description="Ajuste de rodabanca",
            )
        resolve_installation_pending(item=item, actor=self.user, resolution="Corrigido")
        item.refresh_from_db()
        self.assertEqual(item.status, PendingStatus.RESOLVED)
        case2 = self._open_case(subject="rework")
        link_rework(case=case2, actor=self.user, notes="Retrabalho pós-venda")
        case2.refresh_from_db()
        self.assertEqual(case2.rework_origin, "after_sales")
        request_material(case=case2, actor=self.user, notes="Silicone e chapa sobra")
        case2.refresh_from_db()
        self.assertEqual(case2.status, CaseStatus.AWAITING_MATERIAL)

    def test_satisfaction_review_consent_referral(self):
        survey = create_satisfaction_survey(
            actor=self.user,
            customer=self.customer,
            sales_order=self.order,
            survey_type="post_installation",
        )
        with self.assertRaises(ValidationError):
            register_survey_response(survey=survey, actor=self.user, overall_score=9)
        register_survey_response(
            survey=survey,
            actor=self.user,
            overall_score=5,
            would_recommend=True,
        )
        survey.refresh_from_db()
        self.assertEqual(survey.status, SurveyStatus.RESPONDED)
        review = create_review_request(
            actor=self.user,
            customer=self.customer,
            sales_order=self.order,
            channel="whatsapp",
        )
        self.assertEqual(review.status, "requested")
        consent = record_media_consent(
            actor=self.user,
            customer=self.customer,
            sales_order=self.order,
            consent_status=ConsentStatus.GRANTED,
            consent_scope="portfolio",
            authorized_by_name="Cliente",
        )
        revoke_media_consent(consent=consent, actor=self.user, notes="Revogado")
        consent.refresh_from_db()
        self.assertEqual(consent.consent_status, ConsentStatus.REVOKED)
        CommercialSource.objects.get_or_create(
            slug="indicacao",
            defaults={
                "name": "Indicação",
                "channel_group": ChannelGroup.REFERRAL,
                "is_active": True,
            },
        )
        referral = create_referral(
            actor=self.user,
            referring_customer=self.customer,
            sales_order=self.order,
            referred_name="Indicado Teste",
            referred_phone="48999990000",
        )
        lead = convert_referral_to_lead(referral=referral, actor=self.user)
        self.assertTrue(lead.code.startswith("LEAD-"))
        referral.refresh_from_db()
        self.assertEqual(referral.status, ReferralStatus.CONVERTED)
        with self.assertRaises(ValidationError):
            convert_referral_to_lead(referral=referral, actor=self.user)

    def test_scope_rbac_dashboard_alerts(self):
        case = self._open_case(severity="critical")
        qs = cases_queryset_for_user(self.user)
        self.assertTrue(qs.filter(pk=case.pk).exists())
        metrics = after_sales_dashboard_metrics(user=self.user)
        self.assertGreaterEqual(metrics["open_cases"], 1)
        self.assertGreaterEqual(metrics["resolution_rate"], Decimal("0.0"))
        alerts = build_after_sales_alerts(self.user)
        self.assertIsInstance(alerts, list)
        client = Client()
        client.force_login(self.user)
        resp = client.get(reverse("after_sales:dashboard"))
        self.assertEqual(resp.status_code, 200)
        resp = client.get(reverse("after_sales:case_list"))
        self.assertEqual(resp.status_code, 200)

    def test_no_delete_case_and_audit_command(self):
        case = self._open_case()
        with self.assertRaises(ValidationError):
            case.delete()
        out = StringIO()
        call_command("audit_after_sales", stdout=out)
        text = out.getvalue()
        self.assertTrue("Auditoria" in text or "Nenhuma inconsistência" in text)

    def test_seed_permissions_present(self):
        from access_control.permissions import PERMISSIONS

        codes = {p[0] for p in PERMISSIONS}
        self.assertIn("after_sales_cases.view", codes)
        self.assertIn("warranties.decide", codes)
        self.assertIn("after_sales_dashboard.view", codes)

    def test_crm_compatibility_referral_origin(self):
        CommercialSource.objects.get_or_create(
            slug="indicacao",
            defaults={"name": "Indicação", "channel_group": ChannelGroup.REFERRAL, "is_active": True},
        )
        referral = create_referral(
            actor=self.user,
            referring_customer=self.customer,
            referred_name="Lead CRM",
            referred_phone="48988887777",
        )
        lead = convert_referral_to_lead(referral=referral, actor=self.user)
        self.assertIsInstance(lead, Lead)
        self.assertTrue(
            lead.commercial_source_id is None
            or lead.commercial_source.channel_group == ChannelGroup.REFERRAL
            or lead.commercial_source.slug == "indicacao",
        )

    def test_close_blocked_by_active_event(self):
        case = self._open_case()
        assign_case(case=case, actor=self.user, assigned_user=self.tech)
        add_diagnosis(
            case=case,
            actor=self.user,
            technical_diagnosis="ok",
            root_cause=RootCause.NOT_IDENTIFIED,
            responsibility=Responsibility.UNDETERMINED,
        )
        resolve_after_sales_case(
            case=case,
            actor=self.user,
            resolution="feito",
            root_cause=RootCause.NOT_IDENTIFIED,
            responsibility=Responsibility.UNDETERMINED,
        )
        start = timezone.now() + timedelta(hours=3)
        schedule_case_visit(
            case=case,
            actor=self.user,
            start_at=start,
            end_at=start + timedelta(hours=1),
            address="Rua X",
            city="Criciúma",
            state="SC",
        )
        case.status = CaseStatus.RESOLVED
        case.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            close_after_sales_case(case=case, actor=self.user)

    def test_start_work(self):
        case = self._open_case()
        start_case_work(case=case, actor=self.user)
        case.refresh_from_db()
        self.assertEqual(case.status, CaseStatus.IN_PROGRESS)

    def test_empty_dashboard_no_div_zero(self):
        metrics = after_sales_dashboard_metrics(user=self.user)
        self.assertEqual(metrics["avg_first_response_hours"], 0)
        self.assertEqual(metrics["resolution_rate"], Decimal("0.0"))
