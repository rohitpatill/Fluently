"""Tools for the Fluently in-app voice assistant (Gemini Live).

Like `voice_tools.py`, this adapts app actions for the Live API (no auto tool-loop — the router
executes each `tool_call` and sends a `FunctionResponse` back). But these are the ASSISTANT's
tools, not the persona's: read the user's status, and perform a few hands-free setup actions by
WRAPPING the same code paths the REST endpoints use (never duplicating logic):

  * get_my_status    → assistant_service.get_status  (read-only)
  * create_persona   → memory_service.build_persona_content + repo.insert_persona
  * add_word         → topic_service.enrich_word + repo.insert_word  (same as POST /api/words)
  * switch_model_tier→ repo.set_user_tier                            (same as PUT /api/model/tier)

Memory-file editing and conversation search are intentionally NOT exposed here — they don't fit
a help assistant. Adding a new assistant action = add a declaration + an execute branch here only.

The model is instructed (in the assistant prompt) to confirm every create/add/switch out loud
BEFORE calling the tool, since these commit immediately with no undo.
"""

from __future__ import annotations

from typing import Any

from google.genai import types

from .. import repo
from ..config import tier_config
from ..models import Persona, Word
from . import assistant_service, memory_service
from .topic_service import enrich_word


# --- Tool declarations (registered in the LiveConnectConfig) --------------------------------

def assistant_function_declarations() -> list[types.FunctionDeclaration]:
    return [
        types.FunctionDeclaration(
            name="get_my_status",
            description=(
                "Fetch the user's live Fluently numbers — how many practice words they have, how "
                "many are mastered, their average score, their weakest words, how many personas and "
                "conversations they have, how long they've used the app, and their current AI tier. "
                "Call this ONLY when the user asks about their own progress or setup; do not preload it."
            ),
            parameters=types.Schema(type="OBJECT", properties={}),
        ),
        types.FunctionDeclaration(
            name="create_persona",
            description=(
                "Create a new companion persona for the user. It is created IMMEDIATELY with no undo, "
                "so confirm every detail out loud and get a clear yes BEFORE calling this."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "name": types.Schema(type="STRING", description="The persona's name."),
                    "gender": types.Schema(
                        type="STRING",
                        enum=["male", "female"],
                        description="Male or female — used to pick a fitting default voice.",
                    ),
                    "description": types.Schema(
                        type="STRING",
                        description="A short description of who this persona is and how they talk "
                        "(becomes the persona's personality).",
                    ),
                },
                required=["name", "gender", "description"],
            ),
        ),
        types.FunctionDeclaration(
            name="add_word",
            description=(
                "Add a word or phrase to the user's practice list (Fluently auto-generates its "
                "meaning and examples). Confirm the exact spelling before calling."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "text": types.Schema(type="STRING", description="The exact word or phrase to add."),
                },
                required=["text"],
            ),
        ),
        types.FunctionDeclaration(
            name="switch_model_tier",
            description=(
                "Switch the user's AI 'brain' tier. 'swift' = fast and light; 'sage' = sharper but "
                "uses more quota. Confirm which one they want before calling. Requires an existing key."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "tier": types.Schema(type="STRING", enum=["swift", "sage"]),
                },
                required=["tier"],
            ),
        ),
    ]


# --- Execution ------------------------------------------------------------------------------

class AssistantToolExecutor:
    """Runs an assistant tool call server-side and returns a JSON-able result for the model.

    Built once per assistant session with the user closure. Also records each call so the router
    can surface a small on-screen 'action' confirmation to the user (nothing is persisted)."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.records: list[dict] = []

    def execute(self, name: str, args: dict) -> dict:
        args = dict(args or {})
        try:
            if name == "get_my_status":
                result = {"status": "ok", **assistant_service.get_status(self.user_id)}
            elif name == "create_persona":
                result = self._create_persona(args)
            elif name == "add_word":
                result = self._add_word(args)
            elif name == "switch_model_tier":
                result = self._switch_tier(args)
            else:
                result = {"status": "error", "error": f"Unknown tool: {name}"}
        except Exception as e:  # never break the live session — hand the error to the model
            result = {"status": "error", "error": str(e)}
        self.records.append({"name": name, "args": args, "output": result})
        return result

    def _create_persona(self, args: dict) -> dict:
        name = str(args.get("name", "")).strip()
        gender = str(args.get("gender", "")).strip().lower()
        description = str(args.get("description", "")).strip()
        if not name:
            return {"status": "error", "error": "A persona name is required."}
        memory_service.ensure_files(self.user_id)
        # Same shape the persona form/Discover copy uses; Voice defaults from Gender.
        form = {
            "name": name,
            "relation": "",
            "gender": gender,
            "voice": "",
            "personality": description,
            "speaking_style": "",
        }
        content = memory_service.build_persona_content(form)
        persona = repo.insert_persona(Persona(user_id=self.user_id, content=content))
        return {
            "status": "ok",
            "action": "create_persona",
            "persona_name": name,
            "persona_id": persona.id,
            "message": f"Created persona '{name}'. It's in Settings → Personas, where they can "
            f"switch to it, add an avatar, or change the voice.",
        }

    def _add_word(self, args: dict) -> dict:
        text = str(args.get("text", "")).strip()
        if not text:
            return {"status": "error", "error": "A word or phrase is required."}
        if repo.find_word_by_text(text, self.user_id):
            return {"status": "error", "error": f"'{text}' is already on the practice list."}
        kind = "phrase" if " " in text else "word"
        word = Word(text=text, kind=kind, user_id=self.user_id)
        enrichment = enrich_word(text, kind, self.user_id)  # same LLM enrichment as POST /api/words
        if enrichment:
            word.meaning = enrichment.meaning
            word.examples = enrichment.examples
            word.collocations = enrichment.collocations
            word.register_notes = enrichment.register_notes
        repo.insert_word(word)
        return {
            "status": "ok",
            "action": "add_word",
            "word": text,
            "meaning": word.meaning,
            "message": f"Added '{text}'. They can open the Words screen to add their own personal note.",
        }

    def _switch_tier(self, args: dict) -> dict:
        tier = str(args.get("tier", "")).strip().lower()
        if tier_config(tier) is None:
            return {"status": "error", "error": f"Unknown tier: {tier}"}
        user = repo.get_user(self.user_id)
        if user is None or not user.encrypted_api_key:
            return {"status": "error", "error": "Add an API key in Settings before switching tier."}
        repo.set_user_tier(self.user_id, tier)
        return {"status": "ok", "action": "switch_model_tier", "tier": tier,
                "message": f"Switched the brain to {tier.title()}."}

    def drain_records(self) -> list[dict]:
        out = self.records
        self.records = []
        return out
