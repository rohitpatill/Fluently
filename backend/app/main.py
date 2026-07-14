from dotenv import load_dotenv

load_dotenv()  # must run before anything reads provider env vars

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import mongo
from .config import settings
from .routers import (
    auth,
    chat,
    conversations,
    dashboard,
    memory,
    model,
    personas,
    settings as settings_router,
    voice,
    words,
)

app = FastAPI(title="Fluently — English Proficiency Companion", version="0.1.0")

# Background heartbeat: prints to the terminal that the server is alive every 30 seconds.
HEARTBEAT_INTERVAL_SECONDS = 30
_heartbeat_task: asyncio.Task | None = None


async def _heartbeat_loop():
    while True:
        print("Server status: OK — Fluently backend is up and running.", flush=True)
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)

# Allowed browser origins come from CORS_ALLOWED_ORIGINS in .env (comma-separated).
# Every deployed frontend origin MUST be listed or the browser's CORS preflight
# (OPTIONS) is rejected. Config-driven, so production is a .env change, not a code change.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(words.router)
app.include_router(memory.router)
app.include_router(model.router)
app.include_router(personas.router)
app.include_router(voice.router)
app.include_router(dashboard.router)
app.include_router(settings_router.router)


@app.on_event("startup")
def startup():
    mongo.ping()  # fail fast if the cluster is unreachable
    mongo.ensure_indexes()
    # Memory files are bootstrapped per-user on first login (see routers/auth.py),
    # not globally — there is no longer a single "default" user to seed.
    # Start the 30-second server-status heartbeat printer.
    global _heartbeat_task
    _heartbeat_task = asyncio.create_task(_heartbeat_loop())


@app.on_event("shutdown")
def shutdown():
    if _heartbeat_task is not None:
        _heartbeat_task.cancel()


@app.get("/api/health")
def health():
    return {"status": "ok"}
