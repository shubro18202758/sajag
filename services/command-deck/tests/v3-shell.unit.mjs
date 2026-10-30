/**
 * V3 shell unit test (V3-P6B; V3-SPEC §3.1, §6.9) — the operator pages under the V3 shell, held without a browser.
 *
 *   node tests/v3-shell.unit.mjs
 *
 * esbuild bundles the REAL nav table and the shell's string pack and asserts:
 *   - surfaceOf: /analyst, /ops, /gods-eye and /chat are the Analyst family (rail Analyst), /comms lights Advisories, and a
 *     /design page or an unknown path belongs to none; sub-paths follow their root; a look-alike (/opsx) is none;
 *   - the Analyst sub-nav: Workspace /analyst, Situation wall /ops, City map /gods-eye, Assistant /chat — every href is a
 *     route that exists under src/routes/(deck), and the V3 rail's own table still holds (navActive unchanged);
 *   - the pack: EN / HI / MR carry the same `v3s_` keys, HI and MR are translated (no Latin sentence, no Devanagari in
 *     MR, no Marathi in HI), every `v3s_` key the sources use exists, and the existing strings the band reuses exist in
 *     all three languages (nav_ops, shell_band, shell_inbox_*, shell_data, shell_policies, shell_live, ui_more …);
 *   - the sources that cannot be bundled (Svelte) still say it: the (deck) layout is the V3 shell around the operator band
 *     and the page's flex column (no CommandShell / Navbar), it never imports a store (R4), reads the operator session once;
 *     no route imports CommandShell or Navbar; the V3 shell derives the title and the rail item of those pages from
 *     surfaceOf; the operator band keeps the contract's test ids (band-tag via BandTag, data-inbox-intent, data-count,
 *     brain-posture with its data attributes, live-strip through LiveStrip, the More menu) and says it owns no data.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const OUT = path.join(HERE, 'artifacts', 'v3-shell-bundle.mjs');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const read = (rel) => readFileSync(path.join(DECK, rel), 'utf8');
const strip = (src) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1');

mkdirSync(path.dirname(OUT), { recursive: true });
const esbuild = createRequire(path.join(DECK, 'package.json'))('esbuild');
const built = await esbuild.build({
	stdin: {
		contents: `
export * as nav from './src/lib/v3/shell/nav';
export { SHELL_PACKS } from './src/lib/v3/shell/packs.shell';
export { t } from './src/lib/i18n/strings';
import './src/lib/i18n/packs';
import './src/lib/v3/packs.v3';
`,
		resolveDir: DECK,
		loader: 'ts',
		sourcefile: 'v3-shell-entry.ts',
	},
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	outfile: OUT,
	logLevel: 'silent',
	define: { 'import.meta.env': '{"DEV":false}', 'process.env.NODE_ENV': '"test"' },
	supported: { 'top-level-await': true },
});
ok('bundle builds (esbuild, $lib aliased)', built.errors.length === 0, `${built.errors.length} errors`);
const { nav, SHELL_PACKS, t } = await import(pathToFileURL(OUT).href);

// ─── surfaceOf ──────────────────────────────────────────────────────────────

const EXPECT = {
	'/analyst': ['analyst', true],
	'/ops': ['analyst', true],
	'/gods-eye': ['analyst', true],
	'/chat': ['analyst', true],
	'/comms': ['advisories', false],
	'/ops/': ['analyst', true],
	'/gods-eye/feeds': ['analyst', true],
};
const surfBad = Object.entries(EXPECT).filter(([p, [rail, family]]) => nav.surfaceOf(p)?.rail !== rail || nav.surfaceOf(p)?.analyst !== family);
ok('surfaceOf: the workspace, the wall, the city map and the assistant page are the Analyst family (rail Analyst); /comms lights Advisories', surfBad.length === 0, surfBad.map(([p]) => `${p} → ${JSON.stringify(nav.surfaceOf(p))}`).join(' | '));
const NONE = ['/', '/home', '/decide', '/map', '/assistant', '/plan', '/design', '/design/shell', '/opsx', '/analysts', '/chatty', '/o/event:1'];
const noneBad = NONE.filter((p) => nav.surfaceOf(p) !== null);
ok('surfaceOf: V3 screens, /design pages and look-alike paths belong to no deck surface', noneBad.length === 0, noneBad.join(' '));
ok('surfaceOf: every surface names an i18n key for its title', ['/analyst', '/ops', '/gods-eye', '/chat', '/comms'].every((p) => ['en', 'hi', 'mr'].every((l) => t(l, nav.surfaceOf(p).title) !== nav.surfaceOf(p).title)), 'titles resolve in EN / HI / MR');
ok('titles: /analyst "Analyst", /ops "Situation wall", /gods-eye "City map", /chat "Assistant" (EN)', ['Analyst', 'Situation wall', 'City map', 'Assistant'].every((w, i) => t('en', nav.surfaceOf(['/analyst', '/ops', '/gods-eye', '/chat'][i]).title) === w), ['/analyst', '/ops', '/gods-eye', '/chat'].map((p) => t('en', nav.surfaceOf(p).title)).join(' · '));

// ─── the sub-nav ────────────────────────────────────────────────────────────

ok('sub-nav: Workspace /analyst, Situation wall /ops, City map /gods-eye, Assistant /chat, in that order', nav.ANALYST_TABS.map((a) => `${a.id}:${a.href}`).join(',') === 'workspace:/analyst,wall:/ops,city:/gods-eye,assistant:/chat');
const routeDir = path.join(DECK, 'src/routes/(deck)');
const hasRoute = (href) => (href === '/analyst' ? existsSync(path.join(routeDir, '+page.svelte')) : existsSync(path.join(routeDir, href.slice(1), '+page.svelte')));
ok('sub-nav: every tab opens a route that exists (no link ever 404s)', nav.ANALYST_TABS.every((a) => hasRoute(a.href)), nav.ANALYST_TABS.filter((a) => !hasRoute(a.href)).map((a) => a.href).join(' ') || 'all four');
ok('sub-nav: every tab is a surface of the Analyst family, so the band and the rail agree', nav.ANALYST_TABS.every((a) => nav.surfaceOf(a.href)?.analyst === true));
ok('V3 rail unchanged: navActive keeps its table (the shell asks surfaceOf first for the deck pages)', nav.navActive('/') === 'home' && nav.navActive('/analyst') === 'analyst' && nav.navActive('/ops') === null && nav.navActive('/gods-eye') === null && nav.navActive('/chat') === null && nav.navActive('/comms') === 'advisories');
const shellSrc = strip(read('src/lib/v3/shell/V3Shell.svelte'));
ok('V3Shell: the active rail item is the page\'s own, else the deck surface\'s, else navActive; the title falls back to the surface\'s', /v3Bar\.active \?\? surface\?\.rail \?\? navActive\(pathname\)/.test(shellSrc) && /v3Bar\.title \?\? \(surface \? t\(lang, surface\.title\)/.test(shellSrc));
ok('V3Shell: the v2 toaster sits under the V3 top bar (--v-ws-navbar follows --v3-top)', /--v-ws-navbar:\s*var\(--v3-top\)/.test(shellSrc));

// ─── the pack ───────────────────────────────────────────────────────────────

const en = Object.keys(SHELL_PACKS.en);
const same = (a, b) => a.length === b.length && a.every((k) => b.includes(k));
ok('pack: EN / HI / MR carry the same keys, all starting v3s_', same(en, Object.keys(SHELL_PACKS.hi)) && same(en, Object.keys(SHELL_PACKS.mr)) && en.every((k) => k.startsWith('v3s_')), `${en.length} keys`);
const untranslated = (lang) => en.filter((k) => SHELL_PACKS[lang][k] === SHELL_PACKS.en[k]);
ok('pack: HI and MR are translated (no English left in place)', untranslated('hi').length === 0 && untranslated('mr').length === 0, [...untranslated('hi'), ...untranslated('mr')].join(', '));
ok('pack: no Bengali script left in HI or MR; MR is Marathi (Devanagari)', Object.values(SHELL_PACKS.hi).every((s) => !/[ঀ-৿]/.test(s)) && Object.values(SHELL_PACKS.mr).every((s) => /[ऀ-ॿ]/.test(s) && !/[ঀ-৿]/.test(s)));
ok('pack: registered, so t() answers in all three languages', en.every((k) => ['en', 'hi', 'mr'].every((l) => t(l, k) === SHELL_PACKS[l][k])));
const ACR = new Set('AI ID'.split(' '));
ok('pack: EN copy rules (no ALL-CAPS word, at most one " · ", sentence case)', Object.values(SHELL_PACKS.en).every((s) => (s.match(/ · /g) ?? []).length <= 1 && s.split(/[^A-Za-z]+/).every((w) => w.length < 2 || !/^[A-Z]+$/.test(w) || ACR.has(w))));

const used = new Set();
for (const f of ['src/lib/v3/shell/OpsBand.svelte', 'src/lib/v3/shell/nav.ts', 'src/lib/v3/shell/V3Shell.svelte', 'src/routes/(deck)/+layout.svelte']) for (const m of read(f).matchAll(/['"`](v3s_[a-z0-9_]+)['"`]/g)) used.add(m[1]);
ok('every v3s_ key the sources use exists in the pack', [...used].every((k) => en.includes(k)) && used.size >= 5, `${used.size} used: ${[...used].filter((k) => !en.includes(k)).join(' ') || 'all present'}`);
const REUSED = ['nav_ops', 'shell_band', 'shell_inbox_none', 'shell_inbox_waiting', 'shell_inbox_watchlist', 'shell_data', 'shell_policies', 'shell_policies_tip', 'shell_live', 'shell_shortcuts', 'shell_public_views', 'shell_hk_modules', 'shell_hk_module', 'v3_nav_analyst', 'v3_nav_advisories'];
const missing = REUSED.flatMap((k) => ['en', 'hi', 'mr'].filter((l) => !t(l, k) || t(l, k) === k).map((l) => `${l}:${k}`));
ok('the strings the operator band reuses exist in EN, HI and MR (no copy of an existing string is changed or duplicated)', missing.length === 0, missing.join(' ') || `${REUSED.length} keys`);

// ─── the (deck) layout and the operator band ────────────────────────────────

const layout = read('src/routes/(deck)/+layout.svelte');
const layoutCode = strip(layout);
ok('(deck) layout: the V3 shell wraps the operator band and the page\'s flex column', /import V3Shell from '\$lib\/v3\/shell\/V3Shell\.svelte'/.test(layoutCode) && /import OpsBand from '\$lib\/v3\/shell\/OpsBand\.svelte'/.test(layoutCode) && /<V3Shell>[\s\S]*<OpsBand \/>[\s\S]*\{@render children\?\.\(\)\}[\s\S]*<\/V3Shell>/.test(layoutCode));
ok('(deck) layout: the page keeps the column the v2 shell\'s main was (flex, column, min-height 0, scrolls)', /\.deck-main\s*\{[^}]*display:\s*flex[^}]*flex-direction:\s*column[^}]*min-height:\s*0[^}]*overflow:\s*auto/.test(layoutCode));
ok('(deck) layout: no CommandShell or Navbar; the V3 tokens are loaded here; the operator session is read once on mount', !/CommandShell|Navbar/.test(layoutCode) && /import '\$lib\/v3\/tokens\.css'/.test(layoutCode) && (layoutCode.match(/operatorSession\.refresh\(\)/g) ?? []).length === 1);
ok('(deck) layout: stays on the design-shell side of the R4 boundary (imports no ops, gods-eye or decisions store)', !/\$lib\/(ops|gods-eye|decisions|workspace)\//.test(layoutCode));

const walk = (d, out = []) => {
	for (const f of readdirSync(d)) {
		const p = path.join(d, f);
		if (statSync(p).isDirectory()) walk(p, out);
		else if (/\.(svelte|ts)$/.test(f)) out.push(p);
	}
	return out;
};
const importers = walk(path.join(DECK, 'src')).filter((f) => /import[^;]*\b(CommandShell|Navbar)\b[^;]*from|from\s+['"][^'"]*\/(CommandShell|Navbar)\.svelte['"]/.test(strip(readFileSync(f, 'utf8'))));
ok('no route or component imports the v2 CommandShell or Navbar any more', importers.length === 0, importers.map((f) => path.relative(DECK, f)).join(' ') || 'none');
const routeShells = walk(path.join(DECK, 'src/routes')).filter((f) => /\+layout\.svelte$/.test(f)).map((f) => [path.relative(DECK, f), /V3Shell|CitizenShell/.test(strip(readFileSync(f, 'utf8')))]);
ok('every operator route group draws the V3 shell, every public one its own', routeShells.filter(([f]) => /\((deck|v3)\)/.test(f)).every(([, v]) => v), routeShells.map(([f, v]) => `${f}:${v}`).join(' '));

const band = read('src/lib/v3/shell/OpsBand.svelte');
const bandCode = strip(band);
const NEED = [
	['the band tag (v2 BandTag: band-tag, data-band, data-age-sec)', /import BandTag from '\$lib\/shell\/BandTag\.svelte'[\s\S]*<BandTag band=\{commandBar\.band\} bandSource=\{commandBar\.bandSource\} bandAgeSec=\{commandBar\.bandAgeSec\}/],
	['the Inbox button (data-inbox-intent, data-count, the page\'s onInbox)', /data-inbox-intent=\{commandBar\.inboxIntent\}[\s\S]*data-count=\{commandBar\.inboxCount\}[\s\S]*disabled=\{!commandBar\.onInbox\}[\s\S]*commandBar\.onInbox\?\.\(\)/],
	['the Data button (brain-posture with data-decider, data-tier, data-worst; the v2 DataPanel)', /data-testid="brain-posture"[\s\S]*data-decider=\{ds\.decider\}[\s\S]*data-tier=\{ds\.tier\}[\s\S]*data-worst=\{ds\.worst\}[\s\S]*<DataPanel status=\{ds\}/],
	['Policies (the v2 PoliciesPanel)', /<PoliciesPanel \{lang\} \/>/],
	['More (data-menu="more", aria-label, the public views)', /data-menu="more"/, /PUBLIC_NAV\.map/],
	['the shortcuts sheet (HotkeysDialog data-shell="hotkeys"), `?` only when not typing, no Ctrl/Alt/Meta', /<HotkeysDialog[^>]*data-shell="hotkeys"/, /e\.key === '\?'/, /typing\(e\.target\) \|\| e\.ctrlKey \|\| e\.metaKey \|\| e\.altKey/],
];
for (const [name, ...res] of NEED) ok(`OpsBand: ${name}`, res.every((re) => re.test(bandCode)));
const liveBand = strip(read('src/lib/v3/shell/LiveBand.svelte'));
ok('LiveBand: the live strip only while the page has live content (the v2 LiveStrip, liveHasContent), directly under the top bar', /liveHasContent\(commandBar\.live\)/.test(liveBand) && /\{#if live\}[\s\S]*data-v3="live-band"[\s\S]*<LiveStrip \{live\} \{lang\} \/>/.test(liveBand) && /grid-row:\s*2/.test(liveBand) && !/\$lib\/(ops|gods-eye|decisions|workspace)\//.test(liveBand));
ok('V3Shell draws the live band under the top bar and keeps the screen in its own row, so the band never moves the rail or the bar', /<TopBar[^>]*\/>\s*<LiveBand \/>\s*<main/.test(shellSrc) && /grid-template-rows:\s*var\(--v3-top\) auto minmax\(0, 1fr\)/.test(shellSrc) && /\.v3-main\s*\{[^}]*grid-row:\s*3/.test(shellSrc));
ok('OpsBand does not draw the live strip (V3Shell does: one place, every page)', !/LiveStrip|live-band/.test(bandCode));
ok('OpsBand: it is the operator "command bar" (data-shell="command-bar") and owns no data (imports no store)', /data-shell="command-bar"/.test(bandCode) && !/\$lib\/(ops|gods-eye|decisions|workspace)\//.test(bandCode));
ok('OpsBand: no single key approves, unmasks, dispatches or publishes (the only key it binds is `?`)', (bandCode.match(/e\.key ===/g) ?? []).length === 1);
ok('OpsBand: no hex colour (the V3 tokens only)', !/#[0-9a-fA-F]{3,8}\b/.test(bandCode.replace(/href="#[^"]*"/g, '')));
ok('the legacy navbar Share is drawn nowhere in the V3 chrome (the view header owns Share)', !/commandBar\.onShare/.test(bandCode) && !/commandBar\.onShare/.test(strip(read('src/lib/v3/shell/TopBar.svelte'))));

console.log(failures ? `\n${failures} FAILED` : '\nv3-shell: all green');
process.exit(failures ? 1 : 0);
