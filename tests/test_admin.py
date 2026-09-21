from unittest.mock import patch

import pytest
from django.urls import reverse

from django_tron_payments.admin import ManagedWalletAdmin
from django_tron_payments.models import ManagedWallet, PaymentAuditEvent
from tests.factories import make_user


@pytest.mark.django_db
def test_operations_dashboard_requires_staff_access(client):
    response = client.get(reverse("django_tron_payments:operations-dashboard"))

    assert response.status_code == 302


@pytest.mark.django_db
def test_staff_can_queue_a_reconciliation_task(client):
    staff_user = make_user(username="operator", is_staff=True)
    client.force_login(staff_user)

    with patch(
        "django_tron_payments.views.reconcile_tron_payments.delay"
    ) as delay:
        response = client.post(
            reverse("django_tron_payments:operations-run", args=("reconcile",))
        )

    assert response.status_code == 302
    delay.assert_called_once_with()


@pytest.mark.django_db
def test_staff_dashboard_shows_insufficient_trx_reason(client, settings):
    staff_user = make_user(username="fee-operator", is_staff=True)
    wallet = ManagedWallet.objects.create(
        user=staff_user,
        network="nile",
        address="TJRyWwFs9wTFGZg3JbrwxJ5dUN76iZqR5w",
        encrypted_private_key="ciphertext",
        encryption_backend="test.backend",
    )
    PaymentAuditEvent.objects.create(
        wallet=wallet,
        event_type="sweep.skipped",
        message="Token sweep was skipped because the wallet lacks fee TRX.",
        metadata={
            "network": "nile",
            "asset_code": "USDT",
            "reason": "insufficient_trx_for_fee",
            "trx_balance_sun": 2_999_999,
            "required_trx_sun": 3_000_000,
        },
    )
    client.force_login(staff_user)

    response = client.get(reverse("django_tron_payments:operations-dashboard"))

    assert response.status_code == 200
    assert b"Token sweeps not queued" in response.content
    assert b"USDT" in response.content
    assert b"2,999,999" not in response.content
    assert b"2999999" in response.content
    assert b"3000000" in response.content


@pytest.mark.django_db
def test_wallet_admin_never_includes_private_key_ciphertext():
    model_admin = ManagedWalletAdmin(ManagedWallet, admin_site=None)

    assert "encrypted_private_key" in model_admin.exclude
    assert "encrypted_private_key" not in model_admin.readonly_fields
