import { motion } from 'motion/react';
import { AlertCircle } from 'lucide-react';
import * as api from '../api';

/** The official multi-color Google "G" mark (inline SVG so it needs no external asset). */
function GoogleGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
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

export default function Login() {
  // The backend bounces failed logins back with ?auth_error=1 so we can surface it gently.
  const authError = new URLSearchParams(window.location.search).has('auth_error');

  return (
    <div className="h-screen bg-linear-to-b from-bg to-accent-soft flex items-center justify-center animate-fade-in">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        className="w-[420px] max-w-[90vw] flex flex-col items-center text-center"
      >
        <div className="flex items-center gap-2.5 mb-8">
          <div className="w-2.5 h-2.5 rounded-full bg-accent" />
          <span className="text-[15px] font-bold tracking-tight text-text">Fluently</span>
        </div>

        <div className="w-full bg-surface border border-border-2 rounded-[22px] shadow-soft px-9 py-10">
          <h1 className="m-0 text-[28px] font-bold tracking-tight leading-tight text-text">
            Welcome back.
          </h1>
          <p className="mt-2.5 mb-0 text-[15px] text-[#6B7080] font-serif-italic leading-relaxed">
            Sign in to pick up where you left off — your words, your chats, your companion.
          </p>

          <button
            onClick={api.loginWithGoogle}
            className="mt-8 w-full flex items-center justify-center gap-3 bg-surface hover:bg-[#F7F8FA] border border-border-2 rounded-2xl px-6 py-3.5 text-[15px] font-semibold text-text-2 cursor-pointer transition-colors shadow-card"
          >
            <GoogleGlyph />
            Continue with Google
          </button>

          {authError && (
            <div className="mt-4 flex items-center justify-center gap-2 text-[13px] text-red">
              <AlertCircle size={14} />
              Sign-in didn't go through. Please try again.
            </div>
          )}
        </div>

        <p className="mt-6 mb-0 text-[12.5px] text-muted-2 leading-relaxed px-6">
          New here? Continuing with Google creates your account automatically.
        </p>
      </motion.div>
    </div>
  );
}
