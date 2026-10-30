/**
 * The shared tile cache of every MapThumb (V3-SPEC §4.6) — one LRU of GRADED tiles, so fifteen thumbs of
 * one city fetch each tile once, and a fetch queue of at most four requests in flight (the OSM tile usage
 * policy; the browser's HTTP cache does the rest).
 *
 * Source: the keyless OpenStreetMap raster the God's-eye canvas already uses (layers/basemap.ts
 * OSM_TILE_URL) — no new third-party host. Tiles are fetched with CORS (the OSM tile servers answer
 * `Access-Control-Allow-Origin: *`) so they can be graded in the browser, no server step:
 *
 *   1. the deck's own "Dark" re-grade (basemap.ts DARK_REGRADE: brightness, contrast, saturation), so a
 *      thumb starts from what the live map shows;
 *   2. "Sajag night" (redesign/v3/prototype/tools/grade.py, the grade the approved prototype was made
 *      with): luminance remapped onto the night ramp, water / parks / major roads recoloured into their
 *      night tints — every hue neutralised, so an OSM red or orange symbol can never read as an alert or
 *      a decision. `day` is the same with the day ramp (public pages, P6).
 *
 * A tile that cannot load resolves to null: the thumb keeps its night placeholder (and draws the deck's
 * own road network on it when it has one — never a blank, never an error colour).
 */
import { DARK_REGRADE, OSM_TILE_URL } from '$lib/gods-eye/layers/basemap';
import { MAP_PALETTE } from '../tokens';
import { SatelliteSource, browserFetchJson, browserFetchTile, sessionStore, type SatPriority } from './satellite';

export type Grade = 'night' | 'day';

type RGB = readonly [number, number, number];
const hx = (h: string): RGB => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
const pair = (p: readonly [string, string]): [RGB, RGB] => [hx(p[0]), hx(p[1])];

/** grade.py's palette, from the tokens (land / water / park / road: [dark end, light end]). */
const PALETTE = Object.fromEntries(
	(['night', 'day'] as const).map((g) => {
		const m = MAP_PALETTE[g];
		return [g, { land: pair(m.land), water: pair(m.water), park: pair(m.park), road: pair(m.road), lo: m.lo, hi: m.hi, gamma: m.gamma }];
	}),
) as Record<Grade, { land: [RGB, RGB]; water: [RGB, RGB]; park: [RGB, RGB]; road: [RGB, RGB]; lo: number; hi: number; gamma: number }>;

/**
 * Grade RGBA pixels in place (exported pure for tests/home.unit.mjs): the deck's dark re-grade, then the
 * Sajag grade with its water / park / road masks (each mask softened by a 1-2-1 blur, as grade.py's 0.6 px
 * Gaussian does).
 */
export function gradePixels(px: Uint8ClampedArray, w: number, h: number, grade: Grade = 'night'): void {
	const p = PALETTE[grade];
	const { brightness, contrast, saturation } = DARK_REGRADE;
	const n = w * h;
	const R = new Float32Array(n);
	const G = new Float32Array(n);
	const B = new Float32Array(n);
	const water = new Float32Array(n);
	const park = new Float32Array(n);
	const road = new Float32Array(n);
	for (let i = 0; i < n; i++) {
		let r = px[i * 4] / 255;
		let g = px[i * 4 + 1] / 255;
		let b = px[i * 4 + 2] / 255;
		// the deck's dark re-grade (Cesium's imagery order: brightness, contrast, saturation)
		r = (r * brightness - 0.5) * contrast + 0.5;
		g = (g * brightness - 0.5) * contrast + 0.5;
		b = (b * brightness - 0.5) * contrast + 0.5;
		const l = 0.2125 * r + 0.7154 * g + 0.0721 * b;
		r = Math.min(1, Math.max(0, l + (r - l) * saturation)) * 255;
		g = Math.min(1, Math.max(0, l + (g - l) * saturation)) * 255;
		b = Math.min(1, Math.max(0, l + (b - l) * saturation)) * 255;
		R[i] = r;
		G[i] = g;
		B[i] = b;
		water[i] = b - r > 6 && g - r > 6 ? 1 : 0;
		park[i] = g - r > 8 && g - b > 6 ? 1 : 0;
		road[i] = r - b > 18 && r - g > 5 && !(r - g > 25 && r - b > 25) ? 1 : 0;
	}
	const soften = (m: Float32Array) => {
		const t = new Float32Array(n);
		for (let y = 0; y < h; y++)
			for (let x = 0; x < w; x++) {
				const i = y * w + x;
				t[i] = (m[x > 0 ? i - 1 : i] + 2 * m[i] + m[x < w - 1 ? i + 1 : i]) / 4;
			}
		for (let y = 0; y < h; y++)
			for (let x = 0; x < w; x++) {
				const i = y * w + x;
				m[i] = (t[y > 0 ? i - w : i] + 2 * t[i] + t[y < h - 1 ? i + w : i]) / 4;
			}
	};
	soften(water);
	soften(park);
	soften(road);
	const span = p.hi - p.lo;
	for (let i = 0; i < n; i++) {
		const L = 0.3 * R[i] + 0.59 * G[i] + 0.11 * B[i];
		const t = Math.min(1, Math.max(0, (L - p.lo) / span)) ** p.gamma;
		const mix = (pair: [RGB, RGB], c: number) => pair[0][c] * (1 - t) + pair[1][c] * t;
		for (let c = 0; c < 3; c++) {
			let v = mix(p.land, c);
			v = v * (1 - water[i]) + mix(p.water, c) * water[i];
			v = v * (1 - park[i]) + mix(p.park, c) * park[i];
			v = v * (1 - road[i]) + mix(p.road, c) * road[i];
			px[i * 4 + c] = v;
		}
		px[i * 4 + 3] = 255;
	}
}

/** The tile URL (the canvas's own source; z/x/y only — integers, never caller text). */
export function tileUrl(z: number, x: number, y: number): string {
	return OSM_TILE_URL.replace('{z}', String(Math.trunc(z))).replace('{x}', String(Math.trunc(x))).replace('{y}', String(Math.trunc(y)));
}

const MAX_TILES = 192;
const MAX_IN_FLIGHT = 4;
const cache = new Map<string, Promise<CanvasImageSource | null>>();
let inFlight = 0;
const queue: (() => void)[] = [];

/** A slot of the shared queue; `first` jumps the waiting line (the night tiles laid under a slow satellite picture). */
function slot(first = false): Promise<void> {
	if (inFlight < MAX_IN_FLIGHT) {
		inFlight++;
		return Promise.resolve();
	}
	return new Promise((resolve) => {
		const go = () => (inFlight++, resolve());
		if (first) queue.unshift(go);
		else queue.push(go);
	});
}

function release(): void {
	inFlight--;
	queue.shift()?.();
}

/**
 * Satellite requests hold at most SAT_SHARE of the four slots, so a slow imagery source can never starve the night
 * tiles a thumb falls back to (one slot always turns over). Still ≤ 4 in flight in all.
 */
const SAT_SHARE = 3;
let satInFlight = 0;
const satQueue: (() => void)[] = [];

async function satSlot(): Promise<void> {
	while (satInFlight >= SAT_SHARE) await new Promise<void>((r) => satQueue.push(r));
	satInFlight++;
	await slot();
}

function satRelease(): void {
	release();
	satInFlight--;
	satQueue.shift()?.();
}

async function loadTile(z: number, x: number, y: number, grade: Grade, first = false): Promise<HTMLCanvasElement | null> {
	await slot(first);
	try {
		const img = new Image();
		img.crossOrigin = 'anonymous';
		img.decoding = 'async';
		img.referrerPolicy = 'strict-origin-when-cross-origin';
		img.src = tileUrl(z, x, y);
		await img.decode();
		const c = document.createElement('canvas');
		c.width = img.naturalWidth || 256;
		c.height = img.naturalHeight || 256;
		const g = c.getContext('2d', { willReadFrequently: true });
		if (!g) return null;
		g.drawImage(img, 0, 0);
		const data = g.getImageData(0, 0, c.width, c.height);
		gradePixels(data.data, c.width, c.height, grade);
		g.putImageData(data, 0, 0);
		return c;
	} catch {
		return null;
	} finally {
		release();
	}
}

/** Insert into the shared LRU (night and satellite tiles together); a failed tile is not kept. */
function remember(key: string, hit: Promise<CanvasImageSource | null>): Promise<CanvasImageSource | null> {
	cache.set(key, hit);
	// a failed tile is not cached (a later thumb may try again once the network is back)
	void hit.then((c) => {
		if (!c && cache.get(key) === hit) cache.delete(key);
	});
	while (cache.size > MAX_TILES) {
		const oldest = cache.keys().next().value;
		if (oldest === undefined) break;
		cache.delete(oldest);
	}
	return hit;
}

function recall(key: string): Promise<CanvasImageSource | null> | undefined {
	const hit = cache.get(key);
	if (hit) {
		cache.delete(key);
		cache.set(key, hit);
	}
	return hit;
}

/** One graded tile (shared; least-recently-used tiles leave the cache past 192). */
export function gradedTile(z: number, x: number, y: number, grade: Grade, first = false): Promise<CanvasImageSource | null> {
	const key = `${grade}:${z}/${x}/${y}`;
	return recall(key) ?? remember(key, loadTile(z, x, y, grade, first));
}

/**
 * The satellite source every thumb shares (satellite.ts holds its quota rules): its requests go through the SAME
 * queue as the night tiles, so a page never has more than four tile requests in flight in all.
 */
export const satellite = new SatelliteSource({
	fetchJson: browserFetchJson,
	fetchTile: browserFetchTile,
	limiter: { acquire: satSlot, release: satRelease },
	store: sessionStore(),
});

/**
 * One natural-colour satellite tile (ungraded), from the same LRU; null when satellite is off or there is no imagery.
 * A card asks with priority 'card' (it yields the hero reserve, satellite.ts); a null is never cached, so the same tile
 * can still come for a hero.
 */
export function satelliteTile(z: number, x: number, y: number, priority: SatPriority = 'hero'): Promise<CanvasImageSource | null> {
	const key = `sat:${z}/${x}/${y}`;
	return recall(key) ?? remember(key, satellite.tile(z, x, y, priority));
}

/** How many tiles the cache holds (tests and the gallery). */
export const tileCacheSize = () => cache.size;
