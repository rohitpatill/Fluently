"""Conversations API: create with target words, category, delete, search engine."""


def _seed_words(client, n=4):
    for i in range(n):
        client.post("/api/words", json={"text": f"word-{i}", "kind": "word"})


def test_create_conversation_picks_targets(client):
    _seed_words(client)
    r = client.post("/api/conversations", json={"suggest_topics": False})
    assert r.status_code == 200
    conv = r.json()["conversation"]
    assert len(conv["target_word_ids"]) == 3  # settings.target_words_per_conversation


def test_create_with_topic_suggestions_mocked(client):
    r = client.post("/api/conversations", json={"suggest_topics": True})
    assert r.status_code == 200
    assert r.json()["topics"] == []  # mocked LLM returns empty list, no crash


def test_set_category(client):
    cid = client.post("/api/conversations", json={"suggest_topics": False}).json()["conversation"]["id"]
    r = client.patch(f"/api/conversations/{cid}/category", params={"category": "science"})
    assert r.json()["category"] == "science"


def test_list_get_delete(client):
    cid = client.post("/api/conversations", json={"suggest_topics": False}).json()["conversation"]["id"]
    assert len(client.get("/api/conversations").json()) == 1
    assert client.get(f"/api/conversations/{cid}").status_code == 200
    assert client.get(f"/api/conversations/{cid}/messages").json() == []
    assert client.delete(f"/api/conversations/{cid}").status_code == 200
    assert client.get(f"/api/conversations/{cid}").status_code == 404


def _seed_searchable_chat(client):
    cid = client.post("/api/conversations", json={"suggest_topics": False}).json()["conversation"]["id"]
    from app.database import SessionLocal
    from app.models import Message

    db = SessionLocal()
    msgs = [
        ("user", "I watched a documentary about space telescopes"),
        ("assistant", "The James Webb one?"),
        ("user", "Yes, the mirror engineering was incredible"),
        ("assistant", "A true marvel"),
        ("user", "Anyway, how is your day going?"),
    ]
    for i, (role, content) in enumerate(msgs, 1):
        db.add(Message(conversation_id=cid, seq=i, role=role, content=content))
    db.commit()
    db.close()
    return cid


def test_search_bm25_with_window(client):
    _seed_searchable_chat(client)
    r = client.post(
        "/api/conversations/search",
        json={"query": "telescope mirror engineering", "mode": "bm25", "n_before": 1, "n_after": 1, "max_results": 3},
    )
    hits = r.json()
    assert len(hits) >= 1
    top = hits[0]
    assert "mirror engineering" in " ".join(m["content"] for m in top["context"])
    assert len(top["context"]) <= 3  # 1 before + match + 1 after


def test_search_regex_mode(client):
    _seed_searchable_chat(client)
    hits = client.post(
        "/api/conversations/search", json={"query": "James\\s+Webb", "mode": "regex", "max_results": 5}
    ).json()
    assert len(hits) == 1


def test_search_full_conversation_flag(client):
    _seed_searchable_chat(client)
    hits = client.post(
        "/api/conversations/search", json={"query": "telescopes", "mode": "regex", "full_conversation": True}
    ).json()
    assert len(hits[0]["context"]) == 5  # entire conversation returned


def test_search_no_results(client):
    _seed_searchable_chat(client)
    hits = client.post("/api/conversations/search", json={"query": "quantum blockchain zebra"}).json()
    assert hits == []
