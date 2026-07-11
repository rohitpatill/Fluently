# backendTestsContext.md — scope: `backend/tests/`

Permanent pytest suite. Parent: [../backendContext.md](../backendContext.md).
Run: `.venv\Scripts\python run_tests.py` (fast, mocked) / `--live` (real provider from .env).

| File | Covers |
|---|---|
| `conftest.py` | Temp SQLite DB + temp memory files per run (env vars set BEFORE app import — real data/ never touched). `fresh_db` autouse fixture. `FakeChatModel` (scripted AIMessage responses, records invocations), `FakeStructuredFactory/Model` (canned structured outputs, keyed by schema class — includes `topic_service.OnboardingFacts`). `mock_llms` autouse fixture patches all LLM factories unless test marked `@pytest.mark.live`. |
| `test_memory.py` | Free-text append/edit (no ids/stamps — `old_string`/`new_string`/`replace_all`), verbatim storage, entry-count ignores headings, persona form + relationship-memory preservation, raw save round-trip + 400/404, onboarding endpoint (LLM-structured multi-file distribution + name-only no-LLM path). |
| `test_words.py` | Add/list, 409 duplicate, 400/422 invalid, manual adjust + clamping, events, delete, personal note (PUT set/trim/clear + 404) and its appearance in the chat prompt's target-words block. |
| `test_scoring.py` | Matrix deltas, zero floor, daily cap (+manual bypass), times_used/last_used semantics, decay (idle threshold, idempotent), spaced-repetition picker ordering. |
| `test_conversations.py` | Create picks 3 targets, mocked topics, category patch, CRUD, search: bm25 window, regex, full_conversation, empty. |
| `test_chat.py` | Basic turn, 400/404, tool loop + stored tool_calls transparency (`memory_update` action='append'), `memory_update` tolerates a `.md` suffix on `file`, GET .../messages returns persisted `word_events` on the user message (with word_text), history reconstruction (AIMessage+ToolMessage pair with original id), judge events applied, judge failure swallowed, auto-title, agent adjust_word_score (+unknown id), opener (+400 when non-empty). |
| `test_dashboard.py` | Health, stats aggregation. |
| `test_settings.py` | Hard-delete endpoints: purge conversations (keeps words/memories), purge memories (keeps persona/words/conversations), purge-all (keep_words true/false), idempotency. |
| `test_live_smoke.py` | `@pytest.mark.live`: real enrichment, real chat turn + auto-title, real judge scoring, real topics. Costs quota. |
| `last_report.txt` | Latest run_tests.py report (generated). |

Patterns: patch LLM factories on the CONSUMING module (`chat_service.get_chat_model`, `judge_service.get_judge_model`, `topic_service.get_utility_model`). Every new API/feature: happy path + error paths + side effects, same change.
