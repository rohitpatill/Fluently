# Deployment Guide — Fluently (and any split frontend/backend app)

> A hard-won checklist. This app is deployed as **two separate services**:
> **frontend on Vercel**, **backend on Render**, with **Google OAuth** and a **custom
> domain**. This guide captures every trap we hit so we never repeat them.
>
> **Golden rule:** NOTHING that changes between environments (URLs, origins, secrets)
> may be hardcoded in source. It ALL comes from environment variables. This file
> contains **no real keys or URLs** — placeholders only — so it is safe to commit.

---

## 0. The mental model (read this first)

A split deployment has **two independent services on two different domains**:

```
   Browser
      │
      ▼
  FRONTEND  (Vercel)      e.g.  https://yourapp.com
      │  calls the backend over HTTPS (cross-site)
      ▼
  BACKEND   (Render)      e.g.  https://api.yourapp.com
      │
      ├── MongoDB Atlas (database)
      └── Google OAuth  (login)
```

Because the frontend and backend are on **different domains**, the browser treats
every API call as **cross-site**. That single fact is the root cause of ~80% of the
problems below (CORS, cookies, redirects). Keep it in mind.

Three URLs you must always keep straight — write them down before you start:

| Name | What it is | Example placeholder |
|------|-----------|---------------------|
| **FRONTEND URL** | Where the React app is served | `https://yourapp.com` |
| **BACKEND URL** | Where the API is served | `https://api.yourapp.com` |
| **OAUTH CALLBACK** | Backend path Google redirects to | `<BACKEND>/api/auth/google/callback` |

---

## 1. The #1 mistake — hardcoded URLs (fix BEFORE deploying)

**What went wrong:** the frontend had `const BASE_URL = 'http://localhost:8000'`
baked into the source. When deployed, it still called `localhost` → nothing worked.

**Rule:** the frontend must read the backend URL from a build-time env var. With Vite:

```js
// api.js — CORRECT
const BASE_URL = import.meta.env.VITE_API_URL;
// every endpoint is built from this: `${BASE_URL}/api/...`
```

**Vite gotcha:** env vars are **baked in at BUILD time**, not runtime. So:
- The var **must** exist in the hosting dashboard **before** the build runs.
- If you add/change it later, you **must trigger a fresh rebuild** (and disable build
  cache) or the old value stays baked in.
- Client-exposed vars **must** be prefixed `VITE_` or Vite strips them.

**Never** `git push` a real `.env`. Only commit `.env.example` with placeholders.

**Checklist:**
- [ ] Zero hardcoded `http://localhost`, IPs, or full API URLs in frontend source
      (grep the whole `src/` for `localhost`, `:8000`, `http://`, `fetch(`, `axios`).
- [ ] The one allowed reference is display/error text — not a real request target.
- [ ] All API calls go through a single wrapper that uses the env var.

---

## 2. The #2 mistake — CORS (cross-origin) blocking every call

**Symptom:** backend logs show `OPTIONS /api/... 400 Bad Request` (or the browser
console says "blocked by CORS policy"). The `OPTIONS` request is the browser's
**CORS preflight** — if it fails, the real request never happens.

**Cause:** the backend's allowed-origins list was hardcoded to `localhost` and didn't
include the deployed frontend origin.

**Rule:** allowed origins come from an env var — a comma-separated list. **Never
hardcode**, and **never use `*` when cookies/credentials are involved** (browsers
forbid `allow_origins="*"` together with `allow_credentials=True` — login breaks).

```python
# main.py — CORRECT (reads a comma-separated env var)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,  # from CORS_ALLOWED_ORIGINS
    allow_credentials=True,                    # required for cookie auth
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`CORS_ALLOWED_ORIGINS` must list **every** origin that will call the API:
```
CORS_ALLOWED_ORIGINS=http://localhost:5173,https://yourapp.com
```

**Checklist:**
- [ ] Every deployed frontend origin is in `CORS_ALLOWED_ORIGINS`.
- [ ] Origins are the **scheme + host** only — no trailing slash, no path.
- [ ] Keep `localhost` entries so local dev still works.
- [ ] Not using `*` (incompatible with credentialed cookie auth).

---

## 3. The #3 mistake — cross-site session cookies don't stick

**Symptom:** Google login **succeeds** (callback runs, redirects) but the very next
`/api/auth/me` returns **401** and you bounce back to the login screen — a loop.

**Cause:** the session cookie was set with `SameSite=Lax`. Browsers **drop Lax
cookies on cross-site requests**, so with frontend and backend on different domains
the cookie is never stored/sent.

**Rule:** for a cross-site frontend↔backend, the auth cookie MUST be:
- `SameSite=None` **and**
- `Secure=True` (browsers only accept `SameSite=None` over HTTPS)

Make this **automatic and config-driven**, not manual:

```python
# config.py — decide cookie flags from the deployment URLs
@property
def cookie_secure(self) -> bool:
    return self.oauth_redirect_base.lower().startswith("https")

@property
def cookie_samesite(self) -> str:
    # 'none' when frontend & backend are different sites AND we're on https
    return "none" if (self.cross_site and self.cookie_secure) else "lax"
```

Then apply `secure=` and `samesite=` from config on **every** `set_cookie` **and**
`delete_cookie` call (mismatched flags on delete = logout silently fails).

**Consequence you must accept:** because `SameSite=None` requires `Secure` (HTTPS),
you **cannot** test a cross-site deploy with an `http://localhost` frontend against an
HTTPS backend — the cookie won't stick. Test either fully local (both localhost) OR
fully deployed (both HTTPS).

**Checklist:**
- [ ] Cookie `secure` + `samesite` are derived from env, not hardcoded.
- [ ] Same flags used on set AND delete.
- [ ] Backend URL is HTTPS in production (so `Secure` turns on).

---

## 4. Environment variables — the single source of truth

Keep **one** `.env.example` per service, committed, with placeholders only. Real
values live ONLY in the hosting dashboards (Render/Vercel) and your local `.env`
(git-ignored).

### Frontend (Vercel) env vars
| Key | Meaning | Example |
|-----|---------|---------|
| `VITE_API_URL` | Backend base URL (no trailing slash, no `/api`) | `https://api.yourapp.com` |

### Backend (Render) env vars
| Key | Meaning | Notes |
|-----|---------|-------|
| `MONGODB_URI` | DB connection string incl. db name | secret |
| `MONGODB_DB` | Database name | e.g. `yourdb` |
| `ENCRYPTION_KEY` | App's at-rest encryption key | **secret — never rotate once data exists** |
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth client id | from Google Console |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth client secret | secret |
| `OAUTH_REDIRECT_BASE` | Public **backend** URL | `https://api.yourapp.com` (also flips cookies to Secure) |
| `FRONTEND_URL` | Public **frontend** URL | `https://yourapp.com` (post-login redirect) |
| `CORS_ALLOWED_ORIGINS` | Comma list of allowed origins | `http://localhost:5173,https://yourapp.com` |
| `SESSION_SECRET` | Signs the session JWT | secret, strong random |
| `STATE_COOKIE_SECRET` | Signs the OAuth state/nonce cookie | secret, strong random |
| `SESSION_MAX_AGE_DAYS` | Session lifetime | e.g. `7` |

> **Do not** set app-owned LLM provider keys for real users if the app uses
> bring-your-own-key — those are legacy/unused. Users supply their own key at runtime.

**The classic env trap:** setting a var in the dashboard AFTER the first deploy and
expecting it to take effect. It won't for a Vite frontend (build-time bake-in) —
**redeploy without build cache**. For the backend, a restart/redeploy picks up new
env vars.

---

## 5. Google Cloud Console — OAuth setup

In **APIs & Services → Credentials → your OAuth 2.0 Web client**, two boxes matter and
they are **not** the same thing:

| Box | What goes here | Value |
|-----|----------------|-------|
| **Authorized redirect URIs** | The **backend** callback (server does the code exchange) | `<BACKEND>/api/auth/google/callback` |
| **Authorized JavaScript origins** | The **frontend** origin (browser) | `<FRONTEND>` |

Add BOTH the local and production values so both environments work:
```
Redirect URIs:
  http://localhost:8000/api/auth/google/callback
  https://api.yourapp.com/api/auth/google/callback
JavaScript origins:
  http://localhost:5173
  https://yourapp.com
```

The redirect URI must match **exactly** (scheme, host, path) what the backend builds
from `OAUTH_REDIRECT_BASE`. A mismatch = `redirect_uri_mismatch` error.

**Consent screen branding:** to show your **app name** (not the raw domain) on the
Google account-chooser, fill in the **OAuth consent screen** (app name, logo, support
email, homepage, privacy policy). Showing a fully branded/"verified" screen requires
**a domain you own** + Google's verification review — you cannot fully brand it on a
free `*.onrender.com` / `*.vercel.app` subdomain.

**Changes can take minutes to hours to apply.**

---

## 6. Custom domain — required to look professional AND to avoid the red warning

**Symptom we hit:** Chrome showed a red **"Dangerous site"** / Safe Browsing wall on
the free `*.onrender.com` (and sometimes `*.vercel.app`) URL. This is **not your code**
— free shared subdomains inherit bad reputation from other users abusing them, and an
OAuth login page trips heuristics.

**The only reliable fix:** put **both** services on **your own domain**:

```
Frontend →  yourapp.com          (Vercel)
Backend  →  api.yourapp.com      (Render)   ← this one was the last flagged piece!
```

Note: fixing only the frontend domain is not enough — during login the browser is
redirected to the **backend**, so a flagged backend URL still shows the warning. Give
the backend a custom subdomain too.

### DNS setup (registrar / e.g. Hostinger → DNS records)

| Service | Record type | Name/Host | Value/Target |
|---------|------------|-----------|--------------|
| Frontend root (Vercel) | `A` | `@` | Vercel's IP (shown in Vercel) |
| Frontend www (Vercel) | `CNAME` | `www` | Vercel's DNS target (shown in Vercel) |
| Backend api (Render) | `CNAME` | `api` | `<your-service>.onrender.com` (shown in Render) |

Steps:
1. In the hosting platform (Render/Vercel) → **Settings → Custom Domains → Add** the
   domain; it shows you the exact record to create.
2. In your **domain registrar's DNS panel**, add that record exactly as shown.
3. Back in Render/Vercel, click **Verify**. DNS can take minutes to 24h to propagate.
4. The platform auto-issues an **SSL certificate** once verified (HTTPS just works).

**After the custom domains are live, update everything to use them:**
- Vercel `VITE_API_URL` → `https://api.yourapp.com` (then **redeploy**)
- Render `OAUTH_REDIRECT_BASE` → `https://api.yourapp.com`
- Render `FRONTEND_URL` → `https://yourapp.com`
- Render `CORS_ALLOWED_ORIGINS` → include `https://yourapp.com`
- Google Console → add the new redirect URI + JavaScript origin
- (Optional) request a Safe Browsing review if a flag lingers.

---

## 7. Platform-specific gotchas

### Vercel (frontend)
- **Root Directory:** set to the frontend subfolder (e.g. `frontend`) if it's a monorepo.
- **Framework preset:** Vite. **Build:** `vite build`. **Output:** `dist`. **Install:** `npm install`.
- Use the **stable project domain** (e.g. `yourapp.vercel.app` or your custom domain),
  NOT the per-deploy URL (`...-hash-...vercel.app`) — that one changes every push.
- Env vars are baked at build → **redeploy (no cache)** after changing them.

### Render (backend)
- **Free tier spins down after inactivity** → first request after idle takes ~50s
  ("Can't reach server" on the first try). Warm it by hitting `<BACKEND>/api/health`
  and waiting, or upgrade off free tier.
- New env vars require a **redeploy/restart** to take effect.
- Bind the server to the port Render provides and `0.0.0.0`.

---

## 8. Debugging playbook (symptom → cause → fix)

| Symptom | Most likely cause | Fix |
|---------|-------------------|-----|
| Frontend calls `localhost:8000` in prod | `VITE_API_URL` missing at build / not rebuilt | Set var, **redeploy without cache** |
| `OPTIONS ... 400` in backend logs; "blocked by CORS" | Frontend origin not in allow-list | Add it to `CORS_ALLOWED_ORIGINS`, redeploy |
| Login succeeds then `/auth/me` 401, bounces to login | Cookie `SameSite=Lax` on cross-site | `SameSite=None; Secure` + HTTPS backend |
| `redirect_uri_mismatch` from Google | Callback URL not registered / mismatched | Add exact `<BACKEND>/api/auth/google/callback` in Console |
| Red "Dangerous site" wall | Safe Browsing flag on free subdomain | Use custom domain for BOTH services |
| Google shows raw domain, not app name | Consent screen not configured/verified | Fill consent screen; verify with owned domain |
| First request very slow / times out | Render free tier cold start | Warm it, or upgrade |
| Env change had no effect | Build-time bake-in (Vite) / no restart | Rebuild frontend / restart backend |

**Where to look:** browser **DevTools → Network** (check the actual Request URL + the
`OPTIONS` preflight response), and the **backend logs** (Render → Logs). These two
together tell you exactly which layer is failing.

---

## 9. Security must-dos

- **Never commit real secrets.** Only `.env.example` with placeholders is committed.
  Real values live in the hosting dashboards + local git-ignored `.env`.
- **If a secret is ever printed, screenshotted, or pasted anywhere — rotate it.**
  Treat it as compromised (DB passwords, OAuth client secret, session secrets).
- **Never rotate an at-rest encryption key** once it has encrypted stored data — the
  data becomes undecryptable. It's the one secret you keep forever.
- Cookies: `HttpOnly` always; `Secure` in production; `SameSite` per the cross-site rule.
- Store **no** third-party OAuth tokens you don't need; read identity from the verified
  ID token and discard the rest.

---

## 10. Fresh-deploy checklist (copy this per environment)

**Before first deploy**
- [ ] No hardcoded URLs/secrets anywhere in source (grep to confirm)
- [ ] `.env.example` up to date; real `.env` git-ignored

**Frontend (Vercel)**
- [ ] Root dir, build/output/install commands correct
- [ ] `VITE_API_URL` set to backend URL (no trailing slash) for the right environment
- [ ] Deployed, then verified in DevTools that requests hit the real backend

**Backend (Render)**
- [ ] All env vars from §4 set (DB, secrets, OAuth, URLs, CORS)
- [ ] `OAUTH_REDIRECT_BASE` = HTTPS backend URL
- [ ] `FRONTEND_URL` = frontend URL
- [ ] `CORS_ALLOWED_ORIGINS` includes the frontend origin

**Google Console**
- [ ] Redirect URI = `<BACKEND>/api/auth/google/callback` (exact)
- [ ] JavaScript origin = `<FRONTEND>`
- [ ] Consent screen filled (app name/logo) if branding matters

**Custom domains (recommended / to remove warnings)**
- [ ] Frontend domain added + DNS record + verified + SSL
- [ ] Backend `api.` subdomain added + CNAME + verified + SSL
- [ ] All env vars + Google Console updated to the custom domains

**Final verification**
- [ ] Open the frontend on its real domain — no security warning
- [ ] Login end-to-end works and the session persists across refresh
- [ ] A protected API call returns data (not 401 / not CORS-blocked)
```
