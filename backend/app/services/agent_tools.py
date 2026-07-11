"""LangChain tools available to the chat agent.

Built per-request with a closure over the DB session and current conversation id.
Tool outputs are returned to the model as ToolMessages and stored on the assistant
message record (transparency), but are NOT injected as visible chat messages.
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..models import Word
from . import memory_service, scoring_service, search_service


class MemoryAppendArgs(BaseModel):
    file: str = Field(description="Which memory file: 'identity' (facts about the user), 'memory' (life events/people), or 'persona' (your own relationship memories)")
    text: str = Field(description="One short factual sentence to remember")


class MemoryUpdateArgs(BaseModel):
    file: str = Field(description="'identity' | 'memory' | 'persona'")
    line_id: str = Field(description="The line id to update, e.g. 'i042'")
    text: str = Field(description="The corrected/updated sentence")


class MemoryDeleteArgs(BaseModel):
    file: str = Field(description="'identity' | 'memory' | 'persona'")
    line_id: str = Field(description="The line id to delete, e.g. 'm007'")


class SearchArgs(BaseModel):
    query: str = Field(description="What to search for in past conversations (keywords or a regex)")
    mode: str = Field(default="bm25", description="'bm25' for keyword relevance ranking, 'regex' for exact/pattern match")
    n_before: int = Field(default=3, description="Messages of context to include before each match")
    n_after: int = Field(default=3, description="Messages of context to include after each match")
    full_conversation: bool = Field(default=False, description="Return the entire conversation containing each match instead of a window")
    max_results: int = Field(default=3, description="How many matches (each with its context window) to return")


class AdjustScoreArgs(BaseModel):
    word_id: int = Field(description="The word's id (shown next to each target word in your context)")
    delta: float = Field(description="Score change, e.g. +3 or -5. Positive for notably good use, negative to flag for more practice")
    reason: str = Field(description="One short sentence: why you adjusted it")


def build_tools(db: Session, current_conversation_id: int | None = None):
    @tool(args_schema=MemoryAppendArgs)
    def memory_append(file: str, text: str) -> str:
        """Save a new durable memory line about the user (identity/memory) or about your relationship with them (persona). Use whenever you learn something worth remembering."""
        entry = memory_service.append(file, text)
        return f"Saved to {file}.md as [{entry['line_id']}]."

    @tool(args_schema=MemoryUpdateArgs)
    def memory_update(file: str, line_id: str, text: str) -> str:
        """Update an existing memory line by its line id (shown in brackets in the file). Use instead of appending a duplicate when a fact changes."""
        try:
            memory_service.update(file, line_id, text)
            return f"Updated [{line_id}] in {file}.md."
        except KeyError as e:
            return str(e)

    @tool(args_schema=MemoryDeleteArgs)
    def memory_delete(file: str, line_id: str) -> str:
        """Delete a memory line by its line id when it is wrong or no longer relevant."""
        try:
            memory_service.delete(file, line_id)
            return f"Deleted [{line_id}] from {file}.md."
        except KeyError as e:
            return str(e)

    @tool(args_schema=SearchArgs)
    def search_conversations(
        query: str,
        mode: str = "bm25",
        n_before: int = 3,
        n_after: int = 3,
        full_conversation: bool = False,
        max_results: int = 3,
    ) -> str:
        """Search all PAST conversations with the user for relevant context. Use when the user references something discussed before, or when past context would improve your reply. Returns matched messages with surrounding context."""
        hits = search_service.search(
            db,
            query=query,
            mode=mode,
            n_before=n_before,
            n_after=n_after,
            full_conversation=full_conversation,
            max_results=max_results,
            exclude_conversation_id=current_conversation_id,
        )
        return search_service.format_hits_for_llm(hits)

    @tool(args_schema=AdjustScoreArgs)
    def adjust_word_score(word_id: int, delta: float, reason: str) -> str:
        """Adjust a tracked word's proficiency score (0-100). Use sparingly — automatic judging already scores normal usage. Reach for this only for exceptional cases: the user explicitly asks to practice a word more (negative delta), or demonstrates mastery the automatic judge can't see."""
        word = db.get(Word, word_id)
        if word is None:
            return f"No word with id {word_id}."
        event = scoring_service.apply_event(
            db, word, "manual", judge_notes=f"[agent] {reason}",
            conversation_id=current_conversation_id, manual_delta=delta,
        )
        return f'"{word.text}" score changed by {event.delta:+g} to {event.score_after:g}/100.'

    return [memory_append, memory_update, memory_delete, search_conversations, adjust_word_score]
