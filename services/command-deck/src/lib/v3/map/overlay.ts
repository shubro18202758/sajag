/**
 * What a MapThumb draws over the map (V3-SPEC §4.6): only the one thing that matters — a route, a pin,
 * a trail, a road. Meaning is the colour role (§4.2): teal a protected route (travelled dim, ahead bright),
 * orange dot a decision waits, red a stolen / watchlisted vehicle and its reads, green the 108 corridor,
 * dashed neutral an unverified place, sky (--v-map-water) a road at waterlogging risk.
 */
import type { LonLat } from './mercator';

export type LineStyle = 'route' | 'route-done' | 'trail' | 'green' | 'road' | 'water' | 'dashed' | 'flood';
export type PointTone = 'neutral' | 'route' | 'alert' | 'brand';

export interface ThumbLine {
	coords: readonly LonLat[];
	style: LineStyle;
}

export interface ThumbPoint {
	at: LonLat;
	tone?: PointTone;
	/** A V3 glyph name (the TYPE of the thing; its state is the colour). */
	glyph?: string;
	/** An orange dot: a decision waits on this place. */
	decide?: boolean;
	/** A soft ring around it (the subject of the card). */
	halo?: boolean;
	/** A small read dot instead of a marker (a trail's earlier reads). */
	small?: boolean;
	label?: string | null;
	sub?: string | null;
	labelSide?: 'l' | 'r';
}

export interface ThumbRing {
	at: LonLat;
	/** Radius in metres (an official warning's area, a matched place's uncertainty). */
	radiusM: number;
}

export interface ThumbOverlay {
	lines?: readonly ThumbLine[];
	points?: readonly ThumbPoint[];
	rings?: readonly ThumbRing[];
}

/** Every lon/lat an overlay touches (the thumb frames them). */
export function overlayPoints(o: ThumbOverlay | null | undefined): LonLat[] {
	if (!o) return [];
	return [...(o.lines ?? []).flatMap((l) => l.coords), ...(o.points ?? []).map((p) => p.at), ...(o.rings ?? []).map((r) => r.at)];
}
