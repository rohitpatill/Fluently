from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException

from ..config import settings
from ..deps import get_current_user
from ..schemas import (
    MemoryAppend,
    MemoryEdit,
    MemoryFileOut,
    MemoryLineOut,
    OnboardingInfo,
    OnboardingResult,
    PersonaForm,
)
from ..services import memory_service, topic_service

router = APIRouter(prefix="/api/memory", tags=["memory"])

VALID = {"identity", "memory", "persona"}


def _check(file: str):
    if file not in VALID:
        raise HTTPException(404, f"Unknown memory file '{file}'. Use: identity | memory | persona")


@router.get("/{file}", response_model=MemoryFileOut)
def read_memory(file: str, user_id: str = Depends(get_current_user)):
    _check(file)
    return MemoryFileOut(
        file=file,
        raw=memory_service.read_file(file, user_id),
        lines=[MemoryLineOut(**e) for e in memory_service.parse_lines(file, user_id)],
    )


@router.post("/{file}/lines", response_model=MemoryLineOut)
def append_line(file: str, payload: MemoryAppend, user_id: str = Depends(get_current_user)):
    _check(file)
    return MemoryLineOut(**memory_service.append(file, payload.text, user_id))


@router.post("/{file}/edit")
def edit_memory(file: str, payload: MemoryEdit, user_id: str = Depends(get_current_user)):
    """Replace text in a memory file (old_string -> new_string). Empty new_string deletes."""
    _check(file)
    try:
        result = memory_service.edit(
            file, payload.old_string, payload.new_string, payload.replace_all, user_id
        )
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, **result}


@router.put("/{file}/raw")
def save_raw(file: str, payload: dict, user_id: str = Depends(get_current_user)):
    """Overwrite the entire markdown file with user-edited content (UI markdown editor)."""
    _check(file)
    raw = payload.get("raw")
    if raw is None:
        raise HTTPException(400, "Body must be {\"raw\": \"<file content>\"}")
    memory_service.write_raw(file, raw, user_id)
    return {"ok": True}


@router.put("/persona/form")
def set_persona(form: PersonaForm, user_id: str = Depends(get_current_user)):
    """Onboarding: define who the system is (name, relation, personality...)."""
    memory_service.set_persona(form.model_dump(), user_id)
    return {"ok": True}


def _persona_name(user_id: str) -> str:
    for line in memory_service.read_file("persona", user_id).splitlines():
        if line.lower().startswith("name:"):
            return line.split(":", 1)[1].strip() or "your companion"
    return "your companion"


@router.post("/onboarding", response_model=OnboardingResult)
def onboarding(info: OnboardingInfo, user_id: str = Depends(get_current_user)):
    """Finish onboarding: store the user's name, then LLM-structure their free-text 'about you'
    dump into clean entries spread across identity/memory/persona. Falls back to appending the
    raw text to identity if the structuring call fails, so onboarding never breaks."""
    name = info.name.strip()
    if name:
        memory_service.append("identity", f"Name: {name}.", user_id)

    about = info.about.strip()
    if not about:
        return OnboardingResult(identity=[f"Name: {name}."] if name else [])

    try:
        today = datetime.now(ZoneInfo(settings.user_timezone)).strftime("%Y-%m-%d")
    except Exception:
        today = datetime.now().strftime("%Y-%m-%d")

    facts = topic_service.structure_onboarding_info(about, _persona_name(user_id), today, user_id)
    if facts is None:  # LLM failed — keep the user's words rather than lose them
        memory_service.append("identity", about, user_id)
        return OnboardingResult(identity=[about])

    for file in ("identity", "memory", "persona"):
        for line in getattr(facts, file):
            if line.strip():
                memory_service.append(file, line.strip(), user_id)
    return OnboardingResult(identity=facts.identity, memory=facts.memory, persona=facts.persona)
