/**
 * /assistant smoke (V3-P4; V3-SPEC §5.7, §7.6, §8) — HERMETIC: every same-origin /api/* and /gods-eye/* GET is answered
 * in the browser from Home's fixture world (tests/home-smoke.mjs); the ONE non-GET the page may send — POST
 * /api/convoy/chat/stream — is answered in the browser with a canned NDJSON turn (no model is called) and counted;
 * every other non-GET is ABORTED and recorded; tiles and third parties are aborted.
 *
 *   node tests/v3-assistant-smoke.mjs [deckUrl]       (default http://127.0.0.1:5472; a dev deck of this tree)
 *   V3_SHOTS=<dir> node tests/v3-assistant-smoke.mjs …   also saves screenshots
 *
 * The canned turn is a grounded answer that cites the fixture's stolen vehicle (a decision waits on it) and a camera,
 * ran three lookups (one in the traffic twin), had one statement removed by the grounding check, and carries the
 * brain's raw diagnostics — a decider/Gemma disagreement, the model ids, the tool names, a lookup dump — exactly the
 * things the page must turn into words.
 *
 * Asserts:
 *   1. the empty state, four suggestions, the scope line; zero page errors;
 *   2. a suggestion sends exactly ONE chat POST (the brain's English question; no session yet); the bubble shows
 *      the label;
 *   3. the answer renders with the cited objects as chips (the vehicle chip orange: a decision waits); the steps
 *      are folded in a closed <details> and read as words (the twin step "simulated");
 *   4. the grounding check's note is kept; the disagreement is ONE human sentence;
 *   5. NO raw model code, model id or tool name anywhere in the page's DOM (innerText and HTML);
 *   6. the proposal card: "Open to decide" → /decide/stolen-sighting:<vehicle> (its ONE home), "Show on map";
 *      no Apply and no Approve control anywhere;
 *   7. the context panel lists the named objects, the vehicle with "a decision waits"; the model line in words;
 *   8. honesty: no raw registration mark in innerText without an officer (the masked one shows);
 *   9. a typed follow-up sends ONE more POST carrying the brain session from the first answer;
 *  10. Clear conversation empties the thread;
 *  11. HI and MR: the suggestions and the empty state are translated;
 *  12. 1366×768: the context column is 300 px, the suggestions stay on one row;
 *  13. Show on map opens /map with the object selected on the canvas;
 *  14. zero other non-GET requests: every one but the answered chat POSTs was aborted (none was attempted).
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
const VEH = `vehicle:${E.ids.vehicle}`;
const CAM = 'camera:EM-CAM-03';
const TOOLS = ['list_enforcement_recommendations', 'city_get_dossier', 'simulate_twin'];
const RAW = [...TOOLS, 'decider_gemma_disagreement', 'ungrounded_claims_removed', 'pplx-decider-v1-27b', 'gemma-3-27b-it', 'decider:', 'gemma:', 'route_length_m'];
const ndjson = (rows) => rows.map((r) => JSON.stringify(r)).join('\n') + '\n';
const turn = (sid, answer) =>
	ndjson([
		{ type: 'tool_call', data: { id: 'c1', name: TOOLS[0], args: {} } },
		{ type: 'tool_result', data: { id: 'c1', name: TOOLS[0], ok: true, summary: '4 decisions waiting' } },
		{ type: 'tool_call', data: { id: 'c2', name: TOOLS[1], args: { urn: VEH } } },
		{ type: 'tool_result', data: { id: 'c2', name: TOOLS[1], ok: true, summary: 'last read on EM-CAM-03' } },
		{ type: 'tool_call', data: { id: 'c3', name: TOOLS[2], args: {} } },
		{ type: 'tool_result', data: { id: 'c3', name: TOOLS[2], ok: true, summary: '3 exit plans compared' } },
		{ type: 'token', data: answer },
		{ type: 'directive', data: { id: `dir-${sid}`, verb: 'canvas_fly_to', args: { urn: CAM }, label: 'fly to EM-CAM-03', provenance: { session_id: sid, tier: 'decider' } } },
		{
			type: 'done',
			data: {
				session_id: sid,
				tiers_used: ['decider:pplx-decider-v1-27b', 'gemma:gemma-3-27b-it'],
				operator_alerts: ['decider_gemma_disagreement: decider hold vs Gemma release — acted on the tactical pick', 'ungrounded_claims_removed: 1 claim(s) no tool reported were removed from the answer'],
				degraded: false,
				citations: [
					{ urn: VEH, label: E.maskedPlate },
					{ urn: CAM, label: 'EM-CAM-03' },
				],
			},
		},
	]);
const ANSWER = `Four decisions are waiting. The most pressing is authorising the pursuit of ${E.maskedPlate}, reported stolen and last read on EM-CAM-03. What the lookups returned: list_enforcement_recommendations 4 rows; predict_eta refused: route_length_m missing.`;

const chats = [];
const writes = [];
const errors = [];
const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--disable-dev-shm-usage', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--use-gl=angle', '--window-size=1920,1080'] });

async function open(page, { lang = 'en', w = 1920, h = 1080 } = {}) {
	await page.setViewport({ width: w, height: h });
	await page.setCookie({ name: 'sajag_lang', value: lang, url: origin });
	await page.goto(`${base}/assistant`, { waitUntil: 'networkidle2', timeout: 120_000 }).catch(() => {});
	await page.waitForSelector('[data-testid="v3-suggestions"]', { timeout: 30_000 }).catch(() => {});
	await page.waitForFunction(() => (window.__V3_ASSISTANT__?.canonical?.decisions ?? 0) >= 4, { timeout: 30_000 }).catch(() => {});
	await sleep(1500);
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
			if (m === 'POST' && u.origin === origin && u.pathname === '/api/convoy/chat/stream') {
				let body = {};
				try {
					body = JSON.parse(req.postData() ?? '{}');
				} catch {
					// not JSON
				}
				chats.push(body);
				return req.respond({ status: 200, contentType: 'application/x-ndjson', body: turn(`sess-${chats.length}`, ANSWER) });
			}
			writes.push(`${m} ${u.origin === origin ? u.pathname : u.host}`);
			return req.abort();
		}
		if (u.origin === origin && (u.pathname.startsWith('/api/') || u.pathname.startsWith('/gods-eye/'))) {
			const a = fx.answer(u.pathname + u.search);
			return req.respond(a ? { status: a.status, contentType: 'application/json', body: JSON.stringify(a.body) } : { status: 404, contentType: 'application/json', body: '{"detail":"Not Found"}' });
		}
		if (u.origin !== origin) return req.abort();
		return req.continue();
	});

	// ── 1: the empty state ──────────────────────────────────────────────────
	await open(page);
	const s1 = await page.evaluate(() => ({
		empty: !!document.querySelector('[data-testid="v3-assistant-empty"]'),
		sugs: [...document.querySelectorAll('[data-testid="v3-suggestions"] [data-suggest]')].map((b) => b.getAttribute('data-suggest')),
		scope: document.querySelector('.scope')?.textContent ?? '',
		ctx: !!document.querySelector('[data-testid="v3-context"]'),
	}));
	ok('1. the empty state, four suggestions, the scope line and the context column', s1.empty && s1.sugs.length === 4 && /cannot approve, unmask or dispatch/.test(s1.scope) && s1.ctx, s1.sugs.join(','));
	await shot(page, 'assistant-1920-empty.png');

	// ── 2–8: one turn ───────────────────────────────────────────────────────
	await page.click('[data-suggest="next-hour"]');
	await page.waitForSelector('[data-testid="v3-answer"]', { timeout: 15_000 }).catch(() => {});
	await sleep(1200);
	ok('2. a suggestion sends exactly ONE chat POST — the brain’s question, no session yet', chats.length === 1 && /What needs my decision in the next hour/.test(chats[0]?.message ?? '') && !chats[0]?.session_id, JSON.stringify(chats[0] ?? {}).slice(0, 140));
	const s3 = await page.evaluate(() => {
		const fold = document.querySelector('[data-testid="v3-steps-fold"]');
		return {
			you: document.querySelector('[data-testid="v3-you"]')?.textContent ?? '',
			chips: [...document.querySelectorAll('[data-testid="v3-answer"] [data-testid="v3-obj-chip"]')].map((c) => ({ t: c.textContent.trim(), d: c.getAttribute('data-decide') })),
			foldOpen: fold ? fold.open : null,
			steps: [...document.querySelectorAll('[data-testid="v3-step"]')].map((s) => s.textContent.replace(/\s+/g, ' ').trim()),
		};
	});
	ok('2. the bubble shows the suggestion’s label', s3.you === 'What needs me in the next hour?');
	ok('3. the cited objects are chips in the sentence; the vehicle’s is orange (a decision waits)', s3.chips.length >= 2 && s3.chips.some((c) => c.d === 'true'), JSON.stringify(s3.chips));
	ok('3. the steps are folded (a closed <details>) and read as words; the twin step says "simulated"', s3.foldOpen === false && s3.steps.length === 3 && s3.steps.some((x) => /Ran the plan in the traffic twin.*simulated/.test(x)), s3.steps.join(' | '));
	const s4 = await page.evaluate(() => ({
		grounding: document.querySelector('[data-testid="v3-grounding"]')?.textContent ?? '',
		cautions: [...document.querySelectorAll('[data-testid="v3-caution"]')].map((c) => [c.getAttribute('data-caution'), c.textContent.trim()]),
	}));
	ok('4. the grounding check’s note is kept', /1 statement removed: not in the lookups/.test(s4.grounding));
	ok('4. the disagreement is ONE human sentence', s4.cautions.filter(([k]) => k === 'v3a_caution_disagree').length === 1 && s4.cautions.some(([, t]) => /Two of my models disagreed/.test(t)), JSON.stringify(s4.cautions).slice(0, 200));
	await page.evaluate(() => document.querySelector('[data-testid="v3-steps-fold"]')?.setAttribute('open', ''));
	await page.evaluate(() => document.querySelector('[data-testid="v3-trace"]')?.setAttribute('open', ''));
	await sleep(300);
	const dom = await page.evaluate(() => ({ text: document.body.innerText, html: document.querySelector('[data-v3="assistant"]')?.outerHTML ?? '' }));
	const leaks = (s) => ['list_enforcement_recommendations', 'city_get_dossier', 'simulate_twin', 'decider_gemma_disagreement', 'ungrounded_claims_removed', 'pplx-decider-v1-27b', 'gemma-3-27b-it', 'decider:', 'gemma:', 'route_length_m', 'predict_eta'].filter((c) => s.includes(c));
	ok('5. no raw model code, model id or tool name in the page (innerText, steps and trace open)', leaks(dom.text).length === 0, leaks(dom.text).join(','));
	ok('5. … nor anywhere in its HTML', leaks(dom.html).length === 0, leaks(dom.html).join(','));
	const s6 = await page.evaluate(() => ({
		open: [...document.querySelectorAll('[data-testid="v3-proposal-open"]')].map((a) => a.getAttribute('href')),
		map: document.querySelectorAll('[data-testid="v3-proposal-map"]').length,
		verbs: [...document.querySelectorAll('button, a')].map((b) => b.textContent?.trim() ?? '').filter((x) => /^(approve|apply)\b/i.test(x)),
	}));
	ok('6. "Open to decide" → the vehicle’s decision in Decide (its ONE home); "Show on map"', s6.open.some((h) => h === `/decide/${encodeURIComponent(`stolen-sighting:${E.ids.vehicle}`)}`) && s6.map >= 1, s6.open.join(','));
	ok('6. no Apply and no Approve anywhere on /assistant', s6.verbs.length === 0, s6.verbs.join(','));
	const s7 = await page.evaluate(() => ({ hook: window.__V3_ASSISTANT__?.context ?? [], model: document.querySelector('[data-testid="v3-model-line"]')?.textContent ?? '', items: [...document.querySelectorAll('[data-testid="v3-context-item"]')].map((x) => x.textContent.replace(/\s+/g, ' ').trim()) }));
	ok('7. the context lists the named objects; the vehicle "a decision waits"', s7.hook.length === 2 && s7.hook.some((c) => c.decide) && s7.items.some((t) => /a decision waits/.test(t)), s7.items.join(' | '));
	ok('7. the model line is in words', /Decision model, checked by a second model/.test(s7.model) && /Last answer took/.test(s7.model), s7.model);
	ok('8. no raw registration mark without an officer; the masked one shows', !dom.text.includes(E.rawPlate) && dom.text.includes(E.maskedPlate));
	await shot(page, 'assistant-1920-turn.png');

	// ── 9: a follow-up carries the brain session ────────────────────────────
	await page.type('[data-testid="v3-ask"]', 'And the 108 request?');
	await page.keyboard.press('Enter');
	await page.waitForFunction(() => document.querySelectorAll('[data-testid="v3-bot-turn"]').length >= 2, { timeout: 15_000 }).catch(() => {});
	await sleep(800);
	ok('9. a typed follow-up sends ONE more POST carrying the first answer’s session', chats.length === 2 && chats[1]?.session_id === 'sess-1' && chats[1]?.message === 'And the 108 request?', JSON.stringify(chats[1] ?? {}).slice(0, 120));
	await shot(page, 'assistant-1920-followup.png');

	// ── 10: clear ───────────────────────────────────────────────────────────
	await page.click('[data-testid="v3-clear"]');
	await sleep(500);
	ok('10. Clear conversation empties the thread', !!(await page.$('[data-testid="v3-assistant-empty"]')) && (await page.$$('[data-testid="v3-bot-turn"]')).length === 0);

	// ── 11: HI and MR ───────────────────────────────────────────────────────
	for (const [lang, word] of [
		['hi', 'शहर के बारे में पूछें'],
		['mr', 'शहराबद्दल विचारा'],
	]) {
		await open(page, { lang });
		const t = await page.evaluate(() => ({ empty: document.querySelector('[data-testid="v3-assistant-empty"] h2')?.textContent ?? '', sug: document.querySelector('[data-suggest="next-hour"]')?.textContent ?? '' }));
		ok(`11. ${lang.toUpperCase()}: the empty state and the suggestions are translated`, t.empty === word && !/What needs me/.test(t.sug), `${t.empty} · ${t.sug.trim()}`);
		await page.click('[data-suggest="next-hour"]');
		await page.waitForSelector('[data-testid="v3-answer"]', { timeout: 15_000 }).catch(() => {});
		await sleep(1000);
		await shot(page, `assistant-1920-${lang}.png`);
	}

	// ── 12: 1366 ────────────────────────────────────────────────────────────
	await open(page, { w: 1366, h: 768 });
	await page.click('[data-suggest="next-hour"]');
	await page.waitForSelector('[data-testid="v3-answer"]', { timeout: 15_000 }).catch(() => {});
	await sleep(1000);
	const s12 = await page.evaluate(() => ({
		ctx: Math.round(document.querySelector('[data-testid="v3-context"]')?.getBoundingClientRect().width ?? 0),
		tops: [...new Set([...document.querySelectorAll('[data-testid="v3-suggestions"] [data-suggest]')].map((b) => Math.round(b.getBoundingClientRect().top)))],
	}));
	ok('12. 1366: the context column is 300 px; the suggestions stay on one row', s12.ctx === 300 && s12.tops.length === 1, JSON.stringify(s12));
	await shot(page, 'assistant-1366-en.png');

	// ── 13: Show on map ─────────────────────────────────────────────────────
	await page.setViewport({ width: 1920, height: 1080 });
	await page.click('[data-testid="v3-proposal"][data-kind="decision"] [data-testid="v3-proposal-map"]');
	await page.waitForFunction(() => location.pathname === '/map', { timeout: 15_000 }).catch(() => {});
	await page.waitForFunction((urn) => window.__GODS_EYE__?.phase === 'ready' && window.__GODS_EYE__?.selection?.urn === urn, { timeout: 120_000 }, VEH).catch(() => {});
	const s13 = await page.evaluate(() => ({ path: location.pathname, sel: window.__GODS_EYE__?.selection?.urn ?? null }));
	ok('13. Show on map opens /map with the object selected on the canvas', s13.path === '/map' && s13.sel === VEH, JSON.stringify(s13));

	// ── 14 ──────────────────────────────────────────────────────────────────
	ok('14. no other non-GET left the browser (only the answered chat POSTs)', writes.length === 0, writes.slice(0, 4).join(', ') || `${chats.length} chat POSTs answered locally`);
	ok('1. zero page errors', errors.length === 0, errors.slice(0, 3).join(' | '));
} finally {
	await browser.close();
}

console.log(failures ? `\nv3-assistant-smoke: ${failures} failure(s)` : '\nv3-assistant-smoke: ALL OK');
process.exit(failures ? 1 : 0);
