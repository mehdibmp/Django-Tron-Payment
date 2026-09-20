from cryptography.fernet import Fernet

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from django_tron_payments.crypto.fernet import FernetKeyCipher


@pytest.mark.django_db
def test_fernet_cipher_round_trips_private_key_material():
    cipher = FernetKeyCipher()

    encrypted = cipher.encrypt(b"a" * 64)

    assert encrypted != "a" * 64
    assert cipher.decrypt(encrypted) == b"a" * 64


@pytest.mark.django_db
def test_fernet_cipher_rejects_missing_keys():
    with override_settings(TRON_PAYMENTS={
        "TRONGRID_API_KEY": "test-api-key",
        "TREASURY_ADDRESS": "TJRyWwFs9wTFGZg3JbrwxJ5dUN76iZqR5w",
        "ENCRYPTION_OPTIONS": {"FERNET_KEYS": []},
    }):
        with pytest.raises(ImproperlyConfigured):
            FernetKeyCipher()


@pytest.mark.django_db
def test_fernet_cipher_accepts_rotated_key_ring():
    old_key = Fernet.generate_key().decode("ascii")
    new_key = Fernet.generate_key().decode("ascii")
    with override_settings(TRON_PAYMENTS={
        "TRONGRID_API_KEY": "test-api-key",
        "TREASURY_ADDRESS": "TJRyWwFs9wTFGZg3JbrwxJ5dUN76iZqR5w",
        "ENCRYPTION_OPTIONS": {"FERNET_KEYS": [new_key, old_key]},
    }):
        cipher = FernetKeyCipher()
        assert cipher.decrypt(cipher.encrypt(b"private-key")) == b"private-key"
