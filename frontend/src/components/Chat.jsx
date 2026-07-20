import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import { toast } from 'sonner';
import { ChevronDown, Menu, Mic, Plus, Search, Send, Sparkles, Trash2, Wrench, X } from 'lucide-react';

import * as api from '../api';
import { useConversations, useMessages, useVoiceStatus } from '../hooks/useApi';
import { useDevMode } from '../hooks/useDevMode';
import useKeyboardInset from '../hooks/useKeyboardInset';
import { PersonaAvatar, Spinner, ThreadItemSkeleton, MessageBubbleSkeleton } from './Shared';
import VoiceOverlay from './VoiceOverlay';
import { formatThreadTime, nowClockLabel } from '../utils';

const CHIP_STYLES = {
  good: 'bg-[#EAF8F0] border-[#BFE8D2] text-[#1E7D4B]',
  awkward: 'bg-amber-bg border-amber-border text-amber-text',
  wrong: 'bg-[#FCEFEE] border-[#F2CBC7] text-red',
};

function chipKind(eventType) {
  if (eventType === 'awkward') return 'awkward';
  if (eventType === 'wrong') return 'wrong';
  return 'good';
}

function ScoringChip({ event, index, animate }) {
  const [open, setOpen] = useState(false);
  const kind = chipKind(event.event_type);
  const note = event.judge_notes || '';
  const expandable = !!note;
  // The word this score is for — so 3 chips in a row are distinguishable and the user knows
  // exactly which word earned what. Reloaded/text events carry `word_text`; live voice `score`
  // events carry `word`.
  const word = event.word_text || event.word || '';

  return (
    <motion.button
      type="button"
      initial={animate ? { opacity: 0, y: 4 } : false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: animate ? 0.12 + index * 0.08 : 0, duration: 0.35, ease: [0.2, 0.8, 0.2, 1] }}
      onClick={() => expandable && setOpen((v) => !v)}
      title={expandable && !open ? note : ''}
      className={`inline-flex items-start gap-1.5 border rounded-2xl px-3 py-1 text-xs font-medium text-left max-w-full ${CHIP_STYLES[kind]} ${
        expandable ? 'cursor-pointer' : 'cursor-default'
      }`}
    >
      <Sparkles size={11} className="mt-[3px] shrink-0" />
      {word && <span className="shrink-0 font-semibold">{word}</span>}
      <span className="font-mono shrink-0 font-semibold">{event.delta > 0 ? `+${event.delta}` : event.delta}</span>
      {note && (
        <span className={`font-normal opacity-90 min-w-0 ${open ? 'break-words' : 'truncate'}`}>· {note}</span>
      )}
      {expandable && (
        <ChevronDown size={12} className={`mt-[3px] shrink-0 opacity-70 transition-transform ${open ? 'rotate-180' : ''}`} />
      )}
    </motion.button>
  );
}

function ScoringChips({ events, animate = true }) {
  return (
    <div className="flex gap-2 flex-wrap justify-end max-w-full sm:max-w-[560px]">
      {events.map((e, i) => (
        <ScoringChip key={e.id ?? i} event={e} index={i} animate={animate} />
      ))}
    </div>
  );
}

function ToolCallCard({ call, index }) {
  const [open, setOpen] = useState(true); // individual card starts expanded when the group opens
  return (
    <div className="bg-surface border border-border-2 rounded-xl text-[12px] overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2.5 bg-transparent border-none cursor-pointer text-left hover:bg-[#F7F8FA] transition-colors"
      >
        <span className="text-[10px] font-mono text-muted-2 shrink-0">{index + 1}</span>
        <span className="font-mono font-semibold text-accent flex-1 min-w-0 truncate">{call.name}</span>
        <ChevronDown size={13} className={`shrink-0 text-muted-2 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.16 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3">
              {call.args && Object.keys(call.args).length > 0 && (
                <div className="mb-1.5">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-2 mb-1">Input</div>
                  <pre className="whitespace-pre-wrap break-words font-mono text-[11.5px] text-text-2 bg-[#F7F8FA] rounded-lg p-2 m-0 overflow-x-auto">
                    {JSON.stringify(call.args, null, 2)}
                  </pre>
                </div>
              )}
              {call.output != null && call.output !== '' && (
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-2 mb-1">Output</div>
                  <pre className="whitespace-pre-wrap break-words font-mono text-[11.5px] text-text-2 bg-[#F7F8FA] rounded-lg p-2 m-0 max-h-56 overflow-auto">
                    {typeof call.output === 'string' ? call.output : JSON.stringify(call.output, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ToolCalls({ calls }) {
  const [open, setOpen] = useState(false);
  if (!calls?.length) return null;
  return (
    <div className="mt-1.5 max-w-[640px]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 text-[11px] font-medium text-muted bg-[#F1F2F6] hover:bg-[#E9EAF0] rounded-full px-2.5 py-1 border-none cursor-pointer transition-colors"
      >
        <Wrench size={11} />
        {calls.length} tool call{calls.length > 1 ? 's' : ''}
        <ChevronDown size={12} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
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
            <div className="mt-2 flex flex-col gap-2">
              {calls.map((c, i) => (
                <ToolCallCard key={i} call={c} index={i} />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function TypingIndicator({ personaName, personaAvatar }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3 items-center">
      <PersonaAvatar name={personaName} avatarUrl={personaAvatar} size="xs" />
      <div className="bg-surface border border-border rounded-[4px_18px_18px_18px] px-4 py-3 flex gap-1.5 items-center">
        {[0, 0.2, 0.4].map((d) => (
          <span key={d} className="w-1.5 h-1.5 rounded-full bg-[#9CA1B0] animate-dot-pulse" style={{ animationDelay: `${d}s` }} />
        ))}
        <span className="text-xs text-muted-2 ml-1.5 font-serif-italic">{personaName} is thinking…</span>
      </div>
    </motion.div>
  );
}

export default function Chat({ personaName, personaAvatar = '', personaId = null }) {
  const queryClient = useQueryClient();
  const conversations = useConversations(personaId);
  const [devMode] = useDevMode();

  const [activeId, setActiveId] = useState(null);
  const [threadQuery, setThreadQuery] = useState('');
  const [draft, setDraft] = useState('');
  const [typing, setTyping] = useState(false);
  const [pendingUser, setPendingUser] = useState(null); // optimistic user bubble
  const [chipsByMessage, setChipsByMessage] = useState({}); // user message id -> scoring events (session only)
  const [topicsByConv, setTopicsByConv] = useState({}); // conv id -> topic cards from creation
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [threadsOpen, setThreadsOpen] = useState(false);
  const [clock, setClock] = useState(nowClockLabel());
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [topicsLoading, setTopicsLoading] = useState(false); // "Suggest topics" clicked → topic cards loading
  const voiceStatus = useVoiceStatus();

  const messages = useMessages(activeId);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const { inset: keyboardInset } = useKeyboardInset();

  useEffect(() => {
    const t = setInterval(() => setClock(nowClockLabel()), 30000);
    return () => clearInterval(t);
  }, []);

  // Keep activeId consistent with the (persona-scoped) conversation list:
  //  - first load / after a switch to a persona that HAS chats: auto-select the newest;
  //  - if the open chat is no longer in the list (persona switched, or it was deleted):
  //    drop the stale selection so the main pane never shows another persona's / a deleted
  //    chat. We wait for the list to finish loading so a mid-fetch empty array doesn't
  //    transiently clear a still-valid selection.
  useEffect(() => {
    if (conversations.isLoading || !conversations.data) return;
    const list = conversations.data;
    if (activeId == null) {
      if (list.length) setActiveId(list[0].id);
      return;
    }
    // Don't fall back while a refetch is in flight: right after a new chat is created
    // we invalidate ['conversations'], so the cached list is briefly the OLD one that
    // doesn't yet contain the just-created activeId. Treating that as "stale" would
    // bounce the user back to the previous chat. Only judge staleness on a settled list.
    if (conversations.isFetching) return;
    if (!list.some((c) => c.id === activeId)) {
      // Stale selection: clear it (+ any optimistic bubbles) and fall back to the newest.
      setActiveId(list.length ? list[0].id : null);
      setPendingUser(null);
      setTyping(false);
    }
  }, [conversations.data, conversations.isLoading, conversations.isFetching, activeId]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages.data, typing, pendingUser, keyboardInset]);

  useEffect(() => {
    setThreadsOpen(false);
  }, [activeId]);

  const filteredThreads = useMemo(() => {
    const list = conversations.data || [];
    const q = threadQuery.trim().toLowerCase();
    return q ? list.filter((c) => c.title.toLowerCase().includes(q)) : list;
  }, [conversations.data, threadQuery]);

  const newChat = useMutation({
    // Create WITHOUT topic suggestions so there's no LLM wait — we land in the new
    // (empty) chat instantly. Topics are only fetched if the user asks (suggestTopics).
    mutationFn: () => api.createConversation({ suggest_topics: false }),
    onMutate: () => {
      setPendingUser(null);
      setTyping(false);
    },
    onSuccess: ({ conversation }) => {
      setActiveId(conversation.id);
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
      inputRef.current?.focus();
    },
    onError: (e) => toast.error(e.message),
  });

  // Fetch topic suggestions for the CURRENT chat on demand (the "Suggest topics" button).
  async function suggestTopics() {
    if (!activeId || topicsLoading) return;
    setTopicsLoading(true);
    try {
      const list = await api.suggestTopics(activeId);
      setTopicsByConv((m) => ({ ...m, [activeId]: list }));
    } catch (e) {
      toast.error(e.message);
    } finally {
      setTopicsLoading(false);
    }
  }

  async function afterAssistantReply(data) {
    if (data?.scoring_events?.length) {
      const words = queryClient.getQueryData(['words']) || [];
      const named = data.scoring_events.map((e) => ({
        ...e,
        word_text: words.find((w) => w.id === e.word_id)?.text,
      }));
      setChipsByMessage((m) => ({ ...m, [data.user_message.id]: named }));
      queryClient.invalidateQueries({ queryKey: ['words'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    }
    // Fetch the fresh message list to completion BEFORE we drop the optimistic
    // bubbles, so the real messages are already in cache when pendingUser/typing
    // clear — no gap where the list briefly renders without them (the flicker).
    await queryClient.refetchQueries({ queryKey: ['messages', activeId] });
    queryClient.invalidateQueries({ queryKey: ['conversations'] }); // auto-title
    queryClient.invalidateQueries({ queryKey: ['memory'] }); // agent may have written memories
  }

  async function send(text) {
    const content = (text ?? draft).trim();
    if (!content || typing || !activeId) return;
    setDraft('');
    setPendingUser(content);
    setTyping(true);
    try {
      const data = await api.sendChatMessage(activeId, content);
      await afterAssistantReply(data);
      // Real messages are now in cache — drop the optimistic bubble in the same
      // commit as hiding the typing indicator, so the swap is invisible.
      setPendingUser(null);
    } catch (e) {
      toast.error(e.message);
      setDraft(content); // give the text back
      setPendingUser(null);
    } finally {
      setTyping(false);
      inputRef.current?.focus();
    }
  }

  async function pickTopic(topic) {
    if (typing) return;
    try {
      await api.setConversationCategory(activeId, topic.category);
    } catch {
      /* category is a nice-to-have; keep going */
    }
    send(`Let's talk about: ${topic.title}`);
  }

  async function letPersonaStart() {
    if (typing || !activeId) return;
    setTyping(true);
    try {
      await api.requestOpener(activeId);
      queryClient.invalidateQueries({ queryKey: ['messages', activeId] });
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
    } catch (e) {
      toast.error(e.message);
    } finally {
      setTyping(false);
      inputRef.current?.focus();
    }
  }

  async function removeThread(id) {
    try {
      await api.deleteConversation(id);
      if (activeId === id) setActiveId(null);
      setConfirmDeleteId(null);
      queryClient.removeQueries({ queryKey: ['messages', id] });
      await queryClient.invalidateQueries({ queryKey: ['conversations'] });
    } catch (e) {
      toast.error(e.message);
    }
  }

  const msgs = messages.data || [];
  const isEmptyConversation = activeId != null && !messages.isLoading && msgs.length === 0 && !pendingUser;
  const topics = topicsByConv[activeId] || [];
  const hour = new Date().getHours();
  const greeting = hour < 5 ? 'Up late, are we?' : hour < 12 ? 'Good morning ✦' : hour < 17 ? 'Good afternoon ✦' : 'Good evening ✦';

  return (
    <div className="h-full min-h-0 flex flex-col md:flex-row">
      {/* threads */}
      <div className="hidden md:flex md:w-[290px] md:max-h-none bg-[#FBFBFC] md:border-r border-border flex-col md:pt-6 shrink-0">
        <div className="px-4 md:px-5 flex items-center justify-between">
          <span className="text-[17px] font-bold">Conversations</span>
          <button
            onClick={() => newChat.mutate()}
            disabled={newChat.isPending}
            title="New conversation"
            className="w-8 h-8 border-none rounded-[10px] bg-accent hover:bg-accent-hover text-white flex items-center justify-center cursor-pointer shadow-accent disabled:opacity-60 transition-colors"
          >
            {newChat.isPending ? <Spinner className="w-4 h-4 border-2 border-white/40 border-t-white" /> : <Plus size={17} />}
          </button>
        </div>
        <div className="mx-4 md:mx-5 mt-3 md:mt-4 mb-2 flex items-center gap-2 bg-[#F1F2F6] rounded-[10px] px-3">
          <Search size={13} className="text-muted shrink-0" />
          <input
            value={threadQuery}
            onChange={(e) => setThreadQuery(e.target.value)}
            placeholder="Search conversations…"
            className="border-none outline-none bg-transparent text-[13px] py-2 w-full text-text"
          />
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto px-3 pb-3 md:pb-5 pt-1.5 flex flex-col gap-1">
          {conversations.isLoading &&
            Array.from({ length: 4 }).map((_, i) => <ThreadItemSkeleton key={i} />)}
          {filteredThreads.map((t) => (
            <div
              key={t.id}
              onClick={() => setActiveId(t.id)}
              className={`group rounded-xl px-3 py-2.5 cursor-pointer transition-colors ${
                activeId === t.id ? 'bg-accent-soft' : 'hover:bg-[#F1F2F6]'
              }`}
            >
              <div className="flex justify-between items-center gap-2">
                <span className="text-[13.5px] font-semibold truncate">{t.title}</span>
                <span className="text-[11px] text-muted-2 shrink-0 group-hover:hidden">{formatThreadTime(t.updated_at)}</span>
                {confirmDeleteId === t.id ? (
                  <button
                    onClick={(e) => { e.stopPropagation(); removeThread(t.id); }}
                    className="hidden group-hover:inline text-[11px] font-semibold text-red bg-transparent border-none cursor-pointer shrink-0"
                  >
                    sure?
                  </button>
                ) : (
                  <button
                    onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(t.id); setTimeout(() => setConfirmDeleteId(null), 2500); }}
                    title="Delete conversation"
                    className="hidden group-hover:inline text-muted-2 hover:text-red bg-transparent border-none cursor-pointer shrink-0"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
              {t.category && <span className="text-[11px] text-accent">{t.category}</span>}
            </div>
          ))}
          {!conversations.isLoading && filteredThreads.length === 0 && (
            <p className="text-[13px] text-muted-2 text-center mt-8 font-serif-italic">
              {threadQuery ? 'Nothing matches.' : 'No conversations yet — start one ↑'}
            </p>
          )}
        </div>
      </div>

      <AnimatePresence>
        {threadsOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.16 }}
            className="fixed inset-0 z-50 bg-black/25 md:hidden"
            onClick={() => setThreadsOpen(false)}
          >
            <motion.div
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1] }}
              className="h-full w-[86vw] max-w-[340px] bg-[#FBFBFC] border-r border-border shadow-[18px_0_40px_-28px_rgba(26,29,39,.45)] flex flex-col pt-5 pb-4"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="px-4 mb-4 flex items-center justify-between">
                <div className="flex items-center gap-3 min-w-0">
                  <PersonaAvatar name={personaName} avatarUrl={personaAvatar} size="sm" online />
                  <div className="min-w-0">
                    <div className="text-[15px] font-bold truncate">{personaName}</div>
                    <div className="text-[12px] text-muted">conversations</div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setThreadsOpen(false)}
                  title="Close conversations"
                  className="w-9 h-9 rounded-xl border-none bg-[#F1F2F6] text-muted flex items-center justify-center cursor-pointer"
                >
                  <X size={17} />
                </button>
              </div>

              <div className="px-4 flex items-center justify-between">
                <span className="text-[17px] font-bold">Conversations</span>
                <button
                  onClick={() => newChat.mutate()}
                  disabled={newChat.isPending}
                  title="New conversation"
                  className="w-8 h-8 border-none rounded-[10px] bg-accent hover:bg-accent-hover text-white flex items-center justify-center cursor-pointer shadow-accent disabled:opacity-60 transition-colors"
                >
                  {newChat.isPending ? <Spinner className="w-4 h-4 border-2 border-white/40 border-t-white" /> : <Plus size={17} />}
                </button>
              </div>
              <div className="mx-4 mt-3 mb-2 flex items-center gap-2 bg-[#F1F2F6] rounded-[10px] px-3">
                <Search size={13} className="text-muted shrink-0" />
                <input
                  value={threadQuery}
                  onChange={(e) => setThreadQuery(e.target.value)}
                  placeholder="Search conversations..."
                  className="border-none outline-none bg-transparent text-[13px] py-2 w-full text-text"
                />
              </div>
              <div className="flex-1 min-h-0 overflow-y-auto px-3 pb-3 pt-1.5 flex flex-col gap-1">
                {conversations.isLoading &&
                  Array.from({ length: 4 }).map((_, i) => <ThreadItemSkeleton key={i} />)}
                {filteredThreads.map((t) => (
                  <div
                    key={t.id}
                    onClick={() => setActiveId(t.id)}
                    className={`group rounded-xl px-3 py-2.5 cursor-pointer transition-colors ${
                      activeId === t.id ? 'bg-accent-soft' : 'hover:bg-[#F1F2F6]'
                    }`}
                  >
                    <div className="flex justify-between items-center gap-2">
                      <span className="text-[13.5px] font-semibold truncate">{t.title}</span>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-[11px] text-muted-2">{formatThreadTime(t.updated_at)}</span>
                        {/* mobile has no hover — the delete affordance is always visible here */}
                        {confirmDeleteId === t.id ? (
                          <button
                            onClick={(e) => { e.stopPropagation(); removeThread(t.id); }}
                            className="text-[11px] font-semibold text-red bg-transparent border-none cursor-pointer p-1 -m-1"
                          >
                            sure?
                          </button>
                        ) : (
                          <button
                            onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(t.id); setTimeout(() => setConfirmDeleteId(null), 2500); }}
                            title="Delete conversation"
                            className="text-muted-2 hover:text-red bg-transparent border-none cursor-pointer p-1 -m-1"
                          >
                            <Trash2 size={15} />
                          </button>
                        )}
                      </div>
                    </div>
                    {t.category && <span className="text-[11px] text-accent">{t.category}</span>}
                  </div>
                ))}
                {!conversations.isLoading && filteredThreads.length === 0 && (
                  <p className="text-[13px] text-muted-2 text-center mt-8 font-serif-italic">
                    {threadQuery ? 'Nothing matches.' : 'No conversations yet'}
                  </p>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* main */}
      <div
        className="flex-1 min-h-0 flex flex-col bg-bg min-w-0"
        style={keyboardInset ? { paddingBottom: keyboardInset } : undefined}
      >
        {/* header */}
        <div className="h-[64px] md:h-[72px] flex items-center justify-between gap-3 px-4 md:px-8 border-b border-border shrink-0">
          <button
            type="button"
            onClick={() => setThreadsOpen(true)}
            title="Open conversations"
            className="md:hidden w-10 h-10 rounded-xl border-none bg-surface text-accent shadow-card flex items-center justify-center cursor-pointer shrink-0"
          >
            <Menu size={19} />
          </button>
          <button
            type="button"
            onClick={() => setThreadsOpen(true)}
            className="md:hidden flex items-center gap-3 min-w-0 bg-transparent border-none p-0 text-left cursor-pointer"
          >
            <PersonaAvatar name={personaName} avatarUrl={personaAvatar} size="sm" online />
            <div className="min-w-0">
              <div className="text-[15px] font-bold truncate">{personaName}</div>
              <div className="text-[12px] text-muted truncate">tap for conversations</div>
            </div>
          </button>
          <div className="hidden md:flex items-center gap-3.5">
            <PersonaAvatar name={personaName} avatarUrl={personaAvatar} size="md" online />
            <div>
              <div className="text-[15.5px] font-bold">{personaName}</div>
              <div className="text-[12.5px] text-muted">always here to talk</div>
            </div>
          </div>
          <div className="text-[11.5px] md:text-[12.5px] text-muted bg-surface border border-border-2 rounded-full px-3 md:px-3.5 py-1.5 shrink-0">{clock}</div>
        </div>

        {activeId == null ? (
          /* no conversation selected */
          <div className="flex-1 flex flex-col items-center justify-center gap-5 px-6 text-center">
            <PersonaAvatar name={personaName} avatarUrl={personaAvatar} size="xl" />
            <h2 className="m-0 text-2xl font-bold">{greeting}</h2>
            <p className="m-0 text-muted font-serif-italic">Start a conversation with {personaName}.</p>
            <button
              onClick={() => newChat.mutate()}
              disabled={newChat.isPending}
              className="bg-accent hover:bg-accent-hover text-white border-none rounded-2xl px-6 py-3 text-sm font-semibold shadow-accent cursor-pointer transition-colors disabled:opacity-60"
            >
              {newChat.isPending ? 'Opening…' : 'New conversation'}
            </button>
          </div>
        ) : isEmptyConversation ? (
          /* empty new chat: two-choice landing — chat now, or ask for topic suggestions */
          <div className="flex-1 flex flex-col items-center justify-start md:justify-center px-4 sm:px-6 md:px-12 py-7 gap-6 md:gap-7 overflow-y-auto">
            <div className="flex flex-col items-center text-center">
              <div className="mb-4 flex justify-center"><PersonaAvatar name={personaName} avatarUrl={personaAvatar} size="lg" /></div>
              <h2 className="m-0 text-[24px] md:text-[26px] font-bold tracking-tight">{greeting}</h2>
              <p className="mt-2 mb-0 text-[14px] md:text-[15px] text-muted font-serif-italic">
                Just start typing below, or pick how you'd like to begin.
              </p>
            </div>

            {topicsLoading ? (
              /* topics requested — skeleton cards while the LLM responds */
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5 md:gap-4 w-full max-w-[860px]">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="bg-surface border border-border-2 rounded-[18px] p-5 flex flex-col gap-2.5 shadow-card animate-pulse">
                    <span className="self-start h-4 w-16 rounded-full bg-[#EEF0F4]" />
                    <span className="h-4 w-3/4 rounded bg-[#EEF0F4]" />
                    <span className="h-3 w-full rounded bg-[#F1F2F6]" />
                    <span className="h-3 w-5/6 rounded bg-[#F1F2F6]" />
                  </div>
                ))}
              </div>
            ) : topics.length > 0 ? (
              /* topic cards */
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5 md:gap-4 w-full max-w-[860px]">
                {topics.map((tc, i) => (
                  <motion.button
                    key={i}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.06 }}
                    onClick={() => pickTopic(tc)}
                    className="text-left bg-surface border border-border-2 rounded-[18px] p-5 flex flex-col gap-2 shadow-card cursor-pointer transition-all hover:border-accent-soft-border hover:-translate-y-0.5 hover:shadow-accent"
                  >
                    <span className="self-start text-[11px] font-semibold uppercase tracking-wider text-accent bg-accent-soft rounded-full px-2.5 py-0.5">{tc.category}</span>
                    <span className="text-[15px] font-semibold leading-snug">{tc.title}</span>
                    <span className="text-[12.5px] text-muted leading-normal">{tc.description}</span>
                  </motion.button>
                ))}
              </div>
            ) : (
              /* two-choice landing buttons — fully responsive (stack on phone, row on ≥sm) */
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-center gap-3 w-full max-w-[520px]">
                <button
                  onClick={letPersonaStart}
                  disabled={typing}
                  className="flex-1 bg-accent hover:bg-accent-hover text-white border-none rounded-2xl px-5 py-3.5 text-sm font-semibold shadow-accent cursor-pointer transition-colors disabled:opacity-60"
                >
                  {typing ? `${personaName} is starting…` : `Let ${personaName} start ✦`}
                </button>
                <button
                  onClick={suggestTopics}
                  disabled={typing}
                  className="flex-1 bg-surface hover:bg-[#F1F2F6] text-text-2 border border-border-2 rounded-2xl px-5 py-3.5 text-sm font-semibold shadow-card cursor-pointer transition-colors disabled:opacity-60"
                >
                  Suggest topics
                </button>
              </div>
            )}
          </div>
        ) : (
          /* messages */
          <div ref={scrollRef} className="flex-1 min-h-0 px-4 sm:px-6 md:px-[8%] py-5 md:py-7 flex flex-col gap-4 md:gap-5 overflow-y-auto">
            {messages.isLoading &&
              [false, true, false, true].map((mine, i) => <MessageBubbleSkeleton key={i} mine={mine} />)}
            {msgs.map((m) =>
              m.role === 'assistant' ? (
                <motion.div key={m.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex gap-2.5 md:gap-3 max-w-full md:max-w-[640px]">
                  <div className="mt-1"><PersonaAvatar name={personaName} avatarUrl={personaAvatar} size="xs" /></div>
                  <div className="min-w-0">
                    <div className="bg-surface border border-border rounded-[4px_18px_18px_18px] px-4 py-3 md:px-4.5 text-[14px] md:text-[14.5px] leading-relaxed text-text-2 shadow-[0_3px_10px_-6px_rgba(26,29,39,.1)] break-words [&_p]:m-0 [&_p+p]:mt-2">
                      <ReactMarkdown>{m.content}</ReactMarkdown>
                    </div>
                    {devMode && <ToolCalls calls={m.tool_calls} />}
                  </div>
                </motion.div>
              ) : (
                <motion.div key={m.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-end gap-2">
                  <div className="max-w-[88%] sm:max-w-[560px] bg-accent text-white rounded-[18px_4px_18px_18px] px-4 py-3 md:px-4.5 text-[14px] md:text-[14.5px] leading-relaxed shadow-accent whitespace-pre-wrap break-words">
                    {m.content}
                  </div>
                  {chipsByMessage[m.id] ? (
                    <ScoringChips events={chipsByMessage[m.id]} />
                  ) : (
                    m.word_events?.length > 0 && <ScoringChips events={m.word_events} animate={false} />
                  )}
                </motion.div>
              )
            )}
            {pendingUser && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-end">
                <div className="max-w-[88%] sm:max-w-[560px] bg-accent text-white rounded-[18px_4px_18px_18px] px-4 py-3 md:px-4.5 text-[14px] md:text-[14.5px] leading-relaxed shadow-accent whitespace-pre-wrap break-words">
                  {pendingUser}
                </div>
              </motion.div>
            )}
            <AnimatePresence>{typing && <TypingIndicator personaName={personaName} personaAvatar={personaAvatar} />}</AnimatePresence>
          </div>
        )}

        {/* composer */}
        {activeId != null && (
          <div className="px-4 sm:px-6 md:px-[8%] pb-4 md:pb-6 pt-2 shrink-0">
            <div className="bg-surface border border-border-2 rounded-[18px] shadow-[0_12px_30px_-14px_rgba(26,29,39,.18)] px-3.5 md:px-4.5 py-2.5 flex items-center gap-3">
              <textarea
                ref={inputRef}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                rows={1}
                placeholder={`Message ${personaName}…`}
                className="border-none outline-none text-[14.5px] w-full bg-transparent text-text resize-none leading-relaxed max-h-32 field-sizing-content"
              />
              {voiceStatus.data?.available && (
                <button
                  onClick={() => setVoiceOpen(true)}
                  title={`Talk with ${personaName}`}
                  aria-label={`Talk with ${personaName}`}
                  className="w-9 h-9 shrink-0 border border-border-2 rounded-xl bg-surface hover:bg-bg text-accent flex items-center justify-center cursor-pointer transition-colors"
                >
                  <Mic size={16} />
                </button>
              )}
              <button
                onClick={() => send()}
                disabled={typing || !draft.trim()}
                className="w-9 h-9 shrink-0 border-none rounded-xl bg-accent hover:bg-accent-hover disabled:opacity-45 flex items-center justify-center shadow-accent cursor-pointer text-white transition-colors"
              >
                <Send size={15} />
              </button>
            </div>
          </div>
        )}
      </div>

      <VoiceOverlay
        open={voiceOpen}
        conversationId={activeId}
        personaName={personaName}
        personaAvatar={personaAvatar}
        onClose={() => {
          setVoiceOpen(false);
          // The voice turn(s) were saved server-side + scores/memory may have changed.
          queryClient.invalidateQueries({ queryKey: ['messages', activeId] });
          queryClient.invalidateQueries({ queryKey: ['conversations'] });
          queryClient.invalidateQueries({ queryKey: ['words'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard'] });
          queryClient.invalidateQueries({ queryKey: ['memory'] });
        }}
      />
    </div>
  );
}
