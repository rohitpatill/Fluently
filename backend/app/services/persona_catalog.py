"""Curated public-persona catalog (read-only, shipped with the app).

The data lives in `app/assets/personas.json` (NOT the database — it's identical for every user
and would waste the free-tier Mongo quota). Choosing a catalog persona COPIES it into the
user's own `personas` collection as a normal, fully-editable persona; the original is never
touched. Loaded once and cached in-process.
"""

import json
from functools import lru_cache
from pathlib import Path

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "assets" / "personas.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    with _CATALOG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def categories() -> list[dict]:
    """The catalog grouped by category, as served to the frontend Discover tab.
    Each persona carries a stable `id`, name, relation, avatar_url, and description."""
    data = _load()
    out = []
    for cat in data.get("categories", []):
        out.append(
            {
                "key": cat["key"],
                "label": cat["label"],
                "personas": [
                    {
                        "id": p["id"],
                        "name": p["name"],
                        "relation": p.get("relation", ""),
                        "gender": p.get("gender", ""),
                        "speaking_style": p.get("speaking_style", ""),
                        "avatar_url": p.get("avatar_url", ""),
                        "description": p.get("description", ""),
                    }
                    for p in cat.get("personas", [])
                ],
            }
        )
    return out


def get_entry(catalog_id: str) -> dict | None:
    """Find one catalog persona by its stable id (across all categories)."""
    for cat in _load().get("categories", []):
        for p in cat.get("personas", []):
            if p["id"] == catalog_id:
                return p
    return None
