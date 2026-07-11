# backendAppContext.md — scope: `backend/app/`

The FastAPI application package. Parent: [../backendContext.md](../backendContext.md).
Children: [routers/backendAppRoutersContext.md](routers/backendAppRoutersContext.md), [services/backendAppServicesContext.md](services/backendAppServicesContext.md).

## Files

| File | Purpose |
|---|---|
| `main.py` | FastAPI app: CORS (localhost:5173/3000), includes all routers. Startup: `mongo.ping()` (fail fast if Atlas unreachable) → `mongo.ensure_indexes()` → `memory_service.ensure_files()` (bootstrap the 3 memory-file docs for the default user). `GET /api/health`. |
| `config.py` | pydantic-settings `Settings` (reads `.env`): provider keys, model choices per role (default/judge/utility), scoring constants (matrix deltas, daily cap, decay), `target_words_per_conversation=3`, `user_timezone` (default `Asia/Kolkata` — drives ALL temporal reasoning in prompts), `mongodb_uri`, `mongodb_db` (default `fluently`), `data_path`. Import `settings` singleton. |
| `mongo.py` | MongoDB connection layer (PyMongo, sync). Single shared `MongoClient`; collection accessors (`conversations_col`/`messages_col`/`words_col`/`word_events_col`/`memory_files_col`); `ping()`, `ensure_indexes()` (per-user-unique words `uq_user_text`, conv/message/event/memory indexes), `DEFAULT_USER_ID = "default"` sentinel (single-user until OAuth). |
| `repo.py` | **THE single data-access layer — the ONLY module that touches MongoDB.** Every service/router calls these functions (never pymongo directly). Swapping databases later = rewrite this file only. All functions take `user_id` (defaults to the sentinel) so OAuth scoping is an already-present filter. IDs in/out are ObjectId hex strings. Covers words/events/conversations/messages/memory-files CRUD + dashboard aggregations + search loads + purge. |
| `models.py` | PLAIN document classes (NOT ORM): `Conversation`, `Message`, `Word`, `WordEvent` — each with `to_doc()`/`from_doc()`, a string `id` (ObjectId hex), and a `user_id`. Relationship-y fields (`conversation.messages`, `word.events`) are populated on demand by `repo`, not stored in the doc. Same fields as before (Word incl. `note` = user's memory hook; WordEvent `message_id` links an event to the causing user message). |
| `schemas.py` | All Pydantic request/response models. **All ids are `str`** (ObjectId hex), not int — `WordOut.id`, `ConversationOut.id`/`target_word_ids`, `MessageOut.id`/`conversation_id`, `WordEventOut.id`/`word_id`/`conversation_id`/`message_id`, `SearchRequest.conversation_id`, `SearchHit` ids. `WordOut` includes `note`; `WordNoteUpdate` (PUT note body). `WordEventOut` carries optional `word_text`. `MessageOut` carries `word_events` (per-message scoring events, populated by GET .../messages). Memory: `MemoryLineOut` (text only, no id/timestamp), `MemoryAppend`, `MemoryEdit` (old_string/new_string/replace_all), `OnboardingInfo`/`OnboardingResult`. |
| `prompts.py` | ALL prompt templates: `CHAT_SYSTEM_TEMPLATE` (dynamic blocks — see chat turn flow below), `JUDGE_SYSTEM`, `TOPICS_SYSTEM`, `WORD_ENRICH_SYSTEM`, `ONBOARDING_STRUCTURE_SYSTEM`, `TITLE_SYSTEM`, `OPENER_INSTRUCTION`, `PERSONA_FALLBACK`. Edit prompts HERE only. Tool arg descriptions in `agent_tools.py` are part of the effective prompt too (tool schemas are model-visible) — keep them consistent with the rules stated here. |

## Data flow (one chat turn)
`routers/chat.py` → `services/chat_service.run_agent_turn(conversation, user_content, ...)` (store user msg via `repo` → `prompt_builder` system prompt → rebuild history incl. tool calls → bind_tools invoke loop ≤6 iters → store assistant msg + tool_calls JSON → auto-title) → `services/judge_service.judge_user_message(conversation_id, user_message_id)` (structured output → `scoring_service.apply_event`) → response with scoring_events. No DB session is threaded through — all persistence goes through `repo` (Mongo).

## Storage note
MongoDB Atlas (via `mongo.py` + `repo.py`); NO SQLite/SQLAlchemy anywhere. The 3 memory markdown files are documents in the `memory_files` collection (read-modify-write of the whole string), not on-disk files. Every document carries `user_id` (single-user sentinel now; OAuth-ready).
