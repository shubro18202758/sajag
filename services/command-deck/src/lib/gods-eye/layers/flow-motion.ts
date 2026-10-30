/**
 * The flow layer's motion and names (chrome v2): traffic dots that run along every road that has a current reading,
 * and the road's name with its reading as a label.
 *
 * MOTION FROM THE DATA. Each road with a fresh observation carries dots moving the way traffic runs on it (the drawn
 * direction, and back again unless the road is one-way), at the road's OBSERVED speed shown sped up FLOW_TIME_LAPSE
 * times (the legend says so), spaced by its congestion: a jammed road is a dense slow queue, a free road a few fast
 * dots. A road with no current reading has no dots. Nothing moves that the feed does not report.
 *
 * NAMES. One label per road at its midpoint: the road name, then its speed and — when the forecast service has the
 * road's current volume/capacity (its 15-minute V/C, on the simulated history) — "V/C 0.62". Congested roads claim
 * label room first (live-marks declutter priority 1.5; others 3).
 *
 * Primitives only: one PointPrimitiveCollection (≤ FLOW_MAX_DOTS dots, moved every frame) and one LabelCollection,
 * at the city's sampled ground height (live-marks cityGround).
 */

import { t } from '$lib/i18n/strings';
import type { GodsEyeLayerContext } from '../registry';
import { canvasFont } from '../theme';
import { cityGround, declutterFor, labelBox, primitivesOk, type DeclutterItem, type Loose } from '../hud/map/live-marks';
import '../hud/map/packs.livemap';

/** Dots move at the observed speed × this (a time-lapse; the legend says "sped up 20×"). */
export const FLOW_TIME_LAPSE = 20;
/** At most this many dots on the whole network. */
export const FLOW_MAX_DOTS = 1400;

export interface FlowRoad {
	segmentId: number;
	name: string;
	coordinates: ReadonlyArray<readonly [number, number]>;
	oneway: boolean;
	speedKmh: number;
	congestion: number;
	/** The forecast service's current V/C for the road (null when it has none). */
	vc: number | null;
	simulated: boolean;
	/** The road's ramp colour (CSS) for its dots. */
	ink?: string;
}

/** Dot spacing (m) from congestion: 90 m in a jam … 350 m on a free road (pure; exported for tests). */
export function dotGapM(congestion: number): number {
	const c = Math.max(0, Math.min(1, Number(congestion) || 0));
	return 90 + 260 * (1 - c);
}

/** How many dots one direction of a road carries (pure). */
export function dotsFor(lengthM: number, congestion: number): number {
	return Math.max(1, Math.min(14, Math.round(lengthM / dotGapM(congestion))));
}

interface Track {
	pts: Loose[];
	cum: number[];
	len: number;
	speed: number;
	dots: Array<{ p: Loose; off: number; dir: 1 | -1 }>;
}

export function createFlowMotion(ctx: GodsEyeLayerContext) {
	// a Cesium without the primitive collections (a test double): no motion, no names
	if (!primitivesOk(ctx)) return { update() {}, clear() {}, dots: 0, destroy() {} };
	const cesium = ctx.cesium as Loose;
	const scene = (ctx.viewer as Loose).scene;
	let points: Loose = null;
	let labels: Loose = null;
	let tracks: Track[] = [];
	let off: (() => void) | null = null;
	let lastSig = '';
	let dotCount = 0;
	const scratch = new cesium.Cartesian3(0, 0, 0);

	const bySeg = new Map<number, { track: Track; label: Loose }>();
	const roadText = (r: FlowRoad, lang: string) => {
		const name = r.name.length > 30 ? `${r.name.slice(0, 29)}…` : r.name;
		return `${name}\n${t(lang, 'lm_road_line2', Math.round(r.speedKmh), r.vc != null ? r.vc.toFixed(2) : null, r.simulated)}`;
	};

	function frame() {
		if (!tracks.length) return;
		const now = performance.now() / 1000;
		for (const tr of tracks) {
			for (const d of tr.dots) {
				let s = (((d.off + tr.speed * now) % tr.len) + tr.len) % tr.len;
				if (d.dir < 0) s = tr.len - s;
				// binary search the segment of the polyline that holds s
				let lo = 0;
				let hi = tr.cum.length - 1;
				while (hi - lo > 1) {
					const mid = (lo + hi) >> 1;
					if (tr.cum[mid] <= s) lo = mid;
					else hi = mid;
				}
				const span = tr.cum[hi] - tr.cum[lo] || 1;
				cesium.Cartesian3.lerp(tr.pts[lo], tr.pts[hi], (s - tr.cum[lo]) / span, scratch);
				d.p.position = scratch;
			}
		}
	}

	function clear() {
		if (points) scene.primitives.remove(points);
		if (labels) scene.primitives.remove(labels);
		points = labels = null;
		tracks = [];
		bySeg.clear();
		dotCount = 0;
		declutterFor(ctx).clear('flow');
	}

	/** Rebuild from the roads with a current reading (cheap no-op when nothing that shows changed). */
	function update(roads: readonly FlowRoad[], lang: string) {
		const h = cityGround(ctx);
		// the STRUCTURE (which roads, how many dots, their colour) rebuilds; a moved speed or V/C only rewrites the road's
		// label text and its dots' pace in place (a rebuilt label is rasterised again, which blinks on a slow GPU)
		const sig = JSON.stringify([lang, Math.round(h), roads.map((r) => [r.segmentId, Math.round(r.congestion * 20), r.oneway, r.ink ?? ''])]);
		if (sig === lastSig && points) {
			for (const r of roads) {
				const d = bySeg.get(r.segmentId);
				if (!d) continue;
				const speed = (Math.max(2, r.speedKmh) / 3.6) * FLOW_TIME_LAPSE;
				if (speed !== d.track.speed) {
					// keep every dot where it is: shift its phase by what the new pace would have added
					const nowSec = performance.now() / 1000;
					for (const dot of d.track.dots) dot.off += (d.track.speed - speed) * nowSec;
					d.track.speed = speed;
				}
				const text = roadText(r, lang);
				if (d.label.text !== text) d.label.text = text;
			}
			return;
		}
		lastSig = sig;
		clear();
		if (!roads.length) return;
		points = scene.primitives.add(new cesium.PointPrimitiveCollection());
		labels = scene.primitives.add(new cesium.LabelCollection({ scene }));
		if (!off) {
			const o = scene.preUpdate?.addEventListener?.(frame);
			off = typeof o === 'function' ? o : null;
		}
		const dotRim = cesium.Color.fromCssColorString('rgba(10, 10, 10, 0.9)');
		const ink = cesium.Color.fromCssColorString('rgba(245, 245, 245, 1)');
		const halo = cesium.Color.fromCssColorString('rgba(10, 10, 10, 0.92)');
		const items: DeclutterItem[] = [];
		// budget: scale every road's dots down together when the network would exceed the cap
		const lens = roads.map((r) => {
			let len = 0;
			for (let i = 1; i < r.coordinates.length; i++) {
				const [a, b] = [r.coordinates[i - 1], r.coordinates[i]];
				len += Math.hypot((b[0] - a[0]) * 102_800, (b[1] - a[1]) * 110_600);
			}
			return len;
		});
		const want = roads.reduce((n, r, i) => n + dotsFor(lens[i], r.congestion) * (r.oneway ? 1 : 2), 0);
		const scale = want > FLOW_MAX_DOTS ? FLOW_MAX_DOTS / want : 1;
		for (const [i, r] of roads.entries()) {
			if (r.coordinates.length < 2) continue;
			const pts = r.coordinates.map(([lon, lat]) => cesium.Cartesian3.fromDegrees(lon, lat, h + 2));
			const cum = [0];
			for (let k = 1; k < pts.length; k++) cum.push(cum[k - 1] + cesium.Cartesian3.distance(pts[k - 1], pts[k]));
			const len = cum[cum.length - 1];
			if (!(len > 20)) continue;
			const n = Math.max(1, Math.round(dotsFor(len, r.congestion) * scale));
			// the dot wears its road's colour, lightened (the road's line under it carries the same meaning)
			const dotInk = cesium.Color.fromCssColorString(r.ink ?? 'rgba(255, 255, 255, 0.95)');
			const track: Track = { pts, cum, len, speed: (Math.max(2, r.speedKmh) / 3.6) * FLOW_TIME_LAPSE, dots: [] };
			for (const dir of r.oneway ? [1 as const] : [1 as const, -1 as const]) {
				for (let k = 0; k < n; k++) {
					const p = points.add({ position: pts[0], pixelSize: 4.5, color: dotInk, outlineColor: dotRim, outlineWidth: 1.25, disableDepthTestDistance: Number.POSITIVE_INFINITY });
					track.dots.push({ p, off: (len * (k + (dir < 0 ? 0.5 : 0))) / n, dir });
					dotCount++;
				}
			}
			tracks.push(track);
			// the road's name and reading at its midpoint
			const half = len / 2;
			let j = 1;
			while (j < cum.length - 1 && cum[j] < half) j++;
			const mid = cesium.Cartesian3.lerp(pts[j - 1], pts[j], (half - cum[j - 1]) / (cum[j] - cum[j - 1] || 1), new cesium.Cartesian3(0, 0, 0));
			const text = roadText(r, lang);
			const label = labels.add({
				position: mid,
				text,
				font: canvasFont('600 12px var(--v-font-ui)'),
				fillColor: ink,
				outlineColor: halo,
				outlineWidth: 3,
				style: cesium.LabelStyle?.FILL_AND_OUTLINE ?? 2,
				verticalOrigin: cesium.VerticalOrigin?.CENTER ?? 0,
				horizontalOrigin: cesium.HorizontalOrigin?.CENTER ?? 0,
				disableDepthTestDistance: Number.POSITIVE_INFINITY,
				show: false,
			});
			const box = labelBox(text, 12);
			items.push({ key: `road:${r.segmentId}`, priority: r.congestion > 0.6 ? 1.5 : 3, position: mid, w: box.w + 30, h: box.h, dy: box.h / 2, maxAlt: 9_000, apply: (show) => (label.show = show) });
			bySeg.set(r.segmentId, { track, label });
			void i;
		}
		declutterFor(ctx).set('flow', items);
	}

	return {
		update,
		clear,
		get dots() {
			return dotCount;
		},
		destroy() {
			clear();
			off?.();
			off = null;
		},
	};
}
