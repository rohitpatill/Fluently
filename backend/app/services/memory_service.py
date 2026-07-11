"""Free-form markdown memory files. No IDs, no machine-added stamps — the agent
edits these files the same way it would edit any small text file (append a line, or
replace a snippet). Whatever the agent writes is exactly what is stored.

Three files live in DATA_DIR:
  identity.md  — facts about the USER (who they are, background, personality, how they
                 talk, preferences, recurring English mistakes, inferred patterns)
  memory.md    — the USER'S LIFE: events, people, relationships, ongoing situations,
                 plans, goals, deadlines. Time-bound entries carry an ABSOLUTE date,
                 written by the agent inside the text (the system never adds dates).
  persona.md   — who the SYSTEM is (from onboarding) + what the persona remembers about
                 the relationship, from its own side (shared jokes, promises, moments).

The whole file is always injected into the prompt, so the agent references text
directly (old_string / new_string) instead of by any ID it would have to track.
"""

from pathlib import Path

from ..config import settings

FILES = {"identity": "identity.md", "memory": "memory.md", "persona": "persona.md"}

# Headers hold ONLY a markdown heading (parse_lines skips headings, so the file starts
# with zero entries). Descriptive prose is intentionally kept out so every content line
# is a real memory entry.
_HEADERS = {
    "identity": "# User Identity\n\n",
    "memory": "# Memories\n\n",
    "persona": "# System Persona\n\n",
}


def normalize_file(file: str) -> str:
    """Accept the bare key ('identity') and tolerate a '.md' suffix the model may add."""
    key = (file or "").strip().lower()
    if key.endswith(".md"):
        key = key[:-3]
    return key


def _path(file: str) -> Path:
    key = normalize_file(file)
    if key not in FILES:
        raise ValueError(f"Unknown memory file '{file}'. Use one of: {', '.join(FILES)}")
    return settings.data_path / FILES[key]


def ensure_files() -> None:
    for key in FILES:
        p = _path(key)
        if not p.exists():
            p.write_text(_HEADERS[key], encoding="utf-8")


def read_file(file: str) -> str:
    ensure_files()
    return _path(file).read_text(encoding="utf-8")


def parse_lines(file: str) -> list[dict]:
    """Return the memory file's content lines (used only for the UI's entry count).
    A content line is any non-empty line that is not a markdown heading."""
    entries = []
    for line in read_file(file).splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            entries.append({"text": s})
    return entries


def append(file: str, text: str) -> dict:
    """Add a new entry line to the end of the file. Stored verbatim — no stamp, no ID.
    The agent is responsible for any date it wants inside the text."""
    ensure_files()
    text = " ".join(text.strip().splitlines())  # one entry = one line
    p = _path(file)
    content = p.read_text(encoding="utf-8")
    if content and not content.endswith("\n"):
        content += "\n"
    p.write_text(content + text + "\n", encoding="utf-8")
    return {"text": text}


def edit(file: str, old_string: str, new_string: str, replace_all: bool = False) -> dict:
    """Replace text in the file (like a plain file edit). Used to correct or remove an
    existing memory: pass the current snippet as old_string and the replacement (empty
    string to delete) as new_string. Raises KeyError if old_string is absent."""
    ensure_files()
    if not old_string:
        raise ValueError("old_string must not be empty")
    p = _path(file)
    content = p.read_text(encoding="utf-8")
    if old_string not in content:
        raise KeyError(f"Text not found in {file}.md: {old_string!r}")

    occurrences = content.count(old_string)
    count = -1 if replace_all else 1
    updated = content.replace(old_string, new_string, count)
    if not new_string.strip():
        # collapse a blank gap left behind by a delete-to-empty
        while "\n\n\n" in updated:
            updated = updated.replace("\n\n\n", "\n\n")
    p.write_text(updated, encoding="utf-8")
    return {"replaced": occurrences if replace_all else 1}


def reset_file(file: str) -> None:
    """Hard-reset a memory file back to its pristine header (all entries gone)."""
    _path(file).write_text(_HEADERS[file], encoding="utf-8")


def write_raw(file: str, raw: str) -> None:
    """Overwrite the whole file — used by the UI's markdown editor (user edits freely)."""
    ensure_files()
    _path(file).write_text(raw if raw.endswith("\n") or not raw else raw + "\n", encoding="utf-8")


_PERSONA_FIELDS = ("Name:", "Relation to user:", "Gender:", "Personality:", "Speaking style:")


def set_persona(form: dict) -> None:
    """Rewrite the persona header block from the onboarding form, keeping existing
    relationship-memory entries (any content line that isn't a header/field line)."""
    ensure_files()
    marker = "## Relationship memories"
    raw = _path("persona").read_text(encoding="utf-8")

    if marker in raw:
        existing = raw.split(marker, 1)[1]
    else:
        # legacy/fresh file with no marker: keep any non-heading, non-field content line
        existing = "\n".join(
            ln for ln in raw.splitlines()
            if ln.strip()
            and not ln.startswith("#")
            and not ln.strip().startswith(_PERSONA_FIELDS)
        )
    existing_memories = existing.strip()

    header = (
        "# System Persona\n\n"
        f"Name: {form.get('name', '')}\n"
        f"Relation to user: {form.get('relation', '')}\n"
        f"Gender: {form.get('gender', '')}\n"
        f"Personality: {form.get('personality', '')}\n"
        f"Speaking style: {form.get('speaking_style', '')}\n\n"
        f"{marker}\n\n"
    )
    _path("persona").write_text(
        header + (existing_memories + "\n" if existing_memories else ""), encoding="utf-8"
    )
