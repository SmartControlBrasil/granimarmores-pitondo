import json
from dataclasses import dataclass

from django.conf import settings
from django.urls import reverse


DEFAULT_ROBOTS = "index, follow"
DEFAULT_OG_TYPE = "website"
DEFAULT_TWITTER_CARD = "summary_large_image"
DEFAULT_OG_LOCALE = "pt_BR"

DEFAULT_SOCIAL_IMAGE = "institutional/images/logo-gp.webp"

SITE_PROFILE = {
    "company_name": "Granimármores Pitondo",
    "site_name": "Granimármores Pitondo",
    "phone": "(11) 94024-1328",
    "street_address": "Av. do Cursino, 3342",
    "address_locality": "Jardim da Saúde",
    "address_city": "São Paulo",
    "address_region": "SP",
    "address_country": "BR",
    "default_social_image": DEFAULT_SOCIAL_IMAGE,
}


@dataclass(frozen=True)
class PageSeo:
    title: str
    description: str
    og_type: str = DEFAULT_OG_TYPE
    og_image: str | None = None
    robots: str = DEFAULT_ROBOTS


DEFAULT_PAGE_SEO = PageSeo(
    title="Granimármores Pitondo | Mármores, Granitos e Projetos Sob Medida",
    description=(
        "Mármores, granitos e superfícies sob medida para cozinhas, banheiros, "
        "escadas, áreas gourmet e projetos comerciais em São Paulo."
    ),
)

PAGE_SEO = {
    "home": PageSeo(
        title="Granimármores Pitondo | Mármores, Granitos e Projetos Sob Medida",
        description=(
            "Soluções sob medida em mármore, granito e superfícies especiais para "
            "cozinhas, banheiros, escadas, áreas gourmet e projetos comerciais."
        ),
    ),
    "sobre": PageSeo(
        title="Sobre a Granimármores Pitondo | Qualidade e Acabamento Sob Medida",
        description=(
            "Conheça a Granimármores Pitondo e nosso trabalho com medição, fabricação "
            "e instalação de mármores, granitos e superfícies sob medida."
        ),
    ),
    "services": PageSeo(
        title="Soluções em Mármore e Granito | Granimármores Pitondo",
        description=(
            "Bancadas, revestimentos, escadas e ambientes completos em mármore, granito "
            "e superfícies especiais, com projeto, corte e acabamento sob medida."
        ),
    ),
    "projects": PageSeo(
        title="Projetos em Pedra Natural | Granimármores Pitondo",
        description=(
            "Veja ambientes produzidos em mármore e granito para cozinhas, banheiros, "
            "escadas, áreas gourmet e projetos comerciais sob medida."
        ),
    ),
    "materials": PageSeo(
        title="Materiais: Mármore, Granito e Superfícies | Granimármores Pitondo",
        description=(
            "Conheça mármore, granito, quartzito e superfícies especiais usadas em "
            "bancadas, revestimentos e projetos residenciais e comerciais."
        ),
    ),
    "cozinhas": PageSeo(
        title="Cozinhas Planejadas em Mármore e Granito | Granimármores Pitondo",
        description=(
            "Projetos de cozinhas com bancadas, ilhas, pias e revestimentos em mármore, "
            "granito, quartzo e superfícies especiais. Solicite seu orçamento."
        ),
    ),
    "banheiros": PageSeo(
        title="Banheiros Planejados em Mármore e Granito | Granimármores Pitondo",
        description=(
            "Banheiros e lavabos com bancadas, lavatórios, cubas, nichos e revestimentos "
            "em mármore, granito, quartzo e superfícies especiais."
        ),
    ),
    "escadas": PageSeo(
        title="Escadas em Mármore e Granito | Granimármores Pitondo",
        description=(
            "Escadas sob medida em mármore e granito, com degraus, espelhos, patamares, "
            "soleiras e acabamento especializado para projetos residenciais e comerciais."
        ),
    ),
    "areas_gourmet": PageSeo(
        title="Áreas Gourmet em Mármore e Granito | Granimármores Pitondo",
        description=(
            "Bancadas, ilhas, pias e revestimentos para áreas gourmet, produzidos sob "
            "medida em mármore, granito e superfícies especiais."
        ),
    ),
    "projetos_comerciais": PageSeo(
        title="Projetos Comerciais em Mármore e Granito | Granimármores Pitondo",
        description=(
            "Soluções em mármore, granito e superfícies especiais para recepções, lojas, "
            "escritórios, clínicas, restaurantes e ambientes corporativos."
        ),
    ),
    "blog": PageSeo(
        title="Blog | Mármores, Granitos e Cuidados com Pedras",
        description=(
            "Conteúdos sobre mármore, granito, bancadas, cozinhas, banheiros, áreas "
            "gourmet, conservação e planejamento de projetos sob medida."
        ),
    ),
    "contato": PageSeo(
        title="Contato e Orçamento | Granimármores Pitondo",
        description=(
            "Entre em contato com a Granimármores Pitondo e solicite uma avaliação para "
            "cozinhas, banheiros, escadas, áreas gourmet e projetos comerciais."
        ),
    ),
    "quotation": PageSeo(
        title="Solicite um Orçamento | Granimármores Pitondo",
        description=(
            "Envie medidas, fotos ou a planta do seu projeto e receba orientação da "
            "Granimármores Pitondo para bancadas e ambientes em pedra sob medida."
        ),
    ),
}

BLOG_ARTICLE_SEO = {
    "escolher-pedra-bancada-cozinha": PageSeo(
        title="Escolha da Pedra para Bancada de Cozinha | Granimármores Pitondo",
        description=(
            "Critérios para escolher mármore, granito, quartzo e superfícies especiais "
            "para bancadas de cozinha com segurança técnica."
        ),
        og_type="article",
        og_image="institutional/images/blog/mulher-escolhendo-pedra.webp",
    ),
    "marmore-ou-granito-diferencas": PageSeo(
        title="Mármore ou Granito: Diferenças e Aplicações | Granimármores Pitondo",
        description=(
            "Entenda diferenças entre mármore e granito e saiba por que a escolha "
            "depende da aplicação, manutenção e estética do projeto."
        ),
        og_type="article",
        og_image="institutional/images/blog/marmore-ou-granito.webp",
    ),
    "cuidados-conservar-bancadas-pedra": PageSeo(
        title="Cuidados com Bancadas e Superfícies de Pedra | Granimármores Pitondo",
        description=(
            "Veja cuidados básicos para limpeza e conservação de bancadas, lavatórios, "
            "escadas e superfícies de pedra no dia a dia."
        ),
        og_type="article",
        og_image="institutional/images/blog/cuidados-com-pedra.webp",
    ),
}


def site_base_url():
    return f"https://{settings.SITE_DOMAIN}"


def absolute_url(path_or_static):
    if path_or_static.startswith(("http://", "https://")):
        return path_or_static
    if path_or_static.startswith("/"):
        return f"{site_base_url()}{path_or_static}"
    return f"{site_base_url()}/{path_or_static}"


def absolute_static_url(static_path):
    return absolute_url(f"/static/{static_path.lstrip('/')}")


def resolve_page_seo(request):
    match = getattr(request, "resolver_match", None)
    if not match or match.namespace != "institutional":
        return DEFAULT_PAGE_SEO

    if match.url_name == "blog_article":
        slug = match.kwargs.get("slug", "")
        return BLOG_ARTICLE_SEO.get(slug, DEFAULT_PAGE_SEO)

    return PAGE_SEO.get(match.url_name, DEFAULT_PAGE_SEO)


def resolve_canonical_url(request):
    match = getattr(request, "resolver_match", None)
    if match and match.namespace == "institutional":
        if match.url_name == "blog_article":
            slug = match.kwargs.get("slug", "")
            if slug in BLOG_ARTICLE_SEO:
                return absolute_url(reverse("institutional:blog_article", kwargs={"slug": slug}))
        elif match.url_name:
            try:
                return absolute_url(reverse(f"institutional:{match.url_name}"))
            except Exception:
                pass
    return absolute_url(request.path)


def build_local_business_schema():
    profile = SITE_PROFILE
    schema = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": profile["company_name"],
        "url": site_base_url(),
        "telephone": profile["phone"],
        "image": absolute_static_url(profile["default_social_image"]),
        "address": {
            "@type": "PostalAddress",
            "streetAddress": profile["street_address"],
            "addressLocality": profile["address_locality"],
            "addressRegion": profile["address_region"],
            "addressCountry": profile["address_country"],
        },
    }
    return json.dumps(schema, ensure_ascii=False)


def build_site_seo_context(request):
    page = resolve_page_seo(request)
    og_image = page.og_image or SITE_PROFILE["default_social_image"]
    canonical_url = resolve_canonical_url(request)

    return {
        "company_name": SITE_PROFILE["company_name"],
        "site_name": SITE_PROFILE["site_name"],
        "base_url": site_base_url(),
        "phone": SITE_PROFILE["phone"],
        "street_address": SITE_PROFILE["street_address"],
        "address_locality": SITE_PROFILE["address_locality"],
        "address_city": SITE_PROFILE["address_city"],
        "address_region": SITE_PROFILE["address_region"],
        "address_country": SITE_PROFILE["address_country"],
        "page_title": page.title,
        "page_description": page.description,
        "canonical_url": canonical_url,
        "og_type": page.og_type,
        "og_title": page.title,
        "og_description": page.description,
        "og_url": canonical_url,
        "og_image": absolute_static_url(og_image),
        "og_locale": DEFAULT_OG_LOCALE,
        "twitter_card": DEFAULT_TWITTER_CARD,
        "robots": page.robots,
        "local_business_schema": build_local_business_schema(),
    }


def build_robots_txt():
    domain = settings.SITE_DOMAIN
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /painel/",
        "",
        f"Sitemap: https://{domain}/sitemap.xml",
        "",
    ]
    return "\n".join(lines)
