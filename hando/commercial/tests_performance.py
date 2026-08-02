# ruff: noqa: PT009, S106
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import RolePermission
from access_control.models import UserAccess
from access_control.permissions import PERMISSIONS
from commercial.lead_conversion import create_lead
from commercial.lead_forms import LeadForm
from commercial.lead_models import LeadStatus
from commercial.lead_workflow import change_lead_status
from commercial.performance_forms import SalesGoalForm
from commercial.performance_forms import SalesScorePolicyForm
from commercial.performance_metrics import compute_goal_progress
from commercial.performance_metrics import compute_salesperson_metrics
from commercial.performance_metrics import safe_rate
from commercial.performance_models import GoalPeriodType
from commercial.performance_models import SalesGoal
from commercial.performance_models import SalesScoreEvent
from commercial.performance_models import SalesScorePolicy
from commercial.performance_models import ScoreEventType
from commercial.performance_ranking import build_ranking
from commercial.performance_score import create_default_score_policy
from commercial.performance_score import event_exists
from commercial.performance_score import get_active_score_policy
from commercial.performance_score import record_manual_score_adjustment
from commercial.performance_score import record_score_event
from commercial.performance_score_hooks import score_first_contact
from commercial.performance_score_processor import process_penalties
from salespeople.models import Salesperson

User = get_user_model()


PERF_PERMISSIONS = [
    "sales_goals.view",
    "sales_goals.create",
    "sales_goals.update",
    "sales_goals.deactivate",
    "sales_score_policy.view",
    "sales_score_policy.create",
    "sales_score_policy.update",
    "sales_score_events.view",
    "sales_score_events.adjust",
    "sales_performance.view_own",
    "sales_performance.view_all",
    "sales_ranking.view",
    "leads.view",
    "leads.create",
    "leads.change_status",
    "leads.mark_won",
    "leads.mark_lost",
]


class PerformanceTestMixin:
    @classmethod
    def setUpTestData(cls):
        call_command("setup_erp_foundation")
        cls.admin = User.objects.create_user(username="perfadmin", password="test")
        cls.seller_user = User.objects.create_user(username="seller1", password="test")
        cls.manager_user = User.objects.create_user(username="manager1", password="test")
        admin_role = AccessRole.objects.get(slug="administrativo")
        seller_role = AccessRole.objects.get(slug="vendedor")
        manager_role = AccessRole.objects.get(slug="gestor-comercial")
        UserAccess.objects.create(user=cls.admin, role=admin_role, is_active=True)
        UserAccess.objects.create(user=cls.seller_user, role=seller_role, is_active=True)
        UserAccess.objects.create(user=cls.manager_user, role=manager_role, is_active=True)
        cls.salesperson = Salesperson.objects.create(
            code="V001",
            display_name="Vendedor Teste",
            user=cls.seller_user,
            is_active=True,
        )
        cls.manager_sp = Salesperson.objects.create(
            code="V002",
            display_name="Gestor Teste",
            user=cls.manager_user,
            is_active=True,
        )
        for code in PERF_PERMISSIONS:
            perm = next(p for p in PERMISSIONS if p[0] == code)
            from access_control.models import AccessPermission

            permission, _ = AccessPermission.objects.get_or_create(
                code=code,
                defaults={"name": perm[1], "module": perm[2], "action": perm[3]},
            )
            RolePermission.objects.update_or_create(
                role=manager_role,
                permission=permission,
                defaults={"allowed": True},
            )
            if code in {"sales_performance.view_own", "sales_ranking.view", "sales_score_events.view"}:
                RolePermission.objects.update_or_create(
                    role=seller_role,
                    permission=permission,
                    defaults={"allowed": True},
                )


class SalesGoalTests(PerformanceTestMixin, TestCase):
    def test_create_goal(self):
        goal = SalesGoal.objects.create(
            salesperson=self.salesperson,
            period_type=GoalPeriodType.MONTHLY,
            start_date=timezone.localdate().replace(day=1),
            end_date=timezone.localdate(),
            lead_goal=10,
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.assertTrue(goal.is_active)

    def test_invalid_dates(self):
        form = SalesGoalForm(
            data={
                "salesperson": self.salesperson.pk,
                "period_type": GoalPeriodType.MONTHLY,
                "start_date": "2026-08-10",
                "end_date": "2026-08-01",
                "lead_goal": 1,
                "contact_goal": 0,
                "quote_goal": 0,
                "won_lead_goal": 0,
                "sales_value_goal": "0",
                "conversion_goal": 0,
                "response_time_goal_minutes": 0,
                "follow_up_compliance_goal": 0,
            },
        )
        self.assertFalse(form.is_valid())

    def test_duplicate_goal(self):
        start = timezone.localdate().replace(day=1)
        end = timezone.localdate()
        SalesGoal.objects.create(
            salesperson=self.salesperson,
            period_type=GoalPeriodType.MONTHLY,
            start_date=start,
            end_date=end,
            created_by=self.admin,
            updated_by=self.admin,
        )
        form = SalesGoalForm(
            data={
                "salesperson": self.salesperson.pk,
                "period_type": GoalPeriodType.MONTHLY,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "lead_goal": 5,
                "contact_goal": 0,
                "quote_goal": 0,
                "won_lead_goal": 0,
                "sales_value_goal": "0",
                "conversion_goal": 0,
                "response_time_goal_minutes": 0,
                "follow_up_compliance_goal": 0,
            },
        )
        self.assertFalse(form.is_valid())


class ScorePolicyTests(PerformanceTestMixin, TestCase):
    def test_default_policy_seed(self):
        policy, created = create_default_score_policy(actor=self.admin)
        policy2, created2 = create_default_score_policy(actor=self.admin)
        self.assertFalse(created2)
        self.assertEqual(policy.pk, policy2.pk)

    def test_active_policy(self):
        policy, _ = create_default_score_policy(actor=self.admin)
        self.assertTrue(get_active_score_policy())

    def test_overlap_validation(self):
        SalesScorePolicy.objects.update(is_active=False)
        today = timezone.localdate()
        SalesScorePolicy.objects.create(
            name="P1",
            valid_from=today,
            is_active=True,
            created_by=self.admin,
            updated_by=self.admin,
        )
        p2 = SalesScorePolicy(
            name="P2",
            valid_from=today,
            is_active=True,
            created_by=self.admin,
            updated_by=self.admin,
        )
        with self.assertRaises(ValidationError):
            p2.full_clean()


class ScoreEventTests(PerformanceTestMixin, TestCase):
    def setUp(self):
        create_default_score_policy(actor=self.admin)
        self.policy = get_active_score_policy()

    def _lead(self):
        form = LeadForm(
            data={
                "name": "Lead Score",
                "phone": "11988887777",
                "assigned_salesperson": self.salesperson.pk,
                "priority": "normal",
                "probability": 10,
                "estimated_value": "0",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        return create_lead(form=form, actor=self.admin)

    def test_first_contact_once(self):
        lead = self._lead()
        score_first_contact(lead=lead, actor=self.admin)
        score_first_contact(lead=lead, actor=self.admin)
        self.assertEqual(
            SalesScoreEvent.objects.filter(
                event_type=ScoreEventType.FIRST_CONTACT,
                reference_id=lead.pk,
            ).count(),
            1,
        )

    def test_manual_adjustment(self):
        event = record_manual_score_adjustment(
            salesperson=self.salesperson,
            points=15,
            adjustment_date=timezone.localdate(),
            justification="Bônus campanha",
            actor=self.admin,
        )
        self.assertEqual(event.points, 15)

    def test_manual_adjustment_requires_justification(self):
        with self.assertRaises(ValidationError):
            record_manual_score_adjustment(
                salesperson=self.salesperson,
                points=5,
                adjustment_date=timezone.localdate(),
                justification="",
                actor=self.admin,
            )

    def test_idempotency_helper(self):
        lead = self._lead()
        record_score_event(
            salesperson=self.salesperson,
            event_type=ScoreEventType.FIRST_CONTACT,
            reference_type="lead",
            reference_id=lead.pk,
            reference_label=lead.code,
        )
        self.assertTrue(
            event_exists(
                salesperson=self.salesperson,
                event_type=ScoreEventType.FIRST_CONTACT,
                reference_type="lead",
                reference_id=lead.pk,
            ),
        )


class MetricsRankingTests(PerformanceTestMixin, TestCase):
    def test_safe_rate_zero(self):
        self.assertEqual(safe_rate(0, 0), Decimal("0"))

    def test_ranking_tie_breaker(self):
        create_default_score_policy(actor=self.admin)
        start = timezone.now() - timedelta(days=30)
        end = timezone.now()
        ranking = build_ranking(user=self.manager_user, start=start, end=end)
        positions = [r["position"] for r in ranking["rows"]]
        self.assertEqual(positions, sorted(positions))

    def test_my_performance_view(self):
        self.client.login(username="seller1", password="test")
        response = self.client.get(reverse("leads:my_performance"))
        self.assertEqual(response.status_code, 200)

    def test_ranking_view(self):
        self.client.login(username="manager1", password="test")
        response = self.client.get(reverse("leads:ranking"))
        self.assertEqual(response.status_code, 200)

    def test_team_performance_view(self):
        self.client.login(username="manager1", password="test")
        response = self.client.get(reverse("leads:team_performance"))
        self.assertEqual(response.status_code, 200)


class WorkflowScoreTests(PerformanceTestMixin, TestCase):
    def setUp(self):
        create_default_score_policy(actor=self.admin)

    def test_won_scores_once(self):
        form = LeadForm(
            data={
                "name": "Lead Won",
                "phone": "11977776666",
                "assigned_salesperson": self.salesperson.pk,
                "priority": "normal",
                "probability": 10,
                "estimated_value": "0",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        lead = create_lead(form=form, actor=self.admin)
        change_lead_status(
            lead=lead,
            new_status=LeadStatus.TRIAGE,
            actor=self.admin,
        )
        change_lead_status(
            lead=lead,
            new_status=LeadStatus.ASSIGNED,
            actor=self.admin,
        )
        change_lead_status(
            lead=lead,
            new_status=LeadStatus.CONTACTED,
            actor=self.admin,
        )
        change_lead_status(
            lead=lead,
            new_status=LeadStatus.QUALIFIED,
            actor=self.admin,
        )
        change_lead_status(
            lead=lead,
            new_status=LeadStatus.QUOTE_PREPARATION,
            actor=self.admin,
        )
        change_lead_status(
            lead=lead,
            new_status=LeadStatus.QUOTE_SENT,
            actor=self.admin,
        )
        change_lead_status(
            lead=lead,
            new_status=LeadStatus.NEGOTIATION,
            actor=self.admin,
        )
        change_lead_status(
            lead=lead,
            new_status=LeadStatus.WON,
            actor=self.admin,
        )
        self.assertEqual(
            SalesScoreEvent.objects.filter(
                salesperson=self.salesperson,
                event_type=ScoreEventType.LEAD_WON,
            ).count(),
            1,
        )


class CommandTests(PerformanceTestMixin, TestCase):
    def test_process_dry_run(self):
        create_default_score_policy(actor=self.admin)
        result = process_penalties(dry_run=True)
        self.assertIn("created", result)

    def test_seed_idempotent(self):
        call_command("setup_erp_foundation")
        self.assertTrue(SalesScorePolicy.objects.filter(name="Política Comercial Padrão").exists())
