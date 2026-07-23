"""Fluently in-app voice assistant — real-time duplex audio over a WebSocket (Gemini Live).

Separate from persona voice chat (`routers/voice.py`): this is the APP talking to the user for
help and a few hands-free actions. It reuses the SAME transport pattern and per-user key, but:
  * NOTHING is persisted — the assistant conversation is ephemeral (no Message rows, no titles).
  * NOTHING is scored — there is no judge and no score_word tool.
  * It is NOT tied to a persona conversation — it needs no conversation_id.

The assistant speaks FIRST: on connect we nudge the model to greet the user by name, so they
hear "Hey Rohit, what can I help with?" instead of silence.

Client protocol (JSON text frames), mirrors voice.py minus scoring/persistence:
    browser -> server:  {"type":"audio","data":"<base64 16k PCM>"}
                        {"type":"end"}
    server -> browser:  {"type":"ready"}
                        {"type":"audio","data":"<base64 24k PCM>"}
                        {"type":"input_transcript","text":...}
                        {"type":"output_transcript","text":...}
                        {"type":"action", "name":..., "message":...}   # a tool did something
                        {"type":"turn_complete"}
                        {"type":"interrupted"}
                        {"type":"error","message":...}
"""

from __future__ import annotations

import asyncio
import base64
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from .. import repo
from ..config import settings
from ..deps import get_current_user_obj
from ..models import User
from ..prompts import ASSISTANT_GREETING_INSTRUCTION
from ..services import assistant_service, auth_service
from ..services.assistant_tools import AssistantToolExecutor
from ..services.model_service import NoModelConfigured, resolve_for_user

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.get("/status")
def assistant_status(user: User = Depends(get_current_user_obj)):
    """Whether the Fluently voice assistant is available (the user has a working BYO key + tier)."""
    return {"available": bool(user.encrypted_api_key and user.model_tier)}


# --- Auth (WS handshake can't use the HTTP Depends chain — it raises HTTPException) ---------

def _authenticate(ws: WebSocket) -> str | None:
    token = ws.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    try:
        user_id = auth_service.decode_session_jwt(token)
    except auth_service.AuthError:
        return None
    return user_id if repo.get_user(user_id) is not None else None


# --- Relay loops ---------------------------------------------------------------------------

async def _browser_to_gemini(ws: WebSocket, session) -> None:
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
            return


async def _gemini_to_browser(ws: WebSocket, session, executor: AssistantToolExecutor) -> None:
    """Relay audio/transcripts to the browser and execute tool calls. No persistence, no scoring.
    `session.receive()` ends per turn, so wrap it in an outer loop to keep the session alive."""
    while True:
        async for message in session.receive():
            sc = message.server_content
            if sc is not None:
                if sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            b64 = base64.b64encode(part.inline_data.data).decode("utf-8")
                            await ws.send_json({"type": "audio", "data": b64})
                if sc.input_transcription and sc.input_transcription.text:
                    await ws.send_json({"type": "input_transcript", "text": sc.input_transcription.text})
                if sc.output_transcription and sc.output_transcription.text:
                    await ws.send_json({"type": "output_transcript", "text": sc.output_transcription.text})
                if sc.interrupted:
                    await ws.send_json({"type": "interrupted"})
                if sc.turn_complete:
                    await ws.send_json({"type": "turn_complete"})

            if message.tool_call:
                responses = []
                for fc in message.tool_call.function_calls:
                    result = executor.execute(fc.name, dict(fc.args or {}))
                    responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response=result))
                    # Surface a small on-screen confirmation when an action actually ran.
                    if result.get("status") == "ok" and result.get("action"):
                        await ws.send_json({
                            "type": "action",
                            "name": result.get("action"),
                            "message": result.get("message", ""),
                        })
                if responses:
                    await session.send_tool_response(function_responses=responses)


@router.websocket("/ws")
async def assistant_ws(ws: WebSocket, tab: str = "chat"):
    await ws.accept()

    user_id = _authenticate(ws)
    if user_id is None:
        await ws.send_json({"type": "error", "message": "Not authenticated"})
        await ws.close(code=4401)
        return

    executor = AssistantToolExecutor(user_id=user_id)

    try:
        resolved = resolve_for_user(user_id)  # decrypts the user's own key (pays for the session)
        client = genai.Client(api_key=resolved.api_key)
        config = assistant_service.build_live_config(user_id, tab)

        async with client.aio.live.connect(model=settings.voice_model, config=config) as session:
            await ws.send_json({"type": "ready"})
            # Speak first: nudge the model to greet the user by name (sent as a client turn so the
            # session has non-empty content, the same trick text chat's opener uses for Gemini).
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=ASSISTANT_GREETING_INSTRUCTION)])
            )
            tasks = [
                asyncio.create_task(_browser_to_gemini(ws, session)),
                asyncio.create_task(_gemini_to_browser(ws, session, executor)),
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
    except Exception as e:  # never leak a raw stack trace
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
