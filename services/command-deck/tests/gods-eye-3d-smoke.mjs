/**
 * God's-eye 3D smoke — the photoreal city with every overlay ON it (WP-22).
 *
 * Runs against an ion-KEYED deck origin (SAJAG_CESIUM_ION_TOKEN on the deck;
 * the token is never printed: the mode answer is read only for its `mode`
 * and asset id), under SOFTWARE WebGL (SwiftShader — the gods-eye-smoke
 * flags), 1920×1080.
 *
 * Operator gate: the release deck runs with the PIN gate ON, and there the
 * deck hands the ion upgrade ONLY to a signed-in operator (an anonymous
 * mode read is keyless by design). Like gods-eye-smoke, this smoke signs in
 * ONCE through tests/lib/operator-session.mjs — the PIN is read at run time
 * (SAJAG_OPERATOR_PIN, else SAJAG_OPERATOR_PIN_FILE, else sajag.env) and never
 * logged — reads the mode endpoint, the active events and the interception
 * plan WITH the session, sets the session cookie on every page before its
 * first navigation (fresh browser contexts and the City Command home
 * included) and signs out on exit. Gate off (a private preview): nothing to
 * sign in to, the same checks run.
 *
 *   1. the mode endpoint answers ion-photoreal (else: not a keyed deck —
 *      this smoke needs one; gods-eye-smoke covers the keyless canvas);
 *   2. /gods-eye on the central overview reaches phase 'ready', the
 *      photoreal-3d layer reports its tiles covering the view (Google
 *      Photorealistic 3D Tiles, ion asset 2275207 — allow ~2 minutes under
 *      SwiftShader) with the globe kept beneath as the overlays' ground, and
 *      the snapshot's imageryMode is 'ion-photoreal' — never the offline
 *      schematic;
 *   3. ZERO Content-Security-Policy violations (console + the
 *      securitypolicyviolation event) and zero page errors — on /gods-eye,
 *      '/' and /ops;
 *   4. every overlay layer with entities on the canvas reports them DRAPED
 *      (ground polylines / fills) or CLAMPED (markers on the terrain, depth
 *      test off) and floating 0 (layerStats.<id>.{draped,clamped,floating},
 *      the drape audit reading the entities back); the flow network draped
 *      segment for segment;
 *   5. the draped flow network is VISIBLE on the 3D tiles, whatever its
 *      palette (UI-S3: the v2 ramp is neutral — luminance and width — so a
 *      colour match can no longer prove it): at ONE camera pose (the idle
 *      orbit stopped, the pose read from __GODS_EYE__, held before the
 *      captures and asserted unchanged across them) the canvas is captured
 *      with the flow layer on and off (and off once more, the tiles' own
 *      noise); the pixels that changed must be substantial, well above that
 *      noise, and lie ALONG the network — within a few px of the segments
 *      projected from their real geometry (GET /spatial/segments) with the
 *      camera's own pose and frustum — and cover most of the segments on
 *      screen. No fixed sleeps (review r1): Cesium builds a draped primitive
 *      asynchronously and shows the old picture until the new one is ready,
 *      later under load, so every state — off (the reference), on, off,
 *      back on — is captured only once the picture ALONG THE NETWORK has
 *      settled (captures 1.5 s apart, two in a row within the floor) and
 *      the state has landed (the flow's pixels there, or gone); the check
 *      fails only when a state never settles within the bound
 *      (GODS_EYE_3D_SETTLE_MS, default 60 s per state), and it reports
 *      every state's settle time;
 *   6. no stall: no frame over 3 s in a 10 s window on the overview;
 *   7. the data credits (Google, Cesium ion, '© OpenStreetMap contributors'
 *      spelled out) are on screen and not covered by a panel on the '/'
 *      wall — the WHOLE bar, its right end included: it wraps before the
 *      cockpit's tool dock instead of running under it (asserted with
 *      GODS_EYE_3D_MERGED=1, reported otherwise);
 *   8. the pursuit overlay: drawn (entities > 0) whenever the oracle holds a
 *      live interception plan with a sighting (read through the deck's
 *      proxy — a GET), else reported;
 *   9. screenshots: tests/artifacts/gods-eye-3d-smoke{,-root,-home,-v2}.png
 *      (or the directory in GODS_EYE_3D_OUT);
 *  11. chrome v2 (the /design/map harness, UI-S3; SPEC §5.3, §12.4): the
 *      credits at the bottom RIGHT of the map pane on the photoreal city,
 *      never covered; `.chip.mode` in the toolbar; the neutral flow network
 *      visible by the same pose-locked check (when the harness is deployed —
 *      reported otherwise).
 *
 * MERGED canvas (GODS_EYE_3D_MERGED=1, or the older
 * GODS_EYE_3D_CITY_COMMAND_CREDITS=assert) — once WP-22's GodsEyeCanvas,
 * enforcement and replay changes are merged, these are asserted instead of
 * reported: the City Command credits clear of the fusion rail; the chip
 * reads 'Photoreal 3D · Google'; the e-challan pins and the pursuit overlay
 * publish their drape audit (floating 0); a FRESH /gods-eye (no share hash)
 * lands on the presentation-grade home — pitch −35…−45°, camera 1.5–3 km up.
 *
 * SOAK (GODS_EYE_3D_SOAK_MIN=10): after the checks, the '/' wall orbits on
 * the keyed city for that many minutes, sampled every 20 s (JS heap, tile
 * memory, frames, camera altitude, entities, page errors): no page error,
 * no frame over 3 s, the orbit's altitude constant (±50 m), the tiles
 * within their cache bound and the heap without a runaway (the last third's
 * median within 1.5× + 40 MB of the first third's).
 *
 * Environment fault, said and retried: from the demo box one of
 * api.cesium.com's CDN addresses refuses every TLS handshake and a browser
 * context keeps its pick, so a load whose ion requests fail at the TLS layer
 * (and whose tiles therefore never arrive) is retried in a fresh browser
 * context — own DNS cache and sockets — at most twice per page.
 *
 * Usage:   node tests/gods-eye-3d-smoke.mjs [origin]   # default http://127.0.0.1:5223
 *          SAJAG_OPERATOR_PIN_FILE=<0600 file> node tests/gods-eye-3d-smoke.mjs <gate-on origin>
 *          (a sandbox deck's throwaway PIN; without it the helper reads sajag.env)
 * Exits 0 with `ok <name> — <detail>` lines; exit 1 on any failure.
 */

import { createRequire } from 'node:module';
import { existsSync, mkdirSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { deckFetch, puppeteerCookies, signIn, signOut } from './lib/operator-session.mjs';
import { WORKSPACE } from './lib/routes.mjs';
import { SEGMENTS_QUERY } from './lib/city-box.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const OUT = process.env['GODS_EYE_3D_OUT'] ?? path.join(HERE, 'artifacts');

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

const ARGS = [
	'--no-sandbox',
	'--disable-setuid-sandbox',
	'--disable-dev-shm-usage',
	'--enable-unsafe-swiftshader',
	'--use-gl=angle',
	'--use-angle=swiftshader',
	'--ignore-gpu-blocklist',
	'--window-size=1920,1080',
	// performance.memory un-bucketed and live (the soak samples the JS heap)
	'--enable-precise-memory-info',
];

/** The seaface overview: off Haji Ali at ~2.6 km, looking north along the Worli seaface to the Bandra–Worli Sea Link. */
const OVERVIEW_HASH = '#v=2&lat=18.96697&lon=72.81124&alt=2600&heading=4&pitch=-30&style=raw';
/** Overlay layers that must stand on the city (photoreal-3d is the city itself). */
const OVERLAYS = ['events', 'flow', 'traces', 'enforcement', 'signals', 'units', 'dispatch', 'convoy', 'cameras', 'anomalies'];
const TILE_WAIT_MS = Number(process.env['GODS_EYE_3D_TILE_WAIT_MS'] ?? 150_000);
/** The WP-22 canvas / enforcement / replay changes are merged: their checks are asserted. */
const MERGED = process.env['GODS_EYE_3D_MERGED'] === '1' || process.env['GODS_EYE_3D_CITY_COMMAND_CREDITS'] === 'assert';
/** The presentation-grade City Command home on the photoreal city (task 3). */
const HOME_3D = { minPitch: -45.5, maxPitch: -34.5, minAlt: 1500, maxAlt: 3000 };
/** The honest imagery chip (sentence case since UI-S3; i18n/packs.map.ts). */
const CHIP_PHOTOREAL = 'Photoreal 3D · Google';
const SOAK_MIN = Number(process.env['GODS_EYE_3D_SOAK_MIN'] ?? 0);
/** Tile cache bound of layers/photoreal-3d.ts (cacheBytes + maximumCacheOverflowBytes), MB. */
const TILE_CACHE_MB = 768;

/** Where the canvas's data credits are, and whether a panel covers them. */
async function creditsOnScreen(page) {
	return page.evaluate(() => {
		const credits = document.querySelector('.ge-canvas .cesium-viewer-bottom');
		if (!credits) return { present: false, visible: false, google: false, cesium: false };
		const r = credits.getBoundingClientRect();
		let text = credits.textContent ?? '';
		text += ` ${Array.from(credits.querySelectorAll('img, a')).map((el) => el.getAttribute('title') ?? el.getAttribute('alt') ?? el.getAttribute('href') ?? '').join(' ')}`;
		const y = r.top + r.height / 2;
		const mine = (x) => {
			const top = document.elementFromPoint(x, y);
			return !!top && credits.contains(top);
		};
		const inView = r.width > 0 && r.height > 0 && r.bottom <= innerHeight;
		return {
			present: true,
			visible: inView && mine(r.left + Math.min(40, r.width / 2)),
			// the whole bar, its right end included (the data providers' names), not under a panel
			clear: inView && mine(r.left + Math.min(40, r.width / 2)) && mine(r.right - Math.min(40, r.width / 2)),
			google: /google/i.test(text),
			cesium: /cesium/i.test(text),
			// the OSM attribution spelled out on the plate (OSMF guidelines), not only '© OSM'
			osm: /openstreetmap contributors/i.test(text),
			at: `${Math.round(r.left)},${Math.round(r.top)}`,
			w: Math.round(r.width),
		};
	});
}

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const redact = (text) => String(text).replace(/([?&](?:access_token|key)=)[^&\s"']+/g, '$1…');

const origin = (process.argv[2] ?? 'http://127.0.0.1:5223').replace(/\/+$/, '');
/** The operator session (signed in once; `gate:false` on a gate-off preview). */
let session = null;

/**
 * A page that records CSP violations (console + DOM event), page errors and
 * ion TLS refusals — carrying the operator session from its first navigation
 * (every caller navigates after this returns; a fresh browser context has
 * no cookie of its own).
 */
async function openPage(context) {
	const page = await context.newPage();
	await page.setViewport({ width: 1920, height: 1080 });
	if (session?.gate) await page.setCookie(...puppeteerCookies(session));
	const log = { csp: [], errors: [], ionRefused: 0 };
	page.on('console', (m) => {
		const text = m.text();
		if (/Content Security Policy/i.test(text)) log.csp.push(redact(text).slice(0, 180));
	});
	page.on('pageerror', (e) => log.errors.push(redact(e.message).slice(0, 180)));
	page.on('requestfailed', (req) => {
		if (/^https:\/\/api\.cesium\.com\//.test(req.url()) && /SSL|CONNECTION|TIMED_OUT/i.test(req.failure()?.errorText ?? '')) log.ionRefused++;
	});
	await page.evaluateOnNewDocument(() => {
		window.__CSP_EVENTS__ = [];
		document.addEventListener('securitypolicyviolation', (e) => {
			window.__CSP_EVENTS__.push(`${e.violatedDirective} ${String(e.blockedURI).replace(/([?&](?:access_token|key)=)[^&]+/g, '$1…').slice(0, 120)}`);
		});
	});
	return { page, log };
}

async function waitReady(page, timeoutMs = 90_000) {
	return page
		.waitForFunction(() => window.__GODS_EYE__?.phase && window.__GODS_EYE__.phase !== 'loading', { timeout: timeoutMs })
		.then(() => page.evaluate(() => window.__GODS_EYE__.phase))
		.catch(() => null);
}

/** Wait until the photoreal tiles cover the view (or the layer gives up, or ion refused this context). */
async function waitTiles(page, timeoutMs, log = null) {
	const deadline = Date.now() + timeoutMs;
	const start = Date.now();
	let last = null;
	while (Date.now() < deadline) {
		last = await page.evaluate(() => window.__GODS_EYE__?.layerStats?.['photoreal-3d'] ?? null).catch(() => null);
		if (last && (last.initialTilesLoaded === 1 || last.via === 'failed')) return last;
		if (log?.ionRefused && Date.now() - start > 30_000) return last; // the environment refused this context
		await sleep(2000);
	}
	return last;
}

/**
 * Open `route` until its photoreal tiles land: a context whose ion requests
 * the CDN refused (environment) is retried in a fresh one, at most twice.
 */
async function openWithTiles(browser, route) {
	let opened = null;
	for (let attempt = 1; attempt <= 3; attempt++) {
		const context = attempt === 1 ? browser.defaultBrowserContext() : await browser.createBrowserContext();
		const { page, log } = await openPage(context);
		await page.goto(`${origin}${route}`, { waitUntil: 'domcontentloaded', timeout: 90_000 });
		const phase = await waitReady(page);
		const tiles = phase === 'ready' ? await waitTiles(page, TILE_WAIT_MS, log) : null;
		opened = { page, log, phase, tiles, attempt };
		if (tiles?.initialTilesLoaded === 1 || !log.ionRefused || attempt === 3) break;
		console.log(`note ${route}: api.cesium.com refused TLS in this browser context (${log.ionRefused}×, environment) — retrying in a fresh context (${attempt}/3)`);
		await page.close();
	}
	return opened;
}

/** The city's road network (GET through the deck proxy): each segment's lon/lat polyline. */
async function cityNetwork() {
	const body = await deckFetch(session, `/api/v1/spatial/segments?${SEGMENTS_QUERY}`, { signal: AbortSignal.timeout(10_000) })
		.then((r) => (r.ok ? r.json() : null))
		.catch(() => null);
	const rows = Array.isArray(body?.segments) ? body.segments : [];
	return rows
		.map((r) => (Array.isArray(r?.geometry?.coordinates) ? r.geometry.coordinates.filter((c) => Array.isArray(c) && Number.isFinite(c[0]) && Number.isFinite(c[1])) : []))
		.filter((c) => c.length >= 2);
}

/** The camera pose the canvas publishes (degrees / metres), or null. */
const poseOf = (page) => page.evaluate(() => window.__GODS_EYE__?.camera ?? null).catch(() => null);
const samePose = (a, b) =>
	!!a && !!b && Math.abs(a.lon - b.lon) < 1e-7 && Math.abs(a.lat - b.lat) < 1e-7 && Math.abs(a.alt - b.alt) < 0.05 && Math.abs(a.heading - b.heading) < 1e-3 && Math.abs(a.pitch - b.pitch) < 1e-3;

/**
 * The flow check's settle loop (review r1: fixed sleeps raced Cesium, which
 * builds a draped GroundPolylinePrimitive asynchronously — on worker threads,
 * slower under load — and keeps showing the old picture until the new one is
 * ready). Captures SETTLE_GAP_MS apart, for at most SETTLE_MAX_MS per state.
 */
const SETTLE_GAP_MS = 1500;
const SETTLE_MAX_MS = Number(process.env['GODS_EYE_3D_SETTLE_MS'] ?? 60_000);
/** A changed pixel: RGB L1 distance between two captures. */
const CHANGED_L1 = 48;
/** Two captures count as settled when they differ along the network by at most this (px), or 10 % of the flow's own pixels. */
const SETTLE_FLOOR_PX = 150;
/** The flow is drawn when this many network pixels differ from the flow-off picture. */
const FLOW_MIN_PX = 600;
/**
 * A loaded box, emulated (opt-in): the page's CPU throttled by this rate
 * (DevTools CPU throttling) for the flow check only, so the settle loop can
 * be proven against slow primitive builds without loading the shared box.
 */
const FLOW_THROTTLE = Number(process.env['GODS_EYE_3D_FLOW_THROTTLE'] ?? 0);

/**
 * Install the in-page probe at the locked pose: canvas captures kept in the
 * page, the projected network's mask (every segment from its real geometry,
 * GET /spatial/segments, projected with the camera's own pose and Cesium's
 * 60° frustum, NEAR px either side), changed-pixel counts along the mask and
 * over the whole frame, and the verdict's facts.
 */
async function installFlowProbe(page, network, pose) {
	return page.evaluate(
		(segments, pose, L1) => {
			const c = document.querySelector('.ge-canvas canvas');
			if (!c) return null;
			const w = c.width;
			const h = c.height;
			const caps = {};
			const capture = (name) => {
				const el = document.querySelector('.ge-canvas canvas');
				if (!el || el.width !== w || el.height !== h) return false;
				const t = document.createElement('canvas');
				t.width = w;
				t.height = h;
				const g = t.getContext('2d');
				g.drawImage(el, 0, 0);
				caps[name] = g.getImageData(0, 0, w, h).data;
				return true;
			};
			// project the network with the camera's own pose (WGS84, a pinhole on Cesium's 60° frustum)
			const A = 6378137;
			const E2 = 6.69437999014e-3;
			const rad = (x) => (x * Math.PI) / 180;
			const ecef = (lon, lat, hgt) => {
				const l = rad(lon);
				const f = rad(lat);
				const N = A / Math.sqrt(1 - E2 * Math.sin(f) ** 2);
				return [(N + hgt) * Math.cos(f) * Math.cos(l), (N + hgt) * Math.cos(f) * Math.sin(l), (N * (1 - E2) + hgt) * Math.sin(f)];
			};
			const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
			const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
			const L = rad(pose.lon);
			const F = rad(pose.lat);
			const east = [-Math.sin(L), Math.cos(L), 0];
			const north = [-Math.sin(F) * Math.cos(L), -Math.sin(F) * Math.sin(L), Math.cos(F)];
			const up = [Math.cos(F) * Math.cos(L), Math.cos(F) * Math.sin(L), Math.sin(F)];
			const hd = rad(pose.heading);
			const pt = rad(pose.pitch);
			const horiz = [0, 1, 2].map((k) => Math.sin(hd) * east[k] + Math.cos(hd) * north[k]);
			const dir = [0, 1, 2].map((k) => Math.cos(pt) * horiz[k] + Math.sin(pt) * up[k]);
			const right = [0, 1, 2].map((k) => Math.cos(hd) * east[k] - Math.sin(hd) * north[k]);
			const camUp = cross(right, dir);
			const C = ecef(pose.lon, pose.lat, pose.alt);
			const cw = c.clientWidth || w;
			const ch = c.clientHeight || h;
			const sx = w / cw;
			const aspect = cw / ch;
			const fov = Math.PI / 3;
			const tx = aspect >= 1 ? Math.tan(fov / 2) : Math.tan(fov / 2) * aspect;
			const ty = aspect >= 1 ? Math.tan(fov / 2) / aspect : Math.tan(fov / 2);
			const project = (lon, lat) => {
				const P = ecef(lon, lat, 0);
				const v = [P[0] - C[0], P[1] - C[1], P[2] - C[2]];
				const z = dot(v, dir);
				if (z <= 1) return null;
				return [(cw / 2 + (dot(v, right) / z) * (cw / 2 / tx)) * sx, (ch / 2 - (dot(v, camUp) / z) * (ch / 2 / ty)) * sx];
			};
			// the network mask: every projected segment, NEAR px wide either side
			const NEAR = 14;
			const m = document.createElement('canvas');
			m.width = w;
			m.height = h;
			const g = m.getContext('2d');
			g.strokeStyle = '#fff';
			g.lineWidth = 2 * NEAR + 1;
			g.lineCap = 'round';
			g.lineJoin = 'round';
			const onScreen = [];
			for (const seg of segments) {
				const pts = seg.map(([lon, lat]) => project(lon, lat));
				let drawn = false;
				g.beginPath();
				for (let i = 1; i < pts.length; i++) {
					const a = pts[i - 1];
					const b = pts[i];
					if (!a || !b) continue;
					g.moveTo(a[0], a[1]);
					g.lineTo(b[0], b[1]);
					if ((a[0] >= 0 && a[0] < w && a[1] >= 0 && a[1] < h) || (b[0] >= 0 && b[0] < w && b[1] >= 0 && b[1] < h)) drawn = true;
				}
				g.stroke();
				if (drawn) onScreen.push(pts);
			}
			const md = g.getImageData(0, 0, w, h).data;
			const mask = new Uint8Array(w * h);
			let maskPx = 0;
			for (let p = 0; p < w * h; p++)
				if (md[p * 4] > 0) {
					mask[p] = 1;
					maskPx++;
				}
			const changedAt = (a, b, i) => Math.abs(a[i] - b[i]) + Math.abs(a[i + 1] - b[i + 1]) + Math.abs(a[i + 2] - b[i + 2]) > L1;
			window.__FLOWCHK__ = {
				capture,
				/** keep a capture under another name */
				keep(from, to) {
					caps[to] = caps[from];
				},
				/** changed pixels between two captures: along the network, and over the whole frame */
				diff(a, b) {
					const A_ = caps[a];
					const B_ = caps[b];
					if (!A_ || !B_) return null;
					let along = 0;
					let frame = 0;
					for (let p = 0, i = 0; p < w * h; p++, i += 4) {
						if (!changedAt(A_, B_, i)) continue;
						frame++;
						if (mask[p]) along++;
					}
					return { along, frame };
				},
				/** the verdict's facts from the settled on / off1 / off2 captures */
				facts() {
					const { on, off1, off2 } = caps;
					if (!on || !off1 || !off2) return null;
					const changed = new Uint8Array(w * h);
					let nChanged = 0;
					let noise = 0;
					let onNetwork = 0;
					for (let p = 0, i = 0; p < w * h; p++, i += 4) {
						if (changedAt(on, off1, i)) {
							changed[p] = 1;
							nChanged++;
							if (mask[p]) onNetwork++;
						}
						if (changedAt(off2, off1, i)) noise++;
					}
					// coverage: a segment is seen when a changed pixel lies within 6 px of a point along it
					const hitNear = (x, y) => {
						for (let dy = -6; dy <= 6; dy++)
							for (let dx = -6; dx <= 6; dx++) {
								const X = Math.round(x + dx);
								const Y = Math.round(y + dy);
								if (X >= 0 && X < w && Y >= 0 && Y < h && changed[Y * w + X]) return true;
							}
						return false;
					};
					let seen = 0;
					for (const pts of onScreen) {
						let hit = false;
						for (let i = 1; i < pts.length && !hit; i++) {
							const a = pts[i - 1];
							const b = pts[i];
							if (!a || !b) continue;
							const steps = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 8));
							for (let k = 0; k <= steps && !hit; k++) {
								const x = a[0] + ((b[0] - a[0]) * k) / steps;
								const y = a[1] + ((b[1] - a[1]) * k) / steps;
								if (x >= 0 && x < w && y >= 0 && y < h && hitNear(x, y)) hit = true;
							}
						}
						if (hit) seen++;
					}
					return { w, h, changed: nChanged, onNetwork, noise, segments: onScreen.length, seen };
				},
				drop() {
					delete window.__FLOWCHK__;
				},
			};
			return { w, h, maskPx, segments: onScreen.length };
		},
		network,
		pose,
		CHANGED_L1,
	);
}

/**
 * Poll the canvas every SETTLE_GAP_MS until the picture ALONG THE NETWORK has
 * settled in the wanted state — two consecutive captures differ there by at
 * most the floor (SETTLE_FLOOR_PX, or 10 % of the flow's own pixels) — and
 * the state has landed:
 *   'on'     the capture differs from the flow-off capture `ref` by at least
 *            FLOW_MIN_PX network pixels (the flow is drawn);
 *   'off'    it differs from the flow-on capture `ref` by at least 70 % of
 *            the flow's own pixels `flowPx` (the flow is gone);
 *   'still'  no reference (the first flow-off picture): settled only.
 * The settled capture is kept as `name`. Never fails by itself: it says
 * whether the state settled within SETTLE_MAX_MS, how long it took and the
 * last counts.
 */
async function settleFlow(page, want, name, { ref = null, flowPx = 0, maskPx = 0 } = {}) {
	const t0 = Date.now();
	let polls = 0;
	let last = null;
	await page.evaluate(() => window.__FLOWCHK__?.capture('prev'));
	while (Date.now() - t0 < SETTLE_MAX_MS) {
		await sleep(SETTLE_GAP_MS);
		polls++;
		const r = await page
			.evaluate((refName) => {
				const k = window.__FLOWCHK__;
				if (!k || !k.capture('cur')) return null;
				const step = k.diff('prev', 'cur');
				const vsRef = refName ? k.diff(refName, 'cur') : null;
				k.keep('cur', 'prev');
				return { step: step?.along ?? null, vsRef: vsRef?.along ?? null };
			}, ref)
			.catch(() => null);
		if (!r || r.step == null) continue;
		last = r;
		const own = want === 'on' ? (r.vsRef ?? 0) : want === 'off' ? flowPx : 0.1 * maskPx;
		const floor = Math.max(SETTLE_FLOOR_PX, Math.round(0.1 * own));
		const landed = want === 'on' ? (r.vsRef ?? 0) >= FLOW_MIN_PX : want === 'off' ? (r.vsRef ?? 0) >= 0.7 * flowPx : true;
		if (landed && r.step <= floor) {
			await page.evaluate((n) => window.__FLOWCHK__?.keep('prev', n), name);
			return { settled: true, ms: Date.now() - t0, polls, step: r.step, vsRef: r.vsRef, floor };
		}
	}
	// unsettled: the last capture still stands under `name`, so the facts can be reported
	await page.evaluate((n) => window.__FLOWCHK__?.keep('prev', n), name).catch(() => {});
	return { settled: false, ms: Date.now() - t0, polls, step: last?.step ?? null, vsRef: last?.vsRef ?? null };
}

/** The camera pose once two reads SETTLE_GAP_MS apart are the same pose (within the bound), or null. */
async function lockedPose(page, timeoutMs = 20_000) {
	const deadline = Date.now() + timeoutMs;
	let last = await poseOf(page);
	while (Date.now() < deadline) {
		await sleep(SETTLE_GAP_MS);
		const now = await poseOf(page);
		if (samePose(last, now)) return now;
		last = now;
	}
	return null;
}

/**
 * Is the flow layer visible? Pose-locked on/off captures (the header, item
 * 5), each taken only once the picture along the projected network has
 * SETTLED in its state (settleFlow): flow off (the reference), flow on (the
 * flow's own pixels against that reference), flow off again (the verdict's
 * off1, then off2 one gap later for the tiles' own noise), and flow back on
 * (restored for the rest of the run). `toggle` clicks the flow layer's
 * control; `network` is the segments' lon/lat polylines. Returns the counts,
 * the verdict's facts and every state's settle time.
 */
async function flowVisibility(page, network, toggle) {
	// the operator's camera: an idle orbit stands down (a wheel on the canvas host, no zoom)
	await page.evaluate(() => document.querySelector('.ge-canvas')?.dispatchEvent(new WheelEvent('wheel', { deltaY: 0, bubbles: true })));
	const flowOn = () => page.evaluate(() => (window.__GODS_EYE__?.distinctLayerIds ?? []).includes('flow'));
	const poseM = await lockedPose(page);
	const orbiting = await page.evaluate(() => !!window.__GODS_EYE__?.orbiting);
	const base = { orbiting, offNow: false, samePose: false, settle: {} };
	if (!poseM) return { ...base, error: 'the camera never held one pose for the captures' };
	const probe = await installFlowProbe(page, network, poseM);
	if (!probe) return { ...base, error: 'no map canvas' };
	if (FLOW_THROTTLE > 1) await page.emulateCPUThrottling(FLOW_THROTTLE).catch(() => {});
	const settle = {};
	// 1. flow OFF: the reference picture
	if (await flowOn()) await toggle();
	settle.ref = await settleFlow(page, 'still', 'off0', { maskPx: probe.maskPx });
	// 2. flow ON: drawn and settled against the reference
	await toggle();
	settle.on = await settleFlow(page, 'on', 'on', { ref: 'off0' });
	const flowPx = settle.on.vsRef ?? 0;
	const pose0 = await poseOf(page);
	// 3. flow OFF: gone and settled, then the tiles' own noise one gap later
	await toggle();
	const offNow = !(await flowOn());
	settle.off = await settleFlow(page, 'off', 'off1', { ref: 'on', flowPx });
	await sleep(SETTLE_GAP_MS);
	await page.evaluate(() => window.__FLOWCHK__?.capture('off2'));
	const pose1 = await poseOf(page);
	const facts = await page.evaluate(() => window.__FLOWCHK__?.facts() ?? null);
	// 4. flow back ON for the rest of the run, settled too
	await toggle();
	settle.back = await settleFlow(page, 'on', 'back', { ref: 'off1' });
	if (FLOW_THROTTLE > 1) await page.emulateCPUThrottling(1).catch(() => {});
	await page.evaluate(() => window.__FLOWCHK__?.drop());
	return {
		...(facts ?? {}),
		pose0,
		pose1,
		offNow,
		orbiting,
		samePose: samePose(poseM, pose0) && samePose(pose0, pose1),
		maskPx: probe.maskPx,
		flowPx,
		settle,
	};
}

/** The flow verdict: every state settled, substantial change above the tiles' noise, along the projected network, covering it. */
function flowVerdict(f) {
	const along = f.changed > 0 ? f.onNetwork / f.changed : 0;
	const cover = f.segments > 0 ? f.seen / f.segments : 0;
	const s = f.settle ?? {};
	const states = ['ref', 'on', 'off', 'back'];
	const settled = states.every((k) => s[k]?.settled);
	const times = states.map((k) => `${k} ${s[k] ? `${(s[k].ms / 1000).toFixed(1)} s${s[k].settled ? '' : ' NOT SETTLED'}` : '—'}`).join(', ');
	return {
		pass: !f.error && settled && f.samePose && f.offNow && !f.orbiting && f.changed >= 600 && f.noise <= Math.max(400, 0.25 * f.changed) && along >= 0.6 && cover >= 0.5,
		detail: f.error
			? f.error
			: `pose ${f.samePose ? 'unchanged' : 'MOVED'} · changed ${f.changed} px (noise ${f.noise}) · ${(along * 100).toFixed(0)} % within 14 px of the projected network · ${f.seen}/${f.segments} on-screen segments seen · settled: ${times} (flow ${f.flowPx} network px, bound ${SETTLE_MAX_MS / 1000} s${FLOW_THROTTLE > 1 ? `, CPU throttled ×${FLOW_THROTTLE}` : ''})${f.offNow ? '' : ' · the toggle did not switch the layer off'}${f.orbiting ? ' · ORBITING' : ''} (${f.w}×${f.h})`,
	};
}

/**
 * A live interception plan with a sighting — the pursuit overlay must then
 * draw. Read through the deck's proxy like the canvas does (GETs only), with
 * the operator session: under the gate an anonymous read is refused.
 */
async function livePursuitPlan() {
	const get = (route, ms) =>
		deckFetch(session, route, { signal: AbortSignal.timeout(ms) })
			.then((r) => (r.ok ? r.json() : null))
			.catch(() => null);
	const body = await get('/api/v1/events/active', 8000);
	const rows = Array.isArray(body?.events) ? body.events : [];
	for (const row of rows) {
		const id = String(row.event_id ?? row.id ?? '');
		if (row.event_kind !== 'vehicle_pursuit' || !/^[\w-]+$/.test(id)) continue;
		const plan = await get(`/api/v1/events/${id}/interception-plan?max_cost_sec=600`, 12_000);
		if (plan && typeof plan.vehicle_id === 'string' && Array.isArray(plan.latest_sighting?.position)) {
			return { eventId: id, chokes: Array.isArray(plan.interception_junctions) ? plan.interception_junctions.length : 0 };
		}
	}
	return null;
}

/** The camera once it stopped moving (two reads `gapMs` apart within 5 m / 0.2°), or the last read. */
async function settledCamera(page, timeoutMs, gapMs = 1500) {
	const deadline = Date.now() + timeoutMs;
	let last = await page.evaluate(() => window.__GODS_EYE__?.camera ?? null).catch(() => null);
	while (Date.now() < deadline) {
		await sleep(gapMs);
		const now = await page.evaluate(() => window.__GODS_EYE__?.camera ?? null).catch(() => null);
		if (last && now && Math.abs(now.alt - last.alt) < 5 && Math.abs(now.pitch - last.pitch) < 0.2 && Math.abs(now.heading - last.heading) < 0.2) return now;
		last = now;
	}
	return last;
}

/** SOAK: the '/' wall orbiting on the keyed city for `minutes`, sampled every 20 s. */
async function soak(minutes) {
	const { page, log, phase, tiles } = await openWithTiles(browser, WORKSPACE);
	ok(`soak: '/' phase ready on the photoreal city`, phase === 'ready' && tiles?.initialTilesLoaded === 1, `phase=${phase} tiles=${tiles?.initialTilesLoaded}`);
	const samples = [];
	const t0 = Date.now();
	while (Date.now() - t0 < minutes * 60_000) {
		await sleep(20_000);
		const s = await page
			.evaluate(
				() =>
					new Promise((resolve) => {
						const d = [];
						let last = performance.now();
						const start = last;
						function step(now) {
							d.push(now - last);
							last = now;
							if (now - start < 2000) requestAnimationFrame(step);
							else {
								const sorted = [...d].sort((a, b) => a - b);
								const g = window.__GODS_EYE__;
								resolve({
									heapMB: Math.round((performance.memory?.usedJSHeapSize ?? 0) / 1e6),
									tileMB: g?.layerStats?.['photoreal-3d']?.memMB ?? null,
									alt: Math.round(g?.camera?.alt ?? NaN),
									orbiting: !!g?.orbiting,
									entities: g?.entityCount ?? null,
									median: Math.round(sorted[Math.floor(sorted.length / 2)] ?? NaN),
									max: Math.round(sorted[sorted.length - 1] ?? NaN),
								});
							}
						}
						requestAnimationFrame(step);
					}),
			)
			.catch(() => null);
		if (!s) continue;
		samples.push({ min: +((Date.now() - t0) / 60_000).toFixed(1), ...s });
		console.log(`soak ${JSON.stringify(samples[samples.length - 1])}`);
	}
	const third = Math.max(1, Math.floor(samples.length / 3));
	const med = (xs) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)] ?? NaN;
	const heapFirst = med(samples.slice(0, third).map((s) => s.heapMB));
	const heapLast = med(samples.slice(-third).map((s) => s.heapMB));
	const orbit = samples.filter((s) => s.orbiting).map((s) => s.alt);
	const tileMax = Math.max(0, ...samples.map((s) => s.tileMB ?? 0));
	const frameMax = Math.max(0, ...samples.map((s) => s.max));
	// a sample every ~22 s (20 s apart + a 2 s frame window): at least one per 30 s, and the window covered
	ok(
		`soak: sampled across the whole ${minutes} min`,
		samples.length >= Math.floor((minutes * 60) / 30) && (samples.at(-1)?.min ?? 0) >= minutes - 0.5,
		`${samples.length} samples · last at ${samples.at(-1)?.min ?? '—'} min`,
	);
	ok('soak: zero page errors', log.errors.length === 0, log.errors.slice(0, 2).join(' | ') || 'none');
	ok('soak: no frame over 3 s', frameMax < 3000, `max frame ${frameMax} ms · medians ${samples.map((s) => s.median).join('/')} ms`);
	ok('soak: the orbit holds its altitude (±50 m)', orbit.length > 0 && Math.max(...orbit) - Math.min(...orbit) <= 100, `orbiting in ${orbit.length}/${samples.length} samples · alt ${Math.min(...orbit)}–${Math.max(...orbit)} m`);
	ok('soak: tiles within their cache bound', tileMax <= TILE_CACHE_MB, `tile memory peak ${tileMax} MB (bound ${TILE_CACHE_MB} MB)`);
	ok('soak: no heap runaway', heapLast <= heapFirst * 1.5 + 40, `JS heap median ${heapFirst} MB (first third) → ${heapLast} MB (last third)`);
	await page.close();
}

const browser = await puppeteer.launch({ executablePath, headless: 'new', args: ARGS });
try {
	// ── 0. the operator session (gate on: the ion upgrade is an operator's) ──
	session = await signIn(origin, 'Gods-eye 3D smoke (automated check)');
	ok('operator gate', true, session.gate ? 'on — signed in' : 'off — a private preview, nothing to sign in to');

	// ── 1. a keyed deck ─────────────────────────────────────────────────────
	// Read WITH the session: under the gate an anonymous read is keyless by design.
	const modeDoc = await deckFetch(session, '/gods-eye/mode', { signal: AbortSignal.timeout(5000) })
		.then((r) => r.json())
		.catch(() => ({}));
	ok('mode endpoint answers ion-photoreal (a keyed deck)', modeDoc.mode === 'ion-photoreal', `mode=${modeDoc.mode ?? 'unreachable'}${modeDoc.mode === 'keyless-osm' ? ' — run against the SAJAG_CESIUM_ION_TOKEN preview' : ''}`);
	ok('mode endpoint names the photoreal asset', modeDoc.tiles3d_asset_id === 2275207, `tiles3d_asset_id=${modeDoc.tiles3d_asset_id}`);
	if (modeDoc.mode !== 'ion-photoreal') throw new Error('not an ion-keyed deck');

	// ── 2. the overview on the photoreal city ─────────────────────────────
	const { page, log, phase, tiles: p3d, attempt } = await openWithTiles(browser, `/gods-eye${OVERVIEW_HASH}`);
	ok('canvas phase ready', phase === 'ready', `phase=${phase}${attempt > 1 ? ` (attempt ${attempt}: ion TLS refusals retried)` : ''}`);
	ok(
		'photoreal-3d: Google Photorealistic 3D Tiles cover the view',
		p3d?.initialTilesLoaded === 1 && p3d.via === 'ion' && p3d.count === 1,
		JSON.stringify(p3d),
	);
	ok('photoreal-3d: the globe kept beneath the tiles (the overlays\' ground)', p3d?.globeUnderTiles === 1, `globeUnderTiles=${p3d?.globeUnderTiles}`);
	await sleep(8000); // the layers' draws settle on the landed view
	const snap = await page.evaluate(() => {
		const g = window.__GODS_EYE__;
		return {
			imageryMode: g.imageryMode,
			imageryNote: g.imageryNote,
			offline: g.offlineDetected,
			layerStats: g.layerStats,
			pursuit: g.pursuitEntities,
			entities: g.entityCount,
			chips: Array.from(document.querySelectorAll('.ge-hud .chip.mode')).map((c) => c.textContent.trim()),
		};
	});
	ok('imageryMode ion-photoreal — never the offline schematic', snap.imageryMode === 'ion-photoreal' && snap.offline === false, `imageryMode=${snap.imageryMode} offline=${snap.offline} note=${snap.imageryNote ?? '—'}`);
	ok('no offline schematic chip', !snap.chips.some((c) => /offline/i.test(c)), snap.chips.join(' | ') || 'no mode chip');
	const chipSays = snap.chips.includes(CHIP_PHOTOREAL);
	if (MERGED) ok(`chip reads '${CHIP_PHOTOREAL}'`, chipSays, snap.chips.join(' | ') || 'no mode chip');
	else console.log(`note chip: ${snap.chips.join(' | ') || 'no mode chip'} ('${CHIP_PHOTOREAL}' asserted with GODS_EYE_3D_MERGED=1)`);

	// ── 4. every overlay draped or clamped (+ the pursuit overlay) ─────────
	const audited = [];
	for (const id of [...OVERLAYS, 'pursuit']) {
		const st = snap.layerStats?.[id];
		if (id === 'pursuit' && !st) {
			// the overlay publishes its audit through the merged canvas; before that only its count
			if (MERGED && snap.pursuit > 0) ok('pursuit: drape audit published', false, `${snap.pursuit} entities, no layerStats.pursuit`);
			else console.log(`note pursuit: ${snap.pursuit} entities${snap.pursuit > 0 ? ', drape audit published by the merged canvas' : ''}`);
			continue;
		}
		if (!st) {
			ok(`${id}: layer on the canvas`, false, 'no layerStats');
			continue;
		}
		if (!('floating' in st)) {
			// nothing drawn (no audit to publish), or a layer that publishes none
			// (enforcement before the WP-22 change to it is merged): reported —
			// asserted once it is merged
			if (MERGED && st.count > 0) ok(`${id}: drape audit published`, false, `${st.count} on the canvas, no draped/clamped/floating counts`);
			else
				console.log(
					st.count > 0
						? `note ${id}: ${st.count} on the canvas, no drape audit published by this build`
						: `ok   ${id}: nothing to drape right now (count 0)`,
				);
			continue;
		}
		const shown = (st.draped ?? 0) + (st.clamped ?? 0) + (st.floating ?? 0);
		if (!shown) {
			console.log(`ok   ${id}: nothing to drape right now (count ${st.count})`);
			continue;
		}
		audited.push(id);
		ok(`${id}: every entity draped or clamped (floating 0)`, st.floating === 0, `draped ${st.draped} · clamped ${st.clamped} · floating ${st.floating}`);
	}
	const flow = snap.layerStats?.flow;
	ok('flow: the network draped segment for segment', !!flow && flow.segments > 0 && flow.draped === flow.segments, `segments ${flow?.segments} · draped ${flow?.draped}`);
	ok('overlays audited on the 3D city', audited.length >= 3, audited.join(', '));
	const plan = await livePursuitPlan();
	if (plan) {
		ok('pursuit overlay drawn on the live interception plan', snap.pursuit > 0, `entities ${snap.pursuit} · plan for event ${plan.eventId} (${plan.chokes} chokes)`);
	} else {
		console.log(`note pursuit: no live interception plan with a sighting right now — entities ${snap.pursuit} (not asserted)`);
	}

	// ── 6. no stall on the overview ───────────────────────────────────────
	const frames = await page.evaluate(
		() =>
			new Promise((resolve) => {
				const d = [];
				let last = performance.now();
				const t0 = last;
				function step(now) {
					d.push(now - last);
					last = now;
					if (now - t0 < 10_000) requestAnimationFrame(step);
					else {
						const s = [...d].sort((a, b) => a - b);
						resolve({ n: d.length, median: Math.round(s[Math.floor(s.length / 2)]), max: Math.round(s[s.length - 1]) });
					}
				}
				requestAnimationFrame(step);
			}),
	);
	ok('no stall: no frame over 3 s (SwiftShader, 1920×1080)', frames.max < 3000, `${frames.n} frames · median ${frames.median} ms · max ${frames.max} ms`);

	const ccCredits = await creditsOnScreen(page);
	if (MERGED) {
		ok('City Command: Google + Cesium ion credits on screen, clear of the fusion rail', ccCredits.visible && ccCredits.clear && ccCredits.google && ccCredits.cesium, JSON.stringify(ccCredits));
		ok("City Command: '© OpenStreetMap contributors' on the credit plate (OSM-derived roads on the 3D city)", ccCredits.osm === true, JSON.stringify(ccCredits));
	} else {
		console.log(`note City Command credits: ${JSON.stringify(ccCredits)} (asserted with GODS_EYE_3D_MERGED=1)`);
	}

	mkdirSync(OUT, { recursive: true });
	await page.screenshot({ path: path.join(OUT, 'gods-eye-3d-smoke.png') });

	// ── 5. the flow network visible on the tiles (pose-locked on/off captures) ─
	const network = await cityNetwork();
	// the V3 Analyst city map keeps its layer tree in a sheet that is closed by default: open it once (the
	// toolbar's Layers control) so the flow layer's row exists, then click that row as before
	const toggleFlow = async () => {
		if (!(await page.$('[data-layer="flow"]'))) {
			await page.evaluate(() => [...document.querySelectorAll('.ge-hud .toolbar button')].find((b) => /layers/i.test(b.getAttribute('aria-label') ?? ''))?.click());
			await page.waitForSelector('[data-layer="flow"]', { timeout: 10_000 }).catch(() => null);
		}
		await page.evaluate(() => document.querySelector('[data-layer="flow"]')?.click());
	};
	const flowSeen = network.length ? await flowVisibility(page, network, toggleFlow) : null;
	const verdict = flowSeen ? flowVerdict(flowSeen) : { pass: false, detail: 'no segment geometry from /spatial/segments' };
	if (flowSeen?.settle) console.log(`note flow settle (/gods-eye): ${JSON.stringify(flowSeen.settle)}`);
	ok('the draped flow network is visible on the 3D tiles (pose-locked on/off: changed pixels along the projected network)', verdict.pass, verdict.detail);
	const cspEvents = await page.evaluate(() => window.__CSP_EVENTS__ ?? []);
	ok('/gods-eye: zero CSP violations', log.csp.length === 0 && cspEvents.length === 0, [...log.csp, ...cspEvents].slice(0, 2).join(' | ') || 'none');
	ok('/gods-eye: zero page errors', log.errors.length === 0, log.errors.slice(0, 2).join(' | ') || 'none');
	await page.close();

	// ── 3 + 7. '/' and /ops: CSP, photoreal, credits on screen ─────────────
	for (const route of [WORKSPACE, '/ops']) {
		const { page: p, log: l, phase: ph, tiles } = await openWithTiles(browser, route);
		await sleep(5000);
		const s = {
			mode: await p.evaluate(() => window.__GODS_EYE__?.imageryMode),
			credits: await creditsOnScreen(p),
		};
		const ev = await p.evaluate(() => window.__CSP_EVENTS__ ?? []);
		ok(`${route}: phase ready, photoreal tiles in view, imageryMode ion-photoreal`, ph === 'ready' && tiles?.initialTilesLoaded === 1 && s.mode === 'ion-photoreal', `phase=${ph} tiles=${tiles?.initialTilesLoaded} mode=${s.mode}`);
		ok(`${route}: zero CSP violations`, l.csp.length === 0 && ev.length === 0, [...l.csp, ...ev].slice(0, 2).join(' | ') || 'none');
		ok(`${route}: zero page errors`, l.errors.length === 0, l.errors.slice(0, 2).join(' | ') || 'none');
		if (route === WORKSPACE) {
			ok("'/': Google + Cesium ion credits on screen, not under a panel", s.credits.visible && s.credits.google && s.credits.cesium, JSON.stringify(s.credits));
			// The cockpit caps the bar before its bottom-centre tool dock (it wraps
			// instead) and its left rail ends at its panels: the WHOLE bar — the
			// providers' tail and 'Data attribution' included — must be clear.
			const whole = `${s.credits.w} px wide at ${s.credits.at} · osm ${s.credits.osm}`;
			if (MERGED) {
				ok("'/': the whole credit bar clear of the tool dock (right end too)", s.credits.clear === true, whole);
				ok("'/': '© OpenStreetMap contributors' on the credit plate", s.credits.osm === true, whole);
			} else {
				console.log(`note '/': whole credit bar clear (right end too): ${s.credits.clear} — ${whole} (asserted with GODS_EYE_3D_MERGED=1)`);
			}
			await p.screenshot({ path: path.join(OUT, 'gods-eye-3d-smoke-root.png') });
		}
		await p.close();
	}

	// ── 10. City Command's own home: a fresh /gods-eye, no share hash ──────
	{
		const { page: p, log: l } = await openPage(browser.defaultBrowserContext());
		await p.goto(`${origin}/gods-eye`, { waitUntil: 'domcontentloaded', timeout: 90_000 });
		const ph = await waitReady(p);
		// the home lands at once; a late fused picture re-frames it once within 12 s (+ a 1.6 s flight)
		await sleep(15_000);
		const cam = ph === 'ready' ? await settledCamera(p, 20_000) : null;
		const inBand = !!cam && cam.pitch >= HOME_3D.minPitch && cam.pitch <= HOME_3D.maxPitch && cam.alt >= HOME_3D.minAlt && cam.alt <= HOME_3D.maxAlt;
		const detail = cam
			? `pitch ${cam.pitch.toFixed(1)}° · alt ${Math.round(cam.alt)} m · heading ${cam.heading.toFixed(0)}° · at ${cam.lon.toFixed(4)},${cam.lat.toFixed(4)}`
			: `phase=${ph} · no camera`;
		if (MERGED) ok('City Command home: presentation-grade oblique (pitch −35…−45°, 1.5–3 km up)', inBand, detail);
		else console.log(`note City Command home: ${detail} (asserted with GODS_EYE_3D_MERGED=1)`);
		await sleep(10_000); // let the tiles under the landed home stream before the picture
		await p.screenshot({ path: path.join(OUT, 'gods-eye-3d-smoke-home.png') });
		ok('City Command home: zero page errors', l.errors.length === 0, l.errors.slice(0, 2).join(' | ') || 'none');
		await p.close();
	}

	// ── 11. chrome v2 on the photoreal city: the /design/map harness (UI-S3) ─
	{
		const status = await deckFetch(session, '/design/map', { signal: AbortSignal.timeout(15_000) })
			.then((r) => r.status)
			.catch(() => 0);
		if (status !== 200) {
			console.log(`note chrome v2: /design/map answered ${status || 'nothing'} — the harness is not deployed on this deck (UI-S7B deletes it); the v2 checks run where it is`);
		} else {
			const { page: p, log: l, phase: ph, tiles } = await openWithTiles(browser, '/design/map');
			await sleep(6000);
			ok('v2: phase ready, photoreal tiles in view', ph === 'ready' && tiles?.initialTilesLoaded === 1, `phase=${ph} tiles=${tiles?.initialTilesLoaded}`);
			const credits = await creditsOnScreen(p);
			const where = await p.evaluate(() => {
				const bar = document.querySelector('.ge-canvas .cesium-viewer-bottom')?.getBoundingClientRect();
				const pane = document.querySelector('.ge-wrap')?.getBoundingClientRect();
				return bar && pane ? { right: Math.round(pane.right - bar.right), bottom: Math.round(pane.bottom - bar.bottom), rightHalf: bar.left >= pane.left + pane.width / 2 - 1 } : null;
			});
			ok(
				'v2: the credits at the bottom right of the map pane, never covered (Google, Cesium ion, OSM)',
				credits.visible && credits.clear && credits.google && credits.cesium && credits.osm && !!where && where.right >= 0 && where.right <= 16 && where.bottom >= 0 && where.bottom <= 16 && where.rightHalf,
				JSON.stringify({ ...credits, ...where }),
			);
			const mode = await p.evaluate(() => document.querySelector('.ge-hud .toolbar .chip.mode')?.textContent?.trim() ?? null);
			ok('v2: .chip.mode in the toolbar', !!mode, `'${mode}'`);
			const toggleV2 = async () => {
				await p.evaluate(() => {
					if (!document.querySelector('[data-layer="flow"]')) document.querySelector('.ge-hud [data-rail="layers"]')?.click();
				});
				await sleep(500);
				await p.evaluate(() => document.querySelector('[data-layer="flow"]')?.click());
			};
			const fv = network.length ? await flowVisibility(p, network, toggleV2) : null;
			const vv = fv ? flowVerdict(fv) : { pass: false, detail: 'no segment geometry' };
			if (fv?.settle) console.log(`note flow settle (v2 harness): ${JSON.stringify(fv.settle)}`);
			ok('v2: the neutral flow network is visible on the 3D tiles (pose-locked on/off)', vv.pass, vv.detail);
			const ev = await p.evaluate(() => window.__CSP_EVENTS__ ?? []);
			ok('v2: zero CSP violations and page errors', l.csp.length === 0 && ev.length === 0 && l.errors.length === 0, [...l.csp, ...ev, ...l.errors].slice(0, 2).join(' | ') || 'none');
			await p.screenshot({ path: path.join(OUT, 'gods-eye-3d-smoke-v2.png') });
			await p.close();
		}
	}

	if (SOAK_MIN > 0) await soak(SOAK_MIN);
} catch (err) {
	ok('3d smoke ran to the end', false, err instanceof Error ? err.message : String(err));
} finally {
	await signOut(session);
	await browser.close().catch(() => {});
}

if (failures > 0) {
	console.error(`gods-eye-3d-smoke: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('ok   gods-eye-3d-smoke — all assertions passed');
process.exit(0);
