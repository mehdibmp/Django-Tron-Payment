from unittest.mock import patch

import pytest

from django_tron_payments.clients.base import TronClientError
from django_tron_payments.constants import SweepStatus
from django_tron_payments.models import TreasurySweep
from django_tron_payments.services.sweeps import (
    _broadcast_sweep,
    confirm_broadcast_sweeps,
    queue_sweeps,
)
from django_tron_payments.services.wallets import get_or_create_wallet
from tests.factories import make_user


@pytest.mark.django_db
def test_queue_sweeps_keeps_the_configured_trx_reserve(settings):
    wallet = get_or_create_wallet(user=make_user())

    with patch(
        "django_tron_payments.services.sweeps.TronGridClient.get_trx_balance_sun",
        return_value=2_000_000,
    ):
        assert queue_sweeps() == 1

    sweep = TreasurySweep.objects.get(wallet=wallet, asset_code="TRX")
    assert sweep.amount_atomic == 1_000_000
    assert sweep.status == SweepStatus.QUEUED


@pytest.mark.django_db
def test_ambiguous_broadcast_is_held_for_receipt_reconciliation(settings):
    wallet = get_or_create_wallet(user=make_user())
    sweep = TreasurySweep.objects.create(
        wallet=wallet,
        network="nile",
        asset_code="TRX",
        asset_kind="TRX",
        destination_address=settings.TRON_PAYMENTS["TREASURY_ADDRESS"],
        amount_atomic=1_000_000,
    )

    def ambiguous_broadcast(*, on_transaction_built, **kwargs):
        on_transaction_built("c" * 64)
        raise TronClientError("Network response was interrupted.")

    with patch(
        "django_tron_payments.services.sweeps.broadcast_transfer",
        side_effect=ambiguous_broadcast,
    ):
        assert _broadcast_sweep(sweep.id) is False

    sweep.refresh_from_db()
    assert sweep.status == SweepStatus.BUILDING
    assert sweep.transaction_id == "c" * 64
    assert "requires receipt reconciliation" in sweep.last_error


@pytest.mark.django_db
def test_confirming_a_building_sweep_finalizes_its_known_transaction(settings):
    wallet = get_or_create_wallet(user=make_user())
    sweep = TreasurySweep.objects.create(
        wallet=wallet,
        network="nile",
        asset_code="TRX",
        asset_kind="TRX",
        destination_address=settings.TRON_PAYMENTS["TREASURY_ADDRESS"],
        amount_atomic=1_000_000,
        transaction_id="d" * 64,
        status=SweepStatus.BUILDING,
    )

    with patch(
        "django_tron_payments.services.sweeps.TronGridClient.transaction_confirmed",
        return_value=True,
    ):
        assert confirm_broadcast_sweeps() == 1

    sweep.refresh_from_db()
    assert sweep.status == SweepStatus.CONFIRMED
    assert sweep.confirmed_at is not None
