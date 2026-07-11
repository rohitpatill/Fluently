"""One-time migration: copy existing SQLite data (backend/data/eng.db) + the 3 on-disk
memory markdown files into MongoDB.

Run this ONCE if you want to bring your current words / conversations / score history /
memories into the new Mongo store. It is idempotent-ish: re-running clears the target
user's Mongo data first (with --wipe) so you don't get duplicates.

Usage (from backend/, venv active):
    .venv\\Scripts\\python import_sqlite_to_mongo.py            # dry-run summary only
    .venv\\Scripts\\python import_sqlite_to_mongo.py --commit    # actually write to Mongo
    .venv\\Scripts\\python import_sqlite_to_mongo.py --commit --wipe   # wipe target user first

IDs: SQLite integer ids are remapped to fresh Mongo ObjectIds; all cross-references
(conversation.target_word_ids, message.conversation_id, word_event.word_id/conversation_id/
message_id) are rewritten through the id map so relationships stay intact.
"""

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app import mongo, repo  # noqa: E402
from app.models import Conversation, Message, Word, WordEvent  # noqa: E402
from app.mongo import DEFAULT_USER_ID  # noqa: E402

DB_PATH = Path("./data/eng.db")
DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
MEMORY_FILES = {"identity": "identity.md", "memory": "memory.md", "persona": "persona.md"}


def _dt(val):
    """SQLite stores datetimes as ISO strings; normalize to aware UTC datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(val))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _json(val, default):
    if val is None:
        return default
    if isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="actually write to Mongo (default: dry run)")
    ap.add_argument("--wipe", action="store_true", help="delete target user's Mongo data before import")
    ap.add_argument("--user", default=DEFAULT_USER_ID, help="user_id to assign imported docs to")
    args = ap.parse_args()
    uid = args.user

    if not DB_PATH.exists():
        print(f"No SQLite DB found at {DB_PATH.resolve()} — nothing to import.")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    words = [dict(r) for r in conn.execute("SELECT * FROM words")] if "words" in tables else []
    convs = [dict(r) for r in conn.execute("SELECT * FROM conversations")] if "conversations" in tables else []
    msgs = [dict(r) for r in conn.execute("SELECT * FROM messages")] if "messages" in tables else []
    events = [dict(r) for r in conn.execute("SELECT * FROM word_events")] if "word_events" in tables else []
    conn.close()

    mem_present = [k for k, f in MEMORY_FILES.items() if (DATA_DIR / f).exists()]

    print("=== SQLite source summary ===")
    print(f"  words:         {len(words)}")
    print(f"  conversations: {len(convs)}")
    print(f"  messages:      {len(msgs)}")
    print(f"  word_events:   {len(events)}")
    print(f"  memory files:  {', '.join(mem_present) or '(none)'}")
    print(f"  target user_id: {uid}")

    if not args.commit:
        print("\nDRY RUN — nothing written. Re-run with --commit to import.")
        return

    mongo.ensure_indexes()

    if args.wipe:
        repo.purge_conversations(uid)
        repo.purge_words(uid)
        for key in MEMORY_FILES:
            mongo.memory_files_col().delete_one({"user_id": uid, "file": key})
        print("\nWiped existing Mongo data for this user.")

    word_id_map: dict[int, str] = {}
    conv_id_map: dict[int, str] = {}
    msg_id_map: dict[int, str] = {}

    # ---- words
    for w in words:
        obj = Word(
            text=w["text"], kind=w.get("kind", "word"), meaning=w.get("meaning", ""),
            examples=_json(w.get("examples"), []), collocations=_json(w.get("collocations"), []),
            register_notes=w.get("register_notes", ""), note=w.get("note", "") or "",
            score=w.get("score", 0.0), times_used=w.get("times_used", 0),
            last_used_at=_dt(w.get("last_used_at")), last_decay_at=_dt(w.get("last_decay_at")),
            created_at=_dt(w.get("created_at")), user_id=uid,
        )
        repo.insert_word(obj)
        word_id_map[w["id"]] = obj.id

    # ---- conversations (remap target_word_ids)
    for c in convs:
        targets = [word_id_map[t] for t in _json(c.get("target_word_ids"), []) if t in word_id_map]
        obj = Conversation(
            title=c.get("title", "New conversation"), category=c.get("category"),
            target_word_ids=targets, created_at=_dt(c.get("created_at")),
            updated_at=_dt(c.get("updated_at")), user_id=uid,
        )
        repo.insert_conversation(obj)
        conv_id_map[c["id"]] = obj.id

    # ---- messages (remap conversation_id)
    for m in msgs:
        cid = conv_id_map.get(m["conversation_id"])
        if cid is None:
            continue
        obj = Message(
            conversation_id=cid, seq=m.get("seq", 0), role=m.get("role", ""),
            content=m.get("content", ""), tool_calls=_json(m.get("tool_calls"), []),
            created_at=_dt(m.get("created_at")), user_id=uid,
        )
        repo.insert_message(obj)
        msg_id_map[m["id"]] = obj.id

    # ---- word_events (remap word_id / conversation_id / message_id)
    for e in events:
        wid = word_id_map.get(e["word_id"])
        if wid is None:
            continue
        obj = WordEvent(
            word_id=wid,
            conversation_id=conv_id_map.get(e.get("conversation_id")),
            message_id=msg_id_map.get(e.get("message_id")),
            event_type=e.get("event_type", ""), delta=e.get("delta", 0.0),
            score_after=e.get("score_after", 0.0), judge_notes=e.get("judge_notes", ""),
            created_at=_dt(e.get("created_at")), user_id=uid,
        )
        repo.insert_event(obj)

    # ---- memory files
    for key, fname in MEMORY_FILES.items():
        p = DATA_DIR / fname
        if p.exists():
            repo.set_memory_file(key, p.read_text(encoding="utf-8"), uid)

    print("\n=== Imported into Mongo ===")
    print(f"  words:         {len(word_id_map)}")
    print(f"  conversations: {len(conv_id_map)}")
    print(f"  messages:      {len(msg_id_map)}")
    print(f"  word_events:   {len(events)}")
    print(f"  memory files:  {', '.join(mem_present) or '(none)'}")
    print("Done.")


if __name__ == "__main__":
    main()
