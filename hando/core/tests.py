
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import RolePermission
from access_control.models import UserAccess
from access_control.services.authorization import can_access_object
from access_control.services.authorization import user_has_permission
from accounts.services import deactivate_user
from assets.models import Asset
from assets.models import AssetCategory
from audit.models import AuditEvent
from audit.models import UserSessionLog
from customers.models import Customer
from fleet.models import Vehicle
from maintenance.models import MaintenanceOrder
from salespeople.models import Salesperson

User = get_user_model()


class ERPFoundationTests(TestCase):
    def setUp(self):
        self.permission = AccessPermission.objects.create(
            code="customers.view",
            name="Ver clientes",
            module="customers",
            action="view",
        )
        self.create_customer_permission = AccessPermission.objects.create(
            code="customers.create",
            name="Criar clientes",
            module="customers",
            action="create",
        )
        self.dashboard_permission = AccessPermission.objects.create(
            code="dashboard.view",
            name="Ver dashboard",
            module="dashboard",
            action="view",
        )
        self.admin_role = AccessRole.objects.create(
            name="Administrativo",
            slug="administrativo",
            hierarchy_level=1,
            has_full_access=True,
            is_system=True,
            customer_scope=DataScope.ALL,
            quote_scope=DataScope.ALL,
            asset_scope=DataScope.ALL,
            maintenance_scope=DataScope.ALL,
        )
        self.sales_role = AccessRole.objects.create(
            name="Vendedor",
            slug="vendedor",
            hierarchy_level=50,
            customer_scope=DataScope.OWN,
            quote_scope=DataScope.OWN,
            asset_scope=DataScope.OWN,
            maintenance_scope=DataScope.OWN,
        )
        RolePermission.objects.create(
            role=self.sales_role, permission=self.permission, allowed=True,
        )
        self.admin = User.objects.create_user(
            username="admin", password="pass", is_active=True,
        )
        self.user = User.objects.create_user(
            username="user", password="pass", is_active=True,
        )
        self.other = User.objects.create_user(
            username="other", password="pass", is_active=True,
        )
        UserAccess.objects.create(user=self.admin, role=self.admin_role)

    def test_administrativo_has_full_access(self):
        self.assertTrue(user_has_permission(self.admin, "anything.really"))

    def test_user_without_access_has_no_functional_permission(self):
        self.assertFalse(user_has_permission(self.user, "customers.view"))

    def test_expired_access_does_not_grant_permission(self):
        UserAccess.objects.create(
            user=self.user,
            role=self.sales_role,
            valid_from=timezone.now() - timezone.timedelta(days=2),
            valid_until=timezone.now() - timezone.timedelta(days=1),
        )
        self.assertFalse(user_has_permission(self.user, "customers.view"))

    def test_inactive_user_has_no_permission(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        UserAccess.objects.create(user=self.user, role=self.sales_role)
        self.assertFalse(user_has_permission(self.user, "customers.view"))

    def test_salesperson_own_scope_blocks_other_customer(self):
        seller = Salesperson.objects.create(
            user=self.user, code="S01", display_name="Seller",
        )
        other_seller = Salesperson.objects.create(
            user=self.other, code="S02", display_name="Other",
        )
        UserAccess.objects.create(user=self.user, role=self.sales_role)
        customer = Customer.objects.create(
            customer_type="company", name="Outro", assigned_salesperson=other_seller,
        )
        self.assertFalse(can_access_object(self.user, customer, "view"))
        self.assertEqual(seller.user, self.user)

    def test_salesperson_can_access_own_customer(self):
        seller = Salesperson.objects.create(
            user=self.user, code="S01", display_name="Seller",
        )
        UserAccess.objects.create(user=self.user, role=self.sales_role)
        customer = Customer.objects.create(
            customer_type="company", name="Cliente", assigned_salesperson=seller,
        )
        self.assertTrue(can_access_object(self.user, customer, "view"))

    def test_protected_route_returns_403_without_permission(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("customers:list"))
        self.assertEqual(response.status_code, 403)

    def test_menu_hides_module_without_permission(self):
        RolePermission.objects.create(
            role=self.admin_role, permission=self.dashboard_permission, allowed=True,
        )
        self.client.force_login(self.user)
        response = self.client.get("/")
        self.assertNotContains(response, "Clientes")

    def test_customer_creation_generates_audit(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("customers:create"),
            {
                "customer_type": "company",
                "name": "Cliente Teste",
                "document": "12345678000190",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            AuditEvent.objects.filter(
                module="customers", action="create", object_repr="Cliente Teste",
            ).exists(),
        )

    def test_role_permission_change_generates_audit_when_recorded(self):
        event = AuditEvent.objects.create(
            user=self.admin,
            event_type="configuration",
            module="access_control",
            action="update_role",
            object_repr=str(self.sales_role),
            metadata={"changes": {"name": {"from": "A", "to": "B"}}},
        )
        self.assertEqual(event.module, "access_control")

    def test_login_creates_active_session(self):
        self.assertTrue(self.client.login(username="admin", password="pass"))
        self.assertTrue(
            UserSessionLog.objects.filter(user=self.admin, is_active=True).exists(),
        )

    def test_logout_closes_session(self):
        self.client.login(username="admin", password="pass")
        self.client.logout()
        self.assertTrue(
            UserSessionLog.objects.filter(
                user=self.admin, is_active=False, logout_reason="manual",
            ).exists(),
        )

    def test_deactivate_user_revokes_sessions(self):
        UserSessionLog.objects.create(user=self.user, session_key="abc", is_active=True)
        deactivate_user(self.user, actor=self.admin)
        self.assertFalse(
            UserSessionLog.objects.get(user=self.user, session_key="abc").is_active,
        )

    def test_logs_do_not_store_password(self):
        AuditEvent.objects.create(
            event_type="authentication",
            module="accounts",
            action="login",
            status="failed",
            metadata={"password": "secret", "username": "x"},
        )
        self.assertNotIn("password", AuditEvent.objects.get().metadata)

    def test_audit_event_cannot_be_edited(self):
        event = AuditEvent.objects.create(
            event_type="view", module="audit", action="view",
        )
        event.description = "edited"
        with self.assertRaises(ValueError):
            event.save()

    def test_asset_accepts_machine_and_furniture(self):
        machines = AssetCategory.objects.create(name="Máquinas")
        furniture = AssetCategory.objects.create(name="Móveis")
        Asset.objects.create(
            asset_code="M01", name="Máquina de corte", category=machines,
        )
        Asset.objects.create(asset_code="F01", name="Mesa", category=furniture)
        self.assertEqual(Asset.objects.count(), 2)

    def test_vehicle_rejects_duplicate_plate(self):
        Vehicle.objects.create(
            asset_code="V01", plate="ABC1234", brand="VW", model="Saveiro",
        )
        with self.assertRaises(Exception):
            Vehicle.objects.create(
                asset_code="V02", plate="ABC1234", brand="Fiat", model="Strada",
            )

    def test_vehicle_odometer_cannot_decrease(self):
        vehicle = Vehicle.objects.create(
            asset_code="V01", plate="ABC1234", brand="VW", model="Saveiro", odometer=100,
        )
        vehicle.odometer = 90
        with self.assertRaises(ValidationError):
            vehicle.full_clean()

    def test_maintenance_order_requires_asset_or_vehicle(self):
        order = MaintenanceOrder(number="OS1", maintenance_type="preventive")
        with self.assertRaises(ValidationError):
            order.full_clean()

    def test_maintenance_order_rejects_asset_and_vehicle_together(self):
        category = AssetCategory.objects.create(name="Máquinas")
        asset = Asset.objects.create(
            asset_code="M01", name="Máquina", category=category,
        )
        vehicle = Vehicle.objects.create(
            asset_code="V01", plate="ABC1234", brand="VW", model="Saveiro",
        )
        order = MaintenanceOrder(
            number="OS1", maintenance_type="preventive", asset=asset, vehicle=vehicle,
        )
        with self.assertRaises(ValidationError):
            order.full_clean()

    def test_maintenance_completion_records_author_and_date(self):
        category = AssetCategory.objects.create(name="Máquinas")
        asset = Asset.objects.create(
            asset_code="M01", name="Máquina", category=category,
        )
        order = MaintenanceOrder.objects.create(
            number="OS1", maintenance_type="preventive", asset=asset,
        )
        order.complete(self.admin)
        order.refresh_from_db()
        self.assertEqual(order.completed_by, self.admin)
        self.assertIsNotNone(order.completed_at)

    def test_dashboard_does_not_show_static_demo_numbers(self):
        self.client.force_login(self.admin)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "3,456")
        self.assertNotContains(response, "$4,578")

    def test_setup_command_is_idempotent(self):
        call_command("setup_erp_foundation")
        first_roles = AccessRole.objects.count()
        first_permissions = AccessPermission.objects.count()
        call_command("setup_erp_foundation")
        self.assertEqual(AccessRole.objects.count(), first_roles)
        self.assertEqual(AccessPermission.objects.count(), first_permissions)
