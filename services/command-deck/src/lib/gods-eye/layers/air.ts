/**
 * air layer — the ten WBPCB/CPCB air-quality monitoring sites, each banded by India's National AQI (indicative).
 *
 * Data: GET /api/cityfeeds/feeds/air (services/cityfeeds through the deck proxy), every 10 min with back-off. The
 * values are Open-Meteo's air-quality model (CAMS) at the sites, not the stations' own readings; the National AQI is
 * CPCB's breakpoint table applied to the modelled 24-hour PM2.5 and PM10 means (INDICATIVE). Each pick text says so.
 *
 * SYMBOLOGY (colour only for meaning, no new colour token): the EXISTING band ladder — Good and Satisfactory
 * --v-band-green, Moderate --v-band-amber, Poor and Very poor --v-band-red, Severe --v-band-black-fill with the
 * --v-band-black-hairline ring ($lib/cityfeeds/model TONE_TOKEN) — on a dot that ALSO grows with the band
 * (airRadius: 8 px Good … 18 px Severe, so the meaning never rides on colour alone), a soft 450 m veil of the same
 * band under it, and a label naming the site and its value ("Victoria Memorial · AQI 62") that joins the map's one
 * label budget (hud/map/live-marks), so it never sits on another layer's label. It never reads --v-act, --v-data or --v-tool.
 *
 * Pick ids `aq:<site id>` → URN `place:aq_<site id>` (an air-quality site is a place, never a person).
 */

import type { GodsEyeLayer, GodsEyeLayerContext, GodsEyeLayerInstance } from '../registry';
import { DRAPE_Z, clampedDot, drapeAudit, drapedEllipse, ground } from './draping';
import { cityGround, declutterFor, labelBox, primitivesOk, type DeclutterItem, type Loose } from '../hud/map/live-marks';
import { canvasFont, cssVar } from '../theme';
import { inkAlpha, mapInk } from '../hud/map/symbols';
import { createPoller, type Poller } from '$lib/ai/poll';
import { getAir } from '$lib/cityfeeds/client';
import { TONE_TOKEN, airRadius, toneOf, worstBandIndex } from '$lib/cityfeeds/model';
import type { AirView } from '$lib/cityfeeds/types';
import { ops } from '$lib/ops/store.svelte';
import { t } from '$lib/i18n/strings';
import { shortPlace } from './live-values';
import { liveClock } from '../hud/map/live-clock';
import { photorealBaseOn } from './photoreal-3d';
import '../hud/map/packs.livemap';

export const AIR_PICK_PREFIX = 'aq:';

/** A site's label: the place and its value, "Victoria Memorial · AQI 42" (pure; exported for tests). */
export function airLabel(s: { name: string; name_mr?: string | null; naqi?: { aqi: number } | null }, lang: string): string {
	return t(lang, 'lm_air', shortPlace(lang === 'mr' && s.name_mr ? s.name_mr : s.name), s.naqi ? s.naqi.aqi : '—');
}

/** The band ladder's fallbacks (Cesium needs a colour even before the tokens resolve; never a new palette). */
const FALLBACK: Record<string, string> = { '--v-band-green': 'seagreen', '--v-band-amber': 'goldenrod', '--v-band-red': 'indianred', '--v-band-black-fill': 'black', '--v-band-black-hairline': 'indianred', '--v-map-marker': 'gray' };

function createAirLayer(): GodsEyeLayerInstance {
	let ctx: GodsEyeLayerContext | null = null;
	let active = false;
	let poller: Poller | null = null;
	let air: AirView | null = null;
	let feed: 'loading' | 'ok' | 'down' | 'not-deployed' = 'loading';
	let lastSig = '';
	const ids: string[] = [];
	let hint = 'loading air quality';
	let detail: Record<string, number> = {};
	let labels: Loose = null;

	const ink = (token: string) => cssVar(token) || FALLBACK[token] || 'gray';

	function draw() {
		if (!ctx || !active) return;
		const { cesium, viewer } = ctx;
		const stations = air?.stations ?? [];
		const lang = ops.lang ?? 'en';
		const sig = JSON.stringify([lang, photorealBaseOn(), stations.map((s) => [s.id, s.naqi?.aqi ?? null, s.naqi?.band ?? null]), ink('--v-band-green'), ink('--v-band-red')]);
		if (sig === lastSig) return;
		lastSig = sig;
		for (const id of ids) viewer.entities.removeById(id);
		ids.length = 0;
		if (labels) (viewer.scene.primitives as Loose).remove(labels);
		labels = primitivesOk(ctx) ? (viewer.scene.primitives as Loose).add(new (cesium as Loose).LabelCollection({ scene: viewer.scene })) : null;
		const items: DeclutterItem[] = [];
		const labelInk = cesium.Color.fromCssColorString(mapInk('label-ink'));
		const halo = cesium.Color.fromCssColorString(mapInk('casing'));
		for (const s of stations) {
			const band = s.naqi?.band ?? null;
			const tok = TONE_TOKEN[toneOf('air', band)];
			const fill = ink(tok.fill);
			const ring = tok.ring ? ink(tok.ring) : mapInk('casing');
			// the soft veil on the City map only: on the photoreal city a draped translucent disc is a classification
			// volume on the 3D tiles (costly per frame) and the dot and its label already say the band and the value
			if (!photorealBaseOn()) {
				const veil = viewer.entities.add({
					id: `${AIR_PICK_PREFIX}veil-${s.id}`,
					position: ground(cesium, s.lon, s.lat),
					ellipse: drapedEllipse(cesium, { radiusM: 450, material: cesium.Color.fromCssColorString(inkAlpha(fill, 0.2)), z: DRAPE_Z.zone }),
				});
				ids.push(veil.id);
			}
			// the place and its value: "Victoria Memorial · AQI 42" (the legend and the pick text say modelled)
			const aqiText = airLabel(s, lang);
			const pm = s.pm25_24h != null ? ` PM2.5 24-hour mean ${s.pm25_24h} µg/m³, PM10 ${s.pm10_24h ?? '—'} µg/m³.` : '';
			const entity = viewer.entities.add({
				id: `${AIR_PICK_PREFIX}${s.id}`,
				position: ground(cesium, s.lon, s.lat),
				billboard: clampedDot(cesium, { pixelSize: airRadius(band) * 2, color: cesium.Color.fromCssColorString(fill), outlineColor: cesium.Color.fromCssColorString(ring), outlineWidth: 2 }),
				description: `Air quality at ${s.name}: indicative National AQI ${s.naqi ? `${s.naqi.aqi}, ${s.naqi.band_en}` : 'unavailable'} (CPCB bands on modelled values, not the station's own reading).${pm} Model: Open-Meteo air-quality (CAMS). Site position: ${s.coord_source}.`,
			});
			ids.push(entity.id);
			// the label joins the map's one label budget (live-marks): "Victoria Memorial · AQI 42"
			if (!labels) continue;
			const at = cesium.Cartesian3.fromDegrees(s.lon, s.lat, cityGround(ctx) + 4);
			const poor = worstBandIndex([band]) >= 3;
			const label = labels.add({
				position: at,
				text: aqiText,
				font: canvasFont([poor ? '600' : '500', '12px', 'var(--v-font-ui)'].join(' ')),
				fillColor: labelInk,
				outlineColor: halo,
				outlineWidth: 3,
				style: 2,
				verticalOrigin: 1,
				pixelOffset: new cesium.Cartesian2(0, -(airRadius(band) + 6)),
				disableDepthTestDistance: Number.POSITIVE_INFINITY,
				show: false,
			});
			const box = labelBox(aqiText, 12);
			items.push({ key: `aq:${s.id}`, priority: poor ? 0.7 : 2.1, position: at, w: box.w, h: box.h, dy: -(airRadius(band) + 6), maxAlt: 30_000, apply: (show) => (label.show = show) });
		}
		declutterFor(ctx).set('air', items);
		const worst = worstBandIndex(stations.map((s) => s.naqi?.band));
		detail = { sites: stations.length, worst_band: worst, drawn: stations.length };
		if (feed === 'not-deployed') hint = 'air quality feed not deployed on this deck';
		else if (feed === 'down' && !air) hint = 'air quality feed unreachable — nothing drawn';
		else if (!air) hint = 'loading air quality';
		else hint = `${stations.length} sites, indicative National AQI (modelled; CPCB bands)${air.city ? `, worst ${air.city.aqi} ${air.city.band_en} at ${air.city.worst_site_name}` : ''}`;
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
						air = await getAir();
						feed = 'ok';
						liveClock.mark('air');
					} catch (err) {
						feed = err instanceof Error && err.name === 'AiNotDeployed' ? 'not-deployed' : 'down';
						throw err;
					} finally {
						lastSig = '';
						draw();
						ctx?.notify();
					}
				},
				{ baseMs: 600_000 },
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
			if (ctx && labels) (ctx.viewer.scene.primitives as Loose).remove(labels);
			labels = null;
			if (ctx) declutterFor(ctx).clear('air');
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
			return pickId.startsWith(AIR_PICK_PREFIX);
		},
		urnOf(pickId) {
			const id = pickId.slice(AIR_PICK_PREFIX.length);
			return /^[a-z_]+$/.test(id) ? `place:aq_${id}` : null;
		},
		coverageStats() {
			return {
				count: detail.sites ?? 0,
				loading: feed === 'loading',
				hint,
				error: feed === 'down' && !air ? 'air quality feed down' : null,
				detail: ctx ? { ...detail, ...drapeAudit(ctx.viewer, ids) } : detail,
				via: 'cityfeeds/air',
			};
		},
		destroy() {
			this.deactivate();
		},
	};
}

export const airLayer: GodsEyeLayer = {
	id: 'air',
	name: 'Air quality (National AQI, modelled)',
	label: 'AIR',
	requiresKeyId: null,
	pickPrefix: AIR_PICK_PREFIX,
	defaultOn: true,
	group: 'intelligence',
	create: createAirLayer,
};
