# frontendContext.md — scope: `frontend/`

React 19 + Vite (JavaScript) SPA talking to the FastAPI backend at http://localhost:8000.
Parent: [../CLAUDE.md](../CLAUDE.md). Child: [src/frontendSrcContext.md](src/frontendSrcContext.md).

## Stack (researched July 2026 — do not regress)
Tailwind CSS v4 (CSS-first `@theme` tokens, NO tailwind.config.js) · motion (`motion/react`) ·
@tanstack/react-query (all server state) · lucide-react (icons) · sonner (toasts) ·
react-markdown (assistant messages) · @fontsource-variable/* (self-hosted fonts) ·
NO router — state-based view switching · NO hand-written CSS files beyond index.css tokens.

## Layout

| Item | What it is |
|---|---|
| `src/` | All app code. See child context file. |
| `index.html` | Vite entry, title "Fluently" (the app's name), favicon.svg. |
| `vite.config.js` | react + @tailwindcss/vite plugins, dev port 5173. |
| `package.json` | Scripts: `dev`, `build`, `preview`. |
| `Fluent App.dc.html`, `Fluent.dc.html`, `support.js`, `.thumbnail` | ORIGINAL design prototypes (non-React). Reference/inspiration only — never imported, never delete. |
| `public/` | favicon.svg (+ leftover icons.svg from scaffold). |
| `.env` (+ `.env.example`) | Vite build-time config: `VITE_API_URL` (backend base), `VITE_MAX_MESSAGE_CHARS` (text-message char cap, default 1200). No secrets. |

## Rules for editing here
- `npm run build` must pass after every change.
- Visual language: light/airy, accent #4B5DE4, soft shadows, micro-animations, serif-italic persona accents. Tokens live in `src/index.css` `@theme` — add tokens there, use utility classes in components.
- All server data through TanStack Query hooks (`src/hooks/useApi.js`) + `src/api.js` — never raw fetch in components.
- After any change, update the context file of the folder you edited (+ parents if their summaries changed).
