"""Bring-your-own-key model config: tier catalogue, key verify+store (encrypted), tier
switching, status hiding the key, and the LLM-route gate for users without a model.

`model_service.verify_key` is mocked everywhere — no real Gemini traffic. The ENCRYPTION_KEY
used to encrypt/decrypt comes from .env (never hardcoded in tests). We assert the plaintext
key is NEVER persisted.
"""

import pytest
from bson import ObjectId

from app import mongo, repo
from app.deps import get_current_user, get_current_user_obj
from app.main import app
from app.models import User
from app.services import crypto_service, model_service
from tests.conftest import TEST_USER_ID


@pytest.fixture
def ok_verify(monkeypatch):
    """Pretend every key verifies successfully."""
    monkeypatch.setattr(model_service, "verify_key", lambda api_key, tier: True)


@pytest.fixture
def bad_verify(monkeypatch):
    """Pretend every key fails verification."""
    monkeypatch.setattr(model_service, "verify_key", lambda api_key, tier: False)


# ---------- tier catalogue ----------
def test_tiers_lists_swift_and_sage(client):
    tiers = client.get("/api/model/tiers").json()
    keys = {t["key"] for t in tiers}
    assert keys == {"swift", "sage"}
    swift = next(t for t in tiers if t["key"] == "swift")
    assert swift["model"] == "gemini-3.1-flash-lite"
    assert "price" in swift and "tagline" in swift


# ---------- status ----------
def test_status_reports_configured_user(client):
    # conftest seeds TEST_USER_ID with a key + swift tier.
    s = client.get("/api/model/status").json()
    assert s["has_key"] is True
    assert s["tier"] == "swift"


def test_status_never_returns_the_key(client):
    body = client.get("/api/model/status").text
    assert "encrypted_api_key" not in body
    assert "api_key" not in body


# ---------- set key ----------
def test_set_key_verifies_encrypts_and_stores(client, ok_verify):
    r = client.post("/api/model/key", json={"api_key": "AIza-secret-plain", "tier": "sage"})
    assert r.status_code == 200
    assert r.json() == {"has_key": True, "tier": "sage"}

    # The plaintext must NOT be in the DB; the stored value must decrypt back to it.
    doc = mongo.users_col().find_one({"_id": ObjectId(TEST_USER_ID)})
    assert doc["model_tier"] == "sage"
    assert doc["encrypted_api_key"] != "AIza-secret-plain"
    assert "AIza-secret-plain" not in doc["encrypted_api_key"]
    assert crypto_service.decrypt(doc["encrypted_api_key"]) == "AIza-secret-plain"


def test_set_key_rejects_bad_key(client, bad_verify):
    r = client.post("/api/model/key", json={"api_key": "nope", "tier": "swift"})
    assert r.status_code == 400
    # The previously-seeded key must be untouched (still decryptable, not overwritten by "nope").
    doc = mongo.users_col().find_one({"_id": ObjectId(TEST_USER_ID)})
    assert crypto_service.decrypt(doc["encrypted_api_key"]) != "nope"


def test_set_key_rejects_unknown_tier(client, ok_verify):
    r = client.post("/api/model/key", json={"api_key": "AIza-x", "tier": "genius"})
    assert r.status_code == 400


def test_set_key_requires_nonempty_key(client, ok_verify):
    r = client.post("/api/model/key", json={"api_key": "   ", "tier": "swift"})
    assert r.status_code == 400


# ---------- switch tier ----------
def test_switch_tier(client):
    r = client.put("/api/model/tier", json={"tier": "sage"})
    assert r.status_code == 200
    assert r.json()["tier"] == "sage"
    assert repo.get_user(TEST_USER_ID).model_tier == "sage"


def test_switch_tier_unknown(client):
    assert client.put("/api/model/tier", json={"tier": "genius"}).status_code == 400


def test_switch_tier_requires_existing_key(client):
    # Wipe the seeded key, then a tier switch must be refused.
    mongo.users_col().update_one(
        {"_id": ObjectId(TEST_USER_ID)}, {"$set": {"encrypted_api_key": "", "model_tier": ""}}
    )
    assert client.put("/api/model/tier", json={"tier": "swift"}).status_code == 400


# ---------- the LLM-route gate ----------
def test_chat_gated_when_no_model_configured(client):
    """A user with no key must get 403 (not 500) from an LLM-using route."""
    mongo.users_col().update_one(
        {"_id": ObjectId(TEST_USER_ID)}, {"$set": {"encrypted_api_key": "", "model_tier": ""}}
    )
    # get_current_user_obj is overridden in conftest to a static User with a key — override it
    # here to reflect the now-unconfigured DB user so require_model_configured sees the truth.
    unconfigured = User(id=TEST_USER_ID, google_sub=f"sub-{TEST_USER_ID}",
                        email="x@example.com", name="Test User",
                        encrypted_api_key="", model_tier="")
    app.dependency_overrides[get_current_user_obj] = lambda: unconfigured
    try:
        # need a conversation id to hit the route; create is ALSO gated, so assert on it too.
        r = client.post("/api/conversations", json={"suggest_topics": False})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user_obj, None)
