# Deploy — Granimármores Pitondo

Procedimento de deploy e operação. Valores de infraestrutura **não versionados** no repositório estão marcados como **a validar**.

## Visão geral

Deploy único serve site institucional (`/`) e ERP Hando (`/painel/`) no mesmo processo.

| Item | Valor confirmado no código |
|------|---------------------------|
| Domínio de produção (canônico) | `granimarmorespitondo.com.br` (`SITE_DOMAIN` padrão) |
| Settings produção | `config.settings.production` |
| WSGI | `config.wsgi.application` |
| Servidor app | Gunicorn (`requirements/production.txt`) |
| Estáticos | WhiteNoise + `collectstatic` → `staticfiles/` |
| Banco | PostgreSQL via `DATABASE_URL` |

## Infraestrutura (a validar)

Os itens abaixo **não estão versionados** no repositório. Confirmar na VPS antes do deploy:

| Item | Status |
|------|--------|
| Diretório do projeto na VPS | **a validar** (ex.: `/var/www/granimarmores-pitondo`) |
| Usuário de sistema | **a validar** (ex.: `www-data` ou usuário dedicado) |
| Serviço systemd | **a validar** (nome sugerido: `granimarmores-pitondo.service`) |
| Proxy OpenLiteSpeed | **a validar** (reverse proxy para Gunicorn) |
| Socket/porta Gunicorn | **a validar** (ex.: `127.0.0.1:8001`) |
| Caminho do virtualenv | **a validar** |

## Pré-requisitos na VPS

- Python 3.12+
- PostgreSQL
- Git
- OpenLiteSpeed (ou proxy equivalente — **a validar**)
- Dependências de sistema para `psycopg` e Pillow

## Variáveis de ambiente obrigatórias (produção)

Criar `.env` na raiz do projeto (nunca commitar):

```env
DEBUG=False
SECRET_KEY=<chave-forte-unica>
ALLOWED_HOSTS=granimarmorespitondo.com.br,www.granimarmorespitondo.com.br
SITE_DOMAIN=granimarmorespitondo.com.br

DATABASE_URL=postgresql://<user>:<password>@127.0.0.1:5432/granimarmores_pitondo
DATABASE_CONN_MAX_AGE=60

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<smtp-host>
EMAIL_PORT=587
EMAIL_HOST_USER=<smtp-user>
EMAIL_HOST_PASSWORD=<smtp-password>
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=Granimármores Pitondo <contato@granimarmorespitondo.com.br>
CONTACT_EMAIL_TO=contato@granimarmorespitondo.com.br
CONTACT_EMAIL_CC=granimarmorespitondo@gmail.com
CONTACT_RECIPIENT_EMAIL=contato@granimarmorespitondo.com.br
SERVER_EMAIL=sistema@granimarmorespitondo.com.br

DJANGO_ACCOUNT_ALLOW_REGISTRATION=False
```

## Procedimento de deploy

```bash
cd <diretorio-do-projeto>   # a validar
git pull origin main
source .venv/bin/activate
pip install -r requirements/production.txt

export DJANGO_SETTINGS_MODULE=config.settings.production

python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

### Gunicorn (referência)

**a validar** — exemplo de unit systemd:

```ini
[Unit]
Description=Granimarmores Pitondo Django
After=network.target

[Service]
User=<usuario>
Group=<grupo>
WorkingDirectory=<diretorio-do-projeto>
Environment="DJANGO_SETTINGS_MODULE=config.settings.production"
EnvironmentFile=<diretorio-do-projeto>/.env
ExecStart=<diretorio-do-projeto>/.venv/bin/gunicorn \
    config.wsgi:application \
    --bind 127.0.0.1:8001 \
    --workers 3 \
    --timeout 120
Restart=always

[Install]
WantedBy=multi-user.target
```

> **Atenção:** `config/wsgi.py` define `DJANGO_SETTINGS_MODULE=config.settings.development` como padrão. Em produção, **sempre** exportar `config.settings.production` no serviço systemd ou no ambiente do Gunicorn.

### OpenLiteSpeed (a validar)

Configurar virtual host `granimarmorespitondo.com.br` com proxy reverso para o bind do Gunicorn. Servir `/static/` via WhiteNoise (aplicação) ou cache de proxy — **a validar** conforme setup atual da VPS.

## Reinício e validação

```bash
sudo systemctl daemon-reload          # a validar
sudo systemctl restart granimarmores-pitondo   # a validar
sudo systemctl status granimarmores-pitondo    # a validar
```

### Testes HTTP mínimos pós-deploy

```bash
curl -I https://granimarmorespitondo.com.br/
curl -I https://granimarmorespitondo.com.br/contato/
curl -I https://granimarmorespitondo.com.br/sitemap.xml
curl -I https://granimarmorespitondo.com.br/accounts/login/
curl -I https://granimarmorespitondo.com.br/painel/
```

Expectativas:

| URL | Esperado |
|-----|----------|
| `/` | 200 |
| `/contato/` | 200 |
| `/sitemap.xml` | 200, `Content-Type: application/xml` |
| `/accounts/login/` | 200 |
| `/painel/` | 302 → login (se não autenticado) |

## Sitemap e robots.txt

| Recurso | Status |
|---------|--------|
| `/sitemap.xml` | **Implementado** — 16 URLs públicas |
| `/robots.txt` | **Implementado** — view Django em `/robots.txt` |

Enviar sitemap ao Google Search Console:

```
https://granimarmorespitondo.com.br/sitemap.xml
```

## PostgreSQL

- Banco recomendado em produção (`DATABASE_URL`)
- Backup antes de cada deploy com migrations
- **Nunca** sobrescrever banco de produção com dump de dev sem plano

## Migrations

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
python manage.py migrate --noinput
```

Revisar migrations pendentes antes do deploy:

```bash
python manage.py showmigrations --plan
```

## Rollback via Git

1. Identificar commit estável: `git log --oneline -10`
2. Checkout ou revert na VPS: `git checkout <commit>` ou `git revert <commit>`
3. Reinstalar deps se necessário
4. `python manage.py migrate` (cuidado: migrations irreversíveis exigem plano)
5. `python manage.py collectstatic --noinput`
6. Reiniciar serviço Gunicorn

**Nunca** fazer `git push --force` em `main` sem coordenação.

## Itens que jamais devem ser sobrescritos sem backup

| Item | Motivo |
|------|--------|
| Banco PostgreSQL de produção | Dados operacionais |
| Diretório `media/` | PDFs de orçamentos, uploads |
| Arquivo `.env` | Segredos e configuração |
| `staticfiles/` | Regenerável via `collectstatic`, mas exige rebuild |
| Migrations já aplicadas | Requer plano de rollback de schema |

## Seed pós-deploy (primeira instalação)

```bash
python manage.py createsuperuser
python manage.py setup_erp_foundation --admin-username=<username>
```

## Monitoramento (a validar)

- Logs do Gunicorn / systemd journal
- Logs Django (`LOG_LEVEL`, `DJANGO_LOG_LEVEL`)
- Espaço em disco (`media/`, PostgreSQL)
- Certificado TLS no OpenLiteSpeed
