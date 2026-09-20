"""Isolated settings used by the package test suite."""

from cryptography.fernet import Fernet

SECRET_KEY = "django-tron-payments-test-secret"
DEBUG = True
USE_TZ = True
ROOT_URLCONF = "django_tron_payments.urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "django_tron_payments",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

TRON_PAYMENTS = {
    "NETWORK": "nile",
    "TRONGRID_API_KEY": "test-api-key",
    "TREASURY_ADDRESS": "TJRyWwFs9wTFGZg3JbrwxJ5dUN76iZqR5w",
    "ENCRYPTION_OPTIONS": {"FERNET_KEYS": [Fernet.generate_key().decode("ascii")]},
}
