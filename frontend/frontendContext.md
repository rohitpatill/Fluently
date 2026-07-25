# frontendContext.md — scope: `frontend/`

React 19 + Vite (JavaScript) SPA talking to the FastAPI backend. **Ships two ways from ONE codebase:**
as the **website**, and — wrapped by Capacitor — as the **native Android app** (same `dist/` build,
no second frontend, UI written once).
Parent: [../CLAUDE.md](../CLAUDE.md).
Children: [src/frontendSrcContext.md](src/frontendSrcContext.md),
[android/frontendAndroidContext.md](android/frontendAndroidContext.md) ← **read before any app/bundle work**.

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
| `public/` | favicon.svg, **logo.png** (app-icon source, see the Android context) (+ leftover icons.svg from scaffold). |
| `.env` (+ `.env.example`) | Vite build-time config: `VITE_API_URL` (backend base), `VITE_MAX_MESSAGE_CHARS` (text-message char cap, default 1200). No secrets. **NOTE:** `VITE_API_URL` is baked in at build time for the app too — a shared/release APK MUST be built with the production URL (see the Android context §5). |
| `android/` | **The native Android app** (Capacitor Gradle project) — committed as source because it carries the hand-edited manifest (OAuth deep link + mic permissions), the debug-only cleartext config, and the generated icons/splash. See [android/frontendAndroidContext.md](android/frontendAndroidContext.md). |
| `capacitor.config.json` | Capacitor config: `appId: com.fluently.app`, `appName: Fluently`, `webDir: dist`. |
| `assets/` | Generated icon/splash SOURCE images (from `public/logo.png`) used to regenerate the Android launcher icons + splash screens. |
| `CAPACITOR.md` | Interim quick-start for the app. The authoritative doc is `android/frontendAndroidContext.md`. |

## Rules for editing here
- `npm run build` must pass after every change.
- **This code runs as BOTH the website and the Android app.** Every native-only behavior must be a
  no-op on the web, and all web/native branching goes through `src/platform.js` (+ `src/authToken.js`
  for the session) — never scattered `Capacitor.isNativePlatform()` checks in components. A UI change
  automatically applies to both; a native change may also require a new app bundle.
- Visual language: light/airy, accent #4B5DE4, soft shadows, micro-animations, serif-italic persona accents. Tokens live in `src/index.css` `@theme` — add tokens there, use utility classes in components.
- All server data through TanStack Query hooks (`src/hooks/useApi.js`) + `src/api.js` — never raw fetch in components.
- After any change, update the context file of the folder you edited (+ parents if their summaries changed).
