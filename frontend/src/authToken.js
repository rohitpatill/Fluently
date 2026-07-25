// Native-app session token store.
//
// WHY THIS EXISTS: on the WEBSITE the session is an HttpOnly cookie the browser sends
// automatically — nothing to manage. Inside the NATIVE app that's impossible: Google forbids
// OAuth in embedded WebViews, so login runs in the SYSTEM BROWSER, whose cookie jar the app's
// WebView (origin `https://localhost`) cannot read. The backend therefore hands the same signed
// session JWT to the app via a deep link, and the app sends it as `Authorization: Bearer <jwt>`
// (see backend `deps._session_token`, which accepts either transport).
//
// Storage is @capacitor/preferences (native key-value store), NOT localStorage — it survives
// WebView data clearing and is the platform-appropriate place for this.
//
// On the web every function here is a no-op returning null, so the cookie flow is untouched.

import { Preferences } from '@capacitor/preferences';
import { isNativeApp } from './platform';

const TOKEN_KEY = 'fluently.sessionToken';

// Cached in memory so `api.js` can attach the header synchronously on every request without
// awaiting native storage per call. Hydrated once at startup by `loadToken()`.
let cachedToken = null;

/** The current session token, or null. Synchronous — safe to call in a fetch wrapper. */
export function getToken() {
  return cachedToken;
}

/** Load the persisted token into memory. Call once at startup (before the first request). */
export async function loadToken() {
  if (!isNativeApp()) return null;
  try {
    const { value } = await Preferences.get({ key: TOKEN_KEY });
    cachedToken = value || null;
  } catch {
    cachedToken = null;
  }
  return cachedToken;
}

/** Persist a new session token (called after a successful deep-link login). */
export async function setToken(token) {
  cachedToken = token || null;
  if (!isNativeApp()) return;
  try {
    if (token) await Preferences.set({ key: TOKEN_KEY, value: token });
    else await Preferences.remove({ key: TOKEN_KEY });
  } catch {
    /* storage failure shouldn't crash auth — the in-memory token still works this session */
  }
}

/** Forget the session token (logout). */
export async function clearToken() {
  await setToken(null);
}
