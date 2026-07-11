"""Google OAuth ("Continue with Google") + session endpoints.

Flow:
  GET  /api/auth/google/login     → redirect to Google's consent screen (sets a signed
                                     state/nonce cookie for CSRF + replay protection).
  GET  /api/auth/google/callback  → verify state, exchange code, verify ID token, upsert the
                                     user (first user adopts legacy "default" data), mint a
                                     session cookie, and bounce back to the frontend.
  GET  /api/auth/me               → the current user's profile (+ whether onboarding is done).
  POST /api/auth/logout           → clear the session cookie.
"""

import secrets

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from .. import repo
from ..config import settings
from ..deps import get_current_user_obj
from ..models import User
from ..schemas import MeResponse
from ..services import auth_service, memory_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

# The signed state/nonce cookie lives only for the duration of the handshake and is scoped
# to the auth routes so it isn't sent on every API call.
_STATE_COOKIE = "fluently_oauth_state"
_STATE_COOKIE_PATH = "/api/auth"


def _set_state_cookie(response: Response, value: str) -> None:
    response.set_cookie(
        _STATE_COOKIE,
        value,
        max_age=auth_service.STATE_MAX_AGE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=_STATE_COOKIE_PATH,
    )


def _clear_state_cookie(response: Response) -> None:
    response.delete_cookie(_STATE_COOKIE, path=_STATE_COOKIE_PATH)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=auth_service.session_max_age_seconds(),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _auth_error_redirect() -> RedirectResponse:
    """Bounce the browser back to the SPA with a flag it can surface gently."""
    return RedirectResponse(f"{settings.frontend_url}/?auth_error=1")


@router.get("/google/login")
def google_login():
    """Kick off the OAuth flow: set the state/nonce cookie and redirect to Google."""
    state, nonce = auth_service.new_state_and_nonce()
    response = RedirectResponse(auth_service.build_google_auth_url(state, nonce))
    _set_state_cookie(response, auth_service.sign_state(state, nonce))
    return response


@router.get("/google/callback")
def google_callback(request: Request, code: str | None = None, state: str | None = None):
    """Handle Google's redirect: validate everything, establish the session, go to the SPA."""
    signed_state = request.cookies.get(_STATE_COOKIE)
    if not code or not state or not signed_state:
        return _auth_error_redirect()

    try:
        expected_state, expected_nonce = auth_service.unsign_state(signed_state)
        # Constant-time comparison guards against timing side-channels.
        if not secrets.compare_digest(expected_state, state):
            raise auth_service.AuthError("OAuth state mismatch — possible CSRF")

        tokens = auth_service.exchange_code_for_tokens(code)
        claims = auth_service.verify_google_id_token(tokens.get("id_token", ""), expected_nonce)
    except auth_service.AuthError:
        return _auth_error_redirect()

    # Is this the very first user? If so, they adopt the legacy "default" data.
    first_user = not repo.has_any_user()

    user, created = repo.upsert_user_from_google(
        sub=claims["sub"],
        email=claims.get("email", ""),
        name=claims.get("name", ""),
        picture=claims.get("picture", ""),
    )

    if created and first_user:
        repo.reassign_default_data(user.id)
    # Ensure the user's 3 memory-file docs exist (adoption already brought them for the
    # first user; this bootstraps everyone else).
    memory_service.ensure_files(user.id)

    response = RedirectResponse(settings.frontend_url)
    _set_session_cookie(response, auth_service.mint_session_jwt(user.id))
    _clear_state_cookie(response)
    return response


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user_obj)):
    """The current user's profile plus whether they've finished onboarding (persona set)."""
    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        picture=user.picture,
        has_persona=_has_persona(user.id),
    )


@router.post("/logout")
def logout(response: Response):
    """Clear the session cookie. Idempotent — safe to call when already logged out."""
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"ok": True}


def _has_persona(user_id: str) -> bool:
    """A user has completed onboarding once their persona file carries a `Name:` line."""
    for line in memory_service.read_file("persona", user_id).splitlines():
        if line.lower().startswith("name:") and line.split(":", 1)[1].strip():
            return True
    return False
