# ruff: noqa: PT009, S106, PT027
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import UserAccess
from materials.forms import MaterialForm
from materials.models import Material
from materials.models import MaterialCategory
from materials.models import MaterialPriceHistory
from materials.services.material_management import save_material

User = get_user_model()


class MaterialTests(TestCase):
    def setUp(self):
        role = AccessRole.objects.create(
            name="Administrativo",
            slug="administrativo",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
            quote_scope=DataScope.ALL,
            asset_scope=DataScope.ALL,
            maintenance_scope=DataScope.ALL,
        )
        self.user = User.objects.create_user("admin", password="pass")
        UserAccess.objects.create(user=self.user, role=role)
        self.client.force_login(self.user)
        self.category = MaterialCategory.objects.create(name="Granito", slug="granito")

    def test_duplicate_code_is_rejected(self):
        Material.objects.create(code="GR01", name="Preto", category=self.category)
        with self.assertRaises(IntegrityError):
            Material.objects.create(code="GR01", name="Branco", category=self.category)

    def test_negative_price_is_rejected(self):
        material = Material(
            code="GR01",
            name="Preto",
            category=self.category,
            cost_price=Decimal("-1"),
        )
        with self.assertRaises(ValidationError):
            material.full_clean()

    def test_price_change_generates_history(self):
        material = Material.objects.create(
            code="GR01",
            name="Preto",
            category=self.category,
            sale_price=Decimal("100.00"),
            minimum_sale_price=Decimal("80.00"),
        )
        form = MaterialForm(
            {
                "code": "GR01",
                "name": "Preto",
                "category": self.category.pk,
                "unit": "m2",
                "thickness_mm": "0.00",
                "cost_price": "50.00",
                "sale_price": "110.00",
                "minimum_sale_price": "80.00",
                "loss_percentage": "0.00",
                "default_margin_percentage": "0.00",
                "price_change_reason": "Atualização de tabela",
                "is_active": "on",
            },
            instance=material,
        )
        self.assertTrue(form.is_valid(), form.errors)
        save_material(form=form, actor=self.user)
        self.assertTrue(
            MaterialPriceHistory.objects.filter(
                material=material,
                price_type="sale",
            ).exists(),
        )

    def test_minimum_price_change_requires_reason(self):
        material = Material.objects.create(
            code="GR01",
            name="Preto",
            category=self.category,
            sale_price=Decimal("100.00"),
            minimum_sale_price=Decimal("80.00"),
        )
        form = MaterialForm(
            {
                "code": "GR01",
                "name": "Preto",
                "category": self.category.pk,
                "unit": "m2",
                "thickness_mm": "0.00",
                "cost_price": "50.00",
                "sale_price": "100.00",
                "minimum_sale_price": "90.00",
                "loss_percentage": "0.00",
                "default_margin_percentage": "0.00",
                "is_active": "on",
            },
            instance=material,
        )
        self.assertFalse(form.is_valid())

    def test_material_list_renders(self):
        response = self.client.get(reverse("materials:list"))
        self.assertEqual(response.status_code, 200)
