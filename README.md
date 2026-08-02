# Granimármores Pitondo

Plataforma Django unificada da Granimármores Pitondo: **site institucional público** e **ERP Hando** (painel operacional) no mesmo projeto, banco e deploy.

## Visão geral

| Camada | Prefixo de URL | Público |
|--------|----------------|---------|
| Site institucional | `/` | Sim |
| Autenticação (Allauth) | `/accounts/` | Login/logout |
| ERP Hando | `/painel/` | Não (requer login) |
| Django Admin | `/admin/` | Não (técnico) |
| Sitemap | `/sitemap.xml` | Sim |

O formulário de contato/orçamento do site **cria ou reutiliza clientes** no ERP (`customers.Customer`), registra **auditoria** e envia **e-mail** de notificação.

## Arquitetura (resumo)

```
manage.py                    ← único ponto de entrada Django
config/                      ← settings, urls, wsgi (configuração principal)
src/institutional/           ← site público (presentation + application)
hando/                       ← apps ERP (quotes, materials, access_control…)
templates/institutional/     ← HTML do site público
static/institutional/        ← assets do site (tema Designesia)
hando/hando/templates/       ← painel visual Hando (preservar)
```

Detalhes: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Estrutura de diretórios

```
.
├── manage.py
├── config/                   # Settings e URLs oficiais
├── requirements/             # Dependências Python
├── src/institutional/        # Módulo institucional
│   ├── presentation/         # views, urls, sitemaps
│   └── application/          # serviços (ex.: contact_requests)
├── hando/                    # Apps ERP (importados via sys.path)
│   ├── quotes/
│   ├── materials/
│   ├── customers/
│   ├── access_control/
│   └── hando/templates/      # UI do painel Hando
├── templates/institutional/
├── static/institutional/
├── media/                    # uploads (MEDIA_ROOT)
└── docs/                     # documentação técnica
```

> **Atenção:** existe `hando/manage.py` e `hando/config/` herdados do template Cookiecutter. **Não são a configuração principal.** Use apenas o `manage.py` da raiz.

## Requisitos

- Python **3.12+** (compatível com Django 6.x)
- Django **6.0.x** (`requirements/base.txt`)
- PostgreSQL recomendado para produção; SQLite aceito em desenvolvimento
- Ambiente virtual (`.venv`)

## Instalação local

```bash
git clone <repositório>
cd granimarmores-pitondo
python -m venv .venv
source .venv/bin/activate
pip install -r requirements/development.txt
```

## Criação do `.env`

Copie o exemplo e ajuste:

```bash
cp .env.example .env
```

Variáveis relevantes (ver `.env.example` e `config/settings/base.py`):

| Variável | Uso |
|----------|-----|
| `DEBUG` | `True` em desenvolvimento |
| `SECRET_KEY` | Chave Django (obrigatória em produção) |
| `ALLOWED_HOSTS` | Hosts permitidos |
| `DATABASE_URL` | PostgreSQL ou SQLite |
| `SITE_DOMAIN` | Domínio canônico do sitemap (padrão: `granimarmorespitondo.com.br`) |
| `CONTACT_RECIPIENT_EMAIL` | Destino das notificações do formulário |
| `EMAIL_*` | SMTP em produção |
| `DJANGO_ACCOUNT_ALLOW_REGISTRATION` | Padrão `False` (sem signup público de funcionários) |

## Migrações

```bash
python manage.py migrate
```

## Configuração inicial dos cargos (RBAC)

Após criar um superusuário, execute o seed da fundação ERP:

```bash
python manage.py createsuperuser
python manage.py setup_erp_foundation
# opcional: vincular cargo Administrativo a um usuário específico
python manage.py setup_erp_foundation --admin-username=<username>
```

O comando cria permissões, cargos iniciais, categorias base e associa o superusuário ao cargo **Administrativo**.

Detalhes: [docs/RBAC.md](docs/RBAC.md)

## Execução local

```bash
source .venv/bin/activate
python manage.py runserver
```

- Site: http://127.0.0.1:8000/
- Painel: http://127.0.0.1:8000/painel/ (após login)
- Login: http://127.0.0.1:8000/accounts/login/

Settings padrão do `manage.py`: `config.settings.development`

## Testes

```bash
# Verificação geral do projeto
python manage.py check

# Testes institucionais (páginas, contato, sitemap)
python manage.py test src.institutional.infrastructure.django.tests

# Testes ERP (exemplos)
python manage.py test hando.quotes.tests hando.materials.tests hando.access_control.tests

# Suite completa
python manage.py test
```

## Principais URLs

### Públicas (institucional)

| URL | Nome |
|-----|------|
| `/` | Home |
| `/sobre/` | Sobre |
| `/solucoes/` | Soluções |
| `/projetos/` | Projetos |
| `/materiais/` | Materiais |
| `/cozinhas/` | Cozinhas |
| `/banheiros/` | Banheiros |
| `/escadas/` | Escadas |
| `/areas-gourmet/` | Áreas gourmet |
| `/projetos-comerciais/` | Projetos comerciais |
| `/blog/` | Blog |
| `/blog/<slug>/` | Artigo (3 slugs publicados) |
| `/contato/` | Contato |
| `/orcamento/` | Orçamento (mesmo fluxo de contato) |
| `/sitemap.xml` | Sitemap XML |
| `/robots.txt` | Diretivas para crawlers |

### Operacionais (ERP, autenticadas)

| URL | Módulo |
|-----|--------|
| `/painel/` | Dashboard |
| `/painel/clientes/` | Clientes |
| `/painel/comercial/orcamentos/` | Orçamentos |
| `/painel/cadastros/` | Materiais |
| `/painel/administracao/usuarios/` | Usuários |
| `/painel/administracao/acessos/` | Cargos e permissões |
| `/painel/administracao/auditoria/` | Auditoria |

## Alertas arquiteturais

1. **Um único projeto Django** — não criar segundo `manage.py` nem settings paralelos em produção.
2. **`config/` na raiz** é a configuração oficial; ignore `hando/config/` para execução.
3. **Painel Hando** — preservar templates e assets em `hando/hando/templates/` e `hando/hando/static/`.
4. **Menu oculto ≠ módulo ausente** — itens do sidebar somem por falta de permissão RBAC.
5. **Sem signup público** — `ACCOUNT_ALLOW_REGISTRATION` padrão é `False`.
6. **`robots.txt`** — servido dinamicamente em `/robots.txt` (ver `src/institutional/presentation/robots.py`).
7. Metadados SEO centralizados em `src/institutional/presentation/seo.py`.
7. Documentos legados em `docs/ARQUITETURA_E_DIRETRIZES.md` e `docs/DECISOES_ARQUITETURAIS.md` complementam esta documentação; preferir `docs/ARCHITECTURE.md` e `docs/DECISIONS.md` para referência operacional.

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Monólito, camadas, fluxos |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Desenvolvimento seguro |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Deploy e operação |
| [docs/RBAC.md](docs/RBAC.md) | Cargos, permissões, diagnóstico |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decisões arquiteturais |
| [docs/SEO.md](docs/SEO.md) | SEO técnico institucional |
| [docs/COMMERCIAL_MASTER_DATA.md](docs/COMMERCIAL_MASTER_DATA.md) | Cadastros mestres comerciais |
| [docs/CRM.md](docs/CRM.md) | CRM, leads e funil comercial |
| [docs/SALES_PERFORMANCE.md](docs/SALES_PERFORMANCE.md) | Metas, score e desempenho comercial |
| [docs/PRODUCTION.md](docs/PRODUCTION.md) | Pedidos, produção, entrega e instalação |
| [docs/STOCK.md](docs/STOCK.md) | Estoque, chapas, reservas e consumo |
| [docs/OPERATIONAL_SCHEDULE.md](docs/OPERATIONAL_SCHEDULE.md) | Agenda operacional interna |
| [docs/AFTER_SALES.md](docs/AFTER_SALES.md) | Pós-venda, garantia e assistência |
| [docs/MEDIA_LIBRARY.md](docs/MEDIA_LIBRARY.md) | Biblioteca interna de mídias |
| [docs/EXECUTIVE_DASHBOARD.md](docs/EXECUTIVE_DASHBOARD.md) | Painel executivo da diretoria |
| [docs/FINANCE.md](docs/FINANCE.md) | Financeiro operacional e fluxo de caixa |
| [docs/PURCHASING.md](docs/PURCHASING.md) | Compras, fornecedores e abastecimento |
| [docs/COMMISSIONS.md](docs/COMMISSIONS.md) | Comissões comerciais e fechamentos |
| [docs/ADMIN_NAVIGATION.md](docs/ADMIN_NAVIGATION.md) | Sidebar e menus dropdown do painel |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Roadmap de produto (legado) |
