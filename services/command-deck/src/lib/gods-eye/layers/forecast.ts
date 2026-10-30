/**
 * forecast layer — the roads the corridor forecast (services/forecast, Chronos-2) expects to cross 0.8 V/C within
 * the next 2 hours, drawn ON the canvas over the platform's road geometry (godsEye.segments, joined by id).
 *
 * Data: GET /api/forecast/forecast/segments?horizon_min=120, every 5 min with back-off (the service caches its run;
 * every surface asks for the full horizon so they share one computation). A road is drawn when its median (p50)
 * V/C reaches the threshold at any step within the horizon. Until Mumbai traffic is recorded, the history under
 * the forecast is SIMULATED and the layer says so (detail.simulated → the sheet's "Simulated" tag; the pick text).
 *
 * SYMBOLOGY (never a hue: a forecast is a measure, not a state that asks for an action): the neutral flow ink at
 * its jammed stop (--v-flow-5) DASHED — what is coming, not what is — 5 px when the median reaches 0.9, 3.5 px
 * below, in the dark ground casing. Under chrome v2 a selection dims it; the kind filter that hides roads hides it.
 *
 * Pick ids `fc:<segmentId>` → URN `segment:<id>` (the same road the flow layer picks); the selection card shows the
 * road's +30 / +60 / +120 min band.
 */

import { godsEye } from '../store.svelte';
import type { GodsEyeLayer, GodsEyeLayerContext, GodsEyeLayerInstance } from '../registry';
import { DRAPE_Z, drapeAudit, drapedPolyline, groundPath } from './draping';
import { chromeOf, flowDim, kindShown, viewOf } from '../hud/map/view';
import { inkAlpha, mapInk } from '../hud/map/symbols';
import { cssVar } from '$lib/design/tokens';
import { getForecast } from '$lib/ai/client';
import { createPoller, type Poller } from '$lib/ai/poll';
import { forecastPoints } from '$lib/ai/core';
import type { ForecastDoc, ForecastSegment } from '$lib/ai/types';

export const FORECAST_PICK_PREFIX = 'fc:';

/** Dash widths (px): the median reaching 0.9 draws heavier. */
export const FORECAST_STYLE = Object.freeze({ heavy: 5, light: 3.5, dash: 10, casing: 2 });

function peakP50(seg: ForecastSegment): number {
	return seg.steps.reduce((m, s) => Math.max(m, s.vc?.p50 ?? 0), 0);
}

function text(seg: ForecastSegment, simulated: boolean): string {
	const pts = forecastPoints(seg)
		.filter((p): p is NonNullable<typeof p> => !!p)
		.map((p) => `+${p.lead} min ${p.vc.p50.toFixed(2)} (${p.vc.p10.toFixed(2)}–${p.vc.p90.toFixed(2)})`);
	const now = seg.now ? ` Now ${seg.now.vc.toFixed(2)}.` : '';
	const cross = seg.crossing?.in_min != null ? ` Crosses 0.8 in about ${seg.crossing.in_min} min.` : seg.above_threshold_now ? ' Already over 0.8.' : '';
	return `${seg.road_name} (${seg.place}): V/C forecast, median with the p10–p90 band — ${pts.join(', ')}.${now}${cross} Chronos-2, modelled${simulated ? ', on simulated traffic history' : ''}.`;
}

function createForecastLayer(): GodsEyeLayerInstance {
	let ctx: GodsEyeLayerContext | null = null;
	let active = false;
	let poller: Poller | null = null;
	let drawTimer: ReturnType<typeof setInterval> | null = null;
	let doc: ForecastDoc | null = null;
	let feed: 'loading' | 'ok' | 'down' | 'not-deployed' = 'loading';
	let lastSig = '';
	const ids: string[] = [];
	let hint = 'loading the corridor forecast';
	let detail: Record<string, number> = {};

	function draw() {
		if (!ctx || !active) return;
		const { cesium, viewer } = ctx;
		const view = chromeOf(ctx) === 'v2' ? viewOf(ctx) : null;
		const dim = view ? flowDim(view) : { alpha: 1, thinPx: 0 };
		const hidden = !!view && !kindShown(view, 'segment');
		const threshold = doc?.threshold_vc ?? 0.8;
		const simulated = (doc?.data_labels ?? []).some((l) => /SIMULATED/i.test(l));
		const hot = (doc?.segments ?? []).filter((s) => peakP50(s) >= threshold);
		const geo = godsEye.segmentById;
		const ink = cssVar('--v-flow-5') || 'white';
		const casing = mapInk('casing');
		const sig = JSON.stringify([hot.map((s) => [s.segment_id, peakP50(s) >= 0.9, geo.get(s.segment_id)?.coordinates.length ?? 0, text(s, simulated)]), dim, hidden, ink, casing]);
		if (sig === lastSig) return;
		lastSig = sig;
		for (const id of ids) viewer.entities.removeById(id);
		ids.length = 0;
		let missing = 0;
		for (const s of hot) {
			const g = geo.get(s.segment_id);
			if (!g || g.coordinates.length < 2) {
				missing++;
				continue;
			}
			if (hidden) continue;
			const width = Math.max(1, (peakP50(s) >= 0.9 ? FORECAST_STYLE.heavy : FORECAST_STYLE.light) - dim.thinPx);
			const entity = viewer.entities.add({
				id: `${FORECAST_PICK_PREFIX}${s.segment_id}`,
				polyline: drapedPolyline(cesium, {
					positions: groundPath(cesium, g.coordinates),
					width: width + FORECAST_STYLE.casing,
					material: new cesium.PolylineDashMaterialProperty({
						color: cesium.Color.fromCssColorString(inkAlpha(ink, 0.95 * dim.alpha)),
						gapColor: cesium.Color.fromCssColorString(inkAlpha(casing, 0.75 * dim.alpha)),
						dashLength: FORECAST_STYLE.dash,
					}),
					z: DRAPE_Z.superseded,
				}),
				description: text(s, simulated),
			});
			ids.push(entity.id);
		}
		detail = { crossing: hot.length, drawn: ids.length, not_drawn: missing, simulated: simulated ? hot.length : 0, roads: doc?.segments.length ?? 0 };
		const tag = simulated ? ' · forecast on simulated traffic' : '';
		const notDrawn = missing ? ` · ${missing} not drawn (no road geometry in the platform feed)` : '';
		hint =
			feed === 'not-deployed'
				? 'corridor forecast not deployed on this deck'
				: feed === 'down' && !doc
					? 'corridor forecast unreachable — nothing drawn'
					: !doc
						? 'loading the corridor forecast'
						: `${hot.length} of ${doc.segments.length} roads forecast to reach ${threshold} V/C within ${doc.horizon_min} min (${doc.model})${tag}${notDrawn}`;
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
						doc = await getForecast(120);
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
				{ baseMs: 300_000 },
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
			return pickId.startsWith(FORECAST_PICK_PREFIX);
		},
		urnOf(pickId) {
			const id = pickId.slice(FORECAST_PICK_PREFIX.length);
			return /^\d+$/.test(id) ? `segment:${id}` : null;
		},
		coverageStats() {
			return {
				count: detail.crossing ?? 0,
				loading: feed === 'loading',
				hint,
				error: feed === 'down' && !doc ? 'corridor forecast down' : null,
				detail: ctx ? { ...detail, ...drapeAudit(ctx.viewer, ids) } : detail,
				via: 'forecast/segments',
			};
		},
		destroy() {
			this.deactivate();
		},
	};
}

export const forecastLayer: GodsEyeLayer = {
	id: 'forecast',
	name: 'Traffic forecast (Chronos-2)',
	label: 'FCST',
	requiresKeyId: null,
	pickPrefix: FORECAST_PICK_PREFIX,
	defaultOn: false,
	group: 'traffic',
	create: createForecastLayer,
};
