"""Idempotent, locally signed treasury sweeping."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from django_tron_payments.clients.trongrid import TronGridClient
from django_tron_payments.conf import PaymentAsset, get_tron_settings
from django_tron_payments.constants import ACTIVE_SWEEP_STATUSES, SweepStatus
from django_tron_payments.models import ManagedWallet, PaymentAuditEvent, TreasurySweep
from django_tron_payments.services.audit import record_event
from django_tron_payments.services.signing import broadcast_transfer


def queue_sweeps() -> int:
    """Queue one sweep per eligible wallet and configured asset."""
    configured = get_tron_settings()
    client = TronGridClient(configured)
    queued = 0
    wallets = ManagedWallet.objects.filter(network=configured.network, status="active")
    for wallet in wallets.iterator():
        trx_balance_sun = client.get_trx_balance_sun(wallet.address)
        for asset in configured.assets:
            if asset.kind.upper() == "TRC20" and trx_balance_sun < configured.trc20_fee_limit_sun:
                _record_insufficient_trx_event(
                    wallet=wallet,
                    asset=asset,
                    trx_balance_sun=trx_balance_sun,
                    required_trx_sun=configured.trc20_fee_limit_sun,
                )
                continue
            amount = _available_amount(
                client,
                wallet,
                asset,
                trx_balance_sun=trx_balance_sun,
            )
            if amount < asset.minimum_deposit_atomic:
                continue
            _, created = _create_sweep(wallet, asset, amount)
            queued += int(created)
    return queued


def broadcast_queued_sweeps() -> int:
    """Broadcast each currently queued sweep exactly once under a row lock."""
    broadcast_count = 0
    for sweep_id in TreasurySweep.objects.filter(status=SweepStatus.QUEUED).values_list("id", flat=True):
        if _broadcast_sweep(sweep_id):
            broadcast_count += 1
    return broadcast_count


def confirm_broadcast_sweeps() -> int:
    """Finalize broadcast records only after the confirmed receipt succeeds."""
    configured = get_tron_settings()
    client = TronGridClient(configured)
    count = 0
    for sweep_id in TreasurySweep.objects.filter(
        status__in=(SweepStatus.BUILDING, SweepStatus.BROADCAST),
    ).values_list("id", flat=True):
        with transaction.atomic():
            sweep = TreasurySweep.objects.select_for_update().get(id=sweep_id)
            if sweep.status not in (SweepStatus.BUILDING, SweepStatus.BROADCAST) or not sweep.transaction_id:
                continue
            if not client.transaction_confirmed(sweep.transaction_id):
                continue
            sweep.status = SweepStatus.CONFIRMED
            sweep.confirmed_at = timezone.now()
            sweep.last_error = ""
            sweep.save(update_fields=("status", "confirmed_at", "last_error", "updated_at"))
            record_event(
                event_type="sweep.confirmed",
                message="Confirmed a treasury sweep receipt.",
                wallet=sweep.wallet,
                treasury_sweep=sweep,
                transaction_id=sweep.transaction_id,
                asset_code=sweep.asset_code,
                amount_atomic=sweep.amount_atomic,
            )
            count += 1
    return count


def _available_amount(
    client: TronGridClient,
    wallet: ManagedWallet,
    asset: PaymentAsset,
    *,
    trx_balance_sun: int | None = None,
) -> int:
    configured = get_tron_settings()
    if trx_balance_sun is None:
        trx_balance_sun = client.get_trx_balance_sun(wallet.address)
    if asset.kind.upper() == "TRX":
        reserve_sun = configured.trx_sweep_reserve_sun
        if any(configured_asset.kind.upper() == "TRC20" for configured_asset in configured.assets):
            reserve_sun = max(reserve_sun, configured.trc20_fee_limit_sun)
        return max(trx_balance_sun - reserve_sun, 0)
    if trx_balance_sun < configured.trc20_fee_limit_sun:
        return 0
    return client.get_trc20_balance(wallet.address, asset)


def _create_sweep(wallet: ManagedWallet, asset: PaymentAsset, amount: int):
    with transaction.atomic():
        exists = TreasurySweep.objects.select_for_update().filter(
            wallet=wallet,
            asset_code=asset.code,
            status__in=ACTIVE_SWEEP_STATUSES,
        ).exists()
        if exists:
            return None, False
        return TreasurySweep.objects.create(
            wallet=wallet,
            network=wallet.network,
            asset_code=asset.code,
            asset_kind=asset.kind,
            token_contract_address=asset.contract_address,
            destination_address=get_tron_settings().treasury_address,
            amount_atomic=amount,
            fee_limit_sun=get_tron_settings().trc20_fee_limit_sun if asset.kind == "TRC20" else 0,
        ), True


def _record_insufficient_trx_event(
    *,
    wallet: ManagedWallet,
    asset: PaymentAsset,
    trx_balance_sun: int,
    required_trx_sun: int,
) -> PaymentAuditEvent:
    metadata = {
        "network": wallet.network,
        "asset_code": asset.code,
        "reason": "insufficient_trx_for_fee",
        "trx_balance_sun": trx_balance_sun,
        "required_trx_sun": required_trx_sun,
    }
    latest_event = (
        PaymentAuditEvent.objects.filter(
            wallet=wallet,
            event_type="sweep.skipped",
            metadata__asset_code=asset.code,
        )
        .order_by("-created_at")
        .first()
    )
    if latest_event is not None and latest_event.metadata == metadata:
        return latest_event
    return record_event(
        event_type="sweep.skipped",
        message=(
            f"Skipped the {asset.code} sweep because the wallet has "
            f"{trx_balance_sun} SUN TRX, below the "
            f"{required_trx_sun} SUN fee requirement."
        ),
        wallet=wallet,
        **metadata,
    )


def _broadcast_sweep(sweep_id) -> bool:
    with transaction.atomic():
        sweep = TreasurySweep.objects.select_for_update().select_related("wallet").get(id=sweep_id)
        if sweep.status != SweepStatus.QUEUED:
            return False
        sweep.status = SweepStatus.BUILDING
        sweep.attempt_count += 1
        sweep.save(update_fields=("status", "attempt_count", "updated_at"))

    def persist_transaction_id(transaction_id: str) -> None:
        with transaction.atomic():
            current_sweep = TreasurySweep.objects.select_for_update().get(id=sweep_id)
            if current_sweep.status != SweepStatus.BUILDING or current_sweep.transaction_id:
                raise RuntimeError("Sweep state changed before transaction broadcast.")
            current_sweep.transaction_id = transaction_id
            current_sweep.save(update_fields=("transaction_id", "updated_at"))

    try:
        transaction_id = broadcast_transfer(
            wallet=sweep.wallet,
            asset=get_tron_settings().asset(sweep.asset_code),
            amount_atomic=sweep.amount_atomic,
            on_transaction_built=persist_transaction_id,
        )
    except Exception:
        with transaction.atomic():
            current_sweep = TreasurySweep.objects.select_for_update().get(id=sweep_id)
            current_sweep.last_error = "Treasury broadcast outcome requires receipt reconciliation."
            if not current_sweep.transaction_id:
                current_sweep.status = SweepStatus.FAILED
            current_sweep.save(update_fields=("status", "last_error", "updated_at"))
        record_event(
            event_type="sweep.failed",
            message="Treasury sweep did not report a successful broadcast.",
            wallet=sweep.wallet,
            treasury_sweep=current_sweep,
            asset_code=sweep.asset_code,
        )
        return False

    with transaction.atomic():
        current_sweep = TreasurySweep.objects.select_for_update().get(id=sweep_id)
        if current_sweep.status != SweepStatus.BUILDING or current_sweep.transaction_id != transaction_id:
            return False
        current_sweep.status = SweepStatus.BROADCAST
        current_sweep.broadcast_at = timezone.now()
        current_sweep.last_error = ""
        current_sweep.save(update_fields=("status", "broadcast_at", "last_error", "updated_at"))
    record_event(
        event_type="sweep.broadcast",
        message="Broadcast a locally signed treasury sweep.",
        wallet=sweep.wallet,
        treasury_sweep=current_sweep,
        transaction_id=transaction_id,
        asset_code=sweep.asset_code,
        amount_atomic=sweep.amount_atomic,
    )
    return True