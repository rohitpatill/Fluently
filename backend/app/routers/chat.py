from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Conversation, Message
from ..schemas import ChatRequest, ChatResponse, MessageOut, WordEventOut
from ..services import chat_service, judge_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/{conversation_id}", response_model=ChatResponse)
def send_message(conversation_id: int, payload: ChatRequest, db: Session = Depends(get_db)):
    """One chat turn:
    1. store user message
    2. assemble dynamic system prompt (persona + identity + memory + targets + category + time)
    3. run the tool-calling agent loop (memory tools + conversation search)
    4. store assistant message with full tool-call transparency
    5. judge the user message against ALL tracked words and apply scoring events
    """
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    if not payload.content.strip():
        raise HTTPException(400, "Message is empty")

    assistant_msg = chat_service.run_agent_turn(
        db, conv, payload.content.strip(), provider=payload.provider, model_name=payload.model
    )

    user_msg = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id, Message.role == "user")
        .order_by(Message.seq.desc())
        .first()
    )

    events = judge_service.judge_user_message(db, conversation_id, user_msg.id) if user_msg else []

    return ChatResponse(
        user_message=MessageOut.model_validate(user_msg),
        assistant_message=MessageOut.model_validate(assistant_msg),
        scoring_events=[WordEventOut.model_validate(e) for e in events],
    )
