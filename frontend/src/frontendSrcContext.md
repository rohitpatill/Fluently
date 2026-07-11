# frontendSrcContext.md — scope: `frontend/src/`

Parent: [../frontendContext.md](../frontendContext.md). Child: [components/frontendSrcComponentsContext.md](components/frontendSrcComponentsContext.md).

| File | Purpose |
|---|---|
| `main.jsx` | React root: QueryClientProvider (retry 1, no refetchOnWindowFocus) + sonner `<Toaster>` + Fontsource imports + index.css. |
| `App.jsx` | Shell + gating order: health check (error ⇒ full-screen retry) → **auth gate** (`useMe`; 401/no session ⇒ `<Login>`) → onboarding gate (`me.has_persona` false ⇒ `<Onboarding>`) → rail + AnimatePresence view switch: 'chat' \| 'words' \| 'memory' \| 'settings'. Passes `me` to Rail/SettingsView. Persona/identity queries are `enabled` only once authenticated. |
| `index.css` | `@import "tailwindcss"` + `@theme` design tokens: color palette (accent/bg/surface/border/muted/amber/green/red), fonts (sans=Schibsted Grotesk, serif=Newsreader, mono=JetBrains Mono), radii, shadows (soft/card/accent), keyframes (msgIn/chipPop/dotPulse/fadeIn/shimmer/**skeletonSweep**). Plus scrollbar styling, `.font-serif-italic` helper, and `.skeleton-shimmer` (calm gradient-sweep placeholder, `--animate-skeleton`). ALL new tokens go here. |
| `api.js` | Fetch wrapper (`ApiError` with status; friendly network-down message) + one exported function per backend endpoint. Base URL constant `http://localhost:8000`. **All requests send `credentials: 'include'`** (the cross-origin session cookie). Auth: `getMe()` (GET /api/auth/me), `logout()` (POST /api/auth/logout), `loginWithGoogle()` (full-page redirect to `${BASE_URL}/api/auth/google/login`). Words: `setWordNote(id, note)`. Memory: `appendMemoryLine`, `editMemory(...)`, `putMemoryRaw`, `submitOnboarding(name, about)`. |
| `utils.js` | `relativeTime`, `formatThreadTime`, `nowClockLabel`, `parsePersonaName` (multiline `Name: X` from persona.md), `parsePersonaRelation` (`Relation to user:`), `parseIdentityName` (`Name: X.` from identity entry line), `initial`. |
| `hooks/useApi.js` | TanStack Query hooks: `useHealth` (15s poll), `useMe` (`retry:false` so a 401 resolves fast to "logged out"), `usePersonaMemory({enabled})`, `useConversations`, `useMessages(id)`, `useWords`, `useDashboardStats`, `useWordEvents(id, enabled)`, `useMemoryFile(file, {enabled})`. Query keys: ['health'], ['me'], ['memory', file], ['conversations'], ['messages', id], ['words'], ['dashboard'], ['word-events', id]. |
| `hooks/useDevMode.js` | `useDevMode()` → `[enabled, toggle]`, localStorage-backed (key `fluently.devMode`), off by default. NOT server state (client-only). Syncs across components in-tab via a custom `fluently:devmode` window event + cross-tab via `storage`. `getDevMode()` helper for a one-off read. |
| `components/` | All screens + shared pieces. See child context file. |

Invalidation convention: after a chat turn invalidate messages/conversations/words/dashboard/memory (the agent may have changed any of them); after word/memory mutations invalidate their own keys + dashboard.
