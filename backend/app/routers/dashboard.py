from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from .. import repo
from ..deps import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def stats(user_id: str = Depends(get_current_user)):
    uid = user_id
    counts = repo.dashboard_counts(uid)

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    events_week, gained_week = repo.events_since(week_ago, uid)

    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    slipping = repo.slipping_words(cutoff, uid, limit=5)
    top = repo.top_words(uid, limit=5)
    weakest = repo.weakest_words(uid, limit=5)

    return {
        "total_words": counts["total_words"],
        "mastered": counts["mastered"],
        "average_score": round(float(counts["average_score"]), 1),
        "usage_events_this_week": events_week,
        "points_gained_this_week": round(float(gained_week), 1),
        "total_conversations": counts["total_conversations"],
        "total_messages": counts["total_messages"],
        "top_words": [{"id": w.id, "text": w.text, "score": w.score} for w in top],
        "weakest_words": [{"id": w.id, "text": w.text, "score": w.score} for w in weakest],
        "slipping_words": [{"id": w.id, "text": w.text, "score": w.score} for w in slipping],
    }
