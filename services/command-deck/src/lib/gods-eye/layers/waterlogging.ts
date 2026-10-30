/**
 * waterlogging layer — the hydro nowcast's risk class per road, drawn ON the canvas like the flow layer (draped
 * polylines on the platform's own road geometry, godsEye.segments, joined by segment id).
 *
 * Data: GET /api/hydro/hydro/nowcast (services/hydro through the deck proxy), every 2 min with back-off. Each
 * road's class 0–3 is the PEAK within the next 2 hours (MODELLED), from rain (LIVE, Open-Meteo — a model nowcast,
 * not a gauge), the Arabian Sea tide (MODELLED), terrain and drainage (MODELLED) and pump state (EMULATED). The pick
 * text says all of that in plain words.
 *
 * HINDSIGHT ($lib/ai/hindsight): when the map page opens the 18–19 Aug 2025 replay, the layer draws each road's
 * MODELLED class at the chosen moment of that night from IMD's OBSERVED rain instead, and every pick text and the
 * hint begin with the replay's date — never today's city.
 *
 * SYMBOLOGY (colour only for meaning): one semantic hue, --v-map-water (waterlogging is a hazard on the road, not
 * a measure), stepped by WIDTH and opacity — class 1 shallow: a thin 45 % line; class 2 deep: 6 px at 85 % in a
 * dark casing; class 3 impassable: 9 px, opaque, in the casing. A dry road draws nothing (absence is not drawn as
 * data). It never reads --v-act, --v-data or --v-tool. Under chrome v2 a selection dims it like the flow layer,
 * and the kind filter that hides roads hides it too.
 *
 * A road the nowcast names but the platform's road feed has no geometry for is counted (hint "n not drawn"),
 * never placed on a guessed line.
 *
 * Pick ids `wl:<segmentId>` → URN `segment:<id>` (the same road the flow layer picks).
 */

import { godsEye } from '../store.svelte';
import type { GodsEyeLayer, GodsEyeLayerContext, GodsEyeLayerInstance } from '../registry';
import { DRAPE_Z, drapeAudit, drapedPolyline, groundPath } from './draping';
import { chromeOf, flowDim, kindShown, viewOf } from '../hud/map/view';
import { inkAlpha, mapInk } from '../hud/map/symbols';
import { cssVar } from '$lib/design/tokens';
import { getNowcast } from '$lib/ai/client';
import { createPoller, type Poller } from '$lib/ai/poll';
import { hindsight } from '$lib/ai/hindsight';
import { replayClassAt } from '$lib/ai/core';
import type { HydroNowcast } from '$lib/ai/types';

export const WATERLOG_PICK_PREFIX = 'wl:';

/** Width (px) and opacity per class (1 shallow, 2 deep, 3 impassable); casing from class 2. */
export const WATER_STYLE: Readonly<Record<1 | 2 | 3, { width: number; alpha: number; casing: boolean }>> = Object.freeze({
	1: { width: 3, alpha: 0.45, casing: false },
	2: { width: 6, alpha: 0.85, casing: true },
	3: { width: 9, alpha: 1, casing: true },
});

const CLASS_WORD = ['dry', 'shallow water', 'deep water', 'impassable'] as const;

const istTime = (ms: number) => new Date(ms + 5.5 * 3_600_000).toISOString().slice(11, 16);

interface Row {
	id: number;
	cls: 1 | 2 | 3;
	coords: Array<[number, number]>;
	text: string;
}

function createWaterloggingLayer(): GodsEyeLayerInstance {
	let ctx: GodsEyeLayerContext | null = null;
	let active = false;
	let poller: Poller | null = null;
	let drawTimer: ReturnType<typeof setInterval> | null = null;
	let nowcast: HydroNowcast | null = null;
	let feed: 'loading' | 'ok' | 'down' | 'not-deployed' = 'loading';
	let lastSig = '';
	const ids: string[] = [];
	let hint = 'loading the waterlogging nowcast';
	let detail: Record<string, number> = {};

	function liveText(s: HydroNowcast['segments'][number]): string {
		const d = s.drivers ?? {};
		const deep = s.lead_time_deep_min == null ? '' : s.lead_time_deep_min === 0 ? ' Deep water now.' : ` Deep water in about ${s.lead_time_deep_min} min.`;
		const rain = d.rain ? ` Rain ${d.rain.label === 'LIVE' ? 'live' : String(d.rain.label).toLowerCase()} (Open-Meteo, a model nowcast): ${d.rain.next_2h_mm ?? 0} mm in the next 2 h.` : '';
		const tide = d.tide ? ` Tide modelled at ${d.tide.level_m} m, gates ${d.tide.gate_closed_now ? 'shut' : 'open'}.` : '';
		const pumps = d.pumps?.station ? ` Pumps emulated (${d.pumps.station}: ${d.pumps.pumps_available ?? '?'} of ${d.pumps.pumps_total ?? '?'}).` : '';
		return `${s.road_name} (${s.place}): waterlogging risk ${s.risk_class}, ${CLASS_WORD[s.risk_class] ?? ''} (${s.expected_depth_band}) within 2 h, modelled.${deep}${rain}${tide}${pumps}`;
	}

	function rows(): { rows: Row[]; missing: number; counts: Record<string, number> } {
		const geo = godsEye.segmentById;
		const out: Row[] = [];
		let missing = 0;
		const counts: Record<string, number> = { '1': 0, '2': 0, '3': 0 };
		if (hindsight.on && hindsight.at != null) {
			const at = hindsight.at;
			for (const s of hindsight.segments.values()) {
				const c = replayClassAt(s, at);
				if (c < 1) continue;
				counts[String(c)]++;
				const g = geo.get(s.segment_id);
				if (!g || g.coordinates.length < 2) {
					missing++;
					continue;
				}
				const first = s.first_class2_ist ? ` First deep at ${s.first_class2_ist.slice(11)} IST.` : '';
				out.push({
					id: s.segment_id,
					cls: c as 1 | 2 | 3,
					coords: g.coordinates,
					text: `Hindsight, 19 Aug 2025 ${istTime(at)} IST — ${s.road_name} (${s.place}): ${CLASS_WORD[c]}, modelled from IMD observed rain.${first} Not today's city.`,
				});
			}
			return { rows: out, missing, counts };
		}
		for (const s of nowcast?.segments ?? []) {
			const c = s.risk_class;
			if (!(c >= 1)) continue;
			counts[String(Math.min(3, c))]++;
			const g = geo.get(s.segment_id);
			if (!g || g.coordinates.length < 2) {
				missing++;
				continue;
			}
			out.push({ id: s.segment_id, cls: Math.min(3, c) as 1 | 2 | 3, coords: g.coordinates, text: liveText(s) });
		}
		return { rows: out, missing, counts };
	}

	function draw() {
		if (!ctx || !active) return;
		const { cesium, viewer } = ctx;
		const view = chromeOf(ctx) === 'v2' ? viewOf(ctx) : null;
		const dim = view ? flowDim(view) : { alpha: 1, thinPx: 0 };
		const hidden = !!view && !kindShown(view, 'segment');
		const r = rows();
		const water = cssVar('--v-map-water') || 'deepskyblue';
		const casingInk = mapInk('casing');
		const sig = JSON.stringify([r.rows.map((x) => [x.id, x.cls, x.coords.length, x.text]), dim, hidden, water, casingInk, hindsight.version]);
		if (sig === lastSig) return;
		lastSig = sig;
		for (const id of ids) viewer.entities.removeById(id);
		ids.length = 0;
		if (!hidden) {
			for (const x of r.rows) {
				const st = WATER_STYLE[x.cls];
				const core = Math.max(1, st.width - dim.thinPx);
				const color = cesium.Color.fromCssColorString(inkAlpha(water, st.alpha * dim.alpha));
				let width = core;
				let material: unknown = new cesium.ColorMaterialProperty(color);
				if (st.casing && cesium.PolylineOutlineMaterialProperty) {
					width = core + 3;
					material = new cesium.PolylineOutlineMaterialProperty({ color, outlineColor: cesium.Color.fromCssColorString(inkAlpha(casingInk, 0.9 * dim.alpha)), outlineWidth: 3 });
				}
				const entity = viewer.entities.add({
					id: `${WATERLOG_PICK_PREFIX}${x.id}`,
					polyline: drapedPolyline(cesium, { positions: groundPath(cesium, x.coords), width, material, z: DRAPE_Z.zone }),
					description: x.text,
				});
				ids.push(entity.id);
			}
		}
		const atRisk = r.counts['1'] + r.counts['2'] + r.counts['3'];
		detail = { at_risk: atRisk, shallow: r.counts['1'], deep: r.counts['2'], impassable: r.counts['3'], drawn: hidden ? 0 : ids.length, not_drawn: r.missing, hindsight: hindsight.on ? 1 : 0 };
		const notDrawn = r.missing ? ` · ${r.missing} not drawn (no road geometry in the platform feed)` : '';
		if (hindsight.on && hindsight.at != null) {
			hint = `Hindsight 19 Aug 2025 ${istTime(hindsight.at)} IST (IMD observed rain, modelled ponding): ${r.counts['3']} impassable · ${r.counts['2']} deep · ${r.counts['1']} shallow${notDrawn}`;
		} else if (feed === 'not-deployed') hint = 'waterlogging nowcast not deployed on this deck';
		else if (feed === 'down' && !nowcast) hint = 'waterlogging nowcast unreachable — nothing drawn';
		else if (!nowcast) hint = 'loading the waterlogging nowcast';
		else
			hint = atRisk
				? `${atRisk} roads at risk within 2 h (modelled): ${r.counts['3']} impassable · ${r.counts['2']} deep · ${r.counts['1']} shallow${notDrawn}`
				: `no road at risk within 2 h (modelled; rain ${nowcast.labels?.rain === 'LIVE' ? 'live' : 'unavailable'}, ${nowcast.rain_feed?.city_now_mm_h ?? 0} mm/h now)`;
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
			poller = createPoller(
				async () => {
					try {
						nowcast = await getNowcast();
						feed = 'ok';
					} catch (err) {
						feed = err instanceof Error && err.name === 'AiNotDeployed' ? 'not-deployed' : 'down';
						throw err;
					} finally {
						lastSig = '';
						draw();
						ctx?.notify();
					}
				},
				{ baseMs: 120_000 },
			);
			poller.start();
			draw();
			drawTimer = setInterval(() => draw(), 2000);
		},
		deactivate() {
			active = false;
			poller?.stop();
			poller = null;
			if (drawTimer) clearInterval(drawTimer);
			drawTimer = null;
			if (ctx) for (const id of ids) ctx.viewer.entities.removeById(id);
			ids.length = 0;
			lastSig = '';
			detail = {};
		},
		refresh() {
			lastSig = '';
			poller?.kick();
			draw();
		},
		restyle() {
			draw();
		},
		handlePick(pickId) {
			return pickId.startsWith(WATERLOG_PICK_PREFIX);
		},
		urnOf(pickId) {
			const id = pickId.slice(WATERLOG_PICK_PREFIX.length);
			return /^\d+$/.test(id) ? `segment:${id}` : null;
		},
		coverageStats() {
			return {
				count: detail.at_risk ?? 0,
				loading: feed === 'loading' && !hindsight.on,
				hint,
				error: feed === 'down' && !nowcast ? 'hydro nowcast down' : null,
				detail: ctx ? { ...detail, ...drapeAudit(ctx.viewer, ids) } : detail,
				via: hindsight.on ? 'hydro/replay' : 'hydro/nowcast',
			};
		},
		destroy() {
			this.deactivate();
		},
	};
}

export const waterloggingLayer: GodsEyeLayer = {
	id: 'waterlog',
	name: 'Waterlogging risk (hydro nowcast)',
	label: 'WATER',
	requiresKeyId: null,
	pickPrefix: WATERLOG_PICK_PREFIX,
	defaultOn: true,
	group: 'traffic',
	create: createWaterloggingLayer,
};
