"""Chat turn flow: message storage, tool-calling loop, transparency, judge scoring, title."""

from langchain_core.messages import AIMessage

from app.services import chat_service, judge_service
from tests.conftest import FakeChatModel, FakeStructuredFactory, FakeStructuredModel


def _new_conv(client):
    return client.post("/api/conversations", json={"suggest_topics": False}).json()["conversation"]["id"]


def test_basic_chat_turn(client):
    cid = _new_conv(client)
    r = client.post(f"/api/chat/{cid}", json={"content": "Hello there!"})
    assert r.status_code == 200
    data = r.json()
    assert data["user_message"]["content"] == "Hello there!"
    assert data["assistant_message"]["content"] == "Hey! Nice to hear from you."
    msgs = client.get(f"/api/conversations/{cid}/messages").json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert [m["seq"] for m in msgs] == [1, 2]


def test_empty_message_rejected(client):
    cid = _new_conv(client)
    assert client.post(f"/api/chat/{cid}", json={"content": "   "}).status_code == 400
    assert client.post("/api/chat/99999", json={"content": "hi"}).status_code == 404


def test_tool_calling_loop_and_transparency(client, monkeypatch):
    """Model asks for a memory_update(append) tool call, then answers. Verify the tool really ran
    and the call is stored verbatim on the assistant message."""
    cid = _new_conv(client)
    responses = [
        AIMessage(
            content="",
            tool_calls=[{"name": "memory_update", "args": {"file": "identity", "action": "append", "text": "User loves telescopes."}, "id": "call_1", "type": "tool_call"}],
        ),
        AIMessage(content="Noted! Telescopes are fascinating."),
    ]
    monkeypatch.setattr(chat_service, "get_chat_model", lambda *a, **k: FakeChatModel(responses))

    r = client.post(f"/api/chat/{cid}", json={"content": "I love telescopes, remember that"})
    tool_calls = r.json()["assistant_message"]["tool_calls"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "memory_update"
    assert tool_calls[0]["id"] == "call_1"
    assert "identity.md" in tool_calls[0]["output"]
    # the memory line was actually written
    lines = client.get("/api/memory/identity").json()["lines"]
    assert any("telescopes" in l["text"].lower() for l in lines)


def test_memory_update_tolerates_md_suffix(client, monkeypatch):
    """The model sometimes passes 'identity.md' instead of 'identity' — the tool must still write
    it (and report the clean filename once), not fail with 'Unknown memory file'."""
    cid = _new_conv(client)
    responses = [
        AIMessage(
            content="",
            tool_calls=[{"name": "memory_update", "args": {"file": "identity.md", "action": "append", "text": "Loves biryani."}, "id": "call_md", "type": "tool_call"}],
        ),
        AIMessage(content="Got it."),
    ]
    monkeypatch.setattr(chat_service, "get_chat_model", lambda *a, **k: FakeChatModel(responses))

    r = client.post(f"/api/chat/{cid}", json={"content": "remember I love biryani"})
    output = r.json()["assistant_message"]["tool_calls"][0]["output"]
    assert "Unknown memory file" not in output
    assert output == "Saved a new memory to identity.md."  # clean name, not identity.md.md
    lines = client.get("/api/memory/identity").json()["lines"]
    assert any("biryani" in l["text"].lower() for l in lines)


def test_history_reconstruction_includes_tool_calls(client, monkeypatch):
    """Second turn must replay the first turn's AIMessage(tool_calls)+ToolMessage pair."""
    cid = _new_conv(client)
    responses = [
        AIMessage(content="", tool_calls=[{"name": "memory_update", "args": {"file": "memory", "action": "append", "text": "fact"}, "id": "c1", "type": "tool_call"}]),
        AIMessage(content="First reply."),
    ]
    fake1 = FakeChatModel(responses)
    monkeypatch.setattr(chat_service, "get_chat_model", lambda *a, **k: fake1)
    client.post(f"/api/chat/{cid}", json={"content": "turn one"})

    fake2 = FakeChatModel([AIMessage(content="Second reply.")])
    monkeypatch.setattr(chat_service, "get_chat_model", lambda *a, **k: fake2)
    client.post(f"/api/chat/{cid}", json={"content": "turn two"})

    sent = fake2.invocations[0]
    types = [type(m).__name__ for m in sent]
    assert "ToolMessage" in types  # past tool call replayed
    tool_msg_idx = types.index("ToolMessage")
    assert types[tool_msg_idx - 1] == "AIMessage"  # preceded by its AIMessage(tool_calls)
    assert sent[tool_msg_idx].tool_call_id == "c1"  # original ID preserved


def test_judge_applies_scoring_events(client, monkeypatch):
    wid = client.post("/api/words", json={"text": "ubiquitous", "kind": "word"}).json()["id"]
    cid = _new_conv(client)

    result = judge_service.JudgeResult(
        judgements=[judge_service.UsageJudgement(word="ubiquitous", classification="perfect_unprompted", suggestion="")]
    )
    monkeypatch.setattr(
        judge_service, "get_judge_model",
        lambda *a, **k: FakeStructuredFactory({judge_service.JudgeResult: result}),
    )

    r = client.post(f"/api/chat/{cid}", json={"content": "Smartphones are ubiquitous these days."})
    events = r.json()["scoring_events"]
    assert len(events) == 1
    assert events[0]["event_type"] == "perfect_unprompted" and events[0]["delta"] == 5.0
    assert client.get(f"/api/words/{wid}").json()["score"] == 5.0


def test_messages_endpoint_returns_persisted_scoring_events(client, monkeypatch):
    """Scoring chips must survive a refresh: GET .../messages attaches each user message's
    word_events (with resolved word_text) so the frontend can re-render them."""
    client.post("/api/words", json={"text": "ubiquitous", "kind": "word"})
    cid = _new_conv(client)

    result = judge_service.JudgeResult(
        judgements=[judge_service.UsageJudgement(word="ubiquitous", classification="awkward", suggestion="Try: everywhere.")]
    )
    monkeypatch.setattr(
        judge_service, "get_judge_model",
        lambda *a, **k: FakeStructuredFactory({judge_service.JudgeResult: result}),
    )
    client.post(f"/api/chat/{cid}", json={"content": "Phones are ubiquitous."})

    msgs = client.get(f"/api/conversations/{cid}/messages").json()
    user_msg = next(m for m in msgs if m["role"] == "user")
    assistant_msg = next(m for m in msgs if m["role"] == "assistant")
    assert len(user_msg["word_events"]) == 1
    ev = user_msg["word_events"][0]
    assert ev["event_type"] == "awkward"
    assert ev["word_text"] == "ubiquitous"
    assert ev["judge_notes"] == "Try: everywhere."
    assert ev["message_id"] == user_msg["id"]
    # events attach to the user message only, never the assistant reply
    assert assistant_msg["word_events"] == []


def test_judge_failure_never_breaks_chat(client, monkeypatch):
    _new = client.post("/api/words", json={"text": "resilient", "kind": "word"})
    cid = _new_conv(client)

    def boom(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(judge_service, "get_judge_model", boom)
    r = client.post(f"/api/chat/{cid}", json={"content": "The system is resilient."})
    assert r.status_code == 200
    assert r.json()["scoring_events"] == []


def test_auto_title_after_first_exchange(client):
    cid = _new_conv(client)
    client.post(f"/api/chat/{cid}", json={"content": "Hello!"})
    assert client.get(f"/api/conversations/{cid}").json()["title"] == "Test Title"


def test_agent_can_adjust_word_score(client, monkeypatch):
    wid = client.post("/api/words", json={"text": "resilient", "kind": "word"}).json()["id"]
    cid = _new_conv(client)
    responses = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "adjust_word_score",
                "args": {"word_id": wid, "delta": 7, "reason": "Used it masterfully in a metaphor."},
                "id": "call_adj",
                "type": "tool_call",
            }],
        ),
        AIMessage(content="Nice use of 'resilient'!"),
    ]
    monkeypatch.setattr(chat_service, "get_chat_model", lambda *a, **k: FakeChatModel(responses))

    r = client.post(f"/api/chat/{cid}", json={"content": "Watch me use resilient masterfully."})
    assert r.status_code == 200
    tool_calls = r.json()["assistant_message"]["tool_calls"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "adjust_word_score"
    assert "score changed by" in tool_calls[0]["output"]

    word = client.get(f"/api/words/{wid}").json()
    assert word["score"] == 7.0

    events = client.get(f"/api/words/{wid}/events").json()
    assert len(events) == 1
    assert events[0]["event_type"] == "manual"
    assert "[agent]" in events[0]["judge_notes"]


def test_agent_adjust_score_unknown_word_id(client, monkeypatch):
    cid = _new_conv(client)
    responses = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "adjust_word_score",
                "args": {"word_id": "000000000000000000000000", "delta": 3, "reason": "test"},
                "id": "call_adj2",
                "type": "tool_call",
            }],
        ),
        AIMessage(content="All good."),
    ]
    monkeypatch.setattr(chat_service, "get_chat_model", lambda *a, **k: FakeChatModel(responses))

    r = client.post(f"/api/chat/{cid}", json={"content": "Try adjusting a bogus word id."})
    assert r.status_code == 200
    tool_calls = r.json()["assistant_message"]["tool_calls"]
    assert "No word with id" in tool_calls[0]["output"]


def test_opener_generates_first_message(client):
    cid = _new_conv(client)
    r = client.post(f"/api/conversations/{cid}/opener")
    assert r.status_code == 200
    assert r.json()["role"] == "assistant" and r.json()["seq"] == 1
    # opener only allowed on empty conversations
    assert client.post(f"/api/conversations/{cid}/opener").status_code == 400
