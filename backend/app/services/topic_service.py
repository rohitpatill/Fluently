"""Topic suggestions for a new chat + word enrichment on add."""

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..models import Conversation, Word
from ..prompts import TOPICS_SYSTEM, WORD_ENRICH_SYSTEM
from .llm_service import get_utility_model
from . import memory_service


class Topic(BaseModel):
    title: str
    description: str = Field(description="One inviting sentence about what this chat would be")
    category: str


class TopicList(BaseModel):
    topics: list[Topic]


class WordEnrichment(BaseModel):
    meaning: str
    examples: list[str] = Field(description="2-3 natural conversational example sentences")
    collocations: list[str] = Field(description="3-5 common collocations")
    register_notes: str = Field(description="formal/informal/neutral + context warnings")


def suggest_topics(db: Session, target_words: list[Word]) -> list[Topic]:
    identity = memory_service.read_file("identity")[:3000]
    memory = memory_service.read_file("memory")[:3000]
    recent = (
        db.query(Conversation).order_by(Conversation.updated_at.desc()).limit(8).all()
    )
    recent_titles = "\n".join(f"- {c.title}" for c in recent) or "(no previous conversations)"
    words = ", ".join(w.text for w in target_words) or "(none)"

    prompt = (
        f"USER IDENTITY NOTES:\n{identity}\n\nMEMORIES:\n{memory}\n\n"
        f"RECENT CONVERSATIONS:\n{recent_titles}\n\nCURRENT TARGET WORDS: {words}"
    )
    try:
        llm = get_utility_model(temperature=0.8).with_structured_output(TopicList)
        return llm.invoke([SystemMessage(content=TOPICS_SYSTEM), HumanMessage(content=prompt)]).topics
    except Exception:
        return []


def enrich_word(text: str, kind: str) -> WordEnrichment | None:
    try:
        llm = get_utility_model(temperature=0).with_structured_output(WordEnrichment)
        return llm.invoke(
            [SystemMessage(content=WORD_ENRICH_SYSTEM), HumanMessage(content=f"{kind}: {text}")]
        )
    except Exception:
        return None
