"""Topic suggestions for a new chat + word enrichment on add."""

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from .. import repo
from ..models import Word
from ..mongo import DEFAULT_USER_ID
from ..prompts import ONBOARDING_STRUCTURE_SYSTEM, TOPICS_SYSTEM, WORD_ENRICH_SYSTEM
from .llm_service import get_utility_model
from .model_service import resolve_for_user
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


def suggest_topics(target_words: list[Word], user_id: str = DEFAULT_USER_ID,
                   persona_id: str | None = None) -> list[Topic]:
    identity = memory_service.read_file("identity", user_id)[:3000]
    memory = memory_service.read_file("memory", user_id)[:3000]
    # Only surface conversations held with the ACTIVE persona (keeps each companion's context
    # separate — a mentor shouldn't reference chats you had with a best-friend persona).
    recent = repo.recent_conversations(user_id, limit=8, persona_id=persona_id)
    recent_titles = "\n".join(f"- {c.title}" for c in recent) or "(no previous conversations)"
    words = ", ".join(w.text for w in target_words) or "(none)"

    prompt = (
        f"USER IDENTITY NOTES:\n{identity}\n\nMEMORIES:\n{memory}\n\n"
        f"RECENT CONVERSATIONS:\n{recent_titles}\n\nCURRENT TARGET WORDS: {words}"
    )
    try:
        r = resolve_for_user(user_id)
        llm = get_utility_model(r.provider, r.model, api_key=r.api_key, temperature=0.8).with_structured_output(TopicList)
        return llm.invoke([SystemMessage(content=TOPICS_SYSTEM), HumanMessage(content=prompt)]).topics
    except Exception:
        return []


class OnboardingFacts(BaseModel):
    identity: list[str] = Field(
        default_factory=list,
        description="Timeless facts about who the user is (job, background, personality, tastes). No dates.",
    )
    memory: list[str] = Field(
        default_factory=list,
        description="The user's life: people they mention, relationships, events (with absolute dates), plans.",
    )
    persona: list[str] = Field(
        default_factory=list,
        description="First-person things the persona should remember about its relationship with the user.",
    )


def structure_onboarding_info(raw_about: str, persona_name: str, today: str,
                              user_id: str = DEFAULT_USER_ID) -> OnboardingFacts | None:
    """Turn the free-text onboarding 'about you' dump into clean, categorized memory lines
    spread across identity/memory/persona. Returns None on failure (caller falls back to raw)."""
    if not raw_about.strip():
        return OnboardingFacts()
    prompt = (
        f"Persona name: {persona_name}. Today's date: {today}.\n\n"
        f"The user wrote this about themselves during onboarding:\n\"\"\"\n{raw_about}\n\"\"\""
    )
    try:
        r = resolve_for_user(user_id)
        llm = get_utility_model(r.provider, r.model, api_key=r.api_key, temperature=0).with_structured_output(OnboardingFacts)
        return llm.invoke(
            [SystemMessage(content=ONBOARDING_STRUCTURE_SYSTEM), HumanMessage(content=prompt)]
        )
    except Exception:
        return None


def enrich_word(text: str, kind: str, user_id: str = DEFAULT_USER_ID) -> WordEnrichment | None:
    try:
        r = resolve_for_user(user_id)
        llm = get_utility_model(r.provider, r.model, api_key=r.api_key, temperature=0).with_structured_output(WordEnrichment)
        return llm.invoke(
            [SystemMessage(content=WORD_ENRICH_SYSTEM), HumanMessage(content=f"{kind}: {text}")]
        )
    except Exception:
        return None
