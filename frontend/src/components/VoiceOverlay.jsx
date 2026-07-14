import { useEffect } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Mic, Sparkles, X } from 'lucide-react';
import { PersonaAvatar } from './Shared';
import { useVoiceSession } from '../hooks/useVoiceSession';

/**
 * VoiceOverlay — the full-screen "talk to your persona" experience.
 *
 * A blurred backdrop over the app with the persona's avatar centered. The avatar breathes
 * while listening and pulses in rings while the persona speaks, so it feels like the person
 * is really there. Live transcripts sit below; word-score "pops" float up whenever the user
 * nails (or fumbles) a target word — the USP, shown to everyone regardless of Developer mode.
 *
 * All audio/session logic lives in useVoiceSession; this component is purely presentational.
 * On close it stops the session (which asks the server to persist the final turn) and calls
 * onClose so the parent can refresh the chat thread the voice conversation was saved into.
 */

const EVENT_TONE = {
  perfect_unprompted: { ring: '#1E7D4B', bg: '#EAF8F0', border: '#BFE8D2', text: '#1E7D4B' },
  perfect_prompted: { ring: '#1E7D4B', bg: '#EAF8F0', border: '#BFE8D2', text: '#1E7D4B' },
  awkward: { ring: '#B67A1B', bg: 'var(--color-amber-bg)', border: 'var(--color-amber-border)', text: 'var(--color-amber-text)' },
  wrong: { ring: '#C6453B', bg: '#FCEFEE', border: '#F2CBC7', text: '#C6453B' },
};

function ScorePop({ score, onDone }) {
  const tone = EVENT_TONE[score.event_type] || EVENT_TONE.perfect_unprompted;
  useEffect(() => {
    const t = setTimeout(() => onDone(score.id), 2600);
    return () => clearTimeout(t);
  }, [score.id, onDone]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.9 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -14, scale: 0.95 }}
      transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
      className="flex items-center gap-2 rounded-2xl border px-3.5 py-1.5 text-sm font-medium shadow-sm"
      style={{ backgroundColor: tone.bg, borderColor: tone.border, color: tone.text }}
    >
      <Sparkles size={13} className="shrink-0" />
      <span className="font-semibold">“{score.word}”</span>
      <span className="font-mono font-semibold">{score.delta > 0 ? `+${score.delta}` : score.delta}</span>
      {score.note ? <span className="opacity-80 max-w-[220px] truncate">· {score.note}</span> : null}
    </motion.div>
  );
}

export default function VoiceOverlay({ open, conversationId, personaName, personaAvatar, onClose }) {
  const voice = useVoiceSession(conversationId);
  const { status, error, speaking, listening, inputText, outputText, scores, dismissScore, start, stop } = voice;

  // Auto-start when the overlay opens; always stop when it closes/unmounts.
  useEffect(() => {
    if (open && conversationId) start();
    return () => stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, conversationId]);

  // Escape to close.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') handleClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const handleClose = () => {
    stop();
    onClose?.();
  };

  const statusLabel =
    status === 'connecting' ? 'Connecting…'
    : status === 'error' ? (error || 'Something went wrong')
    : speaking ? `${personaName} is speaking…`
    : listening ? 'Listening…'
    : status === 'live' ? 'Listening…'
    : 'Starting…';

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.25 }}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center backdrop-blur-xl bg-bg/70"
        >
          {/* close */}
          <button
            onClick={handleClose}
            aria-label="End voice"
            className="absolute top-5 right-5 w-10 h-10 rounded-full bg-surface/80 border border-border flex items-center justify-center text-muted hover:text-text transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>

          {/* score pops */}
          <div className="absolute top-6 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 w-full px-6 max-w-md pointer-events-none">
            <AnimatePresence>
              {scores.map((s) => (
                <ScorePop key={s.id} score={s} onDone={dismissScore} />
              ))}
            </AnimatePresence>
          </div>

          {/* the persona presence */}
          <div className="relative flex items-center justify-center mb-8">
            {/* speaking rings */}
            <AnimatePresence>
              {speaking && (
                <>
                  {[0, 1, 2].map((i) => (
                    <motion.span
                      key={i}
                      initial={{ scale: 1, opacity: 0.45 }}
                      animate={{ scale: 2.1, opacity: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 1.8, repeat: Infinity, delay: i * 0.6, ease: 'easeOut' }}
                      className="absolute w-[110px] h-[110px] rounded-full bg-accent/25"
                    />
                  ))}
                </>
              )}
            </AnimatePresence>
            {/* breathing while listening */}
            <motion.div
              animate={
                speaking
                  ? { scale: [1, 1.06, 1] }
                  : listening
                    ? { scale: [1, 1.03, 1] }
                    : { scale: 1 }
              }
              transition={{ duration: speaking ? 0.7 : 2.4, repeat: Infinity, ease: 'easeInOut' }}
              className="relative rounded-full"
            >
              <div className="drop-shadow-[0_18px_40px_-14px_rgba(90,103,216,0.6)]">
                <PersonaAvatar name={personaName} avatarUrl={personaAvatar} size="xl" online={status === 'live'} />
              </div>
            </motion.div>
          </div>

          <div className="text-center px-8 max-w-lg">
            <h2 className="font-serif-italic text-2xl text-text mb-1">{personaName}</h2>
            <p className="text-sm text-muted mb-6">{statusLabel}</p>

            {/* live transcript (current turn) */}
            <div className="min-h-[3.5rem] space-y-2">
              <AnimatePresence mode="popLayout">
                {outputText && (
                  <motion.p
                    key="out"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="text-[15px] text-text-2 leading-relaxed"
                  >
                    {outputText}
                  </motion.p>
                )}
                {inputText && (
                  <motion.p
                    key="in"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="text-[13.5px] text-muted italic leading-relaxed"
                  >
                    “{inputText}”
                  </motion.p>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* stop control */}
          <div className="absolute bottom-10 flex flex-col items-center gap-3">
            {status === 'error' ? (
              <button
                onClick={start}
                className="px-6 py-3 rounded-full bg-accent text-white font-medium shadow-accent hover:bg-accent-hover transition-colors cursor-pointer"
              >
                Try again
              </button>
            ) : (
              <button
                onClick={handleClose}
                className="w-16 h-16 rounded-full bg-red text-white flex items-center justify-center shadow-[0_12px_30px_-10px_rgba(198,69,59,0.7)] hover:brightness-110 transition cursor-pointer"
                aria-label="End voice conversation"
              >
                <span className="w-5 h-5 rounded-[4px] bg-white" />
              </button>
            )}
            <p className="text-xs text-muted flex items-center gap-1.5">
              <Mic size={12} /> Tap to end · saved to this chat
            </p>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
