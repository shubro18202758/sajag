/**
 * Advisories unit gate (V3-P6A; V3-SPEC §6.7, §8) — zero browser.
 *
 *   node tests/v3-comms.unit.mjs
 *   P6A_TREE=<copy of services/command-deck>  node tests/v3-comms.unit.mjs     (the mutation harness points it at a scratch copy)
 *
 *   1. MODEL     the pure view model (lib/v3/comms/model.ts): the exercise marker is split off a draft without losing a
 *                character of it; the roving keys wrap; a row is marked withheld for an operator-only kind OR an OSINT mark.
 *   2. PACKS     packs.comms3 EN / HI / MR carry the same keys; every `v3c_*` key the Advisories code uses exists; the EN copy
 *                keeps the copy rules; HI / MR are really translated; nothing says a draft was delivered.
 *   3. SAFETY    the withholding rules stay where the safety tests pin them, in the route's own source: "Drafted — not
 *                delivered" has exactly two call sites (the one status + the transient toast), the operator-only arm keeps its
 *                three empty withheld nodes and its single badge, the OSINT badge is the other and only other one, no
 *                Copy control exists in the withheld arm, the sign-in card is the first thing under the head.
 *   4. SHELL     /comms leaves the (deck) layout with `+layout@.svelte` and wears the V3 shell through CommsFrame exactly once;
 *                the frame imports no store (R4); no hex colour and no v2 icon set in the Advisories code.
 *   5. A11Y      the event list is a radiogroup of radios with a roving tab stop; the audience control states pressed; the side
 *                sheet is labelled and closes on Escape.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, readdirSync, existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TOOLS = path.resolve(HERE, '..');
const DECK = process.env.P6A_TREE ? path.resolve(process.env.P6A_TREE) : TOOLS;
const OUT = path.join(HERE, 'artifacts', 'v3-comms-bundle.mjs');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const read = (rel) => readFileSync(path.join(DECK, rel), 'utf8');

mkdirSync(path.dirname(OUT), { recursive: true });
const esbuild = createRequire(path.join(TOOLS, 'package.json'))('esbuild');
const built = await esbuild.build({
	stdin: {
		contents: `export * as model from './src/lib/v3/comms/model';\nexport * as packs from './src/lib/v3/comms/packs.comms3';\nexport { hi } from './src/lib/v3/comms/packs.comms3.hi';\nexport { mr } from './src/lib/v3/comms/packs.comms3.mr';`,
		resolveDir: DECK,
		loader: 'ts',
		sourcefile: 'v3-comms-entry.ts',
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
ok('bundle builds (model, packs.comms3)', built.errors.length === 0, built.errors[0]?.message?.split('\n')[0] ?? '');
if (built.errors.length) process.exit(1);
const { model, packs, hi, mr } = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);

// ── 1. MODEL ────────────────────────────────────────────────────────────────
{
	const m = model.splitMarker('[SIMULATED FEED · EMULATED — exercise text, not a real road hold] Procession: ~3 min hold.');
	ok('1. the exercise marker is split off the draft and nothing is lost (marker + rest = the string)', m.marker === '[SIMULATED FEED · EMULATED — exercise text, not a real road hold]' && `${m.marker} ${m.rest}` === '[SIMULATED FEED · EMULATED — exercise text, not a real road hold] Procession: ~3 min hold.');
	ok('1. a draft with no marker is untouched', model.splitMarker('Procession: ~3 min hold.').marker === null && model.splitMarker('Procession: ~3 min hold.').rest === 'Procession: ~3 min hold.');
	ok('1. only a LEADING bracket is a marker (a bracket later in the text is the text)', model.splitMarker('Hold on [Vidyasagar Setu] from 10:05').marker === null);
	ok('1. the OSINT label marker is split the same way', model.splitMarker('[News-reported — open-source report] Zone officers: x').marker === '[News-reported — open-source report]');
	ok('1. roving keys wrap and ignore others', model.rovingIndex('ArrowDown', 3, 4) === 0 && model.rovingIndex('ArrowUp', 0, 4) === 3 && model.rovingIndex('Home', 2, 4) === 0 && model.rovingIndex('End', 0, 4) === 3 && model.rovingIndex('a', 0, 4) === null && model.rovingIndex('ArrowDown', 0, 0) === null);
	const isPublic = (k) => k === 'procession';
	ok('1. a row is withheld for an operator-only kind, or for ANY OSINT mark (fail-closed), and not otherwise', model.rowWithheld({ eventKind: 'vehicle_pursuit' }, isPublic, null) === true && model.rowWithheld({ eventKind: 'procession' }, isPublic, { verification: null }) === true && model.rowWithheld({ eventKind: 'procession' }, isPublic, null) === false);
	const rows = model.factRows({ stretch: { roadName: 'Vidyasagar Setu' }, holdMinutes: 3 }, { kind: 'Procession', hold: '~3 min', when: '10:05', alt: 'VIP Road (Kazi Nazrul Islam Avenue)' });
	ok('1. the facts-used rows come in the order an officer checks them; no hold means no "from" row', rows.map((r) => r.key).join() === 'kind,road,hold,when,alt' && model.factRows({ stretch: { roadName: null }, holdMinutes: null }, { kind: 'x', hold: null, when: '', alt: null }).find((r) => r.key === 'when').value === null);
}

// ── 2. PACKS ────────────────────────────────────────────────────────────────
{
	const en = packs.COMMS3_PACKS.en;
	const keys = Object.keys(en);
	const missHi = keys.filter((k) => !(k in hi));
	const missMr = keys.filter((k) => !(k in mr));
	const extra = [...Object.keys(hi), ...Object.keys(mr)].filter((k) => !(k in en));
	ok('2. HI and MR carry exactly the EN keys', missHi.length === 0 && missMr.length === 0 && extra.length === 0, `${keys.length} keys · missing hi ${missHi} mr ${missMr} · extra ${extra}`);
	ok('2. every key starts with v3c_', keys.every((k) => k.startsWith('v3c_')));
	const used = new Set([...(function* () {
		const walk = function* (d) {
			for (const e of readdirSync(d, { withFileTypes: true })) {
				const p = path.join(d, e.name);
				if (e.isDirectory()) yield* walk(p);
				else if (/\.(svelte|ts)$/.test(e.name) && !/packs\.comms3/.test(e.name)) yield readFileSync(p, 'utf8');
			}
		};
		for (const d of ['src/lib/v3/comms', 'src/routes/(deck)/comms']) for (const src of walk(path.join(DECK, d))) for (const m of src.matchAll(/['"`](v3c_[a-z0-9_]+)['"`]/g)) yield m[1];
	})()]);
	ok('2. every v3c_ key the Advisories code uses exists', [...used].every((k) => k in en), [...used].filter((k) => !(k in en)).join());
	const call = (pack, k) => (typeof pack[k] === 'function' ? pack[k]('X') : pack[k]);
	const problems = [];
	for (const k of keys) {
		const t = String(call(en, k));
		if ((t.match(/ · /g) ?? []).length > 1) problems.push(`${k}: more than one " · "`);
		if (/\b[A-Z]{3,}\b/.test(t.replace(/\b(IST|SMS|ETA)\b/g, ''))) problems.push(`${k}: ALL-CAPS word`);
		if (/title$/i.test(k) && t.length > 32) problems.push(`${k}: title longer than 32`);
		if (/\b(was sent|is sent|been sent|delivered|published)\b/i.test(t)) problems.push(`${k}: claims a delivery`);
	}
	ok('2. the EN copy keeps the copy rules and never claims a delivery', problems.length === 0, problems.join(' | '));
	const untranslated = keys.filter((k) => typeof en[k] === 'string' && (hi[k] === en[k] || mr[k] === en[k] || !/[ऀ-ॿ]/.test(hi[k]) || !/[ऀ-ॿ]/.test(mr[k]) || /[ঀ-৿]/.test(mr[k])));
	ok('2. HI is Devanagari and MR Marathi for every string (nothing left in English)', untranslated.length === 0, untranslated.join());
	ok('2. the functional strings take their argument in all three languages', ['v3c_map_alt', 'v3c_copy_lang'].every((k) => [en, hi, mr].every((p) => String(p[k]('Ganesh visarjan')).includes('Ganesh visarjan'))));
}

// ── 3. SAFETY (the route's own source) ─────────────────────────────────────
const PAGE = 'src/routes/(deck)/comms/+page.svelte';
{
	const src = read(PAGE);
	ok('3. "Drafted — not delivered" has exactly two call sites in the route: the one status and the transient toast', (src.match(/comms_drafted_badge/g) ?? []).length === 2);
	const badges = [...src.matchAll(/data-testid="comms-withheld-badge" data-withheld-reason="([a-z-]+)"/g)].map((m) => m[1]);
	ok('3. the desk has exactly two withheld badges in source — one per arm, each stated once at run time', badges.length === 2 && badges.includes('osint') && badges.includes('operator-kind'), badges.join());
	const opBadge = src.match(/<span class="withheld-note" data-testid="comms-withheld-badge" data-withheld-reason="operator-kind">[\s\S]*?<\/span>/)?.[0] ?? '';
	ok('3. the operator-only badge says comms_withheld in its own span', /comms_withheld/.test(opBadge));
	const armStart = src.indexOf('{#if operatorOnly}');
	const tri = src.match(/<div class="trilingual withheld" data-testid="comms-trilingual" data-ready=\{facts \? 'yes' : 'no'\}>\s*\{#each SUPPORTED as s \(s\.code\)\}([\s\S]*?)\{\/each\}\s*<\/div>/);
	ok('3. the operator-only arm keeps its three withheld nodes: empty draft line, no dash, no Copy, no notice text', armStart >= 0 && !!tri && tri[1].includes('data-withheld="yes"') && tri[1].includes('data-facts=""') && tri[1].includes('<p class="adv-text withheld" lang={s.code}></p>') && !tri[1].includes('class="copy"') && !tri[1].includes('comms_') && !tri[1].includes('—'));
	ok('3. Regenerate is demoted and disabled for an operator-only kind and for an OSINT-withheld audience', /disabled=\{!facts \|\| operatorOnly \|\| audienceWithheld\}/.test(src) && /operatorOnly \|\| audienceWithheld \? 'ghost' : 'primary'/.test(src));
	ok('3. the citizen all-clear is refused for an operator-only kind and for ANY OSINT event', /disabled=\{!isPublicKind\(draftKind\) \|\| !!osintMark\}/.test(src) && /if \(!selected \|\| !isPublicKind\(draftKind\) \|\| osintMark\) return;/.test(src));
	ok('3. the OSINT arm hides its columns (kept in the DOM) only when EVERY draft is osint-withheld', /class:withheld=\{drafts\.length > 0 && drafts\.every\(\(d\) => d\?\.withheld && d\.withheldReason === 'osint'\)\}/.test(src));
	ok('3. Copy puts the whole draft string (marker included) on the clipboard', /oncopy\(draft\.text\)/.test(read('src/lib/v3/comms/DraftColumn.svelte')) && /writeText\(text\)/.test(src));
	ok('3. a withheld draft cannot be copied (Copy disabled for it, and the handler refuses)', /disabled=\{!draft \|\| draft\.withheld\}/.test(read('src/lib/v3/comms/DraftColumn.svelte')) && /if \(!draft \|\| draft\.withheld\) return;/.test(read('src/lib/v3/comms/DraftColumn.svelte')));
	const afterHead = src.slice(src.indexOf('</svelte:head>') + '</svelte:head>'.length);
	ok('3. the sign-in card is the first thing under the head (no panel of refused reads)', /^\s*\{#if ops\.signInRequired\}/.test(afterHead) && afterHead.includes('data-testid="comms-signin-required"'));
	ok('3. the page keeps its interrupts and the registry lifecycle', src.includes('wireInterrupts(') && src.includes('inboxFromUnits(') && /cityRegistry\.start\(\)/.test(src) && /cityRegistry\.stop\(\)/.test(src) && !src.includes('commandBar.live = null'));
	ok('3. no audit or analysis table on the page', !/<table|<thead|<tbody/.test(src) && !read('src/lib/v3/comms/CommsSheet.svelte').match(/<table/));
	const decisions = src.match(/\b(approve|reject|dismiss|authorise)\b/gi) ?? [];
	ok('3. the desk offers no decision verb (it drafts; a named officer decides elsewhere)', decisions.length === 0, decisions.join());
}

// ── 4. SHELL ────────────────────────────────────────────────────────────────
{
	const layout = 'src/routes/(deck)/comms/+layout@.svelte';
	ok('4. /comms resets out of the (deck) layout (`+layout@.svelte`) and renders CommsFrame', existsSync(path.join(DECK, layout)) && /CommsFrame/.test(read(layout)));
	const frame = read('src/lib/v3/comms/CommsFrame.svelte');
	ok('4. CommsFrame wraps the page in V3Shell exactly once, sets the command theme and reads the operator session', (frame.match(/<V3Shell>/g) ?? []).length === 1 && /dataset\.theme = 'command'/.test(frame) && /operatorSession\.refresh\(\)/.test(frame) && /\$lib\/v3\/tokens\.css/.test(frame));
	ok('4. the frame imports no store (the shell boundary, R4)', !/\$lib\/(ops|workspace|gods-eye|stores)/.test(frame));
	const files = [];
	const walk = (d) => {
		for (const e of readdirSync(path.join(DECK, d), { withFileTypes: true })) {
			const p = `${d}/${e.name}`;
			if (e.isDirectory()) walk(p);
			else if (/\.(svelte|ts)$/.test(e.name)) files.push(p);
		}
	};
	walk('src/lib/v3/comms');
	walk('src/routes/(deck)/comms');
	const bad = files.filter((f) => /#[0-9a-fA-F]{3,8}(?![a-zA-Z0-9])/.test(read(f).replace(/\{#(each|if|snippet)/g, '')));
	ok('4. no hex colour in the Advisories code (tokens only)', bad.length === 0, bad.join());
	ok('4. the v2 icon set is not used (V3 glyphs only)', files.every((f) => !/\$lib\/design\/icons|from '\$lib\/ui'/.test(read(f)) || /provideUiLang/.test(read(f))), 'provideUiLang is the language context, not an icon');
	ok('4. no raw ids or tool names as visible text: kinds go through kindLabel', /kindLabel\(lang, ev\.eventKind\)/.test(read(PAGE)));
}

// ── 5. A11Y ────────────────────────────────────────────────────────────────
{
	const page = read(PAGE);
	const row = read('src/lib/v3/comms/EventRow.svelte');
	const sheet = read('src/lib/v3/comms/CommsSheet.svelte');
	ok('5. the event list is a radiogroup of radios (aria-checked) with a roving tab stop and arrow keys', /role="radiogroup"/.test(page) && /role="radio"/.test(row) && /aria-checked=\{selected\}/.test(row) && /tabindex=\{r\.id === selectedId \? 0 : -1\}/.test(page) && /rovingIndex\(/.test(page));
	ok('5. the audience control states pressed (aria-pressed) on every button', /aria-pressed=\{audience === a\}/.test(page) && /role="group" aria-label=\{C\('comms_audience'\)\}/.test(page));
	ok('5. the side sheet is a labelled complementary region with tabs, and Escape closes it and returns focus', /<aside class="sheet"[^>]*aria-label=/.test(sheet) && /role="tablist"/.test(sheet) && /e\.key === 'Escape'/.test(page) && /back\?\.focus\(\)/.test(page));
	ok('5. the native event select is out of the tab order and hidden from assistive tech (the radiogroup is the accessible control)', /class="sr" tabindex="-1" aria-hidden="true"/.test(page));
	ok('5. the Copy buttons are named per language', /aria-label=\{copyAria\}/.test(read('src/lib/v3/comms/DraftColumn.svelte')));
	ok('5. motion respects prefers-reduced-motion (row lift, sheet slide)', /prefers-reduced-motion/.test(row) && /prefers-reduced-motion/.test(sheet));
}

if (failures) {
	console.error(`\nv3-comms.unit: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('\nv3-comms.unit: all green');
