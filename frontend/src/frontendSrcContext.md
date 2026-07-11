# frontendSrcContext.md — scope: `frontend/src/`

Parent: [../frontendContext.md](../frontendContext.md). Child: [components/frontendSrcComponentsContext.md](components/frontendSrcComponentsContext.md).

| File | Purpose |
|---|---|
| `main.jsx` | React root: QueryClientProvider (retry 1, no refetchOnWindowFocus) + sonner `<Toaster>` + Fontsource imports + index.css. |
| `App.jsx` | Shell: health check (error ⇒ full-screen retry), onboarding gate (no persona `Name:` ⇒ `<Onboarding>`), rail + AnimatePresence view switch: 'chat' \| 'words' \| 'memory'. Derives personaName/userName from memory files. |
| `index.css` | `@import "tailwindcss"` + `@theme` design tokens: color palette (accent/bg/surface/border/muted/amber/green/red), fonts (sans=Schibsted Grotesk, serif=Newsreader, mono=JetBrains Mono), radii, shadows (soft/card/accent), keyframes (msgIn/chipPop/dotPulse/fadeIn/shimmer). Plus scrollbar styling + `.font-serif-italic` helper. ALL new tokens go here. |
| `api.js` | Fetch wrapper (`ApiError` with status; friendly network-down message) + one exported function per backend endpoint. Base URL constant `http://localhost:8000`. |
| `utils.js` | `relativeTime`, `formatThreadTime`, `nowClockLabel`, `parsePersonaName` (multiline `Name: X` from persona.md), `parsePersonaRelation` (`Relation to user:`), `parseIdentityName` (`Name: X.` from identity entry line), `initial`. |
| `hooks/useApi.js` | TanStack Query hooks: `useHealth` (15s poll), `usePersonaMemory`, `useConversations`, `useMessages(id)`, `useWords`, `useDashboardStats`, `useWordEvents(id, enabled)`, `useMemoryFile(file)`. Query keys: ['health'], ['memory', file], ['conversations'], ['messages', id], ['words'], ['dashboard'], ['word-events', id]. |
| `components/` | All screens + shared pieces. See child context file. |

Invalidation convention: after a chat turn invalidate messages/conversations/words/dashboard/memory (the agent may have changed any of them); after word/memory mutations invalidate their own keys + dashboard.
