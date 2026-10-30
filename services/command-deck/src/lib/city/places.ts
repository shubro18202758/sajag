/**
 * The City Pack's named places as map marks (places.generated.ts, from landmarks.json, gazetteer.json and
 * network.json by scripts/gen_deck_places.mjs): the labelled reference geography the map opens with. Reference
 * places only, never people; their names in EN / MR / HI where the pack holds them (a station's Hindi name falls back
 * to its signage name).
 */

import { PLACE_MARK_ROWS } from './places.generated';
import type { CityLang } from './index';

export type PlaceMarkKind =
	| 'junction'
	| 'bridge'
	| 'terminal'
	| 'venue'
	| 'hospital'
	| 'ghat'
	| 'pandal'
	| 'hydro'
	| 'police'
	| 'traffic'
	| 'fire'
	| 'ems'
	| 'post'
	| 'area'
	| 'market'
	| 'lowlying'
	| 'landmark';

export interface PlaceMark {
	readonly id: string;
	readonly kind: PlaceMarkKind;
	/** 1 landmark · 2 area, venue, ghat, terminal, hotspot · 3 station, pandal. */
	readonly tier: 1 | 2 | 3;
	readonly lon: number;
	readonly lat: number;
	readonly en: string;
	readonly mr: string;
	readonly hi: string;
	/** Where the row came from in the City Pack. */
	readonly src: 'landmarks' | 'gazetteer' | 'network' | 'network-osm';
	readonly lowLying?: boolean;
}

export const PLACE_MARKS: readonly PlaceMark[] = PLACE_MARK_ROWS as unknown as readonly PlaceMark[];

/** The place's name in the UI language (English when the pack has none). */
export function placeMarkName(p: PlaceMark, lang?: CityLang | string | null): string {
	if (lang === 'mr') return p.mr || p.en;
	if (lang === 'hi') return p.hi || p.en;
	return p.en;
}

/** Counts by kind (the layer's honest detail). */
export function placeMarkCounts(rows: readonly PlaceMark[] = PLACE_MARKS): Record<string, number> {
	const out: Record<string, number> = {};
	for (const r of rows) out[r.kind] = (out[r.kind] ?? 0) + 1;
	return out;
}
