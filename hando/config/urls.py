# ruff: noqa
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include
from django.urls import path
from django.views import defaults as default_views
from django.views.generic import TemplateView

urlpatterns = [
    
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),
    # User management
    path("users/", include("hando.users.urls", namespace="users")),
    path("accounts/", include("allauth.urls")),
    path("erp/usuarios/", include("accounts.urls", namespace="accounts")),
    path("erp/acessos/", include("access_control.urls", namespace="access_control")),
    path("erp/auditoria/", include("audit.urls", namespace="audit")),
    path("erp/clientes/", include("customers.urls", namespace="customers")),
    path("erp/vendedores/", include("salespeople.urls", namespace="salespeople")),
    path("erp/materiais/", include("materials.urls", namespace="materials")),
    path("erp/orcamentos/", include("quotes.urls", namespace="quotes")),
    path("erp/ativos/", include("assets.urls", namespace="assets")),
    path("erp/veiculos/", include("fleet.urls", namespace="fleet")),
    path("erp/manutencao/", include("maintenance.urls", namespace="maintenance")),
    path("", include("hando.pages.urls", namespace="pages")),
    # Your stuff: custom urls includes go here
    # ...
    # Media files
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]


if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
