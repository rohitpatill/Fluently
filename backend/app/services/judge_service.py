"""Judge LLM: after each user message, detect target-word usage and apply scoring events."""

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..models import Conversation, Message, Word, WordEvent
from ..prompts import JUDGE_SYSTEM
from .llm_service import get_judge_model
from .scoring_service import apply_event

CONTEXT_MESSAGES = 6


class UsageJudgement(BaseModel):
    word: str = Field(description="The target word/phrase exactly as listed")
    classification: str = Field(
        description="One of: perfect_unprompted | perfect_prompted | awkward | wrong"
    )
    suggestion: str = Field(default="", description="For awkward/wrong: one short better-usage suggestion")


class JudgeResult(BaseModel):
    judgements: list[UsageJudgement] = Field(default_factory=list)


def judge_user_message(db: Session, conversation_id: int, user_message_id: int) -> list[WordEvent]:
    conversation = db.get(Conversation, conversation_id)
    user_msg = db.get(Message, user_message_id)
    if conversation is None or user_msg is None:
        return []

    # judge against ALL tracked words, not just conversation targets — the user may
    # spontaneously use any practiced word, and it must count the same everywhere
    words = db.query(Word).all()
    if not words:
        return []
    word_map = {w.text.lower(): w for w in words}

    prior = [m for m in conversation.messages if m.seq < user_msg.seq][-CONTEXT_MESSAGES:]
    context = "\n".join(f"{m.role}: {m.content}" for m in prior) or "(conversation start)"
    target_list = "\n".join(f'- "{w.text}" ({w.kind})' for w in words)

    prompt = (
        f"TARGET WORDS/PHRASES:\n{target_list}\n\n"
        f"RECENT CONTEXT:\n{context}\n\n"
        f"USER'S MESSAGE TO JUDGE:\n{user_msg.content}"
    )

    try:
        judge = get_judge_model().with_structured_output(JudgeResult)
        result: JudgeResult = judge.invoke([SystemMessage(content=JUDGE_SYSTEM), HumanMessage(content=prompt)])
    except Exception:
        return []  # scoring must never break the chat flow

    events: list[WordEvent] = []
    valid = {"perfect_unprompted", "perfect_prompted", "awkward", "wrong"}
    for j in result.judgements:
        word = word_map.get(j.word.lower().strip())
        if word is None or j.classification not in valid:
            continue
        events.append(
            apply_event(
                db,
                word,
                j.classification,
                judge_notes=j.suggestion,
                conversation_id=conversation_id,
                message_id=user_message_id,
            )
        )
    return events
