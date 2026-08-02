# Desenvolvimento — Granimármores Pitondo

Guia para desenvolvimento local **seguro**, alinhado à arquitetura unificada.

## Princípios

1. Use **apenas** `manage.py` da raiz.
2. Settings oficiais: `config.settings.development` (padrão) ou `config.settings.production`.
3. **Não** altere `hando/config/` como fonte de configuração principal.
4. **Não** crie segundo projeto Django, backoffice paralelo ou auth operacional concorrente.
5. **Preserve** o painel visual Hando (`hando/hando/templates/`, `hando/hando/static/`).
6. Backend ERP deve validar **RBAC**; ocultar menu não substitui checagem de permissão.

## Ambiente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements/development.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py setup_erp_foundation
```

### Settings module

| Contexto | `DJANGO_SETTINGS_MODULE` |
|----------|--------------------------|
| Dev (`manage.py` padrão) | `config.settings.development` |
| Produção | `config.settings.production` |
| Testes (`manage.py test`) | herda de `development` via `manage.py` |

> **A validar:** testes do subprojeto `hando/` referenciam `config.settings.test` em `hando/pyproject.toml`, mas **não há** `config/settings/test.py` na raiz. Use `python manage.py test` na raiz.

## Variáveis de ambiente usadas

Confirmadas em `config/settings/base.py`:

```
DEBUG
SECRET_KEY
ALLOWED_HOSTS
SITE_DOMAIN
DATABASE_URL
DATABASE_CONN_MAX_AGE
EMAIL_BACKEND
EMAIL_HOST
EMAIL_PORT
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
EMAIL_USE_TLS
EMAIL_USE_SSL
EMAIL_TIMEOUT
DEFAULT_FROM_EMAIL
CONTACT_RECIPIENT_EMAIL
SERVER_EMAIL
LOG_LEVEL
DJANGO_LOG_LEVEL
PROJECT_LOG_LEVEL
DJANGO_ACCOUNT_ALLOW_REGISTRATION
DJANGO_ADMIN_FORCE_ALLAUTH
```

## Onde implementar mudanças

| Tipo de mudança | Local |
|-----------------|-------|
| Página pública nova | `src/institutional/presentation/urls.py` + view + template em `templates/institutional/` |
| Lógica do formulário de contato | `src/institutional/application/contact_requests.py` |
| Sitemap | `src/institutional/presentation/sitemaps.py` |
| Módulo ERP novo | app em `hando/<modulo>/` + registro em `INSTALLED_APPS` + rota em `config/urls.py` sob `/painel/` |
| Permissão nova | `hando/access_control/permissions.py` + views/services |
| UI do painel | templates Hando existentes |

## Comandos úteis

```bash
# Servidor
python manage.py runserver

# Checks
python manage.py check

# Migrations (criar apenas quando necessário)
python manage.py makemigrations
python manage.py migrate

# Seed RBAC
python manage.py setup_erp_foundation

# Testes institucionais
python manage.py test src.institutional.infrastructure.django.tests

# Testes ERP (amostra)
python manage.py test hando.quotes.tests hando.access_control.tests

# Suite completa
python manage.py test

# Coletar estáticos (simular produção)
python manage.py collectstatic --noinput
```

## Testes confirmados no repositório

| Módulo | Arquivo |
|--------|---------|
| Institucional | `src/institutional/infrastructure/django/tests.py` |
| Orçamentos | `hando/quotes/tests.py` |
| Materiais | `hando/materials/tests.py` |
| RBAC | `hando/access_control/tests.py` |
| Clientes | `hando/customers/tests.py` |
| Contas | `hando/accounts/tests.py` |
| Usuários | `hando/hando/users/tests/` |
| Core | `hando/core/tests.py` |

## URLs de desenvolvimento

| Recurso | URL local |
|---------|-----------|
| Home | http://127.0.0.1:8000/ |
| Contato | http://127.0.0.1:8000/contato/ |
| Sitemap | http://127.0.0.1:8000/sitemap.xml |
| Login | http://127.0.0.1:8000/accounts/login/ |
| Painel | http://127.0.0.1:8000/painel/ |
| Admin | http://127.0.0.1:8000/admin/ |

## O que não fazer

- Executar `hando/manage.py` (legado; settings em `hando/config/settings/local.py`).
- Mover apps entre diretórios sem plano de migração.
- Substituir templates Hando por HTML simples.
- Criar models duplicados de `Customer`, `Quote`, `User`.
- Expor signup público de funcionários sem revisão (`ACCOUNT_ALLOW_REGISTRATION`).
- Commitar `.env`, segredos ou `db.sqlite3` com dados sensíveis.

## Arquivos legados (não remover nesta fase)

- `templates/institutional/pages/home_original_intrio.html`
- `templates/institutional/pages/home_before_split.html`
- `hando/manage.py`, `hando/config/`
- `docs/ARQUITETURA_E_DIRETRIZES.md`, `docs/DECISOES_ARQUITETURAIS.md`

Documentação operacional preferencial: `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`.

## Versões confirmadas

- Django: **6.0.x** (`requirements/base.txt`; instalado: 6.0.7 no ambiente local)
- Python: **3.12+** recomendado

## Checklist antes de abrir PR

- [ ] `python manage.py check`
- [ ] `python manage.py test` (ou subset relevante)
- [ ] Sem segundo `manage.py` / settings paralelos
- [ ] Permissões RBAC aplicadas em views sensíveis
- [ ] Auditoria em fluxos operacionais novos
- [ ] Sitemap atualizado se rota pública nova
