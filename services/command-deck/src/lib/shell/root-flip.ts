/**
 * The V3 root flip (V3-SPEC §3.2, §10 P5): `/` is Home and the v2 corridor workspace lives at `/analyst`.
 *
 * The flip is a SvelteKit `reroute` (src/hooks.ts), not a file move: the workspace keeps its route node
 * (`src/routes/(deck)/+page.svelte`, id `/(deck)`), so it keeps `data-template="convoy-command"`, its test
 * ids and the OPERATOR content-security policy and gate, which hooks.server.ts decides from `event.route.id`
 * (never from the URL). Home keeps its own node (`/(v3)/home`) and `/home` keeps answering as an alias.
 *
 * This module is the one place that knows both spellings: the reroute table, the workspace's hash keys (an
 * old bookmark `/#v=2…` belongs to the workspace and is handed to `/analyst#v=2…`), and the early script
 * Home runs before first paint so that hand-over never shows Home. It is plain TypeScript with no imports,
 * so the reroute (universal: server and browser), the page and tests/root-flip.unit.mjs all read it.
 */

/** The URL of V3 Home. */
export const HOME_URL = '/';
/** The URL of the Analyst workspace (the v2 page that used to be `/`). */
export const WORKSPACE_URL = '/analyst';

/** The route paths the two URLs resolve to (the files under src/routes keep their place). */
export const HOME_NODE = '/home';
export const WORKSPACE_NODE = '/';

/** pathname → the pathname SvelteKit should resolve a route for. Anything absent resolves as itself. */
export const REROUTES: Readonly<Record<string, string>> = Object.freeze({
	'/': HOME_NODE,
	[WORKSPACE_URL]: WORKSPACE_NODE,
	[`${WORKSPACE_URL}/`]: WORKSPACE_NODE,
});

/** The reroute: the resolved pathname for `pathname`, or undefined to leave it alone. */
export function reroutePath(pathname: string): string | undefined {
	return Object.prototype.hasOwnProperty.call(REROUTES, pathname) ? REROUTES[pathname] : undefined;
}

/**
 * The hash keys that belong to the workspace: the God's-eye share link's own (camera, style, layers, sel;
 * gods-eye/share-link.ts), the workspace's (view, window, filters, docks, items; workspace/hash.ts) and the
 * decision homes' deep links (inbox, movement). Home's own anchors (#v3-live, #v3-reported) carry none.
 */
export const WORKSPACE_HASH_KEYS: readonly string[] = Object.freeze([
	'v',
	'lat',
	'lon',
	'alt',
	'heading',
	'pitch',
	'roll',
	'style',
	'bhot',
	'palette',
	'layers',
	'sel',
	'view',
	't0',
	't1',
	'f',
	'dock',
	'items',
	'inbox',
	'movement',
]);

/** True when `hash` (with or without the leading '#') carries a workspace key — an old `/#…` bookmark. */
export function isWorkspaceHash(hash: string | null | undefined): boolean {
	const body = typeof hash === 'string' ? hash.replace(/^#/, '') : '';
	if (!body) return false;
	let pairs: [string, string][];
	try {
		pairs = [...new URLSearchParams(body).entries()];
	} catch {
		return false;
	}
	// a key counts with a value; the one bare key is `#inbox` (the canvas-less pages' inbox button used to open `/#inbox`)
	return pairs.some(([k, v]) => WORKSPACE_HASH_KEYS.includes(k) && (v !== '' || k === 'inbox'));
}

/** Where an old `/#…` bookmark lands: `/analyst#…` when the hash is the workspace's, else null (stay on Home). */
export function workspaceHandOver(hash: string | null | undefined): string | null {
	const h = typeof hash === 'string' ? hash : '';
	return isWorkspaceHash(h) ? `${WORKSPACE_URL}${h.startsWith('#') ? h : `#${h}`}` : null;
}

/**
 * The same hand-over as one inline script, for Home's <head>: it runs while the document is still being
 * parsed, so an old bookmark replaces the entry before Home paints (a fragment never reaches the server, so
 * no server redirect can do this). The key list is the one above; the script holds no URL but the workspace's.
 * hooks.server.ts gives every inline script the response's CSP nonce.
 */
export function earlyHandOverScript(): string {
	const keys = JSON.stringify(WORKSPACE_HASH_KEYS);
	return (
		`(function(){try{var h=location.hash;if(h.length<2)return;var k=${keys},p=new URLSearchParams(h.slice(1)),f=false;` +
		`p.forEach(function(v,n){if(k.indexOf(n)>=0&&(v!==''||n==='inbox'))f=true});` +
		`if(f)location.replace(${JSON.stringify(WORKSPACE_URL)}+h)}catch(e){}})();`
	);
}

/** `earlyHandOverScript()` as a <script> element, for `{@html}` in Home's <svelte:head>. */
export function earlyHandOverTag(): string {
	return `<script>${earlyHandOverScript()}</script>`;
}
