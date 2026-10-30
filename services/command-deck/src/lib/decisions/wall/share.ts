/**
 * The situation wall's share link (SPEC §6.3 header, §7.5): the existing
 * share-link freeze — the whole-city camera, the COMMAND sensor and every
 * layer — in today's `#v=2` hash, so any receiver (old or new) opens the
 * city as the wall frames it. A link carries URNs only, never a mark
 * (masked egress); the wall's link carries no selection at all.
 */
import type { ShareViewState } from '$lib/gods-eye/share-link';
import { GODS_EYE_LAYER_IDS } from '$lib/gods-eye/layers';
import { parseUrn } from '$lib/gods-eye/city-api';
import { CITY_BBOX } from '$lib/city';

/** The whole city as the wall frames it (the City Pack box's centre, 2.6 km up, 35° down). */
export const WALL_VIEW: ShareViewState = {
	lat: (CITY_BBOX.minLat + CITY_BBOX.maxLat) / 2,
	lon: (CITY_BBOX.minLon + CITY_BBOX.maxLon) / 2,
	alt: 2600,
	heading: 0,
	pitch: -35,
	roll: 0,
	style: 'raw', // COMMAND — the canvas default sensor
	bhot: false,
	layers: [...GODS_EYE_LAYER_IDS],
};

/**
 * What a hand-off from the wall to `/` carries (Open in workspace, the Mode
 * chip): the operator's pick, else the object the page shows without one
 * (the docked inspector's), else nothing. A URN only — never a mark.
 */
export function carriedUrn(current: string | null | undefined, focus: string | null | undefined): string | null {
	if (current && parseUrn(current)) return current;
	return focus && parseUrn(focus) ? focus : null;
}
