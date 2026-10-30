/**
 * FIX-E-PERF2 production smoke (round 2): what the per-language packs and the
 * split icon set do in the SHIPPED build, in headless Chrome.
 *
 *   ORACLE_PORT=8162 BRAIN_PORT=8262 EMULATOR_PORT=8962 node tests/perf2-prod-smoke.mjs
 *
 * It serves the production build (`node build`, the same private preview
 * tests/route-coldload.mjs spawns: a free 54xx loopback port, the sandbox the
 * caller names, gate off, keyless; every non-GET answered 204 in the browser)
 * and checks, on a cold, cache-less load:
 *
 *  1. No English flash. `/analyst` (the workspace), `/ops`, `/gods-eye` in a hi and a mr session
 *     (sajag_lang cookie): the visible text is sampled every 30 ms from first
 *     paint for 2 s; any sample that shows one of the route's fixed English
 *     chrome phrases fails. The phrases were measured once on main's
 *     production build (shown in English on the settled EN page, absent from
 *     the settled HI and MR pages) and are fixed below.
 *  2. No blank glyph. In the same samples, and for EN too: an icon in the
 *     first viewport whose name is a valid glyph but which has no path fails
 *     (and on /design, /comms, /citizen and /driver, whose server render
 *     draws glyphs outside the first-paint half: no icon anywhere on those
 *     pages may lose its paths at hydration).
 *  3. Languages load on the shipped path, for every pack module: one sampled
 *     key per module (lib/i18n `.hi.ts` / `.mr.ts` values, read as AST) is
 *     read through the build's read-only probe (window.__sajagLangProbe, the
 *     string a language's own pack holds) —
 *       a. the cookie path: a cold hi / mr load has every module present on
 *          the route in that language before any interaction;
 *       b. the language switch on `/analyst` (the ops store's setter + the shell);
 *       c. the language switch on /design (a page-owned language: the
 *          shell's effect is the only path);
 *     every module present (its EN is registered) must hold the language,
 *     and across the routes visited all 16 modules are covered.
 *  4. /citizen: an English page that previews an alert in हिंदी / मराठी
 *     shows the preview in that script.
 *
 * Exit 0 when every check passes, 1 otherwise.
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { CHROME_ARGS, DECK, chromePath, coldPage, loadPuppeteer, startProdServer } from './route-coldload.mjs';
import { WORKSPACE } from './lib/routes.mjs';

const ts = createRequire(path.join(DECK, 'package.json'))('typescript');
const I18N = path.join(DECK, 'src/lib/i18n');
const MODULES = [
	'strings', 'strings.ops', 'strings.citizen', 'packs', 'packs.ui', 'packs.wall', 'packs.views', 'packs.decisions',
	'packs.dss', 'packs.analysis', 'packs.assistant', 'packs.osint', 'packs.corridor', 'packs.map', 'packs.workspace', 'packs.agent',
];

/**
 * English chrome phrases per route (measured on main's production build against
 * int3cl: present on the settled EN page, absent from the settled HI and MR pages).
 */
const EN_PHRASES = {
	[WORKSPACE]: ['Fit to the data', 'Rows in view', 'No feed rows in this range', 'Needs your decision', 'Active events', 'Exercise data', 'Decision model', 'Vehicles only', 'Authorise pursuit', 'Vehicle pursuit'],
	'/ops': [
		'What happened', 'Selected event', 'Registration marks masked', 'This console', 'Search around', 'Decisions waiting', 'Needs decision', 'Reported stolen',
		'Request unit', 'Watchlist read', 'Last read', 'Corridor operations', 'Generate decision support', 'Traffic flow', 'Feed anomalies', 'Corridor events',
		'Active events', 'Simulated feed', 'Exercise data', 'Decision model', 'Tactical only', 'Vehicles only', 'Lab and system', 'City band', 'Lawful basis',
		'Writer off', 'City picture', 'Units dispatched', 'Ambulance windows', 'Corridor speed', 'Live feed', 'Congested roads', 'Watchlist reads',
		'Open in workspace', 'Convoy route', 'Simulated flow', 'Committed before the log window', 'City signal plans', 'Corridor priority', 'When enabled',
		'Writer idle', 'Apply plan', 'Restore all', 'Active movement adaptation', 'Band driver', 'Protocol floors', 'Shadow evaluation', 'Fails closed',
		'No waypoint', 'No unit out now', 'Watchlist and retention', 'Add vehicle', 'Purge running', 'Feeds and services', 'City feed', 'Scenario emulator',
		'Opened by', 'Show system fields', 'Rules engine', 'Show on map', 'Name a duty officer', 'Authorise pursuit', 'Vehicle pursuit',
	],
	'/gods-eye': ['Fit to the data', 'Rows in view', 'No feed rows in this range', 'Decisions waiting', 'Feed anomalies', 'Watchlisted vehicles', 'City command', 'Open events', 'Exercise data', 'Traffic feed', 'Decision model', 'Vehicles only', 'Cameras answering'],
};

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ── the sampled key per module (plain strings, translated in both languages) ──

function literal(file, name) {
	const sf = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
	for (const st of sf.statements) {
		if (!ts.isVariableStatement(st)) continue;
		for (const d of st.declarationList.declarations) {
			let o = d.initializer;
			while (o && (ts.isAsExpression(o) || ts.isSatisfiesExpression?.(o) || ts.isParenthesizedExpression(o))) o = o.expression;
			if (ts.isIdentifier(d.name) && d.name.text === name && o && ts.isObjectLiteralExpression(o)) {
				const map = new Map();
				for (const p of o.properties) if (ts.isPropertyAssignment(p) && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) && ts.isStringLiteral(p.initializer)) map.set(p.name.text, p.initializer.text);
				return map;
			}
		}
	}
	return new Map();
}
const SAMPLE = {};
for (const m of MODULES) {
	const en = literal(path.join(I18N, `${m}.ts`), 'en');
	const hi = literal(path.join(I18N, `${m}.hi.ts`), 'hi');
	const mr = literal(path.join(I18N, `${m}.mr.ts`), 'mr');
	const key = [...en.keys()].sort().find((k) => hi.get(k) && mr.get(k) && hi.get(k) !== en.get(k) && mr.get(k) !== en.get(k));
	if (key) SAMPLE[m] = { key, en: en.get(key), hi: hi.get(key), mr: mr.get(key) };
}
ok('setup: a sampled key for each of the 16 pack modules', Object.keys(SAMPLE).length === 16, Object.keys(SAMPLE).length + '/16');

// every glyph name in the set: the IconName union in lib/design/icons.ts
const iconSrc = fs.readFileSync(path.join(DECK, 'src/lib/design/icons.ts'), 'utf8');
const VALID_GLYPHS = [...(iconSrc.match(/export type IconName =([\s\S]*?);/)?.[1] ?? '').matchAll(/'([a-z0-9-]+)'/g)].map((m) => m[1]);
ok('setup: the glyph name list (the IconName union)', VALID_GLYPHS.length === 206, `${VALID_GLYPHS.length} names`);

/** Which modules are present (EN registered) and which hold `lang`, read through the build's probe. */
async function langState(page, lang) {
	return page.evaluate(
		(sample, lang) => {
			const probe = window.__sajagLangProbe;
			if (typeof probe !== 'function') return { probe: false, present: [], missing: [] };
			const present = Object.keys(sample).filter((m) => probe('en', sample[m].key) === sample[m].en);
			const missing = present.filter((m) => probe(lang, sample[m].key) !== sample[m][lang]);
			return { probe: true, present, missing };
		},
		SAMPLE,
		lang,
	);
}
const coveredModules = { hi: new Set(), mr: new Set() };
async function expectLang(page, lang, label) {
	let s = await langState(page, lang);
	for (let i = 0; i < 40 && s.probe && s.missing.length; i++) {
		await sleep(100);
		s = await langState(page, lang);
	}
	ok(`${label}: every pack module on the page holds ${lang.toUpperCase()} (${s.present.length} present)`, s.probe && s.present.length > 0 && s.missing.length === 0, s.probe ? (s.missing.join(', ') || s.present.join(' ')) : 'no probe in the build');
	for (const m of s.present) if (!s.missing.includes(m)) coveredModules[lang].add(m);
}

// ── the first-paint sampler (installed before any page script) ───────────────

function installSampler(validGlyphs, anywhere = false) {
	const valid = new Set(validGlyphs);
	const shown = (b) => anywhere || (b.width > 0 && b.bottom > 0 && b.top < innerHeight && b.right > 0 && b.left < innerWidth);
	const S = (window.__perf2 = { samples: [], start: 0 });
	const tick = () => {
		const body = document.body;
		if (body && !S.start && body.innerText.trim()) S.start = performance.now();
		if (!S.start) return;
		const at = Math.round(performance.now() - S.start);
		if (at > 3000) return; // the 2 s window, plus the sample that closes it when a long task delays the timer
		const blank = [];
		for (const s of document.querySelectorAll('svg[data-ui="icon"]')) {
			const n = s.getAttribute('data-icon');
			if (!n || !valid.has(n) || s.querySelector('path')) continue;
			if (shown(s.getBoundingClientRect())) blank.push(n);
		}
		S.samples.push({ at, text: body.innerText, blank });
	};
	const iv = setInterval(tick, 30);
	setTimeout(() => clearInterval(iv), 15000);
	document.addEventListener('DOMContentLoaded', tick);
	// a glyph blanked between two timer samples (hydration emptying a server-drawn icon, a late chunk) is caught at
	// the DOM mutation itself: every mutation batch in the window re-checks the icons in the viewport
	const mo = new MutationObserver(() => {
		if (!S.start || performance.now() - S.start > 3000) return;
		for (const s of document.querySelectorAll('svg[data-ui="icon"]')) {
			const n = s.getAttribute('data-icon');
			if (!n || !valid.has(n) || s.querySelector('path')) continue;
			if (shown(s.getBoundingClientRect())) {
				S.samples.push({ at: Math.round(performance.now() - S.start), text: '', blank: [n], mutation: true });
				break;
			}
		}
	});
	const watch = () => mo.observe(document.documentElement, { childList: true, subtree: true });
	if (document.documentElement) watch();
	else document.addEventListener('readystatechange', watch, { once: true });
}

const server = await startProdServer();
const browser = await loadPuppeteer().launch({ executablePath: chromePath(), headless: 'new', args: CHROME_ARGS });
try {
	// 1 + 2 + 3a: cold loads
	for (const route of [WORKSPACE, '/ops', '/gods-eye']) {
		for (const lang of ['en', 'hi', 'mr']) {
			const { ctx, page } = await coldPage(browser, server.origin, lang);
			const errors = [];
			page.on('pageerror', (e) => errors.push(String(e?.message ?? e)));
			await page.evaluateOnNewDocument(installSampler, VALID_GLYPHS);
			await page.goto(server.origin + route, { waitUntil: 'load', timeout: 120000 });
			for (let i = 0; i < 60; i++) {
				const last = await page.evaluate(() => window.__perf2.samples.at(-1)?.at ?? 0);
				if (last >= 2000) break;
				await sleep(100);
			}
			const window2s = await page.evaluate(() => window.__perf2.samples);
			if (lang !== 'en') {
				const hits = [];
				for (const s of window2s.filter((x) => !x.mutation)) {
					const seen = EN_PHRASES[route].filter((p) => s.text.includes(p));
					if (seen.length) hits.push(`${s.at} ms: ${seen.slice(0, 3).join(' | ')}`);
				}
				// the page's own boot can hold the main thread (the 3D canvas): require the samples to span the window
				const span = window2s.length ? window2s[window2s.length - 1].at : 0;
				ok(
					`no English flash: ${route} cold ${lang} — ${window2s.filter((x) => !x.mutation).length} samples (every 30 ms when the main thread is free) up to ${span} ms`,
					window2s.filter((x) => !x.mutation).length >= 10 && span >= 2000 && hits.length === 0,
					hits.slice(0, 3).join('; ') || `${EN_PHRASES[route].length} phrases never shown`,
				);
				await expectLang(page, lang, `cookie path ${route} ${lang}`);
			}
			const blanks = [...new Set(window2s.flatMap((s) => s.blank.map((n) => `${n}@${s.at}ms`)))];
			const finalBlank = await page.evaluate((valid) => {
				const set = new Set(valid);
				return [...document.querySelectorAll('svg[data-ui="icon"]')]
					.filter((s) => set.has(s.getAttribute('data-icon')) && !s.querySelector('path'))
					.filter((s) => {
						const b = s.getBoundingClientRect();
						return b.width > 0 && b.bottom > 0 && b.top < innerHeight && b.right > 0 && b.left < innerWidth;
					})
					.map((s) => s.getAttribute('data-icon'));
			}, VALID_GLYPHS);
			ok(`no blank glyph: ${route} cold ${lang} — first viewport, first 2 s and settled`, blanks.length === 0 && finalBlank.length === 0, [...blanks.slice(0, 5), ...finalBlank.map((n) => `${n}@settled`)].join(', ') || 'every glyph drawn');
			ok(`no page error: ${route} cold ${lang}`, errors.length === 0, errors.slice(0, 2).join(' | '));
			await ctx.close();
		}
	}

	// 2 (other routes): a page whose server render draws a deferred glyph waits for it before hydrating
	// (any icon on the page, not only the first viewport: none the server drew may ever lose its paths)
	for (const [route, lang] of [['/design', 'en'], ['/comms', 'en'], ['/citizen', 'hi'], ['/driver', 'mr']]) {
		const { ctx, page } = await coldPage(browser, server.origin, lang);
		await page.evaluateOnNewDocument(installSampler, VALID_GLYPHS, true);
		await page.goto(server.origin + route, { waitUntil: 'load', timeout: 120000 });
		for (let i = 0; i < 60; i++) {
			if ((await page.evaluate(() => window.__perf2.samples.at(-1)?.at ?? 0)) >= 2000) break;
			await sleep(100);
		}
		const samples = await page.evaluate(() => window.__perf2.samples);
		const blanks = [...new Set(samples.flatMap((x) => x.blank.map((n) => `${n}@${x.at}ms`)))];
		ok(`no blank glyph: ${route} cold ${lang} — anywhere on the page, first 3 s (hydration never empties a server-drawn glyph)`, samples.length >= 10 && blanks.length === 0, blanks.slice(0, 5).join(', ') || `${samples.length} samples`);
		if (route === '/design') {
			// the gallery lists the whole set (ICONS_16 stays complete for its callers)
			const all = await page.evaluate(() => /\b206 on the 16 px grid\b/.test(document.body.innerText));
			ok('/design: the "All glyphs" gallery counts all 206 glyphs in the production build', all);
		}
		await ctx.close();
	}

	// 3b + 3c: the switch, on a store-owned page and on a page-owned one
	for (const route of [WORKSPACE, '/design']) {
		const { ctx, page } = await coldPage(browser, server.origin, 'en');
		await page.goto(server.origin + route, { waitUntil: 'load', timeout: 120000 });
		await page.waitForSelector('[data-testid="v3-header-menu"]', { timeout: 30000 });
		await sleep(1500);
		for (const lang of ['hi', 'mr']) {
			// V3-P6B: the language switch is in the V3 top bar's menu (the v2 navbar's inline switch is gone)
			if (!(await page.$('[data-v3="header-menu"]'))) await page.click('[data-testid="v3-header-menu"]');
			await page.waitForSelector(`[data-v3="header-menu"] [data-lang-code="${lang}"]`, { timeout: 10000 });
			await page.click(`[data-v3="header-menu"] [data-lang-code="${lang}"]`);
			await expectLang(page, lang, `switch ${route} → ${lang}`);
			const htmlLang = await page.evaluate(() => document.documentElement.lang);
			ok(`switch ${route} → ${lang}: <html lang> follows`, htmlLang === lang, htmlLang);
		}
		await ctx.close();
	}

	// 4: /citizen — an English page previews an alert in the chosen language
	{
		const { ctx, page } = await coldPage(browser, server.origin, 'en');
		await page.goto(server.origin + '/citizen', { waitUntil: 'load', timeout: 120000 });
		await page.waitForSelector('[data-testid="subscribe-phone"]', { timeout: 30000 });
		await sleep(1500);
		await page.type('[data-testid="subscribe-phone"]', '9876543210');
		await page.select('[data-testid="subscribe-lang"]', 'hi');
		await page.click('form button[type="submit"]');
		const script = { hi: /[ऀ-ॿ]/, mr: /[ঀ-৿]/ };
		for (const lang of ['hi', 'mr']) {
			if (lang === 'mr') await page.select('[data-testid="subscribe-lang"]', 'mr');
			let text = '';
			for (let i = 0; i < 40; i++) {
				text = await page.$eval('[data-testid="subscribe-preview"] p', (e) => e.textContent ?? '').catch(() => '');
				if (script[lang].test(text)) break;
				await sleep(100);
			}
			const pageLang = await page.evaluate(() => document.documentElement.lang);
			ok(`/citizen: an English page previews the alert in ${lang.toUpperCase()} script`, pageLang === 'en' && script[lang].test(text) && !/No public corridor event to preview/.test(text), `page ${pageLang}: ${text.slice(0, 60)}`);
			await expectLang(page, lang, `/citizen alert language ${lang}`);
		}
		await ctx.close();
	}

	for (const lang of ['hi', 'mr']) {
		const missing = MODULES.filter((m) => !coveredModules[lang].has(m));
		ok(`coverage: across the pages visited, all 16 pack modules were checked in ${lang.toUpperCase()} on the shipped path`, missing.length === 0, missing.join(', ') || '16/16');
	}
} finally {
	await browser.close();
	server.stop();
}

console.log(failures ? `\nperf2-prod-smoke: ${failures} failure(s)` : '\nperf2-prod-smoke: all green');
process.exit(failures ? 1 : 0);
