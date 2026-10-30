/**
 * places layer — the gazetteer places a surfaced situation is reported at
 * (place:, OS-DECK-A). Off by default: a place is reference geography, and
 * the LayerTree row turns it on when an operator wants the place picture
 * (the reported situations name their places in the inspector and on hover
 * regardless).
 *
 * Feed: the city registry's `place` entities (contract C-C extension; the
 * snapshot's ONE GET /city/entities, no GET of its own). Neutral small
 * markers with the map-marker glyph, in both chromes; labels and clustering
 * belong to the canvas's v2 pass. Pick id `place:<slug>` → URN
 * `place:<slug>`.
 */

import { ops } from '$lib/ops/store.svelte';
import { cityRegistry } from '../entities/registry.svelte';
import { displayText } from '../plates';
import type { GodsEyeLayer, GodsEyeLayerContext, GodsEyeLayerInstance } from '../registry';
import { canvasFont, cssColor, cssVar } from '../theme';
import { clampedDot, clampedLabel, drapeAudit, ground } from './draping';
import { kindIcon } from '$lib/design/icons';
import { chromeOf, markerStyle, viewOf, kindsSignature, type MapView } from '../hud/map/view';
import { markerBillboard, tagMarker, type MarkerMeta } from '../hud/map/symbols';

export const PLACE_PICK_PREFIX = 'place:';

const LABEL_MAX_CHARS = 32;
const LABEL_FAR = 12_000;

/** The place slug behind a pick id, null when the id is not one of this layer's. */
export function placeSlugFromPick(pickId: string): string | null {
	if (!pickId.startsWith(PLACE_PICK_PREFIX)) return null;
	return pickId.slice(PLACE_PICK_PREFIX.length) || null;
}

function createPlacesLayer(): GodsEyeLayerInstance {
	let ctx: GodsEyeLayerContext | null = null;
	let active = false;
	let timer: ReturnType<typeof setInterval> | null = null;
	const entityIds: string[] = [];
	let lastSignature = '';
	let drawn = 0;
	let detail: Record<string, number> = {};

	function draw() {
		if (!ctx || !active) return;
		const { cesium, viewer } = ctx;
		const rows = cityRegistry.byKind('place');
		const officer = ops.officerOn;
		const view: MapView | null = chromeOf(ctx) === 'v2' ? viewOf(ctx) : null;
		const sig = JSON.stringify([rows.map((e) => [e.id, e.lon, e.lat, e.label]), officer, view ? [kindsSignature(view), view.version] : null]);
		if (sig === lastSignature) return;
		lastSignature = sig;

		for (const id of entityIds) viewer.entities.removeById(id);
		entityIds.length = 0;
		drawn = 0;

		const canvasInk = cssColor(cesium, '--v-map-marker-fill', cesium.Color.GRAY);
		const ringInk = cssColor(cesium, '--v-map-marker', cesium.Color.LIGHTGRAY);
		const labelInk = cssColor(cesium, '--v-map-label-ink', cesium.Color.WHITE);

		for (const e of rows) {
			if (e.lon == null || e.lat == null) continue;
			const style = view ? markerStyle({ urn: e.urn, kind: e.kind, t: e.t }, view) : null;
			const alpha = style ? style.alpha : 1;
			drawn++;
			const label = (() => {
				const shown = displayText(e.label, officer);
				return shown.length > LABEL_MAX_CHARS ? `${shown.slice(0, LABEL_MAX_CHARS - 1)}…` : shown;
			})();
			if (view) {
				const meta: MarkerMeta = {
					urn: e.urn,
					kind: 'place',
					glyph: kindIcon('place'),
					shape: 'disc',
					size: 17,
					cluster: true,
					t: e.t,
					label: [{ text: label }],
					labelWhen: 'hover',
				};
				const entity = viewer.entities.add({
					id: `${PLACE_PICK_PREFIX}${e.id}`,
					position: ground(cesium, e.lon, e.lat),
					billboard: markerBillboard(cesium, meta),
					description: `${displayText(e.label, officer)}. A gazetteer place a reported situation names.`,
				});
				tagMarker(entity, meta);
				entityIds.push(entity.id);
			} else {
				const entity = viewer.entities.add({
					id: `${PLACE_PICK_PREFIX}${e.id}`,
					position: ground(cesium, e.lon, e.lat),
					billboard: clampedDot(cesium, {
						pixelSize: 9,
						color: cesium.Color.fromCssColorString(cssVar('--v-map-marker-fill') ?? 'dimgray'),
						outlineColor: ringInk,
						outlineWidth: 1.5,
					}),
					label: clampedLabel(cesium, {
						text: label,
						font: canvasFont('12px var(--v-font-ui)'),
						fillColor: labelInk,
						outlineColor: canvasInk,
						outlineWidth: 2,
						style: 2,
						verticalOrigin: -1,
						pixelOffset: new cesium.Cartesian2(0, 10),
						distanceDisplayCondition: new cesium.DistanceDisplayCondition(0, LABEL_FAR),
					}),
					description: `${displayText(e.label, officer)}. A gazetteer place a reported situation names.`,
				});
				entityIds.push(entity.id);
			}
		}
		detail = { drawn, ...(ctx && drawn ? drapeAudit(ctx.viewer, entityIds) : {}) };
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
			drawn = 0;
			detail = {};
		},
		refresh() {
			lastSignature = '';
			void cityRegistry.refresh();
			draw();
		},
		restyle() {
			draw();
		},
		handlePick(pickId) {
			return pickId.startsWith(PLACE_PICK_PREFIX);
		},
		urnOf(pickId) {
			const slug = placeSlugFromPick(pickId);
			return slug ? `place:${slug}` : null;
		},
		coverageStats() {
			const served = cityRegistry.served('place');
			const down = cityRegistry.status !== 'idle' && !served;
			return {
				count: drawn,
				loading: cityRegistry.status === 'idle',
				hint: down ? 'city fusion API unavailable — places not shown' : `${drawn} reported-at places on canvas`,
				error: down ? (cityRegistry.note ?? 'places source not ok') : null,
				detail,
				via: 'city-api',
			};
		},
		destroy() {
			this.deactivate();
		},
	};
}

export const placesLayer: GodsEyeLayer = {
	id: 'places',
	name: 'Reported-at places',
	label: 'PLACES',
	requiresKeyId: null,
	pickPrefix: PLACE_PICK_PREFIX,
	defaultOn: false,
	group: 'intelligence',
	create: createPlacesLayer,
};
