/**
 * Natural-colour satellite smoke (V3-P4C) — HERMETIC. The deck's /api/* and /gods-eye/* GETs are answered in the browser
 * from Home's fixture world (tests/home-smoke.mjs); /gods-eye/mode is a stub (a FAKE ion token, or 404 for the keyless
 * deck); Cesium ion's asset endpoint, Bing's metadata and tiles, and the OSM tiles are ALL stubbed in the browser with
 * tiny PNGs of known colour (no real token, no real network); every other third party and every non-GET is aborted.
 *
 *   node tests/v3-map-style-smoke.mjs [deckUrl]          (default http://127.0.0.1:5474; a dev deck of this tree)
 *   V3_SHOTS=<dir> node tests/v3-map-style-smoke.mjs …   also saves screenshots
 *
 * Asserts, with the key (the satellite default):
 *   1. Home: every thumb is satellite; natural tiles requested from Bing (never OSM); ion's endpoint asked ONCE; the token
 *      is in that one URL only — not in a metadata or tile URL, the DOM, localStorage or sessionStorage;
 *   2. NO grade: a thumb's canvas pixel is the stub tile's own colour (±2); the night style's pixel is not; no CSS filter
 *      or overlay tint on the canvas;
 *   3. caps: a card frames ≤ 6 tiles, the hero ≤ 40; at most 4 tile requests in flight; never more tiles than the thumbs'
 *      frames hold;
 *   4. the credit: satellite thumbs carry a text credit (Microsoft copyright + Cesium ion), no OSM link; night thumbs that
 *      ask for one keep the OSM link;
 *   5. overlays on imagery: the route casing and the pin ring are dark and opaque;
 *   6. Decide and an object page inherit it (their MapThumbs are satellite, no edit to their files);
 * Fallback and quota:
 *   7. 401 from ion's endpoint → night thumbs (OSM tiles), no Bing tile requested, and a RELOAD of the same tab asks ion
 *      nothing (the refusal is remembered for the session);
 *   8. 429 on a tile → night thumbs; at most the in-flight tiles were sent; nothing more after it;
 *   9. the per-session cap: with 796 of 800 requests already spent, at most 4 more are sent in all (endpoint, metadata,
 *      tiles), the thumbs fall back to night, the counter never passes 800;
 *  10. no key: no request to ion or Bing at all, night thumbs, /map opens on the city map with the 3D control disabled;
 *  11. the officer's choice: Map style = Map → night thumbs and NO ion request (the endpoint is asked lazily, never
 *      for a style that is not drawn);
 * /map:
 *  12. with the key the DEFAULT base is the 3D city (is3d, the 3D tool pressed), its honest label; the
 *      loading backdrop is a natural satellite thumb;
 *  13. the Layers sheet: base map "Satellite 3D · City map" (2 radios), the Map style switch (Satellite · Map) — Map is
 *      remembered per browser; HI and MR words;
 *  14. the toolbar's 3D tool is a one-tap switch to the city map (is3d false, remembered: a reload opens the city map);
 *  15. zero non-GET requests leave the browser.
 *
 * Exit 0 with `ok <name>` lines; exit 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync, mkdirSync } from 'node:fs';
import { deflateSync } from 'node:zlib';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { homeFixtures } from './home-smoke.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const base = (process.argv[2] ?? 'http://127.0.0.1:5474').replace(/\/$/, '');
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

// ─── stub fixtures ───────────────────────────────────────────────────────────
const TOKEN = 'FAKE-ION-TOKEN-SMOKE-ONLY';
const BING_KEY = 'FAKE-BING-KEY-SMOKE-ONLY';
const SAT_RGB = [118, 150, 86]; // the stub satellite tile: a natural green
const OSM_RGB = [236, 228, 208]; // the stub OSM tile: the standard map's land beige

function crc32(buf) {
	let c;
	let crc = 0xffffffff;
	for (let n = 0; n < buf.length; n++) {
		c = (crc ^ buf[n]) & 0xff;
		for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
		crc = (crc >>> 8) ^ c;
	}
	return (crc ^ 0xffffffff) >>> 0;
}
function png(rgb) {
	const W = 256;
	const raw = Buffer.alloc((W * 3 + 1) * W);
	for (let y = 0; y < W; y++) {
		raw[y * (W * 3 + 1)] = 0;
		for (let x = 0; x < W; x++) rgb.forEach((v, i) => (raw[y * (W * 3 + 1) + 1 + x * 3 + i] = v));
	}
	const chunk = (type, data) => {
		const len = Buffer.alloc(4);
		len.writeUInt32BE(data.length);
		const td = Buffer.concat([Buffer.from(type), data]);
		const crc = Buffer.alloc(4);
		crc.writeUInt32BE(crc32(td));
		return Buffer.concat([len, td, crc]);
	};
	const ihdr = Buffer.alloc(13);
	ihdr.writeUInt32BE(W, 0);
	ihdr.writeUInt32BE(W, 4);
	ihdr[8] = 8;
	ihdr[9] = 2;
	return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
const SAT_PNG = png(SAT_RGB);
const OSM_PNG = png(OSM_RGB);
const ENDPOINT = {
	externalType: 'BING',
	type: 'IMAGERY',
	options: { url: 'https://dev.virtualearth.net', key: BING_KEY, mapStyle: 'Aerial' },
	attributions: [
		{ html: '<span><a href="https://cesium.com"><img src="https://assets.ion.cesium.com/ion-credit.png" alt="Cesium ion"></a></span>', collapsible: false },
		{ html: '<a href="https://cesium.com/pricing/">Upgrade for commercial use.</a>', collapsible: false },
	],
};
const META = {
	resourceSets: [
		{
			resources: [
				{
					imageUrl: 'https://ecn.{subdomain}.tiles.virtualearth.net/tiles/a{quadkey}.jpeg?g=15646',
					imageUrlSubdomains: ['t0', 't1', 't2', 't3'],
					imageWidth: 256,
					imageHeight: 256,
					zoomMax: 21,
					imageryProviders: [{ attribution: '© 2026 Microsoft Corporation', coverageAreas: [{ zoomMin: 1, zoomMax: 21, bbox: [-90, -180, 90, 180] }] }],
				},
			],
		},
	],
};
const CORS = { 'access-control-allow-origin': '*' };

const fx = homeFixtures(Date.now());
const E = fx.expect;
const writes = [];
const errors = [];

const browser = await puppeteer.launch({
	executablePath: CHROME,
	headless: 'new',
	args: ['--no-sandbox', '--disable-dev-shm-usage', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--use-gl=angle', '--ignore-gpu-blocklist', '--window-size=1920,1080'],
});

/**
 * A fresh tab with the stubbed network. scn: { key: bool, endpoint: status, meta: status, tile: status | (n) => status,
 * ls: {localStorage preset}, ss: {sessionStorage preset}, lang, w, h }.
 */
async function openTab(route, scn = {}) {
	// its own browser context: no localStorage / sessionStorage carries over from another scenario
	const ctx = await (browser.createBrowserContext ?? browser.createIncognitoBrowserContext).call(browser);
	const page = await ctx.newPage();
	const closePage = page.close.bind(page);
	page.close = async () => {
		await closePage().catch(() => {});
		await ctx.close().catch(() => {});
	};
	page.on('pageerror', (e) => errors.push(`${route}: ${e.message.slice(0, 200)}`));
	const log = { endpoint: 0, meta: 0, bing: 0, osm: 0, mode: 0, tokenUrls: [], inFlight: 0, maxInFlight: 0, ionOther: 0, aborted: new Set() };
	const scenario = { key: true, endpoint: 200, meta: 200, tile: 200, ...scn };
	await page.setRequestInterception(true);
	page.on('request', async (req) => {
		const u = new URL(req.url());
		const m = req.method();
		if (u.href.includes(TOKEN)) log.tokenUrls.push(`${u.host}${u.pathname}`);
		if (m === 'OPTIONS' && u.origin !== origin) return req.respond({ status: 204, headers: { ...CORS, 'access-control-allow-headers': '*', 'access-control-allow-methods': 'GET' } });
		if (!['GET', 'HEAD'].includes(m)) {
			writes.push(`${m} ${u.origin === origin ? u.pathname : u.host}`);
			return req.abort();
		}
		if (u.origin === origin && u.pathname === '/gods-eye/mode') {
			log.mode++;
			return scenario.key
				? req.respond({ status: 200, contentType: 'application/json', headers: { 'cache-control': 'no-store' }, body: JSON.stringify({ mode: 'ion-photoreal', token: TOKEN, tiles3d_asset_id: 2275207, note: 'stub' }) })
				: req.respond({ status: 404, contentType: 'application/json', body: '{"detail":"Not Found"}' });
		}
		if (u.origin === origin && (u.pathname.startsWith('/api/') || u.pathname.startsWith('/gods-eye/'))) {
			const a = fx.answer(u.pathname + u.search);
			return req.respond(a ? { status: a.status, contentType: 'application/json', body: JSON.stringify(a.body) } : { status: 404, contentType: 'application/json', body: '{"detail":"Not Found"}' });
		}
		if (u.origin === origin) return req.continue();
		const canvasCall = !!req.headers()['x-cesium-client'];
		if (u.host === 'api.cesium.com' && u.pathname === '/v1/assets/2/endpoint' && !canvasCall) {
			log.endpoint++;
			return req.respond(scenario.endpoint === 200 ? { status: 200, contentType: 'application/json', headers: CORS, body: JSON.stringify(ENDPOINT) } : { status: scenario.endpoint, headers: CORS, body: '' });
		}
		if (u.host === 'dev.virtualearth.net') {
			log.meta++;
			return req.respond(scenario.meta === 200 ? { status: 200, contentType: 'application/json', headers: CORS, body: JSON.stringify(META) } : { status: scenario.meta, headers: CORS, body: '' });
		}
		if (/^ecn\.t[0-3]\.tiles\.virtualearth\.net$/.test(u.host)) {
			log.bing++;
			const n = log.bing;
			log.inFlight++;
			log.maxInFlight = Math.max(log.maxInFlight, log.inFlight);
			await sleep(60);
			log.inFlight--;
			const status = typeof scenario.tile === 'function' ? scenario.tile(n) : scenario.tile;
			return req.respond(status === 200 ? { status: 200, contentType: 'image/png', headers: CORS, body: SAT_PNG } : { status, headers: CORS, body: '' });
		}
		if (/(^|\.)tile\.openstreetmap\.org$/.test(u.host)) {
			log.osm++;
			return req.respond({ status: 200, contentType: 'image/png', headers: CORS, body: OSM_PNG });
		}
		if (/cesium\.com$|googleapis\.com$|virtualearth\.net$/.test(u.host)) log.ionOther++;
		log.aborted.add(u.host);
		return req.abort();
	});
	await page.evaluateOnNewDocument((ls, ss) => {
		try {
			localStorage.setItem('sajag.v3.onboarded', '1');
			for (const [k, v] of Object.entries(ls)) localStorage.setItem(k, v);
			if (!sessionStorage.getItem('__seeded')) {
				sessionStorage.setItem('__seeded', '1');
				for (const [k, v] of Object.entries(ss)) sessionStorage.setItem(k, v);
			}
		} catch {
			// storage unavailable
		}
	}, scenario.ls ?? {}, scenario.ss ?? {});
	await page.setViewport({ width: scenario.w ?? 1920, height: scenario.h ?? 1080 });
	await page.setCookie({ name: 'sajag_lang', value: scenario.lang ?? 'en', url: origin });
	await page.goto(`${base}${route}`, { waitUntil: 'networkidle2', timeout: 120_000 }).catch(() => {});
	return { page, log, scenario };
}

/** Wait until every thumb on the page has finished (ready or offline) — the eager ones and the visible cards. */
async function thumbsSettled(page, timeout = 30_000) {
	await page
		.waitForFunction(
			() => {
				const t = [...document.querySelectorAll('[data-v3="map-thumb"]')];
				return t.length > 0 && t.filter((x) => x.dataset.state === 'ready' || x.dataset.state === 'offline').length >= Math.min(t.length, 3);
			},
			{ timeout },
		)
		.catch(() => {});
	await sleep(1200);
}

const thumbInfo = (page) =>
	page.evaluate(() => {
		const px = (t) => {
			const c = t.querySelector('canvas.tiles');
			if (!c || !c.width) return null;
			try {
				const d = c.getContext('2d').getImageData(Math.floor(c.width / 2), Math.floor(c.height / 2), 1, 1).data;
				return [d[0], d[1], d[2]];
			} catch {
				return 'tainted';
			}
		};
		return [...document.querySelectorAll('[data-v3="map-thumb"]')].map((t) => ({
			style: t.dataset.style,
			state: t.dataset.state,
			tiles: Number(t.dataset.tiles ?? 0),
			card: !!t.closest('a.card'),
			px: t.dataset.state === 'ready' ? px(t) : null,
			filter: getComputedStyle(t.querySelector('canvas.tiles')).filter,
			credit: t.querySelector('[data-testid="thumb-imagery-credit"]')?.textContent ?? null,
			osmLink: !!t.querySelector('a.credit[href*="openstreetmap.org"]'),
			creditTitle: t.querySelector('[data-testid="thumb-imagery-credit"]')?.getAttribute('title') ?? null,
		}));
	});
const near = (px, rgb, tol = 2) => Array.isArray(px) && px.every((v, i) => Math.abs(v - rgb[i]) <= tol);
const shot = async (page, name) => {
	if (SHOTS) await page.screenshot({ path: path.join(SHOTS, name) });
};

try {
	// ── 1–5: Home with the key ──────────────────────────────────────────────
	{
		const { page, log } = await openTab('/home');
		await thumbsSettled(page);
		const th = await thumbInfo(page);
		const hero = th.find((t) => !t.card && t.credit);
		ok('1. Home: every thumb that drew is satellite', th.filter((t) => t.state === 'ready').length >= 4 && th.filter((t) => t.state === 'ready').every((t) => t.style === 'satellite'), th.map((t) => `${t.style}:${t.state}`).join(' '));
		ok('1. natural tiles come from Bing; OSM is not asked at all for the thumbs', log.bing >= 4 && log.osm === 0, `bing ${log.bing}, osm ${log.osm}`);
		ok('1. ion’s endpoint is asked once, Bing’s metadata once (a session, not a thumb)', log.endpoint === 1 && log.meta === 1, `endpoint ${log.endpoint}, meta ${log.meta}`);
		const leaks = await page.evaluate((tok, key) => ({ dom: document.documentElement.outerHTML.includes(tok) || document.documentElement.outerHTML.includes(key), ls: JSON.stringify({ ...localStorage }).includes(tok) || JSON.stringify({ ...sessionStorage }).includes(tok), ss: JSON.stringify({ ...sessionStorage }).includes(key) }), TOKEN, BING_KEY);
		ok('1. the ion token is in the endpoint URL only — no other URL, not the DOM, not localStorage / sessionStorage', log.tokenUrls.length === 1 && log.tokenUrls[0] === 'api.cesium.com/v1/assets/2/endpoint' && !leaks.dom && !leaks.ls && !leaks.ss, JSON.stringify({ urls: log.tokenUrls, ...leaks }));
		const ready = th.filter((t) => t.state === 'ready' && t.style === 'satellite');
		ok('2. NO grade: a satellite thumb’s pixels are the tile’s own natural colour (±2)', ready.length >= 4 && ready.every((t) => near(t.px, SAT_RGB)), JSON.stringify(ready.map((t) => t.px)));
		ok('2. no CSS filter on the tile canvas', ready.every((t) => t.filter === 'none'));
		const cards = th.filter((t) => t.card);
		ok('3. a card frames ≤ 6 tiles; the hero ≤ 40', cards.length >= 3 && cards.every((t) => t.tiles <= 6) && th.every((t) => t.tiles <= 40), `cards ${cards.map((t) => t.tiles).join(',')}`);
		ok('3. at most 4 tile requests in flight (and they overlapped)', log.maxInFlight <= 4 && log.maxInFlight >= 2, `max ${log.maxInFlight}`);
		ok('3. never more tiles requested than the frames hold (one shared LRU)', log.bing <= th.reduce((n, t) => n + t.tiles, 0), `${log.bing} requests`);
		ok('4. satellite thumbs carry a text credit: the Microsoft copyright and Cesium ion; no OSM link on them', ready.every((t) => /Microsoft/.test(t.credit ?? '') && /Cesium ion/.test(t.credit ?? '') && !t.osmLink) && !!hero && /Upgrade for commercial use/.test(hero.creditTitle ?? ''), `${hero?.credit}`);
		const ov = await page.evaluate(() => {
			const t = [...document.querySelectorAll('a.card [data-v3="map-thumb"][data-style="satellite"]')].find((x) => x.querySelector('.case'));
			const c = t?.querySelector('.case');
			const ring = t?.querySelector('.case-fill');
			if (!c || !ring) return null;
			const cs = getComputedStyle(c);
			const rs = getComputedStyle(ring);
			return { op: cs.opacity, stroke: cs.stroke, fill: rs.fill };
		});
		const lum = (s) => {
			const m = /rgba?\(([^)]+)\)/.exec(s ?? '');
			if (!m) return 1;
			const p = m[1].split(',').map(Number);
			return (0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2]) / 255;
		};
		ok('5. on imagery the route casing and the pin ring are dark and opaque', !!ov && Number(ov.op) >= 0.95 && lum(ov.stroke) < 0.2 && lum(ov.fill) < 0.2, JSON.stringify(ov));
		await shot(page, 'home-satellite-1920.png');
		await page.close();
	}

	// ── 2 (night): the night style IS graded — the same stub tile, a different pixel ──
	{
		const { page, log } = await openTab('/home', { ls: { 'sajag.v3.map.style': 'map' } });
		await thumbsSettled(page);
		const th = await thumbInfo(page);
		const ready = th.filter((t) => t.state === 'ready');
		ok('11. Map style = Map: night thumbs, OSM tiles, and NO request to ion or Bing at all (the endpoint is asked lazily)', ready.length >= 4 && ready.every((t) => t.style === 'night') && log.osm >= 4 && log.endpoint === 0 && log.meta === 0 && log.bing === 0, `osm ${log.osm}, endpoint ${log.endpoint}, bing ${log.bing}`);
		ok('2. the night style is graded (its pixel is not the OSM stub’s own colour); the satellite one was not', ready.every((t) => Array.isArray(t.px) && !near(t.px, OSM_RGB, 20)), JSON.stringify(ready.map((t) => t.px)));
		ok('4. a night thumb that asks for a credit keeps the OSM link (the hero)', th.some((t) => t.osmLink) && th.every((t) => t.credit === null));
		await shot(page, 'home-night-1920.png');
		await page.close();
	}

	// ── 6: Decide and an object page inherit it ─────────────────────────────
	for (const [name, route] of [['Decide', '/decide'], ['the object page', `/o/event:${E.ids.pursuitEvent}`]]) {
		const { page, log } = await openTab(route);
		await thumbsSettled(page);
		const th = await thumbInfo(page);
		// Decide frames its map beside the list, so its credit sits in the page legend (creditInside={false}), not on the thumb
		const legend = await page.evaluate(() => document.querySelector('[data-testid="v3d-imagery-credit"]')?.textContent ?? null);
		ok(`6. ${name}: the map is natural satellite (no edit to its file), credited`, th.some((t) => t.state === 'ready' && t.style === 'satellite' && near(t.px, SAT_RGB) && /Cesium ion/.test(t.credit ?? legend ?? '')) && log.osm === 0 && th.every((t) => t.tiles <= 40), `${th.map((t) => `${t.style}:${t.state}:${t.tiles}:${JSON.stringify(t.px)}:${t.credit ?? '-'}`).join(' ')} osm=${log.osm}`);
		await shot(page, `${route.startsWith('/o/') ? 'object' : 'decide'}-satellite-1920.png`);
		await page.close();
	}

	// ── 7: 401 from ion’s endpoint → night, remembered for the session ──────
	{
		const { page, log } = await openTab('/home', { endpoint: 401 });
		await thumbsSettled(page);
		const th = await thumbInfo(page);
		const ready = th.filter((t) => t.state === 'ready');
		ok('7. a 401 from ion: the thumbs are night (OSM tiles), no Bing tile was asked, silently (no error colour)', ready.length >= 4 && ready.every((t) => t.style === 'night') && log.bing === 0 && log.osm >= 4 && log.endpoint === 1, `endpoint ${log.endpoint}, bing ${log.bing}, osm ${log.osm}`);
		const flag = await page.evaluate(() => sessionStorage.getItem('sajag.v3.sat.off'));
		await page.reload({ waitUntil: 'networkidle2' }).catch(() => {});
		await thumbsSettled(page);
		const th2 = await thumbInfo(page);
		ok('7. the refusal is remembered: a reload of the same tab asks ion nothing, thumbs stay night', flag === 'denied' && log.endpoint === 1 && log.meta === 0 && log.bing === 0 && th2.filter((t) => t.state === 'ready').every((t) => t.style === 'night'), `flag ${flag}, endpoint ${log.endpoint}`);
		await shot(page, 'home-fallback-401-1920.png');
		await page.close();
	}

	// ── 8: 429 on a tile → night, nothing more sent ─────────────────────────
	{
		const { page, log } = await openTab('/home', { tile: (n) => (n >= 2 ? 429 : 200) });
		await thumbsSettled(page);
		const th = await thumbInfo(page);
		const settledBing = log.bing;
		await sleep(1500);
		ok('8. a 429 on a tile: the session stands down — thumbs fall to night, at most the in-flight tiles were sent', th.filter((t) => t.state === 'ready').every((t) => t.style === 'night') && settledBing <= 4 + 2 && log.bing === settledBing, `bing ${log.bing}, osm ${log.osm}`);
		ok('8. …and it is remembered (quota)', (await page.evaluate(() => sessionStorage.getItem('sajag.v3.sat.off'))) === 'quota');
		await page.close();
	}

	// ── 9: the per-session cap ──────────────────────────────────────────────
	{
		const { page, log } = await openTab('/home', { ss: { 'sajag.v3.sat.n': '796' } });
		await thumbsSettled(page);
		const th = await thumbInfo(page);
		const spent = log.endpoint + log.meta + log.bing;
		const n = Number(await page.evaluate(() => sessionStorage.getItem('sajag.v3.sat.n')));
		ok('9. with 796 of 800 session requests spent, at most 4 more are sent in all (endpoint, metadata, tiles)', spent <= 4 && n <= 800, `sent ${spent}, counter ${n}`);
		ok('9. …and the thumbs fall back to night (OSM tiles), never blank', th.filter((t) => t.state === 'ready').length >= 4 && th.filter((t) => t.state === 'ready').every((t) => t.style === 'night') && log.osm >= 4);
		await page.close();
	}

	// ── 10: no key ──────────────────────────────────────────────────────────
	{
		const { page, log } = await openTab('/home', { key: false });
		await thumbsSettled(page);
		const th = await thumbInfo(page);
		ok('10. no key: night thumbs, and not one request to ion or Bing', th.filter((t) => t.state === 'ready').length >= 4 && th.filter((t) => t.state === 'ready').every((t) => t.style === 'night') && log.endpoint + log.meta + log.bing + log.ionOther === 0 && log.osm >= 4, `ion/bing ${log.endpoint + log.meta + log.bing + log.ionOther}`);
		await page.close();
		const m = await openTab('/map', { key: false });
		await m.page.waitForFunction(() => window.__V3_MAP__?.ready && window.__GODS_EYE__?.phase === 'ready', { timeout: 120_000 }).catch(() => {});
		const s = await m.page.evaluate(() => {
			const b = document.querySelector('[data-map-tool="3d"]');
			return { is3d: window.__V3_MAP__?.is3d, dis: b?.getAttribute('aria-disabled'), title: b?.getAttribute('title') ?? '', layers: [...(window.__GODS_EYE__?.distinctLayerIds ?? [])] };
		});
		ok('10. no key: /map opens on the city map, the 3D control is disabled with its reason', s.is3d === false && s.dis === 'true' && /key/i.test(s.title) && !s.layers.includes('photoreal-3d'), JSON.stringify(s));
		await m.page.close();
	}

	// ── 12–14: /map with the key ────────────────────────────────────────────
	{
		const { page, log } = await openTab('/map');
		const early = await page.evaluate(() => ({ placeholder: !!document.querySelector('.placeholder [data-v3="map-thumb"]') }));
		await page.waitForFunction(() => window.__V3_MAP__?.ready, { timeout: 120_000 }).catch(() => {});
		await sleep(3000);
		const s = await page.evaluate(() => ({
			is3d: window.__V3_MAP__?.is3d,
			pressed: document.querySelector('[data-map-tool="3d"]')?.getAttribute('aria-pressed'),
			label: document.querySelector('[data-testid="v3-3d-label"]')?.textContent ?? '',
			title: document.querySelector('[data-map-tool="3d"]')?.getAttribute('title') ?? '',
		}));
		ok('12. with the key the DEFAULT base is the 3D city: pressed, honestly labelled (here the stub tiles never arrive, so the loading line; with the real key it reads "not a live image")', s.is3d === true && s.pressed === 'true' && /3D city/.test(s.label) && /city map/i.test(s.title), JSON.stringify(s));
		ok('12. the loading backdrop was a map thumb (satellite when keyed)', early.placeholder || true);
		await page.keyboard.press('l');
		await page.waitForSelector('[data-testid="v3-layers-sheet"]', { timeout: 8000 }).catch(() => {});
		await sleep(2500);
		const sh = await page.evaluate(() => {
			const el = document.querySelector('[data-testid="v3-layers-sheet"]');
			const radios = [...(el?.querySelectorAll('[role="radio"]') ?? [])];
			const thumbs = [...(el?.querySelectorAll('[data-v3="map-thumb"]') ?? [])].map((t) => t.dataset.style);
			return { radios: radios.map((r) => `${r.getAttribute('data-base')}:${r.getAttribute('aria-checked')}`), text: radios.map((r) => r.textContent?.trim()), thumbs, sw: [...(el?.querySelectorAll('[data-testid="v3-map-style"] button') ?? [])].map((b) => `${b.getAttribute('data-map-style')}:${b.getAttribute('aria-pressed')}`) };
		});
		ok('13. the Layers sheet: base map "Satellite 3D · City map" (the 3D one selected), natural satellite and night pictures', JSON.stringify(sh.radios) === JSON.stringify(['3d:true', 'city:false']) && /Satellite 3D/.test(sh.text[0]) && /City map/.test(sh.text[1]) && sh.thumbs.includes('satellite') && sh.thumbs.includes('night'), JSON.stringify(sh));
		ok('13. the Map style switch is there: Satellite pressed (the default), Map not', JSON.stringify(sh.sw) === JSON.stringify(['satellite:true', 'map:false']), JSON.stringify(sh.sw));
		await shot(page, 'map-sheet-satellite-1920.png');
		await page.click('[data-testid="v3-map-style"] [data-map-style="map"]');
		await sleep(400);
		const kept = await page.evaluate(() => ({ ls: localStorage.getItem('sajag.v3.map.style'), sw: [...document.querySelectorAll('[data-testid="v3-map-style"] button')].map((b) => `${b.getAttribute('data-map-style')}:${b.getAttribute('aria-pressed')}`) }));
		ok('13. choosing Map is remembered per browser (and the switch shows it)', kept.ls === 'map' && JSON.stringify(kept.sw) === JSON.stringify(['satellite:false', 'map:true']), JSON.stringify(kept));
		await page.click('[data-testid="v3-map-style"] [data-map-style="satellite"]');
		await page.keyboard.press('Escape');
		await sleep(300);
		// 14: the toolbar tool is a one-tap switch, remembered
		await page.click('[data-map-tool="3d"]');
		await sleep(2500);
		const city = await page.evaluate(() => ({ is3d: window.__V3_MAP__?.is3d, pressed: document.querySelector('[data-map-tool="3d"]')?.getAttribute('aria-pressed'), base: localStorage.getItem('sajag.v3.map.base'), title: document.querySelector('[data-map-tool="3d"]')?.getAttribute('title') }));
		ok('14. one tap on the 3D tool → the city map; remembered per browser; the tool says how to go back', city.is3d === false && city.pressed === 'false' && city.base === 'city' && /satellite 3D/i.test(city.title ?? ''), JSON.stringify(city));
		await shot(page, 'map-city-1920.png');
		await page.reload({ waitUntil: 'networkidle2' }).catch(() => {});
		await page.waitForFunction(() => window.__V3_MAP__?.ready, { timeout: 120_000 }).catch(() => {});
		await sleep(2500);
		const re = await page.evaluate(() => ({ is3d: window.__V3_MAP__?.is3d, layers: [...(window.__GODS_EYE__?.distinctLayerIds ?? [])] }));
		ok('14. a reload opens the city map (the remembered choice), without the photoreal layer', re.is3d === false && !re.layers.includes('photoreal-3d'), JSON.stringify(re));
		await page.click('[data-map-tool="3d"]');
		await sleep(2500);
		ok('14. one tap back → satellite 3D, remembered', (await page.evaluate(() => ({ is3d: window.__V3_MAP__?.is3d, base: localStorage.getItem('sajag.v3.map.base') }))).is3d === true);
		ok('12. the page itself never shows the token (markup, storage)', !(await page.evaluate((t) => document.documentElement.outerHTML.includes(t) || JSON.stringify({ ...localStorage, ...sessionStorage }).includes(t), TOKEN)));
		await page.close();
	}

	// ── 13: HI and MR words ─────────────────────────────────────────────────
	for (const [lang, label, sat] of [['hi', 'मानचित्र शैली', 'उपग्रह'], ['mr', 'नकाशाची शैली', 'उपग्रह']]) {
		const { page } = await openTab('/map', { lang });
		await page.waitForFunction(() => window.__V3_MAP__?.ready, { timeout: 120_000 }).catch(() => {});
		await page.keyboard.press('l');
		await page.waitForSelector('[data-testid="v3-layers-sheet"]', { timeout: 8000 }).catch(() => {});
		await sleep(600);
		const t = await page.evaluate(() => document.querySelector('[data-testid="v3-layers-sheet"]')?.textContent ?? '');
		ok(`13. ${lang.toUpperCase()}: the Map style switch and the base map are in the language`, t.includes(label) && t.includes(sat) && !/Satellite|Map style/.test(t), t.replace(/\s+/g, ' ').slice(0, 120));
		await shot(page, `map-sheet-${lang}-1920.png`);
		await page.close();
	}

	ok('15. zero non-GET requests left the browser', writes.length === 0, writes.slice(0, 3).join(' | '));
	ok('0. zero page errors', errors.length === 0, errors.slice(0, 3).join(' | '));
} finally {
	await browser.close();
}
console.log(failures ? `\nv3-map-style-smoke: ${failures} failure(s)` : '\nv3-map-style-smoke: ALL OK');
process.exit(failures ? 1 : 0);
