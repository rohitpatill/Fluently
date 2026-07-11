"""Scoring engine unit tests: matrix deltas, no-cap gains, decay, target-word picking."""

from datetime import datetime, timedelta, timezone

from app import repo
from app.models import Word
from app.services import scoring_service


def _word(text="test-word", **kw):
    w = Word(text=text, **kw)
    return repo.insert_word(w)


def test_matrix_deltas():
    w = _word()
    assert scoring_service.apply_event(w, "perfect_unprompted").delta == 5.0
    w2 = _word(text="w2")
    assert scoring_service.apply_event(w2, "perfect_prompted").delta == 3.0
    w3 = _word(text="w3")
    assert scoring_service.apply_event(w3, "awkward").delta == 1.0
    w4 = _word(text="w4", score=10.0)
    assert scoring_service.apply_event(w4, "wrong").delta == -2.0
    w5 = _word(text="w5")
    assert scoring_service.apply_event(w5, "passive").delta == 0.5


def test_wrong_never_goes_below_zero():
    w = _word(score=1.0)
    e = scoring_service.apply_event(w, "wrong")
    assert e.score_after == 0.0 and e.delta == -1.0


def test_no_daily_cap_gains_apply_in_full():
    # No cap: a word can climb 0 -> 100 in a single day, every gain in full.
    w = _word()
    for _ in range(19):
        scoring_service.apply_event(w, "perfect_unprompted")  # 19 * 5 = 95
    assert w.score == 95.0
    # last gain clamps to the 100 ceiling
    e = scoring_service.apply_event(w, "perfect_unprompted")
    assert w.score == 100.0 and e.delta == 5.0
    # already at 100: further gain clamps to 0 delta (ceiling, not a daily cap)
    assert scoring_service.apply_event(w, "perfect_unprompted").delta == 0.0
    # negatives still apply
    assert scoring_service.apply_event(w, "wrong").delta == -2.0
    # manual delta applies directly
    assert scoring_service.apply_event(w, "manual", manual_delta=-50).delta == -50.0


def test_usage_updates_last_used_and_times_used():
    w = _word()
    scoring_service.apply_event(w, "perfect_prompted")
    assert w.times_used == 1 and w.last_used_at is not None
    scoring_service.apply_event(w, "passive")  # passive doesn't count as production
    assert w.times_used == 1


def test_decay_after_idle():
    w = _word(score=50.0)
    w.last_used_at = datetime.now(timezone.utc) - timedelta(days=28)  # 14 idle + 2 weeks decay
    repo.save_word(w)
    e = scoring_service.apply_decay(w)
    assert e is not None and e.delta == -2.0 and w.score == 48.0
    # immediately re-applying decays nothing more
    assert scoring_service.apply_decay(w) is None


def test_no_decay_when_recently_used_or_zero():
    w = _word(score=50.0)
    w.last_used_at = datetime.now(timezone.utc) - timedelta(days=5)
    repo.save_word(w)
    assert scoring_service.apply_decay(w) is None

    w2 = _word(text="zero", score=0.0)
    w2.last_used_at = datetime.now(timezone.utc) - timedelta(days=60)
    repo.save_word(w2)
    assert scoring_service.apply_decay(w2) is None


def test_pick_target_words_spaced_repetition():
    now = datetime.now(timezone.utc)
    _word(text="mastered", score=100.0)  # excluded
    _word(text="low-old", score=10.0, last_used_at=now - timedelta(days=30))
    _word(text="low-recent", score=10.0, last_used_at=now - timedelta(days=1))
    _word(text="high", score=80.0)
    picked = scoring_service.pick_target_words(limit=3)
    texts = [w.text for w in picked]
    assert "mastered" not in texts
    assert texts[0] == "low-old"  # lowest score, least recently used first
    assert texts[1] == "low-recent"
