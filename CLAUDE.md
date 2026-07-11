# Fluently (project dir: ENG) — English Proficiency Companion

**App name: Fluently** — use it in all user-facing surfaces (browser tab, UI copy, API title).

> **⚠️ CRITICAL INSTRUCTION — KEEP THIS FILE UP TO DATE ⚠️**
> Every single change that affects anything documented here — new files, deleted files,
> renamed modules, changed logic, new endpoints, schema changes, new env vars, scoring
> rule changes — MUST be reflected in this file in the same edit session. This file is
> the source of truth for the project structure. If you change code, update CLAUDE.md.

## ⚠️ HIERARCHICAL CONTEXT SYSTEM — HIGHEST-PRIORITY RULES ⚠️

Every folder where code is edited has a **context file** named after its camelCase path:
`frontend/frontendContext.md`, `backend/backendContext.md`, `backend/app/backendAppContext.md`,
`backend/app/services/backendAppServicesContext.md`, … Each one is the concise blueprint of
ITS OWN scope only: what files/subfolders it contains, one-liner purposes, key data flows,
and local editing rules — enough for any agent landing there to work without reading the
whole codebase.

**Current hierarchy:**
```
CLAUDE.md                                  ← top: whole-project truth (this file, most detail-dense)
├── frontend/frontendContext.md            ← detailed scope context
│   └── src/frontendSrcContext.md
│       └── components/frontendSrcComponentsContext.md
└── backend/backendContext.md              ← detailed scope context
    ├── app/backendAppContext.md
    │   ├── routers/backendAppRoutersContext.md
    │   └── services/backendAppServicesContext.md
    └── tests/backendTestsContext.md
```

**Rules (apply to EVERY edit, no exceptions):**
1. **Before editing** anything in a folder: read the context files on the path from CLAUDE.md
   down to that folder. That chain IS your context — do not skip levels.
2. **After editing — WAIT FOR USER VERIFICATION before updating context files.** When a
   change is user-requested (new feature, fix, behavior change), do NOT update context files
   right after coding: the user will test it first, and there may be several fix iterations.
   Only when the user confirms it works, update the context file of each touched folder.
   Update parent context files (and CLAUDE.md) ONLY if their one-line summaries or structure
   claims became wrong. Detail lives at the level it belongs to: deepest = most specific,
   each parent mentions children in ~1 line each.
   (Exception: purely structural changes the user won't test — e.g. file moves/renames —
   update context files immediately so they never point at wrong paths.)
3. **New folder with code** ⇒ create its context file immediately (camelCase-path naming) and
   add one line for it in the parent context file + the hierarchy tree above.
4. **Deleted/renamed files or folders** ⇒ fix every context file that mentions them.
5. Keep context files CONCISE — blueprints, not documentation dumps. No duplicated prose
   between levels; link down instead.
6. These files are the project's memory across agents and sessions. A stale context file is
   a bug of the highest severity — fixing it outranks the feature you came to build.

## What this is

A persona-driven chat companion that helps the user (an intermediate English speaker)
master specific vocabulary words/phrases. The user adds words; the system weaves them
naturally into conversations, judges how well the user produces them, and tracks a
0–100 proficiency score per word with a dashboard.

**Stack:** React (frontend, TBD) + FastAPI + LangChain 1.x (Python) + SQLite (local, for now — planned move to MongoDB Atlas for multi-device).

## Core concepts

1. **Persona** — the user assigns the system an identity at onboarding (name, relation
   e.g. best friend/mentor, personality, speaking style). Stored in `persona.md`.
2. **Memory files** (in `backend/data/`, editable by the agent via tools):
   - `identity.md` — facts about the user (who they are, patterns, recurring English mistakes)
   - `memory.md` — life events, people, ongoing situations
   - `persona.md` — who the system is + its own relationship memories
   Every entry is one line: `[i042] 2026-07-11 14:03 +05:30 | fact` — stable line IDs,
   local timestamp with UTC offset. Tools target line IDs, never fuzzy text.
3. **Scoring matrix** (single source of truth: `scoring_service.py`):
   perfect_unprompted +5 | perfect_prompted +3 | awkward +1 | wrong −2 | passive +0.5 |
   decay −1/week after 14 idle days (lazy, on dashboard reads) | manual = user-set delta.
   Daily cap: +10 per word per day. Score clamped 0–100.
4. **Judge** — after every user message, a cheap judge LLM (structured output) classifies
   usage of ALL tracked words in that message and applies scoring events. Never blocks chat.
5. **Dynamic system prompt** — assembled per LLM call in `prompt_builder.py`, order:
   persona → user identity → memories → target words & scores → time context (with UTC
   offset, so the persona knows it's night/dinner time) → category/topic → tool rules →
   behavior rules (crisp human-like messages, max 2–3 target words woven naturally).
6. **Target words** — picked per conversation by spaced repetition (lowest score, then
   least recently used), stored on the conversation row.
7. **Agent tools** (in-process LangChain tools, NOT a separate MCP server — extractable later):
   `memory_append/update/delete` (line-ID based), `search_conversations` (BM25 or regex
   over all past messages, flags: n_before/n_after context window, full_conversation,
   max_results; excludes the current conversation), and `adjust_word_score` (manual delta
   by word id — ids are shown in the system prompt; agent told to use sparingly since the
   judge scores normal usage automatically). Tool calls are stored verbatim on the
   assistant message (`tool_calls` JSON) for transparency but are not visible chat messages.

## Repository layout

```
ENG/
├── CLAUDE.md            ← this file (KEEP UPDATED)
├── .claude/agents/researcher.md   ← deep-research subagent (sonnet + web tools)
├── .claude/agents/tester.md       ← test-runner subagent (sonnet; reads this file, runs suite, reports)
├── frontend/            ← React app (BUILT — see "Frontend" below)
│   ├── package.json     Vite + React 19, Tailwind v4, motion, TanStack Query, lucide, sonner,
│   │                    react-markdown, Fontsource variable fonts. No router (state-based views).
│   ├── vite.config.js   react + @tailwindcss/vite plugins, port 5173
│   ├── Fluent App.dc.html / Fluent.dc.html / support.js  ← original design prototypes (reference only)
│   └── src/
│       ├── main.jsx         React root: QueryClientProvider + sonner Toaster + font imports
│       ├── index.css        Tailwind v4 @theme design tokens (colors/fonts/radii/shadows/keyframes)
│       ├── api.js           fetch wrapper, one function per backend endpoint (base localhost:8000)
│       ├── utils.js         time formatting, persona/identity name parsing from raw markdown
│       ├── hooks/useApi.js  TanStack Query hooks (health poll, conversations, messages, words, stats, memory)
│       └── components/
│           ├── Onboarding.jsx  2-step persona + user form
│           ├── Rail.jsx        left nav — EXACTLY 3 tabs: Chat, Words, Memory
│           ├── Chat.jsx        threads sidebar, topic cards, opener, messages (markdown), scoring chips, composer
│           ├── Words.jsx       stats cards, add+enrich, score bars, expandable details + event history
│           ├── Memory.jsx      3 RAW markdown editors (identity/memory/persona) with Save → PUT .../raw
│           └── Shared.jsx      PersonaAvatar, Spinner, loaders, error screen, ScoreBar
└── backend/
    ├── requirements.txt
    ├── .env.example     ← copy to .env and fill API keys
    ├── pytest.ini       ← live tests deselected by default (addopts -m "not live")
    ├── run_tests.py     ← one-shot concise test report (--live adds real-LLM smoke tests)
    ├── tests/           ← permanent suite: conftest (temp DB + mocked LLMs), test_memory,
    │                      test_words, test_scoring, test_conversations, test_chat,
    │                      test_dashboard, test_live_smoke (@pytest.mark.live)
    ├── data/            ← created at runtime: eng.db (SQLite) + the 3 memory .md files
    └── app/
        ├── main.py              FastAPI app, CORS, routers, startup (create tables + memory files)
        ├── config.py            pydantic-settings: keys, model choices, scoring constants
        ├── database.py          SQLAlchemy engine/session (SQLite)
        ├── models.py            Conversation, Message, Word, WordEvent
        ├── schemas.py           all Pydantic request/response models
        ├── prompts.py           ALL prompt templates (chat system, judge, topics, enrich, title, opener)
        ├── routers/
        │   ├── chat.py          POST /api/chat/{conversation_id} — full turn + judge scoring
        │   ├── conversations.py CRUD + topic suggestions + opener + POST /api/conversations/search
        │   ├── words.py         CRUD + LLM enrichment on add + manual adjust + event history
        │   ├── memory.py        read/append/update/delete memory lines + PUT persona/form (onboarding)
        │   └── dashboard.py     GET /api/dashboard/stats
        └── services/
            ├── llm_service.py      init_chat_model factory (openai | anthropic | google_genai)
            ├── prompt_builder.py   dynamic system prompt assembly
            ├── chat_service.py     manual tool-calling loop, history reconstruction, auto-title
            ├── judge_service.py    structured-output usage judging → scoring events
            ├── scoring_service.py  scoring matrix, daily cap, lazy decay, spaced-repetition picker
            ├── topic_service.py    topic suggestions + word enrichment
            ├── memory_service.py   line-ID markdown file engine
            ├── search_service.py   BM25/regex search with context windows
            └── agent_tools.py      LangChain @tool definitions (closure over db session)
```

## API surface

- `POST /api/conversations` — new chat; picks target words; returns topic suggestions (first LLM call of a new chat)
- `PATCH /api/conversations/{id}/category` — set topic after user picks one
- `POST /api/conversations/{id}/opener` — persona opens the chat itself (time/memory aware)
- `GET /api/conversations` / `GET .../{id}` / `GET .../{id}/messages` / `DELETE .../{id}`
- `POST /api/conversations/search` — BM25/regex search (same engine as the agent tool)
- `POST /api/chat/{conversation_id}` — send message, get assistant reply + scoring events
- `GET|POST|PUT|DELETE /api/words...` — list (applies decay), add (LLM-enriched), adjust score, events
- `GET|POST|PUT|DELETE /api/memory/{identity|memory|persona}...` — memory file management
- `PUT /api/memory/{file}/raw` — overwrite whole markdown file (UI's raw markdown editor)
- `PUT /api/memory/persona/form` — onboarding persona form
- `GET /api/dashboard/stats`, `GET /api/health`

## Chat turn flow (backend)

1. Store user message → 2. build system prompt → 3. rebuild LangChain message array from DB
(AIMessage.tool_calls + ToolMessage pairs reconstructed with original IDs — required by
providers) → 4. `bind_tools(...).invoke()` loop (max 6 iterations) executing tools →
5. store assistant message with `tool_calls` JSON → 6. auto-title after first exchange →
7. judge user message → scoring events returned in the response.

## Conventions & decisions

- LangChain 1.x: manual message-list + `bind_tools` loop (officially documented pattern);
  NOT `create_agent`/checkpointers — we own persistence in SQLite.
- Gemini must use explicit provider string `google_genai` (bare `gemini-*` infers Vertex).
- Env keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` (see `.env.example`).
- LLM failures in judge/topics/enrichment/title are swallowed — they must never break chat.
- Sync SQLAlchemy + sync routes (FastAPI threadpools them). Streaming/SSE is a planned
  upgrade (pattern documented in research: astream + StreamingResponse).
- No summarization/compaction of history yet; no vector search yet (BM25 only) — both planned.
- Current default models (.env): `google_genai` / `gemini-3.1-flash-lite-preview` for chat,
  judge, and utility (user has a Gemini key). Model choice is config-only — change .env anytime.
- Gemini quirk: `AIMessage.content` can be a LIST of content blocks, not a str — always
  flatten via `chat_service._flatten_content` before treating replies as text.

## Testing (run after EVERY meaningful backend change)

```
cd backend
.venv\Scripts\python run_tests.py           # fast suite, LLMs mocked (~5s, free)
.venv\Scripts\python run_tests.py --live    # + real-provider smoke tests (uses .env models, costs quota)
```
- Prints a per-area PASS/FAIL report and writes tests/last_report.txt. Exit code 1 on failure.
- Tests use a fresh temp SQLite DB + temp memory files per run — real data/ is never touched.
- conftest.py mocks all LLM factories unless a test is marked `@pytest.mark.live`.
- Every new API/feature MUST get tests in the same change: happy path, error paths, side effects.
- The `tester` subagent (.claude/agents/tester.md) can run the suite and diagnose failures;
  it reads this file for context first.

## Frontend (built)

React 19 + Vite, JavaScript. Run: `cd frontend && npm install && npm run dev` (http://localhost:5173;
backend must be on :8000). `npm run build` must pass after every frontend change.
Behavior notes:
- Onboarding shows when persona.md has no `Name:` line (detection in App.jsx via parsePersonaName).
- Scoring chips are session-only (from POST /api/chat response), not shown for reloaded history.
- After each chat turn the app invalidates words/dashboard/memory queries (agent may have changed them).
- Thread delete + word remove use inline two-step confirm (click → "sure?" for 2.5s), no modals.
- Chat sends invalidate conversations (auto-title updates in sidebar).

## Running the backend

```
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   (fill in at least one provider key)
uvicorn app.main:app --reload --port 8000
```
