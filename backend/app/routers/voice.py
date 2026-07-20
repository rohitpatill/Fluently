"""Voice mode — real-time duplex audio with Gemini Live over a WebSocket.

Architecture (mirrors text chat, in audio):
    browser mic (16kHz PCM) --WS--> here --realtime--> Gemini Live
    Gemini Live --audio(24kHz)/transcripts/tool_calls--> here --WS--> browser

We proxy the live session through the backend (never exposing the user's Gemini key to the
browser), execute tool calls SERVER-SIDE against the same tools text chat uses, and persist
each completed turn as normal `Message` rows so the conversation shows up in the chat thread
afterwards (per-turn, so nothing is lost if the tab closes).

Client protocol (JSON text frames both ways):
    browser -> server:  {"type":"audio","data":"<base64 16k PCM>"}
                        {"type":"end"}                      # user asked to stop
    server -> browser:  {"type":"ready","voice":"Aoede"}
                        {"type":"audio","data":"<base64 24k PCM>"}
                        {"type":"input_transcript","text":...}   # what the user said
                        {"type":"output_transcript","text":...}  # what the persona says
                        {"type":"score", ...word/delta/score_after...}   # live word animation
                        {"type":"tool","name":...}                # (dev/telemetry, non-score)
                        {"type":"turn_complete"}
                        {"type":"interrupted"}                    # barge-in: clear playback
                        {"type":"error","message":...}
"""

from __future__ import annotations

import asyncio
import base64
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from google.genai import types

from .. import repo
from ..config import DEFAULT_VOICE, VOICES, settings
from ..deps import get_current_user_obj
from ..models import Message, User
from ..schemas import VoiceCatalogOut, VoiceOut
from ..services import auth_service, chat_service, model_service, voice_service
from ..services.model_service import NoModelConfigured
from ..services.voice_tools import VoiceToolExecutor

router = APIRouter(prefix="/api/voice", tags=["voice"])

# Where users can hear the voices themselves (Google AI Studio, this exact live model).
AUDITION_URL = f"https://aistudio.google.com/live?model={settings.voice_model}"


# --- REST: voice catalogue + availability --------------------------------------------------

@router.get("/voices", response_model=VoiceCatalogOut)
def list_voices(user: User = Depends(get_current_user_obj)):
    """The voice catalogue for the persona-form picker (name + tone + gender), the default
    voice id, and the URL where the user can audition them. `available` on /status governs
    whether voice mode can actually run (needs a configured key)."""
    return VoiceCatalogOut(
        voices=[VoiceOut(**v) for v in VOICES],
        default=DEFAULT_VOICE,
        audition_url=AUDITION_URL,
    )


@router.get("/status")
def voice_status(user: User = Depends(get_current_user_obj)):
    """Whether voice mode is available for this user (they have a working BYO key + tier)."""
    return {"available": bool(user.encrypted_api_key and user.model_tier)}


# --- WebSocket auth (cannot use the HTTP Depends chain — it raises HTTPException) ----------

def _authenticate(ws: WebSocket) -> str | None:
    """Resolve the current user's id from the session cookie on the WS handshake, or None."""
    token = ws.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    try:
        user_id = auth_service.decode_session_jwt(token)
    except auth_service.AuthError:
        return None
    return user_id if repo.get_user(user_id) is not None else None


# --- Per-turn transcript buffer ------------------------------------------------------------

class _TurnBuffer:
    """Accumulates the streamed input/output transcript chunks for the current turn, and
    persists them as a user Message + assistant Message when the turn completes."""

    def __init__(self, conversation, executor: VoiceToolExecutor):
        self.conversation = conversation
        self.executor = executor
        self.user_text = ""
        self.assistant_text = ""

    def add_input(self, text: str) -> None:
        self.user_text += text

    def add_output(self, text: str) -> None:
        self.assistant_text += text

    def _next_seq(self) -> int:
        msgs = self.conversation.messages
        return (msgs[-1].seq + 1) if msgs else 1

    def flush(self) -> None:
        """Persist the completed turn (if it produced anything) and reset for the next one.

        Order matters: persist the USER message first so we can back-fill any live word-score
        events with its id (chips reattach to the right message on reload), then the ASSISTANT
        message carrying this turn's tool_calls (surfaced in Developer mode like text chat)."""
        records = self.executor.drain_records()
        user_text = self.user_text.strip()
        assistant_text = self.assistant_text.strip()
        self.user_text = self.assistant_text = ""

        if not user_text and not assistant_text and not records:
            return

        user_msg = None
        if user_text:
            user_msg = Message(
                conversation_id=self.conversation.id, seq=self._next_seq(),
                role="user", content=user_text, user_id=self.conversation.user_id,
            )
            repo.insert_message(user_msg)
            self.conversation.messages.append(user_msg)

        # Back-fill message_id on live score events -> the user message of this turn.
        if user_msg is not None:
            for rec in records:
                if rec["name"] == "score_word":
                    ev_id = (rec.get("output") or {}).get("event_id")
                    if ev_id:
                        repo.set_event_message_id(ev_id, user_msg.id, self.conversation.user_id)

        # Assistant message: store tool_calls in the SAME shape text chat uses
        # ({id,name,args,output}) so Developer mode renders them identically. Voice tool calls
        # have no provider id, so we synthesize a stable one.
        tool_calls = [
            {
                "id": f"voice-{i}",
                "name": rec["name"],
                "args": rec["args"],
                "output": rec["output"] if isinstance(rec["output"], str) else json.dumps(rec["output"]),
            }
            for i, rec in enumerate(records)
        ]
        if assistant_text or tool_calls:
            assistant_msg = Message(
                conversation_id=self.conversation.id, seq=self._next_seq(),
                role="assistant", content=assistant_text, tool_calls=tool_calls,
                user_id=self.conversation.user_id,
            )
            repo.insert_message(assistant_msg)
            self.conversation.messages.append(assistant_msg)

        repo.touch_conversation(self.conversation.id)


async def _maybe_title(conversation, user_id: str) -> None:
    """Auto-title a voice conversation after its first exchange — same flow as text chat.

    Reuses chat_service._maybe_set_title (self-guards on title=="New conversation" and
    >=2 messages, so calling it after every turn is safe/idempotent). Runs off the event
    loop via to_thread since the title LLM call is blocking, and swallows all errors so a
    failed title never disrupts the live session."""
    if conversation.title != "New conversation" or len(conversation.messages) < 2:
        return
    try:
        resolved = model_service.resolve_for_user(user_id)
        await asyncio.to_thread(chat_service._maybe_set_title, conversation, resolved)
    except Exception:
        pass


# --- Relay loops ---------------------------------------------------------------------------

async def _browser_to_gemini(ws: WebSocket, session) -> None:
    """Forward the browser's mic PCM to Gemini; handle the explicit stop signal."""
    while True:
        raw = await ws.receive_text()
        msg = json.loads(raw)
        mtype = msg.get("type")
        if mtype == "audio":
            audio_bytes = base64.b64decode(msg["data"])
            await session.send_realtime_input(
                audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
            )
        elif mtype == "end":
            # User pressed stop — end this coroutine; the caller tears the session down.
            return


async def _gemini_to_browser(ws: WebSocket, session, buffer: _TurnBuffer, executor: VoiceToolExecutor) -> None:
    """Relay Gemini's audio/transcripts to the browser, execute tool calls, persist turns.

    `session.receive()` yields ONE turn's worth of messages and then its async iterator ends.
    So we wrap it in an outer `while True` to re-enter it for every subsequent turn — without
    this, the session would tear down after the first exchange (matches the proven pattern in
    the reference architecture)."""
    while True:
        async for message in session.receive():
            sc = message.server_content

            # --- Audio + transcripts ---
            if sc is not None:
                if sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            b64 = base64.b64encode(part.inline_data.data).decode("utf-8")
                            await ws.send_json({"type": "audio", "data": b64})

                if sc.input_transcription and sc.input_transcription.text:
                    text = sc.input_transcription.text
                    buffer.add_input(text)
                    await ws.send_json({"type": "input_transcript", "text": text})

                if sc.output_transcription and sc.output_transcription.text:
                    text = sc.output_transcription.text
                    buffer.add_output(text)
                    await ws.send_json({"type": "output_transcript", "text": text})

                if sc.interrupted:
                    # Barge-in: tell the browser to drop its queued playback.
                    await ws.send_json({"type": "interrupted"})

                if sc.turn_complete:
                    buffer.flush()  # persist this turn as messages
                    # Title after the first exchange, exactly like text chat (self-guards).
                    await _maybe_title(buffer.conversation, buffer.conversation.user_id)
                    await ws.send_json({"type": "turn_complete"})

            # --- Tool calls (execute server-side, reply to the model) ---
            if message.tool_call:
                responses = []
                for fc in message.tool_call.function_calls:
                    result = executor.execute(fc.name, dict(fc.args or {}))
                    responses.append(
                        types.FunctionResponse(id=fc.id, name=fc.name, response=result)
                    )
                    # A score result drives the live on-screen animation immediately.
                    if fc.name == "score_word" and result.get("status") == "ok":
                        await ws.send_json({
                            "type": "score",
                            "word": result["word"],
                            "word_id": result["word_id"],
                            "event_type": result["event_type"],
                            "delta": result["delta"],
                            "score_after": result["score_after"],
                            "note": result.get("note", ""),
                        })
                    else:
                        await ws.send_json({"type": "tool", "name": fc.name})
                if responses:
                    await session.send_tool_response(function_responses=responses)


@router.websocket("/ws/{conversation_id}")
async def voice_ws(ws: WebSocket, conversation_id: str):
    await ws.accept()

    user_id = _authenticate(ws)
    if user_id is None:
        await ws.send_json({"type": "error", "message": "Not authenticated"})
        await ws.close(code=4401)
        return

    conversation = repo.get_conversation(conversation_id, user_id, with_messages=True)
    if conversation is None:
        await ws.send_json({"type": "error", "message": "Conversation not found"})
        await ws.close(code=4404)
        return

    executor = VoiceToolExecutor(
        conversation_id=conversation.id, user_id=user_id, persona_id=conversation.persona_id
    )
    buffer = _TurnBuffer(conversation, executor)

    try:
        async with voice_service.open_session(conversation) as (session, voice):
            await ws.send_json({"type": "ready", "voice": voice})
            # Run both directions; when EITHER finishes (user pressed stop, or the model/socket
            # ended), cancel the other so the session tears down cleanly.
            tasks = [
                asyncio.create_task(_browser_to_gemini(ws, session)),
                asyncio.create_task(_gemini_to_browser(ws, session, buffer, executor)),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for t in done:
                if t.exception() and not isinstance(t.exception(), WebSocketDisconnect):
                    raise t.exception()
    except NoModelConfigured:
        await ws.send_json({"type": "error", "message": "No model configured"})
    except WebSocketDisconnect:
        pass
    except Exception as e:  # never leak a raw stack trace to the client
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        # Persist any half-finished turn's transcript so nothing is lost on abrupt close.
        try:
            buffer.flush()
            # Title if this was the first exchange and no turn_complete fired to do it.
            await _maybe_title(buffer.conversation, buffer.conversation.user_id)
        except Exception:
            pass
        try:
            await ws.close()
        except Exception:
            pass
