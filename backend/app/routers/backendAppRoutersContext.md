# backendAppRoutersContext.md — scope: `backend/app/routers/`

HTTP layer only — validation + delegation to services. Sync `def` routes (FastAPI threadpools them).
Parent: [../backendAppContext.md](../backendAppContext.md).

| File | Endpoints |
|---|---|
| `chat.py` | `POST /api/chat/{conversation_id}` — full chat turn; returns user_message, assistant_message (with tool_calls), scoring_events. |
| `conversations.py` | `POST /api/conversations` (picks target words via spaced repetition, optional topic suggestions), `GET` list/detail/messages, `PATCH .../category` (query param), `POST .../opener` (400 if messages exist), `DELETE`, `POST /api/conversations/search` (BM25/regex, window flags). |
| `words.py` | `GET /api/words` (applies lazy decay), `POST` (409 duplicate, LLM enrichment on add), `GET/DELETE /{id}`, `POST /{id}/adjust` (manual event), `GET /{id}/events` (last 100). |
| `memory.py` | `GET /api/memory/{file}` (raw + parsed lines, no ids/timestamps), `POST .../lines` (append), `POST .../edit` (old_string→new_string, empty new_string deletes; 404 if old_string absent, 400 if empty), `PUT .../{file}/raw` (whole-file overwrite, 400 without "raw" key), `PUT /api/memory/persona/form` (onboarding step 1), `POST /api/memory/onboarding` (onboarding step 2 finish: stores Name deterministically + LLM-structures the free-text "about" box across identity/memory/persona via `topic_service.structure_onboarding_info`; falls back to raw-append to identity on LLM failure). Valid files: identity, memory, persona. |
| `dashboard.py` | `GET /api/dashboard/stats` — totals, mastered, average, weekly events/gains, top/weakest/slipping words. |

Conventions: raise `HTTPException` with clear detail; response models from `schemas.py`; no business logic here.
