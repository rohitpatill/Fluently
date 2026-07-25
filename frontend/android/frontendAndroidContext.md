# frontendAndroidContext.md — scope: `frontend/android/`

The **native Android app** (Google Play target), produced by wrapping the existing React web
build in [Capacitor](https://capacitorjs.com/). Parent: [../frontendContext.md](../frontendContext.md).

> **THE ONE IDEA:** there is **no second frontend**. The Android app runs the *same* React code
> as the website, inside a native WebView. `npm run build` produces `dist/`; the website deploys
> it, and Capacitor packages that identical `dist/` into an APK/AAB. A UI change is written **once**.

**Read this file before touching anything in `android/`, before building a bundle, and before
changing native auth.** Everything needed to rebuild this from a fresh machine is here.

---

## 1. Status

| Thing | State |
|---|---|
| Android app | **Working on-device** (built, installed, tested on a Galaxy S23 FE) |
| Google login in-app | **Working** (system browser → deep link → bearer token) |
| Text chat / words / memory / dashboard | Working |
| Voice mode + Fluently assistant (mic, WebSocket) | Working |
| Website | **Completely unaffected** by any of this |
| iOS | Not started (`npx cap add ios`, needs a Mac) |
| OTA / live updates | **Deliberately NOT used** (paid). Every change ⇒ new bundle ⇒ Play Store. |
| Signed release AAB / Play Store listing | **Not done yet** — no keystore exists |

---

## 2. Machine requirements (fresh setup)

| Requirement | Version / note |
|---|---|
| **Node.js** | ≥ 22 (hard floor for Capacitor 8). Verified on v22.19. |
| **Android Studio** | **Otter 2025.2.1 or newer** (Capacitor 8 floor). Verified on Quail 2 / 2026.1.2. |
| **Android SDK Platform 36** | **Must be added manually** via SDK Manager → SDK Platforms. Not installed by default; the build fails without it (`compileSdk`/`targetSdk` = 36). |
| **Android SDK Build-Tools + Platform-Tools** | SDK Manager → SDK Tools. Platform-Tools provides `adb`. |
| **JDK 21** | **No separate install needed** — Android Studio bundles it (JBR). Gradle from a terminal needs `JAVA_HOME` pointed at it (see §4). |
| Physical Android phone (or emulator) | Developer options + USB debugging on. A real device is required to trust the mic/voice path. |

Default paths on this Windows machine (referenced by the commands below):

```
Android SDK : C:\Users\<you>\AppData\Local\Android\Sdk
Bundled JDK : C:\Program Files\Android\Android Studio\jbr
adb         : <SDK>\platform-tools\adb.exe
```

Toolchain floors baked into the project: AGP 8.13.0 · Gradle 8.14.3 · minSdk 24 · compileSdk/targetSdk 36.

---

## 3. Layout — what's here and what's generated

| Path | What it is |
|---|---|
| `app/src/main/AndroidManifest.xml` | **Hand-edited, do not regenerate blindly.** Holds the launcher intent-filter, the **OAuth deep-link intent-filter** (`com.rohitpatil.fluently://auth`), and `RECORD_AUDIO` + `MODIFY_AUDIO_SETTINGS` for voice. |
| `app/src/debug/AndroidManifest.xml` | **Debug-only** overlay: points at the network-security config below. Merged into debug builds ONLY, so release stays HTTPS-strict. |
| `app/src/debug/res/xml/network_security_config.xml` | **Debug-only**: permits cleartext HTTP to **loopback only** (`localhost`, `127.0.0.1`, `10.0.2.2`) so on-device testing can reach a dev backend via `adb reverse`. Every other host still requires HTTPS. |
| `app/src/main/res/mipmap-*/` | Launcher icons (all densities, `ic_launcher`, `_round`, adaptive `_foreground`/`_background`). Generated — see §7. |
| `app/src/main/res/drawable-*/` | Splash screens, portrait + landscape, light + `-night` dark. Generated — see §7. |
| `app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml` | Adaptive-icon definition (applies a **16.7% inset** to both layers — critical, see §7). |
| `app/build.gradle`, `build.gradle`, `variables.gradle`, `settings.gradle`, `capacitor.settings.gradle` | Gradle build scripts (Capacitor-managed; `variables.gradle` holds the SDK versions). |
| `gradlew`, `gradlew.bat`, `gradle/wrapper/` | Gradle wrapper — **committed**, required for builds on a fresh clone. |
| `app/src/main/assets/public/` | The synced web build. **Gitignored + regenerated** by `npx cap sync`. Never edit. |
| `app/build/`, `.gradle/`, `local.properties` | Build output / machine-local. **Gitignored.** |

`android/` **is committed to Git** — it carries the hand-edited manifest, the debug network config,
and the generated icons. Re-running `npx cap add android` would silently discard all of that.

Config lives one level up: **`frontend/capacitor.config.json`** — `appId: com.rohitpatil.fluently`,
`appName: Fluently`, `webDir: dist`.

---

## 4. Build & run — the everyday workflow

Always: **build the web app first, then sync, then build native.** Skipping the web build ships stale assets.

```bash
# 1. web build + copy into the native project (+ update native plugins)
cd frontend
npm run build
npx cap sync android
```

Then either open the IDE:

```bash
npx cap open android      # Android Studio → press Run ▶
```

…or build straight from the terminal (Gradle needs the bundled JDK):

```powershell
# PowerShell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
cd D:\Study\ENG\frontend\android
.\gradlew.bat assembleDebug
```

Output APK (**~4.9 MB**, this is the file you share with people):

```
frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

Install / launch / inspect:

```bash
adb devices                                  # phone must read "device", not "unauthorized"
adb install -r <path-to>/app-debug.apk       # -r keeps app data (session token survives)
adb shell am force-stop com.rohitpatil.fluently
adb shell monkey -p com.rohitpatil.fluently -c android.intent.category.LAUNCHER 1
```

**Debugging the WebView:** desktop Chrome → **`chrome://inspect`** → *inspect* under Fluently.
Full console + network tab, exactly like debugging the website. Enabled automatically in debug builds.

First Gradle build downloads ~900 MB of dependencies and takes **~10 min**; later builds ~30 s.

---

## 5. Which backend the app talks to — the thing that trips everyone up

`VITE_API_URL` (in `frontend/.env`) is **baked into the bundle at build time**. Inside the app,
`localhost` means **the phone itself**, not your PC. Two valid setups:

### A. Production (what you ship / share)

```
VITE_API_URL=https://api.fluently.fun
```

Works on any phone, over mobile data, no cable. **Use this for every shared APK and every release.**

### B. Local backend, real phone (development)

```
VITE_API_URL=http://localhost:8000
```
plus, with the phone connected by USB:
```bash
adb reverse tcp:8000 tcp:8000
```

`adb reverse` tunnels the **phone's** `localhost:8000` to the backend on your dev machine.

> **Why the tunnel instead of your LAN IP:** Google **rejects raw private IPs**
> (`http://10.x.x.x:8000/...`) as OAuth redirect URIs, so login would break. `localhost` is
> special-cased by Google and is already registered in the Google Cloud console, so tunnelling
> keeps the existing redirect URI valid. This is the *only* practical way to test login locally.

Also required for setup B: the **local** backend's `CORS_ALLOWED_ORIGINS` must include
`https://localhost`, and the debug network-security config (§3) allows the cleartext HTTP.

**After switching `VITE_API_URL` you must `npm run build && npx cap sync android` and rebuild** —
the value is compiled in, not read at runtime.

Verify what actually shipped:
```bash
grep -o "https://api.fluently.fun" frontend/dist/assets/*.js   # expect a hit for a prod build
```
(Delete `dist/` first — stale hashed bundles from earlier builds linger and produce false results.)

---

## 6. Native auth architecture — why it isn't just the cookie

**The problem.** The website's session is an **HttpOnly cookie**. Two facts make that unusable in the app:
1. **Google refuses OAuth inside embedded WebViews** (`disallowed_useragent`), so login *must* run in the system browser.
2. The system browser's cookie jar is **unreadable** by the app's WebView (origin `https://localhost`) — separate storage.

**The solution — one session JWT, two transports.** Nothing about the website changed.

```
app: "Continue with Google"
  └─ @capacitor/browser opens  <backend>/api/auth/google/login?native=1   (SYSTEM browser)
       └─ backend signs state as "state:nonce:native"  ← flag is inside the SIGNED cookie,
          so it survives the trip to Google and cannot be tampered with
            └─ Google consent → /api/auth/google/callback
                 └─ native? → 302 to  com.rohitpatil.fluently://auth?token=<session JWT>
                                      (no cookie set — the app could never read it)
                      └─ Android routes that URL to MainActivity (deep-link intent-filter)
                           └─ @capacitor/app `appUrlOpen` → store token, close browser tab
                                └─ every request now carries the token
```

**Where each piece lives**

| Concern | File |
|---|---|
| Is-native detection, native init, **deep-link listener** | `frontend/src/platform.js` |
| Token persistence (`@capacitor/preferences`, cached in memory) | `frontend/src/authToken.js` |
| Attach token to **HTTP** (`Authorization: Bearer`) + **WebSocket** (`?token=`) | `frontend/src/api.js` |
| Hydrate token **before first render**, register deep link | `frontend/src/main.jsx` |
| Deep-link scheme registration | `app/src/main/AndroidManifest.xml` |
| Accept bearer **or** cookie (HTTP) | `backend/app/deps.py::_session_token` |
| Accept `?token=` **or** cookie (WebSocket) | `backend/app/deps.py::user_id_from_websocket` |
| `native=1` + deep-link redirect | `backend/app/routers/auth.py` |
| `native` flag inside signed state | `backend/app/services/auth_service.py` |
| Deep-link URL (config-driven) | `backend/app/config.py::native_app_redirect` |

**Why WebSockets differ:** the browser `WebSocket` API **cannot send custom headers**, so voice
and assistant sockets pass the token as a **query param** instead. Same JWT, same validation.
Known trade-off: tokens can appear in server access logs; a short-lived single-use socket ticket
would harden this later.

**Token lifetime = `SESSION_MAX_AGE_DAYS`** (default 7). It is minted+signed with the backend's
`SESSION_SECRET`, so a token from your **local** backend is invalid against **production** and
vice-versa — after switching environments, clear app data (`adb shell pm clear com.rohitpatil.fluently`)
or just log in again.

**Requirements outside the code:** production `CORS_ALLOWED_ORIGINS` must include
`https://localhost`, and Google Cloud console must list
`https://api.fluently.fun/api/auth/google/callback` as an authorized redirect URI.

---

## 7. App icon & splash — regenerating (and the trap)

Source of truth: **`frontend/public/logo.png`** (497×510, RGBA, white background baked in).
Generated intermediates live in **`frontend/assets/`**: `icon.png`, `icon-foreground.png`,
`icon-background.png`, `splash.png`, `splash-dark.png` (dark uses `#1A1D27` = the `--color-text` token).

> ⚠️ **THE TRAP — padding is applied twice.** Android's adaptive-icon config
> (`mipmap-anydpi-v26/ic_launcher.xml`) already insets **both layers by 16.7%**. `logo.png` also
> has its own built-in padding. So scaling the art down again when generating produces a **tiny
> logo floating in a big white box** — this exact mistake was made and fixed once already.
>
> Correct sizing: **`icon.png` full-bleed** (the logo *is* its own background) and
> **`icon-foreground.png` at ~92%** — let Android's 16.7% inset be the padding.

Regeneration procedure (the tool is intentionally **not** a permanent dependency — it pulls in
`sharp`/`libvips` with numerous CVEs; it is dev-only and removed again afterwards):

```bash
cd frontend
npm install --save-dev @capacitor/assets
# (re)create frontend/assets/* at the sizes above, then:
npx capacitor-assets generate --android      # writes ~136 files into android/.../res/
npm uninstall @capacitor/assets              # ALWAYS remove it again
npm run build && npx cap sync android
```

**After running it, re-verify the manifest** — the tool **reformats `AndroidManifest.xml`** and you
must confirm these survived: `RECORD_AUDIO`, `MODIFY_AUDIO_SETTINGS`, the `com.rohitpatil.fluently`
deep-link filter, `BROWSABLE`, `INTERNET`.

Check the *generated* result, not just the source: open
`app/src/main/res/mipmap-xxxhdpi/ic_launcher.png`. Android caches launcher icons aggressively —
if the old icon persists, clear the launcher (`adb shell pm clear com.sec.android.app.launcher` on
Samsung) or reboot. A full uninstall also works but **wipes the stored session token**.

---

## 8. Sharing the APK / releasing to Play Store

**Sharing with people now:** send `app/build/outputs/apk/debug/app-debug.apk` (~4.9 MB). The
recipient must allow "install from unknown sources". It talks to production, so it just works.
This is a **debug** build — fine for testers, not acceptable for the Play Store.

**Play Store requires a signed release AAB** — not built yet. Outstanding work:

1. **Create a keystore.** ⚠️ **Irreversible:** every future update must be signed with the *same*
   key. Lose it and the app can **never** be updated — you'd need a new listing and would lose all
   users and reviews. Back it up (password manager / secure cloud) and **never commit it**
   (`*.jks`/`*.keystore` are gitignored).
2. Add a `signingConfig` + release block to `app/build.gradle`, keeping credentials **out of Git**
   (use `local.properties`, gitignored, or environment variables).
3. Set `VITE_API_URL` to production, rebuild, then `./gradlew bundleRelease`.
4. **Bump `versionCode`** for *every* Play upload (must strictly increase); `versionName` is the
   human-facing string.
5. Play Console: $25 one-time account, store listing, screenshots, a **privacy policy URL**
   (mandatory — the app handles Google account data, chat content and microphone audio, and sends
   text/audio to Google Gemini), and the data-safety form.
6. ⏳ **New personal developer accounts must run a closed test with ≥12 testers for 14 days**
   before production access, plus ~7 days review. **Budget ~3 weeks of calendar time** independent
   of code readiness.

**No OTA.** Live-updates (e.g. `@capgo/capacitor-updater`) were evaluated and **deliberately
skipped** (paid). Consequence: **every** change — even a one-line CSS tweak — needs a new bundle
uploaded to Play, and users update through the store.

---

## 9. Troubleshooting — real failures seen here, and the fix

| Symptom | Cause & fix |
|---|---|
| `JAVA_HOME is not set` from `gradlew` | Terminal Gradle can't see Android Studio's JDK. Set `JAVA_HOME` to `C:\Program Files\Android\Android Studio\jbr`. |
| Build fails on missing SDK | **SDK Platform 36** not installed. SDK Manager → SDK Platforms → tick API 36. |
| `adb devices` → **`unauthorized`** | The "Allow USB debugging?" prompt wasn't accepted. Accept it (tick *always allow*); replug the cable if it doesn't appear. Recurs after revoking authorization. |
| `adb devices` → empty | USB is in "charging only" — switch the phone's USB mode to **File Transfer / MTP**. |
| App shows **"Can't reach your companion"** | Almost always **CORS**: the backend's `CORS_ALLOWED_ORIGINS` is missing `https://localhost` (the WebView's origin). Diagnose with `curl -i <backend>/api/health -H "Origin: https://localhost"` and look for `access-control-allow-origin`. Its absence is the bug. |
| Login opens the browser, succeeds, **never returns to the app** | The backend is missing the native flow, or the deep link isn't registered. Check the state cookie from `/api/auth/google/login?native=1` — the signed payload must end in **`:native`**. If it doesn't, prod is running old code. Verify registration: `adb shell pm dump com.rohitpatil.fluently \| grep -i "com.rohitpatil.fluently://"`. |
| Logged in, but UI still shows the login screen | React Query cached the pre-login **401** and `['me']` uses `retry:false`; an *invalidate* doesn't refetch an errored query. `main.jsx` uses **`resetQueries()`** after the deep link for exactly this reason. |
| Voice/mic says **"not authenticated"** while text chat works fine | The WebSocket isn't carrying the token. Sockets can't send headers — `api.js` must append `?token=`, and the backend must read it (`deps.user_id_from_websocket`). |
| Mic silently fails | `RECORD_AUDIO` missing from the manifest, or permission denied. Check: `adb shell dumpsys package com.rohitpatil.fluently \| grep RECORD_AUDIO` → expect `granted=true`. |
| Blank/white screen | `webDir` mismatch, or the web app wasn't built before syncing. Run `npm run build` **then** `npx cap sync android`. |
| Old icon still showing | Launcher icon cache. Clear the launcher or reboot (see §7). |
| Release build can't reach the backend | `VITE_API_URL` still `localhost`, and/or a leftover `server.url` block in `capacitor.config.json` (a dev-only live-reload setting that **must not** ship). |
| Content hidden under the status bar / notch | Capacitor 8 draws **edge-to-edge**. Handled by the `html.capacitor-native` safe-area rule in `src/index.css`, applied only in the app. |

---

## 10. Rules for editing here

- **Never** re-run `npx cap add android` on this project — it would discard the hand-edited
  manifest, the debug network config, and the generated icons.
- Web/native branching belongs in **`src/platform.js`** (and `authToken.js` for the session).
  Don't scatter `Capacitor.isNativePlatform()` checks through components.
- Anything in `src/` must keep working **as a plain website** — every native path is a no-op on web.
- Changing the deep-link scheme means changing **three** places: the manifest intent-filter,
  `backend/app/config.py::native_app_redirect`, and `backend/.env.example`.
- Adding a Capacitor plugin ⇒ `npx cap sync android` **and** a new bundle for users (native code
  changed, so OTA-style web-only updates could never cover it).
- Keystores, `local.properties`, and build outputs **never** go into Git.
- After changing anything documented here, update this file in the same session.
