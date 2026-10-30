/**
 * V3 map style unit test (V3-P4C: natural-colour satellite imagery everywhere) — zero browser, zero network.
 *
 *   node tests/v3-map-style.unit.mjs
 *
 * esbuild bundles the REAL modules ($lib aliased; .svelte / .svelte.ts compiled for the server, the v3-map.unit
 * pattern) and drives them:
 *
 *   rules      resolveThumbStyle: no answer yet → wait (null); no key → night; a refusal this session → night; key →
 *              satellite unless the officer chose the map. resolveBase: the photoreal 3D city by default when it can be
 *              had, the city map when the officer chose it or there is no key. startLayers adds photoreal-3d only for
 *              satellite 3D, never twice. Stored values are validated (a stray string is no choice).
 *   bing       quadKey (Bing's documented example), the tile URL (integers only, https virtualearth.net only), the
 *              metadata parser (rejects another host / tile size), the attribution text (an <img alt> credit is its alt,
 *              no markup survives), the per-area copyright lines and the credit line.
 *   quota      the satellite source with a fake network: the happy path is endpoint → metadata → tile with the ion token in
 *              the endpoint URL only; the session cap is HARD (the 801st request is never sent, the session stands down
 *              once, silently); a 401 / 403 on the endpoint or a tile, and a 429, stand the session down and are
 *              remembered; requests queued behind a refusal are NOT sent; three transient failures stand it down for the
 *              page view; a non-Bing source is unsupported; at most 4 requests in flight; the token never appears in a
 *              tile or metadata URL, an error message or the console.
 *   caps       a card frames to ≤ 6 tiles (a hero ≤ 40), at the sizes the V3 cards, hero and stage really have.
 *   contrast   overlays stay readable on the brightest and the darkest imagery: label ink over its halo, the lines over
 *              their casing, read from the CSS actually shipped in MapThumb.svelte.
 *   pack       MapStyleSwitch's words: EN / HI / MR carry the same keys, v3ms_ prefix, translated, in their own script,
 *              "not a live image" in all three.
 *   render     MapStyleSwitch: two toggle buttons (aria-pressed), satellite pressed by default, off with its reason
 *              without the key or after a refusal, the map pressed when chosen; LayersSheet carries it.
 *   wiring     Home, Decide, the object hero and the assistant cards pass no style (they inherit); MapThumb follows the
 *              shared preference, falls back to night for a draw when no satellite tile came, shares ONE tile queue with
 *              the night tiles; the page never prints the token; /map waits for the deck's imagery answer before the
 *              canvas mounts and starts the photoreal city from the remembered base map.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const SRC = path.join(DECK, 'src');
const OUT_DIR = path.join(HERE, 'artifacts');
mkdirSync(OUT_DIR, { recursive: true });

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

const req = createRequire(path.join(DECK, 'package.json'));
const esbuild = req('esbuild');
const { compile, compileModule } = req('svelte/compiler');

globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });
globalThis.$props = () => ({});
globalThis.$bindable = (v) => v;

const sveltePlugin = {
	name: 'svelte-ssr',
	setup(b) {
		b.onLoad({ filter: /\.svelte$/ }, async (args) => {
			const src = readFileSync(args.path, 'utf8');
			const { js } = compile(src, { filename: args.path, generate: 'server', css: 'injected', dev: false });
			return { contents: js.code, loader: 'js', resolveDir: path.dirname(args.path) };
		});
		b.onLoad({ filter: /\.svelte\.(ts|js)$/ }, async (args) => {
			const src = readFileSync(args.path, 'utf8');
			const plain = args.path.endsWith('.ts') ? (await esbuild.transform(src, { loader: 'ts' })).code : src;
			const { js } = compileModule(plain, { filename: args.path, generate: 'server', dev: false });
			return { contents: js.code, loader: 'js', resolveDir: path.dirname(args.path) };
		});
	},
};

const ENTRY = `
export { render } from 'svelte/server';
export * as rules from './src/lib/v3/map/style-rules';
export * as sat from './src/lib/v3/map/satellite';
export * as merc from './src/lib/v3/map/mercator';
export * as tiles from './src/lib/v3/map/tiles';
export { mapStyle } from './src/lib/v3/map/map-style.svelte';
export { MAPSTYLE_PACKS } from './src/lib/v3/map/packs.mapstyle';
export { t } from './src/lib/i18n/strings';
export { default as MapStyleSwitch } from './src/lib/v3/map/MapStyleSwitch.svelte';
export { default as LayersSheet } from './src/lib/v3/map/LayersSheet.svelte';
export * as tokens from './src/lib/v3/tokens';
`;
const OUT = path.join(OUT_DIR, 'v3-map-style-bundle.mjs');
let M = null;
try {
	const built = await esbuild.build({
		stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'v3-map-style-entry.ts' },
		absWorkingDir: DECK,
		alias: { $lib: './src/lib' },
		bundle: true,
		format: 'esm',
		platform: 'node',
		conditions: ['svelte', 'node'],
		outfile: OUT,
		logLevel: 'silent',
		plugins: [sveltePlugin],
	});
	ok('bundle builds (the real rules, satellite source, store and components; svelte/server)', built.errors.length === 0, `${built.errors.length} errors`);
	M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
} catch (err) {
	ok('bundle builds (the real rules, satellite source, store and components; svelte/server)', false, String(err?.message ?? err).slice(0, 400));
}
if (!M) {
	console.log(`\n${failures} failure(s)`);
	process.exit(1);
}
const { rules, sat } = M;
const read = (p) => readFileSync(path.join(SRC, p), 'utf8');

// ─── rules ───────────────────────────────────────────────────────────────────
{
	const R = rules.resolveThumbStyle;
	ok('rules: the deck has not answered yet → wait (null), never a flash of the wrong style', R({ pref: null, keyed: null, degraded: false }) === null && R({ pref: 'map', keyed: null, degraded: false }) === null);
	ok('rules: no ion key → the night map, whatever was chosen', R({ pref: 'satellite', keyed: false, degraded: false }) === 'night' && R({ pref: null, keyed: false, degraded: false }) === 'night');
	ok('rules: the key and no choice → natural satellite (the default)', R({ pref: null, keyed: true, degraded: false }) === 'satellite');
	ok('rules: the key and the officer chose Satellite → satellite; chose Map → night', R({ pref: 'satellite', keyed: true, degraded: false }) === 'satellite' && R({ pref: 'map', keyed: true, degraded: false }) === 'night');
	ok('rules: a refusal this session (401 / 429 / the cap) → night, even when Satellite is chosen', R({ pref: 'satellite', keyed: true, degraded: true }) === 'night' && R({ pref: null, keyed: true, degraded: true }) === 'night');
	ok('rules: /map opens on satellite 3D when it can (default or chosen), on the city map when the officer chose it', rules.resolveBase({ pref: null, can3d: true }) === 'sat3d' && rules.resolveBase({ pref: 'sat3d', can3d: true }) === 'sat3d' && rules.resolveBase({ pref: 'city', can3d: true }) === 'city');
	ok('rules: no key → the city map (the honest reason is on the 3D control)', rules.resolveBase({ pref: null, can3d: false }) === 'city' && rules.resolveBase({ pref: 'sat3d', can3d: false }) === 'city');
	const D = ['events', 'convoy', 'traces', 'enforcement', 'osint'];
	ok('rules: satellite 3D starts the photoreal layer once; the city map starts without it', rules.startLayers(D, 'sat3d').filter((x) => x === 'photoreal-3d').length === 1 && rules.startLayers([...D, 'photoreal-3d'], 'sat3d').filter((x) => x === 'photoreal-3d').length === 1 && !rules.startLayers(D, 'city').includes('photoreal-3d') && rules.startLayers(D, 'sat3d').slice(0, 5).join() === D.join());
	ok('rules: a stored value is a choice only when it is one of ours', rules.parseStylePref('satellite') === 'satellite' && rules.parseStylePref('map') === 'map' && rules.parseStylePref('night') === null && rules.parseStylePref('<x>') === null && rules.parseStylePref(null) === null && rules.parseBasePref('sat3d') === 'sat3d' && rules.parseBasePref('city') === 'city' && rules.parseBasePref('3d') === null);
	ok('rules: the keys are per browser and v3-scoped', rules.STYLE_KEY === 'sajag.v3.map.style' && rules.BASE_KEY === 'sajag.v3.map.base');
}

// ─── bing ────────────────────────────────────────────────────────────────────
const META = {
	resourceSets: [
		{
			resources: [
				{
					imageUrl: 'https://ecn.{subdomain}.tiles.virtualearth.net/tiles/a{quadkey}.jpeg?g=15646',
					imageUrlSubdomains: ['t0', 't1', 't2', 't3'],
					imageWidth: 256,
					imageHeight: 256,
					zoomMax: 21,
					imageryProviders: [
						{ attribution: '© 2026 Microsoft Corporation', coverageAreas: [{ zoomMin: 1, zoomMax: 21, bbox: [-90, -180, 90, 180] }] },
						{ attribution: '© 2026 Maxar', coverageAreas: [{ zoomMin: 12, zoomMax: 19, bbox: [20, 85, 25, 90] }] },
						{ attribution: '© 2026 Elsewhere', coverageAreas: [{ zoomMin: 1, zoomMax: 21, bbox: [40, 0, 50, 10] }] },
					],
				},
			],
		},
	],
};
const ENDPOINT = {
	externalType: 'BING',
	type: 'IMAGERY',
	options: { url: 'https://dev.virtualearth.net', key: 'BINGKEY-FAKE', mapStyle: 'Aerial' },
	attributions: [
		{ html: '<span><a href="https://cesium.com" target="_blank"><img src="https://assets.ion.cesium.com/ion-credit.png" alt="Cesium ion"></a></span>', collapsible: false },
		{ html: '<a href="https://cesium.com/pricing/" target="_blank">Upgrade for commercial use.</a>', collapsible: false },
	],
};
{
	ok('bing: quadKey is Bing’s documented example (tile 3,5 at level 3 → "213")', sat.quadKey(3, 3, 5) === '213' && sat.quadKey(1, 0, 0) === '0' && sat.quadKey(1, 1, 1) === '3' && sat.quadKey(0, 0, 0) === '');
	const setup = sat.parseBingMetadata(META);
	ok('bing: the metadata parses into a template, subdomains, the highest zoom and the area credits', setup && setup.zoomMax === 21 && setup.subdomains.length === 4 && setup.providers.length === 3);
	const u = sat.bingTileUrl(setup, 15, 22863, 14267);
	ok('bing: the tile URL is the template with a quadkey and a subdomain, https virtualearth.net only', /^https:\/\/ecn\.t[0-3]\.tiles\.virtualearth\.net\/tiles\/a\d{15}\.jpeg\?g=15646&n=z$/.test(u) && sat.isBingHost(u), u);
	ok('bing: the tile URL takes integers only (a fraction or text cannot reach it)', sat.bingTileUrl(setup, 15.9, 3.7, 5.2) === sat.bingTileUrl(setup, 15, 3, 5) && !/NaN|undefined/.test(sat.bingTileUrl(setup, 15.9, 3.7, 5.2)));
	ok('bing: only https virtualearth.net is ever asked (the deck’s CSP admits exactly it)', sat.isBingHost('https://dev.virtualearth.net') && !sat.isBingHost('http://dev.virtualearth.net') && !sat.isBingHost('https://virtualearth.net.evil.example') && !sat.isBingHost('https://evil.example/virtualearth.net') && !sat.isBingHost('not a url'));
	const evil = JSON.parse(JSON.stringify(META));
	evil.resourceSets[0].resources[0].imageUrl = 'https://evil.example/tiles/a{quadkey}.jpeg';
	const big = JSON.parse(JSON.stringify(META));
	big.resourceSets[0].resources[0].imageWidth = 512;
	ok('bing: metadata that names another host or another tile size is refused', sat.parseBingMetadata(evil) === null && sat.parseBingMetadata(big) === null && sat.parseBingMetadata({}) === null && sat.parseBingMetadata(null) === null);
	ok('bing: attribution text — an <img alt> credit is its alt, no markup survives', sat.plainText(ENDPOINT.attributions[0].html) === 'Cesium ion' && sat.plainText(ENDPOINT.attributions[1].html) === 'Upgrade for commercial use.' && sat.plainText('<b onclick="x()">A &amp; B &copy;</b><script>1</script>') === 'A & B © 1');
	ok('bing: the endpoint’s credits are collected as plain text, once each', JSON.stringify(sat.endpointCredits(ENDPOINT)) === JSON.stringify(['Cesium ion', 'Upgrade for commercial use.']) && sat.endpointCredits({}).length === 0);
	// Kolkata: lon 88.2-88.5, lat 22.45-22.7 (bbox west, south, east, north)
	const here = sat.providerCredits(setup.providers, 15, [88.2, 22.45, 88.5, 22.7]);
	ok('bing: the area’s copyright lines are those whose coverage includes the view at that zoom', JSON.stringify(here) === JSON.stringify(['© 2026 Microsoft Corporation', '© 2026 Maxar']), here.join(' | '));
	ok('bing: out of a provider’s zoom range or area, its line is left out', !sat.providerCredits(setup.providers, 10, [88.2, 22.45, 88.5, 22.7]).includes('© 2026 Maxar') && !here.includes('© 2026 Elsewhere'));
	ok('bing: the credit line = the area’s lines (≤ 2) then what ion requires, no repeat', sat.creditLine(['© A', '© B', '© C'], ['Cesium ion', '© A']) === '© A · © B · Cesium ion');
}

// ─── quota ───────────────────────────────────────────────────────────────────
const TOKEN = 'ION-TOKEN-SECRET-VALUE';
function rig(over = {}) {
	const log = [];
	let inFlight = 0;
	let maxInFlight = 0;
	let counter = 0;
	let flag = over.flag ?? null;
	const waiters = [];
	const deps = {
		async fetchJson(url) {
			log.push({ kind: 'json', url });
			if (over.json) return over.json(url, log);
			if (url.startsWith(sat.ION_ENDPOINT_URL)) return { status: 200, json: ENDPOINT };
			return { status: 200, json: META };
		},
		async fetchTile(url) {
			log.push({ kind: 'tile', url });
			await Promise.resolve();
			if (over.tile) return over.tile(url, log);
			return { status: 200, image: { fake: url } };
		},
		wait: () => Promise.resolve(),
		limiter: {
			acquire() {
				if (inFlight < sat.SAT_MAX_IN_FLIGHT) {
					inFlight++;
					maxInFlight = Math.max(maxInFlight, inFlight);
					return Promise.resolve();
				}
				return new Promise((r) => waiters.push(() => (inFlight++, (maxInFlight = Math.max(maxInFlight, inFlight)), r())));
			},
			release() {
				inFlight--;
				waiters.shift()?.();
			},
		},
		store: {
			used: () => counter,
			add: (n) => void (counter += n),
			flag: () => flag,
			setFlag: (d) => void (flag = d),
		},
	};
	const src = new sat.SatelliteSource(deps);
	const degrades = [];
	src.onDegrade = (w) => degrades.push(w);
	return { src, log, degrades, deps, maxIn: () => maxInFlight, counter: () => counter, flag: () => flag, setCounter: (n) => (counter = n) };
}
const errs = [];
const origErr = console.error;
const origWarn = console.warn;
const origLog = console.log;
{
	const r = rig();
	r.src.configure(TOKEN);
	const img = await r.src.tile(15, 22863, 14267);
	ok('quota: endpoint → metadata → tile; the first tile is the image', !!img && r.log.map((l) => l.kind).join() === 'json,json,tile');
	ok('quota: the ion token goes to the endpoint URL only — never into the metadata or a tile URL', r.log[0].url.startsWith(sat.ION_ENDPOINT_URL) && r.log[0].url.includes(TOKEN) && r.log.slice(1).every((l) => !l.url.includes(TOKEN)));
	ok('quota: metadata is asked over https at virtualearth.net with the endpoint’s own key', /^https:\/\/dev\.virtualearth\.net\/REST\/v1\/Imagery\/Metadata\/Aerial\?incl=ImageryProviders&uriScheme=https&key=BINGKEY-FAKE$/.test(r.log[1].url), r.log[1].url);
	ok('quota: every request is counted against the session (endpoint + metadata + tile = 3)', r.counter() === 3);
	await r.src.tile(15, 22864, 14267);
	ok('quota: setup is done once (one more tile = one more request)', r.log.filter((l) => l.kind === 'json').length === 2 && r.counter() === 4);
	const cr0 = r.src.credit(15, [88.2, 22.45, 88.5, 22.7]);
	ok('quota: the credit line is the area’s copyright + what ion requires; the compact one drops the pricing sentence', cr0.full === '© 2026 Microsoft Corporation · © 2026 Maxar · Cesium ion · Upgrade for commercial use.' && cr0.short === '© 2026 Microsoft Corporation · Cesium ion', JSON.stringify(cr0));
}
{
	// the session cap is HARD
	const r = rig();
	r.src.configure(TOKEN);
	await r.src.tile(15, 1, 1); // setup (2) + 1 tile
	r.setCounter(sat.SAT_SESSION_CAP - 3);
	const out = [];
	for (let i = 0; i < 8; i++) out.push(await r.src.tile(15, 100 + i, 5));
	const sent = r.log.filter((l) => l.kind === 'tile').length - 1;
	ok('quota: the session cap is hard — exactly the remaining budget is sent, the rest never leaves the browser', sent === 3 && out.filter(Boolean).length === 3 && r.counter() === sat.SAT_SESSION_CAP, `sent ${sent}, counter ${r.counter()}`);
	ok('quota: spending the cap stands the session down once, silently (cap, no flag kept)', r.degrades.length === 1 && r.degrades[0] === 'cap' && r.src.available === false && r.flag() === null);
	ok('quota: the cap is 800 requests a tab session', sat.SAT_SESSION_CAP === 800);
}
{
	// the hero reserve: a card yields the last SAT_HERO_RESERVE requests to the eager heroes; the cap itself is unchanged
	const r = rig();
	r.src.configure(TOKEN);
	await r.src.tile(15, 1, 1); // setup (2) + 1 tile
	r.setCounter(sat.SAT_SESSION_CAP - sat.SAT_HERO_RESERVE - 2);
	const cards = [];
	for (let i = 0; i < 5; i++) cards.push(await r.src.tile(15, 200 + i, 5, 'card'));
	const cardSent = r.log.filter((l) => l.kind === 'tile').length - 1;
	ok('quota: a card stops at the hero reserve (night tiles for it), silently and without standing the session down', cardSent === 2 && cards.filter(Boolean).length === 2 && r.counter() === sat.SAT_SESSION_CAP - sat.SAT_HERO_RESERVE && r.degrades.length === 0 && r.src.available === true, `sent ${cardSent}, counter ${r.counter()}`);
	const hero = await r.src.tile(15, 300, 5, 'hero');
	ok('quota: a hero still draws satellite inside the reserve', !!hero && r.counter() === sat.SAT_SESSION_CAP - sat.SAT_HERO_RESERVE + 1);
	r.setCounter(sat.SAT_SESSION_CAP - 1);
	const last = [await r.src.tile(15, 301, 5, 'hero'), await r.src.tile(15, 302, 5, 'hero')];
	ok('quota: the reserve ends at the same hard cap (800): the hero\'s 801st request is never sent', !!last[0] && last[1] === null && r.counter() === sat.SAT_SESSION_CAP && r.degrades.join() === 'cap' && sat.SAT_HERO_RESERVE === 200);
	ok('quota: MapThumb asks as a hero only when eager (Home\'s featured decision, a stage), as a card otherwise', /satelliteTile\(t\.z, t\.x, t\.y, eager \? 'hero' : 'card'\)/.test(readFileSync(path.join(DECK, 'src/lib/v3/map/MapThumb.svelte'), 'utf8')));
}
{
	// a reload loop cannot reset the cap: a fresh source on an exhausted store sends nothing
	const r = rig();
	r.setCounter(sat.SAT_SESSION_CAP);
	r.src.configure(TOKEN);
	const t = await r.src.tile(15, 1, 1);
	ok('quota: an exhausted session (kept in sessionStorage) sends nothing after a reload', t === null && r.log.length === 0 && r.degrades.join() === 'cap');
}
for (const status of [401, 403]) {
	const r = rig({ json: (url) => (url.startsWith(sat.ION_ENDPOINT_URL) ? { status, json: null } : { status: 200, json: META }) });
	r.src.configure(TOKEN);
	const t = await r.src.tile(15, 1, 1);
	ok(`fallback: ${status} from ion’s endpoint → no tile, the session stands down (denied) and remembers it`, t === null && r.degrades.join() === 'denied' && r.flag() === 'denied' && r.src.available === false && r.log.length === 1);
}
{
	const r = rig({ tile: (_u, log) => ({ status: log.filter((l) => l.kind === 'tile').length >= 2 ? 429 : 200, image: { fake: 1 } }) });
	r.src.configure(TOKEN);
	const out = await Promise.all([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((i) => r.src.tile(15, i, 1)));
	const sent = r.log.filter((l) => l.kind === 'tile').length;
	ok('fallback: a 429 on a tile stands the session down (quota), remembered', r.degrades.join() === 'quota' && r.flag() === 'quota');
	ok('fallback: requests queued behind the refusal are NOT sent (at most the 4 already in flight left the browser)', sent <= sat.SAT_MAX_IN_FLIGHT && out.filter(Boolean).length <= 1, `${sent} tile requests sent, ${out.filter(Boolean).length} drawn`);
	ok('fallback: after the refusal every later tile answers null with no request', (await r.src.tile(15, 99, 99)) === null && r.log.filter((l) => l.kind === 'tile').length === sent);
}
{
	const r = rig({ tile: () => ({ status: 401, image: null }) });
	r.src.configure(TOKEN);
	await r.src.tile(15, 1, 1);
	ok('fallback: 401 on a tile → denied, remembered', r.degrades.join() === 'denied' && r.flag() === 'denied');
	// a new page view in the same tab session: the remembered refusal is honoured, no request at all
	const again = new sat.SatelliteSource(r.deps);
	again.configure(TOKEN);
	const t2 = await again.tile(15, 2, 2);
	ok('fallback: a remembered refusal keeps the next page view on the night tiles with no request', again.available === false && t2 === null && r.log.filter((l) => l.kind === 'tile').length === 1 && r.log.filter((l) => l.kind === 'json').length === 2);
}
{
	const r = rig({ tile: () => ({ status: 404, image: null }) });
	r.src.configure(TOKEN);
	const t = await r.src.tile(15, 1, 1);
	await r.src.tile(15, 2, 1);
	await r.src.tile(15, 3, 1);
	ok('fallback: a 404 (no imagery at that tile) is not a failure of the source', t === null && r.src.available === true && r.degrades.length === 0);
}
{
	const r = rig({
		tile: () => {
			throw new Error('network down');
		},
	});
	r.src.configure(TOKEN);
	for (let i = 0; i < 5; i++) await r.src.tile(15, i, 1);
	ok('fallback: three failures in a row (no network) stand it down for this page view only, nothing remembered', r.degrades.join() === 'unreachable' && r.flag() === null && r.log.filter((l) => l.kind === 'tile').length === sat.SAT_FAIL_LIMIT);
}
{
	let n = 0;
	const r = rig({ json: (url) => (url.startsWith(sat.ION_ENDPOINT_URL) ? (n++ < 1 ? { status: 503, json: null } : { status: 200, json: ENDPOINT }) : { status: 200, json: META }) });
	r.src.configure(TOKEN);
	const first = await r.src.tile(15, 1, 1);
	const second = await r.src.tile(15, 2, 1);
	ok('fallback: one transient endpoint failure (a refused handshake, a 5xx) is retried once inside the same burst — the page is not left on night tiles', !!first && !!second && r.src.available === true && r.log.filter((l) => l.url.startsWith(sat.ION_ENDPOINT_URL)).length === 2);
	let m = 0;
	const rb = rig({ json: (url) => (url.startsWith(sat.ION_ENDPOINT_URL) ? (m++ < 2 ? { status: 503, json: null } : { status: 200, json: ENDPOINT }) : { status: 200, json: META }) });
	rb.src.configure(TOKEN);
	const f1 = await rb.src.tile(15, 1, 1);
	const f2 = await rb.src.tile(15, 2, 1);
	ok('fallback: a setup that fails twice in a burst gives night tiles for that burst; the next tile asks again (bounded)', f1 === null && !!f2 && rb.src.available === true);
	const r2 = rig({ json: () => ({ status: 503, json: null }) });
	r2.src.configure(TOKEN);
	for (let i = 0; i < 10; i++) await r2.src.tile(15, i, 1);
	ok('fallback: a setup that never answers is tried at most SAT_SETUP_CAP times, then stands down', r2.log.filter((l) => l.url.startsWith(sat.ION_ENDPOINT_URL)).length <= sat.SAT_SETUP_CAP && r2.degrades.length === 1, r2.degrades.join());
}
{
	const r = rig({ json: (url) => (url.startsWith(sat.ION_ENDPOINT_URL) ? { status: 200, json: { ...ENDPOINT, externalType: 'TERRAIN' } } : { status: 200, json: META }) });
	r.src.configure(TOKEN);
	ok('fallback: an imagery source that is not Bing is unsupported (no guessing at a URL)', (await r.src.tile(15, 1, 1)) === null && r.degrades.join() === 'unsupported' && r.log.length === 1);
	const r2 = rig();
	r2.src.configure(TOKEN);
	ok('quota: no tile above the source’s highest zoom is requested', (await r2.src.tile(22, 1, 1)) === null && r2.log.filter((l) => l.kind === 'tile').length === 0);
	const r3 = rig();
	ok('quota: with no token nothing is requested at all', (await r3.src.tile(15, 1, 1)) === null && r3.log.length === 0 && r3.src.available === false);
}
{
	const r = rig();
	r.src.configure(TOKEN);
	await Promise.all(Array.from({ length: 30 }, (_, i) => r.src.tile(15, i, 3)));
	ok('quota: at most 4 requests in flight, however many tiles are asked at once', r.maxIn() <= sat.SAT_MAX_IN_FLIGHT && r.maxIn() >= 2, `max ${r.maxIn()}`);
}
{
	// the token never leaks: not into an error, not into the console
	console.error = (...a) => errs.push(a.join(' '));
	console.warn = (...a) => errs.push(a.join(' '));
	const r = rig({
		json: () => {
			throw new Error('boom');
		},
	});
	r.src.configure(TOKEN);
	let thrown = null;
	try {
		await r.src.tile(15, 1, 1);
	} catch (e) {
		thrown = e;
	}
	console.error = origErr;
	console.warn = origWarn;
	ok('quota: a failing request throws nothing and logs nothing (so the token cannot reach a log)', thrown === null && errs.length === 0);
	const srcText = ['satellite.ts', 'tiles.ts', 'map-style.svelte.ts', 'MapThumb.svelte', 'MapStyleSwitch.svelte', 'MapPage.svelte', 'LayersSheet.svelte'].map((f) => read(`lib/v3/map/${f}`).replace(/\/\*[\s\S]*?\*\/|\/\/.*/g, '')).join('\n');
	ok('quota: no console call, no throw of a message, no token in an attribute or text anywhere in the V3 map code', !/console\.(log|warn|error|info|debug)/.test(srcText) && !/throw new Error\([^)]*(token|key)/i.test(srcText) && !/\{[^}]*(imageryToken|\btoken\b)[^}]*\}\s*<\/|(title|aria-label|data-[a-z-]+)=\{[^}]*(imageryToken|\btoken\b)/i.test(srcText.replace(/\{ *token *\}/g, '')));
}

// ─── caps ────────────────────────────────────────────────────────────────────
{
	const { frame } = M.merc;
	const sizes = [
		['Home card thumb (≈ 300×170)', 300, 170, false],
		['Home card thumb at 1366 (≈ 268×150)', 268, 150, false],
		['assistant proposal thumb (≈ 160×90)', 160, 90, false],
		['Layers sheet picture (≈ 120×46)', 120, 46, false],
	];
	const bbox = [88.30356, 22.5469, 88.39356, 22.6069];
	let bad = [];
	for (const [name, w, h] of sizes) for (const zoom of [13, 14, 15, 16]) for (const center of [[88.3499, 22.5682], [88.3411, 22.5607]]) {
		const f = frame({ center, zoom, maxTiles: Math.min(6, sat.SAT_CARD_TILES), pad: 32 }, w, h);
		if (!f || f.tiles.length > sat.SAT_CARD_TILES) bad.push(`${name} z${zoom}: ${f?.tiles.length}`);
		const g = frame({ bbox, maxTiles: sat.SAT_CARD_TILES }, w, h);
		if (!g || g.tiles.length > sat.SAT_CARD_TILES) bad.push(`${name} bbox: ${g?.tiles.length}`);
	}
	ok('caps: a card frames to ≤ 6 satellite tiles at every V3 card size', bad.length === 0 && sat.SAT_CARD_TILES === 6, bad.join(' | '));
	let hero = [];
	for (const [w, h] of [[1920, 1080], [1366, 768], [1100, 700], [800, 600]]) {
		const f = frame({ center: [88.3499, 22.5682], zoom: 16, maxTiles: sat.SAT_HERO_TILES }, w, h);
		if (!f || f.tiles.length > sat.SAT_HERO_TILES) hero.push(`${w}×${h}: ${f?.tiles.length}`);
	}
	ok('caps: an eager hero / stage / map backdrop frames to ≤ 40 satellite tiles at 1920 and 1366', hero.length === 0 && sat.SAT_HERO_TILES === 40, hero.join(' | '));
	const thumb = read('lib/v3/map/MapThumb.svelte');
	ok('caps: MapThumb frames satellite to min(maxTiles, 6 on a card | 40 eager)', /const tileCap = \$derived\(eff === 'satellite' \? Math\.min\(maxTiles, eager \? SAT_HERO_TILES : SAT_CARD_TILES\) : maxTiles\)/.test(thumb) && /maxTiles: tileCap/.test(thumb));
	ok('caps: night and satellite tiles share ONE queue (≤ 4 in flight in all) and one LRU', /limiter: \{ acquire: satSlot, release: satRelease \}/.test(read('lib/v3/map/tiles.ts')) && /const SAT_SHARE = 3;/.test(read('lib/v3/map/tiles.ts')) && /const MAX_IN_FLIGHT = 4/.test(read('lib/v3/map/tiles.ts')) && sat.SAT_MAX_IN_FLIGHT === 4 && /sat:\$\{z\}/.test(read('lib/v3/map/tiles.ts')));
}

// ─── contrast: overlays on the brightest and the darkest imagery ─────────────
{
	const rgb = (h) => {
		const m = /^#([0-9a-f]{6})$/i.exec(h);
		if (m) return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16)).concat(1);
		const r = /rgba?\(([^)]+)\)/.exec(h);
		const p = r[1].split(',').map((x) => parseFloat(x));
		return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
	};
	const lum = ([r, g, b]) => {
		const f = (v) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
		return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
	};
	const cr = (a, b) => (Math.max(lum(a), lum(b)) + 0.05) / (Math.min(lum(a), lum(b)) + 0.05);
	const over = (fg, alpha, bg) => [0, 1, 2].map((i) => fg[i] * alpha + bg[i] * (1 - alpha));
	const night = M.tokens.v3Tokens('night');
	const css = read('lib/v3/map/MapThumb.svelte');
	const rule = (sel) => {
		const m = css.match(new RegExp(sel.replace(/[.[\]()'=]/g, '\\$&') + '\\s*\\{([^}]*)\\}'));
		return m ? m[1] : '';
	};
	const prop = (body, name) => (new RegExp(`${name}:\\s*([^;]+);`).exec(body) ?? [])[1]?.trim();
	const glass = rgb(night['--v3-glass']);
	const BRIGHT = [255, 255, 255];
	const DARK = [0, 0, 0];
	const satCase = css.match(/\.thumb\[data-style='satellite'\] \.case,\s*\.thumb\[data-style='satellite'\] \.ring-case \{([^}]*)\}/)?.[1] ?? '';
	const caseOp = Number(prop(satCase, 'opacity'));
	const ringOp = caseOp;
	const caseInk = rgb(night[(/var\((--v3-[a-z-]+)\)/.exec(prop(satCase, 'stroke') ?? '') ?? [])[1] ?? '--v3-glass']);
	const lblBody = css.match(/\.thumb\[data-style='satellite'\] \.lbl \{([^}]*)\}/)?.[1] ?? '';
	const lblStroke = prop(lblBody, 'stroke');
	const lblWidth = parseFloat(prop(lblBody, 'stroke-width') ?? '0');
	ok('contrast: the satellite label halo is the dark glass, ≥ 5 px wide', lblStroke === 'var(--v3-glass)' && lblWidth >= 5, `${lblStroke} ${lblWidth}px`);
	const halo = over(glass, glass[3], BRIGHT); // the glass halo composited over the brightest roof
	const t1 = rgb(night['--v3-t1']);
	const t2 = rgb(night['--v3-t2']);
	ok('contrast: label ink (t1) over its halo on the BRIGHTEST imagery ≥ 4.5:1', cr(t1, halo) >= 4.5, cr(t1, halo).toFixed(2));
	ok('contrast: the dim label ink (t2) over its halo on the brightest imagery ≥ 4.5:1', cr(t2, halo) >= 4.5, cr(t2, halo).toFixed(2));
	ok('contrast: label ink over its halo on the DARKEST imagery ≥ 4.5:1', cr(t1, over(glass, glass[3], DARK)) >= 4.5 && cr(t2, over(glass, glass[3], DARK)) >= 4.5);
	ok('contrast: on satellite the line / ring casing is the scrim at full strength, so a bright roof never shows through it', caseOp >= 0.95 && caseInk[3] >= 0.95, `opacity ${caseOp}, ink alpha ${caseInk[3]}`);
	const casingBright = over(caseInk, caseInk[3] * caseOp, BRIGHT);
	const casingDark = over(caseInk, caseInk[3] * caseOp, DARK);
	const lines = [['route', '--v3-route'], ['route-done', '--v3-route-done'], ['alert', '--v3-alert'], ['green', '--v3-ok'], ['neutral', '--v3-t1']];
	const worst = [];
	for (const [name, tok] of lines) {
		const c = rgb(night[tok]);
		worst.push([cr(c, casingBright), `${name} line over its casing on the brightest imagery`], [cr(c, casingDark), `${name} line over its casing on the darkest imagery`]);
	}
	worst.sort((a, b) => a[0] - b[0]);
	ok('contrast: every route / trail / corridor / neutral line ≥ 3:1 against its casing (graphics) on bright and dark imagery', worst[0][0] >= 3, `worst ${worst[0][0].toFixed(2)} — ${worst[0][1]}`);
	ok('contrast: the casing itself stands off the brightest imagery ≥ 3:1 (the line has an edge)', cr(casingBright, BRIGHT) >= 3, cr(casingBright, BRIGHT).toFixed(2));
	ok('contrast: a pin sits on a dark ring (case-fill = the glass, the scrim on satellite), r + 3 px, with a glyph in the primary ink', /\.case-fill \{\s*fill: var\(--v3-glass\);/.test(css) && /data-style='satellite'\] \.case-fill \{\s*fill: var\(--v3-scrim\)/.test(css) && /<circle class="case-fill" cx=\{x\} cy=\{y\} r=\{r \+ 3\}/.test(css));
	ok('contrast: neutral road / dashed lines are drawn stronger on satellite (opacity ≥ 0.9, was 0.5–0.55)', /data-style='satellite'\] \.ln-road,[\s\S]{0,80}\.ln-dashed \{\s*stroke-opacity: 0\.95/.test(css));
	ok('contrast: an uncertainty ring has a dark casing under its dashes', /<circle class="ring-case"/.test(css) && /\.ring-case \{[^}]*stroke: var\(--v3-glass\)/.test(css));
	ok('contrast: the tiles are drawn ungraded — no filter, no overlay tint, on the satellite canvas', !/\.tiles[^{]*\{[^}]*filter:/.test(css) && !/backdrop-filter|mix-blend-mode/.test(css));
}

// ─── pack ────────────────────────────────────────────────────────────────────
{
	const P = M.MAPSTYLE_PACKS;
	const keys = Object.keys(P.en);
	const same = (a, b) => a.length === b.length && a.every((k) => b.includes(k));
	ok('pack: EN / HI / MR carry the same keys, all v3ms_', same(keys, Object.keys(P.hi)) && same(keys, Object.keys(P.mr)) && keys.every((k) => k.startsWith('v3ms_')), `${keys.length} keys`);
	ok('pack: HI and MR are translated and in their own script', keys.every((k) => P.hi[k] !== P.en[k] && P.mr[k] !== P.en[k] && /[ऀ-ॿ]/.test(P.hi[k]) && /[ऀ-ॿ]/.test(P.mr[k]) && !/[ঀ-৿]/.test(P.mr[k])));
	ok('pack: at most one " · " per string; no ALL-CAPS word beyond the acronyms (EN)', keys.every((k) => P.en[k].split(' · ').length <= 2) && keys.every((k) => !P.en[k].split(/[\s,.:;()·/—-]+/).some((w) => w.length > 1 && /^[A-Z]+$/.test(w) && !['OK'].includes(w))));
	ok('pack: satellite imagery is "not a live image" in all three languages', /not a live image/.test(P.en.v3ms_tip_satellite) && /लाइव चित्र नहीं/.test(P.hi.v3ms_tip_satellite) && /थेट प्रतिमा नाही/.test(P.mr.v3ms_tip_satellite));
	ok('pack: the labels are "Satellite" and "Map" (EN); "Map style" is the group', P.en.v3ms_satellite === 'Satellite' && P.en.v3ms_map === 'Map' && P.en.v3ms_label === 'Map style');
	const map3 = read('lib/v3/map/packs.map3.ts');
	ok('pack: /map names the base map "Satellite 3D · City map" (EN, HI, MR)', /v3m_base_3d: 'Satellite 3D'/.test(map3) && /v3m_base_city: 'City map'/.test(map3) && /v3m_base_3d: 'उपग्रह 3D'/.test(read('lib/v3/map/packs.map3.hi.ts')) && /v3m_base_3d: 'उपग्रह 3D'/.test(read('lib/v3/map/packs.map3.mr.ts')));
}

// ─── render ──────────────────────────────────────────────────────────────────
{
	const html = (C, props) => M.render(C, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
	const sw = (h, which) => (h.match(new RegExp(`<button[^>]*data-map-style="${which}"[^>]*>`)) ?? [''])[0];
	const S = M.mapStyle;
	S.pref = null;
	S.keyed = true;
	S.degraded = null;
	const def = html(M.MapStyleSwitch, { lang: 'en', hint: true });
	ok('switch: "Map style" with ONE group of two toggle buttons, Satellite and Map', /Map style/.test(def) && (def.match(/<button/g) ?? []).length === 2 && /role="group"/.test(def) && !/role="radio"/.test(def));
	ok('switch: with the key and no choice, Satellite is pressed (the default), Map is not', /aria-pressed="true"/.test(sw(def, 'satellite')) && /aria-pressed="false"/.test(sw(def, 'map')));
	ok('switch: Satellite’s tooltip says natural colour and "not a live image"', /Natural-colour satellite imagery · not a live image/.test(sw(def, 'satellite')));
	S.pref = 'map';
	const mapped = html(M.MapStyleSwitch, { lang: 'en' });
	ok('switch: chosen Map → Map pressed, Satellite not', /aria-pressed="true"/.test(sw(mapped, 'map')) && /aria-pressed="false"/.test(sw(mapped, 'satellite')));
	S.pref = null;
	S.keyed = false;
	const nokey = html(M.MapStyleSwitch, { lang: 'en' });
	ok('switch: without the key Satellite is disabled with its reason and Map is pressed', /aria-disabled="true"/.test(sw(nokey, 'satellite')) && /Needs the Cesium ion key on this deck/.test(nokey) && /aria-pressed="true"/.test(sw(nokey, 'map')));
	S.keyed = true;
	S.degraded = 'quota';
	const paused = html(M.MapStyleSwitch, { lang: 'en' });
	ok('switch: after a refusal this session Satellite is paused with the reason, Map is pressed', /aria-disabled="true"/.test(sw(paused, 'satellite')) && /paused for this session/.test(paused) && /aria-pressed="true"/.test(sw(paused, 'map')));
	S.degraded = null;
	const hi = html(M.MapStyleSwitch, { lang: 'hi' });
	const mr = html(M.MapStyleSwitch, { lang: 'mr' });
	ok('switch: HI and MR are translated', /मानचित्र शैली/.test(hi) && /उपग्रह/.test(hi) && /नकाशाची शैली/.test(mr) && /उपग्रह/.test(mr));
	ok('store: effective follows the rules (key + no choice → satellite; map chosen → night; refusal → night)', (S.pref = null, S.keyed = true, S.effective === 'satellite') && (S.pref = 'map', S.effective === 'night') && (S.pref = 'satellite', S.degraded = 'cap', S.effective === 'night') && (S.degraded = null, S.keyed = null, S.effective === null));
	S.pref = null;
	S.keyed = true;
	const sheet = html(M.LayersSheet, { rows: [], is3d: true, can3d: true, why3d: 'x', lang: 'en', onlayer() {}, on3d() {}, onclose() {} });
	ok('sheet: Satellite 3D and City map are the base-map radios (2), then the Map style switch', (sheet.match(/role="radio"/g) ?? []).length === 2 && /data-base="3d"[\s\S]*Satellite 3D/.test(sheet) && /data-base="city"[\s\S]*City map/.test(sheet) && /data-testid="v3-map-style"/.test(sheet));
	ok('sheet: the Satellite 3D picture is natural satellite imagery, the City map picture the night map', /data-base="3d"[\s\S]*?data-v3="map-thumb"/.test(sheet) && read('lib/v3/map/LayersSheet.svelte').includes('style="satellite"') && read('lib/v3/map/LayersSheet.svelte').includes('style="night"'));
}

// ─── wiring (source) ─────────────────────────────────────────────────────────
{
	const callers = {
		'Home hero': 'lib/v3/home/FeatureHero.svelte',
		'Home cards': 'lib/v3/home/CardFrame.svelte',
		Decide: 'lib/v3/decide/DecidePage.svelte',
		'object hero': 'lib/v3/object/HeroMap.svelte',
		'assistant proposal': 'lib/v3/assistant/ProposalCard.svelte',
	};
	for (const [name, f] of Object.entries(callers)) {
		const src = read(f);
		const tags = [...src.matchAll(/<MapThumb\b[\s\S]*?(?:\/>|>)/g)].map((m) => m[0]);
		ok(`callers: ${name} uses MapThumb and passes no style / grade (it inherits the shared style)`, tags.length >= 1 && tags.every((t) => !/\sstyle=|\sgrade=/.test(t)), `${tags.length} use(s)`);
	}
	const thumb = read('lib/v3/map/MapThumb.svelte');
	ok('thumb: with no style prop it follows the shared preference (mapStyle.effective) and waits for the deck’s answer (null)', /const eff = \$derived<ThumbStyle \| null>\(style \?\? mapStyle\.effective\)/.test(thumb) && /st === null\) return;/.test(thumb) && /mapStyle\.ensure\(\)/.test(thumb));
	ok('thumb: satellite tiles come from satelliteTile (ungraded); night tiles from gradedTile', /as === 'satellite' \? satelliteTile\(t\.z, t\.x, t\.y, eager \? 'hero' : 'card'\) : gradedTile\(t\.z, t\.x, t\.y, grade, under\)/.test(thumb));
	ok('thumb: no satellite tile came → the night tiles for that draw (never a blank)', /ok === 0 && st === 'satellite' && drawn === key[\s\S]{0,80}paint\('night'\)/.test(thumb));
	ok('thumb: the key includes the style, so a fall back redraws', /const key = `\$\{st\}\|/.test(thumb));
	ok('thumb: the imagery credit is a text line (never injected HTML), shown only for drawn satellite tiles', /\{#if shown === 'satellite' && creditText && creditRoom && creditInside\}[\s\S]{0,200}\{creditText\}<\/span>/.test(thumb) && !/\{@html/.test(thumb));
	ok('thumb: the OSM link stays for night thumbs that ask for a credit', /\{:else if credit\}[\s\S]{0,160}openstreetmap\.org\/copyright/.test(thumb));
	const store = read('lib/v3/map/map-style.svelte.ts');
	ok('store: the key answer comes from the deck’s own mode endpoint (GODS_EYE_MODE_API), once, with a 4 s budget; nothing else', /GODS_EYE_MODE_API/.test(store) && /AbortSignal\.timeout\(4000\)/.test(store) && /satellite\.configure\(token\)/.test(store) && !/this\.token|token =\s*\$state/.test(store));
	ok('store: only the choice is remembered (localStorage), never the token', /write\(STYLE_KEY, p\)/.test(store) && /write\(BASE_KEY, b\)/.test(store) && !/write\([^)]*token/i.test(store));
	const page = read('lib/v3/map/MapPage.svelte');
	ok('map: the canvas mounts only after the deck’s imagery answer, with the start layers from the remembered base map', /\{#if sessionKnown && modeKnown\}/.test(page) && /canvasLayers = startLayers\(V3_DEFAULT_LAYERS, mapStyle\.baseFor\(keyed\)\)/.test(page) && /defaultLayers=\{canvasLayers\}/.test(page));
	ok('map: the officer’s 3D / city choice is remembered per browser', /mapStyle\.setBase\(want \? 'sat3d' : 'city'\)/.test(page));
	ok('map: the token goes to the canvas’s store and the satellite source — never into the page markup', /mapStyle\.provide\(godsEye\.imageryToken\)/.test(page) && !/\{[^}]*imageryToken[^}]*\}\s*[<"]/.test(page.replace(/mapStyle\.provide\(godsEye\.imageryToken\)/, '')));
	ok('map: the loading backdrop is a MapThumb (satellite when keyed) — no night map is forced on it', /<MapThumb bbox=\{bboxArray\(CITY_BBOX\)\} zoom=\{13\} maxTiles=\{48\} eager/.test(page) && !/style="night"/.test(page));
	ok('map: nothing outside /map imports the map page or pack, and MapStyleSwitch lives outside the /map-only pack', !/packs\.map3/.test(read('lib/v3/map/MapStyleSwitch.svelte')) && /packs\.mapstyle/.test(read('lib/v3/map/MapStyleSwitch.svelte')));
}

console.log(failures ? `\nv3-map-style.unit: ${failures} failure(s)` : '\nv3-map-style.unit: ALL OK');
process.exit(failures ? 1 : 0);
