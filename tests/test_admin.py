from unittest.mock import patch

import pytest
from django.urls import reverse

from django_tron_payments.admin import ManagedWalletAdmin
from django_tron_payments.models import ManagedWallet
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
def test_wallet_admin_never_includes_private_key_ciphertext():
    model_admin = ManagedWalletAdmin(ManagedWallet, admin_site=None)

    assert "encrypted_private_key" in model_admin.exclude
    assert "encrypted_private_key" not in model_admin.readonly_fields
