import { motion } from 'motion/react';
import { RefreshCw } from 'lucide-react';
import { initial } from '../utils';

export function PersonaAvatar({ name, size = 'md', online = false }) {
  const sizes = {
    xs: 'w-[30px] h-[30px] text-sm',
    sm: 'w-[34px] h-[34px] text-base',
    md: 'w-[42px] h-[42px] text-lg',
    lg: 'w-16 h-16 text-2xl',
    xl: 'w-[72px] h-[72px] text-3xl',
  };
  return (
    <div className="relative shrink-0">
      <div
        className={`${sizes[size]} rounded-full bg-linear-to-br from-accent to-[#9AA6F5] text-white flex items-center justify-center font-serif-italic shadow-accent`}
      >
        {initial(name)}
      </div>
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
