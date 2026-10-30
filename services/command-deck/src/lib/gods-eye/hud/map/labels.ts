/**
 * Greedy map-label placement (SPEC §5.3 "Labels", §13.5).
 *
 * Each label is tried at up to eight candidate positions around its anchor
 * (right, left, below, above and the four corners) and takes the first one
 * that stays inside the view and overlaps neither an occupied box (the
 * marker discs, the pins) nor a label placed before it. Labels are placed in
 * priority order (higher first; ties keep the caller's order), so the
 * selected vehicle's own label and the newest reads win the space. A label
 * that fits nowhere is DROPPED (the canvas shows it on hover instead).
 *
 * O(n·k) with k = 8 candidates against the boxes placed so far; the canvas
 * caps n at 120 and runs it on camera-move end and on data change, never
 * per frame. Pure: no DOM, no Cesium.
 *
 * Exported for other layers to reuse (plan contract X7):
 *   placeLabels(items, occupied, opts) → { placed, dropped }
 */

/** A candidate position: right, left, below, above, then the corners. */
export type LabelPos = 'r' | 'l' | 'b' | 't' | 'br' | 'tr' | 'bl' | 'tl';

/** Every candidate in the default try order. */
export const LABEL_POSITIONS: readonly LabelPos[] = ['r', 'l', 'b', 't', 'br', 'tr', 'bl', 'tl'];

/** An axis-aligned screen box (CSS px, origin top-left). */
export interface Box {
	x: number;
	y: number;
	w: number;
	h: number;
}

/** One label to place: its anchor, its size and the radius of what it labels. */
export interface LabelItem {
	id: string;
	/** Anchor (the marker's drawn centre). */
	x: number;
	y: number;
	/** Label box size. */
	w: number;
	h: number;
	/** Radius of the marker the label belongs to (the label clears it). */
	r?: number;
	/** Candidate order for this label (default LABEL_POSITIONS). */
	prefer?: readonly LabelPos[];
	/** Higher places first. */
	priority?: number;
}

export interface PlacedLabel {
	id: string;
	pos: LabelPos;
	box: Box;
}

export interface PlaceOptions {
	/** The view size: a label never leaves it (minus `margin`). */
	width: number;
	height: number;
	/** Keep-out at the view's edges, px (default 2). */
	margin?: number;
	/** Gap between the marker's edge and the label, px (default 4). */
	gap?: number;
	/** At most this many labels are considered (default 120, SPEC §13.5). */
	max?: number;
}

export interface PlaceResult {
	placed: Map<string, PlacedLabel>;
	/** Ids that fit nowhere (shown on hover). */
	dropped: string[];
}

/** The most labels one placement pass considers (SPEC §13.5). */
export const LABEL_MAX = 120;

export const boxesOverlap = (a: Box, b: Box): boolean => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;

/** The box of a label at candidate `pos` around anchor (x, y) of a marker of radius r. */
export function candidateBox(pos: LabelPos, x: number, y: number, w: number, h: number, r = 0, gap = 4): Box {
	const g = r + gap;
	switch (pos) {
		case 'r':
			return { x: x + g, y: y - h / 2, w, h };
		case 'l':
			return { x: x - g - w, y: y - h / 2, w, h };
		case 'b':
			return { x: x - w / 2, y: y + g, w, h };
		case 't':
			return { x: x - w / 2, y: y - g - h, w, h };
		case 'br':
			return { x: x + g - 2, y: y + 2, w, h };
		case 'tr':
			return { x: x + g - 2, y: y - h - 2, w, h };
		case 'bl':
			return { x: x - g - w + 2, y: y + 2, w, h };
		case 'tl':
			return { x: x - g - w + 2, y: y - h - 2, w, h };
	}
}

/** A disc of radius r at (x, y) as an occupied box. */
export function discBox(x: number, y: number, r: number): Box {
	return { x: x - r, y: y - r, w: 2 * r, h: 2 * r };
}

/**
 * Place labels greedily. Pure; the result keeps every placed label's
 * position and box, and lists the ids that fit nowhere.
 */
export function placeLabels(items: readonly LabelItem[], occupied: readonly Box[], opts: PlaceOptions): PlaceResult {
	const margin = opts.margin ?? 2;
	const gap = opts.gap ?? 4;
	const max = Math.max(0, Math.min(opts.max ?? LABEL_MAX, LABEL_MAX));
	const boxes: Box[] = [...occupied];
	const placed = new Map<string, PlacedLabel>();
	const dropped: string[] = [];
	const ordered = items
		.map((it, i) => ({ it, i }))
		.filter(({ it }) => Number.isFinite(it.x) && Number.isFinite(it.y) && it.w > 0 && it.h > 0)
		.sort((a, b) => (b.it.priority ?? 0) - (a.it.priority ?? 0) || a.i - b.i)
		.map(({ it }) => it);
	ordered.forEach((it, n) => {
		if (n >= max) {
			dropped.push(it.id);
			return;
		}
		for (const pos of it.prefer?.length ? it.prefer : LABEL_POSITIONS) {
			const box = candidateBox(pos, it.x, it.y, it.w, it.h, it.r ?? 0, gap);
			if (box.x < margin || box.y < margin || box.x + box.w > opts.width - margin || box.y + box.h > opts.height - margin) continue;
			if (boxes.some((b) => boxesOverlap(b, box))) continue;
			boxes.push(box);
			placed.set(it.id, { id: it.id, pos, box });
			return;
		}
		dropped.push(it.id);
	});
	return { placed, dropped };
}
