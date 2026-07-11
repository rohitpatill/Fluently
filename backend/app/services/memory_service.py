"""Free-form markdown memory files, now stored as documents in MongoDB (one doc per
(user_id, file) in the `memory_files` collection) instead of on disk.

The tool logic is UNCHANGED: read the full markdown string, mutate it in memory, write
the whole string back — the classic read-modify-write pattern. Only the storage swapped
from `Path.read_text/write_text` to `repo.get_memory_file/set_memory_file`.

Three files per user:
  identity — facts about the USER (who they are, background, personality, how they talk,
             recurring English mistakes) — no dates.
  memory   — the USER'S LIFE: events, people, relationships, plans, deadlines. Time-bound
             entries carry an ABSOLUTE date written by the agent inside the text.
  persona  — who the SYSTEM is (from onboarding) + what the persona remembers about the
             relationship, first-person.

The whole file is always injected into the prompt, so the agent edits by quoting text
(old_string / new_string), not by any ID.
"""

from .. import repo
from ..mongo import DEFAULT_USER_ID

FILES = ("identity", "memory", "persona")

# Headers hold ONLY a markdown heading (parse_lines skips headings, so a fresh file has
# zero entries). Descriptive prose is intentionally kept out.
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


def _validate(file: str) -> str:
    key = normalize_file(file)
    if key not in FILES:
        raise ValueError(f"Unknown memory file '{file}'. Use one of: {', '.join(FILES)}")
    return key


def ensure_files(user_id: str = DEFAULT_USER_ID) -> None:
    for key in FILES:
        if repo.get_memory_file(key, user_id) is None:
            repo.set_memory_file(key, _HEADERS[key], user_id)


def read_file(file: str, user_id: str = DEFAULT_USER_ID) -> str:
    key = _validate(file)
    content = repo.get_memory_file(key, user_id)
    if content is None:
        content = _HEADERS[key]
        repo.set_memory_file(key, content, user_id)
    return content


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
    repo.set_memory_file(key, content + text + "\n", user_id)
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
        raise KeyError(f"Text not found in {key}.md: {old_string!r}")

    occurrences = content.count(old_string)
    count = -1 if replace_all else 1
    updated = content.replace(old_string, new_string, count)
    if not new_string.strip():
        # collapse a blank gap left behind by a delete-to-empty
        while "\n\n\n" in updated:
            updated = updated.replace("\n\n\n", "\n\n")
    repo.set_memory_file(key, updated, user_id)
    return {"replaced": occurrences if replace_all else 1}


def reset_file(file: str, user_id: str = DEFAULT_USER_ID) -> None:
    """Hard-reset a memory file back to its pristine header (all entries gone)."""
    key = _validate(file)
    repo.set_memory_file(key, _HEADERS[key], user_id)


def write_raw(file: str, raw: str, user_id: str = DEFAULT_USER_ID) -> None:
    """Overwrite the whole file — used by the UI's markdown editor (user edits freely)."""
    key = _validate(file)
    normalized = raw if (raw.endswith("\n") or not raw) else raw + "\n"
    repo.set_memory_file(key, normalized, user_id)


_PERSONA_FIELDS = ("Name:", "Relation to user:", "Gender:", "Personality:", "Speaking style:")


def set_persona(form: dict, user_id: str = DEFAULT_USER_ID) -> None:
    """Rewrite the persona header block from the onboarding form, keeping existing
    relationship-memory entries (any content line that isn't a header/field line)."""
    ensure_files(user_id)
    marker = "## Relationship memories"
    raw = read_file("persona", user_id)

    if marker in raw:
        existing = raw.split(marker, 1)[1]
    else:
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
    repo.set_memory_file(
        "persona", header + (existing_memories + "\n" if existing_memories else ""), user_id
    )
