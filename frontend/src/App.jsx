import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useQueryClient } from '@tanstack/react-query';
import { Sparkles, X } from 'lucide-react';

import Rail from './components/Rail';
import Login from './components/Login';
import Onboarding, { BrainStep } from './components/Onboarding';
import Chat from './components/Chat';
import Words from './components/Words';
import Memory from './components/Memory';
import SettingsView from './components/SettingsView';
import AssistantOverlay from './components/AssistantOverlay';
import AssistantFab from './components/AssistantFab';
import { FullScreenError, FullScreenLoader } from './components/Shared';
import {
  useAssistantStatus,
  useHealth,
  useMe,
  useMemoryFile,
  usePersonaMemory,
  usePersonas,
} from './hooks/useApi';
import useKeyboardInset from './hooks/useKeyboardInset';
import { parseIdentityName, parsePersonaName } from './utils';

// One-time "tap ✦ to ask Fluently anything" pointer, shown once ever (client-only flag).
const ASSISTANT_HINT_KEY = 'fluently.assistantHintSeen';

export default function App() {
  const [view, setView] = useState('chat');
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantHint, setAssistantHint] = useState(false);
  const queryClient = useQueryClient();
  const { open: keyboardOpen } = useKeyboardInset();

  const health = useHealth();
  const me = useMe();

  // Persona/identity are only needed once we know the user is authenticated.
  const authed = !!me.data;
  const persona = usePersonaMemory({ enabled: authed });
  const identity = useMemoryFile('identity', { enabled: authed });
  const personas = usePersonas({ enabled: authed });
  // The assistant needs the user to have a configured key/tier (same gate as voice).
  const assistantStatus = useAssistantStatus({ enabled: authed && !!me.data?.has_key });
  const assistantAvailable = !!assistantStatus.data?.available;

  // First-run pointer to the assistant FAB — shown once ever, after the app is usable.
  useEffect(() => {
    if (assistantAvailable && !localStorage.getItem(ASSISTANT_HINT_KEY)) {
      setAssistantHint(true);
    }
  }, [assistantAvailable]);

  const dismissAssistantHint = () => {
    setAssistantHint(false);
    try { localStorage.setItem(ASSISTANT_HINT_KEY, '1'); } catch { /* noop */ }
  };

  const openAssistant = () => {
    dismissAssistantHint();
    setAssistantOpen(true);
  };

  // The assistant just performed an action over its WebSocket (created a persona, added a word,
  // switched the tier). It wrote straight to the DB, so refresh the affected React Query caches
  // right away — the relevant screen updates live, no manual refresh needed.
  const handleAssistantAction = (name) => {
    if (name === 'add_word') {
      queryClient.invalidateQueries({ queryKey: ['words'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    } else if (name === 'create_persona') {
      queryClient.invalidateQueries({ queryKey: ['personas'] });
      queryClient.invalidateQueries({ queryKey: ['me'] });
    } else if (name === 'switch_model_tier') {
      queryClient.invalidateQueries({ queryKey: ['me'] });
      queryClient.invalidateQueries({ queryKey: ['assistant-status'] });
    }
  };

  if (health.isError) {
    return (
      <FullScreenError
        title="Can't reach your companion"
        message="The backend at localhost:8000 isn't responding. Start it, then try again."
        onRetry={() => {
          health.refetch();
          me.refetch();
        }}
      />
    );
  }

  if (health.isLoading || me.isLoading) return <FullScreenLoader label="Waking things up…" />;

  // Not authenticated (no session / expired) → the login screen.
  if (!authed) return <Login />;

  // Authenticated but onboarding not finished (no persona Name yet) → full onboarding
  // (persona → about you → brain, which also sets the model key).
  if (!me.data.has_persona) {
    return (
      <Onboarding
        onComplete={() => {
          setView('words'); // first stop after onboarding: add words to practice
          queryClient.invalidateQueries({ queryKey: ['memory'] });
          queryClient.invalidateQueries({ queryKey: ['me'] });
        }}
      />
    );
  }

  // Persona set, but no model configured (e.g. a user who onboarded before this feature) →
  // gate on the standalone "How smart should I be?" step until they add a working key + tier.
  if (!me.data.has_key) {
    return (
      <div className="min-h-dvh bg-linear-to-b from-bg to-accent-soft flex items-center justify-center animate-fade-in overflow-y-auto px-4 py-6">
        <div className="w-[620px] max-w-full">
          <BrainStep
            personaName={me.data.name}
            onReady={() => {
              setView('words'); // land on Words so they can start adding practice words
              me.refetch();
            }}
            ctaLabel="Let's go ✦"
          />
        </div>
      </div>
    );
  }

  if (persona.isLoading) return <FullScreenLoader label="Waking things up…" />;

  const activePersona = (personas.data || []).find((p) => p.is_active);
  const personaId = activePersona?.id || null;
  const personaName =
    activePersona?.name || parsePersonaName(persona.data?.raw) || me.data.name || 'your companion';
  const personaAvatar = activePersona?.avatar_url || '';
  const userName = parseIdentityName(identity.data?.raw) || me.data.name;

  return (
    <div className="h-dvh min-h-0 flex flex-col md:flex-row animate-fade-in">
      <Rail view={view} setView={setView} personaName={personaName} personaAvatar={personaAvatar} userName={userName} me={me.data} hidden={keyboardOpen} />
      <div className={`flex-1 min-w-0 min-h-0 h-full md:pb-0 ${keyboardOpen ? 'pb-0' : 'pb-[76px]'}`}>
        <AnimatePresence mode="wait">
          <motion.div
            key={view}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.18 }}
            className="h-full"
          >
            {view === 'chat' && <Chat personaName={personaName} personaAvatar={personaAvatar} personaId={personaId} />}
            {view === 'words' && <Words />}
            {view === 'memory' && <Memory personaName={personaName} />}
            {view === 'settings' && <SettingsView personaName={personaName} me={me.data} />}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Draggable "Ask Fluently" button — app-wide, one tap from anywhere, and movable so it
          never collides with a screen's own controls (e.g. the chat composer). Hidden while the
          mobile keyboard is open, and until the user has a configured model (same gate as voice). */}
      {assistantAvailable && !keyboardOpen && (
        <>
          <AssistantFab onOpen={openAssistant} />

          <AnimatePresence>
            {assistantHint && (
              <motion.div
                initial={{ opacity: 0, y: 8, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.96 }}
                transition={{ duration: 0.25 }}
                className="fixed z-40 left-4 bottom-[120px] w-[248px] rounded-2xl bg-surface border border-border shadow-card p-3.5"
              >
                <button
                  onClick={dismissAssistantHint}
                  aria-label="Dismiss"
                  className="absolute top-2 right-2 text-muted hover:text-text cursor-pointer"
                >
                  <X size={14} />
                </button>
                <div className="flex items-center gap-1.5 text-accent font-semibold text-sm mb-1">
                  <Sparkles size={14} /> New here?
                </div>
                <p className="text-[13px] text-text-2 leading-snug">
                  Tap the logo anytime to <span className="font-serif-italic">talk to Fluently</span> —
                  ask how anything works, or have it set things up for you. Drag it wherever you like.
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}

      <AssistantOverlay
        open={assistantOpen}
        tab={view}
        onAction={handleAssistantAction}
        onClose={() => setAssistantOpen(false)}
      />
    </div>
  );
}
