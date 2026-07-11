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
0. **Starting a new session:** read this file first, then — before touching any folder — read
   the context-file chain down to it (rule 1). Do this even if the task sounds small; the chain
   is what tells you the CURRENT shape of the code, which may have moved since your training.
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

**Stack:** React (frontend) + FastAPI + LangChain 1.x (Python) + MongoDB Atlas (cloud, via PyMongo sync). All DB access is behind a single swappable data layer (`backend/app/repo.py`). **Multi-user via Google OAuth** ("Continue with Google" only): every stored document carries a `user_id` = a real user's id, and every request is scoped to the logged-in user. The `"default"` sentinel now only tags un-adopted legacy (pre-OAuth) data. **Bring-your-own-key:** each user supplies their OWN Google Gemini API key (stored encrypted) and picks a model tier — the app no longer uses a shared server-side key for real users.

## Core concepts

1. **Persona** — the user assigns the system an identity at onboarding (name, relation
   e.g. best friend/mentor, personality, speaking style). Stored in `persona.md`.
2. **Memory files** (documents in the Mongo `memory_files` collection — one per (user, file);
   NOT on-disk files anymore — editable by the agent via tools):
   - `identity` — timeless facts about the user (who they are, background, personality,
     how they talk, recurring English mistakes) — NO dates, NO name repeated per entry (the
     user is the implied subject; only other people are named).
   - `memory` — the user's life in motion: events, people, relationships, plans, deadlines.
     Time-bound entries carry an ABSOLUTE date written by the agent inside the text itself
     (e.g. "Demo on 2026-07-17.") — never "tomorrow"/"next week".
   - `persona` — what the persona remembers about ITS relationship with the user (shared
     jokes, promises, moments), written first-person, never repeating its own name.
   Each doc holds the whole markdown string. Pure free-text — NO line IDs, NO machine-added
   stamps. The agent writes exactly what should be stored; the single `memory_update(file, action)`
   tool edits by `action='append'` (new text) or `action='edit'` (`old_string`→`new_string`,
   empty deletes) — a read-modify-write of the whole string (read full doc → mutate → write back),
   since the whole file is always in the prompt.
3. **Scoring matrix** (single source of truth: `scoring_service.py`):
   perfect_unprompted +5 | perfect_prompted +3 | awkward +1 | wrong −2 | passive +0.5 |
   decay −1/week after 14 idle days (lazy, on dashboard reads) | manual = user-set delta.
   Daily cap: +10 per word per day. Score clamped 0–100.
4. **Judge** — after every user message, a cheap judge LLM (structured output) classifies
   usage of ALL tracked words in that message and applies scoring events. Never blocks chat.
5. **Dynamic system prompt** — assembled per LLM call in `prompt_builder.py`, order (deliberate
   for model attention): persona → user identity → user's life/memories → vocabulary practice
   (the #1 hidden mission — 5-step per-turn strategy: pick lowest-scored fitting targets, set up
   more than use, react to correct/wrong usage, model cleaner English, never reveal the system)
   → TIME block (date/weekday/exact time+AM/PM/part-of-day + yesterday/tomorrow/this-week
   enumerated/last-next week/this-next month, computed in `user_timezone` — explicitly told NOT
   to infer season/weather from the month) → category/topic → memory curation (the #2 job, every
   turn: notice new/changed/unchanged facts, append vs. edit, subject-free style, absolute dates
   only for time-bound facts) → other tools → behavior rules (crisp, human-like, silent
   bookkeeping, spine not sycophancy, mirror the user).
6. **Target words** — picked per conversation by spaced repetition (lowest score, then
   least recently used), stored on the conversation row. Each `Word` also has an optional user
   `note` (their own memory hook — where they saw it, a mnemonic); it's user-authored only (judge/
   agent never write it) and is fed into the target-words prompt block so the persona can lean on
   that association when setting the word up.
7. **Agent tools** (in-process LangChain tools, NOT a separate MCP server — extractable later):
   `memory_update(file, action, ...)` — ONE tool, `action='append'` (text) or `'edit'`
   (old_string→new_string, empty deletes); `file` is the bare name `identity|memory|persona`
   (the tool defensively strips a stray `.md` via `memory_service.normalize_file`); no read tool
   (whole file is always in the prompt);
   `search_conversations` (BM25 or regex over all past messages, flags: n_before/n_after context
   window, full_conversation, max_results; excludes the current conversation); `adjust_word_score`
   (manual delta by word id — ids are shown in the system prompt; agent told to use sparingly
   since the judge scores normal usage automatically). Tool calls are stored verbatim on the
   assistant message (`tool_calls` JSON) for transparency, and surfaced under each reply in the
   UI's Developer mode (Settings toggle, off by default) — but are not visible chat messages.
   Tool arg descriptions are model-visible (part of the effective prompt) — keep them aligned
   with `prompts.py`'s rules (subject-free style, absolute-dates-only-when-time-bound, etc.).
8. **Onboarding structuring** — the onboarding "about you" free-text box is NOT pasted raw. One
   utility LLM call (`topic_service.structure_onboarding_info`) distills it into clean entries
   distributed across identity/memory/persona (see `POST /api/memory/onboarding`). Falls back to
   raw-append on LLM failure so onboarding never breaks. The persona form's short discrete fields
   (name/relation/personality) and the raw markdown editor's manual edits are NOT LLM-structured
   — only the free-text onboarding box gets this treatment.
9. **Auth (Google OAuth, "Continue with Google" only)** — no passwords. Server-side OAuth 2.0
   Authorization Code flow: Google tokens never reach the browser; we read identity (sub/email/
   name/picture) from the verified ID token and store NO Google tokens. A `users` collection keys
   each Google `sub` → an internal `user_id` (the user doc's own `_id`), which flows into every
   `repo`/service call. Session = a stateless signed JWT (PyJWT HS256) in an HttpOnly cookie
   (`SameSite=Lax`, `Secure` auto-on over https). CSRF/replay guarded by a short-lived signed
   state+nonce cookie during the handshake. `app/deps.py::get_current_user` resolves the cookie →
   `user_id` for every router. **First** Google user to log in ADOPTS the legacy `"default"` data
   (one-time); everyone else starts fresh (per-user onboarding). All redirect/session config is
   `.env`-driven (`OAUTH_REDIRECT_BASE`, `FRONTEND_URL`, secrets, `SESSION_MAX_AGE_DAYS`) so
   production is a config change, not a code change. Server-side session revocation is a future
   additive step (add a `token_version` claim) — not built yet. See `docs/oauth-handoff.md` for
   the original decisions.
10. **Bring-your-own-key + model tiers (BUILT)** — every user brings their OWN Google Gemini
    API key and picks a **tier** that governs EVERY LLM call for them (chat + judge + utility):
    **Swift** = `gemini-3.1-flash-lite` (cheap, everyday) | **Sage** = `gemini-3.5-flash`
    (sharper, pricier). The tier catalogue (names/model ids/taglines/prices) is the single source
    of truth in `config.MODEL_TIERS`. The key is stored **encrypted at rest** (Fernet, via
    `crypto_service.py`; master `ENCRYPTION_KEY` lives ONLY in `.env` — a DB leak yields useless
    ciphertext). `model_service.resolve_for_user(user_id)` decrypts the key + maps tier→model per
    request; `verify_key` makes one throwaway call to validate a key before storing it. Configured
    at onboarding step 3 ("How smart should I be?") and changeable anytime in Settings' Brain card.
    A user with no key is GATED: LLM routes return 403 (`deps.require_model_configured`) and the
    frontend forces the brain step. The app's own `.env` provider keys are no longer used for real
    users. (Encrypted API-key storage was the old "Phase 3" — now built.)

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
│       ├── api.js           fetch wrapper (credentials:'include' for the session cookie), one function per backend endpoint (base localhost:8000); auth: getMe/logout/loginWithGoogle; model: getModelTiers/getModelStatus/setModelKey/setModelTier
│       ├── utils.js         time formatting, persona/identity name parsing from raw markdown
│       ├── hooks/useApi.js  TanStack Query hooks (health poll, me/auth [+has_key/tier], conversations, messages, words, stats, memory, model tiers)
│       ├── hooks/useDevMode.js localStorage-backed Developer-mode toggle (client-only, off by default)
│       └── components/
│           ├── Login.jsx       auth gate — single "Continue with Google" screen (Fluently-styled)
│           ├── Onboarding.jsx  3-step flow: persona → about you → BrainStep (key + Swift/Sage tier); exports BrainStep (reused by App's model gate)
│           ├── Rail.jsx        responsive nav — desktop left rail; mobile bottom bar; 3 main tabs + Settings
│           ├── Chat.jsx        desktop threads sidebar / mobile slide-out conversations drawer, topic cards, opener, messages, scoring chips, dev tools, composer
│           ├── Words.jsx       stats cards, add+enrich, score bars, responsive rows, expandable detail with mobile-visible note edit
│           ├── Memory.jsx      3 RAW markdown editors (identity/memory/persona) with Save → PUT .../raw
│           ├── SettingsView.jsx Account profile + Log out, Brain (Swift/Sage switch + replace-key), Developer-mode toggle, data-management hard-delete cards
│           └── Shared.jsx      PersonaAvatar, Spinner, loaders, error screen, ScoreBar, TierCard (Swift/Sage brain card)
└── backend/
    ├── requirements.txt  (+ google-auth, PyJWT, itsdangerous for OAuth/session; cryptography for key encryption)
    ├── .env.example     ← copy to .env and fill ENCRYPTION_KEY + Google OAuth client id/secret + session secrets + MONGODB_URI
    ├── pytest.ini       ← live tests deselected by default (addopts -m "not live")
    ├── run_tests.py     ← AREA-SELECTABLE concise test report: `run_tests.py [area...]` (no args = all; --list; --live)
    ├── tests/           ← permanent suite: conftest (isolated Mongo <db>_test + mocked LLMs + mocked resolve_for_user;
    │                      seeds a key+tier so gated routes pass; ENCRYPTION_KEY from .env, never hardcoded;
    │                      `client` authed as a fixed user, `anon_client` for the real auth flow),
    │                      test_auth (OAuth flow + first-user adoption + data isolation),
    │                      test_memory, test_words, test_scoring, test_conversations, test_chat,
    │                      test_model (BYO key/tiers/verify+encrypt/gate),
    │                      test_dashboard, test_settings, test_mongo_connection (@live),
    │                      test_live_smoke (@pytest.mark.live)
    ├── import_sqlite_to_mongo.py  ← one-time SQLite→Mongo migration script (id remap; --commit/--wipe)
    ├── data/            ← legacy pre-migration BACKUP only (old eng.db + .md files); app no longer uses it
    └── app/
        ├── main.py              FastAPI app, CORS (credentials on), routers (incl. auth, model), startup (mongo ping → ensure_indexes; memory bootstrap is per-user on login)
        ├── config.py            pydantic-settings: encryption_key, legacy model choices, scoring constants, user_timezone, mongodb_uri/db, Google-OAuth + session settings; MODEL_TIERS (Swift/Sage source of truth) + tier_config
        ├── mongo.py             MongoDB connection (PyMongo), collection accessors (incl. users_col), ensure_indexes (incl. uq_google_sub), DEFAULT_USER_ID
        ├── repo.py              THE single data layer — only module touching Mongo (swap DB = rewrite here); incl. user upsert + first-login adoption + set_user_key/set_user_tier/clear_user_model
        ├── models.py            PLAIN doc classes (to_doc/from_doc, str ids): Conversation, Message (tool_calls), Word (incl. user note), WordEvent (incl. message_id), User (google_sub/email/name/picture/encrypted_api_key/model_tier)
        ├── deps.py              FastAPI auth deps: get_current_user (cookie→user_id, 401 else), get_current_user_obj (→ profile), require_model_configured (403 if no key/tier — LLM routes)
        ├── schemas.py           all Pydantic request/response models (MeResponse [+has_key/tier], ModelTierOut/ModelStatusOut/SetKeyRequest/SetTierRequest)
        ├── prompts.py           ALL prompt templates (chat system, judge, topics, enrich, onboarding-structure, title, opener)
        ├── routers/
        │   ├── auth.py          Google OAuth + session: /api/auth/google/login + /callback, /me, /logout
        │   ├── model.py         BYO-key model config: GET /tiers + /status, POST /key (verify+encrypt+store), PUT /tier
        │   ├── chat.py          POST /api/chat/{conversation_id} — full turn + judge scoring (gated: require_model_configured)
        │   ├── conversations.py CRUD + topic suggestions + opener + POST /api/conversations/search (create/opener gated)
        │   ├── words.py         CRUD + LLM enrichment on add + manual adjust + event history + PUT /note (user hook)
        │   ├── memory.py        read/append/edit (old_string->new_string) memory files + PUT persona/form + POST onboarding (LLM-structured)
        │   ├── settings.py      data-management hard deletes (purge-all full-wipe also clears model key+tier)
        │   └── dashboard.py     GET /api/dashboard/stats
        └── services/
            ├── auth_service.py     Google OAuth flow + JWT session (build auth url, code exchange, ID-token verify, signed state/nonce, mint/decode session JWT)
            ├── crypto_service.py   Fernet encrypt/decrypt for users' API keys (ENCRYPTION_KEY from .env; never in DB)
            ├── model_service.py    per-user model resolution: tiers_public, resolve_for_user (decrypt+map tier→model), verify_key
            ├── llm_service.py      key-aware init_chat_model factory (provider, model, api_key) — no os.environ mutation
            ├── prompt_builder.py   dynamic system prompt assembly
            ├── chat_service.py     manual tool-calling loop, history reconstruction, auto-title; resolves per-user model
            ├── judge_service.py    structured-output usage judging → scoring events; resolves per-user model
            ├── scoring_service.py  scoring matrix, daily cap, lazy decay, spaced-repetition picker
            ├── topic_service.py    topic suggestions + word enrichment + onboarding structuring; all take user_id + resolve model
            ├── memory_service.py   free-text markdown engine over the Mongo memory_files collection (no ids/stamps; normalize_file tolerates .md)
            ├── search_service.py   BM25/regex search (ranking in Python) over Mongo-loaded messages, context windows
            └── agent_tools.py      LangChain @tool definitions (closure over user_id, not a db session)
```

## API surface

- **Auth:** `GET /api/auth/google/login` (→ Google consent), `GET /api/auth/google/callback` (verify → session cookie → redirect to frontend; failure → `frontend_url/?auth_error=1`), `GET /api/auth/me` (profile + `has_persona` + `has_key`/`tier`; 401 if unauthenticated), `POST /api/auth/logout`. Every OTHER endpoint below requires the session cookie (401 without it) and is scoped to that user.
- **Model (BYO key):** `GET /api/model/tiers` (Swift/Sage catalogue), `GET /api/model/status` (`{has_key, tier}`, never the key), `POST /api/model/key` (`{api_key, tier}` → verify → encrypt → store; 400 on bad key), `PUT /api/model/tier` (`{tier}` switch). LLM-using routes (`POST /api/chat/...`, `POST /api/conversations`, `.../opener`) return **403** if the user has no key/tier yet.
- `POST /api/conversations` — new chat; picks target words; returns topic suggestions (first LLM call of a new chat)
- `PATCH /api/conversations/{id}/category` — set topic after user picks one
- `POST /api/conversations/{id}/opener` — persona opens the chat itself (time/memory aware)
- `GET /api/conversations` / `GET .../{id}` / `GET .../{id}/messages` (each msg has `tool_calls`; user msgs also carry `word_events` so chips + dev-mode tool calls survive refresh) / `DELETE .../{id}`
- `POST /api/conversations/search` — BM25/regex search (same engine as the agent tool)
- `POST /api/chat/{conversation_id}` — send message, get assistant reply + scoring events
- `GET|POST|PUT|DELETE /api/words...` — list (applies decay), add (LLM-enriched), adjust score, events, `PUT .../{id}/note` (user's own memory hook; empty clears)
- `GET /api/memory/{identity|memory|persona}` — raw text + parsed content lines (no ids/timestamps)
- `POST /api/memory/{file}/lines` — append a new entry (verbatim, no stamp added)
- `POST /api/memory/{file}/edit` — `{old_string, new_string, replace_all}`; empty new_string deletes
- `PUT /api/memory/{file}/raw` — overwrite whole markdown file (UI's raw markdown editor)
- `PUT /api/memory/persona/form` — onboarding step 1 (persona identity fields)
- `POST /api/memory/onboarding` — onboarding step 2 finish: `{name, about}` → stores Name +
  LLM-structures `about` across identity/memory/persona (falls back to raw append on LLM failure)
- `GET /api/dashboard/stats`, `GET /api/health`

## Chat turn flow (backend)

0. (route gated by `require_model_configured` → 403 if the user has no key/tier) →
1. Store user message → 2. resolve the user's model+key (`model_service.resolve_for_user`) +
build system prompt → 3. rebuild LangChain message array from DB (AIMessage.tool_calls +
ToolMessage pairs reconstructed with original IDs — required by providers) → 4.
`bind_tools(...).invoke()` loop (max 6 iterations) executing tools, using the user's key+model →
5. store assistant message with `tool_calls` JSON → 6. auto-title after first exchange (same
per-user model) → 7. judge user message (same per-user model) → scoring events returned in the response.

## Conventions & decisions

- LangChain 1.x: manual message-list + `bind_tools` loop (officially documented pattern);
  NOT `create_agent`/checkpointers — we own persistence in MongoDB.
- Persistence: MongoDB Atlas via PyMongo (sync), ALL access behind `app/repo.py` (the single
  swappable data layer — services/routers never touch pymongo). `app/mongo.py` owns the client,
  collections, and indexes. IDs are ObjectId hex STRINGS end-to-end. Every data doc has a `user_id`
  (a real Google user's id; `"default"` only tags un-adopted legacy data); words are unique per
  `(user_id, text)`. The 3 memory files live in the `memory_files` collection; users in the
  `users` collection. `data/` is now just a legacy backup; the app never reads it.
- Auth: Google OAuth only, server-side code flow, stateless JWT session cookie. Routers resolve
  the user via `Depends(get_current_user)` (`app/deps.py`) — NEVER hardcode a user id. Store NO
  Google tokens. Any new persisted auth state (e.g. a future `token_version` for revocation) goes
  through `repo.py`. Verify against `docs/oauth-handoff.md` for the locked decisions.
- Gemini must use explicit provider string `google_genai` (bare `gemini-*` infers Vertex).
- **Bring-your-own-key:** each user's Gemini key + tier live on their `User` doc; the key is
  ENCRYPTED (`crypto_service`, Fernet, `ENCRYPTION_KEY` from `.env`). NEVER call an LLM factory
  with the app's own key for a real user — always `model_service.resolve_for_user(user_id)` and
  pass its `api_key`/`model` into the factory. NEVER log/return the plaintext key. NEVER rotate
  `ENCRYPTION_KEY` (stored keys become undecryptable). Adding a model tier = add a row to
  `config.MODEL_TIERS` (nothing else changes). NEVER hardcode any key in a test file (committed to
  Git) — read `ENCRYPTION_KEY` from `.env`, encrypt via `crypto_service` when a test needs ciphertext.
- Env keys: `ENCRYPTION_KEY` (Fernet, REQUIRED) + `MONGODB_URI` (SRV string incl. `/fluently` db
  name) + `MONGODB_DB`, plus the Google-OAuth block (`GOOGLE_OAUTH_CLIENT_ID`/`_SECRET`,
  `OAUTH_REDIRECT_BASE`, `FRONTEND_URL`, `SESSION_SECRET`, `STATE_COOKIE_SECRET`,
  `SESSION_MAX_AGE_DAYS`). Provider keys (`OPENAI/ANTHROPIC/GOOGLE_API_KEY`) + DEFAULT/JUDGE/UTILITY
  model settings are LEGACY/unused (users bring their own key). Real secrets ONLY in `.env`;
  `.env.example` carries placeholders (incl. no real `ENCRYPTION_KEY`). For production: change
  `OAUTH_REDIRECT_BASE`/`FRONTEND_URL` and add the prod callback URI in Google Console — no code
  change (cookies auto-flip to `Secure` over https).
- LLM failures in judge/topics/enrichment/title/onboarding-structuring are swallowed — never break chat or onboarding.
- Sync PyMongo + sync routes (FastAPI threadpools them). Streaming/SSE is a planned
  upgrade (pattern documented in research: astream + StreamingResponse).
- No summarization/compaction of history yet; no vector search yet (BM25 only) — both planned.
- Model per user = their chosen tier (Swift `gemini-3.1-flash-lite` / Sage `gemini-3.5-flash`,
  from `config.MODEL_TIERS`); governs chat + judge + utility. Not `.env`-driven anymore.
- Gemini quirk: `AIMessage.content` can be a LIST of content blocks, not a str — always
  flatten via `chat_service._flatten_content` before treating replies as text.

## Testing — use judgment, don't run blindly

```
cd backend
.venv\Scripts\python run_tests.py                 # ALL areas, LLMs mocked (~5s, free)
.venv\Scripts\python run_tests.py words scoring   # ONLY the named area(s) — much faster
.venv\Scripts\python run_tests.py --list          # show the area keys -> test files
.venv\Scripts\python run_tests.py --live          # + real-provider smoke tests (real Gemini, costs quota)
```

- **Run only the area(s) you touched.** `run_tests.py` is area-selectable: each area maps to one
  test file (`auth, memory, words, scoring, conversations, chat, model, dashboard, settings, live`
  — see `--list`). Pass one or more keys (space- or comma-separated) to run just those; pass
  nothing to run everything. A change confined to one area's code path → run that area. A change to
  SHARED plumbing (`repo`, `mongo`, `deps`, `config`, `models`, `schemas`, `prompt_builder`) can
  affect any area → run ALL (pass nothing). Unsure → run ALL. Unknown keys are rejected (exit 2), so
  a typo never silently runs nothing. Adding a test file ⇒ add its `key: (module, label)` row to
  `AREAS` in `run_tests.py` in the same change.
- **Run the suite when logic changed**: services, routers, schemas, models, scoring, or anything
  with behavior the tests actually exercise. **Skip it when nothing testable changed**: pure
  prompt wording (`prompts.py`), tool-description copy, docs/context-file edits, or a
  frontend-only tweak with no backend touch — the suite can't detect a wording change and running
  it just burns time confirming a no-op. Mixed change (e.g. new field + prompt tweak) → run it for
  the logic part. Genuinely unsure whether something counts as "logic" → default to running it.
- Prints a per-area PASS/FAIL report and writes tests/last_report.txt. Exit code 1 on failure.
- Tests use an ISOLATED Mongo database `<MONGODB_DB>_test` (collections wiped per test) — the real
  `fluently` DB is never touched. Running the suite needs network + a valid `MONGODB_URI` (even the
  mocked-LLM run hits the real Atlas cluster's `_test` DB).
- conftest.py mocks all LLM factories unless a test is marked `@pytest.mark.live`.
- Every new API/feature MUST get tests in the same change: happy path, error paths, side effects.
- The `tester` subagent (.claude/agents/tester.md) can run the suite and diagnose failures;
  it reads this file for context first.

## Frontend (built)

React 19 + Vite, JavaScript. Run: `cd frontend && npm install && npm run dev` (http://localhost:5173;
backend must be on :8000). `npm run build` must pass after every frontend change.
Behavior notes:
- Gating order (App.jsx): health → auth (`useMe`) → onboarding (no persona `Name:` line ⇒ `<Onboarding>`) → model-config gate (`me.has_key` false ⇒ standalone `<BrainStep>`) → app. After onboarding OR the brain-gate completes, the app lands on the **Words** view (add practice words first).
- Onboarding is 3 steps: persona → about you → "How smart should I be?" (paste Gemini key → Verify → Swift/Sage cards appear → pick → Continue). The about-text is submitted only at the end, so its LLM structuring uses the user's own key.
- Scoring chips persist across refresh: shown from the live POST /api/chat response, and on reload
  from each user message's `word_events` (GET .../messages). Each chip is click-to-expand for the
  full judge note.
- Developer mode (Settings toggle, localStorage, off by default): shows the agent's tool calls
  (name/input/output) under each assistant reply, each call individually collapsible. Uses the
  message's stored `tool_calls`, so it works for reloaded history too.
- Words: expanded word detail leads with the user's personal note (add/edit inline → PUT .../note),
  full-width meaning below, and event history as a collapsible strip at the bottom.
- After each chat turn the app invalidates words/dashboard/memory queries (agent may have changed them).
- Thread delete + word remove use inline two-step confirm (click → "sure?" for 2.5s), no modals.
- Chat sends invalidate conversations (auto-title updates in sidebar/drawer).
- Memory tab defaults to rendered View (markdown) on open/tab-switch; Edit shows the raw textarea;
  Save returns to View. Onboarding's free-text "about you" box is LLM-structured server-side, not
  pasted raw — shows a brief "getting to know you" overlay while that call runs.

## Running the backend

```
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   (fill in ENCRYPTION_KEY [generate via Fernet.generate_key()], a real MONGODB_URI incl. /fluently db name, + the Google-OAuth block; users bring their own Gemini key at onboarding)
uvicorn app.main:app --reload --port 8000
```

To bring pre-migration SQLite data into Mongo (optional, one-time):
`.venv\Scripts\python import_sqlite_to_mongo.py --commit`  (reads backend/data/eng.db + the old .md files).
