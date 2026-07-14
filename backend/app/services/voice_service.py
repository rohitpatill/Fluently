"""Gemini Live (real-time audio) session wrapper.

The single seam that knows how to open a duplex voice session with Gemini and how to shape
its config. The WebSocket router (`routers/voice.py`) owns the browser<->model relay loops;
this module owns everything model-specific, so swapping the live model or its config is a
one-file change.

Voice mode reuses the rest of the app wholesale:
  * the SAME per-user BYO key + provider (`model_service.resolve_for_user`) — the user's own
    Gemini key pays for voice too;
  * the SAME dynamic system prompt as text chat (`prompt_builder.build_system_prompt`), so the
    persona, identity, memory, target words, time block and behavior rules are all identical;
  * the SAME tools, adapted for the live protocol (`voice_tools`).

The chosen VOICE (Aoede/Puck/...) comes from the active persona's `Voice:` field, defaulted
from its Gender when unset (see config.resolve_voice / memory_service).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from google import genai
from google.genai import types

from ..config import resolve_voice, settings
from ..models import Conversation
from ..prompts import VOICE_MODE_INSTRUCTION
from . import memory_service, prompt_builder, voice_tools
from .model_service import resolve_for_user


def voice_for_conversation(conversation: Conversation) -> str:
    """The Gemini Live voice id for a conversation — the active persona's chosen voice,
    defaulted from its Gender when unset. Always returns a valid voice id."""
    fields = memory_service.parse_persona_fields(
        memory_service.read_file("persona", conversation.user_id)
    )
    return resolve_voice(fields.get("voice", ""), fields.get("gender", ""))


def build_live_config(conversation: Conversation, voice: str) -> types.LiveConnectConfig:
    """Assemble the LiveConnectConfig: audio out, locked voice, full system prompt, tools,
    and input/output transcription (so we can persist + display the conversation as text).

    The system prompt is the SAME one text chat builds (persona/identity/memory/targets/time)
    with the voice-only override appended — so voice inherits all context but scores via the
    score_word tool and speaks conversationally. Text mode never gets this suffix."""
    system_instruction = (
        prompt_builder.build_system_prompt(conversation) + "\n\n" + VOICE_MODE_INSTRUCTION
    )
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        ),
        system_instruction=system_instruction,
        tools=[types.Tool(function_declarations=voice_tools.voice_function_declarations())],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )


@asynccontextmanager
async def open_session(conversation: Conversation):
    """Async context manager yielding a connected Gemini Live session for this conversation.

    Resolves the user's own key/model tier is IGNORED for the model id (voice uses the fixed
    `settings.voice_model`), but the user's API KEY still pays for it. Raises NoModelConfigured
    (from resolve_for_user) if the user has no key — the router turns that into a clean close.
    """
    resolved = resolve_for_user(conversation.user_id)  # decrypts the user's own key
    client = genai.Client(api_key=resolved.api_key)
    voice = voice_for_conversation(conversation)
    config = build_live_config(conversation, voice)

    async with client.aio.live.connect(model=settings.voice_model, config=config) as session:
        yield session, voice
