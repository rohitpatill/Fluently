"""Google OAuth + session: login redirect, callback (mocked Google), /me, logout, the
first-user 'default' data adoption, and the critical per-user data-isolation guarantee.

Google network calls are mocked — no real traffic. The session cookie is the real signed
JWT the backend mints, so these exercise the true auth path end-to-end.
"""

import pytest
from fastapi.testclient import TestClient

from app import mongo, repo
from app.config import settings
from app.main import app
from app.routers import auth as auth_router
from app.services import auth_service


@pytest.fixture(autouse=True)
def _auth_secrets(monkeypatch):
    """Ensure signing secrets exist even if the local .env doesn't set them."""
    monkeypatch.setattr(settings, "session_secret", "test-session-secret", raising=False)
    monkeypatch.setattr(settings, "state_cookie_secret", "test-state-secret", raising=False)
    monkeypatch.setattr(settings, "google_oauth_client_id", "test-client-id", raising=False)
    # No dependency overrides here — we want the REAL auth path.
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _google_claims(sub="google-sub-A", email="a@example.com", name="Alice", verified=True):
    return {
        "iss": "https://accounts.google.com",
        "sub": sub,
        "email": email,
        "email_verified": verified,
        "name": name,
        "picture": f"https://pic/{sub}.png",
        "nonce": "IGNORED-mocked",  # verify_google_id_token is mocked, so nonce isn't checked
    }


def _do_login(client: TestClient, monkeypatch, claims=None) -> None:
    """Drive a full login: /login to get the state cookie, then callback with mocked Google."""
    claims = claims or _google_claims()
    # 1. login sets the signed state cookie (don't follow the redirect to Google).
    r = client.get("/api/auth/google/login", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "accounts.google.com" in r.headers["location"]

    # Recover the state value the backend signed, so we can echo it back like Google would.
    signed = client.cookies.get(auth_router._STATE_COOKIE)
    state, _nonce, _native = auth_service.unsign_state(signed)

    # 2. Mock the Google network hops.
    monkeypatch.setattr(auth_service, "exchange_code_for_tokens", lambda code: {"id_token": "fake"})
    monkeypatch.setattr(auth_service, "verify_google_id_token", lambda tok, nonce: claims)

    r = client.get(
        f"/api/auth/google/callback?code=abc&state={state}", follow_redirects=False
    )
    assert r.status_code in (302, 307)
    assert r.headers["location"] == settings.frontend_url
    # Session cookie is now set on the client.
    assert settings.session_cookie_name in client.cookies


def test_login_redirects_to_google(anon_client):
    r = anon_client.get("/api/auth/google/login", follow_redirects=False)
    assert r.status_code in (302, 307)
    loc = r.headers["location"]
    assert loc.startswith(auth_service.GOOGLE_AUTH_ENDPOINT)
    assert "scope=openid+email+profile" in loc
    assert "response_type=code" in loc
    assert auth_router._STATE_COOKIE in anon_client.cookies


def test_callback_happy_path_creates_user(anon_client, monkeypatch):
    _do_login(anon_client, monkeypatch)
    me = anon_client.get("/api/auth/me").json()
    assert me["email"] == "a@example.com"
    assert me["name"] == "Alice"
    assert me["has_persona"] is False  # brand-new user hasn't onboarded
    assert repo.get_user_by_sub("google-sub-A") is not None


def test_callback_missing_state_cookie_is_rejected(anon_client, monkeypatch):
    monkeypatch.setattr(auth_service, "exchange_code_for_tokens", lambda code: {"id_token": "fake"})
    monkeypatch.setattr(auth_service, "verify_google_id_token", lambda tok, nonce: _google_claims())
    # No prior /login → no state cookie.
    r = anon_client.get("/api/auth/google/callback?code=abc&state=whatever", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "auth_error=1" in r.headers["location"]
    assert settings.session_cookie_name not in anon_client.cookies


def test_callback_state_mismatch_is_rejected(anon_client, monkeypatch):
    anon_client.get("/api/auth/google/login", follow_redirects=False)
    monkeypatch.setattr(auth_service, "exchange_code_for_tokens", lambda code: {"id_token": "fake"})
    monkeypatch.setattr(auth_service, "verify_google_id_token", lambda tok, nonce: _google_claims())
    r = anon_client.get("/api/auth/google/callback?code=abc&state=TAMPERED", follow_redirects=False)
    assert "auth_error=1" in r.headers["location"]
    assert settings.session_cookie_name not in anon_client.cookies


def test_callback_rejects_unverified_email(anon_client, monkeypatch):
    # verify_google_id_token is the real thing here would raise; simulate that by raising.
    anon_client.get("/api/auth/google/login", follow_redirects=False)
    signed = anon_client.cookies.get(auth_router._STATE_COOKIE)
    state, _nonce, _native = auth_service.unsign_state(signed)

    def _raise(tok, nonce):
        raise auth_service.AuthError("Google account email is not verified")

    monkeypatch.setattr(auth_service, "exchange_code_for_tokens", lambda code: {"id_token": "fake"})
    monkeypatch.setattr(auth_service, "verify_google_id_token", _raise)
    r = anon_client.get(f"/api/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    assert "auth_error=1" in r.headers["location"]


def test_me_requires_auth(anon_client):
    assert anon_client.get("/api/auth/me").status_code == 401


def test_logout_clears_session(anon_client, monkeypatch):
    _do_login(anon_client, monkeypatch)
    assert anon_client.get("/api/auth/me").status_code == 200
    anon_client.post("/api/auth/logout")
    anon_client.cookies.clear()  # browser would drop the deleted cookie
    assert anon_client.get("/api/auth/me").status_code == 401


def test_first_user_adopts_default_data(anon_client, monkeypatch):
    # Seed some legacy "default" data (as the migration would leave behind).
    from app.models import Word

    repo.insert_word(Word(text="legacy", user_id=mongo.DEFAULT_USER_ID))
    repo.set_memory_file("identity", "# User Identity\n\nName: Legacy.\n", mongo.DEFAULT_USER_ID)

    _do_login(anon_client, monkeypatch, _google_claims(sub="first", email="first@x.com"))
    user = repo.get_user_by_sub("first")

    # The first user now owns the legacy word...
    words = repo.list_words(user.id)
    assert any(w.text == "legacy" for w in words)
    # ...and there is no more data left under the sentinel.
    assert repo.list_words(mongo.DEFAULT_USER_ID) == []
    assert user.adopted_default is True


def test_second_user_does_not_adopt(anon_client, monkeypatch):
    from app.models import Word

    repo.insert_word(Word(text="legacy", user_id=mongo.DEFAULT_USER_ID))
    # First user adopts it.
    _do_login(anon_client, monkeypatch, _google_claims(sub="first", email="first@x.com"))
    anon_client.post("/api/auth/logout")
    anon_client.cookies.clear()

    # Second user logs in — starts empty, sees nothing of the first user's data.
    _do_login(anon_client, monkeypatch, _google_claims(sub="second", email="second@x.com"))
    second = repo.get_user_by_sub("second")
    assert repo.list_words(second.id) == []
    assert second.adopted_default is False


def test_data_isolation_between_users(anon_client, monkeypatch):
    """The core guarantee: user A's data is invisible to user B, and survives for A."""
    # User A logs in and adds a word.
    _do_login(anon_client, monkeypatch, _google_claims(sub="A", email="a@x.com"))
    anon_client.post("/api/words", json={"text": "ubiquitous", "kind": "word"})
    a_words = anon_client.get("/api/words").json()
    assert [w["text"] for w in a_words] == ["ubiquitous"]

    # Switch to user B (fresh session).
    anon_client.post("/api/auth/logout")
    anon_client.cookies.clear()
    _do_login(anon_client, monkeypatch, _google_claims(sub="B", email="b@x.com"))

    # B sees NONE of A's words, and adds their own.
    assert anon_client.get("/api/words").json() == []
    anon_client.post("/api/words", json={"text": "serendipity", "kind": "word"})
    assert [w["text"] for w in anon_client.get("/api/words").json()] == ["serendipity"]

    # Back to A — their word is still there, B's is not visible.
    anon_client.post("/api/auth/logout")
    anon_client.cookies.clear()
    _do_login(anon_client, monkeypatch, _google_claims(sub="A", email="a@x.com"))
    assert [w["text"] for w in anon_client.get("/api/words").json()] == ["ubiquitous"]


# ---------------------------------------------------------------- native app (Capacitor)
# The native app can't use the session COOKIE: its WebView origin (https://localhost) has a
# separate cookie jar from the system browser where Google login runs. So login is started
# with ?native=1, and the callback hands the session JWT back through the app's custom-scheme
# deep link; the app then authenticates with `Authorization: Bearer <jwt>`.


def test_state_carries_native_flag_signed():
    """The native marker round-trips inside the SIGNED state (can't be tampered with)."""
    state, nonce = auth_service.new_state_and_nonce()

    signed_native = auth_service.sign_state(state, nonce, native=True)
    assert auth_service.unsign_state(signed_native) == (state, nonce, True)

    signed_web = auth_service.sign_state(state, nonce)
    assert auth_service.unsign_state(signed_web) == (state, nonce, False)


def test_native_callback_redirects_to_deep_link_with_token(anon_client, monkeypatch):
    """?native=1 → callback redirects to the app's deep link carrying a usable session JWT,
    and does NOT set a session cookie (the app's WebView could never read it)."""
    r = anon_client.get("/api/auth/google/login?native=1", follow_redirects=False)
    assert r.status_code in (302, 307)

    signed = anon_client.cookies.get(auth_router._STATE_COOKIE)
    state, _nonce, native = auth_service.unsign_state(signed)
    assert native is True

    monkeypatch.setattr(auth_service, "exchange_code_for_tokens", lambda code: {"id_token": "fake"})
    monkeypatch.setattr(auth_service, "verify_google_id_token", lambda tok, nonce: _google_claims())

    r = anon_client.get(
        f"/api/auth/google/callback?code=abc&state={state}", follow_redirects=False
    )
    assert r.status_code in (302, 307)
    location = r.headers["location"]
    assert location.startswith(settings.native_app_redirect)
    assert "token=" in location
    # No session cookie for the native flow.
    assert settings.session_cookie_name not in r.cookies

    # The handed-back token is a valid session for a real user.
    token = location.split("token=", 1)[1]
    from urllib.parse import unquote
    user_id = auth_service.decode_session_jwt(unquote(token))
    assert repo.get_user(user_id) is not None


def test_bearer_token_authenticates_like_the_cookie(anon_client, monkeypatch):
    """A bearer token is accepted anywhere the cookie is — same user, same data."""
    _do_login(anon_client, monkeypatch, _google_claims(sub="native-1", email="n@x.com"))
    me_via_cookie = anon_client.get("/api/auth/me").json()

    token = auth_service.mint_session_jwt(me_via_cookie["id"])
    anon_client.cookies.clear()  # prove the cookie is NOT what's authenticating us

    r = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["id"] == me_via_cookie["id"]


def test_bad_bearer_token_is_rejected(anon_client):
    """A tampered/garbage bearer token yields 401, never a 500."""
    r = anon_client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert r.status_code == 401


def test_native_auth_error_redirects_to_deep_link(anon_client, monkeypatch):
    """A failed native login bounces back into the APP (not the website) with an error flag."""
    anon_client.get("/api/auth/google/login?native=1", follow_redirects=False)
    signed = anon_client.cookies.get(auth_router._STATE_COOKIE)
    state, _nonce, _native = auth_service.unsign_state(signed)

    def _raise(tok, nonce):
        raise auth_service.AuthError("Google account email is not verified")

    monkeypatch.setattr(auth_service, "exchange_code_for_tokens", lambda code: {"id_token": "fake"})
    monkeypatch.setattr(auth_service, "verify_google_id_token", _raise)

    r = anon_client.get(
        f"/api/auth/google/callback?code=abc&state={state}", follow_redirects=False
    )
    assert r.headers["location"].startswith(settings.native_app_redirect)
    assert "auth_error=1" in r.headers["location"]


def test_websocket_auth_accepts_token_query_param(monkeypatch):
    """WS auth (voice / assistant) accepts `?token=` — the native app's only option, since a
    WebSocket cannot send an Authorization header. Cookie remains valid for the website."""
    from app import deps

    class _FakeWS:
        def __init__(self, query=None, cookies=None):
            self.query_params = query or {}
            self.cookies = cookies or {}

    user, _ = repo.upsert_user_from_google(sub="ws-sub", email="ws@x.com")
    token = auth_service.mint_session_jwt(user.id)

    # 1. native transport: token in the query string
    assert deps.user_id_from_websocket(_FakeWS(query={"token": token})) == user.id

    # 2. web transport: token in the session cookie (unchanged behavior)
    assert deps.user_id_from_websocket(
        _FakeWS(cookies={settings.session_cookie_name: token})
    ) == user.id

    # 3. no credentials at all → None (router closes the socket)
    assert deps.user_id_from_websocket(_FakeWS()) is None

    # 4. garbage token → None, never an exception
    assert deps.user_id_from_websocket(_FakeWS(query={"token": "nope"})) is None
