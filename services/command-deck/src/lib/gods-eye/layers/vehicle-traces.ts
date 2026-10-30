/**
 * vehicle-traces layer — earmarked vehicles with traces, camera hops and badges.
 *
 * Feed: the canvas store's vehicles (city registry vehicle entities, or
 * GET /api/v1/vehicles as the fallback). Traces come from the registry's
 * sighting entities — the snapshot carries the last 8 reads of every
 * FLAGGED vehicle — so a healthy city picture costs no per-vehicle request;
 * only when the registry does not serve sightings does the layer fall back
 * to fetchVehicleTrace (data.ts: the timed trace, else the last 8
 * sightings). Each trace draws as a polyline plus NUMBERED CAMERA HOPS
 * (1 = oldest read), each hop naming the ANPR reader that saw the plate —
 * the path an operator can follow.
 *
 * Earmark colors: watch → data accent, flagged → act orange, unearmarked →
 * dim ink. Every emulated read carries its source ('emulated_anpr' today)
 * and the marker label shows an EMULATED badge — the ethics rail (C6):
 * synthetic reads are always labelled; vehicles only, never persons; the
 * plate is MASKED (MH47EM•••1) unless a named duty officer is on console.
 *
 * Pick ids: `veh:mark-<vehicleId>`, `veh:trace-<vehicleId>` → URN
 * `vehicle:<id>`; `veh:hop-<vehicleId>-<n>` → the hop's `sighting:<id>`
 * when the source names it, else the vehicle.
 *
 * Every time reads in IST (the city's clock, never the browser's zone or
 * an ISO-Z string). A vehicle without an active earmark has no lawful
 * basis for its individual reads (C6): the oracle withholds them, nothing
 * is drawn, and the chip hint says 'reads withheld: no active earmark
 * (C6)'. The pursuit overlay already labels the pursued vehicle's newest
 * sighting, so its marker here keeps the dot but drops the duplicate
 * plate label (two labels on one spot read as noise).
 *
 * DRAPED (layers/draping.ts): each trace is a ground polyline on terrain and
 * the photoreal 3D tiles, above the corridor spines; marks, hops and their
 * labels are clamped to the ground and never hidden by a building. Every
 * label stands on the translucent canvas plate; a hop label is the first to
 * give way in the canvas's declutter (after the vehicle's own mark label,
 * and under any e-challan / sighting pin at the same camera site).
 */

import { fetchVehicleTrace, type TraceHop, type VehicleRecord, type VehicleTrace } from '../data';
import { feedError, feedHint, godsEye } from '../store.svelte';
import { istDayTime, istStamp } from '../hud/format';
import { ops } from '$lib/ops/store.svelte';
import { pageHidden } from '$lib/ops/client';
import { displayPlate } from '../plates';
import type { GodsEyeLayer, GodsEyeLayerContext, GodsEyeLayerInstance } from '../registry';
import { canvasFont, cssVar, withAlpha } from '../theme';
import { DRAPE_Z, clampedDot, clampedLabel, drapeAudit, drapedPolyline, ground, groundPath } from './draping';
import { kindIcon } from '$lib/design/icons';
import { chromeOf, inWindow, kindShown, kindsSignature, viewOf, type MapView } from '../hud/map/view';
import { PIN, mapInk, markerBillboard, tagMarker, tagTrack, type MarkerMeta } from '../hud/map/symbols';

export const VEHICLE_TRACES_PICK_PREFIX = 'veh:';

/**
 * Earmark colours from the tokens (CSS colour strings for
 * fromCssColorString call sites): a FLAGGED plate is a human-must-act
 * surface (act orange); WATCH sits at the data accent — neither competes
 * with the band ladder's amber. No hex: theme.cssVar reads live tokens,
 * CSS colour-keyword fallbacks only.
 */
function earmarkColor(state: 'watch' | 'flagged' | null): string {
	if (state === 'flagged') return cssVar('--v-act') ?? 'orange';
	if (state === 'watch') return cssVar('--v-data') ?? 'cyan';
	return cssVar('--v-ink-3') ?? 'lightgray';
}

const MAX_TRACES = 12; // trace fetches per refresh — bounded on purpose

/** Chrome v2: the latest pass is the reads within this of the newest (SPEC §5.3). */
export const LATEST_PASS_MS = 30 * 60_000;
/** Chrome v2: the longest trace read for a time window (s). */
const WINDOW_TRACE_MAX_SEC = 24 * 3600;
/** Chrome v2 track widths (px): the alert line over its casing (SPEC §5.3). */
export const TRACK_WIDTH = { line: 3, casing: 7 } as const;

/** The selected vehicle (a vehicle URN among the selection), or null. */
export function selectedVehicle(view: MapView): string | null {
	const urns = view.selection ? [view.selection, ...view.items] : [...view.items];
	const hit = urns.find((u) => u.startsWith('vehicle:'));
	return hit ? hit.slice('vehicle:'.length) : null;
}

/**
 * The reads a v2 track draws (SPEC §5.3): with a window, the reads inside
 * it; without one, the latest pass — the reads within 30 min of the newest.
 * Chronological; reads with no time are kept only without a window.
 */
export function trackHops(hops: readonly TraceHop[], window: MapView['window']): TraceHop[] {
	const timed = [...hops].sort((a, b) => (a.t ?? 0) - (b.t ?? 0) || a.seq - b.seq);
	if (window) return timed.filter((h) => h.t != null && inWindow(h.t, window));
	const newest = Math.max(...timed.map((h) => h.t ?? Number.NEGATIVE_INFINITY));
	if (!Number.isFinite(newest)) return timed;
	return timed.filter((h) => h.t == null || newest - h.t <= LATEST_PASS_MS);
}
const TRACE_WINDOW_SEC = 900;

/** A read's time as the control room says it: HH:MM:SS IST today, '22 Oct 21:40 IST' before. */
function ist(t: number | null): string {
	return t != null ? `${istStamp(t)} IST` : '—';
}

/** An ISO date-time (retention_until) in IST, day included. */
function istIso(v: string | null): string {
	if (!v) return '—';
	const t = Date.parse(v);
	return Number.isFinite(t) ? `${istDayTime(t)} IST` : v;
}

function hopDescription(plate: string, h: TraceHop, of: number): string {
	return `hop ${h.seq}/${of} · ${plate} · camera ${h.cameraId ?? '—'} · ${ist(h.t)}${
		h.speedKmh != null ? ` · ${Math.round(h.speedKmh)} km/h` : ''
	} · source ${h.source ?? '—'}${h.source === 'emulated_anpr' ? ' (EMULATED)' : ''}`;
}

function createVehicleTracesLayer(): GodsEyeLayerInstance {
	let ctx: GodsEyeLayerContext | null = null;
	let active = false;
	let timer: ReturnType<typeof setInterval> | null = null;
	const entityIds: string[] = [];
	/** pick id → URN (hops name their sighting when the source does). */
	const urns = new Map<string, string>();
	let lastSignature = '';
	/** Bumped per redraw: an older async draw stops before adding anything. */
	let generation = 0;
	let tracedCount = 0;
	let hopCount = 0;
	let traceVia = 'none';
	/** Vehicles whose individual reads the oracle withheld (no active earmark, C6). */
	let withheldCount = 0;

	function clearEntities() {
		if (ctx) for (const id of entityIds) ctx.viewer.entities.removeById(id);
		entityIds.length = 0;
		urns.clear();
	}

	function track(id: string, urn: string) {
		entityIds.push(id);
		urns.set(id, urn);
	}

	async function draw(): Promise<void> {
		if (!ctx || !active) return;
		const { cesium, viewer } = ctx;
		const vehicles = godsEye.vehicles;
		const officer = ops.officerOn;
		const registryTraces = new Map<string, VehicleTrace>();
		for (const v of vehicles) {
			const t = godsEye.registryTrace(v.vehicleId);
			if (t) registryTraces.set(v.vehicleId, t);
		}
		const v2 = chromeOf(ctx) === 'v2';
		const view = v2 ? viewOf(ctx) : null;
		const sig = JSON.stringify([
			vehicles.map((v) => [
				v.vehicleId,
				v.earmarkState,
				v.lastSighting?.lon,
				v.lastSighting?.lat,
				v.lastSighting?.t,
				registryTraces.get(v.vehicleId)?.hops.map((h) => h.sightingId ?? h.t) ?? null,
			]),
			godsEye.vehiclesFeed.status,
			officer,
			ops.interception?.latestSighting ? ops.interception.vehicleId : null,
			view ? [selectedVehicle(view), view.window, kindsSignature(view)] : null,
		]);
		if (sig === lastSignature) return;
		// Trace reads wait for a visible page; the next tick retries.
		if (pageHidden()) return;
		lastSignature = sig;
		const gen = ++generation;

		clearEntities();
		tracedCount = 0;
		hopCount = 0;
		withheldCount = 0;
		traceVia = registryTraces.size ? 'city' : 'none';
		if (view) {
			await drawV2(view, registryTraces, gen);
			return;
		}
		const canvasInk = cesium.Color.fromCssColorString(cssVar('--v-canvas') ?? 'black');
		// The pursuit overlay labels this vehicle's newest sighting itself.
		const pursued = ops.interception?.latestSighting ? ops.interception.vehicleId : null;
		// A translucent canvas plate behind labels: legible over any basemap.
		const labelPlate = cesium.Color.fromCssColorString(withAlpha(cssVar('--v-canvas') ?? 'black', 0.72));

		for (const v of vehicles) {
			const color = earmarkColor(v.earmarkState);
			const badge = v.earmarkState === 'watch' ? 'WATCH' : v.earmarkState === 'flagged' ? 'FLAGGED' : '';
			const emulated = v.lastSighting?.source === 'emulated_anpr';
			const plate = displayPlate(v.plate, officer) ?? v.vehicleId.slice(0, 8);

			if (v.lastSighting) {
				const labelled = v.vehicleId !== pursued;
				const entity = viewer.entities.add({
					id: `${VEHICLE_TRACES_PICK_PREFIX}mark-${v.vehicleId}`,
					position: ground(cesium, v.lastSighting.lon, v.lastSighting.lat),
					billboard: clampedDot(cesium, {
						pixelSize: v.earmarkState === 'flagged' ? 12 : 8,
						color: cesium.Color.fromCssColorString(color),
						outlineColor: canvasInk,
						outlineWidth: 2,
					}),
					...(labelled
						? {
								label: clampedLabel(cesium, {
									text: `${plate}${badge ? ` ·${badge}` : ''}${emulated ? ' ·EMULATED' : ''}`,
									font: canvasFont('13px var(--v-font-ui)'),
									fillColor: cesium.Color.fromCssColorString(cssVar('--v-ink-1') ?? 'white'),
									outlineColor: canvasInk,
									outlineWidth: 2,
									style: 2,
									showBackground: true,
									backgroundColor: labelPlate,
									backgroundPadding: new cesium.Cartesian2(5, 3),
									verticalOrigin: -1,
									pixelOffset: new cesium.Cartesian2(0, 12),
									// declutter: a watch plate reads up close, a flagged one from the city view
									distanceDisplayCondition: new cesium.DistanceDisplayCondition(0, v.earmarkState === 'flagged' ? 30_000 : 12_000),
								}),
							}
						: {}),
					description: `vehicle ${plate} · earmark ${v.earmarkState ?? 'none'}${
						v.lawfulBasis ? ` · lawful basis ${v.lawfulBasis}` : ''
					} · retention until ${istIso(v.retentionUntil)} · last seen ${ist(v.lastSighting.t)} at camera ${
						v.lastSighting.cameraId ?? '—'
					}${v.lastSighting.hit ? ` · HIT ${v.lastSighting.hit}` : ''} · source ${v.lastSighting.source ?? '—'}${
						emulated ? ' (EMULATED)' : ''
					}${officer ? '' : ' · plate masked (no named duty officer)'}`,
				});
				track(entity.id, `vehicle:${v.vehicleId}`);
			}
		}

		// Traces + numbered camera hops for the most recent vehicles (bounded).
		const traced = vehicles
			.filter((v) => v.lastSighting)
			.sort((a, b) => (b.lastSighting?.t ?? 0) - (a.lastSighting?.t ?? 0))
			.slice(0, MAX_TRACES);
		for (const v of traced) {
			let trace = registryTraces.get(v.vehicleId) ?? null;
			if (!trace) {
				// The registry serves hops for FLAGGED vehicles only; a watch
				// vehicle (or a degraded registry) reads its own trace.
				try {
					trace = await fetchVehicleTrace(v.vehicleId, TRACE_WINDOW_SEC, AbortSignal.timeout(6000));
				} catch {
					continue; // trace + sightings both down — the marker stands alone
				}
				if (!ctx || !active || gen !== generation) return; // superseded mid-flight
				if (trace.via === 'withheld') {
					withheldCount++;
					continue; // C6: no lawful basis to disclose its reads — nothing to draw
				}
				if (traceVia === 'none') traceVia = trace.via;
			}
			if (trace.coordinates.length < 2) continue;
			const plate = displayPlate(v.plate, officer) ?? v.vehicleId.slice(0, 8);
			const color = cesium.Color.fromCssColorString(earmarkColor(v.earmarkState));
			const line = viewer.entities.add({
				id: `${VEHICLE_TRACES_PICK_PREFIX}trace-${v.vehicleId}`,
				polyline: drapedPolyline(cesium, {
					positions: groundPath(cesium, trace.coordinates),
					width: 3,
					material: color,
					z: DRAPE_Z.trace,
				}),
				description: `trace ${plate} · ${
					trace.via === 'trace' ? `window ${TRACE_WINDOW_SEC}s` : `last ${trace.hops.length} sightings`
				} · ${trace.hops.length} camera hops · newest ${ist(trace.latestT)}${trace.status ? ` · ${trace.status}` : ''}${
					trace.disclosure ? ` · disclosed under ${trace.disclosure.replace(/_/g, ' ')}` : ''
				} · source ${trace.source ?? '—'}${
					trace.source === 'emulated_anpr' ? ' (EMULATED)' : ''
				}`,
			});
			track(line.id, `vehicle:${v.vehicleId}`);
			for (const h of trace.hops) {
				const hop = viewer.entities.add({
					id: `${VEHICLE_TRACES_PICK_PREFIX}hop-${v.vehicleId}-${h.seq}`,
					position: ground(cesium, h.lon, h.lat),
					billboard: clampedDot(cesium, {
						pixelSize: 7,
						color,
						outlineColor: canvasInk,
						outlineWidth: 1,
					}),
					label: clampedLabel(cesium, {
						text: `${h.seq}${h.cameraId ? ` ${h.cameraId}` : ''}`,
						font: canvasFont('12px var(--v-font-ui)'),
						fillColor: cesium.Color.fromCssColorString(cssVar('--v-ink-1') ?? 'white'),
						outlineColor: canvasInk,
						outlineWidth: 2,
						style: 2,
						// on the canvas plate (legible over the city and the lines through
						// it); the canvas's declutter hides it under an e-challan / sighting
						// pin standing on the same camera site — the pin names the site
						showBackground: true,
						backgroundColor: labelPlate,
						backgroundPadding: new cesium.Cartesian2(4, 2),
						verticalOrigin: 1, // label above the hop dot
						pixelOffset: new cesium.Cartesian2(0, -8),
						// hop numbers up close only (the overview keeps the trace line)
						distanceDisplayCondition: new cesium.DistanceDisplayCondition(0, 4500),
					}),
					description: hopDescription(plate, h, trace.hops.length),
				});
				track(hop.id, h.sightingId ? `sighting:${h.sightingId}` : `vehicle:${v.vehicleId}`);
				hopCount++;
			}
			tracedCount++;
		}
	}

	/**
	 * Chrome v2 (SPEC §5.3): every earmarked vehicle is the offset PIN — its
	 * tip on the last read, its head 46 px up-left, the ring red for a
	 * watchlisted or stolen vehicle — so the camera under it stays visible.
	 * Only the SELECTED vehicle shows its track: the reads in time order, a
	 * 3 px --v-map-alert line over a 7 px casing (the canvas adds direction
	 * arrows on spans over 60 px), the latest pass without a window, the
	 * window's reads with one; each read carries its label (camera id in the
	 * identifier face, time in Inter).
	 */
	async function drawV2(view: MapView, registryTraces: Map<string, VehicleTrace>, gen: number): Promise<void> {
		if (!ctx) return;
		const { cesium, viewer } = ctx;
		const officer = ops.officerOn;
		for (const v of godsEye.vehicles) {
			if (!v.lastSighting) continue;
			const plate = displayPlate(v.plate, officer) ?? v.vehicleId.slice(0, 8);
			const earmarked = v.earmarkState === 'watch' || v.earmarkState === 'flagged' || !!v.lawfulBasis;
			const meta: MarkerMeta = {
				urn: `vehicle:${v.vehicleId}`,
				kind: 'vehicle',
				glyph: kindIcon('vehicle'),
				shape: 'pin',
				role: earmarked ? 'alert' : 'marker',
				t: v.lastSighting.t,
				label: [{ id: plate }],
				labelLock: !officer,
				labelWhen: 'selected',
				labelPrefer: ['l', 't', 'tl', 'r', 'b'],
				labelPriority: 100,
				click: { x: PIN.dx, y: PIN.dy },
				radius: PIN.head + 3,
			};
			const emulated = v.lastSighting.source === 'emulated_anpr';
			const entity = viewer.entities.add({
				id: `${VEHICLE_TRACES_PICK_PREFIX}mark-${v.vehicleId}`,
				position: ground(cesium, v.lastSighting.lon, v.lastSighting.lat),
				billboard: markerBillboard(cesium, meta),
				description: `Vehicle ${plate}${v.lawfulBasis ? `, ${v.lawfulBasis.replace(/_/g, ' ')}` : ''}${v.earmarkState ? ` (${v.earmarkState})` : ''}. Last read ${ist(v.lastSighting.t)} at camera ${
					v.lastSighting.cameraId ?? 'unknown'
				}${emulated ? ', emulated' : ''}. Retained until ${istIso(v.retentionUntil)}.${officer ? '' : ' Registration mark masked until a duty officer is named.'}`,
			});
			tagMarker(entity, meta);
			track(entity.id, `vehicle:${v.vehicleId}`);
		}

		const vehicleId = selectedVehicle(view);
		const vehicle = vehicleId ? godsEye.vehicles.find((x) => x.vehicleId === vehicleId) : null;
		if (!vehicleId || !vehicle) return;
		let trace = registryTraces.get(vehicleId) ?? null;
		if (!trace || (view.window && trace.hops.every((h) => h.t == null || h.t > view.window![0]))) {
			const span = view.window ? Math.min(WINDOW_TRACE_MAX_SEC, Math.ceil((Date.now() - view.window[0]) / 1000) + 60) : 3600;
			try {
				const read = await fetchVehicleTrace(vehicleId, Math.max(TRACE_WINDOW_SEC, span), AbortSignal.timeout(6000));
				if (!ctx || !active || gen !== generation) return; // superseded mid-flight
				if (read.via === 'withheld') {
					withheldCount++;
					return; // C6: no lawful basis to disclose its reads
				}
				if (!trace || read.hops.length >= trace.hops.length) trace = read;
				traceVia = trace.via;
			} catch {
				if (!trace) return; // trace and sightings both down: the pin stands alone
			}
		}
		const hops = trackHops(trace.hops, view.window);
		if (hops.length === 0) return;
		const now = Date.now();
		const plate = displayPlate(vehicle.plate, officer) ?? vehicleId.slice(0, 8);
		const coords = hops.map((h) => [h.lon, h.lat] as [number, number]);
		// a kind filter that leaves vehicles out hides the track (the pass hides the pin and its arrows)
		if (coords.length >= 2 && kindShown(view, 'vehicle')) {
			// one draped line: the 3 px alert core inside its 7 px casing (an
			// outline material, so the core always paints over the casing)
			const alert = cesium.Color.fromCssColorString(mapInk('alert'));
			const casing = cesium.Color.fromCssColorString(mapInk('casing'));
			// Cesium's outline material takes BOTH edges together: interior = width − outlineWidth
			const outlineW = TRACK_WIDTH.casing - TRACK_WIDTH.line;
			const line = viewer.entities.add({
				id: `${VEHICLE_TRACES_PICK_PREFIX}trace-${vehicleId}`,
				polyline: drapedPolyline(cesium, {
					positions: groundPath(cesium, coords),
					width: cesium.PolylineOutlineMaterialProperty ? TRACK_WIDTH.casing : TRACK_WIDTH.line,
					material: cesium.PolylineOutlineMaterialProperty
						? new cesium.PolylineOutlineMaterialProperty({ color: alert, outlineColor: casing, outlineWidth: outlineW })
						: alert,
					z: DRAPE_Z.trace,
				}),
				description: `Track of ${plate}: ${hops.length} reads${view.window ? ' in the window' : ' in the latest pass'}, newest ${ist(hops[hops.length - 1].t)}.`,
			});
			tagTrack(line, { urn: `vehicle:${vehicleId}`, coords });
			track(line.id, `vehicle:${vehicleId}`);
		}
		hops.forEach((h, i) => {
			const meta: MarkerMeta = {
				urn: h.sightingId ? `sighting:${h.sightingId}` : `vehicle:${vehicleId}`,
				kind: 'sighting',
				glyph: kindIcon('sighting'),
				shape: 'dot',
				r: 3,
				role: 'alert',
				t: h.t,
				// the time alone today, dated ("23 Oct 22:08") for an older read (the formatter's stamp)
				label: h.cameraId ? [{ id: h.cameraId }, ...(h.t != null ? [{ time: h.t, anchor: now }] : [])] : h.t != null ? [{ time: h.t, anchor: now }] : null,
				labelWhen: 'always',
				labelPrefer: ['br', 'bl', 'tr', 'tl', 'b', 'r', 'l', 't'],
				// the newest read wins the space
				labelPriority: 50 + i,
				radius: 11,
			};
			const hop = viewer.entities.add({
				id: `${VEHICLE_TRACES_PICK_PREFIX}hop-${vehicleId}-${h.seq}`,
				position: ground(cesium, h.lon, h.lat),
				billboard: markerBillboard(cesium, meta),
				description: `Read ${i + 1} of ${hops.length}: ${plate} at camera ${h.cameraId ?? 'unknown'}, ${ist(h.t)}${
					h.speedKmh != null ? `, ${Math.round(h.speedKmh)} km/h` : ''
				}${h.source === 'emulated_anpr' ? ', emulated' : ''}.`,
			});
			tagMarker(hop, meta);
			track(hop.id, meta.urn as string);
			hopCount++;
		});
		tracedCount = 1;
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
			void draw();
			timer = setInterval(() => void draw(), 4000);
		},
		restyle() {
			void draw();
		},
		deactivate() {
			active = false;
			generation++;
			if (timer) clearInterval(timer);
			timer = null;
			clearEntities();
			lastSignature = '';
		},
		refresh() {
			lastSignature = '';
			void godsEye.pollVehicles();
			void draw();
		},
		handlePick(pickId) {
			return pickId.startsWith(VEHICLE_TRACES_PICK_PREFIX);
		},
		urnOf(pickId) {
			return urns.get(pickId) ?? null;
		},
		coverageStats() {
			return {
				// The chip counts VEHICLES on the canvas (each with its hops).
				count: godsEye.vehicles.filter((v) => v.lastSighting).length,
				loading: godsEye.vehiclesFeed.status === 'empty' && godsEye.vehiclesFeed.updatedAt === 0,
				hint:
					godsEye.vehiclesFeed.status === 'not-deployed'
						? '/api/v1/vehicles 404 — watchlist-anpr stream pending'
						: (feedHint(godsEye.vehiclesFeed) ??
							`${godsEye.vehicles.length} earmarked vehicles · ${tracedCount} traced · ${hopCount} camera hops (${traceVia})${
								withheldCount ? ` · ${withheldCount} reads withheld: no active earmark (C6)` : ''
							} · plates ${ops.officerOn ? 'shown to the duty officer' : 'masked'}`),
				error: feedError(godsEye.vehiclesFeed),
				detail: {
					vehicles: godsEye.vehicles.length,
					traced: tracedCount,
					hops: hopCount,
					withheld: withheldCount,
					// v2: the LayerTree row's provenance glyph (SPEC §5.3, §9.2): vehicles whose last read is emulated
					...(chromeOf(ctx) === 'v2'
						? { emulated: godsEye.vehicles.filter((v) => v.lastSighting && v.lastSighting.source === 'emulated_anpr').length }
						: {}),
					...(ctx && entityIds.length ? drapeAudit(ctx.viewer, entityIds) : {}),
				},
				via: godsEye.via('vehicle'),
			};
		},
		destroy() {
			this.deactivate();
		},
	};
}

export const vehicleTracesLayer: GodsEyeLayer = {
	id: 'traces',
	name: 'Vehicle traces + earmarks',
	label: 'TRACES',
	requiresKeyId: null,
	pickPrefix: VEHICLE_TRACES_PICK_PREFIX,
	defaultOn: true,
	group: 'enforcement',
	create: createVehicleTracesLayer,
};
