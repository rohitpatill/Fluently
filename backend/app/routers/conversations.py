from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Conversation, Message
from ..schemas import (
    ConversationCreate,
    ConversationOut,
    MessageOut,
    NewConversationResponse,
    SearchHit,
    SearchRequest,
    TopicSuggestion,
)
from ..services import chat_service, scoring_service, search_service, topic_service

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db)):
    return db.query(Conversation).order_by(Conversation.updated_at.desc()).all()


@router.post("", response_model=NewConversationResponse)
def create_conversation(payload: ConversationCreate, db: Session = Depends(get_db)):
    """Start a new chat: pick target words (spaced repetition), optionally suggest topics.
    The first LLM call of a new chat is the topic-suggestion call, as designed."""
    targets = scoring_service.pick_target_words(db)
    conv = Conversation(
        category=payload.category,
        title=payload.title or "New conversation",
        target_word_ids=[w.id for w in targets],
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    topics: list[TopicSuggestion] = []
    if payload.suggest_topics and not payload.category:
        topics = [
            TopicSuggestion(title=t.title, description=t.description, category=t.category)
            for t in topic_service.suggest_topics(db, targets)
        ]
    return NewConversationResponse(conversation=conv, topics=topics)


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv.messages


@router.patch("/{conversation_id}/category", response_model=ConversationOut)
def set_category(conversation_id: int, category: str, db: Session = Depends(get_db)):
    """Set the topic after the user picks one of the suggestions."""
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    conv.category = category
    db.commit()
    db.refresh(conv)
    return conv


@router.post("/{conversation_id}/opener", response_model=MessageOut)
def generate_opener(conversation_id: int, db: Session = Depends(get_db)):
    """Persona opens the conversation itself (time-aware, memory-aware greeting)."""
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    if conv.messages:
        raise HTTPException(400, "Conversation already has messages")
    return chat_service.generate_opener(db, conv)


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    db.delete(conv)
    db.commit()
    return {"ok": True}


@router.post("/search", response_model=list[SearchHit])
def search_conversations(payload: SearchRequest, db: Session = Depends(get_db)):
    """Same search the agent tool uses, exposed for the UI."""
    hits = search_service.search(
        db,
        query=payload.query,
        mode=payload.mode,
        conversation_id=payload.conversation_id,
        n_before=payload.n_before,
        n_after=payload.n_after,
        full_conversation=payload.full_conversation,
        max_results=payload.max_results,
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
