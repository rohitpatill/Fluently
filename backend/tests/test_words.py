"""Words API: add, duplicate, list, manual adjust, events, delete."""


def test_add_and_list_word(client):
    r = client.post("/api/words", json={"text": "ubiquitous", "kind": "word"})
    assert r.status_code == 200
    w = r.json()
    assert w["score"] == 0.0 and w["text"] == "ubiquitous"

    words = client.get("/api/words").json()
    assert len(words) == 1


def test_duplicate_word_rejected(client):
    client.post("/api/words", json={"text": "serendipity", "kind": "word"})
    assert client.post("/api/words", json={"text": "Serendipity", "kind": "word"}).status_code == 409


def test_empty_and_invalid_kind_rejected(client):
    assert client.post("/api/words", json={"text": "   ", "kind": "word"}).status_code == 400
    assert client.post("/api/words", json={"text": "ok", "kind": "sentence"}).status_code == 422


def test_manual_adjust_and_events(client):
    wid = client.post("/api/words", json={"text": "pragmatic", "kind": "word"}).json()["id"]

    e = client.post(f"/api/words/{wid}/adjust", json={"delta": 30, "reason": "seed"}).json()
    assert e["score_after"] == 30.0 and e["event_type"] == "manual"

    # user lowers it to practice more
    e = client.post(f"/api/words/{wid}/adjust", json={"delta": -10, "reason": "practice more"}).json()
    assert e["score_after"] == 20.0

    events = client.get(f"/api/words/{wid}/events").json()
    assert len(events) == 2


def test_manual_adjust_clamped_0_100(client):
    wid = client.post("/api/words", json={"text": "clamp-test", "kind": "phrase"}).json()["id"]
    assert client.post(f"/api/words/{wid}/adjust", json={"delta": 500}).json()["score_after"] == 100.0
    assert client.post(f"/api/words/{wid}/adjust", json={"delta": -500}).json()["score_after"] == 0.0


def test_delete_word(client):
    wid = client.post("/api/words", json={"text": "ephemeral", "kind": "word"}).json()["id"]
    assert client.delete(f"/api/words/{wid}").status_code == 200
    assert client.get(f"/api/words/{wid}").status_code == 404
