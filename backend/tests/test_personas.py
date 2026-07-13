"""Multi-persona management + persona scoping.

Covers: list/create/edit/activate/delete personas, the "keep >= 1" guard, that switching a
persona swaps ONLY the persona file (identity/memory stay shared), that conversations and
conversation-search are scoped to the active persona, and that deleting a persona cascades to
its conversations while keeping word scores.
"""

from app import repo


def _active(client):
    return next(p for p in client.get("/api/personas").json() if p["is_active"])


def test_seeded_user_has_one_active_persona(client):
    r = client.get("/api/personas")
    assert r.status_code == 200
    personas = r.json()
    assert len(personas) == 1
    assert personas[0]["is_active"] is True
    assert personas[0]["conversation_count"] == 0


def test_create_persona_does_not_switch_active(client):
    before = _active(client)
    r = client.post(
        "/api/personas",
        json={"name": "Maya", "relation": "mentor", "personality": "calm", "avatar_url": "https://x/y.jpg"},
    )
    assert r.status_code == 200
    created = r.json()
    assert created["name"] == "Maya"
    assert created["relation"] == "mentor"
    assert created["avatar_url"] == "https://x/y.jpg"
    assert created["is_active"] is False
    # still two personas, original still active
    personas = client.get("/api/personas").json()
    assert len(personas) == 2
    assert _active(client)["id"] == before["id"]


def test_activate_switches_persona(client):
    new_id = client.post("/api/personas", json={"name": "Maya", "relation": "mentor"}).json()["id"]
    r = client.post(f"/api/personas/{new_id}/activate")
    assert r.status_code == 200
    assert r.json()["is_active"] is True
    assert _active(client)["id"] == new_id


def test_switching_persona_swaps_only_persona_file(client):
    # seed identity + memory (shared) and give the first persona a distinctive name
    client.post("/api/memory/identity/lines", json={"text": "Name: Aarav."})
    client.post("/api/memory/memory/lines", json={"text": "Trip on 2026-08-01."})
    client.put("/api/memory/persona/form", json={"name": "Jack", "relation": "best friend"})

    maya_id = client.post("/api/personas", json={"name": "Maya", "relation": "mentor"}).json()["id"]
    client.post(f"/api/personas/{maya_id}/activate")

    # persona file now reflects Maya, NOT Jack
    persona_raw = client.get("/api/memory/persona").json()["raw"]
    assert "Maya" in persona_raw and "Jack" not in persona_raw

    # identity + memory are UNCHANGED (shared across personas)
    assert "Name: Aarav." in client.get("/api/memory/identity").json()["raw"]
    assert "Trip on 2026-08-01." in client.get("/api/memory/memory").json()["raw"]


def test_persona_relationship_memories_are_isolated(client):
    # write a relationship memory under the active (Jack) persona
    client.put("/api/memory/persona/form", json={"name": "Jack", "relation": "best friend"})
    client.post("/api/memory/persona/lines", json={"text": "We joked about the Goa trip."})
    assert "Goa" in client.get("/api/memory/persona").json()["raw"]

    # switch to a fresh persona — its persona file must NOT carry Jack's memory
    maya_id = client.post("/api/personas", json={"name": "Maya", "relation": "mentor"}).json()["id"]
    client.post(f"/api/personas/{maya_id}/activate")
    assert "Goa" not in client.get("/api/memory/persona").json()["raw"]

    # switch back — Jack still remembers it
    personas = client.get("/api/personas").json()
    jack_id = next(p["id"] for p in personas if p["name"] == "Jack")
    client.post(f"/api/personas/{jack_id}/activate")
    assert "Goa" in client.get("/api/memory/persona").json()["raw"]


def test_conversations_are_scoped_to_active_persona(client):
    # conversation created under the seeded persona
    conv1 = client.post("/api/conversations", json={"suggest_topics": False}).json()["conversation"]
    assert len(client.get("/api/conversations").json()) == 1

    # switch persona → the previous conversation disappears from the list
    maya_id = client.post("/api/personas", json={"name": "Maya", "relation": "mentor"}).json()["id"]
    client.post(f"/api/personas/{maya_id}/activate")
    assert client.get("/api/conversations").json() == []

    # a conversation created now belongs to Maya
    conv2 = client.post("/api/conversations", json={"suggest_topics": False}).json()["conversation"]
    listed = client.get("/api/conversations").json()
    assert [c["id"] for c in listed] == [conv2["id"]]

    # switching back shows only the first
    personas = client.get("/api/personas").json()
    jack_id = next(p["id"] for p in personas if p["name"] != "Maya")
    client.post(f"/api/personas/{jack_id}/activate")
    assert [c["id"] for c in client.get("/api/conversations").json()] == [conv1["id"]]


def test_search_is_scoped_to_active_persona(client):
    # a couple of messages under the seeded persona (BM25 needs >1 doc so a term isn't in
    # every document — IDF for an all-documents term is non-positive and gets filtered out)
    conv = client.post("/api/conversations", json={"suggest_topics": False}).json()["conversation"]
    client.post(f"/api/chat/{conv['id']}", json={"content": "banana pancakes are great"})
    client.post(f"/api/chat/{conv['id']}", json={"content": "the weather is cold today"})
    hits = client.post("/api/conversations/search", json={"query": "banana"}).json()
    assert len(hits) >= 1

    # switch persona → that message is invisible to search
    maya_id = client.post("/api/personas", json={"name": "Maya", "relation": "mentor"}).json()["id"]
    client.post(f"/api/personas/{maya_id}/activate")
    assert client.post("/api/conversations/search", json={"query": "banana"}).json() == []


def test_delete_persona_cascades_conversations_keeps_words(client):
    # add a word (with a score) that must survive
    client.post("/api/words", json={"text": "ubiquitous"})
    words_before = client.get("/api/words").json()
    assert len(words_before) == 1

    # give the active persona a conversation + message, then delete a DIFFERENT (new) persona
    conv = client.post("/api/conversations", json={"suggest_topics": False}).json()["conversation"]
    client.post(f"/api/chat/{conv['id']}", json={"content": "hello"})

    maya_id = client.post("/api/personas", json={"name": "Maya", "relation": "mentor"}).json()["id"]
    client.post(f"/api/personas/{maya_id}/activate")
    maya_conv = client.post("/api/conversations", json={"suggest_topics": False}).json()["conversation"]
    client.post(f"/api/chat/{maya_conv['id']}", json={"content": "hi there"})

    # delete Maya → her conversation is gone, Jack's survives, words survive
    r = client.delete(f"/api/personas/{maya_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["conversations_deleted"] == 1

    personas = client.get("/api/personas").json()
    assert len(personas) == 1  # back to just Jack
    assert client.get("/api/words").json() == words_before  # scores intact


def test_delete_active_persona_auto_switches(client):
    maya_id = client.post("/api/personas", json={"name": "Maya", "relation": "mentor"}).json()["id"]
    client.post(f"/api/personas/{maya_id}/activate")
    assert _active(client)["id"] == maya_id

    r = client.delete(f"/api/personas/{maya_id}")
    assert r.status_code == 200
    # another persona automatically becomes active
    personas = client.get("/api/personas").json()
    assert len(personas) == 1
    assert personas[0]["is_active"] is True
    assert personas[0]["id"] != maya_id


def test_cannot_delete_last_persona(client):
    only = _active(client)
    r = client.delete(f"/api/personas/{only['id']}")
    assert r.status_code == 400
    assert "at least one" in r.json()["detail"].lower()
    assert len(client.get("/api/personas").json()) == 1


def test_edit_persona_preserves_relationship_memories(client):
    client.put("/api/memory/persona/form", json={"name": "Jack", "relation": "best friend"})
    client.post("/api/memory/persona/lines", json={"text": "We joked about the Goa trip."})
    pid = _active(client)["id"]

    r = client.put(
        f"/api/personas/{pid}",
        json={"name": "Jackie", "relation": "mentor", "personality": "wise", "avatar_url": "https://a/b.png"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Jackie"
    assert r.json()["relation"] == "mentor"
    assert r.json()["avatar_url"] == "https://a/b.png"
    # header changed but the relationship memory is preserved
    raw = client.get("/api/memory/persona").json()["raw"]
    assert "Name: Jackie" in raw and "Goa" in raw


def test_set_avatar_endpoint(client):
    pid = _active(client)["id"]
    r = client.put(f"/api/personas/{pid}/avatar", json={"avatar_url": "https://img/pic.jpg"})
    assert r.status_code == 200
    assert r.json()["avatar_url"] == "https://img/pic.jpg"
    # clearing it
    r = client.put(f"/api/personas/{pid}/avatar", json={"avatar_url": ""})
    assert r.json()["avatar_url"] == ""


def test_actions_on_missing_persona_404(client):
    assert client.post("/api/personas/deadbeefdeadbeefdeadbeef/activate").status_code == 404
    assert client.put("/api/personas/deadbeefdeadbeefdeadbeef", json={"name": "X", "relation": "y"}).status_code == 404
    assert client.delete("/api/personas/deadbeefdeadbeefdeadbeef").status_code == 404


def test_personas_require_auth(anon_client):
    assert anon_client.get("/api/personas").status_code == 401
    assert anon_client.post("/api/personas", json={"name": "X", "relation": "y"}).status_code == 401


def test_isolation_between_users(client):
    """One user's personas must never appear for another user."""
    from tests.conftest import seed_user

    other_id = "1111111111111111aaaaaaaa"
    seed_user(other_id, sub="sub-other", email="other@example.com")
    # seed_user bootstrapped a persona for `other`; the authed client must not see it
    client.post("/api/personas", json={"name": "Maya", "relation": "mentor"})
    names = {p["name"] for p in client.get("/api/personas").json()}
    other_personas = repo.list_personas(other_id)
    assert len(other_personas) == 1
    assert "Maya" not in {repo.get_persona(p.id, other_id).content for p in other_personas}
