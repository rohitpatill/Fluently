from dotenv import load_dotenv

load_dotenv()  # must run before anything reads provider env vars

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import inspect, text

from .database import Base, engine
from .routers import chat, conversations, dashboard, memory, settings, words
from .services import memory_service

app = FastAPI(title="Fluently — English Proficiency Companion", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(words.router)
app.include_router(memory.router)
app.include_router(dashboard.router)
app.include_router(settings.router)


def _lightweight_migrations():
    """Add columns introduced after a user's DB was first created. SQLite only, additive,
    idempotent — enough for this single-file local app (no Alembic yet)."""
    inspector = inspect(engine)
    if "words" not in inspector.get_table_names():
        return  # create_all will make it fresh with all columns
    columns = {c["name"] for c in inspector.get_columns("words")}
    if "note" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE words ADD COLUMN note TEXT DEFAULT ''"))


@app.on_event("startup")
def startup():
    _lightweight_migrations()  # before create_all so existing tables get new columns
    Base.metadata.create_all(bind=engine)
    memory_service.ensure_files()


@app.get("/api/health")
def health():
    return {"status": "ok"}
