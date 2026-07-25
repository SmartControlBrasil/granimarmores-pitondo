"""
Configurações base do projeto Granimármores Pitondo.

Este arquivo contém as configurações compartilhadas entre os ambientes
de desenvolvimento e produção.
"""

from pathlib import Path

import environ


# =============================================================================
# DIRETÓRIOS DO PROJETO
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent


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

    # Aplicações do projeto
    "src.institutional.infrastructure.django.apps.InstitutionalConfig",
]


# =============================================================================
# MIDDLEWARES
# =============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.static",
                "django.template.context_processors.media",
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


# =============================================================================
# ARQUIVOS ESTÁTICOS
# =============================================================================

STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
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

LOGIN_URL = "/login/"

LOGIN_REDIRECT_URL = "/painel/"

LOGOUT_REDIRECT_URL = "/"


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

EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)

EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)

DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default="Granimármores Pitondo <contato@granimarmorespitondo.com.br>",
)

SERVER_EMAIL = env(
    "SERVER_EMAIL",
    default="sistema@granimarmorespitondo.com.br",
)

CONTACT_NOTIFICATION_EMAIL = env("CONTACT_NOTIFICATION_EMAIL", default="")


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