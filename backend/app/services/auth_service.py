"""Google OAuth 2.0 (server-side Authorization Code flow) + JWT session handling.

Pure, framework-agnostic helpers — no FastAPI types leak in here, so every function is
unit-testable in isolation. The router (`routers/auth.py`) wires these into HTTP; the
session dependency (`deps.py`) uses `decode_session_jwt`.

Security model (verified against current Google identity + library docs):
  - Server-side code flow: Google tokens NEVER reach the browser.
  - A short-lived, signed, HttpOnly cookie carries the CSRF `state` + OIDC `nonce` across
    the redirect (no server-side session store needed).
  - The ID token is verified via `google-auth` (signature against Google's JWKS, `exp`,
    `aud`), and we ADDITIONALLY assert `iss`, `nonce`, and `email_verified` ourselves.
  - The login session is a stateless JWT (HS256) stored in an HttpOnly cookie.
"""

from __future__ import annotations

import secrets
import time
from urllib.parse import urlencode

import httpx
import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from ..config import settings

# Google endpoints (stable, documented).
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = "openid email profile"
_VALID_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

# The OAuth handshake must complete within this window (seconds).
STATE_MAX_AGE = 300
_JWT_ALGORITHM = "HS256"
_STATE_SEPARATOR = ":"

# One reusable transport for ID-token verification; it caches Google's public keys.
_google_request = google_requests.Request()


class AuthError(Exception):
    """Raised on any OAuth/session verification failure — the router turns this into a
    friendly auth-error redirect rather than leaking internals to the browser."""


# --------------------------------------------------------------------------- state / nonce
def new_state_and_nonce() -> tuple[str, str]:
    """Fresh, cryptographically strong CSRF state + OIDC nonce."""
    return secrets.token_urlsafe(32), secrets.token_urlsafe(32)


def sign_state(state: str, nonce: str) -> str:
    """Sign `state:nonce` into an opaque, tamper-evident cookie value."""
    signer = TimestampSigner(settings.state_cookie_secret)
    return signer.sign(f"{state}{_STATE_SEPARATOR}{nonce}".encode()).decode()


def unsign_state(signed: str, max_age: int = STATE_MAX_AGE) -> tuple[str, str]:
    """Recover (state, nonce) from the signed cookie, enforcing signature + freshness."""
    signer = TimestampSigner(settings.state_cookie_secret)
    try:
        raw = signer.unsign(signed, max_age=max_age).decode()
    except (BadSignature, SignatureExpired) as exc:
        raise AuthError("Invalid or expired OAuth state") from exc
    state, _, nonce = raw.partition(_STATE_SEPARATOR)
    if not state or not nonce:
        raise AuthError("Malformed OAuth state")
    return state, nonce


# --------------------------------------------------------------------------- Google flow
def build_google_auth_url(state: str, nonce: str) -> str:
    """Build the Google consent-screen URL for the authorization-code flow."""
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "state": state,
        "nonce": nonce,
        "access_type": "online",       # login-only: no refresh token needed
        "prompt": "select_account",    # always let the user pick which Google account
    }
    return f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange the authorization `code` for tokens at Google's token endpoint."""
    try:
        resp = httpx.post(
            GOOGLE_TOKEN_ENDPOINT,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": settings.google_redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise AuthError("Failed to exchange authorization code with Google") from exc
    return resp.json()


def verify_google_id_token(raw_id_token: str, expected_nonce: str) -> dict:
    """Verify a Google ID token and return its validated claims.

    `google-auth` checks the signature (via Google's JWKS), `exp`, and `aud`. We then
    assert `iss`, `nonce`, and `email_verified` ourselves (defense in depth)."""
    try:
        claims = google_id_token.verify_oauth2_token(
            raw_id_token,
            _google_request,
            audience=settings.google_oauth_client_id,
            clock_skew_in_seconds=10,
        )
    except ValueError as exc:
        raise AuthError("Google ID token failed verification") from exc

    if claims.get("iss") not in _VALID_ISSUERS:
        raise AuthError("Google ID token has an invalid issuer")
    if claims.get("nonce") != expected_nonce:
        raise AuthError("Google ID token nonce mismatch — possible replay")
    if not claims.get("email_verified", False):
        raise AuthError("Google account email is not verified")
    return claims


# --------------------------------------------------------------------------- session JWT
def mint_session_jwt(user_id: str) -> str:
    """Issue a signed session token (HS256) carrying the internal user id."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + settings.session_max_age_days * 24 * 60 * 60,
    }
    return jwt.encode(payload, settings.session_secret, algorithm=_JWT_ALGORITHM)


def decode_session_jwt(token: str) -> str:
    """Validate a session token and return the internal user id. Raises AuthError on any
    problem (expired, tampered, wrong algorithm)."""
    try:
        payload = jwt.decode(token, settings.session_secret, algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid or expired session") from exc
    user_id = payload.get("sub")
    if not user_id:
        raise AuthError("Session token is missing a subject")
    return user_id


def session_max_age_seconds() -> int:
    """Cookie Max-Age (seconds) matching the JWT lifetime."""
    return settings.session_max_age_days * 24 * 60 * 60
