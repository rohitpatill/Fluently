import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useQueryClient } from '@tanstack/react-query';

import Rail from './components/Rail';
import Login from './components/Login';
import Onboarding, { BrainStep } from './components/Onboarding';
import Chat from './components/Chat';
import Words from './components/Words';
import Memory from './components/Memory';
import SettingsView from './components/SettingsView';
import { FullScreenError, FullScreenLoader } from './components/Shared';
import { useHealth, useMe, useMemoryFile, usePersonaMemory } from './hooks/useApi';
import useKeyboardInset from './hooks/useKeyboardInset';
import { parseIdentityName, parsePersonaName } from './utils';

export default function App() {
  const [view, setView] = useState('chat');
  const queryClient = useQueryClient();
  const { open: keyboardOpen } = useKeyboardInset();

  const health = useHealth();
  const me = useMe();

  // Persona/identity are only needed once we know the user is authenticated.
  const authed = !!me.data;
  const persona = usePersonaMemory({ enabled: authed });
  const identity = useMemoryFile('identity', { enabled: authed });

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

  const personaName = parsePersonaName(persona.data?.raw) || me.data.name || 'your companion';
  const userName = parseIdentityName(identity.data?.raw) || me.data.name;

  return (
    <div className="h-dvh min-h-0 flex flex-col md:flex-row animate-fade-in">
      <Rail view={view} setView={setView} personaName={personaName} userName={userName} me={me.data} hidden={keyboardOpen} />
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
            {view === 'chat' && <Chat personaName={personaName} />}
            {view === 'words' && <Words />}
            {view === 'memory' && <Memory personaName={personaName} />}
            {view === 'settings' && <SettingsView personaName={personaName} me={me.data} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
