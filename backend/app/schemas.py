from datetime import datetime

from pydantic import BaseModel, Field


# ---------- Words ----------
class WordCreate(BaseModel):
    text: str
    kind: str = Field(default="word", pattern="^(word|phrase)$")


class WordOut(BaseModel):
    id: int
    text: str
    kind: str
    meaning: str
    examples: list[str]
    collocations: list[str]
    register_notes: str
    score: float
    times_used: int
    last_used_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WordScoreAdjust(BaseModel):
    delta: float  # e.g. -20 for "I want to practice this more"
    reason: str = ""


class WordEventOut(BaseModel):
    id: int
    word_id: int
    conversation_id: int | None
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
    id: int
    title: str
    category: str | None
    target_word_ids: list[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ToolCallOut(BaseModel):
    name: str
    args: dict
    output: str


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    seq: int
    role: str
    content: str
    tool_calls: list
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
    conversation_id: int | None = None  # limit to one conversation
    n_before: int = 3
    n_after: int = 3
    full_conversation: bool = False
    max_results: int = 5


class SearchHit(BaseModel):
    conversation_id: int
    conversation_title: str
    message_id: int
    score: float
    context: list[MessageOut]  # window of messages around the hit
