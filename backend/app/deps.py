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


def _user_from_request(request: Request) -> User:
    """Resolve and authenticate the current user from the session cookie, or raise 401."""
    token = request.cookies.get(settings.session_cookie_name)
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


def require_model_configured(user: User = Depends(get_current_user_obj)) -> str:
    """Like `get_current_user`, but ALSO requires the user to have finished the
    'How smart should I be?' setup (a stored key + tier). LLM-using routes depend on this so
    an unconfigured user gets a clean 403 the frontend turns into the model-config gate —
    rather than a 500 from `model_service.resolve_for_user` deep in a service.

    Built on `get_current_user_obj` so test overrides of the current user flow through here."""
    if not (user.encrypted_api_key and user.model_tier):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No model configured")
    return user.id
