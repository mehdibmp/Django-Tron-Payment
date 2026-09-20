from unittest.mock import patch

import pytest

from django_tron_payments.models import ManagedWallet
from django_tron_payments.services.wallets import get_or_create_wallet, public_wallet_address
from tests.factories import make_user


@pytest.mark.django_db
def test_wallet_creation_returns_only_a_public_address(settings):
    user = make_user()

    wallet = get_or_create_wallet(user=user)

    assert wallet.address.startswith("T")
    assert wallet.encrypted_private_key
    assert wallet.encrypted_private_key != wallet.address
    assert public_wallet_address(user=user) == wallet.address


@pytest.mark.django_db
def test_wallet_is_idempotent_for_one_user_and_network(settings):
    user = make_user()

    first_wallet = get_or_create_wallet(user=user)
    second_wallet = get_or_create_wallet(user=user)

    assert first_wallet.id == second_wallet.id
    assert ManagedWallet.objects.filter(user=user, network="nile").count() == 1


@pytest.mark.django_db
def test_wallet_private_key_is_never_serialized_in_audit_metadata(settings):
    user = make_user()
    wallet = get_or_create_wallet(user=user)

    with patch("django_tron_payments.services.wallets.record_event") as record_event:
        get_or_create_wallet(user=user)

    record_event.assert_not_called()
    assert all(
        wallet.encrypted_private_key not in str(event.metadata)
        for event in wallet.audit_events.all()
    )