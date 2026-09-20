"""Protocols for encrypting custodial private keys at rest."""

from __future__ import annotations

from typing import Protocol


class KeyCipher(Protocol):
    """A pluggable cipher implemented by Fernet, KMS, or an HSM adapter."""

    def encrypt(self, plaintext: bytes) -> str:
        """Encrypt plaintext and return a database-safe token."""

    def decrypt(self, ciphertext: str) -> bytes:
        """Decrypt a token created by this cipher."""
