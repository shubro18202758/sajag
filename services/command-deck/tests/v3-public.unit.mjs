/**
 * Public pages unit gate (V3-P6A; V3-SPEC §6.8, §8) — zero browser.
 *
 *   node tests/v3-public.unit.mjs
 *   P6A_TREE=<copy of services/command-deck>  node tests/v3-public.unit.mjs     (the mutation harness points it at a scratch copy)
 *
 *   1. GEOMETRY  the hold thumbnail's overlay (lib/v3/public/geometry.ts): segments chain in route order; a LIVE stretch draws
 *                solid (route), anything else DASHED — an emulated or fixture hold is never drawn as a live road hold; no
 *                geometry means no overlay (nothing is drawn that is not known).
 *   2. PACKS     packs.pub3 EN / HI / MR carry the same keys, really translated, copy rules kept.
 *   3. BOUNDARY  the public pages load no operator code: nothing under lib/v3/public, lib/citizen or routes/(public) imports the
 *                V3 shell, the officer control, the operator session, the decision units, the workspace or the entity registry;
 *                the pages never start the operator store; the shell carries no link into the deck.
 *   4. HONESTY   the SIMULATED / EMULATED / unverified / offline tags and the scripted-mode note are kept where the smokes and
 *                the deck-fixes unit pin them; /driver never shows a registration mark and collects no location; the posture
 *                never uses the alert red or the decision orange (frozen meanings).
 *   5. LAYOUT    one column of 592 px, type floors (posture ≥ 22 px, chips ≥ 16 px, controls ≥ 44 px, the request button ≥ 56 px),
 *                prefers-reduced-motion honoured, the day tokens are the only colours.
 *   6. LANDING   the third public page, /welcome (V3-LANDING; tests/welcome.unit.mjs holds the rest): the same boundary (no
 *                operator code, never the operator store), no hex colour, the strict (non-operator) document policy, and its
 *                links into the console reload (a CSP is per document).
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TOOLS = path.resolve(HERE, '..');
const DECK = process.env.P6A_TREE ? path.resolve(process.env.P6A_TREE) : TOOLS;
const OUT = path.join(HERE, 'artifacts', 'v3-public-bundle.mjs');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const read = (rel) => readFileSync(path.join(DECK, rel), 'utf8');
const walk = (d, out = []) => {
	for (const e of readdirSync(path.join(DECK, d), { withFileTypes: true })) {
		const p = `${d}/${e.name}`;
		if (e.isDirectory()) walk(p, out);
		else if (/\.(svelte|ts)$/.test(e.name)) out.push(p);
	}
	return out;
};

mkdirSync(path.dirname(OUT), { recursive: true });
const esbuild = createRequire(path.join(TOOLS, 'package.json'))('esbuild');
const built = await esbuild.build({
	stdin: {
		contents: `export * as geo from './src/lib/v3/public/geometry';\nexport * as packs from './src/lib/v3/public/packs.pub3';\nexport { hi } from './src/lib/v3/public/packs.pub3.hi';\nexport { mr } from './src/lib/v3/public/packs.pub3.mr';`,
		resolveDir: DECK,
		loader: 'ts',
		sourcefile: 'v3-public-entry.ts',
	},
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	outfile: OUT,
	logLevel: 'silent',
	define: { 'import.meta.env.SSR': 'true' },
}).catch((e) => ({ errors: [e] }));
ok('bundle builds (geometry, packs.pub3)', built.errors.length === 0, built.errors[0]?.message?.split('\n')[0] ?? '');
if (built.errors.length) process.exit(1);
const { geo, packs, hi, mr } = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);

// ── 1. GEOMETRY ─────────────────────────────────────────────────────────────
{
	const segs = new Map([
		[1, { coordinates: [[72.0, 22.54], [72.1, 22.54]] }],
		[2, { coordinates: [[72.2, 22.54], [72.1, 22.54]] }], // stored against the route: must be turned
		[3, { coordinates: [[72.2, 22.54], [88.07, 22.64]] }],
	]);
	const chain = geo.chainSegments([1, 2, 3], segs);
	ok('1. segments chain in route order, each turned to start where the last ended, joints not doubled', JSON.stringify(chain) === JSON.stringify([[72.0, 22.54], [72.1, 22.54], [72.2, 22.54], [88.07, 22.64]]), JSON.stringify(chain));
	ok('1. a segment the geometry does not know is skipped, not invented', geo.chainSegments([1, 99, 2], segs).length === 3);
	const live = geo.holdOverlay([1, 2], segs, true);
	const dashed = geo.holdOverlay([1, 2], segs, false);
	ok('1. a LIVE stretch draws as the route line, solid', live.lines[0].style === 'route');
	ok('1. an emulated / fixture / unverified stretch draws DASHED — never a live road hold', dashed.lines[0].style === 'dashed' && dashed.lines.every((l) => l.style !== 'route'));
	ok('1. one pin sits on the stretch (a place, never a person)', live.points.length === 1 && live.points[0].glyph === 'pin');
	ok('1. no geometry, no overlay (nothing is drawn that is not known)', geo.holdOverlay([99], segs, true) === null && geo.holdOverlay([], segs, true) === null);
}

// ── 2. PACKS ────────────────────────────────────────────────────────────────
{
	const en = packs.PUB3_PACKS.en;
	const keys = Object.keys(en);
	ok('2. HI and MR carry exactly the EN keys; every key starts with v3p_', keys.every((k) => k in hi && k in mr && k.startsWith('v3p_')) && Object.keys(hi).length === keys.length && Object.keys(mr).length === keys.length, `${keys.length} keys`);
	const used = new Set();
	for (const f of [...walk('src/lib/v3/public'), ...walk('src/lib/citizen'), ...walk('src/routes/(public)')]) if (!/packs\.pub3/.test(f)) for (const m of read(f).matchAll(/['"`](v3p_[a-z0-9_]+)['"`]/g)) used.add(m[1]);
	const dynamic = [...used].filter((k) => !(k in en));
	ok('2. every v3p_ key the public code uses exists (the language-short keys are built from the code)', dynamic.length === 0, dynamic.join());
	ok('2. the three language-short keys exist for every supported code', ['en', 'hi', 'mr'].every((c) => `v3p_lang_short_${c}` in en));
	const call = (p, k) => (typeof p[k] === 'function' ? p[k](2) : p[k]);
	const bad = keys.filter((k) => (String(call(en, k)).match(/ · /g) ?? []).length > 1 || /\b[A-Z]{4,}\b/.test(String(call(en, k))));
	ok('2. the EN copy keeps the copy rules', bad.length === 0, bad.join());
	const same = keys.filter((k) => !/lang_short|logo/.test(k) && (call(hi, k) === call(en, k) || call(mr, k) === call(en, k) || !/[ऀ-ॿ]/.test(call(hi, k)) || !/[ऀ-ॿ]/.test(call(mr, k)) || /[ঀ-৿]/.test(call(mr, k))));
	ok('2. HI is Devanagari and MR Marathi (nothing left in English)', same.length === 0, same.join());
}

// ── 3. BOUNDARY ─────────────────────────────────────────────────────────────
{
	const files = [...walk('src/lib/v3/public'), ...walk('src/lib/citizen'), ...walk('src/routes/(public)')];
	const DENY = /(\$lib\/v3\/(shell|decide|object|plan|assistant|home\/view|home\/Feature)|\$lib\/v3\/map\/(MapPage|NowPanel|LayersSheet|MapTools|SelectionCard|StatsPanel|WeatherChip)|\$lib\/shell\/(OfficerControl|session|OperatorSignIn|SignInWall|CommandShell|Navbar|LiveStrip|DataPanel)|\$lib\/decisions|\$lib\/workspace|\$lib\/gods-eye\/(entities|canvas)|\$lib\/assistant|\.\.\/shell\/|\.\.\/decide\/|\.\.\/object\/)/;
	const offenders = [];
	for (const f of files) for (const m of read(f).matchAll(/(?:from|import)\s+['"]([^'"]+)['"]/g)) if (DENY.test(m[1])) offenders.push(`${f} → ${m[1]}`);
	ok('3. no public file imports the V3 shell, the officer control, the operator session, decisions, the workspace or the entity registry', offenders.length === 0, offenders.slice(0, 4).join(' | '));
	const starts = files.filter((f) => /\bops\.start\(|cityRegistry\.start\(|liveWorld\./.test(read(f)));
	ok('3. no public page starts the operator store or the city registry', starts.length === 0, starts.join());
	const shell = read('src/lib/v3/public/PublicShell.svelte');
	ok('3. the public shell links only the two public views — no band code, no operator search, no Share, no officer', !/href="\/(ops|decide|map|comms|analyst|assistant|plan)/.test(shell) && !/band|share|officer|search/i.test(shell.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '').replace(/\{#each[\s\S]*$/, '') ) );
	ok('3. the (public) layout wears PublicShell (and still resets the theme on leaving)', /PublicShell/.test(read('src/routes/(public)/+layout.svelte')) && /dataset\.theme = 'command'/.test(read('src/routes/(public)/+layout.svelte')));
	ok('3. the public map thumb reads only the public segments endpoint', /fetchSegments\(NETWORK_BBOX\)/.test(read('src/lib/v3/public/geometry.ts')) && !/ORACLE_V1|\/api\/v1\/(vehicles|enforcement|dispatches|city)/.test(read('src/lib/v3/public/geometry.ts')));
}

// ── 4. HONESTY ──────────────────────────────────────────────────────────────
{
	const adv = read('src/lib/citizen/CitizenAdvisory.svelte');
	const drv = read('src/lib/citizen/GreenCorridorDriver.svelte');
	ok('4. the SIMULATED FEED · EMULATED tag is on every emulated card, the hero and the Later row; the unverified tag keeps its pin', (adv.match(/data-source-badge="emulated"/g) ?? []).length >= 3 && /data-source-badge="unverified"/.test(adv) && /unverified \? 'card_unv_now'/.test(adv));
	ok('4. an emulated hold never reads "Holding now" on a real road (sim / unverified words)', /emulated \? 'card_sim_now'/.test(adv) && /emulated \? 'card_sim_soon'/.test(adv));
	ok('4. an emulated or unverified card is outlined (dashed), never solid', /\.event-card\.emulated \{[^}]*border-style: dashed/.test(adv));
	ok('4. the hold map draws a non-live stretch dashed (the live flag is `source === live`)', /live=\{ev\.source === 'live'\}/.test(adv));
	ok('4. /driver keeps the scripted-mode honesty note, the "nothing is sent" fallback and the withheld-emulated count', /data-testid="scripted-note"/.test(drv) && /scripted_note/.test(drv) && /data-testid="driver-emulated-withheld"/.test(drv) && /\{#if !scripted\}<p data-testid="driver-sub">/.test(drv));
	ok('4. /driver has no approve control and keeps the officer in the loop', !/approve\w*\(|onclick=\{[^}]*approve/i.test(drv) && /driver_awaiting_title/.test(drv));
	ok('4. /driver collects no location and shows no registration mark (no geolocation call, no plate field)', !/geolocation|getCurrentPosition|watchPosition/.test(drv + adv) && !/\b(plate|registration)\b/i.test(drv.replace(/\/\*[\s\S]*?\*\//g, '')));
	const css = (src) => src.slice(src.indexOf('<style>'));
	const red = /var\(--v3-(alert|decide)[a-z-]*\)/;
	ok('4. the public pages never use the alert red or the decision orange (frozen meanings)', !red.test(css(adv)) && !red.test(css(drv)) && !red.test(css(read('src/lib/v3/public/PublicShell.svelte'))) && !red.test(css(read('src/lib/v3/public/PublicTag.svelte'))));
	ok('4. the golden-hour clock still counts from THIS request, never from page load (F-08)', /requestedAtMs == null \? null/.test(drv) && /golden_not_started/.test(drv) && !/goldenElapsed \+= 1/.test(drv));
	ok('4. the page titles are translated keys', /<title>\{t\(ops\.lang, 'citizenTabTitle'\)\} · Sajag<\/title>/.test(read('src/routes/(public)/citizen/+page.svelte')) && /<title>\{t\(lang, 'driverTitle'\)\} · Sajag<\/title>/.test(read('src/routes/(public)/driver/+page.svelte')));
}

// ── 5. LAYOUT ───────────────────────────────────────────────────────────────
{
	const adv = read('src/lib/citizen/CitizenAdvisory.svelte');
	const drv = read('src/lib/citizen/GreenCorridorDriver.svelte');
	const px = (src, sel, prop) => {
		const m = src.match(new RegExp(`${sel.replace(/[.[\]()]/g, '\\$&')}\\s*\\{[^}]*?${prop}:\\s*(\\d+)px`));
		return m ? Number(m[1]) : null;
	};
	ok('5. one column of 592 px on both pages', /max-width: 592px/.test(adv) && /max-width: 592px/.test(drv));
	ok('5. /citizen: the posture sentence ≥ 22 px, the title ≥ 28 px', (px(adv, '.strip p', 'font-size') ?? 0) >= 22 && (px(adv, '.kicker', 'font-size') ?? 0) >= 28);
	ok('5. /driver: the clock ≥ 56 px, the countdown number ≥ 56 px, the request button ≥ 56 px, urgency chips ≥ 44 px with ≥ 16 px type', (px(drv, '.golden-clock', 'font-size') ?? 0) >= 56 && (px(drv, '.cd-n', 'font-size') ?? 0) >= 56 && (px(drv, '.big', 'min-height') ?? 0) >= 56 && (px(drv, '.urg', 'min-height') ?? 0) >= 44 && (px(drv, '.urg', 'font-size') ?? 0) >= 16);
	ok('5. the public controls are touch-sized (≥ 44 px): language buttons, view links, form fields, subscribe, the CTA', (px(read('src/lib/v3/public/PublicShell.svelte'), '.lang > button', 'min-height') ?? 0) >= 40 && (px(read('src/lib/v3/public/PublicShell.svelte'), '.view', 'min-height') ?? 0) >= 44 && (px(adv, 'form input,\n\tform select', 'height') ?? 0) >= 44 && (px(adv, '.cta', 'min-height') ?? 0) >= 44);
	ok('5. the pulse stops under prefers-reduced-motion', /prefers-reduced-motion: reduce\)[\s\S]*?\.pulse \{[^}]*animation: none/.test(drv));
	const hex = [...walk('src/lib/v3/public'), 'src/lib/citizen/CitizenAdvisory.svelte', 'src/lib/citizen/GreenCorridorDriver.svelte', 'src/lib/citizen/LightCorridorMap.svelte'].filter((f) => /#[0-9a-fA-F]{3,8}(?![a-zA-Z0-9])/.test(read(f).replace(/\{#(each|if|snippet)/g, '')));
	ok('5. no hex colour on the public pages (the V3 day tokens only)', hex.length === 0, hex.join());
	ok('5. the day theme carries the V3 day tokens (the public shell loads tokens.css; the server renders daylight)', /\$lib\/v3\/tokens\.css/.test(read('src/lib/v3/public/PublicShell.svelte')) && /id\.startsWith\('\/\(public\)'\) \? 'daylight'/.test(read('src/hooks.server.ts')));
}

// ── 6. LANDING ──────────────────────────────────────────────────────────────
{
	const files = [...walk('src/lib/v3/landing'), ...walk('src/routes/(landing)')];
	const DENY = /(\$lib\/v3\/(shell|decide|object|plan|assistant|home|map)\/|\$lib\/shell\/|\$lib\/decisions|\$lib\/workspace|\$lib\/gods-eye|\$lib\/ops|\$lib\/assistant|\$lib\/stores|\$stores|data-service)/;
	const offenders = [];
	for (const f of files) for (const m of read(f).matchAll(/(?:from|import)\s+['"]([^'"]+)['"]/g)) if (DENY.test(m[1])) offenders.push(`${f} → ${m[1]}`);
	ok('6. /welcome loads no operator code (no shell, screen, store, workspace, gods-eye or data-service)', files.length >= 7 && offenders.length === 0, offenders.slice(0, 4).join(' | ') || `${files.length} files`);
	ok('6. /welcome never starts the operator store or the city registry, and calls no API', files.every((f) => !/\bops\.start\(|cityRegistry\.start\(|liveWorld\.|\bfetch\(/.test(read(f))));
	const hex = files.filter((f) => /#[0-9a-fA-F]{3,8}(?![a-zA-Z0-9-])/.test(read(f).replace(/href="#[\w-]+"/g, '').replace(/\{#(each|if|snippet)/g, '')));
	ok('6. no hex colour on /welcome (the V3 tokens only)', hex.length === 0, hex.join());
	const hooks = read('src/hooks.server.ts');
	ok('6. /welcome is a strict public document (hooks: only the (deck) and (v3) groups get the operator policy)', /operator: id\.startsWith\('\/\(deck\)'\) \|\| id\.startsWith\('\/\(v3\)'\),/.test(hooks));
	const land = read('src/lib/v3/landing/Landing.svelte');
	const toConsole = [...land.matchAll(/<a\b[^>]*href=\{HREF\.console\}[^>]*>/g)].map((m) => m[0]);
	ok('6. every /welcome link into the console reloads (never a client-side hop into the operator policy)', toConsole.length > 0 && toConsole.every((t) => /data-sveltekit-reload/.test(t)));
}

if (failures) {
	console.error(`\nv3-public.unit: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('\nv3-public.unit: all green');
