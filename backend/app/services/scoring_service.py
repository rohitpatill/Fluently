"""Word proficiency scoring.

The single source of truth for how a word's 0-100 score changes, regardless of
which module the usage happened in:

  perfect_unprompted  +5   used it well, system did not set up the context
  perfect_prompted    +3   used it well after the system nudged/used it first
  awkward             +1   right meaning, awkward phrasing or wrong register
  wrong               -2   incorrect usage
  passive             +0.5 clearly understood it in reading, didn't produce it
  decay               -1/week after 14 idle days (applied lazily)
  manual              user-set delta from the dashboard

Daily cap: a word can gain at most +10 per day, so one chat can't max it out.
"""

from datetime import datetime, timedelta, timezone

from .. import repo
from ..config import settings
from ..models import Word, WordEvent, utcnow

EVENT_DELTAS = {
    "perfect_unprompted": lambda: settings.score_perfect_unprompted,
    "perfect_prompted": lambda: settings.score_perfect_prompted,
    "awkward": lambda: settings.score_awkward,
    "wrong": lambda: settings.score_wrong,
    "passive": lambda: settings.score_passive,
}


def _gained_today(word_id: str) -> float:
    day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return repo.gained_today(word_id, day_start, exclude_types=["manual"])


def apply_event(
    word: Word,
    event_type: str,
    judge_notes: str = "",
    conversation_id: str | None = None,
    message_id: str | None = None,
    manual_delta: float | None = None,
) -> WordEvent:
    if event_type == "manual":
        delta = manual_delta or 0.0
    else:
        delta = EVENT_DELTAS[event_type]()
        if delta > 0:
            headroom = settings.score_daily_cap - _gained_today(word.id)
            delta = max(0.0, min(delta, headroom))

    new_score = max(0.0, min(100.0, word.score + delta))
    actual_delta = new_score - word.score
    word.score = new_score
    if event_type in ("perfect_unprompted", "perfect_prompted", "awkward", "wrong"):
        word.times_used += 1
        word.last_used_at = utcnow()
    repo.save_word(word)

    event = WordEvent(
        word_id=word.id,
        conversation_id=conversation_id,
        message_id=message_id,
        event_type=event_type,
        delta=actual_delta,
        score_after=new_score,
        judge_notes=judge_notes,
        user_id=word.user_id,
    )
    return repo.insert_event(event)


def apply_decay(word: Word) -> WordEvent | None:
    """Lazy decay: -1 per full idle week beyond 14 idle days. Called on dashboard reads."""
    now = datetime.now(timezone.utc)
    anchor = word.last_used_at or word.created_at
    if anchor is None:
        return None
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    idle = now - anchor
    if idle < timedelta(days=settings.decay_idle_days) or word.score <= 0:
        return None
    last_decay = word.last_decay_at or anchor
    if last_decay.tzinfo is None:
        last_decay = last_decay.replace(tzinfo=timezone.utc)
    decay_start = max(anchor + timedelta(days=settings.decay_idle_days), last_decay)
    weeks = int((now - decay_start).days // 7)
    if weeks <= 0:
        return None
    delta = -settings.decay_per_week * weeks
    new_score = max(0.0, word.score + delta)
    actual = new_score - word.score
    if actual == 0:
        return None
    word.score = new_score
    word.last_decay_at = now
    repo.save_word(word)
    event = WordEvent(
        word_id=word.id, event_type="decay", delta=actual, score_after=new_score,
        judge_notes=f"{weeks} idle week(s) beyond {settings.decay_idle_days} days",
        user_id=word.user_id,
    )
    return repo.insert_event(event)


def pick_target_words(limit: int | None = None, user_id: str = repo.DEFAULT_USER_ID) -> list[Word]:
    """Spaced-repetition pick: lowest score first, least-recently-used breaks ties."""
    limit = limit or settings.target_words_per_conversation
    words = [w for w in repo.list_words(user_id) if w.score < 100]
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

    def sort_key(w: Word):
        last = w.last_used_at or epoch
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (w.score, last)

    return sorted(words, key=sort_key)[:limit]
