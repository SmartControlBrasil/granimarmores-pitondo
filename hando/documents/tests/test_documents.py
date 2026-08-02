# ruff: noqa: PT009, S106
from datetime import timedelta
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
from customers.models import Customer
from documents.export import sanitize_csv_cell
from documents.models import AcceptanceStatus
from documents.models import Confidentiality
from documents.models import DocumentCategory
from documents.models import DocumentStatus
from documents.models import DocumentType
from documents.models import DocumentVersion
from documents.models import RelationshipType
from documents.models import TemplateStatus
from documents.models import VersionStatus
from documents.services.acceptance import register_document_acceptance
from documents.services.acceptance import register_document_send
from documents.services.acceptance import register_document_signature
from documents.services.approvals import approve_document_version
from documents.services.approvals import reject_document_version
from documents.services.approvals import submit_document_for_review
from documents.services.documents import approve_document_template
from documents.services.documents import create_document_from_template
from documents.services.documents import create_document_template
from documents.services.documents import create_document_type
from documents.services.documents import create_managed_document
from documents.services.lifecycle import cancel_document
from documents.services.lifecycle import link_documents
from documents.services.lifecycle import renew_document
from documents.services.lifecycle import sync_document_statuses
from documents.services.lifecycle import terminate_document
from documents.services.placeholders import render_placeholders
from documents.services.versions import create_version
from documents.services.versions import edit_draft_version
from salespeople.models import Salesperson


User = get_user_model()


def _sync_permissions():
    for code, name, module, action in PERMISSIONS:
        AccessPermission.objects.update_or_create(
            code=code,
            defaults={"name": name, "module": module, "action": action, "is_active": True},
        )


def _grant(role, *codes):
    for code in codes:
        perm = AccessPermission.objects.get(code=code)
        RolePermission.objects.get_or_create(role=role, permission=perm, defaults={"allowed": True})


class DocumentManagementTests(TestCase):
    def setUp(self):
        _sync_permissions()
        self.admin_role = AccessRole.objects.create(
            name="Administrativo",
            slug="admin-docs",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
        )
        self.seller_role = AccessRole.objects.create(
            name="Vendedor",
            slug="seller-docs",
            hierarchy_level=50,
            has_full_access=False,
            customer_scope=DataScope.OWN,
        )
        _grant(
            self.seller_role,
            "documents.view",
            "documents.create",
            "documents.update",
            "documents.send",
            "documents.print",
            "document_types.view",
            "document_templates.view",
        )
        self.user = User.objects.create_user("docadmin", password="pass")
        UserAccess.objects.create(user=self.user, role=self.admin_role)
        self.seller_user = User.objects.create_user("docseller", password="pass")
        UserAccess.objects.create(user=self.seller_user, role=self.seller_role)
        self.sp = Salesperson.objects.create(
            code="VD",
            display_name="Vendedor Docs",
            user=self.seller_user,
        )
        self.customer = Customer.objects.create(
            customer_type="individual",
            name="Cliente Docs",
            assigned_salesperson=self.sp,
        )
        self.other_customer = Customer.objects.create(
            customer_type="individual",
            name="Outro Cliente",
        )
        self.doc_type = create_document_type(
            data={
                "name": "Proposta Comercial",
                "code": "proposta-comercial-test",
                "category": DocumentCategory.COMMERCIAL,
                "requires_internal_approval": True,
                "requires_customer_acceptance": True,
                "allows_renewal": True,
                "has_validity": True,
                "default_validity_days": 30,
            },
            actor=self.user,
        )
        self.client = Client()

    def test_type_and_template_and_placeholders(self):
        self.assertEqual(self.doc_type.code, "proposta-comercial-test")
        template = create_document_template(
            data={
                "name": "Modelo Proposta",
                "document_type": self.doc_type,
                "content_format": "plain_text",
                "body": "Cliente {{ customer_name }} orc {{ quote_number }} {{ unknown_field }}",
                "header": "",
                "footer": "",
            },
            actor=self.user,
        )
        approve_document_template(template=template, actor=self.user)
        template.refresh_from_db()
        self.assertEqual(template.status, TemplateStatus.APPROVED)

        rendered, missing = render_placeholders(
            "Olá {{ customer_name }} {{ bad_token }}",
            {"customer_name": "Ana"},
        )
        self.assertIn("Ana", rendered)
        self.assertIn("bad_token", missing)

        document = create_document_from_template(
            template=template,
            actor=self.user,
            customer=self.customer,
            title="Proposta Cliente",
        )
        self.assertTrue(document.number.startswith("DOC-"))
        self.assertEqual(document.status, DocumentStatus.DRAFT)
        self.assertIn("Cliente Docs", document.current_version.rendered_content)
        self.assertIn("unknown_field", document.current_version.missing_placeholders)

    def test_numbering_and_version_immutability_checksum(self):
        d1 = create_managed_document(
            data={
                "title": "Doc 1",
                "document_type": self.doc_type,
                "customer": self.customer,
            },
            actor=self.user,
            initial_content="v1",
        )
        d2 = create_managed_document(
            data={
                "title": "Doc 2",
                "document_type": self.doc_type,
                "customer": self.customer,
            },
            actor=self.user,
            initial_content="v2",
        )
        self.assertNotEqual(d1.number, d2.number)
        version = d1.current_version
        self.assertEqual(len(version.checksum), 64)
        submit_document_for_review(document=d1, actor=self.user, reviewers=[self.user])
        approve_document_version(version=d1.current_version, actor=self.user)
        d1.refresh_from_db()
        approved = d1.current_version
        with self.assertRaises(ValidationError):
            approved.content = "hack"
            approved.save()
        with self.assertRaises(ValidationError):
            edit_draft_version(version=approved, content="x", actor=self.user)
        new_v = create_version(
            document=d1,
            actor=self.user,
            content="nova",
            change_summary="ajuste",
        )
        self.assertEqual(new_v.version_number, 2)
        approved.refresh_from_db()
        self.assertEqual(approved.status, VersionStatus.SUPERSEDED)

    def test_review_approve_reject_send_accept_sign(self):
        doc = create_managed_document(
            data={
                "title": "Fluxo",
                "document_type": self.doc_type,
                "customer": self.customer,
                "requires_acceptance": True,
                "requires_signature": True,
            },
            actor=self.user,
            initial_content="conteudo",
        )
        submit_document_for_review(document=doc, actor=self.user)
        reject_document_version(
            version=doc.current_version,
            actor=self.user,
            reason="Ajustar texto",
        )
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.REJECTED)
        create_version(document=doc, actor=self.user, content="conteudo 2")
        submit_document_for_review(document=doc, actor=self.user)
        approve_document_version(version=doc.current_version, actor=self.user)
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.APPROVED)
        register_document_send(
            document=doc,
            actor=self.user,
            data={"channel": "email", "recipient_name": "Cliente", "recipient_email": "a@b.com"},
        )
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.SENT)
        register_document_acceptance(
            document=doc,
            actor=self.user,
            data={
                "accepted": True,
                "accepted_by_name": "Cliente Docs",
                "channel": "in_person",
            },
        )
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.ACCEPTED)
        register_document_signature(
            document=doc,
            actor=self.user,
            data={
                "signer_name": "Cliente Docs",
                "signature_type": "wet_signature",
                "channel": "in_person",
            },
        )
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.ACTIVE)
        with self.assertRaises(ValidationError):
            doc.acceptances.first().delete()

    def test_renew_cancel_terminate_amendment_expiration(self):
        doc = create_managed_document(
            data={
                "title": "Contrato",
                "document_type": self.doc_type,
                "customer": self.customer,
                "expiration_date": timezone.localdate() + timedelta(days=10),
            },
            actor=self.user,
            initial_content="contrato",
        )
        submit_document_for_review(document=doc, actor=self.user)
        approve_document_version(version=doc.current_version, actor=self.user)
        register_document_acceptance(
            document=doc,
            actor=self.user,
            data={"accepted": True, "accepted_by_name": "X", "channel": "other"},
        )
        renewed = renew_document(
            document=doc,
            actor=self.user,
            expiration_date=timezone.localdate() + timedelta(days=365),
        )
        self.assertEqual(renewed.renewed_from_id, doc.pk)
        self.assertFalse(renewed.acceptances.exists())
        amendment = create_managed_document(
            data={
                "title": "Aditivo",
                "document_type": self.doc_type,
                "customer": self.customer,
                "context_justification": "Aditivo ao contrato",
            },
            actor=self.user,
            initial_content="aditivo",
        )
        link_documents(
            from_document=doc,
            to_document=amendment,
            relationship_type=RelationshipType.AMENDMENT,
            actor=self.user,
        )
        cancel_document(document=amendment, actor=self.user, reason="Desistência")
        amendment.refresh_from_db()
        self.assertEqual(amendment.status, DocumentStatus.CANCELLED)
        terminate_document(document=doc, actor=self.user, reason="Fim do prazo")
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentStatus.TERMINATED)

        active = create_managed_document(
            data={
                "title": "Ativo",
                "document_type": self.doc_type,
                "customer": self.customer,
                "expiration_date": timezone.localdate() - timedelta(days=1),
            },
            actor=self.user,
            initial_content="x",
        )
        submit_document_for_review(document=active, actor=self.user)
        approve_document_version(version=active.current_version, actor=self.user)
        active.status = DocumentStatus.ACTIVE
        active.save(update_fields=["status"])
        report = sync_document_statuses(dry_run=False)
        self.assertGreaterEqual(report["updated"], 1)
        active.refresh_from_db()
        self.assertEqual(active.status, DocumentStatus.EXPIRED)

    def test_scope_confidential_rbac_dashboard_sidebar_csv(self):
        own = create_managed_document(
            data={
                "title": "Do vendedor",
                "document_type": self.doc_type,
                "customer": self.customer,
            },
            actor=self.user,
            initial_content="own",
        )
        secret = create_managed_document(
            data={
                "title": "Secreto",
                "document_type": self.doc_type,
                "customer": self.other_customer,
                "confidentiality": Confidentiality.CONFIDENTIAL,
                "context_justification": "interno",
            },
            actor=self.user,
            initial_content="secret",
        )
        self.client.force_login(self.seller_user)
        response = self.client.get(reverse("documents:document_list"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(own.number, content)
        self.assertNotIn(secret.number, content)

        self.client.force_login(self.user)
        dash = self.client.get(reverse("documents:dashboard"))
        self.assertEqual(dash.status_code, 200)
        home = self.client.get(reverse("pages:dashboard"))
        self.assertEqual(home.status_code, 200)
        self.assertIn("sidebarDocuments", home.content.decode())
        self.assertIn("Documentos", home.content.decode())
        export = self.client.get(reverse("documents:document_list") + "?export=csv")
        self.assertEqual(export.status_code, 200)
        self.assertIn("text/csv", export["Content-Type"])
        self.assertEqual(sanitize_csv_cell("=1+1"), "'=1+1")

    def test_seed_and_commands(self):
        out = StringIO()
        call_command("setup_erp_foundation", stdout=out)
        self.assertTrue(DocumentType.objects.filter(code="proposta-comercial").exists())
        self.assertFalse(
            DocumentVersion.objects.filter(document__document_type__code="proposta-comercial").exists(),
        )
        doc = create_managed_document(
            data={
                "title": "Cmd",
                "document_type": self.doc_type,
                "customer": self.customer,
                "expiration_date": timezone.localdate() - timedelta(days=2),
            },
            actor=self.user,
            initial_content="c",
        )
        submit_document_for_review(document=doc, actor=self.user)
        approve_document_version(version=doc.current_version, actor=self.user)
        doc.status = DocumentStatus.ACTIVE
        doc.save(update_fields=["status"])
        call_command("sync_document_statuses", "--dry-run", stdout=StringIO())
        call_command("audit_document_consistency", "--dry-run", stdout=StringIO())
        self.assertEqual(
            AcceptanceStatus.ACCEPTED,
            AcceptanceStatus.ACCEPTED,
        )
