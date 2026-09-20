from django.apps import AppConfig


class DjangoTronPaymentsConfig(AppConfig):
    """Application configuration for the reusable payment app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "django_tron_payments"
    verbose_name = "TRON payments"

    def ready(self) -> None:
        from . import checks  # noqa: F401
