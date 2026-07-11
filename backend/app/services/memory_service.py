"""Markdown memory files with stable line IDs.

Three files live in DATA_DIR:
  identity.md  — who the user is (facts, patterns, emotional intelligence, mistakes)
  memory.md    — life events, relationships, ongoing situations
  persona.md   — who the SYSTEM is (from onboarding form) + its relationship memories

Every entry is one line:  [i042] 2026-07-11 14:03 +05:30 | the fact
Line IDs are stable — update/delete target IDs, never fuzzy text.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings

FILES = {"identity": "identity.md", "memory": "memory.md", "persona": "persona.md"}
PREFIX = {"identity": "i", "memory": "m", "persona": "p"}

_LINE_RE = re.compile(r"^\[(?P<id>[a-z]\d{3,})\]\s+(?P<ts>[\d\-]+\s[\d:]+\s[+\-][\d:]+)\s*\|\s*(?P<text>.*)$")

_HEADERS = {
    "identity": "# User Identity\n\nCore facts about the user: who they are, how they talk, "
    "their preferences, emotional patterns, recurring English mistakes.\n\n",
    "memory": "# Memories\n\nImportant events and situations in the user's life, "
    "people and relationships, things to follow up on.\n\n",
    "persona": "# System Persona\n\nWho the assistant is (set during onboarding) and its own "
    "memories of the relationship with the user.\n\n",
}


def _path(file: str) -> Path:
    if file not in FILES:
        raise ValueError(f"Unknown memory file '{file}'. Use one of: {', '.join(FILES)}")
    return settings.data_path / FILES[file]


def ensure_files() -> None:
    for key in FILES:
        p = _path(key)
        if not p.exists():
            p.write_text(_HEADERS[key], encoding="utf-8")


def _now_stamp() -> str:
    # local time with UTC offset, e.g. "2026-07-11 14:03 +05:30"
    now = datetime.now(timezone.utc).astimezone()
    off = now.strftime("%z")
    return now.strftime("%Y-%m-%d %H:%M ") + f"{off[:3]}:{off[3:]}"


def read_file(file: str) -> str:
    ensure_files()
    return _path(file).read_text(encoding="utf-8")


def parse_lines(file: str) -> list[dict]:
    entries = []
    for line in read_file(file).splitlines():
        m = _LINE_RE.match(line.strip())
        if m:
            entries.append({"line_id": m["id"], "timestamp": m["ts"], "text": m["text"]})
    return entries


def _next_id(file: str) -> str:
    prefix = PREFIX[file]
    nums = [int(e["line_id"][1:]) for e in parse_lines(file) if e["line_id"].startswith(prefix)]
    return f"{prefix}{(max(nums) + 1 if nums else 1):03d}"


def append(file: str, text: str) -> dict:
    ensure_files()
    text = " ".join(text.strip().splitlines())  # keep entries single-line
    line_id = _next_id(file)
    entry = f"[{line_id}] {_now_stamp()} | {text}\n"
    p = _path(file)
    content = p.read_text(encoding="utf-8")
    if not content.endswith("\n"):
        content += "\n"
    p.write_text(content + entry, encoding="utf-8")
    return {"line_id": line_id, "timestamp": _now_stamp(), "text": text}


def update(file: str, line_id: str, new_text: str) -> dict:
    ensure_files()
    new_text = " ".join(new_text.strip().splitlines())
    p = _path(file)
    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = _LINE_RE.match(line.strip())
        if m and m["id"] == line_id:
            lines[i] = f"[{line_id}] {_now_stamp()} | {new_text}\n"
            p.write_text("".join(lines), encoding="utf-8")
            return {"line_id": line_id, "timestamp": _now_stamp(), "text": new_text}
    raise KeyError(f"Line id '{line_id}' not found in {file}.md")


def delete(file: str, line_id: str) -> None:
    ensure_files()
    p = _path(file)
    lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [ln for ln in lines if not (_LINE_RE.match(ln.strip()) and _LINE_RE.match(ln.strip())["id"] == line_id)]
    if len(kept) == len(lines):
        raise KeyError(f"Line id '{line_id}' not found in {file}.md")
    p.write_text("".join(kept), encoding="utf-8")


def write_raw(file: str, raw: str) -> None:
    """Overwrite the whole file — used by the UI's markdown editor (user edits freely)."""
    ensure_files()
    _path(file).write_text(raw if raw.endswith("\n") or not raw else raw + "\n", encoding="utf-8")


def set_persona(form: dict) -> None:
    """Rewrite the persona header block from the onboarding form (keeps existing [pNNN] memory lines)."""
    ensure_files()
    existing = [f"[{e['line_id']}] {e['timestamp']} | {e['text']}" for e in parse_lines("persona")]
    header = (
        "# System Persona\n\n"
        f"Name: {form.get('name', '')}\n"
        f"Relation to user: {form.get('relation', '')}\n"
        f"Gender: {form.get('gender', '')}\n"
        f"Personality: {form.get('personality', '')}\n"
        f"Speaking style: {form.get('speaking_style', '')}\n\n"
        "## Relationship memories\n\n"
    )
    _path("persona").write_text(header + "\n".join(existing) + ("\n" if existing else ""), encoding="utf-8")
