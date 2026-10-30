/**
 * The live map's shared drawing kit (the landmarks, live-values and flow layers):
 *
 *   cityGround(ctx)    the ground height the city's marks sit at (metres above the ellipsoid), sampled from the scene
 *                      itself — the photoreal 3D tiles or the globe — at the City Pack's road crossings and refreshed
 *                      every 90 s (the base map can change under a running map). The island city lies near sea level: one height for the
 *                      city keeps hundreds of labels and moving flow dots off the per-primitive terrain clamp.
 *   declutter          ONE label budget for every layer that registers here: on each camera move (≤ 4 per second)
 *                      the labels are placed in priority order (alerts, then landmarks, live values, roads, areas,
 *                      stations) and a label that would overlap one already placed — or that its zoom band leaves
 *                      out (maxAlt) — is hidden. Nothing is drawn twice; nothing is invented.
 *   glyphImage(…)      a small cached disc image with a one-letter glyph (neutral by default; colour only for meaning).
 *
 * Cesium is reached loosely here (the deck's cesium.d.ts is a subset): LabelCollection, BillboardCollection and
 * PointPrimitiveCollection are the primitive collections the brief asks for instead of thousands of entities.
 */

import type { GodsEyeLayerContext } from '../../registry';
import { PLACE_MARKS } from '$lib/city/places';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Loose = any;

/** Does this Cesium build (or a test double) carry the primitive collections the live layers draw with? */
export function primitivesOk(ctx: GodsEyeLayerContext): boolean {
	const c = ctx.cesium as Loose;
	const scene = (ctx.viewer as Loose)?.scene;
	return (
		typeof c?.Cartesian3 === 'function' &&
		typeof c?.Cartesian3?.fromDegrees === 'function' &&
		typeof c?.LabelCollection === 'function' &&
		typeof c?.BillboardCollection === 'function' &&
		typeof c?.PointPrimitiveCollection === 'function' &&
		typeof scene?.primitives?.add === 'function'
	);
}

// ── the city's ground height ────────────────────────────────────────────────

const GROUND_REFRESH_MS = 90_000;
const groundByViewer = new WeakMap<object, { h: number; at: number; busy: boolean; sampled: boolean }>();

/** Road crossings from the City Pack: open ground where the photoreal mesh is the road surface. */
function groundProbes(): Array<[number, number]> {
	return PLACE_MARKS.filter((p) => p.kind === 'junction')
		.slice(0, 18)
		.map((p) => [p.lon, p.lat]);
}

/** The median of the finite values (NaN for none). */
export function median(xs: readonly number[]): number {
	const v = xs.filter((x) => Number.isFinite(x)).sort((a, b) => a - b);
	if (!v.length) return Number.NaN;
	return v.length % 2 ? v[v.length >> 1] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2;
}

/** The city's ground height now (0 until the first sample lands); kicks a re-sample when due. */
export function cityGround(ctx: GodsEyeLayerContext): number {
	const viewer = ctx.viewer as Loose;
	let g = groundByViewer.get(viewer);
	if (!g) groundByViewer.set(viewer, (g = { h: 0, at: 0, busy: false, sampled: false }));
	const now = Date.now();
	if (!g.busy && now - g.at > GROUND_REFRESH_MS) {
		g.busy = true;
		g.at = now;
		const cesium = ctx.cesium as Loose;
		const scene = viewer.scene;
		let cartos: Loose[] = [];
		try {
			cartos = groundProbes().map(([lon, lat]) => cesium.Cartographic.fromDegrees(lon, lat));
		} catch {
			g.busy = false;
			return g.h;
		}
		const done = (h: number) => {
			const st = groundByViewer.get(viewer);
			if (!st) return;
			st.busy = false;
			if (Number.isFinite(h)) {
				st.h = h;
				st.sampled = true;
			}
		};
		try {
			const p = scene?.sampleHeightMostDetailed?.(cartos);
			if (p && typeof p.then === 'function') {
				p.then((rows: Array<{ height?: number }>) => done(median(rows.map((r) => (r?.height ?? Number.NaN) as number)))).catch(() => done(Number.NaN));
			} else {
				const h = median(cartos.map((c: Loose) => scene?.globe?.getHeight?.(c) ?? Number.NaN));
				done(h);
			}
		} catch {
			done(Number.NaN);
		}
	}
	return g.h;
}

// ── one label budget for every registered layer ─────────────────────────────

export interface DeclutterItem {
	key: string;
	/** Lower draws first: 0 alert · 1 landmark · 2 live value · 3 road · 4 area · 5 station. */
	priority: number;
	/** World position (Cartesian3) the label is anchored at. */
	position: unknown;
	/** The label's box in px (estimated from its text). */
	w: number;
	h: number;
	/** Box offset from the anchor in px (the label sits above its dot by default). */
	dy?: number;
	/** Hidden above this camera height (m): the zoom band. */
	maxAlt: number;
	apply(show: boolean): void;
}

/** A label's box from its text: ~0.56 em per character of the widest line, plus a margin. */
export function labelBox(text: string, fontPx: number): { w: number; h: number } {
	const lines = String(text).split('\n');
	const widest = Math.max(...lines.map((l) => l.length));
	return { w: Math.round(widest * fontPx * 0.56 + 10), h: Math.round(lines.length * (fontPx + 3) + 6) };
}

/** Greedy placement in priority order: the keys shown (pure; exported for tests). */
export function placeLabels(
	items: ReadonlyArray<{ key: string; priority: number; x: number; y: number; w: number; h: number }>,
	view: { w: number; h: number },
	max = 90,
	keepOut: ReadonlyArray<[number, number, number, number]> = [],
): Set<string> {
	const shown = new Set<string>();
	// the page's panels over the canvas count as taken: a label under a panel is a label nobody reads
	const boxes: Array<[number, number, number, number]> = [...keepOut];
	const sorted = [...items].sort((a, b) => a.priority - b.priority || a.key.localeCompare(b.key));
	for (const it of sorted) {
		if (shown.size >= max) break;
		const x0 = it.x - it.w / 2;
		const y0 = it.y - it.h;
		const x1 = x0 + it.w;
		const y1 = it.y;
		if (x1 < 0 || y1 < 0 || x0 > view.w || y0 > view.h) continue;
		let hit = false;
		for (const b of boxes) {
			if (x0 < b[2] + 3 && x1 > b[0] - 3 && y0 < b[3] + 2 && y1 > b[1] - 2) {
				hit = true;
				break;
			}
		}
		if (hit) continue;
		boxes.push([x0, y0, x1, y1]);
		shown.add(it.key);
	}
	return shown;
}

/** The chrome floating over the map (the page's [data-ge-keepout] panels and the canvas's own v2 chrome), in canvas px. */
function keepOutBoxes(canvas: HTMLCanvasElement): Array<[number, number, number, number]> {
	if (typeof document === 'undefined' || !canvas.getBoundingClientRect) return [];
	const o = canvas.getBoundingClientRect();
	const out: Array<[number, number, number, number]> = [];
	for (const el of document.querySelectorAll('[data-ge-keepout], .v2-panel, .v2-legend, .v2-nav, .v2-readout, .v2-top > *, .cesium-viewer-bottom')) {
		const r = el.getBoundingClientRect();
		if (r.width > 0 && r.height > 0) out.push([r.left - o.left - 4, r.top - o.top - 4, r.right - o.left + 4, r.bottom - o.top + 4]);
	}
	return out;
}

class Declutter {
	private layers = new Map<string, DeclutterItem[]>();
	private lastPose = '';
	private lastRun = 0;
	private dirty = true;
	private remove: (() => void) | null = null;
	shown = 0;
	candidates = 0;

	constructor(private readonly ctx: GodsEyeLayerContext) {
		const scene = (ctx.viewer as Loose).scene;
		const ev = scene?.postRender ?? scene?.preUpdate;
		if (ev?.addEventListener) {
			const off = ev.addEventListener(() => this.tick());
			this.remove = typeof off === 'function' ? off : () => ev.removeEventListener?.(this.tick);
		}
	}

	set(layer: string, items: DeclutterItem[]) {
		this.layers.set(layer, items);
		this.dirty = true;
	}

	clear(layer: string) {
		this.layers.delete(layer);
		this.dirty = true;
	}

	private tick() {
		const now = performance.now();
		if (now - this.lastRun < 250) return;
		const cam = (this.ctx.viewer as Loose).camera;
		const p = cam?.positionWC;
		const d = cam?.directionWC;
		const pose = p && d ? `${Math.round(p.x)},${Math.round(p.y)},${Math.round(p.z)},${d.x.toFixed(3)},${d.y.toFixed(3)},${d.z.toFixed(3)}` : '';
		if (pose === this.lastPose && !this.dirty) return;
		this.lastPose = pose;
		this.lastRun = now;
		this.dirty = false;
		this.run();
	}

	run() {
		const viewer = this.ctx.viewer as Loose;
		const cesium = this.ctx.cesium as Loose;
		const scene = viewer.scene;
		const alt = viewer.camera?.positionCartographic?.height ?? 0;
		const canvas = scene.canvas as HTMLCanvasElement;
		const view = { w: canvas.clientWidth || canvas.width, h: canvas.clientHeight || canvas.height };
		const all: DeclutterItem[] = [];
		for (const items of this.layers.values()) all.push(...items);
		const proj: Array<{ key: string; priority: number; x: number; y: number; w: number; h: number }> = [];
		const byKey = new Map<string, DeclutterItem>();
		for (const it of all) {
			byKey.set(it.key, it);
			if (alt > it.maxAlt) continue;
			let wp: { x: number; y: number } | undefined;
			try {
				wp = cesium.SceneTransforms.worldToWindowCoordinates(scene, it.position);
			} catch {
				wp = undefined;
			}
			if (!wp || !Number.isFinite(wp.x)) continue;
			proj.push({ key: it.key, priority: it.priority, x: wp.x, y: wp.y + (it.dy ?? 0), w: it.w, h: it.h });
		}
		this.candidates = proj.length;
		const max = Math.max(24, Math.min(110, Math.round((view.w * view.h) / 19_000)));
		const shown = placeLabels(proj, view, max, keepOutBoxes(canvas));
		this.shown = shown.size;
		for (const [key, it] of byKey) it.apply(shown.has(key));
	}

	destroy() {
		this.remove?.();
		this.remove = null;
		this.layers.clear();
	}
}

const engines = new WeakMap<object, Declutter>();

/** The viewer's one label budget (created on first use). */
export function declutterFor(ctx: GodsEyeLayerContext): Declutter {
	let e = engines.get(ctx.viewer as object);
	if (!e) engines.set(ctx.viewer as object, (e = new Declutter(ctx)));
	return e;
}

// ── field units (agency-units.ts) ───────────────────────────────────────────

/** A unit glides to its newly reported position over this long (≈ one city-registry poll). */
export const UNIT_GLIDE_MS = 4200;
/** …unless the report is this far away (m): a reassignment or a new run jumps. */
export const UNIT_JUMP_M = 1500;

/** The v2 always-on tag: the unit id and its status word ("KTP-EM-LC3 · patrol"), emulated units say so. */
export function unitTag(u: { unitId: string; status?: string | null; emulated?: boolean }): string {
	const st = u.status ? u.status.replace(/_/g, ' ') : '';
	return `${u.unitId}${st ? ` · ${st}` : ''}${u.emulated ? ' (emulated)' : ''}`;
}

// ── glyph images ────────────────────────────────────────────────────────────

const glyphCache = new Map<string, HTMLCanvasElement>();

/** A disc with a one-letter glyph (cached by look). `ring` is the rim colour; `fill` the disc. */
export function glyphImage(letter: string, fill: string, ring: string, ink: string, px = 32): HTMLCanvasElement | null {
	if (typeof document === 'undefined') return null;
	const key = `${letter}|${fill}|${ring}|${ink}|${px}`;
	const hit = glyphCache.get(key);
	if (hit) return hit;
	const c = document.createElement('canvas');
	c.width = c.height = px;
	const g = c.getContext('2d');
	if (!g) return null;
	const r = px / 2;
	g.beginPath();
	g.arc(r, r, r - 2, 0, Math.PI * 2);
	g.fillStyle = fill;
	g.fill();
	g.lineWidth = 2.5;
	g.strokeStyle = ring;
	g.stroke();
	if (letter) {
		g.fillStyle = ink;
		g.font = `700 ${Math.round(px * 0.5)}px system-ui, sans-serif`;
		g.textAlign = 'center';
		g.textBaseline = 'middle';
		g.fillText(letter, r, r + 1);
	}
	glyphCache.set(key, c);
	return c;
}

/** A soft ring image for pulses (white, transparent centre), cached. */
export function ringImage(px = 64, stroke = 'rgba(255,255,255,0.95)'): HTMLCanvasElement | null {
	if (typeof document === 'undefined') return null;
	const key = `ring|${px}|${stroke}`;
	const hit = glyphCache.get(key);
	if (hit) return hit;
	const c = document.createElement('canvas');
	c.width = c.height = px;
	const g = c.getContext('2d');
	if (!g) return null;
	g.beginPath();
	g.arc(px / 2, px / 2, px / 2 - 3, 0, Math.PI * 2);
	g.lineWidth = 3;
	g.strokeStyle = stroke;
	g.stroke();
	glyphCache.set(key, c);
	return c;
}

/** "20:41:07" in IST (the map's clocks are the city's). */
export function istClock(ms: number): string {
	return new Date(ms).toLocaleTimeString('en-GB', { timeZone: 'Asia/Kolkata', hour12: false });
}

/** Minutes ago in plain words ("now", "4 min", "2 h"). */
export function agoShort(ms: number, now = Date.now()): string {
	const s = Math.max(0, Math.round((now - ms) / 1000));
	if (s < 60) return 'now';
	const m = Math.round(s / 60);
	if (m < 60) return `${m} min`;
	const h = Math.round(m / 60);
	return h < 48 ? `${h} h` : `${Math.round(h / 24)} d`;
}
