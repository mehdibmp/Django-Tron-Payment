"""Django system checks for safe package configuration."""

from __future__ import annotations

from django.core.checks import Error, Warning, register
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from django_tron_payments.conf import get_tron_settings


@register()
def check_tron_payments_configuration(app_configs, **kwargs):
    """Report missing or unsafe settings before payment work is attempted."""
    del app_configs, kwargs
    try:
        configured = get_tron_settings()
    except ImproperlyConfigured as exc:
        return [Error(str(exc), id="tron_payments.E001")]

    messages = []
    if configured.network == "mainnet":
        messages.append(
            Warning(
                "django-tron-payments is configured for TRON Mainnet. Confirm that "
                "production key custody, monitoring, and treasury controls are ready.",
                id="tron_payments.W001",
            )
        )
    try:
        import_string(configured.encryption_backend)
    except (ImportError, AttributeError):
        messages.append(
            Error(
                "TRON_PAYMENTS['ENCRYPTION_BACKEND'] cannot be imported.",
                id="tron_payments.E002",
            )
        )
    return messages