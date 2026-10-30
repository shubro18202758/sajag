/**
 * The road geometry the public pages draw on their map thumbnails (V3-SPEC §6.8) — the SAME public read the corridor map
 * makes (GET /api/v1/spatial/segments, the one /api path a public page may call besides /api/public/*), read once per page
 * view and shared. Pure helpers below turn a held stretch into the overlay MapThumb draws.
 *
 * Honesty (as the corridor map's): a LIVE event's stretch draws solid; a fixture, emulated or unverified one draws DASHED,
 * never as a live road hold. No operator store, no registry, no officer code is imported here.
 */
import { fetchSegments, type SegmentGeometry } from '$lib/gods-eye/data';
import { NETWORK_BBOX } from '$lib/ops/endpoints';
import type { LonLat } from '../map/mercator';
import type { ThumbOverlay } from '../map/overlay';

let memo: Promise<Map<number, SegmentGeometry>> | null = null;

/** Every segment of the network by id (one request per page view; a failed read is retried on the next ask). */
export function loadSegments(): Promise<Map<number, SegmentGeometry>> {
	if (!memo) {
		memo = fetchSegments(NETWORK_BBOX)
			.then((list) => new Map(list.map((sg) => [sg.segmentId, sg])))
			.catch((err) => {
				memo = null;
				throw err;
			});
	}
	return memo;
}

const d2 = (a: LonLat, b: LonLat) => (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2;

/** Segments chained in route order: each one turned so it starts where the last one ended. */
export function chainSegments(ids: readonly number[], segs: ReadonlyMap<number, { coordinates: Array<[number, number]> }>): LonLat[] {
	const out: LonLat[] = [];
	for (const id of ids) {
		const s = segs.get(id)?.coordinates;
		if (!s || s.length < 2) continue;
		let pts: LonLat[] = s as LonLat[];
		if (out.length) {
			const end = out[out.length - 1];
			if (d2(end, s[s.length - 1] as LonLat) < d2(end, s[0] as LonLat)) pts = [...(s as LonLat[])].reverse();
		}
		out.push(...(out.length ? pts.slice(1) : pts));
	}
	return out;
}

/** The overlay of one held stretch set: the road (solid when live, dashed otherwise) and one pin at its middle. */
export function holdOverlay(
	ids: readonly number[],
	segs: ReadonlyMap<number, { coordinates: Array<[number, number]> }>,
	live: boolean,
): ThumbOverlay | null {
	const route = chainSegments(ids, segs);
	if (route.length < 2) return null;
	return {
		lines: [{ coords: route, style: live ? 'route' : 'dashed' }],
		points: [{ at: route[Math.floor(route.length / 2)], glyph: 'pin', tone: 'brand' }],
	};
}
