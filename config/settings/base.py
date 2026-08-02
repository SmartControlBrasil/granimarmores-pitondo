"""
Configurações base do projeto Granimármores Pitondo.

Este arquivo contém as configurações compartilhadas entre os ambientes
de desenvolvimento e produção.
"""

import sys
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured


# =============================================================================
# DIRETÓRIOS DO PROJETO
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent
HANDO_DIR = BASE_DIR / "hando"

if str(HANDO_DIR) not in sys.path:
    sys.path.insert(0, str(HANDO_DIR))


# =============================================================================
# VARIÁVEIS DE AMBIENTE
# =============================================================================

env = environ.Env(
    DEBUG=(bool, False),
)

environ.Env.read_env(BASE_DIR / ".env")


# =============================================================================
# SEGURANÇA
# =============================================================================

SECRET_KEY = env(
    "SECRET_KEY",
    default="django-insecure-change-this-key-before-production",
)

DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=[
        "127.0.0.1",
        "localhost",
    ],
)

SITE_DOMAIN = env(
    "SITE_DOMAIN",
    default="granimarmorespitondo.com.br",
)


# =============================================================================
# APLICAÇÕES
# =============================================================================

INSTALLED_APPS = [
    # Aplicações padrão do Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.forms",

    # Terceiros usados pelo Hando
    "crispy_forms",
    "crispy_bootstrap5",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.socialaccount",

    # Site institucional
    "src.institutional.infrastructure.django.apps.InstitutionalConfig",

    # ERP Hando canônico
    "hando.users",
    "hando.pages",
    "core",
    "accounts",
    "access_control",
    "audit",
    "customers",
    "salespeople",
    "commercial",
    "materials",
    "quotes",
    "assets",
    "fleet",
    "maintenance",
    "production",
    "scheduling",
    "after_sales",
    "media_library",
    "executive_dashboard",
]

# Painel executivo: cache curto por usuário/filtros (0 desativa)
EXECUTIVE_DASHBOARD_CACHE_SECONDS = env.int("EXECUTIVE_DASHBOARD_CACHE_SECONDS", default=60)

# Biblioteca interna de mídia (armazenamento local do ERP)
MEDIA_LIBRARY_MAX_IMAGE_SIZE_MB = 10
MEDIA_LIBRARY_MAX_DOCUMENT_SIZE_MB = 20
MEDIA_LIBRARY_MAX_FILES_PER_BATCH = 20
MEDIA_LIBRARY_ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"]
MEDIA_LIBRARY_ALLOWED_DOCUMENT_TYPES = ["application/pdf"]


# =============================================================================
# MIDDLEWARES
# =============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "audit.middleware.AuditMiddleware",
]


# =============================================================================
# URLS, TEMPLATES, WSGI E ASGI
# =============================================================================

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
            HANDO_DIR / "hando" / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.static",
                "django.template.context_processors.media",
                "django.template.context_processors.tz",
                "hando.users.context_processors.allauth_settings",
                "access_control.context_processors.erp_permissions",
                "src.institutional.presentation.context_processors.institutional_seo",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

ASGI_APPLICATION = "config.asgi.application"


# =============================================================================
# BANCO DE DADOS
# =============================================================================

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}

DATABASES["default"]["CONN_MAX_AGE"] = env.int(
    "DATABASE_CONN_MAX_AGE",
    default=0,
)

# =============================================================================
# VALIDAÇÃO DE SENHAS
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# =============================================================================
# INTERNACIONALIZAÇÃO
# =============================================================================

LANGUAGE_CODE = "pt-br"

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True

USE_TZ = True

# Agenda operacional: alerta de confirmação pendente (horas antes do início)
AGENDA_CONFIRMATION_WARNING_HOURS = 24


# =============================================================================
# ARQUIVOS ESTÁTICOS
# =============================================================================

STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
    HANDO_DIR / "hando" / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"


# =============================================================================
# ARQUIVOS DE MÍDIA
# =============================================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# =============================================================================
# CONFIGURAÇÕES PADRÃO DO DJANGO
# =============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =============================================================================
# SESSÃO E COOKIES
# =============================================================================

SESSION_COOKIE_HTTPONLY = True

CSRF_COOKIE_HTTPONLY = True

SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SAMESITE = "Lax"


# =============================================================================
# AUTENTICAÇÃO
# =============================================================================

AUTH_USER_MODEL = "users.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_URL = "account_login"

LOGIN_REDIRECT_URL = "pages:dashboard"

LOGOUT_REDIRECT_URL = "/"

FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

CRISPY_TEMPLATE_PACK = "bootstrap5"

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

ACCOUNT_ALLOW_REGISTRATION = env.bool(
    "DJANGO_ACCOUNT_ALLOW_REGISTRATION",
    default=False,
)

ACCOUNT_AUTHENTICATION_METHOD = "username"

ACCOUNT_EMAIL_REQUIRED = True

ACCOUNT_EMAIL_VERIFICATION = "none"

ACCOUNT_ADAPTER = "hando.users.adapters.AccountAdapter"

ACCOUNT_FORMS = {"signup": "hando.users.forms.UserSignupForm"}

SOCIALACCOUNT_ADAPTER = "hando.users.adapters.SocialAccountAdapter"

SOCIALACCOUNT_FORMS = {"signup": "hando.users.forms.UserSocialSignupForm"}

DJANGO_ADMIN_FORCE_ALLAUTH = env.bool(
    "DJANGO_ADMIN_FORCE_ALLAUTH",
    default=False,
)


# =============================================================================
# E-MAIL
# =============================================================================

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

EMAIL_HOST = env("EMAIL_HOST", default="")

EMAIL_PORT = env.int("EMAIL_PORT", default=587)

EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")

EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)

EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)

if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured(
        "EMAIL_USE_TLS e EMAIL_USE_SSL não podem estar ativos ao mesmo tempo.",
    )

EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)

DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default="Granimármores Pitondo <contato@granimarmorespitondo.com.br>",
)

CONTACT_RECIPIENT_EMAIL = env(
    "CONTACT_RECIPIENT_EMAIL",
    default="contato@granimarmorespitondo.com.br",
)

SERVER_EMAIL = env(
    "SERVER_EMAIL",
    default="sistema@granimarmorespitondo.com.br",
)


# =============================================================================
# LOGS
# =============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": (
                "{levelname} {asctime} {name} "
                "{module} {process:d} {thread:d} {message}"
            ),
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": [
            "console",
        ],
        "level": env(
            "LOG_LEVEL",
            default="INFO",
        ),
    },
    "loggers": {
        "django": {
            "handlers": [
                "console",
            ],
            "level": env(
                "DJANGO_LOG_LEVEL",
                default="INFO",
            ),
            "propagate": False,
        },
        "src": {
            "handlers": [
                "console",
            ],
            "level": env(
                "PROJECT_LOG_LEVEL",
                default="INFO",
            ),
            "propagate": False,
        },
    },
}