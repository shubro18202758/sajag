/**
 * showcase/console_shots.mjs — the README / docs screenshot set (docs/screenshots/README.md), taken on the running deck.
 *
 *   node scripts/showcase/console_shots.mjs [--origin http://127.0.0.1:5373] [--out docs/screenshots]
 *        [--only home,map-live-3d] [--skip a,b] [--signin 'Demo duty officer'] [--quality 85]
 *        [--fake-audio-en report_en.wav] [--fake-audio-mr report_mr.wav] [--osint <osint_event id>] [--vehicle <vehicle id>]
 *        [--swiftshader] [--list]
 *
 * NOT a test: a camera. Each shot opens one page of the deck, in English unless it says otherwise (the language
 * cookie sajag_lang: en | mr | hi): console pages at 1440 × 900 in a signed-in context, the hero map shots at
 * 1920 × 1080, the public pages /welcome, /citizen and /driver in a separate, anonymous context (the phone pages at
 * 390 × 844, rendered at 2×); `decide-masked` is a console page with no officer named, which only a deck with the
 * operator gate off can show (a dev deck reading the live stack). It sets the map's base (2D city map or photoreal 3D) and legend the way an officer
 * would (the per-browser preferences), performs the shot's few clicks (open the Layers sheet, pick a road, start the
 * 23 Sep 2025 replay, pick a decision in the queue, hold the mic), waits for the page to settle — the live map gets
 * 60–90 s to fill its roads, places, readings and units — and saves a JPEG (quality 85). Nothing is edited afterwards.
 *
 * Staged states (the evening, the escort, decision support) come from scripts/demo_reset.sh and scripts/demo_tour.sh,
 * run by the operator before the camera; the camera itself never stages anything. A `strict` shot (an e-challan on the
 * theft victim's vehicle, an escort on /plan) is saved only when its state is on the board; otherwise it fails and is
 * left out, never faked.
 *
 * WebGL: the GPU (ANGLE on EGL) by default; the two replay shots use software WebGL (SwiftShader), where the draped
 * hindsight roads draw; --swiftshader puts every shot on it.
 *
 * SAFETY (on any deck; the live one is :5373): every non-GET /api/* request is answered 503 here and never reaches the deck,
 * except the on-premises AI services' compute calls (speech, vision, twin, hydro replay, forecast refresh), the
 * assistant's chat turn, the flow layer's live read (a POST) and the session itself — the shots can never write the
 * live city (no approval, no dispatch, no event, no plan, no field report is ever sent). Response bodies are never
 * logged (the signed-in /gods-eye/mode answer carries the ion token). The operator PIN is read at run time by
 * scripts/lib/deck_session.mjs and never printed.
 *
 * Each shot prints one JSON line: the file, what the page refused or logged, and two checks for the reviewer
 * (`busy`: a loading or error line on screen; `marathi`: Marathi characters on an English shot).
 *
 * Exit: 0 every requested shot saved; 1 any shot failed (the others are still saved).
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { puppeteerCookies, signIn, signOut } from '../lib/deck_session.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const require = createRequire(path.join(ROOT, 'frontend', 'package.json'));
const puppeteer = require('puppeteer-core');
const CHROME = process.env.CHROME_PATH
	|| `${process.env.HOME}/.cache/puppeteer/chrome/linux_arm-153.0.8010.36/chrome-linux-arm64/chrome`;

const argv = process.argv.slice(2);
const opt = (name, dflt) => {
	const i = argv.indexOf(name);
	return i >= 0 && argv[i + 1] !== undefined ? argv[i + 1] : dflt;
};
const list = (name) => opt(name, '').split(',').map((s) => s.trim()).filter(Boolean);
const ORIGIN = opt('--origin', 'http://127.0.0.1:5373').replace(/\/+$/, '');
const OUT = path.resolve(opt('--out', path.join(ROOT, 'docs', 'screenshots')));
const ONLY = list('--only');
const SKIP = list('--skip');
const OFFICER = opt('--signin', 'Demo duty officer');
const QUALITY = Number(opt('--quality', 85));
/** WAVs the fake microphone plays: a synthetic English report and a synthetic Marathi one (the speech service's TTS). */
const AUDIO = { en: opt('--fake-audio-en', null), mr: opt('--fake-audio-mr', opt('--fake-audio', null)) };
/** A current reported situation that is about a place (a road closure, flooding, weather): never crime or politics. */
const OSINT_ID = opt('--osint', '75432078-c3fa-4328-856f-899bbfa59494');
const VEHICLE_ID = opt('--vehicle', '44f24e0b-27cd-4bc0-845b-912edb50b506');
const SWIFTSHADER = argv.includes('--swiftshader');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const CONSOLE = { width: 1440, height: 900 };
const HERO = { width: 1920, height: 1080 };
const PHONE = { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true };

// ── helpers the shots use ──────────────────────────────────────────────────
/** Click the first element whose visible text matches (a button, link, tab or chip). */
async function clickText(page, re, { selector = 'button, a, [role="tab"], [role="button"], label, summary', timeout = 15000 } = {}) {
	const t0 = Date.now();
	while (Date.now() - t0 < timeout) {
		const ok = await page.evaluate((sel, s, f) => {
			const rx = new RegExp(s, f);
			const els = [...document.querySelectorAll(sel)].filter((e) => {
				const r = e.getBoundingClientRect();
				return r.width > 0 && r.height > 0 && rx.test((e.innerText || e.getAttribute('aria-label') || e.title || '').trim());
			});
			if (!els.length) return false;
			els[0].scrollIntoView({ block: 'center' });
			els[0].click();
			return true;
		}, selector, re.source, re.flags);
		if (ok) return true;
		await sleep(500);
	}
	throw new Error(`no clickable element matching ${re}`);
}

/** Wait until the page's text matches (or the timeout passes — then the shot is still taken, and flagged). */
async function waitText(page, re, timeout = 30000) {
	const t0 = Date.now();
	while (Date.now() - t0 < timeout) {
		const hit = await page.evaluate((s, f) => new RegExp(s, f).test(document.body?.innerText || ''), re.source, re.flags).catch(() => false);
		if (hit) return true;
		await sleep(700);
	}
	return false;
}

/** Click the first visible element matching a CSS selector (optionally whose aria-label / text matches). */
async function clickSel(page, sel, re = null, timeout = 30000) {
	const t0 = Date.now();
	while (Date.now() - t0 < timeout) {
		const ok = await page.evaluate((q, s, f) => {
			const rx = s ? new RegExp(s, f) : null;
			const el = [...document.querySelectorAll(q)].find((e) => {
				const r = e.getBoundingClientRect();
				if (!(r.width > 0 && r.height > 0)) return false;
				return !rx || rx.test(`${e.getAttribute('aria-label') || ''} ${e.innerText || ''} ${e.title || ''}`);
			});
			if (!el) return false;
			el.scrollIntoView({ block: 'center' });
			el.click();
			return true;
		}, sel, re ? re.source : null, re ? re.flags : '');
		if (ok) return true;
		await sleep(700);
	}
	throw new Error(`no element ${sel}${re ? ` matching ${re}` : ''}`);
}

/** A real mouse click at the centre of the first visible element matching a selector and (optionally) a text/label regex. */
async function mouseSel(page, sel, re = null, timeout = 60000) {
	const t0 = Date.now();
	while (Date.now() - t0 < timeout) {
		const box = await page.evaluate((q, s, f) => {
			const rx = s ? new RegExp(s, f) : null;
			const el = [...document.querySelectorAll(q)].find((e) => !rx || rx.test(`${e.getAttribute('aria-label') || ''} ${e.innerText || ''}`));
			if (!el) return null;
			el.scrollIntoView({ block: 'center' });
			const r = el.getBoundingClientRect();
			return r.width > 0 && r.height > 0 ? { x: r.left + r.width / 2, y: r.top + r.height / 2 } : null;
		}, sel, re ? re.source : null, re ? re.flags : '');
		if (box) {
			await sleep(600);
			await page.mouse.click(box.x, box.y);
			return true;
		}
		await sleep(1500);
	}
	throw new Error(`no element ${sel}${re ? ` matching ${re}` : ''}`);
}

/** Pick one decision in the Decide queue (its row's aria-label names the kind, the title and the mark). */
const pickQueue = (page, re, timeout = 90000) => mouseSel(page, 'a[data-testid="queue-card"]', re, timeout);

/** Every scroller back to the top (a sheet's own scroll included). */
async function scrollTop(page) {
	await page.evaluate(() => {
		window.scrollTo(0, 0);
		for (const el of document.querySelectorAll('*')) if (el.scrollTop > 0) el.scrollTop = 0;
	});
}

/** Wait for the God's-eye photoreal tiles (the canvas reports them on window.__GODS_EYE__). */
async function waitTiles(page, timeout = 150000) {
	const t0 = Date.now();
	while (Date.now() - t0 < timeout) {
		const s = await page.evaluate(() => {
			const g = window.__GODS_EYE__ || {};
			const p3d = g.layerStats?.['photoreal-3d'] ?? null;
			return { via: p3d?.via ?? null, loaded: p3d?.initialTilesLoaded ?? p3d?.detail?.initialTilesLoaded ?? null };
		}).catch(() => null);
		if (s && s.via === 'ion' && s.loaded === 1) return true;
		await sleep(3000);
	}
	return false;
}

/** Wait until the map canvas says it is ready (then the shot's own settle lets the live layers fill). */
async function waitMap(page, timeout = 120000) {
	const t0 = Date.now();
	while (Date.now() - t0 < timeout) {
		if (await page.evaluate(() => window.__GODS_EYE__?.phase === 'ready').catch(() => false)) return true;
		await sleep(2000);
	}
	return false;
}

/** Build a /map or /gods-eye share hash (share-link.ts v=2 format); `sel` hands over a selection. */
function godsEyeHash({ lat, lon, alt, heading = 20, pitch = -45, layers }) {
	const p = new URLSearchParams();
	p.set('v', '2');
	p.set('lat', lat.toFixed(6));
	p.set('lon', lon.toFixed(6));
	p.set('alt', alt.toFixed(6));
	p.set('heading', heading.toFixed(6));
	p.set('pitch', pitch.toFixed(6));
	p.set('roll', '0');
	p.set('style', 'raw');
	p.set('layers', layers.join(','));
	return `#${p.toString()}`;
}

/** Pick a road through the top bar's search (the omnibar selects it and the map flies to it). */
async function omniPick(page, query) {
	await clickSel(page, '[data-shell="command-search"]');
	await sleep(900);
	await page.keyboard.type(query, { delay: 40 });
	await sleep(3500);
	await page.keyboard.press('Enter');
	await sleep(9000);
}

/** Click a road on the canvas: the canvas hook (window.__GODS_EYE__.locate) gives the on-screen point of each visible,
 *  uncovered entity of a layer (wl: waterlogging, seg: traffic flow, fc: forecast, aq: air); the first preferred id wins. */
async function pickRoad(page, prefix, prefer = []) {
	const pts = (await page.evaluate((p) => window.__GODS_EYE__?.locate?.(p) ?? [], prefix).catch(() => [])).filter((q) => !/veil/.test(q.id));
	if (!pts.length) throw new Error(`no visible ${prefix} entity to pick`);
	const byId = new Map(pts.map((q) => [q.id, q]));
	const first = prefer.map((id) => byId.get(`${prefix}${id}`)).find(Boolean) ?? pts[Math.floor(pts.length / 2)];
	// the first that opens a selection card wins (a label or another mark may sit on top of a point)
	for (const hit of [first, ...pts.filter((q) => q !== first)].slice(0, 6)) {
		await page.mouse.click(hit.x, hit.y);
		await sleep(5000);
		if (await page.$('[data-testid="v3-selection"]')) return hit.id;
	}
	throw new Error(`no ${prefix} pick opened a selection card`);
}

/** The waterlogging roads land batch by batch: wait until the visible count holds steady. */
async function steadyWl(page, timeout = 150000) {
	const t0 = Date.now();
	let last = -1, steady = 0;
	while (Date.now() - t0 < timeout && steady < 4) {
		const n = await page.evaluate(() => (window.__GODS_EYE__?.locate?.('wl:') ?? []).length).catch(() => 0);
		steady = n >= 10 && n === last ? steady + 1 : 0;
		last = n;
		await sleep(3000);
	}
	return last;
}

/** Turn a Map layer on (the Layers sheet's switch); `keepOpen` leaves the sheet open for the shot. */
async function mapLayer(page, id, on = true, keepOpen = false) {
	const open = await page.$eval('[data-testid="v3-layers-sheet"]', () => true).catch(() => false);
	if (!open) await clickSel(page, '[data-testid="v3-map-layers"]');
	await sleep(800);
	const pressed = await page.$eval(`button[data-layer="${id}"]`, (b) => b.getAttribute('aria-checked') === 'true').catch(() => null);
	if (pressed !== on) await clickSel(page, `button[data-layer="${id}"]`);
	await sleep(600);
	if (!keepOpen) await page.keyboard.press('Escape');
}

/** The voice field report: open the sheet, pick the spoken language, hold the mic while the fake microphone plays. */
async function voiceReport(page, spoken) {
	await clickSel(page, '[data-testid="field-report-open"]');
	await sleep(1500);
	if (spoken) await clickSel(page, `[data-testid="field-sheet"] .langs button[lang="${spoken}"]`, null, 10000);
	await sleep(800);
	const hold = await page.waitForSelector('[data-testid="field-hold"]', { visible: true, timeout: 15000 });
	const box = await hold.boundingBox();
	await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
	await page.mouse.down();
	await sleep(9500); // the clips run 6–8 s after a short lead
	await page.mouse.up();
	await page.waitForSelector('[data-testid="field-result"]', { visible: true, timeout: 150000 });
	await sleep(2500);
}

/** Ask the assistant one question and wait for the streamed answer to end (no bot turn still working). */
async function ask(page, question) {
	const box = await page.waitForSelector('[data-testid="v3-ask"]', { visible: true, timeout: 30000 });
	await box.click();
	await page.keyboard.type(question, { delay: 25 });
	await sleep(600);
	await page.keyboard.press('Enter');
	await sleep(5000);
	const t0 = Date.now();
	while (Date.now() - t0 < 240000) {
		const busy = await page.evaluate(() => !document.querySelector('[data-testid="v3-bot-turn"]')
			|| !!document.querySelector('[data-testid="v3-bot-turn"][data-working="true"]')).catch(() => true);
		if (!busy) break;
		await sleep(2000);
	}
	await sleep(4000);
}

// ── the set (docs/screenshots/README.md) ───────────────────────────────────
/** The Map's own default layers (lib/v3/map/model.ts V3_DEFAULT_LAYERS); the photoreal city is added in 3D. */
/** The storm the hydro replay re-runs (the hydro service's replay id; Mumbai: the 18–19 Aug 2025 red-alert night unless the service names another). */
const REPLAY_DATE = process.env.SHOT_REPLAY_DATE || '2025-08-19';
const LIVE_LAYERS = ['events', 'convoy', 'traces', 'enforcement', 'osint', 'flow', 'cameras', 'units', 'dispatch', 'waterlog', 'landmarks', 'livevalues', 'air'];
const L3D = [...LIVE_LAYERS, 'photoreal-3d'];
/** Over the island city from the south: Lower Parel, Worli, the Sea Link, Dadar and Sion in one frame. */
const WIDE = (layers) => godsEyeHash({ lat: 18.9600, lon: 72.8350, alt: 6500, heading: 0, pitch: -48, layers });
/** Closer: Parel, Hindmata, Dadar TT and King's Circle, where a monsoon evening's water, units and pumps meet. */
const CLOSE = (layers) => godsEyeHash({ lat: 18.9880, lon: 72.8440, alt: 3000, heading: 6, pitch: -40, layers });
/** The western suburbs (Bandra, Santacruz, the Milan and Andheri subways), seen from the south. */
const NORTH = (layers) => godsEyeHash({ lat: 19.0350, lon: 72.8400, alt: 5200, heading: 10, pitch: -42, layers });
/** South Mumbai (Marine Drive, Churchgate, CSMT), seen from the south-west. */
const SOUTH = (layers) => godsEyeHash({ lat: 18.9050, lon: 72.8100, alt: 4200, heading: 30, pitch: -40, layers });
/** The city from above (the 2D city map): the island city and the near suburbs. */
const CITY = (layers, alt = 24000) => godsEyeHash({ lat: 19.0500, lon: 72.8650, alt, heading: 0, pitch: -89, layers });

const SHOTS = [
	// ── the front door and Home ──
	{ name: 'landing', url: '/welcome', view: CONSOLE, public: true, wait: 6000 },
	{ name: 'home', url: '/home', view: CONSOLE, wait: 20000 },
	{ name: 'home-mr', url: '/home', view: CONSOLE, lang: 'mr', wait: 20000 },

	// ── the live map ──
	{ name: 'map-live-3d', url: '/map' + WIDE(L3D), view: HERO, map: { base: 'sat3d', legend: true, tiles: true, settle: 80000 } },
	{ name: 'map-live-3d-close', url: '/map' + CLOSE(L3D), view: HERO, map: { base: 'sat3d', legend: false, tiles: true, settle: 75000 } },
	{ name: 'map-live-2d', url: '/map' + CITY(LIVE_LAYERS, 14500), view: HERO, map: { base: 'city', legend: true, settle: 70000 } },
	{ name: 'map-layers', url: '/map' + CITY(LIVE_LAYERS, 15000), view: CONSOLE, map: { base: 'city', legend: true, settle: 60000 },
		act: async (page) => {
			await clickSel(page, '[data-testid="v3-map-layers"]');
			await page.waitForSelector('[data-testid="v3-layers-sheet"]', { visible: true, timeout: 15000 });
			await sleep(3000);
		} },
	// a road's card: the 2D map with only the roads, their forecast and the places, so a click lands on the road itself
	// (with every layer on, an event's route or a feed check sits on top of the road)
	{ name: 'map-forecast', url: '/map' + godsEyeHash({ lat: 19.0100, lon: 72.8450, alt: 7000, heading: 0, pitch: -89, layers: ['flow', 'forecast', 'landmarks', 'livevalues'] }), view: CONSOLE,
		map: { base: 'city', legend: false, settle: 45000 },
		act: async (page) => {
			// Dr Ambedkar Road (Hindmata - Dadar TT and its neighbours), Tilak Bridge, Senapati Bapat Marg (cities/mumbai/network.json)
			await pickRoad(page, 'seg:', [1066, 1065, 1067, 1071, 1072, 1064]);
			await sleep(9000);
		} },
	{ name: 'map-waterlogging', gl: 'swiftshader', url: `/map?replay=${REPLAY_DATE}` + godsEyeHash({ lat: 19.0450, lon: 72.8550, alt: 14000, heading: 0, pitch: -89, layers: ['waterlog', 'landmarks'] }), view: CONSOLE,
		map: { base: 'city', legend: false, settle: 15000 },
		act: async (page) => {
			await waitText(page, /hindsight/i, 60000);
			await clickText(page, /^05:30$/).catch(() => {});
			await steadyWl(page);
			await sleep(5000);
			// the chronic spots on the network: Hindmata - Dadar TT, King's Circle, Sion, the Milan and Andheri subway roads
			await pickRoad(page, 'wl:', [1066, 1068, 1069, 1043, 1027, 1030, 1065, 1067]).catch(() => {});
			await sleep(6000);
		} },
	{ name: `replay-${REPLAY_DATE}`, gl: 'swiftshader', url: `/map?replay=${REPLAY_DATE}` + godsEyeHash({ lat: 19.0300, lon: 72.8550, alt: 15000, heading: 0, pitch: -89, layers: ['waterlog', 'landmarks'] }), view: CONSOLE,
		map: { base: 'city', legend: false, settle: 15000 },
		act: async (page) => {
			await waitText(page, /hindsight/i, 60000);
			await clickText(page, /^04:00$/).catch(() => {});
			await steadyWl(page);
			await sleep(10000);
		} },
	{ name: 'map-air', url: '/map' + CITY(['air', 'events', 'landmarks', 'livevalues'], 30000), view: CONSOLE, map: { base: 'city', legend: false, settle: 40000 },
		act: async (page) => {
			await mapLayer(page, 'air', true).catch(() => {});
			await sleep(6000);
			await pickRoad(page, 'aq:', []).catch(() => {});
			await sleep(5000);
		} },

	// ── Decide: one decision at a time ──
	{ name: 'decide-corridor', url: '/decide', view: CONSOLE, wait: 20000,
		act: async (page) => { await pickQueue(page, /108 corridor request/i); await sleep(6000); await scrollTop(page); } },
	{ name: 'decide-stolen', url: '/decide', view: CONSOLE, wait: 20000,
		act: async (page) => { await pickQueue(page, /stolen vehicle|authorise pursuit/i); await sleep(6000); await scrollTop(page); } },
	// the same sheet with NO officer named: the mark masked, the buttons waiting for a name. Only a deck with the operator
	// gate off can show a console page without a session (a dev deck reading the live stack: --origin http://127.0.0.1:5383)
	{ name: 'decide-masked', url: '/decide', view: CONSOLE, wait: 20000, nameless: true,
		act: async (page) => { await pickQueue(page, /stolen vehicle|authorise pursuit/i); await sleep(6000); await scrollTop(page); } },
	// strict: saved only when such a card is pending (the evening's reset rejects them; never staged or faked)
	{ name: 'decide-echallan', url: '/decide', view: CONSOLE, wait: 20000, strict: true,
		act: async (page) => {
			// the theft victim's vehicle: the stolen exercise mark's e-challan, which can only be rejected
			await pickQueue(page, /e-challan.*(?:WB ?06|MH ?47) ?EM ?9001/i, 60000);
			await sleep(6000);
			if (!(await waitText(page, /can only be rejected/i, 15000))) throw new Error('the sheet does not say "can only be rejected"');
			await scrollTop(page);
		} },
	{ name: 'decide-dss', url: '/decide', view: CONSOLE, wait: 20000,
		act: async (page) => { await pickQueue(page, /choose a response/i); await sleep(7000); await scrollTop(page); } },
	{ name: 'decide-ai', url: '/decide', view: CONSOLE, wait: 25000,
		act: async (page) => {
			// the twin's signal-timing card (a real mouse click: the queue's own handler selects it)
			await mouseSel(page, '[data-testid="ai-queue-card"]', /signal timing|re-time/i, 90000);
			await sleep(7000);
		} },
	{ name: 'decide-waterlogging', url: '/decide', view: CONSOLE, wait: 15000,
		act: async (page) => {
			await clickSel(page, '[data-testid="ai-exercise"]', null, 30000).catch(() => page.evaluate(() => document.querySelector('[data-testid="ai-exercise"]')?.click()));
			await waitText(page, /exercise/i, 60000);
			await sleep(8000);
			await mouseSel(page, '[data-testid="ai-queue-card"]', /reroute|divert|waterlog/i, 60000);
			await sleep(5000);
		} },
	{ name: 'audit', url: '/analyst', view: CONSOLE, wait: 15000,
		act: async (page) => {
			await clickText(page, /^Audit$/, { selector: 'button, [role="tab"]' });
			await sleep(3500);
			await clickText(page, /^Officers$/, { selector: 'button, [role="tab"], label, span' }).catch(() => {});
			await sleep(3500);
		} },

	// ── Plan, the escort and the field units ──
	{ name: 'plan', url: '/plan', view: CONSOLE, wait: 12000,
		act: async (page) => {
			// a running escort is adopted (step 4, Live): the planner starts a new trip beside it
			if (await page.$('[data-testid="v3-plan-new"]')) { await clickSel(page, '[data-testid="v3-plan-new"]').catch(() => {}); await sleep(3000); }
			await clickSel(page, '[data-testid="v3-plan-class"][data-class="Z+"]', null, 10000).catch(() => {});
			await sleep(3000);
			// Find routes registers a labelled movement (an officer's press): the camera stops before it
		} },
	// strict: saved only while an escort runs (started by an officer on /plan; the camera never starts one)
	{ name: 'plan-live', url: '/plan', view: CONSOLE, wait: 20000, strict: true,
		act: async (page) => {
			if (!(await page.$('[data-testid="v3-plan-follow"]'))) throw new Error('no escort is running (seed escort first)');
			await sleep(5000);
		} },
	// the protected movement on the map (the escort's emulated convoy, its route and rolling holds): its Now row focuses it
	{ name: 'map-escort', url: '/map' + godsEyeHash({ lat: 18.9700, lon: 72.8250, alt: 9000, heading: 20, pitch: -50, layers: L3D }), view: CONSOLE,
		map: { base: 'sat3d', legend: false, tiles: true, settle: 50000 },
		act: async (page) => {
			await mouseSel(page, '[data-testid="v3-now-row"]', /VIP Movement/i, 30000);
			await sleep(15000);
		} },
	{ name: 'dispatch', url: '/ops', view: CONSOLE, wait: 20000,
		act: async (page) => {
			await page.evaluate(() => {
				const t = document.querySelector('[data-testid="dispatch-tile"], [data-testid="dispatch-request"]');
				const sec = t?.closest('section') ?? t;
				sec?.scrollIntoView({ block: 'start' });
			});
			await sleep(4000);
		} },
	// ── object pages ──
	{ name: 'object-segment', url: '/o/segment:1033', view: { width: 1440, height: 1110 }, wait: 20000 },
	{ name: 'object-vehicle', url: `/o/vehicle:${VEHICLE_ID}`, view: CONSOLE, wait: 15000 },
	{ name: 'object-osint', url: `/o/osint_event:${OSINT_ID}`, view: CONSOLE, wait: 15000 },
	{ name: 'road-state', url: '/o/camera:EM-J12', view: { width: 1440, height: 1320 }, wait: 10000,
		act: async (page) => {
			await clickSel(page, 'button.th', /rain|water/i, 20000).catch(() => {});
			await sleep(800);
			await clickSel(page, '[data-testid="rs-read"]');
			await waitText(page, /confidence|waterlogged|depth/i, 240000);
			// the click scrolls the card into view; the shot shows the page from its header, model line included
			await scrollTop(page);
			await sleep(3000);
		} },
	// the same panel reading the nearest public Mapillary photo (Chittaranjan Avenue)
	{ name: 'road-state-street', url: '/o/camera:EM-CAM-04', view: { width: 1440, height: 1320 }, wait: 10000,
		act: async (page) => {
			await page.waitForSelector('[data-testid="rs-street"]:not([disabled])', { visible: true, timeout: 60000 });
			await clickSel(page, '[data-testid="rs-street"]', null, 30000);
			await page.waitForSelector('[data-testid="rs-street-date"]', { visible: true, timeout: 60000 });
			await sleep(800);
			await clickSel(page, '[data-testid="rs-read"]');
			await waitText(page, /confidence/i, 240000);
			await scrollTop(page);
			await sleep(3000);
		} },

	// ── the AI surfaces and the Analyst family ──
	{ name: 'assistant', url: '/assistant', view: CONSOLE, wait: 8000,
		act: async (page) => { await ask(page, 'How is traffic on the Bandra-Worli Sea Link right now?'); await scrollTop(page); await sleep(1500); } },
	{ name: 'assistant-refusal', url: '/assistant', view: CONSOLE, wait: 8000,
		act: async (page) => { await ask(page, 'Who is driving the stolen vehicle, and where do they live?'); await scrollTop(page); await sleep(1500); } },
	{ name: 'advisories', url: '/comms', view: CONSOLE, wait: 15000,
		act: async (page) => {
			// the cloudburst's row (SIMULATED), its three-language draft for the first audience
			await mouseSel(page, '[data-testid="comms-event-row"]', /cloudburst/i, 30000)
				.catch(() => clickText(page, /cloudburst/i, { selector: 'button, a, [role="option"], li' }).catch(() => {}));
			await sleep(8000);
		} },
	{ name: 'analyst-workspace', url: '/analyst', view: CONSOLE, wait: 15000, map: { settle: 30000 } },
	{ name: 'situation-wall', url: '/ops', view: CONSOLE, wait: 20000 },
	{ name: 'analyst-city-map', url: '/gods-eye' + godsEyeHash({ lat: 18.9850, lon: 72.8350, alt: 2600, heading: 20, pitch: -32,
		layers: ['photoreal-3d', 'events', 'units', 'signals', 'cameras', 'traces', 'flow', 'landmarks'] }), view: CONSOLE, map: { tiles: true, settle: 45000 } },
	// 1000 px tall so the sheet's Send to the board line shows under a longer transcript
	{ name: 'voice-report-en', url: '/home', view: { width: 1440, height: 1000 }, wait: 8000, audio: 'en', act: async (page) => voiceReport(page, 'en') },
	{ name: 'voice-report', url: '/home', view: CONSOLE, wait: 8000, audio: 'mr', act: async (page) => voiceReport(page, 'mr') },

	// ── the public pages (anonymous: marks stay masked) ──
	{ name: 'citizen', url: '/citizen', view: PHONE, public: true, wait: 12000,
		act: async (page) => {
			await page.select('[data-testid="water-road"]', '1058').catch(() => {});
			await sleep(3000);
			await page.evaluate(() => document.querySelector('[data-testid="water-card"]')?.scrollIntoView({ block: 'start' }));
			await sleep(2500);
		} },
	{ name: 'driver', url: '/driver', view: PHONE, public: true, wait: 8000 },
];

if (argv.includes('--list')) {
	for (const s of SHOTS) console.log(`${s.name.padEnd(22)} ${(s.lang || 'en')} ${s.public ? 'public ' : s.nameless ? 'no name' : 'console'} ${s.view.width}×${s.view.height}  ${s.url.split('#')[0]}`);
	process.exit(0);
}

const wanted = SHOTS.filter((s) => (!ONLY.length || ONLY.includes(s.name)) && !SKIP.includes(s.name));
for (const s of wanted) if (s.audio && !AUDIO[s.audio]) console.log(JSON.stringify({ shot: s.name, skipped: `needs --fake-audio-${s.audio} <wav>` }));
let todo = wanted.filter((s) => !s.audio || AUDIO[s.audio]);
fs.mkdirSync(OUT, { recursive: true });

function guard(page, errors) {
	page.on('pageerror', (e) => errors.push('pageerror: ' + e.message.slice(0, 200)));
	page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 200)); });
	// on every deck, not only :5373: a dev deck may read the live backend
	page.setRequestInterception(true);
	page.on('request', (req) => {
		const u = new URL(req.url());
		const compute = /^\/api\/(speech|vision|twin|hydro|forecast)\//.test(u.pathname)
			|| u.pathname.endsWith('/api/v1/traffic/live') || u.pathname === '/api/session'
			|| u.pathname === '/api/convoy/chat/stream' || u.pathname === '/api/convoy/chat';
		if (u.pathname.startsWith('/api/') && req.method() !== 'GET' && !compute) {
			errors.push(`blocked live write ${req.method()} ${u.pathname}`);
			return req.respond({ status: 503, contentType: 'application/json', body: '{"error":"console_shots: live writes refused"}' });
		}
		return req.continue();
	});
}

/** One browser per fake-microphone file (the file is a launch flag); one browser at a time. */
async function launch(audioFile, software) {
	const gl = software
		? ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--use-gl=angle', '--ignore-gpu-blocklist']
		: ['--use-angle=gl-egl', '--use-gl=angle', '--enable-gpu', '--ignore-gpu-blocklist'];
	return puppeteer.launch({
		executablePath: CHROME,
		headless: 'new',
		protocolTimeout: 600000,
		args: ['--no-sandbox', ...gl, '--window-size=1920,1080', '--hide-scrollbars',
			'--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
			...(audioFile ? [`--use-file-for-fake-audio-capture=${path.resolve(audioFile)}%noloop`] : [])],
	});
}

let session = null;
let failures = 0;
try {
	session = await signIn(ORIGIN, OFFICER);
	if (session && session.gate !== false) {
		// a gated deck answers a console page without a session with its sign-in screen: nothing to show
		for (const s of todo.filter((x) => x.nameless)) console.log(JSON.stringify({ shot: s.name, skipped: 'needs a deck with the operator gate off (a dev deck reading the live stack)' }));
		todo = todo.filter((x) => !x.nameless);
	}
	// one browser per fake-microphone file and WebGL flavour, one at a time
	const key = (x) => `${x.audio || ''}|${x.gl || ''}`;
	const groups = [...new Set(todo.map(key))];
	for (const g of groups) {
		const [audio, gl] = g.split('|');
		const browser = await launch(audio ? AUDIO[audio] : null, gl === 'swiftshader' || SWIFTSHADER);
		try {
			if (audio) await browser.defaultBrowserContext().overridePermissions(ORIGIN, ['microphone']).catch(() => {});
			const pub = await browser.createBrowserContext();
			for (const s of todo.filter((x) => key(x) === g)) {
				const errors = [];
				const ctx = s.public || s.nameless ? pub : browser.defaultBrowserContext();
				const page = await ctx.newPage();
				const t0 = Date.now();
				try {
					await page.setViewport(s.view);
					const host = new URL(ORIGIN).hostname;
					const cookies = [{ name: 'sajag_lang', value: s.lang || 'en', domain: host, path: '/' }];
					if (!s.public && !s.nameless && session && session.gate !== false) cookies.push(...puppeteerCookies(session));
					await page.setCookie(...cookies);
					// the map's per-browser preferences, as an officer would leave them (base map and legend)
					if (s.map && (s.map.base || s.map.legend !== undefined)) {
						await page.evaluateOnNewDocument((base, legend) => {
							try {
								if (base) localStorage.setItem('sajag.v3.map.base', base);
								if (legend !== undefined) localStorage.setItem('sajag.v3.map.legend', legend ? '1' : '0');
							} catch { /* storage unavailable */ }
						}, s.map.base ?? null, s.map.legend);
					}
					guard(page, errors);
					await page.goto(ORIGIN + s.url, { waitUntil: 'networkidle2', timeout: 120000 }).catch((e) => errors.push('goto: ' + e.message.slice(0, 160)));
					if (s.map) {
						if (!(await waitMap(page))) errors.push('map: not ready');
						if (s.map.tiles && !(await waitTiles(page))) errors.push('map: photoreal tiles not in');
						await sleep(s.map.settle ?? 60000);
					}
					await sleep(s.wait ?? 6000);
					if (s.act) {
						const ok = await s.act(page).then(() => true, (e) => { errors.push('act: ' + e.message.slice(0, 200)); return false; });
						if (!ok && s.strict) throw new Error(`not saved: ${errors[errors.length - 1]}`);
					}
					if (s.settle) await sleep(s.settle);
					const file = path.join(OUT, `${s.name}.jpg`);
					await page.screenshot({ path: file, type: 'jpeg', quality: QUALITY });
					// two checks for the reviewer: a loading or error line on screen, Marathi on an English shot
					const check = await page.evaluate(() => {
						const txt = document.body?.innerText || '';
						const busy = (txt.match(/\b(Loading|Something went wrong|could not load|Retrying)\b[^\n]{0,60}/i) || [null])[0];
						const marathi = (txt.match(/[ঀ-৿]/g) || []).length;
						return { busy, marathi };
					}).catch(() => ({}));
					const kb = Math.round(fs.statSync(file).size / 1024);
					console.log(JSON.stringify({ shot: s.name, file: path.relative(ROOT, file), kb, s: Math.round((Date.now() - t0) / 1000), lang: s.lang || 'en', ...check, errors: errors.slice(0, 6) }));
				} catch (e) {
					failures++;
					console.log(JSON.stringify({ shot: s.name, failed: String(e).slice(0, 240) }));
				} finally {
					await page.close().catch(() => {});
				}
			}
		} finally {
			await browser.close();
		}
	}
} finally {
	if (session && session.gate !== false) await signOut(session).catch(() => {});
}
process.exit(failures ? 1 : 0);
