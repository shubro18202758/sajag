/**
 * cyclone layer — the active North Indian Ocean cyclone from GDACS (for Mumbai, an Arabian Sea storm such as
 * Tauktae, May 2021): its track, positions, wind buffers and the forecast cone, and — because a cyclone hundreds of
 * kilometres away is off the city view — a BEARING MARKER at the city centre (a 5 km arrow toward the storm, its
 * name, distance and direction labelled at the centre).
 *
 * Data: GET /api/cityfeeds/feeds/cyclones (services/cityfeeds through the deck proxy), every 15 min with back-off.
 * GDACS is a LIVE open feed (EC JRC and UN OCHA); distances, bearing and "the city inside a wind buffer" are
 * computed by the service (MODELLED). IMD's RSMC New Delhi bulletins are the official word; the pick text says so.
 * No active cyclone → nothing is drawn and the Layers-sheet row says "No active cyclone".
 *
 * SYMBOLOGY (colour only for meaning, no new token): GDACS's alert level on the EXISTING band ladder — wind buffers
 * 60 km/h --v-band-green, 90 km/h --v-band-amber, 120 km/h --v-band-red as soft veils (12–20 %); the cone a
 * neutral marker veil; the track and the bearing marker in the band of the event's alert level, the forecast part
 * of the track dashed; positions as small neutral dots.
 *
 * Pick ids `cy:<kind>-<n>` → URN `gdacs:TC:<eventid>`.
 */

import type { GodsEyeLayer, GodsEyeLayerContext, GodsEyeLayerInstance } from '../registry';
import { DRAPE_Z, clampedDot, clampedLabel, drapeAudit, drapedPolygon, drapedPolyline, ground, groundPath } from './draping';
import { canvasFont, cssVar } from '../theme';
import { inkAlpha, mapInk, offsetPoint } from '../hud/map/symbols';
import { createPoller, type Poller } from '$lib/ai/poll';
import { getCyclones } from '$lib/cityfeeds/client';
import { CITY_CENTRE, cityName } from '$lib/city';
import { inWindBufferKmh } from '$lib/cityfeeds/model';
import type { CycloneView } from '$lib/cityfeeds/types';

export const CYCLONE_PICK_PREFIX = 'cy:';

const LEVEL_TOKEN: Record<string, string> = { green: '--v-band-green', orange: '--v-band-amber', red: '--v-band-red' };
const FALLBACK: Record<string, string> = { '--v-band-green': 'seagreen', '--v-band-amber': 'goldenrod', '--v-band-red': 'indianred' };
const BUFFER_ALPHA: Record<string, number> = { green: 0.12, orange: 0.16, red: 0.2 };

/** The bearing marker's length on the ground (m): long enough to read at city zoom, short of the city edge. */
export const BEARING_LEN_M = 5000;

function createCycloneLayer(): GodsEyeLayerInstance {
	let ctx: GodsEyeLayerContext | null = null;
	let active = false;
	let poller: Poller | null = null;
	let view: CycloneView | null = null;
	let feed: 'loading' | 'ok' | 'down' | 'not-deployed' = 'loading';
	let lastSig = '';
	const ids: string[] = [];
	let hint = 'loading cyclones';
	let detail: Record<string, number> = {};

	const ink = (token: string) => cssVar(token) || FALLBACK[token] || 'gray';

	function draw() {
		if (!ctx || !active) return;
		const { cesium, viewer } = ctx;
		const nearest = view?.nearest ?? null;
		const feats = view?.features ?? [];
		const sig = JSON.stringify([feats.length, nearest?.name ?? null, nearest?.distance_km ?? null, ink('--v-band-red')]);
		if (sig === lastSig) return;
		lastSig = sig;
		for (const id of ids) viewer.entities.removeById(id);
		ids.length = 0;
		const add = (o: Record<string, unknown>) => ids.push(viewer.entities.add(o).id);
		const eventInk = ink(LEVEL_TOKEN[nearest?.alertlevel ?? ''] ?? '--v-band-amber');
		const official = 'IMD RSMC New Delhi bulletins are the official word.';
		let n = 0;
		if (nearest) {
			const urnText = `${nearest.name} (GDACS ${nearest.alertlevel} alert)`;
			for (const f of feats) {
				const p = f.properties;
				n++;
				if (p.kind === 'wind_buffer' && f.geometry.type === 'Polygon') {
					const ring = (f.geometry.coordinates as number[][][])[0];
					const lvl = String(p.level);
					add({
						id: `${CYCLONE_PICK_PREFIX}buffer-${n}`,
						polygon: drapedPolygon(cesium, { positions: groundPath(cesium, ring as unknown as Array<[number, number]>), material: cesium.Color.fromCssColorString(inkAlpha(ink(LEVEL_TOKEN[lvl] ?? '--v-band-amber'), BUFFER_ALPHA[lvl] ?? 0.14)), z: DRAPE_Z.zone }),
						description: `${urnText}: winds of ${p.wind_kmh} km/h or more expected inside this buffer (GDACS, live). ${official}`,
					});
				} else if (p.kind === 'cone' && f.geometry.type === 'Polygon') {
					const ring = (f.geometry.coordinates as number[][][])[0];
					add({
						id: `${CYCLONE_PICK_PREFIX}cone-${n}`,
						polygon: drapedPolygon(cesium, { positions: groundPath(cesium, ring as unknown as Array<[number, number]>), material: cesium.Color.fromCssColorString(inkAlpha(mapInk('marker'), 0.12)), z: DRAPE_Z.zone }),
						description: `${urnText}: forecast uncertainty cone (GDACS). ${official}`,
					});
				} else if (p.kind === 'track' && f.geometry.type === 'LineString') {
					add({
						id: `${CYCLONE_PICK_PREFIX}track-${n}`,
						polyline: drapedPolyline(cesium, { positions: groundPath(cesium, f.geometry.coordinates as Array<[number, number]>), width: 4, material: cesium.Color.fromCssColorString(eventInk), z: DRAPE_Z.alternate }),
						description: `${urnText}: track leg, category ${p.category} (GDACS). ${official}`,
					});
				} else if (p.kind === 'position' && f.geometry.type === 'Point') {
					const [lon, lat] = f.geometry.coordinates as [number, number];
					add({
						id: `${CYCLONE_PICK_PREFIX}pos-${n}`,
						position: ground(cesium, lon, lat),
						billboard: clampedDot(cesium, { pixelSize: p.forecast ? 7 : 9, color: cesium.Color.fromCssColorString(p.forecast ? mapInk('marker-fill') : eventInk), outlineColor: cesium.Color.fromCssColorString(eventInk), outlineWidth: 2 }),
						description: `${urnText}: ${p.forecast ? 'forecast' : 'past'} position, ${p.label} (GDACS).`,
					});
				}
			}
			// the bearing marker at the city centre: an arrow toward the storm with its name, distance and alert
			const [clon, clat] = [CITY_CENTRE.lon, CITY_CENTRE.lat];
			const tip = offsetPoint(clon, clat, nearest.bearing_deg, BEARING_LEN_M);
			const barbL = offsetPoint(tip[0], tip[1], nearest.bearing_deg + 150, 1600);
			const barbR = offsetPoint(tip[0], tip[1], nearest.bearing_deg - 150, 1600);
			const buffer = inWindBufferKmh(nearest);
			const arrowText = `${nearest.name}: ${nearest.distance_km} km ${nearest.bearing} of ${cityName('en')}, GDACS ${nearest.alertlevel} alert${buffer ? `; ${cityName('en')} inside the ${buffer} km/h buffer` : ''}. ${official}`;
			for (const [k, pts] of [['shaft', [[clon, clat], tip]], ['barb-l', [tip, barbL]], ['barb-r', [tip, barbR]]] as const) {
				add({
					id: `${CYCLONE_PICK_PREFIX}bearing-${k}`,
					polyline: drapedPolyline(cesium, { positions: groundPath(cesium, pts as unknown as Array<[number, number]>), width: 5, material: cesium.Color.fromCssColorString(eventInk), z: DRAPE_Z.alternate }),
					description: arrowText,
				});
			}
			add({
				id: `${CYCLONE_PICK_PREFIX}bearing-label`,
				position: ground(cesium, clon, clat),
				label: clampedLabel(cesium, {
					text: `${nearest.name} · ${nearest.distance_km} km ${nearest.bearing}`,
					font: canvasFont('600 13px var(--v-font-ui)'),
					fillColor: cesium.Color.fromCssColorString(mapInk('label-ink')),
					outlineColor: cesium.Color.fromCssColorString(mapInk('casing')),
					outlineWidth: 3,
					style: 2,
					verticalOrigin: 1,
					pixelOffset: new cesium.Cartesian2(0, -10),
				}),
				description: arrowText,
			});
		}
		const activeN = view?.active?.length ?? 0;
		detail = { active: activeN, distance_km: nearest?.distance_km ?? -1, drawn: ids.length };
		if (feed === 'not-deployed') hint = 'cyclone feed not deployed on this deck';
		else if (feed === 'down' && !view) hint = 'cyclone feed unreachable — nothing drawn';
		else if (!view) hint = 'loading cyclones';
		else hint = nearest ? `${nearest.name}: ${nearest.distance_km} km ${nearest.bearing} of ${cityName('en')}, GDACS ${nearest.alertlevel} alert (live; distances modelled)` : 'No active cyclone in the Arabian Sea or the Bay of Bengal (GDACS)';
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
						view = await getCyclones();
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
				{ baseMs: 900_000 },
			);
			poller.start();
			draw();
		},
		deactivate() {
			active = false;
			poller?.stop();
			poller = null;
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
			lastSig = '';
			draw();
		},
		handlePick(pickId) {
			return pickId.startsWith(CYCLONE_PICK_PREFIX);
		},
		urnOf(pickId) {
			if (!pickId.startsWith(CYCLONE_PICK_PREFIX)) return null;
			const id = view?.nearest ? (view.features.find((f) => f.properties.eventid != null)?.properties.eventid ?? null) : null;
			return id != null ? `gdacs:TC:${String(id)}` : null;
		},
		coverageStats() {
			return {
				count: detail.active ?? 0,
				loading: feed === 'loading',
				hint,
				error: feed === 'down' && !view ? 'cyclone feed down' : null,
				detail: ctx ? { ...detail, ...drapeAudit(ctx.viewer, ids) } : detail,
				via: 'cityfeeds/cyclones',
			};
		},
		destroy() {
			this.deactivate();
		},
	};
}

export const cycloneLayer: GodsEyeLayer = {
	id: 'cyclone',
	name: 'Cyclone track (GDACS)',
	label: 'CYCLONE',
	requiresKeyId: null,
	pickPrefix: CYCLONE_PICK_PREFIX,
	defaultOn: false,
	group: 'intelligence',
	create: createCycloneLayer,
};
