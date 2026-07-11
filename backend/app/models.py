"""Domain document classes (MongoDB-backed).

These are plain attribute-carrying objects — NOT SQLAlchemy models anymore. They exist
so the rest of the app keeps working with familiar objects (`word.score`,
`conversation.messages`, `MessageOut.model_validate(msg)`), while `repo.py` is the only
module that knows about MongoDB. Swapping databases later = rewrite `repo.py` only.

IDs are MongoDB ObjectId hex strings (str), not ints. Every document carries a
`user_id` (defaults to the single-user sentinel) so Google-OAuth scoping later is just a
filter, not a schema reshape.

`to_doc()` serializes for insert/replace; `from_doc()` rebuilds from a Mongo document.
Relationship-y fields (`conversation.messages`, `word.events`) are populated on demand by
`repo.py`, not stored inside the document.
"""

from datetime import datetime, timezone

from .mongo import DEFAULT_USER_ID


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _oid_to_str(v):
    """ObjectId | str | None -> str | None."""
    return str(v) if v is not None else None


class Conversation:
    def __init__(
        self,
        title: str = "New conversation",
        category: str | None = None,
        target_word_ids: list[str] | None = None,
        user_id: str = DEFAULT_USER_ID,
        id: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        self.id = id
        self.user_id = user_id
        self.title = title
        self.category = category
        self.target_word_ids = list(target_word_ids or [])
        self.created_at = created_at or utcnow()
        self.updated_at = updated_at or utcnow()
        # populated on demand by repo.load_messages()
        self.messages: list["Message"] = []

    def to_doc(self) -> dict:
        return {
            "user_id": self.user_id,
            "title": self.title,
            "category": self.category,
            "target_word_ids": list(self.target_word_ids),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_doc(cls, doc: dict) -> "Conversation":
        return cls(
            id=_oid_to_str(doc.get("_id")),
            user_id=doc.get("user_id", DEFAULT_USER_ID),
            title=doc.get("title", "New conversation"),
            category=doc.get("category"),
            target_word_ids=[str(x) for x in doc.get("target_word_ids", [])],
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
        )


class Message:
    def __init__(
        self,
        conversation_id: str,
        seq: int,
        role: str,
        content: str,
        tool_calls: list | None = None,
        user_id: str = DEFAULT_USER_ID,
        id: str | None = None,
        created_at: datetime | None = None,
    ):
        self.id = id
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.seq = seq
        self.role = role
        self.content = content
        self.tool_calls = list(tool_calls or [])
        self.created_at = created_at or utcnow()

    def to_doc(self) -> dict:
        return {
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "seq": self.seq,
            "role": self.role,
            "content": self.content,
            "tool_calls": list(self.tool_calls),
            "created_at": self.created_at,
        }

    @classmethod
    def from_doc(cls, doc: dict) -> "Message":
        return cls(
            id=_oid_to_str(doc.get("_id")),
            user_id=doc.get("user_id", DEFAULT_USER_ID),
            conversation_id=str(doc.get("conversation_id")),
            seq=doc.get("seq", 0),
            role=doc.get("role", ""),
            content=doc.get("content", ""),
            tool_calls=doc.get("tool_calls", []),
            created_at=doc.get("created_at"),
        )


class Word:
    def __init__(
        self,
        text: str,
        kind: str = "word",
        meaning: str = "",
        examples: list | None = None,
        collocations: list | None = None,
        register_notes: str = "",
        note: str = "",
        score: float = 0.0,
        times_used: int = 0,
        last_used_at: datetime | None = None,
        last_decay_at: datetime | None = None,
        user_id: str = DEFAULT_USER_ID,
        id: str | None = None,
        created_at: datetime | None = None,
    ):
        self.id = id
        self.user_id = user_id
        self.text = text
        self.kind = kind
        self.meaning = meaning
        self.examples = list(examples or [])
        self.collocations = list(collocations or [])
        self.register_notes = register_notes
        self.note = note
        self.score = score
        self.times_used = times_used
        self.last_used_at = last_used_at
        self.last_decay_at = last_decay_at
        self.created_at = created_at or utcnow()
        # populated on demand by repo.load_events()
        self.events: list["WordEvent"] = []

    def to_doc(self) -> dict:
        return {
            "user_id": self.user_id,
            "text": self.text,
            "kind": self.kind,
            "meaning": self.meaning,
            "examples": list(self.examples),
            "collocations": list(self.collocations),
            "register_notes": self.register_notes,
            "note": self.note,
            "score": self.score,
            "times_used": self.times_used,
            "last_used_at": self.last_used_at,
            "last_decay_at": self.last_decay_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_doc(cls, doc: dict) -> "Word":
        return cls(
            id=_oid_to_str(doc.get("_id")),
            user_id=doc.get("user_id", DEFAULT_USER_ID),
            text=doc.get("text", ""),
            kind=doc.get("kind", "word"),
            meaning=doc.get("meaning", ""),
            examples=doc.get("examples", []),
            collocations=doc.get("collocations", []),
            register_notes=doc.get("register_notes", ""),
            note=doc.get("note", ""),
            score=doc.get("score", 0.0),
            times_used=doc.get("times_used", 0),
            last_used_at=doc.get("last_used_at"),
            last_decay_at=doc.get("last_decay_at"),
            created_at=doc.get("created_at"),
        )


class User:
    """A Google-authenticated user. The doc's `_id` (hex string) IS the internal `user_id`
    that scopes every other collection. `google_sub` is the stable subject id from Google."""

    def __init__(
        self,
        google_sub: str,
        email: str,
        name: str = "",
        picture: str = "",
        adopted_default: bool = False,
        id: str | None = None,
        created_at: datetime | None = None,
    ):
        self.id = id
        self.google_sub = google_sub
        self.email = email
        self.name = name
        self.picture = picture
        # True once this user has adopted the legacy "default" data (one-time, first user only).
        self.adopted_default = adopted_default
        self.created_at = created_at or utcnow()

    def to_doc(self) -> dict:
        return {
            "google_sub": self.google_sub,
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "adopted_default": self.adopted_default,
            "created_at": self.created_at,
        }

    @classmethod
    def from_doc(cls, doc: dict) -> "User":
        return cls(
            id=_oid_to_str(doc.get("_id")),
            google_sub=doc.get("google_sub", ""),
            email=doc.get("email", ""),
            name=doc.get("name", ""),
            picture=doc.get("picture", ""),
            adopted_default=doc.get("adopted_default", False),
            created_at=doc.get("created_at"),
        )


class WordEvent:
    def __init__(
        self,
        word_id: str,
        event_type: str,
        delta: float,
        score_after: float,
        conversation_id: str | None = None,
        message_id: str | None = None,
        judge_notes: str = "",
        user_id: str = DEFAULT_USER_ID,
        id: str | None = None,
        created_at: datetime | None = None,
    ):
        self.id = id
        self.user_id = user_id
        self.word_id = word_id
        self.conversation_id = conversation_id
        self.message_id = message_id
        self.event_type = event_type
        self.delta = delta
        self.score_after = score_after
        self.judge_notes = judge_notes
        self.created_at = created_at or utcnow()

    def to_doc(self) -> dict:
        return {
            "user_id": self.user_id,
            "word_id": self.word_id,
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "event_type": self.event_type,
            "delta": self.delta,
            "score_after": self.score_after,
            "judge_notes": self.judge_notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_doc(cls, doc: dict) -> "WordEvent":
        return cls(
            id=_oid_to_str(doc.get("_id")),
            user_id=doc.get("user_id", DEFAULT_USER_ID),
            word_id=str(doc.get("word_id")),
            conversation_id=_oid_to_str(doc.get("conversation_id")),
            message_id=_oid_to_str(doc.get("message_id")),
            event_type=doc.get("event_type", ""),
            delta=doc.get("delta", 0.0),
            score_after=doc.get("score_after", 0.0),
            judge_notes=doc.get("judge_notes", ""),
            created_at=doc.get("created_at"),
        )
