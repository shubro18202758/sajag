/**
 * FIX-E-PERF2 unit test (round 2) — the per-language packs, their loading on
 * the SHIPPED (production) path, and the split icon set.
 *
 *   node tests/perf2.unit.mjs                       # the checks
 *   node tests/perf2.unit.mjs --print-golden <src>  # recompute the golden from a tree (review aid)
 *
 * 1. Strings never change, per module × language × copy. PACK_GOLDEN below
 *    was computed ONCE from main's pre-split packs (`--print-golden` on main's
 *    src, reviewed) and is written into this file: for every one of the 16
 *    pack modules and each language, the key count and a sha256 of the
 *    canonical (key, initializer source text) list. Every copy is checked ON
 *    ITS OWN against it — EN in the base module; HI and MR in the `.hi.ts` /
 *    `.mr.ts` modules (the copy that runs: the server, vite dev, the tests and
 *    the production browser all import it); and, for the four packs two AST
 *    readers still read as text (packs, packs.map, packs.workspace,
 *    packs.agent), the never-registered text mirror in the base module. No
 *    merging by key name, no git: a changed value, a dropped or added key in
 *    any one copy fails. The other twelve base modules hold no HI/MR literal
 *    at all (one source of truth).
 * 2. Loading on the production path. The pack modules, lib/i18n/load.ts and
 *    the ops store are bundled with the PRODUCTION client defines
 *    (process.env.NODE_ENV='production', import.meta.env.SSR=false) — the
 *    branch that registers every language eagerly folds away exactly as in
 *    the shipped build — and each path is driven in a fresh module instance:
 *      a. a switch (`ensureLang`) lands HI, then MR, for EVERY one of the 16
 *         modules (one sampled key per module, compared with its .hi/.mr
 *         value); while a chunk is in flight t() answers EN, never a raw key;
 *         the registration hook fires (the re-render signal);
 *      b. the cold path: `<html lang="mr">` set before the modules evaluate →
 *         every module's MR strings are in before evaluation finishes (what
 *         hydration waits for), HI is not fetched;
 *      c. the ops store's `lang` setter alone, and `adoptLangCookie()` alone
 *         (sajag_lang cookie), each land the language for all 16 modules;
 *      d. a real Svelte 5 `$effect` reading t() re-runs once the chunk lands
 *         (svelte compiled for the client; flushSync), showing HI.
 * 3. Icons. `ICONS_16` / `ICONS_20` are complete, frozen and in main's order
 *    with main's path data (golden hashes); in the production bundle
 *    `isIconName` knows all 206 names before anything loads, a deferred glyph
 *    has no paths until `loadRestIcons()` lands and then every name resolves
 *    at 16 and 20 px. The first-paint half is EXACTLY the pinned
 *    first-viewport sets plus the map-marker glyphs (every KIND_ICON /
 *    EVENT_KIND_ICON glyph) plus the canvas's Layers / Legend panel glyphs. With a production build present, the server
 *    render of `/`, `/ops` and `/gods-eye` (EN/HI/MR) is collected and every
 *    glyph it draws must be in the first-paint half and in that route's
 *    pinned set (tests/perf2-prod-smoke.mjs checks the browser's first
 *    viewport for blank glyphs).
 *
 * Exits 0 with `ok` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { WORKSPACE } from './lib/routes.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const require = createRequire(path.join(DECK, 'package.json'));
const ts = require('typescript');

const MODULES = [
	'strings', 'strings.ops', 'strings.citizen', 'packs', 'packs.ui', 'packs.wall', 'packs.views', 'packs.decisions',
	'packs.dss', 'packs.analysis', 'packs.assistant', 'packs.osint', 'packs.corridor', 'packs.map', 'packs.workspace', 'packs.agent',
];
/** The four packs tests/thermal-toolbar.unit.mjs and tests/omnibar-lookup.unit.mjs read as text (FIX-E-PERF2 blocked request). */
const MIRRORED = new Set(['packs', 'packs.map', 'packs.workspace', 'packs.agent']);
const LANGS = ['en', 'hi', 'mr'];

// ── the canonical form of one pack literal ───────────────────────────────────

function unwrap(n) {
	while (n && (ts.isAsExpression(n) || ts.isSatisfiesExpression?.(n) || ts.isParenthesizedExpression(n))) n = n.expression;
	return n;
}

/** Top-level `[export] const <name> = { … }` object literals of a file, by name. */
function packLiterals(file) {
	const sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
	const out = {};
	for (const st of sf.statements) {
		if (!ts.isVariableStatement(st)) continue;
		for (const d of st.declarationList.declarations) {
			const init = unwrap(d.initializer);
			if (ts.isIdentifier(d.name) && init && ts.isObjectLiteralExpression(init)) out[d.name.text] = { sf, obj: init };
		}
	}
	return out;
}

/** key → { text (whitespace-normalised initializer source), value (a plain string literal's value, else null) }. */
function entries({ sf, obj }) {
	const map = new Map();
	let odd = 0;
	for (const p of obj.properties) {
		if (!ts.isPropertyAssignment(p) || !(ts.isIdentifier(p.name) || ts.isStringLiteral(p.name))) {
			odd++;
			continue;
		}
		const init = p.initializer;
		const lit = ts.isStringLiteral(init) || ts.isNoSubstitutionTemplateLiteral(init) ? init.text : null;
		map.set(p.name.text, { text: init.getText(sf).replace(/\s+/g, ' ').trim(), value: lit, dup: map.has(p.name.text) });
	}
	return { map, odd };
}

function digest(lit) {
	const { map, odd } = entries(lit);
	const lines = [...map.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)).map(([k, v]) => `${k}\u0000${v.text}`);
	return { count: map.size, sha: createHash('sha256').update(lines.join('\n')).digest('hex'), odd };
}

// ── --print-golden: recompute the table from a tree (pre-split or split src) ──
// HI/MR are read from the per-language module (`<m>.hi.ts`, `<m>.mr.ts`: the copy that runs) when the tree has
// one, else from the base module's literal (main's pre-split packs). Review the printed rows before pasting them.

if (process.argv[2] === '--print-golden') {
	const dir = path.join(process.argv[3], 'lib/i18n');
	const table = {};
	for (const m of MODULES) {
		const lits = packLiterals(path.join(dir, `${m}.ts`));
		for (const l of ['hi', 'mr']) {
			const split = path.join(dir, `${m}.${l}.ts`);
			if (existsSync(split)) lits[l] = packLiterals(split)[l];
		}
		table[m] = {};
		for (const l of LANGS) {
			if (!lits[l]) throw new Error(`${m}: no const ${l} literal`);
			const d = digest(lits[l]);
			table[m][l] = [d.count, d.sha];
		}
	}
	console.log(JSON.stringify(table, null, '\t'));
	process.exit(0);
}

/**
 * The golden: main's packs before the split (VVIP main, the base this work
 * package is cut against), per module × language: [key count, sha256 of the
 * sorted (key, initializer source) list]. Recompute with --print-golden.
 * Since the split, a row changes only with a reviewed copy change and says why at its end (2026-10-28: the
 * Sajag rename and the Gujarati → Marathi switch; the split packs are digested EN from the base module and
 * HI/MR from the `.hi.ts`/`.mr.ts` modules, exactly as the checks below read them).
 */
const PACK_GOLDEN = {
	// Re-derived 2026-10-28 (Sajag): the Marathi packs (danda sentence ends), the Kolkata EN/HI copy, and the merged streams' pack edits — recomputed with `--print-golden src` after every stream merged.
	// 2026-10-29 (UI audit): strings.citizen gains map_title / map_credits (the citizen map's accessible name); packs HI band words in Hindi.
	// 2026-10-29 (look): packs nav_citizen / nav_driver say "Your road" and "Ambulance (108)" in all three languages.
	// 2026-10-29 (look, round 2): packs.decisions dec_live_movement says "Protected movement" (not "VVIP") in all three languages.
	// 2026-10-30 (lang, Mumbai): Marathi is Devanagari — every MR pack retranslated from the EN; EN/HI copy speaks Mumbai (city, marathon, Republic Day parade at Shivaji Park, Ganesh visarjan, CSMT, the replay no longer names the Kolkata night); the MR text mirrors synced.
	'strings': { en: [146, '97233ec75ada304b22019805e633b478ab1e33a6b6d52e11cd4b87a133471ce0'], hi: [146, '27d4ea3963dcbc568d71a128dcf0d61b6e112f6088ac8920f42197dcc6886dc2'], mr: [146, '3d0c3bd449c9ec5aaddf8684064a71308d19279862f595fd57dcfe300534916f'] },
	'strings.ops': { en: [438, 'df2a64a61f561a8ea444e72a8629dedb67029b0b867f3c5faedca98b3d6f40f8'], hi: [438, 'a15d4339be4e0e76069121c3fc9f038be1c03a4cd91f59bfdf36e890fda6371f'], mr: [438, '8566daf9ad5f278d4c401dc7c1f0104515314f213ad3612b0cd408380e0bfcbf'] },
	'strings.citizen': { en: [205, '6953e82331129c1688891761fe810bc6de9512affd7d9f90fe1d051e90fadf29'], hi: [205, 'c3a8e73b86bf4bc45729a36580839113f9665edc925bb751f75dcfe508f17c2c'], mr: [205, '44167f2e8b36ae830c49834b1896a226bdfb2afa7e2db45017587be2cfe9af8e'] },
	'packs': { en: [390, '2f6d05901fccc1f02881853f452990b2d55b524c57e849d1b4807589014aac77'], hi: [390, '7b8127c4827900a17a8ca7627a62562070b3a111fe9a45759df1aa66e28aaffe'], mr: [390, '1ed52aac92b534a3db14531b5d95cfd007567087dd2cffb3900b0ed2fd8a4432'] },
	'packs.ui': { en: [77, '336571b9c2618b1f5a04460921c2071561d77c328e72959512b7757c5ab10e10'], hi: [77, '0b50bf2c25811a196aad26e73662f949fee8b30f3aab17d89ca0e55f4dbfc376'], mr: [77, 'f1d24395bc728acb7e7fe73e32d3b503bc05fabfc15d424c9586f1d89bea037a'] },
	'packs.wall': { en: [358, '67edbf2dca64dc98dca440f243918541c3a5ac2747a4d9c302809bb5f204d6ff'], hi: [358, 'e3464d365c64c15fd6192384409993fff2365b578a4249fe5ce6e2b03725f725'], mr: [358, 'd9a66360cd41ccb50a0b160884f9bd8e9ede8d0a8f2a51ec6a5987cddb8ebff1'] },
	'packs.views': { en: [229, '98a28fe74628344d747b42ff18af4fe7018a25dff31f8ee374e0d4e972a7ba08'], hi: [229, '518219e53accd6c8b5f7b4265a8fd00050ef6b1cb7c293e3e68f2aa79d57b6c2'], mr: [229, '3987b3f22ec77155e53374a83db699c0c562859371bd98624347835fe0525ff9'] },
	'packs.decisions': { en: [307, '9c7c67345e15f020246cc7e86127d400e7de215a940d43e9d0aa99fd90bc2d08'], hi: [307, '6b6246d206178ce04f4b3c03ad42029e401bc07e6cb5d11460cb8e65e7b4d1af'], mr: [307, '998983e7febe045e7405c2441c51111f1fe6f803846682bdcdbc7d261b4521d5'] },
	'packs.dss': { en: [115, '400f0f70b63377a0f369bf4b64d5f255aabae18b0989ded275d489e98d2fd99a'], hi: [115, '3a27baf86a0478ed51c0b6e875691a03508443f7de541287318fbe6a89b9ed83'], mr: [115, '760ab76937f7a7ea909671ce17795c19ec26cd9df89760516cf63e17d3456987'] },
	'packs.analysis': { en: [168, '339cb1e0d43ce1b0541762822380c842e22519bbbb53183b1c38564ff1ac77f5'], hi: [168, '67ea9601b8491b81886ed31a2189e4dbb74b90bcfc1212408bebd86849ca5896'], mr: [168, '2ef4db927048179dd0cc9f02e87e809c9db9ac78657424e4b6781b1993ea92d7'] },
	'packs.assistant': { en: [38, '83e880385721c92473ef7d2f37ac1922c08bbb8bf5842170b19d7af4e156622c'], hi: [38, 'e1d6fd5d2ddb9180ce886e97a743f09e5c97cc0f1acc3ec8b9b4274d7e647c9d'], mr: [38, '0ff450d0da67f10b59afadb93d574150b09366538b25bb564c74e79b73182d0c'] },
	'packs.osint': { en: [72, 'f2aa54a8e11e26ce4037c4d497266343ff8f0195150de91e8a0a12342c1b392e'], hi: [72, 'be4cd5a171bc5a214f9f58dd86b76dd4d7aabaa35960e42d2604176189bdb295'], mr: [72, 'b41afa5e636c23b5f24944164c932539c5158c8672965539fb24daf42c6364e8'] },
	'packs.corridor': { en: [81, 'c6dc0e39b044c7dbe69f6cdfe970d9b16673b8459f70f7262684b2fccc091ea6'], hi: [81, 'efca89a81e6b091a5c47042653f49d8e8555c536e9b2092c093ad7954976ff7a'], mr: [81, '4fb3e2158b8865bcb09f86fea0c32b9973b18589f278c5c1b113561add0c68e3'] },
	'packs.map': { en: [101, '6cf7c2b55e7e1d74be3bf846fc644d5e67fc6a6f83650e92a03ed5409a03abb7'], hi: [101, '291c2d552140735837313581834865e3740d1a663d56cbf3d3e1ef311347413f'], mr: [101, '4c8f36146030842827f51198fab414b3dfeab0eaf37186ead55de13fb0cd5e53'] },
	'packs.workspace': { en: [436, 'af49d5ccbb1392ed8079b1e13493b5b99d1ae18d1737c1b0fd49e728879df225'], hi: [436, 'bcb96bed1fed1886a1cf9be3bb36aa5063814c53cc9c769d9f692cbc3bdb4ee1'], mr: [436, 'ff3faaed20f76c444df1f938543a2c10f72663a4ec5e063ec190c8434ec50d02'] },
	'packs.agent': { en: [54, '8c5fd936b00f8d06a49eacf656b9f8d13d2eb67028801060823b2640d9fe8992'], hi: [54, 'f0eb02ff780dd0f0645ef18c8312c562966f841c4e14cc7830bfb00e0603cd06'], mr: [54, 'f943e624357edbafb1beddb7bcf9d6a81c153efd32683dc4ac94056b479f1a4b'] },
};

/**
 * The golden icon tables: main's ICONS_16 / ICONS_20 before the split — the
 * name count, a sha256 of the names in table order, and a sha256 of the
 * name+paths list in table order.
 */
const ICON_GOLDEN = {
	n16: 206,
	order16: '6522ab22c7e4f7de6d82dc1f59e82a866065145f0c92e6859f8eb575cca6985d',
	paths16: 'c987a82ad9cf052a81a006a5b6d06f31542ad85347fe467b4a3313a9529d4f16',
	n20: 24,
	paths20: '06aa6824a60a3def1800f6c4f8e7de0e26f06ff239e889c8e601d01dedbba5d2',
};

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

const I18N = path.join(DECK, 'src/lib/i18n');

// ── 1. strings, per module × language × copy ─────────────────────────────────

/**
 * One sampled key per module (a plain string in all three languages, translated), with its HI and MR values. The key
 * is one NO other module defines: registration is first-wins, so a key two modules share (the six OSINT event kinds
 * live in both strings and packs.osint) answers from whichever registered first and cannot prove this module's chunk
 * landed.
 */
const SAMPLE = {};
const OWNERS = new Map(); // EN key → how many of the 16 modules define it
for (const m of MODULES) {
	const lit = packLiterals(path.join(I18N, `${m}.ts`)).en;
	if (lit) for (const k of entries(lit).map.keys()) OWNERS.set(k, (OWNERS.get(k) ?? 0) + 1);
}
for (const m of MODULES) {
	const base = packLiterals(path.join(I18N, `${m}.ts`));
	const copies = [['en', 'base module', base.en]];
	for (const l of ['hi', 'mr']) {
		const f = path.join(I18N, `${m}.${l}.ts`);
		copies.push([l, `${m}.${l}.ts (the copy that runs)`, existsSync(f) ? packLiterals(f)[l] : undefined]);
		// the text mirror may go once the two AST readers read the per-language modules (blocked request): while it exists it is pinned too
		if (MIRRORED.has(m) && base[l]) copies.push([l, 'base-module text mirror', base[l]]);
	}
	for (const [l, where, lit] of copies) {
		const want = PACK_GOLDEN[m]?.[l];
		if (!lit) {
			ok(`strings: ${m} ${l} — ${where} present`, false, 'no such object literal');
			continue;
		}
		const d = digest(lit);
		ok(
			`strings: ${m} ${l} — ${where} matches main (${d.count} keys)`,
			!!want && d.count === want[0] && d.sha === want[1] && d.odd === 0,
			want ? `count ${d.count}/${want[0]} sha ${d.sha.slice(0, 12)}/${want[1].slice(0, 12)}${d.odd ? ` · ${d.odd} non-literal members` : ''}` : 'no golden',
		);
	}
	if (!MIRRORED.has(m)) ok(`strings: ${m} base module holds no HI/MR literal (one source of truth)`, !base.hi && !base.mr);
	const en = base.en && entries(base.en).map;
	const hi = existsSync(path.join(I18N, `${m}.hi.ts`)) ? entries(packLiterals(path.join(I18N, `${m}.hi.ts`)).hi).map : new Map();
	const mr = existsSync(path.join(I18N, `${m}.mr.ts`)) ? entries(packLiterals(path.join(I18N, `${m}.mr.ts`)).mr).map : new Map();
	const key = en && [...en.keys()].sort().find((k) => OWNERS.get(k) === 1 && en.get(k).value && hi.get(k)?.value && mr.get(k)?.value && hi.get(k).value !== en.get(k).value && mr.get(k).value !== en.get(k).value);
	if (key) SAMPLE[m] = { key, en: en.get(key).value, hi: hi.get(key).value, mr: mr.get(key).value };
	ok(`strings: ${m} has a sampled key for the loading checks`, !!key, key ?? 'none');
}
for (const m of MIRRORED) {
	const src = readFileSync(path.join(I18N, `${m}.ts`), 'utf8');
	const mirror = /\nconst (hi|mr)\b/.test(src);
	ok(
		`strings: ${m}'s text mirror (if still present) is never registered — astTextMirror declared, never called`,
		!mirror || (/function astTextMirror\(\)/.test(src) && (src.match(/astTextMirror\s*\(/g) ?? []).length === 1 && !/registerPack\('(hi|mr)', (hi|mr)\)/.test(src.replace(/function astTextMirror\(\)[\s\S]*?\n\}/, ''))),
		mirror ? 'mirror present' : 'no mirror',
	);
}
// the samples must be distinct keys across modules so each probes its own module
const sampleKeys = Object.values(SAMPLE).map((s) => s.key);
ok('strings: the 16 sampled keys are distinct (each probes its own module)', new Set(sampleKeys).size === sampleKeys.length && sampleKeys.length === 16, sampleKeys.length + ' keys');

// ── 2. loading on the production path ────────────────────────────────────────

const esbuild = require('esbuild');
const OUT_DIR = process.env.PERF2_UNIT_OUT ?? path.join(os.tmpdir(), 'sajag-perf2-unit');
mkdirSync(OUT_DIR, { recursive: true });
const PROD_DEFINE = { 'process.env.NODE_ENV': '"production"', 'import.meta.env.SSR': 'false', 'import.meta.env.DEV': 'false', 'import.meta.env.PROD': 'true' };
const stubApp = {
	name: 'stub-app',
	setup(b) {
		b.onResolve({ filter: /^\$(app|env)\// }, (a) => ({ path: a.path, namespace: 'stub-app' }));
		b.onLoad({ filter: /.*/, namespace: 'stub-app' }, () => ({ contents: 'export const browser = false, dev = false, building = false; export const goto = async () => {}; export const page = {}; export const navigating = {}; export const env = {};', loader: 'js' }));
	},
};
const IMPORTS = MODULES.map((m) => `import './src/lib/i18n/${m}';`).join('\n');

async function bundle(name, contents, extra = {}) {
	const outfile = path.join(OUT_DIR, `${name}.mjs`);
	const r = await esbuild.build({
		stdin: { contents, resolveDir: DECK, loader: 'ts', sourcefile: `${name}-entry.ts` },
		absWorkingDir: DECK,
		alias: { $lib: './src/lib' },
		bundle: true,
		format: 'esm',
		platform: 'node',
		define: PROD_DEFINE,
		outfile,
		logLevel: 'silent',
		loader: { '.svelte': 'empty' },
		plugins: [stubApp],
		...extra,
	});
	ok(`bundle ${name} builds with the production client defines`, r.errors.length === 0, `${r.errors.length} errors`);
	return outfile;
}
let instance = 0;
const fresh = (file) => import(`${pathToFileURL(file).href}?i=${++instance}`);

// runes as identity macros for the stores (as tests/wall.unit.mjs runs them)
globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });

const covered = (t, lang) => MODULES.filter((m) => SAMPLE[m] && t(lang, SAMPLE[m].key) === SAMPLE[m][lang]);
const missingOf = (t, lang) => MODULES.filter((m) => !SAMPLE[m] || t(lang, SAMPLE[m].key) !== SAMPLE[m][lang]);
const settle = async (cond, ms = 3000) => {
	const end = Date.now() + ms;
	while (!cond() && Date.now() < end) await new Promise((r) => setTimeout(r, 10));
	return cond();
};

const LOADER = await bundle('perf2-loader', `${IMPORTS}\nexport * as L from './src/lib/i18n/load';\nexport { t } from './src/lib/i18n/strings';\n`);
{
	// a. a switch
	delete globalThis.document;
	delete globalThis.window;
	const { L, t } = await fresh(LOADER);
	let bumps = 0;
	L.setPacksRegisteredHook(() => bumps++);
	const preHi = covered(t, 'hi');
	ok('prod path: nothing but EN is registered before any language is asked for (the eager branch folded away)', preHi.length === 0, preHi.join(', ') || 'none in');
	const flight = L.ensureLang('hi');
	const during = MODULES.filter((m) => SAMPLE[m] && t('hi', SAMPLE[m].key) !== SAMPLE[m].en && t('hi', SAMPLE[m].key) !== SAMPLE[m].hi);
	ok('prod path: while the HI chunks are in flight t() answers EN — never a raw key', during.length === 0, during.join(', ') || 'EN fallback everywhere');
	await flight;
	ok('prod path: ensureLang("hi") lands HI for all 16 pack modules', missingOf(t, 'hi').length === 0, missingOf(t, 'hi').join(', ') || '16/16');
	ok('prod path: MR is not fetched by a HI switch', covered(t, 'mr').length === 0, covered(t, 'mr').join(', ') || 'none');
	ok('prod path: every landing fires the re-render signal (setPacksRegisteredHook)', bumps >= 16, `${bumps} signals`);
	await L.ensureLang('mr');
	ok('prod path: ensureLang("mr") lands MR for all 16 pack modules', missingOf(t, 'mr').length === 0, missingOf(t, 'mr').join(', ') || '16/16');
	const before = bumps;
	await L.ensureLang('hi');
	ok('prod path: a repeat call is free (no re-fetch, no extra signal)', bumps === before);
}
{
	// b. the cold path: the document's language, before the modules finish evaluating. Its own CODE-SPLIT build:
	// each language chunk is a separate file, so a chunk that is fetched but not awaited is still out when the
	// import resolves (an in-bundle chunk would land within the same microtask run and hide a missing await)
	const coldDir = path.join(OUT_DIR, 'cold');
	const coldEntry = path.join(OUT_DIR, 'perf2-cold-entry.ts');
	writeFileSync(coldEntry, MODULES.map((m) => `import '${path.join(DECK, 'src/lib/i18n', m)}';`).join('\n') + `\nexport { t } from '${path.join(DECK, 'src/lib/i18n/strings')}';\n`);
	const r = await esbuild.build({ entryPoints: { cold: coldEntry }, absWorkingDir: DECK, alias: { $lib: './src/lib' }, bundle: true, splitting: true, format: 'esm', platform: 'node', define: PROD_DEFINE, outdir: coldDir, outExtension: { '.js': '.mjs' }, logLevel: 'silent', plugins: [stubApp] });
	ok('bundle perf2-cold (code-split: one file per language chunk) builds with the production client defines', r.errors.length === 0, `${r.errors.length} errors`);
	globalThis.window = { addEventListener() {} };
	globalThis.document = { documentElement: { lang: 'mr' }, cookie: '', querySelectorAll: () => [] };
	const { t } = await import(pathToFileURL(path.join(coldDir, 'cold.mjs')).href);
	ok('cold path: <html lang="mr"> → every module\'s MR strings are in when the modules finish evaluating', missingOf(t, 'mr').length === 0, missingOf(t, 'mr').join(', ') || '16/16');
	ok('cold path: only the document\'s language is fetched (no HI)', covered(t, 'hi').length === 0, covered(t, 'hi').join(', ') || 'none');
	delete globalThis.document;
	delete globalThis.window;
}

const STORE = await bundle('perf2-store', `${IMPORTS}\nexport { ops } from './src/lib/ops/store.svelte';\nexport { t } from './src/lib/i18n/strings';\n`);
{
	// c. the ops store's setter alone
	const { ops, t } = await fresh(STORE);
	ok('store: before a switch, no HI module is in', covered(t, 'hi').length === 0);
	ops.lang = 'hi';
	await settle(() => missingOf(t, 'hi').length === 0);
	ok('store: the `lang` setter alone lands HI for all 16 pack modules', missingOf(t, 'hi').length === 0, missingOf(t, 'hi').join(', ') || '16/16');
}
{
	// c. adoptLangCookie() alone
	const { ops, t } = await fresh(STORE);
	globalThis.document = { documentElement: { lang: 'en' }, cookie: 'sajag_lang=mr', querySelectorAll: () => [] };
	ops.adoptLangCookie();
	await settle(() => missingOf(t, 'mr').length === 0);
	ok('store: adoptLangCookie() alone (sajag_lang=mr) lands MR for all 16 pack modules', ops.lang === 'mr' && missingOf(t, 'mr').length === 0, `lang=${ops.lang}; missing ${missingOf(t, 'mr').join(', ') || 'none'}`);
	delete globalThis.document;
}

{
	// d. a real Svelte 5 effect re-runs when the chunk lands
	const { compileModule } = require('svelte/compiler');
	// a virtual client-compiled module: one $effect that reads t()
	const PROBE_SRC = `import { t } from '$lib/i18n/strings';\nexport function watch(lang, key, out) {\n\treturn $effect.root(() => {\n\t\t$effect(() => {\n\t\t\tout.push(t(lang, key));\n\t\t});\n\t});\n}\n`;
	const runes = {
		name: 'svelte-client-runes',
		setup(b) {
			b.onResolve({ filter: /^perf2-probe$/ }, () => ({ path: 'perf2-probe.svelte.js', namespace: 'perf2-probe' }));
			b.onLoad({ filter: /.*/, namespace: 'perf2-probe' }, () => ({ contents: compileModule(PROBE_SRC, { filename: 'perf2-probe.svelte.js', generate: 'client', dev: false }).js.code, loader: 'js', resolveDir: DECK }));
			b.onLoad({ filter: /\.svelte\.(ts|js)$/ }, async (a) => {
				const src = readFileSync(a.path, 'utf8');
				const plain = a.path.endsWith('.ts') ? (await esbuild.transform(src, { loader: 'ts' })).code : src;
				return { contents: compileModule(plain, { filename: a.path, generate: 'client', dev: false }).js.code, loader: 'js', resolveDir: path.dirname(a.path) };
			});
		},
	};
	let R = null;
	try {
		const file = await bundle(
			'perf2-runes',
			`${IMPORTS}\nimport './src/lib/i18n/pack-registry.svelte';\nexport { watch } from 'perf2-probe';\nexport { ensureLang } from './src/lib/i18n/load';\nexport { flushSync } from 'svelte';\n`,
			{ plugins: [stubApp, runes], conditions: ['svelte', 'browser'] },
		);
		R = await fresh(file);
	} catch (e) {
		ok('runes: the client-compiled probe loads', false, String(e?.message ?? e).slice(0, 300));
	}
	if (R) {
		const s = SAMPLE['packs.wall'];
		const seen = [];
		const stop = R.watch('hi', s.key, seen);
		R.flushSync();
		await R.ensureLang('hi');
		R.flushSync();
		stop();
		ok('runes: a $effect reading t() ran first with EN (never the raw key) and re-ran with HI once the chunk landed', seen[0] === s.en && seen.at(-1) === s.hi, JSON.stringify(seen.map((x) => x.slice(0, 24))));
	}
}

// ── 3. icons ──────────────────────────────────────────────────────────────────

const DESIGN = path.join(DECK, 'src/lib/design');
const ICONS = await bundle('perf2-icons', `export * as I from './src/lib/design/icons';\nexport * as C from './src/lib/design/icons-core';\n`);
{
	delete globalThis.document;
	delete globalThis.window;
	const { I, C } = await fresh(ICONS);
	const names16 = Object.keys(I.ICONS_16);
	const pathsSha = (tbl) => createHash('sha256').update(Object.entries(tbl).map(([n, p]) => `${n}\u0000${(p ?? []).join('\u0001')}`).join('\n')).digest('hex');
	ok('icons: ICONS_16 is complete, frozen and in main\'s order with main\'s path data', names16.length === ICON_GOLDEN.n16 && Object.isFrozen(I.ICONS_16) && createHash('sha256').update(names16.join('\n')).digest('hex') === ICON_GOLDEN.order16 && pathsSha(I.ICONS_16) === ICON_GOLDEN.paths16, `${names16.length} names`);
	ok('icons: ICONS_20 is complete, frozen, with main\'s path data', Object.keys(I.ICONS_20).length === ICON_GOLDEN.n20 && Object.isFrozen(I.ICONS_20) && pathsSha(I.ICONS_20) === ICON_GOLDEN.paths20, `${Object.keys(I.ICONS_20).length} names`);
	ok('icons: ICON_NAMES is the full set in table order', C.ICON_NAMES.length === names16.length && C.ICON_NAMES.every((n, i) => n === names16[i]));
	const core = new Set(Object.keys(C.CORE_16));
	const deferred = names16.filter((n) => !core.has(n));
	ok('icons (prod): isIconName knows every name before anything loads, and rejects others', names16.every((n) => I.isIconName(n)) && !I.isIconName('person') && !I.isIconName('') && !I.isIconName(42), `${names16.length} names, ${deferred.length} deferred`);
	ok('icons (prod): a first-paint glyph draws at once; a deferred one has no paths until its half lands', [...core].every((n) => I.iconPaths(n, 16).paths.length > 0) && deferred.length > 0 && deferred.every((n) => I.iconPaths(n, 16).paths.length === 0 && !I.iconReady(n)));
	ok('icons (prod): nothing has asked for the deferred half yet', I.restIconsInFlight() === null && !I.restIconsLoaded());
	await I.loadRestIcons();
	const bad = names16.filter((n) => {
		const p16 = I.iconPaths(n, 16);
		const p20 = I.iconPaths(n, 20);
		return p16.paths.length === 0 || p16.paths !== I.ICONS_16[n] || p20.grid !== (I.ICONS_20[n] ? 20 : 16) || p20.paths !== (I.ICONS_20[n] ?? I.ICONS_16[n]);
	});
	ok('icons (prod): after loadRestIcons() EVERY name resolves at 16 and 20 px to main\'s drawing', bad.length === 0, bad.slice(0, 6).join(', ') || `${names16.length}/${names16.length}`);
	const pinned = new Set([...Object.values(C.FIRST_PAINT_ICONS).flat(), ...C.MAP_GLYPHS, ...C.CANVAS_PANEL_ICONS]);
	ok('icons: the first-paint half is EXACTLY the pinned first-viewport sets + the map-marker glyphs + the canvas panels\' glyphs', pinned.size === core.size && [...pinned].every((n) => core.has(n)), `${core.size} glyphs`);
	const coreHas20 = Object.keys(C.CORE_20).every((n) => core.has(n)) && [...core].every((n) => !I.ICONS_20[n] || C.CORE_20[n]);
	ok('icons: a first-paint glyph carries its 20 px drawing too (no scaled stand-in until the rest lands)', coreHas20);
	const mapNeed = [...new Set([...Object.values(I.KIND_ICON), ...Object.values(I.EVENT_KIND_ICON), 'dot', 'lock'])];
	ok('icons: every glyph a map marker can draw is first-paint (a canvas billboard cannot redraw itself)', mapNeed.every((n) => C.MAP_GLYPHS.includes(n) && core.has(n)), mapNeed.filter((n) => !core.has(n)).join(', ') || `${mapNeed.length} glyphs`);
}

// the server render of the three routes: every glyph drawn must be first-paint and pinned for that route
{
	const SERVER = path.join(DECK, '.svelte-kit/output/server/index.js');
	const MANIFEST = path.join(DECK, '.svelte-kit/output/server/manifest.js');
	if (!existsSync(SERVER) || !existsSync(MANIFEST)) {
		console.log('skip icons: server-render pin — no production build (.svelte-kit/output/server); `sem.sh deck-build 2 npm run build:cpu` then re-run');
	} else {
		// nothing the render does may reach a backend: point every upstream at the discard port
		for (const k of ['ORACLE_PORT', 'BRAIN_PORT', 'EMULATOR_PORT']) process.env[k] = '9';
		for (const k of ['SAJAG_OPERATOR_PIN', 'SAJAG_OPERATOR_PIN_FILE', 'SAJAG_SESSION_SECRET', 'SAJAG_CESIUM_ION_TOKEN']) delete process.env[k];
		globalThis.crypto ??= (await import('node:crypto')).webcrypto; // node 18: what adapter-node's shims install
		const { Server } = await import(pathToFileURL(SERVER).href);
		const { manifest } = await import(pathToFileURL(MANIFEST).href);
		const server = new Server(manifest);
		await server.init({ env: process.env });
		const C = await import(`${pathToFileURL(path.join(OUT_DIR, 'perf2-icons.mjs')).href}?i=${++instance}`).then((m) => m.C);
		const core = new Set(Object.keys(C.CORE_16));
		// FIRST_PAINT_ICONS is keyed by the LOGICAL route ('/' is the workspace's pinned set); the URL it is served at is WORKSPACE
		const pinKey = (route) => (route === WORKSPACE ? '/' : route);
		for (const route of [WORKSPACE, '/ops', '/gods-eye']) {
			const drawn = new Set();
			for (const lang of LANGS) {
				const res = await server.respond(new Request(`http://127.0.0.1${route}`, { headers: { cookie: `sajag_lang=${lang}` } }), { getClientAddress: () => '127.0.0.1' });
				const html = await res.text();
				for (const m of html.matchAll(/data-icon="([a-z0-9-]+)"/g)) drawn.add(m[1]);
			}
			const notCore = [...drawn].filter((n) => !core.has(n));
			const notPinned = [...drawn].filter((n) => !C.FIRST_PAINT_ICONS[pinKey(route)].includes(n));
			ok(`icons: the server render of ${route} (EN/HI/MR) draws only first-paint glyphs pinned for the route`, drawn.size > 0 && notCore.length === 0 && notPinned.length === 0, `${drawn.size} glyphs${notCore.length ? `; not first-paint: ${notCore.join(', ')}` : ''}${notPinned.length ? `; not pinned: ${notPinned.join(', ')}` : ''}`);
		}
	}
}

if (failures) {
	console.error(`\n${failures} check(s) failed`);
	process.exit(1);
}
console.log('\nok   perf2 — every pack copy matches main, every language lands on the production path for all 16 modules, and the icon set is whole');
process.exit(0);
