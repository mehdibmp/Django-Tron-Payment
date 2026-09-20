"""Private-key cipher resolution."""

from __future__ import annotations

from typing import cast

from django.utils.module_loading import import_string

from django_tron_payments.conf import get_tron_settings
from django_tron_payments.crypto.base import KeyCipher


def get_key_cipher() -> KeyCipher:
    """Instantiate the configured key cipher.

    The configured class must implement ``encrypt(bytes) -> str`` and
    ``decrypt(str) -> bytes``. This seam supports envelope encryption with a KMS,
    HSM, or another managed secrets system without modifying payment logic.
    """
    cipher_class = import_string(get_tron_settings().encryption_backend)
    return cast(KeyCipher, cipher_class())
