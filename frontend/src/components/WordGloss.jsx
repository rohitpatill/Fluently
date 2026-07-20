import { createContext, useContext, useMemo, useState, useCallback, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'motion/react';
import { NotebookPen, X } from 'lucide-react';

// In-chat word gloss: any word the user is practising that appears in a message becomes a
// subtly-underlined, tappable target. Hover (desktop) or tap (mobile) reveals a small themed
// popover with the LLM meaning + the user's own note — so a word can be looked up right where
// it's used, without a trip to the Words tab. Purely client-side (no LLM, no API): matching is
// exact-word, case-insensitive, punctuation-stripped. Phrases are intentionally out of scope.
//
// The popover is rendered ONCE at the provider level (via a portal), not per-word, so it can be
// positioned against the viewport — clamped on desktop, a centered sheet on mobile — instead of
// being anchored inside a message bubble where it would clip off-screen.

const GlossContext = createContext(null);

// Coarse-pointer / small screens get the centered mobile sheet; fine pointers get the anchored
// desktop popover. Read once on open (cheap, avoids a resize listener for this).
function isTouchLike() {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(max-width: 639px)').matches || window.matchMedia('(hover: none)').matches;
}

// Strip surrounding punctuation & lowercase — the normalized key we match on.
function normalize(token) {
  return token.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '').toLowerCase();
}

// Underline intensity by score: weaker (slipping) words pull the eye more; near-mastered fade.
// On the accent-colored user bubble the accent underline is invisible, so we use white there.
function underlineStyle(score, onAccent) {
  const t = Math.max(0, Math.min(100, score)) / 100;
  const opacity = (onAccent ? 0.85 : 0.55) - t * (onAccent ? 0.4 : 0.37);
  const rgb = onAccent ? '255, 255, 255' : '75, 93, 228';
  return {
    textDecorationLine: 'underline',
    textDecorationStyle: 'dotted',
    textDecorationColor: `rgba(${rgb}, ${opacity.toFixed(2)})`,
    textUnderlineOffset: '3px',
    textDecorationThickness: '1.5px',
    cursor: 'pointer',
  };
}

/**
 * Provider — give it the user's word list. Children render <GlossedText>; matched words light up
 * and, when opened, this provider renders the single shared popover.
 */
export function WordGlossProvider({ words = [], children }) {
  const byText = useMemo(() => {
    const m = new Map();
    for (const w of words || []) {
      if (!w?.text) continue;
      const key = normalize(w.text);
      if (!key || key.includes(' ')) continue; // single-token targets only
      if (!m.has(key)) m.set(key, w);
    }
    return m;
  }, [words]);

  // active = { word, rect } — the open gloss and the anchor's bounding rect (for desktop).
  const [active, setActive] = useState(null);
  const open = useCallback((word, rect) => setActive({ word, rect }), []);
  const close = useCallback(() => setActive(null), []);
  const value = useMemo(() => ({ byText, activeKey: active ? normalize(active.word.text) : null, open, close }), [byText, active, open, close]);

  return (
    <GlossContext.Provider value={value}>
      {children}
      <GlossPopover active={active} onClose={close} />
    </GlossContext.Provider>
  );
}

function PopoverBody({ word, onClose }) {
  return (
    <>
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-baseline gap-2 min-w-0">
          <span className="text-[15px] font-bold text-text truncate">{word.text}</span>
          <span className="font-mono text-[11px] font-semibold text-muted-2 shrink-0">{Math.round(word.score)}</span>
        </div>
        <button
          type="button"
          onPointerDown={(e) => { e.stopPropagation(); onClose(); }}
          className="text-muted-2 hover:text-muted bg-transparent border-none cursor-pointer p-0.5 -m-0.5 shrink-0 transition-colors"
          title="Close"
          aria-label="Close"
        >
          <X size={16} />
        </button>
      </div>
      <p className="m-0 text-[13px] leading-relaxed text-text-3 break-words">
        {word.meaning || 'No meaning yet — open the Words tab to enrich it.'}
      </p>
      {word.note && (
        <div className="mt-2.5 bg-accent-soft/50 border border-accent-soft-border rounded-lg px-2.5 py-2">
          <div className="flex items-center gap-1.5 text-[10px] font-semibold tracking-wider uppercase text-accent-hover mb-1">
            <NotebookPen size={11} /> My note
          </div>
          <p className="m-0 text-[12.5px] leading-relaxed text-text-2 break-words">{word.note}</p>
        </div>
      )}
    </>
  );
}

// The single shared popover, portaled to <body>. Two layouts: centered sheet (mobile) / anchored
// clamped card (desktop). Backdrop click and Escape both close.
function GlossPopover({ active, onClose }) {
  const [mobile, setMobile] = useState(false);

  useEffect(() => {
    if (active) setMobile(isTouchLike());
  }, [active]);

  useEffect(() => {
    if (!active) return;
    const onKey = (e) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [active, onClose]);

  // Desktop anchored position: sit above the word, clamped into the viewport horizontally.
  const anchoredStyle = useMemo(() => {
    if (!active?.rect) return {};
    const width = 260;
    const margin = 8;
    const r = active.rect;
    let left = r.left + r.width / 2 - width / 2;
    left = Math.max(margin, Math.min(left, window.innerWidth - width - margin));
    const bottom = window.innerHeight - r.top + 8; // gap above the word
    return { position: 'fixed', left, bottom, width };
  }, [active]);

  return createPortal(
    <AnimatePresence>
      {active && (
        <>
          {/* Backdrop — tap/click anywhere to close. Faintly dims on mobile, invisible on desktop. */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.14 }}
            onPointerDown={(e) => { e.stopPropagation(); onClose(); }}
            className={`fixed inset-0 z-[60] ${mobile ? 'bg-black/30 backdrop-blur-[1px]' : ''}`}
          />
          {mobile ? (
            <motion.div
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={{ duration: 0.18, ease: [0.2, 0.8, 0.2, 1] }}
              onPointerDown={(e) => e.stopPropagation()}
              className="fixed z-[61] left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[86vw] max-w-[360px] max-h-[70vh] overflow-y-auto bg-surface border border-border-2 rounded-2xl shadow-[0_20px_50px_-16px_rgba(26,29,39,.5)] p-4 text-left font-sans"
            >
              <PopoverBody word={active.word} onClose={onClose} />
            </motion.div>
          ) : (
            <motion.div
              initial={{ opacity: 0, y: 6, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 4, scale: 0.98 }}
              transition={{ duration: 0.15, ease: [0.2, 0.8, 0.2, 1] }}
              onPointerDown={(e) => e.stopPropagation()}
              style={anchoredStyle}
              className="z-[61] max-h-[60vh] overflow-y-auto bg-surface border border-border-2 rounded-2xl shadow-[0_14px_34px_-14px_rgba(26,29,39,.4)] p-3.5 text-left font-sans"
            >
              <PopoverBody word={active.word} onClose={onClose} />
            </motion.div>
          )}
        </>
      )}
    </AnimatePresence>,
    document.body,
  );
}

// A single matched, interactive word.
function GlossWord({ word, display, onAccent }) {
  const { activeKey, open, close } = useContext(GlossContext);
  const key = normalize(word.text);
  const isOpen = activeKey === key;
  const ref = useRef(null);

  const openHere = useCallback(() => {
    const rect = ref.current?.getBoundingClientRect();
    open(word, rect);
  }, [open, word]);

  const toggle = useCallback(
    (e) => {
      e.stopPropagation();
      if (isOpen) close();
      else openHere();
    },
    [isOpen, close, openHere],
  );

  return (
    <span
      ref={ref}
      role="button"
      tabIndex={0}
      onPointerDown={toggle}
      // Hover-to-open on desktop (fine pointer); it stays open until you click away / press Esc /
      // click the word again — so moving the cursor onto the card (portaled elsewhere) is safe.
      onMouseEnter={() => { if (!isTouchLike()) openHere(); }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(e); }
        if (e.key === 'Escape') close();
      }}
      className="inline"
      style={underlineStyle(word.score, onAccent)}
    >
      {display}
    </span>
  );
}

// Split a plain text string into runs, wrapping any run that matches a tracked word.
function glossText(text, byText, keyPrefix, onAccent) {
  if (!byText || byText.size === 0) return text;
  const parts = text.split(/(\s+)/); // keep separators to reassemble faithfully
  const out = [];
  parts.forEach((part, i) => {
    const norm = normalize(part);
    const word = norm && byText.get(norm);
    if (word) {
      out.push(<GlossWord key={`${keyPrefix}-${i}`} word={word} display={part} onAccent={onAccent} />);
    } else {
      out.push(part);
    }
  });
  return out;
}

/**
 * Wrap text, glossing any tracked word. Used as react-markdown block/inline renderers (assistant
 * bubbles) and directly with a plain string (user bubbles — pass `onAccent`).
 */
export function GlossedText({ children, onAccent = false }) {
  const ctx = useContext(GlossContext);
  const arr = Array.isArray(children) ? children : [children];
  return (
    <>
      {arr.map((child, i) =>
        typeof child === 'string' ? (
          <span key={i}>{glossText(child, ctx?.byText, i, onAccent)}</span>
        ) : (
          child
        ),
      )}
    </>
  );
}
