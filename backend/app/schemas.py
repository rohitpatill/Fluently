from datetime import datetime

from pydantic import BaseModel, Field


# ---------- Auth ----------
class MeResponse(BaseModel):
    id: str
    email: str
    name: str = ""
    picture: str = ""
    has_persona: bool = False
    # Bring-your-own-key state — the frontend gates on has_key (must configure a model to use
    # the app) and shows the current tier in Settings. The key itself is NEVER returned.
    has_key: bool = False
    tier: str = ""


# ---------- Model (bring-your-own-key + Swift/Sage tiers) ----------
class ModelTierOut(BaseModel):
    key: str
    name: str
    model: str
    tagline: str
    price: str


class ModelStatusOut(BaseModel):
    has_key: bool
    tier: str = ""


class SetKeyRequest(BaseModel):
    api_key: str
    tier: str


class SetTierRequest(BaseModel):
    tier: str


# ---------- Words ----------
class WordCreate(BaseModel):
    text: str
    kind: str = Field(default="word", pattern="^(word|phrase)$")


class WordOut(BaseModel):
    id: str
    text: str
    kind: str
    meaning: str
    examples: list[str]
    collocations: list[str]
    register_notes: str
    note: str = ""  # user's own personal memory hook
    score: float
    times_used: int
    last_used_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WordScoreAdjust(BaseModel):
    delta: float  # e.g. -20 for "I want to practice this more"
    reason: str = ""


class WordNoteUpdate(BaseModel):
    note: str  # user's personal reminder; empty string clears it


class WordEventOut(BaseModel):
    id: str
    word_id: str
    word_text: str | None = None  # resolved word text (for chips) — not a column
    conversation_id: str | None = None
    message_id: str | None = None
    event_type: str
    delta: float
    score_after: float
    judge_notes: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Conversations / chat ----------
class ConversationCreate(BaseModel):
    category: str | None = None
    title: str | None = None
    suggest_topics: bool = True


class ConversationOut(BaseModel):
    id: str
    title: str
    category: str | None
    target_word_ids: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ToolCallOut(BaseModel):
    name: str
    args: dict
    output: str


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    seq: int
    role: str
    content: str
    tool_calls: list
    # scoring events the judge attached to THIS message (user messages only) — powers
    # persistent scoring chips that survive a page refresh. Populated by GET .../messages.
    word_events: list[WordEventOut] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    content: str
    provider: str | None = None  # override default provider/model per message
    model: str | None = None


class ChatResponse(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut
    scoring_events: list[WordEventOut] = []


class TopicSuggestion(BaseModel):
    title: str
    description: str
    category: str


class NewConversationResponse(BaseModel):
    conversation: ConversationOut
    topics: list[TopicSuggestion] = []
    opener: str | None = None  # optional first message from the persona


# ---------- Memory ----------
class MemoryLineOut(BaseModel):
    text: str


class MemoryFileOut(BaseModel):
    file: str  # identity | memory | persona
    lines: list[MemoryLineOut]
    raw: str


class MemoryAppend(BaseModel):
    text: str


class MemoryEdit(BaseModel):
    old_string: str
    new_string: str = ""  # empty string deletes the matched text
    replace_all: bool = False


class OnboardingInfo(BaseModel):
    name: str
    about: str = ""  # free-text "about you" box; LLM-structured into the three files


class OnboardingResult(BaseModel):
    identity: list[str] = []
    memory: list[str] = []
    persona: list[str] = []


# ---------- Persona (onboarding form) ----------
class PersonaForm(BaseModel):
    name: str
    relation: str  # best friend, mentor, teacher, ...
    gender: str = ""
    personality: str = ""  # free-text custom box
    speaking_style: str = ""


# ---------- Search ----------
class SearchRequest(BaseModel):
    query: str
    mode: str = Field(default="bm25", pattern="^(bm25|regex)$")
    conversation_id: str | None = None  # limit to one conversation
    n_before: int = 3
    n_after: int = 3
    full_conversation: bool = False
    max_results: int = 5


class SearchHit(BaseModel):
    conversation_id: str
    conversation_title: str
    message_id: str
    score: float
    context: list[MessageOut]  # window of messages around the hit
