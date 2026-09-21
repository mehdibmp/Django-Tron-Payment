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
def test_queue_sweeps_skips_trc20_without_fee_trx_and_records_reason(settings):
    settings.TRON_PAYMENTS = {
        **settings.TRON_PAYMENTS,
        "TRC20_FEE_LIMIT_SUN": 3_000_000,
        "ASSETS": [
            {
                "CODE": "USDT",
                "KIND": "TRC20",
                "CONTRACT_ADDRESS": settings.TRON_PAYMENTS["TREASURY_ADDRESS"],
                "DECIMALS": 6,
                "MINIMUM_DEPOSIT_ATOMIC": 1,
            },
        ],
    }
    wallet = get_or_create_wallet(user=make_user())

    with patch(
        "django_tron_payments.services.sweeps.TronGridClient.get_trx_balance_sun",
        return_value=2_999_999,
    ):
        assert queue_sweeps() == 0
        assert queue_sweeps() == 0
    assert wallet.audit_events.filter(event_type="sweep.skipped").count() == 1

    assert not TreasurySweep.objects.filter(wallet=wallet, asset_code="USDT").exists()
    event = wallet.audit_events.get(event_type="sweep.skipped")
    assert event.message == (
        "Skipped the USDT sweep because the wallet has 2,999,999 SUN TRX, "
        "below the 3,000,000 SUN fee requirement."
    )
    assert event.metadata == {
        "network": "nile",
        "asset_code": "USDT",
        "reason": "insufficient_trx_for_fee",
        "trx_balance_sun": 2_999_999,
        "required_trx_sun": 3_000_000,
    }


@pytest.mark.django_db
def test_queue_sweeps_preserves_trc20_fee_balance_when_sweeping_trx(settings):
    settings.TRON_PAYMENTS = {
        **settings.TRON_PAYMENTS,
        "TRC20_FEE_LIMIT_SUN": 3_000_000,
        "ASSETS": [
            {
                "CODE": "USDT",
                "KIND": "TRC20",
                "CONTRACT_ADDRESS": settings.TRON_PAYMENTS["TREASURY_ADDRESS"],
                "DECIMALS": 6,
                "MINIMUM_DEPOSIT_ATOMIC": 1,
            },
        ],
    }
    wallet = get_or_create_wallet(user=make_user())

    with (
        patch(
            "django_tron_payments.services.sweeps.TronGridClient.get_trx_balance_sun",
            return_value=4_000_000,
        ) as get_trx_balance,
        patch(
            "django_tron_payments.services.sweeps.TronGridClient.get_trc20_balance",
            return_value=1,
        ),
    ):
        assert queue_sweeps() == 2
        assert get_trx_balance.call_count == 1

    trx_sweep = TreasurySweep.objects.get(wallet=wallet, asset_code="TRX")
    usdt_sweep = TreasurySweep.objects.get(wallet=wallet, asset_code="USDT")
    assert trx_sweep.amount_atomic == 1_000_000
    assert usdt_sweep.amount_atomic == 1






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
