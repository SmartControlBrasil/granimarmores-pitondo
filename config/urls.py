from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include
from django.urls import path

from src.institutional.presentation.robots import robots_txt
from src.institutional.presentation.sitemaps import sitemaps


urlpatterns = [
    path("admin/", admin.site.urls),
    path("robots.txt", robots_txt, name="robots_txt"),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="sitemap",
    ),
    path("accounts/", include("allauth.urls")),
    path("users/", include("hando.users.urls", namespace="users")),
    path("painel/comercial/", include("commercial.lead_urls", namespace="leads")),
    path("painel/comercial/orcamentos/", include("quotes.urls", namespace="quotes")),
    path("painel/clientes/", include("customers.urls", namespace="customers")),
    path(
        "painel/comercial/vendedores/",
        include("salespeople.urls", namespace="salespeople"),
    ),
    path("painel/cadastros/", include("materials.urls", namespace="materials")),
    path("painel/cadastros/", include("commercial.urls", namespace="commercial")),
    path("painel/patrimonio/ativos/", include("assets.urls", namespace="assets")),
    path("painel/patrimonio/veiculos/", include("fleet.urls", namespace="fleet")),
    path("painel/manutencao/", include("maintenance.urls", namespace="maintenance")),
    path("painel/administracao/", include("accounts.urls", namespace="accounts")),
    path(
        "painel/administracao/",
        include("access_control.urls", namespace="access_control"),
    ),
    path(
        "painel/administracao/auditoria/",
        include("audit.urls", namespace="audit"),
    ),
    path("painel/", include("hando.pages.urls", namespace="pages")),
    path("", include("src.institutional.presentation.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
