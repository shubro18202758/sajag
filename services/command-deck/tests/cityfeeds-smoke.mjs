/**
 * City feeds — browser smoke against a dev deck whose /api/cityfeeds reaches services/cityfeeds (CITYFEEDS_PORT).
 *
 *   node tests/cityfeeds-smoke.mjs [http://127.0.0.1:5491]
 *   CF_FIXTURES=1   answer /api/cityfeeds from tests/fixtures/cityfeeds/ (the offline recording) instead of the service
 *   CF_SHOTS=dir    write the screenshots there (map with the air layer, the cyclone layer, the sheet, Home, the
 *                   citizen card; EN and मराठी)
 *
 *   1. Home: the City row under "Next 2 hours" — Air · Heat · Cyclone · River · Quake, each labelled
 *   2. Map: the City row under Rain · Tide; the Layers sheet has the City feeds section; switching the air layer on
 *      draws the ten sites (the canvas's entity count rises, the layer's stats count 10); switching it off clears them
 *   3. Map: the cyclone layer draws the active storm (or its row says "No active cyclone")
 *   4. the Air chip opens its sheet: figures, the proposal (or why none) and the sources; Esc closes it
 *   5. the citizen page: "Air today" in मराठी with the Listen button and the Modelled tag
 * Never writes: every non-GET /api request is refused by the interceptor.
 */
import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const base = (process.argv[2] ?? 'http://127.0.0.1:5491').replace(/\/$/, '');
const origin = new URL(base).origin;
if (/:(5273|5373|8090|8091|8092)$/.test(origin)) {
	console.error('refusing a live port');
	process.exit(2);
}
const SHOTS = process.env.CF_SHOTS ? path.resolve(process.env.CF_SHOTS) : null;
if (SHOTS) mkdirSync(SHOTS, { recursive: true });
const FIX = process.env.CF_FIXTURES === '1';
const fixture = (name) => readFileSync(path.join(HERE, 'fixtures', 'cityfeeds', `${name}.json`), 'utf8');
const ROUTE_FIX = { '/feeds/summary': 'summary', '/feeds/air': 'air', '/feeds/heat': 'heat', '/feeds/cyclones': 'cyclones', '/feeds/river': 'river', '/feeds/quakes': 'quakes' };

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
const errors = [];

const browser = await puppeteer.launch({
	executablePath: CHROME,
	headless: 'new',
	args: ['--no-sandbox', '--disable-dev-shm-usage', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--use-gl=angle', '--ignore-gpu-blocklist', '--window-size=1920,1080'],
});

async function newPage(lang) {
	const page = await browser.newPage();
	await page.setViewport({ width: 1920, height: 1080 });
	await page.setCookie({ name: 'sajag_lang', value: lang, url: origin });
	page.on('pageerror', (e) => errors.push(e.message.slice(0, 240)));
	await page.setRequestInterception(true);
	page.on('request', (req) => {
		const u = new URL(req.url());
		if (u.pathname.startsWith('/api/') && !['GET', 'HEAD', 'OPTIONS'].includes(req.method()) && !u.pathname.endsWith('/api/v1/traffic/live')) {
			return req.respond({ status: 503, contentType: 'application/json', body: '{"error":"cityfeeds-smoke: writes refused"}' });
		}
		if (FIX && u.pathname.startsWith('/api/cityfeeds/')) {
			const name = ROUTE_FIX[u.pathname.slice('/api/cityfeeds'.length)];
			if (name) return req.respond({ status: 200, contentType: 'application/json', body: fixture(name) });
		}
		return req.continue();
	});
	return page;
}

const shot = async (page, name, el = null) => {
	if (!SHOTS) return;
	if (el) await el.screenshot({ path: path.join(SHOTS, name) }).catch(() => page.screenshot({ path: path.join(SHOTS, name) }));
	else await page.screenshot({ path: path.join(SHOTS, name) });
};

const chipState = (page) =>
	page.evaluate(() => {
		const sec = document.querySelector('[data-testid="cf-chips"]');
		return {
			status: sec?.getAttribute('data-status') ?? null,
			rows: [...(sec?.querySelectorAll('[data-chip]') ?? [])].map((b) => ({ id: b.getAttribute('data-chip'), label: b.getAttribute('data-label'), text: b.textContent?.replace(/\s+/g, ' ').trim() ?? '' })),
		};
	});

try {
	for (const lang of ['en', 'mr']) {
		// ── 1. Home ──
		const home = await newPage(lang);
		await home.goto(`${base}/`, { waitUntil: 'networkidle2', timeout: 120_000 }).catch(() => {});
		await home.waitForFunction(() => document.querySelectorAll('[data-testid="cf-chips"] [data-chip]').length === 5 && document.querySelector('[data-testid="cf-chips"]')?.getAttribute('data-status') === 'ok', { timeout: 90_000 }).catch(() => {});
		const h = await chipState(home);
		ok(`1. [${lang}] Home: the City row — air, heat, cyclone, river, quake — each with an honest label`, h.rows.map((r) => r.id).join() === 'air,heat,cyclone,river,quake' && h.rows.every((r) => ['LIVE', 'MODELLED', 'UNAVAILABLE'].includes(r.label ?? '')), JSON.stringify(h.rows.map((r) => `${r.id}:${r.label}:${r.text}`)));
		if (lang === 'mr') ok('1. [mr] Home: the row is in मराठी', /বাতাস/.test(h.rows[0]?.text ?? '') && /ঘূর্ণিঝড়/.test(h.rows[2]?.text ?? ''), h.rows[0]?.text);
		const pulse = await home.$('[data-testid="v3-pulse"]');
		await pulse?.evaluate((el) => el.scrollIntoView({ block: 'end' }));
		await sleep(600);
		await shot(home, `home-${lang}.png`);
		await shot(home, `home-chips-${lang}.png`, await home.$('[data-testid="cf-chips"]'));
		await home.close();

		// ── 2. Map + the air layer ──
		const map = await newPage(lang);
		await map.goto(`${base}/map`, { waitUntil: 'networkidle2', timeout: 120_000 }).catch(() => {});
		await map.waitForFunction(() => window.__V3_MAP__?.ready && window.__GODS_EYE__?.phase === 'ready', { timeout: 120_000 }).catch(() => {});
		await map.waitForFunction(() => document.querySelector('[data-testid="cf-chips"]')?.getAttribute('data-status') === 'ok', { timeout: 90_000 }).catch(() => {});
		await sleep(2500);
		const m = await chipState(map);
		ok(`2. [${lang}] Map: the City row sits on the map with five chips`, m.rows.length === 5, JSON.stringify(m.rows.map((r) => r.text)));
		const before = await map.evaluate(() => window.__GODS_EYE__?.entityCount ?? 0);
		await map.keyboard.press('l');
		await map.waitForSelector('[data-testid="v3-layers-sheet"] [data-layer="air"]', { timeout: 8000 }).catch(() => {});
		const rowsText = await map.evaluate(() => [...document.querySelectorAll('[data-layer-row="air"], [data-layer-row="cyclone"]')].map((r) => r.textContent?.replace(/\s+/g, ' ').trim()));
		ok(`2. [${lang}] the Layers sheet has the City feeds rows (air, cyclone), off at first`, rowsText.length === 2, JSON.stringify(rowsText));
		await map.click('[data-testid="v3-layers-sheet"] [data-layer="air"]').catch(() => {});
		await map.waitForFunction(() => (window.__GODS_EYE__?.layerStats?.air?.count ?? 0) >= 10, { timeout: 90_000 }).catch(() => {});
		await sleep(3000);
		const air = await map.evaluate(() => ({ stats: window.__GODS_EYE__?.layerStats?.air ?? null, n: window.__GODS_EYE__?.entityCount ?? 0, ids: window.__GODS_EYE__?.distinctLayerIds ?? [], row: document.querySelector('[data-layer-row="air"]')?.textContent?.replace(/\s+/g, ' ').trim() }));
		ok(`2. [${lang}] the air switch draws the ten sites (the canvas visibly changes)`, air.ids.includes('air') && (air.stats?.count ?? 0) === 10 && air.n > before, JSON.stringify({ before, after: air.n, count: air.stats?.count, row: air.row }));
		const legend = await map.evaluate(() => !!document.querySelector('[data-testid="v3-legend"] [data-legend="air"]'));
		ok(`2. [${lang}] the legend gains the air-quality line while the layer is on`, legend);
		await shot(map, `map-air-3d-${lang}.png`);
		// the whole city: the City map base (2D, the city's home view) shows every site
		await map.click('[data-testid="v3-layers-sheet"] [data-base="city"]').catch(() => {});
		await sleep(6000);
		await map.keyboard.press('Escape');
		await sleep(800);
		// zoom out to the whole city (the ten sites span Belur Math to Jadavpur)
		for (let i = 0; i < Number(process.env.CF_ZOOM_OUT ?? 3); i++) {
			await map.click('[data-map-tool="zoom-out"]').catch(() => {});
			await sleep(1500);
		}
		await sleep(5000);
		await shot(map, `map-air-${lang}.png`);

		// ── 3. the cyclone layer ──
		await map.keyboard.press('l');
		await map.waitForSelector('[data-testid="v3-layers-sheet"] [data-layer="cyclone"]', { timeout: 8000 }).catch(() => {});
		const beforeCy = await map.evaluate(() => window.__GODS_EYE__?.entityCount ?? 0);
		await map.click('[data-testid="v3-layers-sheet"] [data-layer="cyclone"]').catch(() => {});
		await map.waitForFunction(() => window.__GODS_EYE__?.layerStats?.cyclone && !window.__GODS_EYE__.layerStats.cyclone.loading, { timeout: 90_000 }).catch(() => {});
		await sleep(3000);
		const cy = await map.evaluate(() => ({ stats: window.__GODS_EYE__?.layerStats?.cyclone ?? null, n: window.__GODS_EYE__?.entityCount ?? 0, row: document.querySelector('[data-layer-row="cyclone"]')?.textContent?.replace(/\s+/g, ' ').trim() }));
		const active = (cy.stats?.count ?? 0) > 0;
		ok(`3. [${lang}] the cyclone switch draws the active storm and its bearing marker, or the row says there is none`, active ? cy.n > beforeCy : /No active cyclone|কোনো সক্রিয় ঘূর্ণিঝড় নেই/.test(cy.row ?? ''), JSON.stringify({ before: beforeCy, after: cy.n, hint: cy.stats?.hint, row: cy.row }));
		await shot(map, `map-cyclone-sheet-${lang}.png`);
		await map.keyboard.press('Escape');
		await sleep(600);
		await shot(map, `map-cyclone-${lang}.png`);
		// air off again: its sites leave the canvas
		await map.keyboard.press('l');
		await map.waitForSelector('[data-testid="v3-layers-sheet"] [data-layer="air"]', { timeout: 8000 }).catch(() => {});
		await map.click('[data-testid="v3-layers-sheet"] [data-layer="air"]').catch(() => {});
		await sleep(2500);
		const off = await map.evaluate(() => ({ ids: window.__GODS_EYE__?.distinctLayerIds ?? [], n: window.__GODS_EYE__?.entityCount ?? 0 }));
		ok(`2. [${lang}] the air switch off clears the sites`, !off.ids.includes('air') && off.n < air.n + (cy.n - beforeCy), JSON.stringify(off));
		await map.keyboard.press('Escape');
		await sleep(500);

		// ── 4. the Air chip's sheet ──
		await map.click('[data-testid="cf-chips"] [data-chip="air"]').catch(() => {});
		await map.waitForFunction(() => document.querySelector('[data-testid="cf-sheet"]')?.getAttribute('data-status') === 'ok', { timeout: 60_000 }).catch(() => {});
		await sleep(800);
		const sh = await map.evaluate(() => {
			const s = document.querySelector('[data-testid="cf-sheet"]');
			return { open: !!s, figures: s?.querySelectorAll('[data-testid="cf-figures"] li').length ?? 0, proposal: !!s?.querySelector('[data-testid="cf-proposal"]'), none: s?.querySelector('[data-testid="cf-no-proposal"]')?.textContent?.trim() ?? null, links: s?.querySelectorAll('a[href^="https://"]').length ?? 0, approve: /\b(Approve|Apply)\b/.test(s?.textContent ?? '') };
		});
		ok(`4. [${lang}] the Air chip opens its sheet: figures, the proposal or why none, the sources — never an Approve`, sh.open && sh.figures >= 2 && (sh.proposal || !!sh.none) && sh.links >= 2 && !sh.approve, JSON.stringify(sh));
		await shot(map, `map-air-sheet-${lang}.png`);
		await map.keyboard.press('Escape');
		await sleep(400);
		ok(`4. [${lang}] Esc closes the sheet`, !(await map.$('[data-testid="cf-sheet"]')));
		await map.close();
	}

	// ── 5. the citizen page ──
	const cit = await newPage('mr');
	await cit.goto(`${base}/citizen`, { waitUntil: 'networkidle2', timeout: 120_000 }).catch(() => {});
	await cit.waitForFunction(() => document.querySelector('[data-testid="air-card"]')?.getAttribute('data-status') === 'ready', { timeout: 90_000 }).catch(() => {});
	await sleep(1500);
	const c = await cit.evaluate(() => {
		const card = document.querySelector('[data-testid="air-card"]');
		return { status: card?.getAttribute('data-status'), head: card?.querySelector('[data-testid="air-headline"]')?.textContent ?? '', listen: !!card?.querySelector('button'), tag: card?.querySelector('[data-label="MODELLED"]')?.textContent ?? '' };
	});
	ok('5. citizen: "Air today" in plain मराठी with Marathi digits, a Listen button and the Modelled tag', c.status === 'ready' && /^আজ কলকাতার বাতাস .+ \(AQI প্রায় [০-৯]+\)।$/.test(c.head) && c.listen && /মডেল-ভিত্তিক/.test(c.tag), JSON.stringify(c));
	const card = await cit.$('[data-testid="air-card"]');
	await card?.evaluate((el) => el.scrollIntoView({ block: 'center' }));
	await sleep(400);
	await shot(cit, 'citizen-air-mr.png', card);
	await cit.close();
	ok('no page error', errors.length === 0, errors.slice(0, 4).join(' | '));
} finally {
	await browser.close();
}

if (failures) {
	console.error(`\nFAIL cityfeeds-smoke — ${failures} assertion(s) failed`);
	process.exit(1);
}
console.log('cityfeeds-smoke: ALL OK');
