/**
 * agency-units layer — civic volunteer / police / traffic unit markers.
 *
 * Feed: the canvas store's units — the city registry's unit entities, or
 * GET /api/v1/units → {units: [...]} as the fallback. Two producers share
 * them: approved dispatches projected along the corridor graph (status,
 * eta_sec, progress, arrived) and — contract C-A — emulated patrols (status
 * patrol | available | …). Agency shapes the colour (agency.ts: jan_rakshak
 * → act orange, police → data accent, traffic → tool accent, 108 → ink,
 * fire → act-2, other → dim).
 *
 * Every marker reads `label` over `STATUS · ETA · PROGRESS` — the real
 * lifecycle the oracle reports, '—' where it has none — and every emulated
 * unit carries a persistent EMULATED badge (the C6 rail). 404 → "not
 * deployed" chip.
 *
 * DRAPED (layers/draping.ts): marker and label are clamped to the terrain
 * — street level, under the photoreal 3D tiles too — and never hidden by a
 * building. The label reads in the agency's text ink on the translucent
 * canvas plate, and gives way (the canvas's declutter) to an e-challan /
 * sighting pin it would cover — hover or select the unit to read it there.
 *
 * Pick ids `unit:<unitId>` → URN `unit:<unitId>`.
 */

import { feedError, feedHint, godsEye } from '../store.svelte';
import type { AgencyUnitRecord } from '../data';
import type { GodsEyeLayer, GodsEyeLayerContext, GodsEyeLayerInstance } from '../registry';
import { canvasFont, cssColor } from '../theme';
import { kindIcon } from '$lib/design/icons';
import { chromeOf } from '../hud/map/view';
import { markerBillboard, tagMarker, type MarkerMeta } from '../hud/map/symbols';
import { agencyColor, agencyLabel, agencyTextColor, unitPhase } from './agency';
import { clampedDot, clampedLabel, drapeAudit, ground } from './draping';
import { labelPlate } from './labels';
import { UNIT_GLIDE_MS, UNIT_JUMP_M, unitTag } from '../hud/map/live-marks';
export { UNIT_GLIDE_MS, UNIT_JUMP_M, unitTag };

export const AGENCY_UNITS_PICK_PREFIX = 'unit:';

/** '2m 05s' / '45s' / 'ARRIVED' / '—'. */
function etaText(u: AgencyUnitRecord): string {
	if (u.arrived === true) return 'ARRIVED';
	if (u.etaSec == null) return 'ETA —';
	const s = Math.max(0, Math.round(u.etaSec));
	if (s < 60) return `ETA ${s}s`;
	return `ETA ${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`;
}

/** The second label line: 'EN ROUTE · ETA 2m 05s · 45%'. Exported for tests. */
export function unitStatusLine(u: AgencyUnitRecord): string {
	const status = u.status ? u.status.replace(/_/g, ' ').toUpperCase() : 'STATUS —';
	const progress = u.progress != null ? `${Math.round(u.progress * 100)}%` : '—';
	return `${status} · ${etaText(u)} · ${progress}`;
}

function createAgencyUnitsLayer(): GodsEyeLayerInstance {
	let ctx: GodsEyeLayerContext | null = null;
	let active = false;
	let timer: ReturnType<typeof setInterval> | null = null;
	const entityIds: string[] = [];
	let lastSignature = '';
	/**
	 * Chrome v2 motion (live map, 29 Oct): a unit glides from where it is drawn to its newly REPORTED position over
	 * one poll (UNIT_GLIDE_MS) instead of jumping — the marker shows the last report, reached a moment late, never a
	 * position the feed did not send. A jump of more than UNIT_JUMP_M (a new run, a reassignment) does not glide.
	 */
	const glide = new Map<string, { from: [number, number]; to: [number, number]; t0: number }>();
	const glideAt = (g: { from: [number, number]; to: [number, number]; t0: number }, now: number): [number, number] => {
		const k = Math.max(0, Math.min(1, (now - g.t0) / UNIT_GLIDE_MS));
		return [g.from[0] + (g.to[0] - g.from[0]) * k, g.from[1] + (g.to[1] - g.from[1]) * k];
	};
	function glideTo(id: string, lon: number, lat: number) {
		const now = performance.now();
		const cur = glide.get(id);
		if (!cur) return void glide.set(id, { from: [lon, lat], to: [lon, lat], t0: now });
		if (cur.to[0] === lon && cur.to[1] === lat) return;
		const at = glideAt(cur, now);
		const far = Math.hypot((lon - at[0]) * 102_800, (lat - at[1]) * 110_600) > UNIT_JUMP_M;
		glide.set(id, { from: far ? [lon, lat] : at, to: [lon, lat], t0: now });
	}

	function draw() {
		if (!ctx || !active) return;
		const { cesium, viewer } = ctx;
		const units = godsEye.units;
		const v2 = chromeOf(ctx) === 'v2';
		for (const u of units) glideTo(u.unitId, u.lon, u.lat);
		// v2: a moved unit glides (no rebuild); the legacy chrome redraws on every move as before
		const sig = JSON.stringify([
			units.map((u) => [u.unitId, u.agency, ...(v2 ? [] : [u.lon, u.lat]), u.emulated, v2 ? u.status : unitStatusLine(u)]),
			godsEye.unitsFeed.status,
		]);
		if (sig === lastSignature) return;
		lastSignature = sig;

		for (const id of entityIds) viewer.entities.removeById(id);
		entityIds.length = 0;

		if (v2) {
			// SPEC §2.4: units are neutral (type by glyph); the agency and the
			// status read on hover and in the pick text, never as a hue.
			for (const u of units) {
				const status = u.status ? u.status.replace(/_/g, ' ') : 'status unknown';
				const meta: MarkerMeta = {
					urn: `unit:${u.unitId}`,
					kind: 'unit',
					glyph: kindIcon('unit'),
					shape: 'disc',
					cluster: true,
					// the unit's id and what it is doing, always (the live city's units are part of the picture)
					label: [{ id: unitTag(u) }],
					labelWhen: 'always',
				};
				const unitId = u.unitId;
				const entity = viewer.entities.add({
					id: `${AGENCY_UNITS_PICK_PREFIX}${u.unitId}`,
					position: cesium.CallbackProperty
						? new cesium.CallbackProperty(() => {
								const g = glide.get(unitId);
								const [lon, lat] = g ? glideAt(g, performance.now()) : [u.lon, u.lat];
								return ground(cesium, lon, lat);
							}, false)
						: ground(cesium, u.lon, u.lat),
					billboard: markerBillboard(cesium, meta),
					description: `Unit ${u.label ?? u.unitId} (${agencyLabel(u.agency)}): ${status}${
						u.arrived === true ? ', arrived' : u.etaSec != null ? `, ETA ${Math.max(0, Math.round(u.etaSec))} s` : ''
					}${u.assignedEventId ? `, assigned to event ${u.assignedEventId}` : ''}. Source: ${u.emulated ? 'emulated' : (u.source ?? 'live')}.`,
				});
				tagMarker(entity, meta);
				entityIds.push(entity.id);
			}
			return;
		}

		for (const u of units) {
			const line = unitStatusLine(u);
			const entity = viewer.entities.add({
				id: `${AGENCY_UNITS_PICK_PREFIX}${u.unitId}`,
				position: ground(cesium, u.lon, u.lat),
				billboard: clampedDot(cesium, {
					pixelSize: 9,
					color: agencyColor(u.agency, cesium),
					outlineColor: cssColor(cesium, '--v-canvas', cesium.Color.BLACK),
					outlineWidth: 2,
				}),
				label: clampedLabel(cesium, {
					text: `${u.label ?? u.unitId}${u.emulated ? ' ·EMULATED' : ''}\n${line}`,
					font: canvasFont('12px var(--v-font-ui)'),
					// the agency's TEXT ink (act-text, not the darker act fill) on the
					// canvas plate: legible on the dark basemap and over the pins, flow
					// and trace lines it crosses
					fillColor: agencyTextColor(u.agency, cesium),
					outlineColor: cssColor(cesium, '--v-canvas', cesium.Color.BLACK),
					outlineWidth: 2,
					style: 2, // FILL_AND_OUTLINE
					...labelPlate(cesium),
					verticalOrigin: -1,
					pixelOffset: new cesium.Cartesian2(0, 12),
					// Overview declutter: the marker always shows, its status text up close.
					distanceDisplayCondition: new cesium.DistanceDisplayCondition(0, 7500),
				}),
				description: `unit ${u.unitId} · ${agencyLabel(u.agency)} · ${line} · assigned ${
					u.assignedEventId ?? '—'
				}${u.dispatchId ? ` · dispatch ${u.dispatchId}` : ''}${
					u.speedKmh != null ? ` · ${Math.round(u.speedKmh)} km/h` : ''
				} · ${u.emulated ? `EMULATED (${u.source ?? 'emulated'})` : `live (${u.source ?? '—'})`}`,
			});
			entityIds.push(entity.id);
		}
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
			draw();
			timer = setInterval(draw, 2000);
		},
		deactivate() {
			active = false;
			if (timer) clearInterval(timer);
			timer = null;
			if (ctx) for (const id of entityIds) ctx.viewer.entities.removeById(id);
			entityIds.length = 0;
			lastSignature = '';
		},
		refresh() {
			lastSignature = '';
			void godsEye.pollUnits();
			draw();
		},
		handlePick(pickId) {
			return pickId.startsWith(AGENCY_UNITS_PICK_PREFIX);
		},
		urnOf(pickId) {
			// The pick id IS the URN (`unit:<unitId>`).
			return pickId.length > AGENCY_UNITS_PICK_PREFIX.length ? pickId : null;
		},
		coverageStats() {
			const feed = godsEye.unitsFeed;
			const units = godsEye.units;
			const unplaced = Math.max(0, feed.total - units.length);
			const onScene = units.filter((u) => unitPhase(u) === 'on_scene').length;
			const enRoute = units.filter((u) => unitPhase(u) === 'en_route').length;
			return {
				count: entityIds.length,
				loading: feed.status === 'empty' && feed.updatedAt === 0,
				// An empty answer is not a fault: 'no units fielded' is the hint, never the ⚠ chip.
				hint:
					feed.status === 'not-deployed'
						? '/api/v1/units 404 — signalling stream pending'
						: (feedHint(feed) ??
							`${units.length} units (EMULATED) · ${enRoute} en route · ${onScene} on scene${unplaced ? ` · ${unplaced} awaiting a position` : ''}`),
				error: feedError(feed),
				detail: {
					units: units.length,
					enRoute,
					onScene,
					// v2: the LayerTree row's provenance glyph (SPEC §5.3, §9.2)
					...(chromeOf(ctx) === 'v2' ? { emulated: units.filter((u) => u.emulated).length } : {}),
					...(ctx && entityIds.length ? drapeAudit(ctx.viewer, entityIds) : {}),
				},
				via: godsEye.via('unit'),
			};
		},
		destroy() {
			this.deactivate();
		},
	};
}

export const agencyUnitsLayer: GodsEyeLayer = {
	id: 'units',
	name: 'Civic volunteer + agency units',
	label: 'UNITS',
	requiresKeyId: null,
	pickPrefix: AGENCY_UNITS_PICK_PREFIX,
	defaultOn: true,
	group: 'response',
	create: createAgencyUnitsLayer,
};
