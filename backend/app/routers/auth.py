"""Google OAuth ("Continue with Google") + session endpoints.

Flow:
  GET  /api/auth/google/login     → redirect to Google's consent screen (sets a signed
                                     state/nonce cookie for CSRF + replay protection).
                                     `?native=1` marks a login started by the Android app.
  GET  /api/auth/google/callback  → verify state, exchange code, verify ID token, upsert the
                                     user (first user adopts legacy "default" data), then
                                     finish per client:
                                       web    → set the session cookie, redirect to frontend_url
                                       native → redirect to settings.native_app_redirect with
                                                ?token=<session JWT> (no cookie)
  GET  /api/auth/me               → the current user's profile (+ whether onboarding is done).
  POST /api/auth/logout           → clear the session cookie.

WHY the native branch exists: Google refuses OAuth inside embedded WebViews, so the Android app
opens this flow in the SYSTEM BROWSER — whose cookie jar the app's WebView (origin
`https://localhost`) cannot read. The session JWT is therefore handed back through a custom-scheme
deep link and sent afterwards as `Authorization: Bearer` (see `deps._session_token`). The `native`
flag rides inside the SIGNED state cookie so it survives the round-trip to Google untampered.
"""

import secrets
from urllib.parse import quote

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
        samesite=settings.cookie_samesite,
        path=_STATE_COOKIE_PATH,
    )


def _clear_state_cookie(response: Response) -> None:
    response.delete_cookie(
        _STATE_COOKIE,
        path=_STATE_COOKIE_PATH,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=auth_service.session_max_age_seconds(),
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def _auth_error_redirect(native: bool = False) -> RedirectResponse:
    """Bounce back with an error flag the client can surface gently.

    Native gets the app's deep-link scheme (so the system browser hands control back to the
    app, which shows the inline "try again"); web gets the SPA URL exactly as before.
    """
    if native:
        return RedirectResponse(f"{settings.native_app_redirect}?auth_error=1")
    return RedirectResponse(f"{settings.frontend_url}/?auth_error=1")


@router.get("/google/login")
def google_login(native: int = 0):
    """Kick off the OAuth flow: set the state/nonce cookie and redirect to Google.

    `native=1` marks this as a login started by the NATIVE app (opened in the system browser).
    The flag is carried inside the SIGNED state cookie — not a query param — so it survives the
    round-trip to Google and cannot be tampered with, and the callback knows whether to hand
    the session back via the app's deep link or the website.
    """
    state, nonce = auth_service.new_state_and_nonce()
    response = RedirectResponse(auth_service.build_google_auth_url(state, nonce))
    _set_state_cookie(response, auth_service.sign_state(state, nonce, native=bool(native)))
    return response


@router.get("/google/callback")
def google_callback(request: Request, code: str | None = None, state: str | None = None):
    """Handle Google's redirect: validate everything, establish the session, go to the SPA."""
    signed_state = request.cookies.get(_STATE_COOKIE)
    if not code or not state or not signed_state:
        return _auth_error_redirect()

    # `native` comes out of the SIGNED state, so it reflects how the login actually started.
    native = False
    try:
        expected_state, expected_nonce, native = auth_service.unsign_state(signed_state)
        # Constant-time comparison guards against timing side-channels.
        if not secrets.compare_digest(expected_state, state):
            raise auth_service.AuthError("OAuth state mismatch — possible CSRF")

        tokens = auth_service.exchange_code_for_tokens(code)
        claims = auth_service.verify_google_id_token(tokens.get("id_token", ""), expected_nonce)
    except auth_service.AuthError:
        return _auth_error_redirect(native)

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

    session_jwt = auth_service.mint_session_jwt(user.id)

    if native:
        # NATIVE app: the login ran in the system browser (Google forbids embedded WebViews),
        # whose cookie jar the app's WebView cannot read. So hand the session JWT back through
        # the app's custom-scheme deep link; the app stores it and sends it as a bearer token
        # (see deps._session_token). No cookie is set — it would be unreachable anyway.
        response = RedirectResponse(
            f"{settings.native_app_redirect}?token={quote(session_jwt, safe='')}"
        )
        _clear_state_cookie(response)
        return response

    response = RedirectResponse(settings.frontend_url)
    _set_session_cookie(response, session_jwt)
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
        has_key=bool(user.encrypted_api_key and user.model_tier),
        tier=user.model_tier,
    )


@router.post("/logout")
def logout(response: Response):
    """Clear the session cookie. Idempotent — safe to call when already logged out."""
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return {"ok": True}


def _has_persona(user_id: str) -> bool:
    """A user has completed onboarding once their persona file carries a `Name:` line."""
    for line in memory_service.read_file("persona", user_id).splitlines():
        if line.lower().startswith("name:") and line.split(":", 1)[1].strip():
            return True
    return False
