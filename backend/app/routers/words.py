from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Word, WordEvent
from ..schemas import WordCreate, WordEventOut, WordNoteUpdate, WordOut, WordScoreAdjust
from ..services import scoring_service
from ..services.topic_service import enrich_word

router = APIRouter(prefix="/api/words", tags=["words"])


@router.get("", response_model=list[WordOut])
def list_words(db: Session = Depends(get_db)):
    words = db.query(Word).order_by(Word.score.desc()).all()
    for w in words:
        scoring_service.apply_decay(db, w)  # lazy decay on dashboard read
    return words


@router.post("", response_model=WordOut)
def add_word(payload: WordCreate, db: Session = Depends(get_db)):
    text = payload.text.strip()
    if not text:
        raise HTTPException(400, "Word text is empty")
    existing = db.query(Word).filter(Word.text.ilike(text)).first()
    if existing:
        raise HTTPException(409, f"'{text}' is already being tracked")
    word = Word(text=text, kind=payload.kind)
    enrichment = enrich_word(text, payload.kind)  # LLM: meaning, examples, collocations, register
    if enrichment:
        word.meaning = enrichment.meaning
        word.examples = enrichment.examples
        word.collocations = enrichment.collocations
        word.register_notes = enrichment.register_notes
    db.add(word)
    db.commit()
    db.refresh(word)
    return word


@router.get("/{word_id}", response_model=WordOut)
def get_word(word_id: int, db: Session = Depends(get_db)):
    word = db.get(Word, word_id)
    if not word:
        raise HTTPException(404, "Word not found")
    scoring_service.apply_decay(db, word)
    return word


@router.delete("/{word_id}")
def delete_word(word_id: int, db: Session = Depends(get_db)):
    word = db.get(Word, word_id)
    if not word:
        raise HTTPException(404, "Word not found")
    db.delete(word)
    db.commit()
    return {"ok": True}


@router.put("/{word_id}/note", response_model=WordOut)
def set_note(word_id: int, payload: WordNoteUpdate, db: Session = Depends(get_db)):
    """User's own memory hook for a word (where they saw it, a mnemonic, a translation).
    Purely user-authored — the judge/agent never write here. Empty string clears it."""
    word = db.get(Word, word_id)
    if not word:
        raise HTTPException(404, "Word not found")
    word.note = payload.note.strip()
    db.commit()
    db.refresh(word)
    return word


@router.post("/{word_id}/adjust", response_model=WordEventOut)
def adjust_score(word_id: int, payload: WordScoreAdjust, db: Session = Depends(get_db)):
    """Manual score change — e.g. user lowers a word to practice it more."""
    word = db.get(Word, word_id)
    if not word:
        raise HTTPException(404, "Word not found")
    return scoring_service.apply_event(
        db, word, "manual", judge_notes=payload.reason or "manual adjustment", manual_delta=payload.delta
    )


@router.get("/{word_id}/events", response_model=list[WordEventOut])
def word_history(word_id: int, db: Session = Depends(get_db)):
    if not db.get(Word, word_id):
        raise HTTPException(404, "Word not found")
    return (
        db.query(WordEvent).filter(WordEvent.word_id == word_id).order_by(WordEvent.created_at.desc()).limit(100).all()
    )
