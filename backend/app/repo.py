"""The ONE place that talks to MongoDB. Everything else calls these functions.

Swap databases later = rewrite this module only (and mongo.py). Services and routers
never import pymongo or touch a collection directly.

Every function takes `user_id` (defaults to the single-user sentinel) so OAuth scoping
later is a filter that already exists. IDs in and out are ObjectId hex strings.
"""

from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId

from .models import Conversation, Message, Persona, User, Word, WordEvent, utcnow
from .mongo import (
    DEFAULT_USER_ID,
    conversations_col,
    memory_files_col,
    messages_col,
    personas_col,
    users_col,
    word_events_col,
    words_col,
)


def _oid(id_str: str):
    """Coerce a hex string to ObjectId; raise ValueError (→ 404-able) on bad input."""
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        raise ValueError(f"Invalid id: {id_str!r}")


# ============================================================ WORDS
def list_words(user_id: str = DEFAULT_USER_ID, sort_by_score_desc: bool = True) -> list[Word]:
    cur = words_col().find({"user_id": user_id})
    if sort_by_score_desc:
        cur = cur.sort("score", -1)
    return [Word.from_doc(d) for d in cur]


def get_word(word_id: str, user_id: str = DEFAULT_USER_ID) -> Word | None:
    try:
        doc = words_col().find_one({"_id": _oid(word_id), "user_id": user_id})
    except ValueError:
        return None
    return Word.from_doc(doc) if doc else None


def get_words_by_ids(word_ids: list[str], user_id: str = DEFAULT_USER_ID) -> list[Word]:
    oids = []
    for wid in word_ids:
        try:
            oids.append(_oid(wid))
        except ValueError:
            continue
    if not oids:
        return []
    docs = words_col().find({"_id": {"$in": oids}, "user_id": user_id})
    return [Word.from_doc(d) for d in docs]


def find_word_by_text(text: str, user_id: str = DEFAULT_USER_ID) -> Word | None:
    # case-insensitive exact match (mirrors the old .ilike(text))
    doc = words_col().find_one(
        {"user_id": user_id, "text": {"$regex": f"^{_escape_regex(text)}$", "$options": "i"}}
    )
    return Word.from_doc(doc) if doc else None


def insert_word(word: Word) -> Word:
    res = words_col().insert_one(word.to_doc())
    word.id = str(res.inserted_id)
    return word


def save_word(word: Word) -> Word:
    """Persist changes to an existing word (full replace of mutable fields)."""
    words_col().update_one({"_id": _oid(word.id)}, {"$set": word.to_doc()})
    return word


def delete_word(word_id: str, user_id: str = DEFAULT_USER_ID) -> bool:
    oid = _oid(word_id)
    words_col().delete_one({"_id": oid, "user_id": user_id})
    # cascade: remove the word's events
    word_events_col().delete_many({"word_id": word_id, "user_id": user_id})
    return True


def load_events(word: Word) -> Word:
    docs = word_events_col().find({"word_id": word.id}).sort("created_at", 1)
    word.events = [WordEvent.from_doc(d) for d in docs]
    return word


# ============================================================ WORD EVENTS
def insert_event(event: WordEvent) -> WordEvent:
    res = word_events_col().insert_one(event.to_doc())
    event.id = str(res.inserted_id)
    return event


def word_events(word_id: str, user_id: str = DEFAULT_USER_ID, limit: int = 100) -> list[WordEvent]:
    docs = (
        word_events_col()
        .find({"word_id": word_id, "user_id": user_id})
        .sort("created_at", -1)
        .limit(limit)
    )
    return [WordEvent.from_doc(d) for d in docs]


def events_for_conversation(conversation_id: str, user_id: str = DEFAULT_USER_ID) -> list[WordEvent]:
    docs = (
        word_events_col()
        .find({"conversation_id": conversation_id, "message_id": {"$ne": None}, "user_id": user_id})
        .sort("created_at", 1)
    )
    return [WordEvent.from_doc(d) for d in docs]


# ============================================================ CONVERSATIONS
def list_conversations(user_id: str = DEFAULT_USER_ID, persona_id: str | None = None) -> list[Conversation]:
    q: dict = {"user_id": user_id}
    if persona_id is not None:
        q["persona_id"] = persona_id
    docs = conversations_col().find(q).sort("updated_at", -1)
    return [Conversation.from_doc(d) for d in docs]


def get_conversation(conversation_id: str, user_id: str = DEFAULT_USER_ID, with_messages: bool = False) -> Conversation | None:
    try:
        doc = conversations_col().find_one({"_id": _oid(conversation_id), "user_id": user_id})
    except ValueError:
        return None
    if not doc:
        return None
    conv = Conversation.from_doc(doc)
    if with_messages:
        load_messages(conv)
    return conv


def insert_conversation(conv: Conversation) -> Conversation:
    res = conversations_col().insert_one(conv.to_doc())
    conv.id = str(res.inserted_id)
    return conv


def save_conversation(conv: Conversation) -> Conversation:
    conv.updated_at = utcnow()
    conversations_col().update_one({"_id": _oid(conv.id)}, {"$set": conv.to_doc()})
    return conv


def touch_conversation(conversation_id: str) -> None:
    conversations_col().update_one({"_id": _oid(conversation_id)}, {"$set": {"updated_at": utcnow()}})


def delete_conversation(conversation_id: str, user_id: str = DEFAULT_USER_ID) -> bool:
    oid = _oid(conversation_id)
    conversations_col().delete_one({"_id": oid, "user_id": user_id})
    messages_col().delete_many({"conversation_id": conversation_id, "user_id": user_id})
    # keep score history alive but detach it from the deleted conversation
    word_events_col().update_many(
        {"conversation_id": conversation_id, "user_id": user_id},
        {"$set": {"conversation_id": None, "message_id": None}},
    )
    return True


def recent_conversations(user_id: str = DEFAULT_USER_ID, limit: int = 8,
                          persona_id: str | None = None) -> list[Conversation]:
    q: dict = {"user_id": user_id}
    if persona_id is not None:
        q["persona_id"] = persona_id
    docs = conversations_col().find(q).sort("updated_at", -1).limit(limit)
    return [Conversation.from_doc(d) for d in docs]


# ============================================================ MESSAGES
def load_messages(conv: Conversation) -> Conversation:
    docs = messages_col().find({"conversation_id": conv.id}).sort("seq", 1)
    conv.messages = [Message.from_doc(d) for d in docs]
    return conv


def insert_message(msg: Message) -> Message:
    res = messages_col().insert_one(msg.to_doc())
    msg.id = str(res.inserted_id)
    return msg


def all_messages(user_id: str = DEFAULT_USER_ID, exclude_conversation_id: str | None = None,
                 conversation_id: str | None = None, persona_id: str | None = None) -> list[Message]:
    """Load messages for search (BM25/regex ranking happens in Python, as before).

    When `persona_id` is given, results are limited to conversations belonging to that persona,
    so a companion can only recall/search chats it actually had with the user."""
    q: dict = {"user_id": user_id, "role": {"$in": ["user", "assistant"]}}
    if conversation_id is not None:
        q["conversation_id"] = conversation_id
    if exclude_conversation_id is not None:
        q["conversation_id"] = {"$ne": exclude_conversation_id}
    if persona_id is not None:
        # Narrow to the persona's conversations, honoring any include/exclude constraint by
        # folding it into the id set (replaces the plain conversation_id filter set above).
        conv_ids = [c.id for c in list_conversations(user_id, persona_id=persona_id)]
        if conversation_id is not None:
            conv_ids = [cid for cid in conv_ids if cid == conversation_id]
        if exclude_conversation_id is not None:
            conv_ids = [cid for cid in conv_ids if cid != exclude_conversation_id]
        q["conversation_id"] = {"$in": conv_ids}
    docs = messages_col().find(q).sort([("conversation_id", 1), ("seq", 1)])
    return [Message.from_doc(d) for d in docs]


def last_user_message(conversation_id: str, user_id: str = DEFAULT_USER_ID) -> Message | None:
    doc = (
        messages_col()
        .find({"conversation_id": conversation_id, "role": "user", "user_id": user_id})
        .sort("seq", -1)
        .limit(1)
    )
    docs = list(doc)
    return Message.from_doc(docs[0]) if docs else None


def get_message(message_id: str, user_id: str = DEFAULT_USER_ID) -> Message | None:
    try:
        doc = messages_col().find_one({"_id": _oid(message_id), "user_id": user_id})
    except ValueError:
        return None
    return Message.from_doc(doc) if doc else None


# ============================================================ DASHBOARD STATS
def dashboard_counts(user_id: str = DEFAULT_USER_ID) -> dict:
    wc = words_col()
    total_words = wc.count_documents({"user_id": user_id})
    mastered = wc.count_documents({"user_id": user_id, "score": {"$gte": 100}})
    avg_res = list(wc.aggregate([
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": None, "avg": {"$avg": "$score"}}},
    ]))
    avg_score = float(avg_res[0]["avg"]) if avg_res else 0.0
    return {
        "total_words": total_words,
        "mastered": mastered,
        "average_score": avg_score,
        "total_conversations": conversations_col().count_documents({"user_id": user_id}),
        "total_messages": messages_col().count_documents({"user_id": user_id}),
    }


def events_since(since: datetime, user_id: str = DEFAULT_USER_ID) -> tuple[int, float]:
    ec = word_events_col()
    count = ec.count_documents({"user_id": user_id, "created_at": {"$gte": since}})
    gained = list(ec.aggregate([
        {"$match": {"user_id": user_id, "created_at": {"$gte": since}, "delta": {"$gt": 0}}},
        {"$group": {"_id": None, "total": {"$sum": "$delta"}}},
    ]))
    return count, (float(gained[0]["total"]) if gained else 0.0)


def top_words(user_id: str = DEFAULT_USER_ID, limit: int = 5) -> list[Word]:
    docs = words_col().find({"user_id": user_id}).sort("score", -1).limit(limit)
    return [Word.from_doc(d) for d in docs]


def weakest_words(user_id: str = DEFAULT_USER_ID, limit: int = 5) -> list[Word]:
    docs = words_col().find({"user_id": user_id, "score": {"$lt": 100}}).sort("score", 1).limit(limit)
    return [Word.from_doc(d) for d in docs]


def slipping_words(cutoff: datetime, user_id: str = DEFAULT_USER_ID, limit: int = 5) -> list[Word]:
    docs = (
        words_col()
        .find({
            "user_id": user_id,
            "score": {"$gt": 0, "$lt": 100},
            "$or": [{"last_used_at": None}, {"last_used_at": {"$lt": cutoff}}],
        })
        .sort("score", -1)
        .limit(limit)
    )
    return [Word.from_doc(d) for d in docs]


# ============================================================ MEMORY FILES
def get_memory_file(file: str, user_id: str = DEFAULT_USER_ID) -> str | None:
    """Return the full markdown string, or None if the file doc doesn't exist yet."""
    doc = memory_files_col().find_one({"user_id": user_id, "file": file})
    return doc["content"] if doc else None


def set_memory_file(file: str, content: str, user_id: str = DEFAULT_USER_ID) -> None:
    """Upsert the whole markdown string for a memory file (read-modify-write pattern)."""
    memory_files_col().update_one(
        {"user_id": user_id, "file": file},
        {"$set": {"content": content, "updated_at": utcnow()},
         "$setOnInsert": {"user_id": user_id, "file": file, "created_at": utcnow()}},
        upsert=True,
    )


# ============================================================ SETTINGS / PURGE
def purge_conversations(user_id: str = DEFAULT_USER_ID) -> tuple[int, int]:
    word_events_col().update_many(
        {"user_id": user_id}, {"$set": {"conversation_id": None, "message_id": None}}
    )
    n_msg = messages_col().delete_many({"user_id": user_id}).deleted_count
    n_conv = conversations_col().delete_many({"user_id": user_id}).deleted_count
    return n_conv, n_msg


def purge_words(user_id: str = DEFAULT_USER_ID) -> int:
    word_events_col().delete_many({"user_id": user_id})
    return words_col().delete_many({"user_id": user_id}).deleted_count


def _escape_regex(text: str) -> str:
    import re
    return re.escape(text)


# ============================================================ USERS / AUTH
def get_user(user_id: str) -> User | None:
    try:
        doc = users_col().find_one({"_id": _oid(user_id)})
    except ValueError:
        return None
    return User.from_doc(doc) if doc else None


def get_user_by_sub(google_sub: str) -> User | None:
    doc = users_col().find_one({"google_sub": google_sub})
    return User.from_doc(doc) if doc else None


def has_any_user() -> bool:
    """True if at least one user account exists — used to detect the very first login."""
    return users_col().count_documents({}, limit=1) > 0


def upsert_user_from_google(sub: str, email: str, name: str = "", picture: str = "") -> tuple[User, bool]:
    """Find the user by Google subject id, or create them. Returns (user, created).
    On an existing user, refresh mutable profile fields (name/picture/email can change)."""
    existing = get_user_by_sub(sub)
    if existing:
        users_col().update_one(
            {"_id": _oid(existing.id)},
            {"$set": {"email": email, "name": name, "picture": picture}},
        )
        existing.email, existing.name, existing.picture = email, name, picture
        return existing, False

    user = User(google_sub=sub, email=email, name=name, picture=picture)
    res = users_col().insert_one(user.to_doc())
    user.id = str(res.inserted_id)
    return user, True


def set_user_key(user_id: str, encrypted_api_key: str, model_tier: str) -> None:
    """Store the user's ENCRYPTED api key + chosen tier (the 'How smart should I be?' step
    and the Settings 'replace key' flow both land here). Never store plaintext."""
    users_col().update_one(
        {"_id": _oid(user_id)},
        {"$set": {"encrypted_api_key": encrypted_api_key, "model_tier": model_tier}},
    )


def set_user_tier(user_id: str, model_tier: str) -> None:
    """Switch the user's tier only (same key). Used by the Settings Swift↔Sage toggle."""
    users_col().update_one({"_id": _oid(user_id)}, {"$set": {"model_tier": model_tier}})


def clear_user_model(user_id: str) -> None:
    """Wipe the user's stored key + tier, so they must reconfigure via the 'How smart should
    I be?' step. Part of the FULL reset (purge-all without keeping words)."""
    users_col().update_one(
        {"_id": _oid(user_id)}, {"$set": {"encrypted_api_key": "", "model_tier": ""}}
    )


# ============================================================ PERSONAS
def list_personas(user_id: str = DEFAULT_USER_ID) -> list[Persona]:
    docs = personas_col().find({"user_id": user_id}).sort("created_at", 1)
    return [Persona.from_doc(d) for d in docs]


def get_persona(persona_id: str, user_id: str = DEFAULT_USER_ID) -> Persona | None:
    try:
        doc = personas_col().find_one({"_id": _oid(persona_id), "user_id": user_id})
    except ValueError:
        return None
    return Persona.from_doc(doc) if doc else None


def insert_persona(persona: Persona) -> Persona:
    persona.created_at = persona.created_at or utcnow()
    persona.updated_at = utcnow()
    res = personas_col().insert_one(persona.to_doc())
    persona.id = str(res.inserted_id)
    return persona


def save_persona(persona: Persona) -> Persona:
    persona.updated_at = utcnow()
    personas_col().update_one({"_id": _oid(persona.id)}, {"$set": persona.to_doc()})
    return persona


def set_persona_content(persona_id: str, content: str, user_id: str = DEFAULT_USER_ID) -> None:
    personas_col().update_one(
        {"_id": _oid(persona_id), "user_id": user_id},
        {"$set": {"content": content, "updated_at": utcnow()}},
    )


def set_persona_avatar(persona_id: str, avatar_url: str, user_id: str = DEFAULT_USER_ID) -> None:
    personas_col().update_one(
        {"_id": _oid(persona_id), "user_id": user_id},
        {"$set": {"avatar_url": avatar_url, "updated_at": utcnow()}},
    )


def delete_persona(persona_id: str, user_id: str = DEFAULT_USER_ID) -> tuple[int, int]:
    """Delete a persona AND all its conversations/messages (they only made sense with that
    companion). Word scores stay — score events are detached from the removed conversations.
    Returns (conversations_deleted, messages_deleted)."""
    convs = list_conversations(user_id, persona_id=persona_id)
    conv_ids = [c.id for c in convs]
    n_msg = 0
    if conv_ids:
        n_msg = messages_col().delete_many(
            {"conversation_id": {"$in": conv_ids}, "user_id": user_id}
        ).deleted_count
        word_events_col().update_many(
            {"conversation_id": {"$in": conv_ids}, "user_id": user_id},
            {"$set": {"conversation_id": None, "message_id": None}},
        )
    n_conv = conversations_col().delete_many(
        {"_id": {"$in": [_oid(cid) for cid in conv_ids]}, "user_id": user_id}
    ).deleted_count if conv_ids else 0
    personas_col().delete_one({"_id": _oid(persona_id), "user_id": user_id})
    return n_conv, n_msg


def count_personas(user_id: str = DEFAULT_USER_ID) -> int:
    return personas_col().count_documents({"user_id": user_id})


def purge_personas(user_id: str = DEFAULT_USER_ID) -> int:
    """Delete ALL of a user's personas and clear the active pointer. Part of the full-reset /
    reset-keep-words flows (the app then restarts at onboarding, recreating one persona)."""
    n = personas_col().delete_many({"user_id": user_id}).deleted_count
    users_col().update_one({"_id": _oid(user_id)}, {"$set": {"active_persona_id": None}})
    return n


def set_active_persona(user_id: str, persona_id: str | None) -> None:
    users_col().update_one({"_id": _oid(user_id)}, {"$set": {"active_persona_id": persona_id}})


def reassign_default_data(new_user_id: str) -> dict:
    """One-time adoption: move every legacy `DEFAULT_USER_ID` document to `new_user_id`.
    Called only for the first-ever user (guarded by the caller). Returns per-collection counts."""
    counts = {}
    for name, col in (
        ("conversations", conversations_col()),
        ("messages", messages_col()),
        ("words", words_col()),
        ("word_events", word_events_col()),
        ("memory_files", memory_files_col()),
    ):
        res = col.update_many({"user_id": DEFAULT_USER_ID}, {"$set": {"user_id": new_user_id}})
        counts[name] = res.modified_count
    users_col().update_one({"_id": _oid(new_user_id)}, {"$set": {"adopted_default": True}})
    return counts
