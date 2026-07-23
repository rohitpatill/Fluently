import { useEffect, useRef } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Check, Mic, Sparkles, X } from 'lucide-react';
import { useAssistantSession } from '../hooks/useAssistantSession';

/**
 * AssistantOverlay — the full-screen "talk to Fluently" help experience.
 *
 * Deliberately looks DIFFERENT from the persona VoiceOverlay: instead of a persona avatar, a
 * glowing Fluently sparkle mark, so the user feels they're talking to the app itself, not a
 * companion. Live captions below; small action toasts pop when the assistant creates a persona,
 * adds a word, or switches the tier. Nothing here is saved or scored.
 *
 * All audio/session logic lives in useAssistantSession; this is purely presentational.
 * `tab` is the current app screen, forwarded so the assistant can ground its help.
 */

function ActionToast({ action, onDone }) {
  useEffect(() => {
    const t = setTimeout(() => onDone(action.id), 4200);
    return () => clearTimeout(t);
  }, [action.id, onDone]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.9 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -14, scale: 0.95 }}
      transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
      className="flex items-center gap-2 rounded-2xl border px-3.5 py-2 text-sm font-medium shadow-sm bg-[#EAF8F0] border-[#BFE8D2] text-[#1E7D4B] max-w-sm"
    >
      <Check size={15} className="shrink-0" />
      <span>{action.message}</span>
    </motion.div>
  );
}

export default function AssistantOverlay({ open, tab, onAction, onClose }) {
  const asst = useAssistantSession(tab);
  const { status, error, speaking, listening, inputText, outputText, actions, dismissAction, start, stop } = asst;

  // Fire onAction once per NEW action so the parent can refresh the affected caches live.
  const seenActionRef = useRef(0);
  useEffect(() => {
    actions.forEach((a) => {
      if (a.id > seenActionRef.current) {
        seenActionRef.current = a.id;
        onAction?.(a.name);
      }
    });
  }, [actions, onAction]);

  // Auto-start when opened; always stop on close/unmount.
  useEffect(() => {
    if (open) start();
    return () => stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

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
    status === 'connecting' ? 'Waking Fluently…'
    : status === 'error' ? (error || 'Something went wrong')
    : speaking ? 'Fluently is speaking…'
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
          className="fixed inset-0 z-[60] flex flex-col items-center justify-center backdrop-blur-xl bg-bg/70"
        >
          <button
            onClick={handleClose}
            aria-label="Close Fluently assistant"
            className="absolute top-5 right-5 w-10 h-10 rounded-full bg-surface/80 border border-border flex items-center justify-center text-muted hover:text-text transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>

          {/* action toasts */}
          <div className="absolute top-6 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 w-full px-6 max-w-md pointer-events-none">
            <AnimatePresence>
              {actions.map((a) => (
                <ActionToast key={a.id} action={a} onDone={dismissAction} />
              ))}
            </AnimatePresence>
          </div>

          {/* the Fluently sparkle presence */}
          <div className="relative flex items-center justify-center mb-8">
            <AnimatePresence>
              {speaking && (
                <>
                  {[0, 1, 2].map((i) => (
                    <motion.span
                      key={i}
                      initial={{ scale: 1, opacity: 0.4 }}
                      animate={{ scale: 2.1, opacity: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 1.8, repeat: Infinity, delay: i * 0.6, ease: 'easeOut' }}
                      className="absolute w-[120px] h-[120px] rounded-full bg-accent/25"
                    />
                  ))}
                </>
              )}
            </AnimatePresence>
            <motion.div
              animate={
                speaking ? { scale: [1, 1.06, 1] }
                  : listening ? { scale: [1, 1.03, 1] }
                    : { scale: 1 }
              }
              transition={{ duration: speaking ? 0.7 : 2.4, repeat: Infinity, ease: 'easeInOut' }}
              className="relative w-28 h-28 rounded-full bg-linear-to-br from-accent to-accent-hover flex items-center justify-center shadow-accent drop-shadow-[0_18px_40px_-14px_rgba(90,103,216,0.6)]"
            >
              <Sparkles size={44} className="text-white" />
            </motion.div>
          </div>

          <div className="text-center px-8 max-w-lg">
            <h2 className="font-serif-italic text-2xl text-text mb-1">Fluently</h2>
            <p className="text-sm text-muted mb-6">{statusLabel}</p>

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
                aria-label="End assistant"
              >
                <span className="w-5 h-5 rounded-[4px] bg-white" />
              </button>
            )}
            <p className="text-xs text-muted flex items-center gap-1.5">
              <Mic size={12} /> Ask about any feature · not saved, not scored
            </p>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
