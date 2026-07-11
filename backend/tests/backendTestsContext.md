# backendTestsContext.md — scope: `backend/tests/`

Permanent pytest suite. Parent: [../backendContext.md](../backendContext.md).
Run: `.venv\Scripts\python run_tests.py` (fast, mocked) / `--live` (real provider from .env).

| File | Covers |
|---|---|
| `conftest.py` | Temp SQLite DB + temp memory files per run (env vars set BEFORE app import — real data/ never touched). `fresh_db` autouse fixture. `FakeChatModel` (scripted AIMessage responses, records invocations), `FakeStructuredFactory/Model` (canned structured outputs). `mock_llms` autouse fixture patches all LLM factories unless test marked `@pytest.mark.live`. |
| `test_memory.py` | Persona form, line append/update/delete, ID stability/no-reuse, multiline collapse, raw save round-trip + 400/404. |
| `test_words.py` | Add/list, 409 duplicate, 400/422 invalid, manual adjust + clamping, events, delete. |
| `test_scoring.py` | Matrix deltas, zero floor, daily cap (+manual bypass), times_used/last_used semantics, decay (idle threshold, idempotent), spaced-repetition picker ordering. |
| `test_conversations.py` | Create picks 3 targets, mocked topics, category patch, CRUD, search: bm25 window, regex, full_conversation, empty. |
| `test_chat.py` | Basic turn, 400/404, tool loop + stored tool_calls transparency, history reconstruction (AIMessage+ToolMessage pair with original id), judge events applied, judge failure swallowed, auto-title, agent adjust_word_score (+unknown id), opener (+400 when non-empty). |
| `test_dashboard.py` | Health, stats aggregation. |
| `test_live_smoke.py` | `@pytest.mark.live`: real enrichment, real chat turn + auto-title, real judge scoring, real topics. Costs quota. |
| `last_report.txt` | Latest run_tests.py report (generated). |

Patterns: patch LLM factories on the CONSUMING module (`chat_service.get_chat_model`, `judge_service.get_judge_model`, `topic_service.get_utility_model`). Every new API/feature: happy path + error paths + side effects, same change.
