/**
 * OSINT report section — the RENDERED markup (FIX-E). The inspector's
 * report section is server-rendered here with svelte/compiler (the
 * wall.unit.mjs pattern) so the auditor's DOM-level findings are killed at
 * the DOM, not in the view-model:
 *
 *   1. osint-verification carries data-verification = the props' state, and
 *      an UNVERIFIED-OSINT row reads "Unverified OSINT" (never a verified
 *      look);
 *   2. a news/social source row never renders an anchor; an official-tier
 *      row renders its link with rel="noopener noreferrer"; the title and
 *      the cached-sample tag render from the dossier's per-signal sources;
 *   3. every section group renders its model testid — osint-second-order is
 *      IN the DOM — and osint-sources is always present (the "Open the
 *      source list" action scrolls to it), with zero reporting rows too;
 *   4. duplicate second-order notes render both (a keyed each never
 *      crashes on equal note strings);
 *   5. the whitelist holds in markup: the poisoned fixture renders neither
 *      an author nor a byline.
 *
 * Run from services/command-deck:   node tests/osint-dom.unit.mjs
 * (bundle written to tests/artifacts/, which is gitignored)
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseHTML } from './lib/minidom.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const ARTIFACTS = path.join(HERE, 'artifacts');
mkdirSync(ARTIFACTS, { recursive: true });

const FIXTURES = path.join(HERE, 'fixtures', 'osint');
const readFixture = (name) => JSON.parse(readFileSync(path.join(FIXTURES, name), 'utf8'));
const CORRELATED = readFixture('correlated.json');
const DISTRICT = readFixture('district.json');
const ROBBERY = readFixture('robbery.json');
const POISONED = readFixture('poisoned.json');

const createRequire = (await import('node:module')).createRequire;
const require = createRequire(path.join(DECK, 'package.json'));
const esbuild = require('esbuild');

const stubStores = {
	name: 'stub-osint-dom-stores',
	setup(build) {
		build.onResolve({ filter: /ops\/store\.svelte$/ }, () => ({ path: 'ops-store', namespace: 'stub-ops' }));
		// the lang rides a getter so a test can render the section in HI/MR (tier words, notes)
		build.onLoad({ filter: /.*/, namespace: 'stub-ops' }, () => ({
			contents: 'export const ops = { get lang() { return globalThis.__osint_lang || "en"; }, officerOn: false, dutyOfficer: "", watchlist: [] };',
			loader: 'js',
		}));
		// the city registry reads a live snapshot; the harness feeds it nothing
		build.onResolve({ filter: /entities\/registry\.svelte$/ }, () => ({ path: 'city-registry', namespace: 'stub-registry' }));
		build.onLoad({ filter: /.*/, namespace: 'stub-registry' }, () => ({
			contents: 'export const cityRegistry = { feed: () => null, byKind: () => [], served: () => true, status: "idle", note: null };',
			loader: 'js',
		}));
		// the actions' workspace store: only openOmnibar/addFilter are ever called
		build.onResolve({ filter: /workspace\/workspace\.svelte$/ }, () => ({ path: 'ws-store', namespace: 'stub-ws' }));
		build.onLoad({ filter: /.*/, namespace: 'stub-ws' }, () => ({
			contents: 'export const workspace = { openOmnibar() {}, addFilter() {} };',
			loader: 'js',
		}));
	},
};

/** The section's Svelte tree, compiled for the server (no DOM at build). */
const sveltePlugin = {
	name: 'svelte-ssr',
	setup(b) {
		b.onLoad({ filter: /\.svelte$/ }, async (args) => {
			const { compile } = require('svelte/compiler');
			const src = readFileSync(args.path, 'utf8');
			const { js } = compile(src, { filename: args.path, generate: 'server', css: 'injected', dev: false });
			return { contents: js.code, loader: 'js', resolveDir: path.dirname(args.path) };
		});
		b.onLoad({ filter: /\.svelte\.(ts|js)$/ }, async (args) => {
			const { compileModule } = require('svelte/compiler');
			const src = readFileSync(args.path, 'utf8');
			const plain = args.path.endsWith('.ts') ? (await esbuild.transform(src, { loader: 'ts' })).code : src;
			const { js } = compileModule(plain, { filename: args.path, generate: 'server', dev: false });
			return { contents: js.code, loader: 'js', resolveDir: path.dirname(args.path) };
		});
	},
};

const ENTRY = `
export { render } from 'svelte/server';
export { default as OsintReportSection } from './src/lib/osint/OsintReportSection.svelte';
export { readReport } from './src/lib/osint/model';
export { osintActions } from './src/lib/osint/actions';
`;
const OUT = path.join(ARTIFACTS, 'osint-dom-bundle.mjs');
let S = null;
let buildError = null;
try {
	const built = await esbuild.build({
		stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'osint-dom-entry.ts' },
		absWorkingDir: DECK,
		alias: { $lib: './src/lib' },
		bundle: true,
		format: 'esm',
		platform: 'node',
		conditions: ['svelte', 'node'],
		outfile: OUT,
		logLevel: 'silent',
		plugins: [stubStores, sveltePlugin],
	});
	buildError = built.errors.map((e) => e.text).join(' | ');
	S = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
} catch (err) {
	buildError = String(err?.message ?? err);
}

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

ok('the server bundle builds (svelte/compiler, generate: server)', !!S && !buildError, buildError ?? '');

/** The section's markup for a row (props + label), stripped of hydration comments. */
function renderSection(props, over = {}) {
	const html = S.render(
		S.OsintReportSection,
		{
			// the component's props: { row, dossier }
			props: {
				row: {
					urn: over.urn ?? 'osint_event:8ec6f567-9366-47ae-8fde-38aa421a3219',
					kind: 'osint_event',
					id: '8ec6f567-9366-47ae-8fde-38aa421a3219',
					label: over.label ?? 'Road accident · Sector V (Salt Lake)',
					sublabel: null,
					icon: 'geosearch',
					state: 'surfaced',
					stateIntent: 'none',
					t: null,
					end: null,
					lon: null,
					lat: null,
					source: 'osint',
					verification: over.verification ?? null,
					credibility: null,
					test: false,
					masked: false,
					props,
				},
				dossier: null,
			},
		},
	).body.replace(/<!--[\s\S]*?-->/g, '');
	return parseHTML(html);
}

/** The R2 dossier shape: per-signal sources + notes keyed by signal_id. */
const NEWS_SIGNAL = '9a1b2c3d-0000-4c3c-8d4d-00000000a001';
const WIRE_SIGNAL = '9a1b2c3d-0000-4c3c-8d4d-00000000a002';
const CONTEXT_SIGNAL = '9a1b2c3d-0000-4c3c-8d4d-00000000a003';
function withDossierSources(base) {
	return {
		...base,
		sources: [
			{ signal_id: NEWS_SIGNAL, source: 'google_news_rss', publisher: 'news-a.example', url: null, title: 'Car crashes near club; [AGE] rider hurt', fetch_mode: 'cached-sample', role: 'primary' },
			{ signal_id: WIRE_SIGNAL, source: 'sachet_cap', publisher: 'sachet.ndma.gov.in', url: 'https://sachet.ndma.gov.in/cap/a92f', title: 'District warning: heavy rain', fetch_mode: 'cached-sample', role: 'corroborating' },
		],
		source_notes: [
			{ signal_id: NEWS_SIGNAL, source_tier: 'aggregator', link_note: 'source link withheld — may name a person' },
			{ signal_id: WIRE_SIGNAL, source_tier: 'official', link_note: null },
		],
		context_sources: [{ signal_id: CONTEXT_SIGNAL, source: 'sachet_cap', publisher: 'sachet.ndma.gov.in', url: null, title: 'District warning', fetch_mode: 'cached-sample', role: 'context' }],
	};
}

if (S) {
	// ─── 1. the verification tag is the props' state, in words ────────────────
	{
		const doc = renderSection(CORRELATED.props);
		const tag = doc.querySelector('[data-testid="osint-verification"]');
		ok(
			'osint-verification[data-verification] equals the props\' verification_state (NEWS-REPORTED)',
			!!tag && tag.getAttribute('data-verification') === 'NEWS-REPORTED',
			tag ? `data-verification=${tag.getAttribute('data-verification')}` : 'tag missing',
		);
		ok('the tag reads the state in words ("News-reported")', !!tag && /News-reported/.test(tag.textContent));
		const unv = renderSection({ ...ROBBERY.props, verification_state: 'UNVERIFIED-OSINT' }, { verification: 'UNVERIFIED-OSINT' });
		const unvTag = unv.querySelector('[data-testid="osint-verification"]');
		ok(
			'an UNVERIFIED-OSINT row reads "Unverified OSINT", never a verified look',
			!!unvTag && unvTag.getAttribute('data-verification') === 'UNVERIFIED-OSINT' && /Unverified OSINT/.test(unvTag.textContent) && !/Official/.test(unvTag.textContent),
			unvTag ? `${unvTag.getAttribute('data-verification')}:${unvTag.textContent.trim()}` : 'tag missing',
		);
	}

	// ─── 2. links: official tier only; title + cached sample from the dossier ─
	{
		const doc = renderSection(withDossierSources(CORRELATED.props));
		const rows = doc.querySelectorAll('[data-testid="osint-source"]');
		ok('both reporting sources render as rows', rows.length === 2, String(rows.length));
		const news = rows.find((r) => r.getAttribute('data-publisher') === 'news-a.example');
		const official = rows.find((r) => r.getAttribute('data-publisher') === 'sachet.ndma.gov.in');
		ok('a news row renders NO anchor at all (its link is withheld)', !!news && news.querySelectorAll('a[href]').length === 0);
		// fix round 2, item 9: the withheld note reads ONCE PER LIST, not once per row — the
		// section carries it exactly once for two withheld... (here: one withheld row)
		ok('the withheld note reads once per section', (doc.querySelector('[data-testid="osint-report"]').textContent.match(/Source link withheld/g) ?? []).length === 1, String((doc.querySelector('[data-testid="osint-report"]').textContent.match(/Source link withheld/g) ?? []).length));
		ok(
			'an official-tier row renders its link with rel="noopener noreferrer"',
			!!official && official.querySelectorAll('a[href]').length === 1 && official.querySelector('a[href]').getAttribute('rel') === 'noopener noreferrer' && /sachet\.ndma\.gov\.in/.test(official.querySelector('a[href]').getAttribute('href')),
			official ? official.querySelector('a[href]')?.outerHTML ?? '' : 'row missing',
		);
		// fix round 2, item 9: the official row names its title ONCE — as the link text — and
		// carries no second "Official source" tag (its tier tag already says Official)
		ok('the official row carries no duplicate title span (the title IS the link text)', official.querySelectorAll('.title, span.title').length === 0 && official.textContent.indexOf('District warning: heavy rain') === official.textContent.lastIndexOf('District warning: heavy rain'), official.textContent.replace(/\s+/g, ' ').slice(0, 140));
		ok('the "Official source" tag is gone (the tier tag says Official)', !/Official source/.test(doc.querySelector('[data-testid="osint-report"]').textContent));
		// fix round 2, item 8 (kills R2g/R2h): a POISONED news-tier url on the wire renders no
		// anchor and no url text anywhere in the section
		const poisoned = renderSection({
			...CORRELATED.props,
			sources: [
				{ signal_id: NEWS_SIGNAL, source: 'reddit_rss', publisher: 'reddit.com', url: 'https://www.reddit.com/r/kolkata/comments/zz1/poisoned', title: 'Big crowd near Law Garden right now', fetch_mode: 'cached-sample', role: 'primary' },
			],
			source_notes: [{ signal_id: NEWS_SIGNAL, source_tier: 'social_unverified', link_note: 'source link withheld — may name a person' }],
		});
		ok('a poisoned news-tier url renders NO anchor anywhere in the section', poisoned.querySelectorAll('[data-testid="osint-report"] a[href]').length === 0, String(poisoned.querySelectorAll('[data-testid="osint-report"] a[href]').length));
		ok('the poisoned url leaks nowhere (no href, no url text)', !/reddit\.com\/r\//.test(poisoned.querySelector('[data-testid="osint-report"]').outerHTML));
		// fix round 2, item 8: https: is the only scheme ever bound as an official href
		const insecure = renderSection({
			...CORRELATED.props,
			sources: [{ signal_id: WIRE_SIGNAL, source: 'sachet_cap', publisher: 'sachet.ndma.gov.in', url: 'http://sachet.ndma.gov.in/cap/a92f', title: 'District warning: heavy rain', fetch_mode: 'cached-sample', role: 'primary' }],
			source_notes: [{ signal_id: WIRE_SIGNAL, source_tier: 'official', link_note: null }],
		});
		ok('an official row with an http: url renders NO anchor', insecure.querySelectorAll('[data-testid="osint-report"] a[href]').length === 0, String(insecure.querySelectorAll('[data-testid="osint-report"] a[href]').length));
		ok('the news row shows its (redacted) title and the cached-sample tag', !!news && /\[AGE\] rider hurt/.test(news.textContent) && /cached sample/.test(news.textContent));
		ok('officialness rides the TIER: the aggregator row is data-official=0, the official row 1', news?.getAttribute('data-official') === '0' && official?.getAttribute('data-official') === '1');
		// per-source tiers (S1): each row wears ITS OWN tier tag, not the situation's
		ok('the tier tags are per source (aggregator on the news row, official on the official row)', !!news && !!official && /Aggregator/.test(news.textContent) && !/Aggregator/.test(official.textContent) && /Official/.test(official.textContent));
		// the per-signal rows came from the dossier shape, not the situation's tier list
		ok('the situation-level tier row is gone (tiers ride the source rows)', !/Source tiers/.test(doc.querySelector('[data-testid="osint-report"]').textContent));
	}

	// ─── 2b. the fetch-mode tag is HONEST (fix round 2, item 1): a cached-sample tag ONLY on a
	// cached-sample row — fetch_mode 'live' is never tagged as a cached sample
	{
		const mixed = renderSection({
			...CORRELATED.props,
			sources: [
				{ signal_id: NEWS_SIGNAL, source: 'gdelt_doc', publisher: 'news-c.example', url: null, title: 'Crowd near Law Garden; [PERSON] quoted', fetch_mode: 'live', role: 'primary' },
				{ signal_id: WIRE_SIGNAL, source: 'google_news_rss', publisher: 'news-a.example', url: null, title: 'Car crashes near club; [AGE] rider hurt', fetch_mode: 'cached-sample', role: 'corroborating' },
			],
			source_notes: [
				{ signal_id: NEWS_SIGNAL, source_tier: 'aggregator', link_note: 'source link withheld — may name a person' },
				{ signal_id: WIRE_SIGNAL, source_tier: 'aggregator', link_note: 'source link withheld — may name a person' },
			],
		});
		const rows = mixed.querySelectorAll('[data-testid="osint-source"]');
		const liveRow = rows.find((r) => r.getAttribute('data-publisher') === 'news-c.example');
		const cachedRow = rows.find((r) => r.getAttribute('data-publisher') === 'news-a.example');
		ok('a fetch_mode "live" row carries NO cached-sample tag', !!liveRow && !/cached sample/.test(liveRow.textContent), liveRow?.textContent.replace(/\s+/g, ' ').slice(0, 120));
		ok('a fetch_mode "cached-sample" row still carries the tag', !!cachedRow && /cached sample/.test(cachedRow.textContent));
	}

	// ─── 2c. the tier words localize (fix round 2, item 7) ────────────────────
	{
		globalThis.__osint_lang = 'hi';
		try {
			const hi = renderSection(withDossierSources(CORRELATED.props));
			const rows = hi.querySelectorAll('[data-testid="osint-source"]');
			const news = rows.find((r) => r.getAttribute('data-publisher') === 'news-a.example');
			const official = rows.find((r) => r.getAttribute('data-publisher') === 'sachet.ndma.gov.in');
			ok(
				'the tier tags read the pack in HI (never the EN words)',
				!!news && /समाचार एकत्रकर्ता/.test(news.textContent) && !/Aggregator/.test(news.textContent) && !!official && /आधिकारिक/.test(official.textContent) && !/Official/.test(official.textContent),
				news?.textContent.replace(/\s+/g, ' ').slice(0, 100),
			);
		} finally {
			delete globalThis.__osint_lang;
		}
	}

	// ─── 3. section testids: osint-second-order in the DOM, osint-sources always ─
	{
		const doc = renderSection(ROBBERY.props);
		ok('osint-second-order is IN the DOM (the section group renders its model testid)', doc.querySelectorAll('[data-testid="osint-second-order"]').length === 1);
		ok('osint-sources is present on a situation with sources', doc.querySelectorAll('[data-testid="osint-sources"]').length === 1);
		const none = renderSection({ ...DISTRICT.props, provenance: { ...DISTRICT.props.provenance, publishers: [] } });
		ok('osint-sources is present even with ZERO reporting rows (the action must scroll somewhere)', none.querySelectorAll('[data-testid="osint-sources"]').length === 1);
		// fix round 2, item 7: the compact section carries no Location group and no situation
		// class row — those read in the inspector's Properties groups (generic.ts)
		ok('the compact section carries no Location group (the Properties groups own it)', none.querySelectorAll('[data-section-title="Location"]').length === 0 && none.querySelectorAll('[data-testid="osint-road"]').length === 0, String(none.querySelectorAll('[data-section-title]').length));
		ok('the compact section shows no situation-class row (only the summary line)', !none.querySelector('[data-testid="osint-class"]') && !none.querySelector('[data-testid="osint-correlated"]'));
	}

	// ─── 4. duplicate second-order notes: one counted note, an index-keyed each ────
	{
		// fix round 2, item 16: two flags with the SAME words collapse into ONE counted note
		const dup = renderSection({
			...ROBBERY.props,
			second_order: [
				{ kind: 'ambulance_route', urn: 'segment:12', segment_id: 12, note: 'On a 108 route' },
				{ kind: 'ambulance_route', urn: 'segment:13', segment_id: 13, note: 'On a 108 route' },
			],
		});
		ok('duplicate second-order notes render ONCE, counted ("On a 108 route ×2")', (dup.textContent.match(/On a 108 route/g) ?? []).length === 1 && /×2/.test(dup.textContent), String((dup.textContent.match(/On a 108 route/g) ?? []).length));
		// the client-mode compile of the REAL section (generate: 'client', dev: true): the
		// notes each must compile with the INDEX as its key ($.index) — Svelte 5 keeps no
		// runtime duplicate-key check to trip by mounting, so the compiled key fn IS the guard
		const { compile } = require('svelte/compiler');
		const sectionSrc = readFileSync(path.join(DECK, 'src/lib/osint/OsintReportSection.svelte'), 'utf8');
		const clientJs = compile(sectionSrc, { filename: 'OsintReportSection.svelte', generate: 'client', dev: true }).js.code;
		// the compiled call head of the notes each: `$.each(node, 1, () => $.get(s).notes, <KEYFN>, …)`
		// — the index key compiles to `$.index`; a text key would be `(n) => n`
		const at = clientJs.indexOf('.notes');
		const head = at >= 0 ? clientJs.slice(clientJs.lastIndexOf('$.each(', at), at + 160) : '';
		ok('the client compile keys the notes each by the INDEX ($.index), never by the note text', head.startsWith('$.each(') && /\$\.index/.test(head), head.replace(/\s+/g, ' ').slice(0, 120) || 'notes each not found in the client compile');
	}

	// ─── 5. "Open the source list" scrolls to the osint-sources group (2c) ────
	{
		const doc = renderSection(withDossierSources(CORRELATED.props));
		// the section's markup, in a document the action's querySelector can reach
		globalThis.document = doc;
		const target = doc.querySelector('[data-testid="osint-sources"]');
		let scrolled = null;
		target.scrollIntoView = (opts) => {
			scrolled = opts;
		};
		const row = {
			urn: 'osint_event:x', kind: 'osint_event', id: 'x', label: 'x', sublabel: null, icon: 'dot', state: null, stateIntent: 'none',
			t: null, end: null, lon: null, lat: null, source: 'osint', verification: null, credibility: null, test: false, masked: false, props: { toponym: 'Sector V (Salt Lake)' },
		};
		const actions = S.osintActions(row, 'en');
		const openSources = actions.find((a) => a.id === 'osint.sources');
		openSources.run();
		ok('the "Open the source list" action scrolls to the osint-sources group (the real id)', scrolled != null && !!target, String(scrolled));
		delete globalThis.document;
	}

	// ─── 5. the whitelist holds in markup ─────────────────────────────────────
	{
		const doc = renderSection(POISONED.props);
		const text = doc.querySelector('[data-testid="osint-report"]').textContent;
		ok(
			'the poisoned fixture renders neither author, byline, nor their values',
			!/author|byline|Staff Correspondent|A Reporter/i.test(text),
			text.slice(0, 80),
		);
		// no held-social line on any per-report view (R1: it implies corroboration)
		const held = renderSection(CORRELATED.props);
		ok('no "social posts held" line anywhere on a per-report view (R1)', !/social post/i.test(held.querySelector('[data-testid="osint-report"]').textContent));
	}
}

if (failures) {
	console.error(`FAIL osint-dom.unit.mjs — ${failures} failing assertion(s)`);
	process.exit(1);
}
if (!process.argv.includes('--inspector')) {
	console.log('ok   osint-dom.unit.mjs — all assertions passed');
	// the renders started the shell clock's interval: leave explicitly
	process.exit(0);
}

// ─── 6. the INSPECTOR browser check (fix round 2, item 2) ────────────────────
// `node tests/osint-dom.unit.mjs --inspector http://127.0.0.1:5423` — drives the
// /design/osint harness on the dev deck and MEASURES the compact inspector: the tabs sit
// above the fold at 1920×1080 (≤ 600 px) and at 1366×768 and 1440×900 (≤ 560 px), the
// verification tag renders exactly once, the context hint is a VISIBLE second line, and a
// language switch reaches the OSINT surfaces (tier words in HI). Exit 1 on any failure.
const BASE = process.argv[process.argv.indexOf('--inspector') + 1];
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(BASE ?? '')) {
	console.error('FAIL --inspector needs the dev deck base (http://127.0.0.1:<port>)');
	process.exit(1);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let browserFails = 0;
try {
	const { createRequire } = await import('node:module');
	const requireP = createRequire(process.env.PUPPETEER_FROM ?? path.resolve(DECK, '../../frontend/package.json'));
	const puppeteer = requireP('puppeteer');
	const CHROME = `${process.env.HOME}/.cache/puppeteer/chrome/linux_arm-153.0.8010.36/chrome-linux-arm64/chrome`;
	const browser = await puppeteer.launch({
		executablePath: CHROME,
		headless: 'new',
		args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--use-gl=angle', '--ignore-gpu-blocklist'],
	});
	const sizes = [
		[1920, 1080, 600],
		[1440, 900, 560],
		[1366, 768, 560],
	];
	for (const [w, h, max] of sizes) {
		const page = await browser.newPage();
		await page.setViewport({ width: w, height: h });
		await page.goto(`${BASE}/design/osint`, { waitUntil: 'networkidle2', timeout: 120_000 }).catch(() => {});
		await sleep(4_000);
		const m = await page.evaluate(() => {
			const insp = document.querySelector('[data-testid="entity-dossier"]');
			const tabs = insp?.querySelector('.tabs');
			const r = tabs?.getBoundingClientRect();
			// the tabs count as ABOVE THE FOLD only when the scroller has not been scrolled
			let scroller = null;
			for (let e = tabs; e && e !== document.body; e = e.parentElement) {
				const s = getComputedStyle(e);
				if (/(auto|scroll)/.test(s.overflowY) && e.scrollHeight > e.clientHeight) scroller = e;
			}
			return {
				tabsTop: r ? Math.round(r.top) : null,
				tabsBottom: r ? Math.round(r.bottom) : null,
				innerH: innerHeight,
				verifTags: document.querySelectorAll('[data-testid="osint-verification"]').length,
				provTags: insp ? insp.querySelectorAll('[data-ui="provenance-tag"]').length : null,
				hint: document.querySelector('[data-figure-sub]')?.textContent ?? null,
				hintVisible: (() => {
					const el = document.querySelector('[data-figure-sub]');
					if (!el) return false;
					const b = el.getBoundingClientRect();
					return b.height > 0 && b.width > 0;
				})(),
			};
		});
		const okTabs = m.tabsTop != null && m.tabsTop <= max && m.tabsBottom <= m.innerH;
		console.log(`${okTabs ? 'ok  ' : 'FAIL'} tabs above the fold at ${w}×${h} (top ${m.tabsTop} ≤ ${max}, bottom ${m.tabsBottom} ≤ ${m.innerH})`);
		if (!okTabs) browserFails++;
		console.log(`${m.verifTags === 1 ? 'ok  ' : 'FAIL'} exactly ONE osint-verification tag at ${w}×${h} (${m.verifTags})`);
		if (m.verifTags !== 1) browserFails++;
		console.log(`${m.provTags === 2 ? 'ok  ' : 'FAIL'} the inspector carries exactly two provenance tags (header + section; the Provenance row's is gone) at ${w}×${h} (${m.provTags})`);
		if (m.provTags !== 2) browserFails++;
		console.log(`${m.hintVisible && /district warning in effect/.test(m.hint ?? '') ? 'ok  ' : 'FAIL'} the context hint is a VISIBLE second line at ${w}×${h} (${JSON.stringify(m.hint)})`);
		if (!(m.hintVisible && /district warning in effect/.test(m.hint ?? ''))) browserFails++;
		await page.close();
	}
	// HI: the language switch reaches the OSINT surfaces (the harness wires onLangChange)
	{
		const page = await browser.newPage();
		await page.setViewport({ width: 1366, height: 768 });
		await page.goto(`${BASE}/design/osint`, { waitUntil: 'networkidle2', timeout: 120_000 }).catch(() => {});
		await sleep(4_000);
		// V3-P6B: the language switch is in the V3 top bar's menu (the v2 navbar's inline switch is gone): open it first
		// (this harness page is a fixed full-screen overlay, so the trigger is clicked in the page, as the old inline switch was)
		if (!(await page.$('[data-lang-code="hi"]'))) await page.evaluate(() => document.querySelector('[data-testid="v3-header-menu"]')?.click());
		await page.waitForSelector('[data-lang-code="hi"]', { timeout: 8_000 }).catch(() => {});
		const clicked = await page.evaluate(() => {
			const b = document.querySelector('[data-lang-code="hi"]') ?? [...document.querySelectorAll('button, [role="radio"]')].find((e) => (e.textContent || '').trim() === 'हि');
			if (b) {
				b.click();
				return true;
			}
			return false;
		});
		await sleep(1_500);
		const hiText = await page.evaluate(() => document.querySelector('[data-testid="osint-report"]')?.textContent ?? '');
		const hiTier = /समाचार एकत्रकर्ता/.test(hiText) && !/Aggregator/.test(hiText);
		console.log(`${clicked && hiTier ? 'ok  ' : 'FAIL'} a language switch reaches the OSINT surfaces (HI tier word in the section)`);
		if (!clicked || !hiTier) browserFails++;
		await page.close();
	}
	await browser.close();
} catch (e) {
	console.error(`FAIL inspector browser check — ${String(e?.message ?? e).slice(0, 200)}`);
	browserFails++;
}
if (browserFails) {
	console.error(`FAIL osint-dom.unit.mjs --inspector — ${browserFails} failing check(s)`);
	process.exit(1);
}
console.log('ok   osint-dom.unit.mjs — all assertions passed (inspector check included)');
process.exit(0);
