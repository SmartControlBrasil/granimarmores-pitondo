from .base import *


DEBUG = True

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "0.0.0.0",
]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
