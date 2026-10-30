/**
 * Root-flip unit test (V3 P5; V3-SPEC §3.2, §10 P5) — the URL table of the flip, held without a browser.
 *
 *   node tests/root-flip.unit.mjs
 *
 * esbuild bundles the REAL modules (src/hooks.ts, src/lib/shell/root-flip.ts, the two nav tables,
 * decisions/homes.ts) and asserts:
 *   - tests/lib/routes.mjs names the same two roots the app does (WORKSPACE = `/analyst`, HOME = `/`);
 *   - the reroute table: `/` → Home's node, `/analyst` (and `/analyst/`) → the workspace's node, everything else
 *     untouched — and `reroute({ url })` in src/hooks.ts answers exactly that;
 *   - every old workspace deep-link form (`/#v=2…`, `#inbox=`, `#movement=`, `#items=`, `#sel=`, `#view=`, the
 *     window / filter / dock keys) hands over to `/analyst#…` with its hash untouched, and a Home anchor or a
 *     /ops deep link (`#evt=`, `#rec=`) does not; the <head> script Home runs before first paint does the same;
 *   - the navigation tables: the v2 Corridor module opens /analyst, the v2 mark and the V3 rail's Home open `/`,
 *     the rail's Analyst opens /analyst, /ops keeps its module, and each pathname lights the right item;
 *   - decision homes: homeLink on the workspace route is `/analyst#…` and no link spells the workspace as `/` or `/#…`;
 *   - the sources that cannot be bundled (Svelte) still say it: the Share link, the brand mark, Home's hand-over,
 *     and the edge still derives the operator policy from the resolved route node, never from the URL.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { HOME, NODE, WORKSPACE, budgetRoutes, ceilingOf, workspacePath, workspaceUrl } from './lib/routes.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const OUT = path.join(HERE, 'artifacts', 'root-flip-bundle.mjs');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const read = (rel) => readFileSync(path.join(DECK, rel), 'utf8');

mkdirSync(path.dirname(OUT), { recursive: true });
const esbuild = createRequire(path.join(DECK, 'package.json'))('esbuild');
const built = await esbuild.build({
	stdin: {
		contents: `
export * as flip from './src/lib/shell/root-flip';
export * as hooks from './src/hooks';
export * as v2nav from './src/lib/shell/nav';
export * as v3nav from './src/lib/v3/shell/nav';
export * as homes from './src/lib/decisions/homes';
export { t } from './src/lib/i18n/strings';
import './src/lib/i18n/packs';
`,
		resolveDir: DECK,
		loader: 'ts',
		sourcefile: 'root-flip-entry.ts',
	},
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	outfile: OUT,
	logLevel: 'silent',
	define: { 'import.meta.env': '{"DEV":false}' },
});
ok('bundle builds (esbuild, $lib aliased)', built.errors.length === 0, `${built.errors.length} errors`);
const { flip, hooks, v2nav, v3nav, homes, t } = await import(pathToFileURL(OUT).href);

// ─── the two roots ─────────────────────────────────────────────────────────

ok('routes.mjs: WORKSPACE is the app\'s workspace URL (/analyst)', WORKSPACE === flip.WORKSPACE_URL && WORKSPACE === '/analyst', `${WORKSPACE} / ${flip.WORKSPACE_URL}`);
ok('routes.mjs: HOME is the app\'s Home URL (/)', HOME === flip.HOME_URL && HOME === '/', `${HOME} / ${flip.HOME_URL}`);
ok('routes.mjs: URL → node map matches the reroute (workspace → /(deck), Home → /(v3)/home, /home too)', NODE[WORKSPACE] === '/(deck)' && NODE[HOME] === '/(v3)/home' && NODE['/home'] === '/(v3)/home');
ok('routes.mjs: workspaceUrl / workspacePath compose the URL', workspaceUrl('http://h:1', '#sel=a:1') === 'http://h:1/analyst#sel=a:1' && workspacePath('v=2') === '/analyst#v=2' && workspacePath() === '/analyst' && workspaceUrl('http://h:1') === 'http://h:1/analyst');

// ─── the reroute table ─────────────────────────────────────────────────────

ok('reroute table: exactly /, /analyst and /analyst/', eq(Object.entries(flip.REROUTES).sort(), [['/', '/home'], ['/analyst', '/'], ['/analyst/', '/']].sort()), JSON.stringify(flip.REROUTES));
const RESOLVE = {
	'/': '/home',
	'/analyst': '/',
	'/analyst/': '/',
	'/home': undefined,
	'/ops': undefined,
	'/gods-eye': undefined,
	'/decide': undefined,
	'/decide/escort-proposal:x': undefined,
	'/o/event:1': undefined,
	'/map': undefined,
	'/plan': undefined,
	'/assistant': undefined,
	'/chat': undefined,
	'/comms': undefined,
	'/citizen': undefined,
	'/driver': undefined,
	'/design': undefined,
	'/analyst/extra': undefined,
	'/analystic': undefined,
	'/Analyst': undefined,
	'//analyst': undefined,
	'/api/v1/health': undefined,
	'/__proto__': undefined,
	'/constructor': undefined,
	'/toString': undefined,
	'/hasOwnProperty': undefined,
};
const bad = Object.entries(RESOLVE).filter(([from, to]) => flip.reroutePath(from) !== to);
ok(`reroutePath: ${Object.keys(RESOLVE).length} pathnames resolve as pinned (only /, /analyst, /analyst/ move)`, bad.length === 0, bad.map(([f, t]) => `${f}→${flip.reroutePath(f)} (want ${t})`).join(' · '));
const urlAt = (p) => {
	const u = new URL('http://deck.internal/');
	u.pathname = p;
	return u;
};
const viaHook = Object.entries(RESOLVE).filter(([from, to]) => hooks.reroute({ url: urlAt(from), fetch: globalThis.fetch }) !== to);
ok('src/hooks.ts: reroute({ url }) answers the table for every pathname', viaHook.length === 0, viaHook.map(([f]) => f).join(' '));
ok('reroutePath: a bare key that exists on every object (constructor, toString, __proto__, hasOwnProperty) resolves to nothing', ['constructor', 'toString', '__proto__', 'hasOwnProperty', 'valueOf'].every((k) => flip.reroutePath(k) === undefined));
ok('src/hooks.ts: the query and the hash do not change the resolution', hooks.reroute({ url: new URL('/analyst?x=1#sel=a:1', 'http://deck.internal'), fetch: globalThis.fetch }) === '/' && hooks.reroute({ url: new URL('/?lang=hi', 'http://deck.internal'), fetch: globalThis.fetch }) === '/home');
ok('src/hooks.ts is the universal hooks file with a reroute export (server and browser both reroute)', /export const reroute\b/.test(read('src/hooks.ts')) && !/\$env|node:|from '\$app\/server'/.test(read('src/hooks.ts')));

// ─── hash deep links: every old bookmark form lands on /analyst#… ──────────

const OLD_FORMS = [
	'#v=2&lat=22.5682&lon=88.3499&alt=1500&heading=45&pitch=-40&style=flir&layers=events',
	'#v=2&lat=NaN&lon=Infinity&alt=-5&style=flir',
	'#v=2&lat=22.5582&lon=88.3599&alt=900&layers=events,cameras&sel=junction:15',
	'#inbox=stolen-sighting:rec-1',
	'#inbox=pursuit%3Aevt-9',
	'#inbox',
	'#movement=escort-proposal:mv-1',
	'#items=vehicle:abc,junction:15',
	'#items=event%3A1',
	'#sel=event:7f1c',
	'#view=table',
	'#view=split&dock=101c',
	'#t0=1760000000000&t1=1760003600000',
	'#f=W3siZmllbGQiOiJraW5kIiwidmFsdWVzIjpbImV2ZW50Il19XQ',
	'#dock=1c0',
	'#layers=events,cameras',
	'#style=flir&bhot=0&palette=iron',
	'#lat=22.54&lon=88.27&alt=900&heading=0&pitch=-45&roll=0',
	'#unknownfirst=1&sel=event:2',
	'v=2&lat=22.5582',
];
const notMoved = OLD_FORMS.filter((h) => flip.workspaceHandOver(h) !== `/analyst${h.startsWith('#') ? h : `#${h}`}` || flip.isWorkspaceHash(h) !== true);
ok(`deep links: ${OLD_FORMS.length} old workspace forms (/#v=2…, #inbox=, #movement=, #items=, #sel=, #view=, window/filter/dock/camera keys) → /analyst#… with the hash untouched`, notMoved.length === 0, notMoved.join(' | '));

const STAY = ['', '#', '#v3-live', '#v3-reported', '#v3-decide', '#evt=abc', '#rec=r1', '#dsp=d1', '#unit=pursuit:x', '#foo=bar', '#lang=hi', '#vv=2', '#view', '#sel', '#items', '#movement'];
const moved = STAY.filter((h) => flip.workspaceHandOver(h) !== null || flip.isWorkspaceHash(h));
ok(`deep links: ${STAY.length} hashes Home keeps (its own anchors, /ops deep links #evt= #rec= #dsp= #unit=, bare keys without a value) stay on Home`, moved.length === 0, moved.join(' | '));
ok('deep links: nothing hostile changes the destination (the target is always the relative /analyst#…)', ['#sel=//evil.example/x', '#v=2&x=https://evil.example', '#inbox=javascript:alert(1)', '#items=%0d%0aLocation:x'].every((h) => (flip.workspaceHandOver(h) ?? '').startsWith('/analyst#')));
ok('deep links: null / undefined / a malformed hash never throw', flip.workspaceHandOver(null) === null && flip.workspaceHandOver(undefined) === null && flip.isWorkspaceHash('#%E0%A4%A') === false);

// the inline script Home runs in <head> (a fragment never reaches the server, so no server redirect can do this)
function runEarly(hash, { throws = false } = {}) {
	const calls = [];
	const location = {
		get hash() {
			if (throws) throw new Error('no location');
			return hash;
		},
		replace: (u) => calls.push(u),
	};
	vm.runInNewContext(flip.earlyHandOverScript(), { location, URLSearchParams });
	return calls;
}
const earlyBad = [...OLD_FORMS, ...STAY].filter((h) => h === '' || h.startsWith('#')).filter((h) => {
	const want = flip.workspaceHandOver(h);
	const got = runEarly(h);
	return want === null ? got.length !== 0 : !(got.length === 1 && got[0] === want);
});
ok('the <head> script: replaces to exactly the table\'s /analyst#… for every old form, and does nothing for the rest', earlyBad.length === 0, earlyBad.join(' | '));
ok('the <head> script: a throwing location never breaks the page', eq(runEarly('#sel=a:1', { throws: true }), []));
ok('the <head> script: is one <script> element with no external reference', /^<script>[\s\S]*<\/script>$/.test(flip.earlyHandOverTag()) && flip.earlyHandOverTag().split('</script').length === 2 && !/https?:|src=/.test(flip.earlyHandOverTag()));
ok('the workspace hash keys cover every key the share link and the workspace write (so no bookmark is dropped)', ['v', 'lat', 'lon', 'alt', 'heading', 'pitch', 'roll', 'style', 'bhot', 'palette', 'layers', 'sel', 'view', 't0', 't1', 'f', 'dock', 'items', 'inbox', 'movement'].every((k) => flip.WORKSPACE_HASH_KEYS.includes(k)));
{
	const shareSrc = read('src/lib/gods-eye/share-link.ts');
	const wsSrc = read('src/lib/workspace/hash.ts');
	const share = [...(/SHARE_KEYS[^=]*=\s*new Set\(\[([^\]]*)\]/.exec(shareSrc)?.[1] ?? '').matchAll(/'([^']+)'/g)].map((m) => m[1]);
	const wsKeys = [...(/WORKSPACE_KEYS\s*=\s*\[([^\]]*)\]/.exec(wsSrc)?.[1] ?? '').matchAll(/'([^']+)'/g)].map((m) => m[1]);
	const missing = [...share, ...wsKeys].filter((k) => !flip.WORKSPACE_HASH_KEYS.includes(k));
	ok(`the workspace hash keys are derived from the sources of truth (share-link SHARE_KEYS ${share.length} + workspace WORKSPACE_KEYS ${wsKeys.length})`, share.length >= 12 && wsKeys.length >= 6 && missing.length === 0, missing.join(' '));
}

// ─── navigation ────────────────────────────────────────────────────────────

const mod = (id) => v2nav.MODULES.find((m) => m.id === id);
ok('v2 navbar: the Corridor module opens /analyst', mod('corridor')?.href === WORKSPACE, mod('corridor')?.href);
ok('v2 navbar: City /gods-eye, Situation /ops, Advisories /comms, Assistant /chat unchanged', mod('city')?.href === '/gods-eye' && mod('situation')?.href === '/ops' && mod('advisories')?.href === '/comms' && mod('assistant')?.href === '/chat');
ok('v2 navbar: /ops is labelled "Situation wall" in EN / HI / MR (the existing nav_ops strings; the nav label only)', mod('situation')?.href === '/ops' && t('en', mod('situation').key) === 'Situation wall' && t('hi', mod('situation').key) === 'स्थिति दीवार' && t('mr', mod('situation').key) === 'परिस्थिती भिंत', `${t('en', mod('situation').key)} / ${t('hi', mod('situation').key)} / ${t('mr', mod('situation').key)}`);
ok('v2 navbar: no module opens `/`', v2nav.MODULES.every((m) => m.href !== '/'));
ok('v2 navbar: Corridor is active on /analyst and not on Home; no other module is active on /analyst', v2nav.moduleActive(mod('corridor'), WORKSPACE) && !v2nav.moduleActive(mod('corridor'), '/') && v2nav.MODULES.filter((m) => m.id !== 'corridor').every((m) => !v2nav.moduleActive(m, WORKSPACE)));
ok('v2 navbar: nothing is active on `/` (Home is not a v2 module)', v2nav.MODULES.every((m) => !v2nav.moduleActive(m, '/')));
ok('v2 navbar search index lists the workspace at /analyst', v2nav.NAV_INDEX.some((n) => n.href === WORKSPACE) && !v2nav.NAV_INDEX.some((n) => n.href === '/'));
const NAVBAR = read('src/lib/shell/Navbar.svelte');
ok('v2 navbar: the brand mark opens `/` (Home), not /home', /<a class="brand" href="\/"/.test(NAVBAR) && !/class="brand" href="\/home"/.test(NAVBAR));

const rail = (id) => v3nav.V3_NAV.find((n) => n.id === id);
ok('V3 rail: Home is `/`, Analyst is /analyst, the rest unchanged', rail('home')?.href === '/' && v3nav.V3_ANALYST.href === WORKSPACE && rail('map')?.href === '/map' && rail('decide')?.href === '/decide' && rail('plan')?.href === '/plan' && rail('assistant')?.href === '/assistant' && rail('advisories')?.href === '/comms');
ok('V3 rail: no item is /home or the old workspace root', v3nav.V3_NAV.every((n) => n.href !== '/home') && v3nav.V3_ANALYST.href !== '/');
const ACTIVE = { '/': 'home', '/home': 'home', '/analyst': 'analyst', '/analyst/': 'analyst', '/decide': 'decide', '/decide/pursuit%3Ax': 'decide', '/map': 'map', '/plan': 'plan', '/assistant': 'assistant', '/comms': 'advisories', '/o/event:1': null, '/ops': null, '/gods-eye': null, '/chat': null, '/homework': null, '/analysts': null };
const activeBad = Object.entries(ACTIVE).filter(([p, id]) => v3nav.navActive(p) !== id);
ok('V3 rail: navActive lights the right item for every pathname (`/` and /home → Home, /analyst → Analyst)', activeBad.length === 0, activeBad.map(([p, id]) => `${p} → ${v3nav.navActive(p)} (want ${id})`).join(' · '));

// ─── decision homes ────────────────────────────────────────────────────────

const KINDS = Object.keys(homes.HOMES);
const links = KINDS.flatMap((k) => homes.HOME_ROUTES.map((r) => ({ k, r, ...homes.homeLink(k, 'rec-1', r) })));
ok('homes: one decision home per kind per route is intact (the rule and its table)', KINDS.length >= 7 && KINDS.every((k) => eq(Object.keys(homes.HOMES[k]).sort(), [...homes.HOME_ROUTES].sort())));
ok('homes: a workspace-route link opens /analyst#inbox=… / #movement=… (or /analyst for a map home)', links.filter((l) => l.r === '/' && l.k !== 'map-proposal').every((l) => (homes.homeOf(l.k, '/') === 'movement' ? l.href.startsWith('/analyst#movement=') : l.href.startsWith('/analyst#inbox=')) && !l.href.includes('WB')) && homes.homeLink('map-proposal', 'x', '/').href === '/analyst', links.filter((l) => l.r === '/').map((l) => l.href).join(' '));
ok('homes: /gods-eye and /ops links are unchanged (/gods-eye#…, /ops#unit=…)', links.filter((l) => l.r === '/gods-eye' && homes.homeOf(l.k, '/gods-eye') !== 'map').every((l) => l.href.startsWith('/gods-eye#')) && links.filter((l) => l.r === '/ops' && homes.homeOf(l.k, '/ops') === 'decisions').every((l) => l.href.startsWith('/ops#unit=')));
ok('homes: no link spells the workspace as `/` or `/#…`', links.every((l) => l.href !== '/' && !l.href.startsWith('/#')));
ok('homes: an unknown route reads as the workspace (a V3 page\'s link card opens Analyst)', homes.homeLink('pursuit', 'p1', '/chat').href.startsWith('/analyst#inbox='));

// ─── sources that cannot be bundled ────────────────────────────────────────

const DECK_PAGE = read('src/routes/(deck)/+page.svelte');
ok('workspace Share: copies /analyst#… (WORKSPACE_URL), not the bare origin', /\$\{WORKSPACE_URL\}\$\{hash \? `#\$\{hash\}` : ''\}/.test(DECK_PAGE) && !/location\.origin : ''\}\/\$\{hash/.test(DECK_PAGE));
const HOME_PAGE = read('src/routes/(v3)/home/+page.svelte');
const MOUNT = HOME_PAGE.slice(HOME_PAGE.indexOf('onMount(() => {'), HOME_PAGE.indexOf('registerProviders();'));
ok('Home: hands a workspace hash to Analyst ahead of first paint (<head> script) and on a client-side mount (before anything starts), as a client navigation', /\{@html earlyHandOverTag\(\)\}/.test(HOME_PAGE) && /<svelte:head>[\s\S]*earlyHandOverTag/.test(HOME_PAGE) && /workspaceHandOver\(location\.hash\)/.test(MOUNT) && /goto\(handOver, \{ replaceState: true/.test(MOUNT) && !/location\.replace\(handOver/.test(MOUNT));
ok('Home: a hash-only navigation while Home is open is handed over too (hashchange + afterNavigate)', /addEventListener\('hashchange', handOverNow\)/.test(HOME_PAGE) && /removeEventListener\('hashchange', handOverNow\)/.test(HOME_PAGE) && /afterNavigate\(/.test(HOME_PAGE) && /function handOverNow\(\)[\s\S]{0,160}workspaceHandOver\(location\.hash\)/.test(HOME_PAGE));
const EDGE = read('src/hooks.server.ts');
ok('edge: the operator CSP and theme follow the resolved route node (event.route.id), never the URL', /operator: id\.startsWith\('\/\(deck\)'\)/.test(EDGE) && !/event\.url\.pathname\s*(===|\.startsWith)\s*['"`]\/(analyst)?['"`]/.test(EDGE));
ok('edge: no code in the edge names /analyst (comments aside): the gate and proxy rules gate /api, the page policy reads the route node', !/analyst/.test(EDGE.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')));
ok('hooks: the table lives in one module the hook and the page both read', /from '\.\/lib\/shell\/root-flip'/.test(read('src/hooks.ts')) && /from '\$lib\/shell\/root-flip'/.test(HOME_PAGE));

// ─── no stray spelling of the workspace as the root, in the sources the flip owns ──

const SRC_FILES = ['src/lib/shell/nav.ts', 'src/lib/shell/Navbar.svelte', 'src/lib/v3/shell/nav.ts', 'src/lib/decisions/homes.ts', 'src/routes/(deck)/+page.svelte', 'src/routes/(deck)/comms/+page.svelte', 'src/routes/(v3)/home/+page.svelte', 'src/lib/v3/home/view.ts'];
const stray = [];
for (const f of SRC_FILES) {
	read(f).split('\n').forEach((line, i) => {
		const code = line.replace(/\/\/.*$/, '').replace(/^\s*(\*|\/\*).*$/, '').replace(/<!--.*?-->/g, '');
		if (/(goto\(\s*['"`]\/['"`]\s*\)|href:\s*['"`]\/['"`]|href=["']\/["']|['"`]\/#[^'"`]*['"`]|`\/#)/.test(code) && !/class="brand"/.test(code) && !/id: 'home'/.test(code)) stray.push(`${f}:${i + 1}`);
	});
}
ok('no owned source links the workspace as `/` or `/#…` (the brand mark opening Home is the one `/`)', stray.length === 0, stray.join(' '));

// ─── route-budget keys: the tests read whichever keys the JSON has ──────────

{
	const legacy = { '/': 100, '/ops': 200, '/gods-eye': 300 };
	const flipped = { '/analyst': 100, '/': 40, '/home': 40, '/ops': 200, '/gods-eye': 300 };
	ok('budget keys (before the JSON patch): /analyst reads the old `/` ceiling; Home and /home are held to it too', ceilingOf(legacy, '/analyst') === 100 && ceilingOf(legacy, '/') === 100 && ceilingOf(legacy, '/home') === 100 && ceilingOf(legacy, '/ops') === 200);
	ok('budget keys (after the JSON patch): each URL reads its own key', ceilingOf(flipped, '/analyst') === 100 && ceilingOf(flipped, '/') === 40 && ceilingOf(flipped, '/home') === 40);
	ok('budget keys: a URL without a ceiling reads undefined (reported, never passed)', ceilingOf(flipped, '/nope') === undefined && ceilingOf(null, '/') === undefined);
	const r = budgetRoutes({ routes: { '/map': '/(v3)/map' } });
	ok('budget routes: workspace → (deck), `/` and /home → (v3)/home, extras from the JSON', r['/analyst'] === '/(deck)' && r['/'] === '/(v3)/home' && r['/home'] === '/(v3)/home' && r['/ops'] === '/(deck)/ops' && r['/gods-eye'] === '/(deck)/gods-eye' && r['/map'] === '/(v3)/map');
}

console.log(failures ? `\n${failures} FAILED` : '\nroot-flip: all green');
process.exit(failures ? 1 : 0);
