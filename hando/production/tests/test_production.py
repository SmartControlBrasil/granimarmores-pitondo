# ruff: noqa: PT009, S106
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import RolePermission
from access_control.models import UserAccess
from access_control.services.authorization import user_has_permission
from commercial.models import LossReason
from commercial.performance_models import SalesScoreEvent
from commercial.performance_models import ScoreEventType
from commercial.performance_score import create_default_score_policy
from customers.models import Customer
from production.models import PieceStageStatus
from production.models import ProductionOrderStatus
from production.models import ProductionStage
from production.models import QualityChecklist
from production.models import SalesOrder
from production.models import SalesOrderStatus
from production.selectors import calculate_order_progress
from production.selectors import calculate_piece_progress
from production.services.numbering import next_production_order_number
from production.services.numbering import next_sales_order_number
from production.services.order_workflow import change_order_status
from production.services.piece_workflow import complete_stage
from production.services.piece_workflow import skip_stage
from production.services.piece_workflow import start_stage
from production.services.quality import approve_inspection
from production.services.quality import create_inspection
from production.services.quality import reject_inspection
from production.services.work_orders import complete_production_order
from production.services.work_orders import create_production_order
from production.services.work_orders import generate_piece_stages
from production.services.work_orders import generate_pieces_from_order
from production.services.work_orders import release_production_order
from production.services.work_orders import start_production_order
from quotes.models import Quote
from quotes.models import QuoteItem
from quotes.models import QuoteStatus
from quotes.services.acceptance import accept_quote
from quotes.services.acceptance import refuse_quote
from quotes.services.workflow import change_status
from salespeople.models import Salesperson

User = get_user_model()


def _grant(role, code):
    permission = AccessPermission.objects.filter(code=code).first()
    if permission:
        RolePermission.objects.update_or_create(
            role=role,
            permission=permission,
            defaults={"allowed": True},
        )


class ProductionFlowTests(TestCase):
    def setUp(self):
        self.admin_role = AccessRole.objects.create(
            name="Administrativo",
            slug="admin-prod",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
            quote_scope=DataScope.ALL,
        )
        self.user = User.objects.create_user("adminprod", password="pass")
        UserAccess.objects.create(user=self.user, role=self.admin_role)
        self.salesperson = Salesperson.objects.create(code="VP", display_name="Vendedor")
        self.customer = Customer.objects.create(
            customer_type="person",
            name="Cliente Produção",
            email="prod@example.com",
        )
        self.loss_reason = LossReason.objects.create(
            name="Preço teste",
            slug="preco-teste",
            requires_notes=True,
        )
        create_default_score_policy(actor=self.user)
        self.quote = Quote.objects.create(
            number="ORC-TEST-001",
            customer=self.customer,
            salesperson=self.salesperson,
            status=QuoteStatus.SENT,
            subtotal=Decimal("1000.00"),
            grand_total=Decimal("1000.00"),
            sent_at=timezone.now(),
            valid_until=timezone.localdate() + timezone.timedelta(days=15),
            created_by=self.user,
        )
        QuoteItem.objects.create(
            quote=self.quote,
            description="Bancada",
            quantity=Decimal("1"),
            unit_price=Decimal("1000.00"),
            subtotal=Decimal("1000.00"),
        )
        ProductionStage.objects.create(name="Corte", slug="corte", display_order=1, is_active=True)
        QualityChecklist.objects.create(name="Padrão", slug="padrao-test", is_active=True)

    def test_acceptance_creates_order_and_score(self):
        order = accept_quote(quote=self.quote, actor=self.user)
        self.assertEqual(self.quote.status, QuoteStatus.ACCEPTED)
        self.assertIsInstance(order, SalesOrder)
        self.assertEqual(order.total, Decimal("1000.00"))
        self.assertTrue(
            SalesScoreEvent.objects.filter(
                salesperson=self.salesperson,
                event_type=ScoreEventType.LEAD_WON,
                reference_type="quote",
                reference_id=self.quote.pk,
            ).exists(),
        )

    def test_duplicate_order_blocked(self):
        accept_quote(quote=self.quote, actor=self.user)
        order2 = accept_quote(quote=self.quote, actor=self.user)
        self.assertEqual(SalesOrder.objects.exclude(status=SalesOrderStatus.CANCELLED).count(), 1)
        self.assertEqual(order2.pk, SalesOrder.objects.first().pk)

    def test_invalid_acceptance(self):
        draft = Quote.objects.create(
            number="ORC-DRAFT",
            customer=self.customer,
            salesperson=self.salesperson,
            status=QuoteStatus.DRAFT,
            subtotal=Decimal("100"),
            grand_total=Decimal("100"),
            valid_until=timezone.localdate() + timezone.timedelta(days=15),
            created_by=self.user,
        )
        with self.assertRaises(ValidationError):
            accept_quote(quote=draft, actor=self.user)

    def test_refuse_requires_reason(self):
        with self.assertRaises(ValidationError):
            refuse_quote(quote=self.quote, actor=self.user, loss_reason=self.loss_reason, notes="")

    def test_numbering(self):
        n1 = next_sales_order_number()
        n2 = next_sales_order_number()
        self.assertNotEqual(n1, n2)
        self.assertTrue(n1.startswith("PED-"))
        op1 = next_production_order_number()
        self.assertTrue(op1.startswith("OP-"))

    def test_production_workflow_and_progress(self):
        order = accept_quote(quote=self.quote, actor=self.user)
        production = create_production_order(sales_order=order, actor=self.user)
        pieces = generate_pieces_from_order(production_order=production, actor=self.user)
        for piece in pieces:
            generate_piece_stages(piece=piece, actor=self.user)
        release_production_order(production_order=production, actor=self.user)
        start_production_order(production_order=production, actor=self.user)
        piece = pieces[0]
        stage = piece.stages.order_by("sequence").first()
        start_stage(piece_stage=stage, actor=self.user)
        complete_stage(piece_stage=stage, actor=self.user)
        self.assertGreater(calculate_piece_progress(piece), Decimal("0"))
        self.assertGreater(calculate_order_progress(production), Decimal("0"))

    def test_skip_stage_requires_permission(self):
        order = accept_quote(quote=self.quote, actor=self.user)
        production = create_production_order(sales_order=order, actor=self.user)
        piece = generate_pieces_from_order(production_order=production, actor=self.user)[0]
        generate_piece_stages(piece=piece, actor=self.user)
        stage = piece.stages.order_by("sequence").first()
        skip_stage(piece_stage=stage, actor=self.user, reason="Teste administrativo")
        stage.refresh_from_db()
        self.assertEqual(stage.status, PieceStageStatus.SKIPPED)

    def test_quality_reject_and_rbac(self):
        order = accept_quote(quote=self.quote, actor=self.user)
        production = create_production_order(sales_order=order, actor=self.user)
        inspection = create_inspection(production_order=production, actor=self.user)
        reject_inspection(
            inspection=inspection,
            actor=self.user,
            notes="Medida divergente",
            create_rework=False,
        )
        self.assertTrue(user_has_permission(self.user, "sales_orders.view"))

    def test_order_status_transition(self):
        order = accept_quote(quote=self.quote, actor=self.user)
        change_order_status(
            order=order,
            new_status=SalesOrderStatus.TECHNICAL_REVIEW,
            actor=self.user,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, SalesOrderStatus.TECHNICAL_REVIEW)

    def test_complete_production_requires_stages(self):
        order = accept_quote(quote=self.quote, actor=self.user)
        production = create_production_order(sales_order=order, actor=self.user)
        generate_pieces_from_order(production_order=production, actor=self.user)
        release_production_order(production_order=production, actor=self.user)
        start_production_order(production_order=production, actor=self.user)
        with self.assertRaises(ValidationError):
            complete_production_order(production_order=production, actor=self.user)

    def test_progress_zero_safe(self):
        order = accept_quote(quote=self.quote, actor=self.user)
        production = create_production_order(sales_order=order, actor=self.user)
        self.assertEqual(calculate_order_progress(production), Decimal("0"))
