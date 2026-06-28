"""Secret encryption for channel Apprise URLs.

Channel secrets are encrypted at rest (Fernet) so the database row never
contains a plaintext Apprise URL. The cipher is intentionally minimal:
encryption and decryption only - no key rotation is implemented yet
(key rotation will be added with the dynamic-configuration feature).

The key is loaded from ``ENCRYPTION_KEY`` (URL-safe base64 32-byte key,
per the cryptography library's Fernet requirement).
"""

from __future__ import annotations

from typing import Protocol

__all__ = [
    "FernetSecretCipher",
    "SecretCipher",
    "SecretCipherError",
]


class SecretCipherError(RuntimeError):
    """Raised when a secret cannot be encrypted or decrypted."""


class SecretCipher(Protocol):
    """Symmetric encryption boundary for opaque channel secrets."""

    def encrypt(self, plaintext: str) -> bytes: ...
    def decrypt(self, ciphertext: bytes) -> str: ...


class FernetSecretCipher:
    """A :class:`SecretCipher` backed by :class:`cryptography.fernet.Fernet`.

    The constructor accepts either a pre-built ``Fernet`` instance or a
    URL-safe base64 32-byte key. The class is deterministic (no random
    IV) so the same plaintext always produces a distinct ciphertext, but
    decryption is unique to the supplied key.
    """

    def __init__(self, key_or_fernet: object) -> None:
        from cryptography.fernet import Fernet, InvalidToken

        self._InvalidToken = InvalidToken
        if isinstance(key_or_fernet, Fernet):
            self._fernet = key_or_fernet
            return
        if not isinstance(key_or_fernet, str | bytes):
            raise SecretCipherError(
                "ENCRYPTION_KEY must be a URL-safe base64 string",
            )
        try:
            self._fernet = Fernet(
                key_or_fernet if isinstance(key_or_fernet, bytes) else key_or_fernet.encode("utf-8"),
            )
        except Exception as exc:
            raise SecretCipherError(
                f"invalid ENCRYPTION_KEY: {exc}",
            ) from exc

    def encrypt(self, plaintext: str) -> bytes:
        """Return a Fernet token for ``plaintext`` (URL-safe base64 bytes)."""
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        """Reverse :meth:`encrypt`; raise :class:`SecretCipherError` on tamper."""
        try:
            return self._fernet.decrypt(ciphertext).decode("utf-8")
        except self._InvalidToken as exc:
            raise SecretCipherError("secret decryption failed (bad key or tampered data)") from exc
