"""Auth dependencies — the single seam that resolves the current user for every route.

Routers depend on `get_current_user` (returns the internal `user_id` string) instead of the
old hardcoded `DEFAULT_USER_ID`. Tests override `get_current_user` to run as a fixed user
without a real cookie (see `tests/conftest.py`).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from . import repo
from .config import settings
from .models import User
from .services import auth_service


def _session_token(request: Request) -> str | None:
    """The caller's session JWT, from either transport.

    Two transports carry the SAME signed session JWT, so everything downstream is identical:

    * `Authorization: Bearer <jwt>` — used by the NATIVE app (Capacitor). The app's WebView
      lives on its own origin (`https://localhost`) and cannot share the browser's cookie jar,
      so it stores the JWT itself and sends it as a header.
    * the HttpOnly session cookie — used by the WEBSITE, exactly as before.

    The header is checked first (only the native app sends it); the cookie remains the
    fallback, so web behavior is completely unchanged.
    """
    header = request.headers.get("Authorization") or ""
    scheme, _, value = header.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return request.cookies.get(settings.session_cookie_name)


def _user_from_request(request: Request) -> User:
    """Resolve and authenticate the current user from the bearer token or session cookie."""
    token = _session_token(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        user_id = auth_service.decode_session_jwt(token)
    except auth_service.AuthError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    user = repo.get_user(user_id)
    if user is None:
        # Token is well-formed but the account no longer exists.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return user


def get_current_user(request: Request) -> str:
    """FastAPI dependency yielding the current user's internal `user_id`."""
    return _user_from_request(request).id


def get_current_user_obj(request: Request) -> User:
    """FastAPI dependency yielding the full current-user profile (for `/me`)."""
    return _user_from_request(request)


def user_id_from_websocket(ws) -> str | None:
    """Resolve the current user's id on a WEBSOCKET handshake, or None if unauthenticated.

    WebSocket routers must authenticate by hand (the HTTP `Depends` chain can't raise an
    HTTPException on a WS handshake), so this is the shared seam they all call — keeping WS
    auth identical to HTTP auth in one place.

    Two transports, in priority order:
      1. `?token=<jwt>` query param — used by the NATIVE app. The browser WebSocket API cannot
         send custom headers, so a bearer header is impossible here; the token therefore rides
         in the query string (over WSS it is encrypted in transit like any other URL).
      2. the session cookie — used by the WEBSITE, exactly as before.
    """
    token = ws.query_params.get("token") or ws.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    try:
        user_id = auth_service.decode_session_jwt(token)
    except auth_service.AuthError:
        return None
    return user_id if repo.get_user(user_id) is not None else None


def require_model_configured(user: User = Depends(get_current_user_obj)) -> str:
    """Like `get_current_user`, but ALSO requires the user to have finished the
    'How smart should I be?' setup (a stored key + tier). LLM-using routes depend on this so
    an unconfigured user gets a clean 403 the frontend turns into the model-config gate —
    rather than a 500 from `model_service.resolve_for_user` deep in a service.

    Built on `get_current_user_obj` so test overrides of the current user flow through here."""
    if not (user.encrypted_api_key and user.model_tier):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No model configured")
    return user.id
