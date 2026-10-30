/**
 * Web Mercator for MapThumb (V3-SPEC §4.6) — pure functions, the same math OSM's tiles are cut with, so
 * an overlay drawn from lon/lat sits exactly on the raster under it.
 *
 *   world pixel at zoom z:  x = (lon + 180) / 360 · 256 · 2^z
 *                           y = (1 − ln(tan φ + sec φ) / π) / 2 · 256 · 2^z
 */
export type LonLat = readonly [number, number];
export type BBox = readonly [number, number, number, number]; // west, south, east, north

export const TILE = 256;
export const MIN_ZOOM = 10;
export const MAX_ZOOM = 17;

/** Lon/lat → world pixels at zoom z. */
export function project(p: LonLat, z: number): [number, number] {
	const scale = TILE * 2 ** z;
	const lat = Math.max(-85.0511, Math.min(85.0511, p[1]));
	const phi = (lat * Math.PI) / 180;
	return [((p[0] + 180) / 360) * scale, ((1 - Math.log(Math.tan(phi) + 1 / Math.cos(phi)) / Math.PI) / 2) * scale];
}

/** World pixels at zoom z → lon/lat (the inverse of project). */
export function unproject(x: number, y: number, z: number): LonLat {
	const scale = TILE * 2 ** z;
	const lon = (x / scale) * 360 - 180;
	const lat = (Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / scale))) * 180) / Math.PI;
	return [lon, lat];
}

/** The bbox of a set of points (null when there are none). */
export function bboxOf(points: readonly LonLat[]): BBox | null {
	const ok = points.filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1]));
	if (!ok.length) return null;
	let w = Infinity,
		s = Infinity,
		e = -Infinity,
		n = -Infinity;
	for (const [lon, lat] of ok) {
		w = Math.min(w, lon);
		e = Math.max(e, lon);
		s = Math.min(s, lat);
		n = Math.max(n, lat);
	}
	return [w, s, e, n];
}

/** The largest zoom (≤ maxZoom) at which `bbox` fits in w×h with `pad` px on every side. */
export function fitZoom(bbox: BBox, w: number, h: number, pad = 24, maxZoom = 16): number {
	for (let z = maxZoom; z > MIN_ZOOM; z--) {
		const a = project([bbox[0], bbox[3]], z);
		const b = project([bbox[2], bbox[1]], z);
		if (b[0] - a[0] <= Math.max(1, w - 2 * pad) && b[1] - a[1] <= Math.max(1, h - 2 * pad)) return z;
	}
	return MIN_ZOOM;
}

export interface TileRef {
	x: number;
	y: number;
	z: number;
	/** Where the tile's top-left corner lands in the box (px). */
	dx: number;
	dy: number;
}

/** The tiles covering the world-pixel window [x0, x0+w) × [y0, y0+h) at zoom z. */
export function tilesFor(x0: number, y0: number, w: number, h: number, z: number): TileRef[] {
	const n = 2 ** z;
	const out: TileRef[] = [];
	const tx0 = Math.floor(x0 / TILE);
	const ty0 = Math.max(0, Math.floor(y0 / TILE));
	const tx1 = Math.floor((x0 + w - 1) / TILE);
	const ty1 = Math.min(n - 1, Math.floor((y0 + h - 1) / TILE));
	for (let y = ty0; y <= ty1; y++) for (let x = tx0; x <= tx1; x++) out.push({ x: ((x % n) + n) % n, y, z, dx: x * TILE - x0, dy: y * TILE - y0 });
	return out;
}

export interface Framing {
	z: number;
	/** World pixel of the box's top-left corner. */
	x0: number;
	y0: number;
	tiles: TileRef[];
}

/**
 * Frame a w×h box: around `center` at `zoom`, or fitted to `bbox`; then zoomed out until it needs at most
 * `maxTiles` tiles (the "at most 6 tiles per thumb" rule). `focus` places the subject inside the box
 * (0.5, 0.5 = centred; the hero puts it right of its copy).
 */
export function frame(
	opts: { center?: LonLat | null; zoom?: number | null; bbox?: BBox | null; focus?: readonly [number, number]; maxTiles?: number; pad?: number; maxZoom?: number },
	w: number,
	h: number,
): Framing | null {
	if (!(w > 0 && h > 0)) return null;
	const focus = opts.focus ?? [0.5, 0.5];
	const maxTiles = opts.maxTiles ?? 6;
	let center: LonLat | null = opts.center ?? null;
	let z = opts.zoom ?? 15;
	if (opts.bbox) {
		const [west, south, east, north] = opts.bbox;
		center = [(west + east) / 2, (south + north) / 2];
		// the subject is framed in the part of the box the focus leaves free
		const fw = Math.min(focus[0], 1 - focus[0]) * 2 * w;
		const fh = Math.min(focus[1], 1 - focus[1]) * 2 * h;
		z = fitZoom(opts.bbox, Math.max(fw, 80), Math.max(fh, 60), opts.pad ?? 24, opts.maxZoom ?? 16);
		// centre the bbox's projected middle (not the lon/lat middle: Mercator stretches latitude)
		const a = project([west, north], z);
		const b = project([east, south], z);
		let cx = (a[0] + b[0]) / 2;
		let cy = (a[1] + b[1]) / 2;
		for (;;) {
			const x0 = cx - w * focus[0];
			const y0 = cy - h * focus[1];
			const tiles = tilesFor(x0, y0, w, h, z);
			if (tiles.length <= maxTiles || z <= MIN_ZOOM) return { z, x0, y0, tiles };
			// zoom out one step: every world pixel halves
			z--;
			cx /= 2;
			cy /= 2;
		}
	}
	if (!center) return null;
	for (; z >= MIN_ZOOM; z--) {
		const [cx, cy] = project(center, z);
		const x0 = cx - w * focus[0];
		const y0 = cy - h * focus[1];
		const tiles = tilesFor(x0, y0, w, h, z);
		if (tiles.length <= maxTiles || z === MIN_ZOOM) return { z, x0, y0, tiles };
	}
	return null;
}

/** A lon/lat in the framed box's pixels. */
export function toBox(p: LonLat, f: Framing): [number, number] {
	const [x, y] = project(p, f.z);
	return [x - f.x0, y - f.y0];
}

/** The lon/lat window a framed w×h box shows (west, south, east, north) — what the imagery credit is looked up for. */
export function framedBBox(f: Framing, w: number, h: number): BBox {
	const nw = unproject(f.x0, f.y0, f.z);
	const se = unproject(f.x0 + w, f.y0 + h, f.z);
	return [nw[0], se[1], se[0], nw[1]];
}
