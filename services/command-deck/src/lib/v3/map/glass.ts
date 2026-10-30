/**
 * The map's glass surface (V3-P4 review item 6): every overlay that floats over the map — the Now list, the layers
 * and stats panels, the legend, the selection card, the chips and the tools — sits on a translucent grey-tinted
 * glass. The values are the V3 glass tokens (`--v3-glass-bg`, `--v3-glass-solid`, `--v3-glass-border`,
 * `--v3-glass-blur`), set on the map's root and used through the `.v3-glass` surface (MapPage):
 *
 *   - where the browser has backdrop-filter, the translucent `bg` (and, with the blur enabled, the `blur`);
 *   - where it has not, the `solid` fallback.
 *
 * The background's alpha is chosen so that EVERY V3 text ink keeps ≥ 4.5:1 even with NO blur, composited over the
 * darkest (black) and the lightest (white) pixel a map can put under it — the night OSM grade, the photoreal city and
 * the white-hot thermal-style filter all lie between them (tests/v3-map.unit.mjs computes it from tokens.ts).
 * No hex here: rgb()/rgba() only (the hex sweep keeps hex in the token files).
 */
export const GLASS = Object.freeze({
	/** The translucent glass (alpha 0.9 over a neutral grey). */
	bg: 'rgba(24, 24, 24, 0.9)',
	/** Where backdrop-filter is unsupported: the same tint, opaque. */
	solid: 'rgb(24, 24, 24)',
	border: 'rgba(255, 255, 255, 0.14)',
	/** The blur the glass uses where backdrop-filter is supported. */
	blur: 'blur(14px) saturate(140%)',
});

/** The glass tokens as CSS custom properties (set on the map's root). */
export function glassVars(): string {
	return `--v3-glass-bg:${GLASS.bg};--v3-glass-solid:${GLASS.solid};--v3-glass-border:${GLASS.border};--v3-glass-blur:${GLASS.blur}`;
}

/** The browser can blur what lies behind an element (the glass's translucent form); false → the solid fallback. */
export function glassSupported(): boolean {
	try {
		return typeof CSS !== 'undefined' && (CSS.supports('backdrop-filter', 'blur(1px)') || CSS.supports('-webkit-backdrop-filter', 'blur(1px)'));
	} catch {
		return false;
	}
}
