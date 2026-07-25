# ruff: noqa: PT009, S106
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import UserAccess
from audit.models import AuditEvent
from audit.models import UserSessionLog

User = get_user_model()


class UserCrudTests(TestCase):
    def setUp(self):
        self.admin_role = AccessRole.objects.create(
            name="Administrativo",
            slug="administrativo",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
            quote_scope=DataScope.ALL,
            asset_scope=DataScope.ALL,
            maintenance_scope=DataScope.ALL,
        )
        self.basic_role = AccessRole.objects.create(
            name="Operacional",
            slug="operacional",
            hierarchy_level=60,
        )
        self.admin = User.objects.create_user("admin", password="pass", is_active=True)
        UserAccess.objects.create(user=self.admin, role=self.admin_role)
        self.client.force_login(self.admin)

    def test_user_list_renders_active_access(self):
        response = self.client.get(reverse("accounts:users"))
        self.assertEqual(response.status_code, 200)

    def test_create_user_records_audit_without_password(self):
        response = self.client.post(
            reverse("accounts:user_create"),
            {
                "username": "novo",
                "name": "Novo Usuário",
                "email": "novo@example.com",
                "is_active": "on",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
                "full_name": "Novo Usuário",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="novo")
        self.assertTrue(user.check_password("StrongPass123!"))
        event = AuditEvent.objects.get(module="accounts", action="create_user")
        self.assertNotIn("password", event.metadata)

    def test_last_full_access_user_cannot_be_deactivated(self):
        response = self.client.post(
            reverse("accounts:user_deactivate", args=[self.admin.pk]),
        )
        self.assertEqual(response.status_code, 302)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_assign_access_closes_previous_access(self):
        user = User.objects.create_user("worker", password="pass")
        UserAccess.objects.create(user=user, role=self.basic_role)
        response = self.client.post(
            reverse("accounts:user_access", args=[user.pk]),
            {"role": self.admin_role.pk, "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            UserAccess.objects.filter(user=user, is_active=True).count(),
            1,
        )
        self.assertTrue(
            AuditEvent.objects.filter(
                action="assign_user_access",
                object_id=str(user.pk),
            ).exists(),
        )

    def test_revoke_sessions_closes_active_logs(self):
        user = User.objects.create_user("worker", password="pass")
        UserSessionLog.objects.create(user=user, session_key="abc", is_active=True)
        response = self.client.post(reverse("accounts:user_sessions", args=[user.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(UserSessionLog.objects.get(user=user).is_active)
