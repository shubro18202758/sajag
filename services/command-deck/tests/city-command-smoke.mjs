/**
 * SAJAG CITY COMMAND smoke — the fused God's-eye surface end to end, under
 * SOFTWARE WebGL (SwiftShader, the flags the red-team render proof
 * validated: --enable-unsafe-swiftshader --use-gl=angle --use-angle=swiftshader).
 * Every assertion reads the live page or the deck's own proxied API (GET
 * only), never a fixture:
 *
 *   parsers   the pure fusion modules bundled from src with esbuild
 *             (city-api.ts, plates.ts, share-link.ts, the REPLAY tape
 *             parser): URN grammar, plate masking, the share hash's
 *             palette/sel keys, and the live C-C snapshot + feed and a
 *             recorded emulator tape through the real parsers
 *   layout    /gods-eye at 1920×1080: CITY VITALS left, the canvas, the
 *             FUSION RAIL bottom (no overlap); ≥10 rail rows within 30 s;
 *             __GODS_EYE__.layerStats over the floors — events ≥1 live ·
 *             flow ≥35 coloured · traces ≥1 · signals ≥11 · cameras ≥4 ·
 *             enforcement ≥1; the snapshot carries the selection URN and
 *             the vitals values; a SIMULATED ingest feed is labelled so
 *   dossier   clicking the earmarked vehicle's marker (CC_PLATE, default
 *             MH47EM9001) opens its dossier: ≥4 sightings and their
 *             cameras, the approved recommendation (CC_REC, default
 *             e91d4591) with its deciding officer, the pursuit (CC_PURSUIT,
 *             default 4508d86d); the plate is MASKED (MH47EM•••1) until a
 *             duty officer name is entered, then shown in full
 *   rail      clicking a FUSION RAIL row selects its entity, puts the camera
 *             within 0.02° of it in ≤ 3 s and highlights it (halo on the
 *             entity, its primitives emphasised, the row marked) — the
 *             target is a row whose entity is IN the live registry (a closed
 *             dispatch the layers never draw cannot be highlighted)
 *   feeds     (stubbed reads on one page) an empty-but-healthy UNITS feed
 *             (registry status ok, 0 units) shows the 'no units fielded'
 *             hint and NO ⚠; segments served with geometry_basis
 *             'schematic' (contract C-K) are counted in the FLOW hint
 *             ('n OSM-traced · m schematic (dashed)')
 *   replay    REPLAY of run CC_REPLAY_RUN (default 20): scrubbing the tape
 *             moves the vehicle marker across ≥2 EM-CAM hops while the
 *             EMULATED pills stay visible; LIVE restores the live layers
 *   cockpit   (opt-in, CC_PLAN=1 — one plan through the SHARED models) '/'
 *             plans Nabanna → Kolkata Airport (Z): the registered event's
 *             RECOMMENDED primary spine and dashed alternates are on the
 *             canvas within 5 s of the plan answer, the camera focuses the
 *             event, and the ConvoyHud ETA is not 0
 *   escort    (opt-in, CC_ESCORT=1 — needs an escort reporting GPS, WP-12
 *             contract C-J/C-B) the convoy marker moves between two
 *             snapshots 5 s apart; '/' adopts the running escort (HUD ESCORT
 *             LIVE) and the HUD mirrors the brain's status doc — the hold
 *             line, the pending approvals, EMULATED GPS / SIMULATED FEED —
 *             read-only (the hermetic Approve / Reject / CLEAR writes are
 *             ops-wall-smoke's escort case)
 *   hidden    a hidden /ops tab sends no POST /api/v1/traffic/live (the FLOW
 *             layer's poll is gated like every other canvas feed)
 *   plates    C6 at every text sink, with NO duty officer named: a dispatch
 *             pick whose event title carries the plate (City Command's
 *             dossier MAP line; the cockpit's pick card), the cockpit's
 *             LOCKED chip title and LiveRail focus note for the pursuit, and
 *             a page-wide scan (text + title/aria-label attributes) of both
 *             views — the raw plate appears nowhere, the masked one does;
 *             once an officer is named, the LOCKED title shows it in full
 *   provenance  the /ops situation wall (which starts no corridor readout of
 *             its own): while the corridor summary stands on synthetic rows
 *             the FLOW and ANOMALY chips carry the SIM tag, and an anomaly
 *             pick card says SIMULATED FEED — never a bare feed name
 *
 * Usage:
 *   node tests/city-command-smoke.mjs [origin]      # default http://127.0.0.1:5199
 *   # origin is spawned from build/ when not answering (PORT from the origin;
 *   # ORACLE_PORT / BRAIN_PORT / EMULATOR_PORT env, default 8091/8092/8090) —
 *   # a PRIVATE preview: gate off, the PIN and the session secret never reach it
 *   CC_SMOKE_ONLY=layout,dossier   check subset (parsers, layout, dossier,
 *                                  rail, feeds, posture, replay, cockpit,
 *                                  escort, hidden, plates, provenance)
 *   CC_PLAN=1  CC_ESCORT=1         the opt-in checks
 *   SAJAG_OPERATOR_PIN, else SAJAG_OPERATOR_PIN_FILE, else sajag.env (CC_PIN, when
 *   set, is passed on as SAJAG_OPERATOR_PIN) — read only when the origin's
 *                                  operator gate is on: ONE sign-in through
 *                                  tests/lib/operator-session.mjs as
 *                                  'City-command smoke (automated check)'
 *                                  (never logged), the sajag_operator cookie
 *                                  on every fetch and page (set before the
 *                                  first navigation), signed out on exit. A
 *                                  signed-in officer sees raw plates, so the
 *                                  masked-path checks report as skipped
 *                                  (ops-wall-smoke covers them hermetically).
 *                                  Use a THROWAWAY PIN on a private preview
 *                                  — never a live one.
 *   CC_MIN_FLOW=35 CC_MIN_SIGNALS=11 CC_MIN_CAMERAS=4 CC_MIN_RAIL=10  floors
 *   PUPPETEER_FROM=…/package.json, CHROME_PATH=…   tool resolution overrides
 *
 * Final pins (UI-S7B, SPEC §12.4–12.5): the geometry through the workspace
 * frame (`[data-ws=frame]`, `data-dock`, `data-pane`) only; the pick dismissed
 * with Esc on the inspector it opened (only while the click left a selection
 * of its own); the audit rows under `[data-bottom-tab=audit]`; the provenance
 * tags `chip-simulated` and the v2 wall's Simulated-flow legend; the planner
 * behind `[data-rail=plan]`; the dossier's blocks in the inspector's tabs; and
 * the officer typed into the navbar's `duty-officer` (§12.2: the inspector's
 * own officer prompt is retired — it unmasks the plate the same way). The
 * rail check names its rows on the v2 Explorer (kind tree → object table →
 * the inspector's "Show on map" action flies).
 *
 * Nothing here POSTs except the operator sign-in (gate on only) and the
 * opt-in cockpit plan (the operator's own PLAN button). Exits 0 with
 * `ok <name> — <detail>` lines, 1 on any FAIL.
 * Screenshots land in tests/artifacts/city-command-*.png (CC_ARTIFACTS overrides).
 */

import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { deckFetch, nameOfficer, officerValue, puppeteerCookies, signIn, signOut } from './lib/operator-session.mjs';
import { textIs, textMatches } from './lib/queue.mjs';
import { WORKSPACE } from './lib/routes.mjs';
import { COPY, SEL, clearCanvasRegion, dismissPick, ensureAuditRows, ensureInspectorTab, ensureLayers, ensurePlanner, ensureRail, ensureVitals, firstPresentText, leaveReplay, lockTitle, rowMarked, textHas, within } from './lib/tolerant.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const ARTIFACTS = process.env.CC_ARTIFACTS ?? path.join(HERE, 'artifacts');

const ORIGIN = (process.argv[2] ?? 'http://127.0.0.1:5199').replace(/\/$/, '');
const ONLY = new Set((process.env.CC_SMOKE_ONLY ?? '').split(',').map((s) => s.trim()).filter(Boolean));
const OPT_IN = { cockpit: process.env.CC_PLAN === '1', escort: process.env.CC_ESCORT === '1' };
const run = (name) => (ONLY.size ? ONLY.has(name) : OPT_IN[name] ?? true);

const PLATE = process.env.CC_PLATE ?? 'MH47EM9001';
const REC_PREFIX = process.env.CC_REC ?? 'e91d4591';
const PURSUIT_PREFIX = process.env.CC_PURSUIT ?? '4508d86d';
const REPLAY_RUN = Number(process.env.CC_REPLAY_RUN ?? 20);
const FLOORS = {
	flow: Number(process.env.CC_MIN_FLOW ?? 35),
	signals: Number(process.env.CC_MIN_SIGNALS ?? 11),
	cameras: Number(process.env.CC_MIN_CAMERAS ?? 4),
	rail: Number(process.env.CC_MIN_RAIL ?? 10),
};
const FLY_TOLERANCE_DEG = 0.02;
const FLY_BUDGET_MS = 3000;
const W = 1920;
const H = 1080;

// Puppeteer resolves from THIS repo's frontend tree first (the e2e harness
// pattern), then the shared main tree; Chrome from the puppeteer cache.
const PUPPETEER_CANDIDATES = [
	process.env.PUPPETEER_FROM,
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
	process.env.CHROME_PATH,
	path.join(os.homedir(), '.cache/puppeteer/chrome/linux_arm-153.0.8010.36/chrome-linux-arm64/chrome'),
].filter(Boolean);
const executablePath = CHROME_CANDIDATES.find((p) => existsSync(p));

const SWIFTSHADER_ARGS = [
	'--no-sandbox',
	'--disable-setuid-sandbox',
	'--disable-dev-shm-usage',
	'--enable-unsafe-swiftshader',
	'--use-gl=angle',
	'--use-angle=swiftshader',
];

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * V3-P6B: the duty-officer input is in the V3 top bar's officer popover (the pill `v3-officer`), not inline in a
 * navbar. Open the popover (when it is not already) so the input exists, and return the input's selector.
 */
async function openOfficerField(page) {
	const sel = 'input[data-testid="duty-officer"]';
	if (!(await page.$(sel))) {
		await page.click('[data-v3="top-bar"] [data-testid="v3-officer"]');
		await page.waitForSelector(sel, { timeout: 8000 });
	}
	return sel;
}
const fmt = (n, d = 4) => (typeof n === 'number' ? n.toFixed(d) : String(n));

/**
 * Operator gate (SAJAG_OPERATOR_PIN on the deck): ONE sign-in through the
 * shared helper (tests/lib/operator-session.mjs — it probes the gate, reads
 * the PIN at run time and never logs it), then the sajag_operator session
 * cookie rides on every fetch and every page; signed out on exit. Gate off:
 * no session. CC_PIN (this smoke's earlier name for the PIN) is passed on
 * as SAJAG_OPERATOR_PIN.
 */
if (process.env.CC_PIN) process.env.SAJAG_OPERATOR_PIN = process.env.CC_PIN;
let session = { base: ORIGIN, gate: false, officer: null, cookie: null, value: null };

/** GET JSON; a read of the deck under test carries its operator session (another origin never does). */
async function getJson(url) {
	const init = { signal: AbortSignal.timeout(15000) };
	const res = await (new URL(url).origin === new URL(ORIGIN).origin ? deckFetch(session, url, init) : fetch(url, init));
	if (!res.ok) throw new Error(`${res.status} ${url}`);
	return res.json();
}

async function originAlive(origin) {
	try {
		const res = await fetch(`${origin}/gods-eye`, { signal: AbortSignal.timeout(3000) });
		return res.ok;
	} catch {
		return false;
	}
}

/** Spawn `node build` on the origin's port when nothing answers there. */
async function ensureOrigin(origin) {
	if (await originAlive(origin)) return null;
	if (!existsSync(path.join(DECK, 'build', 'index.js'))) throw new Error('no build/ output — run `npm run build` first');
	const port = new URL(origin).port || '5199';
	const env = {
		...process.env,
		PORT: port,
		HOST: '127.0.0.1',
		ORACLE_PORT: process.env.ORACLE_PORT ?? '8091',
		BRAIN_PORT: process.env.BRAIN_PORT ?? '8092',
		EMULATOR_PORT: process.env.EMULATOR_PORT ?? '8090',
	};
	// A preview this smoke spawns is private: gate off whatever this shell
	// exported (the PIN and the session secret stay with the deployed deck).
	for (const k of ['SAJAG_OPERATOR_PIN', 'SAJAG_OPERATOR_PIN_FILE', 'SAJAG_SESSION_SECRET', 'SAJAG_SESSION_SECURE']) delete env[k];
	const proc = spawn('node', ['build'], {
		cwd: DECK,
		env,
		stdio: ['ignore', 'pipe', 'pipe'],
	});
	proc.stdout.on('data', () => {});
	proc.stderr.on('data', (d) => process.stderr.write(`[deck] ${d}`));
	for (let i = 0; i < 40; i++) {
		if (await originAlive(origin)) return proc;
		await sleep(500);
	}
	proc.kill();
	throw new Error(`deck origin did not come up on ${origin}`);
}

async function newPage(browser, w = W, h = H) {
	const page = await browser.newPage();
	await page.setViewport({ width: w, height: h });
	if (session.gate) await page.setCookie(...puppeteerCookies(session));
	page.on('pageerror', (e) => console.error(`  pageerror: ${String(e).slice(0, 200)}`));
	return page;
}

/** Load a route and wait for the canvas phase to settle. */
async function openCanvas(page, route, timeoutMs = 60000) {
	await page.goto(`${ORIGIN}${route}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
	const deadline = Date.now() + timeoutMs;
	while (Date.now() < deadline) {
		const phase = await page.evaluate(() => window.__GODS_EYE__?.phase ?? null).catch(() => null);
		if (phase && phase !== 'loading') return phase;
		await sleep(400);
	}
	return null;
}

const snapshot = (page) =>
	page.evaluate(() => {
		const g = window.__GODS_EYE__;
		if (!g) return null;
		// eslint-disable-next-line @typescript-eslint/no-unused-vars
		const { locate, ready, ...rest } = g;
		return JSON.parse(JSON.stringify(rest));
	});

/** Poll `probe(snapshot)` until it returns truthy (or the deadline). */
async function waitSnap(page, probe, timeoutMs, everyMs = 250) {
	const deadline = Date.now() + timeoutMs;
	let last = null;
	while (Date.now() < deadline) {
		last = await snapshot(page).catch(() => null);
		if (last && probe(last)) return { snap: last, ok: true };
		await sleep(everyMs);
	}
	return { snap: last, ok: false };
}

/** In-page readback of the WebGL canvas (preserveDrawingBuffer is on). */
const readback = (page) =>
	page.evaluate(() => {
		const c = document.querySelector('.ge-canvas canvas');
		if (!c || !c.width) return null;
		const off = document.createElement('canvas');
		off.width = 320;
		off.height = Math.max(1, Math.round((320 * c.height) / c.width));
		const ctx = off.getContext('2d');
		ctx.drawImage(c, 0, 0, off.width, off.height);
		const d = ctx.getImageData(0, 0, off.width, off.height).data;
		let chroma = 0;
		let n = 0;
		for (let i = 0; i < d.length; i += 4) {
			chroma += Math.max(d[i], d[i + 1], d[i + 2]) - Math.min(d[i], d[i + 1], d[i + 2]);
			n++;
		}
		return { meanChroma: chroma / n };
	});

/**
 * The clear canvas region City Command's panels leave (client px): today the
 * `.stage` minus the vitals, dossier and rail panels; the redesign's map pane
 * minus its open docks, the vitals card and the inspector (SPEC §12.4;
 * tests/lib/tolerant.mjs clearCanvasRegion).
 */
const clearRegion = (page) => page.evaluate(clearCanvasRegion);

/** True when the client point lands on the Cesium canvas (not a panel over it). */
const onCanvas = (page, x, y) =>
	page.evaluate(
		(px, py) => {
			const el = document.elementFromPoint(px, py);
			return !!el && el.tagName === 'CANVAS' && !!el.closest('.ge-canvas');
		},
		x,
		y,
	);

/**
 * Bring an on-globe entity (`prefix` locate) into the clear region by
 * dragging the map — what an operator would do when it sits under a panel.
 */
async function spotInView(page, prefix) {
	for (let attempt = 0; attempt < 4; attempt++) {
		const spots = await page.evaluate((p) => window.__GODS_EYE__?.locate?.(p) ?? [], prefix);
		const spot = spots[0];
		if (spot && (await onCanvas(page, spot.x, spot.y))) return spot;
		const region = await clearRegion(page);
		if (!region) return spot ?? null;
		if (!spot) {
			// off screen: nothing to drag towards — let the caller report it
			if (attempt === 0) await sleep(2000);
			continue;
		}
		const dx = (region.cx - spot.x) * 0.6;
		const dy = (region.cy - spot.y) * 0.6;
		await page.mouse.move(region.cx, region.cy);
		await page.mouse.down();
		for (let i = 1; i <= 12; i++) await page.mouse.move(region.cx + (dx * i) / 12, region.cy + (dy * i) / 12);
		await page.mouse.up();
		await sleep(1200);
	}
	return null;
}

/** Hover until the canvas shows a pointer over the spot (the primitive is pickable), then click. */
async function hoverAndClick(page, spot) {
	let cursor = '';
	const settleBy = Date.now() + 6000;
	for (let i = 0; Date.now() < settleBy; i++) {
		await page.mouse.move(spot.x + (i % 2), spot.y);
		await sleep(300);
		cursor = await page.evaluate(() => document.querySelector('.ge-canvas')?.style.cursor ?? '');
		if (cursor === 'pointer') break;
	}
	await page.mouse.click(spot.x, spot.y);
	return cursor;
}

/** C6 mask, as the server and the deck print it: MH47EM9001 → MH47EM•••1. */
function masked(plate) {
	const m = /^([A-Z]{2}[ -]?\d{1,2}[ -]?(?:[A-Z]{1,3}[ -]?)?)(\d{4})$/.exec(plate);
	return m ? `${m[1]}•••${m[2].slice(-1)}` : `${plate.slice(0, -4)}•••${plate.slice(-1)}`;
}

// ── parsers: the fusion modules, bundled from src ──────────────────────────

async function parsersCheck() {
	const require2 = createRequire(path.join(DECK, 'package.json'));
	const esbuild = require2('esbuild');
	mkdirSync(ARTIFACTS, { recursive: true });
	const OUT = path.join(ARTIFACTS, 'city-command-bundle.mjs');
	const ENTRY = `
export * as cityApi from './src/lib/gods-eye/city-api';
export * as plates from './src/lib/gods-eye/plates';
export * as share from './src/lib/gods-eye/share-link';
export * as tape from './src/lib/gods-eye/hud/replay.svelte';
`;
	const result = await esbuild.build({
		stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'city-command-entry.ts' },
		absWorkingDir: DECK,
		alias: { $lib: './src/lib' },
		bundle: true,
		format: 'esm',
		platform: 'node',
		outfile: OUT,
		logLevel: 'silent',
	});
	ok('parsers bundle builds (esbuild, $lib aliased)', result.errors.length === 0, `${result.errors.length} errors`);
	// Svelte 5 runes are compiler macros: identity stubs run the stores as plain classes.
	globalThis.$state = Object.assign((v) => v, { raw: (v) => v });
	const { cityApi, plates, share, tape } = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);

	// URN grammar (the only ids that ever reach a URL).
	const urnCases = [
		['vehicle:1b94e9d2-7e11-4174-a735-7dd3be3189cf', true],
		['camera:EM-CAM-01', true],
		['junction:3', true],
		['convoy:mv-escort-1', true],
		['vehicle:not-a-uuid', false],
		['junction:J3', false],
		['../../etc/passwd', false],
		['person:42', false],
	];
	const urnBad = urnCases.filter(([u, want]) => !!cityApi.parseUrn(u) !== want);
	ok('parsers URN grammar', urnBad.length === 0, urnBad.length ? `wrong: ${urnBad.map(([u]) => u).join(', ')}` : `${urnCases.length} cases (kinds outside C-C and malformed ids refused)`);

	// C6 plate rail.
	const maskOk =
		plates.maskPlate('MH47EM9001') === 'MH47EM•••1' &&
		plates.maskPlatesInText('PURSUIT — stolen MH47EM9001 (FIR 4401/2026)') === 'PURSUIT — stolen MH47EM•••1 (FIR 4401/2026)' &&
		plates.displayPlate('MH47EM9001', false) === 'MH47EM•••1' &&
		plates.displayPlate('MH47EM9001', true) === 'MH47EM9001';
	ok('parsers plate mask (C6)', maskOk, `MH47EM9001 → ${plates.maskPlate('MH47EM9001')} unless a duty officer is named`);

	// Share hash: Ironbow palette rides only with FLIR; the selection is a URN or nothing.
	const ids = ['events', 'flow', 'traces'];
	const base = { lat: 22.5682, lon: 88.3499, alt: 5000, heading: 0, pitch: -45, roll: 0, layers: ids };
	const iron = share.buildShareHash({ ...base, style: 'flir', bhot: false, palette: 'iron', selected: 'vehicle:1b94e9d2-7e11-4174-a735-7dd3be3189cf' }, ids);
	const back = share.parseShareHash(iron, ids);
	const raw = share.buildShareHash({ ...base, style: 'raw', bhot: false, palette: 'iron', selected: null }, ids);
	const hostile = share.parseShareHash(`${raw}&sel=javascript:alert(1)`, ids);
	ok(
		'parsers share hash (palette + sel)',
		iron.includes('palette=iron') && back?.palette === 'iron' && back?.selected === 'vehicle:1b94e9d2-7e11-4174-a735-7dd3be3189cf' && !raw.includes('palette') && hostile?.selected === null,
		`flir→palette=iron round-trips, raw carries none, a hostile sel is dropped`,
	);

	// Brain health: a decider still loading its weights is 'loading' (amber), never 'unreachable'.
	const loading = cityApi.parseBrainHealth({ strategic_tier: { model_host: 'loading', degraded: false }, tactical_tier: { llama_server: 'connected' } });
	const down = cityApi.parseBrainHealth({ strategic_tier: { model_host: 'unreachable' }, tactical_tier: {} });
	ok('parsers brain health tiers', loading.decider === 'loading' && loading.gemma === 'connected' && down.decider === 'unreachable', `model_host loading → ${loading.decider} · unreachable → ${down.decider}`);

	// The live fused picture + feed through the real parsers (GET via the deck proxy).
	const snap = cityApi.parseCitySnapshot(await getJson(`${ORIGIN}/api/v1/city/entities`));
	const badUrn = snap.entities.filter((e) => !cityApi.parseUrn(e.urn));
	const kinds = [...new Set(snap.entities.map((e) => e.kind))];
	ok('parsers city snapshot (C-C)', snap.entities.length > 0 && badUrn.length === 0, `${snap.entities.length} entities · kinds ${kinds.join(',')} · ${badUrn.length} unparseable URNs`);
	const rows = cityApi.parseFeedRows(await getJson(`${ORIGIN}/api/v1/city/feed?limit=60`));
	const rails = rows.reduce((m, r) => ({ ...m, [r.actorKind]: (m[r.actorKind] ?? 0) + 1 }), {});
	ok('parsers city feed (C-C FeedItem)', rows.length > 0 && rows.every((r) => ['human', 'machine', 'system'].includes(r.actorKind)), `${rows.length} rows · ${JSON.stringify(rails)}`);

	// A recorded emulator tape (C-G GET through the deck's emulator proxy).
	let tapeOk = false;
	let tapeDetail = '';
	try {
		const t = tape.parseTape(await getJson(`${ORIGIN}/api/emulator/api/v1/emulator/runs/${REPLAY_RUN}`));
		const cams = [...new Set((t?.anpr ?? []).map((r) => r.cameraId))];
		tapeOk = !!t && t.anpr.length >= 2 && cams.length >= 2 && t.inputs.length > 0 && t.durationSec > 0;
		tapeDetail = t
			? `run ${t.runId}: ${t.anpr.length} anpr reads at ${cams.length} cameras · ${t.units.length} unit frames · ${t.inputs.length} inputs_doc · ${Math.round(t.durationSec)} s`
			: 'no tape frames';
	} catch (err) {
		tapeDetail = String(err).slice(0, 160);
	}
	ok(`parsers replay tape (run ${REPLAY_RUN})`, tapeOk, tapeDetail);
}

// ── layout: vitals · canvas · rail, the floors, the snapshot ───────────────

async function layoutCheck(browser) {
	const name = 'layout';
	const page = await newPage(browser);
	try {
		const phase = await openCanvas(page, '/gods-eye');
		ok(`${name} canvas ready`, phase === 'ready', `phase=${phase}`);
		if (phase !== 'ready') return;
		const t0 = Date.now();
		let rows = 0;
		let auditTab = false;
		while (Date.now() - t0 < 30000) {
			// the redesign keeps the rows under the bottom dock's Audit tab (a no-op today)
			if (!auditTab) auditTab = await ensureAuditRows(page, { timeout: 2000 });
			rows = await page.evaluate(() => document.querySelectorAll('[data-testid=fusion-rail] .f-row').length);
			if (rows >= FLOORS.rail) break;
			await sleep(500);
		}
		ok(`${name} fusion rail rows`, rows >= FLOORS.rail, `${rows} rows after ${Math.round((Date.now() - t0) / 1000)} s (floor ${FLOORS.rail})${auditTab ? ' · under the Audit tab' : ''}`);

		const floors = (s) => {
			const L = s?.layerStats ?? {};
			return {
				events: Number(L.events?.live ?? 0),
				flow: Number(L.flow?.coloured ?? 0),
				traces: Number(L.traces?.count ?? 0),
				signals: Number(L.signals?.count ?? 0),
				cameras: Number(L.cameras?.count ?? 0),
				enforcement: Number(L.enforcement?.count ?? 0),
			};
		};
		const met = (f) => f.events >= 1 && f.flow >= FLOORS.flow && f.traces >= 1 && f.signals >= FLOORS.signals && f.cameras >= FLOORS.cameras && f.enforcement >= 1;
		const { snap, ok: allMet } = await waitSnap(page, (s) => met(floors(s)), 45000, 1000);
		const f = floors(snap);
		ok(
			`${name} layer floors`,
			allMet,
			`events ${f.events} live (≥1) · flow ${f.flow} coloured (≥${FLOORS.flow}) · traces ${f.traces} (≥1) · signals ${f.signals} (≥${FLOORS.signals}) · cameras ${f.cameras} (≥${FLOORS.cameras}) · enforcement ${f.enforcement} (≥1)`,
		);
		const layers = snap?.layerStats ?? {};
		const viaCity = Object.entries(layers).filter(([, v]) => v.via === 'city-api').map(([k]) => k);
		ok(`${name} layers read the fused registry`, snap?.registry?.status === 'ok' && viaCity.length >= 4, `registry ${snap?.registry?.status} · ${snap?.registry?.entities} entities · via city-api: ${viaCity.join(',')}`);

		const v = snap?.vitals ?? null;
		ok(
			`${name} snapshot carries selection + vitals`,
			!!snap && 'selection' in snap && 'urn' in (snap.selection ?? {}) && !!v && typeof v.decisions?.total === 'number' && 'posture' in v && !!v.feeds,
			v
				? `posture ${v.posture ? `${v.posture.band} (${v.posture.source}${v.posture.ageSec != null ? `, ${v.posture.ageSec}s` : ''})` : 'none'} · decisions ${v.decisions.total} (${v.decisions.echallans} e-challan, ${v.decisions.dispatchRequests} dispatch, ${v.decisions.ambulance} 108) · units ${v.units.out} · ANPR ${v.anpr.hits15m} hits/${v.anpr.reads15m} reads · ingest ${v.feeds.ingestPerMin}/min · decider ${v.ai?.decider ?? '—'}`
				: 'no vitals on the snapshot',
		);

		const boxes = await page.evaluate(() => {
			const box = (el) => {
				const r = el?.getBoundingClientRect();
				return r ? { x: r.x, y: r.y, r: r.right, b: r.bottom, w: r.width, h: r.height } : null;
			};
			const b = (sel) => box(document.querySelector(sel));
			return {
				// V3-P6B: the page lives beside the V3 rail and under the V3 bars, so its widths are read against its own frame
				deck: b('.deck-main'),
				vitals: b('[data-testid=city-vitals]'),
				panel: b('.vitals-panel'),
				rail: b('.rail-panel'),
				canvas: b('.ge-canvas'),
				ethics: b('[data-testid=vitals-ethics]'),
				// the redesign's workspace frame (SPEC §5.3, §12.4)
				frame: !!document.querySelector('[data-ws="frame"]'),
				pane: b('[data-pane="map"]'),
				docks: [...document.querySelectorAll('[data-ws="frame"] [data-dock]')].map((d) => ({ id: d.getAttribute('data-dock'), open: d.getAttribute('data-open'), ...box(d) })),
			};
		});
		if (!boxes.frame) {
			return ok(`${name} workspace frame`, false, 'no [data-ws=frame] on /gods-eye — the v2 map mode geometry is the only layout (§12.4)');
		}
		// map mode (SPEC §6.2, §12.4): the canvas ≥ 95 % wide, the vitals card at the top right, no dock over the map pane
		{
			const pane = boxes.pane ?? boxes.canvas;
			const over = boxes.docks.filter((d) => d.w > 0 && d.h > 0 && !!pane && d.x < pane.r - 1 && d.r > pane.x + 1 && d.y < pane.b - 1 && d.b > pane.y + 1);
			// the canvas is ≥ 95 % of the PAGE's width (the area beside the V3 rail: the viewport less the rail), the card in its right quarter
			const FW = boxes.deck?.w ?? W;
			const FL = boxes.deck?.x ?? 0;
			const sane = !!pane && !!boxes.canvas && boxes.canvas.w >= FW * 0.95 && !!boxes.vitals && boxes.vitals.r - FL >= FW * 0.75 && boxes.vitals.y <= H * 0.3 && over.length === 0;
			ok(`${name} vitals · canvas · docks`, sane, `page frame ${Math.round(FW)} px · canvas ${Math.round(boxes.canvas?.w ?? 0)}×${Math.round(boxes.canvas?.h ?? 0)} · vitals card ${Math.round(boxes.vitals?.x ?? -1)}–${Math.round(boxes.vitals?.r ?? -1)} px from y=${Math.round(boxes.vitals?.y ?? -1)} · docks over the map pane: ${over.map((d) => d.id).join(',') || 'none'}`);
			// the full vitals (the Info tab) keep the ethics rails above the fold
			await ensureVitals(page, 'vitals-ethics');
			const ethics = await page.evaluate(() => {
				const r = document.querySelector('[data-testid=vitals-ethics]')?.getBoundingClientRect();
				return r ? { b: r.bottom, h: r.height } : null;
			});
			ok(`${name} ethics rails above the fold`, !!ethics && ethics.h > 0 && ethics.b <= H + 1, `ETHICS RAILS ends at y=${Math.round(ethics?.b ?? -1)} (viewport ${H})`);
		}

		// Honesty: a synthetic ingest feed is labelled SIMULATED, never dressed as live
		// (after the geometry: the redesign's layer tree sits in the left dock).
		if (v?.feeds?.simulated || Number(layers.flow?.simulated ?? 0) > 0) {
			await ensureLayers(page);
			const tags = await page.evaluate(([chipSel, vitalsSel]) => {
				const words = (el) => (el ? `${el.textContent ?? ''} ${el.getAttribute('title') ?? ''}`.replace(/\s+/g, ' ').trim() : null);
				return { chip: words(document.querySelector(chipSel)), vitals: words(document.querySelector(vitalsSel)) };
			}, [SEL.flowSimulated, SEL.vitalsSimulated]);
			ok(
				`${name} simulated feed labelled`,
				tags.chip != null && tags.vitals != null && textMatches(tags.chip, COPY.simulated) && textMatches(tags.vitals, COPY.simulated),
				`FLOW chip SIM tag '${tags.chip ?? '—'}' · vitals SIMULATED FEED pill '${tags.vitals ?? '—'}'`,
			);
		}

		const rb = await readback(page);
		ok(`${name} canvas renders`, (rb?.meanChroma ?? 0) > 0, `mean chroma ${fmt(rb?.meanChroma, 1)}`);
		// The artifact waits (bounded) for the basemap, so the picture is complete.
		await waitSnap(page, (s) => s.tilesLoaded || s.offlineDetected, 30000, 1000);
		mkdirSync(ARTIFACTS, { recursive: true });
		await page.screenshot({ path: path.join(ARTIFACTS, 'city-command-layout.png') });
	} finally {
		await page.close();
	}
}

// ── dossier: the earmarked vehicle, masked until an officer is named ───────

async function dossierCheck(browser) {
	const name = 'dossier';
	const body = await getJson(`${ORIGIN}/api/v1/city/entities?kinds=vehicle`);
	const vehicle = (body.entities ?? []).find((e) => e.props?.plate === PLATE);
	if (!vehicle) return ok(name, false, `no earmarked vehicle with plate ${masked(PLATE)} in the fused picture`);
	const urn = `vehicle:${vehicle.id}`;
	const page = await newPage(browser);
	try {
		const phase = await openCanvas(page, '/gods-eye');
		if (phase !== 'ready') return ok(name, false, `phase=${phase}`);
		const prefix = `veh:mark-${vehicle.id}`;
		const deadline = Date.now() + 30000;
		let spot = null;
		while (Date.now() < deadline && !spot) {
			spot = await spotInView(page, prefix);
			if (!spot) await sleep(1000);
		}
		if (!spot) return ok(`${name} marker on screen`, false, `'${prefix}' not on the canvas`);
		const cursor = await hoverAndClick(page, spot);
		const loaded = await page
			.waitForFunction(
				(u) => {
					const el = document.querySelector('[data-testid=entity-dossier]');
					return el?.dataset.urn === u && el.dataset.state === 'ok';
				},
				{ timeout: 12000 },
				urn,
			)
			.then(() => true)
			.catch(() => false);
		// the redesign's inspector lists links under its Links tab (today the dossier renders every block at once)
		if (loaded) await ensureInspectorTab(page, 'links', '.rel-chip');
		const opened =
			loaded &&
			(await page
				.waitForFunction(() => document.querySelectorAll('[data-testid=entity-dossier] .rel-chip').length > 0, { timeout: 8000 })
				.then(() => true)
				.catch(() => false));
		ok(`${name} marker click opens the dossier`, opened, `clicked ${prefix} at ${Math.round(spot.x)},${Math.round(spot.y)} (cursor '${cursor}')`);
		if (!opened) return;

		const read = () =>
			page.evaluate(() => {
				const el = document.querySelector('[data-testid=entity-dossier]');
				const chips = (rel) =>
					[...el.querySelectorAll(`.rel-group[data-relation="${rel}"] .rel-chip`)].map((c) => ({
						urn: c.dataset.urn,
						text: c.textContent.replace(/\s+/g, ' ').trim(),
					}));
				const plate = el.querySelector('[data-testid=dossier-plate] .plate');
				return {
					sightings: chips('sighting'),
					cameras: chips('seen_by_camera'),
					recs: chips('recommendation'),
					pursuits: chips('pursuit'),
					plate: plate?.textContent?.trim() ?? null,
					maskedAttr: plate?.getAttribute('data-masked') ?? null,
					text: el.textContent.replace(/\s+/g, ' '),
					audit: el.querySelectorAll('.a-row').length,
				};
			});
		const d = await read();
		// the audit rows: today in the dossier; the redesign's Activity tab (read after the links)
		if (await ensureInspectorTab(page, 'activity', '.a-row')) d.audit = (await read()).audit;
		const camIds = new Set(d.cameras.map((c) => c.urn.replace(/^camera:/, '')));
		const sightCams = d.sightings.map((s) => [...camIds].find((id) => s.text.includes(id)) ?? null);
		ok(
			`${name} sightings and their cameras`,
			d.sightings.length >= 4 && d.cameras.length >= 1 && sightCams.every(Boolean),
			`${d.sightings.length} sightings at ${[...new Set(sightCams)].join(', ')} · ${d.cameras.length} camera chips`,
		);
		const rec = d.recs.find((r) => r.urn.startsWith(`recommendation:${REC_PREFIX}`));
		let officer = null;
		if (rec) {
			const detail = await getJson(`${ORIGIN}/api/v1/city/entity/recommendation/${rec.urn.slice('recommendation:'.length)}`).catch(() => null);
			officer = detail?.entity?.props?.decided_by ?? null;
		}
		ok(
			`${name} approved recommendation + officer`,
			!!rec && /APPROVED/i.test(rec.text) && !!officer && rec.text.includes(officer),
			rec ? `${rec.urn.slice(0, 32)}… "${rec.text.slice(0, 90)}" (decided_by ${officer ?? '—'})` : `no ${REC_PREFIX} chip among ${d.recs.length} recommendations`,
		);
		const pursuit = d.pursuits.find((p) => p.urn.startsWith(`event:${PURSUIT_PREFIX}`));
		ok(`${name} pursuit linked`, !!pursuit, pursuit ? `${pursuit.urn.slice(0, 20)}… ${pursuit.text.slice(0, 70)}` : `${d.pursuits.length} pursuit chips`);
		ok(`${name} audit trail`, d.audit >= 3, `${d.audit} audit rows`);
		if (session.gate) {
			// The gate's signed-in officer IS the duty officer (C6): the plate is theirs to see.
			ok(`${name} plate shown to the signed-in officer (gate session)`, d.plate === PLATE && d.maskedAttr === 'false', `shown '${d.plate}' (data-masked=${d.maskedAttr})`);
			ok(`${name} masked path (skipped under the gate)`, true, 'a signed-in session names the officer — ops-wall-smoke covers the masked path hermetically');
			await page.screenshot({ path: path.join(ARTIFACTS, 'city-command-dossier.png') });
			return;
		}
		ok(
			`${name} plate masked without a duty officer`,
			d.plate === masked(PLATE) && d.maskedAttr === 'true' && !d.text.includes(PLATE),
			`shown '${d.plate}' (data-masked=${d.maskedAttr}); the full plate appears nowhere in the dossier: ${!d.text.includes(PLATE)}`,
		);

		// A named duty officer unmasks it (C6: the officer is on console): the
		// top bar's duty-officer (plan X12; §12.2 retires the inspector's own
		// dossier-officer prompt — one officer control, and it unmasks the
		// inspector's plate the same way). V3-P6B: the field sits in the officer pill's popover.
		await openOfficerField(page);
		const officerSel = await nameOfficer(page, 'Duty Officer CC Smoke', { prefer: ['duty-officer'], delay: 0 });
		await page.keyboard.press('Enter');
		await page.keyboard.press('Escape');
		const shown = await page
			.waitForFunction(
				(p) => document.querySelector('[data-testid=dossier-plate] .plate')?.textContent?.trim() === p,
				{ timeout: 5000 },
				PLATE,
			)
			.then(() => true)
			.catch(() => false);
		const after = await read();
		ok(`${name} plate shown to a named officer`, shown && after.maskedAttr === 'false', `shown '${after.plate}' (data-masked=${after.maskedAttr}) · officer typed into ${officerSel}`);
		await waitSnap(page, (s) => s.tilesLoaded || s.offlineDetected, 20000, 1000);
		await page.screenshot({ path: path.join(ARTIFACTS, 'city-command-dossier.png') });
	} finally {
		await page.close();
	}
}

// ── rail: a row click flies to its entity and highlights it ────────────────

const POINT_KINDS = ['camera', 'sighting', 'recommendation', 'vehicle', 'dispatch', 'unit', 'junction'];

/**
 * The v2 row surface (UI-S7B repoint, audit E-WORKSPACE): the legacy fusion
 * rail is not the v2 surface — its bottom-dock audit rows carry the feed
 * row's FIRST urn (usually the event's), so no row named a located point
 * entity and the check failed on main. Equal strength on the Explorer: the
 * kind tree row opens the object TABLE, whose rows name located point
 * entities; clicking a row selects the object everywhere, and the
 * inspector's own "Show on map" action flies the camera to it (§12.4).
 */
async function railCheck(browser) {
	const name = 'rail';
	const page = await newPage(browser);
	try {
		const phase = await openCanvas(page, WORKSPACE);
		if (phase !== 'ready') return ok(name, false, `phase=${phase}`);
		await waitSnap(page, (s) => s.registry?.status === 'ok', 20000);
		const registry = await getJson(`${ORIGIN}/api/v1/city/entities`).catch(() => null);
		const located = new Map();
		for (const e of registry?.entities ?? []) {
			if (typeof e.lon === 'number' && typeof e.lat === 'number' && typeof e.urn === 'string' && POINT_KINDS.includes(e.urn.split(':')[0])) located.set(e.urn, e);
		}
		// Explorer: the Object types tree lists every kind with rows — open the
		// left dock's Explorer tab the way an operator does (the dock is closed
		// by default), then pick the first kind whose table can hold a located
		// point entity.
		const readKindRows = () =>
			page.evaluate(() =>
				[...document.querySelectorAll('[data-testid="explorer-kinds"] [data-kind]')].map((n) => ({ kind: n.getAttribute('data-kind'), count: Number(n.getAttribute('data-count') ?? -1) })),
			);
		let kindRows = await readKindRows();
		if (!kindRows.length) {
			const opened = await ensureRail(page, 'explorer', '[data-testid="explorer-kinds"]', { timeout: 10000 });
			if (!opened && !(await page.$('[data-testid="explorer-kinds"]'))) return ok(name, false, 'the Explorer tab never opened (no [data-rail=explorer] click, no tree)');
			kindRows = await readKindRows();
		}
		const kind = kindRows.find((k) => located.size > 0 && k.count > 0 && [...located.keys()].some((u) => u.startsWith(`${k.kind}:`)));
		if (!kind) return ok(name, false, `no Explorer kind names a located point entity of the live registry (${kindRows.length} kinds · ${located.size} located point entities)`);
		await page.evaluate((k) => document.querySelector(`[data-testid="explorer-kinds"] [data-kind="${k}"]`)?.click(), kind.kind);
		const tableUp = await page
			.waitForFunction((k) => !!document.querySelector(`[data-testid="object-table"] tr[data-urn^="${k}:"]`), { timeout: 15000 }, kind.kind)
			.then(() => true)
			.catch(() => false);
		if (!tableUp) return ok(name, false, `the object table never listed a ${kind.kind} row after the Explorer kind click`);
		// the located entity's row, in the table
		const urn = [...located.keys()].find((u) => u.startsWith(`${kind.kind}:`) && !!located.get(u));
		const e = located.get(urn);
		const clicked = await page.evaluate((u) => {
			const row = document.querySelector(`[data-testid="object-table"] tr[data-urn="${u}"]`);
			row?.click();
			return !!row;
		}, urn);
		const selected = await page
			.waitForFunction((u) => window.__GODS_EYE__?.selection?.urn === u, { timeout: 8000 }, urn)
			.then(() => true)
			.catch(() => false);
		// the row carries the selection mark while the table is up (the
		// show-on-map click below switches the centre to the map)
		const linked = await page.evaluate(rowMarked, `[data-testid="object-table"] tr[data-urn="${urn}"]`);
		ok(`${name} table row selects the entity`, clicked && selected && linked, `${urn} (${kind.kind} row clicked; selection ${selected ? 'set' : 'not set'} · row marked ${linked})`);
		if (!selected) return;
		// the inspector opened on it; its Actions tab carries "Show on map".
		// The inspector's module loads with the first pick (FIX-E-PERF2; the
		// operator's first press prefetches it): wait for the inspector to show
		// THIS entity before reading its tabs, as an officer waits for the panel
		// — the tab lookup itself never waits, so a still-loading inspector read
		// as "no Show on map" (FIX-F-REGR item 2).
		const showSel = '[data-testid="entity-dossier"] li[data-action-id="ws.show-on-map"] button';
		const inspected = await page
			.waitForFunction((u) => document.querySelector('[data-testid="entity-dossier"]')?.getAttribute('data-urn') === u, { timeout: 15000 }, urn)
			.then(() => true)
			.catch(() => false);
		if (!inspected) return ok(name, false, `the inspector never showed the selected entity (${urn}) within 15 s of the pick`);
		await ensureInspectorTab(page, 'actions', 'li[data-action-id]', { timeout: 12000 });
		const showBtn = await page.waitForSelector(showSel, { timeout: 8000 }).catch(() => null);
		if (!showBtn) return ok(name, false, 'no "Show on map" action on the inspector (the Actions tab must offer it for a located entity)');
		// The flight is read from the page's own fly bookkeeping (flyMs: request
		// → landing, page clock). One sample is not a fair measure under load
		// (audit E-S7B F11: 920–1106 ms normally, 3254 ms once at load average
		// ~26), so the operator's action is repeated: THREE flights, the camera
		// panned away by a canvas drag before each re-flight. EVERY flight must
		// land on the entity (the S5 kill: a show-on-map that never flies fails
		// on the first one); the MEDIAN landing time is held to the budget, and
		// all three times are reported.
		const near = (s) =>
			!!s?.camera &&
			s.selection?.urn === urn &&
			s.selection?.flyOutcome === 'landed' &&
			s.selection?.flyMs != null &&
			Math.abs(s.camera.lon - e.lon) <= FLY_TOLERANCE_DEG &&
			Math.abs(s.camera.lat - e.lat) <= FLY_TOLERANCE_DEG;
		const panAway = async () => {
			const box = await page.evaluate(() => {
				const c = document.querySelector('.ge-wrap canvas') ?? document.querySelector('canvas');
				const b = c?.getBoundingClientRect();
				return b ? { x: b.x, y: b.y, w: b.width, h: b.height } : null;
			});
			if (!box) return null;
			const x0 = box.x + box.w * 0.5;
			const y0 = box.y + box.h * 0.5;
			await page.mouse.move(x0, y0);
			await page.mouse.down();
			for (let i = 1; i <= 12; i++) await page.mouse.move(x0 - (box.w * 0.35 * i) / 12, y0 - (box.h * 0.3 * i) / 12);
			await page.mouse.up();
			await sleep(1500); // the 1 Hz snapshot catches the moved camera
			const c = (await snapshot(page).catch(() => null))?.camera;
			return c ? Math.round(Math.hypot((c.lon - e.lon) * 102_000, (c.lat - e.lat) * 110_540)) : null;
		};
		const flights = [];
		for (let i = 0; i < 3; i++) {
			const awayM = i === 0 ? null : await panAway();
			let btn = await page.$(showSel);
			if (!btn) {
				await ensureInspectorTab(page, 'actions', 'li[data-action-id]', { timeout: 12000 });
				btn = await page.$(showSel);
			}
			if (!btn) {
				flights.push({ arrived: false, flyMs: null, awayM, why: 'the Show on map action was gone' });
				break;
			}
			const t0 = Date.now();
			await btn.click();
			const { snap, ok: arrived } = await waitSnap(page, near, FLY_BUDGET_MS + 6000, 100);
			flights.push({ arrived, flyMs: snap?.selection?.flyMs ?? null, wallMs: Date.now() - t0, awayM, cam: snap?.camera ?? null });
			if (!arrived) break;
		}
		const landed = flights.filter((f) => f.arrived && f.flyMs != null);
		const times = landed.map((f) => f.flyMs).sort((a, b) => a - b);
		const median = times.length === 3 ? times[1] : null;
		ok(
			`${name} show-on-map flies to the entity`,
			landed.length === 3 && median != null && median <= FLY_BUDGET_MS,
			`${urn} at ${fmt(e.lon)},${fmt(e.lat)}: ${flights
				.map((f, i) => `flight ${i + 1}${f.awayM != null ? ` (from ${f.awayM} m away)` : ''} ${f.arrived ? `landed ${f.flyMs} ms` : `DID NOT LAND${f.why ? ` — ${f.why}` : ''} (camera ${fmt(f.cam?.lon)},${fmt(f.cam?.lat)})`}`)
				.join(' · ')} — median ${median ?? '—'} ms (≤ ${FLY_BUDGET_MS} ms; every flight lands ≤ ${FLY_TOLERANCE_DEG}°)`,
		);
		await sleep(1500); // the 1 Hz tick re-applies the highlight after any layer redraw
		const s2 = await snapshot(page);
		const dossierUrn = await page.evaluate(() => document.querySelector('[data-testid=entity-dossier]')?.dataset.urn ?? null);
		const halo = s2?.selection?.halo;
		ok(
			`${name} entity highlighted`,
			!!halo && Math.abs(halo.lon - e.lon) < 0.0015 && Math.abs(halo.lat - e.lat) < 0.0015 && (s2?.selection?.highlighted ?? 0) >= 1 && dossierUrn === urn,
			`halo ${halo ? `${fmt(halo.lon)},${fmt(halo.lat)}` : '—'} · ${s2?.selection?.highlighted ?? 0} primitives emphasised · inspector ${dossierUrn ?? '—'}`,
		);
		await page.screenshot({ path: path.join(ARTIFACTS, 'city-command-rail.png') });
	} finally {
		await page.close();
	}
}

// ── feeds: an empty answer is not a fault; schematic geometry is counted ───

async function feedsCheck(browser) {
	const name = 'feeds';
	// The live picture with NO units (status ok): an empty-but-healthy feed.
	const real = await getJson(`${ORIGIN}/api/v1/city/entities`);
	const noUnits = {
		...real,
		entities: (real.entities ?? []).filter((e) => e.kind !== 'unit'),
		feeds: { ...(real.feeds ?? {}), unit: { count: 0, newest_t: null, age_sec: null, unlocated: 0, status: 'ok' } },
	};
	let schematicServed = 0;
	let osmServed = 0;
	const page = await newPage(browser);
	await page.setRequestInterception(true);
	page.on('request', (req) => {
		const u = new URL(req.url());
		if (u.origin === ORIGIN && u.pathname === '/api/v1/city/entities' && !u.search) {
			req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...noUnits, as_of: new Date().toISOString() }) }).catch(() => undefined);
			return;
		}
		if (u.origin === ORIGIN && u.pathname === '/api/v1/spatial/segments' && req.method() === 'GET') {
			// The real segments, every other one served as a SCHEMATIC chord (C-K).
			getJson(u.href)
				.then((body) => {
					const segs = (body.segments ?? []).map((sg, i) => ({ ...sg, geometry_basis: i % 2 ? 'schematic' : 'osm_display' }));
					schematicServed = segs.filter((sg) => sg.geometry_basis === 'schematic').length;
					osmServed = segs.length - schematicServed;
					return req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...body, segments: segs }) });
				})
				.catch(() => req.continue().catch(() => undefined));
			return;
		}
		req.continue().catch(() => undefined);
	});
	try {
		const phase = await openCanvas(page, '/gods-eye');
		if (phase !== 'ready') return ok(name, false, `phase=${phase}`);
		const units = await waitSnap(page, (s) => s.registry?.status === 'ok' && s.registry?.kinds?.unit === 0, 20000, 500);
		await sleep(1500);
		await ensureLayers(page); // the redesign's LayerTree (a no-op today: the HUD chips)
		const chip = await page.evaluate(() => {
			const el = document.querySelector('[data-layer=units]');
			return el ? { warn: el.classList.contains('warn'), title: el.getAttribute('title') ?? '' } : null;
		});
		ok(
			`${name} an empty-but-healthy UNITS feed shows no ⚠`,
			units.ok && !!chip && !chip.warn && textIs(chip.title, COPY.noUnitsFielded),
			chip ? `UNITS chip warn=${chip.warn} · hint '${chip.title}'` : 'no UNITS chip',
		);
		const flow = await waitSnap(page, (s) => Number(s.layerStats?.flow?.schematic ?? 0) > 0, 30000, 500);
		const f = flow.snap?.layerStats?.flow ?? {};
		const hint = await page.evaluate(() => document.querySelector('[data-layer=flow]')?.getAttribute('title') ?? '');
		ok(
			`${name} schematic geometry is counted in the FLOW hint`,
			flow.ok && Number(f.schematic) === schematicServed && Number(f.osm) === osmServed && textHas(hint, `${osmServed} OSM-traced · ${schematicServed} schematic (dashed)`),
			`served ${osmServed} OSM-traced + ${schematicServed} schematic · layer ${f.osm ?? '—'} / ${f.schematic ?? '—'} · hint '${hint.slice(0, 120)}'`,
		);
	} finally {
		await page.close();
	}
}

// ── posture: a city band HELD for hours on a healthy engine is not STALE ───

async function postureCheck(browser) {
	const name = 'posture';
	// No active event carries a band (as on live while the only event is
	// planning): CITY POSTURE speaks for the city band — entered 3 h 50 min ago,
	// the engine's newest evaluation 2 s ago, inputs simulated.
	const real = await getJson(`${ORIGIN}/api/v1/city/entities`);
	const unbanded = { ...real, entities: (real.entities ?? []).map((e) => (e.kind === 'event' ? { ...e, band: null } : e)) };
	const HELD_SEC = 3 * 3600 + 50 * 60;
	const since = new Date(Date.now() - HELD_SEC * 1000).toISOString();
	const page = await newPage(browser);
	await page.setRequestInterception(true);
	page.on('request', (req) => {
		const u = new URL(req.url());
		if (u.origin === ORIGIN && u.pathname === '/api/v1/city/entities' && !u.search) {
			req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...unbanded, as_of: new Date().toISOString() }) }).catch(() => undefined);
			return;
		}
		if (u.origin === ORIGIN && u.pathname === '/api/v1/adaptive/status' && req.method() === 'GET') {
			getJson(u.href)
				.then((body) =>
					req.respond({
						status: 200,
						contentType: 'application/json',
						body: JSON.stringify({
							...body,
							city_band: { band: 'GREEN', since, subjects: 1, driver: null, simulated_feed: true, stale: false, stale_reason: null, stale_since: null },
							engine_loop: { ...(body.engine_loop ?? {}), last_tick_age_sec: 2 },
						}),
					}),
				)
				.catch(() => req.continue().catch(() => undefined));
			return;
		}
		req.continue().catch(() => undefined);
	});
	try {
		const phase = await openCanvas(page, '/gods-eye');
		if (phase !== 'ready') return ok(name, false, `phase=${phase}`);
		const held = await waitSnap(page, (s) => s.vitals?.posture?.source === 'city-band' && s.vitals.posture.heldSec != null, 20000, 500);
		const p = held.snap?.vitals?.posture ?? {};
		await ensureVitals(page, 'vitals-posture'); // the redesign's map mode: the full vitals in the Info tab
		const dom = await page.evaluate(() => {
			const sec = document.querySelector('[data-testid=vitals-posture]');
			const pill = sec?.querySelector('[data-testid=vitals-posture-simulated]');
			const sr = sec?.getBoundingClientRect();
			const pr = pill?.getBoundingClientRect();
			return {
				staleTag: !!sec?.querySelector('[data-testid=vitals-posture-stale]'),
				held: sec?.querySelector('[data-testid=vitals-posture-held]')?.textContent?.replace(/\s+/g, ' ').trim() ?? '',
				pill: pr && sr ? { right: Math.round(pr.right), edge: Math.round(sr.right), width: Math.round(pr.width), text: `${pill.textContent ?? ''} ${pill.getAttribute('title') ?? ''}`.replace(/\s+/g, ' ').trim() } : null,
			};
		});
		ok(
			`${name} a city band held 3 h 50 min on a healthy engine is aged from its newest reading — never STALE`,
			held.ok && p.band === 'GREEN' && p.basis === 'reading' && p.stale === false && (p.ageSec ?? 999) < 60 && !dom.staleTag,
			`${p.band ?? '—'} · basis ${p.basis ?? '—'} · age ${p.ageSec ?? '—'} s · stale ${p.stale} · STALE tag ${dom.staleTag}`,
		);
		ok(
			`${name} …how long it has held is its own line ('Held 3 h 50 min · since HH:MM IST')`,
			Math.abs((p.heldSec ?? 0) - HELD_SEC) < 120 && textMatches(dom.held, COPY.heldLine),
			`${dom.held || 'no held line'} · heldSec ${p.heldSec ?? '—'}`,
		);
		ok(
			`${name} …its SIMULATED FEED pill wraps inside the rail (never clipped)`,
			!!dom.pill && dom.pill.width > 0 && dom.pill.right <= dom.pill.edge && textMatches(dom.pill.text, COPY.simulated),
			dom.pill ? `'${dom.pill.text}' · pill right ${dom.pill.right} ≤ section edge ${dom.pill.edge}` : 'no SIMULATED FEED pill',
		);
		const box = await page.$eval('[data-testid=vitals-posture]', (e) => {
			const r = e.getBoundingClientRect();
			return { x: Math.max(0, r.x - 8), y: Math.max(0, r.y - 8), width: r.width + 16, height: r.height + 16 };
		});
		await page.screenshot({ path: path.join(ARTIFACTS, 'city-command-posture.png'), clip: box });
	} finally {
		await page.close();
	}
}

// ── replay: an emulator tape on the canvas clock ───────────────────────────

async function replayCheck(browser) {
	const name = 'replay';
	const run20 = await getJson(`${ORIGIN}/api/emulator/api/v1/emulator/runs/${REPLAY_RUN}`).catch(() => null);
	const reads = (run20?.tape?.frames ?? []).filter((f) => f.kind === 'anpr_read' && f.payload?.plate);
	if (!reads.length) return ok(name, false, `run ${REPLAY_RUN} carries no anpr_read frames (emulator /runs/${REPLAY_RUN})`);
	// The tape's vehicle under watch: a plate the sweep matched (a hit), then the most reads.
	const byPlate = new Map();
	for (const f of reads) byPlate.set(f.payload.plate, [...(byPlate.get(f.payload.plate) ?? []), f]);
	const hits = (fs) => fs.filter((f) => f.payload.matched_plate_hit).length;
	const [plate, hops] = [...byPlate.entries()].sort((a, b) => hits(b[1]) - hits(a[1]) || b[1].length - a[1].length)[0];
	const page = await newPage(browser);
	try {
		const phase = await openCanvas(page, '/gods-eye');
		if (phase !== 'ready') return ok(name, false, `phase=${phase}`);
		// hardening (gate C: this wait timed out once at 30 s under load): every
		// wait here is caught and reported, never allowed to abort the smoke.
		const toggleUp = await page.waitForSelector('[data-testid=replay-toggle]', { timeout: 20000 }).then(() => true).catch(() => false);
		if (!toggleUp) return ok(name, false, 'no [data-testid=replay-toggle] on the canvas (the Timeline control must exist)');
		await page.click('[data-testid=replay-toggle]');
		const barShown = await page.waitForSelector('[data-testid=replay-bar]', { timeout: 20000 }).then(() => true).catch(() => false);
		if (!barShown) return ok(name, false, 'the replay bar never mounted after the toggle (20 s)');
		// The picker lists the runs ledger once it answers; pick the run only then.
		const listed = await page
			.waitForFunction(
				(id) => [...(document.querySelector('[data-testid=replay-run]')?.options ?? [])].some((o) => o.value === String(id)),
				{ timeout: 15000 },
				REPLAY_RUN,
			)
			.then(() => true)
			.catch(() => false);
		ok(`${name} run picker lists run ${REPLAY_RUN}`, listed, listed ? 'from GET /api/emulator/api/v1/emulator/runs' : 'run not in the ledger listing');
		if (!listed) return;
		await page.select('[data-testid=replay-run]', String(REPLAY_RUN));
		const loaded = await page
			.waitForFunction((id) => {
				const bar = document.querySelector('[data-testid=replay-bar]');
				return bar?.dataset.status === 'ready' && window.__GODS_EYE__?.replay?.runId === id && (window.__GODS_EYE__?.replay?.tracks ?? 0) > 0;
			}, { timeout: 20000 }, REPLAY_RUN)
			.then(() => true)
			.catch(() => false);
		const s0 = await snapshot(page);
		ok(`${name} tape loaded`, loaded, `run ${s0?.replay?.runId ?? '—'} · ${s0?.replay?.tracks ?? 0} tracks · ${Math.round(s0?.replay?.durationSec ?? 0)} s · status ${s0?.replay?.status ?? '—'}`);
		if (!loaded) return;

		const pills = () =>
			page.evaluate((src) => {
				const vis = (sel) => {
					const el = document.querySelector(sel);
					const r = el?.getBoundingClientRect();
					return !!r && r.width > 0 && r.height > 0 && new RegExp(src, 'i').test(el.textContent ?? '');
				};
				return { bar: vis('[data-testid=replay-emulated-pill]'), chip: vis('[data-testid=replay-pill]') };
			}, COPY.replayEmulated.source);
		const scrub = (sec) =>
			page.evaluate((v) => {
				const input = document.querySelector('[data-testid=replay-scrubber]');
				input.value = String(v);
				input.dispatchEvent(new Event('input', { bubbles: true }));
			}, sec);
		const label = masked(plate);
		const visits = [];
		let pillsHeld = true;
		const times = [...new Set(hops.map((f) => f.t_sec))].sort((a, b) => a - b);
		for (const t of times) {
			await scrub(t + 1);
			await sleep(700);
			const s = await snapshot(page);
			const marker = Object.values(s?.replay?.markers ?? {}).find((m) => m.label === label || m.label === plate);
			if (marker) visits.push({ t, camera: marker.camera, lon: marker.lon, lat: marker.lat });
			const p = await pills();
			pillsHeld = pillsHeld && p.bar && p.chip;
		}
		const cams = [...new Set(visits.map((v) => v.camera).filter((c) => /^EM-CAM/.test(c ?? '')))];
		const first = visits[0];
		const last = visits[visits.length - 1];
		const movedM = first && last ? Math.hypot((last.lon - first.lon) * 102_000, (last.lat - first.lat) * 110_540) : 0;
		ok(
			`${name} scrubbing moves the vehicle across EM-CAM hops`,
			cams.length >= 2 && movedM > 50,
			`${label}: ${visits.map((v) => `t+${Math.round(v.t)}s ${v.camera}`).join(' → ')} · moved ${Math.round(movedM)} m`,
		);
		ok(`${name} EMULATED pills stay visible`, pillsHeld, 'scrubber-bar pill and canvas chip at every scrub position');
		await page.screenshot({ path: path.join(ARTIFACTS, 'city-command-replay.png') });

		await leaveReplay(page); // today the rail's LIVE mode button; the redesign's Live/Replay control
		const live = await waitSnap(page, (s) => s.replay === null && (s.layerStats?.traces?.count ?? 0) >= 0, 5000);
		ok(`${name} LIVE restores the live picture`, live.ok, `replay ${live.snap?.replay === null ? 'off' : 'still on'}`);
	} finally {
		await page.close();
	}
}

// ── cockpit (opt-in): plan → RECOMMENDED spine + dashed alternates ─────────

async function cockpitCheck(browser) {
	const name = 'cockpit';
	const page = await newPage(browser);
	let planDoc = null;
	page.on('response', async (res) => {
		if (/\/api\/convoy\/movements\/[^/]+\/plan$/.test(res.url()) && res.request().method() === 'POST') {
			planDoc = await res.json().catch(() => null);
		}
	});
	try {
		const phase = await openCanvas(page, WORKSPACE);
		if (phase !== 'ready') return ok(name, false, `phase=${phase}`);
		const pick = (sel, text) =>
			page.evaluate(
				(s, t) => {
					const el = document.querySelector(s);
					const opt = [...(el?.options ?? [])].find((o) => o.textContent.trim() === t);
					if (!el || !opt) return false;
					el.value = opt.value;
					el.dispatchEvent(new Event('change', { bubbles: true }));
					return true;
				},
				sel,
				text,
			);
		await ensurePlanner(page); // the redesign's PlanPanel sits behind [data-rail=plan]; a no-op today
		const chosen = (await pick('[data-testid=planner-origin]', 'Nabanna')) && (await pick('[data-testid=planner-destination]', 'Kolkata Airport'));
		await page.evaluate(() => [...document.querySelectorAll('.class-pill')].find((b) => b.textContent.trim() === 'Z')?.click());
		ok(`${name} form`, chosen, 'Nabanna → Kolkata Airport · class Z');
		// An escort already running for an active movement is ADOPTED by the
		// planner (STOP instead of PLAN): the brain never re-plans under a live
		// convoy, so the plan check cannot run until it is stopped.
		await sleep(2500);
		const adopted = await page.evaluate(() => document.querySelector('[data-template=convoy-hud]')?.getAttribute('data-phase') === 'escorting');
		if (adopted) return ok(`${name} (skipped)`, true, 'an escort is running and the planner adopted it — stop it before a plan check');
		// Spine counts before the plan: the NEW event's RECOMMENDED / dashed
		// segments must add to them (an older plan of the same route may be on
		// the canvas already).
		const before = (await snapshot(page))?.layerStats?.events ?? {};
		const recBefore = Number(before.recommended ?? 0);
		const altBefore = Number(before.alternates ?? 0);
		const planned = await page.evaluate(() => {
			const btn = [...document.querySelectorAll('button')].find((b) => /plan corridor/i.test(b.textContent ?? ''));
			btn?.click();
			return !!btn;
		});
		if (!planned) return ok(name, false, 'no PLAN button');
		const answered = await page
			.waitForSelector('[data-testid=planner-candidates]', { timeout: 240000 })
			.then(() => true)
			.catch(() => false);
		const tAnswer = Date.now();
		ok(`${name} plan answered`, answered && !!planDoc, planDoc ? `status ${planDoc.status} · event ${planDoc.event_id ?? '—'} · ${(planDoc.alternate_routes ?? []).length} alternates · decider_pick ${planDoc.decider_pick ? planDoc.decider_pick.route_id : 'none'}` : 'no plan document');
		if (!answered || !planDoc) return;
		const eventId = planDoc.event_id;
		const alternates = (planDoc.alternate_routes ?? []).length;
		const spines = await waitSnap(
			page,
			(s) =>
				(s.layerStats?.events?.recommended ?? 0) > recBefore &&
				(alternates === 0 || (s.layerStats?.events?.alternates ?? 0) > altBefore),
			5000,
			250,
		);
		const L = spines.snap?.layerStats?.events ?? {};
		ok(
			`${name} RECOMMENDED spine + dashed alternates`,
			spines.ok && !!eventId,
			`within ${Date.now() - tAnswer} ms of the answer: RECOMMENDED segments ${recBefore} → ${L.recommended ?? 0}, dashed alternate segments ${altBefore} → ${L.alternates ?? 0} (plan has ${alternates} alternates)`,
		);
		const ev = eventId ? await getJson(`${ORIGIN}/api/v1/city/entity/event/${eventId}`).catch(() => null) : null;
		const c = ev?.entity;
		const focused = await waitSnap(
			page,
			(s) => s.subjectLockId === eventId || (!!c && !!s.camera && Math.abs(s.camera.lon - c.lon) <= FLY_TOLERANCE_DEG && Math.abs(s.camera.lat - c.lat) <= FLY_TOLERANCE_DEG),
			8000,
		);
		ok(`${name} camera focuses the plan`, focused.ok, `lock ${focused.snap?.subjectLockId ?? '—'} · camera ${fmt(focused.snap?.camera?.lon)},${fmt(focused.snap?.camera?.lat)}${c ? ` vs event ${fmt(c.lon)},${fmt(c.lat)}` : ''}`);
		const eta = await page.evaluate(() => Number(document.querySelector('[data-template=convoy-hud]')?.getAttribute('data-eta-sec') || 0));
		ok(`${name} ConvoyHud ETA`, eta > 0, `${Math.round(eta)} s (estimated_time_sec of the recommended route)`);
		await page.screenshot({ path: path.join(ARTIFACTS, 'city-command-cockpit.png') });
	} finally {
		await page.close();
	}
}

// ── escort (opt-in): the convoy marker moves ───────────────────────────────

async function escortCheck(browser) {
	const name = 'escort';
	const page = await newPage(browser);
	try {
		const phase = await openCanvas(page, '/gods-eye');
		if (phase !== 'ready') return ok(name, false, `phase=${phase}`);
		const first = await waitSnap(page, (s) => (s.registry?.convoys?.length ?? 0) > 0 && (s.layerStats?.convoy?.count ?? 0) > 0, 20000);
		let a = first.snap?.registry?.convoys?.[0];
		if (!a) return ok(name, false, 'no escort reporting GPS (start one from the VVIP corridor module — WP-12)');
		// Pairs of snapshots 5 s apart; a pair can straddle one slow fused-picture
		// poll on a loaded host, so up to three pairs are tried (each reported).
		const pairs = [];
		let movedM = 0;
		for (let i = 0; i < 3 && movedM <= 1; i++) {
			if (i > 0) a = (await snapshot(page))?.registry?.convoys?.find((c) => c.id === a.id) ?? a;
			await sleep(5000);
			const b = (await snapshot(page))?.registry?.convoys?.find((c) => c.id === a.id);
			movedM = b ? Math.hypot((b.lon - a.lon) * 102_000, (b.lat - a.lat) * 110_540) : 0;
			pairs.push(`${movedM.toFixed(1)} m`);
		}
		const marker = await page.evaluate((id) => (window.__GODS_EYE__?.locate?.(`cvy:${id}`) ?? []).length, a.id);
		ok(`${name} convoy marker moves`, movedM > 1, `convoy ${a.id} (${a.source}) moved ${pairs.join(' / ')} between snapshots 5 s apart · marker unobstructed on screen ${marker > 0}`);
		await escortHudCheck(browser, a.id);
	} finally {
		await page.close();
	}
}

/**
 * '/' adopts the running escort and its HUD mirrors the brain's C-J status
 * doc — READ ONLY: nothing is approved, rejected, stopped or cleared here.
 */
async function escortHudCheck(browser, movementId) {
	const name = 'escort HUD';
	const doc = await getJson(`${ORIGIN}/api/convoy/movements/${encodeURIComponent(movementId)}/escort`).catch(() => null);
	if (!doc || (doc.status !== 'running' && doc.status !== 'waiting_for_gps')) {
		return ok(`${name} (skipped)`, true, `escort status for ${movementId}: ${doc?.status ?? 'unreadable'}`);
	}
	const page = await newPage(browser);
	try {
		await page.goto(`${ORIGIN}${WORKSPACE}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
		const adopted = await page
			.waitForFunction(() => document.querySelector('[data-template=convoy-hud]')?.getAttribute('data-phase') === 'escorting', { timeout: 20000 })
			.then(() => true)
			.catch(() => false);
		ok(`${name} '/' adopts the running escort`, adopted, adopted ? `movement ${movementId}` : 'the HUD never reached ESCORT LIVE');
		if (!adopted) return;
		await sleep(3500); // two follower reads (1.5 s)
		const hud = await page.evaluate(() => ({
			hold: !!document.querySelector('[data-testid=convoy-hud-hold]'),
			approvals: document.querySelectorAll('[data-testid=convoy-hud-approval]').length,
			emulated: !!document.querySelector('[data-template=convoy-hud] [data-testid=convoy-hud-emulated]') || /emulated gps/i.test(document.querySelector('[data-testid=convoy-hud-provenance]')?.textContent ?? ''),
			simulated: !!document.querySelector('[data-testid=convoy-hud-simulated]'),
		}));
		const fresh = (await getJson(`${ORIGIN}/api/convoy/movements/${encodeURIComponent(movementId)}/escort`).catch(() => null)) ?? doc;
		const pending = (fresh.pending_approvals ?? []).filter((x) => typeof x?.approval_id === 'string' && x.approval_id && (x.status == null || x.status === 'pending')).length;
		const wantEmulated = fresh.gps?.mode === 'emulated' || fresh.position?.source === 'emulated_gps';
		const wantSimulated =
			fresh.traffic_feed?.simulated === true ||
			(fresh.pending_approvals ?? []).some((x) => x?.simulated === true || [].concat(x?.data_quality ?? []).includes('synthetic'));
		ok(
			`${name} mirrors the brain (hold · approvals · provenance)`,
			hud.hold === !!fresh.hold && hud.approvals === pending && (!wantEmulated || hud.emulated) && hud.simulated === wantSimulated,
			`hold ${hud.hold}/${!!fresh.hold} · approvals ${hud.approvals}/${pending} · EMULATED GPS ${hud.emulated}/${wantEmulated} · SIMULATED FEED ${hud.simulated}/${wantSimulated}`,
		);
	} finally {
		await page.close();
	}
}

// ── hidden: a background /ops tab stops polling the flow layer ────────────

async function hiddenCheck(browser) {
	const name = 'hidden';
	const page = await newPage(browser, 1600, 900);
	let front = null;
	try {
		const posts = [];
		page.on('request', (req) => {
			if (req.method() === 'POST' && req.url().includes('/api/v1/traffic/live')) posts.push(Date.now());
		});
		const phase = await openCanvas(page, '/ops');
		if (phase !== 'ready') return ok(name, false, `phase=${phase}`);
		await sleep(10000);
		const visiblePosts = posts.length;
		// Another tab in front: this one is hidden now (a new tab opens activated).
		front = await browser.newPage();
		await front.goto('about:blank');
		await front.bringToFront();
		const hidden = await page.evaluate(() => document.visibilityState);
		const since = Date.now();
		await sleep(30000);
		const hiddenPosts = posts.filter((t) => t > since + 500).length;
		ok(
			`${name} no flow polls from a hidden tab`,
			hidden === 'hidden' && visiblePosts > 0 && hiddenPosts === 0,
			`visibility ${hidden}: ${visiblePosts} POST /traffic/live while visible (10 s), ${hiddenPosts} while hidden (30 s)`,
		);
	} finally {
		await front?.close();
		await page.close();
	}
}

// ── plates: C6 at every text sink, no duty officer named ──────────────────

/**
 * Switch layers off as an operator would: today's HUD chips (a click toggles,
 * `.off` when off); the redesign's LayerTree rows (behind the Layers tab, an
 * EyeToggle in the row, `aria-pressed=false` / `data-visible=false` when off).
 */
async function layersOff(page, ids) {
	await ensureLayers(page);
	await page.evaluate((list) => {
		const off = (el) => el.classList.contains('off') || el.getAttribute('aria-pressed') === 'false' || el.getAttribute('data-visible') === 'false';
		for (const id of list) {
			const el = document.querySelector(`.chip.layer[data-layer="${id}"], [data-layer="${id}"]`);
			if (el && !off(el)) (el.querySelector('.eye, [data-eye]') ?? el).click();
		}
	}, ids);
}

/** Every text a page shows or announces: rendered text + title / aria-label attributes. */
const pageTexts = (page) =>
	page.evaluate(() => {
		const attrs = [...document.querySelectorAll('[title],[aria-label]')]
			.map((el) => `${el.getAttribute('title') ?? ''} ${el.getAttribute('aria-label') ?? ''}`)
			.join(' ');
		return `${document.body.innerText} ${attrs}`;
	});

/**
 * Click the on-screen primitive whose id starts with `prefix` and confirm the
 * canvas picked THAT primitive (__GODS_EYE__.picked): a junction carries
 * several layers (a moving unit, an event spine, the waypoint ring), so a
 * click that lands on a neighbour is retried a few pixels off, then on the
 * next locate round (moving units pass). `wantUrn` is the URN prefix the
 * wanted primitive selects (a neighbour's selection is dismissed, that one
 * never is).
 */
async function clickPrefix(page, prefix, { rounds = 5, spotsPerRound = 1, wantUrn = null } = {}) {
	const OFFSETS = [[0, 0], [4, 0], [-4, 0], [0, 4], [0, -4], [7, 7], [-7, -7], [7, -7], [-7, 7]];
	for (let round = 0; round < rounds; round++) {
		// a spot whose projection is not finite (behind the camera, or a tile
		// that has not framed the city yet) can never be clicked — skip it
		const spots = (await page.evaluate((p) => window.__GODS_EYE__?.locate?.(p) ?? [], prefix))
			.filter((s) => Number.isFinite(s?.x) && Number.isFinite(s?.y))
			.slice(0, spotsPerRound);
		for (const spot of spots) {
			for (const [dx, dy] of OFFSETS) {
				const at = { x: spot.x + dx, y: spot.y + dy };
				// a pick card, the inspector (or any panel) over the spot would take the click
				if (!(await onCanvas(page, at.x, at.y))) continue;
				const before = await page.evaluate(() => window.__GODS_EYE__?.selection?.urn ?? null);
				await page.mouse.move(at.x, at.y);
				await sleep(250);
				await page.mouse.click(at.x, at.y);
				await sleep(700);
				const picked = await page.evaluate(() => window.__GODS_EYE__?.picked?.id ?? null);
				if (picked?.startsWith(prefix)) return at;
				// Something else sits on top here (an event marker on the same road):
				// dismiss it as an operator would — today's pick card on its ✕, else
				// the dossier / inspector the click opened with Esc — and try the next spot.
				if (picked) {
					await dismissPick(page, { wantUrn, before });
					await sleep(200);
				}
			}
		}
		await sleep(1500);
	}
	return null;
}

async function platesCheck(browser) {
	const name = 'plates';
	if (session.gate) return ok(`${name} (skipped under the gate)`, true, 'a signed-in session names the officer, so every sink shows the raw plate by design — ops-wall-smoke covers the masked path hermetically');
	const MASKED = masked(PLATE);
	const dispatches = (await getJson(`${ORIGIN}/api/v1/city/entities?kinds=dispatch`)).entities ?? [];
	const dsp = dispatches.find((d) => typeof d.props?.event_title === 'string' && d.props.event_title.includes(PLATE) && d.lon != null);
	const events = (await getJson(`${ORIGIN}/api/v1/city/entities?kinds=event`)).entities ?? [];
	const pursuit = events.find((e) => typeof e.props?.title === 'string' && e.props.title.includes(PLATE));
	if (!dsp && !pursuit) return ok(name, false, `no dispatch or event titled with ${MASKED} in the fused picture`);

	// 1. City Command: the dossier's MAP line for a dispatch pick.
	if (dsp) {
		const page = await newPage(browser);
		try {
			const phase = await openCanvas(page, '/gods-eye');
			if (phase !== 'ready') return ok(name, false, `phase=${phase}`);
			// The signal glyph shares the waypoint junction, and a unit that
			// ARRIVED stands on it (C-N: units drive to the junction itself):
			// an operator switches SIGNALS and UNITS off to reach the waypoint.
			await layersOff(page, ['signals', 'units']);
			await sleep(1500);
			const spot = await clickPrefix(page, `dsp:wp-${dsp.id}`, { wantUrn: `dispatch:${dsp.id}` });
			const d = await page.evaluate(() => {
				const el = document.querySelector('[data-testid=entity-dossier]');
				return {
					urn: el?.dataset.urn ?? null,
					mapLine: el?.querySelector('.map-pick .pick-text')?.textContent ?? null,
					text: el?.textContent?.replace(/\s+/g, ' ') ?? '',
				};
			});
			ok(
				`${name} dossier MAP line masks the dispatch's event title`,
				!!spot && d.urn === `dispatch:${dsp.id}` && !!d.mapLine && d.mapLine.includes(MASKED) && !d.text.includes(PLATE),
				`clicked dsp:wp-${dsp.id.slice(0, 8)} → ${d.urn ?? 'no dossier'} · MAP line '${(d.mapLine ?? '—').slice(0, 110)}…' · raw plate in the drawer: ${d.text.includes(PLATE)}`,
			);
			const all = await pageTexts(page);
			ok(`${name} City Command page-wide (no officer)`, !all.includes(PLATE), `raw plate in page text/attributes: ${all.includes(PLATE)}`);
		} finally {
			await page.close();
		}
	}

	// 2. The cockpit: LOCKED chip + LiveRail focus note for the pursuit, a dispatch pick card.
	const page = await newPage(browser);
	try {
		const phase = await openCanvas(page, WORKSPACE);
		if (phase !== 'ready') return ok(name, false, `phase=${phase}`);
		await sleep(3000); // the board lands
		const officer = (await officerValue(page, ['planner-officer', 'duty-officer'])) || ((await page.$eval('[data-v3="top-bar"] [data-testid="v3-officer"]', (el) => (el.getAttribute('data-named') === 'true' ? el.textContent : '')).catch(() => '')) ?? '');
		if (officer.trim().length >= 2) return ok(name, false, `a duty officer is already named on '/' ('${officer}') — the masked path cannot be checked`);
		if (pursuit) {
			const row = SEL.cockpitRow(pursuit.id);
			const clicked = await page.evaluate((sel) => {
				const el = document.querySelector(sel);
				el?.click();
				return !!el;
			}, row);
			let title = null;
			for (let i = 0; i < 40 && !title; i++) {
				await sleep(400);
				title = await page.evaluate(lockTitle);
			}
			const note = await page.evaluate((sel) => document.querySelector(sel)?.getAttribute('title') ?? '', within(row, '.ev-focus'));
			ok(
				`${name} LOCKED chip title + focus note masked`,
				clicked && !!title && title.includes(MASKED) && !title.includes(PLATE) && !note.includes(PLATE),
				`${clicked ? 'pursuit row clicked' : 'pursuit row not in the LiveRail'} · LOCKED '${(title ?? '—').slice(0, 90)}' · focus note '${note.slice(0, 60)}'`,
			);
		}
		if (dsp) {
			// signal glyphs and arrived units share the waypoint junctions (see above)
			await layersOff(page, ['signals', 'units']);
			await sleep(1500);
			// The LOCK frames the pursuit (~2 km up): a far choke's waypoint is
			// off screen. Pick a dispatch of this plate whose waypoint IS on
			// screen; with none, release the lock and widen the view (wheel
			// out), as an operator would, until one shows.
			const ofPlate = dispatches.filter((d) => typeof d.props?.event_title === 'string' && d.props.event_title.includes(PLATE) && d.lon != null);
			const onScreen = async () => {
				for (const c of ofPlate) {
					const spots = await page.evaluate((p) => window.__GODS_EYE__?.locate?.(p) ?? [], `dsp:wp-${c.id}`);
					if (spots.length) return c;
				}
				return null;
			};
			let target = await onScreen();
			if (!target) {
				await page.evaluate(() => {
					const chips = [...document.querySelectorAll('.ge-hud .chip.lock')];
					(chips.find((c) => /locked/i.test(c.textContent ?? '') || c.getAttribute('aria-pressed') === 'true') ?? chips[0])?.click();
				});
				await sleep(1200);
				const mid = await page.evaluate(() => {
					const r = document.querySelector('.ge-canvas canvas, canvas')?.getBoundingClientRect();
					return r ? { x: r.left + r.width / 2, y: r.top + r.height / 2 } : null;
				});
				for (let i = 0; i < 6 && !target; i++) {
					if (mid) {
						await page.mouse.move(mid.x, mid.y);
						await page.mouse.wheel({ deltaY: 500 });
					}
					await sleep(1200);
					target = await onScreen();
				}
			}
			const spot = target ? await clickPrefix(page, `dsp:wp-${target.id}`, { wantUrn: `dispatch:${target.id}` }) : null;
			// today's pick card, else the redesign's inspector opened on the dispatch (its MAP line)
			const card = await page.evaluate(firstPresentText, ['.ge-pick .pick-text', '[data-testid="entity-dossier"][data-urn^="dispatch:"] .map-pick .pick-text']);
			ok(
				`${name} cockpit pick card masks the dispatch's event title`,
				!!spot && !!card && card.includes(MASKED) && !card.includes(PLATE),
				`${target ? `dsp:wp-${target.id.slice(0, 8)} on screen` : 'no waypoint of the plate on screen'} · card '${(card ?? '—').slice(0, 120)}…'`,
			);
		}
		const all = await pageTexts(page);
		ok(`${name} cockpit page-wide (no officer)`, !all.includes(PLATE), `raw plate in page text/attributes: ${all.includes(PLATE)}`);
		// A named duty officer is on console: the same title shows the plate (masking is officer-gated, not blanket).
		if (pursuit) {
			await nameOfficer(page, 'Duty Officer CC Smoke', { prefer: ['planner-officer', 'duty-officer'], delay: 0 }).catch(async () => {
				await openOfficerField(page); // the cockpit's planner field is not open: the top bar's officer popover
				await nameOfficer(page, 'Duty Officer CC Smoke', { prefer: ['duty-officer'], delay: 0 });
				await page.keyboard.press('Escape');
			});
			// the title of the chip that HOLDS the camera (lockTitle, as the masked half above reads it)
			let lockedTitle = await page.evaluate(lockTitle);
			const deadline = Date.now() + 5000;
			while (!lockedTitle?.includes(PLATE) && Date.now() < deadline) {
				await sleep(250);
				lockedTitle = await page.evaluate(lockTitle);
			}
			const shown = !!lockedTitle?.includes(PLATE);
			ok(`${name} LOCKED title shows the plate to a named officer`, shown, shown ? `officer named → ${PLATE} in the LOCKED title` : `still masked (or the lock was released): '${(lockedTitle ?? '—').slice(0, 90)}'`);
		}
	} finally {
		await page.close();
	}
}

// ── provenance: the /ops wall labels the synthetic ingest feed ─────────────

async function provenanceCheck(browser) {
	const name = 'provenance';
	const summary = await getJson(`${ORIGIN}/api/v1/corridor/summary`).catch(() => null);
	const synthetic =
		!!summary && (summary.provenance === 'emulated' || summary.provenance === 'mixed' || Number(summary.emulated_segments ?? 0) > 0);
	if (!synthetic) return ok(`${name} (skipped)`, true, `corridor summary provenance '${summary?.provenance ?? 'unreachable'}' — not synthetic, nothing to label`);
	const page = await newPage(browser);
	try {
		const phase = await openCanvas(page, '/ops');
		if (phase !== 'ready') return ok(name, false, `phase=${phase}`);
		const { snap } = await waitSnap(page, (s) => Number(s.layerStats?.anomalies?.simulated ?? 0) > 0 && Number(s.layerStats?.flow?.simulated ?? 0) > 0, 30000, 1000);
		// the v2 wall (the /ops default since UI-S6) states the feed's provenance
		// in its own chrome: the "Simulated flow" legend entry and the metric
		// strip's feed label (gate C: the legacy chip bar is gone)
		const chips = await page.evaluate(() => {
			const vis = (el) => !!el && el.getBoundingClientRect().width > 0 && el.getBoundingClientRect().height > 0;
			const legend = [...document.querySelectorAll('[data-wall="city"] .legend .item')].find((el) => /simulated/i.test(el.textContent || ''));
			return {
				flow: vis(legend),
				anomaly: vis(legend),
				anomalyHint: (document.body.innerText.match(/[^\n]*simulated feed[^\n]*/i) ?? [''])[0],
			};
		});
		const anomalies = Number(snap?.layerStats?.anomalies?.anomalies ?? 0);
		ok(
			`${name} /ops FLOW + ANOMALY provenance (v2 legend: Simulated flow, visible)`,
			chips.flow && (anomalies === 0 || (chips.anomaly && textMatches(chips.anomalyHint, COPY.simulatedFeedWords))),
			`summary '${summary.provenance}' (${summary.emulated_segments ?? '—'} emulated segments) · FLOW SIM ${chips.flow} · ANOMALY SIM ${chips.anomaly} over ${anomalies} pulses · hint '${chips.anomalyHint.slice(0, 90)}'`,
		);
		if (anomalies > 0) {
			// A pulse sits ON its segment — under the flow line, often under an
			// event marker or a pursuit's trace on the same road: an operator
			// switches those layers off to reach it.
			await layersOff(page, ['flow', 'events', 'traces', 'enforcement']);
			await sleep(1500);
			const spot = await clickPrefix(page, 'anm:', { rounds: 4, spotsPerRound: 3, wantUrn: 'anomaly:' });
			const card = spot ? await page.evaluate(firstPresentText, ['.ge-pick .pick-text', '[data-testid="entity-dossier"][data-urn^="anomaly:"]']) : null;
			ok(
				`${name} /ops anomaly pick card says SIMULATED FEED`,
				// the canvas pick text says "SIMULATED FEED"; the inspector's provenance row says it as the
				// workspace's own words, "Simulated traffic feed" (ws_v_simulated_feed) — either, never the bare feed name
				!!card && (textMatches(card, COPY.simulatedFeedWords) || /simulated traffic feed/i.test(card)) && !textMatches(card, COPY.bareFeedName),
				card ? `'…${card.slice(-110)}'` : 'no anomaly pulse clickable on the wall',
			);
		}
	} finally {
		await page.close();
	}
}

// ── main ───────────────────────────────────────────────────────────────────

let deckProc = null;
let browser = null;
try {
	deckProc = await ensureOrigin(ORIGIN);
	ok('deck origin up', true, ORIGIN);
	mkdirSync(ARTIFACTS, { recursive: true });
	session = await signIn(ORIGIN, 'City-command smoke (automated check)');
	ok('operator gate', true, session.gate ? 'on — signed in' : 'off');
	if (run('parsers')) await parsersCheck();
	browser = await puppeteer.launch({ executablePath, headless: 'new', args: SWIFTSHADER_ARGS });
	if (run('layout')) await layoutCheck(browser);
	if (run('dossier')) await dossierCheck(browser);
	if (run('rail')) await railCheck(browser);
	if (run('feeds')) await feedsCheck(browser);
	if (run('posture')) await postureCheck(browser);
	if (run('replay')) await replayCheck(browser);
	if (run('cockpit')) await cockpitCheck(browser);
	if (run('escort')) await escortCheck(browser);
	if (run('hidden')) await hiddenCheck(browser);
	if (run('plates')) await platesCheck(browser);
	if (run('provenance')) await provenanceCheck(browser);
} catch (err) {
	ok('city-command smoke', false, String(err?.stack ?? err).slice(0, 400));
} finally {
	await signOut(session);
	await browser?.close();
	deckProc?.kill();
}

console.log(failures ? `FAIL city-command smoke — ${failures} failure(s)` : 'PASS city-command smoke');
process.exit(failures ? 1 : 0);
