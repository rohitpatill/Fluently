# frontendSrcContext.md — scope: `frontend/src/`

Parent: [../frontendContext.md](../frontendContext.md). Child: [components/frontendSrcComponentsContext.md](components/frontendSrcComponentsContext.md).

| File | Purpose |
|---|---|
| `main.jsx` | React root: QueryClientProvider (retry 1, no refetchOnWindowFocus) + sonner `<Toaster>` + Fontsource imports + index.css. |
| `App.jsx` | Shell: health check (error ⇒ full-screen retry), onboarding gate (no persona `Name:` ⇒ `<Onboarding>`), rail + AnimatePresence view switch: 'chat' \| 'words' \| 'memory' \| 'settings'. Derives personaName/userName from memory files. |
| `index.css` | `@import "tailwindcss"` + `@theme` design tokens: color palette (accent/bg/surface/border/muted/amber/green/red), fonts (sans=Schibsted Grotesk, serif=Newsreader, mono=JetBrains Mono), radii, shadows (soft/card/accent), keyframes (msgIn/chipPop/dotPulse/fadeIn/shimmer/**skeletonSweep**). Plus scrollbar styling, `.font-serif-italic` helper, and `.skeleton-shimmer` (calm gradient-sweep placeholder, `--animate-skeleton`). ALL new tokens go here. |
| `api.js` | Fetch wrapper (`ApiError` with status; friendly network-down message) + one exported function per backend endpoint. Base URL constant `http://localhost:8000`. Words: `setWordNote(id, note)` (PUT .../note). Memory: `appendMemoryLine`, `editMemory(file, oldString, newString, replaceAll)` (POST .../edit), `putMemoryRaw`, `submitOnboarding(name, about)` (POST /api/memory/onboarding — LLM-structures the free-text box). |
| `utils.js` | `relativeTime`, `formatThreadTime`, `nowClockLabel`, `parsePersonaName` (multiline `Name: X` from persona.md), `parsePersonaRelation` (`Relation to user:`), `parseIdentityName` (`Name: X.` from identity entry line), `initial`. |
| `hooks/useApi.js` | TanStack Query hooks: `useHealth` (15s poll), `usePersonaMemory`, `useConversations`, `useMessages(id)`, `useWords`, `useDashboardStats`, `useWordEvents(id, enabled)`, `useMemoryFile(file)`. Query keys: ['health'], ['memory', file], ['conversations'], ['messages', id], ['words'], ['dashboard'], ['word-events', id]. |
| `hooks/useDevMode.js` | `useDevMode()` → `[enabled, toggle]`, localStorage-backed (key `fluently.devMode`), off by default. NOT server state (client-only). Syncs across components in-tab via a custom `fluently:devmode` window event + cross-tab via `storage`. `getDevMode()` helper for a one-off read. |
| `components/` | All screens + shared pieces. See child context file. |

Invalidation convention: after a chat turn invalidate messages/conversations/words/dashboard/memory (the agent may have changed any of them); after word/memory mutations invalidate their own keys + dashboard.
