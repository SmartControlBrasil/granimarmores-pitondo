from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.urls import resolve
from django.urls import reverse

from audit.models import AuditEvent
from customers.models import Customer


PAGE_DIR = "institutional/pages/"
HTML = ".html"


def template(name):
    return f"{PAGE_DIR}{name}{HTML}"


def valid_contact_data(**overrides):
    data = {
        "nome": "Maria Silva",
        "telefone": "(11) 99999-0000",
        "email": "maria@example.com",
        "cidade": "São Paulo",
        "ambiente": "Cozinha",
        "mensagem": "Bancada em granito para cozinha com ilha central.",
        "privacidade": "on",
        "website": "",
    }
    data.update(overrides)
    return data


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="Granimármores Pitondo <contato@granimarmorespitondo.com.br>",
    CONTACT_RECIPIENT_EMAIL="contato@granimarmorespitondo.com.br",
)
class InstitutionalPagesTests(TestCase):
    pages = {
        "home": ("/", template("home"), "Mármores e granitos"),
        "sobre": ("/sobre/", template("about"), "Sobre a Granimármores Pitondo"),
        "cozinhas": ("/cozinhas/", template("cozinhas"), "Cozinhas que unem beleza e funcionalidade"),
        "escadas": ("/escadas/", template("escadas"), "Escadas em Mármore e Granito"),
        "areas_gourmet": ("/areas-gourmet/", template("areas_gourmet"), "Áreas Gourmet"),
        "banheiros": ("/banheiros/", template("banheiros"), "Banheiros que unem"),
        "projetos_comerciais": ("/projetos-comerciais/", template("projetos_comerciais"), "Projetos"),
        "blog": ("/blog/", template("blog"), "Blog sobre mármores"),
        "contato": ("/contato/", template("contact"), "Solicite uma avaliação"),
    }

    articles = {
        "escolher-pedra-bancada-cozinha": "Como escolher a pedra ideal",
        "marmore-ou-granito-diferencas": "Mármore ou granito",
        "cuidados-conservar-bancadas-pedra": "Cuidados para conservar",
    }

    def post_contact(self, **overrides):
        return self.client.post(
            reverse("institutional:contato"),
            data=valid_contact_data(**overrides),
        )

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

    def test_contact_form_get_has_csrf_and_fields(self):
        response = self.client.get(reverse("institutional:contato"))

        self.assertEqual(response.status_code, 200)
        for field in ["nome", "telefone", "email", "cidade", "ambiente", "mensagem", "privacidade", "website"]:
            self.assertContains(response, f'name="{field}"')
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_valid_post_persists_customer_and_sends_notification_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post_contact()

        self.assertRedirects(response, reverse("institutional:contato"))
        customer = Customer.objects.get()
        self.assertEqual(customer.name, "Maria Silva")
        self.assertEqual(customer.mobile_phone, "(11) 99999-0000")
        self.assertEqual(customer.email, "maria@example.com")
        self.assertIn("Site institucional", customer.notes)
        self.assertIn("Cozinha", customer.notes)
        self.assertIn("Bancada em granito", customer.notes)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["contato@granimarmorespitondo.com.br"])
        self.assertEqual(
            message.from_email,
            "Granimármores Pitondo <contato@granimarmorespitondo.com.br>",
        )
        self.assertEqual(message.reply_to, ["maria@example.com"])
        self.assertIn("Nova solicitação de orçamento pelo site - Maria Silva - Cozinha", message.subject)
        self.assertIn("Telefone / WhatsApp: (11) 99999-0000", message.body)
        self.assertIn("Origem:" + "\n" + "Site institucional", message.body)
        self.assertTrue(AuditEvent.objects.filter(action="public_contact_received").exists())
        self.assertTrue(AuditEvent.objects.filter(action="public_contact_notification", status="success").exists())

    def test_smtp_is_not_called_before_commit(self):
        with patch("src.institutional.presentation.views.send_public_contact_notification") as mocked:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                response = self.post_contact()

        self.assertRedirects(response, reverse("institutional:contato"))
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(len(callbacks), 1)
        mocked.assert_not_called()

    def test_valid_post_without_customer_email_persists_and_sends_without_reply_to(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post_contact(email="")

        self.assertRedirects(response, reverse("institutional:contato"))
        customer = Customer.objects.get()
        self.assertEqual(customer.email, "")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].reply_to, [])
        self.assertIn("E-mail: Não informado", mail.outbox[0].body)

    def test_required_fields_are_validated_in_backend(self):
        response = self.client.post(reverse("institutional:contato"), data={})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Preencha os campos obrigatórios")
        self.assertFalse(Customer.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_privacy_is_required_in_backend(self):
        response = self.post_contact(privacidade="")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirme o consentimento")
        self.assertFalse(Customer.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_email_is_validated_in_backend(self):
        response = self.post_contact(email="email-invalido")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe um e-mail válido")
        self.assertFalse(Customer.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_honeypot_filled_redirects_without_creating_customer_or_email(self):
        response = self.post_contact(website="https://spam.example")

        self.assertRedirects(response, reverse("institutional:contato"))
        self.assertFalse(Customer.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_two_requests_same_phone_keep_one_customer_and_two_histories(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.post_contact(ambiente="Cozinha", mensagem="Mensagem A")
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post_contact(ambiente="Banheiro", mensagem="Mensagem B")

        self.assertRedirects(response, reverse("institutional:contato"))
        self.assertEqual(Customer.objects.count(), 1)
        customer = Customer.objects.get()
        self.assertIn("Tipo de ambiente: Cozinha", customer.notes)
        self.assertIn("Mensagem A", customer.notes)
        self.assertIn("Tipo de ambiente: Banheiro", customer.notes)
        self.assertIn("Mensagem B", customer.notes)
        self.assertEqual(
            AuditEvent.objects.filter(
                object_type="Customer",
                object_id=str(customer.pk),
                action__in=["public_contact_received", "public_contact_deduplicated"],
            ).count(),
            2,
        )
        self.assertEqual(len(mail.outbox), 2)

    def test_phone_email_conflict_does_not_merge_customers(self):
        Customer.objects.create(
            customer_type=Customer.CustomerType.INDIVIDUAL,
            name="Cliente A",
            mobile_phone="11999999999",
            email="a@example.com",
        )
        Customer.objects.create(
            customer_type=Customer.CustomerType.INDIVIDUAL,
            name="Cliente B",
            mobile_phone="11888888888",
            email="b@example.com",
        )

        response = self.post_contact(
            telefone="(11) 99999-9999",
            email="b@example.com",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Não foi possível validar os dados informados")
        self.assertEqual(Customer.objects.count(), 2)
        self.assertEqual(Customer.objects.get(name="Cliente A").email, "a@example.com")
        self.assertEqual(Customer.objects.get(name="Cliente B").mobile_phone, "11888888888")
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="public_contact_identity_conflict",
                status="failed",
            ).exists(),
        )

    def test_smtp_failure_keeps_customer_and_does_not_return_500(self):
        with (
            patch(
                "src.institutional.application.contact_requests.EmailMessage.send",
                side_effect=RuntimeError("SMTP indisponível"),
            ),
            patch("src.institutional.application.contact_requests.logger.exception"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.post_contact()

        self.assertRedirects(response, reverse("institutional:contato"))
        customer = Customer.objects.get()
        self.assertIn("Bancada em granito", customer.notes)
        self.assertTrue(
            AuditEvent.objects.filter(
                object_type="Customer",
                object_id=str(customer.pk),
                action="public_contact_notification",
                status="failed",
            ).exists(),
        )

    def test_database_failure_does_not_send_smtp(self):
        self.client.raise_request_exception = False
        with patch(
            "src.institutional.presentation.views.persist_public_contact_request",
            side_effect=RuntimeError("falha banco"),
        ):
            response = self.post_contact()

        self.assertEqual(response.status_code, 500)
        self.assertFalse(Customer.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_submission_is_visible_to_commercial_customer_flow(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.post_contact()

        self.assertTrue(
            Customer.objects.filter(
                name="Maria Silva",
                notes__contains="[Site institucional] Solicitação de orçamento",
                is_active=True,
            ).exists(),
        )


@override_settings(SITE_DOMAIN="granimarmorespitondo.com.br")
class InstitutionalSitemapTests(TestCase):
    PUBLIC_PATHS = (
        "/",
        "/sobre/",
        "/solucoes/",
        "/projetos/",
        "/materiais/",
        "/cozinhas/",
        "/banheiros/",
        "/escadas/",
        "/areas-gourmet/",
        "/projetos-comerciais/",
        "/blog/",
        "/contato/",
        "/orcamento/",
        "/blog/escolher-pedra-bancada-cozinha/",
        "/blog/marmore-ou-granito-diferencas/",
        "/blog/cuidados-conservar-bancadas-pedra/",
    )

    PRIVATE_PATH_FRAGMENTS = (
        "/admin/",
        "/accounts/",
        "/users/",
        "/painel/",
        "/painel/comercial/orcamentos/",
        "/painel/clientes/",
        "/painel/administracao/",
    )

    def test_sitemap_returns_xml_with_public_urls(self):
        response = self.client.get("/sitemap.xml")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/xml")
        content = response.content.decode()

        self.assertIn('xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"', content)
        self.assertIn("<urlset", content)

        for path in self.PUBLIC_PATHS:
            with self.subTest(path=path):
                self.assertIn(
                    f"https://granimarmorespitondo.com.br{path}",
                    content,
                )

        for fragment in self.PRIVATE_PATH_FRAGMENTS:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, content)

    def test_sitemap_uses_reverse_for_institutional_routes(self):
        response = self.client.get("/sitemap.xml")
        content = response.content.decode()

        expected_urls = {
            reverse("institutional:home"),
            reverse("institutional:sobre"),
            reverse("institutional:cozinhas"),
            reverse("institutional:banheiros"),
            reverse("institutional:escadas"),
            reverse("institutional:areas_gourmet"),
            reverse("institutional:projetos_comerciais"),
            reverse("institutional:blog"),
            reverse("institutional:contato"),
            reverse(
                "institutional:blog_article",
                kwargs={"slug": "escolher-pedra-bancada-cozinha"},
            ),
        }

        for path in expected_urls:
            with self.subTest(path=path):
                self.assertIn(f"https://granimarmorespitondo.com.br{path}", content)


@override_settings(SITE_DOMAIN="granimarmorespitondo.com.br")
class InstitutionalSeoTests(TestCase):
    def test_robots_txt_returns_plain_text(self):
        response = self.client.get("/robots.txt")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        content = response.content.decode()

        self.assertIn("Sitemap: https://granimarmorespitondo.com.br/sitemap.xml", content)
        self.assertIn("Disallow: /painel/", content)
        self.assertIn("Disallow: /admin/", content)
        self.assertIn("Disallow: /accounts/", content)
        self.assertTrue(content.endswith("\n"))

    def test_home_contains_canonical_open_graph_and_schema(self):
        response = self.client.get(reverse("institutional:home"))
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<link rel="canonical" href="https://granimarmorespitondo.com.br/">')
        self.assertContains(response, 'name="description"')
        self.assertContains(response, "Soluções sob medida em mármore, granito e superfícies especiais")
        self.assertContains(response, 'property="og:title"')
        self.assertContains(response, 'property="og:description"')
        self.assertContains(response, 'property="og:url"')
        self.assertContains(response, 'property="og:image"')
        self.assertContains(response, 'name="twitter:card" content="summary_large_image"')
        self.assertContains(response, '"@type": "LocalBusiness"')

    def test_internal_page_has_unique_canonical_and_description(self):
        response = self.client.get(reverse("institutional:cozinhas"))
        html = response.content.decode()

        self.assertContains(
            response,
            '<link rel="canonical" href="https://granimarmorespitondo.com.br/cozinhas/">',
        )
        self.assertContains(
            response,
            "Projetos de cozinhas com bancadas, ilhas, pias e revestimentos",
        )
        self.assertNotContains(
            response,
            '<link rel="canonical" href="https://granimarmorespitondo.com.br/">',
        )

    def test_blog_article_has_article_open_graph(self):
        response = self.client.get(
            reverse(
                "institutional:blog_article",
                kwargs={"slug": "marmore-ou-granito-diferencas"},
            ),
        )
        html = response.content.decode()

        self.assertContains(response, 'property="og:type" content="article"')
        self.assertContains(
            response,
            '<link rel="canonical" href="https://granimarmorespitondo.com.br/blog/marmore-ou-granito-diferencas/">',
        )

    def test_sitemap_still_excludes_private_urls(self):
        response = self.client.get("/sitemap.xml")
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("/painel/", content)
        self.assertNotIn("/admin/", content)
        self.assertNotIn("/accounts/", content)

