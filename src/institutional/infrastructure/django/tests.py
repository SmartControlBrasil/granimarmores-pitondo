import json
from html.parser import HTMLParser
from unittest.mock import patch
from urllib.parse import urlsplit

from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.urls import resolve
from django.urls import reverse

from audit.models import AuditEvent
from customers.models import Customer


PAGE_DIR = "institutional/pages/"
HTML = ".html"
CANONICAL_BASE_URL = "https://granimarmorespitondo.com.br"


class SeoHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_head = False
        self.in_json_ld = False
        self.canonical_tags = []
        self.head_canonical_tags = []
        self.og_url = None
        self.json_ld_scripts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "head":
            self.in_head = True
        elif tag == "link" and attrs.get("rel") == "canonical":
            self.canonical_tags.append(attrs)
            if self.in_head:
                self.head_canonical_tags.append(attrs)
        elif tag == "meta" and attrs.get("property") == "og:url":
            self.og_url = attrs.get("content")
        elif tag == "script" and attrs.get("type") == "application/ld+json":
            self.in_json_ld = True

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False
        elif tag == "script":
            self.in_json_ld = False

    def handle_data(self, data):
        if self.in_json_ld:
            self.json_ld_scripts.append(data.strip())


def parse_seo_html(response):
    parser = SeoHTMLParser()
    parser.feed(response.content.decode())
    return parser


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

    def test_header_includes_mobile_restricted_area_link(self):
        response = self.client.get(reverse("institutional:home"))

        self.assertContains(response, 'class="mobile-restricted-area"')
        self.assertContains(response, reverse("account_login"))
        self.assertContains(response, "ÁREA RESTRITA")
        self.assertContains(response, 'class="btn-main fx-slide"')

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
    PUBLIC_CANONICALS = (
        ("home", {}, "/"),
        ("sobre", {}, "/sobre/"),
        ("services", {}, "/solucoes/"),
        ("cozinhas", {}, "/cozinhas/"),
        ("banheiros", {}, "/banheiros/"),
        ("escadas", {}, "/escadas/"),
        ("areas_gourmet", {}, "/areas-gourmet/"),
        ("projetos_comerciais", {}, "/projetos-comerciais/"),
        ("projects", {}, "/projetos/"),
        ("materials", {}, "/materiais/"),
        ("blog", {}, "/blog/"),
        ("contato", {}, "/contato/"),
        ("quotation", {}, "/orcamento/"),
        (
            "blog_article",
            {"slug": "escolher-pedra-bancada-cozinha"},
            "/blog/escolher-pedra-bancada-cozinha/",
        ),
        (
            "blog_article",
            {"slug": "marmore-ou-granito-diferencas"},
            "/blog/marmore-ou-granito-diferencas/",
        ),
        (
            "blog_article",
            {"slug": "cuidados-conservar-bancadas-pedra"},
            "/blog/cuidados-conservar-bancadas-pedra/",
        ),
    )

    TRACKING_QUERY_STRINGS = (
        ("home", {}, "gclid=123", "/"),
        ("services", {}, "utm_source=google&utm_campaign=ads", "/solucoes/"),
        ("projects", {}, "fbclid=abc", "/projetos/"),
    )

    def canonical_url(self, path):
        return f"{CANONICAL_BASE_URL}{path}"

    def parse_json_ld(self, parser):
        self.assertEqual(len(parser.json_ld_scripts), 1)
        return json.loads(parser.json_ld_scripts[0])

    def assert_canonical(self, response, expected_url):
        parser = parse_seo_html(response)
        self.assertEqual(len(parser.canonical_tags), 1)
        self.assertEqual(len(parser.head_canonical_tags), 1)
        self.assertEqual(parser.canonical_tags[0].get("href"), expected_url)

        parsed = urlsplit(expected_url)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "granimarmorespitondo.com.br")
        self.assertNotEqual(parsed.netloc[:4], "www.")
        self.assertEqual(parsed.query, "")
        self.assertEqual(parsed.fragment, "")
        self.assertTrue(parsed.path.endswith("/"))
        return parser

    def find_schema_entity(self, graph, entity_type):
        for entity in graph:
            value = entity.get("@type")
            if value == entity_type or (isinstance(value, list) and entity_type in value):
                return entity
        return None

    def test_public_html_pages_render_exactly_one_head_canonical(self):
        for route, kwargs, path in self.PUBLIC_CANONICALS:
            with self.subTest(route=route, path=path):
                response = self.client.get(reverse(f"institutional:{route}", kwargs=kwargs))

                self.assertEqual(response.status_code, 200)
                self.assert_canonical(response, self.canonical_url(path))

    def test_tracking_parameters_are_removed_from_canonical(self):
        for route, kwargs, query_string, path in self.TRACKING_QUERY_STRINGS:
            with self.subTest(route=route, query_string=query_string):
                url = reverse(f"institutional:{route}", kwargs=kwargs)
                response = self.client.get(f"{url}?{query_string}")

                self.assertEqual(response.status_code, 200)
                self.assert_canonical(response, self.canonical_url(path))

    def test_contact_and_quotation_have_different_canonicals(self):
        contact = self.client.get(reverse("institutional:contato"))
        quotation = self.client.get(reverse("institutional:quotation"))

        contact_parser = self.assert_canonical(contact, self.canonical_url("/contato/"))
        quotation_parser = self.assert_canonical(quotation, self.canonical_url("/orcamento/"))
        self.assertNotEqual(
            contact_parser.canonical_tags[0]["href"],
            quotation_parser.canonical_tags[0]["href"],
        )

    def test_canonical_og_json_ld_breadcrumb_and_sitemap_are_consistent(self):
        sitemap_response = self.client.get("/sitemap.xml")
        sitemap = sitemap_response.content.decode()

        for route, kwargs, path in self.PUBLIC_CANONICALS:
            with self.subTest(route=route, path=path):
                expected_url = self.canonical_url(path)
                response = self.client.get(reverse(f"institutional:{route}", kwargs=kwargs))
                parser = self.assert_canonical(response, expected_url)
                data = self.parse_json_ld(parser)
                graph = data["@graph"]

                self.assertEqual(parser.og_url, expected_url)
                self.assertIn(expected_url, sitemap)

                breadcrumb = self.find_schema_entity(graph, "BreadcrumbList")
                if route == "home":
                    self.assertIsNone(breadcrumb)
                else:
                    self.assertIsNotNone(breadcrumb)
                    items = breadcrumb["itemListElement"]
                    self.assertEqual(items[-1]["item"], expected_url)

                service = self.find_schema_entity(graph, "Service")
                if route in {"cozinhas", "banheiros", "escadas", "areas_gourmet", "projetos_comerciais"}:
                    self.assertIsNotNone(service)
                    self.assertEqual(service["url"], expected_url)
                else:
                    self.assertIsNone(service)

                blog_posting = self.find_schema_entity(graph, "BlogPosting")
                if route == "blog_article":
                    self.assertIsNotNone(blog_posting)
                    self.assertEqual(blog_posting["url"], expected_url)
                    self.assertEqual(blog_posting["mainEntityOfPage"], expected_url)
                else:
                    self.assertIsNone(blog_posting)

    def test_non_html_public_responses_do_not_render_canonical(self):
        for path in ("/robots.txt", "/sitemap.xml"):
            with self.subTest(path=path):
                response = self.client.get(path)
                parser = parse_seo_html(response)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(parser.canonical_tags, [])

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
        self.assertContains(response, '"LocalBusiness"')

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

    def test_local_business_logo_file_exists(self):
        import os
        from django.conf import settings
        logo_path = os.path.join(settings.BASE_DIR, "static/institutional/images/logo-gp.webp")
        self.assertTrue(os.path.exists(logo_path), f"Logo não encontrado no caminho físico: {logo_path}")

    def test_json_ld_schemas_are_valid_and_comprehensive(self):
        import json
        pages_to_test = [
            ("home", {}),
            ("sobre", {}),
            ("services", {}),
            ("projects", {}),
            ("materials", {}),
            ("contato", {}),
            ("quotation", {}),
            ("blog", {}),
            ("cozinhas", {}),
            ("blog_article", {"slug": "marmore-ou-granito-diferencas"}),
        ]

        for route, kwargs in pages_to_test:
            with self.subTest(route=route):
                if kwargs:
                    url = reverse(f"institutional:{route}", kwargs=kwargs)
                else:
                    url = reverse(f"institutional:{route}")

                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()

                # Encontrar a tag script
                start_marker = '<script type="application/ld+json">'
                end_marker = '</script>'
                self.assertIn(start_marker, html)

                start_idx = html.find(start_marker) + len(start_marker)
                end_idx = html.find(end_marker, start_idx)
                json_str = html[start_idx:end_idx].strip()

                # Fazer parse real
                data = json.loads(json_str)
                self.assertEqual(data.get("@context"), "https://schema.org")
                self.assertIn("@graph", data)

                graph = data["@graph"]

                # Garantir ausência de Review ou AggregateRating conforme as regras da Fase 3
                for entity in graph:
                    self.assertNotIn(entity.get("@type"), ["Review", "AggregateRating"])

                # Encontrar entidades
                business = next((x for x in graph if "LocalBusiness" in x.get("@type", []) or x.get("@type") == "LocalBusiness"), None)
                website = next((x for x in graph if x.get("@type") == "WebSite"), None)
                breadcrumb = next((x for x in graph if x.get("@type") == "BreadcrumbList"), None)
                blog_posting = next((x for x in graph if x.get("@type") == "BlogPosting"), None)
                service = next((x for x in graph if x.get("@type") == "Service"), None)

                # Validar Business
                self.assertIsNotNone(business)
                self.assertEqual(business["@id"], "https://granimarmorespitondo.com.br/#business")
                self.assertEqual(business["name"], "Granimármores Pitondo")
                self.assertEqual(business["telephone"], "+55 11 94024-1328")
                self.assertEqual(business["address"]["streetAddress"], "Av. do Cursino, 3342 - Jardim da Saúde")
                self.assertEqual(business["address"]["addressLocality"], "São Paulo")
                self.assertIn("Marmoraria especializada", business["description"])
                self.assertTrue(business["url"].startswith("http"))
                self.assertTrue(business["logo"]["url"].startswith("http"))

                # Validar WebSite
                self.assertIsNotNone(website)
                self.assertEqual(website["@id"], "https://granimarmorespitondo.com.br/#website")
                self.assertEqual(website["publisher"]["@id"], "https://granimarmorespitondo.com.br/#business")

                # Validar Breadcrumbs (nas páginas internas)
                if route != "home":
                    self.assertIsNotNone(breadcrumb)
                    self.assertTrue(breadcrumb["@id"].endswith("#breadcrumb"))
                    elements = breadcrumb["itemListElement"]
                    self.assertTrue(len(elements) >= 2)
                    self.assertEqual(elements[0]["name"], "Início")
                    self.assertEqual(elements[0]["item"], "https://granimarmorespitondo.com.br")

                    # Checar sequencialidade de posições e URLs absolutas
                    for i, elem in enumerate(elements):
                        self.assertEqual(elem["position"], i + 1)
                        self.assertTrue(elem["item"].startswith("https://granimarmorespitondo.com.br"))

                    # Validar hierarquia semântica específica para serviços (Início > Soluções > Serviço)
                    if route == "cozinhas":
                        self.assertEqual(len(elements), 3)
                        self.assertEqual(elements[1]["name"], "Soluções")
                        self.assertEqual(elements[1]["item"], "https://granimarmorespitondo.com.br/solucoes/")
                        self.assertEqual(elements[2]["name"], "Cozinhas")
                        self.assertEqual(elements[2]["item"], "https://granimarmorespitondo.com.br/cozinhas/")

                # Validar BlogPosting
                if route == "blog_article":
                    self.assertIsNotNone(blog_posting)
                    self.assertTrue(blog_posting["@id"].endswith("#blogposting"))
                    self.assertEqual(blog_posting["publisher"]["@id"], "https://granimarmorespitondo.com.br/#business")
                    self.assertIn("marmore-ou-granito-diferencas", blog_posting["url"])
                    self.assertTrue(blog_posting["image"].startswith("http"))
                    self.assertNotIn("author", blog_posting) # Confirmar que não inventou autor

                # Validar Service
                if route == "cozinhas":
                    self.assertIsNotNone(service)
                    self.assertTrue(service["@id"].endswith("#service"))
                    self.assertEqual(service["provider"]["@id"], "https://granimarmorespitondo.com.br/#business")
                    self.assertIn("Cozinhas", service["name"])
                    self.assertTrue(service["url"].startswith("https://"))
