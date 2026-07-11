# backendAppContext.md — scope: `backend/app/`

The FastAPI application package. Parent: [../backendContext.md](../backendContext.md).
Children: [routers/backendAppRoutersContext.md](routers/backendAppRoutersContext.md), [services/backendAppServicesContext.md](services/backendAppServicesContext.md).

## Files

| File | Purpose |
|---|---|
| `main.py` | FastAPI app: CORS (localhost:5173/3000), includes all routers, startup creates DB tables + memory files. `GET /api/health`. |
| `config.py` | pydantic-settings `Settings` (reads `.env`): provider keys, model choices per role (default/judge/utility), scoring constants (matrix deltas, daily cap, decay), `target_words_per_conversation=3`, `user_timezone` (default `Asia/Kolkata` — drives ALL temporal reasoning in prompts), `data_path`. Import `settings` singleton. |
| `database.py` | SQLAlchemy engine/SessionLocal/Base + `get_db` dependency. SQLite via DATABASE_URL. |
| `models.py` | ORM: `Conversation` (title, category, target_word_ids JSON), `Message` (conversation_id, seq, role, content, tool_calls JSON), `Word` (text, kind, meaning, examples, collocations, register_notes, score, times_used, last_used_at, last_decay_at), `WordEvent` (score-change audit log). |
| `schemas.py` | All Pydantic request/response models for the API. Memory: `MemoryLineOut` (text only, no id/timestamp), `MemoryAppend`, `MemoryEdit` (old_string/new_string/replace_all), `OnboardingInfo`/`OnboardingResult`. |
| `prompts.py` | ALL prompt templates: `CHAT_SYSTEM_TEMPLATE` (dynamic blocks — see chat turn flow below), `JUDGE_SYSTEM`, `TOPICS_SYSTEM`, `WORD_ENRICH_SYSTEM`, `ONBOARDING_STRUCTURE_SYSTEM`, `TITLE_SYSTEM`, `OPENER_INSTRUCTION`, `PERSONA_FALLBACK`. Edit prompts HERE only. Tool arg descriptions in `agent_tools.py` are part of the effective prompt too (tool schemas are model-visible) — keep them consistent with the rules stated here. |

## Data flow (one chat turn)
`routers/chat.py` → `services/chat_service.run_agent_turn` (store user msg → `prompt_builder` system prompt → rebuild history incl. tool calls → bind_tools invoke loop ≤6 iters → store assistant msg + tool_calls JSON → auto-title) → `services/judge_service.judge_user_message` (structured output → `scoring_service.apply_event`) → response with scoring_events.
