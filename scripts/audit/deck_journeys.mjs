/**
 * audit/deck_journeys.mjs — the deck's main journeys, walked in a real browser with a screenshot per step.
 *
 *   node scripts/audit/deck_journeys.mjs [--origin http://127.0.0.1:5373] [--out <dir>] [--lang en]
 *        [--only decide,map,roadstate,assistant,plan,citizen,driver] [--signin 'Journey check (automated)']
 *        [--allow-writes]
 *
 *   decide     the queue; open an e-challan (never the stolen plate's sighting, never the 108 request), read why;
 *              with --allow-writes approve it, then open another and reject it with a reason
 *   map        the Map's Layers sheet: every layer switched on and off in turn (waterlogging, forecast, air,
 *              cameras, signals, flow, …), a shot with each on
 *   roadstate  the camera object page: the nearby street photo, then the road-state read
 *   assistant  one question in Marathi and one in English
 *   plan       a movement plan, Mantralaya to the airport (T2): places, class, Find routes (a WRITE: a planning movement —
 *              --allow-writes; it is labelled "JOURNEY CHECK (automated)", which demo_reset --cancel-debris cancels)
 *   citizen    /citizen (anonymous): pick a road, press Listen
 *   driver     /driver (anonymous)
 *
 * Without --allow-writes every non-GET /api/* request except the session and the compute reads is answered 503 in
 * the browser and never leaves it. The officer name defaults to the journey actor demo_reset.sh recognises as
 * debris. The operator PIN is read by scripts/lib/deck_session.mjs and never printed; response bodies are never
 * logged. Each step prints one JSON line (shot file, console errors, failed requests).
 */
import fs from 'node:fs';
import os from 'node:os';
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
const ORIGIN = opt('--origin', 'http://127.0.0.1:5373').replace(/\/+$/, '');
const OUT = path.resolve(opt('--out', path.join(os.tmpdir(), 'sajag-deck-journeys')));
const LANG = opt('--lang', 'en');
const ONLY = opt('--only', 'decide,map,roadstate,assistant,plan,citizen,driver').split(',').map((s) => s.trim()).filter(Boolean);
const OFFICER = opt('--signin', 'Journey check (automated)');
const WRITES = argv.includes('--allow-writes');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const CONSOLE = { width: 1440, height: 900 };
const PHONE = { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true };
const STOLEN = /(?:WB\s?06|MH\s?47)\s?EM\s?9001/i;

fs.mkdirSync(OUT, { recursive: true });

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
		await sleep(600);
	}
	throw new Error(`no element ${sel}${re ? ` matching ${re}` : ''}`);
}
async function waitText(page, re, timeout = 30000) {
	const t0 = Date.now();
	while (Date.now() - t0 < timeout) {
		if (await page.evaluate((s, f) => new RegExp(s, f).test(document.body?.innerText || ''), re.source, re.flags).catch(() => false)) return true;
		await sleep(700);
	}
	return false;
}
const text = (page, sel) => page.$eval(sel, (e) => e.innerText.trim()).catch(() => null);

const browser = await puppeteer.launch({
	executablePath: CHROME,
	headless: 'new',
	protocolTimeout: 240000,
	args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--use-gl=angle', '--ignore-gpu-blocklist',
		'--window-size=1440,900', '--autoplay-policy=no-user-gesture-required', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'],
});
let session = null;
const log = [];

async function open(url, { view = CONSOLE, pub = false, lang = LANG } = {}) {
	const ctx = pub ? await browser.createBrowserContext() : browser.defaultBrowserContext();
	const page = await ctx.newPage();
	page.__errs = [];
	page.__net = [];
	page.__writes = [];
	await page.setViewport(view);
	const host = new URL(ORIGIN).hostname;
	const cookies = [{ name: 'sajag_lang', value: lang, domain: host, path: '/' }];
	if (!pub && session?.gate) cookies.push(...puppeteerCookies(session));
	await page.setCookie(...cookies);
	page.on('pageerror', (e) => page.__errs.push('pageerror: ' + String(e.message).slice(0, 240)));
	page.on('console', (m) => { if (m.type() === 'error') page.__errs.push('console: ' + m.text().slice(0, 240)); });
	page.on('response', (res) => {
		if (res.status() >= 400) {
			const u = new URL(res.url());
			page.__net.push(`${res.status()} ${res.request().method()} ${u.origin === ORIGIN ? '' : u.origin}${u.pathname}`);
		}
	});
	await page.setRequestInterception(true);
	page.on('request', (req) => {
		const u = new URL(req.url());
		const compute = /^\/api\/(speech|vision|twin|hydro|forecast)\//.test(u.pathname) || u.pathname.endsWith('/api/v1/traffic/live')
			|| u.pathname === '/api/session' || u.pathname.startsWith('/api/convoy/chat');
		if (u.origin === ORIGIN && u.pathname.startsWith('/api/') && !['GET', 'HEAD'].includes(req.method())) {
			page.__writes.push(`${req.method()} ${u.pathname}`);
			if (!WRITES && !compute) return req.respond({ status: 503, contentType: 'application/json', body: '{"error":"deck_journeys: writes refused"}' });
		}
		return req.continue();
	});
	await page.goto(ORIGIN + url, { waitUntil: 'load', timeout: 90000 }).catch((e) => page.__errs.push('goto: ' + e.message.slice(0, 160)));
	return page;
}
async function shot(page, journey, step, note = {}) {
	const file = path.join(OUT, `${journey}-${String(log.filter((l) => l.journey === journey).length + 1).padStart(2, '0')}-${step}.jpg`);
	await page.screenshot({ path: file, type: 'jpeg', quality: 82 }).catch(() => {});
	const rec = { journey, step, file, ...note, errors: page.__errs.splice(0), failed: page.__net.splice(0), writes: page.__writes.splice(0) };
	log.push(rec);
	console.log(JSON.stringify(rec));
}

const J = {
	async decide() {
		const page = await open('/decide');
		await sleep(15000);
		await shot(page, 'decide', 'queue', { count: await text(page, '[data-testid="v3-queue-count"]') });
		// the e-challans of the queue (never the stolen plate, never the 108 corridor request)
		const pick = async (skip = []) => page.evaluate((stolen, skipKeys) => {
			const rx = new RegExp(stolen, 'i');
			const cards = [...document.querySelectorAll('[data-testid="queue-card"][data-key^="echallan:"]')]
				.filter((c) => !rx.test(c.innerText + (c.getAttribute('aria-label') || '')));
			const c = cards.find((x) => !skipKeys.includes(x.getAttribute('data-key') || x.innerText.slice(0, 60)));
			if (!c) return null;
			c.scrollIntoView({ block: 'center' });
			c.click();
			return c.getAttribute('data-key') || c.innerText.slice(0, 60);
		}, STOLEN.source, skip);
		const first = await pick();
		await sleep(5000);
		await shot(page, 'decide', 'open-echallan', { picked: first, url: page.url() });
		// read why: open every <details> of the sheet
		await page.evaluate(() => document.querySelectorAll('[data-testid="v3-decision-sheet"] details').forEach((d) => { d.open = true; }));
		await sleep(1500);
		await shot(page, 'decide', 'why');
		const sheet = await text(page, '[data-testid="v3-decision-sheet"]');
		if (sheet && STOLEN.test(sheet)) throw new Error('the open unit names the stolen plate: stopping before any decision');
		if (!WRITES) return;
		const primary = await page.$eval('[data-testid="v3-primary"]', (b) => ({ action: b.dataset.action, label: b.innerText.trim(), blocked: b.getAttribute('aria-disabled') })).catch(() => null);
		await shot(page, 'decide', 'before-approve', { primary });
		if (!primary || primary.blocked === 'true') return;
		await clickSel(page, '[data-testid="v3-primary"]');
		await sleep(6000);
		await shot(page, 'decide', 'approved', { outcome: await text(page, '[data-testid="v3-outcome"], [data-testid="decision-outcome"], [data-testid="decision-refusal"]') });
		// another e-challan: reject it with a reason
		await page.goto(ORIGIN + '/decide', { waitUntil: 'load' });
		await sleep(12000);
		const second = await pick([first]);
		await sleep(5000);
		const sec = await page.$$eval('[data-testid="v3-secondary"]', (bs) => bs.map((b) => ({ action: b.dataset.action, label: b.innerText.trim() }))).catch(() => []);
		await shot(page, 'decide', 'open-second', { picked: second, secondary: sec });
		const rej = sec.find((s) => /reject|dismiss|decline|বাতিল|अस्वीकार/i.test(`${s.action} ${s.label}`));
		if (!rej) return;
		await clickSel(page, `[data-testid="v3-secondary"][data-action="${rej.action}"]`);
		await sleep(1200);
		const reason = await page.$('[data-testid="decision-reason"]');
		if (reason) { await reason.type('Reading needs a second camera check (journey check)', { delay: 10 }); }
		await shot(page, 'decide', 'reject-reason');
		await clickSel(page, `[data-testid="v3-secondary"][data-action="${rej.action}"]`);
		await sleep(6000);
		await shot(page, 'decide', 'rejected', { outcome: await text(page, '[data-testid="v3-outcome"], [data-testid="decision-outcome"], [data-testid="decision-refusal"]') });
		await page.close();
	},

	async map() {
		const page = await open('/map');
		await sleep(25000);
		await shot(page, 'map', 'open');
		await clickSel(page, '[data-testid="v3-map-layers"]');
		await sleep(1500);
		const rows = await page.$$eval('button[data-layer]', (bs) => bs.map((b) => ({ id: b.dataset.layer, on: b.getAttribute('aria-checked') })));
		await shot(page, 'map', 'layers-sheet', { rows });
		await page.keyboard.press('Escape');
		for (const r of rows) {
			// switch it on (or leave it on), shoot, then restore it
			await clickSel(page, '[data-testid="v3-map-layers"]');
			await sleep(800);
			if (r.on !== 'true') await clickSel(page, `button[data-layer="${r.id}"]`);
			await sleep(800);
			const sub = await page.$eval(`[data-layer-row="${r.id}"] .sub`, (e) => e.innerText.trim()).catch(() => null);
			await page.keyboard.press('Escape');
			await sleep(9000);
			await shot(page, 'map', `layer-${r.id}`, { sub });
			if (r.on !== 'true') {
				await clickSel(page, '[data-testid="v3-map-layers"]');
				await sleep(600);
				await clickSel(page, `button[data-layer="${r.id}"]`);
				await sleep(600);
				await page.keyboard.press('Escape');
			}
		}
		// a camera on the map: its selection card (the road state lives on its object page)
		await clickSel(page, '[data-testid="v3-map-layers"]');
		await sleep(600);
		const camOn = await page.$eval('button[data-layer="cameras"]', (b) => b.getAttribute('aria-checked')).catch(() => null);
		if (camOn !== 'true') await clickSel(page, 'button[data-layer="cameras"]').catch(() => {});
		await page.keyboard.press('Escape');
		await sleep(6000);
		const pts = await page.evaluate(() => window.__GODS_EYE__?.locate?.('cam:') ?? window.__GODS_EYE__?.locate?.('camera:') ?? []).catch(() => []);
		if (pts.length) {
			await page.mouse.click(pts[0].x, pts[0].y);
			await sleep(5000);
			await shot(page, 'map', 'camera-selected', { id: pts[0].id });
		}
		await page.close();
	},

	async roadstate() {
		const page = await open('/o/camera:EM-CAM-04', { view: { width: 1440, height: 1200 } });
		await sleep(10000);
		await shot(page, 'roadstate', 'object-page');
		const street = await page.waitForSelector('[data-testid="rs-street"]:not([disabled])', { visible: true, timeout: 60000 }).catch(() => null);
		if (street) {
			await clickSel(page, '[data-testid="rs-street"]');
			await page.waitForSelector('[data-testid="rs-street-date"]', { visible: true, timeout: 60000 }).catch(() => {});
			await sleep(3000);
			await shot(page, 'roadstate', 'street-photo');
		}
		await clickSel(page, '[data-testid="rs-read"]').catch(() => {});
		const ok = await waitText(page, /confidence|waterlogged|depth|আস্থা|विश्वास/i, 240000);
		await sleep(2000);
		await shot(page, 'roadstate', 'read', { answered: ok });
		await page.close();
	},

	async assistant() {
		for (const [lang, q] of [['mr', 'এখন কোন রাস্তায় জল জমেছে?'], ['en', 'Which roads are waterlogged right now, and what should we do?']]) {
			const page = await open('/assistant', { lang });
			await sleep(8000);
			await shot(page, 'assistant', `${lang}-open`);
			await page.type('[data-testid="v3-ask"]', q, { delay: 15 });
			await page.keyboard.press('Enter');
			await sleep(4000);
			const t0 = Date.now();
			while (Date.now() - t0 < 240000) {
				// the stream is over when the composer takes a question again: type a probe character, read the send button
				const busy = await page.evaluate(() => {
					const ask = document.querySelector('[data-testid="v3-ask"]');
					const send = document.querySelector('[data-testid="v3-send"]');
					return !ask || !send || ask.disabled || (!!ask.value.trim() && send.disabled) || /thinking|reading the city/i.test(document.body.innerText);
				}).catch(() => true);
				if (!busy) break;
				await sleep(2500);
			}
			await sleep(3000);
			await shot(page, 'assistant', `${lang}-answer`, { secs: Math.round((Date.now() - t0) / 1000) });
			await page.close();
		}
	},

	async plan() {
		const page = await open('/plan');
		await sleep(10000);
		await shot(page, 'plan', 'open');
		const places = await page.$$('[data-testid="v3-plan-place"] input, input[data-testid="v3-plan-place"]');
		const fill = async (i, q) => {
			if (!places[i]) return;
			await places[i].click({ clickCount: 3 });
			await places[i].type(q, { delay: 30 });
			await sleep(1500);
			await page.keyboard.press('Enter');
			await sleep(1200);
		};
		await fill(0, 'Mantralaya');
		await fill(1, 'Airport');
		await shot(page, 'plan', 'places');
		await clickSel(page, '[data-testid="v3-plan-class"]').catch(() => {});
		await sleep(800);
		// the label: a labelled movement is never shown as a real one, and demo_reset recognises it as debris
		await clickSel(page, 'button.linkish', /label/i, 5000).catch(() => {});
		await sleep(500);
		const lab = await page.$('[data-testid="v3-plan-label"]');
		if (lab) await lab.type('JOURNEY CHECK (automated)');
		await shot(page, 'plan', 'class-label', { labelled: !!lab });
		if (!WRITES || !lab) return;
		await clickSel(page, '[data-testid="v3-plan-find"]');
		// the planner answers synchronously (it can take minutes): wait for its state, a refusal or "no route"
		await page.waitForSelector('[data-testid="v3-plan-status"], [data-testid="v3-plan-failure"], [data-testid="v3-plan-no-route"], [data-testid="v3-plan-refusal"]', { timeout: 300000 }).catch(() => {});
		await sleep(6000);
		await shot(page, 'plan', 'routes', { status: await text(page, '[data-testid="v3-plan-status"]') });
		await page.close();
	},

	async citizen() {
		const page = await open('/citizen', { view: PHONE, pub: true, lang: LANG === 'en' ? 'mr' : LANG });
		await sleep(10000);
		await shot(page, 'citizen', 'open');
		const opts = await page.$$eval('[data-testid="water-road"] option', (os) => os.map((o) => o.value).filter(Boolean)).catch(() => []);
		if (opts.length) await page.select('[data-testid="water-road"]', opts.includes('1058') ? '1058' : opts[0]);
		await sleep(3000);
		await page.evaluate(() => document.querySelector('[data-testid="water-card"]')?.scrollIntoView({ block: 'center' }));
		await sleep(800);
		await shot(page, 'citizen', 'road-picked', { roads: opts.length });
		await clickSel(page, '[data-testid="water-card"] [data-testid="listen"]', null, 8000).catch(() => clickSel(page, '[data-testid="listen"]'));
		await sleep(1500);
		await shot(page, 'citizen', 'listen-loading');
		const t0 = Date.now();
		let state = null;
		while (Date.now() - t0 < 90000) {
			state = await page.evaluate(() => {
				const b = document.querySelector('[data-testid="water-card"] [data-testid="listen"]') || document.querySelector('[data-testid="listen"]');
				return b ? `${b.getAttribute('aria-pressed') || ''} ${b.getAttribute('data-phase') || ''} ${b.innerText.trim()}` : null;
			});
			if (state && !/loading|লোড|लोड|…/i.test(state)) break;
			await sleep(1500);
		}
		await shot(page, 'citizen', 'listen-done', { state, secs: Math.round((Date.now() - t0) / 1000) });
		await page.evaluate(() => document.scrollingElement.scrollTo(0, document.scrollingElement.scrollHeight));
		await sleep(1500);
		await shot(page, 'citizen', 'bottom');
		await page.close();
	},

	async driver() {
		for (const lang of ['mr', 'en']) {
			const page = await open('/driver', { view: PHONE, pub: true, lang });
			await sleep(12000);
			await shot(page, 'driver', `${lang}-open`);
			await page.evaluate(() => { const el = document.querySelector('.driver-page'); if (el) el.scrollTop = el.scrollHeight; });
			await sleep(1500);
			await shot(page, 'driver', `${lang}-bottom`);
			await page.close();
		}
	},
};

let failed = 0;
try {
	session = await signIn(ORIGIN, OFFICER);
	for (const name of ONLY) {
		try {
			await J[name]();
		} catch (e) {
			failed++;
			console.log(JSON.stringify({ journey: name, failed: String(e).slice(0, 300) }));
		}
	}
} finally {
	if (session?.gate) await signOut(session).catch(() => {});
	await browser.close().catch(() => {});
	fs.writeFileSync(path.join(OUT, 'journeys.json'), JSON.stringify(log, null, 1));
}
process.exit(failed ? 1 : 0);
