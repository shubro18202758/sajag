/**
 * The COMPLETE icon tables (FIX-E-PERF2): `ICONS_16` / `ICONS_20` exactly as
 * they were before the split — every glyph, frozen, in the original key order —
 * re-exported by ./icons.ts for the callers that list or read the whole set
 * (the /design glyph gallery, the tests). Nothing on a route's first paint
 * reads them: the deck draws through `iconPaths()` (./icons.ts), which serves
 * the first-paint half at once and the rest on first use. This module is pure
 * (no side effect), so a bundle that never touches the two names drops it and
 * the deferred half it imports.
 */
import type { IconName } from './icons';
import { CORE_16, CORE_20, ICON_NAMES } from './icons-core';
import { REST_16, REST_20 } from './icons-rest';

function merged16(): Readonly<Record<IconName, readonly string[]>> {
	const out = {} as Record<IconName, readonly string[]>;
	for (const n of ICON_NAMES) out[n] = CORE_16[n] ?? REST_16[n];
	return Object.freeze(out);
}

function merged20(): Readonly<Partial<Record<IconName, readonly string[]>>> {
	const out: Partial<Record<IconName, readonly string[]>> = {};
	for (const n of ICON_NAMES) {
		const p = CORE_20[n] ?? REST_20[n];
		if (p) out[n] = p;
	}
	return Object.freeze(out);
}

/** 16 px grid path data (viewBox 0 0 16 16), one or more evenodd paths per icon — all 206. */
export const ICONS_16: Readonly<Record<IconName, readonly string[]>> = /*#__PURE__*/ merged16();

/** 20 px grid path data (viewBox 0 0 20 20) for the icons drawn at 20 px and above. */
export const ICONS_20: Readonly<Partial<Record<IconName, readonly string[]>>> = /*#__PURE__*/ merged20();
