"""Assembles the dynamic system prompt for every chat LLM call."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .. import repo
from ..config import settings
from ..models import Conversation
from ..prompts import CHAT_SYSTEM_TEMPLATE, PERSONA_FALLBACK
from . import memory_service


def _persona_block(user_id: str) -> tuple[str, str]:
    raw = memory_service.read_file("persona", user_id).strip()
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


def _part_of_day(hour: int) -> str:
    if hour < 5:
        return "late night"
    if hour < 12:
        return "morning"
    if hour < 14:
        return "midday"
    if hour < 18:
        return "afternoon"
    if hour < 22:
        return "evening"
    return "late night"


def _time_block() -> str:
    """A compact but complete temporal map, in the user's timezone. The persona has NO
    other clock — it must resolve every 'tomorrow' / 'next Friday' from here, and write
    ABSOLUTE dates into memory. Kept dense on purpose: the model reads it every turn."""
    try:
        now = datetime.now(ZoneInfo(settings.user_timezone))
    except Exception:
        now = datetime.now().astimezone()

    def d(dt) -> str:  # "Sat 2026-07-11"
        return dt.strftime("%a %Y-%m-%d")

    today = now.date()
    monday = today - timedelta(days=today.weekday())  # this week's Monday
    week = [monday + timedelta(days=i) for i in range(7)]
    week_str = ", ".join(f"{dt.strftime('%a')} {dt.strftime('%Y-%m-%d')}" for dt in week)
    last_week = (monday - timedelta(days=7), monday - timedelta(days=1))
    next_week = (monday + timedelta(days=7), monday + timedelta(days=13))
    next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)

    return (
        f"NOW: {now.strftime('%A, %Y-%m-%d, %I:%M %p')} ({_part_of_day(now.hour)}) "
        f"— user timezone {settings.user_timezone}.\n"
        f"Yesterday: {d(today - timedelta(days=1))} | Tomorrow: {d(today + timedelta(days=1))} "
        f"| Day after: {d(today + timedelta(days=2))}\n"
        f"This week (Mon-Sun): {week_str}\n"
        f"Last week: {d(last_week[0])} to {d(last_week[1])} | "
        f"Next week: {d(next_week[0])} to {d(next_week[1])}\n"
        f"This month: {now.strftime('%B %Y')} | Next month: {next_month.strftime('%B %Y')}"
    )


def _target_words_block(conversation: Conversation) -> str:
    if not conversation.target_word_ids:
        return "(no target words yet — the user hasn't added vocabulary, just have a great conversation)"
    words = repo.get_words_by_ids(conversation.target_word_ids, conversation.user_id)
    lines = []
    for w in words:
        lines.append(
            f'- [id={w.id}] "{w.text}" ({w.kind}, proficiency {w.score:.0f}/100): {w.meaning or "no description yet"}'
            + (f" | register: {w.register_notes}" if w.register_notes else "")
            + (f" | user's own memory hook: \"{w.note}\"" if w.note else "")
        )
    return "\n".join(lines)


def build_system_prompt(conversation: Conversation) -> str:
    persona_block, persona_name = _persona_block(conversation.user_id)

    identity = memory_service.read_file("identity", conversation.user_id).strip() or "(nothing recorded yet)"
    memory = memory_service.read_file("memory", conversation.user_id).strip() or "(nothing recorded yet)"

    category_block = (
        f"This conversation's chosen topic/category: {conversation.category}. Steer the talk around it naturally."
        if conversation.category
        else "No specific topic chosen — free conversation."
    )

    return CHAT_SYSTEM_TEMPLATE.format(
        persona_block=persona_block,
        identity_block=identity,
        memory_block=memory,
        target_words_block=_target_words_block(conversation),
        time_block=_time_block(),
        category_block=category_block,
        persona_name=persona_name,
    )
