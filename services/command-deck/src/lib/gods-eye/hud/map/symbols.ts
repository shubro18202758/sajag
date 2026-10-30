/**
 * The operator map's symbology under chrome v2 (SPEC §2.4, §5.3 "Markers").
 *
 * COLOUR MEANS STATE ONLY. Every object is a neutral 21 px disc
 * (--v-map-marker-fill) with a 1.5 px --v-map-marker ring and a 12 px type
 * glyph from kindIcon(); hue appears only by role — the watchlisted or
 * stolen vehicle's ring (--v-map-alert), the convoy (--v-map-route),
 * corridor events (--v-map-event), the decision dot and the hold point
 * (--v-map-decision) and the selection (--v-map-select). Colours come only
 * from the --v-map-* tokens (mapInk), read at runtime through the design
 * tokens' cssVar() with the typed mirror as the fallback; this module never
 * names --v-act, --v-data or --v-tool.
 *
 * Images are drawn once per state into a 2D canvas (Blueprint path data
 * through Path2D, text in the deck's own web fonts) and cached as data URLs,
 * so Cesium's texture atlas reuses one entry per state. Every marker image
 * is the same 38 × 38 px box around its centre (room for the selection halo,
 * the decision dot and the count chip), so states swap without moving.
 * Without a DOM (unit tests) the painters answer null and the graphics keep
 * their size and clamp.
 *
 * Labels follow the formatter (svgLabelParts, SPEC §3.3): identifiers in the
 * mono face, times and words in Inter with tabular figures, on the
 * --v-map-label-bg plate.
 *
 * META: a layer tags each v2 marker entity (tagMarker) with what it is —
 * URN, kind, glyph, role, time, label — and the canvas's v2 pass reads the
 * tags to cluster, place labels, fade, dim and mark the selection, without
 * the layer redrawing.
 */

import { cssVar as tokenVar, flowStop, flowStyle, mapColor, type FlowStop, type MapRole } from '$lib/design/tokens';
import { iconPaths, type IconName } from '$lib/design/icons';
import { svgLabelParts, type SvgLabelPart } from '$lib/ui/format/format';
import { clampedBillboard } from '../../layers/draping';

// ── tokens ───────────────────────────────────────────────────────────────

/** A --v-map-* role's colour (runtime token; typed mirror without a DOM). */
export function mapInk(role: MapRole): string {
	return tokenVar(`--v-map-${role}`) || mapColor(role);
}

/** The ramp step (1–5) of a congestion index (tokens.ts), for layers that key a picture on it. */
export { flowStop };

/** The neutral flow ramp's drawing of a congestion index (tokens.ts flowStyle). */
export function flowInk(congestionIdx: number): { stop: FlowStop; color: string; width: number; casing: string | null } {
	const stop = flowStop(congestionIdx);
	return { stop, ...flowStyle(stop) };
}

/** A token colour at `alpha` (rgba() from #rrggbb or rgb(); anything else passes through). */
export function inkAlpha(css: string, alpha: number): string {
	const a = Math.max(0, Math.min(1, alpha));
	const hex = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(css.trim());
	if (hex) return `rgba(${parseInt(hex[1], 16)}, ${parseInt(hex[2], 16)}, ${parseInt(hex[3], 16)}, ${a})`;
	const rgb = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)$/i.exec(css.trim());
	if (rgb) return `rgba(${rgb[1]}, ${rgb[2]}, ${rgb[3]}, ${(rgb[4] != null ? Number(rgb[4]) : 1) * a})`;
	return css;
}

// ── metrics (SPEC §5.3; prototype ui-views.js) ─────────────────────────────

export const MARKER = Object.freeze({
	/** Every marker image is this square box around its centre. */
	box: 38,
	/** Neutral disc diameter and ring. */
	disc: 21,
	ring: 1.5,
	/** Hue-bearing rings (vehicle, convoy) and the selected ring. */
	roleRing: 2.5,
	glyph: 12,
	/** Selection halo radius. */
	halo: 17,
	/** Decision dot: radius and offset from the centre. */
	dot: 5.5,
	dotAt: 12,
	/** Count chip: radius and offset from the centre; its digits (px), never below 11 (SPEC §1.6, §3.2). */
	chip: 7,
	chipAt: 9,
	chipText: 11,
	/** Hit radius used for label keep-out and clustering. */
	radius: 11,
});

/** The vehicle pin: the tip on the last read, the head 46 px up-left (SPEC §5.3). */
export const PIN = Object.freeze({ dx: -26, dy: -38, head: 14, glyph: 16, tip: 3 });

/** Label plate metrics. */
export const LABEL = Object.freeze({ h: 20, padX: 6, size: 12, radius: 3, lock: 12 });

// ── painting ──────────────────────────────────────────────────────────────

const SCALE = 2;
const cache = new Map<string, MapImage | null>();

/** A painted image: data URL, CSS-px size, and the pixelOffset that puts its anchor on the position. */
export interface MapImage {
	url: string;
	w: number;
	h: number;
	/** pixelOffset (CSS px, y down) for CENTER/CENTER origins so the anchor lands on the position. */
	offset: { x: number; y: number };
}

function canvas2d(w: number, h: number): CanvasRenderingContext2D | null {
	if (typeof document === 'undefined' || typeof document.createElement !== 'function') return null;
	const c = document.createElement('canvas');
	if (!c || typeof c.getContext !== 'function') return null;
	c.width = Math.ceil(w * SCALE);
	c.height = Math.ceil(h * SCALE);
	const g = c.getContext('2d');
	if (!g) return null;
	g.scale(SCALE, SCALE);
	return g;
}

function finish(g: CanvasRenderingContext2D, w: number, h: number, anchor: { x: number; y: number }): MapImage | null {
	try {
		const url = g.canvas.toDataURL('image/png');
		return { url, w, h, offset: { x: w / 2 - anchor.x, y: h / 2 - anchor.y } };
	} catch {
		return null;
	}
}

/**
 * At most this many painted images are kept (least recently used first
 * out): label images are keyed by their text — plates, camera ids, read
 * times — so a wall that runs for days would otherwise grow without bound.
 * The markers' few states stay hot and never fall out.
 */
export const MAP_IMAGE_CACHE_MAX = 512;

function memo(key: string, paint: () => MapImage | null): MapImage | null {
	const hit = cache.get(key);
	if (hit) {
		// a hit moves to the newest end (Map keeps insertion order)
		cache.delete(key);
		cache.set(key, hit);
		return hit;
	}
	const img = paint();
	// a failed paint (no DOM yet) is not cached: the next call may succeed
	if (img) {
		cache.set(key, img);
		while (cache.size > MAP_IMAGE_CACHE_MAX) {
			const oldest = cache.keys().next().value;
			if (oldest === undefined) break;
			cache.delete(oldest);
		}
	}
	return img;
}

/** How many painted images are cached now (the unit test reads it). */
export function mapImageCacheSize(): number {
	return cache.size;
}

/** Forget every painted image (after the web fonts load, or a theme change). */
export function clearMapImages(): void {
	cache.clear();
}

/** Draw a Blueprint glyph centred on (cx, cy) at `size` px. */
function glyph(g: CanvasRenderingContext2D, name: IconName, cx: number, cy: number, size: number, fill: string) {
	if (typeof Path2D !== 'function') return;
	const { paths, grid } = iconPaths(name, size);
	if (!paths.length) return;
	g.save();
	g.translate(cx - size / 2, cy - size / 2);
	g.scale(size / grid, size / grid);
	g.fillStyle = fill;
	for (const d of paths) g.fill(new Path2D(d), 'evenodd');
	g.restore();
}

function circle(g: CanvasRenderingContext2D, x: number, y: number, r: number, fill: string | null, stroke: string | null, width = 0) {
	g.beginPath();
	g.arc(x, y, r, 0, Math.PI * 2);
	if (fill) {
		g.fillStyle = fill;
		g.fill();
	}
	if (stroke && width > 0) {
		g.lineWidth = width;
		g.strokeStyle = stroke;
		g.stroke();
	}
}

function roundRect(g: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
	g.beginPath();
	g.moveTo(x + r, y);
	g.lineTo(x + w - r, y);
	g.arcTo(x + w, y, x + w, y + r, r);
	g.lineTo(x + w, y + h - r);
	g.arcTo(x + w, y + h, x + w - r, y + h, r);
	g.lineTo(x + r, y + h);
	g.arcTo(x, y + h, x, y + h - r, r);
	g.lineTo(x, y + r);
	g.arcTo(x, y, x + r, y, r);
	g.closePath();
}

/** The UI and identifier faces, from the type tokens (canvas text cannot read var()). */
export function mapFaces(): { ui: string; id: string } {
	return { ui: tokenVar('--v-font-ui') || 'sans-serif', id: tokenVar('--v-font-mono') || 'monospace' };
}

/** Load the faces the map's canvas text uses (labels, count chips); resolves either way. */
export async function ensureMapFonts(): Promise<boolean> {
	if (typeof document === 'undefined' || !document.fonts?.load) return false;
	const { ui, id } = mapFaces();
	try {
		await Promise.all([
			document.fonts.load(`${LABEL.size}px ${ui}`),
			document.fonts.load(`600 ${MARKER.chipText}px ${ui}`),
			document.fonts.load(`${LABEL.size}px ${id}`),
		]);
		return true;
	} catch {
		return false;
	}
}

/** What a marker image shows. */
export interface MarkerLook {
	glyph: IconName;
	/** Ring hue: neutral by default. */
	role?: 'marker' | 'alert' | 'route' | 'event' | 'decision';
	shape?: 'disc' | 'square';
	/** Disc diameter (21 by default). */
	size?: number;
	selected?: boolean;
	hover?: boolean;
	decision?: boolean;
	/** Members behind a cluster lead (≥ 2 draws the count chip). */
	count?: number;
}

/** A marker: disc (or rounded square) + ring + glyph, with selection, decision dot and count chip. */
export function markerImage(look: MarkerLook): MapImage | null {
	const size = look.size ?? MARKER.disc;
	const key = `m|${look.glyph}|${look.role ?? 'marker'}|${look.shape ?? 'disc'}|${size}|${look.selected ? 1 : 0}|${look.hover ? 1 : 0}|${look.decision ? 1 : 0}|${look.count ?? 0}`;
	return memo(key, () => {
		const B = Math.max(MARKER.box, size + 18);
		const g = canvas2d(B, B);
		if (!g) return null;
		const c = B / 2;
		const r = size / 2;
		const select = mapInk('select');
		if (look.selected) circle(g, c, c, Math.max(MARKER.halo, r + 6), inkAlpha(select, 0.32), null);
		const ringInk = look.selected ? select : look.hover ? mapInk('label-ink') : look.role && look.role !== 'marker' ? mapInk(look.role) : mapInk('marker');
		const ringW = look.selected || (look.role && look.role !== 'marker') ? MARKER.roleRing : MARKER.ring;
		if (look.shape === 'square') {
			roundRect(g, c - r, c - r, size, size, 4);
			g.fillStyle = mapInk('marker-fill');
			g.fill();
			g.lineWidth = ringW;
			g.strokeStyle = look.selected ? select : mapInk('label-ink');
			g.stroke();
		} else {
			circle(g, c, c, r, mapInk('marker-fill'), ringInk, ringW);
		}
		glyph(g, look.glyph, c, c, size >= 26 ? 16 : MARKER.glyph, mapInk('label-ink'));
		if (look.decision) circle(g, c + MARKER.dotAt, c - MARKER.dotAt, MARKER.dot, mapInk('decision'), mapInk('casing'), 1.5);
		if ((look.count ?? 0) > 1) countChip(g, c + MARKER.chipAt, c + MARKER.chipAt, look.count as number);
		return finish(g, B, B, { x: c, y: c });
	});
}

function countChip(g: CanvasRenderingContext2D, x: number, y: number, n: number) {
	const text = n > 99 ? '99+' : String(n);
	const r = text.length > 1 ? MARKER.chip + 2 : MARKER.chip;
	// the pressed-control fill: neutral, never a hue (SPEC §2.4)
	circle(g, x, y, r, tokenVar('--v-surface-4') || mapInk('marker-fill'), mapInk('casing'), 1.5);
	g.fillStyle = mapInk('label-ink');
	g.font = `600 ${MARKER.chipText}px ${mapFaces().ui}`;
	g.textAlign = 'center';
	g.textBaseline = 'middle';
	g.fillText(text, x, y + 0.5);
}

/** The vehicle pin: tip dot on the last read, leader line, head disc 46 px up-left. */
export function pinImage(look: { glyph: IconName; selected?: boolean; decision?: boolean; alert?: boolean }): MapImage | null {
	const key = `p|${look.glyph}|${look.selected ? 1 : 0}|${look.decision ? 1 : 0}|${look.alert === false ? 0 : 1}`;
	return memo(key, () => {
		const pad = 22;
		const minX = PIN.dx - pad;
		const minY = PIN.dy - pad;
		const W = -minX + 6;
		const H = -minY + 6;
		const g = canvas2d(W, H);
		if (!g) return null;
		const tip = { x: -minX, y: -minY };
		const head = { x: tip.x + PIN.dx, y: tip.y + PIN.dy };
		const ring = look.alert === false ? mapInk('marker') : mapInk('alert');
		const select = mapInk('select');
		// leader: casing under a thin line
		g.lineCap = 'round';
		g.beginPath();
		g.moveTo(tip.x, tip.y);
		g.lineTo(head.x, head.y);
		g.lineWidth = 4;
		g.strokeStyle = mapInk('casing');
		g.stroke();
		g.lineWidth = 1.5;
		g.strokeStyle = look.selected ? select : ring;
		g.stroke();
		circle(g, tip.x, tip.y, PIN.tip, ring, mapInk('casing'), 1.5);
		if (look.selected) circle(g, head.x, head.y, PIN.head + 7, inkAlpha(select, 0.32), null);
		circle(g, head.x, head.y, PIN.head, mapInk('marker-fill'), ring, MARKER.roleRing);
		if (look.selected) circle(g, head.x, head.y, PIN.head + 3.5, null, select, 2);
		glyph(g, look.glyph, head.x, head.y, PIN.glyph, mapInk('label-ink'));
		if (look.decision) circle(g, head.x + 12, head.y - 12, MARKER.dot, mapInk('decision'), mapInk('casing'), 1.5);
		return finish(g, W, H, tip);
	});
}

/** A small neutral dot (junctions, reads off a camera): radius, ring, optional role fill. */
export function dotImage(look: { r: number; role?: 'marker' | 'alert'; filled?: boolean; selected?: boolean }): MapImage | null {
	const key = `d|${look.r}|${look.role ?? 'marker'}|${look.filled ? 1 : 0}|${look.selected ? 1 : 0}`;
	return memo(key, () => {
		const B = Math.ceil(2 * look.r + 10);
		const g = canvas2d(B, B);
		if (!g) return null;
		const c = B / 2;
		const ink = look.selected ? mapInk('select') : look.role === 'alert' ? mapInk('alert') : mapInk('marker');
		circle(g, c, c, look.r, look.filled ? ink : mapInk('marker-fill'), look.filled ? mapInk('casing') : ink, 1.5);
		return finish(g, B, B, { x: c, y: c });
	});
}

/** A feed anomaly: a small neutral diamond up-right of its point (prototype ui-views.js). */
export function diamondImage(selected = false): MapImage | null {
	return memo(`a|${selected ? 1 : 0}`, () => {
		const B = 24;
		const g = canvas2d(B, B);
		if (!g) return null;
		const c = B / 2;
		g.save();
		g.translate(c + 8, c - 8);
		g.rotate(Math.PI / 4);
		roundRect(g, -4, -4, 8, 8, 1.5);
		g.fillStyle = mapInk('marker-fill');
		g.fill();
		g.lineWidth = 1.5;
		g.strokeStyle = selected ? mapInk('select') : mapInk('marker');
		g.stroke();
		g.restore();
		return finish(g, B, B, { x: c, y: c });
	});
}

/**
 * The pursuit heading's arrow head pointing UP (north): rotate it by −bearing
 * with a north aligned axis. (The selected track's direction arrows are
 * draped chevrons instead: trackArrows.)
 */
export function arrowImage(kind: 'heading'): MapImage | null {
	return memo(`r|${kind}`, () => {
		const B = 18;
		const g = canvas2d(B, B);
		if (!g) return null;
		const c = B / 2;
		g.beginPath();
		g.moveTo(c - 5.5, c + 6);
		g.lineTo(c, c - 6);
		g.lineTo(c + 5.5, c + 6);
		g.closePath();
		g.fillStyle = mapInk('alert');
		g.fill();
		g.lineWidth = 1.2;
		g.strokeStyle = mapInk('casing');
		g.stroke();
		return finish(g, B, B, { x: c, y: c });
	});
}

/** One label run as painted: text, face, ink. */
interface Run {
	text: string;
	face: 'ui' | 'id';
	dim: boolean;
}

function runsOf(parts: readonly SvgLabelPart[]): Run[] {
	return svgLabelParts(parts).map((r, i) => ({
		text: (i > 0 ? ' ' : '') + r.text,
		face: r.face === 'mono' ? 'id' : 'ui',
		// times recede to the second ink (prototype .mlabel .tt)
		dim: r.kind === 'time',
	}));
}

/** The text of a label as it reads (tests, tooltips, the hover list). */
export function labelText(parts: readonly SvgLabelPart[]): string {
	return runsOf(parts)
		.map((r) => r.text)
		.join('');
}

/**
 * A map label on its plate: identifiers mono, times and words Inter (the
 * formatter decides which, svgLabelParts), a lock glyph after a masked mark.
 */
export function labelImage(parts: readonly SvgLabelPart[], opts: { lock?: boolean } = {}): MapImage | null {
	const runs = runsOf(parts);
	if (!runs.length) return null;
	const key = `l|${runs.map((r) => `${r.face}${r.dim ? 'd' : ''}:${r.text}`).join('\u0001')}|${opts.lock ? 1 : 0}`;
	return memo(key, () => {
		const probe = canvas2d(4, 4);
		if (!probe) return null;
		const faces = mapFaces();
		const fontOf = (r: Run) => `${LABEL.size}px ${r.face === 'id' ? faces.id : faces.ui}`;
		let textW = 0;
		for (const r of runs) {
			probe.font = fontOf(r);
			textW += probe.measureText(r.text).width;
		}
		const lockW = opts.lock ? LABEL.lock + 4 : 0;
		const W = Math.ceil(textW + 2 * LABEL.padX + lockW);
		const H = LABEL.h;
		const g = canvas2d(W, H);
		if (!g) return null;
		roundRect(g, 0, 0, W, H, LABEL.radius);
		g.fillStyle = mapInk('label-bg');
		g.fill();
		g.textBaseline = 'alphabetic';
		g.textAlign = 'left';
		let x = LABEL.padX;
		const inkBright = mapInk('label-ink');
		const inkDim = mapInk('marker');
		for (const r of runs) {
			g.font = fontOf(r);
			g.fillStyle = r.dim ? inkDim : inkBright;
			g.fillText(r.text, x, H - 6);
			x += g.measureText(r.text).width;
		}
		if (opts.lock) glyph(g, 'lock', x + 4 + LABEL.lock / 2, H / 2, LABEL.lock, inkDim);
		return finish(g, W, H, { x: W / 2, y: H / 2 });
	});
}

/** Geographic bearing (deg, clockwise from north) from a to b. */
export function bearingDeg(a: readonly [number, number], b: readonly [number, number]): number {
	const k = Math.cos((((a[1] + b[1]) / 2) * Math.PI) / 180);
	const deg = (Math.atan2((b[0] - a[0]) * k, b[1] - a[1]) * 180) / Math.PI;
	return (deg + 360) % 360;
}

/** A point `metres` from (lon, lat) along `bearing` (deg). */
export function offsetPoint(lon: number, lat: number, bearing: number, metres: number): [number, number] {
	const r = (bearing * Math.PI) / 180;
	return [lon + (metres * Math.sin(r)) / (111_320 * Math.cos((lat * Math.PI) / 180)), lat + (metres * Math.cos(r)) / 110_540];
}

/** Ground distance (m) between two lon/lat points (equirectangular; city scale). */
export function groundMetres(a: readonly [number, number], b: readonly [number, number]): number {
	const k = Math.cos((((a[1] + b[1]) / 2) * Math.PI) / 180);
	return Math.hypot((b[0] - a[0]) * 111_320 * k, (b[1] - a[1]) * 110_540);
}

/**
 * The selected track's direction arrows (SPEC §5.3; prototype shots 01, 10):
 * one on every span drawn at least `minPx` long whose midpoint is on screen,
 * a chevron of two `armPx` arms pointing along the span, DRAPED on the same
 * surface as the track (terrain or the 3D tiles) in the alert ink over a
 * casing, the width of the track's core.
 */
export const TRACK_ARROW = Object.freeze({ minPx: 60, armPx: 11, halfAngleDeg: 50, width: 6, core: 3 });

/** One direction arrow: its id is the span's own geometry and the drawn scale. */
export interface TrackArrow {
	/** `lon0,lat0>lon1,lat1@step`: a span that moves (a read in, a read out, another window) is a NEW arrow. */
	id: string;
	bearing: number;
	/** Where it stands (the span's midpoint) and its chevron, left arm → tip → right arm. */
	mid: [number, number];
	chevron: [number, number][];
}

/**
 * The direction arrows of a drawn track, PURE: `coords` the track's lon/lat
 * points in time order, `project` lon/lat → canvas px (null off the globe).
 * Each arrow is keyed by its span's endpoints (6 decimals, ~0.1 m) plus the
 * scale step its arms were sized for, so the caller can keep an arrow whose
 * key it still wants, drop every other, and never move one: a span that
 * changes is a different key. The arms are sized in metres from the span's
 * own scale (its ground length over its drawn length) in quarter-octave
 * steps, so a zoom past a step re-sizes them and a small one does not.
 */
export function trackArrows(
	coords: ReadonlyArray<readonly [number, number]>,
	project: (lon: number, lat: number) => { x: number; y: number } | null | undefined,
	view: { width: number; height: number },
	opts: { minPx?: number; armPx?: number } = {},
): TrackArrow[] {
	const minPx = opts.minPx ?? TRACK_ARROW.minPx;
	const armPx = opts.armPx ?? TRACK_ARROW.armPx;
	const out = new Map<string, TrackArrow>();
	const pts = coords.map(([lon, lat]) => project(lon, lat) ?? null);
	const fix = (n: number) => n.toFixed(6);
	for (let i = 1; i < coords.length; i++) {
		const a = pts[i - 1];
		const b = pts[i];
		if (!a || !b || !Number.isFinite(a.x + a.y + b.x + b.y)) continue;
		const px = Math.hypot(b.x - a.x, b.y - a.y);
		const mx = (a.x + b.x) / 2;
		const my = (a.y + b.y) / 2;
		if (px < minPx || mx < 0 || my < 0 || mx > view.width || my > view.height) continue;
		const p0 = coords[i - 1];
		const p1 = coords[i];
		const metres = groundMetres(p0, p1);
		if (!(metres > 0)) continue;
		const step = Math.round(Math.log2((armPx * metres) / px) * 4) / 4;
		const arm = 2 ** step;
		const bearing = bearingDeg(p0, p1);
		const mid: [number, number] = [(p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2];
		// the tip a little ahead of the midpoint, so the chevron centres on it
		const tip = offsetPoint(mid[0], mid[1], bearing, arm * 0.4);
		const left = offsetPoint(tip[0], tip[1], bearing + 180 - TRACK_ARROW.halfAngleDeg, arm);
		const right = offsetPoint(tip[0], tip[1], bearing + 180 + TRACK_ARROW.halfAngleDeg, arm);
		const id = `${fix(p0[0])},${fix(p0[1])}>${fix(p1[0])},${fix(p1[1])}@${step}`;
		out.set(id, { id, bearing, mid, chevron: [left, tip, right] });
	}
	return [...out.values()];
}

/**
 * The local north as a world axis at (lon, lat): a billboard aligned to it
 * and rotated by −bearing points along that bearing whatever the camera's
 * heading (direction arrows). Undefined on a build that cannot construct a
 * Cartesian3 (tests): the arrow then points screen-up, rotated.
 */
export function northAxis(cesium: CesiumGlobal, lon: number, lat: number): unknown {
	if (typeof cesium.Cartesian3 !== 'function') return undefined;
	const a = cesium.Cartesian3.fromDegrees(lon, lat, 0) as { x: number; y: number; z: number };
	const b = cesium.Cartesian3.fromDegrees(lon, lat + 0.001, 0) as { x: number; y: number; z: number };
	const d = { x: b.x - a.x, y: b.y - a.y, z: b.z - a.z };
	const n = Math.hypot(d.x, d.y, d.z);
	if (!(n > 0)) return undefined;
	return new cesium.Cartesian3(d.x / n, d.y / n, d.z / n);
}

/** Billboard graphics for a painted image, clamped (never buried in the 3D city). */
export function imageBillboard(cesium: CesiumGlobal, img: MapImage | null, fallback: { w: number; h: number }, extra: Record<string, unknown> = {}): Record<string, unknown> {
	const w = img?.w ?? fallback.w;
	const h = img?.h ?? fallback.h;
	const offset = img?.offset ?? { x: 0, y: 0 };
	return clampedBillboard(cesium, {
		...(img ? { image: img.url } : {}),
		width: w,
		height: h,
		...(offset.x || offset.y ? { pixelOffset: typeof cesium.Cartesian2 === 'function' ? new cesium.Cartesian2(offset.x, offset.y) : offset } : {}),
		...extra,
	});
}

// ── meta: what a v2 marker is (read by the canvas's v2 pass) ──────────────

/** How a marker is drawn (the pass repaints it from this when the view changes). */
export type MarkerShape = 'disc' | 'square' | 'pin' | 'dot' | 'diamond' | 'none';

export interface MarkerMeta {
	urn: string | null;
	kind: string;
	glyph: IconName;
	shape: MarkerShape;
	role?: MarkerLook['role'];
	size?: number;
	/** Dot radius (shape 'dot'). */
	r?: number;
	/** The object's own time (window fading). */
	t?: number | null;
	/** Takes part in clustering (21 px discs). */
	cluster?: boolean;
	/** On the selection's track: leads its cluster. */
	lead?: boolean;
	/** The marker's label; when it shows: 'always', 'selected' (its object or a parent selected), or 'hover'. */
	label?: readonly SvgLabelPart[] | null;
	labelWhen?: 'always' | 'selected' | 'hover';
	/** The label also shows when this URN is selected (a read's vehicle). */
	labelWith?: string | null;
	labelLock?: boolean;
	labelPrefer?: readonly ('r' | 'l' | 'b' | 't' | 'br' | 'tr' | 'bl' | 'tl')[];
	labelPriority?: number;
	/** Dimmed regardless of the view (a likely-passed choke). */
	passed?: boolean;
	/** Where an operator clicks it, relative to its position (the pin's head). */
	click?: { x: number; y: number };
	/** Radius of the drawn mark (label keep-out). */
	radius?: number;
}

const META = new WeakMap<object, MarkerMeta>();

/** Tag a v2 marker entity (call right after viewer.entities.add). */
export function tagMarker<E extends object>(entity: E, meta: MarkerMeta): E {
	META.set(entity, meta);
	return entity;
}

/** A v2 marker's meta, or null for anything else. */
export function markerMeta(entity: object | null | undefined): MarkerMeta | null {
	return entity ? (META.get(entity) ?? null) : null;
}

/** A drawn track (the selected vehicle's reads): the canvas adds its direction arrows. */
export interface TrackMeta {
	urn: string;
	coords: ReadonlyArray<readonly [number, number]>;
}

const TRACKS = new WeakMap<object, TrackMeta>();

/** Tag a v2 track polyline (its direction arrows are placed on camera-move end). */
export function tagTrack<E extends object>(entity: E, meta: TrackMeta): E {
	TRACKS.set(entity, meta);
	return entity;
}

/** A v2 track's meta, or null. */
export function trackMeta(entity: object | null | undefined): TrackMeta | null {
	return entity ? (TRACKS.get(entity) ?? null) : null;
}

/** The image a meta draws in a given state (the pass and the layers share it). */
export function imageFor(meta: MarkerMeta, state: { selected?: boolean; decision?: boolean; count?: number; hover?: boolean } = {}): MapImage | null {
	switch (meta.shape) {
		case 'pin':
			return pinImage({ glyph: meta.glyph, selected: state.selected, decision: state.decision, alert: meta.role !== 'marker' });
		case 'dot':
			return dotImage({ r: meta.r ?? 4.5, role: meta.role === 'alert' ? 'alert' : 'marker', filled: meta.role === 'alert', selected: state.selected });
		case 'diamond':
			return diamondImage(state.selected);
		case 'none':
			return null;
		default:
			return markerImage({
				glyph: meta.glyph,
				role: meta.role,
				shape: meta.shape === 'square' ? 'square' : 'disc',
				size: meta.size,
				selected: state.selected,
				hover: state.hover,
				decision: state.decision,
				count: state.count,
			});
	}
}

/** The fallback box of a meta's image (no DOM). */
export function boxOf(meta: MarkerMeta): { w: number; h: number } {
	switch (meta.shape) {
		case 'pin':
			return { w: -PIN.dx + 28, h: -PIN.dy + 28 };
		case 'dot':
			return { w: Math.ceil(2 * (meta.r ?? 4.5) + 10), h: Math.ceil(2 * (meta.r ?? 4.5) + 10) };
		case 'diamond':
			return { w: 24, h: 24 };
		default:
			return { w: Math.max(MARKER.box, (meta.size ?? MARKER.disc) + 18), h: Math.max(MARKER.box, (meta.size ?? MARKER.disc) + 18) };
	}
}

/**
 * A v2 marker's billboard graphics (initial state: nothing selected), its
 * meta tag applied by the caller. `extra` carries Cesium options such as a
 * time-varying position.
 */
export function markerBillboard(cesium: CesiumGlobal, meta: MarkerMeta, state: Parameters<typeof imageFor>[1] = {}, extra: Record<string, unknown> = {}): Record<string, unknown> {
	return imageBillboard(cesium, imageFor(meta, state), boxOf(meta), extra);
}
