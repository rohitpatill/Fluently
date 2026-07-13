from fastapi import APIRouter, Depends, HTTPException

from .. import repo
from ..deps import get_current_user, require_model_configured
from ..models import Conversation
from ..schemas import (
    ConversationCreate,
    ConversationOut,
    MessageOut,
    NewConversationResponse,
    SearchHit,
    SearchRequest,
    TopicSuggestion,
    WordEventOut,
)
from ..services import chat_service, memory_service, scoring_service, search_service, topic_service

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
def list_conversations(user_id: str = Depends(get_current_user)):
    # Threads are persona-scoped: only show conversations of the ACTIVE persona.
    persona_id = memory_service.active_persona_id(user_id)
    return repo.list_conversations(user_id, persona_id=persona_id)


@router.post("", response_model=NewConversationResponse)
def create_conversation(
    payload: ConversationCreate, user_id: str = Depends(require_model_configured)
):
    """Start a new chat: pick target words (spaced repetition), optionally suggest topics.
    The first LLM call of a new chat is the topic-suggestion call, as designed."""
    persona_id = memory_service.active_persona_id(user_id)
    targets = scoring_service.pick_target_words(user_id=user_id)
    conv = Conversation(
        category=payload.category,
        title=payload.title or "New conversation",
        target_word_ids=[w.id for w in targets],
        user_id=user_id,
        persona_id=persona_id,
    )
    repo.insert_conversation(conv)

    topics: list[TopicSuggestion] = []
    if payload.suggest_topics and not payload.category:
        topics = [
            TopicSuggestion(title=t.title, description=t.description, category=t.category)
            for t in topic_service.suggest_topics(targets, user_id, persona_id=persona_id)
        ]
    return NewConversationResponse(conversation=conv, topics=topics)


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: str, user_id: str = Depends(get_current_user)):
    conv = repo.get_conversation(conversation_id, user_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(conversation_id: str, user_id: str = Depends(get_current_user)):
    conv = repo.get_conversation(conversation_id, user_id, with_messages=True)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    # Attach each user message's scoring events (with resolved word text) so the
    # frontend can render persistent scoring chips that survive a page refresh.
    events = repo.events_for_conversation(conversation_id, user_id)
    word_text = {w.id: w.text for w in repo.list_words(user_id)}
    by_message: dict[str, list[WordEventOut]] = {}
    for e in events:
        by_message.setdefault(e.message_id, []).append(
            WordEventOut.model_validate(e).model_copy(update={"word_text": word_text.get(e.word_id)})
        )

    out: list[MessageOut] = []
    for m in conv.messages:
        mo = MessageOut.model_validate(m)
        mo.word_events = by_message.get(m.id, [])
        out.append(mo)
    return out


@router.patch("/{conversation_id}/category", response_model=ConversationOut)
def set_category(
    conversation_id: str, category: str, user_id: str = Depends(get_current_user)
):
    """Set the topic after the user picks one of the suggestions."""
    conv = repo.get_conversation(conversation_id, user_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    conv.category = category
    repo.save_conversation(conv)
    return conv


@router.post("/{conversation_id}/opener", response_model=MessageOut)
def generate_opener(conversation_id: str, user_id: str = Depends(require_model_configured)):
    """Persona opens the conversation itself (time-aware, memory-aware greeting)."""
    conv = repo.get_conversation(conversation_id, user_id, with_messages=True)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    if conv.messages:
        raise HTTPException(400, "Conversation already has messages")
    return chat_service.generate_opener(conv)


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str, user_id: str = Depends(get_current_user)):
    conv = repo.get_conversation(conversation_id, user_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    repo.delete_conversation(conversation_id, user_id)
    return {"ok": True}


@router.post("/search", response_model=list[SearchHit])
def search_conversations(
    payload: SearchRequest, user_id: str = Depends(get_current_user)
):
    """Same search the agent tool uses, exposed for the UI."""
    hits = search_service.search(
        query=payload.query,
        mode=payload.mode,
        conversation_id=payload.conversation_id,
        n_before=payload.n_before,
        n_after=payload.n_after,
        full_conversation=payload.full_conversation,
        max_results=payload.max_results,
        user_id=user_id,
        persona_id=memory_service.active_persona_id(user_id),
    )
    return [
        SearchHit(
            conversation_id=h["conversation_id"],
            conversation_title=h["conversation_title"],
            message_id=h["message_id"],
            score=h["score"],
            context=[MessageOut.model_validate(m) for m in h["context"]],
        )
        for h in hits
    ]
