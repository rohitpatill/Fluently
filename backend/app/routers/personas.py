"""Multi-persona management.

A user may keep several companion personas and switch the active one. `identity` and `memory`
(the human's facts + life) are SHARED across all personas; only the `persona` file (who the
companion is + its own relationship memories) and the chat threads are persona-scoped.

Endpoints:
  GET    /api/personas               → list all personas (active flagged, with thread counts)
  POST   /api/personas               → create a new persona (does NOT switch to it)
  PUT    /api/personas/{id}          → edit a persona's identity fields (name/relation/...)
  PUT    /api/personas/{id}/avatar   → set/clear a persona's public avatar URL
  POST   /api/personas/{id}/activate → switch the active persona
  DELETE /api/personas/{id}          → delete a persona + its threads (keep >= 1)
"""

from fastapi import APIRouter, Depends, HTTPException

from .. import repo
from ..deps import get_current_user
from ..models import Persona
from ..schemas import (
    CatalogCategory,
    PersonaAvatarUpdate,
    PersonaCreate,
    PersonaForm,
    PersonaOut,
)
from ..services import memory_service, persona_catalog

router = APIRouter(prefix="/api/personas", tags=["personas"])


def _to_out(p: Persona, active_id: str, conv_count: int) -> PersonaOut:
    fields = memory_service.parse_persona_fields(p.content)
    return PersonaOut(
        id=p.id,
        avatar_url=p.avatar_url,
        is_active=(p.id == active_id),
        conversation_count=conv_count,
        created_at=p.created_at,
        **fields,
    )


@router.get("", response_model=list[PersonaOut])
def list_personas(user_id: str = Depends(get_current_user)):
    active_id = memory_service.active_persona_id(user_id)  # also self-heals legacy users
    personas = repo.list_personas(user_id)
    counts = {
        p.id: len(repo.list_conversations(user_id, persona_id=p.id)) for p in personas
    }
    return [_to_out(p, active_id, counts.get(p.id, 0)) for p in personas]


@router.get("/catalog", response_model=list[CatalogCategory])
def list_catalog(user_id: str = Depends(get_current_user)):
    """The curated public-persona catalog (Discover), grouped by category. Read-only —
    choosing one copies it into the user's personas via POST /catalog/{catalog_id}/use."""
    return persona_catalog.categories()


@router.post("/catalog/{catalog_id}/use", response_model=PersonaOut)
def use_catalog_persona(catalog_id: str, user_id: str = Depends(get_current_user)):
    """Copy a catalog persona into the user's own personas (fully editable afterwards; the
    catalog entry is never modified). Does NOT switch the active persona — the frontend
    closes Discover and shows it in 'Your personas'."""
    entry = persona_catalog.get_entry(catalog_id)
    if not entry:
        raise HTTPException(404, "Unknown catalog persona")
    memory_service.ensure_files(user_id)
    form = {
        "name": entry.get("name", ""),
        "relation": entry.get("relation", ""),
        "gender": entry.get("gender", ""),
        # the catalog's hand-picked voice (falls back to a gender default in build_persona_content)
        "voice": entry.get("voice", ""),
        # the catalog description guides how the companion talks — seed it as personality
        "personality": entry.get("description", ""),
        "speaking_style": entry.get("speaking_style", ""),
    }
    content = memory_service.build_persona_content(form)
    persona = repo.insert_persona(
        Persona(user_id=user_id, content=content, avatar_url=entry.get("avatar_url", "").strip())
    )
    active_id = memory_service.active_persona_id(user_id)
    return _to_out(persona, active_id, 0)


@router.post("", response_model=PersonaOut)
def create_persona(payload: PersonaCreate, user_id: str = Depends(get_current_user)):
    """Create a new companion from the persona form. Fresh persona → no relationship memories
    yet. Does NOT switch the active persona (the frontend decides whether to activate)."""
    memory_service.ensure_files(user_id)
    content = memory_service.build_persona_content(payload.model_dump())
    persona = repo.insert_persona(
        Persona(user_id=user_id, content=content, avatar_url=payload.avatar_url.strip())
    )
    active_id = memory_service.active_persona_id(user_id)
    return _to_out(persona, active_id, 0)


@router.put("/{persona_id}", response_model=PersonaOut)
def edit_persona(persona_id: str, payload: PersonaForm, user_id: str = Depends(get_current_user)):
    """Edit a persona's identity fields, preserving its relationship memories + avatar."""
    persona = repo.get_persona(persona_id, user_id)
    if not persona:
        raise HTTPException(404, "Persona not found")
    # Update the avatar via a targeted field write BEFORE rewriting the content — a full-doc
    # save() here would clobber the content that set_persona is about to change.
    if payload.avatar_url.strip() != persona.avatar_url:
        repo.set_persona_avatar(persona_id, payload.avatar_url.strip(), user_id)
    memory_service.set_persona(payload.model_dump(), user_id, persona_id=persona_id)
    persona = repo.get_persona(persona_id, user_id)
    active_id = memory_service.active_persona_id(user_id)
    conv_count = len(repo.list_conversations(user_id, persona_id=persona_id))
    return _to_out(persona, active_id, conv_count)


@router.put("/{persona_id}/avatar", response_model=PersonaOut)
def set_avatar(persona_id: str, payload: PersonaAvatarUpdate, user_id: str = Depends(get_current_user)):
    persona = repo.get_persona(persona_id, user_id)
    if not persona:
        raise HTTPException(404, "Persona not found")
    repo.set_persona_avatar(persona_id, payload.avatar_url.strip(), user_id)
    persona = repo.get_persona(persona_id, user_id)
    active_id = memory_service.active_persona_id(user_id)
    conv_count = len(repo.list_conversations(user_id, persona_id=persona_id))
    return _to_out(persona, active_id, conv_count)


@router.post("/{persona_id}/activate", response_model=PersonaOut)
def activate_persona(persona_id: str, user_id: str = Depends(get_current_user)):
    """Switch the active companion. Subsequent chats/threads/search scope to this persona."""
    persona = repo.get_persona(persona_id, user_id)
    if not persona:
        raise HTTPException(404, "Persona not found")
    repo.set_active_persona(user_id, persona_id)
    conv_count = len(repo.list_conversations(user_id, persona_id=persona_id))
    return _to_out(persona, persona_id, conv_count)


@router.delete("/{persona_id}")
def delete_persona(persona_id: str, user_id: str = Depends(get_current_user)):
    """Delete a persona and all of ITS conversations/messages (word scores are kept). Refuses
    to delete the last remaining persona. If the active one is deleted, another becomes active."""
    persona = repo.get_persona(persona_id, user_id)
    if not persona:
        raise HTTPException(404, "Persona not found")
    if repo.count_personas(user_id) <= 1:
        raise HTTPException(400, "You must keep at least one persona.")

    was_active = memory_service.active_persona_id(user_id) == persona_id
    n_conv, n_msg = repo.delete_persona(persona_id, user_id)
    if was_active:
        remaining = repo.list_personas(user_id)
        repo.set_active_persona(user_id, remaining[0].id if remaining else None)
    return {"ok": True, "conversations_deleted": n_conv, "messages_deleted": n_msg}
