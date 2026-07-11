"""Symmetric encryption for users' bring-your-own API keys.

We store each user's Gemini API key ENCRYPTED (Fernet / AES-128-CBC + HMAC, authenticated).
The symmetric key lives ONLY in `.env` (`ENCRYPTION_KEY`), never in the database — so a DB
leak alone yields useless ciphertext. This module is the single seam that does the crypto;
everything else deals in either plaintext (transiently, in memory) or ciphertext (at rest).
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from ..config import settings


class CryptoError(Exception):
    """Raised when encryption/decryption can't proceed (misconfig or tampered ciphertext)."""


def _fernet() -> Fernet:
    key = (settings.encryption_key or "").strip()
    if not key:
        raise CryptoError(
            "ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
            "and put it in backend/.env."
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as e:
        raise CryptoError("ENCRYPTION_KEY is not a valid Fernet key (must be 32 url-safe base64 bytes).") from e


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext secret → url-safe ciphertext string suitable for DB storage."""
    if plaintext is None:
        plaintext = ""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt ciphertext produced by `encrypt`. Raises CryptoError on tamper/wrong key."""
    if not ciphertext:
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise CryptoError("Could not decrypt stored key (wrong ENCRYPTION_KEY or corrupted data).") from e
