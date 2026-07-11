# OAuth Handoff — read this before implementing Google login

> Purpose: capture the **decisions, constraints, and non-obvious context** an agent needs
> before adding Google OAuth to Fluently. This is NOT a step-by-step implementation plan —
> you will design that yourself after reading the code and the context-file hierarchy
> (start at `CLAUDE.md`, then `backend/backendContext.md` → `app/backendAppContext.md` → …).
> This doc only tells you what you can't infer from the code alone.

---

## 0. Hard rules (do not violate)

- **NEVER run a single git operation.** Not `add`, `commit`, `branch`, `status` — nothing.
  The user manages all git themselves and may discard/verify manually. This is absolute.
- **Do not update context files (or CLAUDE.md) until the user has verified the feature works.**
  Per CLAUDE.md rule 2: user tests first, there may be fix iterations, THEN docs get updated.
  (Exception: purely structural changes like file moves — those update docs immediately.)
- The app name is **Fluently** — use it in all user-facing surfaces.
- Backend is **sync PyMongo + sync FastAPI routes**. Do NOT convert to async.

## 1. Where the project is right now (post-migration state)

The app just finished migrating from SQLite → **MongoDB Atlas** and is fully working
(59/59 tests green, real data migrated). Key facts that matter for OAuth:

- **All DB access goes through ONE module: `backend/app/repo.py`.** Services/routers never
  touch pymongo directly. `backend/app/mongo.py` owns the client, collections, indexes.
- **Every stored document ALREADY has a `user_id` field.** Right now it's the sentinel
  `DEFAULT_USER_ID = "default"` (defined in `mongo.py`). Every `repo.py` function already
  takes a `user_id` parameter (≈60 call sites already thread it through). Collections:
  `conversations`, `messages`, `words`, `word_events`, `memory_files`.
- **`words` is unique per `(user_id, text)`** (index `uq_user_text`), NOT globally. Two users
  can both track "ubiquitous". `memory_files` is unique per `(user_id, file)`.
- IDs are **ObjectId hex strings** end-to-end (schemas, frontend). No integers anywhere.

**This is the whole reason OAuth was sequenced AFTER the DB migration:** the data layer is
already user-scoped. Your job is mostly to (a) authenticate a real user, (b) resolve their
real `user_id`, and (c) pass THAT id into the existing `repo`/service calls instead of the
`"default"` sentinel — plus the frontend login/logout/session UX.

## 2. What the user actually asked for (scope)

- **"Continue with Google" ONLY.** No username/password, no email/password forms. Just the
  Google OAuth "Continue with Google" flow.
- On login, the user is created if new; **all their data is scoped to their user id** — a
  logged-in user sees ONLY their own words/conversations/memories, never the global/default data.
- **Session maintained as long as they're logged in in that browser**; logout clears it.
  This is standard session/token handling — the user expects you to know the universal pattern.
- Single-user "default" data already exists in Mongo (the migrated data). Decide with the user
  what happens to it — likely: the first Google user to log in either adopts it or it stays
  orphaned. **Ask the user** rather than silently reassigning or deleting it.

## 3. Decisions already made (don't relitigate these)

- **Order is locked:** Mongo migration (done) → **OAuth (now)** → API-key handling (later).
- **API keys are PHASE 3, not now.** When it comes: the key must be **ENCRYPTED at rest
  (reversible with a server master key), NOT hashed.** The user initially said "hash it and
  unhash it" — that's a misconception; a hash is one-way and you can never recover the key to
  send to OpenAI/Google. The correct design is symmetric encryption bound to the user. It also
  pulls in provider-selection + model-selection UI. **Do not build any of this during OAuth.**
- Keep the storage layer swappable — anything new you persist (users, sessions) goes through
  `repo.py`, not raw pymongo scattered around.

## 4. Things to think about / decide WITH the user before coding

- **New collections:** likely a `users` collection (keyed by Google `sub`/subject id → your
  internal `user_id`), possibly a `sessions` collection (or use signed cookies / JWT — your call,
  discuss the trade-off). The internal `user_id` you mint is what flows into every existing
  `repo` call.
- **How `user_id` reaches the routers.** Today routers hardcode `DEFAULT_USER_ID`. You'll need a
  FastAPI dependency that resolves the current user from the session/cookie and yields their
  `user_id`, replacing the hardcoded sentinel across `routers/*.py`. This is the main backend
  surgery — it touches every router, but it's mechanical (the `repo`/service functions already
  accept `user_id`).
- **Google OAuth credentials** (client id/secret, redirect URI) will be new `.env` entries —
  mirror the existing pattern: real values in `.env`, PLACEHOLDERS in `.env.example` (committed).
  The user will need to create an OAuth app in Google Cloud Console; surface exactly what config
  you need from them (authorized redirect URIs, scopes = basic profile/email).
- **CORS + cookies:** frontend is `http://localhost:5173`, backend `http://localhost:8000`
  (different origins). Session cookies across origins need correct `SameSite`/credentials setup;
  `allow_credentials=True` is already on in `main.py`. Plan for this.
- **Frontend:** a login screen / "Continue with Google" button, a logged-in state, logout, and
  gating the whole app behind auth. Today `App.jsx` gates on onboarding (persona `Name:` present).
  Auth gating should wrap around that. Onboarding then becomes per-user.
- **The `"default"` sentinel data** (see §2) — get an explicit decision.
- **Tests:** the suite runs against an isolated `<MONGODB_DB>_test` Mongo DB. Every new
  auth endpoint/behavior needs tests in the same change (happy path + error paths + the
  scoping guarantee: user A cannot read user B's data). You can use the `tester` subagent.

## 5. Verification expectations

- `backend`: `.venv\Scripts\python run_tests.py` must stay green (needs network + `MONGODB_URI`).
- `frontend`: `npm run build` must pass after any frontend change.
- The critical thing to prove: **data isolation** — log in as user A, add words/chats; log in as
  user B, confirm A's data is invisible; log back in as A, confirm it's all still there.

## 6. Quick orientation pointers (read these, don't take my word)

- `backend/app/mongo.py` — `DEFAULT_USER_ID`, collections, `ensure_indexes()`.
- `backend/app/repo.py` — every data operation; note every function's `user_id` param.
- `backend/app/routers/*.py` — see how each currently passes `DEFAULT_USER_ID` (that's what you'll
  replace with a resolved-current-user dependency).
- `backend/app/main.py` — app setup, CORS, startup.
- `frontend/src/App.jsx` — the current onboarding gate you'll wrap with auth.
- `CLAUDE.md` + the `*Context.md` hierarchy — the authoritative, freshly-updated project map.
