"""Scoring engine unit tests: matrix deltas, daily cap, decay, target-word picking."""

from datetime import datetime, timedelta, timezone

from app.models import Word
from app.services import scoring_service


def _word(db, text="test-word", **kw):
    w = Word(text=text, **kw)
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


def test_matrix_deltas(db):
    w = _word(db)
    assert scoring_service.apply_event(db, w, "perfect_unprompted").delta == 5.0
    w2 = _word(db, text="w2")
    assert scoring_service.apply_event(db, w2, "perfect_prompted").delta == 3.0
    w3 = _word(db, text="w3")
    assert scoring_service.apply_event(db, w3, "awkward").delta == 1.0
    w4 = _word(db, text="w4", score=10.0)
    assert scoring_service.apply_event(db, w4, "wrong").delta == -2.0
    w5 = _word(db, text="w5")
    assert scoring_service.apply_event(db, w5, "passive").delta == 0.5


def test_wrong_never_goes_below_zero(db):
    w = _word(db, score=1.0)
    e = scoring_service.apply_event(db, w, "wrong")
    assert e.score_after == 0.0 and e.delta == -1.0


def test_daily_cap(db):
    w = _word(db)
    scoring_service.apply_event(db, w, "perfect_unprompted")  # +5
    scoring_service.apply_event(db, w, "perfect_unprompted")  # +5 -> at cap 10
    e = scoring_service.apply_event(db, w, "perfect_unprompted")  # capped to 0
    assert e.delta == 0.0 and w.score == 10.0
    # negative events still apply at cap
    assert scoring_service.apply_event(db, w, "wrong").delta == -2.0
    # manual bypasses the cap
    assert scoring_service.apply_event(db, w, "manual", manual_delta=50).delta == 50.0


def test_usage_updates_last_used_and_times_used(db):
    w = _word(db)
    scoring_service.apply_event(db, w, "perfect_prompted")
    assert w.times_used == 1 and w.last_used_at is not None
    scoring_service.apply_event(db, w, "passive")  # passive doesn't count as production
    assert w.times_used == 1


def test_decay_after_idle(db):
    w = _word(db, score=50.0)
    w.last_used_at = datetime.now(timezone.utc) - timedelta(days=28)  # 14 idle + 2 weeks decay
    db.commit()
    e = scoring_service.apply_decay(db, w)
    assert e is not None and e.delta == -2.0 and w.score == 48.0
    # immediately re-applying decays nothing more
    assert scoring_service.apply_decay(db, w) is None


def test_no_decay_when_recently_used_or_zero(db):
    w = _word(db, score=50.0)
    w.last_used_at = datetime.now(timezone.utc) - timedelta(days=5)
    db.commit()
    assert scoring_service.apply_decay(db, w) is None

    w2 = _word(db, text="zero", score=0.0)
    w2.last_used_at = datetime.now(timezone.utc) - timedelta(days=60)
    db.commit()
    assert scoring_service.apply_decay(db, w2) is None


def test_pick_target_words_spaced_repetition(db):
    now = datetime.now(timezone.utc)
    _word(db, text="mastered", score=100.0)  # excluded
    _word(db, text="low-old", score=10.0, last_used_at=now - timedelta(days=30))
    _word(db, text="low-recent", score=10.0, last_used_at=now - timedelta(days=1))
    _word(db, text="high", score=80.0)
    picked = scoring_service.pick_target_words(db, limit=3)
    texts = [w.text for w in picked]
    assert "mastered" not in texts
    assert texts[0] == "low-old"  # lowest score, least recently used first
    assert texts[1] == "low-recent"
