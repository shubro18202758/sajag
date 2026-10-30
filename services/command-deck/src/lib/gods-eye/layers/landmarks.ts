/**
 * landmarks layer — the City Pack's named places, labelled on the map (on by default): the canonical landmarks
 * (Bandra–Worli Sea Link, CSMT, Dadar TT, Hindmata, King's Circle, Wankhede, the BMC pumping stations …), the
 * gazetteer's neighbourhoods, beaches and visarjan points, venues, terminals and low-lying spots, and the network's police, traffic police and fire
 * stations, hospitals and ambulance (108) bases ($lib/city/places, generated from the pack — reference geography,
 * never a live claim and never a person).
 *
 * DRAWING: one LabelCollection and one BillboardCollection (primitives, not entities), at the city's sampled ground
 * height (hud/map/live-marks cityGround), never hidden by the 3D buildings. Every label joins the map's ONE label
 * budget (live-marks declutter): landmarks first, then areas, then stations; a label that would overlap one already
 * placed, or that its zoom band leaves out, is hidden, and a station's glyph shows only with its label (a landmark's
 * small disc always shows). On the City map base the tiles already name the neighbourhoods, so the area names
 * are left out there (photorealBaseOn). Neutral inks only (--v-map-label-ink on the dark casing): a place is not a state.
 * Names follow the UI language (EN / MR / HI).
 *
 * No pick: a place mark selects nothing (the gazetteer `places` layer keeps the place: URNs of reported situations).
 */

import { ops } from '$lib/ops/store.svelte';
import { PLACE_MARKS, placeMarkCounts, placeMarkName, type PlaceMark } from '$lib/city/places';
import type { GodsEyeLayer, GodsEyeLayerContext, GodsEyeLayerInstance } from '../registry';
import { canvasFont } from '../theme';
import { mapInk } from '../hud/map/symbols';
import { photorealBaseOn } from './photoreal-3d';
import { cityGround, declutterFor, glyphImage, labelBox, type DeclutterItem, type Loose, primitivesOk } from '../hud/map/live-marks';

export const LANDMARKS_PICK_PREFIX = 'lm:';

/** Zoom bands (camera height, m) per tier: landmarks from afar, areas at district scale, stations up close. */
export const PLACE_MAX_ALT: Record<1 | 2 | 3, number> = { 1: 45_000, 2: 16_000, 3: 6_500 };
/** Declutter priority per tier (live-marks: 0 alert · 1 landmark · 2 live value · 3 road · 4 area · 5 station). */
export const PLACE_PRIORITY: Record<1 | 2 | 3, number> = { 1: 1, 2: 4, 3: 5 };

/** The glyph a mark wears (map convention letters for the services; a plain disc otherwise). */
export function placeGlyph(kind: PlaceMark['kind']): string {
	switch (kind) {
		case 'hospital':
			return 'H';
		case 'police':
			return 'P';
		case 'traffic':
			return 'T';
		case 'fire':
			return 'F';
		case 'ems':
			return '+';
		default:
			return '';
	}
}

function createLandmarksLayer(): GodsEyeLayerInstance {
	let ctx: GodsEyeLayerContext | null = null;
	let active = false;
	let labels: Loose = null;
	let dots: Loose = null;
	let timer: ReturnType<typeof setInterval> | null = null;
	let drawnLang = '';
	let drawnH = Number.NaN;
	let drawnAreas = false;
	let marks: Array<{ lon: number; lat: number; label: Loose; dot: Loose; item: DeclutterItem }> = [];
	let detail: Record<string, number> = {};

	function clear() {
		if (!ctx) return;
		const prims = (ctx.viewer as Loose)?.scene?.primitives;
		if (!prims) return;
		if (labels) prims.remove(labels);
		if (dots) prims.remove(dots);
		labels = dots = null;
		marks = [];
		declutterFor(ctx).clear('landmarks');
	}

	function draw() {
		if (!ctx || !active || !primitivesOk(ctx)) return;
		const cesium = ctx.cesium as Loose;
		const scene = (ctx.viewer as Loose).scene;
		const lang = ops.lang ?? 'en';
		const h = cityGround(ctx);
		// on the City map the tiles already name the neighbourhoods: the area names are left to them
		const areas = photorealBaseOn();
		if (lang === drawnLang && Math.abs(h - drawnH) < 0.5 && areas === drawnAreas && labels) return;
		if (lang === drawnLang && areas === drawnAreas && labels) {
			// only the sampled ground moved: the marks move in place (a rebuilt label is rasterised again)
			drawnH = h;
			for (const m of marks) {
				const at = cesium.Cartesian3.fromDegrees(m.lon, m.lat, h + 3);
				m.label.position = at;
				if (m.dot) m.dot.position = at;
				m.item.position = at;
			}
			declutterFor(ctx).set('landmarks', marks.map((m) => m.item));
			return;
		}
		drawnAreas = areas;
		clear();
		drawnLang = lang;
		drawnH = h;
		labels = scene.primitives.add(new cesium.LabelCollection({ scene }));
		dots = scene.primitives.add(new cesium.BillboardCollection({ scene }));
		const ink = cesium.Color.fromCssColorString(mapInk('label-ink'));
		const areaInk = cesium.Color.fromCssColorString('rgba(226, 226, 226, 0.88)');
		const stationInk = cesium.Color.fromCssColorString('rgba(214, 214, 214, 0.95)');
		const halo = cesium.Color.fromCssColorString('rgba(10, 10, 10, 0.92)');
		const items: DeclutterItem[] = [];
		for (const p of PLACE_MARKS) {
			if (p.kind === 'area' && !areas) continue;
			const position = cesium.Cartesian3.fromDegrees(p.lon, p.lat, h + 3);
			const text = placeMarkName(p, lang);
			const px = p.tier === 1 ? 13 : p.tier === 2 ? 12 : 11;
			const glyph = placeGlyph(p.kind);
			const dotPx = p.tier === 1 ? 10 : glyph ? 15 : 8;
			const img = glyphImage(glyph, p.tier === 1 ? 'rgba(245,245,245,0.95)' : 'rgba(34,34,34,0.92)', p.tier === 1 ? 'rgba(12,12,12,0.9)' : 'rgba(200,200,200,0.9)', 'rgba(250,250,250,1)', glyph ? 30 : 20);
			const showDotAlways = p.tier === 1;
			const dot =
				p.kind === 'area' || !img
					? null
					: dots.add({
							position,
							image: img,
							width: dotPx,
							height: dotPx,
							disableDepthTestDistance: Number.POSITIVE_INFINITY,
							show: showDotAlways,
						});
			const label = labels.add({
				position,
				text,
				font: canvasFont([p.tier === 1 ? '600' : '500', px + 'px', 'var(--v-font-ui)'].join(' ')),
				fillColor: p.tier === 1 ? ink : p.tier === 2 ? areaInk : stationInk,
				outlineColor: halo,
				outlineWidth: 3,
				style: cesium.LabelStyle?.FILL_AND_OUTLINE ?? 2,
				verticalOrigin: cesium.VerticalOrigin?.BOTTOM ?? 1,
				horizontalOrigin: cesium.HorizontalOrigin?.CENTER ?? 0,
				pixelOffset: new cesium.Cartesian2(0, p.kind === 'area' ? 0 : -(dotPx / 2 + 3)),
				disableDepthTestDistance: Number.POSITIVE_INFINITY,
				show: false,
			});
			const box = labelBox(text, px);
			const item: DeclutterItem = {
				key: `lm:${p.id}`,
				priority: PLACE_PRIORITY[p.tier] + (p.kind === 'junction' ? 0.3 : 0),
				position,
				w: box.w,
				h: box.h,
				dy: p.kind === 'area' ? 0 : -(dotPx / 2 + 3),
				maxAlt: PLACE_MAX_ALT[p.tier],
				apply(show) {
					label.show = show;
					if (dot && !showDotAlways) dot.show = show;
				},
			};
			items.push(item);
			marks.push({ lon: p.lon, lat: p.lat, label, dot, item });
		}
		declutterFor(ctx).set('landmarks', items);
		detail = { places: PLACE_MARKS.length, ...placeMarkCounts() };
		ctx.notify();
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
			// the UI language and the sampled ground height can change under the map
			timer = setInterval(draw, 3000);
		},
		deactivate() {
			active = false;
			if (timer) clearInterval(timer);
			timer = null;
			clear();
			drawnLang = '';
			drawnH = Number.NaN;
			detail = {};
		},
		refresh() {
			drawnLang = '';
			draw();
		},
		restyle() {
			draw();
		},
		handlePick() {
			return false;
		},
		urnOf() {
			return null;
		},
		coverageStats() {
			const d = ctx ? declutterFor(ctx) : null;
			return {
				count: detail.places ?? 0,
				loading: false,
				hint: `${detail.places ?? 0} City Pack places (landmarks, areas, stations) · reference geography`,
				error: null,
				detail: { ...detail, labelsShown: d?.shown ?? 0, labelCandidates: d?.candidates ?? 0 },
				via: 'city-pack',
			};
		},
		destroy() {
			this.deactivate();
		},
	};
}

export const landmarksLayer: GodsEyeLayer = {
	id: 'landmarks',
	name: 'City places (City Pack landmarks, areas, stations)',
	label: 'PLACES',
	requiresKeyId: null,
	pickPrefix: LANDMARKS_PICK_PREFIX,
	defaultOn: true,
	group: 'intelligence',
	create: createLandmarksLayer,
};
