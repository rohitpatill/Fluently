import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { RefreshCw, Zap, Sparkles, Check, CloudOff } from 'lucide-react';
import { initial } from '../utils';

export function PersonaAvatar({ name, size = 'md', online = false, avatarUrl = '' }) {
  const sizes = {
    xs: 'w-[30px] h-[30px] text-sm',
    sm: 'w-[34px] h-[34px] text-base',
    md: 'w-[42px] h-[42px] text-lg',
    lg: 'w-16 h-16 text-2xl',
    xl: 'w-[72px] h-[72px] text-3xl',
  };
  return (
    <div className="relative shrink-0">
      {avatarUrl ? (
        // Public image URL (no bytes stored server-side). On load error, the gradient-initial
        // fallback shows through because the <img> collapses — so we layer it under the image.
        <div
          className={`${sizes[size]} relative rounded-full bg-linear-to-br from-accent to-[#9AA6F5] text-white flex items-center justify-center font-serif-italic shadow-accent overflow-hidden`}
        >
          <span className="absolute inset-0 flex items-center justify-center">
            {initial(name)}
          </span>
          <img
            src={avatarUrl}
            alt={name || 'persona'}
            referrerPolicy="no-referrer"
            className="relative w-full h-full object-cover"
            onError={(e) => {
              e.currentTarget.style.display = 'none';
            }}
          />
        </div>
      ) : (
        <div
          className={`${sizes[size]} rounded-full bg-linear-to-br from-accent to-[#9AA6F5] text-white flex items-center justify-center font-serif-italic shadow-accent`}
        >
          {initial(name)}
        </div>
      )}
      {online && (
        <span className="absolute right-0 bottom-0 w-[11px] h-[11px] rounded-full bg-green border-2 border-bg" />
      )}
    </div>
  );
}

export function Spinner({ className = '' }) {
  return (
    <div
      className={`w-7 h-7 rounded-full border-[3px] border-border-2 border-t-accent animate-spin ${className}`}
    />
  );
}

export function FullScreenLoader({ label = 'Loading…' }) {
  return (
    <div className="min-h-dvh flex flex-col items-center justify-center gap-4 bg-bg px-6 text-center">
      <Spinner />
      <p className="text-muted text-sm">{label}</p>
    </div>
  );
}

// ── Boot screen ────────────────────────────────────────────────────────
// Shown while the very first health/auth probe is in flight. The backend sleeps on a free
// host, so this wait can genuinely run 20-30s. A bare spinner reads as "broken" after ~5s,
// so instead we (a) tell the truth on a timer and (b) play out the product's own story —
// the same bubble → reply → score → memory beats as the login page's 3D stack — so the
// wait teaches the user what Fluently does rather than just burning their patience.

/**
 * Elapsed-time copy. It ACKNOWLEDGES the wait without ever explaining the cause: the user is
 * here to learn English, and hosting/cold-start detail is both meaningless to them and not
 * something they can act on. Silence past ~10s is what reads as "broken", so the escalation
 * exists purely to keep saying "we know, we're still here".
 */
const BOOT_STAGES = [
  { at: 0, label: 'Waking things up…' },
  { at: 5, label: 'Just a moment — getting everything ready.' },
  { at: 12, label: 'Almost there. Thanks for your patience.' },
  { at: 22, label: 'Still working on it — hang tight.' },
  { at: 40, label: 'This one’s taking a while. Still with you.' },
  { at: 65, label: 'Nearly there — thanks for waiting it out.' },
];

/** The four beats of a real turn, revealed one at a time as the wait goes on. */
const BOOT_BEATS = [
  {
    kind: 'them',
    text: 'So — how did yesterday’s demo actually go? You were dreading it.',
  },
  { kind: 'me', text: 'Honestly? I was unflappable. Nobody could tell.' },
  { kind: 'score', word: 'unflappable', score: 84, note: 'used unprompted, in the right place' },
  { kind: 'memory', text: 'noted — the demo went well' },
];

export function BootScreen() {
  // Tenths of a second, so the beat reveal can be paced sub-second without a fast interval.
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const t = setInterval(() => setTick(Math.floor((Date.now() - started) / 100)), 200);
    return () => clearInterval(t);
  }, []);

  const elapsed = tick / 10;
  // Beats land at 0.5s, 1.7s, 2.9s, 4.1s — paced so a FAST boot shows only the first beat
  // or two and the app never feels withheld, while a cold start fills the whole wait.
  const shownCount = Math.max(0, Math.min(BOOT_BEATS.length, Math.floor((elapsed - 0.5) / 1.2) + 1));
  const shown = BOOT_BEATS.slice(0, shownCount);
  const stage = [...BOOT_STAGES].reverse().find((s) => elapsed >= s.at) || BOOT_STAGES[0];

  return (
    <div className="relative min-h-dvh w-full overflow-x-hidden overflow-y-auto bg-bg flex items-center justify-center px-5 py-10">
      {/* the login page's ambient accent wash, so boot → login → app is one continuous space */}
      <div
        aria-hidden="true"
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            'radial-gradient(120% 90% at 78% 18%, var(--color-accent-soft) 0%, rgba(238,240,254,0) 62%), ' +
            'radial-gradient(80% 70% at 8% 92%, var(--color-accent-soft) 0%, rgba(238,240,254,0) 58%), ' +
            'linear-gradient(180deg, var(--color-bg) 0%, var(--color-bg-2) 100%)',
        }}
      />

      <div className="relative w-full max-w-[420px] flex flex-col items-center">
        <div className="flex items-center gap-2.5 mb-8">
          <span className="w-2.5 h-2.5 rounded-full bg-accent shadow-accent animate-dot-pulse" />
          <span className="text-[15px] font-bold tracking-tight text-text">Fluently</span>
        </div>

        {/* The story beats. Fixed min-height so the block doesn't jump as items appear. */}
        <div
          aria-hidden="true"
          className="w-full flex flex-col gap-2.5 min-h-[232px] sm:min-h-[248px] justify-center"
        >
          <AnimatePresence>
            {shown.map((b, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.35, ease: [0.2, 0.8, 0.2, 1] }}
                className={
                  b.kind === 'me'
                    ? 'self-end max-w-[80%]'
                    : b.kind === 'them'
                      ? 'self-start max-w-[88%]'
                      : b.kind === 'score'
                        ? 'self-start w-[min(100%,290px)] ml-2'
                        : 'self-start ml-3'
                }
              >
                {b.kind === 'them' && (
                  <div className="px-4 py-3 border border-border rounded-[20px_20px_20px_6px] bg-surface/92 shadow-card">
                    <p className="m-0 font-serif-italic text-[15px] sm:text-[16px] leading-[1.5] text-text-2">
                      {b.text}
                    </p>
                  </div>
                )}
                {b.kind === 'me' && (
                  <div
                    className="px-4 py-2.5 rounded-[20px_20px_6px_20px] shadow-accent"
                    style={{
                      background:
                        'linear-gradient(180deg, var(--color-accent) 0%, #4353DC 100%)',
                    }}
                  >
                    <p className="m-0 text-[14px] sm:text-[15px] leading-[1.5] text-[#F2F3FE]">
                      {b.text}
                    </p>
                  </div>
                )}
                {b.kind === 'score' && (
                  <div className="px-4 py-3.5 border border-border-2 rounded-[18px] bg-surface shadow-soft">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-[14px] font-bold tracking-tight text-text truncate">
                        {b.word}
                      </span>
                      <span className="font-mono text-[11px] text-green shrink-0">
                        {b.score} / 100
                      </span>
                    </div>
                    <div className="mt-2.5 h-[5px] rounded-full bg-border overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${b.score}%` }}
                        transition={{ duration: 0.9, ease: [0.2, 0.8, 0.2, 1], delay: 0.15 }}
                        className="h-full rounded-full"
                        style={{
                          background:
                            'linear-gradient(90deg, var(--color-accent) 0%, var(--color-green) 100%)',
                        }}
                      />
                    </div>
                    <p className="mt-2.5 mb-0 text-[11.5px] leading-[1.5] text-muted">{b.note}</p>
                  </div>
                )}
                {b.kind === 'memory' && (
                  <div className="inline-flex items-center gap-2 px-3 py-2 border border-amber-border rounded-full bg-amber-bg">
                    <span className="w-[5px] h-[5px] rounded-full bg-amber-text-2 shrink-0" />
                    <span className="text-[11px] tracking-[.01em] text-amber-text">{b.text}</span>
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        {/* Status line — the honest, escalating part. aria-live so it's announced, not silent. */}
        <div className="mt-8 flex items-center gap-2.5 min-h-[24px]" role="status" aria-live="polite">
          <span className="w-4 h-4 rounded-full border-2 border-border-2 border-t-accent animate-spin shrink-0" />
          <AnimatePresence mode="wait">
            <motion.p
              key={stage.at}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.22 }}
              className="m-0 text-[13px] text-muted text-center text-pretty"
            >
              {stage.label}
            </motion.p>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

// ── Full-screen error ──────────────────────────────────────────────────
// Deliberately says nothing technical. The old copy printed VITE_API_URL at the user, which
// is meaningless to them and reads as a broken build. `attempts` escalates the guidance once
// retrying clearly isn't working, so we stop implying one more tap will fix it.
export function FullScreenError({ title, message, onRetry, attempts = 0, retrying = false }) {
  const persistent = attempts >= 2;
  return (
    <div className="min-h-dvh flex items-center justify-center bg-bg px-5 py-10 overflow-y-auto">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center w-full max-w-[440px]"
      >
        <div className="w-14 h-14 rounded-2xl bg-amber-bg border border-amber-border text-amber-text flex items-center justify-center mx-auto mb-5">
          <CloudOff size={22} />
        </div>
        <h2 className="text-xl sm:text-[22px] font-bold m-0 mb-2.5 text-text text-balance">
          {title}
        </h2>
        <p className="text-text-3 text-[14.5px] m-0 leading-relaxed text-pretty">{message}</p>

        {persistent && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-3 mb-0 text-[13px] text-muted leading-relaxed text-pretty"
          >
            Still not working? It may be a longer outage on our side — please try again in a
            little while. Nothing you’ve saved is affected.
          </motion.p>
        )}

        {onRetry && (
          <button
            onClick={onRetry}
            disabled={retrying}
            className="mt-6 inline-flex items-center justify-center gap-2 bg-accent hover:bg-accent-hover disabled:opacity-70 disabled:cursor-wait text-white rounded-2xl px-6 py-3 text-sm font-semibold shadow-accent cursor-pointer transition-colors focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
          >
            <RefreshCw size={15} className={retrying ? 'animate-spin' : ''} />
            {retrying ? 'Trying…' : 'Try again'}
          </button>
        )}
      </motion.div>
    </div>
  );
}

// ── Skeleton placeholders ──────────────────────────────────────────────
// Calm, content-shaped loaders for cloud-latency data fetches. A gentle
// gradient sweep (see .skeleton-shimmer in index.css) over the neutral
// border-2 token — no new colors, no bouncy motion.

export function Skeleton({ className = '', style }) {
  return <div style={style} className={`skeleton-shimmer rounded-lg ${className}`} />;
}

// Softer fade/slide used when real content replaces a skeleton.
const REVEAL = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.25, ease: [0.2, 0.8, 0.2, 1] },
};
export { REVEAL };

// Matches WordRow: name (w-190) + score bar (flex-1) + score number + chevron.
export function WordRowSkeleton() {
  return (
    <div className="border-b border-[#F1F2F6] last:border-b-0">
      <div className="flex items-center gap-4 px-6 py-4">
        <Skeleton className="h-4 w-[150px] shrink-0 rounded-md" />
        <div className="flex-1 h-2 skeleton-shimmer rounded-full" />
        <Skeleton className="h-4 w-9 rounded-md" />
        <Skeleton className="h-3.5 w-3.5 rounded-md" />
      </div>
    </div>
  );
}

// Matches a thread list item: title line + a shorter meta line.
export function ThreadItemSkeleton() {
  return (
    <div className="rounded-xl px-3 py-2.5">
      <div className="flex justify-between items-center gap-2">
        <Skeleton className="h-3.5 w-[60%] rounded-md" />
        <Skeleton className="h-3 w-8 rounded-md" />
      </div>
      <Skeleton className="h-2.5 w-[38%] mt-2 rounded-md" />
    </div>
  );
}

// Matches a chat bubble; alternates alignment via `mine`.
export function MessageBubbleSkeleton({ mine = false }) {
  if (mine) {
    return (
      <div className="flex justify-end">
        <Skeleton className="h-[58px] w-[52%] max-w-[560px] rounded-[18px_4px_18px_18px]" />
      </div>
    );
  }
  return (
    <div className="flex gap-3 max-w-[640px]">
      <Skeleton className="w-[30px] h-[30px] rounded-full shrink-0 mt-1" />
      <Skeleton className="h-[64px] w-[60%] rounded-[4px_18px_18px_18px]" />
    </div>
  );
}

// Matches StatCard: small label line + a larger value line.
export function StatCardSkeleton() {
  return (
    <div className="rounded-2xl px-5 py-4 border bg-surface border-border">
      <Skeleton className="h-2.5 w-[55%] rounded-md" />
      <Skeleton className="h-6 w-[45%] mt-2.5 rounded-md" />
    </div>
  );
}

// Matches a Discover catalog card: circular avatar + name line + relation line, centered.
export function DiscoverCardSkeleton() {
  return (
    <div className="rounded-[18px] border border-border bg-surface flex flex-col items-center gap-2.5 px-3 py-4">
      <Skeleton className="w-[72px] h-[72px] rounded-full" />
      <Skeleton className="h-3.5 w-[70%] rounded-md" />
      <Skeleton className="h-2.5 w-[45%] rounded-md" />
    </div>
  );
}

// Matches a "Your personas" row: avatar + name/relation/count lines + a couple of action pills.
export function PersonaRowSkeleton() {
  return (
    <div className="bg-surface border border-border rounded-[18px] p-4 sm:p-5">
      <div className="flex items-center gap-4">
        <Skeleton className="w-16 h-16 rounded-full shrink-0" />
        <div className="flex-1 min-w-0">
          <Skeleton className="h-4 w-[45%] rounded-md" />
          <Skeleton className="h-3 w-[30%] rounded-md mt-2" />
          <Skeleton className="h-2.5 w-[22%] rounded-md mt-2" />
        </div>
      </div>
      <div className="flex gap-2 mt-4">
        <Skeleton className="h-8 w-32 rounded-xl" />
        <Skeleton className="h-8 w-20 rounded-xl" />
      </div>
    </div>
  );
}

// Matches the memory markdown block: a few lines of varying width.
export function MemoryEditorSkeleton() {
  const widths = ['85%', '70%', '92%', '55%', '78%', '40%'];
  return (
    <div className="flex-1 flex flex-col gap-3.5 px-6 py-5">
      {widths.map((w, i) => (
        <Skeleton key={i} className="h-3.5 rounded-md" style={{ width: w }} />
      ))}
    </div>
  );
}

// ── Model tier ("brain") card ──────────────────────────────────────────
// One selectable card for a Swift/Sage tier. Sage carries a subtle visual "step up"
// (icon + accent) so the hierarchy reads without ever calling the cheaper one "dumb".
// Used in onboarding (pick-then-continue) and Settings (instant switch).
export function TierCard({ tier, selected, onSelect, disabled = false }) {
  const isSage = tier.key === 'sage';
  const Icon = isSage ? Sparkles : Zap;
  return (
    <button
      type="button"
      onClick={() => !disabled && onSelect?.(tier.key)}
      disabled={disabled}
      className={`relative text-left w-full rounded-2xl border p-5 transition-all cursor-pointer disabled:cursor-not-allowed ${
        selected
          ? 'border-accent bg-accent-soft shadow-accent'
          : 'border-border-2 bg-surface hover:border-accent/50'
      }`}
    >
      {selected && (
        <span className="absolute top-4 right-4 w-6 h-6 rounded-full bg-accent text-white flex items-center justify-center">
          <Check size={14} strokeWidth={3} />
        </span>
      )}
      <div className="flex items-center gap-2.5">
        <span
          className={`w-9 h-9 rounded-xl flex items-center justify-center ${
            isSage ? 'bg-accent text-white' : 'bg-accent-soft text-accent'
          }`}
        >
          <Icon size={18} />
        </span>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-lg font-bold text-text leading-none">{tier.name}</span>
            {isSage && (
              <span className="text-[10px] font-semibold uppercase tracking-wider text-accent">
                More powerful
              </span>
            )}
          </div>
          <div className="text-[11px] font-mono text-muted-2 mt-1 truncate">{tier.model}</div>
        </div>
      </div>
      <p className="mt-3 mb-0 text-[13.5px] leading-relaxed text-text-3">{tier.tagline}</p>
      <div className="mt-3 pt-3 border-t border-border-2 text-[11.5px] text-muted-2 font-mono">
        {tier.price}
      </div>
    </button>
  );
}

export function ScoreBar({ score, slipping }) {
  return (
    <div className="flex-1 h-2 bg-[#EFF1F5] rounded-full overflow-hidden">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${Math.max(0, Math.min(100, score))}%` }}
        transition={{ duration: 0.6, ease: [0.2, 0.8, 0.2, 1] }}
        className={`h-full rounded-full ${
          slipping ? 'bg-[#E4B15E]' : 'bg-linear-to-r from-accent to-[#7B8AF0]'
        }`}
      />
    </div>
  );
}
