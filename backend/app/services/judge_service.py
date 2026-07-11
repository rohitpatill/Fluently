"""Judge LLM: after each user message, detect target-word usage and apply scoring events."""

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from .. import repo
from ..models import WordEvent
from ..mongo import DEFAULT_USER_ID
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


def judge_user_message(conversation_id: str, user_message_id: str,
                        user_id: str = DEFAULT_USER_ID) -> list[WordEvent]:
    conversation = repo.get_conversation(conversation_id, user_id, with_messages=True)
    user_msg = repo.get_message(user_message_id, user_id)
    if conversation is None or user_msg is None:
        return []

    # judge against ALL tracked words, not just conversation targets — the user may
    # spontaneously use any practiced word, and it must count the same everywhere
    words = repo.list_words(user_id)
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
                word,
                j.classification,
                judge_notes=j.suggestion,
                conversation_id=conversation_id,
                message_id=user_message_id,
            )
        )
    return events
