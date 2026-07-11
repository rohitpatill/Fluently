"""Dashboard stats + health."""


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_dashboard_stats(client):
    for i, delta in enumerate([100, 40, 0]):
        wid = client.post("/api/words", json={"text": f"w{i}", "kind": "word"}).json()["id"]
        if delta:
            client.post(f"/api/words/{wid}/adjust", json={"delta": delta})
    client.post("/api/conversations", json={"suggest_topics": False})

    s = client.get("/api/dashboard/stats").json()
    assert s["total_words"] == 3
    assert s["mastered"] == 1
    assert s["total_conversations"] == 1
    assert len(s["top_words"]) == 3
    assert s["top_words"][0]["score"] == 100.0
    assert s["weakest_words"][0]["score"] == 0.0
