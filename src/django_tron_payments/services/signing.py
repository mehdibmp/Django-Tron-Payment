"""Local transaction signing for managed wallets."""

from __future__ import annotations

from tronpy.keys import PrivateKey

from django_tron_payments.clients.base import TronClientError
from django_tron_payments.clients.trongrid import TronGridClient
from django_tron_payments.conf import PaymentAsset, get_tron_settings
from django_tron_payments.crypto.factory import get_key_cipher
from django_tron_payments.models import ManagedWallet


def broadcast_transfer(
    *,
    wallet: ManagedWallet,
    asset: PaymentAsset,
    amount_atomic: int,
    on_transaction_built,
) -> str:
    """Build and sign locally, persist its ID, then submit a treasury transfer."""
    configured = get_tron_settings()
    client = TronGridClient(configured)
    cipher = get_key_cipher()
    private_key = PrivateKey.fromhex(
        cipher.decrypt(wallet.encrypted_private_key).decode("ascii")
    )
    try:
        if asset.kind == "TRX":
            transaction = (
                client.sdk.trx.transfer(wallet.address, configured.treasury_address, amount_atomic)
                .build()
                .sign(private_key)
            )
        else:
            contract = client.sdk.get_contract(asset.contract_address)
            transaction = (
                contract.functions.transfer(configured.treasury_address, amount_atomic)
                .with_owner(wallet.address)
                .fee_limit(configured.trc20_fee_limit_sun)
                .build()
                .sign(private_key)
            )
        transaction_id = str(transaction.txid)
        on_transaction_built(transaction_id)
        result = transaction.broadcast()
    except Exception as exc:
        raise TronClientError("Unable to build, sign, persist, or broadcast the treasury transfer.") from exc

    if not result.get("result"):
        raise TronClientError("TronGrid rejected the treasury transfer broadcast.")
    return transaction_id