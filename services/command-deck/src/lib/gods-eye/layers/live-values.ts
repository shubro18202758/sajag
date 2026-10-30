/**
 * livevalues layer — the city's live readings AT their places, each with its value and its provenance in the label
 * (on by default), and a pulse on what is fresh:
 *
 *   BMC storm-water pumps           GET /api/hydro/hydro/pumps          60 s   "Haji Ali · pumps 7/8 (emulated)"
 *   the sea tide (Apollo Bunder)    GET /api/hydro/hydro/tide          120 s   "Apollo Bunder tide station · 3.04 m falling (modelled)"
 *   heat at the IMD observatories   GET /api/cityfeeds/feeds/heat      600 s   "Santacruz · 29.9 °C (modelled)"
 *   CWC river gauges in the region  GET /api/cityfeeds/feeds/river     900 s   "… · 4.12 m (live gauge)"
 *   NASA FIRMS heat spots (48 h)    GET /api/cityfeeds/feeds/fires     600 s   "Satellite heat spot · 3 h ago (live)"
 *   USGS earthquakes near the city  GET /api/cityfeeds/feeds/quakes    900 s   only within the region box
 *   fresh situations                the city registry (osint_event, event), every 3 s: a title label and a pulsing
 *                                   ring while the item is under 20 minutes old (its own time, never a timer's)
 *
 * Every value is the feed's own; a feed that does not answer draws nothing and says so in the hint. Colour only for
 * meaning on the small disc (green ok, amber watch, red alert; neutral otherwise) — the label carries the value and
 * the provenance word, so the meaning never rides on colour alone. Primitives only (one BillboardCollection, one
 * LabelCollection, one pulse BillboardCollection); every label joins the map's one label budget (live-marks).
 *
 * No pick: the readings' own sheets open from the City chips; a situation's marker belongs to its own layer.
 */

import { ops } from '$lib/ops/store.svelte';
import { t } from '$lib/i18n/strings';
import { aiJson } from '$lib/ai/client';
import { CITY_BBOX, inBox, landmarkLonLat, landmarkName } from '$lib/city';
import { cityRegistry } from '../entities/registry.svelte';
import { displayText } from '../plates';
import type { GodsEyeLayer, GodsEyeLayerContext, GodsEyeLayerInstance } from '../registry';
import { canvasFont, cssVar } from '../theme';
import { agoShort, cityGround, declutterFor, glyphImage, labelBox, ringImage, type DeclutterItem, type Loose, primitivesOk } from '../hud/map/live-marks';
import { liveClock } from '../hud/map/live-clock';
import '../hud/map/packs.livemap';

export const LIVE_VALUES_PICK_PREFIX = 'lv:';

/** An item is fresh (it pulses) while its own time is under this old. */
export const FRESH_MS = 20 * 60_000;

export type Tone = 'ok' | 'warn' | 'alert' | 'neutral';

export interface LiveRow {
	key: string;
	lon: number;
	lat: number;
	text: string;
	tone: Tone;
	/** Declutter priority (live-marks: 0 alert · 1 landmark · 2 live value · 3 road …). */
	priority: number;
	maxAlt: number;
	/** Epoch ms of the item's own time; a fresh one pulses. */
	t?: number | null;
}

/** The region the regional feeds (rivers, quakes) are drawn in: the city box and ~40 km round it. */
const REGION_MARGIN_DEG = 0.4;

const SOURCES = {
	pumps: { path: '/api/hydro/hydro/pumps', everyMs: 60_000 },
	tide: { path: '/api/hydro/hydro/tide', everyMs: 120_000 },
	heat: { path: '/api/cityfeeds/feeds/heat', everyMs: 600_000 },
	river: { path: '/api/cityfeeds/feeds/river', everyMs: 900_000 },
	fires: { path: '/api/cityfeeds/feeds/fires', everyMs: 600_000 },
	quakes: { path: '/api/cityfeeds/feeds/quakes', everyMs: 900_000 },
} as const;
type SourceId = keyof typeof SOURCES;

/** The tide station's landmark (cities/<id>/landmarks.json): Apollo Bunder, Mumbai harbour. */
export const TIDE_PLACE = 'apollo_bunder';
/** The tide label's place: the pack's name for the station in the UI language ("Apollo Bunder"), never the long form. */
function tidePlaceName(lang: string): string {
	const n = landmarkName(TIDE_PLACE, lang);
	return n === TIDE_PLACE ? landmarkName('garden_reach', lang) : n.replace(/\s+(tide station|ज्वार स्टेशन|भरती केंद्र)$/i, '');
}

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const str = (v: unknown): string => (typeof v === 'string' ? v : '');
const clip = (s: string, n = 34) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);
/** "Haji Ali storm-water pumping station" → "Haji Ali" (the label names the place; the word says what). */
export function shortPlace(name: string): string {
	return clip(name.replace(/\s+((drainage|storm[- ]?water|sewage)\s+)?pumping station$/i, '').replace(/\s+\(\s*bmc\s*\)$/i, '').replace(/\s*\([^)]*\)\s*$/, '').trim(), 28);
}

/** Pure: one source's answer → rows (exported for tests). */
export function rowsOf(source: SourceId, body: Loose, lang: string, now = Date.now()): LiveRow[] {
	const L = (k: string, ...a: unknown[]) => t(lang, k, ...a);
	const out: LiveRow[] = [];
	if (source === 'pumps') {
		for (const st of Array.isArray(body?.stations) ? body.stations : []) {
			const lon = num(st?.lon), lat = num(st?.lat);
			const total = num(st?.pumps_total), up = num(st?.pumps_available);
			if (lon == null || lat == null || total == null || up == null) continue;
			const a = total ? up / total : 0;
			out.push({ key: `pump:${str(st.id)}`, lon, lat, text: L('lm_pumps', shortPlace(str(st.name)), up, total), tone: a >= 0.75 ? 'ok' : a >= 0.5 ? 'warn' : 'alert', priority: a < 0.5 ? 0.6 : 2.4, maxAlt: 14_000 });
		}
	} else if (source === 'tide') {
		const lvl = num(body?.now?.level_m);
		const at = landmarkLonLat(TIDE_PLACE) ?? landmarkLonLat('garden_reach');
		if (lvl != null && at) {
			const dir = body?.now?.gate_closed ? L('lm_gates_shut') : body?.now?.rising ? L('lm_rising') : L('lm_falling');
			const gate = num(body?.gate_close_level_m) ?? 5;
			out.push({ key: `tide:${TIDE_PLACE}`, lon: at[0], lat: at[1], text: L('lm_tide', tidePlaceName(lang), lvl.toFixed(2), dir), tone: body?.now?.gate_closed ? 'alert' : lvl > gate - 0.5 ? 'warn' : 'neutral', priority: body?.now?.gate_closed ? 0.4 : 2, maxAlt: 30_000 });
		}
	} else if (source === 'heat') {
		for (const p of Array.isArray(body?.points) ? body.points : []) {
			const lon = num(p?.lon), lat = num(p?.lat), temp = num(p?.now?.temp);
			if (lon == null || lat == null || temp == null) continue;
			const band = str(p?.now?.band);
			out.push({ key: `heat:${str(p.id)}`, lon, lat, text: L('lm_heat', shortPlace(str(p.name)), temp.toFixed(1)), tone: band === 'danger' || band === 'extreme' ? 'alert' : band === 'caution' ? 'warn' : 'neutral', priority: 2.2, maxAlt: 30_000 });
		}
	} else if (source === 'river') {
		for (const g of Array.isArray(body?.stations) ? body.stations : []) {
			const lon = num(g?.lon), lat = num(g?.lat), lvl = num(g?.level_m);
			if (lon == null || lat == null || lvl == null || !inBox(lon, lat, CITY_BBOX, REGION_MARGIN_DEG)) continue;
			const status = str(g?.status);
			out.push({ key: `river:${str(g.code)}`, lon, lat, text: L('lm_river', clip(str(g.name), 26), lvl.toFixed(2)), tone: status === 'danger' ? 'alert' : status === 'warning' ? 'warn' : 'ok', priority: status === 'normal' ? 2.3 : 0.5, maxAlt: 60_000 });
		}
	} else if (source === 'fires' || source === 'quakes') {
		for (const f of Array.isArray(body?.features) ? body.features : []) {
			const c = f?.geometry?.coordinates;
			const lon = num(c?.[0]), lat = num(c?.[1]);
			if (lon == null || lat == null || !inBox(lon, lat, CITY_BBOX, source === 'fires' ? 0.05 : REGION_MARGIN_DEG)) continue;
			const p = f?.properties ?? {};
			const at = Date.parse(str(p.at) || str(p.time));
			const ago = Number.isFinite(at) ? agoShort(at, now) : '—';
			if (source === 'fires') out.push({ key: `fire:${lon.toFixed(4)},${lat.toFixed(4)}`, lon, lat, text: L('lm_fire', ago), tone: 'alert', priority: 0.3, maxAlt: 40_000, t: Number.isFinite(at) ? at : null });
			else out.push({ key: `quake:${str(p.id)}`, lon, lat, text: L('lm_quake', num(p.mag)?.toFixed(1) ?? '?', ago), tone: 'warn', priority: 0.5, maxAlt: 120_000, t: Number.isFinite(at) ? at : null });
		}
	}
	return out;
}

const TONE_TOKEN: Record<Tone, [string, string]> = {
	ok: ['--v-band-green', 'seagreen'],
	warn: ['--v-band-amber', 'goldenrod'],
	alert: ['--v-band-red', 'indianred'],
	neutral: ['--v-map-marker', 'lightgray'],
};

function createLiveValuesLayer(): GodsEyeLayerInstance {
	let ctx: GodsEyeLayerContext | null = null;
	let active = false;
	let labels: Loose = null;
	let dots: Loose = null;
	let rings: Loose = null;
	let offPulse: (() => void) | null = null;
	const timers: Array<ReturnType<typeof setInterval>> = [];
	const bySource = new Map<string, LiveRow[]>();
	const state: Record<string, 'loading' | 'ok' | 'down'> = {};
	let lastSig = '';
	let pulses: Array<{ b: Loose; t0: number }> = [];
	let detail: Record<string, number> = {};

	function clear() {
		if (!ctx) return;
		const prims = (ctx.viewer as Loose)?.scene?.primitives;
		if (!prims) return;
		for (const c of [labels, dots, rings]) if (c) prims.remove(c);
		labels = dots = rings = null;
		pulses = [];
		drawn.clear();
		declutterFor(ctx).clear('livevalues');
	}

	function freshRows(lang: string, now: number): LiveRow[] {
		const out: LiveRow[] = [];
		const officer = ops.officerOn;
		for (const kind of ['osint_event', 'event'] as const) {
			for (const e of cityRegistry.byKind(kind)) {
				if (e.lon == null || e.lat == null) continue;
				// a corridor event's own time is when it started (its entity time is its last update); a report's is when
				// it was reported
				const props = (e.props ?? {}) as Record<string, unknown>;
				const started = Date.parse(String(props.actual_start ?? props.planned_start ?? ''));
				const t0 = kind === 'event' ? (Number.isFinite(started) ? started : null) : (e.t ?? null);
				const fresh = t0 != null && now - t0 < FRESH_MS && now - t0 > -60_000;
				const src = e.source === 'emulated' ? ` (${t(lang, 'lm_src_emulated')})` : '';
				const title = `${clip(displayText(e.label, officer), 30)}${src}`;
				const ago = t0 != null ? (now - t0 < 60_000 ? t(lang, 'lm_now') : agoShort(t0, now)) : '';
				out.push({
					key: `${kind}:${e.id}`,
					lon: e.lon,
					lat: e.lat,
					text: ago ? t(lang, 'lm_fresh', title, ago) : title,
					tone: kind === 'event' ? 'warn' : 'neutral',
					priority: fresh ? 0.2 : kind === 'event' ? 0.9 : 1.6,
					maxAlt: fresh ? 60_000 : 20_000,
					t: fresh ? t0 : null,
				});
			}
		}
		return out;
	}

	/** What is drawn per row key: updated IN PLACE when only its text or the ground height moves (a rebuilt label
	 *  must be rasterised again, which blinks on a slow GPU); re-created only when its look (tone, pulse) changes. */
	const drawn = new Map<string, { label: Loose; dot: Loose; ring: Loose; item: DeclutterItem; look: string; text: string; lon: number; lat: number }>();

	function rebuild(force = false) {
		if (!ctx || !active || !primitivesOk(ctx)) return;
		const cesium = ctx.cesium as Loose;
		const scene = (ctx.viewer as Loose).scene;
		const lang = ops.lang ?? 'en';
		const now = Date.now();
		bySource.set('fresh', freshRows(lang, now));
		const rows = [...bySource.values()].flat();
		const h = cityGround(ctx);
		const sig = JSON.stringify([lang, Math.round(h), rows.map((r) => [r.key, r.text, r.tone, r.t ? 1 : 0])]);
		if (!force && sig === lastSig) return;
		lastSig = sig;
		if (!labels) {
			labels = scene.primitives.add(new cesium.LabelCollection({ scene }));
			dots = scene.primitives.add(new cesium.BillboardCollection({ scene }));
			rings = scene.primitives.add(new cesium.BillboardCollection({ scene }));
		}
		const ink = cesium.Color.fromCssColorString('rgba(250, 250, 250, 1)');
		const halo = cesium.Color.fromCssColorString('rgba(10, 10, 10, 0.92)');
		const ring = ringImage(64);
		let freshCount = 0;
		const counts: Record<string, number> = {};
		const keep = new Set<string>();
		const drop = (key: string) => {
			const d = drawn.get(key);
			if (!d) return;
			labels.remove(d.label);
			if (d.dot) dots.remove(d.dot);
			if (d.ring) rings.remove(d.ring);
			drawn.delete(key);
		};
		for (const r of rows) {
			if (keep.has(r.key)) continue;
			keep.add(r.key);
			const src = r.key.split(':')[0];
			counts[src] = (counts[src] ?? 0) + 1;
			if (r.t != null) freshCount++;
			const position = cesium.Cartesian3.fromDegrees(r.lon, r.lat, h + 4);
			const [tok, fb] = TONE_TOKEN[r.tone];
			const fill = cssVar(tok) || fb;
			const isSituation = src === 'osint_event' || src === 'event';
			const look = JSON.stringify([fill, r.t != null, r.priority < 1, isSituation]);
			const box = labelBox(r.text, r.priority < 1 ? 13 : 12);
			const was = drawn.get(r.key);
			if (was && was.look === look) {
				// the same mark: its words and place move in place
				if (was.text !== r.text) {
					was.label.text = r.text;
					was.text = r.text;
				}
				was.label.position = position;
				if (was.dot) was.dot.position = position;
				if (was.ring) was.ring.position = position;
				was.item.position = position;
				was.item.w = box.w;
				was.item.h = box.h;
				was.item.priority = r.priority;
				was.item.maxAlt = r.maxAlt;
				continue;
			}
			drop(r.key);
			const img = glyphImage('', fill, 'rgba(12,12,12,0.95)', '#fff', 22);
			// a situation's marker is its own layer's: here only its label (and pulse)
			const dot = isSituation || !img ? null : dots.add({ position, image: img, width: 12, height: 12, disableDepthTestDistance: Number.POSITIVE_INFINITY });
			const pulseRing =
				r.t != null && ring
					? rings.add({ position, image: ring, width: 44, height: 44, color: cesium.Color.fromCssColorString(fill), disableDepthTestDistance: Number.POSITIVE_INFINITY })
					: null;
			const px = r.priority < 1 ? 13 : 12;
			const label = labels.add({
				position,
				text: r.text,
				font: canvasFont([r.priority < 1 ? '600' : '500', px + 'px', 'var(--v-font-ui)'].join(' ')),
				fillColor: ink,
				outlineColor: halo,
				outlineWidth: 3,
				style: cesium.LabelStyle?.FILL_AND_OUTLINE ?? 2,
				verticalOrigin: cesium.VerticalOrigin?.BOTTOM ?? 1,
				horizontalOrigin: cesium.HorizontalOrigin?.CENTER ?? 0,
				pixelOffset: new cesium.Cartesian2(0, isSituation ? -16 : -9),
				disableDepthTestDistance: Number.POSITIVE_INFINITY,
				show: false,
			});
			const item: DeclutterItem = { key: `lv:${r.key}`, priority: r.priority, position, w: box.w, h: box.h, dy: isSituation ? -16 : -9, maxAlt: r.maxAlt, apply: (show) => (label.show = show) };
			drawn.set(r.key, { label, dot, ring: pulseRing, item, look, text: r.text, lon: r.lon, lat: r.lat });
		}
		for (const key of [...drawn.keys()]) if (!keep.has(key)) drop(key);
		pulses = [...drawn.values()].filter((d) => d.ring).map((d, i) => ({ b: d.ring, t0: i * 397 }));
		declutterFor(ctx).set(
			'livevalues',
			[...drawn.values()].map((d) => d.item),
		);
		detail = { readings: drawn.size, fresh: freshCount, ...counts };
		ctx.notify();
	}

	function pulse() {
		if (!pulses.length) return;
		const now = performance.now();
		for (const p of pulses) {
			const phase = ((now + p.t0) % 1800) / 1800;
			p.b.scale = 0.35 + 1.15 * phase;
			const c = p.b.color;
			if (c) p.b.color = new (ctx!.cesium as Loose).Color(c.red, c.green, c.blue, 0.95 * (1 - phase));
		}
	}

	async function poll(id: SourceId) {
		if (!ctx || !active) return;
		try {
			const body = await aiJson<Loose>(SOURCES[id].path, {}, 30_000);
			bySource.set(id, rowsOf(id, body, ops.lang ?? 'en'));
			state[id] = 'ok';
			liveClock.mark(id);
		} catch {
			state[id] = 'down';
			// last good rows stay; a source that never answered draws nothing
		}
		rebuild();
	}

	return {
		async status() {
			return { configured: true };
		},
		init(layerCtx) {
			ctx = layerCtx;
		},
		activate() {
			active = true;
			for (const id of Object.keys(SOURCES) as SourceId[]) {
				state[id] = 'loading';
				void poll(id);
				timers.push(setInterval(() => void poll(id), SOURCES[id].everyMs));
			}
			// fresh situations and the clock words ("4 min") from the registry, every 3 s
			timers.push(setInterval(() => rebuild(), 3000));
			const scene = (ctx!.viewer as Loose)?.scene;
			const off = scene?.preUpdate?.addEventListener?.(pulse);
			offPulse = typeof off === 'function' ? off : null;
			rebuild(true);
		},
		deactivate() {
			active = false;
			for (const x of timers) clearInterval(x);
			timers.length = 0;
			offPulse?.();
			offPulse = null;
			clear();
			bySource.clear();
			lastSig = '';
			detail = {};
		},
		refresh() {
			for (const id of Object.keys(SOURCES) as SourceId[]) void poll(id);
		},
		restyle() {
			rebuild(true);
		},
		handlePick() {
			return false;
		},
		urnOf() {
			return null;
		},
		coverageStats() {
			const down = Object.entries(state)
				.filter(([, v]) => v === 'down')
				.map(([k]) => k);
			return {
				count: detail.readings ?? 0,
				loading: Object.values(state).some((v) => v === 'loading'),
				hint: `${detail.readings ?? 0} readings at their places (${detail.fresh ?? 0} fresh)${down.length ? ` · not answering: ${down.join(', ')}` : ''}`,
				error: null,
				detail,
				via: 'hydro+cityfeeds+city-api',
			};
		},
		destroy() {
			this.deactivate();
		},
	};
}

export const liveValuesLayer: GodsEyeLayer = {
	id: 'livevalues',
	name: 'Live readings at their places (pumps, tide, heat, rivers, fires, fresh situations)',
	label: 'LIVE',
	requiresKeyId: null,
	pickPrefix: LIVE_VALUES_PICK_PREFIX,
	defaultOn: true,
	group: 'intelligence',
	create: createLiveValuesLayer,
};
