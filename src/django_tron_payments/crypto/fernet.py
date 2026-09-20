"""Fernet and MultiFernet-based private-key encryption.

For production deployments, keep Fernet keys in a managed secret store and rotate
them with MultiFernet. Projects needing envelope encryption can replace this backend
through ``TRON_PAYMENTS["ENCRYPTION_BACKEND"]`` and provide provider-specific
options with ``TRON_PAYMENTS["ENCRYPTION_OPTIONS"]``.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.core.exceptions import ImproperlyConfigured

from django_tron_payments.conf import get_tron_settings


class FernetKeyCipher:
    """Encrypt and decrypt private-key bytes with one or more Fernet keys."""

    def __init__(self) -> None:
        configured_keys = get_tron_settings().encryption_options.get("FERNET_KEYS", ())
        if not isinstance(configured_keys, (list, tuple)) or not configured_keys:
            raise ImproperlyConfigured(
                "TRON_PAYMENTS['ENCRYPTION_OPTIONS']['FERNET_KEYS'] must contain at "
                "least one Fernet key when using the built-in FernetKeyCipher."
            )
        if not all(isinstance(key, str) for key in configured_keys):
            raise ImproperlyConfigured(
                "TRON_PAYMENTS['ENCRYPTION_OPTIONS']['FERNET_KEYS'] must contain "
                "only strings."
            )
        try:
            self._cipher = MultiFernet(
                [Fernet(key.encode("ascii")) for key in configured_keys]
            )
        except (TypeError, ValueError, UnicodeEncodeError) as exc:
            raise ImproperlyConfigured(
                "TRON_PAYMENTS['ENCRYPTION_OPTIONS']['FERNET_KEYS'] contains an "
                "invalid Fernet key."
            ) from exc

    def encrypt(self, plaintext: bytes) -> str:
        """Return an authenticated encrypted text token."""
        return self._cipher.encrypt(plaintext).decode("ascii")

    def decrypt(self, token: str) -> bytes:
        """Return the original private-key bytes or fail without disclosing key data."""
        try:
            return self._cipher.decrypt(token.encode("ascii"))
        except InvalidToken as exc:
            raise ImproperlyConfigured(
                "A stored wallet private key could not be decrypted with the configured cipher."
            ) from exc
