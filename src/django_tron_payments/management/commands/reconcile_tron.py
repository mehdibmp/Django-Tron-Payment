"""Manually reconcile confirmed TRON deposits."""

from django.core.management.base import BaseCommand

from django_tron_payments.services.deposits import reconcile_active_wallets


class Command(BaseCommand):
    """Discover and record confirmed configured-asset transfers."""

    help = "Reconcile confirmed TRON deposits for all active managed wallets."

    def handle(self, *args, **options):
        del args, options
        created = reconcile_active_wallets()
        self.stdout.write(self.style.SUCCESS(f"Recorded {created} new confirmed payment(s)."))
