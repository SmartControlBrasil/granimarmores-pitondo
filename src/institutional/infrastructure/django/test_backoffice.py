import tempfile
from decimal import Decimal
from unittest import mock
from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import Client
from django.test import TestCase
from django.test import override_settings
from django.urls import resolve
from django.urls import reverse
from django.utils import timezone
from django.core import mail

from src.institutional.infrastructure.django.models import ContactRequest
from src.institutional.infrastructure.django.models import ContactRequestAuditLog
from src.institutional.infrastructure.django.models import ContactRequestNote
from src.institutional.infrastructure.django.models import Opportunity
from src.institutional.infrastructure.django.models import OpportunityAuditLog
from src.institutional.infrastructure.django.models import Quote
from src.institutional.infrastructure.django.models import QuoteItem
from src.institutional.infrastructure.django.models import QuoteSequence
from src.institutional.infrastructure.django.models import QuoteDocument
from src.institutional.infrastructure.django.models import QuoteDelivery
from src.institutional.application.services.access_policy import ADMINISTRATOR
from src.institutional.application.services.access_policy import SALES_MANAGER
from src.institutional.application.services.access_policy import SALESPERSON
from src.institutional.application.services.access_policy import VIEWER


def make_lead(**overrides):
    data = {
        "nome": "Lead Cliente",
        "telefone": "11999990000",
        "email": "lead@example.com",
        "cidade": "São Paulo",
        "ambiente": "Cozinha",
        "medidas": "2,40m",
        "mensagem": "Solicitação de teste para bancada.",
    }
    data.update(overrides)
    return ContactRequest.objects.create(**data)


class BackofficeTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="operador",
            email="operador@example.com",
            password="senha-segura-123",
        )
        self.other_user = user_model.objects.create_user(
            username="vendedor",
            email="vendedor@example.com",
            password="senha-segura-123",
        )
        perms = Permission.objects.filter(
            content_type__app_label="institutional",
            codename__in=[
                "view_contactrequest",
                "change_contactrequest",
                "assign_contactrequest",
                "add_contactrequestnote",
                "view_contactrequestauditlog",
            ],
        )
        call_command("setup_backoffice_roles", verbosity=0)
        self.user.groups.add(Group.objects.get(name=ADMINISTRATOR))
        self.other_user.groups.add(Group.objects.get(name=SALESPERSON))
        self.user.user_permissions.set(perms)
        self.lead = make_lead(nome="Ana Cliente", status=ContactRequest.Status.NEW)

    def test_panel_requires_login(self):
        response = self.client.get(reverse("backoffice:dashboard"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertTrue(response.url.startswith(reverse("backoffice:login")))

    def test_valid_login_works(self):
        response = self.client.post(
            reverse("backoffice:login"),
            {"username": "operador", "password": "senha-segura-123"},
        )

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, reverse("backoffice:dashboard"))

    def test_anonymous_cannot_access_leads(self):
        response = self.client.get(reverse("backoffice:lead_list"))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn(reverse("backoffice:login"), response.url)

    def test_login_logout_urls_resolve(self):
        self.assertEqual(reverse("backoffice:login"), "/app/login/")
        self.assertEqual(reverse("backoffice:logout"), "/app/logout/")
        self.assertEqual(resolve("/app/login/").view_name, "backoffice:login")
        self.assertEqual(resolve("/app/logout/").view_name, "backoffice:logout")

    def test_dashboard_uses_real_counts(self):
        make_lead(status=ContactRequest.Status.CONTACTED)
        make_lead(status=ContactRequest.Status.QUALIFIED)
        make_lead(status=ContactRequest.Status.CLOSED)
        make_lead(status=ContactRequest.Status.DISCARDED)
        self.client.force_login(self.user)

        response = self.client.get(reverse("backoffice:dashboard"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "Novo")
        self.assertContains(response, "Recebidos nos últimos 7 dias")

    def test_lead_list_returns_real_leads_ordered_by_recent(self):
        older = make_lead(nome="Lead Antigo")
        ContactRequest.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=2),
        )
        newer = make_lead(nome="Lead Novo")
        self.client.force_login(self.user)

        response = self.client.get(reverse("backoffice:lead_list"))
        leads = list(response.context["page_obj"].object_list)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(leads[0].pk, newer.pk)
        self.assertContains(response, "Lead Novo")
        self.assertContains(response, "Lead Antigo")

    def test_lead_list_search_filter_and_pagination(self):
        for index in range(30):
            make_lead(
                nome=f"Lead {index}",
                telefone=f"11999{index:03d}",
                status=ContactRequest.Status.CONTACTED if index == 3 else ContactRequest.Status.NEW,
            )
        self.client.force_login(self.user)

        search_response = self.client.get(reverse("backoffice:lead_list"), {"q": "Lead 3"})
        status_response = self.client.get(
            reverse("backoffice:lead_list"),
            {"status": ContactRequest.Status.CONTACTED},
        )
        page_response = self.client.get(reverse("backoffice:lead_list"))

        self.assertContains(search_response, "Lead 3")
        self.assertNotContains(search_response, "Lead 4")
        self.assertContains(status_response, "Lead 3")
        self.assertEqual(len(page_response.context["page_obj"].object_list), 25)

    def test_lead_detail_displays_data(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("backoffice:lead_detail", args=[self.lead.pk]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, self.lead.nome)
        self.assertContains(response, self.lead.telefone)
        self.assertContains(response, self.lead.mensagem)

    def test_valid_status_change_generates_audit_log(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("backoffice:lead_status", args=[self.lead.pk]),
            {"status": ContactRequest.Status.CONTACTED},
        )

        self.assertRedirects(response, reverse("backoffice:lead_detail", args=[self.lead.pk]))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, ContactRequest.Status.CONTACTED)
        self.assertTrue(
            ContactRequestAuditLog.objects.filter(
                contact_request=self.lead,
                actor=self.user,
                action=ContactRequestAuditLog.Action.STATUS_CHANGED,
            ).exists(),
        )

    def test_invalid_status_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("backoffice:lead_status", args=[self.lead.pk]),
            {"status": "invalido"},
        )

        self.assertRedirects(response, reverse("backoffice:lead_detail", args=[self.lead.pk]))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, ContactRequest.Status.NEW)
        self.assertFalse(ContactRequestAuditLog.objects.filter(action=ContactRequestAuditLog.Action.STATUS_CHANGED).exists())

    def test_status_change_does_not_accept_get(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("backoffice:lead_status", args=[self.lead.pk]))

        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, ContactRequest.Status.NEW)

    def test_valid_assignment_generates_audit_log(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("backoffice:lead_assign", args=[self.lead.pk]),
            {"assigned_to": self.other_user.pk},
        )

        self.assertRedirects(response, reverse("backoffice:lead_detail", args=[self.lead.pk]))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.assigned_to, self.other_user)
        self.assertTrue(
            ContactRequestAuditLog.objects.filter(
                contact_request=self.lead,
                action=ContactRequestAuditLog.Action.ASSIGNED,
                new_value=self.other_user.username,
            ).exists(),
        )

    def test_invalid_assignment_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("backoffice:lead_assign", args=[self.lead.pk]),
            {"assigned_to": 99999},
        )

        self.assertRedirects(response, reverse("backoffice:lead_detail", args=[self.lead.pk]))
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.assigned_to)
        self.assertFalse(ContactRequestAuditLog.objects.filter(action=ContactRequestAuditLog.Action.ASSIGNED).exists())

    def test_note_creation_sets_author_and_audit_log(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("backoffice:lead_note", args=[self.lead.pk]),
            {"content": "Cliente pediu retorno no período da manhã."},
        )

        self.assertRedirects(response, reverse("backoffice:lead_detail", args=[self.lead.pk]))
        note = ContactRequestNote.objects.get()
        self.assertEqual(note.author, self.user)
        self.assertEqual(note.contact_request, self.lead)
        self.assertTrue(
            ContactRequestAuditLog.objects.filter(
                contact_request=self.lead,
                action=ContactRequestAuditLog.Action.NOTE_ADDED,
            ).exists(),
        )

    def test_post_requires_csrf_when_csrf_checks_are_enabled(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(
            reverse("backoffice:lead_status", args=[self.lead.pk]),
            {"status": ContactRequest.Status.CONTACTED},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, ContactRequest.Status.NEW)

    def test_user_without_permission_cannot_change_status(self):
        user_model = get_user_model()
        limited = user_model.objects.create_user(
            username="limitado",
            password="senha-segura-123",
        )
        limited.user_permissions.add(Permission.objects.get(codename="view_contactrequest"))
        self.client.force_login(limited)

        response = self.client.post(
            reverse("backoffice:lead_status", args=[self.lead.pk]),
            {"status": ContactRequest.Status.CONTACTED},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, ContactRequest.Status.NEW)


class BackofficeRoleScopeTests(TestCase):
    def setUp(self):
        call_command("setup_backoffice_roles", verbosity=0)
        user_model = get_user_model()
        self.admin = user_model.objects.create_user("admin", password="senha-segura-123")
        self.manager = user_model.objects.create_user("gerente", password="senha-segura-123")
        self.seller = user_model.objects.create_user("vendedor", password="senha-segura-123")
        self.other_seller = user_model.objects.create_user("outro", password="senha-segura-123")
        self.viewer = user_model.objects.create_user("visualizador", password="senha-segura-123")
        self.no_group = user_model.objects.create_user("semgrupo", password="senha-segura-123")
        self.superuser = user_model.objects.create_superuser("root", "root@example.com", "senha-segura-123")
        self.admin.groups.add(Group.objects.get(name=ADMINISTRATOR))
        self.manager.groups.add(Group.objects.get(name=SALES_MANAGER))
        self.seller.groups.add(Group.objects.get(name=SALESPERSON))
        self.other_seller.groups.add(Group.objects.get(name=SALESPERSON))
        self.viewer.groups.add(Group.objects.get(name=VIEWER))
        self.own_lead = make_lead(nome="Lead Próprio", assigned_to=self.seller)
        self.other_lead = make_lead(nome="Lead Outro", assigned_to=self.other_seller)
        self.unassigned_lead = make_lead(nome="Lead Sem Responsável")

    def login(self, user):
        self.client.force_login(user)

    def test_admin_sees_all_and_can_write(self):
        self.login(self.admin)

        list_response = self.client.get(reverse("backoffice:lead_list"))
        status_response = self.client.post(
            reverse("backoffice:lead_status", args=[self.other_lead.pk]),
            {"status": ContactRequest.Status.CONTACTED},
        )
        assign_response = self.client.post(
            reverse("backoffice:lead_assign", args=[self.unassigned_lead.pk]),
            {"assigned_to": self.seller.pk},
        )
        note_response = self.client.post(
            reverse("backoffice:lead_note", args=[self.other_lead.pk]),
            {"content": "Nota administrativa."},
        )

        self.assertContains(list_response, "Lead Próprio")
        self.assertContains(list_response, "Lead Outro")
        self.assertContains(list_response, "Lead Sem Responsável")
        self.assertEqual(status_response.status_code, HTTPStatus.FOUND)
        self.assertEqual(assign_response.status_code, HTTPStatus.FOUND)
        self.assertEqual(note_response.status_code, HTTPStatus.FOUND)
        self.assertTrue(ContactRequestNote.objects.filter(author=self.admin).exists())

    def test_manager_sees_all_and_can_assign_change_and_note(self):
        self.login(self.manager)

        list_response = self.client.get(reverse("backoffice:lead_list"))
        status_response = self.client.post(
            reverse("backoffice:lead_status", args=[self.other_lead.pk]),
            {"status": ContactRequest.Status.QUALIFIED},
        )
        assign_response = self.client.post(
            reverse("backoffice:lead_assign", args=[self.unassigned_lead.pk]),
            {"assigned_to": self.seller.pk},
        )

        self.assertContains(list_response, "Lead Outro")
        self.assertEqual(status_response.status_code, HTTPStatus.FOUND)
        self.assertEqual(assign_response.status_code, HTTPStatus.FOUND)

    def test_salesperson_sees_only_own_leads_and_can_work_only_own(self):
        self.login(self.seller)

        list_response = self.client.get(reverse("backoffice:lead_list"))
        own_detail = self.client.get(reverse("backoffice:lead_detail", args=[self.own_lead.pk]))
        other_detail = self.client.get(reverse("backoffice:lead_detail", args=[self.other_lead.pk]))
        unassigned_detail = self.client.get(reverse("backoffice:lead_detail", args=[self.unassigned_lead.pk]))
        status_response = self.client.post(
            reverse("backoffice:lead_status", args=[self.own_lead.pk]),
            {"status": ContactRequest.Status.CONTACTED},
        )
        note_response = self.client.post(
            reverse("backoffice:lead_note", args=[self.own_lead.pk]),
            {"content": "Conversei com o cliente."},
        )
        assign_response = self.client.post(
            reverse("backoffice:lead_assign", args=[self.own_lead.pk]),
            {"assigned_to": self.other_seller.pk},
        )

        self.assertContains(list_response, "Lead Próprio")
        self.assertNotContains(list_response, "Lead Outro")
        self.assertNotContains(list_response, "Lead Sem Responsável")
        self.assertEqual(own_detail.status_code, HTTPStatus.OK)
        self.assertEqual(other_detail.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(unassigned_detail.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(status_response.status_code, HTTPStatus.FOUND)
        self.assertEqual(note_response.status_code, HTTPStatus.FOUND)
        self.assertEqual(assign_response.status_code, HTTPStatus.FOUND)
        self.own_lead.refresh_from_db()
        self.assertEqual(self.own_lead.assigned_to, self.seller)

    def test_viewer_can_read_all_but_cannot_write(self):
        self.login(self.viewer)

        list_response = self.client.get(reverse("backoffice:lead_list"))
        detail_response = self.client.get(reverse("backoffice:lead_detail", args=[self.other_lead.pk]))
        status_response = self.client.post(
            reverse("backoffice:lead_status", args=[self.other_lead.pk]),
            {"status": ContactRequest.Status.CONTACTED},
        )
        assign_response = self.client.post(
            reverse("backoffice:lead_assign", args=[self.other_lead.pk]),
            {"assigned_to": self.seller.pk},
        )
        note_response = self.client.post(
            reverse("backoffice:lead_note", args=[self.other_lead.pk]),
            {"content": "Tentativa de nota."},
        )

        self.assertContains(list_response, "Lead Próprio")
        self.assertContains(list_response, "Lead Outro")
        self.assertEqual(detail_response.status_code, HTTPStatus.OK)
        self.assertEqual(status_response.status_code, HTTPStatus.FOUND)
        self.assertEqual(assign_response.status_code, HTTPStatus.FOUND)
        self.assertEqual(note_response.status_code, HTTPStatus.FOUND)
        self.assertFalse(ContactRequestNote.objects.exists())
        self.other_lead.refresh_from_db()
        self.assertEqual(self.other_lead.status, ContactRequest.Status.NEW)

    def test_user_without_group_is_denied_after_login(self):
        self.login(self.no_group)

        response = self.client.get(reverse("backoffice:dashboard"))

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_superuser_has_total_access_without_group(self):
        self.login(self.superuser)

        response = self.client.get(reverse("backoffice:lead_detail", args=[self.unassigned_lead.pk]))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "Lead Sem Responsável")

    def test_dashboard_search_and_filters_respect_salesperson_scope(self):
        self.login(self.seller)

        dashboard_response = self.client.get(reverse("backoffice:dashboard"))
        search_response = self.client.get(reverse("backoffice:lead_list"), {"q": "Outro"})
        status_response = self.client.get(
            reverse("backoffice:lead_list"),
            {"status": ContactRequest.Status.NEW},
        )
        page_response = self.client.get(reverse("backoffice:lead_list"), {"assigned_to": self.other_seller.pk})

        self.assertContains(dashboard_response, "1")
        self.assertNotContains(search_response, "Lead Outro")
        self.assertContains(status_response, "Lead Próprio")
        self.assertNotContains(page_response, "Lead Outro")

    def test_assign_rejects_viewer_inactive_and_unknown_users(self):
        self.login(self.manager)
        inactive = get_user_model().objects.create_user("inativo", password="senha-segura-123", is_active=False)

        viewer_response = self.client.post(
            reverse("backoffice:lead_assign", args=[self.unassigned_lead.pk]),
            {"assigned_to": self.viewer.pk},
        )
        inactive_response = self.client.post(
            reverse("backoffice:lead_assign", args=[self.unassigned_lead.pk]),
            {"assigned_to": inactive.pk},
        )
        unknown_response = self.client.post(
            reverse("backoffice:lead_assign", args=[self.unassigned_lead.pk]),
            {"assigned_to": 99999},
        )

        self.assertEqual(viewer_response.status_code, HTTPStatus.FOUND)
        self.assertEqual(inactive_response.status_code, HTTPStatus.FOUND)
        self.assertEqual(unknown_response.status_code, HTTPStatus.FOUND)
        self.unassigned_lead.refresh_from_db()
        self.assertIsNone(self.unassigned_lead.assigned_to)

    def test_profile_page_displays_operational_role(self):
        self.login(self.seller)

        response = self.client.get(reverse("backoffice:profile"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "Vendedor")
        self.assertContains(response, self.seller.username)


class SetupBackofficeRolesCommandTests(TestCase):
    def test_command_is_idempotent(self):
        call_command("setup_backoffice_roles", verbosity=0)
        first_groups = {
            group.name: set(group.permissions.values_list("codename", flat=True))
            for group in Group.objects.filter(name__in=[ADMINISTRATOR, SALES_MANAGER, SALESPERSON, VIEWER])
        }

        call_command("setup_backoffice_roles", verbosity=0)
        second_groups = {
            group.name: set(group.permissions.values_list("codename", flat=True))
            for group in Group.objects.filter(name__in=[ADMINISTRATOR, SALES_MANAGER, SALESPERSON, VIEWER])
        }

        self.assertEqual(Group.objects.filter(name__in=[ADMINISTRATOR, SALES_MANAGER, SALESPERSON, VIEWER]).count(), 4)
        self.assertEqual(first_groups, second_groups)
        self.assertIn("assign_contactrequest", first_groups[ADMINISTRATOR])
        self.assertIn("add_opportunity", first_groups[SALES_MANAGER])
        self.assertIn("add_quote", first_groups[SALESPERSON])
        self.assertIn("view_quote", first_groups[VIEWER])
        self.assertIn("add_quotedocument", first_groups[SALESPERSON])
        self.assertIn("view_quotedocument", first_groups[VIEWER])
        self.assertNotIn("assign_contactrequest", first_groups[SALESPERSON])
        self.assertNotIn("change_contactrequest", first_groups[VIEWER])



class CommercialOpportunityTests(TestCase):
    def setUp(self):
        call_command("setup_backoffice_roles", verbosity=0)
        user_model = get_user_model()
        self.manager = user_model.objects.create_user("gerente2", password="senha-segura-123")
        self.seller = user_model.objects.create_user("vendedor2", password="senha-segura-123")
        self.other_seller = user_model.objects.create_user("outro2", password="senha-segura-123")
        self.viewer = user_model.objects.create_user("visualizador2", password="senha-segura-123")
        self.manager.groups.add(Group.objects.get(name=SALES_MANAGER))
        self.seller.groups.add(Group.objects.get(name=SALESPERSON))
        self.other_seller.groups.add(Group.objects.get(name=SALESPERSON))
        self.viewer.groups.add(Group.objects.get(name=VIEWER))
        self.own_lead = make_lead(nome="Lead Comercial", assigned_to=self.seller, cidade="Campinas", ambiente="Bancada")
        self.other_lead = make_lead(nome="Lead de Outro", assigned_to=self.other_seller, cidade="Santos", ambiente="Escada")

    def login(self, user):
        self.client.force_login(user)

    def make_opportunity(self, lead=None, assigned_to=None, **overrides):
        lead = lead or self.own_lead
        data = {
            "contact_request": lead,
            "title": lead.ambiente,
            "customer_name": lead.nome,
            "customer_email": lead.email,
            "customer_phone": lead.telefone,
            "city": lead.cidade,
            "assigned_to": assigned_to if assigned_to is not None else lead.assigned_to,
            "created_by": self.manager,
        }
        data.update(overrides)
        return Opportunity.objects.create(**data)

    def test_lead_conversion_creates_opportunity_once_and_audit(self):
        self.login(self.seller)
        response = self.client.post(reverse("backoffice:lead_convert", args=[self.own_lead.pk]))
        duplicate = self.client.post(reverse("backoffice:lead_convert", args=[self.own_lead.pk]))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(Opportunity.objects.count(), 1)
        opportunity = Opportunity.objects.get()
        self.assertEqual(opportunity.contact_request, self.own_lead)
        self.assertEqual(opportunity.assigned_to, self.seller)
        self.assertEqual(opportunity.stage, Opportunity.Stage.QUALIFICATION)
        self.assertTrue(OpportunityAuditLog.objects.filter(opportunity=opportunity, action=OpportunityAuditLog.Action.OPPORTUNITY_CREATED).exists())
        self.assertEqual(duplicate.status_code, HTTPStatus.FOUND)
        self.assertEqual(Opportunity.objects.count(), 1)

    def test_salesperson_cannot_convert_other_lead_and_get_does_not_mutate(self):
        self.login(self.seller)
        get_response = self.client.get(reverse("backoffice:lead_convert", args=[self.own_lead.pk]))
        other_response = self.client.post(reverse("backoffice:lead_convert", args=[self.other_lead.pk]))

        self.assertEqual(get_response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)
        self.assertEqual(other_response.status_code, HTTPStatus.NOT_FOUND)
        self.assertFalse(Opportunity.objects.exists())

    def test_unassigned_lead_requires_responsible_on_conversion(self):
        lead = make_lead(nome="Sem Dono")
        self.login(self.manager)
        missing = self.client.post(reverse("backoffice:lead_convert", args=[lead.pk]), {})
        ok = self.client.post(reverse("backoffice:lead_convert", args=[lead.pk]), {"assigned_to": self.seller.pk})

        self.assertEqual(missing.status_code, HTTPStatus.FOUND)
        self.assertEqual(ok.status_code, HTTPStatus.FOUND)
        self.assertEqual(Opportunity.objects.get(contact_request=lead).assigned_to, self.seller)

    def test_scope_list_detail_and_idor_for_opportunities_and_quotes(self):
        own = self.make_opportunity()
        other = self.make_opportunity(lead=self.other_lead, assigned_to=self.other_seller)
        own_quote = Quote.objects.create(opportunity=own, number="ORC-2026-000001", created_by=self.seller)
        other_quote = Quote.objects.create(opportunity=other, number="ORC-2026-000002", created_by=self.other_seller)
        self.login(self.seller)

        list_response = self.client.get(reverse("backoffice:opportunity_list"))
        own_detail = self.client.get(reverse("backoffice:opportunity_detail", args=[own.pk]))
        other_detail = self.client.get(reverse("backoffice:opportunity_detail", args=[other.pk]))
        own_quote_detail = self.client.get(reverse("backoffice:quote_detail", args=[own_quote.pk]))
        other_quote_detail = self.client.get(reverse("backoffice:quote_detail", args=[other_quote.pk]))

        self.assertContains(list_response, "Lead Comercial")
        self.assertNotContains(list_response, "Lead de Outro")
        self.assertEqual(own_detail.status_code, HTTPStatus.OK)
        self.assertEqual(other_detail.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(own_quote_detail.status_code, HTTPStatus.OK)
        self.assertEqual(other_quote_detail.status_code, HTTPStatus.NOT_FOUND)

    def test_manager_sees_pipeline_grouped_and_filters(self):
        self.make_opportunity(stage=Opportunity.Stage.QUOTATION)
        self.make_opportunity(lead=self.other_lead, assigned_to=self.other_seller, stage=Opportunity.Stage.NEGOTIATION)
        self.login(self.manager)

        response = self.client.get(reverse("backoffice:opportunity_pipeline"), {"stage": Opportunity.Stage.QUOTATION})

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertContains(response, "Orçamento")
        self.assertContains(response, "Lead Comercial")
        self.assertNotContains(response, "Lead de Outro")

    def test_viewer_reads_but_cannot_change_stage_or_quote(self):
        opportunity = self.make_opportunity()
        quote = Quote.objects.create(opportunity=opportunity, number="ORC-2026-000010", created_by=self.seller)
        self.login(self.viewer)

        detail = self.client.get(reverse("backoffice:opportunity_detail", args=[opportunity.pk]))
        stage = self.client.post(reverse("backoffice:opportunity_stage", args=[opportunity.pk]), {"stage": Opportunity.Stage.NEGOTIATION})
        quote_post = self.client.post(reverse("backoffice:quote_detail", args=[quote.pk]), {})

        self.assertEqual(detail.status_code, HTTPStatus.OK)
        self.assertEqual(stage.status_code, HTTPStatus.FOUND)
        self.assertEqual(quote_post.status_code, HTTPStatus.FORBIDDEN)
        opportunity.refresh_from_db()
        self.assertEqual(opportunity.stage, Opportunity.Stage.QUALIFICATION)

    def test_quote_creation_numbering_revision_and_decimal_calculation_ignore_total(self):
        opportunity = self.make_opportunity()
        self.login(self.seller)
        create_response = self.client.post(reverse("backoffice:quote_new", args=[opportunity.pk]), {"notes": "Primeira proposta"})
        quote = Quote.objects.get()
        payload = {
            "validity_date": "",
            "discount_amount": "10.00",
            "notes": "Atualizada",
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-description": "Bancada em granito",
            "form-0-quantity": "2.500",
            "form-0-unit": QuoteItem.Unit.SQUARE_METER,
            "form-0-unit_price": "300.00",
            "form-0-total": "0.01",
            "form-1-description": "Instalação",
            "form-1-quantity": "1",
            "form-1-unit": QuoteItem.Unit.SERVICE,
            "form-1-unit_price": "200.00",
            "form-2-description": "",
            "form-3-description": "",
        }
        update_response = self.client.post(reverse("backoffice:quote_detail", args=[quote.pk]), payload)
        revision_response = self.client.post(reverse("backoffice:quote_revision", args=[quote.pk]))

        self.assertEqual(create_response.status_code, HTTPStatus.FOUND)
        self.assertEqual(update_response.status_code, HTTPStatus.FOUND)
        quote.refresh_from_db()
        self.assertEqual(quote.number, f"ORC-{timezone.localdate().year}-000001")
        self.assertEqual(quote.subtotal, Decimal("950.00"))
        self.assertEqual(quote.discount_amount, Decimal("10.00"))
        self.assertEqual(quote.total, Decimal("940.00"))
        self.assertEqual(quote.items.count(), 2)
        self.assertEqual(revision_response.status_code, HTTPStatus.FOUND)
        self.assertTrue(Quote.objects.filter(number=quote.number, revision=1).exists())
        self.assertEqual(QuoteSequence.objects.get(year=timezone.localdate().year).next_number, 2)

    def test_quote_discount_validation_and_item_scope(self):
        opportunity = self.make_opportunity()
        other = self.make_opportunity(lead=self.other_lead, assigned_to=self.other_seller)
        quote = Quote.objects.create(opportunity=opportunity, number="ORC-2026-000020", created_by=self.seller)
        other_quote = Quote.objects.create(opportunity=other, number="ORC-2026-000021", created_by=self.other_seller)
        other_item = QuoteItem.objects.create(quote=other_quote, description="Outro", quantity=1, unit_price=10, total=10)
        self.login(self.seller)
        payload = {
            "validity_date": "",
            "discount_amount": "100.00",
            "notes": "",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-id": str(other_item.pk),
            "form-0-description": "Tentativa",
            "form-0-quantity": "1",
            "form-0-unit": QuoteItem.Unit.UNIT,
            "form-0-unit_price": "10.00",
        }

        response = self.client.post(reverse("backoffice:quote_detail", args=[quote.pk]), payload)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertFalse(quote.items.exists())

    def test_quote_status_transitions_acceptance_and_invalid_transition(self):
        opportunity = self.make_opportunity(stage=Opportunity.Stage.NEGOTIATION)
        quote = Quote.objects.create(opportunity=opportunity, number="ORC-2026-000030", status=Quote.Status.SENT, created_by=self.seller)
        self.login(self.seller)

        invalid = self.client.post(reverse("backoffice:quote_status", args=[quote.pk]), {"status": Quote.Status.DRAFT})
        accepted = self.client.post(reverse("backoffice:quote_status", args=[quote.pk]), {"status": Quote.Status.ACCEPTED})

        self.assertEqual(invalid.status_code, HTTPStatus.FOUND)
        quote.refresh_from_db()
        self.assertEqual(quote.status, Quote.Status.ACCEPTED)
        opportunity.refresh_from_db()
        self.assertEqual(opportunity.stage, Opportunity.Stage.WON)
        self.assertEqual(opportunity.probability, 100)
        self.assertTrue(OpportunityAuditLog.objects.filter(opportunity=opportunity, action=OpportunityAuditLog.Action.QUOTE_ACCEPTED).exists())
        self.assertEqual(accepted.status_code, HTTPStatus.FOUND)

    def test_lost_requires_reason_and_dashboard_values_are_scoped(self):
        own = self.make_opportunity(estimated_value=Decimal("1000.00"))
        other = self.make_opportunity(lead=self.other_lead, assigned_to=self.other_seller, estimated_value=Decimal("9000.00"))
        self.login(self.seller)
        missing = self.client.post(reverse("backoffice:opportunity_stage", args=[own.pk]), {"stage": Opportunity.Stage.LOST})
        ok = self.client.post(reverse("backoffice:opportunity_stage", args=[own.pk]), {"stage": Opportunity.Stage.LOST, "lost_reason": Opportunity.LostReason.PRICE})
        dashboard = self.client.get(reverse("backoffice:dashboard"))

        self.assertEqual(missing.status_code, HTTPStatus.FOUND)
        own.refresh_from_db()
        self.assertEqual(own.stage, Opportunity.Stage.LOST)
        self.assertEqual(own.lost_reason, Opportunity.LostReason.PRICE)
        self.assertEqual(ok.status_code, HTTPStatus.FOUND)
        labels = {card["label"]: card["value"] for card in dashboard.context["cards"]}
        self.assertEqual(labels["Perdidos"], 1)
        self.assertEqual(labels["Valor em pipeline"], 0)
        other.refresh_from_db()
        self.assertEqual(other.stage, Opportunity.Stage.QUALIFICATION)



class QuoteDocumentFlowTests(TestCase):
    def setUp(self):
        self.tmp_media = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.tmp_media.name,
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        )
        self.settings_override.enable()
        call_command("setup_backoffice_roles", verbosity=0)
        user_model = get_user_model()
        self.manager = user_model.objects.create_user("docgerente", password="senha-segura-123")
        self.seller = user_model.objects.create_user("docvendedor", password="senha-segura-123")
        self.other_seller = user_model.objects.create_user("docoutro", password="senha-segura-123")
        self.viewer = user_model.objects.create_user("docviewer", password="senha-segura-123")
        self.manager.groups.add(Group.objects.get(name=SALES_MANAGER))
        self.seller.groups.add(Group.objects.get(name=SALESPERSON))
        self.other_seller.groups.add(Group.objects.get(name=SALESPERSON))
        self.viewer.groups.add(Group.objects.get(name=VIEWER))
        lead = make_lead(nome="Cliente PDF", email="cliente@example.com", assigned_to=self.seller, ambiente="Cozinha")
        self.opportunity = Opportunity.objects.create(
            contact_request=lead,
            title="Cozinha planejada",
            customer_name=lead.nome,
            customer_email=lead.email,
            customer_phone=lead.telefone,
            city=lead.cidade,
            assigned_to=self.seller,
            created_by=self.manager,
        )
        self.quote = Quote.objects.create(
            opportunity=self.opportunity,
            number="ORC-2026-000100",
            revision=0,
            status=Quote.Status.READY,
            discount_amount=Decimal("10.00"),
            created_by=self.seller,
        )
        QuoteItem.objects.create(quote=self.quote, description="Bancada", quantity=Decimal("2.000"), unit=QuoteItem.Unit.SQUARE_METER, unit_price=Decimal("500.00"), total=Decimal("1000.00"), position=1)

    def tearDown(self):
        self.settings_override.disable()
        self.tmp_media.cleanup()

    def login(self, user):
        self.client.force_login(user)

    def generate_document(self):
        self.login(self.seller)
        response = self.client.post(reverse("backoffice:quote_generate_document", args=[self.quote.pk]))
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        return QuoteDocument.objects.get()

    def test_preview_generation_download_and_idor(self):
        self.login(self.seller)
        preview = self.client.get(reverse("backoffice:quote_preview", args=[self.quote.pk]))
        document = self.generate_document()
        duplicate = self.client.post(reverse("backoffice:quote_generate_document", args=[self.quote.pk]))
        download = self.client.get(reverse("backoffice:quote_document_download", args=[self.quote.pk, document.pk]))
        self.client.force_login(self.other_seller)
        idor = self.client.get(reverse("backoffice:quote_document_download", args=[self.quote.pk, document.pk]))

        self.assertEqual(preview.status_code, HTTPStatus.OK)
        self.assertContains(preview, "Orçamento ORC-2026-000100")
        self.assertEqual(duplicate.status_code, HTTPStatus.FOUND)
        self.assertEqual(QuoteDocument.objects.count(), 1)
        self.assertTrue(document.file.storage.exists(document.file.name))
        self.assertEqual(len(document.checksum), 64)
        self.assertEqual(len(document.snapshot_fingerprint), 64)
        self.assertEqual(document.revision, self.quote.revision)
        self.assertEqual(download.status_code, HTTPStatus.OK)
        self.assertEqual(idor.status_code, HTTPStatus.NOT_FOUND)
        self.assertTrue(OpportunityAuditLog.objects.filter(action=OpportunityAuditLog.Action.QUOTE_DOCUMENT_GENERATED).exists())

    def test_immutability_and_revision_copy_after_sent_or_accepted(self):
        document = self.generate_document()
        self.client.post(reverse("backoffice:quote_send", args=[self.quote.pk, document.pk]), {"recipient": "cliente@example.com"})
        self.quote.refresh_from_db()
        edit_response = self.client.post(reverse("backoffice:quote_detail", args=[self.quote.pk]), {})
        revision_response = self.client.post(reverse("backoffice:quote_revision", args=[self.quote.pk]))
        revision = Quote.objects.get(number=self.quote.number, revision=1)

        self.assertEqual(self.quote.status, Quote.Status.SENT)
        self.assertEqual(edit_response.status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(revision_response.status_code, HTTPStatus.FOUND)
        self.assertEqual(revision.status, Quote.Status.DRAFT)
        self.assertEqual(revision.items.count(), self.quote.items.count())
        self.assertEqual(revision.total, self.quote.total)
        self.assertEqual(QuoteDocument.objects.get(pk=document.pk).snapshot_data["items"][0]["description"], "Bancada")
        self.assertTrue(OpportunityAuditLog.objects.filter(action=OpportunityAuditLog.Action.QUOTE_REVISION_CREATED).exists())

    def test_send_success_failure_and_duplicate_protection(self):
        document = self.generate_document()
        send = self.client.post(reverse("backoffice:quote_send", args=[self.quote.pk, document.pk]), {"recipient": "cliente@example.com"})
        duplicate = self.client.post(reverse("backoffice:quote_send", args=[self.quote.pk, document.pk]), {"recipient": "cliente@example.com"})

        self.assertEqual(send.status_code, HTTPStatus.FOUND)
        self.quote.refresh_from_db()
        document.refresh_from_db()
        self.opportunity.refresh_from_db()
        self.assertEqual(self.quote.status, Quote.Status.SENT)
        self.assertEqual(document.status, QuoteDocument.Status.SENT)
        self.assertEqual(self.opportunity.stage, Opportunity.Stage.QUOTATION_SENT)
        self.assertEqual(duplicate.status_code, HTTPStatus.FOUND)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(QuoteDelivery.objects.filter(status=QuoteDelivery.Status.SENT).count(), 1)

        resend = self.client.post(reverse("backoffice:quote_send", args=[self.quote.pk, document.pk]), {"recipient": "cliente@example.com", "allow_resend": "1"})

        self.assertEqual(resend.status_code, HTTPStatus.FOUND)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(QuoteDelivery.objects.filter(status=QuoteDelivery.Status.SENT).count(), 2)

    def test_send_failure_keeps_quote_generated_and_records_failed_delivery(self):
        document = self.generate_document()
        with mock.patch("django.core.mail.EmailMessage.send", side_effect=RuntimeError("SMTP indisponível")):
            response = self.client.post(reverse("backoffice:quote_send", args=[self.quote.pk, document.pk]), {"recipient": "cliente@example.com"})

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.quote.refresh_from_db()
        document.refresh_from_db()
        delivery = QuoteDelivery.objects.get()
        self.assertEqual(self.quote.status, Quote.Status.READY)
        self.assertEqual(document.status, QuoteDocument.Status.GENERATED)
        self.assertEqual(delivery.status, QuoteDelivery.Status.FAILED)
        self.assertIn("SMTP", delivery.error_message)
        self.assertTrue(OpportunityAuditLog.objects.filter(action=OpportunityAuditLog.Action.QUOTE_SEND_FAILED).exists())

    def test_permissions_viewer_downloads_but_cannot_generate_send_or_void(self):
        document = self.generate_document()
        self.login(self.viewer)
        download = self.client.get(reverse("backoffice:quote_document_download", args=[self.quote.pk, document.pk]))
        generate = self.client.post(reverse("backoffice:quote_generate_document", args=[self.quote.pk]))
        send = self.client.post(reverse("backoffice:quote_send", args=[self.quote.pk, document.pk]), {"recipient": "cliente@example.com"})
        void = self.client.post(reverse("backoffice:quote_document_void", args=[self.quote.pk, document.pk]))

        self.assertEqual(download.status_code, HTTPStatus.OK)
        self.assertEqual(generate.status_code, HTTPStatus.FOUND)
        self.assertEqual(send.status_code, HTTPStatus.FOUND)
        self.assertEqual(void.status_code, HTTPStatus.FOUND)
        document.refresh_from_db()
        self.quote.refresh_from_db()
        self.assertEqual(document.status, QuoteDocument.Status.GENERATED)
        self.assertEqual(self.quote.status, Quote.Status.READY)

    def test_void_generated_document(self):
        document = self.generate_document()
        response = self.client.post(reverse("backoffice:quote_document_void", args=[self.quote.pk, document.pk]))
        document.refresh_from_db()

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(document.status, QuoteDocument.Status.VOID)
        self.assertTrue(OpportunityAuditLog.objects.filter(action=OpportunityAuditLog.Action.QUOTE_DOCUMENT_VOIDED).exists())
