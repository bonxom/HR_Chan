import type { FC } from 'react';

/*
 * Light liquid glass, used as an accent on the clean design: navigation bars, floating
 * layers (dialogs, menus, toasts) and summary tiles. Dense content such as tables and
 * forms uses GLASS_PANEL, which stays nearly opaque so text keeps its contrast.
 * Both fall back to an opaque surface when the user asks for reduced transparency.
 */
const GLASS_EDGE =
  'border border-white/70 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),inset_0_-1px_0_rgba(255,255,255,0.4),0_12px_32px_-14px_rgba(15,60,50,0.28)]';
const GLASS_FALLBACK = 'reduced-transparency:bg-surface reduced-transparency:backdrop-blur-none';

export const GLASS_BAR = `${GLASS_EDGE} bg-white/55 backdrop-blur-2xl backdrop-saturate-[1.8] ${GLASS_FALLBACK}`;
export const GLASS_PANEL = `${GLASS_EDGE} bg-white/80 backdrop-blur-xl backdrop-saturate-150 ${GLASS_FALLBACK}`;
export const GLASS_LAYER = `${GLASS_EDGE} bg-white/85 backdrop-blur-2xl backdrop-saturate-[1.8] ${GLASS_FALLBACK}`;

/** Soft brand-tinted light behind the page; glass needs colour behind it to read. */
export const AmbientBackdrop: FC = () => (
  <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
    <div className="absolute -left-[10%] -top-[15%] h-[60vh] w-[55vw] rounded-full bg-brand/20 blur-[110px]" />
    <div className="absolute -right-[10%] top-[10%] h-[55vh] w-[45vw] rounded-full bg-cyan-300/25 blur-[110px]" />
    <div className="absolute bottom-[-20%] left-[25%] h-[55vh] w-[50vw] rounded-full bg-amber-200/30 blur-[120px]" />
  </div>
);
