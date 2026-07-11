"""Memory files API: persona form, line append/update/delete, line-ID stability."""


def test_persona_form_and_read(client):
    r = client.put(
        "/api/memory/persona/form",
        json={"name": "John", "relation": "best friend", "gender": "male", "personality": "witty", "speaking_style": "casual"},
    )
    assert r.status_code == 200
    raw = client.get("/api/memory/persona").json()["raw"]
    assert "Name: John" in raw and "best friend" in raw


def test_append_update_delete_line(client):
    r = client.post("/api/memory/identity/lines", json={"text": "User is a developer."})
    assert r.status_code == 200
    line_id = r.json()["line_id"]
    assert line_id.startswith("i")

    r = client.put(f"/api/memory/identity/lines/{line_id}", json={"text": "User is a senior developer."})
    assert r.status_code == 200

    lines = client.get("/api/memory/identity").json()["lines"]
    assert len(lines) == 1
    assert lines[0]["text"] == "User is a senior developer."
    assert lines[0]["line_id"] == line_id  # ID stable across update

    assert client.delete(f"/api/memory/identity/lines/{line_id}").status_code == 200
    assert client.get("/api/memory/identity").json()["lines"] == []


def test_line_ids_increment_and_survive_deletes(client):
    ids = [client.post("/api/memory/memory/lines", json={"text": f"fact {i}"}).json()["line_id"] for i in range(3)]
    assert ids == ["m001", "m002", "m003"]
    client.delete(f"/api/memory/memory/lines/{ids[1]}")
    new_id = client.post("/api/memory/memory/lines", json={"text": "fact 4"}).json()["line_id"]
    assert new_id == "m004"  # IDs never reused


def test_multiline_input_collapsed_to_one_line(client):
    r = client.post("/api/memory/identity/lines", json={"text": "line one\nline two"})
    assert "\n" not in r.json()["text"]


def test_persona_form_preserves_relationship_memories(client):
    client.post("/api/memory/persona/lines", json={"text": "We joked about telescopes."})
    client.put("/api/memory/persona/form", json={"name": "Ana", "relation": "mentor"})
    lines = client.get("/api/memory/persona").json()["lines"]
    assert any("telescopes" in l["text"] for l in lines)


def test_unknown_file_and_missing_line(client):
    assert client.get("/api/memory/nope").status_code == 404
    assert client.put("/api/memory/identity/lines/i999", json={"text": "x"}).status_code == 404
    assert client.delete("/api/memory/identity/lines/i999").status_code == 404


def test_raw_save_round_trip(client):
    new_content = "[i001] 2026-07-11 14:03 +05:30 | User is a raw-edit fan.\nSome trailing free text.\n"
    r = client.put("/api/memory/identity/raw", json={"raw": new_content})
    assert r.status_code == 200

    data = client.get("/api/memory/identity").json()
    assert data["raw"] == new_content
    assert len(data["lines"]) == 1
    assert data["lines"][0]["line_id"] == "i001"
    assert data["lines"][0]["text"] == "User is a raw-edit fan."


def test_raw_save_missing_key_400(client):
    r = client.put("/api/memory/identity/raw", json={"not_raw": "x"})
    assert r.status_code == 400


def test_raw_save_unknown_file_404(client):
    r = client.put("/api/memory/nope/raw", json={"raw": "x"})
    assert r.status_code == 404
