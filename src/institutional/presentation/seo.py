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
    "email": "contato@granimarmorespitondo.com.br",
    "street_address": "Av. do Cursino, 3342",
    "address_locality": "Jardim da Saúde",
    "address_city": "São Paulo",
    "address_region": "SP",
    "postal_code": "04132-002",
    "address_country": "BR",
    "area_served": "São Paulo",
    "same_as": "https://www.instagram.com/granimarmorespitondo/",
    "default_social_image": DEFAULT_SOCIAL_IMAGE,
    "description": "Marmoraria especializada no corte, acabamento e instalação de pedras naturais e superfícies especiais para tampos, lavatórios, escadas e ambientes gourmet em São Paulo.",
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
        title="Marmoraria na Saúde e Zona Sul SP | Granimármores Pitondo",
        description=(
            "Marmoraria na Saúde, Zona Sul de São Paulo. Bancadas, pias, escadas "
            "e projetos sob medida em mármore, granito, quartzo e quartzito."
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
        title="Projetos e Aplicações em Pedras | Granimármores Pitondo",
        description=(
            "Conheça aplicações em mármore, granito e outras superfícies para cozinhas, "
            "banheiros, escadas, áreas gourmet e ambientes comerciais."
        ),
    ),
    "materials": PageSeo(
        title="Mármores, Granitos e Outros Materiais | Granimármores Pitondo",
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
    "marmoraria_saude_sp": PageSeo(
        title="Marmoraria na Saúde SP | Granimármores Pitondo",
        description=(
            "Marmoraria na Saúde, São Paulo, com medição, fabricação e instalação "
            "de bancadas, pias, escadas e peças sob medida em pedras e superfícies."
        ),
    ),
    "marmoraria_zona_sul_sp": PageSeo(
        title="Marmoraria na Zona Sul de SP | Granimármores Pitondo",
        description=(
            "Projetos sob medida em mármore, granito, quartzo e quartzito na Zona "
            "Sul de São Paulo, com medição, fabricação, acabamento e instalação."
        ),
    ),
    "politica_de_privacidade": PageSeo(
        title="Política de Privacidade | Granimármores Pitondo",
        description=(
            "Saiba como a Granimármores Pitondo coleta, utiliza, armazena e protege "
            "dados pessoais em seu site e canais digitais."
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


LOCAL_PAGE_SCHEMA = {
    "marmoraria_saude_sp": {
        "name": "Marmoraria na Saúde, São Paulo",
        "faqs": [
            ("Onde fica a Granimármores Pitondo?", "A Granimármores Pitondo fica na Av. do Cursino, 3342, Jardim da Saúde, São Paulo - SP."),
            ("A empresa realiza medição no local?", "Sim. A medição técnica faz parte do processo para conferir medidas, pontos e interferências do ambiente."),
            ("Quais ambientes podem receber peças sob medida?", "Cozinhas, banheiros, escadas, áreas gourmet e projetos comerciais podem receber peças sob medida em pedras e superfícies."),
            ("Como solicitar uma avaliação?", "Envie fotos, medidas ou a planta do ambiente pela página de contato ou orçamento para iniciar a avaliação do projeto."),
        ],
    },
    "marmoraria_zona_sul_sp": {
        "name": "Marmoraria na Zona Sul de São Paulo",
        "faqs": [
            ("A Granimármores Pitondo atende projetos na Zona Sul?", "Sim. A empresa atende projetos residenciais e comerciais na Zona Sul de São Paulo, com base na localização da Saúde."),
            ("Vocês trabalham com cozinhas e áreas gourmet?", "Sim. Cozinhas e áreas gourmet podem receber bancadas, ilhas, pias e revestimentos sob medida."),
            ("É possível fabricar peças conforme planta ou projeto?", "Sim. Fotos, medidas, plantas e referências ajudam na compatibilização com marcenaria, cuba, cooktop e demais pontos do ambiente."),
            ("Quais informações devo enviar para solicitar orçamento?", "Informe o ambiente, medidas aproximadas, fotos ou planta, material desejado e detalhes como cuba, cooktop, recortes e local de instalação."),
        ],
    },
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


def build_local_business_schema(request):
    profile = SITE_PROFILE
    base_url = site_base_url()
    business_id = f"{base_url}/#business"
    website_id = f"{base_url}/#website"
    canonical_url = resolve_canonical_url(request)

    # 1. LocalBusiness / HomeAndConstructionBusiness
    business_schema = {
        "@type": ["LocalBusiness", "HomeAndConstructionBusiness"],
        "@id": business_id,
        "name": profile["company_name"],
        "url": base_url,
        "telephone": "+55 11 94024-1328",
        "email": profile["email"],
        "description": profile["description"],
        "logo": {
            "@type": "ImageObject",
            "url": absolute_static_url("institutional/images/logo-gp.webp"),
        },
        "image": absolute_static_url(profile["default_social_image"]),
        "address": {
            "@type": "PostalAddress",
            "streetAddress": profile["street_address"],
            "addressLocality": profile["address_city"],
            "addressRegion": profile["address_region"],
            "postalCode": profile["postal_code"],
            "addressCountry": profile["address_country"],
        },
        "areaServed": {
            "@type": "City",
            "name": profile["area_served"],
        },
        "sameAs": [profile["same_as"]],
    }

    # 2. WebSite
    website_schema = {
        "@type": "WebSite",
        "@id": website_id,
        "url": base_url,
        "name": profile["company_name"],
        "publisher": {"@id": business_id},
    }

    graph = [business_schema, website_schema]

    # 3. Breadcrumbs
    match = getattr(request, "resolver_match", None)
    if match and match.namespace == "institutional" and match.url_name != "home":
        breadcrumbs = [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Início",
                "item": base_url,
            }
        ]

        # Posição 2
        pos = 2
        url_name = match.url_name

        # Se for página de solução específica, "Soluções" fica no meio
        if url_name in ["cozinhas", "banheiros", "escadas", "areas_gourmet", "projetos_comerciais"]:
            breadcrumbs.append({
                "@type": "ListItem",
                "position": pos,
                "name": "Soluções",
                "item": f"{base_url}/solucoes/",
            })
            pos += 1

            names = {
                "cozinhas": "Cozinhas",
                "banheiros": "Banheiros",
                "escadas": "Escadas",
                "areas_gourmet": "Áreas Gourmet",
                "projetos_comerciais": "Projetos Comerciais",
            }
            breadcrumbs.append({
                "@type": "ListItem",
                "position": pos,
                "name": names.get(url_name, "Solução"),
                "item": canonical_url,
            })
        elif url_name == "blog_article":
            breadcrumbs.append({
                "@type": "ListItem",
                "position": pos,
                "name": "Blog",
                "item": f"{base_url}/blog/",
            })
            pos += 1

            slug = match.kwargs.get("slug", "")
            article = BLOG_ARTICLE_SEO.get(slug)
            if article:
                title = article.title.split(" | ")[0]
                breadcrumbs.append({
                    "@type": "ListItem",
                    "position": pos,
                    "name": title,
                    "item": canonical_url,
                })
        else:
            names = {
                "sobre": "Sobre Nós",
                "services": "Soluções",
                "projects": "Projetos",
                "materials": "Materiais",
                "contato": "Contato",
                "marmoraria_saude_sp": "Marmoraria na Saúde",
                "marmoraria_zona_sul_sp": "Marmoraria na Zona Sul de São Paulo",
                "politica_de_privacidade": "Política de Privacidade",
                "quotation": "Orçamento",
                "blog": "Blog",
            }
            breadcrumbs.append({
                "@type": "ListItem",
                "position": pos,
                "name": names.get(url_name, "Página"),
                "item": canonical_url,
            })

        graph.append({
            "@type": "BreadcrumbList",
            "@id": f"{canonical_url}#breadcrumb",
            "itemListElement": breadcrumbs,
        })

    if match and match.namespace == "institutional" and match.url_name in LOCAL_PAGE_SCHEMA:
        page = resolve_page_seo(request)
        local_page = LOCAL_PAGE_SCHEMA[match.url_name]
        graph.append({
            "@type": "WebPage",
            "@id": f"{canonical_url}#webpage",
            "url": canonical_url,
            "name": local_page["name"],
            "description": page.description,
            "isPartOf": {"@id": website_id},
            "about": {"@id": business_id},
        })
        graph.append({
            "@type": "FAQPage",
            "@id": f"{canonical_url}#faq",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": question,
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": answer,
                    },
                }
                for question, answer in local_page["faqs"]
            ],
        })

    # 4. BlogPosting
    if match and match.namespace == "institutional" and match.url_name == "blog_article":
        slug = match.kwargs.get("slug", "")
        article = BLOG_ARTICLE_SEO.get(slug)
        if article:
            title = article.title.split(" | ")[0]
            graph.append({
                "@type": "BlogPosting",
                "@id": f"{canonical_url}#blogposting",
                "headline": title,
                "description": article.description,
                "url": canonical_url,
                "mainEntityOfPage": canonical_url,
                "publisher": {"@id": business_id},
                "image": absolute_static_url(article.og_image) if article.og_image else absolute_static_url(profile["default_social_image"]),
            })

    # 5. Service (para páginas de soluções específicas)
    if match and match.namespace == "institutional" and match.url_name in ["cozinhas", "banheiros", "escadas", "areas_gourmet", "projetos_comerciais"]:
        page = resolve_page_seo(request)
        title = page.title.split(" | ")[0]
        graph.append({
            "@type": "Service",
            "@id": f"{canonical_url}#service",
            "name": title,
            "description": page.description,
            "url": canonical_url,
            "provider": {"@id": business_id},
            "serviceType": "Marmoraria",
        })

    schema = {
        "@context": "https://schema.org",
        "@graph": graph,
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
        "email": SITE_PROFILE["email"],
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
        "local_business_schema": build_local_business_schema(request),
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
