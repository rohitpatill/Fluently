"""Bridge between the app's LangChain tools and the Gemini Live API.

Text chat runs tools through LangChain's `bind_tools` auto-loop (see `chat_service.py`).
The Live API has NO such auto-loop: the model emits `tool_call` events, and WE must execute
each one and send a `FunctionResponse` back over the socket. This module is the single seam
that adapts the EXISTING tools for that world, so voice and text share one tool implementation:

  * `voice_function_declarations()` — the `genai.types.FunctionDeclaration` list to register
    in `LiveConnectConfig.tools` (derived from the same tools + one voice-only `score_word`).
  * `VoiceToolExecutor` — dispatches a tool_call (name + args) to the right implementation,
    returns a JSON-able result dict, and records what ran (for per-turn message persistence).

Design notes / future flexibility:
  * The conversational tools (`memory_update`, `search_conversations`) are reused verbatim
    from `agent_tools.build_tools()` — one definition, one behavior, everywhere. Adding a new
    shared tool there makes it available to BOTH modes with no change here.
  * `score_word` is voice-ONLY: text mode scores via the post-turn judge, but voice wants the
    animation to pop live, so the live model flags a usage inline. It routes through the SAME
    `scoring_service.apply_event`, so voice scores use the identical matrix and never diverge.
  * `adjust_word_score` is intentionally NOT exposed in voice — `score_word` covers live
    scoring, and manual adjustments belong to the dashboard/text agent.
"""

from __future__ import annotations

from typing import Any

from google.genai import types

from .. import repo
from . import scoring_service
from .agent_tools import build_tools

# The valid scoring classifications a live turn can report — a subset of scoring_service's
# event types (decay/manual/passive are not things the live model should assert inline).
VOICE_SCORE_EVENTS = ("perfect_unprompted", "perfect_prompted", "awkward", "wrong")

# The shared conversational tools we expose to the live model (by name, from build_tools()).
# adjust_word_score is deliberately excluded (see module docstring).
_SHARED_VOICE_TOOL_NAMES = ("memory_update", "search_conversations")


# --- LangChain args_schema (pydantic) -> Gemini JSON schema --------------------------------

_JSON_TYPES = {
    "string": "STRING",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
    "object": "OBJECT",
}


def _to_gemini_schema(pydantic_schema: dict) -> types.Schema:
    """Convert a pydantic model's JSON schema into a genai types.Schema. Flattens enums and
    (for our tools' shallow arg shapes) primitive properties — no nested objects needed."""
    props: dict[str, types.Schema] = {}
    for name, spec in (pydantic_schema.get("properties") or {}).items():
        json_type = spec.get("type", "string")
        # Literal[...] surfaces as an `enum` (no `type`) — treat as STRING enum.
        enum = spec.get("enum")
        gem_type = _JSON_TYPES.get(json_type, "STRING") if json_type else "STRING"
        child = types.Schema(
            type=gem_type,
            description=spec.get("description", ""),
        )
        if enum:
            child.enum = [str(e) for e in enum]
        if json_type == "array":
            child.items = types.Schema(type="STRING")
        props[name] = child
    return types.Schema(
        type="OBJECT",
        properties=props,
        required=list(pydantic_schema.get("required") or []),
    )


def _declaration_from_langchain_tool(lc_tool) -> types.FunctionDeclaration:
    """Build a FunctionDeclaration from a LangChain @tool (reusing its name/description/args)."""
    schema = lc_tool.args_schema.model_json_schema() if lc_tool.args_schema else {"properties": {}}
    return types.FunctionDeclaration(
        name=lc_tool.name,
        description=lc_tool.description,
        parameters=_to_gemini_schema(schema),
    )


def _score_word_declaration() -> types.FunctionDeclaration:
    """The voice-only live scoring tool. The model MUST call it the moment it hears the user
    produce (or misuse) one of the target words, so the UI can pop the score animation live.

    This is a PLAIN (blocking) tool on purpose: `gemini-3.1-flash-live-preview` is blocking-only
    for function calls, and blocking tool-calling is the reliable, proven path (matches the
    reference architecture). The call is a tiny DB write, so the pause is imperceptible."""
    return types.FunctionDeclaration(
        name="score_word",
        description=(
            "Record how the user just used ONE of their target practice words. You MUST call "
            "this EVERY time the user says a target word — it is the core purpose of the "
            "session and powers a live on-screen score animation the user is watching for. Call "
            "it once per target word the user PRODUCED (not words you said). Use the word's [id] "
            "from your context. Judge strictly: 'perfect' means a native speaker notices nothing off."
        ),
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "word_id": types.Schema(
                    type="STRING",
                    description="The target word's [id] as shown in your context.",
                ),
                "classification": types.Schema(
                    type="STRING",
                    enum=list(VOICE_SCORE_EVENTS),
                    description=(
                        "perfect_unprompted = correct & natural and YOU did not set the word up "
                        "first; perfect_prompted = correct & natural but you used/set it up first; "
                        "awkward = right meaning but off phrasing/register; wrong = incorrect usage."
                    ),
                ),
                "note": types.Schema(
                    type="STRING",
                    description="One short reason for awkward/wrong (a better phrasing). Optional for perfect.",
                ),
            },
            required=["word_id", "classification"],
        ),
    )


def voice_function_declarations() -> list[types.FunctionDeclaration]:
    """The full FunctionDeclaration list to register in the live session config."""
    tools = build_tools()  # a throwaway build just to read names/schemas (no closure needed here)
    by_name = {t.name: t for t in tools}
    decls = [
        _declaration_from_langchain_tool(by_name[n])
        for n in _SHARED_VOICE_TOOL_NAMES
        if n in by_name
    ]
    decls.append(_score_word_declaration())
    return decls


# --- Execution -----------------------------------------------------------------------------

class VoiceToolExecutor:
    """Executes live tool calls against the same implementations text chat uses.

    Built once per voice session with the user/persona/conversation closure. Each executed
    call is appended to `self.records` so the router can persist it on the assistant message
    (tool_calls) and surface score events to the browser for the live animation.
    """

    def __init__(self, conversation_id: str, user_id: str, persona_id: str | None):
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.persona_id = persona_id
        # The shared conversational tools, bound to this session's closure.
        lc_tools = build_tools(
            current_conversation_id=conversation_id,
            user_id=user_id,
            persona_id=persona_id,
        )
        self._lc_by_name: dict[str, Any] = {t.name: t for t in lc_tools}
        # Everything that ran this turn — drained by the router after each turn completes.
        self.records: list[dict] = []

    def execute(self, name: str, args: dict) -> dict:
        """Run a tool call, record it, and return a JSON-able result dict for the model."""
        args = dict(args or {})
        try:
            if name == "score_word":
                result = self._score_word(args)
            elif name in self._lc_by_name:
                output = self._lc_by_name[name].invoke(args)
                result = {"result": output if isinstance(output, str) else str(output)}
            else:
                result = {"error": f"Unknown tool: {name}"}
        except Exception as e:  # tool errors go back to the model, never break the session
            result = {"error": str(e)}

        self.records.append({"name": name, "args": args, "output": result})
        return result

    def _score_word(self, args: dict) -> dict:
        """Apply a live word score through the SAME scoring_service the text judge uses.
        Also stashes the resulting WordEvent details on the record so the router can push a
        score-pop event to the browser."""
        word_id = str(args.get("word_id", "")).strip()
        classification = str(args.get("classification", "")).strip()
        note = str(args.get("note", "")).strip()

        if classification not in VOICE_SCORE_EVENTS:
            return {"status": "error", "error": f"Invalid classification: {classification}"}
        word = repo.get_word(word_id, self.user_id)
        if word is None:
            return {"status": "error", "error": f"No word with id {word_id}"}

        # Store only a real correction note (awkward/wrong). A perfect usage gets no note, so
        # its chip shows a clean "+5" just like text mode — no "[voice]" placeholder leaking in.
        event = scoring_service.apply_event(
            word,
            classification,
            judge_notes=note,
            conversation_id=self.conversation_id,
        )
        # Structured detail the router turns into a browser 'score' event for the animation,
        # and uses (`event_id`) to back-fill the event's message_id once the user transcript
        # message for this turn is persisted (so the chip reattaches on reload).
        return {
            "status": "ok",
            "word": word.text,
            "word_id": word.id,
            "event_id": event.id,
            "event_type": classification,
            "delta": event.delta,
            "score_after": event.score_after,
            "note": note,
        }

    def drain_records(self) -> list[dict]:
        """Return and clear the tool-call records accumulated so far (per-turn boundary)."""
        out = self.records
        self.records = []
        return out
