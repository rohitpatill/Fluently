"""One-time migration: single-persona → multi-persona.

For every user (and the legacy "default" bucket) this:
  1. Creates ONE Persona row from their existing `persona` memory_files doc (content preserved
     verbatim, including its `## Relationship memories`).
  2. Sets that persona as the user's `active_persona_id`.
  3. Backfills `persona_id` on ALL of that user's conversations (they belonged to that one
     companion).
  4. Deletes the now-redundant `persona` memory_files doc (identity/memory stay put).

Idempotent: a user who already has a persona row is skipped. Safe to re-run.

Dry-run by default — prints what it WOULD do. Pass --commit to actually write.

Usage:
    cd backend
    .venv\\Scripts\\python migrate_personas.py            # dry run
    .venv\\Scripts\\python migrate_personas.py --commit   # apply
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from app import repo  # noqa: E402
from app.models import Persona  # noqa: E402
from app.mongo import (  # noqa: E402
    DEFAULT_USER_ID,
    conversations_col,
    memory_files_col,
    personas_col,
    users_col,
)

COMMIT = "--commit" in sys.argv


def _user_ids() -> list[str]:
    """Every real user id + the legacy 'default' bucket if it still holds data."""
    ids = [str(u["_id"]) for u in users_col().find({}, {"_id": 1})]
    # Include the legacy default bucket if any un-adopted data is still tagged with it.
    if memory_files_col().count_documents({"user_id": DEFAULT_USER_ID}) or conversations_col().count_documents({"user_id": DEFAULT_USER_ID}):
        ids.append(DEFAULT_USER_ID)
    return ids


def migrate_user(user_id: str) -> dict:
    result = {"user_id": user_id, "action": "", "conversations_backfilled": 0}

    if personas_col().count_documents({"user_id": user_id}) > 0:
        result["action"] = "skipped (already has persona rows)"
        return result

    legacy = memory_files_col().find_one({"user_id": user_id, "file": "persona"})
    content = legacy["content"] if legacy else "# System Persona\n\n"

    result["action"] = "would create persona + backfill" if not COMMIT else "created persona + backfilled"

    if COMMIT:
        persona = repo.insert_persona(Persona(user_id=user_id, content=content))
        # active pointer (only for real users; the 'default' bucket has no user doc)
        if user_id != DEFAULT_USER_ID:
            repo.set_active_persona(user_id, persona.id)
        res = conversations_col().update_many(
            {"user_id": user_id, "$or": [{"persona_id": {"$exists": False}}, {"persona_id": None}]},
            {"$set": {"persona_id": persona.id}},
        )
        result["conversations_backfilled"] = res.modified_count
        # drop the redundant persona memory_files doc (identity/memory remain)
        memory_files_col().delete_one({"user_id": user_id, "file": "persona"})
    else:
        result["conversations_backfilled"] = conversations_col().count_documents(
            {"user_id": user_id, "$or": [{"persona_id": {"$exists": False}}, {"persona_id": None}]}
        )
    return result


def main():
    mode = "COMMIT" if COMMIT else "DRY RUN"
    print(f"=== Persona migration ({mode}) ===\n")
    ids = _user_ids()
    if not ids:
        print("No users found — nothing to migrate.")
        return
    for uid in ids:
        r = migrate_user(uid)
        print(f"user {r['user_id']}: {r['action']} "
              f"(conversations: {r['conversations_backfilled']})")
    print(f"\nDone. {len(ids)} user(s) processed.")
    if not COMMIT:
        print("This was a DRY RUN — re-run with --commit to apply.")


if __name__ == "__main__":
    main()
