from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

# Slugs publicados em src.institutional.presentation.views.blog_article
BLOG_ARTICLE_SLUGS = (
    "escolher-pedra-bancada-cozinha",
    "marmore-ou-granito-diferencas",
    "cuidados-conservar-bancadas-pedra",
)

# Páginas estáticas públicas do namespace institutional (presentation/urls.py).
INSTITUTIONAL_STATIC_PAGES = (
    {"view_name": "institutional:home", "priority": 1.0, "changefreq": "weekly"},
    {"view_name": "institutional:sobre", "priority": 0.8, "changefreq": "monthly"},
    {"view_name": "institutional:services", "priority": 0.8, "changefreq": "monthly"},
    {"view_name": "institutional:projects", "priority": 0.7, "changefreq": "monthly"},
    {"view_name": "institutional:materials", "priority": 0.7, "changefreq": "monthly"},
    {"view_name": "institutional:cozinhas", "priority": 0.8, "changefreq": "monthly"},
    {"view_name": "institutional:banheiros", "priority": 0.8, "changefreq": "monthly"},
    {"view_name": "institutional:escadas", "priority": 0.8, "changefreq": "monthly"},
    {"view_name": "institutional:areas_gourmet", "priority": 0.8, "changefreq": "monthly"},
    {"view_name": "institutional:projetos_comerciais", "priority": 0.8, "changefreq": "monthly"},
    {"view_name": "institutional:blog", "priority": 0.8, "changefreq": "weekly"},
    {"view_name": "institutional:contato", "priority": 0.9, "changefreq": "monthly"},
    {"view_name": "institutional:politica_de_privacidade", "priority": 0.3, "changefreq": "yearly"},
    {"view_name": "institutional:quotation", "priority": 0.9, "changefreq": "monthly"},
)


class InstitutionalPublicSitemap(Sitemap):
    """Sitemap das páginas públicas do site institucional."""

    protocol = "https"

    def get_domain(self, site=None):
        return settings.SITE_DOMAIN

    def items(self):
        static_pages = list(INSTITUTIONAL_STATIC_PAGES)
        article_pages = [
            {
                "view_name": "institutional:blog_article",
                "slug": slug,
                "priority": 0.7,
                "changefreq": "monthly",
            }
            for slug in BLOG_ARTICLE_SLUGS
        ]
        return static_pages + article_pages

    def location(self, item):
        if "slug" in item:
            return reverse(item["view_name"], kwargs={"slug": item["slug"]})
        return reverse(item["view_name"])

    def priority(self, item):
        return item["priority"]

    def changefreq(self, item):
        return item["changefreq"]


sitemaps = {
    "institutional": InstitutionalPublicSitemap,
}
