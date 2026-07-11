"""Data management: HARD deletes. Everything here is irreversible by design —
the frontend is responsible for warnings/confirmation before calling these."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Conversation, Message, Word, WordEvent
from ..services import memory_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


class PurgeAllRequest(BaseModel):
    keep_words: bool = False


def _delete_conversations(db: Session) -> tuple[int, int]:
    # detach score events from soon-to-be-deleted rows so score history survives
    db.query(WordEvent).update({WordEvent.conversation_id: None, WordEvent.message_id: None})
    n_messages = db.query(Message).delete()
    n_conversations = db.query(Conversation).delete()
    return n_conversations, n_messages


@router.delete("/conversations")
def purge_conversations(db: Session = Depends(get_db)):
    """Delete ALL conversations and messages. Words, scores and memories are untouched."""
    n_conv, n_msg = _delete_conversations(db)
    db.commit()
    return {"deleted_conversations": n_conv, "deleted_messages": n_msg}


@router.delete("/memories")
def purge_memories():
    """Reset identity.md and memory.md to pristine (everything known about the user).
    Persona, conversations and words are untouched."""
    memory_service.reset_file("identity")
    memory_service.reset_file("memory")
    return {"reset_files": ["identity", "memory"]}


@router.post("/purge-all")
def purge_all(payload: PurgeAllRequest, db: Session = Depends(get_db)):
    """The nuclear option. Deletes conversations, messages, and all three memory files
    (including the persona — the app restarts at onboarding). With keep_words=True the
    tracked words, their scores and score history survive; otherwise those are deleted too."""
    n_conv, n_msg = _delete_conversations(db)
    n_words = 0
    if not payload.keep_words:
        db.query(WordEvent).delete()
        n_words = db.query(Word).delete()
    db.commit()
    for f in ("identity", "memory", "persona"):
        memory_service.reset_file(f)
    return {
        "deleted_conversations": n_conv,
        "deleted_messages": n_msg,
        "deleted_words": n_words,
        "kept_words": payload.keep_words,
        "reset_files": ["identity", "memory", "persona"],
    }
