# frontendSrcComponentsContext.md — scope: `frontend/src/components/`

Parent: [../frontendSrcContext.md](../frontendSrcContext.md).

| File | Purpose |
|---|---|
| `Onboarding.jsx` | 2-step first-run flow. Step 1: persona name + relation chips (5 presets + custom input) + personality textarea ⇒ `PUT /api/memory/persona/form`. Step 2: persona speech-bubble intro, user name + optional about ⇒ identity lines. Calls `onComplete` ⇒ App invalidates ['memory']. |
| `Rail.jsx` | 68px left nav. EXACTLY 3 tabs (Chat/Words/Memory — never add a 4th without explicit instruction). Persona avatar top, user initial bottom. |
| `Chat.jsx` | The heart. Threads sidebar (search filter, two-step inline delete "sure?", + new chat stores returned topics in `topicsByConv` state). Main: header (persona avatar/name/online dot, 30s clock pill), empty-conversation state (time-aware greeting, topic cards ⇒ PATCH category + auto-send "Let's talk about: {title}", "Let {persona} start ✦" ⇒ opener endpoint), messages (assistant = markdown bubble left, user = accent bubble right), optimistic pending user bubble, typing indicator, scoring chips (`chipsByMessage` session state, word names resolved from ['words'] cache; green perfect / amber awkward+notes / red wrong+notes). Composer: auto-sizing textarea, Enter sends. |
| `Words.jsx` | Stats row (Mastered/Average/Strongest/Slipping-amber from dashboard stats). Add input (kind=phrase if contains space; "Enriching…" pending state; 409 friendly toast; auto-expands new word). Rows sorted score desc: ScoreBar, trophy at 100, expandable detail (meaning+register, 2 examples serif-italic, collocation pills, EventHistory lazy-loaded, "lower score −10", two-step remove). |
| `Memory.jsx` | 3 pills (About you=identity / Your life=memory / Who {persona} is=persona). RAW markdown editor per file: monospace textarea bound to `raw`, dirty tracking, Save ⇒ `PUT /api/memory/{file}/raw`, "Saved ✓" state, entry count header, window.confirm before discarding unsaved edits on tab switch. NOT a per-line list (deliberate deviation from prototype). |
| `Shared.jsx` | `PersonaAvatar` (gradient circle, serif-italic initial, sizes xs–xl, optional online dot), `Spinner`, `FullScreenLoader`, `FullScreenError` (title/message/retry), `ScoreBar` (motion width animation, amber when slipping). |

Conventions: mutations via `useMutation` + `api.*` + targeted `invalidateQueries`; toasts for every success/failure; two-step inline confirms (2.5s timeout) instead of modal dialogs; all animation via motion or the @theme keyframes.
