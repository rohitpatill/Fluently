import { useCallback, useEffect, useState } from 'react';

// Developer mode: a local-only (localStorage) toggle. OFF by default. When ON, the chat
// shows the tool calls the agent made under each assistant message (name + args + output).
// Purely client-side — the tool-call data already ships on every message from the backend.

const KEY = 'fluently.devMode';
const EVENT = 'fluently:devmode';

export function getDevMode() {
  try {
    return localStorage.getItem(KEY) === '1';
  } catch {
    return false;
  }
}

export function useDevMode() {
  const [enabled, setEnabled] = useState(getDevMode);

  useEffect(() => {
    const sync = () => setEnabled(getDevMode());
    // `storage` fires for other tabs; the custom event syncs components in THIS tab.
    window.addEventListener('storage', sync);
    window.addEventListener(EVENT, sync);
    return () => {
      window.removeEventListener('storage', sync);
      window.removeEventListener(EVENT, sync);
    };
  }, []);

  const toggle = useCallback((next) => {
    const value = typeof next === 'boolean' ? next : !getDevMode();
    try {
      localStorage.setItem(KEY, value ? '1' : '0');
    } catch {
      /* ignore quota/private-mode errors */
    }
    window.dispatchEvent(new Event(EVENT));
  }, []);

  return [enabled, toggle];
}
