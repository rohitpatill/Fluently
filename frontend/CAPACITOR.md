# Fluently — Android app (Capacitor) guide

This document is the single source of truth for building and running Fluently as a native
**Android** app using [Capacitor](https://capacitorjs.com/). The **website is unaffected** by
any of this — it still builds and deploys exactly as before (`npm run build` → Vercel). Capacitor
just takes the same `dist/` build and wraps it in a native app shell.

> **Status:** WORKING on-device (Android). App builds, installs, renders, and the full feature set
> runs: Google login (system browser + deep link + bearer token), text chat, words, memory, and
> real-time voice (persona voice mode + the in-app Fluently assistant).
>
> ⚠️ This file is an interim quick-start. The FULL, authoritative documentation lives in
> `android/frontendAndroidContext.md` (requirements, build/release workflow, architecture,
> troubleshooting) — read that first when working on the app.

---

## 0. What was added (and why the website is safe)

| Added / changed | What it is |
|---|---|
| `@capacitor/core`, `@capacitor/cli`, `@capacitor/android`, `@capacitor/app`, `@capacitor/browser`, `@capacitor/preferences` (in `package.json`) | Capacitor runtime + CLI + Android platform + plugins for the (upcoming) OAuth deep-link + token storage. |
| `capacitor.config.json` | Capacitor config: app id `com.rohitpatil.fluently`, name `Fluently`, `webDir: dist`. |
| `android/` | The generated native Android project (Gradle). Open this in Android Studio. |
| `src/platform.js` | Small abstraction: "are we native or web?" + one-time native init. **No-op on the website.** |
| `src/main.jsx` | Calls `initNativeApp()` at startup (no-op on web). |
| `src/index.css` | A safe-area rule scoped to `html.capacitor-native` — **only applies inside the app**, web layout is byte-for-byte unchanged. |
| `android/app/src/main/AndroidManifest.xml` | Added `RECORD_AUDIO` + `MODIFY_AUDIO_SETTINGS` (voice mode mic). |
| root `.gitignore` | Ignores Android build artifacts + signing secrets (keeps `android/` source). |

Nothing in the web runtime path changed: `isNativeApp()` is always `false` in a browser, so the
website behaves identically.

---

## 1. One-time setup: Android Studio

1. Install **Android Studio** (version **Otter | 2025.2.1 or newer** — Capacitor 8 requires it):
   <https://developer.android.com/studio>
2. On first launch, let it install the default SDK. Then open **SDK Manager**
   (More Actions → SDK Manager) and ensure these are installed:
   - **Android SDK Platform 36** (Capacitor 8 targets/compiles against API 36) — tick it and Apply.
   - **Android SDK Build-Tools** (latest)
   - **Android SDK Platform-Tools** (this provides `adb`)
   - **Android Emulator** (only if you want to test in an emulator instead of a phone)
3. Android Studio bundles a compatible JDK (JBR), so you do **not** need to install Java separately
   for building inside Android Studio.

> After installing, the Android SDK lives at `C:\Users\rohit\AppData\Local\Android\Sdk` by default.

---

## 2. Point the app at a backend (dev)

Inside the native app, the web files load from `https://localhost` (the app's own origin) — so
`localhost` does **NOT** mean your PC. For the app to reach your **locally running** backend, it must
use your PC's **LAN IP**.

Your PC's current Wi-Fi LAN IP is **`10.195.9.176`** (re-check with `ipconfig` if your network
changes). Your phone shares this network (its hotspot serves this PC), so the phone can reach the PC.

Create/edit **`frontend/.env`** for the app build:

```
VITE_API_URL=http://10.195.9.176:8000
VITE_MAX_MESSAGE_CHARS=1200
```

And allow the app origin in the **backend** — this is a **`.env` change only, no backend code**.
In `backend/.env`, add `https://localhost` (the app's WebView origin) to `CORS_ALLOWED_ORIGINS`:

```
CORS_ALLOWED_ORIGINS=http://localhost:5173,https://localhost
```

Restart the backend after changing its `.env`.

> For the **production** app build later, `VITE_API_URL` is just your real backend URL
> (e.g. `https://api.fluently.com`) — same as the website uses.

---

## 3. Build the web app and sync it into Android

Every time you change web code and want it reflected in a **non-live-reload** app build:

```bash
cd frontend
npm run build          # produces dist/
npx cap sync android   # copies dist/ into the Android project + updates native plugins
```

Then open the project in Android Studio:

```bash
npx cap open android
```

Press the green **Run ▶** button in Android Studio (with a device/emulator selected) to build and
launch. The first Gradle build downloads dependencies and can take several minutes — this is normal.

---

## 4. Run on your physical phone (USB)

1. On the phone: **Settings → About phone → tap "Build number" 7 times** to unlock Developer options.
2. **Settings → Developer options → enable "USB debugging".**
3. Connect the phone to the PC via USB. Tap **"Allow"** on the "Allow USB debugging?" prompt.
4. In Android Studio, your phone appears in the device dropdown (top toolbar). Select it and press
   **Run ▶**.
5. Verify the device is seen from the terminal (after Android Studio is installed, `adb` is on the
   SDK's `platform-tools`):
   ```bash
   adb devices
   ```
   Your phone should be listed as `device` (not `unauthorized`).

---

## 5. Live-reload during development (optional, very useful)

Instead of rebuilding for every change, you can point the app at your running **Vite dev server** so
edits hot-reload on the phone.

1. Start Vite bound to the network (so the phone can reach it):
   ```bash
   cd frontend
   npm run dev -- --host
   ```
   (The `--host` flag makes Vite listen on your LAN IP, not just localhost.)
2. Add a `server` block to `capacitor.config.json` pointing at your PC:
   ```json
   {
     "appId": "com.rohitpatil.fluently",
     "appName": "Fluently",
     "webDir": "dist",
     "server": {
       "url": "http://10.195.9.176:5173",
       "cleartext": true
     }
   }
   ```
3. `npx cap sync android`, then Run ▶ from Android Studio. The app now loads live from Vite —
   edits reload on the phone instantly.

> ⚠️ **Remove the `server` block before building a release/Play Store bundle** — a release must load
> the bundled files, not a dev server. (Leaving it in is a classic mistake that ships a broken app.)

---

## 6. Debugging the app's WebView from your PC

The app is a WebView, so you get full Chrome DevTools:

1. With the app running on the connected phone, open desktop **Chrome** → visit **`chrome://inspect`**.
2. Under "Remote Target" you'll see the Fluently WebView → click **inspect**.
3. You now have the console, network tab, and elements inspector for the app — exactly like debugging
   the website. Use this to see any errors, failed requests, or CORS problems.

---

## 7. What to check in the spike (the point of this phase)

On the phone, confirm:

- [ ] The app **launches** with no white/blank screen.
- [ ] The **login screen renders** correctly (fonts, colors, layout, safe areas — nothing under the
      status bar or notch).
- [ ] `chrome://inspect` console shows **no fatal errors**.
- [ ] A **non-auth backend call works**: the health check / reaching `VITE_API_URL` succeeds (watch
      the Network tab in `chrome://inspect`; no CORS error). If you see the login screen render
      without a "can't reach server" error, the backend connection is working.
- [ ] Navigation/animations feel right; scrolling works; the mobile keyboard behaves.

### How in-app login works (built and working)
Google blocks OAuth inside embedded WebViews, and the app's WebView (origin `https://localhost`)
cannot read the system browser's cookie jar. So the native flow is:

1. App opens `\<backend\>/api/auth/google/login?native=1` in the **system browser** (`@capacitor/browser`).
2. Backend runs the normal OAuth flow; the `native` flag rides inside the **signed** state cookie.
3. The callback redirects to **`com.rohitpatil.fluently://auth?token=<session JWT>`**.
4. Android hands that URL to the app; `@capacitor/app`'s `appUrlOpen` listener
   (`src/platform.js`) stores the token via `@capacitor/preferences` (`src/authToken.js`).
5. Every HTTP request then sends `Authorization: Bearer <jwt>`; **WebSockets** (voice) pass it as
   `?token=` because the browser WebSocket API cannot send custom headers.

The backend accepts **either** transport (`deps._session_token` / `deps.user_id_from_websocket`),
so the **website's cookie login is completely unchanged**.

---

## 8. Everyday workflow summary

| I changed… | Do this |
|---|---|
| Web code (components, styles, logic) | `npm run build && npx cap sync android` → Run ▶ (or use live-reload) |
| A Capacitor plugin / native config / manifest | `npx cap sync android` → Run ▶ |
| Nothing native, just want the website | `npm run build` and deploy as usual — Capacitor is irrelevant to the web deploy |

---

## 9. Later (not this phase)

- **In-app Google login** (system browser + deep link + bearer token) — the one real auth change.
- **OTA live updates** via `@capgo/capacitor-updater` so the app auto-updates like the website.
- **App icon + splash screen**, then a **signed release AAB** for the Play Store.
- **iOS** (`npx cap add ios`, needs a Mac).
