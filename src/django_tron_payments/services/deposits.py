"""Persist confirmed inbound transfers from TronGrid."""

from __future__ import annotations

from django.db import IntegrityError

from django_tron_payments.clients.trongrid import TronGridClient
from django_tron_payments.conf import PaymentAsset, get_tron_settings
from django_tron_payments.constants import PaymentStatus
from django_tron_payments.models import IncomingPayment, ManagedWallet
from django_tron_payments.services.audit import record_event


def reconcile_wallet(*, wallet: ManagedWallet) -> int:
    """Record new, configured-asset transfers that TronGrid reports as confirmed."""
    configured = get_tron_settings()
    if wallet.network != configured.network:
        return 0

    client = TronGridClient(configured)
    created_count = 0
    for asset in configured.assets:
        for transfer in client.confirmed_transfers(wallet.address, asset):
            if transfer.amount_atomic < asset.minimum_deposit_atomic:
                continue
            payment, created = _create_payment(wallet, asset, transfer)
            if not created:
                continue
            created_count += 1
            record_event(
                event_type="payment.confirmed",
                message="Recorded a confirmed inbound transfer.",
                wallet=wallet,
                incoming_payment=payment,
                transaction_id=payment.transaction_id,
                asset_code=payment.asset_code,
                amount_atomic=payment.amount_atomic,
            )
    return created_count


def reconcile_active_wallets() -> int:
    """Reconcile every active wallet on the configured network once."""
    configured = get_tron_settings()
    total = 0
    wallets = ManagedWallet.objects.filter(network=configured.network, status="active")
    for wallet in wallets.iterator():
        total += reconcile_wallet(wallet=wallet)
    return total


def _create_payment(wallet: ManagedWallet, asset: PaymentAsset, transfer):
    """Use the network event identity as an idempotency key."""
    try:
        return IncomingPayment.objects.get_or_create(
            network=wallet.network,
            asset_code=asset.code,
            transaction_id=transfer.transaction_id,
            event_index=transfer.event_index,
            defaults={
                "wallet": wallet,
                "asset_kind": asset.kind,
                "token_contract_address": asset.contract_address,
                "sender_address": transfer.sender_address,
                "recipient_address": transfer.recipient_address,
                "amount_atomic": transfer.amount_atomic,
                "observed_at": transfer.observed_at,
                "confirmed_at": transfer.observed_at,
                "status": PaymentStatus.CONFIRMED,
                "raw_payload": transfer.raw_payload,
            },
        )
    except IntegrityError:
        return (
            IncomingPayment.objects.get(
                network=wallet.network,
                asset_code=asset.code,
                transaction_id=transfer.transaction_id,
                event_index=transfer.event_index,
            ),
            False,
        )
