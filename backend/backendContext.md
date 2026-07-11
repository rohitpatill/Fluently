# backendContext.md — scope: `backend/`

FastAPI + LangChain 1.x (Python 3.10, venv at `.venv/`) + MongoDB Atlas (PyMongo, sync). Serves the ENG API on :8000.
Parent: [../CLAUDE.md](../CLAUDE.md). Children: [app/backendAppContext.md](app/backendAppContext.md), [tests/backendTestsContext.md](tests/backendTestsContext.md).

## Layout

| Item | What it is |
|---|---|
| `app/` | All application code (FastAPI app, routers, services, models). See child context file. |
| `tests/` | Permanent pytest suite, LLMs mocked by default. See child context file. |
| `data/` | Legacy SQLite `eng.db` + old `.md` files may still sit here as a BACKUP (pre-migration). The app no longer reads/writes them — all data lives in Mongo now. `DATA_DIR` kept only for compatibility. |
| `import_sqlite_to_mongo.py` | One-time migration script: copies `data/eng.db` + the 3 on-disk memory files into Mongo, remapping integer ids → ObjectIds and rewriting all cross-references. `--commit` to write, `--wipe` to clear the target user first, `--user` to target a user_id. Dry-run by default. |
| `requirements.txt` | Pinned-ish deps: fastapi, **pymongo, dnspython**, langchain (+openai/anthropic/google-genai), rank-bm25, pytest, httpx. (SQLAlchemy removed.) |
| `.env` / `.env.example` | Provider keys + model choices (currently google_genai / gemini-3.1-flash-lite-preview for all three roles) + **`MONGODB_URI`** (SRV string incl. `/fluently` db name) + **`MONGODB_DB`** + DATA_DIR. `.env.example` uses a PLACEHOLDER uri (never the real password). Config-only model switching. |
| `pytest.ini` | `addopts -m "not live"` — live tests deselected by default. |
| `run_tests.py` | One-shot concise report runner. `--live` adds real-LLM smoke tests. Writes `tests/last_report.txt`. |

## Rules for editing here
- Run `.venv\Scripts\python run_tests.py` when the change touches actual LOGIC (services, routers, schemas, models, scoring). Use judgment for prompt-only edits (`prompts.py` wording, tool descriptions) — if no Python logic/schema changed, running the suite verifies nothing new (see CLAUDE.md's testing-judgment note).
- Every new API/feature gets tests in the same change.
- LLM failures in judge/topics/enrichment/title/onboarding-structuring must be swallowed (never break chat).
- Scoring rules live ONLY in `app/services/scoring_service.py` (single source of truth).
- ALL database access goes through `app/repo.py` (the single Mongo data layer) — services/routers never import pymongo. Swapping databases later = rewrite `repo.py` + `mongo.py` only.
- Every doc carries a `user_id` (single-user sentinel `"default"` now) — the OAuth-ready filter. Words are unique per `(user_id, text)`, not globally.
- Running the suite requires network + a valid `MONGODB_URI` (mocked tests still hit a real `_test` DB on Atlas).
- After any change, update the context file of the folder you edited (+ parents if their summaries changed).
