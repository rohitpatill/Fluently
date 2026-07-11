import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import { toast } from 'sonner';
import { Plus, Search, Send, Sparkles, Trash2 } from 'lucide-react';

import * as api from '../api';
import { useConversations, useMessages } from '../hooks/useApi';
import { PersonaAvatar, Spinner } from './Shared';
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

function ScoringChips({ events }) {
  return (
    <div className="flex gap-2 flex-wrap justify-end max-w-[560px]">
      {events.map((e, i) => {
        const kind = chipKind(e.event_type);
        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.15 + i * 0.1, type: 'spring', bounce: 0.4 }}
            title={e.judge_notes || ''}
            className={`inline-flex items-center gap-1.5 border rounded-full px-3 py-1 text-xs font-medium ${CHIP_STYLES[kind]}`}
          >
            <Sparkles size={11} />
            <span className="font-semibold">{e.word_text || `word #${e.word_id}`}</span>
            <span className="font-mono">{e.delta > 0 ? `+${e.delta}` : e.delta}</span>
            {kind !== 'good' && e.judge_notes && (
              <span className="font-normal opacity-90 max-w-[260px] truncate">· {e.judge_notes}</span>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}

function TypingIndicator({ personaName }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3 items-center">
      <PersonaAvatar name={personaName} size="xs" />
      <div className="bg-surface border border-border rounded-[4px_18px_18px_18px] px-4 py-3 flex gap-1.5 items-center">
        {[0, 0.2, 0.4].map((d) => (
          <span key={d} className="w-1.5 h-1.5 rounded-full bg-[#9CA1B0] animate-dot-pulse" style={{ animationDelay: `${d}s` }} />
        ))}
        <span className="text-xs text-muted-2 ml-1.5 font-serif-italic">{personaName} is thinking…</span>
      </div>
    </motion.div>
  );
}

export default function Chat({ personaName }) {
  const queryClient = useQueryClient();
  const conversations = useConversations();

  const [activeId, setActiveId] = useState(null);
  const [threadQuery, setThreadQuery] = useState('');
  const [draft, setDraft] = useState('');
  const [typing, setTyping] = useState(false);
  const [pendingUser, setPendingUser] = useState(null); // optimistic user bubble
  const [chipsByMessage, setChipsByMessage] = useState({}); // user message id -> scoring events (session only)
  const [topicsByConv, setTopicsByConv] = useState({}); // conv id -> topic cards from creation
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [clock, setClock] = useState(nowClockLabel());

  const messages = useMessages(activeId);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const t = setInterval(() => setClock(nowClockLabel()), 30000);
    return () => clearInterval(t);
  }, []);

  // auto-select most recent conversation on first load
  useEffect(() => {
    if (activeId == null && conversations.data?.length) setActiveId(conversations.data[0].id);
  }, [conversations.data, activeId]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages.data, typing, pendingUser]);

  const filteredThreads = useMemo(() => {
    const list = conversations.data || [];
    const q = threadQuery.trim().toLowerCase();
    return q ? list.filter((c) => c.title.toLowerCase().includes(q)) : list;
  }, [conversations.data, threadQuery]);

  const newChat = useMutation({
    mutationFn: () => api.createConversation({ suggest_topics: true }),
    onSuccess: ({ conversation, topics }) => {
      setTopicsByConv((m) => ({ ...m, [conversation.id]: topics }));
      setActiveId(conversation.id);
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
      inputRef.current?.focus();
    },
    onError: (e) => toast.error(e.message),
  });

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
    queryClient.invalidateQueries({ queryKey: ['messages', activeId] });
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
    } catch (e) {
      toast.error(e.message);
      setDraft(content); // give the text back
    } finally {
      setTyping(false);
      setPendingUser(null);
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
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
      if (activeId === id) setActiveId(null);
      setConfirmDeleteId(null);
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
    <div className="h-full flex">
      {/* threads */}
      <div className="w-[290px] bg-[#FBFBFC] border-r border-border flex flex-col pt-6 shrink-0">
        <div className="px-5 flex items-center justify-between">
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
        <div className="mx-5 mt-4 mb-2 flex items-center gap-2 bg-[#F1F2F6] rounded-[10px] px-3">
          <Search size={13} className="text-muted shrink-0" />
          <input
            value={threadQuery}
            onChange={(e) => setThreadQuery(e.target.value)}
            placeholder="Search conversations…"
            className="border-none outline-none bg-transparent text-[13px] py-2 w-full text-text"
          />
        </div>
        <div className="flex-1 overflow-y-auto px-3 pb-5 pt-1.5 flex flex-col gap-1">
          {conversations.isLoading && <div className="flex justify-center pt-8"><Spinner /></div>}
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

      {/* main */}
      <div className="flex-1 flex flex-col bg-bg min-w-0">
        {/* header */}
        <div className="h-[72px] flex items-center justify-between px-8 border-b border-border shrink-0">
          <div className="flex items-center gap-3.5">
            <PersonaAvatar name={personaName} size="md" online />
            <div>
              <div className="text-[15.5px] font-bold">{personaName}</div>
              <div className="text-[12.5px] text-muted">always here to talk</div>
            </div>
          </div>
          <div className="text-[12.5px] text-muted bg-surface border border-border-2 rounded-full px-3.5 py-1.5">{clock}</div>
        </div>

        {activeId == null ? (
          /* no conversation selected */
          <div className="flex-1 flex flex-col items-center justify-center gap-5">
            <PersonaAvatar name={personaName} size="xl" />
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
          /* topic cards */
          <div className="flex-1 flex flex-col items-center justify-center px-12 gap-7 overflow-y-auto">
            <div className="text-center">
              <div className="mx-auto mb-4"><PersonaAvatar name={personaName} size="lg" /></div>
              <h2 className="m-0 text-[26px] font-bold tracking-tight">{greeting}</h2>
              <p className="mt-2 mb-0 text-[15px] text-muted font-serif-italic">What's on your mind? Or pick up where we left off.</p>
            </div>
            {topics.length > 0 && (
              <div className="grid grid-cols-3 gap-4 w-full max-w-[860px]">
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
            )}
            <div className="flex items-center gap-3.5">
              <span className="text-[13px] text-muted-2">Just start typing below, or</span>
              <button
                onClick={letPersonaStart}
                disabled={typing}
                className="bg-accent hover:bg-accent-hover text-white border-none rounded-full px-5 py-2.5 text-sm font-semibold shadow-accent cursor-pointer transition-colors disabled:opacity-60"
              >
                {typing ? `${personaName} is starting…` : `Let ${personaName} start ✦`}
              </button>
            </div>
          </div>
        ) : (
          /* messages */
          <div ref={scrollRef} className="flex-1 px-[8%] py-7 flex flex-col gap-5 overflow-y-auto">
            {messages.isLoading && <div className="flex justify-center pt-10"><Spinner /></div>}
            {msgs.map((m) =>
              m.role === 'assistant' ? (
                <motion.div key={m.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3 max-w-[640px]">
                  <div className="mt-1"><PersonaAvatar name={personaName} size="xs" /></div>
                  <div className="bg-surface border border-border rounded-[4px_18px_18px_18px] px-4.5 py-3 text-[14.5px] leading-relaxed text-text-2 shadow-[0_3px_10px_-6px_rgba(26,29,39,.1)] [&_p]:m-0 [&_p+p]:mt-2">
                    <ReactMarkdown>{m.content}</ReactMarkdown>
                  </div>
                </motion.div>
              ) : (
                <motion.div key={m.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-end gap-2">
                  <div className="max-w-[560px] bg-accent text-white rounded-[18px_4px_18px_18px] px-4.5 py-3 text-[14.5px] leading-relaxed shadow-accent whitespace-pre-wrap">
                    {m.content}
                  </div>
                  {chipsByMessage[m.id] && <ScoringChips events={chipsByMessage[m.id]} />}
                </motion.div>
              )
            )}
            {pendingUser && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-end">
                <div className="max-w-[560px] bg-accent text-white rounded-[18px_4px_18px_18px] px-4.5 py-3 text-[14.5px] leading-relaxed shadow-accent whitespace-pre-wrap">
                  {pendingUser}
                </div>
              </motion.div>
            )}
            <AnimatePresence>{typing && <TypingIndicator personaName={personaName} />}</AnimatePresence>
          </div>
        )}

        {/* composer */}
        {activeId != null && (
          <div className="px-[8%] pb-6 pt-2 shrink-0">
            <div className="bg-surface border border-border-2 rounded-[18px] shadow-[0_12px_30px_-14px_rgba(26,29,39,.18)] px-4.5 py-3 flex items-end gap-3">
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
    </div>
  );
}
