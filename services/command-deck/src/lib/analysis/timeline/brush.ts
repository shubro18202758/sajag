/**
 * The brush maths of the timeline (SPEC §5.3 "Live semantics"), pure.
 *
 * Live is on EXACTLY when there is no time window (workspace.timeWindow ===
 * null). Brushing — a drag on the histogram, or a Shift-drag anywhere on the
 * timeline — sets the window, which turns Live off; the Live switch and the
 * travel bar's one "Return to live" clear it. A press that moves less than
 * MIN_BRUSH_PX is a click (the cursor), never a window.
 *
 *   Scale        the time ↔ x mapping of the plot area
 *   brushWindow  two x positions → a window (sorted, clamped), or null
 *   moveEdge     drag a grip: one edge moves, the window never inverts and
 *                keeps at least MIN_WINDOW_MS
 *   shiftWindow  move a whole window (step, play, a drag inside it); a window
 *                pushed past `now` returns to live (null)
 *   applyBrush   the one write: store.setTimeWindow(a, b)
 */

/** A press that moves less than this is a click, not a brush. */
export const MIN_BRUSH_PX = 4;
/** The narrowest window a grip drag leaves. */
export const MIN_WINDOW_MS = 30_000;

export interface Scale {
	start: number;
	end: number;
	/** The plot area's left and right x (px). */
	x0: number;
	x1: number;
}

export function xOf(s: Scale, t: number): number {
	const span = s.end - s.start || 1;
	return s.x0 + ((t - s.start) / span) * (s.x1 - s.x0);
}

export function tOf(s: Scale, x: number): number {
	const w = s.x1 - s.x0 || 1;
	const cx = Math.max(s.x0, Math.min(s.x1, x));
	return s.start + ((cx - s.x0) / w) * (s.end - s.start);
}

/** Two x positions → a window over the scale (sorted, clamped to the plot); null when it is a click. */
export function brushWindow(s: Scale, xa: number, xb: number, minPx = MIN_BRUSH_PX): [number, number] | null {
	const a = Math.max(s.x0, Math.min(s.x1, Math.min(xa, xb)));
	const b = Math.max(s.x0, Math.min(s.x1, Math.max(xa, xb)));
	if (b - a < minPx) return null;
	return [Math.round(tOf(s, a)), Math.round(tOf(s, b))];
}

/** A window clamped into [start, end] (null when nothing of it is left). */
export function clampWindow(w: readonly [number, number] | null, start: number, end: number): [number, number] | null {
	if (!w) return null;
	const a = Math.max(start, Math.min(w[0], w[1]));
	const b = Math.min(end, Math.max(w[0], w[1]));
	return b > a ? [a, b] : null;
}

/** Drag one edge of a window to `t`: the other edge stays, the window keeps ≥ minMs and never inverts. */
export function moveEdge(w: readonly [number, number], edge: 'start' | 'end', t: number, minMs = MIN_WINDOW_MS): [number, number] {
	if (edge === 'start') return [Math.min(t, w[1] - minMs), w[1]];
	return [w[0], Math.max(t, w[0] + minMs)];
}

/**
 * Move a whole window by `delta` ms. Past `now` it is live again (null): the
 * window never runs into the future.
 */
export function shiftWindow(w: readonly [number, number], delta: number, now: number): [number, number] | null {
	const a = w[0] + delta;
	const b = w[1] + delta;
	if (b >= now) return null;
	return [a, b];
}

/** Which part of a window a press at x hits: a grip (± 6 px of an edge), the inside, or nothing. */
export function hitWindow(s: Scale, w: readonly [number, number] | null, x: number, gripPx = 6): 'start' | 'end' | 'inside' | null {
	if (!w) return null;
	const xa = xOf(s, w[0]);
	const xb = xOf(s, w[1]);
	if (Math.abs(x - xa) <= gripPx) return 'start';
	if (Math.abs(x - xb) <= gripPx) return 'end';
	if (x > xa && x < xb) return 'inside';
	return null;
}

/** What the brush writes to: the workspace store's window API (§7.1). */
export interface WindowStore {
	timeWindow: readonly [number, number] | null;
	readonly live: boolean;
	setTimeWindow(a: number, b: number): void;
	returnToLive(): void;
}

/** The one write a brush makes: a window, which turns Live off. */
export function applyBrush(store: WindowStore, w: readonly [number, number] | null): void {
	if (w) store.setTimeWindow(w[0], w[1]);
}

/** Live is exactly "no window". */
export function isLive(window: readonly [number, number] | null | undefined): boolean {
	return window == null;
}

/**
 * The cursor: "Now" at the right edge while live; otherwise the moment the
 * operator put it on, else the window's end.
 */
export function cursorOf(window: readonly [number, number] | null, now: number, picked: number | null): number {
	if (!window) return now;
	return picked != null ? picked : window[1];
}
