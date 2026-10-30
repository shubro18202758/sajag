/**
 * AI surfaces browser smoke (int-ops) — Home, the Map and Decide with the forecast, hydro and twin services, in a
 * hermetic fixture world: the platform answers from tests/home-smoke.mjs's fixtures, the AI services from
 * tests/fixtures/ai/*.json (their real answers on the GB10, 28 Oct 2026), every third party is aborted and every
 * non-GET is intercepted (the twin's compute POST answered from its fixture; the decision record answered 404 —
 * "not deployed yet" — so the console keeps it and says so).
 *
 *   node tests/ai-ops-smoke.mjs [deck base URL, default http://127.0.0.1:5471]   (a dev deck; never a live port)
 *   AI_SHOTS=<dir> writes screenshots.
 *
 *   1. Home: "Next 2 hours" — the forecast crossings (count and the soonest three), the waterlogging line, the tide,
 *      the signal-timing proposals waiting — each with its honest label (Modelled, Simulated)
 *   2. Home: "Replay 23 Sep 2025" — the chart, 13 / 13 reported places flagged, the first flag 02:45, labelled
 *      Observed · Modelled · Hindsight; "Show on the map" links the map's hindsight
 *   3. Map: the Rain · Tide chip — rain (Live), tide and gates (Modelled), pumps (Emulated), roads at risk
 *   4. Map: the Layers sheet holds Waterlogging risk (on) and Traffic forecast (off); the forecast switch draws its
 *      dashed roads (fc: entities appear) — visibly different
 *   5. Map: the 23 Sep 2025 hindsight draws the waterlogging layer (wl: entities), a moment of the night changes it,
 *      the waterlogging switch takes it off the map, "Back to live" returns to the dry nowcast (none)
 *   6. Decide: the AI proposals queue (forecast + twin), a card's sheet with its labels and evidence; the twin's
 *      before / after (four rows)
 *   7. Decide: no officer → Approve sends NOTHING; named → exactly one POST /api/v1/ai-proposals/decision (approve,
 *      the officer named), and the outcome says it was kept on this console (the log is not deployed)
 *   8. Decide: the 23 Sep 2025 exercise — hydro cards flagged Exercise; approving one sends nothing
 *   9. मराठी: Home's card and the map's chip in Marathi
 */
import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { homeFixtures } from './home-smoke.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const base = (process.argv[2] ?? 'http://127.0.0.1:5471').replace(/\/$/, '');
const origin = new URL(base).origin;
if (/:(5273|5373|8090|8091|8092|8190|8191|8192)$/.test(origin)) {
	console.error('refusing a live port');
	process.exit(2);
}
const SHOTS = process.env.AI_SHOTS ? path.resolve(process.env.AI_SHOTS) : null;
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
const AI = Object.fromEntries(['forecast', 'nowcast', 'twin', 'replay', 'tide', 'rain'].map((n) => [n, JSON.parse(readFileSync(path.join(HERE, 'fixtures', 'ai', `${n}.json`), 'utf8'))]));
// the fixtures are a moment of 28 Oct 2026: the tide's "next high water" is computed against the page clock, so the
// smoke holds the tide model's own "now" (the chip says what the model says, whatever the date of the run)
const aiAnswer = (p) => {
	if (/^\/api\/forecast\/forecast\/segments/.test(p)) return AI.forecast;
	if (/^\/api\/hydro\/hydro\/nowcast/.test(p)) return AI.nowcast;
	if (/^\/api\/hydro\/hydro\/tide/.test(p)) return AI.tide;
	if (/^\/api\/hydro\/hydro\/rain/.test(p)) return AI.rain;
	return null;
};

const fx = homeFixtures(Date.now());
const writes = [];
const errors = [];
const browser = await puppeteer.launch({
	executablePath: CHROME,
	headless: 'new',
	args: ['--no-sandbox', '--disable-dev-shm-usage', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--use-gl=angle', '--ignore-gpu-blocklist', '--window-size=1920,1080'],
});

async function page(lang = 'en') {
	const p = await browser.newPage();
	await p.setViewport({ width: 1920, height: 1080 });
	await p.setCookie({ name: 'sajag_lang', value: lang, url: origin });
	p.on('pageerror', (e) => errors.push(e.message.slice(0, 200)));
	await p.evaluateOnNewDocument(() => {
		try {
			localStorage.setItem('sajag.v3.onboarded', '1');
		} catch {
			// storage unavailable
		}
	});
	await p.setRequestInterception(true);
	p.on('request', (req) => {
		const u = new URL(req.url());
		const m = req.method();
		const pth = u.pathname + u.search;
		if (u.origin !== origin) return req.abort();
		if (u.pathname.startsWith('/api/') || u.pathname.startsWith('/gods-eye/')) {
			if (m !== 'GET' && m !== 'HEAD') {
				writes.push({ method: m, path: u.pathname, body: req.postData() ?? '' });
				if (u.pathname === '/api/twin/twin/propose') return req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify(AI.twin) });
				if (u.pathname === '/api/hydro/hydro/replay') return req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify(AI.replay) });
				return req.respond({ status: 404, contentType: 'application/json', body: '{"detail":"Not Found"}' });
			}
			const a = aiAnswer(pth);
			if (a) return req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify(a) });
			const f = fx.answer(pth);
			return req.respond(f ? { status: f.status, contentType: 'application/json', body: JSON.stringify(f.body) } : { status: 404, contentType: 'application/json', body: '{"detail":"Not Found"}' });
		}
		if (m !== 'GET' && m !== 'HEAD') {
			writes.push({ method: m, path: u.pathname, body: '' });
			return req.abort();
		}
		return req.continue();
	});
	return p;
}
const shot = async (p, name) => {
	if (SHOTS) await p.screenshot({ path: path.join(SHOTS, name) });
};
const text = (p, sel) => p.$eval(sel, (e) => e.textContent.replace(/\s+/g, ' ').trim()).catch(() => '');
const entities = (p, prefix) => p.evaluate((pre) => (window.__GODS_EYE__?.locate?.(pre) ?? []).length, prefix).catch(() => -1);
const layerRow = (p, id) => p.evaluate((i) => window.__V3_MAP__?.layers?.find((l) => l.id === i) ?? null, id);

try {
	// ── 1–2: Home ────────────────────────────────────────────────────────────
	const home = await page();
	await home.goto(`${base}/home`, { waitUntil: 'networkidle2', timeout: 120_000 }).catch(() => {});
	await home.waitForFunction(() => /forecast over 0\.8/.test(document.querySelector('[data-testid="ai-next-hours"]')?.textContent ?? ''), { timeout: 60_000 }).catch(() => {});
	const nh = await text(home, '[data-testid="ai-next-hours"]');
	ok('1. Home: Next 2 hours — the crossings count, the soonest three, from the forecast service', nh.includes(`${AI.forecast.proposals.length} roads forecast over 0.8 V/C`) && (await home.$$('[data-testid="ai-next-hours"] .chip')).length === 3, nh.slice(0, 160));
	ok('1. Home: the waterlogging line, the tide and the outfall gates from the hydro service', /No road at waterlogging risk|roads? at waterlogging risk/.test(nh) && nh.includes(`Tide ${AI.tide.now.level_m.toFixed(2)} m`) && /Outfall gates (open|shut)/.test(nh));
	ok('1. Home: every line labelled — Modelled, and Simulated while the forecast history is', /Modelled/.test(nh) && /Simulated/.test(nh));
	await home.waitForFunction(() => /signal-timing proposals? waiting/.test(document.querySelector('[data-testid="ai-next-hours"]')?.textContent ?? ''), { timeout: 30_000 }).catch(() => {});
	ok('1. Home: the twin was asked about the forecast stress (compute only) and its proposal waits', /1 signal-timing proposal waiting/.test(await text(home, '[data-testid="ai-next-hours"]')) && writes.some((w) => w.path === '/api/twin/twin/propose'));
	await shot(home, 'home-next-hours.png');
	await home.click('[data-testid="ai-replay-open"]');
	await home.waitForSelector('[data-testid="ai-replay"][data-ready="true"]', { timeout: 30_000 }).catch(() => {});
	const rp = await text(home, '[data-testid="ai-replay"]');
	ok('2. Home: the replay — 13 / 13 reported places flagged, the first road deep at 02:45 IST', /13 \/ 13/.test(rp) && /02:45/.test(rp) && !!(await home.$('[data-testid="ai-replay-chart"]')), rp.slice(0, 160));
	ok('2. Home: labelled Observed · Modelled · Hindsight, with the archive’s miss said', /Observed/.test(rp) && /Modelled/.test(rp) && /Hindsight/.test(rp) && /gridded archive held 20\.5 mm/.test(rp));
	ok('2. Home: "Show on the map" opens the map in hindsight', (await home.$eval('[data-testid="ai-replay-map"]', (a) => a.getAttribute('href')).catch(() => '')) === '/map?replay=2025-08-19');
	await shot(home, 'home-replay.png');
	await home.close();

	// ── 3–5: Map ─────────────────────────────────────────────────────────────
	const map = await page();
	await map.goto(`${base}/map`, { waitUntil: 'networkidle2', timeout: 120_000 }).catch(() => {});
	await map.waitForFunction(() => window.__V3_MAP__?.ready && window.__GODS_EYE__?.phase === 'ready', { timeout: 120_000 }).catch(() => {});
	await map.waitForFunction(() => /Tide/.test(document.querySelector('[data-testid="ai-rain-tide"]')?.textContent ?? ''), { timeout: 30_000 }).catch(() => {});
	await sleep(2500);
	const chip = await text(map, '[data-testid="ai-rain-tide"]');
	ok('3. Map: Rain · Tide — rain Live, tide and gates Modelled, pumps Emulated, roads at risk Modelled', /Rain \d+\.\d mm\/h/.test(chip) && /Live/.test(chip) && chip.includes(`Tide ${AI.tide.now.level_m.toFixed(2)} m`) && /Modelled/.test(chip) && /Pumps \d+ of \d+ available/.test(chip) && /Emulated/.test(chip), chip.slice(0, 200));
	await map.click('[data-testid="v3-map-layers"]');
	await map.waitForSelector('[data-testid="v3-layers-sheet"] [data-layer="forecast"]', { timeout: 5000 }).catch(() => {});
	const rows = await map.evaluate(() => ({ water: document.querySelector('[data-layer="waterlog"]')?.getAttribute('aria-checked'), fc: document.querySelector('[data-layer="forecast"]')?.getAttribute('aria-checked'), wtxt: document.querySelector('[data-layer-row="waterlog"]')?.textContent ?? '' }));
	ok('4. Map: the sheet holds Waterlogging risk (on, modelled) and Traffic forecast (off)', rows.water === 'true' && rows.fc === 'false' && /Modelled/.test(rows.wtxt), JSON.stringify(rows));
	const fc0 = await entities(map, 'fc:');
	await map.click('[data-testid="v3-layers-sheet"] [data-layer="forecast"]');
	await map.waitForFunction(() => (window.__GODS_EYE__?.locate?.('fc:') ?? []).length > 0 || (window.__V3_MAP__?.layers?.find((l) => l.id === 'forecast')?.count ?? 0) > 0, { timeout: 30_000 }).catch(() => {});
	await sleep(1500);
	const fcRow = await layerRow(map, 'forecast');
	ok('4. Map: the forecast switch draws the roads forecast over 0.8 (visibly different), labelled simulated', fc0 === 0 && fcRow?.visible && fcRow.count > 0 && /simulated traffic/.test(fcRow.hint), JSON.stringify(fcRow));
	await shot(map, 'map-forecast-on.png');
	await map.click('[data-testid="v3-layers-sheet"] [data-layer="forecast"]');
	await map.keyboard.press('Escape');
	await sleep(800);
	const wlLive = await entities(map, 'wl:');
	await map.click('[data-testid="ai-hs-open"]');
	await map.waitForFunction(() => window.__V3_MAP__?.ai?.hindsight === true, { timeout: 30_000 }).catch(() => {});
	await sleep(3500);
	const hs = await map.evaluate(() => window.__V3_MAP__.ai);
	const wlHs = (await layerRow(map, 'waterlog'))?.count ?? 0;
	ok('5. Map: the 23 Sep 2025 hindsight draws the waterlogging layer (none on the dry live evening)', wlLive === 0 && hs.hindsight && wlHs > 40 && /Hindsight 23 Sep 2025/.test((await layerRow(map, 'waterlog')).hint), `${wlLive} → ${wlHs} · ${JSON.stringify(hs.counts)}`);
	const steps = await map.$$('[data-testid="ai-hs-step"]');
	await steps[0]?.click();
	await sleep(3000);
	const early = (await layerRow(map, 'waterlog'))?.count ?? -1;
	ok('5. Map: an earlier moment of the night has fewer roads under water', early >= 0 && early < wlHs, `${early} < ${wlHs}`);
	await shot(map, 'map-hindsight.png');
	await map.click('[data-testid="v3-map-layers"]');
	await map.waitForSelector('[data-testid="v3-layers-sheet"] [data-layer="waterlog"]', { timeout: 5000 }).catch(() => {});
	const before = await entities(map, 'wl:');
	await map.click('[data-testid="v3-layers-sheet"] [data-layer="waterlog"]');
	await sleep(2500);
	const after = await entities(map, 'wl:');
	ok('5. Map: the waterlogging switch takes it off the map (visibly different)', before > 0 && after === 0, `${before} → ${after}`);
	await map.click('[data-testid="v3-layers-sheet"] [data-layer="waterlog"]');
	await map.keyboard.press('Escape');
	await sleep(500);
	await map.click('[data-testid="ai-hs-live"]');
	await sleep(3000);
	ok('5. Map: Back to live returns the dry nowcast (nothing drawn)', (await entities(map, 'wl:')) === 0 && (await map.evaluate(() => window.__V3_MAP__.ai.hindsight)) === false);
	await map.close();

	// ── 6–8: Decide ──────────────────────────────────────────────────────────
	const dec = await page();
	await dec.goto(`${base}/decide`, { waitUntil: 'networkidle2', timeout: 120_000 }).catch(() => {});
	await dec.waitForFunction((n) => (window.__V3_DECIDE__?.ai?.cards?.length ?? 0) >= n, { timeout: 60_000 }, AI.forecast.proposals.length + 1).catch(() => {});
	const q = await dec.evaluate(() => window.__V3_DECIDE__.ai);
	ok('6. Decide: the AI proposals queue — every forecast crossing and the twin’s timing', q.cards.filter((c) => c.source === 'forecast').length === AI.forecast.proposals.length && q.cards.some((c) => c.source === 'twin'), JSON.stringify(q.cards.map((c) => c.source)));
	const twinKey = await dec.evaluate(() => [...document.querySelectorAll('[data-testid="ai-queue-card"]')].find((a) => a.dataset.key.startsWith('ai:twin'))?.dataset.key ?? null);
	await dec.click(`[data-key="${twinKey}"]`);
	await dec.waitForSelector('[data-testid="ai-twin-compare"]', { timeout: 10_000 }).catch(() => {});
	const tw = await dec.evaluate(() => ({ rows: document.querySelectorAll('[data-testid="ai-twin-compare"] [data-metric]').length, sheet: document.querySelector('[data-testid="ai-sheet"]')?.textContent.replace(/\s+/g, ' ') ?? '' }));
	ok('6. Decide: the twin card — before / after in four rows, Modelled, the demand label, the emulated adapter in what changes', tw.rows === 4 && /Modelled/.test(tw.sheet) && /(Simulated|Emulated|Live)/.test(tw.sheet) && /emulated, so no controller changes/.test(tw.sheet), tw.sheet.slice(0, 160));
	await shot(dec, 'decide-twin.png');
	const fcKey = await dec.evaluate(() => [...document.querySelectorAll('[data-testid="ai-queue-card"]')].find((a) => a.dataset.key.startsWith('ai:fc-'))?.dataset.key ?? null);
	await dec.click(`[data-key="${fcKey}"]`);
	await sleep(1200);
	const w0 = writes.filter((w) => w.path.startsWith('/api/v1/')).length;
	await dec.click('[data-testid="ai-approve"]');
	await sleep(800);
	ok('7. Decide: no officer named → Approve sends nothing', writes.filter((w) => w.path.startsWith('/api/v1/')).length === w0);
	await dec.type('[data-testid="decision-officer"]', 'S. Haldar');
	await dec.click('[data-testid="v3-officer-continue"]');
	await sleep(500);
	await dec.click('[data-testid="ai-approve"]');
	await dec.waitForSelector('[data-testid="ai-outcome"]', { timeout: 15_000 }).catch(() => {});
	const posts = writes.filter((w) => w.path === '/api/v1/ai-proposals/decision');
	const body = posts[0] ? JSON.parse(posts[0].body) : null;
	const out = await text(dec, '[data-testid="ai-outcome"]');
	ok('7. Decide: named → exactly one POST /api/v1/ai-proposals/decision (approve, the officer, the proposal mapped)', posts.length === 1 && body?.decision === 'approve' && body?.officer === 'S. Haldar' && body?.proposal?.source === 'forecast' && body?.proposal?.state === 'proposed', posts.map((p) => p.body.slice(0, 120)).join(' | '));
	ok('7. Decide: the outcome says it was kept on this console (the decision log is not deployed yet)', /Approved/.test(out) && /Kept on this console/.test(out), out);
	await shot(dec, 'decide-approved.png');
	await dec.click('[data-testid="ai-exercise"]');
	await dec.waitForFunction(() => window.__V3_DECIDE__?.ai?.cards?.some((c) => c.source === 'hydro'), { timeout: 30_000 }).catch(() => {});
	const exKey = await dec.evaluate(() => [...document.querySelectorAll('[data-testid="ai-queue-card"]')].find((a) => a.dataset.key.startsWith('ai:hy-'))?.dataset.key ?? null);
	await dec.click(`[data-key="${exKey}"]`);
	await sleep(1200);
	const ex = await dec.evaluate(() => document.querySelector('[data-testid="ai-sheet"]')?.dataset.exercise);
	const p0 = writes.filter((w) => w.path === '/api/v1/ai-proposals/decision').length;
	await dec.click('[data-testid="ai-approve"]');
	await dec.waitForSelector('[data-testid="ai-outcome"]', { timeout: 10_000 }).catch(() => {});
	ok('8. Decide: the 23 Sep 2025 exercise — hydro cards flagged; approving one sends nothing', !!exKey && ex === 'true' && writes.filter((w) => w.path === '/api/v1/ai-proposals/decision').length === p0 && /Exercise/.test(await text(dec, '[data-testid="ai-outcome"]')));
	await shot(dec, 'decide-exercise.png');
	await dec.close();

	// ── 9: Marathi ───────────────────────────────────────────────────────────
	const mr = await page('mr');
	await mr.goto(`${base}/home`, { waitUntil: 'networkidle2', timeout: 120_000 }).catch(() => {});
	await mr.waitForFunction(() => /আগামী 2 ঘণ্টা/.test(document.querySelector('[data-testid="ai-next-hours"]')?.textContent ?? ''), { timeout: 60_000 }).catch(() => {});
	const bnTxt = await text(mr, '[data-testid="ai-next-hours"]');
	ok('9. मराठी: Home’s card in Marathi, the numbers in Latin digits, the labels too', /আগামী 2 ঘণ্টা/.test(bnTxt) && /মডেল-ভিত্তিক/.test(bnTxt) && /সিমুলেটেড/.test(bnTxt) && /\d/.test(bnTxt) && !/[০-৯]/.test(bnTxt), bnTxt.slice(0, 160));
	await shot(mr, 'home-mr.png');
	await mr.close();

	const stray = writes.filter((w) => !['/api/twin/twin/propose', '/api/v1/ai-proposals/decision', '/api/hydro/hydro/replay', '/api/v1/traffic/live'].includes(w.path));
	ok('10. no other non-GET left the browser (the twin compute, the replay, the one decision; the flow layer’s read)', stray.length === 0, stray.map((w) => `${w.method} ${w.path}`).join(' | '));
	ok('11. no page error', errors.length === 0, errors.slice(0, 3).join(' | '));
} finally {
	await browser.close();
}
if (failures) {
	console.error(`\nFAIL ai-ops-smoke — ${failures} check(s) failed`);
	process.exit(1);
}
console.log('\nai-ops-smoke: ALL OK');
