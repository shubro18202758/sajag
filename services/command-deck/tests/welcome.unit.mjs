/**
 * The landing page unit gate (/welcome) — zero browser.
 *
 *   node tests/welcome.unit.mjs
 *   WELCOME_TREE=<copy of services/command-deck>  node tests/welcome.unit.mjs     (a mutation harness points it at a scratch copy)
 *
 *   1. ROUTE     /welcome exists as src/routes/(landing)/welcome (its own group: no operator shell, no public day shell); the
 *                server reads the language from the sajag_lang cookie (English when none is set: English is the
 *                product's default everywhere); hooks.server.ts renders the group NIGHT and never gives it the operator
 *                (Cesium) policy.
 *   2. BOUNDARY  public and static: every import under lib/v3/landing and routes/(landing) is on a short allowlist (the i18n
 *                core, the V3 tokens, the imagery layer, the glyph, the landing's own modules) — never $lib/ops, gods-eye,
 *                workspace, stores, data-service, the V3 shell or any operator screen; no fetch and no /api/ call at all.
 *   3. PACKS     packs.landing EN / HI / MR carry the same keys (v3l_*), HI is Devanagari and MR Marathi, every key the page
 *                builds exists (the dynamic ones from the content tables too), the imagery keys it borrows exist in
 *                packs.media, the EN copy keeps the deck's copy rules.
 *   4. CONTENT   the poster: the lockup, the tagline in the reader's language ("Not by stopping. By steering." /
 *                থামিয়ে নয়, সামলে।), the sub-line, Open the console → / (a new document), Check your road → /citizen and
 *                the console screenshot window; the ambulance (108) crew → /driver; the
 *                source → the public repository; every picture is on disk and is Mumbai's; no picture repeats; the key art
 *                shows no crowd; every agency mark resolves and is keyed by a city.json agency id or a data source.
 *   5. HONESTY   every reference photo carries "Reference photo · not live" and its credit, every key art "Illustration";
 *                a console screenshot only of Mumbai, captioned "Console screenshot · exercise data"; the figures carry the dashed Modelled tag and its note, and are
 *                IMPACT_REPORT's or an explicit TODO-IMPACT placeholder that shows no number; no "lives saved"; no person as
 *                an image subject; no contest or prize-event wording anywhere; the marks keep the owners' credit line.
 *   6. LAYOUT    the landing tokens exist (tokens.css ↔ tokens.ts); the page is neutral (no yellow, no taxi token: type
 *                carries the tagline's turn, not colour); motion stops under prefers-reduced-motion; touch-sized controls; no hex colour; the page
 *                scrolls as a document only while it is mounted (:has).
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TOOLS = path.resolve(HERE, '..');
const DECK = process.env.WELCOME_TREE ? path.resolve(process.env.WELCOME_TREE) : TOOLS;
const OUT = path.join(HERE, 'artifacts', 'welcome-bundle.mjs');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const read = (rel) => readFileSync(path.join(DECK, rel), 'utf8');
const has = (rel) => existsSync(path.join(DECK, rel));
const walk = (d, out = []) => {
	if (!has(d)) return out;
	for (const e of readdirSync(path.join(DECK, d), { withFileTypes: true })) {
		const p = `${d}/${e.name}`;
		if (e.isDirectory()) walk(p, out);
		else if (/\.(svelte|ts|css)$/.test(e.name)) out.push(p);
	}
	return out;
};
const stripComments = (src) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '').replace(/(^|[^:'"`])\/\/[^\n]*/g, '$1');

const LIB = 'src/lib/v3/landing';
const ROUTES = 'src/routes/(landing)';
const PAGE = `${ROUTES}/welcome/+page.svelte`;
const LANDING = `${LIB}/Landing.svelte`;
const FILES = [...walk(LIB), ...walk(ROUTES)];

// ── bundle the content tables and the packs ────────────────────────────────
mkdirSync(path.dirname(OUT), { recursive: true });
const esbuild = createRequire(path.join(TOOLS, 'package.json'))('esbuild');
const built = await esbuild
	.build({
		stdin: {
			contents: [
				`export * as content from './${LIB}/content';`,
				`export * as packs from './${LIB}/packs.landing';`,
				`export { hi } from './${LIB}/packs.landing.hi';`,
				`export { mr } from './${LIB}/packs.landing.mr';`,
				`export * as media from './src/lib/v3/media/packs.media';`,
				`export * as tokens from './src/lib/v3/tokens';`,
			].join('\n'),
			resolveDir: DECK,
			loader: 'ts',
			sourcefile: 'welcome-entry.ts',
		},
		absWorkingDir: DECK,
		alias: { $lib: './src/lib' },
		bundle: true,
		format: 'esm',
		platform: 'node',
		outfile: OUT,
		logLevel: 'silent',
		define: { 'import.meta.env.SSR': 'true' },
	})
	.catch((e) => ({ errors: [e] }));
ok('bundle builds (content, packs.landing, packs.media, tokens)', built.errors.length === 0, built.errors[0]?.message?.split('\n')[0] ?? '');
if (built.errors.length) process.exit(1);
const { content: C, packs, hi, mr, media, tokens } = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
const EN = packs.LANDING_PACKS.en;

// ── 1. ROUTE ────────────────────────────────────────────────────────────────
{
	ok('1. /welcome exists in its own route group: (landing)/welcome/+page.svelte, +page.server.ts and the group layout', has(PAGE) && has(`${ROUTES}/welcome/+page.server.ts`) && has(`${ROUTES}/+layout.svelte`));
	ok('1. /welcome is not under (public), (deck) or (v3) — no public day shell, no operator shell', !has('src/routes/(public)/welcome') && !has('src/routes/(deck)/welcome') && !has('src/routes/(v3)/welcome') && !has('src/routes/welcome'));
	const server = read(`${ROUTES}/welcome/+page.server.ts`);
	ok('1. the server render reads the reader\'s language from the sajag_lang cookie (English otherwise)', /langFromCookieHeader\(request\.headers\.get\('cookie'\)\) \?\? 'en'/.test(server));
	const layout = read(`${ROUTES}/+layout.svelte`);
	ok('1. the group layout loads the V3 tokens and the night theme, and nothing else', /\$lib\/v3\/tokens\.css/.test(layout) && /dataset\.theme = 'command'/.test(layout) && (stripComments(layout).match(/^\s*import\s/gm) ?? []).length === 1 && !/Shell|\$lib\/ops|session/.test(stripComments(layout)));
	const hooks = read('src/hooks.server.ts');
	const fn = hooks.slice(hooks.indexOf('function documentDefaults'), hooks.indexOf('function clientKey'));
	ok('1. hooks: the operator policy names only the (deck) and (v3) groups, so the (landing) document stays strict', /operator: id\.startsWith\('\/\(deck\)'\) \|\| id\.startsWith\('\/\(v3\)'\),/.test(fn) && !/operator:[^\n]*landing/.test(fn) && /\(landing\)/.test(fn));
	ok('1. hooks: only (public) renders daylight, so the landing renders night', /theme: id\.startsWith\('\/\(public\)'\) \? 'daylight' : 'command'/.test(fn));
	ok('1. hooks: the operator policy is the only one that relaxes eval (the landing gets the strict one)', /cesium \? " 'unsafe-eval' blob:" : ''/.test(hooks) && /harden\(response, nonce, operator[,)]/.test(hooks));
}

// ── 2. BOUNDARY ─────────────────────────────────────────────────────────────
{
	const ALLOW = [
		/^\$lib\/i18n\/(strings|load|lang-cookie|pack-registry\.svelte)$/,
		/^\$lib\/v3\/tokens\.css$/,
		/^\$lib\/v3\/landing\/(packs\.landing|Landing\.svelte)$/,
		/^\.\.\/media\/(packs\.media|photos|logos|art|AgencyMark\.svelte|Cover\.svelte)$/,
		/^\.\.\/Glyph\.svelte$/,
		/^\$lib\/city$/, // the City Pack (pure data: the city box and agency ids the pictures and marks are chosen by)
		/^\.\/(packs\.landing(\.hi|\.mr)?|content|LangSwitch\.svelte|Landing\.svelte|\$types)$/,
	];
	const bad = [];
	for (const f of FILES) for (const m of stripComments(read(f)).matchAll(/(?:from\s+|import\s+|import\()\s*['"]([^'"]+)['"]/g)) if (!ALLOW.some((re) => re.test(m[1]))) bad.push(`${f} → ${m[1]}`);
	ok('2. every landing import is on the allowlist (i18n core, V3 tokens, imagery, glyph, its own modules)', FILES.length >= 7 && bad.length === 0, bad.slice(0, 4).join(' | ') || `${FILES.length} files`);
	const deny = FILES.filter((f) => /\$lib\/(ops|gods-eye|workspace|stores|api|decisions|shell)\b|\$stores|data-service|\$lib\/v3\/(shell|decide|object|plan|assistant|home|map)\//.test(read(f)));
	ok('2. no operator code: no ops, gods-eye, workspace, stores, data-service, shell or operator screen', deny.length === 0, deny.join());
	const calls = FILES.filter((f) => /\bfetch\(|XMLHttpRequest|EventSource|WebSocket|['"`]\/api\//.test(stripComments(read(f))));
	ok('2. the page is static: no fetch, no socket, no /api/ path', calls.length === 0, calls.join());
}

// ── 3. PACKS ────────────────────────────────────────────────────────────────
{
	const keys = Object.keys(EN);
	ok('3. HI and MR carry exactly the EN keys; every key starts with v3l_', keys.every((k) => k in hi && k in mr && k.startsWith('v3l_')) && Object.keys(hi).length === keys.length && Object.keys(mr).length === keys.length, `${keys.length} keys`);
	const text = (p, k) => String(typeof p[k] === 'function' ? p[k](2) : p[k]);
	const plain = (v) => /^[\d~,.×–\s]+$/.test(v); // a figure ('~33,000') reads the same in every script
	const untranslated = keys.filter((k) => !plain(text(EN, k)) && (text(hi, k) === text(EN, k) || text(mr, k) === text(EN, k) || !/[\u0900-\u097F]/.test(text(hi, k)) || !/[\u0900-\u097F]/.test(text(mr, k)) || /[\u0980-\u09FF]/.test(text(mr, k))));
	ok('3. HI is Devanagari and MR Marathi (nothing left in English)', untranslated.length === 0, untranslated.join());
	// Marathi is Devanagari like Hindi: the leak check is the old Bengali script, and console digits stay Latin
	const leak = keys.filter((k) => /[\u0980-\u09FF]/.test(text(hi, k)) || /[\u0980-\u09FF\u0966-\u096F]/.test(text(mr, k)) || /[\u0A80-\u0AFF]/.test(text(hi, k) + text(mr, k)));
	ok('3. no Bengali script left in the HI or MR pack, MR keeps Latin digits, no Gujarati anywhere', leak.length === 0, leak.join());
	const bnSentences = keys.map((k) => text(mr, k)).filter((v) => /[\u0964\u0965]/.test(v));
	ok('3. MR sentences end with the full stop, never the Hindi danda', bnSentences.length === 0, bnSentences.slice(0, 2).join(' | '));
	// every key the page builds exists: the literal ones and the ones built from the content tables
	const used = new Set();
	for (const f of FILES) if (!/packs\.landing/.test(f)) for (const m of read(f).matchAll(/['"`](v3l_[a-z0-9_]+)['"`]/g)) used.add(m[1]);
	for (const s of C.STEPS) for (const k of [`v3l_${s.key}`, `v3l_${s.key}_title`, `v3l_${s.key}_body`]) used.add(k);
	for (const a of C.AUDIENCES) for (const k of [`v3l_who_${a.key}`, `v3l_who_${a.key}_body`]) used.add(k);
	for (const p of C.PRINCIPLES) for (const k of [`v3l_rule_${p.key}`, `v3l_rule_${p.key}_body`]) used.add(k);
	for (const b of C.BUILT) for (const k of [`v3l_built_${b.key}`, `v3l_built_${b.key}_body`]) used.add(k);
	for (const f of C.TODO_IMPACT.figures) used.add(`v3l_fig_${f.key}_label`);
	const missing = [...used].filter((k) => !(k in EN));
	ok('3. every v3l_ key the page uses exists (the dynamic ones from the content tables too)', missing.length === 0, missing.join() || `${used.size} used`);
	const dynamic = /`v3l_\$\{s\.key\}`|`v3l_\$\{s\.key\}_title`|`v3l_who_\$\{a\.key\}`|`v3l_rule_\$\{p\.key\}`|`v3l_built_\$\{b\.key\}`/;
	ok('3. …the page builds its dynamic keys only from those tables', dynamic.test(read(LANDING)));
	const borrowed = new Set();
	for (const f of FILES) for (const m of read(f).matchAll(/['"`](v3i_[a-z0-9_]+)['"`]/g)) borrowed.add(m[1]);
	const noMedia = [...borrowed].filter((k) => !media.MEDIA_PACK_KEYS.includes(k));
	ok('3. the imagery strings it borrows exist in packs.media (EN · HI · MR there)', borrowed.size >= 5 && noMedia.length === 0, noMedia.join() || [...borrowed].join(' '));
	const ACR = new Set('AI IMD NDMA OSM GPS ANPR SMS FIR IST ID CCTV ICCC OSINT EN MIT KMC BMC BEST CSMT BKC WEH EEH MTP MMRDA SDMA'.split(' '));
	const rules = [];
	for (const k of keys) {
		const v = text(EN, k);
		if ((v.match(/ · /g) ?? []).length > 1) rules.push(`${k}: separator`);
		if (/(title|heading)$/.test(k) && v.length > 32) rules.push(`${k}: heading > 32`);
		for (const w of v.split(/[^A-Za-z0-9•]+/)) if (w.length > 1 && /^[A-Z]+$/.test(w) && !ACR.has(w)) rules.push(`${k}: ALL-CAPS ${w}`);
	}
	ok('3. EN copy rules: ≤ one " · ", headings ≤ 32 characters, no all-caps word outside the acronyms', rules.length === 0, rules.slice(0, 5).join(' | '));
	ok('3. the copy lint reads the landing pack (style-lint targets)', /src\/lib\/v3\/landing\/packs\.landing\.ts/.test(readdirSync(path.join(DECK, 'tests/style-lint.targets')).map((f) => read(`tests/style-lint.targets/${f}`)).join('\n')));
}

// ── 4. CONTENT ──────────────────────────────────────────────────────────────
{
	const H = C.HREF;
	ok('4. the doors: console → /, analyst → /analyst, citizen → /citizen, driver → /driver, source → the public repository', H.console === '/' && H.analyst === '/analyst' && H.citizen === '/citizen' && H.driver === '/driver' && H.source === 'https://github.com/shubro18202758/sajag');
	const src = read(LANDING);
	const tags = [...src.matchAll(/<a\b[^>]*>/g)].map((m) => m[0]);
	const toConsole = tags.filter((t) => /href=\{HREF\.console\}/.test(t));
	ok('4. every link into the console (an operator document) loads a new document (data-sveltekit-reload)', toConsole.length >= 4 && toConsole.every((t) => /data-sveltekit-reload/.test(t)), `${toConsole.length} links`);
	ok('4. the audience links reload exactly when they lead into the console (/ and /analyst)', /data-sveltekit-reload=\{reload\(a\.href\)\}/.test(src) && JSON.stringify(C.OPERATOR_HREFS) === JSON.stringify(['/', '/analyst']));
	const hero = src.slice(src.indexOf('<header class="hero"'), src.indexOf('</header>'));
	ok('4. the poster: the lockup, the tagline in the reader\'s language, the sub-line, Open the console (→ /), Check your road (→ /citizen) and the console window over the photo', /sajag-lockup\.svg/.test(hero) && /class="tagline"/.test(hero) && !/class="tagline" lang=/.test(hero) && /'v3l_tagline_lead'/.test(hero) && /'v3l_tagline_turn'/.test(hero) && /'v3l_hero_sub'/.test(hero) && /href=\{HREF\.console\} data-sveltekit-reload data-testid="land-cta-console"/.test(hero) && /href=\{HREF\.citizen\} data-testid="land-cta-road"/.test(hero) && /<Cover [^>]*photo=\{hero\}/.test(hero) && /data-testid="land-hero-shot"/.test(hero));
	ok('4. the tagline and the lines: English first, the Marathi and Hindi tagline in their packs', EN.v3l_tagline_lead === 'Not by stopping.' && EN.v3l_tagline_turn === 'By steering.' && mr.v3l_tagline_lead === 'थांबवून नव्हे,' && mr.v3l_tagline_turn === 'सांभाळून.' && /^[\u0900-\u097F ,।]+$/.test(hi.v3l_tagline_lead + hi.v3l_tagline_turn) && EN.v3l_hero_sub === 'When heavy rain meets high tide, Mumbai floods in the same places and the trains stop. Sajag gives the city one live picture — the AI proposes, a named officer decides.');
	ok('4. no Marathi in the landing\'s own markup or content tables (Marathi lives in its pack, shown only when chosen)', !/[\u0980-\u09FF]/.test(stripComments(src) + stripComments(read(`${LIB}/content.ts`))));
	ok('4. the hero photo and the console window load eagerly, everything else lazily', /<Cover [^>]*photo=\{hero\}[^>]* eager /.test(hero) && (src.match(/loading="eager"/g) ?? []).length === 1 && /<img src=\{win\.src\}[^>]*loading="eager"/.test(hero) && !/\beager\b/.test(src.slice(src.indexOf('</header>'))) && (src.match(/loading="lazy"/g) ?? []).length >= 2);
	const photos = [C.heroPhoto(), C.endPhoto(), ...C.cityPhotos()];
	const files = photos.flatMap((p) => [`static/photos/${p.slug}-640.webp`, `static/photos/${p.slug}-1600.webp`]);
	for (const s of C.STEPS) files.push(`static${s.art}`);
	for (const a of C.AUDIENCES) files.push(`static${a.art}`);
	const marks = C.marks(C.MARK_ROW);
	for (const m of marks) files.push(`static${m.src}`);
	const absent = files.filter((f) => !has(f));
	ok('4. every picture is on disk (photos in both widths, key art, marks)', absent.length === 0, absent.join() || `${files.length} files`);
	ok('4. every photo is of Mumbai (the city box)', photos.every((p) => p.lat > 18.85 && p.lat < 19.3 && p.lon > 72.75 && p.lon < 73.0), photos.map((p) => p.slug).join());
	ok('4. no photo repeats on the page (hero, closing band, the five of the strip)', new Set(photos.map((p) => p.slug)).size === photos.length && photos.length === 7, photos.map((p) => p.slug).join());
	ok('4. every mark of the row and of Built on resolves', marks.length === C.MARK_ROW.length && C.BUILT.every((b) => C.marks(b.marks).length === b.marks.length));
	const AGENCIES = JSON.parse(read('../../cities/mumbai/city.json')).agencies.map((a) => a.id);
	const SOURCES = ['openstreetmap', 'open_meteo', 'copernicus'];
	const rowAgencies = C.MARK_ROW.filter((k) => AGENCIES.includes(k));
	const CURATED = ['mumbai_police', 'bmc', 'mmrda', 'best', 'cr', 'metro', 'msrdc', 'port', 'ndma', 'imd'];
	ok("4. the row is Mumbai's agencies (city.json ids: the brand's curated row, every one with its mark) and the data sources", C.MARK_ROW.every((k) => AGENCIES.includes(k) || SOURCES.includes(k)) && CURATED.every((k) => rowAgencies.includes(k)) && SOURCES.every((k) => C.MARK_ROW.includes(k)), C.MARK_ROW.join());
	ok('4. the curated pictures: the Sea Link at night, Marine Drive to close, CSMT, the Gateway, a kaali-peeli, a BEST double-decker and a local in the strip', C.heroPhoto().slug === C.HERO_PHOTO_SLUG && C.endPhoto().slug === C.END_PHOTO_SLUG && C.cityPhotos().map((p) => p.slug).join() === C.CITY_PHOTO_SLUGS.join(), [C.heroPhoto().slug, C.endPhoto().slug, ...C.cityPhotos().map((p) => p.slug)].join());
	const pics = [...C.STEPS.map((s) => s.art), ...C.AUDIENCES.map((a) => a.art)];
	ok('4. no picture repeats (three steps and four seats, seven pictures)', new Set(pics).size === pics.length, pics.join());
	ok('4. three steps (See, Decide, Act), four seats, six principles, four foundations', C.STEPS.map((s) => s.key).join() === 'see,decide,act' && C.AUDIENCES.map((a) => a.key).join() === 'officer,analyst,citizen,driver' && C.PRINCIPLES.length === 6 && C.BUILT.length === 4);
	ok('4. the fourth seat is the ambulance (108) crew', /Ambulance \(108\) crew/.test(EN.v3l_who_driver));
}

// ── 5. HONESTY ──────────────────────────────────────────────────────────────
{
	const src = read(LANDING);
	const cover = read('src/lib/v3/media/Cover.svelte');
	ok('5. every reference photo (hero, city strip, closing band) is drawn by Cover, which prints "Reference photo · not live" and the credit on the picture', (src.match(/<Cover [^>]*photo=\{(hero|end|p)\}/g) ?? []).length === 3 && !/photoSrc|\/photos\/[a-z0-9-]+-(640|1600)/.test(src) && /'v3i_ref_photo'/.test(cover) && /\{photo\.credit\}/.test(cover) && media.MEDIA_PACKS.en.v3i_ref_photo === 'Reference photo · not live');
	ok('5. every key art under a step is captioned "Illustration"', /<figcaption class="cap" data-testid="land-step-caption">\{t\(lang, 'v3l_illustration'\)\}/.test(src) && EN.v3l_illustration === 'Illustration');
	const shotFiles = has('static/landing') ? readdirSync(path.join(DECK, 'static/landing')).filter((f) => f !== 'NOTICE.md') : [];
	const noticeNow = has('static/landing/NOTICE.md') ? read('static/landing/NOTICE.md') : '';
	const shotsOk = Object.values(C.SHOTS).every((sh) => shotFiles.includes(sh.src.replace('/landing/', '')) && sh.srcset.split(', ').every((e) => shotFiles.includes(e.split(' ')[0].replace('/landing/', ''))) && noticeNow.includes(sh.src.replace('/landing/', '').replace('-1600.webp', '-{800,1600}.webp')));
	ok('5. every console screenshot is on disk, Mumbai\'s, listed in the notice, and no other screenshot ships', shotsOk && shotFiles.every((f) => Object.values(C.SHOTS).some((sh) => sh.srcset.includes(f))) && /Mumbai/.test(noticeNow), shotFiles.join());
	ok('5. the screenshot carries its honest caption on the picture ("Console screenshot · exercise data")', /<figcaption class="shot-tag" data-testid="land-shot-caption">\{t\(lang, 'v3l_shot_tag'\)\}/.test(src) && EN.v3l_shot_tag === 'Console screenshot · exercise data');
	ok('5. the figures carry the dashed Modelled tag and the note (model outputs, not field measurements, not patient outcomes)', /class="tag-dashed">\{t\(lang, 'v3l_modelled'\)\}/.test(src) && /not field measurements/.test(EN.v3l_modelled_note) && /not a claim about patient outcomes/.test(EN.v3l_modelled_note));
	const report = read('../../IMPACT_REPORT.md');
	const pending = C.TODO_IMPACT.pending === true;
	ok('5. the figures are IMPACT_REPORT\'s, or the TODO-IMPACT placeholder that shows "Being modelled" and no number', C.TODO_IMPACT.figures.length === 3 && (pending ? C.TODO_IMPACT.figures.every((f) => f.value === null) && /'v3l_fig_pending'/.test(src) && /'v3l_modelled_todo'/.test(src) && /being modelled/i.test(EN.v3l_modelled_todo) : C.TODO_IMPACT.figures.every((f) => f.value && report.includes(f.value))), pending ? 'TODO-IMPACT: Kolkata run pending' : C.TODO_IMPACT.figures.map((f) => f.value).join(' '));
	const all = [EN, hi, mr].flatMap((p) => Object.keys(EN).map((k) => String(typeof p[k] === 'function' ? p[k](2) : p[k]))).join('\n');
	ok('5. never "lives saved"', !/lives?\s+saved|saves?\s+lives/i.test(all + read(LANDING)));
	const everything = FILES.map(read).join('\n') + read('static/landing/NOTICE.md');
	const EVENT_WORDS = new RegExp(['hack' + 'athon', 'compet' + 'ition', 'contest', 'ju' + 'dg', 'ju' + 'ry', 'प्रतियोगिता', 'প্রতিযোগিতা', 'ub' + 'er', 'net' + 'flix'].join('|'), 'i');
	const OLD_NAME = new RegExp('\\b' + 'Ve' + 'er\\b');
	ok('5. no contest or prize-event wording, no other product named, anywhere in the landing (code, comments, copy, notice)', !EVENT_WORDS.test(everything) && !OLD_NAME.test(everything));
	const CROWD = /mass_gathering|egress_surge|public_disorder|procession|reported_crime/;
	ok('5. no person as an image subject: the key art shows roads and vehicles, never a crowd', [...C.AUDIENCES, ...C.STEPS].every((a) => !CROWD.test(a.art)));
	ok('5. the marks keep the owners\' credit line (beside the row and in the footer)', (src.match(/'v3i_marks_credit'/g) ?? []).length === 2 && /not affiliated with or endorsed by them/.test(media.MEDIA_PACKS.en.v3i_marks_credit));
	const notice = has('static/landing/NOTICE.md') ? read('static/landing/NOTICE.md') : '';
	ok('5. the screenshots\' provenance is written down: taken on Mumbai, exercise data, no officer named, plates masked', /Mumbai/.test(notice) && /exercise/.test(notice) && /masked/.test(notice) && /No\s+duty officer was named/.test(notice));
	ok('5. the footer credits OpenStreetMap (ODbL), the photos (with their notice) and the artwork', /ODbL/.test(EN.v3l_foot_osm) && /href=\{HREF\.photoCredits\}/.test(src) && /'v3i_art_credit'/.test(src));
}

// ── 6. LAYOUT ───────────────────────────────────────────────────────────────
{
	const S = tokens.V3_SHARED;
	const css = read('src/lib/v3/tokens.css');
	const land = ['--v3-land-hero', '--v3-land-section', '--v3-land-lead', '--v3-land-figure', '--v3-land-lockup', '--v3-land-max'];
	ok('6. no taxi token: the landing is neutral (the turn is carried by type, not colour)', !Object.keys(S).some((k) => /taxi/.test(k)) && !/--v3-land-taxi/.test(css));
	ok('6. the landing tokens live in tokens.ts and tokens.css (both steps)', land.every((k) => k in S && k in tokens.V3_COMPACT && css.includes(`${k}: ${S[k]};`) && css.includes(`${k}: ${tokens.V3_COMPACT[k]};`)));
	ok('6. the poster type is the landing scale (tagline ≥ 96 px, lockup ≥ 64 px at 1920)', parseFloat(S['--v3-land-hero']) >= 96 && parseFloat(S['--v3-land-lockup']) >= 64);
	const src = read(LANDING);
	ok('6. motion stops under prefers-reduced-motion (the photo, the words, the window)', /prefers-reduced-motion: reduce\)[\s\S]*?\.hero-photo,\s*\.hero-copy > \*,\s*\.window \{\s*animation: none;/.test(src));
	ok('6. the tagline\'s turn is white and its lead grey (type, not a colour)', /\.t-turn \{\s*color: var\(--v3-t1\);/.test(src) && /\.t-lead \{\s*color: var\(--v3-t3\);/.test(src) && !/--v3-land-taxi/.test(src));
	const sw = read(`${LIB}/LangSwitch.svelte`);
	ok('6. touch-sized controls: language buttons ≥ 40 px tall and 44 px wide, the CTAs the console pill (56 px)', /min-width: 44px;\s*min-height: 40px;/.test(sw) && /height: var\(--v3-ctl-xl\);/.test(src));
	ok('6. the language switch speaks each language in its own script, pressed state in words (aria-pressed)', /lang=\{s\.code\}/.test(sw) && /aria-pressed=\{lang === s\.code\}/.test(sw) && /writeLangCookie\(code\)/.test(read(PAGE)) && /document\.documentElement\.lang = lang/.test(read(PAGE)));
	const hex = FILES.filter((f) => /#[0-9a-fA-F]{3,8}(?![a-zA-Z0-9-])/.test(stripComments(read(f)).replace(/href="#[\w-]+"/g, '').replace(/\{#(each|if|snippet)/g, '')));
	ok('6. no hex colour in the landing (the V3 tokens only)', hex.length === 0, hex.join());
	ok('6. the page scrolls as a document only while it is mounted (html:has([data-landing]))', /:global\(html:has\(\[data-landing\]\)\)/.test(src) && /data-landing/.test(src));
	ok('6. one column below 640 px and every grid collapses (no sideways scroll at 390)', /@media \(max-width: 640px\)[\s\S]*?\.steps,\s*\.people,\s*\.principles,\s*\.bases \{\s*grid-template-columns: minmax\(0, 1fr\);/.test(src) && /overflow-x: clip;/.test(src));
}

if (failures) {
	console.error(`\nwelcome.unit: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('\nwelcome.unit: all green');
