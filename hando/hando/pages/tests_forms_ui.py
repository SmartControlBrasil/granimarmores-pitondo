# ruff: noqa: PT009
from django.contrib.auth import get_user_model
from django.test import Client
from django.test import TestCase
from django.urls import reverse

from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import UserAccess
from access_control.models import AccessPermission
from access_control.models import RolePermission
from access_control.permissions import PERMISSIONS
from hando.forms import BootstrapFormMixin
from hando.forms import apply_bootstrap_classes
from quotes.forms import QuoteForm
from django import forms


User = get_user_model()


def _sync_permissions():
    for code, name, module, action in PERMISSIONS:
        AccessPermission.objects.update_or_create(
            code=code,
            defaults={"name": name, "module": module, "action": action, "is_active": True},
        )


class ErpFormsUITests(TestCase):
    def setUp(self):
        _sync_permissions()
        role = AccessRole.objects.create(
            name="Administrativo",
            slug="admin-forms-ui",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
        )
        self.user = User.objects.create_user("formui", password="pass")
        UserAccess.objects.create(user=self.user, role=role)
        self.client = Client()

    def test_apply_bootstrap_classes_select_and_input(self):
        class Sample(BootstrapFormMixin, forms.Form):
            name = forms.CharField()
            choice = forms.ChoiceField(choices=[("a", "A")])
            flag = forms.BooleanField(required=False)

        form = Sample()
        self.assertIn("form-control", form.fields["name"].widget.attrs.get("class", ""))
        self.assertIn("form-select", form.fields["choice"].widget.attrs.get("class", ""))
        self.assertIn("form-check-input", form.fields["flag"].widget.attrs.get("class", ""))

    def test_quote_form_labels_portuguese_and_classes(self):
        form = QuoteForm()
        self.assertEqual(form.fields["customer"].label, "Cliente")
        self.assertEqual(form.fields["valid_until"].label, "Válido até")
        self.assertIn("form-select", form.fields["customer"].widget.attrs["class"])
        self.assertIn("form-control", form.fields["payment_terms"].widget.attrs["class"])
        self.assertEqual(form.get_field_width("customer"), "col-md-6")

    def test_is_invalid_after_bound_errors(self):
        form = QuoteForm(data={})
        self.assertFalse(form.is_valid())
        apply_bootstrap_classes(form)
        self.assertIn("is-invalid", form.fields["customer"].widget.attrs["class"])

    def test_novo_orcamento_renders_erp_form(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("quotes:create"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("erp-form", content)
        self.assertIn("form-label", content)
        self.assertIn("Cliente", content)
        self.assertIn("form-select", content)
        self.assertIn("erp-form-actions", content)
