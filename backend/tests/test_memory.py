"""Memory files API: persona form, append, edit (replace/delete), raw round-trip.

Files are pure free-text markdown — no IDs, no machine-added stamps. The agent/UI
edit them by text (old_string -> new_string), like a normal file. Any date lives in
the entry text, written by the agent, never added by the system.
"""


def test_persona_form_and_read(client):
    r = client.put(
        "/api/memory/persona/form",
        json={"name": "John", "relation": "best friend", "gender": "male", "personality": "witty", "speaking_style": "casual"},
    )
    assert r.status_code == 200
    raw = client.get("/api/memory/persona").json()["raw"]
    assert "Name: John" in raw and "best friend" in raw


def test_append_stores_verbatim_no_stamp(client):
    r = client.post("/api/memory/identity/lines", json={"text": "User is a developer."})
    assert r.status_code == 200
    assert r.json()["text"] == "User is a developer."
    raw = client.get("/api/memory/identity").json()["raw"]
    # stored exactly, nothing prepended
    assert "\nUser is a developer.\n" in raw
    # no legacy stamp/id artifacts
    assert "[i0" not in raw and "+05:30" not in raw


def test_append_with_agent_written_date_is_preserved(client):
    r = client.post("/api/memory/memory/lines", json={"text": "Demo on 2026-07-17."})
    assert r.json()["text"] == "Demo on 2026-07-17."


def test_append_multiline_input_collapsed_to_one_line(client):
    r = client.post("/api/memory/identity/lines", json={"text": "line one\nline two"})
    assert "\n" not in r.json()["text"]


def test_entry_count_ignores_headings(client):
    client.post("/api/memory/identity/lines", json={"text": "fact one"})
    client.post("/api/memory/identity/lines", json={"text": "fact two"})
    lines = client.get("/api/memory/identity").json()["lines"]
    # the "# User Identity" heading and its description sentence: heading excluded,
    # the plain description line counts as content — so assert our two facts are present
    texts = [l["text"] for l in lines]
    assert "fact one" in texts and "fact two" in texts
    assert not any(t.startswith("#") for t in texts)


def test_edit_replaces_text(client):
    client.post("/api/memory/identity/lines", json={"text": "User is a developer."})
    r = client.post(
        "/api/memory/identity/edit",
        json={"old_string": "User is a developer.", "new_string": "User is a senior developer."},
    )
    assert r.status_code == 200
    texts = [l["text"] for l in client.get("/api/memory/identity").json()["lines"]]
    assert "User is a senior developer." in texts
    assert "User is a developer." not in texts


def test_edit_empty_new_string_deletes(client):
    client.post("/api/memory/memory/lines", json={"text": "Trip to Goa in July."})
    r = client.post("/api/memory/memory/edit", json={"old_string": "Trip to Goa in July.", "new_string": ""})
    assert r.status_code == 200
    texts = [l["text"] for l in client.get("/api/memory/memory").json()["lines"]]
    assert "Trip to Goa in July." not in texts


def test_edit_missing_text_404(client):
    r = client.post("/api/memory/identity/edit", json={"old_string": "not there", "new_string": "x"})
    assert r.status_code == 404


def test_edit_empty_old_string_400(client):
    r = client.post("/api/memory/identity/edit", json={"old_string": "", "new_string": "x"})
    assert r.status_code == 400


def test_edit_replace_all(client):
    client.post("/api/memory/identity/lines", json={"text": "likes tea"})
    client.post("/api/memory/identity/lines", json={"text": "still likes tea"})
    r = client.post(
        "/api/memory/identity/edit",
        json={"old_string": "tea", "new_string": "coffee", "replace_all": True},
    )
    assert r.status_code == 200
    raw = client.get("/api/memory/identity").json()["raw"]
    assert "tea" not in raw and raw.count("coffee") == 2


def test_persona_form_preserves_relationship_memories(client):
    client.post("/api/memory/persona/lines", json={"text": "We joked about telescopes."})
    client.put("/api/memory/persona/form", json={"name": "Ana", "relation": "mentor"})
    texts = [l["text"] for l in client.get("/api/memory/persona").json()["lines"]]
    assert any("telescopes" in t for t in texts)


def test_unknown_file_404(client):
    assert client.get("/api/memory/nope").status_code == 404
    assert client.post("/api/memory/nope/edit", json={"old_string": "a", "new_string": "b"}).status_code == 404


def test_raw_save_round_trip(client):
    new_content = "# User Identity\n\nUser is a raw-edit fan.\nSome trailing free text.\n"
    r = client.put("/api/memory/identity/raw", json={"raw": new_content})
    assert r.status_code == 200
    data = client.get("/api/memory/identity").json()
    assert data["raw"] == new_content


def test_raw_save_missing_key_400(client):
    r = client.put("/api/memory/identity/raw", json={"not_raw": "x"})
    assert r.status_code == 400


def test_raw_save_unknown_file_404(client):
    r = client.put("/api/memory/nope/raw", json={"raw": "x"})
    assert r.status_code == 404


# ---------- onboarding (LLM-structured intake) ----------
def test_onboarding_structures_about_across_files(client):
    r = client.post(
        "/api/memory/onboarding",
        json={"name": "Aarav", "about": "I'm a 26yo founder, want my English natural in meetings"},
    )
    assert r.status_code == 200
    body = r.json()
    # mock returns identity + memory facts (see conftest)
    assert "26 years old." in body["identity"]
    assert any("meetings" in m for m in body["memory"])

    # name is stored deterministically in identity; structured facts land in the right files
    identity = [l["text"] for l in client.get("/api/memory/identity").json()["lines"]]
    assert "Name: Aarav." in identity
    assert "Founder of a startup." in identity
    memory = [l["text"] for l in client.get("/api/memory/memory").json()["lines"]]
    assert any("meetings" in t for t in memory)


def test_onboarding_name_only_no_llm(client):
    r = client.post("/api/memory/onboarding", json={"name": "Aarav", "about": ""})
    assert r.status_code == 200
    identity = [l["text"] for l in client.get("/api/memory/identity").json()["lines"]]
    assert identity == ["Name: Aarav."]
    # nothing leaked into the other files
    assert client.get("/api/memory/memory").json()["lines"] == []
