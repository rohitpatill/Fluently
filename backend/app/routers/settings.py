"""Data management: HARD deletes. Everything here is irreversible by design —
the frontend is responsible for warnings/confirmation before calling these."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import repo
from ..deps import get_current_user
from ..services import memory_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


class PurgeAllRequest(BaseModel):
    keep_words: bool = False


@router.delete("/conversations")
def purge_conversations(user_id: str = Depends(get_current_user)):
    """Delete ALL conversations and messages. Words, scores and memories are untouched."""
    n_conv, n_msg = repo.purge_conversations(user_id)
    return {"deleted_conversations": n_conv, "deleted_messages": n_msg}


@router.delete("/memories")
def purge_memories(user_id: str = Depends(get_current_user)):
    """Reset identity.md and memory.md to pristine (everything known about the user).
    Persona, conversations and words are untouched."""
    memory_service.reset_file("identity", user_id)
    memory_service.reset_file("memory", user_id)
    return {"reset_files": ["identity", "memory"]}


@router.post("/purge-all")
def purge_all(payload: PurgeAllRequest, user_id: str = Depends(get_current_user)):
    """The nuclear option. Deletes conversations, messages, and all three memory files
    (including the persona — the app restarts at onboarding). With keep_words=True the
    tracked words, their scores and score history survive; otherwise those are deleted too.

    keep_words=False is a TRUE full reset: it ALSO clears the user's stored model key + tier,
    so onboarding restarts from the very beginning (persona → about → 'How smart should I be?').
    keep_words=True leaves the model config intact (you keep practicing your words right away)."""
    n_conv, n_msg = repo.purge_conversations(user_id)
    n_words = 0
    cleared_model = False
    if not payload.keep_words:
        n_words = repo.purge_words(user_id)
        repo.clear_user_model(user_id)
        cleared_model = True
    for f in ("identity", "memory", "persona"):
        memory_service.reset_file(f, user_id)
    return {
        "deleted_conversations": n_conv,
        "deleted_messages": n_msg,
        "deleted_words": n_words,
        "kept_words": payload.keep_words,
        "cleared_model": cleared_model,
        "reset_files": ["identity", "memory", "persona"],
    }
