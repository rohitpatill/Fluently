# RELEASE.md — shipping a new Fluently Android version

The step-by-step runbook for getting code changes onto the Play Store. Follow it in order.

**Read [frontendAndroidContext.md](frontendAndroidContext.md) first** if you have never built this
app before — it covers machine requirements, architecture, and troubleshooting. This file assumes
that setup already works.

> **No OTA.** There are no live/over-the-air updates (deliberately — the services are paid). So
> **every** change that should reach users, even a one-line CSS tweak, needs a new bundle uploaded
> to Play. The website updates instantly on deploy; the app does not.

---

## 0. Before you start

| Prerequisite | Check |
|---|---|
| `android/keystore.properties` exists | Required to sign. Restore from your backup if missing — it is gitignored, so a fresh clone will NOT have it. |
| `android/fluently-release.jks` exists | The upload key. Same as above. **Without it you cannot ship at all.** |
| Backend changes deployed | If this release depends on new API behavior, deploy the backend FIRST — users get the app update at unpredictable times. |
| `frontend/.env` has the production URL | `VITE_API_URL=https://api.fluently.fun` (see step 2). |

---

## 1. Decide what kind of change this is

| Change | Needs a new bundle? |
|---|---|
| React code, CSS, copy, prompts, API calls | **Yes** (no OTA) |
| Backend-only change | No — just deploy the backend |
| New Capacitor plugin, manifest, permissions, icon, SDK/Capacitor upgrade | **Yes**, and re-check the manifest (see §6) |

---

## 2. Point the build at production

`VITE_API_URL` is **baked into the bundle at build time**. A release built against `localhost` is
broken for everyone.

In `frontend/.env`:
```
VITE_API_URL=https://api.fluently.fun
```

Also confirm `frontend/capacitor.config.json` has **no `server` block** — that is a dev-only
live-reload setting and shipping it produces an app that tries to load from a dev machine.

---

## 3. Bump the version

In `frontend/android/app/build.gradle`:

```gradle
versionCode 3        // MUST be higher than every previous upload, on ANY track
versionName "1.1"    // human-facing; bump for real feature releases
```

⚠️ `versionCode` is **global across internal / closed / production**. Play rejects a reused value
(`"Version code N has already been used"`). Used so far: `1` (internal), `2` (closed testing).

> If you only want an existing build on a different track, do **not** rebuild — use Play Console's
> **Promote release** action instead.

---

## 4. Build

```bash
cd frontend
npm run build                # produces dist/ with the prod API URL baked in
npx cap sync android         # copies dist/ into the native project + updates plugins
```

Then, from a terminal (Gradle needs Android Studio's bundled JDK):

```powershell
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
cd D:\Study\ENG\frontend\android
.\gradlew.bat bundleRelease          # AAB for the Play Store
.\gradlew.bat assembleRelease        # optional: signed APK for direct sharing
```

Outputs:
```
app/build/outputs/bundle/release/app-release.aab     ← upload this to Play
app/build/outputs/apk/release/app-release.apk        ← share directly (not via Play)
```

---

## 5. Verify the artifact BEFORE uploading

Cheap checks that catch the mistakes that actually happen:

```bash
# 1. Production URL is baked in (and localhost is NOT)
cd frontend
rm -rf dist && npm run build            # stale hashed bundles cause false results
grep -l "api.fluently.fun" dist/assets/*.js

# 2. The AAB is signed with your key
#    (PowerShell, with JAVA_HOME set as above)
#    $as = (gci "$env:LOCALAPPDATA\Android\Sdk\build-tools\*\apksigner.bat" | select -last 1).FullName
#    & $as verify --print-certs app\build\outputs\apk\release\app-release.apk
#    → expect: CN=Rohit Patil, OU=Fluently

# 3. No debug cleartext config leaked into the release
cd android
unzip -l app/build/outputs/bundle/release/app-release.aab | grep -i network_security
#    → expect NO matches
```

---

## 6. If native things changed

Re-verify the merged manifest kept everything (icon-generation tools and Capacitor upgrades have
silently reformatted it before):

- `RECORD_AUDIO` + `MODIFY_AUDIO_SETTINGS` — voice mode dies without them
- The deep-link `intent-filter` with scheme `com.rohitpatil.fluently` + `BROWSABLE` — login dies without it
- `res/values/strings.xml` → `custom_url_scheme` must match that scheme (Capacitor reads it here)

Changing the deep-link scheme means changing **four** places: the manifest, `strings.xml`,
`backend/app/config.py::native_app_redirect`, and the deployed `NATIVE_APP_REDIRECT` env var.

---

## 7. Upload to Play Console

1. **Testing → Closed testing** (or Production, once you have access) → **Create new release**
2. Upload `app-release.aab`
3. **Release name:** `<versionName> (<versionCode>)`, e.g. `1.1 (3)`
4. **Release notes:** inside the `<en-US>` tags — these ARE shown to testers/users
5. **Review release → Start rollout**

Review takes hours to a few days. Google emails the outcome.

---

## 8. Sanity-test the released build on a real device

Install from the Play link (not the sideloaded APK — different signing chain, see the context file)
and verify the full path, because these are the parts most likely to break in a *release* build:

- [ ] App opens, no white screen, safe areas correct
- [ ] **Google login completes and returns to the app** (system browser → deep link → logged in)
- [ ] Text chat works and scoring chips appear
- [ ] **Voice mode connects** (mic permission prompt → assistant speaks)
- [ ] Words / Memory / Settings load

If login opens the browser but never returns, the deployed `NATIVE_APP_REDIRECT` does not match the
app's scheme — see §6 and the troubleshooting table in the context file.

---

## 9. After shipping

- Note the new `versionCode` (the next release must exceed it)
- Commit the `versionCode`/`versionName` bump
- Keep `keystore.properties` and `fluently-release.jks` backed up — they are gitignored and a fresh
  clone will not have them
