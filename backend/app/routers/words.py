from fastapi import APIRouter, HTTPException

from .. import repo
from ..models import Word
from ..mongo import DEFAULT_USER_ID
from ..schemas import WordCreate, WordEventOut, WordNoteUpdate, WordOut, WordScoreAdjust
from ..services import scoring_service
from ..services.topic_service import enrich_word

router = APIRouter(prefix="/api/words", tags=["words"])


@router.get("", response_model=list[WordOut])
def list_words():
    words = repo.list_words(DEFAULT_USER_ID)
    for w in words:
        scoring_service.apply_decay(w)  # lazy decay on dashboard read
    return words


@router.post("", response_model=WordOut)
def add_word(payload: WordCreate):
    text = payload.text.strip()
    if not text:
        raise HTTPException(400, "Word text is empty")
    existing = repo.find_word_by_text(text, DEFAULT_USER_ID)
    if existing:
        raise HTTPException(409, f"'{text}' is already being tracked")
    word = Word(text=text, kind=payload.kind, user_id=DEFAULT_USER_ID)
    enrichment = enrich_word(text, payload.kind)  # LLM: meaning, examples, collocations, register
    if enrichment:
        word.meaning = enrichment.meaning
        word.examples = enrichment.examples
        word.collocations = enrichment.collocations
        word.register_notes = enrichment.register_notes
    repo.insert_word(word)
    return word


@router.get("/{word_id}", response_model=WordOut)
def get_word(word_id: str):
    word = repo.get_word(word_id, DEFAULT_USER_ID)
    if not word:
        raise HTTPException(404, "Word not found")
    scoring_service.apply_decay(word)
    return word


@router.delete("/{word_id}")
def delete_word(word_id: str):
    word = repo.get_word(word_id, DEFAULT_USER_ID)
    if not word:
        raise HTTPException(404, "Word not found")
    repo.delete_word(word_id, DEFAULT_USER_ID)
    return {"ok": True}


@router.put("/{word_id}/note", response_model=WordOut)
def set_note(word_id: str, payload: WordNoteUpdate):
    """User's own memory hook for a word (where they saw it, a mnemonic, a translation).
    Purely user-authored — the judge/agent never write here. Empty string clears it."""
    word = repo.get_word(word_id, DEFAULT_USER_ID)
    if not word:
        raise HTTPException(404, "Word not found")
    word.note = payload.note.strip()
    repo.save_word(word)
    return word


@router.post("/{word_id}/adjust", response_model=WordEventOut)
def adjust_score(word_id: str, payload: WordScoreAdjust):
    """Manual score change — e.g. user lowers a word to practice it more."""
    word = repo.get_word(word_id, DEFAULT_USER_ID)
    if not word:
        raise HTTPException(404, "Word not found")
    return scoring_service.apply_event(
        word, "manual", judge_notes=payload.reason or "manual adjustment", manual_delta=payload.delta
    )


@router.get("/{word_id}/events", response_model=list[WordEventOut])
def word_history(word_id: str):
    if not repo.get_word(word_id, DEFAULT_USER_ID):
        raise HTTPException(404, "Word not found")
    return repo.word_events(word_id, DEFAULT_USER_ID, limit=100)
