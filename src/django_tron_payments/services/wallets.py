"""Creation and retrieval of custodial user deposit wallets."""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction
from tronpy.keys import PrivateKey

from django_tron_payments.conf import get_tron_settings
from django_tron_payments.crypto.factory import get_key_cipher
from django_tron_payments.models import ManagedWallet
from django_tron_payments.services.audit import record_event


def get_or_create_wallet(*, user: Any) -> ManagedWallet:
    """Return the active-network wallet for a user without exposing its private key."""
    configured = get_tron_settings()
    existing_wallet = ManagedWallet.objects.filter(
        user=user,
        network=configured.network,
    ).first()
    if existing_wallet is not None:
        return existing_wallet

    private_key = PrivateKey.random()
    address = private_key.public_key.to_base58check_address()
    cipher = get_key_cipher()
    encrypted_private_key = cipher.encrypt(private_key.hex().encode("ascii"))

    try:
        with transaction.atomic():
            wallet = ManagedWallet.objects.create(
                user=user,
                network=configured.network,
                address=address,
                encrypted_private_key=encrypted_private_key,
                encryption_backend=configured.encryption_backend,
            )
    except IntegrityError:
        wallet = ManagedWallet.objects.get(user=user, network=configured.network)
    else:
        record_event(
            event_type="wallet.created",
            message="Created a managed deposit wallet.",
            wallet=wallet,
            network=wallet.network,
            address=wallet.address,
        )
    return wallet


def public_wallet_address(*, user: Any) -> str:
    """Get the safe-to-display deposit address for a host-project user."""
    return get_or_create_wallet(user=user).address
