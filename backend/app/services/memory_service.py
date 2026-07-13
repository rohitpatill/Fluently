"""Free-form markdown memory files, now stored as documents in MongoDB (one doc per
(user_id, file) in the `memory_files` collection) instead of on disk.

The tool logic is UNCHANGED: read the full markdown string, mutate it in memory, write
the whole string back — the classic read-modify-write pattern. Only the storage swapped
from `Path.read_text/write_text` to `repo.get_memory_file/set_memory_file`.

Three logical files per user:
  identity — facts about the USER (who they are, background, personality, how they talk,
             recurring English mistakes) — no dates. Shared across all personas.
  memory   — the USER'S LIFE: events, people, relationships, plans, deadlines. Time-bound
             entries carry an ABSOLUTE date written by the agent inside the text. Shared.
  persona  — who the SYSTEM is + what the persona remembers about the relationship,
             first-person. PER-PERSONA: stored in the `personas` collection, resolved to the
             user's ACTIVE persona (a user may keep several and switch). identity/memory stay
             shared because they describe the one human; only the companion changes.

The whole file is always injected into the prompt, so the agent edits by quoting text
(old_string / new_string), not by any ID.
"""

from .. import repo
from ..mongo import DEFAULT_USER_ID

FILES = ("identity", "memory", "persona")

# `identity` and `memory` are shared across all of a user's personas (they describe the human).
# `persona` is NOT a memory_files doc anymore: it is stored per-persona in the `personas`
# collection and resolved to the user's ACTIVE persona. All the read/append/edit/write_raw
# helpers below transparently route `persona` through the active persona so the rest of the
# app (prompt_builder, agent tools, memory router) is unchanged.
_SHARED_FILES = ("identity", "memory")

# Headers hold ONLY a markdown heading (parse_lines skips headings, so a fresh file has
# zero entries). Descriptive prose is intentionally kept out.
_HEADERS = {
    "identity": "# User Identity\n\n",
    "memory": "# Memories\n\n",
    "persona": "# System Persona\n\n",
}


def normalize_file(file: str) -> str:
    """Accept the bare key ('identity'); defensively strip a stray '.md' suffix if one slips in."""
    key = (file or "").strip().lower()
    if key.endswith(".md"):
        key = key[:-3]
    return key


def _validate(file: str) -> str:
    key = normalize_file(file)
    if key not in FILES:
        raise ValueError(f"Unknown memory file '{file}'. Use one of: {', '.join(FILES)}")
    return key


def _active_persona(user_id: str):
    """Resolve the user's active persona, falling back to their first persona (and creating
    one from any legacy memory_files 'persona' doc if none exist yet — keeps old data working)."""
    user = repo.get_user(user_id)
    personas = repo.list_personas(user_id)

    if not personas:
        # Legacy path: migrate the old single 'persona' memory_files doc into a Persona row,
        # so a user who existed before multi-persona keeps their companion seamlessly.
        legacy = repo.get_memory_file("persona", user_id)
        content = legacy if legacy is not None else _HEADERS["persona"]
        from ..models import Persona
        p = repo.insert_persona(Persona(user_id=user_id, content=content))
        repo.set_active_persona(user_id, p.id)
        return p

    active_id = user.active_persona_id if user else None
    if active_id:
        for p in personas:
            if p.id == active_id:
                return p
    # No/stale active pointer — default to the first persona and repair the pointer.
    repo.set_active_persona(user_id, personas[0].id)
    return personas[0]


def active_persona_id(user_id: str = DEFAULT_USER_ID) -> str:
    """The id of the user's active persona (creating one from legacy data if needed). Used to
    stamp new conversations and scope listings/search to the current companion."""
    return _active_persona(user_id).id


def ensure_files(user_id: str = DEFAULT_USER_ID) -> None:
    for key in _SHARED_FILES:
        if repo.get_memory_file(key, user_id) is None:
            repo.set_memory_file(key, _HEADERS[key], user_id)
    # Guarantee the user has at least one persona + an active pointer.
    _active_persona(user_id)


def read_file(file: str, user_id: str = DEFAULT_USER_ID) -> str:
    key = _validate(file)
    if key == "persona":
        return _active_persona(user_id).content or _HEADERS["persona"]
    content = repo.get_memory_file(key, user_id)
    if content is None:
        content = _HEADERS[key]
        repo.set_memory_file(key, content, user_id)
    return content


def _set_content(key: str, content: str, user_id: str) -> None:
    """Write a file's whole content — persona routes to the active persona doc, the two shared
    files to memory_files. The single seam every mutator below funnels through."""
    if key == "persona":
        p = _active_persona(user_id)
        repo.set_persona_content(p.id, content, user_id)
    else:
        repo.set_memory_file(key, content, user_id)


def parse_lines(file: str, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Content lines only (for the UI's entry count). A content line is any non-empty,
    non-heading line."""
    entries = []
    for line in read_file(file, user_id).splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            entries.append({"text": s})
    return entries


def append(file: str, text: str, user_id: str = DEFAULT_USER_ID) -> dict:
    """Add a new entry line to the end of the file. Stored verbatim — no stamp, no ID."""
    key = _validate(file)
    text = " ".join(text.strip().splitlines())  # one entry = one line
    content = read_file(key, user_id)
    if content and not content.endswith("\n"):
        content += "\n"
    _set_content(key, content + text + "\n", user_id)
    return {"text": text}


def edit(file: str, old_string: str, new_string: str, replace_all: bool = False,
         user_id: str = DEFAULT_USER_ID) -> dict:
    """Replace text in the file (like a plain file edit). Empty new_string deletes.
    Raises KeyError if old_string is absent."""
    key = _validate(file)
    if not old_string:
        raise ValueError("old_string must not be empty")
    content = read_file(key, user_id)
    if old_string not in content:
        raise KeyError(f"Text not found in {key}: {old_string!r}")

    occurrences = content.count(old_string)
    count = -1 if replace_all else 1
    updated = content.replace(old_string, new_string, count)
    if not new_string.strip():
        # collapse a blank gap left behind by a delete-to-empty
        while "\n\n\n" in updated:
            updated = updated.replace("\n\n\n", "\n\n")
    _set_content(key, updated, user_id)
    return {"replaced": occurrences if replace_all else 1}


def reset_file(file: str, user_id: str = DEFAULT_USER_ID) -> None:
    """Hard-reset a memory file back to its pristine header (all entries gone)."""
    key = _validate(file)
    _set_content(key, _HEADERS[key], user_id)


def write_raw(file: str, raw: str, user_id: str = DEFAULT_USER_ID) -> None:
    """Overwrite the whole file — used by the UI's markdown editor (user edits freely)."""
    key = _validate(file)
    normalized = raw if (raw.endswith("\n") or not raw) else raw + "\n"
    _set_content(key, normalized, user_id)


_PERSONA_FIELDS = ("Name:", "Relation to user:", "Gender:", "Personality:", "Speaking style:")


def build_persona_content(form: dict, existing_raw: str = "") -> str:
    """Compose a persona's markdown from the onboarding/edit form, PRESERVING any existing
    relationship-memory entries found in `existing_raw` (empty for a brand-new persona)."""
    marker = "## Relationship memories"
    if marker in existing_raw:
        existing = existing_raw.split(marker, 1)[1]
    else:
        existing = "\n".join(
            ln for ln in existing_raw.splitlines()
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
    return header + (existing_memories + "\n" if existing_memories else "")


_FIELD_KEYS = {
    "name:": "name",
    "relation to user:": "relation",
    "gender:": "gender",
    "personality:": "personality",
    "speaking style:": "speaking_style",
}


def parse_persona_fields(content: str) -> dict:
    """Extract the discrete header fields (name/relation/gender/personality/speaking_style)
    from a persona's markdown — for the Settings persona cards + edit form."""
    fields = {v: "" for v in _FIELD_KEYS.values()}
    for line in (content or "").splitlines():
        low = line.strip().lower()
        for prefix, key in _FIELD_KEYS.items():
            if low.startswith(prefix):
                fields[key] = line.split(":", 1)[1].strip()
                break
    return fields


def set_persona(form: dict, user_id: str = DEFAULT_USER_ID, persona_id: str | None = None) -> None:
    """Rewrite a persona's header block from the form, keeping its relationship memories.
    Targets `persona_id` when given (edit/create flow), else the active persona (onboarding)."""
    ensure_files(user_id)
    if persona_id is not None:
        persona = repo.get_persona(persona_id, user_id)
        content = build_persona_content(form, persona.content if persona else "")
        repo.set_persona_content(persona_id, content, user_id)
    else:
        content = build_persona_content(form, read_file("persona", user_id))
        _set_content("persona", content, user_id)
