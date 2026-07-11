# backendContext.md — scope: `backend/`

FastAPI + LangChain 1.x (Python 3.10, venv at `.venv/`) + SQLite. Serves the ENG API on :8000.
Parent: [../CLAUDE.md](../CLAUDE.md). Children: [app/backendAppContext.md](app/backendAppContext.md), [tests/backendTestsContext.md](tests/backendTestsContext.md).

## Layout

| Item | What it is |
|---|---|
| `app/` | All application code (FastAPI app, routers, services, models). See child context file. |
| `tests/` | Permanent pytest suite, LLMs mocked by default. See child context file. |
| `data/` | Runtime-created: `eng.db` (SQLite) + `identity.md` / `memory.md` / `persona.md`. Gitignored. NEVER edit manually while server runs. |
| `requirements.txt` | Pinned-ish deps: fastapi, sqlalchemy, langchain (+openai/anthropic/google-genai), rank-bm25, pytest, httpx. |
| `.env` / `.env.example` | Provider keys + model choices (currently google_genai / gemini-3.1-flash-lite-preview for all three roles) + DATABASE_URL + DATA_DIR. Config-only model switching. |
| `pytest.ini` | `addopts -m "not live"` — live tests deselected by default. |
| `run_tests.py` | One-shot concise report runner. `--live` adds real-LLM smoke tests. Writes `tests/last_report.txt`. |

## Rules for editing here
- Run `.venv\Scripts\python run_tests.py` when the change touches actual LOGIC (services, routers, schemas, models, scoring). Use judgment for prompt-only edits (`prompts.py` wording, tool descriptions) — if no Python logic/schema changed, running the suite verifies nothing new (see CLAUDE.md's testing-judgment note).
- Every new API/feature gets tests in the same change.
- LLM failures in judge/topics/enrichment/title/onboarding-structuring must be swallowed (never break chat).
- Scoring rules live ONLY in `app/services/scoring_service.py` (single source of truth).
- After any change, update the context file of the folder you edited (+ parents if their summaries changed).
