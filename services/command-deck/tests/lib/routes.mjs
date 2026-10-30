/**
 * The ONE place the smokes and unit tests name the two roots (V3 P5, the root flip).
 *
 *   WORKSPACE  the Analyst workspace — the v2 corridor page that used to be `/`
 *              (route node `/(deck)`, data-template="convoy-command", the operator CSP)
 *   HOME       V3 Home (route node `/(v3)/home`; `/home` keeps answering as an alias)
 *
 * A test that opens the workspace imports WORKSPACE; it never spells `/` or `/#…` for it. The values are
 * pinned against the app by tests/root-flip.unit.mjs (they must equal src/lib/shell/root-flip.ts) and
 * proven live by tests/root-flip-smoke.mjs.
 */
export const WORKSPACE = '/analyst';
export const HOME = '/';

/** The workspace URL under `origin`, with an optional hash (with or without '#'). */
export function workspaceUrl(origin, hash = '') {
	const h = String(hash ?? '').replace(/^#/, '');
	return `${origin}${WORKSPACE}${h ? `#${h}` : ''}`;
}

/** The workspace path with an optional hash. */
export function workspacePath(hash = '') {
	const h = String(hash ?? '').replace(/^#/, '');
	return `${WORKSPACE}${h ? `#${h}` : ''}`;
}

/** The route node SvelteKit resolves each URL to (route-budget and route-coldload key their bundles by these). */
export const NODE = { [WORKSPACE]: '/(deck)', [HOME]: '/(v3)/home', '/home': '/(v3)/home' };

/**
 * The routes route-budget.unit.mjs and route-coldload.mjs hold to a ceiling, keyed by URL, valued by the route node
 * the built client dictionary names. The mapping is the TESTS' (not the JSON's): `/analyst` is the workspace's node,
 * `/` and `/home` are Home's. Extra routes named under "routes" in tests/route-budget.json are added.
 */
export function budgetRoutes(ceil) {
	return {
		[WORKSPACE]: '/(deck)',
		[HOME]: '/(v3)/home',
		'/home': '/(v3)/home',
		'/ops': '/(deck)/ops',
		'/gods-eye': '/(deck)/gods-eye',
		...(ceil?.routes ?? {}),
	};
}

/**
 * The ceiling `url` is held to in `table` (one of route-budget.json's "static" / "coldload_en" / "coldload_hi_mr").
 * Reads whichever keys exist, so the same tests pass before and after the JSON moves its keys:
 *   - after the root flip the file carries `/analyst` (the workspace's old `/` figures) and its own `/` and `/home`;
 *   - before it, the file's `/` IS the workspace's ceiling: `/analyst` reads it, and Home (`/`, `/home`) is held to it
 *     too (Home is the lighter page; the stricter Home ceilings arrive with the JSON).
 */
export function ceilingOf(table, url) {
	if (!table) return undefined;
	if (typeof table[url] === 'number') return table[url];
	const legacy = typeof table[WORKSPACE] !== 'number' && typeof table[HOME] === 'number';
	if (url === WORKSPACE && legacy) return table[HOME];
	if (url === '/home' && typeof table[HOME] === 'number') return table[HOME];
	return undefined;
}
