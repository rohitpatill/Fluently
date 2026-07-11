"""Data management: HARD deletes. Everything here is irreversible by design —
the frontend is responsible for warnings/confirmation before calling these."""

from fastapi import APIRouter
from pydantic import BaseModel

from .. import repo
from ..mongo import DEFAULT_USER_ID
from ..services import memory_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


class PurgeAllRequest(BaseModel):
    keep_words: bool = False


@router.delete("/conversations")
def purge_conversations():
    """Delete ALL conversations and messages. Words, scores and memories are untouched."""
    n_conv, n_msg = repo.purge_conversations(DEFAULT_USER_ID)
    return {"deleted_conversations": n_conv, "deleted_messages": n_msg}


@router.delete("/memories")
def purge_memories():
    """Reset identity.md and memory.md to pristine (everything known about the user).
    Persona, conversations and words are untouched."""
    memory_service.reset_file("identity", DEFAULT_USER_ID)
    memory_service.reset_file("memory", DEFAULT_USER_ID)
    return {"reset_files": ["identity", "memory"]}


@router.post("/purge-all")
def purge_all(payload: PurgeAllRequest):
    """The nuclear option. Deletes conversations, messages, and all three memory files
    (including the persona — the app restarts at onboarding). With keep_words=True the
    tracked words, their scores and score history survive; otherwise those are deleted too."""
    n_conv, n_msg = repo.purge_conversations(DEFAULT_USER_ID)
    n_words = 0
    if not payload.keep_words:
        n_words = repo.purge_words(DEFAULT_USER_ID)
    for f in ("identity", "memory", "persona"):
        memory_service.reset_file(f, DEFAULT_USER_ID)
    return {
        "deleted_conversations": n_conv,
        "deleted_messages": n_msg,
        "deleted_words": n_words,
        "kept_words": payload.keep_words,
        "reset_files": ["identity", "memory", "persona"],
    }
