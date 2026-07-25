from unittest import mock

from django.test import TestCase
from django.test import override_settings
from django.urls import resolve, reverse

from src.institutional.infrastructure.django.models import ContactRequest


PAGE_DIR = "institutional/pages/"
HTML = ".html"


def template(name):
    return f"{PAGE_DIR}{name}{HTML}"


class InstitutionalPagesTests(TestCase):
    pages = {
        "home": ("/", template("home"), "Mármores e granitos"),
        "sobre": ("/sobre/", template("about"), "Sobre a Granimármores Pitondo"),
        "cozinhas": ("/cozinhas/", template("cozinhas"), "Cozinhas que unem beleza e funcionalidade"),
        "escadas": ("/escadas/", template("escadas"), "Escadas em Mármore e Granito"),
        "areas_gourmet": ("/areas-gourmet/", template("areas_gourmet"), "Áreas Gourmet"),
        "banheiros": ("/banheiros/", template("banheiros"), "Banheiros em"),
        "projetos_comerciais": ("/projetos-comerciais/", template("projetos_comerciais"), "Projetos"),
        "blog": ("/blog/", template("blog"), "Blog sobre mármores"),
        "contato": ("/contato/", template("contact"), "Solicite uma avaliação"),
    }

    articles = {
        "escolher-pedra-bancada-cozinha": "Como escolher a pedra ideal",
        "marmore-ou-granito-diferencas": "Mármore ou granito",
        "cuidados-conservar-bancadas-pedra": "Cuidados para conservar",
    }

    def test_pages_render_expected_template_and_content(self):
        for route_name, (path, template_name, title) in self.pages.items():
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(f"institutional:{route_name}"))
                html = response.content.decode()

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.request["PATH_INFO"], path)
                self.assertTemplateUsed(response, template_name)
                self.assertContains(response, title)
                self.assertNotContains(response, "institutional/" + "intrio/")
                self.assertNotContains(response, "Intr" + "io")
                self.assertNotRegex(html, r'href="[^"]+\.html"')

    def test_routes_resolve_by_name(self):
        for route_name, (path, _, _) in self.pages.items():
            with self.subTest(route_name=route_name):
                url = reverse(f"institutional:{route_name}")
                match = resolve(url)

                self.assertEqual(url, path)
                self.assertEqual(match.namespace, "institutional")
                self.assertEqual(match.url_name, route_name)

    def test_solution_submenu_and_main_menu(self):
        response = self.client.get(reverse("institutional:home"))
        self.assertContains(response, reverse("institutional:cozinhas"))
        self.assertContains(response, reverse("institutional:escadas"))
        self.assertContains(response, reverse("institutional:areas_gourmet"))
        self.assertContains(response, reverse("institutional:banheiros"))
        self.assertContains(response, reverse("institutional:projetos_comerciais"))
        self.assertNotContains(response, ">Projetos</a>")
        self.assertNotContains(response, ">Materiais</a>")

    def test_blog_articles_render(self):
        for slug, title in self.articles.items():
            with self.subTest(slug=slug):
                response = self.client.get(reverse("institutional:blog_article", args=[slug]))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, title)
                self.assertContains(response, reverse("institutional:contato"))

    def test_contact_form_has_csrf_and_validates_required_fields(self):
        response = self.client.get(reverse("institutional:contato"))
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, 'name="nome"')
        self.assertContains(response, 'name="telefone"')
        self.assertContains(response, 'name="ambiente"')
        self.assertContains(response, 'name="medidas"')

        post_response = self.client.post(reverse("institutional:contato"), data={})
        self.assertEqual(post_response.status_code, 200)
        self.assertContains(post_response, "Preencha os campos obrigatórios")


def valid_contact_data(**overrides):
    data = {
        "nome": "Maria Cliente",
        "telefone": "(11) 99999-0000",
        "email": "maria@example.com",
        "cidade": "São Paulo",
        "ambiente": "Cozinha",
        "medidas": "Bancada de 2,40m com recorte para cuba.",
        "mensagem": "Preciso de orçamento para bancada de cozinha com instalação.",
        "privacidade": "1",
        "website": "",
    }
    data.update(overrides)
    return data


class ContactRequestFlowTests(TestCase):
    def test_get_contact_page_returns_success(self):
        response = self.client.get(reverse("institutional:contato"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Solicite uma avaliação")

    def test_valid_post_creates_lead_and_redirects(self):
        response = self.client.post(
            reverse("institutional:contato"),
            data=valid_contact_data(),
            HTTP_USER_AGENT="pytest-browser",
            REMOTE_ADDR="127.0.0.1",
        )

        self.assertRedirects(response, reverse("institutional:contato"))
        lead = ContactRequest.objects.get()
        self.assertEqual(lead.nome, "Maria Cliente")
        self.assertEqual(lead.telefone, "(11) 99999-0000")
        self.assertEqual(lead.email, "maria@example.com")
        self.assertEqual(lead.cidade, "São Paulo")
        self.assertEqual(lead.ambiente, "Cozinha")
        self.assertEqual(lead.status, ContactRequest.Status.NEW)
        self.assertEqual(lead.source_path, reverse("institutional:contato"))
        self.assertEqual(lead.ip_address, "127.0.0.1")
        self.assertEqual(lead.user_agent, "pytest-browser")

    def test_invalid_post_does_not_create_lead(self):
        response = self.client.post(reverse("institutional:contato"), data={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactRequest.objects.count(), 0)
        self.assertContains(response, "Preencha os campos obrigatórios")

    def test_honeypot_blocks_spam_without_creating_lead(self):
        response = self.client.post(
            reverse("institutional:contato"),
            data=valid_contact_data(website="https://spam.example"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactRequest.objects.count(), 0)
        self.assertContains(response, "Não foi possível processar")

    @override_settings(CONTACT_NOTIFICATION_EMAIL="comercial@example.com")
    def test_smtp_failure_keeps_lead_saved(self):
        with mock.patch(
            "src.institutional.application.services.contact_notification.send_mail",
            side_effect=RuntimeError("SMTP indisponível"),
        ):
            response = self.client.post(
                reverse("institutional:contato"),
                data=valid_contact_data(),
            )

        self.assertRedirects(response, reverse("institutional:contato"))
        lead = ContactRequest.objects.get()
        self.assertIn("SMTP indisponível", lead.notification_error)
        self.assertIsNone(lead.notification_sent_at)
