from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Conversation, Message, Word, WordEvent

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    total_words = db.query(func.count(Word.id)).scalar() or 0
    mastered = db.query(func.count(Word.id)).filter(Word.score >= 100).scalar() or 0
    avg_score = db.query(func.avg(Word.score)).scalar() or 0.0

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    events_week = db.query(func.count(WordEvent.id)).filter(WordEvent.created_at >= week_ago).scalar() or 0
    gained_week = (
        db.query(func.coalesce(func.sum(WordEvent.delta), 0.0))
        .filter(WordEvent.created_at >= week_ago, WordEvent.delta > 0)
        .scalar()
        or 0.0
    )

    slipping = (
        db.query(Word)
        .filter(Word.score > 0, Word.score < 100)
        .filter((Word.last_used_at.is_(None)) | (Word.last_used_at < datetime.now(timezone.utc) - timedelta(days=14)))
        .order_by(Word.score.desc())
        .limit(5)
        .all()
    )
    top = db.query(Word).order_by(Word.score.desc()).limit(5).all()
    weakest = db.query(Word).filter(Word.score < 100).order_by(Word.score.asc()).limit(5).all()

    return {
        "total_words": total_words,
        "mastered": mastered,
        "average_score": round(float(avg_score), 1),
        "usage_events_this_week": events_week,
        "points_gained_this_week": round(float(gained_week), 1),
        "total_conversations": db.query(func.count(Conversation.id)).scalar() or 0,
        "total_messages": db.query(func.count(Message.id)).scalar() or 0,
        "top_words": [{"id": w.id, "text": w.text, "score": w.score} for w in top],
        "weakest_words": [{"id": w.id, "text": w.text, "score": w.score} for w in weakest],
        "slipping_words": [{"id": w.id, "text": w.text, "score": w.score} for w in slipping],
    }
