/**
 * Screens-verify — the interface-revamp UI acceptance camera.
 *
 * Photographs EVERY revamped surface of the ONE deck (the SvelteKit
 * command-deck serving :5273 as container sajag-command-deck) under the
 * red-team-validated SwiftShader software-WebGL flags and proves, per
 * surface:
 *
 *   (a) the page renders its KEY ELEMENTS (each surface's contract below),
 *   (b) the saved PNG is NON-BLANK at the pixel level (Chrome itself
 *       decodes the PNG; ≥8 distinct colours + >90% opaque pixels — the
 *       showcase_canvas_shots.mjs proof, reused verbatim).
 *
 * Surfaces and their key elements:
 *   /ops       the situation wall — band masthead, event board, pursuit
 *              console, enforcement queue, Civic Volunteers dispatch, city
 *              signal plans, AMA module card, decision-audit stream, and
 *              the wall God's-eye canvas (.ge-canvas)
 *   /gods-eye  the cinematic — Cesium viewer ready (window.__GODS_EYE__)
 *   /citizen   the Daylight advisory — band strip + event cards
 *   /driver    the 108 driver flow DRIVEN end-to-end: idle → evaluating →
 *              proposal → approved open window (live countdown)
 *   /comms     the trilingual advisory desk — EN/HI/MR columns
 *   /chat      the takeover chat console
 *
 * Operator gate: the deck surfaces (/ops, /gods-eye, /comms, /chat) are
 * shot SIGNED IN — one sign-in through tests/lib/operator-session.mjs (one
 * attempt, PIN read at run time, never logged; the cookie is set before each
 * page's first navigation; revoked on exit). The public surfaces (/citizen,
 * /driver) are shot anonymously, as the public sees them.
 *
 * Usage: node tests/screens-verify.mjs [origin] [outDir]
 *        defaults: origin http://127.0.0.1:5273 (the container),
 *                  outDir tests/artifacts/screens — the TRACKED evidence of
 *                  record, and only for the live deck's origin (:5273, LG 21);
 *                  any other origin without an outDir writes to the
 *                  untracked, gitignored tests/artifacts/screens-dev and says
 *                  so (tests/lib/screens-out.mjs). Pass an outDir anyway.
 *
 * Old-or-new (UI-S7A): each key element accepts today's markup or the
 * redesign's — a panel title case-insensitively, today's or the rebuilt
 * section's, or the section's test id (SPEC §12.2–12.4; tests/lib/tolerant.mjs).
 * The /comms columns are the three DRAFT columns ([data-lang]; the template
 * preview's columns carry data-template-lang). /comms reads a PUBLIC event's
 * drafts: when the desk's first event is operator-only, the first public event
 * its select lists is picked (a local selection, no write). Two key elements
 * follow the data, on a NON-live deck (any origin but :5273) only: /citizen
 * with an empty public feed shows its honest empty state instead of cards, and
 * a /comms desk that lists no public event must withhold the citizen draft in
 * all three languages — no road, no registration mark, Copy disabled
 * (tests/lib/tolerant.mjs citizenCardsVerdict, commsFactsVerdict). The live
 * deck keeps both of HEAD's assertions. The check names and their count (40)
 * are unchanged: the repo's release-consistency script reads them.
 * Env:   CHROME_PATH (defaults to the puppeteer cache path); SAJAG_OPERATOR_PIN,
 *        else SAJAG_OPERATOR_PIN_FILE (a sandbox deck's PIN), else sajag.env
 * Exit 0 all checks pass; 1 any failure. Manifest:
 *        <outDir>/screens_manifest.json (per-check ok/detail evidence).
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { puppeteerCookies, signIn, signOut } from './lib/operator-session.mjs';
import { defaultScreensDir, isLiveDeckOrigin, isTrackedScreensDir } from './lib/screens-out.mjs';
import { COMMS_DRAFTS, OPS_KEY_ELEMENTS, SEL, citizenCardsVerdict, commsDrafts, commsFactsVerdict, opsKeyElementOk, pickPublicCommsEvent, withheldColumnsVerdict } from './lib/tolerant.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');

const ORIGIN = (process.argv[2] ?? 'http://127.0.0.1:5273').replace(/\/+$/, '');
const OUT_ARG = process.argv[3];
/** Only the live deck (:5273) may default to the tracked evidence of record. */
const OUT = OUT_ARG ?? path.join(DECK, defaultScreensDir(ORIGIN));
if (!OUT_ARG) {
	console.log(
		`screens-verify: no output directory given — writing to ${path.relative(DECK, OUT)} (${isTrackedScreensDir(OUT) ? 'the tracked evidence of record: the live deck' : 'untracked, gitignored dev output'})`,
	);
}

const CHROME =
	process.env.CHROME_PATH ||
	`${process.env.HOME}/.cache/puppeteer/chrome/linux_arm-153.0.8010.36/chrome-linux-arm64/chrome`;

// puppeteer-core resolves from the React frontend's node_modules (the same
// tree the e2e harness and gods-eye-smoke.mjs use); ESM ignores NODE_PATH,
// so import by file URL.
const PUPPETEER_ENTRY = path.join(
	HERE,
	'..',
	'..',
	'..',
	'frontend',
	'node_modules',
	'puppeteer-core',
	'lib',
	'cjs',
	'puppeteer',
	'puppeteer-core.js',
);
if (!fs.existsSync(PUPPETEER_ENTRY)) {
	console.error(`puppeteer-core not found at ${PUPPETEER_ENTRY}`);
	process.exit(2);
}
const puppeteer = await import(pathToFileURL(PUPPETEER_ENTRY).href);

const SWIFTSHADER_ARGS = [
	'--no-sandbox',
	'--disable-setuid-sandbox',
	'--disable-dev-shm-usage',
	'--enable-unsafe-swiftshader',
	'--use-gl=angle',
	'--use-angle=swiftshader',
];

const PALETTE_MIN = 8;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const results = { origin: ORIGIN, chrome: CHROME, screens: {} };
let failures = 0;
/** The operator session for the gated deck surfaces ({gate:false} when the gate is off). */
let session = null;
function record(screen, name, ok, detail = '') {
	const entry = (results.screens[screen] ||= { checks: {} });
	entry.checks[name] = { ok, detail };
	if (!ok) failures++;
}
/** A check that could not run here: recorded as SKIPPED (ok null), never as passed, never as failed. */
let skips = 0;
function skip(screen, name, detail) {
	const entry = (results.screens[screen] ||= { checks: {} });
	entry.checks[name] = { ok: null, skipped: true, detail };
	skips++;
	console.log(`skip  ${screen}: ${name} — ${detail}`);
}

/** Pixel-level non-blank proof over a SAVED PNG (Chrome as decoder). */
async function pngNonBlank(browser, pngPath) {
	const b64 = fs.readFileSync(pngPath).toString('base64');
	const page = await browser.newPage();
	try {
		await page.setContent(
			`<!doctype html><body style="margin:0"><img id="i" src="data:image/png;base64,${b64}"></body>`,
			{ waitUntil: 'load', timeout: 30000 },
		);
		await page.evaluate(() => document.getElementById('i').decode?.() ?? null);
		return await page.evaluate(() => {
			const img = document.getElementById('i');
			const c = document.createElement('canvas');
			c.width = 160;
			c.height = 100;
			const ctx = c.getContext('2d');
			ctx.drawImage(img, 0, 0, 160, 100);
			const d = ctx.getImageData(0, 0, 160, 100).data;
			const colours = new Set();
			let opaque = 0;
			for (let i = 0; i < d.length; i += 4) {
				colours.add(`${d[i]},${d[i + 1]},${d[i + 2]}`);
				if (d[i + 3] > 0) opaque++;
			}
			return { distinctColours: colours.size, opaqueFrac: opaque / (d.length / 4) };
		});
	} finally {
		await page.close();
	}
}

/** Shoot one surface: key-element probe + PNG + non-blank proof. */
async function shoot(browser, screen, route, probe, { viewport = { width: 1440, height: 900 }, settle = 1200, anonymous = false } = {}) {
	const page = await browser.newPage();
	await page.setViewport(viewport);
	if (!anonymous && session) await page.setCookie(...puppeteerCookies(session));
	const consoleErrors = [];
	page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${String(e).slice(0, 160)}`));
	try {
		await page.goto(`${ORIGIN}${route}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
		const probeOut = (await probe(page)) || {};
		for (const [name, { ok, detail }] of Object.entries(probeOut)) {
			record(screen, name, ok, detail);
		}
		record(screen, 'no-page-errors', consoleErrors.length === 0, consoleErrors.slice(0, 3).join(' | ') || 'none');
		await sleep(settle);
		const file = `screen_${screen.replace(/[^a-z0-9-]/g, '_')}.png`;
		await page.screenshot({ path: path.join(OUT, file), captureBeyondViewport: false });
		const png = await pngNonBlank(browser, path.join(OUT, file));
		record(
			screen,
			'png-nonblank',
			png.distinctColours >= PALETTE_MIN && png.opaqueFrac > 0.9,
			`png colours=${png.distinctColours} opaque=${(png.opaqueFrac * 100).toFixed(1)}%`,
		);
		results.screens[screen].file = file;
	} finally {
		await page.close();
	}
}

/**
 * The wall's panel titles (today's `section.panel h2.title`, the rebuilt
 * Section's `[data-prim=panel] h2`) and which key-element test ids render.
 */
function panelTitleProbe(page) {
	return page.evaluate(
		(sel) => {
			const titles = [...document.querySelectorAll(sel.panelTitles)].map((h) => h.textContent.trim());
			return {
				titles,
				present: Object.fromEntries(sel.testids.map((id) => [id, !!document.querySelector(`[data-testid="${id}"]`)])),
				masthead: document.querySelectorAll('[data-prim="band-masthead"]').length,
				panels: document.querySelectorAll(sel.panels).length,
				eventCards: document.querySelectorAll('.event-card, .board .event, article[data-event], [data-testid="event-card"]').length,
				auditRows: document.querySelectorAll('[data-prim="audit-row"], [data-testid="audit-feed"] [data-prim="feed-item"]').length,
				canvasEl: document.querySelectorAll('.ge-canvas canvas').length,
				band: document.querySelector('[data-prim="band-masthead"]')?.getAttribute('data-band') ?? null,
			};
		},
		{ panelTitles: SEL.panelTitles, panels: SEL.panels, testids: [...new Set(OPS_KEY_ELEMENTS.flatMap((k) => k.testids))] },
	);
}

/** One /ops key element as a manifest check: a matching title (today's or the redesign's) or its test id. */
function keyElement(p, key, extra = '') {
	const spec = OPS_KEY_ELEMENTS.find((k) => k.key === key);
	const v = opsKeyElementOk(spec, p.titles, p.present);
	return { ok: v.ok, detail: `${v.via ?? `none of ${JSON.stringify(spec.titles)} / ${spec.testids.join(', ')}`}${extra}` };
}

async function main() {
	fs.mkdirSync(OUT, { recursive: true });
	session = await signIn(ORIGIN, 'Screens verify (automated check)');
	results.operatorGate = session.gate ? 'on (deck surfaces signed in)' : 'off';
	const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: SWIFTSHADER_ARGS });
	try {
		// ── /ops — THE SITUATION WALL ─────────────────────────────────────
		await shoot(
			browser,
			'ops',
			'/ops',
			async (page) => {
				await page.waitForSelector('.wall', { timeout: 30000 });
				await sleep(6000); // board poll rung + canvas first draws under SwiftShader
				const p = await panelTitleProbe(page);
				return {
					'band-masthead mounts': {
						ok: p.masthead === 1,
						detail: `data-prim=band-masthead band=${p.band} panels=${p.panels}`,
					},
					'event board (Corridor Operations Board)': keyElement(p, 'event board (Corridor Operations Board)', ` · titles=${JSON.stringify(p.titles)}`),
					'pursuit console (Pursuit & Watchlist)': keyElement(p, 'pursuit console (Pursuit & Watchlist)'),
					'enforcement queue (Decision Queue)': keyElement(p, 'enforcement queue (Decision Queue)'),
					'Civic Volunteers dispatch (Civic Volunteers Dispatch)': keyElement(p, 'Civic Volunteers dispatch (Civic Volunteers Dispatch)'),
					'signal panel (City Signal Plans)': keyElement(p, 'signal panel (City Signal Plans)'),
					'AMA module card (Active Movement Adaptation)': keyElement(p, 'AMA module card (Active Movement Adaptation)'),
					'audit stream (Decision-Audit Stream)': keyElement(p, 'audit stream (Decision-Audit Stream)', ` · audit rows rendered=${p.auditRows}`),
					'event rows on the board': {
						ok: p.eventCards > 0,
						detail: `event cards=${p.eventCards}`,
					},
					'wall canvas mounts (.ge-canvas)': {
						ok: p.canvasEl > 0,
						detail: `canvas elements=${p.canvasEl}`,
					},
				};
			},
			{ settle: 2500, viewport: { width: 1680, height: 1050 } },
		);

		// ── /gods-eye — THE CINEMATIC ─────────────────────────────────────
		await shoot(
			browser,
			'gods-eye',
			'/gods-eye',
			async (page) => {
				const deadline = Date.now() + 60000;
				let phase = null;
				while (Date.now() < deadline) {
					phase = await page
						.evaluate(() => window.__GODS_EYE__?.phase ?? null)
						.catch(() => null);
					if (phase && phase !== 'loading') break;
					await sleep(500);
				}
				await sleep(9000); // tiles + first layer draws under software GL
				const g = await page.evaluate(() => ({
					phase: window.__GODS_EYE__?.phase ?? null,
					entities: window.__GODS_EYE__?.entityCount ?? 0,
					layers: window.__GODS_EYE__?.distinctLayerIds ?? [],
					hudChips: document.querySelectorAll('.ge-hud .chip').length,
				}));
				return {
					'viewer ready (window.__GODS_EYE__.phase)': { ok: g.phase === 'ready', detail: `phase=${g.phase}` },
					'entities render on the globe': { ok: g.entities > 0, detail: `entities=${g.entities} layers=[${g.layers.join(',')}]` },
					'HUD chips mount': { ok: g.hudChips > 0, detail: `chips=${g.hudChips}` },
				};
			},
			{ settle: 1500 },
		);

		// ── /citizen — THE DAYLIGHT ADVISORY ──────────────────────────────
		await shoot(
			browser,
			'citizen',
			'/citizen',
			async (page) => {
				await page.waitForSelector('[data-screen="citizen"]', { timeout: 30000 });
				await sleep(6500); // board poll rung (5 s) lands the live events
				const p = await page.evaluate(() => ({
					theme: document.documentElement.getAttribute('data-theme'),
					strip: document.querySelector('[data-strip]')?.getAttribute('data-strip') ?? null,
					cards: document.querySelectorAll('.event-card').length,
					holds: document.querySelectorAll('.event-card .hold').length,
					badges: [...document.querySelectorAll('.event-card .badge, [data-variant]')].length,
					kicker: document.querySelector('.kicker')?.textContent?.trim() ?? '',
					empty: !!document.querySelector('[data-screen="citizen"] [data-prim="empty-state"]'),
					feed: document.querySelector('[data-screen="citizen"]')?.getAttribute('data-feed') ?? null,
				}));
				// What the public feed lists (the page's own source; anonymous, read-only): on a
				// NON-live deck with no public event the honest answer is the empty state, never a
				// card (a sandbox's data). The live deck (:5273, LG 21's evidence of record) always
				// needs a card (citizenCardsVerdict).
				const listed = await fetch(`${ORIGIN}/api/public/events`, { signal: AbortSignal.timeout(10000) })
					.then((r) => r.json())
					.then((b) => (Array.isArray(b?.events) ? b.events.length : null))
					.catch(() => null);
				return {
					'daylight theme on public surface': { ok: p.theme === 'daylight', detail: `data-theme=${p.theme}` },
					'plain-language band strip': { ok: !!p.strip, detail: `strip=${p.strip}` },
					'event cards render': citizenCardsVerdict({ live: isLiveDeckOrigin(ORIGIN), listed, ...p }),
					'advisory kicker': { ok: p.kicker.length > 0, detail: p.kicker },
				};
			},
			{ settle: 1500, anonymous: true },
		);

		// ── /driver — the 108 flow (public: anonymous) ───────────────────
		// Driven end-to-end ONLY in its labelled scripted fallback
		// (data-mode="scripted": nothing is sent, the approval is scripted).
		// In live mode a request is a REAL 'requested' dispatch row on the
		// duty officer's wall, and only a named officer opens the window
		// (C6) — so the camera asserts the idle request card and never
		// presses the request button. Seven checks either way.
		{
			const page = await browser.newPage();
			await page.setViewport({ width: 1440, height: 900 });
			const consoleErrors = [];
			page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${String(e).slice(0, 160)}`));
			try {
				await page.goto(`${ORIGIN}/driver`, { waitUntil: 'domcontentloaded', timeout: 60000 });
				await page.waitForSelector('[data-screen="driver"]', { timeout: 30000 });
				// the public feed settles the mode (connecting → live | scripted)
				await page
					.waitForSelector('[data-screen="driver"]:not([data-mode="connecting"])', { timeout: 30000 })
					.catch(() => null);
				const attrOf = (name) => page.$eval('[data-screen="driver"]', (el, n) => el.getAttribute(n), name);
				const phaseOf = () => attrOf('data-phase');
				const mode = await attrOf('data-mode');
				record('driver', 'flow mounts at idle', (await phaseOf()) === 'idle', `phase=${await phaseOf()} mode=${mode}`);
				results.screens.driver.mode = mode; // the checks below depend on it (the consistency oracle reads it)
				// F-08: the request clock counts from a request, never from page load — idle (two reads 1.3 s apart)
				const g1 = await page.$eval('[data-testid="golden-hour"]', (el) => `${el.getAttribute('data-started')}|${el.querySelector('[data-golden-seconds]')?.getAttribute('data-golden-seconds') ?? '-'}`);
				await sleep(1300);
				const g2 = await page.$eval('[data-testid="golden-hour"]', (el) => `${el.getAttribute('data-started')}|${el.querySelector('[data-golden-seconds]')?.getAttribute('data-golden-seconds') ?? '-'}`);
				record('driver', 'request clock idle until a request is sent', g1 === '0|-' && g2 === '0|-', `${g1} → ${g2}`);
				if (mode === 'scripted') {
					// pick the first stretch, request, ride evaluating → proposal
					await page.select('[data-testid="stretch-select"]', await page.$eval('[data-testid="stretch-select"] option:not([value=""])', (o) => o.value));
					await page.evaluate(() => {
						const btns = [...document.querySelectorAll('button')];
						btns.find((b) => b.closest('.request-row'))?.click();
					});
					await page.waitForSelector('[data-testid="evaluating"], [data-testid="proposal"]', { timeout: 20000 });
					record('driver', 'evaluating state mounts', true, `phase=${await phaseOf()}`);
					await page.waitForSelector('[data-testid="proposal"]', { timeout: 30000 });
					record('driver', 'proposal mounts (duty-officer approve present)', true, `phase=${await phaseOf()}`);
					await page.evaluate(() => {
						const btns = [...document.querySelectorAll('[data-testid="proposal"] button')];
						btns.find((b) => /approve|મંજૂર/i.test(b.textContent ?? ''))?.click();
					});
					await page.waitForSelector('[data-testid="window-open"]', { timeout: 20000 });
					const cd = await page.$eval('[data-countdown]', (el) => Number(el.getAttribute('data-countdown')));
					record('driver', 'approved open window (live countdown)', cd > 0, `phase=${await phaseOf()} countdown=${cd}s`);
				} else {
					// live (or a feed that never settled): read the idle card, file nothing
					const card = await page.evaluate(() => {
						const btn = [...document.querySelectorAll('.request-row button')][0] ?? null;
						return {
							stretches: document.querySelectorAll('[data-testid="stretch-select"] option:not([value=""])').length,
							unitInput: !!document.querySelector('[data-testid="unit-input"]'),
							requestButton: !!btn,
							requestHeld: !!btn && btn.disabled,
						};
					});
					record('driver', 'live mode: live corridor stretches on offer', mode === 'live' && card.stretches >= 1,
						`mode=${mode} stretches=${card.stretches}`);
					record('driver', 'live mode: the request must name a 108 unit (button held until one is typed)',
						card.unitInput && card.requestButton && card.requestHeld,
						`unit input=${card.unitInput} request button=${card.requestButton} held=${card.requestHeld}`);
					record('driver', 'live mode: nothing filed by the camera (still idle)', (await phaseOf()) === 'idle',
						`phase=${await phaseOf()} — a window opens only on a named duty officer's approval on /ops`);
				}
				record('driver', 'no-page-errors', consoleErrors.length === 0, consoleErrors.slice(0, 3).join(' | ') || 'none');
				await sleep(1200);
				const file = 'screen_driver.png';
				await page.screenshot({ path: path.join(OUT, file), captureBeyondViewport: false });
				const png = await pngNonBlank(browser, path.join(OUT, file));
				record(
					'driver',
					'png-nonblank',
					png.distinctColours >= PALETTE_MIN && png.opaqueFrac > 0.9,
					`png colours=${png.distinctColours} opaque=${(png.opaqueFrac * 100).toFixed(1)}%`,
				);
				results.screens.driver = { ...(results.screens.driver || {}), file };
			} finally {
				await page.close();
			}
		}

		// ── /comms — THE TRILINGUAL DESK ──────────────────────────────────
		await shoot(
			browser,
			'comms',
			'/comms',
			async (page) => {
				await page.waitForSelector('[data-screen="comms"]', { timeout: 30000 });
				await sleep(2500);
				// HEAD's road-verbatim assertion reads a PUBLIC event's drafts: when the desk's
				// first event is operator-only, the first public one its select lists (a local
				// selection, no write). Withheld drafts stand in only on a non-live deck that
				// lists no public event, and must then hold up (commsFactsVerdict).
				const pick = await pickPublicCommsEvent(page);
				const p = await page.evaluate(commsDrafts, COMMS_DRAFTS);
				// 'all three advisories non-empty' is the PUBLIC-draft assertion. On a
				// non-live desk whose every listed event is withheld (pick.public
				// false) the merged desk composes no draft, so the check becomes the
				// withheld contract itself, asserted POSITIVELY (withheldColumnsVerdict:
				// the badge states it once; operator-kind columns empty, no Copy, empty
				// data-facts; no road, no mark, no enabled Copy) — a draft leaked into
				// a withheld column fails here and in the facts check below (audit
				// E-S7B W1). Never accepted on the live deck.
				const allWithheld = !isLiveDeckOrigin(ORIGIN) && p.cols.length === 3 && p.cols.every((c) => c.withheld === 'yes') && pick.public === false;
				const wv = allWithheld ? withheldColumnsVerdict(p) : null;
				return {
					'trilingual columns mount (EN/HI/MR)': {
						ok: p.langs.join(',') === 'en,hi,mr',
						detail: `langs=[${p.langs.join(',')}]`,
					},
					'all three advisories non-empty': {
						ok: allWithheld ? wv.ok : p.filled === 3,
						detail: allWithheld ? `no public event listed — ${wv.detail}` : `filled=${p.filled}/3`,
					},
					'same facts in all three (road name verbatim)': commsFactsVerdict({ live: isLiveDeckOrigin(ORIGIN), pick, ...p }),
				};
			},
			{ settle: 1500 },
		);

		// ── /chat — THE TAKEOVER CONSOLE ──────────────────────────────────
		await shoot(
			browser,
			'chat',
			'/chat',
			async (page) => {
				await page.waitForSelector('[data-screen="chat"]', { timeout: 30000 });
				await sleep(2000);
				const p = await page.evaluate(() => ({
					context: document.querySelectorAll('[data-testid="chat-context"]').length,
					stream: document.querySelectorAll('[data-testid="chat-stream"]').length,
					input: document.querySelectorAll('[data-testid="chat-input"]').length,
				}));
				return {
					'context header mounts': { ok: p.context === 1, detail: `count=${p.context}` },
					'stream region mounts': { ok: p.stream === 1, detail: `count=${p.stream}` },
					'input mounts': { ok: p.input >= 1, detail: `count=${p.input}` },
				};
			},
			{ settle: 1200 },
		);
		// ── the OSINT fixture harness (/design/osint, dev decks) ─────────
		// UI-S7B: the key element `osint-report` on the OSINT fixture page when
		// one is present (its fixtures are static and synthetic, so the page
		// answering means there IS data: a section that never mounts FAILS). A
		// deck serving no such page skips with a note, never counted as a pass.
		// `dss-section` is asserted on the DSS fixture page (next block): this
		// harness registers only the osint provider.
		{
			const harness = await fetch(`${ORIGIN}/design/osint`, { signal: AbortSignal.timeout(10000) }).then((r) => r.ok).catch(() => false);
			if (!harness) {
				skip('osint', 'osint fixture page (dev harness)', 'no /design/osint harness on this deck — no OSINT fixture to show (the sections are guarded by osint-dom.unit.mjs)');
			} else {
				const page = await browser.newPage();
				await page.setViewport({ width: 1440, height: 900 });
				if (session) await page.setCookie(...puppeteerCookies(session));
				try {
					await page.goto(`${ORIGIN}/design/osint`, { waitUntil: 'domcontentloaded', timeout: 60000 });
					await sleep(4000);
					const p = await page.evaluate(() => ({
						report: !!document.querySelector('[data-testid="osint-report"]'),
						verification: document.querySelector('[data-testid="osint-report"]')?.getAttribute('data-verification') ?? null,
						inspector: !!document.querySelector('[data-testid="entity-dossier"]'),
					}));
					record(
						'osint',
						'osint report section mounts (the fixture is synthetic)',
						p.report,
						p.report ? `verification=${p.verification ?? '—'} · inspector=${p.inspector}` : 'the osint-report section never mounted on the fixture page',
					);
					await sleep(800);
					const file = 'screen_osint.png';
					await page.screenshot({ path: path.join(OUT, file), captureBeyondViewport: false });
					results.screens.osint = { ...(results.screens.osint || {}), file, harness: true };
				} finally {
					await page.close();
				}
			}
		}

		// ── the DSS fixture page (/design/dss?section=1, dev harness) ────
		// `dss-section` (SPEC §12.4) is asserted where a DSS fixture page is
		// present: the harness seeds a synthetic C-U and mounts the inspector's
		// Decision support section, so a page that answers and lacks the hook
		// FAILS (audit E-S7B F9/D1). Skipped with a note ONLY when the deck
		// serves no such page (no DSS fixture data to show) — recorded as a
		// skip, never counted as the section mounting.
		{
			const harness = await fetch(`${ORIGIN}/design/dss`, { signal: AbortSignal.timeout(10000) }).then((r) => r.ok).catch(() => false);
			if (!harness) {
				skip('dss', 'dss section mounts on the DSS fixture page', 'no /design/dss fixture page on this deck — no DSS data to show (dss-card-smoke drives the surface on a dev deck)');
			} else {
				const page = await browser.newPage();
				await page.setViewport({ width: 1440, height: 900 });
				if (session) await page.setCookie(...puppeteerCookies(session));
				try {
					await page.goto(`${ORIGIN}/design/dss?section=1`, { waitUntil: 'domcontentloaded', timeout: 60000 });
					const t0 = Date.now();
					let d = null;
					while (Date.now() - t0 < 20000) {
						d = await page.evaluate(() => ({
							section: document.querySelectorAll('[data-testid="dss-section"]').length,
							link: !!document.querySelector('[data-testid="dss-section"] [data-testid="dss-link"]'),
							generate: !!document.querySelector('[data-testid="dss-section"] [data-testid="dss-generate"]'),
						}));
						if (d.section > 0) break;
						await sleep(500);
					}
					record('dss', 'dss section mounts on the DSS fixture page', !!d && d.section > 0 && (d.link || d.generate), d ? `dss-section ×${d.section} · link card ${d.link} · generate ${d.generate}` : 'page never evaluated');
					await sleep(500);
					const file = 'screen_dss.png';
					await page.screenshot({ path: path.join(OUT, file), captureBeyondViewport: false });
					results.screens.dss = { ...(results.screens.dss || {}), file, harness: true };
				} finally {
					await page.close();
				}
			}
		}
	} finally {
		await browser.close();
		await signOut(session);
		fs.writeFileSync(path.join(OUT, 'screens_manifest.json'), JSON.stringify(results, null, 2));
	}
	console.log(JSON.stringify(results, null, 2));
	const skipNote = skips ? ` (${skips} check(s) SKIPPED — not run here, not counted as passed)` : '';
	console.log(failures === 0 ? `SCREENS VERIFY: OK${skipNote}` : `SCREENS VERIFY: ${failures} check(s) failed${skipNote}`);
	process.exit(failures === 0 ? 0 : 1);
}

main().catch(async (e) => {
	await signOut(session);
	console.error('HARNESS ERROR', e);
	fs.writeFileSync(path.join(OUT, 'screens_manifest.json'), JSON.stringify({ ...results, error: String(e) }, null, 2));
	process.exit(2);
});
