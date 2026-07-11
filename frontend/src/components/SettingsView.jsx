import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { AlertTriangle, Loader2, MessagesSquare, NotebookPen, ShieldAlert, Trash2 } from 'lucide-react';

import * as api from '../api';

/* Danger levels: soft (accent-outline confirm) vs hard (type-to-confirm). */

function DangerCard({ icon: Icon, title, description, keeps, buttonLabel, danger, confirmWord, onConfirm, busy }) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState('');
  const needsTyping = !!confirmWord;
  const armed = !needsTyping || typed.trim().toLowerCase() === confirmWord;

  async function run() {
    setOpen(false);
    setTyped('');
    await onConfirm();
  }

  return (
    <div className={`bg-surface border rounded-[18px] p-5 ${danger ? 'border-[#F2CBC7]' : 'border-border'}`}>
      <div className="flex items-start gap-4">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${danger ? 'bg-[#FCEFEE] text-red' : 'bg-accent-soft text-accent'}`}>
          <Icon size={18} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[15px] font-bold">{title}</div>
          <p className="mt-1 mb-0 text-[13px] text-muted leading-relaxed">{description}</p>
          {keeps && <p className="mt-1.5 mb-0 text-[12px] text-[#1E7D4B]">Keeps: {keeps}</p>}
        </div>
        {!open && (
          <button
            onClick={() => setOpen(true)}
            disabled={busy}
            className={`shrink-0 rounded-xl px-4 py-2 text-[13px] font-semibold cursor-pointer transition-colors border ${
              danger
                ? 'bg-transparent text-red border-[#F2CBC7] hover:bg-[#FCEFEE]'
                : 'bg-transparent text-accent border-accent-soft-border hover:bg-accent-soft'
            } disabled:opacity-50`}
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : buttonLabel}
          </button>
        )}
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className={`mt-4 rounded-xl border px-4 py-3.5 ${danger ? 'bg-[#FCEFEE] border-[#F2CBC7]' : 'bg-amber-bg border-amber-border'}`}>
              <div className={`flex items-center gap-2 text-[13px] font-semibold ${danger ? 'text-red' : 'text-amber-text'}`}>
                <AlertTriangle size={14} />
                This cannot be undone. It is a permanent, hard delete.
              </div>
              {needsTyping && (
                <input
                  value={typed}
                  onChange={(e) => setTyped(e.target.value)}
                  placeholder={`Type "${confirmWord}" to confirm`}
                  autoFocus
                  className="mt-3 w-full bg-surface border border-border-2 rounded-[10px] px-3.5 py-2.5 text-[13.5px] outline-none text-text focus:border-[#F2CBC7]"
                />
              )}
              <div className="flex gap-2.5 mt-3">
                <button
                  onClick={run}
                  disabled={!armed}
                  className={`rounded-[10px] px-4 py-2 text-[13px] font-semibold border-none cursor-pointer transition-colors text-white ${
                    danger ? 'bg-red hover:bg-[#A8443E]' : 'bg-accent hover:bg-accent-hover'
                  } disabled:opacity-40 disabled:cursor-not-allowed`}
                >
                  Yes, {buttonLabel.toLowerCase()}
                </button>
                <button
                  onClick={() => { setOpen(false); setTyped(''); }}
                  className="rounded-[10px] px-4 py-2 text-[13px] font-semibold bg-transparent text-muted border border-border-2 cursor-pointer hover:bg-[#F1F2F6] transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function SettingsView({ personaName }) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);

  async function exec(fn, successMsg) {
    setBusy(true);
    try {
      await fn();
      queryClient.invalidateQueries(); // everything may have changed
      toast.success(successMsg);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="h-full overflow-y-auto px-14 py-9">
      <div className="max-w-[760px] mx-auto">
        <h2 className="m-0 text-[28px] font-bold tracking-tight">Settings</h2>
        <p className="mt-1.5 mb-0 text-sm text-muted">More coming here over time.</p>

        <div className="mt-8">
          <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2 mb-3">Data management</div>
          <div className="flex flex-col gap-3.5">
            <DangerCard
              icon={MessagesSquare}
              title="Delete all conversations"
              description={`Every chat with ${personaName} is permanently deleted.`}
              keeps="your words & scores, all memories, the persona"
              buttonLabel="Delete conversations"
              busy={busy}
              onConfirm={() => exec(api.purgeConversations, 'All conversations deleted')}
            />
            <DangerCard
              icon={NotebookPen}
              title="Delete memories"
              description={`Everything ${personaName} has learned about you and your life is erased — identity and life notebooks reset to blank.`}
              keeps="conversations, words & scores, the persona"
              buttonLabel="Delete memories"
              busy={busy}
              onConfirm={() => exec(api.purgeMemories, 'Memories erased')}
            />
            <DangerCard
              icon={Trash2}
              title="Delete everything, keep my words"
              description={`Conversations, memories and ${personaName} themself are all permanently deleted. The app starts fresh from onboarding — but your tracked words and their proficiency scores survive.`}
              keeps="words & proficiency scores only"
              buttonLabel="Reset app"
              danger
              confirmWord="reset"
              busy={busy}
              onConfirm={() => exec(() => api.purgeAll(true), 'Fresh start — your words survived')}
            />
            <DangerCard
              icon={ShieldAlert}
              title="Delete everything"
              description={`The full wipe: conversations, memories, ${personaName}, your words, scores, history — every trace, hard-deleted from the database. The app restarts as if installed today.`}
              buttonLabel="Delete everything"
              danger
              confirmWord="delete everything"
              busy={busy}
              onConfirm={() => exec(() => api.purgeAll(false), 'Everything deleted — starting fresh')}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
