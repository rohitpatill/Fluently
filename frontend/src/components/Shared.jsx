import { motion } from 'motion/react';
import { RefreshCw, Zap, Sparkles, Check } from 'lucide-react';
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
    <div className="h-screen flex flex-col items-center justify-center gap-4 bg-bg">
      <Spinner />
      <p className="text-muted text-sm">{label}</p>
    </div>
  );
}

export function FullScreenError({ title, message, onRetry }) {
  return (
    <div className="h-screen flex items-center justify-center bg-bg">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center max-w-[420px] px-6"
      >
        <div className="w-14 h-14 rounded-2xl bg-red/10 text-red flex items-center justify-center mx-auto mb-5 text-2xl">
          !
        </div>
        <h2 className="text-xl font-bold m-0 mb-2">{title}</h2>
        <p className="text-muted text-sm m-0 mb-6 leading-relaxed">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="inline-flex items-center gap-2 bg-accent hover:bg-accent-hover text-white rounded-2xl px-6 py-3 text-sm font-semibold shadow-accent cursor-pointer transition-colors"
          >
            <RefreshCw size={15} /> Try again
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
