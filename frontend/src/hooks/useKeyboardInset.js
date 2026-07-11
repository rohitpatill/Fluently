import { useEffect, useState } from 'react';

/**
 * Tracks the mobile on-screen keyboard via the VisualViewport API.
 *
 * When a soft keyboard opens, the visual viewport shrinks from the bottom while
 * the layout viewport (what `fixed`/`dvh` are measured against) does not. The
 * gap between them is the keyboard height. We expose that height as `inset` and
 * a boolean `open`.
 *
 * On desktop / browsers without VisualViewport (or when no keyboard is shown)
 * this stays at `{ inset: 0, open: false }`, so callers can leave the layout
 * completely untouched there.
 */
export default function useKeyboardInset() {
  const [state, setState] = useState({ inset: 0, open: false });

  useEffect(() => {
    const vv = typeof window !== 'undefined' ? window.visualViewport : null;
    if (!vv) return;

    const update = () => {
      // Height hidden below the visual viewport = keyboard (plus any bottom UI).
      const inset = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
      // Small threshold so browser chrome jitter doesn't count as a keyboard.
      const open = inset > 120;
      setState((prev) =>
        prev.open === open && Math.abs(prev.inset - inset) < 1
          ? prev
          : { inset: open ? inset : 0, open }
      );
    };

    update();
    vv.addEventListener('resize', update);
    vv.addEventListener('scroll', update);
    return () => {
      vv.removeEventListener('resize', update);
      vv.removeEventListener('scroll', update);
    };
  }, []);

  return state;
}
