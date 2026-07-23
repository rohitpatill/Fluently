"""Fluently in-app voice assistant — the app talking to the user for help + hands-free actions.

This is a SEPARATE, self-contained feature from the persona voice chat (`voice_service.py` /
`voice_tools.py`). It reuses ONLY the low-level plumbing (the Gemini Live transport in
`routers/assistant.py` and the per-user key from `model_service.resolve_for_user`) — nothing
here touches persona memory, the judge, scoring, or message persistence. The assistant
conversation is ephemeral: nothing is saved and nothing is scored.

This module owns everything model-specific for the assistant:
  * `build_assistant_prompt(user_id, current_tab)` — the assistant system prompt, filled with
    the user's name/identity/memory + which app screen they're on, so Fluently sounds personal.
  * `get_status(user_id)` — the live numbers the `get_my_status` tool returns.
  * `build_live_config(...)` — the Gemini LiveConnectConfig (audio out, a fixed friendly voice,
    the prompt, and the assistant tool declarations).

Swapping the live model or its config is a one-file change here + `config.voice_model`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from google.genai import types

from .. import repo
from ..config import DEFAULT_VOICE, settings
from ..prompts import ASSISTANT_SYSTEM_TEMPLATE
from . import assistant_tools, memory_service


# The assistant always speaks with one consistent, friendly voice — it's the app's own voice,
# NOT a persona, so it deliberately does NOT use the active persona's voice.
ASSISTANT_VOICE = DEFAULT_VOICE  # "Puck" — warm, neutral


def _persona_name(user_id: str) -> str:
    fields = memory_service.parse_persona_fields(memory_service.read_file("persona", user_id))
    return fields.get("name") or "your companion"


def _user_name(user_id: str) -> str:
    """The user's own name, parsed from identity ('Name: X.'); falls back to their Google name."""
    for line in memory_service.read_file("identity", user_id).splitlines():
        if line.strip().lower().startswith("name:"):
            val = line.split(":", 1)[1].strip().rstrip(".")
            if val:
                return val
    user = repo.get_user(user_id)
    return (user.name.split()[0] if user and user.name else "") or "there"


def build_assistant_prompt(user_id: str, current_tab: str) -> str:
    """Assemble the assistant system prompt. Loads identity + memory (per the product decision)
    so Fluently feels custom, plus the user's name, active persona name, and current screen."""
    identity = memory_service.read_file("identity", user_id).strip() or "(nothing recorded yet)"
    memory = memory_service.read_file("memory", user_id).strip() or "(nothing recorded yet)"
    tab = (current_tab or "").strip().lower()
    tab = tab if tab in ("chat", "words", "memory", "settings") else "chat"
    return ASSISTANT_SYSTEM_TEMPLATE.format(
        user_name=_user_name(user_id),
        current_tab=tab,
        persona_name=_persona_name(user_id),
        identity_block=identity,
        memory_block=memory,
    )


def get_status(user_id: str) -> dict:
    """Live numbers for the `get_my_status` tool: word counts + scores, persona count,
    conversation count, and how long the user has been using Fluently."""
    words = repo.list_words(user_id)
    total = len(words)
    mastered = sum(1 for w in words if w.score >= 100)
    avg = round(sum(w.score for w in words) / total, 1) if total else 0.0
    # a few weakest (still-practicing) words to talk about, low score first
    practicing = sorted((w for w in words if w.score < 100), key=lambda w: w.score)
    weakest = [{"word": w.text, "score": round(w.score)} for w in practicing[:5]]

    personas = repo.list_personas(user_id)
    conv_count = len(repo.list_conversations(user_id))  # across all personas

    user = repo.get_user(user_id)
    days = None
    if user and user.created_at:
        created = user.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        days = max(0, (datetime.now(timezone.utc) - created).days)

    return {
        "total_words": total,
        "mastered_words": mastered,
        "average_score": avg,
        "weakest_words": weakest,
        "persona_count": len(personas),
        "active_persona": _persona_name(user_id),
        "conversation_count": conv_count,
        "days_using_fluently": days,
        "current_tier": (user.model_tier if user else "") or "swift",
    }


def build_live_config(user_id: str, current_tab: str) -> types.LiveConnectConfig:
    """The Gemini LiveConnectConfig for an assistant session: audio out, the assistant's own
    fixed voice, the assistant system prompt, its tool declarations, and transcription so the
    UI can show the live captions (transcripts are NOT persisted)."""
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=ASSISTANT_VOICE)
            )
        ),
        system_instruction=build_assistant_prompt(user_id, current_tab),
        tools=[types.Tool(function_declarations=assistant_tools.assistant_function_declarations())],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )
