from fastapi import APIRouter, HTTPException

from ..schemas import MemoryAppend, MemoryFileOut, MemoryLineOut, MemoryUpdate, PersonaForm
from ..services import memory_service

router = APIRouter(prefix="/api/memory", tags=["memory"])

VALID = {"identity", "memory", "persona"}


def _check(file: str):
    if file not in VALID:
        raise HTTPException(404, f"Unknown memory file '{file}'. Use: identity | memory | persona")


@router.get("/{file}", response_model=MemoryFileOut)
def read_memory(file: str):
    _check(file)
    return MemoryFileOut(
        file=file,
        raw=memory_service.read_file(file),
        lines=[MemoryLineOut(**e) for e in memory_service.parse_lines(file)],
    )


@router.post("/{file}/lines", response_model=MemoryLineOut)
def append_line(file: str, payload: MemoryAppend):
    _check(file)
    return MemoryLineOut(**memory_service.append(file, payload.text))


@router.put("/{file}/lines/{line_id}", response_model=MemoryLineOut)
def update_line(file: str, line_id: str, payload: MemoryUpdate):
    _check(file)
    try:
        return MemoryLineOut(**memory_service.update(file, line_id, payload.text))
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.delete("/{file}/lines/{line_id}")
def delete_line(file: str, line_id: str):
    _check(file)
    try:
        memory_service.delete(file, line_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    return {"ok": True}


@router.put("/{file}/raw")
def save_raw(file: str, payload: dict):
    """Overwrite the entire markdown file with user-edited content (UI markdown editor)."""
    _check(file)
    raw = payload.get("raw")
    if raw is None:
        raise HTTPException(400, "Body must be {\"raw\": \"<file content>\"}")
    memory_service.write_raw(file, raw)
    return {"ok": True}


@router.put("/persona/form")
def set_persona(form: PersonaForm):
    """Onboarding: define who the system is (name, relation, personality...)."""
    memory_service.set_persona(form.model_dump())
    return {"ok": True}
