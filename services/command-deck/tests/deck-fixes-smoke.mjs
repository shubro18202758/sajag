/**
 * The deck's pre-release audit fixes, in a browser (FIX-H-DECK).
 *
 *   node tests/deck-fixes-smoke.mjs [origin]             # a RUNNING deck (dev deck or preview)
 *   node tests/deck-fixes-smoke.mjs --prod [port]        # spawns `node build` itself (a built deck)
 *
 * Headless Chrome against the REAL pages. Every non-GET API request is
 * aborted; the assistant's chat stream is answered LOCALLY (a fixed turn, or
 * an aborted/delayed answer) — no model is called, nothing is written.
 *
 *   F-01  the omnibar's "ask": "Asking…" until the first token, then "Sent";
 *         a failed stream answers "assistant unreachable" and claims nothing
 *   F-02  a pursuit with no start shows "Not started" (never NOW as its start)
 *   F-03  the corridor page's tab title is a real word, not a key
 *   F-04  /chat and /comms say "Not read here" for the feeds they do not read
 *   F-05  a planned pursuit never puts a LIVE pursuit segment in the strip
 *   F-09  /citizen with no live corridor event says there is none
 *   F-16  the pursuit's inspector title reads in HI
 *   F-20  the omnibar's "ask " template answers "Keep typing", never "No matches"
 *   F-21  the Data popover holds no second "Decision model" row
 *   F-22  Share on / says its outcome (a toast)
 *   F-23  an unknown address answers the deck's error page
 *   F-25  /citizen and /driver tab titles in the reader's language
 *   F-29  at 1366: inbox titles, the map rule chip and the KPI sub lines are
 *         never cut mid-word
 *   FIX-G-BRAIN  the assistant's answer without the lookup dump; the lookups
 *         in the collapsed steps; the grounding removals as ONE plain line
 * --prod only (a production server spawned here, gate-off unless said):
 *   F-07  /design/** answers 404 (server render AND client navigation's data
 *         request) without SAJAG_DESIGN_HARNESS, 200 with SAJAG_DESIGN_HARNESS=1
 *   F-10  gate ON (a throwaway PIN, never the operator's): /chat and /comms
 *         show the sign-in card, nothing else
 *   F-CONN-11  gate ON: anonymous GET /api/v1/health is refused (403)
 *
 * Exit 0 with `ok <name> — <detail>` lines; 1 on any failure.
 */

import { createRequire } from 'node:module';
import { existsSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { HOME, WORKSPACE, workspacePath } from './lib/routes.mjs';
import { randomBytes } from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const LIVE_PORTS = new Set(['5273', '8090', '8091', '8092']);

const PUPPETEER_CANDIDATES = [process.env.PUPPETEER_FROM, path.resolve(DECK, '../../frontend/package.json')].filter(Boolean);
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
if (!puppeteer) throw new Error('puppeteer not found (set PUPPETEER_FROM)');
const executablePath = [process.env.CHROME_PATH, path.join(os.homedir(), '.cache/puppeteer/chrome/linux_arm-153.0.8010.36/chrome-linux-arm64/chrome')].filter(Boolean).find(existsSync);
if (!executablePath) throw new Error('no Chrome binary found (set CHROME_PATH)');
const ARGS = ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader'];

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
 * V3-P6B: the language switch is in the V3 top bar's menu (`v3-header-menu`), not a navbar group: open the menu when it is
 * not open, choose the language, close the menu. Runs in the page the caller names.
 */
async function pickLanguage(page, code) {
	if (!(await page.$('[data-v3="header-menu"]'))) await page.click('[data-v3="top-bar"] [data-testid="v3-header-menu"]');
	await page.waitForSelector(`[data-v3="header-menu"] [data-lang-code="${code}"]`, { timeout: 8000 });
	await page.click(`[data-v3="header-menu"] [data-lang-code="${code}"]`);
	await sleep(400);
	await page.keyboard.press('Escape');
}
const ndjson = (rows) => rows.map((r) => JSON.stringify(r)).join('\n') + '\n';

const PROD = process.argv.includes('--prod');
const argOrigin = process.argv.slice(2).find((a) => /^https?:\/\//.test(a));
const origin = (argOrigin ?? 'http://127.0.0.1:5468').replace(/\/+$/, '');
if (LIVE_PORTS.has(new URL(origin).port)) throw new Error(`refusing a live port: ${origin}`);

/** The chat stream's answer for the next ask: 'abort' | 'delay' | 'turn'. */
let chatMode = 'turn';
const LOOKUP_TURN = ndjson([
	{ type: 'token', data: 'No road segment named Fake Street is in the city road network. ' },
	{ type: 'token', data: 'What the lookups returned: city_query_entities: 0 rows; predict_eta refused: route_length_m not grounded.' },
	{ type: 'done', data: { session_id: 'fix-h-smoke', tiers_used: ['heuristic'], operator_alerts: ['ungrounded_claims_removed: 2 claim(s) no tool reported were removed from the answer'], degraded: false, citations: [] } },
]);

async function wire(page) {
	await page.setRequestInterception(true);
	page.on('request', (r) => {
		const u = new URL(r.url());
		if (r.method() === 'POST' && u.pathname === '/api/convoy/chat/stream') {
			if (chatMode === 'abort') return r.abort('connectionrefused');
			if (chatMode === 'delay') return setTimeout(() => r.respond({ status: 200, contentType: 'application/x-ndjson', body: LOOKUP_TURN }).catch(() => {}), 3500);
			return r.respond({ status: 200, contentType: 'application/x-ndjson', body: LOOKUP_TURN });
		}
		if (['GET', 'HEAD', 'OPTIONS'].includes(r.method())) return r.continue();
		return r.abort();
	});
}

const browser = await puppeteer.launch({ executablePath, headless: 'new', args: ARGS });
let server = null;
try {
	if (PROD) {
		await prodChecks();
	} else {
		await devChecks();
	}
} finally {
	await browser.close().catch(() => {});
	if (server) server.kill('SIGTERM');
}

if (failures) {
	console.error(`deck-fixes-smoke: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('ok   deck-fixes-smoke — all assertions passed');
process.exit(0);

// ─────────────────────────────────────────────────────────────────────────────

async function open(path_, w = 1366, h = 768, cookies = []) {
	const page = await browser.newPage();
	await wire(page);
	await page.setViewport({ width: w, height: h });
	if (cookies.length) await page.setCookie(...cookies.map((c) => ({ ...c, url: origin })));
	await page.goto(origin + path_, { waitUntil: 'networkidle2', timeout: 120000 }).catch(() => null);
	return page;
}

async function devChecks() {
	const ctx = browser.defaultBrowserContext();
	await ctx.overridePermissions(origin, ['clipboard-read', 'clipboard-write', 'clipboard-sanitized-write']).catch(() => {});

	// ── / at 1366 ────────────────────────────────────────────────────────────
	const p = await open(WORKSPACE);
	await p.waitForSelector('[data-template="convoy-command"]:not([data-pending])', { timeout: 60000 }).catch(() => null);
	await sleep(9000);
	ok('F-03: the corridor page\'s tab title is a word, not an i18n key', (await p.title()) === 'Corridor · Sajag', await p.title());

	const board = await p.evaluate(async () => (await (await fetch('/api/v1/events/active')).json()).events ?? []);
	const activePursuits = board.filter((e) => e.event_kind === 'vehicle_pursuit' && e.status === 'active').length;
	const pursuitSegs = await p.$$eval('[data-live-seg="pursuit"]', (els) => els.length);
	ok('F-05: the strip shows a pursuit only for an ACTIVE one (a planned pursuit is not live)', pursuitSegs === activePursuits, `${pursuitSegs} segment(s) · ${activePursuits} active pursuit(s) of ${board.filter((e) => e.event_kind === 'vehicle_pursuit').length} on the board`);

	const rule = await p.evaluate(() => {
		const el = document.querySelector('[data-map="readout"] .rule');
		const txt = el?.querySelector('.rule-text');
		return el ? { mode: el.getAttribute('data-rule'), text: txt?.textContent ?? '', title: el.getAttribute('title'), cut: txt ? txt.scrollWidth > el.clientWidth + 1 : null, sw: el.scrollWidth, cw: el.clientWidth } : null;
	});
	ok('F-29: the map rule chip at 1366 is never cut mid-word (full line, or the short rule with the line as its tooltip)', !!rule && !rule.cut && (rule.mode === 'full' ? /named officer/.test(rule.text) : rule.text === 'Vehicles only' && /named officer/.test(rule.title ?? '')), JSON.stringify(rule));

	const inbox = await p.$$eval('[data-cursor] .ttl', (els) => els.map((e) => ({ text: e.innerText.replace(/\s+/g, ' ').trim(), cut: e.scrollWidth > e.clientWidth + 1 || [...e.querySelectorAll('.t-pre,.t-post')].some((s) => s.scrollWidth > s.clientWidth + 1) })));
	ok('F-29: no Inbox title is cut at 1366 (the verb wraps)', inbox.length > 0 && inbox.every((r) => !r.cut), inbox.map((r) => `${r.text}${r.cut ? ' [CUT]' : ''}`).join(' | '));

	// F-22: Share says its outcome
	await p.click('[data-share]').catch(() => null);
	const toast = await p.waitForFunction(() => [...document.querySelectorAll('[data-ui="toast"],[data-prim="toast"]')].map((t) => t.innerText).join(' | '), { timeout: 5000 }).then((h) => h.jsonValue()).catch(() => '');
	ok('F-22: Share on / says its outcome (a toast: copied, or refused with what to do)', /Link copied|refused the clipboard/.test(toast), toast || 'no toast');

	// F-20 / F-01: the omnibar
	const openOmni = async () => {
		const input = await p.$('[data-testid="palette-input"]');
		if (input) return input;
		await p.click('[data-shell="command-search"]').catch(() => null);
		return p.waitForSelector('[data-testid="palette-input"]', { visible: true, timeout: 10000 }).catch(() => null);
	};
	let pal = await openOmni();
	ok('omnibar opens', !!pal);
	if (pal) {
		await pal.click({ clickCount: 3 });
		await pal.type('ask ', { delay: 30 });
		await sleep(800);
		const tpl = await p.evaluate(() => ({ text: document.querySelector('[role="listbox"], [data-testid="palette"]')?.innerText ?? document.body.innerText.slice(0, 0), none: /No matches/.test(document.body.innerText) }));
		const panel = await p.evaluate(() => [...document.querySelectorAll('[role="option"]')].map((o) => o.innerText.replace(/\s+/g, ' ')).join(' | '));
		ok('F-20: "ask " (the template) shows what to type next, never "No matches"', !tpl.none && /Keep typing/.test(panel), panel.slice(0, 200));

		// F-01 failure: the stream never answers
		chatMode = 'abort';
		await pal.type('where is the convoy', { delay: 15 });
		await p.keyboard.press('Enter');
		const failed = await p.waitForSelector('[data-testid="palette-answer"][data-status="error"]', { timeout: 15000 }).then(() => true).catch(() => false);
		const failState = await p.evaluate(() => ({ answer: document.querySelector('[data-testid="palette-answer"]')?.innerText ?? '', notes: [...document.querySelectorAll('.note')].map((n) => n.innerText) }));
		ok('F-01: a stream that fails answers "could not be reached" and claims nothing was sent', failed && /could not be reached/.test(failState.answer) && !failState.notes.some((n) => /Sent to the assistant/.test(n)), JSON.stringify(failState));

		// F-01 success: "Asking…" until the first token, then "Sent"
		chatMode = 'delay';
		pal = await openOmni();
		await pal.click({ clickCount: 3 });
		await pal.type('ask how is traffic on Strand Road', { delay: 15 });
		await p.keyboard.press('Enter');
		await sleep(1200);
		const waiting = await p.evaluate(() => ({ answer: document.querySelector('[data-testid="palette-answer"]')?.innerText ?? '', status: document.querySelector('[data-testid="palette-answer"]')?.getAttribute('data-status'), notes: [...document.querySelectorAll('.note')].map((n) => n.innerText) }));
		ok('F-01: before the first token the omnibar says "Asking…" and NOT "Sent to the assistant"', waiting.status === 'streaming' && /Asking/.test(waiting.answer) && !waiting.notes.some((n) => /Sent to the assistant/.test(n)), JSON.stringify(waiting));
		await p.waitForSelector('[data-testid="palette-answer"][data-status="done"]', { timeout: 15000 }).catch(() => null);
		const done = await p.evaluate(() => ({ notes: [...document.querySelectorAll('.note')].map((n) => n.innerText) }));
		ok('F-01: once the answer arrived, "Sent to the assistant" is said', done.notes.some((n) => /Sent to the assistant/.test(n)), JSON.stringify(done));
		await p.keyboard.press('Escape');
		chatMode = 'turn';
	}

	// F-02 / F-16: the planned pursuit's inspector (no start → "Not started"; HI title)
	const pursuit = board.find((e) => e.event_kind === 'vehicle_pursuit' && !e.actual_start && !e.planned_start);
	if (pursuit) {
		const q = await open(workspacePath(new URLSearchParams({ sel: `event:${pursuit.event_id}` }).toString()), 1440, 900);
		await q.waitForSelector('[data-testid="entity-dossier"]', { timeout: 60000 }).catch(() => null);
		await sleep(8000);
		const insp = await q.evaluate(() => document.querySelector('[data-testid="entity-dossier"]')?.innerText ?? '');
		const now = await q.evaluate(() => new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: false }).format(Date.now()));
		ok('F-02: a pursuit with no start reads "Not started" — never now as its start', /Not started/.test(insp) && !new RegExp(`Start\\s*\\n?\\s*${now}`).test(insp), insp.replace(/\s+/g, ' ').slice(0, 220));
		await pickLanguage(q, 'hi');
		await sleep(2500);
		const hi = await q.evaluate(() => document.querySelector('[data-testid="entity-dossier"]')?.innerText ?? '');
		ok('F-16: in HI the pursuit\'s inspector never reads "Pursuit of"', !/Pursuit of/.test(hi) && /पीछा/.test(hi), hi.replace(/\s+/g, ' ').slice(0, 160));
		await pickLanguage(q, 'en');
		await sleep(800);
		await q.close();
	} else ok('F-02: (no un-started pursuit on the sandbox board — covered by tests/deck-fixes.unit.mjs)', true);
	await p.close();

	// ── /ops at 1366: the KPI sub lines; the AMA shadow row ─────────────────
	const o = await open('/ops');
	await o.waitForSelector('[data-wall="metric-strip"]', { timeout: 60000 }).catch(() => null);
	await sleep(9000);
	const subs = await o.$$eval('[data-wall="metric-strip"] [data-metric]', (cells) =>
		cells.map((c) => {
			const sub = [...c.querySelectorAll('span')].filter((s) => s.children.length === 0 && s.textContent.trim()).at(-1);
			const box = sub?.parentElement;
			return { key: c.getAttribute('data-metric'), text: sub?.textContent ?? '', cut: !!box && box.scrollWidth > box.clientWidth + 1 };
		}),
	);
	ok('F-29: no KPI sub line on /ops is cut at 1366', subs.length === 8 && subs.every((s) => !s.cut), subs.map((s) => `${s.key}: ${s.text}${s.cut ? ' [CUT]' : ''}`).join(' | '));
	const ama = await o.evaluate(() => {
		const sec = document.querySelector('[data-wall="adaptation"]');
		const row = [...(sec?.querySelectorAll('tr') ?? [])].find((r) => /Shadow evaluation/.test(r.innerText));
		return row ? row.innerText.replace(/\s+/g, ' ') : null;
	});
	const newest = await o.evaluate(async () => ((await (await fetch('/api/v1/adaptive/overrides?limit=1')).json()).overrides ?? [])[0] ?? null);
	ok(
		'F-12: the shadow-evaluation row says "Not required" for a baseline set (never "Unavailable"), with its publish time labelled',
		!!ama && (newest?.shadow_eval_detail === 'shadow_eval_not_required' ? /Not required/.test(ama) && !/Unavailable/.test(ama) && /published/.test(ama) : true),
		`${ama} · newest ${newest?.shadow_eval}/${newest?.shadow_eval_detail}`,
	);
	await o.close();

	// ── /chat: the Data popover; the assistant's answer ─────────────────────
	for (const route of ['/chat', '/analyst']) {
		const c = await open(route, 1440, 900);
		await sleep(7000);
		await c.click('[data-testid="brain-posture"]').catch(() => null);
		const rows = await c.waitForFunction(() => [...document.querySelectorAll('[data-shell="data-panel"] tr[data-feed]')].map((r) => `${r.getAttribute('data-feed')}=${r.getAttribute('data-status')}:${r.innerText.replace(/\s+/g, ' ').trim()}`), { timeout: 8000 }).then((h) => h.jsonValue()).catch(() => []);
		const byName = (n) => rows.find((r) => r.startsWith(`${n}=`)) ?? '';
		if (route === '/chat') ok(`F-04: ${route} says "Not read here" for the registry, the city feed and the cameras (never "waiting · Degraded")`, ['City picture', 'City feed', 'ANPR cameras'].every((n) => /=none:/.test(byName(n)) && /Not read here/.test(byName(n)) && !/Degraded|waiting/i.test(byName(n))), rows.join(' | '));
		ok(`F-21: ${route}'s Data popover has no second "Decision model" feed row`, rows.length > 0 && !rows.some((r) => r.startsWith('Decision model=')), rows.map((r) => r.split('=')[0]).join(', '));
		await c.keyboard.press('Escape');
		if (route === '/chat') {
			const input = await c.$('[data-testid="chat-input"], .panel.page textarea');
			if (input) {
				await input.type('how do I get to Fake Street', { delay: 10 });
				await c.keyboard.press('Enter');
				await c.waitForSelector('[data-testid="chat-answer"]', { timeout: 20000 }).catch(() => null);
				await sleep(1500);
				const turn = await c.evaluate(() => ({
					answer: [...document.querySelectorAll('[data-testid="chat-answer"]')].at(-1)?.innerText ?? '',
					lookups: !!document.querySelector('[data-testid="chat-lookups"]'),
					lookupsHidden: document.querySelector('[data-testid="chat-lookups"]')?.hidden ?? null,
					removed: document.querySelector('[data-testid="chat-grounding-removed"]')?.innerText ?? '',
					alerts: [...document.querySelectorAll('.alerts li')].map((l) => l.innerText),
				}));
				ok('FIX-G-BRAIN: the answer is the sentence before the lookup dump (no tool names in it)', /^No road segment named Fake Street/.test(turn.answer) && !/city_query_entities|predict_eta|What the lookups returned/.test(turn.answer), JSON.stringify(turn));
				ok('FIX-G-BRAIN: the lookup detail sits in the collapsed steps; the removals are one plain line, not a raw alert', turn.lookups && turn.lookupsHidden === true && turn.removed === '2 statements removed: not in the lookups' && !turn.alerts.some((a) => /ungrounded/.test(a)), JSON.stringify(turn));
			} else ok('FIX-G-BRAIN: the /chat input was found', false);
		}
		await c.close();
	}

	// ── /citizen and /driver ────────────────────────────────────────────────
	const cz = await open('/citizen', 1280, 900, [{ name: 'sajag_lang', value: 'hi' }]);
	await sleep(6000);
	const czState = await cz.evaluate(() => ({ title: document.title, live: Number(document.querySelector('[data-testid="emergency-body"]')?.getAttribute('data-live-events') ?? -1), body: document.querySelector('[data-testid="emergency-body"]')?.innerText ?? '' }));
	ok('F-25: /citizen\'s tab title is in the reader\'s language (HI)', /कॉरिडोर/.test(czState.title) && !/Corridor Alerts/.test(czState.title), czState.title);
	ok('F-09: /citizen\'s emergency line never promises "the active event" when there is none; never "seconds"', czState.live >= 0 && !/सेकंड/.test(czState.body) && (czState.live > 0 || /सक्रिय नहीं/.test(czState.body)), JSON.stringify(czState));
	await cz.close();
	// a fresh reader: no language chosen (the /citizen visit above set HI)
	await (await browser.pages())[0]?.deleteCookie?.({ name: 'sajag_lang', url: origin }).catch(() => {});
	const dr = await open('/driver', 600, 900);
	await dr.deleteCookie({ name: 'sajag_lang', url: origin });
	await dr.reload({ waitUntil: 'networkidle2' }).catch(() => null);
	await sleep(6000);
	const drState = await dr.evaluate(() => ({ title: document.title, mode: document.querySelector('[data-screen="driver"]')?.getAttribute('data-mode'), sub: document.querySelector('[data-testid="driver-sub"]')?.innerText ?? null, started: document.querySelector('[data-testid="golden-hour"]')?.getAttribute('data-started') }));
	ok('F-25: /driver\'s tab title is English (the default with no language chosen)', /Green corridor/.test(drState.title), drState.title);
	ok('F-08/F-09: /driver: the request clock is idle before a request; the officer-queue line only in the live flow, never "seconds"', drState.started === '0' && (drState.mode === 'scripted' ? drState.sub === null : !/સેકંડ|seconds/.test(drState.sub ?? '')), JSON.stringify(drState));
	await dr.close();

	// ── F-23: an unknown address ────────────────────────────────────────────
	const nf = await open('/no-such-page');
	await nf.deleteCookie({ name: 'sajag_lang', url: origin });
	await nf.reload({ waitUntil: 'networkidle2' }).catch(() => null);
	await sleep(1500);
	const nfState = await nf.evaluate(() => ({ title: document.title, page: !!document.querySelector('[data-testid="error-page"][data-status="404"]'), home: !!document.querySelector('[data-testid="error-page"] a[href="/"]') }));
	ok('F-23: an unknown address answers the deck\'s error page (titled, with a way back)', nfState.page && nfState.home && nfState.title === 'Page not found · Sajag', JSON.stringify(nfState));
	await nf.close();
}

/** A production server of build/ on `port`, with `env` added (never the operator's secrets). */
async function startProd(port, env) {
	const child = spawn(process.execPath, ['build'], {
		cwd: DECK,
		env: { ...process.env, SAJAG_OPERATOR_PIN: '', SAJAG_SESSION_SECRET: '', SAJAG_CESIUM_ION_TOKEN: '', PORT: String(port), HOST: '127.0.0.1', ...env },
		stdio: 'ignore',
	});
	for (let i = 0; i < 60; i++) {
		await sleep(500);
		const up = await fetch(`http://127.0.0.1:${port}/citizen`).then((r) => r.status).catch(() => 0);
		if (up) return child;
	}
	child.kill('SIGTERM');
	throw new Error(`node build did not answer on :${port}`);
}

async function prodChecks() {
	if (!existsSync(path.join(DECK, 'build', 'index.js'))) throw new Error('no build/ — `sem.sh deck-build 2 npm run build:cpu` first');
	const port = Number(process.argv.slice(2).find((a) => /^\d{4,5}$/.test(a)) ?? 5481);
	if (LIVE_PORTS.has(String(port))) throw new Error('refusing a live port');
	const base = `http://127.0.0.1:${port}`;
	const get = (p, init) => fetch(base + p, init).then(async (r) => ({ status: r.status, text: await r.text() }));

	// F-07: without the harness flag
	server = await startProd(port, { SAJAG_DESIGN_HARNESS: '' });
	const designs = ['/design', '/design/workspace', '/design/views', '/design/decisions'];
	const off = await Promise.all(designs.map((d) => get(d)));
	const offData = await get('/design/workspace/__data.json');
	// a client navigation's data request answers SvelteKit's error node (the client then renders the 404 page)
	const dataErr = (() => {
		try {
			return (JSON.parse(offData.text).nodes ?? []).some((n) => n?.type === 'error' && n.status === 404);
		} catch {
			return offData.status === 404;
		}
	})();
	ok('F-07: production without SAJAG_DESIGN_HARNESS answers 404 on /design/** (page and client-navigation data)', off.every((r) => r.status === 404) && dataErr, off.map((r, i) => `${designs[i]} ${r.status}`).join(' · ') + ` · __data.json ${offData.text.slice(0, 120)}`);
	ok('F-23: the production 404 is the deck\'s error page', /data-testid="error-page"/.test(off[1].text) && /Page not found · Sajag/.test(off[1].text));
	ok('F-07: the operator pages still serve', (await get(WORKSPACE)).status === 200 && (await get(HOME)).status === 200 && (await get('/ops')).status === 200);
	server.kill('SIGTERM');
	await sleep(1500);

	// F-07: with the flag (the smokes' and verify_all's previews)
	server = await startProd(port, { SAJAG_DESIGN_HARNESS: '1' });
	const on = await Promise.all(designs.map((d) => get(d)));
	ok('F-07: SAJAG_DESIGN_HARNESS=1 serves the harness pages (the smokes drive them)', on.every((r) => r.status === 200), on.map((r, i) => `${designs[i]} ${r.status}`).join(' · '));
	server.kill('SIGTERM');
	await sleep(1500);

	// F-10 / F-CONN-11: the gate ON with a throwaway PIN (never the operator's)
	server = await startProd(port, { SAJAG_OPERATOR_PIN: randomBytes(6).toString('hex'), SAJAG_SESSION_SECRET: randomBytes(32).toString('hex') });
	ok('F-CONN-11: gate on — anonymous GET /api/v1/health is refused (no such oracle route on the allow-list)', (await get('/api/v1/health')).status === 403);
	for (const [route, testid] of [['/chat', 'chat-signin-required'], ['/comms', 'comms-signin-required']]) {
		const page = await browser.newPage();
		await page.setRequestInterception(true);
		page.on('request', (r) => (['GET', 'HEAD', 'OPTIONS'].includes(r.method()) ? r.continue() : r.abort()));
		await page.setViewport({ width: 1440, height: 900 });
		await page.goto(base + route, { waitUntil: 'networkidle2', timeout: 60000 }).catch(() => null);
		const shown = await page.waitForSelector(`[data-testid="${testid}"]`, { timeout: 20000 }).then(() => true).catch(() => false);
		const rest = await page.evaluate(() => ({ chat: !!document.querySelector('.chat-page'), comms: !!document.querySelector('[data-screen="comms"]') }));
		ok(`F-10: gate on, nobody signed in — ${route} shows the sign-in card and no panel of refused reads`, shown && !rest.chat && !rest.comms, JSON.stringify({ shown, ...rest }));
		await page.close();
	}
	server.kill('SIGTERM');
	server = null;
}
