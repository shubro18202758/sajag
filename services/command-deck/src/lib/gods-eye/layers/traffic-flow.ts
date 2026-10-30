/**
 * traffic-flow layer — the restored VVIP template's signature congestion
 * network, drawn ON the God's-eye canvas.
 *
 * Geometry comes from the shared canvas segment feed (GET /spatial/segments,
 * cached in the gods-eye store); congestion comes from the oracle's Valkey
 * hot cache (POST /api/v1/traffic/live with the visible segment ids).
 *
 * HONEST DEGRADATION (the system's rule, kept): a segment with NO current
 * observation — or one older than STALE_OBS_SEC — renders as a thin neutral
 * hairline ('NO DATA' in its pick card), never a guessed colour. When the
 * hot cache is empty (quiet window, emulator idle) the whole network renders
 * neutral and the layer hint says so; the ramp colours appear the moment
 * observations flow (signal-ingress / emulator runs).
 *
 * PROVENANCE: every observation carries its data_quality. The integrated
 * signal-ingress feed is SYNTHETIC (data_quality 'synthetic') — such rows
 * are labelled SIMULATED FEED on the chip hint and every pick card, never
 * LIVE ('live' only ever describes system freshness, not data provenance).
 *
 * EMULATED PLANE (contract C-P): an event-emulator showcase run's traffic
 * no longer lands in `observations` — the oracle serves it beside the
 * ingest plane as `emulated_observations` (origin 'emulated', synthetic).
 * While such a row is fresh it colours its segment (the showcase's
 * congestion is what the run is for), and it says so: EMULATED · SIMULATED
 * FEED on its pick card (the ingest plane's own reading beside it) and an
 * 'n EMULATED' count in the hint. The road name falls back to the row's
 * road_name when the segment feed has none.
 *
 * GEOMETRY BASIS (contract C-K): a segment drawn on real OSM geometry —
 * its routing geometry itself ('osm', the real-road network) or its
 * OSM-traced display geometry ('osm_display') — is a SOLID line; only a
 * SCHEMATIC one (the seed's junction-to-junction chord — not the road's
 * true shape) is drawn DASHED and says so on its pick card, and the hint
 * counts both ('n OSM-traced · m schematic (dashed)') so a chord never
 * passes for a road.
 *
 * DRAPED (layers/draping.ts): every segment is a ground polyline on terrain
 * AND the photoreal 3D tiles (the keyless-era 2 m lines were buried under
 * the real city), at the bottom of the ground draw order — spines, traces
 * and the pursuit paint over it. Widths read at 1920×1080 from the 1.5–3 km
 * overview: a coloured segment is a 6 px line — a 3.5 px ramp-coloured
 * core inside a dark 1.25 px casing on each side (legible on aerial
 * imagery and on the dark raster alike); a
 * schematic chord's dashes alternate with the same dark casing colour; a
 * NO DATA hairline is 2 px of neutral ink.
 *
 * Network hygiene: the 8 s POST is skipped while the tab is hidden (the
 * shared poll gate, $lib/ops/client), so a background /ops tab sends none.
 *
 * Ramp (design tokens at runtime — zero hex literals, theme.ts bridge):
 *   congestion ≤0.2 band-green (free) · ≤0.4 flow-light · ≤0.6 band-amber
 *   · ≤0.8 act (heavy) · >0.8 band-red (severe) — the template ladder,
 *   expressed entirely in existing token slots.
 *
 * CHROME V2 (SPEC §2.3–2.4, §5.3): the operator map's ramp is NEUTRAL —
 * luminance and width, never hue (congestion is a measure, not a state that
 * asks for an action): flowStyle(flowStop(c)) from the design tokens, free
 * roads thin and dim (1.5 px --v-flow-1 at 55 %), jammed roads thick and
 * white (4.5 px --v-flow-5) with a --v-map-casing casing from stop 3 up. A
 * NO DATA road is a 1 px trace dimmer than "free". Under a selection the
 * whole layer drops to 60 % and 0.5 px thinner (hud/map/view.ts flowDim).
 * The pick text says the same facts in plain words, with no stacked status
 * words. The legacy chrome draws exactly as before.
 *
 * Pick ids `seg:<segmentId>` → URN `segment:<id>`.
 */

import { godsEye } from '../store.svelte';
import { ORACLE_V1 } from '$lib/ops/endpoints';
import { createPollGate } from '$lib/ops/client';
import type { GodsEyeLayer, GodsEyeLayerContext, GodsEyeLayerInstance } from '../registry';
import { cssVar, withAlpha } from '../theme';
import { DRAPE_Z, drapeAudit, drapedPolyline, groundPath } from './draping';
import { chromeOf, flowDim, kindShown, viewOf } from '../hud/map/view';
import { flowInk, flowStop, inkAlpha } from '../hud/map/symbols';
import { ops } from '$lib/ops/store.svelte';
import { aiJson } from '$lib/ai/client';
import { createFlowMotion, type FlowRoad } from './flow-motion';
import { liveClock } from '../hud/map/live-clock';

export const TRAFFIC_FLOW_PICK_PREFIX = 'seg:';

/** An observation older than this no longer colours its segment. */
export const STALE_OBS_SEC = 300;

/** Draped widths (px) — legible at 1920×1080 from the 1.5–3 km overview. */
export const FLOW_WIDTH = { coloured: 6, casing: 1.25, noData: 2 } as const;

interface LiveObservation {
	segment_id: number;
	speed_kmh: number;
	congestion_idx: number;
	timestamp_ms: number;
	source?: string;
	/** real | synthetic | anomalous (oracle TrafficObservation.data_quality). */
	data_quality?: string;
	/** C-P: the segment's road name from the oracle's segment map (additive). */
	road_name?: string | null;
	/** C-P: 'live' (the ingest plane) | 'emulated' (an emulator showcase run). */
	origin?: string;
}

/** The rows of one /traffic/live plane, keyed by segment (malformed rows dropped). */
function planeOf(rows: unknown): Map<number, LiveObservation> {
	const out = new Map<number, LiveObservation>();
	for (const o of Array.isArray(rows) ? (rows as LiveObservation[]) : []) {
		if (typeof o?.segment_id === 'number') out.set(o.segment_id, o);
	}
	return out;
}

/** The 5-stop congestion ramp from live tokens (mirrors flowColor() in
 * tokens.ts; canvas code reaches tokens through theme.ts, not design/). */
function rampColor(idx: number): string {
	const stop =
		idx <= 0.2
			? '--v-band-green'
			: idx <= 0.4
				? '--v-flow-light'
				: idx <= 0.6
					? '--v-band-amber'
					: idx <= 0.8
						? '--v-act'
						: '--v-band-red';
	return cssVar(stop) ?? 'cornflowerblue';
}

/**
 * Draped widths of the v2 ramp's extras (the casing each side, the NO DATA
 * trace, px), its alphas, and how long a reading that changes the picture
 * may wait for a draped build still in flight (ms).
 */
/** The road under every reading keeps a dark casing: a light line alone vanishes into satellite and 3D imagery. */
export const FLOW_V2 = { casing: 1.25, noData: 1, freeAlpha: 0.95, alpha: 1, noDataAlpha: 0.35, deferMaxMs: 45_000, groundCasing: 'rgba(17, 17, 17, 0.85)' } as const;

/**
 * Chrome v2: one segment on the neutral ramp (flowStyle(flowStop(c))) — its
 * draped width and material; dimmed and thinned under a selection.
 */
function v2Line(
	cesium: CesiumGlobal,
	obs: LiveObservation | undefined,
	schematic: boolean,
	dim: { alpha: number; thinPx: number },
	rampIdx: number | null = null,
): { width: number; material: unknown } {
	if (!obs) {
		const trace = flowInk(0);
		return { width: FLOW_V2.noData, material: cesium.Color.fromCssColorString(inkAlpha(trace.color, FLOW_V2.noDataAlpha * dim.alpha)) };
	}
	const ramp = vcInk(rampIdx ?? obs.congestion_idx);
	const alpha = (ramp.stop === 1 ? FLOW_V2.freeAlpha : FLOW_V2.alpha) * dim.alpha;
	const core = Math.max(1, ramp.width - dim.thinPx);
	const color = cesium.Color.fromCssColorString(inkAlpha(ramp.color, alpha));
	const casing = cesium.Color.fromCssColorString(inkAlpha(FLOW_V2.groundCasing, Math.min(1, 0.85 * dim.alpha)));
	if (schematic) {
		// a chord is not the road's true shape: dashed, its gaps the casing (or clear)
		return { width: core, material: new cesium.PolylineDashMaterialProperty({ color, gapColor: casing ?? undefined, dashLength: 12 }) };
	}
	if (casing && cesium.PolylineOutlineMaterialProperty) {
		return {
			width: core + 2 * FLOW_V2.casing,
			// the outline material's width is both edges together (interior = width − outlineWidth)
			material: new cesium.PolylineOutlineMaterialProperty({ color, outlineColor: casing, outlineWidth: 2 * FLOW_V2.casing }),
		};
	}
	return { width: core, material: new cesium.ColorMaterialProperty(color) };
}

/**
 * Chrome v2 (live map, 29 Oct): a road's congestion reads in the band ladder the map already uses for meaning —
 * green free (stops 1–2), amber slow (3), red jammed (4–5) — and in WIDTH (the neutral ramp's widths, never under
 * 3 px so a free road still reads on the photoreal city). Never orange (a decision waits) or blue (AI, a route).
 */
export function vcInk(congestionIdx: number): { stop: number; color: string; width: number; token: string } {
	const stop = flowStop(congestionIdx);
	const token = stop <= 2 ? '--v-band-green' : stop === 3 ? '--v-band-amber' : '--v-band-red';
	const fallback = stop <= 2 ? '#32a467' : stop === 3 ? '#ffb257' : '#e76a6e';
	return { stop, token, color: cssVar(token) || fallback, width: Math.max(3, flowInk(congestionIdx).width) };
}

/**
 * A road's volume/capacity as a point on the ramp (so V/C drives the colour when the forecast service has it):
 * under 0.6 free (stop 1), 0.6–0.8 slow (3), 0.8–1.0 heavy (4), 1.0 and over jammed (5) — the usual V/C service
 * bands. Pure; exported for tests.
 */
export function vcRampIdx(vc: number): number {
	return vc < 0.6 ? 0.1 : vc < 0.8 ? 0.5 : vc < 1 ? 0.7 : 0.9;
}

/** Chrome v2: the segment's pick text in plain words (no stacked status words). */
function v2Description(
	name: string,
	schematic: boolean,
	obs: LiveObservation | undefined,
	raw: LiveObservation | undefined,
	ageSec: number | null,
	emulated: boolean,
	live: LiveObservation | undefined,
): string {
	const basis = schematic ? ' Drawn as a straight chord between junctions, not the road’s true shape.' : '';
	if (!obs) {
		return raw
			? `${name}: no current reading (the last one is ${ageSec} s old, past the ${STALE_OBS_SEC} s limit).${basis}`
			: `${name}: no reading in the hot cache.${basis}`;
	}
	const source = emulated
		? 'emulated run, simulated feed'
		: obs.data_quality === 'synthetic'
			? 'simulated feed'
			: obs.data_quality === 'anomalous'
				? 'flagged anomalous'
				: `source ${obs.source ?? 'unknown'}`;
	const ingest =
		emulated && live
			? ` The ingest plane reads ${live.speed_kmh.toFixed(1)} km/h, ${(live.congestion_idx * 100).toFixed(0)} %.`
			: '';
	return `${name}: ${obs.speed_kmh.toFixed(1)} km/h, congestion ${(obs.congestion_idx * 100).toFixed(0)} % (${source}, ${ageSec} s ago).${ingest}${basis}`;
}

function createTrafficFlowLayer(): GodsEyeLayerInstance {
	let ctx: GodsEyeLayerContext | null = null;
	let active = false;
	let pollTimer: ReturnType<typeof setInterval> | null = null;
	let drawTimer: ReturnType<typeof setInterval> | null = null;
	const gate = createPollGate();
	const entityIds: string[] = [];
	let obsById = new Map<number, LiveObservation>();
	/** The emulated plane (C-P emulated_observations): showcase-run rows. */
	let emuById = new Map<number, LiveObservation>();
	let obsFeed: 'ok' | 'empty' | 'down' = 'empty';
	let hint = 'loading';
	let lastSignature = '';
	/** The picture last drawn (the segments' styles): the geometry is rebuilt only when it changes. */
	let lastPicture = '';
	/** …its structure (segments, basis, dim, filter, inks), whether it had data, and when it was drawn (ms). */
	let lastStructure = '';
	let lastHadData = false;
	let lastRedrawAt = 0;
	/** Each drawn segment's pick text (rewritten in place when only the reading moved). */
	const descriptions = new Map<string, string>();
	/** Each drawn segment's look (its ramp step) as drawn: a waiting picture never rewrites a text its line contradicts. */
	const drawnStyles = new Map<string, string>();
	let detail: Record<string, number> = {};
	/** The moving dots and the road names (flow-motion.ts); created on activate. */
	let motion: ReturnType<typeof createFlowMotion> | null = null;
	/** The forecast service's current V/C per road (its 15-minute "now"; simulated history). */
	let vcById = new Map<number, number>();
	let vcTimer: ReturnType<typeof setInterval> | null = null;
	/** The first V/C answer (or its failure) has landed: the first picture waits for it (≤ VC_WAIT_MS) so the
	 *  draped network is built once, in its V/C colours, instead of twice. */
	let vcTried = false;
	let activatedAt = 0;
	const VC_WAIT_MS = 4000;

	async function pollVc() {
		try {
			const body = (await aiJson<{ segments?: Array<{ segment_id?: number; now?: { vc?: number } }> }>('/api/forecast/forecast/segments', {}, 30_000)) ?? {};
			const m = new Map<number, number>();
			for (const r of body.segments ?? []) if (typeof r.segment_id === 'number' && typeof r.now?.vc === 'number') m.set(r.segment_id, r.now.vc);
			vcById = m;
			lastSignature = '';
			liveClock.mark('forecast');
		} catch {
			// no forecast service: the labels carry the speed only
		} finally {
			vcTried = true;
		}
	}

	/** Fixed-endpoint POST to the oracle hot cache (ids come from the
	 * shared segment store — never operator input). */
	async function pollObservations() {
		if (!ctx || !active) return;
		const ids = godsEye.segments.map((s) => s.segmentId);
		if (!ids.length) return;
		try {
			const res = await fetch(`${ORACLE_V1}/traffic/live`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ segment_ids: ids }),
				signal: AbortSignal.timeout(6000),
			});
			if (!res.ok) throw new Error(`${res.status}`);
			const body = (await res.json()) as { observations?: unknown; emulated_observations?: unknown };
			obsById = planeOf(body.observations);
			// an oracle before C-P has no emulated plane: nothing to draw from it
			emuById = planeOf(body.emulated_observations);
			obsFeed = obsById.size || emuById.size ? 'ok' : 'empty';
			if (obsFeed === 'ok') liveClock.mark('flow');
		} catch {
			// Leave last-good observations on the canvas: each one greys out by
			// itself once it is older than STALE_OBS_SEC; the hint degrades.
			obsFeed = obsById.size || emuById.size ? 'ok' : 'down';
		}
	}

	/** Gated: never overlaps itself, never runs while the tab is hidden. */
	const poll = () => void gate('flow', pollObservations);

	/**
	 * Redraw on a data change (the observations, the segment set, the view).
	 * The GEOMETRY is rebuilt only when the PICTURE changes — a segment's
	 * style (its ramp step, its basis, whether it has data), the view's dim,
	 * the kind filter or the theme's inks. A reading that moves without
	 * changing the picture (a speed, an age, a provenance) only rewrites the
	 * pick texts in place: removing and re-adding every segment made Cesium
	 * rebuild the draped primitives, and it DISCARDS a primitive still being
	 * built when the next change lands, so on a loaded box an 8 s poll could
	 * keep the network off the map for tens of seconds (review r1).
	 */
	function draw() {
		if (!ctx || !active) return;
		if (!vcTried && Date.now() - activatedAt < VC_WAIT_MS) return;
		const { cesium, viewer } = ctx;
		const segments = godsEye.segments;
		const now = Date.now();
		const fresh = (o: LiveObservation | undefined) =>
			!!o && Number.isFinite(o.timestamp_ms) && (now - o.timestamp_ms) / 1000 <= STALE_OBS_SEC;
		const planeSig = (plane: Map<number, LiveObservation>) =>
			[...plane.entries()].map(([id, o]) => [
				id,
				Math.round(o.congestion_idx * 20) / 20,
				Math.round(o.speed_kmh),
				o.data_quality ?? '',
				fresh(o),
			]);
		const view = chromeOf(ctx) === 'v2' ? viewOf(ctx) : null;
		const dim = view ? flowDim(view) : null;
		// v2: a kind filter that leaves roads out hides the whole network (SPEC §5.3)
		const hidden = !!view && !kindShown(view, 'segment');
		const sig = JSON.stringify([
			segments.map((s) => `${s.segmentId}${s.geometryBasis === 'schematic' ? 's' : ''}`),
			planeSig(obsById),
			planeSig(emuById),
			dim ? [dim.alpha, dim.thinPx] : null,
			hidden,
		]);
		if (sig === lastSignature) return;
		lastSignature = sig;

		const neutral = withAlpha(cssVar('--v-ink-4') ?? 'slategray', 0.75);
		// the dark casing / dash gap: the canvas ink, slightly translucent
		const casingCss = withAlpha(cssVar('--v-canvas') ?? 'black', 0.85);
		// the ramp's inks, read once per draw (a theme switch changes the picture)
		const bands = new Map<number, string>();
		const legacyInk = (idx: number) => {
			const band = idx <= 0.2 ? 0 : idx <= 0.4 ? 1 : idx <= 0.6 ? 2 : idx <= 0.8 ? 3 : 4;
			let css = bands.get(band);
			if (css === undefined) bands.set(band, (css = rampColor(idx)));
			return css;
		};
		let coloured = 0;
		let simulated = 0;
		let emulatedCount = 0;
		let stale = 0;
		let osmCount = 0;
		let schematicCount = 0;
		const rows: Array<{ seg: (typeof segments)[number]; obs: LiveObservation | undefined; schematic: boolean; style: unknown; description: string; rampIdx: number | null }> = [];

		for (const seg of segments) {
			if (seg.coordinates.length < 2) continue;
			const liveRaw = obsById.get(seg.segmentId);
			const emuRaw = emuById.get(seg.segmentId);
			const live = fresh(liveRaw) ? liveRaw : undefined;
			const emu = fresh(emuRaw) ? emuRaw : undefined;
			// A fresh showcase row colours its segment (badged EMULATED);
			// otherwise the ingest plane's row does.
			const obs = emu ?? live;
			const emulated = !!emu;
			const raw = obs ?? liveRaw ?? emuRaw;
			if (raw && !obs) stale++;
			const synthetic = obs?.data_quality === 'synthetic' || emulated;
			const schematic = seg.geometryBasis === 'schematic';
			if (schematic) schematicCount++;
			else osmCount++;
			if (obs) coloured++;
			if (synthetic) simulated++;
			if (emulated) emulatedCount++;

			const name = seg.roadName ?? raw?.road_name ?? liveRaw?.road_name ?? emuRaw?.road_name ?? `segment ${seg.segmentId}`;
			const road = `${name}${schematic ? ' · SCHEMATIC geometry (straight chord between junctions, not the road’s true shape)' : ' · OSM-traced'}`;
			const ageSec = raw ? Math.max(0, Math.round((now - raw.timestamp_ms) / 1000)) : null;
			const planeProvenance = (o: LiveObservation | undefined) =>
				o?.data_quality === 'synthetic'
					? 'SIMULATED FEED (synthetic signal-ingress rows)'
					: o?.data_quality === 'anomalous'
						? 'flagged anomalous'
						: `source ${o?.source ?? '?'}`;
			const provenance = emulated
				? 'EMULATED · SIMULATED FEED (event-emulator showcase run)'
				: planeProvenance(obs);
			// the ingest plane's own reading stays on the card under a showcase row
			const besides =
				emulated && live
					? ` · ingest plane: ${live.speed_kmh.toFixed(1)} km/h, ${(live.congestion_idx * 100).toFixed(0)}% (${planeProvenance(live)})`
					: '';
			const description = dim
				? v2Description(name, schematic, obs, raw, ageSec, emulated, live)
				: obs
					? `${road} · ${obs.speed_kmh.toFixed(1)} km/h · congestion ${(obs.congestion_idx * 100).toFixed(0)}% · ${provenance} · ${ageSec}s ago${besides}`
					: raw
						? `${road} · NO DATA — last observation ${ageSec}s ago (older than ${STALE_OBS_SEC}s, neutral)`
						: `${road} · NO DATA — no observation in the hot cache (neutral)`;
			// what the segment LOOKS like: its ink (the ramp step), its basis, whether it has data
			// chrome v2 colours a road by its V/C when the forecast service has it (else by the live congestion index)
			const vc = vcById.get(seg.segmentId);
			const rampIdx = obs ? (vc != null ? vcRampIdx(vc) : obs.congestion_idx) : null;
			let style: unknown = null;
			if (obs) {
				if (dim) {
					const ink = vcInk(rampIdx ?? obs.congestion_idx);
					style = [ink.stop, ink.color, ink.width];
				} else style = legacyInk(obs.congestion_idx);
			}
			rows.push({ seg, obs, schematic, style, description, rampIdx });
		}

		// the moving dots and the road names: every road with a current reading (none while the filter hides roads)
		motion?.update(
			hidden
				? []
				: rows
						.filter((r) => r.obs)
						.map(
							(r): FlowRoad => ({
								segmentId: r.seg.segmentId,
								name: r.seg.roadName ?? r.obs?.road_name ?? `segment ${r.seg.segmentId}`,
								coordinates: r.seg.coordinates,
								oneway: r.seg.oneway === true,
								speedKmh: r.obs!.speed_kmh,
								congestion: r.obs!.congestion_idx,
								vc: vcById.get(r.seg.segmentId) ?? null,
								simulated: r.obs!.data_quality === 'synthetic' || r.obs!.origin === 'emulated',
								ink: vcInk(r.rampIdx ?? r.obs!.congestion_idx).color,
							}),
						),
			ops.lang ?? 'en',
		);

		// the STRUCTURE (segments, basis, the view's dim, the filter, the inks) and the PICTURE (+ each segment's step)
		const structure = JSON.stringify([rows.map((r) => [r.seg.segmentId, r.schematic ? 1 : 0]), dim ? [dim.alpha, dim.thinPx] : null, hidden, neutral, casingCss]);
		const picture = JSON.stringify([structure, rows.map((r) => r.style)]);
		// Chrome v2: a READING that changes the picture waits while a draped build is
		// still in flight (Cesium's own signal: the data sources are not all updated),
		// so a loaded box finishes the build it has instead of throwing it away on
		// every poll; at most FLOW_V2.deferMaxMs after the last redraw. A change of
		// structure, the first picture with data, and the legacy chrome never wait.
		const defer =
			!!view &&
			!hidden &&
			picture !== lastPicture &&
			structure === lastStructure &&
			lastHadData &&
			viewer.clockViewModel?.canAnimate === false &&
			now - lastRedrawAt < FLOW_V2.deferMaxMs;
		if ((picture === lastPicture || defer) && !hidden) {
			// the same picture (or one that waits): the pick texts move in place (one collection event, no rebuild);
			// while a new picture waits, a segment whose step changed keeps the text of the step it still shows
			if (defer) lastSignature = ''; // look again on the next tick
			viewer.entities.suspendEvents?.();
			try {
				for (const r of rows) {
					const id = `${TRAFFIC_FLOW_PICK_PREFIX}${r.seg.segmentId}`;
					if (descriptions.get(id) === r.description) continue;
					if (drawnStyles.get(id) !== JSON.stringify(r.style)) continue;
					const entity = viewer.entities.getById(id) as { description?: unknown } | undefined;
					if (entity) entity.description = r.description;
					descriptions.set(id, r.description);
				}
			} finally {
				viewer.entities.resumeEvents?.();
			}
		} else {
			lastPicture = picture;
			lastStructure = structure;
			lastHadData = rows.some((r) => r.obs);
			lastRedrawAt = now;
			for (const id of entityIds) viewer.entities.removeById(id);
			entityIds.length = 0;
			descriptions.clear();
			drawnStyles.clear();
			if (!hidden) {
				const casing = cesium.Color.fromCssColorString(casingCss);
				for (const { seg, obs, schematic, style, description, rampIdx } of rows) {
					// ground positions: the draped line takes its height from the surface
					const positions = groundPath(cesium, seg.coordinates);
					let width: number;
					let material: unknown;
					if (dim) {
						({ width, material } = v2Line(cesium, obs, schematic, dim, rampIdx));
					} else {
						width = obs ? FLOW_WIDTH.coloured : FLOW_WIDTH.noData;
						const colour = cesium.Color.fromCssColorString(obs ? legacyInk(obs.congestion_idx) : neutral);
						// A schematic chord is not the road's true shape: dashed, never solid
						// (its gaps carry the dark casing so the rhythm reads on aerial
						// imagery); a coloured real road wears the casing as an outline.
						material = schematic
							? new cesium.PolylineDashMaterialProperty({ color: colour, gapColor: obs ? casing : undefined, dashLength: 14 })
							: obs && cesium.PolylineOutlineMaterialProperty
								? new cesium.PolylineOutlineMaterialProperty({ color: colour, outlineColor: casing, outlineWidth: FLOW_WIDTH.casing })
								: colour;
					}
					const entity = viewer.entities.add({
						id: `${TRAFFIC_FLOW_PICK_PREFIX}${seg.segmentId}`,
						polyline: drapedPolyline(cesium, { positions, width, material, z: DRAPE_Z.flow }),
						description,
					});
					entityIds.push(entity.id);
					descriptions.set(entity.id, description);
					drawnStyles.set(entity.id, JSON.stringify(style));
				}
			}
		}

		if (hidden) {
			// the count stays the truth about the feed; nothing is drawn
			detail = { coloured, segments: 0, filtered: rows.length };
			hint = `${coloured}/${rows.length} segments on the congestion ramp · hidden by the kind filter`;
			return;
		}
		detail = {
			coloured,
			segments: entityIds.length,
			simulated,
			emulated: emulatedCount,
			stale,
			osm: osmCount,
			schematic: schematicCount,
		};
		const tag =
			(simulated > 0 && simulated === coloured ? ' · SIMULATED FEED' : simulated > 0 ? ` · ${simulated} SIMULATED` : '') +
			(emulatedCount > 0 ? ` · ${emulatedCount} EMULATED` : '');
		const basis = schematicCount ? ` · ${osmCount} OSM-traced · ${schematicCount} schematic (dashed)` : osmCount ? ` · ${osmCount} OSM-traced` : '';
		hint =
			obsFeed === 'down'
				? `traffic/live unreachable — network neutral (${entityIds.length} segments)${basis}`
				: obsFeed === 'empty'
					? `no observations — network neutral (${entityIds.length} segments)${basis}`
					: `${coloured}/${entityIds.length} segments on the congestion ramp${tag}${stale ? ` · ${stale} stale (NO DATA)` : ''}${basis}`;
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
			if (ctx && !motion) motion = createFlowMotion(ctx);
			activatedAt = Date.now();
			poll();
			void pollVc().then(() => draw());
			draw();
			pollTimer = setInterval(poll, 8000);
			drawTimer = setInterval(() => draw(), 2000);
			vcTimer = setInterval(() => void pollVc(), 300_000);
		},
		deactivate() {
			active = false;
			if (pollTimer) clearInterval(pollTimer);
			if (drawTimer) clearInterval(drawTimer);
			if (vcTimer) clearInterval(vcTimer);
			pollTimer = drawTimer = vcTimer = null;
			motion?.destroy();
			motion = null;
			if (ctx) for (const id of entityIds) ctx.viewer.entities.removeById(id);
			entityIds.length = 0;
			lastSignature = '';
			lastPicture = '';
			lastStructure = '';
			lastHadData = false;
			descriptions.clear();
			drawnStyles.clear();
			detail = {};
		},
		refresh() {
			// a refresh redraws the whole picture
			lastSignature = '';
			lastPicture = '';
			lastStructure = '';
			void godsEye.pollSegments(true);
			poll();
			draw();
		},
		restyle() {
			draw();
		},
		handlePick(pickId) {
			return pickId.startsWith(TRAFFIC_FLOW_PICK_PREFIX);
		},
		urnOf(pickId) {
			const id = pickId.slice(TRAFFIC_FLOW_PICK_PREFIX.length);
			return /^\d+$/.test(id) ? `segment:${id}` : null;
		},
		coverageStats() {
			return {
				// The chip counts COLOURED segments (a hairline is an absence of data).
				count: detail.coloured ?? 0,
				loading: godsEye.segmentsFeed.status === 'empty',
				hint,
				error: obsFeed === 'down' ? 'traffic/live feed down' : null,
				detail: ctx ? { ...detail, dots: motion?.dots ?? 0, vc: vcById.size, ...drapeAudit(ctx.viewer, entityIds) } : detail,
				via: 'traffic/live',
			};
		},
		destroy() {
			this.deactivate();
		},
	};
}

export const trafficFlowLayer: GodsEyeLayer = {
	id: 'flow',
	name: 'Traffic flow (congestion ramp)',
	label: 'FLOW',
	requiresKeyId: null,
	pickPrefix: TRAFFIC_FLOW_PICK_PREFIX,
	defaultOn: true,
	group: 'traffic',
	create: createTrafficFlowLayer,
};
