# backendAppRoutersContext.md — scope: `backend/app/routers/`

HTTP layer only — validation + delegation to services/`repo`. Sync `def` routes (FastAPI threadpools them).
Parent: [../backendAppContext.md](../backendAppContext.md).
Routes call `repo` / services directly (no `db` session). Every data route resolves the real user via `user_id: str = Depends(get_current_user)` (from `app/deps.py`) — no more hardcoded `DEFAULT_USER_ID`; a missing/invalid session ⇒ 401. Path ids are strings (ObjectId hex); an invalid/absent id yields 404.

| File | Endpoints |
|---|---|
| `auth.py` | Google OAuth + session (prefix `/api/auth`). `GET /google/login` (sets a signed HttpOnly state+nonce cookie, 307 → Google consent). `GET /google/callback` (verify state/CSRF → exchange code → verify ID token → `upsert_user_from_google`; first-ever user adopts `default` data; bootstraps the user's memory files; sets the JWT session cookie; redirects to `frontend_url`; any failure → `frontend_url/?auth_error=1`, no session set). `GET /me` (current profile + `has_persona`; 401 if unauthenticated). `POST /logout` (clears the session cookie). |
| `chat.py` | `POST /api/chat/{conversation_id}` — full chat turn; returns user_message, assistant_message (with tool_calls), scoring_events. |
| `conversations.py` | `POST /api/conversations` (picks target words via spaced repetition, optional topic suggestions), `GET` list/detail, `GET .../{id}/messages` (each message carries `tool_calls`; USER messages also carry `word_events` — that message's scoring events with resolved `word_text` — so scoring chips + Developer-mode tool calls survive a refresh), `PATCH .../category` (query param), `POST .../opener` (400 if messages exist), `DELETE`, `POST /api/conversations/search` (BM25/regex, window flags). |
| `words.py` | `GET /api/words` (applies lazy decay), `POST` (409 duplicate, LLM enrichment on add), `GET/DELETE /{id}`, `PUT /{id}/note` (user's own memory-hook note; trims, empty clears), `POST /{id}/adjust` (manual event), `GET /{id}/events` (last 100). |
| `memory.py` | `GET /api/memory/{file}` (raw + parsed lines, no ids/timestamps), `POST .../lines` (append), `POST .../edit` (old_string→new_string, empty new_string deletes; 404 if old_string absent, 400 if empty), `PUT .../{file}/raw` (whole-file overwrite, 400 without "raw" key), `PUT /api/memory/persona/form` (onboarding step 1), `POST /api/memory/onboarding` (onboarding step 2 finish: stores Name deterministically + LLM-structures the free-text "about" box across identity/memory/persona via `topic_service.structure_onboarding_info`; falls back to raw-append to identity on LLM failure). Valid files: identity, memory, persona. |
| `dashboard.py` | `GET /api/dashboard/stats` — totals, mastered, average, weekly events/gains, top/weakest/slipping words (via `repo` aggregations). |
| `settings.py` | Data-management HARD deletes: `DELETE /api/settings/conversations` (purge conversations+messages, keep words/memories), `DELETE /api/settings/memories` (reset identity+memory, keep persona), `POST /api/settings/purge-all` (`{keep_words}` — nuke conversations+3 memory files, optionally words+events). All via `repo.purge_*` + `memory_service.reset_file`. |

Conventions: raise `HTTPException` with clear detail; response models from `schemas.py`; no business logic here.
