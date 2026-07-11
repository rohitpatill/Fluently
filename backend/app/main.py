from dotenv import load_dotenv

load_dotenv()  # must run before anything reads provider env vars

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import mongo
from .routers import auth, chat, conversations, dashboard, memory, settings, words

app = FastAPI(title="Fluently — English Proficiency Companion", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(words.router)
app.include_router(memory.router)
app.include_router(dashboard.router)
app.include_router(settings.router)


@app.on_event("startup")
def startup():
    mongo.ping()  # fail fast if the cluster is unreachable
    mongo.ensure_indexes()
    # Memory files are bootstrapped per-user on first login (see routers/auth.py),
    # not globally — there is no longer a single "default" user to seed.


@app.get("/api/health")
def health():
    return {"status": "ok"}
