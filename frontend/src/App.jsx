import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useQueryClient } from '@tanstack/react-query';

import Rail from './components/Rail';
import Onboarding from './components/Onboarding';
import Chat from './components/Chat';
import Words from './components/Words';
import Memory from './components/Memory';
import SettingsView from './components/SettingsView';
import { FullScreenError, FullScreenLoader } from './components/Shared';
import { useHealth, useMemoryFile, usePersonaMemory } from './hooks/useApi';
import { parseIdentityName, parsePersonaName } from './utils';

export default function App() {
  const [view, setView] = useState('chat');
  const queryClient = useQueryClient();

  const health = useHealth();
  const persona = usePersonaMemory();
  const identity = useMemoryFile('identity');

  if (health.isError) {
    return (
      <FullScreenError
        title="Can't reach your companion"
        message="The backend at localhost:8000 isn't responding. Start it, then try again."
        onRetry={() => {
          health.refetch();
          persona.refetch();
          identity.refetch();
        }}
      />
    );
  }

  if (persona.isLoading || health.isLoading) return <FullScreenLoader label="Waking things up…" />;

  const personaName = parsePersonaName(persona.data?.raw);
  if (!personaName) {
    return (
      <Onboarding
        onComplete={() => queryClient.invalidateQueries({ queryKey: ['memory'] })}
      />
    );
  }

  const userName = parseIdentityName(identity.data?.raw);

  return (
    <div className="h-screen flex animate-fade-in">
      <Rail view={view} setView={setView} personaName={personaName} userName={userName} />
      <div className="flex-1 min-w-0 h-full">
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
            {view === 'settings' && <SettingsView personaName={personaName} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
