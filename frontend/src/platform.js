// Platform abstraction — the single source of truth for "are we running inside the
// native (Capacitor) app, or as a plain website?".
//
// WHY THIS EXISTS: the same React codebase ships two ways — as the website (Vercel) and,
// wrapped by Capacitor, as the native Android/iOS app. A few behaviors must differ between
// the two (auth redirect flow, microphone permissions, deep links). Rather than scatter
// `Capacitor.isNativePlatform()` checks across components, every such decision funnels
// through this module. New native concerns get a helper HERE, not an inline check elsewhere.
//
// The website bundle never actually runs Capacitor — `isNativeApp()` is always false there,
// so this module is a no-op cost on web. `@capacitor/core`'s Capacitor global degrades
// gracefully in a normal browser (isNativePlatform() → false), so importing it on the web is safe.

import { Capacitor } from '@capacitor/core';

/** True only when running inside the Capacitor-wrapped native app (Android/iOS). */
export function isNativeApp() {
  return Capacitor.isNativePlatform();
}

/** The current platform: 'web' | 'android' | 'ios'. */
export function platform() {
  return Capacitor.getPlatform();
}

/** True on the plain website (browser), false inside the native app. */
export function isWeb() {
  return !Capacitor.isNativePlatform();
}

/**
 * One-time native-app setup, called once from main.jsx at startup. A no-op on the website
 * (returns immediately), so the web bundle is unaffected. This is the home for any future
 * native bootstrapping (deep-link listeners, status-bar styling, etc.) — add it here, keep
 * main.jsx thin.
 *
 * Currently it tags <html> with `.capacitor-native` so the safe-area CSS in index.css
 * applies ONLY inside the app (the website never gets the class, so its layout is unchanged).
 */
export function initNativeApp() {
  if (!Capacitor.isNativePlatform()) return;
  document.documentElement.classList.add('capacitor-native');
}

/**
 * Register the OAuth deep-link listener — the "return leg" of native login.
 *
 * Native login runs in the system browser; when it finishes, the backend redirects to
 * `com.fluently.app://auth?token=…` (or `?auth_error=1`). Android hands that URL to this app,
 * `@capacitor/app` fires `appUrlOpen`, and we store the token + close the browser tab.
 *
 * `onAuthenticated` is called after a token is stored so the caller can refresh auth state.
 * No-op on the website (which uses the cookie flow and never sees a deep link).
 */
export async function initAuthDeepLink(onAuthenticated) {
  if (!Capacitor.isNativePlatform()) return;

  const { App } = await import('@capacitor/app');
  const { Browser } = await import('@capacitor/browser');
  const { setToken } = await import('./authToken');

  App.addListener('appUrlOpen', async ({ url }) => {
    if (!url || !url.includes('://auth')) return;

    // The custom scheme isn't a URL the URL() parser handles consistently across platforms,
    // so read the query off the raw string.
    const query = url.split('?')[1] || '';
    const params = new URLSearchParams(query);
    const token = params.get('token');

    try {
      await Browser.close();
    } catch {
      /* the tab may already be gone — not an error */
    }

    if (token) {
      await setToken(token);
      onAuthenticated?.();
    }
    // On `auth_error=1` we simply fall through: no token stored, so the app stays on the
    // login screen where the user can retry.
  });
}
