/**
 * /map smoke (V3-P4; V3-SPEC §5.6, §6.5, §6.10, §7.1, §8) — HERMETIC: every same-origin /api/* and /gods-eye/* GET is
 * answered in the browser from Home's fixture world (tests/home-smoke.mjs: a live Class Z movement with its escort
 * proposal, an open pursuit of a stolen vehicle, a work zone, four OSINT reports — one an OFFICIAL district weather
 * warning — three planned events, 28 cameras, a simulated traffic feed); /gods-eye/mode answers 404, so the canvas
 * is keyless (no ion token anywhere); every non-GET is ABORTED and recorded; OSM tiles and every third party are
 * aborted (the canvas falls to its offline schematic — part of the check).
 *
 *   node tests/v3-map-smoke.mjs [deckUrl]          (default http://127.0.0.1:5472; a dev deck of this tree)
 *   V3_SHOTS=<dir> V3_TILES=1 node tests/v3-map-smoke.mjs …   also saves screenshots (tiles allowed: OSM GETs only)
 *
 * Asserts:
 *   1. the page renders: zero page errors; the canvas is up (window.__GODS_EYE__ phase ready, its contract keys all
 *      present) and the V3 chrome around it; NO v2 canvas chrome on /map (no .ge-hud toolbar, no MapNav, no readout);
 *   2. by default: the canvas's layers are exactly events, convoy, traces, enforcement, osint + the live city (flow, cameras, units);
 *   3. counts: each chip's count = its Now group's rows; Needs your decision = selectors.decisionUnits() = the rail's
 *      Decide badge; the fixture's 3 live operations, 4 reports, 3 plans;
 *   4. a chip hides its group: Reported in the city off → the osint layer off and the group gone from the Now list;
 *      on again → back; Live operations off keeps the events layer (Coming up still draws it);
 *   5. the Layers sheet (L): base map choice, Operations and City switches, the Vehicles-only rule; a switch turns
 *      the canvas layer on (cameras) with its provenance in words (Emulated); Esc closes the sheet first;
 *   6. selection: a Now row selects the object everywhere (__GODS_EYE__.selection.urn) and fills the card: ≤ 2 tags,
 *      ≤ 3 figures, the movement's primary verb "Review the hold" → /decide/escort-proposal:<id> (its ONE home);
 *      no Approve / Apply anywhere on the page; the card closes (selection cleared);
 *   7. the thermal-style view is ONE button on the main tools, its tooltip "a visual filter, no thermal sensor",
 *      pressed while on, the canvas's sensor follows (flir-whot), the on-map label says what it is; off again → raw;
 *   8. the 3D city without the ion key: the button is disabled with the reason, pressing it changes nothing;
 *   9. tools drive the canvas: measure toggles the canvas tool; zoom in lowers the camera;
 *  10. replay waits while a movement is live (disabled, the reason in words);
 *  11. honesty: no raw registration mark in innerText without an officer (masked chips with their lock); naming an
 *      officer unmasks; clearing masks again; the official weather warning is a chip, never a news report;
 *  12. keys: no key sends anything (a press of every letter and Enter → zero non-GET);
 *  13. HI and MR: the chips and the Now header are translated (not the English words);
 *  14. 1366×768: the Now panel is 320 px, follow and north step back, the legend hides; nothing overlaps (chips,
 *      Now panel, tools, card);
 *  15. zero non-GET requests leave the browser: every one is aborted, and none but the flow layer's read is sent.
 *
 * The colleague's review (V3-P4 round 2):
 *  R1. focus mode: selecting an event frames it and dims the rest (canvas MapView.focus); "Focused on … · Show all"
 *      appears, and Show all clears the selection and returns to the city;
 *  R2. corridor stats in their own collapsible panel, closed by default, opened from the map tools, in the left
 *      column: signal band, corridor traffic, escorts — no figure repeats the selection card's, no table;
 *  R3. the legend is terse (≤ 4 words a line) and the officer shows / hides it from the toolbar; no threat posture;
 *  R4. the layers and options panel is on the LEFT;
 *  R5. no audit or analysis table on /map;
 *  R6. every overlay is on the glass surface (translucent where the browser can blur, else solid), and every text
 *      on it keeps ≥ 4.5:1 composited over the darkest (black) AND the lightest (white) map pixel;
 *  R7. the shell is identical on every V3 page: the rail items and the top bar's search, language and officer
 *      controls sit at the same pixels on /home, /decide, /map and /assistant, at 1920 and at 1366.
 *
 * Exit 0 with `ok <name>` lines; exit 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { homeFixtures } from './home-smoke.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const base = (process.argv[2] ?? 'http://127.0.0.1:5472').replace(/\/$/, '');
const origin = new URL(base).origin;
if (/:(5273|8090|8091|8092)$/.test(origin)) {
	console.error('refusing a live port');
	process.exit(2);
}
const SHOTS = process.env.V3_SHOTS ? path.resolve(process.env.V3_SHOTS) : null;
const TILES = process.env.V3_TILES === '1';
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

const fx = homeFixtures(Date.now());
const E = fx.expect;
const writes = [];
const errors = [];
const HOOK_KEYS = ['phase', 'imageryMode', 'imageryNote', 'tilesLoaded', 'entityCount', 'distinctLayerIds', 'stats', 'offlineDetected', 'sensorMode', 'camera', 'orbiting', 'selectedEventId', 'subjectLockId', 'picked', 'amaAgeSec', 'pursuitEntities', 'layerStats', 'selection', 'registry', 'replay', 'vitals', 'locate', 'ready'];
const DEFAULTS = ['events', 'convoy', 'traces', 'enforcement', 'osint', 'flow', 'cameras', 'units', 'waterlog'];

const browser = await puppeteer.launch({
	executablePath: CHROME,
	headless: 'new',
	args: ['--no-sandbox', '--disable-dev-shm-usage', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--use-gl=angle', '--ignore-gpu-blocklist', '--window-size=1920,1080'],
});

async function openMap(page, { lang = 'en', w = 1920, h = 1080 } = {}) {
	await page.setViewport({ width: w, height: h });
	await page.setCookie({ name: 'sajag_lang', value: lang, url: origin });
	await page.goto(`${base}/map`, { waitUntil: 'networkidle2', timeout: 120_000 }).catch(() => {});
	await page.waitForFunction(() => window.__V3_MAP__?.ready && window.__GODS_EYE__?.phase === 'ready', { timeout: 120_000 }).catch(() => {});
	await page.waitForFunction(() => (window.__V3_MAP__?.counts?.decide ?? 0) >= 4 && (window.__V3_MAP__?.counts?.live ?? 0) >= 3, { timeout: 30_000 }).catch(() => {});
	await sleep(2500);
}

const shot = async (page, name) => {
	if (SHOTS) await page.screenshot({ path: path.join(SHOTS, name) });
};

try {
	const page = await browser.newPage();
	page.on('pageerror', (e) => errors.push(e.message.slice(0, 240)));
	await page.setRequestInterception(true);
	page.on('request', (req) => {
		const u = new URL(req.url());
		const m = req.method();
		if (!['GET', 'HEAD', 'OPTIONS'].includes(m)) {
			writes.push(`${m} ${u.origin === origin ? u.pathname : u.host}`);
			return req.abort();
		}
		if (u.origin === origin && (u.pathname.startsWith('/api/') || u.pathname.startsWith('/gods-eye/'))) {
			const a = fx.answer(u.pathname + u.search);
			return req.respond(
				a ? { status: a.status, contentType: 'application/json', body: JSON.stringify(a.body) } : { status: 404, contentType: 'application/json', body: '{"detail":"Not Found"}' },
			);
		}
		if (u.origin !== origin) {
			if (TILES && /(^|\.)tile\.openstreetmap\.org$/.test(u.host)) return req.continue();
			return req.abort();
		}
		return req.continue();
	});
	await page.evaluateOnNewDocument(() => {
		try {
			localStorage.setItem('sajag.v3.onboarded', '1');
		} catch {
			// storage unavailable
		}
	});

	// ── 1–3: renders, the contract, clean defaults, counts ──────────────────
	await openMap(page);
	const s1 = await page.evaluate((keys) => {
		const g = window.__GODS_EYE__ ?? {};
		const m = window.__V3_MAP__ ?? {};
		const rows = [...document.querySelectorAll('[data-testid="v3-now-row"]')].map((r) => r.getAttribute('data-group'));
		const chip = (g) => Number(document.querySelector(`[data-testid="v3-map-chips"] [data-group="${g}"]`)?.getAttribute('data-count') ?? NaN);
		return {
			phase: g.phase,
			missing: keys.filter((k) => !(k in g)),
			layers: [...(g.distinctLayerIds ?? [])].sort(),
			v2Toolbar: !!document.querySelector('.ge-hud .toolbar, .v2-nav, .v2-readout, [data-testid="map-toolbar"]'),
			chrome: !!document.querySelector('[data-testid="v3-map-chips"]') && !!document.querySelector('[data-testid="v3-now"]') && !!document.querySelector('[data-testid="v3-map-tools"]'),
			hook: m,
			rowsBy: { live: rows.filter((x) => x === 'live').length, decide: rows.filter((x) => x === 'decide').length, reported: rows.filter((x) => x === 'reported').length, planned: rows.filter((x) => x === 'planned').length },
			chips: { live: chip('live'), decide: chip('decide'), reported: chip('reported'), planned: chip('planned') },
			badge: Number(document.querySelector('[data-testid="v3-decide-badge"]')?.getAttribute('data-count') ?? NaN),
			weather: document.querySelector('[data-testid="v3-weather"]')?.textContent ?? null,
			text: document.body.innerText,
			legend: !!document.querySelector('[data-testid="v3-legend"]'),
		};
	}, HOOK_KEYS);
	ok('1. the canvas is up under chrome v3 (phase ready) and its __GODS_EYE__ contract is whole', s1.phase === 'ready' && s1.missing.length === 0, s1.missing.length ? `missing ${s1.missing.join(',')}` : 'all keys');
	ok('1. the V3 chrome is there (chips, Now, tools) and NO v2 canvas chrome renders on /map', s1.chrome && !s1.v2Toolbar);
	ok('2. by default: events, convoy, traces, enforcement, osint + flow, cameras, units and the waterlogging nowcast — nothing else', JSON.stringify(s1.layers) === JSON.stringify([...DEFAULTS].sort()), s1.layers.join(','));
	ok('3. each chip counts its Now group', ['live', 'decide', 'reported', 'planned'].every((g) => s1.chips[g] === s1.rowsBy[g]), JSON.stringify({ chips: s1.chips, rows: s1.rowsBy }));
	ok('3. Needs your decision = selectors.decisionUnits() = the Decide badge', s1.chips.decide === s1.hook?.canonical?.decisions && s1.badge === s1.chips.decide && s1.chips.decide === E.units, `${s1.chips.decide} / ${s1.hook?.canonical?.decisions} / ${s1.badge}`);
	ok('3. the fixture world: 3 live operations, 4 reports, 3 plans', s1.rowsBy.live === E.liveOps && s1.rowsBy.reported === E.reports && s1.rowsBy.planned === E.planned, JSON.stringify(s1.rowsBy));
	ok('11. the official district weather warning is a chip (never a ring, never a news report)', !!s1.weather && /Official weather warning/.test(s1.weather), s1.weather ?? 'none');
	ok('11. no raw registration mark without an officer; the masked one shows', !s1.text.includes(E.rawPlate) && s1.text.includes(E.maskedPlate));
	ok('1. the three-line legend shows at 1920', s1.legend);
	await shot(page, 'map-1920-en.png');

	// ── 4: a chip hides its group ───────────────────────────────────────────
	await page.click('[data-testid="v3-map-chips"] [data-group="reported"]');
	await sleep(1200);
	const s4 = await page.evaluate(() => ({
		layers: window.__GODS_EYE__?.distinctLayerIds ?? [],
		pressed: document.querySelector('[data-testid="v3-map-chips"] [data-group="reported"]')?.getAttribute('aria-pressed'),
		group: !!document.querySelector('[data-testid="v3-now"] [data-group="reported"]'),
		wx: !!document.querySelector('[data-testid="v3-weather"]'),
	}));
	ok('4. Reported in the city off: the osint layer stands down, the group and the weather chip leave', !s4.layers.includes('osint') && s4.pressed === 'false' && !s4.group && !s4.wx, JSON.stringify(s4));
	await page.click('[data-testid="v3-map-chips"] [data-group="reported"]');
	await page.click('[data-testid="v3-map-chips"] [data-group="live"]');
	await sleep(1200);
	const s4b = await page.evaluate(() => window.__GODS_EYE__?.distinctLayerIds ?? []);
	ok('4. back on: osint returns; Live operations off drops convoy and traces but keeps events (Coming up draws them)', s4b.includes('osint') && !s4b.includes('convoy') && !s4b.includes('traces') && s4b.includes('events'), s4b.join(','));
	await page.click('[data-testid="v3-map-chips"] [data-group="live"]');
	await sleep(800);

	// ── 5: the Layers sheet ─────────────────────────────────────────────────
	await page.keyboard.press('l');
	await page.waitForSelector('[data-testid="v3-layers-sheet"]', { timeout: 5000 }).catch(() => {});
	const s5 = await page.evaluate(() => {
		const sh = document.querySelector('[data-testid="v3-layers-sheet"]');
		return {
			open: !!sh,
			base: sh?.querySelectorAll('[role="radio"]').length ?? 0,
			switches: [...(sh?.querySelectorAll('[role="switch"]') ?? [])].map((x) => x.getAttribute('data-layer')),
			rule: sh?.textContent?.includes('Vehicles only') ?? false,
			faces: sh?.textContent?.includes('no images, frames or faces are kept') ?? false,
		};
	});
	ok('5. L opens the Layers sheet: base map (2), the eleven switches (seven city layers, waterlogging and the forecast, air quality and the cyclone), the Vehicles-only rule', s5.open && s5.base === 2 && s5.switches.length === 11 && s5.switches.includes('waterlog') && s5.switches.includes('forecast') && s5.switches.includes('air') && s5.switches.includes('cyclone') && s5.rule && s5.faces, JSON.stringify(s5));
	await page.click('[data-testid="v3-layers-sheet"] [data-layer="signals"]');
	await sleep(2500);
	const s5b = await page.evaluate(() => ({
		layers: window.__GODS_EYE__?.distinctLayerIds ?? [],
		checked: document.querySelector('[data-testid="v3-layers-sheet"] [data-layer="signals"]')?.getAttribute('aria-checked'),
		row: document.querySelector('[data-layer-row="signals"]')?.textContent ?? '',
		count: document.querySelector('[data-testid="v3-map-layers"]')?.textContent ?? '',
	}));
	ok('5. a switch turns the canvas layer on (junctions and signals), its row in words', s5b.layers.includes('signals') && s5b.checked === 'true' && /Junctions and signals/.test(s5b.row), s5b.row.replace(/\s+/g, ' ').trim());
	ok('5. the Layers chip says how many extra layers are on (the three live-city layers, waterlogging + the one switched on)', /5 on/.test(s5b.count), s5b.count.trim());
	await shot(page, 'map-1920-layers.png');
	await page.keyboard.press('Escape');
	await sleep(400);
	ok('5. Esc closes the sheet first', !(await page.$('[data-testid="v3-layers-sheet"]')));
	await page.keyboard.press('l');
	await page.waitForSelector('[data-testid="v3-layers-sheet"] [data-layer="signals"]', { timeout: 5000 }).catch(() => {});
	await page.click('[data-testid="v3-layers-sheet"] [data-layer="signals"]').catch(() => {});
	await page.keyboard.press('Escape');
	await sleep(600);

	// ── 6: selection → card → its one home ──────────────────────────────────
	const moveUrn = `event:${E.ids.movementEvent}`;
	await page.click(`[data-testid="v3-now-row"][data-urn="${moveUrn}"][data-group="live"]`);
	await page.waitForSelector('[data-testid="v3-selection"]', { timeout: 8000 }).catch(() => {});
	await sleep(1500);
	const s6 = await page.evaluate(() => {
		const c = document.querySelector('[data-testid="v3-selection"]');
		return {
			sel: window.__GODS_EYE__?.selection?.urn ?? null,
			tags: c?.querySelectorAll('.tags > *').length ?? 0,
			stats: c?.querySelectorAll('.stat').length ?? 0,
			primary: c?.querySelector('[data-testid="v3-selection-primary"]')?.getAttribute('href') ?? null,
			primaryText: c?.querySelector('[data-testid="v3-selection-primary"]')?.textContent?.trim() ?? '',
			follow: !!c?.querySelector('[data-testid="v3-selection-follow"]'),
			details: c?.querySelector('[data-testid="v3-selection-details"]')?.getAttribute('href') ?? '',
			current: document.querySelector('[data-testid="v3-now-row"][aria-current="true"]')?.getAttribute('data-urn'),
			verbs: [...document.querySelectorAll('button, a')].map((b) => b.textContent?.trim() ?? '').filter((x) => /^(approve|apply)\b/i.test(x)),
		};
	});
	ok('6. a Now row selects the object everywhere and marks the row', s6.sel === moveUrn && s6.current === moveUrn, `${s6.sel}`);
	ok('6. the card: ≤ 2 tags, 1–3 figures from the convoy feed, Follow, Details', s6.tags >= 1 && s6.tags <= 2 && s6.stats >= 1 && s6.stats <= 3 && s6.follow && s6.details.includes(E.ids.movementEvent), JSON.stringify({ tags: s6.tags, stats: s6.stats }));
	ok('6. the primary verb opens the hold in Decide (its ONE home)', /^\/decide\/escort-proposal%3A/.test(s6.primary ?? '') && /Review the hold/.test(s6.primaryText), `${s6.primary} · ${s6.primaryText}`);
	ok('6. no Approve and no Apply anywhere on /map', s6.verbs.length === 0, s6.verbs.join(','));
	await shot(page, 'map-1920-selection.png');
	await page.click('[data-testid="v3-selection-close"]');
	await sleep(600);
	ok('6. closing the card clears the selection', (await page.evaluate(() => window.__GODS_EYE__?.selection?.urn ?? null)) === null && !(await page.$('[data-testid="v3-selection"]')));

	// ── R1: focus mode — a selected event is framed, the rest steps back, "Show all" returns to the city ──
	await page.click(`[data-testid="v3-now-row"][data-urn="${moveUrn}"][data-group="live"]`);
	await page.waitForSelector('[data-testid="v3-focus"]', { timeout: 8000 }).catch(() => {});
	await page.waitForFunction(() => ['landed', 'no-position', 'cancelled'].includes(window.__GODS_EYE__?.selection?.flyOutcome), { timeout: 15_000 }).catch(() => {});
	await sleep(1500);
	const f1 = await page.evaluate(() => ({ text: document.querySelector('[data-testid="v3-focus"]')?.textContent ?? '', cam: window.__GODS_EYE__?.camera ?? null, sel: window.__GODS_EYE__?.selection ?? {} }));
	ok('R1. selecting an event enters focus mode: "Focused on …" with Show all; the camera flew to frame it', /Focused on/.test(f1.text) && /Show all/.test(f1.text) && f1.sel.urn === moveUrn && f1.sel.flyOutcome === 'landed', `${f1.text.trim()} · fly ${f1.sel.flyOutcome}`);
	await shot(page, 'map-1920-focus.png');
	await page.click('[data-testid="v3-show-all"]');
	await sleep(3000);
	const f2 = await page.evaluate(() => ({ focus: !!document.querySelector('[data-testid="v3-focus"]'), sel: window.__GODS_EYE__?.selection?.urn ?? null, card: !!document.querySelector('[data-testid="v3-selection"]'), cam: window.__GODS_EYE__?.camera ?? null }));
	const moved = f1.cam && f2.cam && (Math.abs(f1.cam.alt - f2.cam.alt) > 50 || Math.abs(f1.cam.lon - f2.cam.lon) > 0.002 || Math.abs(f1.cam.lat - f2.cam.lat) > 0.002);
	ok('R1. Show all clears the focus and the selection and the camera returns to the city', !f2.focus && f2.sel === null && !f2.card && moved, `${JSON.stringify({ focus: f2.focus, sel: f2.sel })} · alt ${Math.round(f1.cam?.alt ?? 0)} → ${Math.round(f2.cam?.alt ?? 0)}`);

	// ── R2: corridor stats — closed by default, from the toolbar, figures never repeated ──
	const st0 = await page.evaluate(() => ({ open: !!document.querySelector('[data-testid="v3-stats"]'), pressed: document.querySelector('[data-map-tool="stats"]')?.getAttribute('aria-pressed') }));
	ok('R2. the corridor stats panel is closed by default', !st0.open && st0.pressed === 'false');
	await page.click(`[data-testid="v3-now-row"][data-urn="${moveUrn}"][data-group="live"]`);
	await sleep(1500);
	await page.click('[data-map-tool="stats"]');
	await page.waitForSelector('[data-testid="v3-stats"]', { timeout: 5000 }).catch(() => {});
	await sleep(1200);
	const st1 = await page.evaluate(() => {
		const p = document.querySelector('[data-testid="v3-stats"]');
		const r = p?.getBoundingClientRect();
		const m = window.__V3_MAP__ ?? {};
		const key = (x) => `${x.value}|${x.label}`;
		const card = new Set((m.cardFigures ?? []).map(key));
		const chips = [...document.querySelectorAll('[data-testid="v3-map-chips"] [data-count]')].map((c) => c.getAttribute('data-count'));
		return {
			open: !!p,
			left: r ? Math.round(r.left) : null,
			sections: [...(p?.querySelectorAll('[data-stats-section]') ?? [])].map((x) => x.getAttribute('data-stats-section')),
			figures: (m.statFigures ?? []).map(key),
			repeats: (m.statFigures ?? []).filter((x) => card.has(key(x))).map(key),
			table: !!document.querySelector('[data-v3="map"] table'),
			text: p?.textContent ?? '',
			chips,
		};
	});
	ok('R2. the toolbar opens it, in the LEFT column: signal band, corridor traffic, escorts', st1.open && st1.left != null && st1.left < 400 && JSON.stringify(st1.sections) === JSON.stringify(['band', 'traffic', 'escorts']), JSON.stringify(st1.sections));
	ok('R2. no figure repeats the selection card’s; the provenance is in words; no table', st1.repeats.length === 0 && /Simulated|Not read yet|No fresh/.test(st1.text) && !st1.table, `${st1.figures.length} figures · repeats ${st1.repeats.join(',') || 'none'}`);
	await shot(page, 'map-1920-stats.png');
	await page.click('[data-map-tool="stats"]');
	await page.click('[data-testid="v3-selection-close"]').catch(() => {});
	await sleep(600);

	// ── R3: the legend — terse, shown or hidden by the officer ──
	const lg0 = await page.evaluate(() => ({ shown: !!document.querySelector('[data-testid="v3-legend"]'), lines: [...document.querySelectorAll('[data-testid="v3-legend"] span')].map((x) => x.textContent.trim()) }));
	await page.click('[data-map-tool="legend"]');
	await sleep(400);
	const lg1 = await page.evaluate(() => !!document.querySelector('[data-testid="v3-legend"]'));
	await page.click('[data-map-tool="legend"]');
	await sleep(400);
	ok('R3. the legend: three terse lines (≤ 4 words), hidden and shown again from the toolbar', lg0.shown && lg0.lines.length === 3 && lg0.lines.every((l) => l.split(/\s+/).length <= 4) && !lg1 && (await page.evaluate(() => !!document.querySelector('[data-testid="v3-legend"]'))), JSON.stringify(lg0.lines));
	ok('R3. no threat-posture block on /map', !(await page.evaluate(() => /threat posture|posture|AMA [A-Z]/i.test(document.querySelector('[data-v3="map"]')?.innerText ?? ''))));

	// ── R4 + R6: the layers panel on the LEFT; every overlay on glass, contrast held ──
	await page.click('[data-testid="v3-map-layers"]');
	await page.waitForSelector('[data-testid="v3-layers-sheet"]', { timeout: 5000 }).catch(() => {});
	await page.click(`[data-testid="v3-now-row"][data-urn="${moveUrn}"][data-group="live"]`);
	await sleep(1500);
	const g = await page.evaluate(() => {
		const rgba = (c) => {
			const m = /rgba?\(([^)]+)\)/.exec(c);
			const p = m ? m[1].split(',').map((x) => parseFloat(x)) : [0, 0, 0, 0];
			return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
		};
		const lum = ([r, gg, b]) => {
			const f = (v) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
			return 0.2126 * f(r) + 0.7152 * f(gg) + 0.0722 * f(b);
		};
		const cr = (a, b) => (Math.max(lum(a), lum(b)) + 0.05) / (Math.min(lum(a), lum(b)) + 0.05);
		const sels = { layers: '[data-testid="v3-layers-sheet"]', now: '[data-testid="v3-now"]', card: '[data-testid="v3-selection"]', legend: '[data-testid="v3-legend"]', tools: '[data-map-tool="measure"]' };
		const out = {};
		for (const [k, sel] of Object.entries(sels)) {
			const el = document.querySelector(sel);
			if (!el) {
				out[k] = null;
				continue;
			}
			const bg = rgba(getComputedStyle(el).backgroundColor);
			let worst = 99;
			for (const t of el.querySelectorAll('*')) {
				if (!t.childNodes.length || ![...t.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
				if (t.closest('[data-tone], .stat, .fig, button.primary, .btn.primary, .is-pressed, .sw2')) continue;
				const fg = rgba(getComputedStyle(t).color);
				for (const under of [[0, 0, 0], [255, 255, 255]]) {
					const comp = [0, 1, 2].map((i) => bg[i] * bg[3] + under[i] * (1 - bg[3]));
					worst = Math.min(worst, cr(fg, comp));
				}
			}
			out[k] = { glass: el.classList.contains('v3-glass'), alpha: bg[3], worst: Math.round(worst * 100) / 100, left: Math.round(el.getBoundingClientRect().left) };
		}
		out.mode = document.querySelector('[data-v3="map"]')?.getAttribute('data-glass');
		return out;
	});
	ok('R4. the layers and options panel is on the LEFT side of the map', g.layers && g.layers.left < 400, JSON.stringify(g.layers));
	ok('R6. every overlay (layers, Now list, card, legend, tools) is on the glass surface', ['layers', 'now', 'card', 'legend', 'tools'].every((k) => g[k]?.glass), JSON.stringify(Object.fromEntries(Object.entries(g).map(([k, v]) => [k, v?.glass ?? v]))));
	ok('R6. the glass is translucent where the browser can blur (else solid) and every text on it holds ≥ 4.5:1 over the darkest AND the lightest map pixel', ['layers', 'now', 'card', 'legend'].every((k) => g[k] && g[k].worst >= 4.5 && (g.mode === 'blur' ? g[k].alpha < 1 && g[k].alpha >= 0.85 : g[k].alpha === 1)), JSON.stringify({ mode: g.mode, ...Object.fromEntries(['layers', 'now', 'card', 'legend'].map((k) => [k, g[k] && [g[k].alpha, g[k].worst]])) }));
	await shot(page, 'map-1920-glass.png');
	await page.click('[data-testid="v3-map-layers"]');
	await page.click('[data-testid="v3-selection-close"]').catch(() => {});
	await sleep(600);

	// ── R5: no decision audit or analysis tables on /map ──
	ok('R5. no audit or analysis table on /map (Details and the stats link go to Analyst)', await page.evaluate(() => !document.querySelector('[data-v3="map"] table, [data-testid*="audit"], [data-testid="analysis-dock"]')));

	// ── 7: thermal-style view ───────────────────────────────────────────────
	const th = await page.evaluate(() => {
		const b = [...document.querySelectorAll('[data-map-tool="thermal"]')];
		return { n: b.length, title: b[0]?.getAttribute('title') ?? '', inTools: !!b[0]?.closest('[data-testid="v3-map-tools"]'), pressed: b[0]?.getAttribute('aria-pressed') };
	});
	ok('7. ONE thermal-style button, on the main tools, with the honest tooltip', th.n === 1 && th.inTools && /visual filter/.test(th.title) && /no thermal sensor/.test(th.title) && th.pressed === 'false', th.title);
	await page.click('[data-map-tool="thermal"]');
	await sleep(1200);
	const th2 = await page.evaluate(() => ({
		sensor: window.__GODS_EYE__?.sensorMode,
		pressed: document.querySelector('[data-map-tool="thermal"]')?.getAttribute('aria-pressed'),
		label: document.querySelector('[data-testid="v3-thermal-label"]')?.textContent ?? '',
	}));
	ok('7. on: the canvas sensor is the white-hot filter, the button pressed, the label says "a visual filter, no thermal sensor"', th2.sensor === 'flir-whot' && th2.pressed === 'true' && /visual filter, no thermal sensor/.test(th2.label), JSON.stringify(th2).slice(0, 160));
	await shot(page, 'map-1920-thermal.png');
	await page.click('[data-map-tool="thermal"]');
	await sleep(800);
	ok('7. off again: normal colours, no label', (await page.evaluate(() => window.__GODS_EYE__?.sensorMode)) === 'raw' && !(await page.$('[data-testid="v3-thermal-label"]')));

	// ── 8: 3D without the key ───────────────────────────────────────────────
	const d3 = await page.evaluate(() => {
		const b = document.querySelector('[data-map-tool="3d"]');
		return { dis: b?.getAttribute('aria-disabled'), title: b?.getAttribute('title') ?? '' };
	});
	await page.click('[data-map-tool="3d"]');
	await sleep(800);
	const d3b = await page.evaluate(() => window.__V3_MAP__?.is3d);
	ok('8. no ion key: the 3D city is disabled with its reason, pressing changes nothing', d3.dis === 'true' && /key/i.test(d3.title) && d3b === false, d3.title);

	// ── 9: tools drive the canvas ───────────────────────────────────────────
	await page.click('[data-map-tool="measure"]');
	await sleep(400);
	const meas = await page.evaluate(() => ({ tool: window.__V3_MAP__?.tool, pressed: document.querySelector('[data-map-tool="measure"]')?.getAttribute('aria-pressed') }));
	await page.click('[data-map-tool="measure"]');
	await sleep(300);
	ok('9. measure toggles the canvas tool', meas.tool === 'measure' && meas.pressed === 'true' && (await page.evaluate(() => window.__V3_MAP__?.tool)) === 'select', JSON.stringify(meas));
	const alt0 = await page.evaluate(() => window.__GODS_EYE__?.camera?.alt ?? null);
	await page.click('[data-map-tool="zoom-in"]');
	await sleep(2500);
	const alt1 = await page.evaluate(() => window.__GODS_EYE__?.camera?.alt ?? null);
	ok('9. zoom in lowers the camera', alt0 != null && alt1 != null && alt1 < alt0, `${Math.round(alt0)} → ${Math.round(alt1)} m`);

	// ── 10: replay waits while a movement is live ───────────────────────────
	const rp = await page.evaluate(() => ({
		dis: document.querySelector('[data-testid="v3-now-replay"]')?.getAttribute('aria-disabled'),
		why: document.querySelector('[data-testid="v3-replay-why"]')?.textContent ?? '',
	}));
	await page.click('[data-testid="v3-now-replay"]');
	await sleep(500);
	ok('10. replay waits while a movement is live, the reason in words', rp.dis === 'true' && /movement is live/.test(rp.why) && (await page.evaluate(() => window.__V3_MAP__?.replaying)) === false, rp.why);

	// ── 11: the officer unmasks; clearing masks again ───────────────────────
	await page.click('[data-testid="v3-officer"]');
	await page.waitForSelector('[data-testid="duty-officer"]', { timeout: 5000 }).catch(() => {});
	await page.type('[data-testid="duty-officer"]', 'Sandbox Officer');
	await page.keyboard.press('Escape');
	await page.waitForFunction((raw) => document.body.innerText.includes(raw), { timeout: 8000 }, E.rawPlate).catch(() => {});
	ok('11. a named officer sees the full mark', await page.evaluate((raw) => document.body.innerText.includes(raw), E.rawPlate));
	await page.click('[data-testid="v3-officer"]');
	await page.waitForSelector('[data-testid="duty-officer"]', { timeout: 5000 }).catch(() => {});
	await page.click('[data-testid="duty-officer"]', { clickCount: 3 });
	await page.keyboard.press('Backspace');
	await page.keyboard.press('Escape');
	await page.waitForFunction((raw) => !document.body.innerText.includes(raw), { timeout: 8000 }, E.rawPlate).catch(() => {});
	ok('11. clearing the officer masks it again', !(await page.evaluate((raw) => document.body.innerText.includes(raw), E.rawPlate)));

	// ── 12: no key sends anything ───────────────────────────────────────────
	const before = writes.filter((w) => !w.includes('/api/v1/traffic/live')).length;
	await page.mouse.click(900, 600);
	for (const k of 'abcdeghijkmnopqrstuvwxyz'.split('')) await page.keyboard.press(k);
	await page.keyboard.press('Enter');
	await sleep(1500);
	ok('12. no key sends anything (every letter, Enter)', writes.filter((w) => !w.includes('/api/v1/traffic/live')).length === before, `${writes.length} non-GET`);

	// ── 13: HI and MR ───────────────────────────────────────────────────────
	for (const [lang, word] of [
		['hi', 'चल रहे संचालन'],
		['mr', 'थेट कारवाया'],
	]) {
		await openMap(page, { lang });
		const t = await page.evaluate(() => ({
			chip: document.querySelector('[data-testid="v3-map-chips"] [data-group="live"]')?.textContent ?? '',
			now: document.querySelector('[data-testid="v3-now"] h2')?.textContent ?? '',
			thermal: document.querySelector('[data-map-tool="thermal"]')?.getAttribute('title') ?? '',
		}));
		ok(`13. ${lang.toUpperCase()}: the chips, the Now header and the thermal tooltip are translated`, t.chip.includes(word) && t.now !== 'Now' && !/Thermal-style/.test(t.thermal), `${t.chip.trim()} · ${t.now}`);
		await shot(page, `map-1920-${lang}.png`);
	}

	// ── 14: 1366 ────────────────────────────────────────────────────────────
	await openMap(page, { w: 1366, h: 768 });
	await page.click(`[data-testid="v3-now-row"][data-group="decide"]`).catch(() => {});
	await sleep(2000);
	const s14 = await page.evaluate(() => {
		const r = (s) => document.querySelector(s)?.getBoundingClientRect() ?? null;
		const vis = (s) => {
			const e = document.querySelector(s);
			return !!e && getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 0;
		};
		const boxes = { chips: r('[data-testid="v3-map-chips"]'), now: r('[data-testid="v3-now"]'), tools: r('[data-testid="v3-map-tools"]'), card: r('[data-testid="v3-selection"]') };
		const hit = (a, b) => a && b && a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
		const names = Object.keys(boxes);
		const overlaps = [];
		for (let i = 0; i < names.length; i++) for (let j = i + 1; j < names.length; j++) if (hit(boxes[names[i]], boxes[names[j]])) overlaps.push(`${names[i]}×${names[j]}`);
		return { nowW: Math.round(boxes.now?.width ?? 0), follow: vis('[data-map-tool="follow"]'), north: vis('[data-map-tool="north"]'), legend: vis('[data-testid="v3-legend"]'), card: !!boxes.card, overlaps };
	});
	ok('14. 1366: the Now panel is 320 px, follow and north step back, the legend hides', s14.nowW === 320 && !s14.follow && !s14.north && !s14.legend, JSON.stringify(s14));
	ok('14. 1366: chips, Now panel, tools and the card never overlap', s14.card && s14.overlaps.length === 0, s14.overlaps.join(',') || 'clear');
	await shot(page, 'map-1366-en.png');

	// ── R7: the shell is identical on every V3 page (rail, top bar, positions) ──
	for (const [w, h] of [
		[1920, 1080],
		[1366, 768],
	]) {
		const geo = {};
		for (const route of ['/home', '/decide', '/map', '/assistant']) {
			await page.setViewport({ width: w, height: h });
			await page.goto(`${base}${route}`, { waitUntil: 'networkidle2', timeout: 120_000 }).catch(() => {});
			await page.waitForSelector('[data-v3="top-bar"]', { timeout: 30_000 }).catch(() => {});
			await sleep(1500);
			geo[route] = await page.evaluate(() => {
				const r = (el) => (el ? [Math.round(el.getBoundingClientRect().left), Math.round(el.getBoundingClientRect().top), Math.round(el.getBoundingClientRect().width), Math.round(el.getBoundingClientRect().height)] : null);
				return JSON.stringify({
					rail: [...document.querySelectorAll('[data-v3-nav]')].map((a) => [a.getAttribute('data-v3-nav'), r(a)]),
					top: r(document.querySelector('[data-v3="top-bar"]')),
					search: r(document.querySelector('[data-shell="command-search"]')),
					officer: r(document.querySelector('[data-testid="v3-officer"]')),
					menu: r(document.querySelector('[data-testid="v3-header-menu"]')),
				});
			});
		}
		const ref = geo['/home'];
		const off = Object.entries(geo).filter(([, v]) => v !== ref).map(([k]) => k);
		ok(`R7. ${w}: the rail and the top bar sit in the same places on /home, /decide, /map, /assistant`, off.length === 0 && ref.includes('"rail":[["home"'), off.join(',') || 'identical');
	}

	// ── 15: nothing written ─────────────────────────────────────────────────
	const other = writes.filter((w) => !w.startsWith('POST /api/v1/traffic/live'));
	ok('15. every non-GET was aborted in the browser; none but the flow layer’s read was even attempted', other.length === 0, `${writes.length} aborted${other.length ? `: ${other.slice(0, 4).join(', ')}` : ''}`);
	ok('1. zero page errors', errors.length === 0, errors.slice(0, 3).join(' | '));
} finally {
	await browser.close();
}

console.log(failures ? `\nv3-map-smoke: ${failures} failure(s)` : '\nv3-map-smoke: ALL OK');
process.exit(failures ? 1 : 0);
