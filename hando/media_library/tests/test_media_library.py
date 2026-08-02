# ruff: noqa: PT009, S106
from decimal import Decimal
from io import BytesIO
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import UserAccess
from after_sales.models import ConsentScope
from after_sales.models import ConsentStatus
from after_sales.models import MediaUsageConsent
from commercial.performance_score import create_default_score_policy
from customers.models import Customer
from media_library.models import MediaAsset
from media_library.models import MediaCategory
from media_library.models import MediaStatus
from media_library.models import TechnicalReviewStatus
from media_library.selectors import media_dashboard_metrics
from media_library.services.classification import classify_media_asset
from media_library.services.classification import review_media_asset
from media_library.services.consent import evaluate_media_consent
from media_library.services.lifecycle import archive_media_asset
from media_library.services.lifecycle import request_media_deletion
from media_library.services.numbering import next_media_code
from media_library.services.portfolio import approve_for_portfolio
from media_library.services.portfolio import create_before_after_pair
from media_library.services.portfolio import create_collection
from media_library.services.portfolio import create_publication_candidate
from media_library.services.portfolio import remove_from_portfolio
from media_library.services.uploads import upload_media_asset
from media_library.services.uploads import upload_multiple_media_assets
from quotes.models import Quote
from quotes.models import QuoteItem
from quotes.models import QuoteStatus
from quotes.services.acceptance import accept_quote
from salespeople.models import Salesperson


User = get_user_model()


def _png(name="t.png", color=(20, 40, 60), size=(80, 60)):
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class MediaLibraryTests(TestCase):
    def setUp(self):
        role = AccessRole.objects.create(
            name="Administrativo",
            slug="admin-media",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
            quote_scope=DataScope.ALL,
        )
        self.user = User.objects.create_user("mediaadmin", password="pass")
        UserAccess.objects.create(user=self.user, role=role)
        create_default_score_policy(actor=self.user)
        self.salesperson = Salesperson.objects.create(code="VM", display_name="Vendedor Mídia")
        self.customer = Customer.objects.create(
            customer_type="individual",
            name="Cliente Mídia",
            assigned_salesperson=self.salesperson,
        )
        self.quote = Quote.objects.create(
            number="ORC-MID-001",
            customer=self.customer,
            salesperson=self.salesperson,
            status=QuoteStatus.SENT,
            subtotal=Decimal("500.00"),
            grand_total=Decimal("500.00"),
            valid_until=timezone.localdate(),
            created_by=self.user,
        )
        QuoteItem.objects.create(
            quote=self.quote,
            description="Bancada",
            quantity=Decimal("1"),
            unit_price=Decimal("500.00"),
            subtotal=Decimal("500.00"),
        )
        self.order = accept_quote(quote=self.quote, actor=self.user)
        self.category = MediaCategory.objects.create(
            name="Obra concluída",
            slug="obra-concluida-test",
            requires_consent=True,
            is_portfolio_eligible=True,
        )
        self.consent = MediaUsageConsent.objects.create(
            customer=self.customer,
            sales_order=self.order,
            consent_status=ConsentStatus.GRANTED,
            consent_scope=ConsentScope.PORTFOLIO,
            authorized_by_name="Cliente",
            authorized_at=timezone.now(),
            recorded_by=self.user,
            created_by=self.user,
        )

    def test_upload_numbering_checksum_duplicate(self):
        asset, dup = upload_media_asset(
            actor=self.user,
            uploaded_file=_png(),
            category=self.category,
            customer=self.customer,
            sales_order=self.order,
            title="Foto 1",
            alt_text="Bancada instalada",
            consent=self.consent,
        )
        self.assertFalse(dup)
        self.assertTrue(asset.code.startswith("MID-"))
        self.assertEqual(asset.status, MediaStatus.UPLOADED)
        self.assertTrue(asset.checksum)
        self.assertTrue(asset.width)
        asset2, dup2 = upload_media_asset(
            actor=self.user,
            uploaded_file=_png(),
            category=self.category,
            customer=self.customer,
            reuse_duplicate=True,
        )
        self.assertTrue(dup2)
        self.assertEqual(asset2.pk, asset.pk)
        self.assertNotEqual(next_media_code(), asset.code)

    def test_invalid_file_and_size(self):
        bad = SimpleUploadedFile("x.exe", b"MZ....", content_type="application/octet-stream")
        with self.assertRaises(ValidationError):
            upload_media_asset(actor=self.user, uploaded_file=bad, category=self.category)
        with self.assertRaises(ValidationError):
            upload_media_asset(
                actor=self.user,
                uploaded_file=_png(),
                # sem categoria nem vínculo
            )

    def test_classify_review_portfolio_consent(self):
        asset, _ = upload_media_asset(
            actor=self.user,
            uploaded_file=_png("a.png"),
            customer=self.customer,
            sales_order=self.order,
            consent=self.consent,
        )
        classify_media_asset(
            asset=asset,
            actor=self.user,
            category=self.category,
            title="Obra",
            alt_text="Cozinha",
        )
        asset.refresh_from_db()
        self.assertEqual(asset.status, MediaStatus.CLASSIFIED)
        review_media_asset(
            asset=asset,
            actor=self.user,
            decision=TechnicalReviewStatus.APPROVED,
        )
        approve_for_portfolio(asset=asset, actor=self.user)
        asset.refresh_from_db()
        self.assertTrue(asset.is_portfolio_approved)
        remove_from_portfolio(asset=asset, actor=self.user)
        asset.refresh_from_db()
        self.assertFalse(asset.is_portfolio_approved)

        denied = MediaUsageConsent.objects.create(
            customer=self.customer,
            consent_status=ConsentStatus.DENIED,
            consent_scope=ConsentScope.PORTFOLIO,
            created_by=self.user,
        )
        asset.consent = denied
        asset.technical_review_status = TechnicalReviewStatus.APPROVED
        asset.alt_text = "x"
        asset.title = "y"
        asset.save()
        with self.assertRaises(ValidationError):
            approve_for_portfolio(asset=asset, actor=self.user)

        asset.consent = self.consent
        asset.save()
        self.consent.consent_status = ConsentStatus.REVOKED
        self.consent.revoked_at = timezone.now()
        self.consent.save()
        self.assertEqual(evaluate_media_consent(asset), "revoked")

    def test_collection_before_after_publication(self):
        a1, _ = upload_media_asset(
            actor=self.user,
            uploaded_file=_png("b1.png", (10, 10, 10)),
            category=self.category,
            customer=self.customer,
            sales_order=self.order,
        )
        a2, _ = upload_media_asset(
            actor=self.user,
            uploaded_file=_png("b2.png", (200, 200, 200)),
            category=self.category,
            customer=self.customer,
            sales_order=self.order,
        )
        collection = create_collection(
            actor=self.user,
            name="Projeto",
            collection_type="before_after",
            customer=self.customer,
            sales_order=self.order,
        )
        self.assertTrue(collection.code.startswith("COL-"))
        pair = create_before_after_pair(
            actor=self.user,
            before_asset=a1,
            after_asset=a2,
            title="Antes/depois",
            collection=collection,
        )
        self.assertEqual(pair.before_asset_id, a1.pk)
        with self.assertRaises(ValidationError):
            create_before_after_pair(
                actor=self.user,
                before_asset=a1,
                after_asset=a1,
                title="igual",
            )
        cand = create_publication_candidate(
            actor=self.user,
            asset=a2,
            channel="instagram",
            caption="Planejado",
        )
        self.assertEqual(cand.status, "candidate")

    def test_multi_upload_archive_delete_dashboard(self):
        results = upload_multiple_media_assets(
            actor=self.user,
            files=[_png("m1.png"), _png("m2.png", (1, 2, 3))],
            common_context={"category": self.category, "customer": self.customer},
        )
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["ok"] for r in results))
        asset = results[0]["asset"]
        archive_media_asset(asset=asset, actor=self.user, reason="Arquivo antigo")
        asset.refresh_from_db()
        self.assertEqual(asset.status, MediaStatus.ARCHIVED)
        asset2 = results[1]["asset"]
        request_media_deletion(asset=asset2, actor=self.user, reason="Pedido administrativo")
        asset2.refresh_from_db()
        self.assertTrue(asset2.deletion_requested)
        metrics = media_dashboard_metrics(user=self.user)
        self.assertGreaterEqual(metrics["total"], 0)
        self.assertEqual(metrics.get("space_mb", 0) >= 0, True)

    def test_private_access_and_seed_command(self):
        asset, _ = upload_media_asset(
            actor=self.user,
            uploaded_file=_png("priv.png"),
            category=self.category,
            customer=self.customer,
        )
        client = Client()
        client.force_login(self.user)
        resp = client.get(reverse("media_library:asset_file", args=[asset.pk]))
        self.assertEqual(resp.status_code, 200)
        resp = client.get(reverse("media_library:library"))
        self.assertEqual(resp.status_code, 200)
        resp = client.get(reverse("media_library:dashboard"))
        self.assertEqual(resp.status_code, 200)
        from access_control.permissions import PERMISSIONS

        codes = {p[0] for p in PERMISSIONS}
        self.assertIn("media_assets.upload", codes)
        self.assertIn("media_portfolio.approve", codes)
        out = StringIO()
        call_command("audit_media_library", stdout=out)
        self.assertTrue("Auditoria" in out.getvalue() or "Nenhuma inconsistência" in out.getvalue())
        out2 = StringIO()
        call_command("rebuild_media_metadata", "--dry-run", stdout=out2)
        self.assertIn("Metadados", out2.getvalue())

    def test_reject_requires_reason(self):
        asset, _ = upload_media_asset(
            actor=self.user,
            uploaded_file=_png("r.png"),
            category=self.category,
            sales_order=self.order,
        )
        with self.assertRaises(ValidationError):
            review_media_asset(
                asset=asset,
                actor=self.user,
                decision=TechnicalReviewStatus.REJECTED,
                reason="",
            )
        review_media_asset(
            asset=asset,
            actor=self.user,
            decision=TechnicalReviewStatus.REJECTED,
            reason="Fora do padrão",
        )
        asset.refresh_from_db()
        self.assertEqual(asset.status, MediaStatus.REJECTED)
        MediaAsset.objects.filter(pk=asset.pk).exists()
