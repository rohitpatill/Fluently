import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';

import '@fontsource-variable/schibsted-grotesk';
import '@fontsource-variable/newsreader';
import '@fontsource-variable/newsreader/wght-italic.css';
import '@fontsource-variable/jetbrains-mono';

import App from './App.jsx';
import { initAuthDeepLink, initNativeApp } from './platform';
import { loadToken } from './authToken';
import './index.css';

// Native-app (Capacitor) one-time setup. All no-ops on the website, so the web build and the
// cookie-based auth flow are completely unaffected.
initNativeApp();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function renderApp() {
  ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
        <Toaster position="bottom-right" theme="light" richColors />
      </QueryClientProvider>
    </React.StrictMode>
  );
}

// Native app: hydrate the stored session token BEFORE the first render, so the initial
// /api/auth/me call already carries `Authorization: Bearer …` and a logged-in user isn't
// briefly bounced to the login screen. Also register the OAuth deep-link listener, which
// refreshes auth state once a login returns from the system browser.
// On the WEBSITE `loadToken()` resolves immediately with null and the deep-link init is a
// no-op, so this costs one microtask and changes nothing.
loadToken()
  .catch(() => null)
  .then(() => {
    initAuthDeepLink(() => {
      // A native login just completed. `resetQueries` (not `invalidateQueries`) because the
      // ['me'] query is currently in an ERROR state from the pre-login 401 and is configured
      // with retry:false — invalidating an errored query doesn't reliably refetch it, so the
      // UI would stay on the login screen despite having a valid token. A reset clears the
      // error and refetches from scratch.
      queryClient.resetQueries();
    });
    renderApp();
  });
