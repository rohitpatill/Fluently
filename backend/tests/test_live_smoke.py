"""LIVE smoke tests — hit the real provider configured in .env
(DEFAULT_PROVIDER/DEFAULT_MODEL etc.). Deselected by default; run with:
    pytest -m live        or        python run_tests.py --live
Requires the matching API key in .env.
"""

import pytest

pytestmark = pytest.mark.live


def _new_conv(client):
    return client.post("/api/conversations", json={"suggest_topics": False}).json()["conversation"]["id"]


def test_live_word_enrichment(client):
    w = client.post("/api/words", json={"text": "meticulous", "kind": "word"}).json()
    assert w["meaning"], "enrichment returned no meaning — provider call likely failed"
    assert len(w["examples"]) >= 2
    assert w["register_notes"]


def test_live_chat_turn_with_persona(client):
    client.put(
        "/api/memory/persona/form",
        json={"name": "John", "relation": "best friend", "personality": "witty, warm", "speaking_style": "casual"},
    )
    client.post("/api/words", json={"text": "serendipity", "kind": "word"})
    cid = _new_conv(client)
    r = client.post(f"/api/chat/{cid}", json={"content": "Hey John! Guess what, I got a surprise bonus today at work."})
    assert r.status_code == 200
    reply = r.json()["assistant_message"]["content"]
    assert len(reply) > 0
    # auto-title should have fired
    assert client.get(f"/api/conversations/{cid}").json()["title"] != "New conversation"


def test_live_judge_scores_target_word(client):
    wid = client.post("/api/words", json={"text": "ubiquitous", "kind": "word"}).json()["id"]
    cid = _new_conv(client)
    r = client.post(f"/api/chat/{cid}", json={"content": "Smartphones have become ubiquitous in every part of daily life."})
    events = r.json()["scoring_events"]
    assert any(e["word_id"] == wid for e in events), "judge did not score a clearly-used target word"
    assert client.get(f"/api/words/{wid}").json()["score"] > 0


def test_live_topic_suggestions(client):
    client.post("/api/memory/identity/lines", json={"text": "User is a software developer who loves astronomy."})
    r = client.post("/api/conversations", json={"suggest_topics": True})
    topics = r.json()["topics"]
    assert len(topics) >= 3
    assert all(t["title"] for t in topics)
