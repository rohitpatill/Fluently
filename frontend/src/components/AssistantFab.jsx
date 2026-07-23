import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * AssistantFab — the draggable "Ask Fluently" floating button.
 *
 * The user asked to be able to drag it anywhere so it never collides with a screen's own
 * controls (e.g. the chat composer's send/mic buttons). Behaviour:
 *   - Draggable by pointer (mouse + touch, via Pointer Events).
 *   - A TAP (no meaningful movement) opens the assistant; a DRAG only moves it — a small
 *     movement threshold separates the two so a drag never accidentally opens the overlay.
 *   - On release it snaps to the nearest side edge and clamps within a safe vertical band
 *     (kept above the mobile bottom nav), so it always looks intentional.
 *   - Position persists in localStorage. DEFAULT is the LEFT side, a bit above centre.
 *
 * Uses the app logo (public/logo.svg) on a white disc so it clearly reads as "Fluently".
 */

const POS_KEY = 'fluently.assistantFabPos'; // { side: 'left'|'right', top: <px from top> }
const FAB = 56; // button size (px)
const EDGE = 16; // gap from the screen edge
const BOTTOM_SAFE = 96; // keep clear of the mobile bottom nav
const TOP_SAFE = 16;
const DRAG_THRESHOLD = 6; // px of movement before it counts as a drag, not a tap

function loadPos() {
  try {
    const raw = localStorage.getItem(POS_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* noop */ }
  // Default: left side, roughly 60% down the viewport.
  return { side: 'left', top: Math.round(window.innerHeight * 0.6) };
}

function clampTop(top) {
  const max = window.innerHeight - BOTTOM_SAFE - FAB;
  const min = TOP_SAFE;
  return Math.min(Math.max(top, min), Math.max(min, max));
}

export default function AssistantFab({ onOpen }) {
  const [pos, setPos] = useState(loadPos);
  const [dragging, setDragging] = useState(false);
  const btnRef = useRef(null);
  const stateRef = useRef({ moved: false, startX: 0, startY: 0, offsetY: 0 });

  // Re-clamp on viewport resize so it never ends up off-screen or under the nav.
  useEffect(() => {
    const onResize = () => setPos((p) => ({ ...p, top: clampTop(p.top) }));
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const persist = useCallback((next) => {
    try { localStorage.setItem(POS_KEY, JSON.stringify(next)); } catch { /* noop */ }
  }, []);

  const onPointerDown = (e) => {
    const rect = btnRef.current.getBoundingClientRect();
    stateRef.current = {
      moved: false,
      startX: e.clientX,
      startY: e.clientY,
      offsetY: e.clientY - rect.top, // where inside the button we grabbed
    };
    btnRef.current.setPointerCapture(e.pointerId);
    setDragging(true);
  };

  const onPointerMove = (e) => {
    if (!dragging) return;
    const s = stateRef.current;
    const dx = e.clientX - s.startX;
    const dy = e.clientY - s.startY;
    if (!s.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return; // still a tap
    s.moved = true;
    // Follow the finger vertically; side is decided by which half of the screen we're on.
    const top = clampTop(e.clientY - s.offsetY);
    const side = e.clientX < window.innerWidth / 2 ? 'left' : 'right';
    setPos({ side, top });
  };

  const endDrag = (e) => {
    if (!dragging) return;
    setDragging(false);
    try { btnRef.current.releasePointerCapture(e.pointerId); } catch { /* noop */ }
    const s = stateRef.current;
    if (!s.moved) {
      onOpen?.(); // it was a tap
      return;
    }
    // Snap: keep the side we ended on, clamp the top, persist.
    setPos((p) => {
      const next = { side: p.side, top: clampTop(p.top) };
      persist(next);
      return next;
    });
  };

  const style = {
    top: pos.top,
    ...(pos.side === 'left' ? { left: EDGE } : { right: EDGE }),
    width: FAB,
    height: FAB,
    touchAction: 'none', // let us handle the drag; don't scroll the page
  };

  return (
    <button
      ref={btnRef}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      aria-label="Ask Fluently"
      style={style}
      className={`fixed z-40 rounded-full bg-white border border-border shadow-card flex items-center justify-center overflow-hidden select-none cursor-grab active:cursor-grabbing hover:shadow-accent transition-shadow ${
        dragging ? 'scale-105' : ''
      }`}
    >
      <img
        src="/logo.svg"
        alt=""
        draggable="false"
        className="w-full h-full object-cover pointer-events-none"
      />
    </button>
  );
}
