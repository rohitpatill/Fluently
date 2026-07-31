import { motion } from 'motion/react';
import { AlertCircle } from 'lucide-react';
import * as api from '../api';

/** The official multi-color Google "G" mark (inline SVG so it needs no external asset). */
function GoogleGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" className="shrink-0">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.47.9 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z"
      />
    </svg>
  );
}

/**
 * The ambient page wash: two soft accent-tinted radial pools, one breathing accent glow,
 * and a faint vertical rule grid masked to fade out at the edges. Purely decorative —
 * every layer is aria-hidden and pointer-events-none so it can never intercept the CTA.
 */
function Backdrop() {
  return (
    <>
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
      <div
        aria-hidden="true"
        className="absolute -top-[14%] -right-[6%] w-[min(58vw,720px)] h-[min(58vw,720px)] rounded-full blur-[6px] pointer-events-none animate-breathe"
        style={{
          background:
            'radial-gradient(circle, rgba(75,93,228,.16) 0%, rgba(75,93,228,0) 68%)',
        }}
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 pointer-events-none opacity-50"
        style={{
          backgroundImage:
            'linear-gradient(to right, rgba(26,29,39,.035) 1px, transparent 1px)',
          backgroundSize: '96px 100%',
          maskImage: 'radial-gradient(90% 70% at 50% 40%, #000 0%, transparent 78%)',
          WebkitMaskImage: 'radial-gradient(90% 70% at 50% 40%, #000 0%, transparent 78%)',
        }}
      />
    </>
  );
}

/**
 * The "engine" — a tilted 3D stack showing what Fluently actually does in one glance:
 * the companion asks about your life, you answer using a tracked word, the word's score
 * moves, memory updates itself. Each layer sits at a different translateZ so the whole
 * thing has real depth under `perspective`. Decorative: hidden on phones (where the
 * copy + CTA must own the screen) and fully aria-hidden.
 */
function Engine() {
  return (
    <div
      aria-hidden="true"
      className="hidden md:flex flex-1 basis-90 min-w-0 max-w-[520px] justify-center [perspective:1400px] max-lg:mx-auto max-lg:max-w-[620px] max-[520px]:landscape:hidden"
    >
      <div
        className="relative w-full max-w-[420px] [transform-style:preserve-3d] animate-drift
                   max-lg:animate-none max-lg:[transform:rotateY(-7deg)_rotateX(4deg)_rotate(-1deg)]"
      >
        {/* accent bloom behind the stack */}
        <div
          className="absolute inset-y-[6%] inset-x-[4%] -bottom-[8%] rounded-[30px] blur-[18px]"
          style={{
            background:
              'radial-gradient(60% 60% at 50% 40%, rgba(75,93,228,.16) 0%, rgba(75,93,228,0) 72%)',
          }}
        />

        <div className="relative flex flex-col gap-3.5">
          {/* the companion, in its serif-italic voice */}
          <div
            className="self-start max-w-[86%] px-[19px] py-[15px] border border-border rounded-[22px_22px_22px_8px]
                       bg-surface/92 shadow-card [transform:translateZ(26px)]"
          >
            <p className="m-0 font-serif-italic text-[17px] leading-[1.5] text-text-2">
              So — how did yesterday's demo actually go? You were dreading it.
            </p>
          </div>

          {/* the user's reply, using a tracked word */}
          <div
            className="self-end max-w-[74%] px-[18px] py-[13px] rounded-[22px_22px_8px_22px]
                       shadow-accent-lg [transform:translateZ(48px)]"
            style={{
              background:
                'linear-gradient(180deg, var(--color-accent) 0%, #4353DC 100%)',
            }}
          >
            <p className="m-0 text-[15px] leading-[1.5] text-[#F2F3FE]">
              Honestly? I was unflappable. Nobody could tell.
            </p>
          </div>

          {/* the score moving, silently */}
          <div
            className="self-start w-[min(100%,300px)] mt-1.5 ml-3.5 px-[17px] py-[15px] border border-border-2
                       rounded-[20px] bg-surface shadow-soft [transform:translateZ(70px)]"
          >
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-[15px] font-bold tracking-tight text-text">unflappable</span>
              <span className="font-mono text-[11px] text-green">84 / 100</span>
            </div>
            <div className="mt-[11px] h-[5px] rounded-full bg-border overflow-hidden">
              <div
                className="w-[84%] h-full rounded-full"
                style={{
                  background:
                    'linear-gradient(90deg, var(--color-accent) 0%, var(--color-green) 100%)',
                }}
              />
            </div>
            <p className="mt-[11px] mb-0 text-[12px] leading-[1.55] text-muted">
              used unprompted, in the right place
            </p>
          </div>

          {/* memory curating itself */}
          <div
            className="self-start flex items-center gap-2 ml-5 px-[13px] py-2 border border-amber-border
                       rounded-full bg-amber-bg [transform:translateZ(88px)]"
          >
            <div className="w-[5px] h-[5px] rounded-full bg-amber-text-2" />
            <span className="text-[11.5px] tracking-[.01em] text-amber-text">
              memory updated — the demo went well
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Login() {
  // The backend bounces failed logins back with ?auth_error=1 so we can surface it gently.
  const authError = new URLSearchParams(window.location.search).has('auth_error');

  return (
    <div
      className="relative min-h-dvh w-full overflow-x-hidden overflow-y-auto flex items-center justify-center
                 px-[clamp(20px,5vw,64px)] py-[clamp(24px,5vw,72px)]
                 max-[520px]:landscape:items-start"
    >
      <Backdrop />

      <div className="relative w-full max-w-[1180px] flex flex-wrap items-center justify-center gap-[clamp(36px,6vw,88px)] max-lg:flex-col max-lg:items-stretch max-lg:gap-10">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="flex-1 basis-95 min-w-0 max-w-[520px] flex flex-col items-start max-lg:mx-auto max-lg:max-w-[620px] max-md:max-w-full"
        >
          <div className="flex items-center gap-2.5 mb-[clamp(28px,4vw,44px)]">
            <div className="w-2.5 h-2.5 rounded-full bg-accent shadow-accent" />
            <span className="text-[15px] font-bold tracking-tight text-text">Fluently</span>
          </div>

          <h1 className="m-0 text-[clamp(34px,5.2vw,52px)] leading-[1.04] tracking-[-.032em] font-bold text-balance">
            Someone to talk to,
            <br />
            <span className="font-serif-italic font-normal tracking-[-.015em]">
              who wants your English to get better.
            </span>
          </h1>

          <p className="mt-[18px] mb-0 max-w-[42ch] text-[clamp(15px,1.2vw,16.5px)] leading-[1.65] text-text-3 text-pretty">
            Chat or talk out loud with a companion you shape yourself. It remembers your life,
            tracks the words you're learning, and slips them back into conversation before you
            notice.
          </p>

          <div className="w-full mt-[clamp(30px,4vw,40px)] flex flex-col gap-3.5 items-start">
            <button
              type="button"
              onClick={api.loginWithGoogle}
              className="w-full max-w-[340px] max-md:max-w-full min-h-[52px] inline-flex items-center justify-center gap-3
                         px-[26px] py-[15px] border border-accent-soft-border rounded-xl2
                         text-[15.5px] font-semibold text-text-2 cursor-pointer shadow-soft
                         transition-[box-shadow,transform,border-color] duration-200 ease-out
                         hover:shadow-[0_14px_34px_-14px_rgba(75,93,228,.35)] hover:border-[#C7CDF8] hover:-translate-y-px
                         active:translate-y-0
                         focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-[3px]"
              style={{
                background:
                  'linear-gradient(180deg, var(--color-surface) 0%, var(--color-surface-2) 100%)',
              }}
            >
              <GoogleGlyph />
              Continue with Google
            </button>

            {authError && (
              <div
                role="alert"
                className="flex items-center gap-2 px-[13px] py-[9px] border border-red-border rounded-xl
                           bg-red-bg text-[13px] text-red animate-chip-pop"
              >
                <AlertCircle size={14} className="shrink-0" />
                That sign-in didn't go through. Give it another try.
              </div>
            )}

            <p className="mt-0.5 mb-0 text-[12.5px] leading-[1.6] text-muted">
              One click is the whole of it — new here, Google creates your account automatically.
            </p>
          </div>
        </motion.div>

        <Engine />
      </div>
    </div>
  );
}
