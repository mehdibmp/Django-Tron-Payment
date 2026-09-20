from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from django_tron_payments.clients.base import ObservedTransfer
from django_tron_payments.conf import PaymentAsset
from django_tron_payments.constants import PaymentStatus
from django_tron_payments.models import IncomingPayment
from django_tron_payments.services.deposits import reconcile_wallet
from django_tron_payments.services.wallets import get_or_create_wallet
from tests.factories import make_user


@pytest.mark.django_db
def test_reconciliation_records_a_confirmed_transfer_once(settings):
    wallet = get_or_create_wallet(user=make_user())
    transfer = ObservedTransfer(
        transaction_id="a" * 64,
        event_index=0,
        sender_address="TQxYyZ1x4ZsVjWQdR4oKdu9wZE7KAjrfpD",
        recipient_address=wallet.address,
        amount_atomic=1_000_000,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        raw_payload={"txID": "a" * 64},
    )

    with patch(
        "django_tron_payments.services.deposits.TronGridClient.confirmed_transfers",
        return_value=[transfer],
    ):
        assert reconcile_wallet(wallet=wallet) == 1
        assert reconcile_wallet(wallet=wallet) == 0

    payment = IncomingPayment.objects.get()
    assert payment.status == PaymentStatus.CONFIRMED
    assert payment.amount_atomic == 1_000_000
    assert payment.wallet_id == wallet.id


@pytest.mark.django_db
def test_reconciliation_ignores_transfers_under_the_asset_minimum(settings):
    wallet = get_or_create_wallet(user=make_user())
    tiny_transfer = ObservedTransfer(
        transaction_id="b" * 64,
        event_index=0,
        sender_address="TQxYyZ1x4ZsVjWQdR4oKdu9wZE7KAjrfpD",
        recipient_address=wallet.address,
        amount_atomic=0,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        raw_payload={},
    )
    asset = PaymentAsset("TRX", "TRX", 6, 1)

    with patch(
        "django_tron_payments.services.deposits.TronGridClient.confirmed_transfers",
        return_value=[tiny_transfer],
    ), patch("django_tron_payments.services.deposits.get_tron_settings") as configured:
        configured.return_value.network = "nile"
        configured.return_value.assets = (asset,)
        assert reconcile_wallet(wallet=wallet) == 0

    assert not IncomingPayment.objects.exists()
