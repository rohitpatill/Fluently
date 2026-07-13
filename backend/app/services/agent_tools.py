"""LangChain tools available to the chat agent.

Built per-request with a closure over the DB session and current conversation id.
Tool outputs are returned to the model as ToolMessages and stored on the assistant
message record (transparency), but are NOT injected as visible chat messages.
"""

from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from .. import repo
from ..mongo import DEFAULT_USER_ID
from . import memory_service, scoring_service, search_service


class MemoryUpdateArgs(BaseModel):
    file: Literal["identity", "memory", "persona"] = Field(
        description="Which memory record to write to — exactly one of "
        "'identity' | 'memory' | 'persona': "
        "'identity' = timeless facts about WHO THE USER IS (name, background, job/studies, goals, "
        "tastes, personality, how they talk, recurring English mistakes) — no dates here; "
        "'memory' = the user's LIFE (events, people and who they are, relationships, plans, "
        "deadlines) — include an absolute date for anything time-bound; "
        "'persona' = what YOU remember about your relationship with the user (shared jokes, "
        "promises, moments), first-person from your side."
    )
    action: Literal["append", "edit"] = Field(
        description="'append' to add a new memory, or 'edit' to change/remove existing text."
    )
    text: str = Field(
        default="",
        description="For action='append' ONLY: the memory to store, as one clear specific "
        "sentence. Write it exactly as it should be saved — nothing is added for you. If it is a "
        "time-bound fact (event/deadline/birthday/trip), include the ABSOLUTE date resolved from "
        "the TIME block (e.g. 'Trip to Goa on 2026-07-17'), never 'tomorrow'/'next week'.",
    )
    old_string: str = Field(
        default="",
        description="For action='edit' ONLY: the exact existing text to replace. Copy it verbatim "
        "from the memory file shown in your context (enough to be unique).",
    )
    new_string: str = Field(
        default="",
        description="For action='edit' ONLY: the replacement text. Leave EMPTY to delete the "
        "matched text entirely.",
    )
    replace_all: bool = Field(
        default=False,
        description="For action='edit': replace every occurrence of old_string instead of just the first.",
    )


class SearchArgs(BaseModel):
    query: str = Field(description="What to search for in past conversations (keywords or a regex)")
    mode: Literal["bm25", "regex"] = Field(default="bm25", description="'bm25' for keyword relevance ranking, 'regex' for exact/pattern match")
    n_before: int = Field(default=3, description="Messages of context to include before each match")
    n_after: int = Field(default=3, description="Messages of context to include after each match")
    full_conversation: bool = Field(default=False, description="Return the entire conversation containing each match instead of a window")
    max_results: int = Field(default=3, description="How many matches (each with its context window) to return")


class AdjustScoreArgs(BaseModel):
    word_id: str = Field(description="The word's id (shown next to each target word in your context)")
    delta: float = Field(description="Score change, e.g. +3 or -5. Positive for notably good use, negative to flag for more practice")
    reason: str = Field(description="One short sentence: why you adjusted it")


def build_tools(current_conversation_id: str | None = None, user_id: str = DEFAULT_USER_ID,
                persona_id: str | None = None):
    @tool(args_schema=MemoryUpdateArgs)
    def memory_update(
        file: str,
        action: str,
        text: str = "",
        old_string: str = "",
        new_string: str = "",
        replace_all: bool = False,
    ) -> str:
        """Save or change what you remember about the user and your relationship. action='append'
        adds a new memory (pass `text`, written exactly as it should be stored); action='edit'
        replaces existing text (pass `old_string` + `new_string`; empty `new_string` deletes it).
        The whole file is already in your context, so to edit or delete just quote the text you see.
        Prefer editing over appending a near-duplicate when a fact changes. Store absolute dates
        only for time-bound facts; never write a date on timeless facts like preferences or names."""
        file = memory_service.normalize_file(file)  # tolerate 'identity.md' → 'identity'
        # Safety net: the enum should prevent it, but if a fused value like
        # "append, new_string" ever slips through, keep only the leading verb.
        act = (action or "").strip().lower().split(",")[0].split()[0] if action else ""
        if act == "append":
            if not text.strip():
                return "append requires non-empty `text`."
            memory_service.append(file, text, user_id)
            return f"Saved a new memory to {file}."
        if act == "edit":
            try:
                memory_service.edit(file, old_string, new_string, replace_all, user_id)
            except KeyError:
                return (
                    f"Could not find that text in {file}. Copy `old_string` exactly as it "
                    f"appears in your context."
                )
            except ValueError as e:
                return str(e)
            return (
                f"Deleted the matched text from {file}."
                if not new_string.strip()
                else f"{file} updated."
            )
        return "Unknown action. Use 'append' or 'edit'."

    @tool(args_schema=SearchArgs)
    def search_conversations(
        query: str,
        mode: str = "bm25",
        n_before: int = 3,
        n_after: int = 3,
        full_conversation: bool = False,
        max_results: int = 3,
    ) -> str:
        """Search all PAST conversations you had with the user for relevant context. Use when the user references something discussed before, or when past context would improve your reply. Returns matched messages with surrounding context. (Only searches conversations you had with the user under your current identity.)"""
        hits = search_service.search(
            query=query,
            mode=mode,
            n_before=n_before,
            n_after=n_after,
            full_conversation=full_conversation,
            max_results=max_results,
            exclude_conversation_id=current_conversation_id,
            user_id=user_id,
            persona_id=persona_id,
        )
        return search_service.format_hits_for_llm(hits)

    @tool(args_schema=AdjustScoreArgs)
    def adjust_word_score(word_id: str, delta: float, reason: str) -> str:
        """Adjust a tracked word's proficiency score (0-100). Use sparingly — automatic judging already scores normal usage. Reach for this only for exceptional cases: the user explicitly asks to practice a word more (negative delta), or demonstrates mastery the automatic judge can't see."""
        word = repo.get_word(word_id, user_id)
        if word is None:
            return f"No word with id {word_id}."
        event = scoring_service.apply_event(
            word, "manual", judge_notes=f"[agent] {reason}",
            conversation_id=current_conversation_id, manual_delta=delta,
        )
        return f'"{word.text}" score changed by {event.delta:+g} to {event.score_after:g}/100.'

    return [memory_update, search_conversations, adjust_word_score]
