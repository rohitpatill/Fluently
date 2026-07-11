"""Assembles the dynamic system prompt for every chat LLM call."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import Conversation, Word
from ..prompts import CHAT_SYSTEM_TEMPLATE, PERSONA_FALLBACK
from . import memory_service


def _persona_block() -> tuple[str, str]:
    raw = memory_service.read_file("persona").strip()
    name = "Alex"
    for line in raw.splitlines():
        if line.lower().startswith("name:"):
            name = line.split(":", 1)[1].strip() or name
            break
    if "Name:" not in raw:
        return PERSONA_FALLBACK, name
    return (
        "=== WHO YOU ARE (persona.md — assigned by the user) ===\n" + raw,
        name,
    )


def _time_block() -> str:
    now = datetime.now(timezone.utc).astimezone()
    off = now.strftime("%z")
    return (
        f"Current date/time for the user: {now.strftime('%A, %Y-%m-%d %H:%M')} "
        f"(UTC{off[:3]}:{off[3:]}, timezone: local). Use this to reason about their day."
    )


def _target_words_block(db: Session, conversation: Conversation) -> str:
    if not conversation.target_word_ids:
        return "(no target words yet — the user hasn't added vocabulary, just have a great conversation)"
    words = db.query(Word).filter(Word.id.in_(conversation.target_word_ids)).all()
    lines = []
    for w in words:
        lines.append(
            f'- [id={w.id}] "{w.text}" ({w.kind}, proficiency {w.score:.0f}/100): {w.meaning or "no description yet"}'
            + (f" | register: {w.register_notes}" if w.register_notes else "")
        )
    return "\n".join(lines)


def build_system_prompt(db: Session, conversation: Conversation) -> str:
    persona_block, persona_name = _persona_block()

    identity = memory_service.read_file("identity").strip() or "(nothing recorded yet)"
    memory = memory_service.read_file("memory").strip() or "(nothing recorded yet)"

    category_block = (
        f"This conversation's chosen topic/category: {conversation.category}. Steer the talk around it naturally."
        if conversation.category
        else "No specific topic chosen — free conversation."
    )

    return CHAT_SYSTEM_TEMPLATE.format(
        persona_block=persona_block,
        identity_block=identity,
        memory_block=memory,
        target_words_block=_target_words_block(db, conversation),
        time_block=_time_block(),
        category_block=category_block,
        persona_name=persona_name,
    )
