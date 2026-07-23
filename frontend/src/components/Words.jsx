import { useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { ChevronDown, Loader2, NotebookPen, Pencil, Plus, Search, Trash2, Trophy, X } from 'lucide-react';

import * as api from '../api';
import { useDashboardStats, useWordEvents, useWords } from '../hooks/useApi';
import { ScoreBar, Spinner, StatCardSkeleton, WordRowSkeleton, REVEAL } from './Shared';
import { relativeTime } from '../utils';

function StatCard({ label, value, accent, warm }) {
  return (
    <div className={`rounded-2xl px-5 py-4 border ${warm ? 'bg-amber-bg border-amber-border' : 'bg-surface border-border'}`}>
      <div className={`text-xs font-semibold tracking-wider uppercase ${warm ? 'text-amber-text-2' : 'text-muted-2'}`}>{label}</div>
      <div className={`mt-1.5 font-bold ${warm ? 'text-[15px] text-amber-text' : accent ? 'text-[26px] font-mono text-accent-hover' : 'text-[26px] font-mono'}`}>
        {value}
      </div>
    </div>
  );
}

function EventHistory({ wordId, expanded }) {
  // History is collapsed by default so it never crowds the meaning — one click reveals it inline.
  const [open, setOpen] = useState(false);
  const show = expanded && open;
  const events = useWordEvents(wordId, show);
  const list = events.data || [];

  return (
    <div className="mt-1 border-t border-[#F1F2F6] pt-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 text-[11px] font-semibold tracking-wider uppercase text-muted-2 hover:text-muted bg-transparent border-none cursor-pointer p-0 transition-colors"
      >
        <ChevronDown size={13} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
        History
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <div className="pt-3">
              {events.isLoading ? (
                <Spinner className="w-5 h-5" />
              ) : !list.length ? (
                <p className="m-0 text-[12.5px] text-muted-2 font-serif-italic">No activity yet — use it in a chat.</p>
              ) : (
                <div className="flex flex-col gap-2 max-h-56 overflow-y-auto pr-2">
                  {list.map((ev) => (
                    <div key={ev.id} className="flex flex-wrap gap-x-2.5 gap-y-1 text-[12.5px] items-baseline">
                      <span className="text-muted-2 w-12 shrink-0">{relativeTime(ev.created_at)}</span>
                      <span className={`font-mono font-semibold shrink-0 ${ev.delta > 0 ? 'text-[#1E7D4B]' : ev.delta < 0 ? 'text-red' : 'text-muted-2'}`}>
                        {ev.delta > 0 ? `+${ev.delta}` : ev.delta}
                      </span>
                      <span className="text-muted-2 shrink-0">{ev.event_type.replace(/_/g, ' ')}</span>
                      {ev.judge_notes && <span className="text-text-3" title={ev.judge_notes}>· {ev.judge_notes}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function PersonalNote({ word }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(word.note || '');

  const save = useMutation({
    mutationFn: (note) => api.setWordNote(word.id, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['words'] });
      setEditing(false);
      toast.success('Note saved');
    },
    onError: (e) => toast.error(e.message),
  });

  function startEdit() {
    setDraft(word.note || '');
    setEditing(true);
  }

  if (editing) {
    return (
      <div className="bg-accent-soft/40 border border-accent-soft-border rounded-xl p-3">
        <div className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wider uppercase text-accent-hover mb-2">
          <NotebookPen size={12} /> My note
        </div>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value.slice(0, 200))}
          autoFocus
          rows={2}
          maxLength={200}
          placeholder="Your own way to remember it — where you saw it, a hook, a translation…"
          className="w-full bg-surface border border-border-2 rounded-lg px-3 py-2 text-[13.5px] outline-none text-text resize-none leading-relaxed focus:border-accent-soft-border"
        />
        <div className="text-right text-[10.5px] text-muted-2 mt-1">{draft.length}/200</div>
        <div className="flex gap-2 mt-2">
          <button
            onClick={() => save.mutate(draft.trim())}
            disabled={save.isPending}
            className="text-xs font-semibold text-white bg-accent hover:bg-accent-hover rounded-lg px-3 py-1.5 border-none cursor-pointer disabled:opacity-50 transition-colors"
          >
            {save.isPending ? 'Saving…' : 'Save'}
          </button>
          <button
            onClick={() => setEditing(false)}
            className="text-xs font-semibold text-muted bg-transparent border border-border-2 rounded-lg px-3 py-1.5 cursor-pointer hover:bg-[#F1F2F6] transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  if (word.note) {
    return (
      <div className="group/note bg-accent-soft/40 border border-accent-soft-border rounded-xl p-3">
        <div className="flex items-center justify-between gap-2 mb-1">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wider uppercase text-accent-hover">
            <NotebookPen size={12} /> My note
          </div>
          <button
            onClick={startEdit}
            title="Edit note"
            className="text-muted-2 hover:text-accent bg-transparent border-none cursor-pointer opacity-100 sm:opacity-0 sm:group-hover/note:opacity-100 transition-opacity"
          >
            <Pencil size={13} />
          </button>
        </div>
        <p className="m-0 text-[13.5px] leading-relaxed text-text-2">{word.note}</p>
      </div>
    );
  }

  return (
    <button
      onClick={startEdit}
      className="self-start inline-flex items-center gap-1.5 text-[12.5px] font-medium text-accent bg-transparent border border-dashed border-accent-soft-border rounded-lg px-3 py-1.5 cursor-pointer hover:bg-accent-soft transition-colors"
    >
      <Plus size={13} /> Add a personal note
    </button>
  );
}

function WordRow({ word, expanded, onToggle }) {
  const queryClient = useQueryClient();
  const [confirmRemove, setConfirmRemove] = useState(false);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['words'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    queryClient.invalidateQueries({ queryKey: ['word-events', word.id] });
  };

  const lower = useMutation({
    mutationFn: () => api.adjustWord(word.id, -10, 'practice more'),
    onSuccess: () => { invalidate(); toast.success(`"${word.text}" lowered — you'll practice it more`); },
    onError: (e) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteWord(word.id),
    onSuccess: () => { invalidate(); toast.success(`"${word.text}" removed`); },
    onError: (e) => toast.error(e.message),
  });

  const mastered = word.score >= 100;

  return (
    <div className="border-b border-[#F1F2F6] last:border-b-0">
      <div onClick={onToggle} className="grid grid-cols-[1fr_auto] sm:flex sm:items-center gap-3 sm:gap-4 px-4 sm:px-6 py-4 cursor-pointer hover:bg-[#FBFBFC] transition-colors">
        <span className="text-[15px] font-semibold sm:w-[190px] sm:shrink-0 flex items-center gap-2 min-w-0">
          <span className="truncate">{word.text}</span>
          {word.kind === 'phrase' && <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-2 bg-[#F1F2F6] rounded-full px-2 py-0.5">phrase</span>}
          {mastered && <Trophy size={13} className="text-[#D9A62E] shrink-0" />}
        </span>
        <div className="col-span-2 sm:col-span-1 sm:flex-1">
          <ScoreBar score={word.score} slipping={false} />
        </div>
        <div className="row-start-1 col-start-2 sm:row-auto sm:col-auto justify-self-end flex items-center gap-2.5 sm:gap-4 shrink-0">
          <span className="font-mono text-sm font-semibold w-9 text-right">{Math.round(word.score)}</span>
          {confirmRemove ? (
            <button
              onClick={(e) => { e.stopPropagation(); remove.mutate(); }}
              disabled={remove.isPending}
              title="Confirm remove"
              className="text-[11px] font-semibold text-red bg-transparent border border-red/40 rounded-full px-2.5 py-1 cursor-pointer hover:bg-red/5 disabled:opacity-50 transition-colors shrink-0"
            >
              {remove.isPending ? '…' : 'sure?'}
            </button>
          ) : (
            <button
              onClick={(e) => { e.stopPropagation(); setConfirmRemove(true); setTimeout(() => setConfirmRemove(false), 2500); }}
              title="Remove word"
              className="text-[#B4B8C4] hover:text-red bg-transparent border-none cursor-pointer p-1 -m-1 transition-colors shrink-0"
            >
              <Trash2 size={15} />
            </button>
          )}
          <motion.span animate={{ rotate: expanded ? 180 : 0 }} className="hidden sm:block text-[#B4B8C4]"><ChevronDown size={15} /></motion.span>
        </div>
      </div>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="overflow-hidden"
          >
            <div className="flex flex-col gap-3 px-4 sm:px-6 pb-5 pt-1 max-w-[720px]">
              <PersonalNote word={word} />
              <p className="m-0 text-[13.5px] leading-relaxed text-text-3">
                <strong>Meaning</strong> — {word.meaning || 'No description yet.'}
                {word.register_notes && <span className="text-muted-2"> · {word.register_notes}</span>}
              </p>
              {word.examples?.slice(0, 2).map((ex, i) => (
                <p key={i} className="m-0 text-[13.5px] leading-relaxed text-text-3 font-serif-italic">“{ex}”</p>
              ))}
              {word.collocations?.length > 0 && (
                <div className="flex gap-2 flex-wrap">
                  {word.collocations.map((c, i) => (
                    <span key={i} className="text-xs bg-[#F1F2F6] rounded-full px-3 py-1 text-text-3">{c}</span>
                  ))}
                </div>
              )}
              <div className="flex flex-wrap items-center gap-2.5 mt-1">
                <span className="text-xs text-muted-2">Practice more:</span>
                <button
                  onClick={() => lower.mutate()}
                  disabled={lower.isPending || word.score <= 0}
                  className="text-xs font-semibold text-accent bg-transparent border border-accent-soft-border rounded-full px-3 py-1 cursor-pointer hover:bg-accent-soft disabled:opacity-45 transition-colors"
                >
                  lower score −10
                </button>
                {confirmRemove ? (
                  <button onClick={() => remove.mutate()} className="text-xs font-semibold text-red bg-transparent border-none cursor-pointer">
                    confirm remove?
                  </button>
                ) : (
                  <button
                    onClick={() => { setConfirmRemove(true); setTimeout(() => setConfirmRemove(false), 2500); }}
                    className="text-xs text-[#B4B8C4] hover:text-red bg-transparent border-none cursor-pointer transition-colors"
                  >
                    remove word
                  </button>
                )}
              </div>
              <EventHistory wordId={word.id} expanded={expanded} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function Words() {
  const queryClient = useQueryClient();
  const words = useWords();
  const stats = useDashboardStats();
  const [newWord, setNewWord] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [search, setSearch] = useState('');

  const add = useMutation({
    mutationFn: (text) => api.addWord(text, text.includes(' ') ? 'phrase' : 'word'),
    onSuccess: (w) => {
      setNewWord('');
      queryClient.invalidateQueries({ queryKey: ['words'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      toast.success(`"${w.text}" added${w.meaning ? ' & enriched' : ''}`);
      setExpandedId(w.id);
    },
    onError: (e) => toast.error(e.status === 409 ? 'You are already tracking that one' : e.message),
  });

  const sorted = useMemo(() => [...(words.data || [])].sort((a, b) => b.score - a.score), [words.data]);
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return q ? sorted.filter((w) => w.text.toLowerCase().includes(q)) : sorted;
  }, [sorted, search]);
  const s = stats.data;

  return (
    <div className="h-full overflow-y-auto px-4 sm:px-7 lg:px-14 py-6 md:py-9">
      <div className="max-w-[980px] mx-auto">
        <div className="flex justify-between items-end flex-wrap gap-4">
          <div>
            <h2 className="m-0 text-[28px] font-bold tracking-tight">Your words</h2>
            <p className="mt-1.5 mb-0 text-sm text-muted">
              {sorted.length ? `${sorted.length} tracked · every conversation makes them stronger` : 'Add the words you want to own.'}
            </p>
          </div>
          <div className="flex w-full sm:w-auto gap-2.5">
            <input
              value={newWord}
              onChange={(e) => setNewWord(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && newWord.trim() && !add.isPending && add.mutate(newWord.trim())}
              placeholder="Add a word or phrase…"
              className="bg-surface border border-border-2 rounded-xl px-4 py-2.5 text-[13.5px] outline-none min-w-0 flex-1 sm:w-[230px] text-text focus:border-accent-soft-border transition-colors"
            />
            <button
              onClick={() => newWord.trim() && add.mutate(newWord.trim())}
              disabled={add.isPending || !newWord.trim()}
              className="bg-accent hover:bg-accent-hover disabled:opacity-55 text-white border-none rounded-xl px-4 sm:px-4.5 py-2.5 text-[13.5px] font-semibold shadow-accent cursor-pointer flex items-center justify-center gap-1.5 transition-colors shrink-0"
            >
              {add.isPending ? (<><Loader2 size={14} className="animate-spin" /> Enriching…</>) : (<><Plus size={14} /> Add</>)}
            </button>
          </div>
        </div>

        {sorted.length > 0 && (
          <div className="mt-5 flex items-center gap-2 bg-surface border border-border-2 rounded-xl px-3.5 focus-within:border-accent-soft-border transition-colors max-w-full sm:max-w-[360px]">
            <Search size={15} className="text-muted-2 shrink-0" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search your words…"
              className="border-none outline-none bg-transparent text-[13.5px] py-2.5 w-full text-text"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                title="Clear search"
                className="text-muted-2 hover:text-muted bg-transparent border-none cursor-pointer p-0.5 -mr-1 shrink-0 transition-colors"
              >
                <X size={15} />
              </button>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 min-[480px]:grid-cols-2 lg:grid-cols-4 gap-3.5 mt-6">
          {stats.isLoading ? (
            Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)
          ) : (
            <>
              <StatCard label="Mastered" value={s ? s.mastered : '—'} />
              <StatCard label="Average score" value={s ? s.average_score : '—'} accent />
              <StatCard label="Strongest" value={s?.top_words?.[0]?.text || '—'} />
              <StatCard label="Slipping" value={s?.slipping_words?.length ? s.slipping_words.map((w) => w.text).join(', ') : 'nothing ✦'} warm />
            </>
          )}
        </div>

        <div className="mt-6 mb-10 bg-surface border border-border rounded-[18px] overflow-hidden">
          {words.isLoading &&
            Array.from({ length: 6 }).map((_, i) => <WordRowSkeleton key={i} />)}
          {!words.isLoading && sorted.length === 0 && (
            <div className="text-center py-14 px-8">
              <p className="m-0 text-[15px] font-semibold">No words yet</p>
              <p className="mt-2 mb-0 text-[13.5px] text-muted font-serif-italic">
                Heard a word you wish you used naturally? Add it — it'll start appearing in your conversations.
              </p>
            </div>
          )}
          {!words.isLoading && sorted.length > 0 && filtered.length === 0 && (
            <div className="text-center py-12 px-8">
              <p className="m-0 text-[14px] font-semibold">No matches</p>
              <p className="mt-1.5 mb-0 text-[13px] text-muted font-serif-italic">
                No word matches “{search.trim()}”.
              </p>
            </div>
          )}
          {!words.isLoading && filtered.length > 0 && (
            <motion.div {...REVEAL}>
              {filtered.map((w) => (
                <WordRow key={w.id} word={w} expanded={expandedId === w.id} onToggle={() => setExpandedId(expandedId === w.id ? null : w.id)} />
              ))}
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
