"""Settings / data management: hard-delete endpoints."""


def _seed(client):
    """A word with score, a conversation with a message, and memory lines."""
    wid = client.post("/api/words", json={"text": "ubiquitous", "kind": "word"}).json()["id"]
    client.post(f"/api/words/{wid}/adjust", json={"delta": 40, "reason": "seed"})
    cid = client.post("/api/conversations", json={"suggest_topics": False}).json()["conversation"]["id"]
    client.post(f"/api/chat/{cid}", json={"content": "Hello!"})
    client.post("/api/memory/identity/lines", json={"text": "Name: Rohit."})
    client.post("/api/memory/memory/lines", json={"text": "Has a big launch next week."})
    client.put("/api/memory/persona/form", json={"name": "Jack", "relation": "best friend"})
    return wid, cid


def test_purge_conversations_keeps_words_and_memories(client):
    wid, cid = _seed(client)
    r = client.delete("/api/settings/conversations")
    assert r.status_code == 200
    assert r.json()["deleted_conversations"] == 1
    assert r.json()["deleted_messages"] == 2  # user + assistant

    assert client.get("/api/conversations").json() == []
    assert client.get(f"/api/words/{wid}").json()["score"] == 40.0
    assert len(client.get("/api/memory/identity").json()["lines"]) == 1
    # score history survives with detached refs
    events = client.get(f"/api/words/{wid}/events").json()
    assert len(events) == 1 and events[0]["conversation_id"] is None


def test_purge_conversations_scoped_to_one_persona(client):
    """?persona_id= deletes only that persona's chats; other personas' chats survive."""
    # The default persona ("Jack") already exists; make its chat.
    jack = next(p for p in client.get("/api/personas").json() if p["is_active"])
    jack_cid = client.post("/api/conversations", json={"suggest_topics": False}).json()["conversation"]["id"]
    client.post(f"/api/chat/{jack_cid}", json={"content": "Hi Jack"})

    # A second persona with its own chat.
    maya_id = client.post("/api/personas", json={"name": "Maya", "relation": "mentor"}).json()["id"]
    client.post(f"/api/personas/{maya_id}/activate")
    maya_cid = client.post("/api/conversations", json={"suggest_topics": False}).json()["conversation"]["id"]
    client.post(f"/api/chat/{maya_cid}", json={"content": "Hi Maya"})

    # Delete ONLY Jack's conversations.
    r = client.delete(f"/api/settings/conversations?persona_id={jack['id']}")
    assert r.status_code == 200
    assert r.json()["deleted_conversations"] == 1

    remaining = client.get("/api/conversations").json()
    # Listing is scoped to the active persona (Maya) — hers must survive.
    assert [c["id"] for c in remaining] == [maya_cid]
    # Jack's chat is gone.
    assert client.get(f"/api/conversations/{jack_cid}").status_code == 404


def test_purge_conversations_all_personas(client):
    """No persona_id → every persona's chats are removed."""
    jack_cid = client.post("/api/conversations", json={"suggest_topics": False}).json()["conversation"]["id"]
    client.post(f"/api/chat/{jack_cid}", json={"content": "Hi Jack"})
    maya_id = client.post("/api/personas", json={"name": "Maya", "relation": "mentor"}).json()["id"]
    client.post(f"/api/personas/{maya_id}/activate")
    maya_cid = client.post("/api/conversations", json={"suggest_topics": False}).json()["conversation"]["id"]
    client.post(f"/api/chat/{maya_cid}", json={"content": "Hi Maya"})

    r = client.delete("/api/settings/conversations")
    assert r.status_code == 200
    assert r.json()["deleted_conversations"] == 2
    assert client.get("/api/conversations").json() == []


def test_purge_memories_keeps_persona_words_conversations(client):
    wid, cid = _seed(client)
    r = client.delete("/api/settings/memories")
    assert r.status_code == 200

    assert client.get("/api/memory/identity").json()["lines"] == []
    assert client.get("/api/memory/memory").json()["lines"] == []
    assert "Name: Jack" in client.get("/api/memory/persona").json()["raw"]
    assert len(client.get("/api/conversations").json()) == 1
    assert client.get(f"/api/words/{wid}").json()["score"] == 40.0


def test_purge_all_keep_words(client):
    from app import repo
    from tests.conftest import TEST_USER_ID

    wid, _ = _seed(client)
    r = client.post("/api/settings/purge-all", json={"keep_words": True})
    assert r.status_code == 200
    body = r.json()
    assert body["kept_words"] is True and body["deleted_words"] == 0
    assert body["cleared_model"] is False  # keep-words leaves the model config intact

    assert client.get("/api/conversations").json() == []
    assert "Name: Jack" not in client.get("/api/memory/persona").json()["raw"]
    assert client.get("/api/memory/identity").json()["lines"] == []
    word = client.get(f"/api/words/{wid}").json()
    assert word["score"] == 40.0  # proficiency survived
    assert len(client.get(f"/api/words/{wid}/events").json()) == 1
    # model key + tier must SURVIVE a keep-words reset
    user = repo.get_user(TEST_USER_ID)
    assert user.encrypted_api_key and user.model_tier == "swift"


def test_purge_all_full_wipe(client):
    from app import repo
    from tests.conftest import TEST_USER_ID

    wid, _ = _seed(client)
    r = client.post("/api/settings/purge-all", json={"keep_words": False})
    assert r.status_code == 200
    assert r.json()["deleted_words"] == 1
    assert r.json()["cleared_model"] is True  # true full reset also wipes the model config

    assert client.get("/api/words").json() == []
    assert client.get("/api/conversations").json() == []
    for f in ("identity", "memory", "persona"):
        assert client.get(f"/api/memory/{f}").json()["lines"] == []
    # fresh-start check: onboarding trigger condition (no persona Name line)
    assert "Name:" not in client.get("/api/memory/persona").json()["raw"].replace("# System Persona", "")
    # model key + tier must be CLEARED so onboarding restarts at "How smart should I be?"
    user = repo.get_user(TEST_USER_ID)
    assert user.encrypted_api_key == "" and user.model_tier == ""


def test_purges_are_idempotent(client):
    assert client.delete("/api/settings/conversations").status_code == 200
    assert client.delete("/api/settings/memories").status_code == 200
    assert client.post("/api/settings/purge-all", json={"keep_words": False}).status_code == 200
