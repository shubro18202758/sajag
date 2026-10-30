/**
 * The map style rules (V3-P4C) — pure, no DOM, no store; tests/v3-map-style.unit.mjs drives them.
 *
 * Two choices, both remembered per browser (localStorage, written only when the officer chooses):
 *   • the base map of /map (the canvas):  'sat3d' = the natural photoreal 3D city,  'city' = the OSM city map.
 *     The default is the photoreal city whenever the deck has the Cesium ion key; without the key it is the city
 *     map (with the honest reason the 3D city is off).
 *   • the style of every MapThumb (Home, Decide, the object pages, the Layers sheet):  'satellite' = natural-colour
 *     imagery, no grading;  'map' = the night-graded OSM raster.  The default is satellite whenever the key exists.
 * A thumb that cannot have satellite (no key, a dead token, a spent quota, the per-session request cap) draws the
 * night tiles instead — see satellite.ts.
 */

export type StylePref = 'satellite' | 'map';
export type BasePref = 'sat3d' | 'city';
/** What a MapThumb draws: natural satellite imagery, or the night-graded OSM raster. */
export type ThumbStyle = 'satellite' | 'night';

export const STYLE_KEY = 'sajag.v3.map.style';
export const BASE_KEY = 'sajag.v3.map.base';

export const parseStylePref = (v: unknown): StylePref | null => (v === 'satellite' || v === 'map' ? v : null);
export const parseBasePref = (v: unknown): BasePref | null => (v === 'sat3d' || v === 'city' ? v : null);

/**
 * The style a thumb draws. `keyed` is null until the deck has answered whether it holds the ion key (a thumb waits
 * for that — a few ms — rather than flashing the wrong style); `degraded` is a satellite refusal this session.
 */
export function resolveThumbStyle(o: { pref: StylePref | null; keyed: boolean | null; degraded: boolean }): ThumbStyle | null {
	if (o.keyed === null) return null;
	if (!o.keyed || o.degraded) return 'night';
	return o.pref === 'map' ? 'night' : 'satellite';
}

/** The base map /map opens on: the photoreal city when it can be had and the officer has not chosen the city map. */
export function resolveBase(o: { pref: BasePref | null; can3d: boolean }): BasePref {
	return o.can3d && o.pref !== 'city' ? 'sat3d' : 'city';
}

/** The canvas's start layers: the V3 clean defaults, plus the photoreal city when the base map is satellite 3D. */
export function startLayers(defaults: readonly string[], base: BasePref): string[] {
	return base === 'sat3d' ? [...defaults.filter((id) => id !== 'photoreal-3d'), 'photoreal-3d'] : defaults.filter((id) => id !== 'photoreal-3d');
}
