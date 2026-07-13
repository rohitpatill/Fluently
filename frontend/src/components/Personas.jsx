import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Check, ChevronRight, Loader2, Pencil, Plus, Settings2, Trash2, UserPlus, X } from 'lucide-react';

import * as api from '../api';
import { usePersonaCatalog, usePersonas } from '../hooks/useApi';
import { PersonaAvatar, Spinner } from './Shared';

const RELATIONS = ['Best friend', 'Mentor', 'Girlfriend', 'Boyfriend', 'Teacher'];

// ── The persona identity form — shared by "add new" and "edit". Mirrors onboarding step 1,
//    plus an optional public avatar URL. Self-contained so onboarding stays untouched. ─────
function PersonaForm({ initial, submitLabel, busy, onSubmit, onCancel }) {
  const [name, setName] = useState(initial?.name || '');
  const [relation, setRelation] = useState(
    initial?.relation && RELATIONS.includes(initial.relation) ? initial.relation : ''
  );
  const [customRelation, setCustomRelation] = useState(
    initial?.relation && !RELATIONS.includes(initial.relation) ? initial.relation : ''
  );
  const [personality, setPersonality] = useState(initial?.personality || '');
  const [speakingStyle, setSpeakingStyle] = useState(initial?.speaking_style || '');
  const [avatarUrl, setAvatarUrl] = useState(initial?.avatar_url || '');

  const effectiveRelation = customRelation.trim() || relation;
  const canSubmit = name.trim().length > 0 && effectiveRelation && !busy;

  function submit() {
    if (!canSubmit) return;
    onSubmit({
      name: name.trim(),
      relation: effectiveRelation,
      personality: personality.trim(),
      speaking_style: speakingStyle.trim(),
      avatar_url: avatarUrl.trim(),
    });
  }

  return (
    <div className="flex flex-col gap-4">
      {/* avatar preview + URL */}
      <div className="flex items-center gap-4">
        <PersonaAvatar name={name || '?'} avatarUrl={avatarUrl.trim()} size="lg" />
        <div className="flex-1 min-w-0 bg-surface border border-border-2 rounded-2xl px-4 py-2.5">
          <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2">
            Avatar image URL — optional
          </div>
          <input
            value={avatarUrl}
            onChange={(e) => setAvatarUrl(e.target.value)}
            placeholder="https://…/photo.jpg"
            className="border-none outline-none text-[13.5px] mt-1 w-full bg-transparent text-text font-mono"
          />
        </div>
      </div>

      <div className="bg-surface border border-border-2 rounded-2xl px-4 py-2.5">
        <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2">
          Their name
        </div>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Jack"
          className="border-none outline-none text-lg font-semibold mt-0.5 w-full bg-transparent text-text"
        />
      </div>

      <div>
        <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2 mb-2">
          Who are they to you?
        </div>
        <div className="flex gap-2 flex-wrap">
          {RELATIONS.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => {
                setRelation(r);
                setCustomRelation('');
              }}
              className={`rounded-full px-4 py-1.5 text-[13px] cursor-pointer transition-colors ${
                relation === r && !customRelation
                  ? 'bg-accent text-white font-semibold shadow-accent border-none'
                  : 'bg-surface text-text-3 border border-border-2'
              }`}
            >
              {r}
            </button>
          ))}
          <input
            value={customRelation}
            onChange={(e) => {
              setCustomRelation(e.target.value);
              if (e.target.value) setRelation('');
            }}
            placeholder="something else…"
            className="bg-surface border border-dashed border-[#C9CDD8] rounded-full px-4 py-1.5 text-[13px] text-text-3 outline-none w-[130px]"
          />
        </div>
      </div>

      <div className="bg-surface border border-border-2 rounded-2xl px-4 py-2.5">
        <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2">
          Personality, age, shared history…
        </div>
        <textarea
          value={personality}
          onChange={(e) => setPersonality(e.target.value)}
          placeholder="28, dry sense of humor, brutally honest but always on my side…"
          className="border-none outline-none resize-none text-[14px] leading-relaxed text-text-3 mt-1.5 w-full h-14 bg-transparent font-sans"
        />
      </div>

      <div className="bg-surface border border-border-2 rounded-2xl px-4 py-2.5">
        <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2">
          How they speak — optional
        </div>
        <input
          value={speakingStyle}
          onChange={(e) => setSpeakingStyle(e.target.value)}
          placeholder="casual, lots of slang, short sentences…"
          className="border-none outline-none text-[14px] mt-1 w-full bg-transparent text-text-3"
        />
      </div>

      <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2.5">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-xl px-4 py-2.5 text-[13px] font-semibold bg-transparent text-muted border border-border-2 cursor-pointer hover:bg-[#F1F2F6] transition-colors"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={!canSubmit}
          className="rounded-xl px-5 py-2.5 text-[13px] font-semibold border-none cursor-pointer text-white bg-accent hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors inline-flex items-center justify-center gap-2"
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : submitLabel}
        </button>
      </div>
    </div>
  );
}

// One persona row: avatar, name/relation, active badge, switch/edit/delete actions.
function PersonaRow({ persona, onlyOne, onActivate, onEdit, onDelete, busyId }) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const busy = busyId === persona.id;

  return (
    <div
      className={`bg-surface border rounded-[18px] p-4 sm:p-5 transition-colors ${
        persona.is_active ? 'border-accent shadow-accent' : 'border-border'
      }`}
    >
      <div className="flex items-center gap-4">
        <PersonaAvatar name={persona.name} avatarUrl={persona.avatar_url} size="lg" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[16px] font-bold truncate">{persona.name || 'Unnamed'}</span>
            {persona.is_active && (
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-accent bg-accent-soft rounded-full px-2 py-0.5">
                <Check size={11} strokeWidth={3} /> Active
              </span>
            )}
          </div>
          {persona.relation && <div className="text-[13px] text-muted mt-0.5">{persona.relation}</div>}
          <div className="text-[12px] text-muted-2 mt-0.5">
            {persona.conversation_count} conversation{persona.conversation_count === 1 ? '' : 's'}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mt-4">
        {!persona.is_active && (
          <button
            onClick={() => onActivate(persona)}
            disabled={busy}
            className="rounded-xl px-4 py-2 text-[13px] font-semibold cursor-pointer transition-colors border-none text-white bg-accent hover:bg-accent-hover disabled:opacity-50 inline-flex items-center gap-2"
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : 'Switch to this persona'}
          </button>
        )}
        <button
          onClick={() => onEdit(persona)}
          className="rounded-xl px-4 py-2 text-[13px] font-semibold cursor-pointer transition-colors border bg-transparent text-text-3 border-border-2 hover:bg-[#F1F2F6] inline-flex items-center gap-2"
        >
          <Pencil size={13} /> Edit
        </button>
        {!onlyOne && !confirmDelete && (
          <button
            onClick={() => setConfirmDelete(true)}
            className="rounded-xl px-4 py-2 text-[13px] font-semibold cursor-pointer transition-colors border bg-transparent text-red border-[#F2CBC7] hover:bg-[#FCEFEE] inline-flex items-center gap-2"
          >
            <Trash2 size={13} /> Delete
          </button>
        )}
      </div>

      <AnimatePresence>
        {confirmDelete && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-3 rounded-xl border border-[#F2CBC7] bg-[#FCEFEE] px-4 py-3.5">
              <div className="text-[13px] text-red font-semibold">
                Delete {persona.name} permanently?
              </div>
              <p className="mt-1 mb-0 text-[12.5px] text-muted leading-relaxed">
                Their {persona.conversation_count} conversation
                {persona.conversation_count === 1 ? '' : 's'} will be erased too. Your words and
                proficiency scores are kept.
              </p>
              <div className="flex flex-col sm:flex-row gap-2.5 mt-3">
                <button
                  onClick={() => {
                    setConfirmDelete(false);
                    onDelete(persona);
                  }}
                  disabled={busy}
                  className="rounded-[10px] px-4 py-2 text-[13px] font-semibold border-none cursor-pointer text-white bg-red hover:bg-[#A8443E] disabled:opacity-50 transition-colors"
                >
                  Yes, delete {persona.name}
                </button>
                <button
                  onClick={() => setConfirmDelete(false)}
                  className="rounded-[10px] px-4 py-2 text-[13px] font-semibold bg-transparent text-muted border border-border-2 cursor-pointer hover:bg-[#FBE7E4] transition-colors"
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

// The management surface (list + create + edit). Rendered INSIDE the overlay panel so a long
// list of personas scrolls within it and never pushes the rest of Settings around.
function ManagePanel({ onClose }) {
  const queryClient = useQueryClient();
  const personas = usePersonas();
  const [tab, setTab] = useState('yours'); // 'yours' | 'discover'
  const [mode, setMode] = useState('list'); // 'list' | 'create' | { edit: persona }
  const [busyId, setBusyId] = useState(null);
  const [formBusy, setFormBusy] = useState(false);

  const list = personas.data || [];
  const onlyOne = list.length <= 1;

  // A persona switch changes companion-scoped everything: refresh the app broadly.
  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ['personas'] });
    queryClient.invalidateQueries({ queryKey: ['me'] });
    queryClient.invalidateQueries({ queryKey: ['memory'] });
    queryClient.invalidateQueries({ queryKey: ['conversations'] });
  };

  async function activate(persona) {
    setBusyId(persona.id);
    try {
      await api.activatePersona(persona.id);
      refreshAll();
      toast.success(`Now talking to ${persona.name}`);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setBusyId(null);
    }
  }

  async function remove(persona) {
    setBusyId(persona.id);
    try {
      await api.deletePersona(persona.id);
      refreshAll();
      toast.success(`${persona.name} deleted`);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setBusyId(null);
    }
  }

  async function createPersona(data) {
    setFormBusy(true);
    try {
      await api.createPersona(data);
      queryClient.invalidateQueries({ queryKey: ['personas'] });
      toast.success(`${data.name} created`);
      setMode('list');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setFormBusy(false);
    }
  }

  async function saveEdit(persona, data) {
    setFormBusy(true);
    try {
      await api.editPersona(persona.id, data);
      refreshAll();
      toast.success(`${data.name} updated`);
      setMode('list');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setFormBusy(false);
    }
  }

  if (personas.isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  if (mode === 'create') {
    return (
      <div className="bg-surface border border-border rounded-[18px] p-4 sm:p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="text-[15px] font-bold flex items-center gap-2">
            <UserPlus size={16} className="text-accent" /> New persona
          </div>
          <button
            onClick={() => setMode('list')}
            className="w-8 h-8 rounded-lg border-none bg-[#F1F2F6] text-muted flex items-center justify-center cursor-pointer"
          >
            <X size={16} />
          </button>
        </div>
        <PersonaForm
          submitLabel="Create persona"
          busy={formBusy}
          onSubmit={createPersona}
          onCancel={() => setMode('list')}
        />
      </div>
    );
  }

  if (mode?.edit) {
    const persona = mode.edit;
    return (
      <div className="bg-surface border border-border rounded-[18px] p-4 sm:p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="text-[15px] font-bold flex items-center gap-2">
            <Pencil size={15} className="text-accent" /> Edit {persona.name}
          </div>
          <button
            onClick={() => setMode('list')}
            className="w-8 h-8 rounded-lg border-none bg-[#F1F2F6] text-muted flex items-center justify-center cursor-pointer"
          >
            <X size={16} />
          </button>
        </div>
        <PersonaForm
          initial={persona}
          submitLabel="Save changes"
          busy={formBusy}
          onSubmit={(data) => saveEdit(persona, data)}
          onCancel={() => setMode('list')}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Your personas | Discover toggle */}
      <div className="grid grid-cols-2 gap-1 p-1 bg-[#F1F2F6] rounded-xl">
        {[
          ['yours', 'Your personas'],
          ['discover', 'Discover'],
        ].map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`rounded-lg py-2 text-[13.5px] font-semibold cursor-pointer transition-colors ${
              tab === key ? 'bg-surface text-text shadow-soft' : 'bg-transparent text-muted hover:text-text-3'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'yours' ? (
        <div className="flex flex-col gap-3.5">
          {list.map((p) => (
            <PersonaRow
              key={p.id}
              persona={p}
              onlyOne={onlyOne}
              busyId={busyId}
              onActivate={activate}
              onEdit={(persona) => setMode({ edit: persona })}
              onDelete={remove}
            />
          ))}
          <button
            onClick={() => setMode('create')}
            className="rounded-[18px] border border-dashed border-accent-soft-border bg-accent-soft/40 hover:bg-accent-soft text-accent px-4 py-4 text-[14px] font-semibold cursor-pointer transition-colors inline-flex items-center justify-center gap-2"
          >
            <Plus size={16} /> Add a new persona
          </button>
        </div>
      ) : (
        <DiscoverPanel
          onUsed={(name) => {
            // copied into "Your personas" — refresh the list, close the overlay, and the
            // parent Settings view now shows the new persona under the user.
            queryClient.invalidateQueries({ queryKey: ['personas'] });
            toast.success(`${name} added to your personas`);
            onClose?.();
          }}
        />
      )}
    </div>
  );
}

// ── Discover: curated public personas grouped by category. Card = circular image + name;
//    tapping expands it in place to reveal the description + "Use this persona". ──────────
function DiscoverCard({ persona, expanded, onToggle, onUse, busy }) {
  return (
    <div
      className={`rounded-[18px] border transition-colors ${
        expanded ? 'border-accent bg-accent-soft/40 sm:col-span-2 lg:col-span-3' : 'border-border bg-surface hover:border-accent/40'
      }`}
    >
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex flex-col items-center gap-2.5 px-3 py-4 cursor-pointer bg-transparent border-none"
      >
        <PersonaAvatar name={persona.name} avatarUrl={persona.avatar_url} size="xl" />
        <div className="text-[13.5px] font-semibold text-text text-center leading-tight">{persona.name}</div>
        {!expanded && persona.relation && (
          <div className="text-[11.5px] text-muted-2">{persona.relation}</div>
        )}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 pt-0 flex flex-col items-center text-center gap-3">
              {persona.relation && (
                <span className="text-[11px] font-semibold uppercase tracking-wider text-accent">
                  {persona.relation}
                </span>
              )}
              <p className="m-0 text-[13.5px] leading-relaxed text-text-3 max-w-[440px]">
                {persona.description}
              </p>
              <button
                onClick={onUse}
                disabled={busy}
                className="mt-1 rounded-xl px-5 py-2.5 text-[13.5px] font-semibold border-none cursor-pointer text-white bg-accent hover:bg-accent-hover disabled:opacity-50 transition-colors inline-flex items-center gap-2"
              >
                {busy ? <Loader2 size={14} className="animate-spin" /> : 'Use this persona'}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function DiscoverPanel({ onUsed }) {
  const catalog = usePersonaCatalog();
  const [expandedId, setExpandedId] = useState(null);
  const [busyId, setBusyId] = useState(null);

  async function use(persona) {
    setBusyId(persona.id);
    try {
      await api.usePersonaFromCatalog(persona.id);
      onUsed?.(persona.name);
    } catch (e) {
      toast.error(e.message);
      setBusyId(null);
    }
  }

  if (catalog.isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  const categories = catalog.data || [];

  return (
    <div className="flex flex-col gap-6">
      {categories.map((cat) => (
        <div key={cat.key}>
          <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2 mb-3">
            {cat.label}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 items-start">
            {cat.personas.map((p) => (
              <DiscoverCard
                key={p.id}
                persona={p}
                expanded={expandedId === p.id}
                busy={busyId === p.id}
                onToggle={() => setExpandedId((cur) => (cur === p.id ? null : p.id))}
                onUse={() => use(p)}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// Full-screen overlay holding the management panel. Centered rounded sheet on desktop;
// full-height bottom sheet on mobile (mirrors the app's mobile conversations drawer). The
// panel body scrolls internally, so any number of personas never disturbs Settings.
function ManageOverlay({ onClose }) {
  // Lock background scroll + close on Escape while the overlay is open.
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.16 }}
      className="fixed inset-0 z-50 bg-black/35 backdrop-blur-[2px] flex items-end sm:items-center sm:justify-center sm:p-6"
      onClick={onClose}
    >
      <motion.div
        initial={{ y: '100%', opacity: 0.6 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: '100%', opacity: 0.6 }}
        transition={{ duration: 0.26, ease: [0.2, 0.8, 0.2, 1] }}
        onClick={(e) => e.stopPropagation()}
        className="w-full sm:max-w-[640px] bg-bg sm:rounded-[22px] rounded-t-[22px] shadow-[0_-18px_50px_-24px_rgba(26,29,39,.5)] sm:shadow-card flex flex-col max-h-[92vh] sm:max-h-[85vh] overflow-hidden"
      >
        {/* header */}
        <div className="flex items-center justify-between gap-3 px-5 sm:px-6 py-4 border-b border-border shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="w-9 h-9 rounded-xl bg-accent-soft text-accent flex items-center justify-center shrink-0">
              <Settings2 size={17} />
            </span>
            <div className="min-w-0">
              <div className="text-[16px] font-bold leading-tight">Manage personas</div>
              <div className="text-[12.5px] text-muted truncate">
                Switch, add, edit or remove your companions
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            title="Close"
            className="w-9 h-9 rounded-xl border-none bg-[#F1F2F6] text-muted flex items-center justify-center cursor-pointer shrink-0 hover:bg-border-2 transition-colors"
          >
            <X size={17} />
          </button>
        </div>

        {/* scrollable body */}
        <div className="flex-1 min-h-0 overflow-y-auto px-4 sm:px-6 py-5">
          <ManagePanel onClose={onClose} />
        </div>
      </motion.div>
    </motion.div>
  );
}

// What Settings actually renders: a compact one-line summary of the ACTIVE persona + a
// "Manage" button. Keeps Settings short no matter how many personas exist.
export default function PersonasSettings() {
  const personas = usePersonas();
  const [open, setOpen] = useState(false);

  const list = personas.data || [];
  const active = list.find((p) => p.is_active) || list[0];
  const others = Math.max(0, list.length - 1);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={personas.isLoading}
        className="w-full text-left bg-surface border border-border rounded-[18px] p-4 sm:p-5 flex items-center gap-4 cursor-pointer hover:border-accent/40 transition-colors disabled:opacity-60"
      >
        {personas.isLoading ? (
          <div className="flex items-center gap-4 w-full">
            <div className="w-12 h-12 rounded-full skeleton-shimmer shrink-0" />
            <div className="flex-1">
              <div className="h-3.5 w-32 skeleton-shimmer rounded-md" />
              <div className="h-2.5 w-24 skeleton-shimmer rounded-md mt-2" />
            </div>
          </div>
        ) : (
          <>
            <PersonaAvatar name={active?.name || '?'} avatarUrl={active?.avatar_url} size="lg" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[15.5px] font-bold truncate">
                  {active?.name || 'Your companion'}
                </span>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-accent bg-accent-soft rounded-full px-2 py-0.5">
                  Active
                </span>
              </div>
              <div className="text-[13px] text-muted mt-0.5">
                {list.length} companion{list.length === 1 ? '' : 's'}
                {others > 0 && ` · ${others} other${others === 1 ? '' : 's'} to switch to`}
              </div>
            </div>
            <span className="shrink-0 inline-flex items-center gap-1.5 text-[13px] font-semibold text-accent bg-accent-soft rounded-xl px-3.5 py-2">
              Manage <ChevronRight size={15} />
            </span>
          </>
        )}
      </button>

      <AnimatePresence>{open && <ManageOverlay onClose={() => setOpen(false)} />}</AnimatePresence>
    </>
  );
}
