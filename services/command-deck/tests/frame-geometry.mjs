/**
 * Frame geometry probe (audit C S1/S2/S3 + audit E round 2 — FIX-E-WORKSPACE).
 *
 *   bash $O/sem.sh chrome 4 node tests/frame-geometry.mjs <origin> [evidence-dir]
 *
 * Run against a RUNNING deck (the dev deck; nothing is spawned here). For
 * every dock state on `/` and `/gods-eye` at 1920×1080 and 1366×768:
 *
 *   1. the map pane never overflows the right dock or the viewport
 *      (`[data-pane="map"]` right edge ≤ the open right dock's x and ≤ the
 *      viewport width; the same on the left), whatever dock toggled — the
 *      escort decision card is never covered (audit C S1);
 *   2. EVERY toggle actually takes effect (audit E round 2): after each
 *      hide-button click, `]`, `[`, rail-button click and rail drawer
 *      toggle the dock's `data-open` must have flipped — the dock states
 *      are NAMED from the measured `data-open`, never assumed;
 *   3. at 1366 the Plan rail button opens the Plan tab (the escort's
 *      Launch/Stop/Clear live there — an unreachable Plan is a lost console);
 *   4. two `city-vitals` are never mounted at once (SPEC §12.1.2);
 *   5. on `/` with decisions waiting and no live movement the right dock
 *      opens on the INBOX (audit C S2 — no unregistered 'movement' seed);
 *   6. in Split view below ~900 px of pane width the Active events card
 *      collapses to its header AND sits below the canvas toolbar, never
 *      under it (audit E item 4);
 *   7. on `/gods-eye` the bottom dock is its 36 px header with the
 *      Live/Replay control in that header (audit C S2);
 *   8. the Cesium credit plate is ONE compact line inside the map pane's
 *      corner on `/` (map view and Split) and inside the /ops map tile —
 *      nothing clipped (no hidden overflow), never intersecting the
 *      coordinate readout, the scale bar or the toolbar, with the OSM
 *      attribution spelled out and the "Data attribution" link on screen
 *      (audit E item 3);
 *   9. once, WITH AN ESCORT LIVE (planned and launched through the Plan tab
 *      on the sandbox the deck is backed by): the right dock seeds the
 *      Movement tab, the dock-tabs row keeps its hide button visible with
 *      four live tabs (audit E item 7), and closing the LEFT dock — or the
 *      right dock — stays closed: no effect ever re-opens a dock the
 *      operator closed (audit E S1). The escort is stopped and cleared on
 *      the way out.
 *
 * Screenshots land in the evidence dir given (arg 2, or GEOMETRY_OUT) —
 * never tests/artifacts/**. Exits 0 with `ok` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { puppeteerCookies, signIn, signOut } from './lib/operator-session.mjs';
import { WORKSPACE } from './lib/routes.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');

const PUPPETEER_CANDIDATES = [
	process.env['PUPPETEER_FROM'],
	path.resolve(DECK, '../../frontend/package.json'),
].filter(Boolean);
let puppeteer = null;
for (const from of PUPPETEER_CANDIDATES) {
	try {
		const req = createRequire(from);
		puppeteer = req('puppeteer').default ?? req('puppeteer');
		break;
	} catch {
		// next candidate
	}
}
if (!puppeteer) throw new Error(`puppeteer not resolvable from ${PUPPETEER_CANDIDATES.join(', ')}`);

const CHROME_CANDIDATES = [
	process.env['CHROME_PATH'],
	path.join(os.homedir(), '.cache/puppeteer/chrome/linux_arm-153.0.8010.36/chrome-linux-arm64/chrome'),
	path.join(os.homedir(), '.cache/puppeteer/chrome/linux_arm-146.0.7680.76/chrome-linux-arm64/chrome'),
].filter(Boolean);
const executablePath = CHROME_CANDIDATES.find(existsSync);
if (!executablePath) throw new Error('no Chrome binary found (set CHROME_PATH)');

const SWIFTSHADER_ARGS = ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader'];

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const origin = process.argv[2] ?? 'http://127.0.0.1:5424';
// never the live deck (this probe drives a real browser against whatever it is given)
if (/:(5273|8090|8091|8092)\b/.test(origin)) {
	console.error(`refusing the live stack: ${origin}`);
	process.exit(2);
}
const OUT_DIR = process.argv[3] ?? process.env.GEOMETRY_OUT ?? path.join(os.tmpdir(), 'sajag-frame-geometry');
mkdirSync(OUT_DIR, { recursive: true });

const browser = await puppeteer.launch({ executablePath, headless: 'new', args: SWIFTSHADER_ARGS });
let session = null;
let shotN = 0;

try {
	session = await signIn(origin, 'Frame geometry probe (automated check)');
	ok('operator gate', true, session.gate ? 'on — signed in' : 'off');

	/** A box as a plain rect ({x,y,w,h,r,b}); null when the element is absent or not laid out. */
	async function rect(page, sel) {
		return page.evaluate((s) => {
			const el = document.querySelector(s);
			if (!el) return null;
			const r = el.getBoundingClientRect();
			return r.width > 0 || r.height > 0 ? { x: r.x, y: r.y, w: r.width, h: r.height, r: r.right, b: r.bottom } : null;
		}, sel);
	}

	/** The dock's data-open as measured (never assumed). */
	async function dockOpen(page, side) {
		return page.evaluate((s) => document.querySelector(`[data-dock="${s}"]`)?.getAttribute('data-open') === 'true', side);
	}

	/** Two rects intersect. */
	const hits = (a, b) => !!a && !!b && a.x < b.r - 0.5 && b.x < a.r - 0.5 && a.y < b.b - 0.5 && b.y < a.b - 0.5;

	async function newPage(width, height) {
		const page = await browser.newPage();
		await page.setViewport({ width, height, deviceScaleFactor: 1 });
		if (session?.gate) await page.setCookie(...puppeteerCookies(session));
		return page;
	}

	async function waitFrame(page, template, timeoutMs = 30000) {
		const deadline = Date.now() + timeoutMs;
		while (Date.now() < deadline) {
			const el = await page.evaluate((t) => !!document.querySelector(`[data-template="${t}"]`), template).catch(() => false);
			if (el) return true;
			await sleep(300);
		}
		return false;
	}

	async function shot(page, name) {
		const file = path.join(OUT_DIR, `${String(++shotN).padStart(2, '0')}-${name}.png`);
		await page.screenshot({ path: file });
		return file;
	}

	/**
	 * Wait for the canvas's tiles and credits to SETTLE — the way shot.mjs
	 * polls the tile state (audit E round 2: the credit-link assertion was
	 * flaky 1-in-3 on a fixed poll count, because Cesium adds the
	 * "Data attribution" link only once the photoreal tiles report their
	 * credits). Resolves when the photoreal layer reports its first tiles
	 * loaded (or, keyless/offline, when the globe's tiles have loaded / the
	 * schematic is on), then re-checks `probe` until it passes or the
	 * deadline. `probe` runs in the page and returns truthy when settled.
	 */
	async function waitTilesSettled(page, probe, { timeoutMs = 60000 } = {}) {
		const deadline = Date.now() + timeoutMs;
		while (Date.now() < deadline) {
			const state = await page
				.evaluate(() => {
					const g = window.__GODS_EYE__ ?? {};
					const p3d = g.layerStats?.['photoreal-3d'] ?? null;
					return {
						phase: g.phase,
						imageryMode: g.imageryMode,
						tilesLoaded: g.tilesLoaded,
						via: p3d?.via ?? null,
						initialTilesLoaded: p3d?.initialTilesLoaded ?? p3d?.detail?.initialTilesLoaded ?? null,
					};
				})
				.catch(() => null);
			const settled = !!state && (state.imageryMode === 'offline-schematic' || (state.via === 'ion' && state.initialTilesLoaded === 1) || state.tilesLoaded === true);
			if (settled) {
				while (Date.now() < deadline) {
					if (await page.evaluate(probe).catch(() => false)) return true;
					await sleep(500);
				}
				return false;
			}
			await sleep(1000);
		}
		return false;
	}

	/** The map-pane/vitals geometry asserts for one dock state (named from the measurement). */
	async function assertDockState(page, route, w, label) {
		const m = await rect(page, '[data-pane="map"]');
		const right = await rect(page, '[data-dock="right"]');
		const left = await rect(page, '[data-dock="left"]');
		const rightOpen = await dockOpen(page, 'right');
		const leftOpen = await dockOpen(page, 'left');
		const vw = w;
		const withinRight = !rightOpen || (m && right ? m.r <= right.x + 1.5 : true);
		const withinLeft = !leftOpen || (m && left ? m.x >= left.r - 1.5 : true);
		const withinViewport = !!m && m.r <= vw + 0.5;
		const state = `L${leftOpen ? 1 : 0}R${rightOpen ? 1 : 0}`;
		ok(`${route} ${w} docks=${state} (${label}): the map pane stays inside the right dock and the viewport`, !!m && withinRight && withinViewport, `map r=${m && Math.round(m.r)} right dock x=${rightOpen && right ? Math.round(right.x) : 'closed'} vw=${vw}`);
		ok(`${route} ${w} docks=${state} (${label}): the map pane stays inside the left dock`, !!m && withinLeft, `map x=${m && Math.round(m.x)} left dock r=${leftOpen && left ? Math.round(left.r) : 'closed'}`);
		const vitals = await page.evaluate(() => document.querySelectorAll('[data-testid="city-vitals"]').length);
		ok(`${route} ${w} docks=${state} (${label}): at most one city-vitals mounted`, vitals <= 1, `${vitals} mounted`);
	}

	/** One toggle step: act, then assert the named dock's data-open actually flipped. */
	async function toggleStep(page, route, w, name, side, act, expectOpen) {
		const before = { left: await dockOpen(page, 'left'), right: await dockOpen(page, 'right') };
		await act();
		await sleep(600);
		const after = { left: await dockOpen(page, 'left'), right: await dockOpen(page, 'right') };
		ok(`${route} ${w}: ${name} — ${side} dock data-open ${before[side] ? 'true→false' : 'false→true'}`, after[side] === expectOpen && after[side] !== before[side], `measured L${after.left ? 1 : 0} R${after.right ? 1 : 0}`);
		const label = name.replace(/[—\[\]()]/g, '').trim().slice(0, 40);
		await assertDockState(page, route, w, label);
	}

	/** A toggle step that asserts the flip itself (either direction). */
	async function toggleFlipStep(page, route, w, name, side, act) {
		const before = await dockOpen(page, side);
		await act();
		await sleep(600);
		const after = await dockOpen(page, side);
		ok(`${route} ${w}: ${name} — ${side} dock data-open flipped`, after !== before, `measured ${before ? 'true→false' : 'false→true'}`);
		await assertDockState(page, route, w, name.replace(/[[\]()]/g, '').trim().slice(0, 40));
	}

	// ── the dock-toggle matrix (audit C S1 + audit E round 2) ──────────────
	// every dock state on `/` and `/gods-eye` at both sizes: EVERY toggle (the
	// hide buttons, `]`, `[`, the rail buttons, the rail drawer toggle) flips
	// the dock's data-open, the map pane stays inside the docks it has and the
	// viewport, and one city-vitals at most.
	const SIZES = [
		[1920, 1080],
		[1366, 768],
	];

	for (const [route, template] of [
		[WORKSPACE, 'convoy-command'],
		['/gods-eye', 'city-command'],
	]) {
		for (const [w, h] of SIZES) {
			const page = await newPage(w, h);
			await page.goto(`${origin}${route}`, { waitUntil: 'domcontentloaded' });
			const up = await waitFrame(page, template);
			ok(`${route} ${w}: the workspace frame mounts`, up);
			if (!up) {
				await page.close();
				continue;
			}
			await sleep(2500); // the canvas and its chrome settle
			const press = (key) => async () => page.keyboard.press(key);
			const click = (sel) => async () => {
				const btn = await page.$(sel);
				if (btn) await btn.click().catch(() => {});
				else ok(`${route} ${w}: toggle target present (${sel})`, false, 'not found');
			};

			await assertDockState(page, route, w, 'start');
			// the seeded Inbox may already have opened the right dock: close it first
			// (a flip), so the matrix below runs from a closed right dock
			if (await dockOpen(page, 'right')) {
				await toggleFlipStep(page, route, w, "']' closes the pre-opened right dock", 'right', press(']'));
			}
			await toggleStep(page, route, w, "']' opens the right dock", 'right', press(']'), true);
			await toggleStep(page, route, w, "the dock hide button closes the right dock", 'right', click('[data-dock="right"] .dt-hide'), false);
			await toggleStep(page, route, w, "']' reopens the right dock", 'right', press(']'), true);
			await toggleStep(page, route, w, "'[' opens the left dock", 'left', press('['), true);
			await toggleStep(page, route, w, 'the dock hide button closes the left dock', 'left', click('[data-dock="left"] .dh-hide'), false);
			await toggleStep(page, route, w, "'[' reopens the left dock", 'left', press('['), true);
			// the rail buttons: the first left tab is the frame's default tab, so a
			// second click on it toggles the dock closed and a third re-opens it
			const firstRail = await page.evaluate(() => document.querySelector('[data-rail]')?.getAttribute('data-rail') ?? null);
			if (firstRail) {
				await toggleStep(page, route, w, `the rail button [data-rail=${firstRail}] toggles the left dock closed`, 'left', click(`[data-rail="${firstRail}"]`), false);
				await toggleStep(page, route, w, `the rail button [data-rail=${firstRail}] opens the left dock again`, 'left', click(`[data-rail="${firstRail}"]`), true);
			}
			// the rail drawer toggle: below 1440 px opening the left dock already
			// closed the right one, so these two steps assert the FLIP itself
			await toggleFlipStep(page, route, w, 'the rail drawer button toggles the right dock', 'right', click('[data-rail-toggle="right"]'));
			await toggleFlipStep(page, route, w, 'the rail drawer button toggles the right dock back', 'right', click('[data-rail-toggle="right"]'));

			// at 1366 the Plan rail button opens the PLAN tab (audit E S1's
			// regression made it unreachable below 1440 px)
			if (route === WORKSPACE && w === 1366) {
				const before = await dockOpen(page, 'left');
				await (await page.$('[data-rail="plan"]'))?.click().catch(() => {});
				await sleep(1200);
				const plan = await page.evaluate(() => ({
					left: document.querySelector('[data-dock="left"]')?.getAttribute('data-open') === 'true',
					tab: document.querySelector('[data-left-tab="plan"]') != null,
					panel: !!document.querySelector('[data-testid="planner-origin"]'),
				}));
				ok('/ 1366: the Plan rail button opens the left dock with the Plan tab', plan.left && plan.tab && plan.panel, `left=${plan.left} tab=${plan.tab} panel=${plan.panel}${before ? ' (was open — tab switched)' : ''}`);
				await assertDockState(page, route, w, 'plan rail');
			}
			await shot(page, `${route === WORKSPACE ? 'root' : 'gods-eye'}-${w}-docks`);
			await page.close();
		}
	}

	// ── `/` — the Inbox default and the collapsing Active events card ─────
	{
		const page = await newPage(1920, 1080);
		await page.goto(`${origin}${WORKSPACE}`, { waitUntil: 'domcontentloaded' });
		await waitFrame(page, 'convoy-command');
		// decisions waiting (no live movement in the sandbox): the right dock's
		// default tab is the INBOX (audit C S2) — the reactive default once the
		// board's first poll has landed
		let inbox = null;
		for (let i = 0; i < 40 && !inbox; i++) {
			inbox = await page.evaluate(() => {
				const tab = document.querySelector('[data-right-tab="inbox"]');
				return tab?.classList.contains('on') ? 'inbox' : null;
			});
			if (!inbox) await sleep(500);
		}
		ok('/ 1920: with decisions waiting the right dock defaults to the Inbox', inbox === 'inbox', `tab ${inbox ?? '(none)'}`);
		await shot(page, 'root-1920-inbox-default');

		// Split view at 1366: the pane is ~half — the Active events card collapses
		const page2 = await newPage(1366, 768);
		await page2.goto(`${origin}${WORKSPACE}`, { waitUntil: 'domcontentloaded' });
		await waitFrame(page2, 'convoy-command');
		await sleep(2000);
		await page2.click('[data-view-option="split"]').catch(() => {});
		await sleep(1200);
		const split = await page2.evaluate(() => {
			const pane = document.querySelector('[data-pane="map"]')?.getBoundingClientRect();
			const card = document.querySelector('.ae-card');
			const section = card?.querySelector('[data-ui="section"], section');
			const toolbar = document.querySelector('[data-map="toolbar"]')?.getBoundingClientRect();
			const cardR = card?.getBoundingClientRect();
			const hit = (a, b) => !!a && !!b && a.x < b.right - 0.5 && b.x < a.right - 0.5 && a.y < b.bottom - 0.5 && b.y < a.top + 0.5;
			return {
				paneW: pane?.width ?? 0,
				collapsed: card ? !card.querySelector('[data-testid="active-events"]') : null,
				open: section?.getAttribute('data-open') ?? null,
				cardUnderToolbar: hit(cardR, toolbar),
				cardTop: cardR?.top ?? null,
				toolbarBottom: toolbar?.bottom ?? null,
			};
		});
		ok('/ 1366 split: the map pane is below the collapse line', split.paneW > 0 && split.paneW < 900, `pane ${Math.round(split.paneW)} px`);
		ok('/ 1366 split: the Active events card collapses to its header', split.collapsed === true, `data-open=${split.open}`);
		// audit E item 4: the collapsed card sits BELOW the canvas toolbar, never under it
		ok('/ 1366 split: the Active events card never sits under the canvas toolbar', split.cardUnderToolbar === false && (split.cardTop ?? 0) >= (split.toolbarBottom ?? 0) - 1, `card top ${split.cardTop && Math.round(split.cardTop)} vs toolbar bottom ${split.toolbarBottom && Math.round(split.toolbarBottom)}`);
		await shot(page2, 'root-1366-split-collapsed-card');

		// audit E item 3 in Split: the credit plate is ONE line, clear of the
		// readout and the scale bar, nothing clipped
		const splitCredits = await page2.evaluate(() => {
			const plate = document.querySelector('.ge-wrap[data-chrome="v2"] .ge-canvas .cesium-viewer-bottom');
			const readout = document.querySelector('[data-map="readout"]')?.getBoundingClientRect();
			const scale = document.querySelector('[data-map="readout"] .box.scale')?.getBoundingClientRect();
			const toolbar = document.querySelector('[data-map="toolbar"]')?.getBoundingClientRect();
			if (!plate) return null;
			const p = plate.getBoundingClientRect();
			const hit = (a, b) => !!a && !!b && a.x < b.right - 0.5 && b.x < a.right - 0.5 && a.y < b.bottom - 0.5 && b.y < a.top + 0.5;
			return {
				h: p.height, w: p.width, scrollH: plate.scrollHeight, clientH: plate.clientHeight,
				readoutHit: hit(p, readout), scaleHit: hit(p, scale), toolbarHit: hit(p, toolbar),
				osm: (plate.textContent ?? '').includes('OpenStreetMap'),
				nowrap: (() => {
					const t = plate.querySelector('.cesium-credit-textContainer');
					return t ? getComputedStyle(t).whiteSpace === 'nowrap' : false;
				})(),
			};
		});
		// the credit DOM settles with the tiles: poll the TILE STATE the way
		// shot.mjs does (audit E round 2 — a fixed 40×500 ms poll was flaky),
		// then the link check inside the same bounded wait
		// Which attribution the canvas owes depends on its imagery: the ion
		// photoreal path lists its credits behind Cesium's "Data attribution"
		// link (the audit E item-3 check, unchanged); a KEYLESS canvas (the
		// gate-off, keyless verify_all preview) has no lightbox credits — its
		// OpenStreetMap credit is spelled out and linked inline on the plate,
		// and that is what must be on screen there.
		// The deck's OWN answer decides which attribution it owes — never a
		// moment-in-time read of the canvas (it is keyless until the ion upgrade
		// lands, so an early read would let a keyed deck off the link check).
		// Only the `mode` field is read; the body is never logged.
		const deckMode = await fetch(`${origin}/gods-eye/mode`, { signal: AbortSignal.timeout(10000) })
			.then((r) => r.json())
			.then((b) => (typeof b?.mode === 'string' ? b.mode : null))
			.catch(() => null);
		await waitTilesSettled(page2, () => true, { timeoutMs: 60000 });
		const splitMode = await page2.evaluate(() => window.__GODS_EYE__?.imageryMode ?? null).catch(() => null);
		const keylessSplit = deckMode === 'keyless-osm';
		const linkVisible = keylessSplit
			? await page2.evaluate(() => {
					const plate = document.querySelector('.ge-wrap[data-chrome="v2"] .ge-canvas .cesium-viewer-bottom') ?? document.querySelector('.cesium-viewer-bottom');
					const a = [...(plate?.querySelectorAll('a[href]') ?? [])].find((x) => /openstreetmap\.org\/copyright/.test(x.getAttribute('href') ?? '') && /OpenStreetMap/.test(x.textContent ?? ''));
					const r = a?.getBoundingClientRect();
					return !!r && r.width > 0 && r.height > 0 && r.right <= window.innerWidth + 0.5 && r.bottom <= window.innerHeight + 0.5;
				})
			: await waitTilesSettled(
					page2,
					() => {
						const l = document.querySelector('.cesium-credit-expand-link')?.getBoundingClientRect();
						return !!l && l.width > 0 && l.height > 0;
					},
					{ timeoutMs: 90000 },
				);
		ok('/ 1366 split: the credit plate is one compact line, nothing clipped', !!splitCredits && splitCredits.h <= 30 && splitCredits.scrollH <= splitCredits.clientH + 1, splitCredits ? `h ${Math.round(splitCredits.h)} scroll ${splitCredits.scrollH}/${splitCredits.clientH}` : 'no plate');
		ok("/ 1366 split: the one-line rule is the page's own (credit text computed nowrap)", !!splitCredits?.nowrap);
		ok('/ 1366 split: the credit plate clears the readout, the scale bar and the toolbar', !!splitCredits && !splitCredits.readoutHit && !splitCredits.scaleHit && !splitCredits.toolbarHit, splitCredits ? `readout ${splitCredits.readoutHit} scale ${splitCredits.scaleHit} toolbar ${splitCredits.toolbarHit}` : '');
		ok(
			keylessSplit ? '/ 1366 split (keyless canvas): the OpenStreetMap credit is spelled out and linked on screen' : '/ 1366 split: the "Data attribution" link is on screen',
			linkVisible,
			`deck mode ${deckMode ?? '— (unanswered: the keyed link check applies)'} · canvas imagery ${splitMode ?? '—'}`,
		);
		await page2.close();

		// audit E item 3 on `/` at 1920 (map view): the one-line plate
		const credits = await page.evaluate(() => {
			const plate = document.querySelector('.ge-wrap[data-chrome="v2"] .ge-canvas .cesium-viewer-bottom');
			const pane = document.querySelector('[data-pane="map"]');
			const readout = document.querySelector('[data-map="readout"]')?.getBoundingClientRect();
			const scale = document.querySelector('[data-map="readout"] .box.scale')?.getBoundingClientRect();
			const toolbar = document.querySelector('[data-map="toolbar"]')?.getBoundingClientRect();
			if (!plate || !pane) return null;
			const p = plate.getBoundingClientRect();
			const m = pane.getBoundingClientRect();
			const hit = (a, b) => !!a && !!b && a.x < b.right - 0.5 && b.x < a.right - 0.5 && a.y < b.bottom - 0.5 && b.y < a.top + 0.5;
			return {
				pr: p.right, pb: p.bottom, pw: p.width, ph: p.height, mr: m.right, mb: m.bottom, mw: m.width,
				scrollH: plate.scrollHeight, clientH: plate.clientHeight,
				readoutHit: hit(p, readout), scaleHit: hit(p, scale), toolbarHit: hit(p, toolbar),
				osm: (plate.textContent ?? '').includes('OpenStreetMap'),
				nowrap: (() => {
					const t = plate.querySelector('.cesium-credit-textContainer');
					return t ? getComputedStyle(t).whiteSpace === 'nowrap' : false;
				})(),
				maxH: getComputedStyle(plate).maxHeight,
			};
		});
		ok('/ 1920: the credit plate sits inside the map pane corner', !!credits && credits.pr <= credits.mr + 1 && credits.pb <= credits.mb + 1, credits ? `plate ${Math.round(credits.pw)}×${Math.round(credits.ph)} pane ${Math.round(credits.mw)} wide` : 'no plate');
		ok('/ 1920: the credit plate is ONE compact line with nothing clipped', !!credits && credits.ph <= 30 && credits.scrollH <= credits.clientH + 1, credits ? `h ${Math.round(credits.ph)} scroll ${credits.scrollH}/${credits.clientH}` : '');
		ok('/ 1920: the one-line rules are the page\'s own (nowrap on the credit text, no max-height clamp)', !!credits?.nowrap && credits.maxH === 'none', credits ? `nowrap ${credits.nowrap} max-height ${credits.maxH}` : '');
		ok('/ 1920: the credit plate clears the readout, the scale bar and the toolbar', !!credits && !credits.readoutHit && !credits.scaleHit && !credits.toolbarHit, credits ? `readout ${credits.readoutHit} scale ${credits.scaleHit} toolbar ${credits.toolbarHit}` : '');
		ok('/ 1920: the OSM attribution stays on screen', !!credits && credits.osm);
		await page.close();
	}

	// ── `/gods-eye` — the collapsed bottom dock and its header replay toggle ─
	{
		const page = await newPage(1366, 768);
		await page.goto(`${origin}/gods-eye`, { waitUntil: 'domcontentloaded' });
		await waitFrame(page, 'city-command');
		await sleep(2500);
		const dock = await page.evaluate(() => {
			const d = document.querySelector('[data-dock="bottom"]');
			const t = document.querySelector('[data-testid="replay-toggle"]');
			if (!d) return null;
			const dr = d.getBoundingClientRect();
			const tr = t?.getBoundingClientRect();
			return {
				h: dr.height,
				toggle: tr ? { top: tr.top, bottom: tr.bottom, dockTop: dr.top, dockBottom: dr.bottom, vis: tr.width > 0 && tr.height > 0 } : null,
			};
		});
		ok('/gods-eye 1366: the bottom dock collapses to its 36 px header', !!dock && dock.h <= 37, `height ${dock && Math.round(dock.h)} px`);
		ok(
			'/gods-eye 1366: the Live/Replay control rides the dock header',
			!!dock?.toggle?.vis && dock.toggle.top >= dock.toggle.dockTop - 2 && dock.toggle.bottom <= dock.toggle.dockTop + 37,
			dock?.toggle ? `toggle y ${Math.round(dock.toggle.top)}..${Math.round(dock.toggle.bottom)} dock ${Math.round(dock.toggle.dockTop)}..${Math.round(dock.toggle.dockBottom)}` : 'no toggle',
		);
		// audit E-WORKSPACE mutant R13 (one-line credit rule unguarded here): the
		// same compact-credit assertions /ops and / carry, on /gods-eye too
		await waitTilesSettled(page, () => true, { timeoutMs: 45000 });
		await sleep(1500);
		const geCredit = await page.evaluate(() => {
			const plate = document.querySelector('.ge-canvas .cesium-viewer-bottom');
			const canvas = document.querySelector('.ge-canvas')?.getBoundingClientRect();
			if (!plate || !canvas) return null;
			const p = plate.getBoundingClientRect();
			return {
				h: p.height,
				scrollH: plate.scrollHeight,
				clientH: plate.clientHeight,
				inside: p.bottom <= canvas.bottom + 1 && p.right <= canvas.right + 1,
				osm: (plate.textContent ?? '').includes('OpenStreetMap'),
				nowrap: (() => {
					const t = plate.querySelector('.cesium-credit-textContainer');
					return t ? getComputedStyle(t).whiteSpace === 'nowrap' : false;
				})(),
			};
		});
		ok('/gods-eye 1366: the credit plate is ONE compact line with nothing clipped (audit R13)', !!geCredit && geCredit.h <= 30 && geCredit.scrollH <= geCredit.clientH + 1 && geCredit.nowrap && geCredit.inside, geCredit ? `h ${Math.round(geCredit.h)} scroll ${geCredit.scrollH}/${geCredit.clientH} nowrap=${geCredit.nowrap} inside=${geCredit.inside} osm=${geCredit.osm}` : 'no plate');
		await shot(page, 'gods-eye-1366-collapsed-dock');
		await page.close();
	}

	// ── `/ops` — the credit plate inside the map tile ──────────────────────
	{
		const page = await newPage(1920, 1080);
		await page.goto(`${origin}/ops`, { waitUntil: 'domcontentloaded' });
		let up = false;
		for (let i = 0; i < 40 && !up; i++) {
			up = await page.evaluate(() => !!document.querySelector('[data-template="situation-wall"]')).catch(() => false);
			if (!up) await sleep(400);
		}
		ok('/ops 1920: the wall mounts', up);
		await sleep(3500); // the tile's canvas and its credits settle
		const tile = await page.evaluate(() => {
			const plate = document.querySelector('.ge-wrap[data-chrome="v2"] .ge-canvas .cesium-viewer-bottom');
			const wrap = document.querySelector('.wall .ge-wrap');
			const readout = document.querySelector('[data-map="readout"]')?.getBoundingClientRect();
			const scale = document.querySelector('[data-map="readout"] .box.scale')?.getBoundingClientRect();
			const toolbar = document.querySelector('[data-map="toolbar"]')?.getBoundingClientRect();
			if (!plate || !wrap) return null;
			const p = plate.getBoundingClientRect();
			const m = wrap.getBoundingClientRect();
			const hit = (a, b) => !!a && !!b && a.x < b.right - 0.5 && b.x < a.right - 0.5 && a.y < b.bottom - 0.5 && b.y < a.top + 0.5;
			return {
				pr: p.right, pb: p.bottom, pw: p.width, ph: p.height, mr: m.right, mb: m.bottom, mw: m.width, mh: m.height,
				scrollH: plate.scrollHeight, clientH: plate.clientHeight,
				readoutHit: hit(p, readout), scaleHit: hit(p, scale), toolbarHit: hit(p, toolbar),
				osm: (plate.textContent ?? '').includes('OpenStreetMap'),
				nowrap: (() => {
					const t = plate.querySelector('.cesium-credit-textContainer');
					return t ? getComputedStyle(t).whiteSpace === 'nowrap' : false;
				})(),
				maxH: getComputedStyle(plate).maxHeight,
			};
		});
		ok('/ops 1920: the credit plate sits inside the map tile corner', !!tile && tile.pr <= tile.mr + 1 && tile.pb <= tile.mb + 1, tile ? `plate ${Math.round(tile.pw)}×${Math.round(tile.ph)} tile ${Math.round(tile.mw)}×${Math.round(tile.mh)}` : 'no plate');
		ok('/ops 1920: the credit plate is ONE compact line with nothing clipped', !!tile && tile.ph <= 30 && tile.scrollH <= tile.clientH + 1, tile ? `h ${Math.round(tile.ph)} scroll ${tile.scrollH}/${tile.clientH}` : '');
		ok('/ops 1920: the one-line rules are the page\'s own (nowrap on the credit text, no max-height clamp)', !!tile?.nowrap && tile.maxH === 'none', tile ? `nowrap ${tile.nowrap} max-height ${tile.maxH}` : '');
		ok('/ops 1920: the credit plate clears the readout, the scale bar and the toolbar', !!tile && !tile.readoutHit && !tile.scaleHit && !tile.toolbarHit, tile ? `readout ${tile.readoutHit} scale ${tile.scaleHit} toolbar ${tile.toolbarHit}` : '');
		ok('/ops 1920: the OSM attribution stays on screen', !!tile && tile.osm);
		await shot(page, 'ops-1920-credits');
		await page.close();
	}

	// ── `/` WITH AN ESCORT LIVE (audit E round 2, kills the S1 dock lock) ──
	// Plan + launch through the Plan tab on the deck's own sandbox, then close
	// each dock and assert it STAYS closed — an effect that re-opens a dock the
	// operator closed is the round-1 regression. The escort is stopped and
	// cleared on the way out. (GEOMETRY_SKIP_ESCORT=1: the mutation runner's
	// short cut for mutants whose kills live elsewhere — the standard run
	// below always includes the escort.)
	// It WRITES (plans, launches, stops and clears an escort on the deck's backend), so it is OPT-IN
	// (GEOMETRY_ESCORT=1) and runs only against a sandbox dev deck on 127.0.0.1:53xx/54xx — never the live :5273.
	const escortOk = process.env.GEOMETRY_ESCORT === '1' && /^http:\/\/127\.0\.0\.1:5[34]\d\d\/?$/.test(origin) && !/:5273\b/.test(origin);
	if (process.env.GEOMETRY_ESCORT === '1' && !escortOk) console.log(`SKIP escort section: ${origin} is not a 127.0.0.1:53xx/54xx sandbox deck`);
	if (escortOk && !process.env.GEOMETRY_SKIP_ESCORT) {
		let escortMovementId = null;
		const page = await newPage(1920, 1080);
		let escortUp = false;
		try {
			await page.goto(`${origin}${WORKSPACE}`, { waitUntil: 'domcontentloaded' });
			await waitFrame(page, 'convoy-command');
			await sleep(2000);
			// the Plan tab (the operator opens it; nothing opens it for them)
			await (await page.$('[data-rail="plan"]'))?.click().catch(() => {});
			await page.waitForSelector('[data-testid="planner-origin"]', { timeout: 10000 }).catch(() => {});
			// a named duty officer travels with the launch (C-J)
			await page.evaluate(() => {
				const el = document.querySelector('[data-testid="planner-officer"]');
				if (!el) return;
				const proto = Object.getPrototypeOf(el);
				const desc = Object.getOwnPropertyDescriptor(proto, 'value');
				desc?.set?.call(el, 'Sandbox Officer');
				el.dispatchEvent(new Event('input', { bubbles: true }));
			});
			await sleep(300);
			await (await page.$('button.plan-btn'))?.click().catch(() => {});
			const planned = await page.waitForSelector('[data-testid="planner-candidates"]', { timeout: 90000 }).then(() => true).catch(() => false);
			ok('escort live: the sandbox plans a corridor', planned, planned ? 'candidates in' : 'the sandbox brain answered no plan — the escort scenario is skipped (the S1 guard is then covered by the unit rails)');
			if (planned) {
				// a CONDITIONAL plan needs its waiver accepted before Launch unlocks
				const waiver = await page.$('[data-testid="planner-waiver"]');
				if (waiver) await waiver.click().catch(() => {});
				await sleep(400);
				// Launch: the .actions button whose label is the pack's "Start escort"
				const launched = await page.evaluate(() => {
					const btn = [...document.querySelectorAll('.actions button')].find((b) => !b.disabled && /start escort/i.test(b.textContent ?? ''));
					if (!btn) return false;
					btn.click();
					return true;
				});
				ok('escort live: Launch is offered and clickable', launched);
				escortUp = await page
					.waitForFunction(() => document.querySelector('[data-template="convoy-hud"]')?.dataset.phase === 'escorting', { timeout: 30000 })
					.then(() => true)
					.catch(() => false);
				ok('escort live: the escort runs (the Movement tab carries it)', escortUp);
				escortMovementId = await page.evaluate(() => document.querySelector('[data-template="convoy-hud"]')?.dataset.movementId ?? null);
				if (escortUp) {
					// the seed effect brings the right dock up on the Movement tab
					const seeded = await page.evaluate(() => {
						const dock = document.querySelector('[data-dock="right"]')?.getAttribute('data-open') === 'true';
						const tab = document.querySelector('[data-right-tab="movement"]')?.classList.contains('on');
						return dock && !!tab;
					});
					ok('escort live: the right dock is open on the Movement tab', !!seeded);
					// audit E item 7: with four live tabs the tab row scrolls and the
					// hide button keeps its place in it
					const tabs = await page.evaluate(() => {
						const bar = document.querySelector('[data-dock="right"] .dock-tabs');
						const hide = document.querySelector('[data-dock="right"] .dt-hide');
						const n = document.querySelectorAll('[data-right-tab]').length;
						if (!bar || !hide) return null;
						const r = bar.getBoundingClientRect();
						const h = hide.getBoundingClientRect();
						return { n, inside: h.left >= r.left - 1 && h.right <= r.right + 1 && h.top >= r.top - 1 && h.bottom <= r.bottom + 1 && h.width > 0 && h.height > 0 };
					});
					ok('escort live: the dock hide button stays visible in the tab bar with four live tabs', !!tabs && tabs.inside && tabs.n >= 3, tabs ? `${tabs.n} tabs, hide inside bar: ${tabs.inside}` : 'no bar');
					// THE S1 KILL: close the LEFT dock; nothing may open it again
					await (await page.$('[data-dock="left"] .dh-hide'))?.click().catch(() => {});
					await sleep(600);
					let closed = await dockOpen(page, 'left');
					ok('escort live: the left dock closes', closed === false);
					await sleep(4000); // several board polls / effect runs
					closed = await dockOpen(page, 'left');
					ok('escort live: the left dock STAYS closed while the escort runs', closed === false, `data-open=${closed}`);
					// …and the right dock: close it, it must stay closed, and reopen by key
					await (await page.$('[data-dock="right"] .dt-hide'))?.click().catch(() => {});
					await sleep(600);
					let rightClosed = !(await dockOpen(page, 'right'));
					ok('escort live: the right dock closes', rightClosed);
					await sleep(4000);
					rightClosed = !(await dockOpen(page, 'right'));
					ok('escort live: the right dock STAYS closed while the escort runs', rightClosed, `data-open=${!rightClosed}`);
					await page.keyboard.press(']');
					await sleep(600);
					ok("escort live: ']' reopens the right dock", (await dockOpen(page, 'right')) === true);
					await shot(page, 'root-1920-escort-live');
				}
			}
		} finally {
			// leave the sandbox as we found it: STOP the escort and CLEAR the
			// corridor through the deck's own proxy (the officer the probe named
			// travels on both) — independent of what the asserts above left open
			try {
				if (escortMovementId) {
					const stop = await page.evaluate(async (mid) => {
						const r = await fetch(`/api/convoy/movements/${mid}/stop`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ officer: 'Sandbox Officer' }) });
						return { status: r.status, body: await r.json().catch(() => null) };
					}, escortMovementId);
					const clear = await page.evaluate(async (mid) => {
						const r = await fetch(`/api/convoy/movements/${mid}/clear`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ officer: 'Sandbox Officer' }) });
						return { status: r.status, body: await r.json().catch(() => null) };
					}, escortMovementId);
					const stopped = stop.status === 200 && ['stopped', 'completed'].includes(stop.body?.status);
					const cleared = clear.status === 200 && (clear.body?.event_transition?.to_status != null || clear.body?.segments_recovered != null);
					ok('escort live: cleaned up (the escort stopped and the corridor cleared)', stopped && cleared, `stop ${stop.status} ${stop.body?.status ?? ''} · clear ${clear.status}`);
				}
			} catch (err) {
				// the cleanup never masks a probe failure; the sandbox keeps its state
				console.log(`     cleanup error: ${String(err?.message ?? err).slice(0, 160)}`);
			}
			await page.close();
		}
	}
} finally {
	if (session) await signOut(session).catch(() => {});
	await browser.close();
}

writeFileSync(
	path.join(OUT_DIR, 'frame-geometry-result.json'),
	JSON.stringify({ origin, at: new Date().toISOString(), failures }, null, 2),
);

if (failures) {
	console.error(`frame-geometry: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('frame-geometry: all green');
