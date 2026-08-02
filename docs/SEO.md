# SEO técnico — Site institucional

Documentação da camada de SEO técnico do site público Granimármores Pitondo.

## Domínio canônico

Configurado centralmente em `config/settings/base.py`:

```python
SITE_DOMAIN = env("SITE_DOMAIN", default="granimarmorespitondo.com.br")
```

URLs absolutas são montadas em `src/institutional/presentation/seo.py` via `site_base_url()`.

## Fonte central de dados

Arquivo: `src/institutional/presentation/seo.py`

Contém:

- perfil da empresa (`SITE_PROFILE`);
- metadados por rota (`PAGE_SEO`);
- metadados por artigo de blog (`BLOG_ARTICLE_SEO`);
- helpers para canonical, Open Graph e schema JSON-LD;
- geração do conteúdo de `robots.txt`.

Context processor: `src/institutional/presentation/context_processors.py`  
Variável de template: `site_seo`

## Rotas de indexação

| Rota | Implementação |
|------|---------------|
| `/sitemap.xml` | Django sitemaps (`src/institutional/presentation/sitemaps.py`) |
| `/robots.txt` | View `robots_txt` (`src/institutional/presentation/robots.py`) |

### `robots.txt`

- Responde `HTTP 200` com `Content-Type: text/plain`
- Funciona com `DEBUG=True` e `DEBUG=False`
- Não depende de arquivo estático
- O arquivo `static/robots.txt` foi **removido** por redundância (não era servido em `/robots.txt`)

## Template base

Arquivo: `templates/institutional/base.html`

Blocos disponíveis:

- `seo_title`
- `seo_description`
- `seo_canonical`
- `seo_robots`
- `seo_og_type`, `seo_og_title`, `seo_og_description`, `seo_og_url`, `seo_og_image`
- `seo_twitter_title`, `seo_twitter_description`, `seo_twitter_image`
- `seo_schema` (JSON-LD adicional por página)

Valores padrão vêm de `site_seo` (context processor).

## Imagem social padrão

```
/static/institutional/images/logo-gp.webp
```

URL absoluta gerada automaticamente. Artigos do blog usam imagens específicas já existentes em `static/institutional/images/blog/`.

## Páginas cobertas

16 URLs públicas indexáveis (13 rotas + 3 artigos):

- Home, sobre, soluções, projetos, materiais
- Cozinhas, banheiros, escadas, áreas gourmet, projetos comerciais
- Blog, contato, orçamento
- 3 artigos do blog

Metadados definidos em `PAGE_SEO` / `BLOG_ARTICLE_SEO`, não duplicados nos templates.

## Dados estruturados

### Implementado

- `LocalBusiness` (JSON-LD) no template base, com dados confirmados:
  - nome, URL, telefone, endereço, cidade, estado, país, imagem

### Não implementado (limitação atual)

- `BlogPosting` nos artigos — **não há autor nem data de publicação persistidos** no código; schema incompleto não foi inventado.

## Blog estático

Artigos são templates HTML com slugs fixos em `views.py` e `seo.py`. Não há CMS. Novos artigos exigem:

1. template em `templates/institutional/pages/blog/`;
2. slug em `views.py`, `sitemaps.py` e `BLOG_ARTICLE_SEO`.

## Testes

Classe `InstitutionalSeoTests` em `src/institutional/infrastructure/django/tests.py`.

```bash
python manage.py test src.institutional.infrastructure.django.tests
```
