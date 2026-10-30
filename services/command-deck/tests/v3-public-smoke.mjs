/**
 * /citizen and /driver smoke in the V3 day look (V3-P6A; V3-SPEC §6.8, §8) — HERMETIC: the public feed, the road geometry and (for
 * the driver's request) the dispatch POST and its poll are answered IN THE BROWSER from the fixtures below; the deck's own
 * /gods-eye/mode is answered keyless; tiles and third parties are aborted; every OTHER non-GET is aborted and counted.
 *
 *   node tests/v3-public-smoke.mjs [deckUrl]      (default http://127.0.0.1:5482; a dev deck of this tree)
 *   V3_SHOTS=<dir> node tests/v3-public-smoke.mjs …   also saves screenshots
 *
 * Asserts:
 *   1. the day theme and the public shell: data-shell="citizen" with the lockup, the plain-language posture, the two views, the
 *      language switch — and NO operator surface: no V3 rail, no top bar, no officer control, no /ops or /decide link, no band
 *      code, no Share;
 *   2. /citizen at 1920, 1366 and 390: one column ≤ 592 px, no sideways scroll, the posture sentence in ≥ 22 px type, every hold
 *      row readable (no clip, no overlap), every source badge inside its card — EN · HI · MR at 390;
 *   3. the hold cards carry a map of the stretch (day-graded), the EMULATED card's is DASHED (never a live road hold) and the live
 *      card's solid; the honest SIMULATED FEED · EMULATED tag and note are kept;
 *   4. contrast: the page's text inks hold ≥ 4.5:1 on what they sit on (measured in the browser, EN · HI · MR);
 *   5. /driver: the golden-hour clock is the hero (≥ 56 px) and says it has not started; the phase rail is four large steps;
 *      the urgency chips are ≥ 44 px tall with ≥ 16 px type; the one request button is ≥ 56 px; English by default;
 *   6. the live request files ONE POST (answered in the browser), waits for the officer — no approve control — then the window
 *      opens with its countdown in the 108 corridor green and the unit EMULATED;
 *   7. the scripted fallback is labelled and files NOTHING (zero POSTs);
 *   8. no registration mark and no operator API call anywhere on either page (only /api/public/*, the segments read and
 *      the dispatch POST the driver itself files);
 *   9. zero other would-be writes; no page error;
 *  10. /welcome (the landing, V3-LANDING): night theme, no shell of either kind; at 1920 × 1080 and 1366 × 768 the first
 *      viewport is the poster (the lockup, the promise, both doors and the console window inside it); EN · HI · MR at
 *      1920, 1366 and 390 with no sideways scroll; the doors lead to / (a new document) and /citizen; every picture keeps
 *      its honest caption; no registration mark; the language switch speaks the pick and persists it; the page makes
 *      no API call at all; its text inks hold ≥ 4.5:1.
 *
 * Exit 0 with `ok <name>` lines; exit 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');

export function publicFixtures(now = Date.now()) {
	const stub = {
		event_id: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee', event_kind: 'procession', status: 'active',
		window_start: new Date(now - 600_000).toISOString(), window_end: new Date(now + 7_200_000).toISOString(),
		stretches: [{ segment_id: 1003, road_name: 'Vidyasagar Setu (NH12, Vidyasagar Flyover)', junction_id: 6 }, { segment_id: 1004, road_name: 'Rash Behari Avenue', junction_id: 9 }],
		phases: [{ label: 'procession window', window_start: null, window_end: null, advance_closure_sec: 150 }],
		hold: { minutes: 3, advance_closure_sec: 150, source: 'closure_policy' },
		alternate: { road_names: ['VIP Road (Kazi Nazrul Islam Avenue)'], segment_ids: [1039], source: 'k_shortest_paths' }, tier: 'watch', unavailable: [],
	};
	const emu = { ...stub, event_id: 'aaaaaaaa-eeee-4ccc-8ddd-eeeeeeeeeeee', event_kind: 'mass_gathering', emulated: true, stretches: [{ segment_id: 1004, road_name: 'Strand Road', junction_id: 9 }] };
	const later = { event_id: 'aaaaaaaa-ffff-4ccc-8ddd-eeeeeeeeeeee', event_kind: 'work_zone', status: 'approved', starts_at: new Date(now + 26 * 3600_000).toISOString(), window_end: new Date(now + 30 * 3600_000).toISOString(), road_names: ['Howrah Bridge', 'Strand Road'], emulated: false };
	const seg = (id, name, a, b) => ({ segment_id: id, road_name: name, road_class: 'primary', geometry: { type: 'LineString', coordinates: [a, b] } });
	const segments = { segments: [seg(1003, 'Vidyasagar Setu (NH12, Vidyasagar Flyover)', [88.3264, 22.5687], [88.3324, 22.5717]), seg(1004, 'Strand Road', [88.3324, 22.5717], [88.3384, 22.5727])] };
	return { stub, emu, later, segments, feed: (events, laterRows = []) => ({ as_of: new Date().toISOString(), events, later: laterRows, tier: events.length ? 'watch' : 'calm', emulated_labelling: true }) };
}

export async function main() {
	const base = (process.argv[2] ?? 'http://127.0.0.1:5482').replace(/\/$/, '');
	const origin = new URL(base).origin;
	if (/:(5273|8090|8091|8092)$/.test(origin)) {
		console.error('refusing a live port');
		process.exit(2);
	}
	const SHOTS = process.env.V3_SHOTS ? path.resolve(process.env.V3_SHOTS) : null;
	if (SHOTS) mkdirSync(SHOTS, { recursive: true });
	let puppeteer = null;
	for (const from of [process.env.PUPPETEER_FROM, path.resolve(DECK, '../../frontend/package.json')].filter(Boolean)) {
		try {
			const req = createRequire(from);
			puppeteer = req('puppeteer').default ?? req('puppeteer');
			break;
		} catch {
			// next candidate
		}
	}
	if (!puppeteer) {
		console.error('puppeteer not found');
		process.exit(1);
	}
	const CHROME = [`${process.env.HOME}/.cache/puppeteer/chrome/linux_arm-153.0.8010.36/chrome-linux-arm64/chrome`].find((p) => existsSync(p));
	let failures = 0;
	const ok = (name, cond, detail = '') => {
		if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
		else {
			failures++;
			console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
		}
	};
	const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
	const fx = publicFixtures();
	const D = 'dddddddd-1111-4222-8333-944455556666';
	const writes = [];
	const posts = [];
	const calls = [];
	const errors = [];
	let feedEvents = [fx.stub, fx.emu];
	let feedLater = [fx.later];
	let polls = 0;
	let approvedAt = null;
	let arrivalAt = null;
	const MR = /[ऀ-ॿ]/;
	const HI = /[ऀ-ॿ]/;

	const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox'] });
	async function open(route, { lang = null, w = 1366, h = 768 } = {}) {
		const page = await browser.newPage();
		await page.setViewport({ width: w, height: h });
		await page.setRequestInterception(true);
		page.on('request', (req) => {
			const u = new URL(req.url());
			const json = (body) => req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
			if (u.origin === origin) calls.push(`${req.method()} ${u.pathname}`);
			if (u.origin === origin && req.method() === 'POST' && /^\/api\/v1\/events\/[^/]+\/dispatch$/.test(u.pathname)) {
				posts.push(u.pathname);
				return json({ dispatch_id: D, event_id: fx.stub.event_id, agency: 'ambulance', unit_id: '108-14', status: 'requested' });
			}
			if (req.method() !== 'GET' && req.method() !== 'HEAD') {
				writes.push(`${req.method()} ${u.pathname}`);
				return req.abort();
			}
			if (u.origin !== origin) return req.abort();
			if (u.pathname === '/api/public/events') return json(fx.feed(feedEvents, feedLater));
			if (u.pathname === '/api/v1/spatial/segments') return json(fx.segments);
			if (u.pathname === '/gods-eye/mode') return json({ mode: 'keyless-osm' });
			if (u.pathname === `/api/public/dispatches/${D}`) {
				polls += 1;
				const t = Date.now();
				if (polls >= 2 && approvedAt === null) {
					approvedAt = t - 2000;
					arrivalAt = t + 95_000;
				}
				const approved = approvedAt !== null;
				return json({
					as_of: new Date(t).toISOString(),
					dispatch: { dispatch_id: D, event_id: fx.stub.event_id, status: approved ? 'approved' : 'requested', unit_id: '108-14', approved_at: approved ? new Date(approvedAt).toISOString() : null },
					unit: approved ? { status: 'approved', eta_sec: Math.max(0, (arrivalAt - t) / 1000), eta_at: new Date(t).toISOString(), arrived: false, position: [88.3289, 22.5702], emulated: true, source: 'emulated_dispatch_projection' } : null,
				});
			}
			if (u.pathname.startsWith('/api/')) return req.respond({ status: 404, contentType: 'application/json', body: '{}' });
			return req.continue();
		});
		if (lang) await page.setCookie({ name: 'sajag_lang', value: lang, url: origin });
		page.on('pageerror', (e) => errors.push(String(e.message).slice(0, 200)));
		await page.goto(`${base}${route}`, { waitUntil: 'domcontentloaded', timeout: 90000 });
		return page;
	}
	/** The contrast of the text inks on what they sit on (measured: the first opaque background up the tree). */
	const contrast = (page, selectors) =>
		page.evaluate((sels) => {
			const parse = (c) => {
				const m = c.match(/rgba?\(([^)]+)\)/);
				if (!m) return null;
				const [r, g, b, a = 1] = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
				return { r, g, b, a };
			};
			const lum = ({ r, g, b }) => {
				const f = (v) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
				return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
			};
			const bgOf = (el) => {
				let layers = [];
				for (let n = el; n; n = n.parentElement) {
					const c = parse(getComputedStyle(n).backgroundColor);
					if (c && c.a > 0) {
						layers.push(c);
						if (c.a >= 1) break;
					}
				}
				let base = { r: 255, g: 255, b: 255 };
				for (const c of layers.reverse()) base = { r: c.r * c.a + base.r * (1 - c.a), g: c.g * c.a + base.g * (1 - c.a), b: c.b * c.a + base.b * (1 - c.a) };
				return base;
			};
			return sels.map((s) => {
				const el = document.querySelector(s);
				if (!el) return { s, ratio: null };
				const fg = parse(getComputedStyle(el).color);
				const bg = bgOf(el);
				const a = lum({ r: fg.r, g: fg.g, b: fg.b });
				const b = lum(bg);
				return { s, ratio: Math.round(((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)) * 100) / 100 };
			});
		}, selectors);

	try {
		// ── /citizen at 1366 · shell ─────────────────────────────────────────
		const c = await open('/citizen', { lang: 'en' });
		await c.waitForSelector('.event-card', { timeout: 30000 });
		await sleep(1500);
		const shell = await c.evaluate(() => ({
			theme: document.documentElement.dataset.theme,
			shell: document.querySelector('[data-shell="citizen"]') !== null,
			logo: document.querySelector('[data-shell="citizen-bar"] img[src="/brand/sajag-lockup-day.svg"]') !== null,
			tier: document.querySelector('[data-shell="citizen-bar"] [data-tier]')?.getAttribute('data-tier'),
			views: [...document.querySelectorAll('[data-shell="citizen-bar"] .views a')].map((a) => a.getAttribute('href')).join(),
			langs: [...document.querySelectorAll('[data-shell="citizen-bar"] .lang button')].map((b) => b.getAttribute('lang')).join(),
			v3shell: document.querySelectorAll('[data-shell="v3"], [data-v3="rail"], [data-v3="top-bar"], [data-testid="v3-officer"]').length,
			opsLinks: document.querySelectorAll('a[href="/ops"], a[href="/decide"], a[href="/map"], a[href="/comms"], a[href="/analyst"], a[href="/"]').length,
			bar: document.querySelector('[data-shell="citizen-bar"]').textContent,
			main: document.querySelector('.citizen').getBoundingClientRect().width,
		}));
		ok('1. day theme; the public shell with the lockup, the posture, two views and the language switch', shell.theme === 'daylight' && shell.shell && shell.logo && shell.tier === 'watch' && shell.views === '/citizen,/driver' && shell.langs === 'en,hi,mr', JSON.stringify(shell));
		ok('1. no operator surface: no V3 rail / top bar / officer control, no link into the deck, no band code, no Share', shell.v3shell === 0 && shell.opsLinks === 0 && !/\b(GREEN|AMBER|RED|BLACK)\b|share/i.test(shell.bar), `v3=${shell.v3shell} links=${shell.opsLinks}`);
		ok('2. one column of at most 592 px at 1366', shell.main <= 592, `${shell.main}`);
		const hold = await c.evaluate(() => ({
			strip: parseFloat(getComputedStyle(document.querySelector('.strip p')).fontSize),
			kicker: parseFloat(getComputedStyle(document.querySelector('.kicker')).fontSize),
			cards: document.querySelectorAll('.event-card').length,
			maps: [...document.querySelectorAll('.event-card')].map((e) => ({ src: e.getAttribute('data-source'), map: e.querySelector('[data-testid="hold-map"]')?.getAttribute('data-live') ?? null })),
			emuTag: document.querySelector('.event-card[data-source="emulated"] [data-source-badge="emulated"]')?.textContent.trim(),
			emuDashed: getComputedStyle(document.querySelector('.event-card[data-source="emulated"]')).borderStyle,
		}));
		ok('2. the posture sentence is big type (≥ 22 px), the title ≥ 28 px', hold.strip >= 22 && hold.kicker >= 28, JSON.stringify({ strip: hold.strip, kicker: hold.kicker }));
		ok('3. every hold card carries a map of its stretch: the live one solid, the EMULATED one DASHED', hold.maps.length === 2 && hold.maps.find((m) => m.src === 'live')?.map === 'yes' && hold.maps.find((m) => m.src === 'emulated')?.map === 'no', JSON.stringify(hold.maps));
		ok('3. the EMULATED card keeps its honest tag and an outlined (dashed) frame', hold.emuTag === 'Simulated feed · emulated' && hold.emuDashed === 'dashed', `${hold.emuTag} · ${hold.emuDashed}`);
		const strokes = await c.$$eval('[data-testid="hold-map"]', (els) => els.map((e) => ({ live: e.getAttribute('data-live'), cls: [...e.querySelectorAll('svg path')].map((p) => p.getAttribute('class')).filter((x) => /^ln /.test(x ?? '')).join() })));
		ok('3. …on the map itself the live stretch is a route line, the emulated one a dashed line (never a live road hold)', strokes.find((s) => s.live === 'yes')?.cls.includes('ln-route') === true && strokes.find((s) => s.live === 'no')?.cls.includes('ln-dashed') === true, JSON.stringify(strokes));
		ok('3. the day-graded map fades in over a day placeholder (the thumb is the day grade)', (await c.$$eval('[data-testid="hold-map"] [data-v3="map-thumb"]', (e) => e.length)) === 2);
		const ink = await contrast(c, ['.kicker', '.strip p', '.hold .seg', '.hold[data-hold-state="now"] .state', '.hold .window', '.consequence', '.provenance', '.subscribe p', '.cta', '.feed-note .note-text', '[data-shell="citizen-bar"] .view', '[data-shell="citizen-bar"] .tier', '.ptag', '.acc-head', '.demo-note']);
		ok('4. EN: every public text ink holds ≥ 4.5:1 on its ground', ink.every((i) => i.ratio === null || i.ratio >= 4.5), ink.map((i) => `${i.s.split(' ').pop()}:${i.ratio}`).join(' '));
		if (SHOTS) await c.screenshot({ path: path.join(SHOTS, 'v3-citizen-en-1366.png') });
		await c.close();

		// ── /citizen at 1920 and the phone widths, EN · HI · MR ──────────────
		for (const [w, h] of [[1920, 1080], [390, 844], [360, 780]]) {
			for (const lang of w === 1920 ? ['en'] : ['en', 'hi', 'mr']) {
				const p = await open('/citizen', { lang, w, h });
				await p.waitForSelector('.hold', { timeout: 30000 });
				await sleep(1200);
				const m = await p.evaluate(() => {
					const rows = [...document.querySelectorAll('.hold')].map((row) => {
						const seg = row.querySelector('.seg');
						const r = seg.getBoundingClientRect();
						const overlaps = [...row.querySelectorAll('.window, .state')].filter((el) => {
							const o = el.getBoundingClientRect();
							return Math.min(r.right, o.right) - Math.max(r.left, o.left) > 1 && Math.min(r.bottom, o.bottom) - Math.max(r.top, o.top) > 1;
						}).length;
						return { box: Math.round(seg.clientWidth), text: seg.scrollWidth, overlaps };
					});
					const badges = [...document.querySelectorAll('.hero .source-badge, .event-card .source-badge, .later-row .source-badge')].map((b) => b.getBoundingClientRect().right <= (b.closest('.hero, .event-card, .later')?.getBoundingClientRect().right ?? 0) + 1);
					const col = document.querySelector('.citizen').getBoundingClientRect();
					return { rows, badges, spill: document.documentElement.scrollWidth - window.innerWidth, scroller: (() => { const s = document.querySelector('.citizen-page'); return s.scrollWidth - s.clientWidth; })(), colW: Math.round(col.width), langAttr: document.documentElement.lang };
				});
				ok(`2. ${w} px ${lang}: every hold row readable (no clip, no overlap), every badge inside its card, no sideways scroll, one column`, m.rows.length >= 2 && m.rows.every((r) => r.text <= r.box + 1 && r.overlaps === 0 && r.box >= 48) && m.badges.every(Boolean) && m.spill <= 1 && m.scroller <= 1 && m.colW <= 592, JSON.stringify({ rows: m.rows, spill: m.spill, colW: m.colW }));
				if (lang !== 'en') {
					const script = lang === 'hi' ? HI : MR;
					ok(`2. ${w} px ${lang}: the page speaks ${lang} (<html lang>, the title)`, m.langAttr === lang && script.test(await p.$eval('.kicker', (e) => e.textContent)));
					const ink2 = await contrast(p, ['.kicker', '.strip p', '.hold .seg', '.hold .window', '.consequence', '.cta']);
					ok(`4. ${lang}: public text inks hold ≥ 4.5:1`, ink2.every((i) => i.ratio === null || i.ratio >= 4.5), ink2.map((i) => i.ratio).join(' '));
				}
				if (SHOTS) await p.screenshot({ path: path.join(SHOTS, `v3-citizen-${lang}-${w}.png`), fullPage: false });
				await p.close();
			}
		}

		// ── /driver · idle, live ─────────────────────────────────────────────
		feedEvents = [fx.stub];
		feedLater = [];
		const d = await open('/driver', { w: 390, h: 844 });
		await d.waitForSelector('[data-screen="driver"][data-mode="live"]', { timeout: 30000 });
		await sleep(800);
		const idle = await d.evaluate(() => {
			const box = (s) => document.querySelector(s)?.getBoundingClientRect();
			const fs = (s) => parseFloat(getComputedStyle(document.querySelector(s)).fontSize);
			const chips = [...document.querySelectorAll('.urg')].map((b) => ({ h: Math.round(b.getBoundingClientRect().height), fs: parseFloat(getComputedStyle(b).fontSize) }));
			return {
				lang: document.documentElement.lang,
				h1: document.querySelector('.head h1').textContent,
				clock: fs('.golden-clock'),
				started: document.querySelector('[data-testid="golden-hour"]').getAttribute('data-started'),
				steps: document.querySelectorAll('[data-testid="phase-rail"] .step').length,
				stepDot: Math.round(box('.step .dot').width),
				chips,
				btn: Math.round(box('[data-testid="request-btn"]').height),
				spill: document.documentElement.scrollWidth - window.innerWidth,
				select: Math.round(box('[data-testid="stretch-select"]').right) <= Math.round(box('.request-card').right),
			};
		});
		ok('5. /driver speaks English by default (no language chosen)', idle.lang === 'en' && /Green corridor/.test(idle.h1), idle.lang);
		ok('5. the golden-hour clock is the hero (≥ 56 px) and has not started before a request', idle.clock >= 56 && idle.started === '0', `${idle.clock}px started=${idle.started}`);
		ok('5. the phase rail is four large steps (≥ 44 px)', idle.steps === 4 && idle.stepDot >= 44, `${idle.steps} steps · ${idle.stepDot}px`);
		ok('5. urgency chips ≥ 44 px tall with ≥ 16 px type; the one request button ≥ 56 px', idle.chips.length === 4 && idle.chips.every((x) => x.h >= 44 && x.fs >= 16) && idle.btn >= 56, JSON.stringify({ chips: idle.chips[0], btn: idle.btn }));
		ok('5. the stretch picker stays inside its card; no sideways scroll at 390 px', idle.select && idle.spill <= 1);
		const inkD = await contrast(d, ['.head h1', '.head p', '.lbl', '.big', '.golden-clock', '.golden-elapsed', '.mode-note .note-text', '.control-room p', '.baseline']);
		ok('4. /driver (Marathi): text inks hold ≥ 4.5:1 on their ground', inkD.every((i) => i.ratio === null || i.ratio >= 4.5), inkD.map((i) => `${i.s}:${i.ratio}`).join(' '));
		await d.select('[data-testid="stretch-select"]', `${fx.stub.event_id}|1003`);
		await d.type('[data-testid="unit-input"]', '108-14');
		await sleep(200);
		const before = posts.length;
		await d.click('[data-testid="request-btn"]');
		await d.waitForSelector('[data-testid="awaiting-officer"]', { timeout: 15000 });
		await sleep(500);
		ok('6. the live request files ONE POST (answered in the browser) and waits for the officer', posts.length === before + 1);
		ok('6. …there is NO approve control on the page (the officer decides elsewhere)', (await d.$$eval('[data-screen="driver"] button', (els) => els.filter((b) => /approve|मंजूर करा|मंज़ूर/i.test(b.textContent ?? '')).length)) === 0);
		await d.waitForSelector('[data-testid="window-open"], [data-testid="window-primed"]', { timeout: 30000 });
		await d.waitForSelector('[data-testid="window-open"]', { timeout: 30000 });
		const open1 = await d.evaluate(() => ({
			cd: Number(document.querySelector('[data-countdown]').getAttribute('data-countdown')),
			cdPx: parseFloat(getComputedStyle(document.querySelector('.cd-n')).fontSize),
			border: getComputedStyle(document.querySelector('[data-testid="window-open"]')).borderTopColor,
			unit: document.querySelector('[data-testid="window-open"] .unit').textContent.trim(),
			mark: /[A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{4}/.test(document.body.innerText),
		}));
		ok('6. the window opens with its countdown in big type; the unit is labelled EMULATED; no registration mark on the page', open1.cd > 0 && open1.cd <= 100 && open1.cdPx >= 56 && /EMULATED|emulated/i.test(open1.unit) && !open1.mark, JSON.stringify(open1));
		ok('6. the open window is the clear green (108 corridor), with words', (await d.evaluate(() => getComputedStyle(document.querySelector('[data-testid="window-open"]')).borderTopColor)) !== 'rgba(0, 0, 0, 0)' && /rgb\(30, 158, 90\)/.test(open1.border), open1.border);
		if (SHOTS) await d.screenshot({ path: path.join(SHOTS, 'v3-driver-window-mr-390.png') });
		await d.close();

		// ── /driver · the scripted fallback files nothing ─────────────────────
		feedEvents = [];
		const postsBefore = posts.length;
		const s = await open('/driver', { lang: 'en', w: 390, h: 844 });
		await s.waitForSelector('[data-screen="driver"][data-mode="scripted"]', { timeout: 30000 });
		const note = await s.$eval('[data-testid="scripted-note"]', (e) => e.textContent.replace(/\s+/g, ' ').trim());
		ok('7. the scripted fallback is labelled (the honesty note stays)', /scripted|demo/i.test(note) && /nothing|not sent|no duty officer/i.test(note), note.slice(0, 110));
		await s.select('[data-testid="stretch-select"]', await s.$eval('[data-testid="stretch-select"] option:not([value=""])', (o) => o.value));
		await s.click('[data-testid="request-btn"]');
		await s.waitForSelector('[data-testid="window-open"]', { timeout: 30000 });
		ok('7. …a scripted run files NOTHING (zero POSTs) and reaches its open window', posts.length === postsBefore);
		await s.close();

		// ── /welcome · the landing (V3-LANDING) ──────────────────────────────
		const welcomeFrom = calls.length;
		for (const [w, h] of [[1920, 1080], [1366, 768], [390, 844]]) {
			for (const lang of ['en', 'hi', 'mr']) {
				const p = await open('/welcome', { lang, w, h });
				await p.waitForSelector('[data-testid="landing"]', { timeout: 30000 });
				await sleep(1400); // the poster's entrance (≤ 1.4 s) settles
				const m = await p.evaluate(() => {
					const q = (sel) => document.querySelector(sel);
					const box = (sel) => q(sel)?.getBoundingClientRect() ?? null;
					const inView = (sel) => {
						const b = box(sel);
						return !!b && b.top >= 0 && b.bottom <= innerHeight && b.height > 0;
					};
					return {
						theme: document.documentElement.dataset.theme,
						lang: document.documentElement.lang,
						promise: q('[data-testid="land-promise"]')?.textContent ?? '',
						heroH: Math.round(box('[data-testid="land-hero"]')?.height ?? 0),
						poster: ['.lockup img', '[data-testid="land-promise"]', '[data-testid="land-cta-console"]', '[data-testid="land-cta-road"]', '[data-testid="land-hero-shot"]'].map(inView),
						shells: document.querySelectorAll('[data-shell="v3"], [data-v3="rail"], [data-v3="top-bar"], [data-testid="v3-officer"], [data-shell="citizen"]').length,
						spill: document.documentElement.scrollWidth - innerWidth,
						doors: [...document.querySelectorAll('[data-testid="land-cta-console"], [data-testid="land-cta-road"]')].map((a) => `${a.getAttribute('href')}${a.hasAttribute('data-sveltekit-reload') ? ' reload' : ''}`).join(),
						consoleReload: [...document.querySelectorAll('a[href="/"], a[href="/analyst"]')].every((a) => a.hasAttribute('data-sveltekit-reload')),
						photoCaps: [...document.querySelectorAll('[data-testid="v3-photo-caption"]')].filter((c) => /\S/.test(c.textContent) && c.querySelector('.credit')?.textContent.includes('Wikimedia Commons')).length,
						shotCaps: document.querySelectorAll('[data-testid="land-shot-caption"], [data-testid="land-step-caption"]').length,
						modelled: !!q('[data-testid="land-modelled"] .tag-dashed'),
						mark: /[A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{4}/.test(document.body.innerText),
					};
				});
				const script = lang === 'hi' ? HI : lang === 'mr' ? MR : /^One live picture of Kolkata's roads/;
				ok(`10. ${w} px ${lang}: /welcome is night, speaks ${lang}, wears no shell, no sideways scroll`, m.theme === 'command' && m.lang === lang && script.test(m.promise) && m.shells === 0 && m.spill <= 1, JSON.stringify({ theme: m.theme, lang: m.lang, spill: m.spill, shells: m.shells }));
				if (w >= 1366) ok(`10. ${w} × ${h} ${lang}: the first viewport is the poster (lockup, promise, both doors, the console window)`, m.heroH === h && m.poster.every(Boolean), JSON.stringify({ heroH: m.heroH, poster: m.poster }));
				ok(`10. ${w} px ${lang}: the doors (/ reloads, /citizen), honest captions on every picture, the Modelled tag, no registration mark`, m.doors === '/ reload,/citizen' && m.consoleReload && m.photoCaps === 2 && m.shotCaps === 4 && m.modelled && !m.mark, JSON.stringify({ doors: m.doors, photoCaps: m.photoCaps, shotCaps: m.shotCaps }));
				if (w === 1920 && lang === 'en') {
					const ink = await contrast(p, ['.eyebrow', '[data-testid="land-promise"]', '.sub', '.rule', '.cap', '.statement', '.fig-label', '.modelled', '.step-body', '.person-body', '.seat', '.principle-body', '.base-body', '.marks-credit', '.foot-credits p', '.nav-links a']);
					ok('10. /welcome text inks hold ≥ 4.5:1 on the night ground', ink.every((i) => i.ratio === null || i.ratio >= 4.5), ink.map((i) => `${i.s.split(' ').pop()}:${i.ratio}`).join(' '));
					await p.click('[data-testid="land-lang"] button[lang="mr"]');
					await sleep(900);
					const sw = await p.evaluate(() => ({ lang: document.documentElement.lang, promise: document.querySelector('[data-testid="land-promise"]').textContent, cookie: document.cookie }));
					ok('10. the language switch speaks the pick at once (<html lang>, the promise) and persists it (sajag_lang)', sw.lang === 'mr' && MR.test(sw.promise) && /sajag_lang=mr/.test(sw.cookie), JSON.stringify(sw));
				}
				if (SHOTS) await p.screenshot({ path: path.join(SHOTS, `v3-welcome-${lang}-${w}.png`) });
				await p.close();
			}
		}
		const welcomeApi = calls.slice(welcomeFrom).filter((c) => / \/api\//.test(c) || / \/gods-eye\//.test(c));
		ok('10. /welcome made no API call at all (static content and static pictures)', welcomeApi.length === 0, welcomeApi.slice(0, 4).join(' | '));

		// 8 · no operator call
		const operator = calls.filter((x) => /^(GET|POST) \/api\/v1\/(vehicles|enforcement|dispatches|city|events\/active|units)|^(GET|POST) \/(ops|decide)(\/|$)/.test(x) && !/POST \/api\/v1\/events\/[^/]+\/dispatch/.test(x));
		ok('8. neither public page made an operator API call (only /api/public/*, the segments read and the dispatch the driver files)', operator.length === 0, operator.slice(0, 4).join(' | '));
		ok('9. zero other would-be writes; no page error', writes.length === 0 && errors.filter((e) => !/Failed to fetch|tile/i.test(e)).length === 0, writes.concat(errors).slice(0, 3).join(' | '));
	} finally {
		await browser.close().catch(() => {});
	}
	if (failures > 0) {
		console.error(`v3-public-smoke: ${failures} FAILURE(S)`);
		process.exit(1);
	}
	console.log('ok   v3-public-smoke — all assertions passed');
	process.exit(0);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
