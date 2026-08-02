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
from access_control.permissions import PERMISSIONS
from commercial.performance_score import create_default_score_policy
from customers.models import Customer
from finance.export import sanitize_csv_cell
from finance.models import AccountType
from finance.models import AccountsReceivable
from finance.models import CategoryType
from finance.models import CostCenter
from finance.models import FinancialAccount
from finance.models import FinancialCategory
from finance.models import FinancialMovement
from finance.models import MethodType
from finance.models import MovementType
from finance.models import PaymentMethod
from finance.models import PaymentStatus
from finance.models import PaymentTerm
from finance.models import TitleStatus
from finance.services.cash_flow import cash_flow_summary
from finance.services.installments import build_installment_plan
from finance.services.payables import create_payable
from finance.services.payments import register_payable_payment
from finance.services.payments import register_receivable_payment
from finance.services.payments import reverse_receivable_payment
from finance.services.receivables import generate_receivable_from_order
from finance.services.reconciliation import create_financial_account
from finance.services.reconciliation import create_manual_adjustment
from finance.services.reconciliation import transfer_between_accounts
from quotes.models import Quote
from quotes.models import QuoteItem
from quotes.models import QuoteStatus
from salespeople.models import Salesperson


User = get_user_model()


def _sync_permissions():
    for code, name, module, action in PERMISSIONS:
        AccessPermission.objects.update_or_create(
            code=code,
            defaults={"name": name, "module": module, "action": action, "is_active": True},
        )


class FinanceTests(TestCase):
    def setUp(self):
        _sync_permissions()
        role = AccessRole.objects.create(
            name="Administrativo",
            slug="admin-fin",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
            quote_scope=DataScope.ALL,
        )
        self.user = User.objects.create_user("finadmin", password="pass")
        UserAccess.objects.create(user=self.user, role=role)
        create_default_score_policy(actor=self.user)
        self.sp = Salesperson.objects.create(code="VF", display_name="Vendedor Fin")
        self.customer = Customer.objects.create(
            customer_type="individual",
            name="Cliente Fin",
            assigned_salesperson=self.sp,
        )
        self.category = FinancialCategory.objects.create(
            name="Venda de peças",
            code="venda-de-pecas",
            category_type=CategoryType.INCOME,
        )
        self.expense_cat = FinancialCategory.objects.create(
            name="Frete",
            code="frete",
            category_type=CategoryType.EXPENSE,
        )
        self.cost_center = CostCenter.objects.create(name="Comercial", code="comercial")
        self.method = PaymentMethod.objects.create(
            name="PIX",
            code="pix",
            method_type=MethodType.PIX,
        )
        self.term = PaymentTerm.objects.create(
            name="À vista",
            installment_count=1,
            first_due_days=0,
            interval_days=0,
        )
        self.term3 = PaymentTerm.objects.create(
            name="3 parcelas",
            installment_count=3,
            first_due_days=0,
            interval_days=30,
        )
        self.account = create_financial_account(
            data={
                "name": "Caixa",
                "account_type": AccountType.CASH,
                "initial_balance": Decimal("1000.00"),
            },
            actor=self.user,
        )
        self.account2 = create_financial_account(
            data={
                "name": "Banco",
                "account_type": AccountType.BANK_ACCOUNT,
                "initial_balance": Decimal("0.00"),
            },
            actor=self.user,
        )
        now = timezone.now()
        self.quote = Quote.objects.create(
            number="ORC-FIN-001",
            customer=self.customer,
            salesperson=self.sp,
            status=QuoteStatus.ACCEPTED,
            subtotal=Decimal("300.00"),
            grand_total=Decimal("300.00"),
            valid_until=timezone.localdate(),
            accepted_at=now,
            created_by=self.user,
        )
        QuoteItem.objects.create(
            quote=self.quote,
            description="Peça",
            quantity=Decimal("1"),
            unit_price=Decimal("300.00"),
            subtotal=Decimal("300.00"),
        )
        from production.models import SalesOrder
        from production.models import SalesOrderStatus

        self.order = SalesOrder.objects.create(
            number="PED-FIN-001",
            quote=self.quote,
            customer=self.customer,
            salesperson=self.sp,
            status=SalesOrderStatus.CONFIRMED,
            order_date=timezone.localdate(),
            subtotal=Decimal("300.00"),
            total=Decimal("300.00"),
            created_by=self.user,
        )
        self.client = Client()

    def test_installment_sum_and_rounding(self):
        plan = build_installment_plan(
            payment_term=self.term3,
            total=Decimal("100.00"),
            base_date=timezone.localdate(),
        )
        self.assertEqual(len(plan), 3)
        self.assertEqual(sum(p["amount"] for p in plan), Decimal("100.00"))

    def test_generate_receivable_and_duplicate_block(self):
        recv = generate_receivable_from_order(
            sales_order=self.order,
            payment_term=self.term,
            actor=self.user,
            category=self.category,
            cost_center=self.cost_center,
        )
        self.assertTrue(recv.number.startswith("REC-"))
        self.assertEqual(recv.original_amount, Decimal("300.00"))
        self.assertEqual(recv.status, TitleStatus.OPEN)
        self.assertEqual(recv.installments.count(), 1)
        with self.assertRaises(ValidationError):
            generate_receivable_from_order(
                sales_order=self.order,
                payment_term=self.term,
                actor=self.user,
            )

    def test_receive_partial_total_overpay_and_reverse(self):
        recv = generate_receivable_from_order(
            sales_order=self.order,
            payment_term=self.term3,
            actor=self.user,
            category=self.category,
        )
        inst = recv.installments.order_by("sequence").first()
        p1 = register_receivable_payment(
            installment=inst,
            amount=Decimal("50.00"),
            payment_date=timezone.localdate(),
            payment_method=self.method,
            financial_account=self.account,
            actor=self.user,
        )
        inst.refresh_from_db()
        recv.refresh_from_db()
        self.assertEqual(inst.status, "partially_paid")
        self.assertEqual(recv.status, TitleStatus.PARTIALLY_PAID)
        self.assertTrue(FinancialMovement.objects.filter(source_receivable_payment=p1).exists())
        with self.assertRaises(ValidationError):
            register_receivable_payment(
                installment=inst,
                amount=Decimal("999.00"),
                payment_date=timezone.localdate(),
                payment_method=self.method,
                financial_account=self.account,
                actor=self.user,
            )
        register_receivable_payment(
            installment=inst,
            amount=inst.outstanding_amount,
            payment_date=timezone.localdate(),
            payment_method=self.method,
            financial_account=self.account,
            actor=self.user,
        )
        # pay remaining installments
        for inst2 in recv.installments.exclude(pk=inst.pk):
            register_receivable_payment(
                installment=inst2,
                amount=inst2.outstanding_amount,
                payment_date=timezone.localdate(),
                payment_method=self.method,
                financial_account=self.account,
                actor=self.user,
            )
        recv.refresh_from_db()
        self.assertEqual(recv.status, TitleStatus.PAID)
        reverse_receivable_payment(payment=p1, actor=self.user, reason="Erro de baixa")
        p1.refresh_from_db()
        self.assertEqual(p1.status, PaymentStatus.REVERSED)

    def test_payable_payment_and_transfer_adjustment(self):
        payable = create_payable(
            data={
                "supplier_name": "Fornecedor X",
                "description": "Frete",
                "category": self.expense_cat,
                "cost_center": self.cost_center,
                "due_date": timezone.localdate(),
                "original_amount": Decimal("80.00"),
            },
            actor=self.user,
        )
        inst = payable.installments.first()
        register_payable_payment(
            installment=inst,
            amount=Decimal("30.00"),
            payment_date=timezone.localdate(),
            payment_method=self.method,
            financial_account=self.account,
            actor=self.user,
        )
        payable.refresh_from_db()
        self.assertEqual(payable.status, TitleStatus.PARTIALLY_PAID)
        transfer_between_accounts(
            source_account=self.account,
            destination_account=self.account2,
            amount=Decimal("10.00"),
            movement_date=timezone.localdate(),
            actor=self.user,
        )
        create_manual_adjustment(
            account=self.account,
            direction="in",
            amount=Decimal("5.00"),
            movement_date=timezone.localdate(),
            reason="Ajuste de caixa",
            actor=self.user,
            category=self.expense_cat,
        )
        self.assertTrue(FinancialMovement.objects.filter(movement_type=MovementType.TRANSFER_OUT).exists())

    def test_cash_flow_and_immutable_movement(self):
        today = timezone.localdate()
        summary = cash_flow_summary(start=today - timedelta(days=7), end=today)
        self.assertIn("realized_balance", summary)
        self.assertIn("projected_balance", summary)
        mov = FinancialMovement.objects.first()
        with self.assertRaises(ValidationError):
            mov.amount = Decimal("1.00")
            mov.save()

    def test_dashboard_rbac_csv_seed_commands(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("finance:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(sanitize_csv_cell("=1+1"), "'=1+1")
        out = StringIO()
        call_command("setup_erp_foundation", stdout=out)
        self.assertTrue(FinancialCategory.objects.filter(code="venda-de-pecas").exists())
        out2 = StringIO()
        call_command("sync_financial_overdue", "--dry-run", stdout=out2)
        self.assertIn("Dry-run", out2.getvalue())
        out3 = StringIO()
        call_command("audit_financial_consistency", stdout=out3)
        self.assertIn("Auditoria financeira", out3.getvalue())

    def test_movement_delete_blocked(self):
        mov = FinancialMovement.objects.first()
        with self.assertRaises(ValidationError):
            mov.delete()
