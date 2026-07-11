"""Search past conversations: BM25 ranking or regex match, with context windows.

The ranking is done in Python (rank_bm25 / regex), exactly as before — MongoDB is only
the message store. Messages are loaded via repo; the algorithm below is unchanged.

Flags:
  - mode: bm25 | regex
  - conversation_id: limit search to one conversation
  - n_before / n_after: messages of context around each hit
  - full_conversation: return the entire conversation containing the hit
  - max_results: number of hits (each hit = one matched message + its window)
"""

import re

from rank_bm25 import BM25Okapi

from .. import repo
from ..models import Message
from ..mongo import DEFAULT_USER_ID


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def search(
    query: str,
    mode: str = "bm25",
    conversation_id: str | None = None,
    n_before: int = 3,
    n_after: int = 3,
    full_conversation: bool = False,
    max_results: int = 5,
    exclude_conversation_id: str | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> list[dict]:
    messages: list[Message] = repo.all_messages(
        user_id=user_id,
        conversation_id=conversation_id,
        exclude_conversation_id=exclude_conversation_id,
    )
    if not messages:
        return []

    # rank messages
    scored: list[tuple[Message, float]] = []
    if mode == "regex":
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            pattern = re.compile(re.escape(query), re.IGNORECASE)
        scored = [(m, 1.0) for m in messages if pattern.search(m.content)]
    else:
        corpus = [_tokenize(m.content) for m in messages]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(_tokenize(query))
        scored = [(m, float(s)) for m, s in zip(messages, scores) if s > 0]
        scored.sort(key=lambda x: x[1], reverse=True)

    # one hit per matched message, deduping overlapping windows in the same conversation
    hits: list[dict] = []
    seen_ranges: dict[str, list[tuple[int, int]]] = {}
    conv_titles = {c.id: c.title for c in repo.list_conversations(user_id)}

    for msg, score in scored:
        if len(hits) >= max_results:
            break
        conv_msgs = [m for m in messages if m.conversation_id == msg.conversation_id]
        idx = next(i for i, m in enumerate(conv_msgs) if m.id == msg.id)
        if full_conversation:
            lo, hi = 0, len(conv_msgs) - 1
        else:
            lo, hi = max(0, idx - n_before), min(len(conv_msgs) - 1, idx + n_after)
        ranges = seen_ranges.setdefault(msg.conversation_id, [])
        if any(lo <= r_hi and hi >= r_lo for r_lo, r_hi in ranges):
            continue
        ranges.append((lo, hi))
        hits.append(
            {
                "conversation_id": msg.conversation_id,
                "conversation_title": conv_titles.get(msg.conversation_id, ""),
                "message_id": msg.id,
                "score": round(score, 3),
                "context": conv_msgs[lo : hi + 1],
            }
        )
    return hits


def format_hits_for_llm(hits: list[dict]) -> str:
    """Render hits as compact text for the tool result the model reads."""
    if not hits:
        return "No matching past conversations found."
    out = []
    for h in hits:
        lines = [f"--- Conversation #{h['conversation_id']} \"{h['conversation_title']}\" (match score {h['score']}) ---"]
        for m in h["context"]:
            marker = " <-- MATCH" if m.id == h["message_id"] else ""
            ts = m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else ""
            lines.append(f"[{ts}] {m.role}: {m.content}{marker}")
        out.append("\n".join(lines))
    return "\n\n".join(out)
