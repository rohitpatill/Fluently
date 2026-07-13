import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { AlertTriangle, Loader2, LogOut, MessagesSquare, NotebookPen, ShieldAlert, Trash2, Users, Wrench } from 'lucide-react';

import * as api from '../api';
import { useDevMode } from '../hooks/useDevMode';
import { useModelTiers } from '../hooks/useApi';
import { TierCard, Spinner } from './Shared';
import PersonasSettings from './Personas';

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
    <div className={`bg-surface border rounded-[18px] p-4 sm:p-5 ${danger ? 'border-[#F2CBC7]' : 'border-border'}`}>
      <div className="flex flex-col sm:flex-row sm:items-start gap-4">
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
            className={`shrink-0 self-start sm:self-auto rounded-xl px-4 py-2 text-[13px] font-semibold cursor-pointer transition-colors border ${
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
              <div className="flex flex-col sm:flex-row gap-2.5 mt-3">
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

function ToggleRow({ icon: Icon, title, description, checked, onChange }) {
  return (
    <div className="bg-surface border border-border rounded-[18px] p-4 sm:p-5 flex items-start gap-4">
      <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 bg-accent-soft text-accent">
        <Icon size={18} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[15px] font-bold">{title}</div>
        <p className="mt-1 mb-0 text-[13px] text-muted leading-relaxed">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`shrink-0 w-11 h-6 rounded-full relative transition-colors cursor-pointer border-none ${
          checked ? 'bg-accent' : 'bg-border-2'
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-transform ${
            checked ? 'translate-x-5' : ''
          }`}
        />
      </button>
    </div>
  );
}

function ProfileCard({ me, onLogout, loggingOut }) {
  const initial = (me?.name || me?.email || '?').trim().charAt(0).toUpperCase();
  return (
    <div className="bg-surface border border-border rounded-[18px] p-4 sm:p-5 flex flex-col min-[420px]:flex-row min-[420px]:items-center gap-4">
      {me?.picture ? (
        <img
          src={me.picture}
          alt=""
          referrerPolicy="no-referrer"
          className="w-12 h-12 rounded-full object-cover shrink-0"
        />
      ) : (
        <div className="w-12 h-12 rounded-full bg-accent-soft text-accent flex items-center justify-center text-lg font-semibold shrink-0">
          {initial}
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="text-[15px] font-bold truncate">{me?.name || 'Signed in'}</div>
        <div className="text-[13px] text-muted truncate">{me?.email}</div>
      </div>
      <button
        onClick={onLogout}
        disabled={loggingOut}
        className="shrink-0 flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-[13px] font-semibold cursor-pointer transition-colors border bg-transparent text-text-3 border-border-2 hover:bg-[#F1F2F6] disabled:opacity-50 w-full min-[420px]:w-auto"
      >
        {loggingOut ? <Loader2 size={14} className="animate-spin" /> : <LogOut size={14} />}
        Log out
      </button>
    </div>
  );
}

// ── Brain (model) settings: switch Swift↔Sage instantly + replace the API key ─────────
function BrainSettings({ me }) {
  const queryClient = useQueryClient();
  const tiers = useModelTiers();
  const [switching, setSwitching] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [newKey, setNewKey] = useState('');
  const [savingKey, setSavingKey] = useState(false);

  const refreshMe = () => queryClient.invalidateQueries({ queryKey: ['me'] });

  async function pick(tier) {
    if (tier === me.tier || switching) return;
    setSwitching(true);
    try {
      await api.setModelTier(tier);
      await refreshMe();
      toast.success(`Switched to ${tier === 'sage' ? 'Sage' : 'Swift'}`);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSwitching(false);
    }
  }

  async function saveKey() {
    const key = newKey.trim();
    if (!key) return;
    setSavingKey(true);
    try {
      // Re-verify against the current tier, then store. Falls back to swift if tier unset.
      await api.setModelKey(key, me.tier || 'swift');
      await refreshMe();
      setNewKey('');
      setShowKey(false);
      toast.success('API key updated');
    } catch (e) {
      toast.error(e.message || "That key didn't work — double-check it and try again.");
    } finally {
      setSavingKey(false);
    }
  }

  return (
    <div className="flex flex-col gap-3.5">
      {tiers.isLoading ? (
        <div className="flex justify-center py-6"><Spinner /></div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-3">
          {(tiers.data || []).map((t) => (
            <TierCard
              key={t.key}
              tier={t}
              selected={me.tier === t.key}
              onSelect={pick}
              disabled={switching}
            />
          ))}
        </div>
      )}

      <div className="bg-surface border border-border rounded-[18px] p-4 sm:p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[15px] font-bold">API key</div>
            <p className="mt-1 mb-0 text-[13px] text-muted leading-relaxed">
              Your Gemini key is stored encrypted. Replace it anytime — it's re-checked before saving.
            </p>
          </div>
          {!showKey && (
            <button
              onClick={() => setShowKey(true)}
              className="shrink-0 rounded-xl px-4 py-2 text-[13px] font-semibold cursor-pointer transition-colors border bg-transparent text-accent border-accent-soft-border hover:bg-accent-soft"
            >
              Replace key
            </button>
          )}
        </div>
        <AnimatePresence>
          {showKey && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="mt-3.5 flex flex-col sm:flex-row gap-2.5">
                <input
                  type="password"
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  placeholder="New Gemini API key (AIza…)"
                  autoFocus
                  className="flex-1 bg-surface border border-border-2 rounded-[10px] px-3.5 py-2.5 text-[13.5px] font-mono outline-none text-text focus:border-accent"
                />
                <button
                  onClick={saveKey}
                  disabled={!newKey.trim() || savingKey}
                  className="rounded-[10px] px-4 py-2.5 text-[13px] font-semibold border-none cursor-pointer text-white bg-accent hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {savingKey ? <Loader2 size={14} className="animate-spin" /> : 'Save'}
                </button>
                <button
                  onClick={() => { setShowKey(false); setNewKey(''); }}
                  className="rounded-[10px] px-4 py-2.5 text-[13px] font-semibold bg-transparent text-muted border border-border-2 cursor-pointer hover:bg-[#F1F2F6] transition-colors"
                >
                  Cancel
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default function SettingsView({ personaName, me }) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [devMode, setDevMode] = useDevMode();

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await api.logout();
      // Clearing the me cache drops the app back to the login screen; wipe the rest too.
      queryClient.clear();
    } catch (e) {
      toast.error(e.message);
      setLoggingOut(false);
    }
  }

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
    <div className="h-full overflow-y-auto px-4 sm:px-7 lg:px-14 py-6 md:py-9">
      <div className="max-w-[760px] mx-auto">
        <h2 className="m-0 text-[24px] sm:text-[28px] font-bold tracking-tight">Settings</h2>
        <p className="mt-1.5 mb-0 text-sm text-muted">More coming here over time.</p>

        <div className="mt-8">
          <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2 mb-3">Account</div>
          <ProfileCard me={me} onLogout={handleLogout} loggingOut={loggingOut} />
        </div>

        <div className="mt-8">
          <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2 mb-3 flex items-center gap-2">
            <Users size={13} /> Personas
          </div>
          <PersonasSettings />
        </div>

        <div className="mt-8">
          <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2 mb-3">Brain</div>
          <BrainSettings me={me} />
        </div>

        <div className="mt-8">
          <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2 mb-3">Developer</div>
          <ToggleRow
            icon={Wrench}
            title="Developer mode"
            description="Show the tools the agent used behind the scenes — memory updates, conversation searches, score adjustments — under each reply, with their inputs and outputs. Off by default; this is a peek under the hood, not needed for everyday practice."
            checked={devMode}
            onChange={setDevMode}
          />
        </div>

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
              description={`The full wipe: conversations, memories, ${personaName}, your words, scores, history — plus your saved model key & tier. Every trace, hard-deleted. The app restarts as if installed today — you'll pick your brain again from scratch.`}
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
