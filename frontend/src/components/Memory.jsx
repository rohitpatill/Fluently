import { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Check, Loader2 } from 'lucide-react';

import * as api from '../api';
import { useMemoryFile } from '../hooks/useApi';
import { Spinner } from './Shared';

const TABS = (personaName) => [
  { key: 'identity', label: 'About you' },
  { key: 'memory', label: 'Your life' },
  { key: 'persona', label: `Who ${personaName} is` },
];

export default function Memory({ personaName }) {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState('identity');
  const [text, setText] = useState('');
  const [dirty, setDirty] = useState(false);
  const [justSaved, setJustSaved] = useState(false);

  const file = useMemoryFile(tab);

  // load fetched raw into the editor whenever the tab's data arrives (unless user has edits)
  useEffect(() => {
    if (file.data && !dirty) setText(file.data.raw);
  }, [file.data, dirty, tab]);

  const save = useMutation({
    mutationFn: () => api.putMemoryRaw(tab, text),
    onSuccess: () => {
      setDirty(false);
      setJustSaved(true);
      setTimeout(() => setJustSaved(false), 2000);
      queryClient.invalidateQueries({ queryKey: ['memory', tab] });
      toast.success('Memory saved — ' + (tab === 'persona' ? `${personaName} adapts instantly` : `${personaName} will remember`));
    },
    onError: (e) => toast.error(e.message),
  });

  function switchTab(next) {
    if (next === tab) return;
    if (dirty && !window.confirm('You have unsaved changes. Discard them?')) return;
    setDirty(false);
    setTab(next);
    setText('');
  }

  const lineCount = file.data ? file.data.lines.length : 0;

  return (
    <div className="h-full overflow-y-auto px-14 py-9">
      <div className="max-w-[920px] mx-auto flex flex-col h-full">
        <h2 className="m-0 text-[28px] font-bold tracking-tight">What {personaName} remembers</h2>
        <p className="mt-1.5 mb-0 text-sm text-muted">
          Three living notebooks, written by {personaName} as you talk. Edit anything — the change takes effect on the very next message.
        </p>

        <div className="flex gap-2.5 mt-6">
          {TABS(personaName).map((t) => (
            <button
              key={t.key}
              onClick={() => switchTab(t.key)}
              className={`rounded-full px-4.5 py-2 text-[13.5px] cursor-pointer transition-colors border ${
                tab === t.key
                  ? 'bg-accent text-white font-semibold border-transparent shadow-accent'
                  : 'bg-surface text-text-3 border-border-2 hover:bg-[#F1F2F6]'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-5 mb-8 flex-1 min-h-[420px] flex flex-col bg-surface border border-border rounded-[18px] overflow-hidden shadow-soft"
        >
          <div className="flex items-center justify-between px-5 py-3 border-b border-[#F1F2F6] shrink-0">
            <span className="text-xs text-muted-2 font-mono">
              {file.isLoading ? 'loading…' : `${tab}.md · ${lineCount} ${lineCount === 1 ? 'entry' : 'entries'}`}
              {dirty && <span className="text-amber-text-2"> · unsaved changes</span>}
            </span>
            <button
              onClick={() => save.mutate()}
              disabled={!dirty || save.isPending}
              className={`flex items-center gap-1.5 border-none rounded-[10px] px-4 py-1.5 text-[12.5px] font-semibold cursor-pointer transition-all ${
                justSaved
                  ? 'bg-[#EAF8F0] text-[#1E7D4B]'
                  : dirty
                    ? 'bg-accent hover:bg-accent-hover text-white shadow-accent'
                    : 'bg-[#F1F2F6] text-muted-2 cursor-default'
              }`}
            >
              {save.isPending ? (
                <><Loader2 size={12} className="animate-spin" /> Saving…</>
              ) : justSaved ? (
                <><Check size={12} /> Saved</>
              ) : (
                'Save'
              )}
            </button>
          </div>
          {file.isLoading ? (
            <div className="flex-1 flex items-center justify-center"><Spinner /></div>
          ) : (
            <textarea
              value={text}
              onChange={(e) => { setText(e.target.value); setDirty(true); }}
              spellCheck={false}
              className="flex-1 w-full border-none outline-none resize-none bg-transparent px-5 py-4 font-mono text-[13px] leading-[1.75] text-text-2"
              placeholder={`Nothing here yet — ${personaName} writes memories as you talk, or add your own lines.`}
            />
          )}
        </motion.div>
      </div>
    </div>
  );
}
