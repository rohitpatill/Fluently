"""MongoDB connection layer (PyMongo, sync — matches the app's sync routes).

Single shared MongoClient (thread-safe, connection-pooled). Collections are exposed
as module-level accessors so services/routers can `from .mongo import db, words_col, ...`.

Collections (mirror the old SQLite tables + the 3 memory files):
  conversations  — one doc per chat (title, category, target_word_ids, timestamps)
  messages       — one doc per message (conversation_id, seq, role, content, tool_calls)
  words          — one doc per tracked word (text, meaning, score, note, ...)
  word_events    — audit log of every score change
  memory_files   — the 3 markdown memory files (identity/memory/persona) as documents

Every document carries a `user_id` (default "default" while single-user) so Google-OAuth
scoping later is just a filter, not a schema reshape.
"""

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database

from .config import settings

# Sentinel user id used everywhere until real OAuth users exist.
DEFAULT_USER_ID = "default"

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        if not settings.mongodb_uri:
            raise RuntimeError("MONGODB_URI is not set — cannot connect to MongoDB.")
        _client = MongoClient(settings.mongodb_uri, tz_aware=True, appname="fluently")
    return _client


def get_db() -> Database:
    return get_client()[settings.mongodb_db]


# Convenience collection accessors ---------------------------------------------
def conversations_col():
    return get_db()["conversations"]


def messages_col():
    return get_db()["messages"]


def words_col():
    return get_db()["words"]


def word_events_col():
    return get_db()["word_events"]


def memory_files_col():
    return get_db()["memory_files"]


def users_col():
    return get_db()["users"]


def ping() -> dict:
    """Cheap round-trip to verify the cluster is reachable. Returns server 'ok'."""
    return get_client().admin.command("ping")


def ensure_indexes() -> None:
    """Create the indexes the app relies on. Idempotent — safe to call at startup."""
    # words: unique per (user_id, text) — per-user uniqueness (two users can both add "ubiquitous")
    words_col().create_index([("user_id", ASCENDING), ("text", ASCENDING)], unique=True, name="uq_user_text")
    words_col().create_index([("user_id", ASCENDING), ("score", ASCENDING)], name="user_score")

    # messages: ordered lookup within a conversation
    messages_col().create_index(
        [("conversation_id", ASCENDING), ("seq", ASCENDING)], name="conv_seq"
    )
    messages_col().create_index([("user_id", ASCENDING)], name="msg_user")

    # conversations: recent-first listing per user
    conversations_col().create_index(
        [("user_id", ASCENDING), ("updated_at", ASCENDING)], name="user_updated"
    )

    # word_events: history per word
    word_events_col().create_index([("word_id", ASCENDING), ("created_at", ASCENDING)], name="word_hist")

    # memory_files: one doc per (user_id, file)
    memory_files_col().create_index(
        [("user_id", ASCENDING), ("file", ASCENDING)], unique=True, name="uq_user_file"
    )

    # users: one doc per Google account. The doc's _id (hex str) IS the internal user_id
    # that scopes every other collection. google_sub is the natural key from Google.
    users_col().create_index([("google_sub", ASCENDING)], unique=True, name="uq_google_sub")
    users_col().create_index([("email", ASCENDING)], name="user_email")
