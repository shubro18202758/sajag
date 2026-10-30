/**
 * Assistant behavioural smoke (FIX-E-ASSIST round 2 — the audit E re-round).
 *
 *   node tests/assistant-smoke.mjs [origin]      # default http://127.0.0.1:5425
 *
 * Headless Chrome against a RUNNING dev deck (dev_deck.sh pattern, int3cl),
 * like tests/design-smoke.mjs. Every non-GET API request is aborted — the
 * ONE exception is POST /api/convoy/chat/stream, which is answered LOCALLY
 * with a fixed mocked turn (labelled on screen: "Mock answer"), so no model
 * is ever called and nothing is written anywhere. Asserts on the REAL pages
 * (the unit suite's source checks became behaviour here — the audit E
 * must-fix 2): what a mutant changes in the WIRING must fail a measured,
 * computed or clicked assertion, not a regex.
 *
 *   1.  /chat + /comms keep the interrupts: the live strip renders content
 *       and the operator band's inbox count equals the canvas pages' (the same
 *       decision units — mutants that feed [] or never read them fail)
 *   2.  the omnibar finds "mh47" on /chat AND /comms (the pages start the
 *       city registry; a commented-out start() leaves the omnibar empty)
 *   3.  with "Show steps" OFF every .step computes display:none; ON they
 *       show; OFF again they hide (a later more-specific flex rule cannot
 *       re-show them) — on /chat?sample=1 and on the / dock
 *   4.  chat-tiers and chat-session exist inside CLOSED Details (sample +
 *       the mocked dock turn)
 *   5.  step-duration and cited-id contrast ≥ 4.5:1 computed WITH opacity
 *   6.  /chat layout: the header's title left edge equals the conversation
 *       column's at 1366 AND 1440; the panel's grid is centred at 1440
 *   7.  the /chat context aside shows the scoped vehicle's masked mark,
 *       never its uuid, and no second "Scoped to this view"
 *   8.  the dock on / at 1440: padding > 0, suggestion chips wrap from the
 *       left, no dock descendant (toggles, Send) clips past the dock edge
 *   9.  a citation click on / STAYS on / and fills the Inspector (the wall
 *       canvas never sees a queued selection request); a directive click
 *       stays too (preventDefault); the dock citation tooltip says
 *       "Select on the map"; a label-shaped cited urn still renders an
 *       ObjectTag
 *   10. the dock scope line is one quiet line (no frame), its event state
 *       word translated
 *   11. the HI and MR scope suffix is not the English string
 *   12. /comms at 1920: the desk is centred on its measure, the dispatch
 *       threads take the remaining height (their section reaches the desk's
 *       bottom, no stranded section ~700 px down, no empty half); at 1366
 *       the review badge is above the fold; the operator-only arm keeps the
 *       three [data-lang][data-withheld] nodes with language names only —
 *       no dash, no dead Copy, the notice said once; a public event's
 *       "Drafted — not delivered" appears once
 *   13. an omnibar pick on /comms opens the object on / (the desk has no
 *       inspector of its own)
 *
 * Shots (only when ASSISTANT_SMOKE_SHOTS is set — a directory; never
 * tests/artifacts/screens, which is tracked evidence of record).
 * Exit 0 with `ok <name> — <detail>` lines; exit 1 on any failure.
 */

import { createRequire } from 'node:module';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { puppeteerCookies, signIn, signOut } from './lib/operator-session.mjs';
import { WORKSPACE } from './lib/routes.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const SHOTS = process.env.ASSISTANT_SMOKE_SHOTS ? path.resolve(process.env.ASSISTANT_SMOKE_SHOTS) : null;
if (SHOTS) mkdirSync(SHOTS, { recursive: true });

// Puppeteer + cached Chrome live in the repo's frontend/ tree (design-smoke pattern).
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

// ── the mocked turn (no model called; the note rides in the answer) ────────
const VEH = 'vehicle:1b94e9d2-7e11-4174-a735-7dd3be3189cf';
const CAM = 'camera:EM-CAM-03';
const LABEL_URN = 'vehicle:MH47EM4444'; // label-shaped: parseUrn rejects it, the kind prefix stands
const ndjson = (rows) => rows.map((r) => JSON.stringify(r)).join('\n') + '\n';
const STREAM = ndjson([
	{ type: 'tool_call', data: { id: 'c1', name: 'get_entity_dossier', args: { urn: VEH } } },
	{ type: 'tool_result', data: { id: 'c1', name: 'get_entity_dossier', ok: true, summary: 'dossier read (mocked turn)' } },
	{ type: 'token', data: 'Mock answer: the watchlisted vehicle was last read on EM-CAM-03. No model was called.' },
	{ type: 'directive', data: { id: 'dir-smoke-1', verb: 'canvas_fly_to', args: { urn: CAM }, label: 'fly to EM-CAM-03', provenance: { session_id: 'sess-smoke', tier: 'decider' } } },
	{
		type: 'done',
		data: {
			session_id: 'sess-smoke',
			tiers_used: ['heuristic:mock-local'],
			operator_alerts: [],
			degraded: false,
			citations: [
				{ urn: VEH, label: 'MH47EM•••1' },
				{ urn: LABEL_URN, label: 'MH47EM•••1' },
				{ urn: CAM, label: 'EM-CAM-03' },
			],
		},
	},
]);

/** WCAG contrast of text over the first non-transparent ancestor background, opacity folded in. */
const COLOR_HELPERS = `
	window.__rgba = (c) => { const m = /rgba?\\(([^)]+)\\)/.exec(c); if (!m) return null;
		const p = m[1].split(',').map((s) => parseFloat(s)); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
	window.__over = (fg, bg) => { const a = fg.a + bg.a * (1 - fg.a); if (!a) return { r: 0, g: 0, b: 0, a: 0 };
		return { r: (fg.r * fg.a + bg.r * bg.a * (1 - fg.a)) / a, g: (fg.g * fg.a + bg.g * bg.a * (1 - fg.a)) / a, b: (fg.b * fg.a + bg.b * bg.a * (1 - fg.a)) / a, a }; };
	window.__lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
		return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
	window.__cr = (fg, bg) => { const l1 = window.__lum(fg), l2 = window.__lum(bg);
		return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05); };
	window.__effBg = (el) => { for (let a = el; a; a = a.parentElement) {
		const c = window.__rgba(getComputedStyle(a).backgroundColor); if (c && c.a > 0.85) return c; } return { r: 18, g: 21, b: 26, a: 1 }; };
	window.__contrastOf = (el) => { const cs = getComputedStyle(el); const op = parseFloat(cs.opacity || '1');
		const fg = window.__rgba(cs.color); const bg = window.__effBg(el);
		return window.__cr(window.__over({ ...fg, a: fg.a * op }, bg), bg); };
`;

const browser = await puppeteer.launch({ executablePath, headless: 'new', args: SWIFTSHADER_ARGS });
let session = null;

try {
	const origin = (process.argv[2] ?? 'http://127.0.0.1:5425').replace(/\/+$/, '');
	session = await signIn(origin, 'Assistant smoke (automated check)');
	ok('deck-origin up', true, origin);

	// One page, interception always on: the chat stream is answered locally,
	// every other write is blocked and logged. A crashed SwiftShader renderer
	// (Cesium is heavy) gets ONE fresh page. `stubBoard`, when set, answers
	// GET /api/v1/events/active with an extra PUBLIC procession event — the
	// N18 draft-log check needs a public kind so the desk's Generate is
	// enabled (an operator-only board leaves the log empty by design); the
	// stub is a READ (the real board plus one synthetic row), never a write.
	const errors = [];
	let p = null;
	let stubBoard = null;
	const wirePage = async () => {
		p = await browser.newPage();
		p.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
		await p.setRequestInterception(true);
		p.on('request', (r) => {
			const u = new URL(r.url());
			if (r.method() === 'POST' && u.pathname === '/api/convoy/chat/stream') {
				return r.respond({ status: 200, contentType: 'application/x-ndjson', body: STREAM });
			}
			if (r.method() === 'GET' && u.pathname === '/api/v1/events/active' && stubBoard) {
				return r.respond({ status: 200, contentType: 'application/json', body: JSON.stringify(stubBoard) });
			}
			if (['GET', 'HEAD', 'OPTIONS'].includes(r.method())) return r.continue();
			console.log(`BLOCKED-WRITE ${r.method()} ${u.pathname}`);
			return r.abort();
		});
	};
	await wirePage();
	const shot = (name) => (SHOTS ? p.screenshot({ path: path.join(SHOTS, name) }).then(() => name) : Promise.resolve('off'));
	let loads = 0;
	/** True while the page is still the one gotoPage loaded (no full reload since). */
	const samePage = () => p.evaluate((n) => window.__assistantSmokeLoad === n, loads).catch(() => false);
	/**
	 * Open the omnibar the way an officer does — the top bar's search (or
	 * Ctrl+K when the page has none) — and wait for its input: on
	 * the canvas pages the omnibar's module loads on first use (FIX-E-PERF2),
	 * so a fixed pause after the click raced the load. Returns the input or null.
	 */
	const openOmnibar = async () => {
		const open = await p.$('[data-testid="palette-input"]');
		if (open) return open;
		const search = await p.$('[data-shell="command-search"]');
		if (search) await search.click();
		else await p.keyboard.down('Control').then(() => p.keyboard.press('k')).finally(() => p.keyboard.up('Control'));
		return p.waitForSelector('[data-testid="palette-input"]', { visible: true, timeout: 10000 }).catch(() => null);
	};
	const gotoPage = async (url, w, h, waitSel) => {
		for (let attempt = 0; attempt < 2; attempt++) {
			try {
				await p.setViewport({ width: w, height: h });
				if (session.gate) await p.setCookie(...puppeteerCookies(session));
				await p.goto(origin + url, { waitUntil: 'networkidle2', timeout: 120000 });
				await p.evaluate(COLOR_HELPERS);
				// the load sentinel: a full page reload (a dev server's HMR reload when
				// its tree's generated files change) drops it, and a check that lost
				// its page says so instead of reading a fresh page as a product fault
				await p.evaluate((n) => (window.__assistantSmokeLoad = n), ++loads);
				if (waitSel) await p.waitForSelector(waitSel, { timeout: 30000 }).catch(() => null);
				await sleep(9000); // the board, the registry and the live strip settle
				return;
			} catch (e) {
				if (attempt === 1) throw e;
				console.log(`note — loading ${url} failed (${String(e).split('\n')[0].slice(0, 90)}); retrying on a fresh page`);
				try {
					await p.close();
				} catch {
					// already gone
				}
				await wirePage();
			}
		}
	};

	// ── the interrupts, on both canvas-less pages (mutants 2a 2b 2c) ───────
	const readBar = () =>
		p.evaluate(() => ({
			strip: !!document.querySelector('[data-testid="live-strip"]'),
			stripText: document.querySelector('[data-testid="live-strip"]')?.innerText.replace(/\s+/g, ' ').slice(0, 120) ?? null,
			pursuit: !!document.querySelector('[data-testid="live-strip"] [data-live-seg="pursuit"]'),
			// V3-P6B: the count is the operator band's Inbox chip, else — a V3 page without that band (/comms) — the rail's Decide badge
			// (the same commandBar.inboxCount), else 0 when the rail is there and shows no badge
			inbox: Number(document.querySelector('[data-inbox-intent]')?.getAttribute('data-count') ?? document.querySelector('[data-testid="v3-decide-badge"]')?.getAttribute('data-count') ?? (document.querySelector('[data-v3="rail"]') ? 0 : -1)),
		}));
	// F-05 (FIX-H-DECK): only an ACTIVE pursuit is live. The sandbox's pursuit may be planned (it
	// was shown live before the fix): the board is stubbed READ-ONLY with that pursuit active, so
	// the strip has something real to carry (the real rows, one status word changed; nothing written).
	const boardNow = await fetch(`${origin}/api/v1/events/active`).then((r) => r.json()).catch(() => ({ events: [] }));
	const boardRows = Array.isArray(boardNow) ? boardNow : (boardNow.events ?? []);
	const strippedPursuit = boardRows.find((e) => e.event_kind === 'vehicle_pursuit') ?? null;
	stubBoard = strippedPursuit ? { events: boardRows.map((e) => (e === strippedPursuit ? { ...e, status: 'active' } : e)) } : null;
	console.log(`note — interrupts: board stubbed read-only with ${strippedPursuit ? 'its pursuit ACTIVE' : 'no pursuit (none on the board)'}`);
	await gotoPage('/ops', 1440, 900, '[data-screen]');
	const opsBar = await readBar();
	ok('canvas reference: /ops live strip renders content', opsBar.strip && (opsBar.pursuit || /pursuit|Pursuit|heading/.test(opsBar.stripText ?? '')), JSON.stringify(opsBar));

	await gotoPage('/chat', 1440, 900, '[data-screen="chat"]');
	const chatBar = await readBar();
	ok(
		'/chat keeps the live strip (content, not null)',
		chatBar.strip && !!chatBar.stripText && chatBar.pursuit === opsBar.pursuit,
		JSON.stringify({ chat: chatBar.stripText, ops: opsBar.stripText }),
	);
	ok(
		'/chat inbox count equals the canvas pages\' (the same decision units)',
		chatBar.inbox === opsBar.inbox && (opsBar.inbox === 0 || chatBar.inbox > 0),
		`/chat ${chatBar.inbox} vs /ops ${opsBar.inbox}`,
	);
	// F-06: /chat has no map — the pursuit segment opens the vehicle on the workspace
	if (chatBar.pursuit && strippedPursuit) {
		await p.click('[data-testid="live-strip"] [data-live-seg="pursuit"]');
		await p.waitForFunction((w) => location.pathname === w, { timeout: 15000 }, WORKSPACE).catch(() => null);
		const landed = await p.evaluate(() => ({ path: location.pathname, hash: decodeURIComponent(location.hash) }));
		const vid = strippedPursuit.metadata?.vehicle_id;
		ok('F-06: on /chat the pursuit segment opens the pursued vehicle on the workspace', landed.path === WORKSPACE && (vid ? landed.hash.includes(`sel=vehicle:${vid}`) : /sel=(vehicle|event):/.test(landed.hash)), JSON.stringify(landed));
	}
	stubBoard = null;

	// ── the omnibar reads a live world on /chat (mutant 3a) ────────────────
	const omniFind = async (q) => {
		await p.evaluate(() => (document.activeElement instanceof HTMLElement ? document.activeElement.blur() : null));
		await p.keyboard.press('Escape');
		const pal = await openOmnibar();
		if (!pal) return { rows: [], note: 'palette never opened (navbar search / Ctrl+K)' };
		await pal.click({ clickCount: 3 });
		await pal.type(q, { delay: 25 });
		await sleep(2500);
		const rows = await p.evaluate(() =>
			[...document.querySelectorAll('[role="option"][data-urn]')].map((r) => ({
				urn: r.getAttribute('data-urn'),
				kind: r.getAttribute('data-kind'),
				text: r.innerText.replace(/\s+/g, ' ').slice(0, 60),
			})),
		);
		await p.keyboard.press('Escape');
		await sleep(300);
		return { rows, note: `${rows.length} rows` };
	};
	const omniChat = await omniFind('mh47');
	ok(
		'/chat omnibar finds mh47 (the vehicle, from the live registry)',
		omniChat.rows.some((r) => r.kind === 'vehicle' && /MH47EM•••1/.test(r.text)),
		JSON.stringify(omniChat.rows.slice(0, 3)),
	);

	// ── /chat sample: steps collapse, tiers/session in closed Details, ──────
	await gotoPage('/chat?sample=1', 1366, 768, '[data-testid="chat-stream"]');
	const closedDetails = () =>
		p.evaluate(() =>
			[...document.querySelectorAll('details.details')]
				.filter((d) => !d.open)
				.map((d) => ({ tiers: !!d.querySelector('[data-testid="chat-tiers"]'), session: !!d.querySelector('[data-testid="chat-session"]') })),
		);
	const stepCards = () =>
		p.evaluate(() => [...document.querySelectorAll('.step[data-testid="chat-tool-card"]')].map((e) => getComputedStyle(e).display));
	const toggleSteps = async () => {
		const sws = await p.$$('[role="switch"]');
		for (const s of sws) {
			const lbl = await s.evaluate((e) => (e.closest('label')?.innerText ?? e.getAttribute('aria-label') ?? '') + '');
			if (/Show steps/i.test(lbl)) {
				await s.click();
				return true;
			}
		}
		return false;
	};
	const off1 = await stepCards();
	ok('/chat steps OFF: every .step computes display none', off1.length >= 3 && off1.every((d) => d === 'none'), JSON.stringify(off1));
	const closed1 = await closedDetails();
	ok(
		'/chat sample: chat-tiers and chat-session live inside CLOSED Details',
		closed1.length >= 1 && closed1.some((d) => d.tiers && d.session),
		JSON.stringify(closed1),
	);
	const toggled = await toggleSteps();
	const on = await stepCards();
	ok('/chat steps ON: the rows show', toggled && on.length >= 3 && on.every((d) => d !== 'none'), `toggled=${toggled} ${JSON.stringify(on)}`);
	const durCr = await p.evaluate(() => {
		const el = document.querySelector('.step-dur');
		return el ? window.__contrastOf(el) : null;
	});
	ok(
		'/chat step-duration contrast ≥ 4.5:1 computed WITH opacity',
		durCr !== null && durCr >= 4.5,
		durCr == null ? 'no .step-dur' : `${durCr.toFixed(2)}:1`,
	);
	await toggleSteps();
	const off2 = await stepCards();
	ok('/chat steps OFF again: the rows hide', off2.every((d) => d === 'none'), JSON.stringify(off2));

	// ── /chat at 1366: the header aligns to the single column (mutant 6d) ──
	const headAlign = await p.evaluate(() => {
		const h1 = document.querySelector('.chat-page .head h1');
		const convo = document.querySelector('.panel.page .convo');
		return { title: Math.round(h1.getBoundingClientRect().left), convo: Math.round(convo.getBoundingClientRect().left) };
	});
	ok('/chat at 1366: the title sits at the conversation\'s left edge', Math.abs(headAlign.title - headAlign.convo) <= 2, JSON.stringify(headAlign));
	if (SHOTS) await shot('assistant-smoke-chat-1366.png');

	// ── /chat at 1440: one centred grid, title on the conversation column ──
	await gotoPage('/chat?sample=1', 1440, 900, '[data-testid="chat-stream"]');
	const grid = await p.evaluate(() => {
		const h1 = document.querySelector('.chat-page .head h1');
		const convo = document.querySelector('.panel.page .convo');
		const aside = document.querySelector('.panel.page .aside');
		const cols = getComputedStyle(document.querySelector('.panel.page .cols'));
		const gap = parseFloat(cols.columnGap || cols.gap || '0');
		const cw = convo.getBoundingClientRect();
		const r = { title: Math.round(h1.getBoundingClientRect().left), convo: Math.round(cw.left), convoRight: Math.round(cw.right), gap, vw: innerWidth };
		r.asideLeft = aside ? Math.round(aside.getBoundingClientRect().left) : null;
		r.gridW = Math.round(r.convoRight - r.convo + gap + (aside ? aside.getBoundingClientRect().width : 0));
		// V3-P6B: the page sits beside the V3 rail, so "centred" is centred in the page's own frame (the area right of the
		// rail), not in the viewport: the pair's left edge is the frame's left plus half of what the pair leaves over
		const frame = document.querySelector('.deck-main')?.getBoundingClientRect() ?? { left: 0, width: r.vw };
		r.frameLeft = Math.round(frame.left);
		r.wantLeft = Math.round(frame.left + (frame.width - (760 + 360 + gap)) / 2);
		return r;
	});
	ok('/chat at 1440: the title sits at the conversation\'s left edge', Math.abs(grid.title - grid.convo) <= 2, JSON.stringify(grid));
	ok(
		'/chat at 1440: the 760+360 pair is centred',
		Math.abs(grid.convo - grid.wantLeft) <= 24,
		`convo left ${grid.convo}, centred in the page frame (left ${grid.frameLeft}) would be ${grid.wantLeft}`,
	);
	// an omnibar pick scopes the panel to the vehicle (a human pick), so the
	// context aside and the scope line name it
	const omniPick = async (q) => {
		await p.evaluate(() => (document.activeElement instanceof HTMLElement ? document.activeElement.blur() : null));
		const pal = await openOmnibar();
		if (!pal) return false;
		await pal.click({ clickCount: 3 });
		await pal.type(q, { delay: 25 });
		await sleep(2500);
		const veh = await p.$('[role="option"][data-kind="vehicle"]');
		if (!veh) {
			await p.keyboard.press('Escape');
			return false;
		}
		await veh.click();
		await sleep(1500);
		await p.keyboard.press('Escape');
		await sleep(300);
		return true;
	};
	const picked = await omniPick('mh47');
	ok('/chat: an omnibar pick scopes the panel to the vehicle', picked, 'vehicle row clicked');
	// the aside names the scoped vehicle by its masked mark, not its uuid;
	// no second "Scoped to this view" under it (audit E, S3)
	const asideScope = await p.evaluate(() => {
		const aside = document.querySelector('.panel.page .aside');
		return {
			text: aside?.innerText.replace(/\s+/g, ' ').slice(0, 200) ?? null,
			uuid: /1b94e9d2-7e11/.test(aside?.innerText ?? ''),
			note: (aside?.innerText ?? '').includes('Scoped to this view'),
		};
	});
	ok(
		'/chat context aside: the scoped vehicle reads as its masked mark (never the uuid), and the scope is stated once',
		/MH47EM•••1/.test(asideScope.text ?? '') && !asideScope.uuid && !asideScope.note,
		JSON.stringify(asideScope),
	);
	const pageCiteCr = await p.evaluate(() => {
		const el = [...document.querySelectorAll('.panel.page .cite')].find((c) => c.querySelector('[data-urn]')?.querySelector('*'));
		if (!el) return null;
		const inner = [...el.querySelectorAll('*')].find((x) => [...x.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()));
		return inner ? window.__contrastOf(inner) : null;
	});
	ok('/chat cited-id contrast ≥ 4.5:1 computed', pageCiteCr !== null && pageCiteCr >= 4.5, pageCiteCr == null ? 'no cited tag' : `${pageCiteCr.toFixed(2)}:1`);
	// the suggestion chips read at the panel's text size (12 px), not as headings
	const chipPx = await p.evaluate(() => {
		const el = document.querySelector('.suggest [data-suggest]');
		return el ? parseFloat(getComputedStyle(el).fontSize) : null;
	});
	ok('/chat suggestion chips render at the panel text size (12 px)', chipPx !== null && chipPx <= 12.5, chipPx == null ? 'no chip' : `${chipPx}px`);

	// ── HI / MR: the scope suffix is not the English string (mutant 7d) ────
	for (const code of ['hi', 'mr']) {
		await pickLanguage(p, code);
		await sleep(700);
		const scope = await p.evaluate(() => ({
			words: [...document.querySelectorAll('[data-testid="chat-context"] .scope-word')].map((w) => w.textContent.trim()),
			line: document.querySelector('[data-testid="chat-context"]')?.innerText.replace(/\s+/g, ' ') ?? '',
		}));
		const suffix = scope.words[scope.words.length - 1] ?? '';
		ok(
			`/chat ${code}: the scope suffix is not the English string`,
			!suffix.includes('and this view') && /[\u0900-\u097F\u0A80-\u0AFF]/.test(suffix) && scope.words.length >= 1,
			JSON.stringify(scope),
		);
	}
	await pickLanguage(p, 'en');
	await sleep(500);

	// ── the dock on / at 1440 (mutants 4a 4b 6a 7a 7b 7c; items 4 7 8 10) ──
	await gotoPage(WORKSPACE, 1440, 900, '[data-screen]');
	let tab = await p.$('[data-right-tab="assistant"]');
	if (!tab) {
		await p.evaluate(() => [...document.querySelectorAll('.rail-btn')].pop()?.click());
		await sleep(1500);
		tab = await p.$('[data-right-tab="assistant"]');
	}
	await tab.click();
	await sleep(2500);
	const input = await p.$('[data-dock="right"] [data-testid="chat-input"]');
	ok('the assistant dock opens on /', !!input);
	await input.click();
	await p.keyboard.type('where is it?', { delay: 10 });
	await p.keyboard.press('Enter');
	await p.waitForFunction(() => document.querySelectorAll('[data-dock="right"] .cite').length >= 2 && document.querySelector('[data-dock="right"] [data-directive]'), { timeout: 20000 }).catch(() => null);
	await sleep(1200);

	const dockTurn = await p.evaluate(() => {
		const dock = document.querySelector('[data-dock="right"]');
		const dr = dock.getBoundingClientRect();
		const panel = dock.querySelector('.panel[data-variant="dock"]');
		const pcs = getComputedStyle(panel);
		const clipped = [...dock.querySelectorAll('*')]
			.filter((e) => {
				const rr = e.getBoundingClientRect();
				return rr.width > 0 && [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) && rr.right > dr.right + 0.5;
			})
			.map((e) => e.textContent.trim().slice(0, 24) + '@' + Math.round(e.getBoundingClientRect().right));
		const chipRow = panel.querySelector('.suggest');
		const chip = panel.querySelector('.suggest [data-suggest]');
		const scope = panel.querySelector('[data-testid="chat-context"]');
		const scs = scope ? getComputedStyle(scope) : null;
		const state = panel.querySelector('[data-testid="chat-context"] .state');
		const lh = scope ? parseFloat(scs.lineHeight) || parseFloat(scs.fontSize) * 1.4 : 0;
		return {
			dockRight: Math.round(dr.right),
			padding: pcs.paddingLeft + '/' + pcs.paddingTop,
			padPx: parseFloat(pcs.paddingLeft),
			chipJustify: chipRow ? getComputedStyle(chipRow).justifyContent : null,
			chipOffset: chipRow && chip ? Math.round(chip.getBoundingClientRect().left - chipRow.getBoundingClientRect().left) : null,
			clipped,
			sendRight: Math.round(panel.querySelector('.composer button[type="submit"], .composer [data-ui="button"]')?.getBoundingClientRect().right ?? 0),
			cites: [...panel.querySelectorAll('.cite')].map((c) => ({
				title: c.title,
				urn: c.querySelector('[data-urn]')?.getAttribute('data-urn') ?? null,
			})),
			scopeBorder: scs ? scs.borderTopWidth : null,
			scopeH: scope ? Math.round(scope.getBoundingClientRect().height) : null,
			scopeOneLine: lh > 0 && scope.getBoundingClientRect().height <= lh * 1.5 + 2,
			scopeText: scope?.innerText.replace(/\s+/g, ' ').slice(0, 140) ?? null,
			stateWord: state?.textContent.trim() ?? null,
			directive: panel.querySelector('[data-directive]')?.innerText.replace(/\s+/g, ' ').slice(0, 80) ?? null,
		};
	});
	ok('dock: the panel has its own padding', dockTurn.padPx >= 8, dockTurn.padding);
	ok('dock: suggestion chips wrap from the left', dockTurn.chipJustify === 'flex-start' && dockTurn.chipOffset !== null && dockTurn.chipOffset <= 8, `justify=${dockTurn.chipJustify} offset=${dockTurn.chipOffset}`);
	ok('dock: nothing clips past the dock edge after a turn (toggles, Send)', dockTurn.clipped.length === 0 && dockTurn.sendRight <= dockTurn.dockRight, `clipped=${JSON.stringify(dockTurn.clipped)} sendRight=${dockTurn.sendRight} dockRight=${dockTurn.dockRight}`);
	ok('dock: the scope is ONE line — no frame, never wrapping', dockTurn.scopeBorder === '0px' && dockTurn.scopeOneLine, `border=${dockTurn.scopeBorder} h=${dockTurn.scopeH}`);
	ok(
		'dock: the scope\'s event state word is translated (never the raw state)',
		dockTurn.stateWord === null || !['planned', 'active', 'completed', 'cancelled'].includes(dockTurn.stateWord),
		JSON.stringify({ state: dockTurn.stateWord, scope: dockTurn.scopeText }),
	);
	const vehCite = dockTurn.cites.find((c) => c.urn === VEH);
	const labelCite = dockTurn.cites.find((c) => c.urn === LABEL_URN);
	ok(
		'dock: the citation tooltip says "Select on the map" (per-variant copy)',
		!!vehCite && /— Select on the map$/.test(vehCite.title),
		JSON.stringify(dockTurn.cites.map((c) => c.title)),
	);
	ok('dock: a label-shaped cited urn still renders an ObjectTag', !!labelCite, JSON.stringify(dockTurn.cites.map((c) => c.urn)));
	ok('dock: the mocked turn carries a proposal card and the Details stay closed with tiers + session', await p.evaluate(() => {
		const panel = document.querySelector('[data-dock="right"] .panel[data-variant="dock"]');
		const closed = [...panel.querySelectorAll('details.details')].filter((d) => !d.open);
		return !!panel.querySelector('[data-directive]') && closed.some((d) => d.querySelector('[data-testid="chat-tiers"]') && d.querySelector('[data-testid="chat-session"]'));
	}));
	const dockSteps = () => p.evaluate(() => [...document.querySelectorAll('[data-dock="right"] .step[data-testid="chat-tool-card"]')].map((e) => getComputedStyle(e).display));
	const dockOff = await dockSteps();
	ok('dock steps OFF: every .step computes display none', dockOff.length >= 1 && dockOff.every((d) => d === 'none'), JSON.stringify(dockOff));
	const dockToggled = await p.evaluate(() => {
		for (const s of document.querySelectorAll('[data-dock="right"] [role="switch"]')) {
			if (/Show steps/i.test((s.closest('label')?.innerText ?? '') + '')) {
				s.click();
				return true;
			}
		}
		return false;
	});
	const dockOn = await dockSteps();
	ok('dock steps ON: the rows show', dockToggled && dockOn.every((d) => d !== 'none'), `toggled=${dockToggled} ${JSON.stringify(dockOn)}`);
	await p.evaluate(() => {
		for (const s of document.querySelectorAll('[data-dock="right"] [role="switch"]')) {
			if (/Show steps/i.test((s.closest('label')?.innerText ?? '') + '')) {
				s.click();
				return;
			}
		}
	});
	if (SHOTS) await shot('assistant-smoke-dock-turn-1440.png');

	// the directive card stays on / (mutant 4b: a lost preventDefault lets
	// its href="/gods-eye" navigate). Clicked BEFORE the citation: switching
	// dock tabs remounts the panel and drops the conversation.
	await p.evaluate(() => document.querySelector('[data-dock="right"] [data-directive]')?.click());
	await sleep(4000);
	const afterDirective = await p.evaluate(() => ({ path: location.pathname, view: document.querySelector('[data-view-option][aria-pressed="true"], [data-view-option].is-pressed')?.getAttribute('data-view-option') ?? null }));
	ok('dock: the proposal card reviews on the CURRENT map (preventDefault held, no navigation)', afterDirective.path === WORKSPACE, JSON.stringify(afterDirective));

	// a citation click stays on / AND fills the Inspector (mutants 4a; item 4)
	// N3 (audit E-ASSIST R2): the dock's select FLIES — record the camera first.
	const camBefore = await p.evaluate(() => ({ ...window.__GODS_EYE__?.camera }));
	const vehPos = await fetch(`${origin}/api/v1/city/entities?kinds=vehicle`)
		.then((r) => r.json())
		.then((b) => (b.entities ?? []).find((e) => e.urn === VEH))
		.catch(() => null);
	await p.evaluate((u) => [...document.querySelectorAll('[data-dock="right"] .cite')].find((c) => c.querySelector(`[data-urn="${u}"]`))?.click(), VEH);
	await sleep(4000);
	const afterCite = await p.evaluate(() => ({ path: location.pathname, hash: location.hash.slice(0, 40) }));
	ok('dock: a citation click stays on / (no goto)', afterCite.path === WORKSPACE, JSON.stringify(afterCite));
	// N3: the camera MOVED to the cited vehicle (fly: true), not just selected it
	let fly = null;
	if (vehPos && vehPos.lon != null) {
		const flyDeadline = Date.now() + 15000;
		while (Date.now() < flyDeadline && !fly) {
			const s = await p.evaluate(() => ({ cam: window.__GODS_EYE__?.camera, outcome: window.__GODS_EYE__?.selection?.flyOutcome ?? null }));
			if (s.outcome === 'landed' || (s.cam && Math.hypot((s.cam.lon - vehPos.lon) * 102_000, (s.cam.lat - vehPos.lat) * 110_540) < 2000)) fly = s;
			else await sleep(400);
		}
		const moved = fly && fly.cam ? Math.hypot((fly.cam.lon - camBefore.lon) * 102_000, (fly.cam.lat - camBefore.lat) * 110_540) : 0;
		const at = fly && fly.cam ? Math.hypot((fly.cam.lon - vehPos.lon) * 102_000, (fly.cam.lat - vehPos.lat) * 110_540) : null;
		ok('dock: the citation click FLIES the camera to the vehicle (audit N3)', !!fly && moved > 100 && at != null && at < 2500, `moved ${Math.round(moved)} m · landed ${at == null ? '—' : `${Math.round(at)} m`} from the vehicle · outcome ${fly?.outcome ?? '—'}`);
	} else {
		ok('dock: the citation click FLIES the camera to the vehicle (audit N3)', false, 'the cited vehicle has no position in the registry to fly to');
	}
	// N5: the dock's scope line names the vehicle by its MASKED mark, never a
	// uuid — read AFTER returning to the Assistant tab (the citation click
	// switched the dock to the Inspector, which unmounts the panel).
	const insp = await p.$('[data-right-tab="inspector"]');
	if (insp) await insp.click();
	// the inspector's module loads with the first pick (FIX-E-PERF2): wait for
	// the panel to settle — the dossier of the cited object, or the empty state
	// — instead of a fixed pause; the assertion below is unchanged
	await p
		.waitForFunction(
			(u) => !!document.querySelector(`[data-right-panel="inspector"] [data-testid="entity-dossier"][data-urn="${u}"]`) || /Nothing selected/i.test(document.querySelector('[data-right-panel="inspector"]')?.innerText ?? ''),
			{ timeout: 15000 },
			VEH,
		)
		.catch(() => null);
	const inspector = await p.evaluate(() => document.querySelector('[data-right-panel]')?.innerText.replace(/\s+/g, ' ').slice(0, 200) ?? null);
	const dockPageKept = await samePage();
	ok(
		'dock: the citation fills the Inspector (the wall canvas never queues a selection)',
		!!inspector && !/Nothing selected/i.test(inspector) && /MH47EM/.test(inspector),
		dockPageKept ? JSON.stringify(inspector) : `${JSON.stringify(inspector)} — the page reloaded under the smoke (a dev-server full reload), so this read a fresh page`,
	);
	if (SHOTS) await shot('assistant-smoke-dock-after-cite-1440.png');
	// orchestrator make-up (audit E-ASSIST R2 must-fix 1): back on the Assistant tab the conversation is still there —
	// selecting a cited object must not wipe the officer's turns
	const backTab = await p.$('[data-right-tab="assistant"]');
	if (backTab) await backTab.click();
	// the panel remounts from its kept conversation (assistant/conversation.ts): wait for the
	// Assistant panel to render (its stream), then count the turns — no fixed pause
	await p.waitForSelector('[data-right-panel="assistant"] [data-testid="chat-stream"]', { timeout: 10000 }).catch(() => null);
	const kept = await p.evaluate(() => document.querySelectorAll('[data-dock="right"] article.msg[data-msg-role]').length);
	ok(
		'dock: after a citation opens the Inspector, returning to the Assistant keeps the conversation',
		kept > 0,
		(await samePage()) ? `${kept} message(s)` : `${kept} message(s) — the page reloaded under the smoke (a dev-server full reload): module state is gone, not dropped by the panel`,
	);
	const dockScope = await p.evaluate(() => document.querySelector('[data-dock="right"] [data-testid="chat-context"]')?.innerText.replace(/\s+/g, ' ') ?? '');
	ok('dock: the scope line names the vehicle (masked mark), never a uuid (audit N5)', /MH47EM•••1/.test(dockScope) && !/[0-9a-f]{8}-[0-9a-f]{4}/i.test(dockScope), dockScope.slice(0, 120) || 'no scope line');

	// N12 (audit E-ASSIST R2): a selection CARRIED IN from another page must
	// not navigate /comms away. The desk's navigation fires only for an
	// OMNIBAR-sourced selection (comms/+page.svelte: `source === 'omnibar'`),
	// so the carried-in pick is made in the omnibar here on / — exactly the
	// pick an officer makes before switching to the desk — and the arrival is
	// CLIENT-SIDE (module state, the selection and its source survive).
	const pickedHere = await (async () => {
		await p.evaluate(() => (document.activeElement instanceof HTMLElement ? document.activeElement.blur() : null));
		await p.keyboard.press('Escape');
		const pal = await openOmnibar();
		if (!pal) return false;
		await pal.click({ clickCount: 3 });
		await pal.type('mh47', { delay: 25 });
		await sleep(2500);
		const veh = await p.$('[role="option"][data-kind="vehicle"]');
		if (!veh) return false;
		await veh.click();
		await sleep(1500);
		// V3-P6B: a pick closes the omnibar and hands focus back to the top bar's search BUTTON (the v2 navbar's was an
		// input, which the workspace's Esc ignores), so Esc is pressed only while the omnibar is still open: an Esc on the
		// workspace itself clears the selection (the shell's rule: Esc closes, then clears), which is not what is held here
		if (await p.$('[data-testid="palette-input"]')) await p.keyboard.press('Escape');
		await sleep(300);
		return true;
	})();
	const carriedSel = await p.evaluate(() => ({ urn: window.__GODS_EYE__?.selection?.urn ?? null }));
	// the pick path above IS the omnibar's (Omnibar.svelte selects with source
	// 'omnibar'); the canvas hook does not publish the source, so the pick
	// route is pinned by construction, and the urn by measurement.
	ok('N12 setup: an omnibar pick on / holds the vehicle', pickedHere && carriedSel.urn === VEH, JSON.stringify(carriedSel));
	await p.evaluate((href) => {
		window.__assistantSmokeSpa = true;
		const a = document.createElement('a');
		a.href = href;
		a.textContent = 'assistant-smoke spa nav';
		document.body.appendChild(a);
		a.click();
		a.remove();
	}, '/comms');
	await p.waitForSelector('[data-screen="comms"]', { timeout: 30000 }).catch(() => null);
	await sleep(5000);
	const carried = await p.evaluate(() => ({ path: location.pathname, spa: window.__assistantSmokeSpa === true }));
	ok('/comms: a selection carried in from another page does NOT navigate away (audit N12)', carried.path === '/comms' && carried.spa, JSON.stringify(carried));

	// ── /comms at 1920 (mutants 8a; the 8d-equivalent; items 5 6 8) ────────
	// the same read-only board as the interrupts check: its pursuit ACTIVE (F-05)
	stubBoard = strippedPursuit ? { events: boardRows.map((e) => (e === strippedPursuit ? { ...e, status: 'active' } : e)) } : null;
	await gotoPage('/comms', 1920, 1080, '[data-screen="comms"]');
	const commsBar = await readBar();
	ok(
		'/comms keeps the live strip and the same inbox count',
		commsBar.strip && !!commsBar.stripText && commsBar.pursuit === opsBar.pursuit && commsBar.inbox === opsBar.inbox,
		JSON.stringify({ strip: commsBar.stripText?.slice(0, 60), inbox: commsBar.inbox, ops: opsBar.inbox }),
	);
	const commsOmni = await omniFind('mh47');
	ok('/comms omnibar finds mh47', commsOmni.rows.some((r) => r.kind === 'vehicle' && /MH47EM•••1/.test(r.text)), JSON.stringify(commsOmni.rows.slice(0, 2)));

	const commsOperator = await p.evaluate(() => {
		const tri = document.querySelector('[data-testid="comms-trilingual"]');
		const badge = document.querySelector('[data-testid="comms-withheld-badge"]');
		return {
			withheldNodes: [...document.querySelectorAll('[data-lang]')].map((e) => ({ lang: e.getAttribute('lang') ?? e.getAttribute('data-lang'), w: e.getAttribute('data-withheld') })),
			triText: tri?.innerText.replace(/\s+/g, ' ').trim() ?? null,
			triCopies: tri ? tri.querySelectorAll('.copy').length : -1,
			badgeText: badge?.innerText.replace(/\s+/g, ' ').trim() ?? null,
			draftedCount: (document.body.innerText.match(/Drafted — not delivered/g) ?? []).length,
		};
	});
	ok(
		'/comms operator-only arm: the three withheld columns keep their nodes, language names only — no dash, no dead Copy, the notice said once',
		commsOperator.withheldNodes.length === 3 &&
			commsOperator.withheldNodes.every((n) => n.w === 'yes') &&
			!!commsOperator.badgeText &&
			!commsOperator.triText.includes('—') &&
			!(commsOperator.badgeText && commsOperator.triText.includes(commsOperator.badgeText)) &&
			commsOperator.triCopies === 0,
		JSON.stringify(commsOperator),
	);
	// V3-P6A: the desk lives under the V3 shell; the draft log and the dispatch threads moved into a side sheet, so the old
	// "threads take the remaining height" geometry is gone. What stays true at 1920: the desk holds its measure, the three
	// draft columns sit side by side inside the viewport, and the threads are NOT on the desk until the sheet opens.
	const comms1920 = await p.evaluate(() => {
		const desk = document.querySelector('.comms');
		const dr = desk.getBoundingClientRect();
		const cols = [...document.querySelectorAll('[data-testid="comms-trilingual"] [data-lang]')].map((c) => c.getBoundingClientRect());
		return { deskWidth: Math.round(dr.width), cols: cols.length, inside: cols.every((r) => r.width > 0 && r.right <= window.innerWidth), withheld: cols.every((r) => r.width === 0), threadsOnDesk: !!document.querySelector('.thread'), sheet: !!document.querySelector('[data-testid="comms-sheet"]') };
	});
	ok('/comms at 1920: the desk holds its measure (≤ 1760 px)', comms1920.deskWidth <= 1760, JSON.stringify(comms1920));
	ok('/comms at 1920: the dispatch threads are behind the side sheet (not on the desk), and the three columns share the row (or are all withheld for an operator-only event — v3-comms-smoke holds the public layout)', !comms1920.threadsOnDesk && !comms1920.sheet && (comms1920.cols === 3 ? comms1920.inside || comms1920.withheld : true), JSON.stringify(comms1920));
	if (SHOTS) await shot('assistant-smoke-comms-1920.png');

	// a public event: the drafts compose and "Drafted — not delivered" is said
	// once. On a board whose only event is operator-only (int3cl today) the
	// desk has nothing to draft for — the N18 kill needs a usable Generate, so
	// the board is answered with the REAL events plus one synthetic PUBLIC
	// procession (a READ stub in the page, never a write to any backend) and
	// the desk is reloaded onto it.
	const realBoard = await fetch(`${origin}/api/v1/events/active`, { signal: AbortSignal.timeout(15000) })
		.then((r) => r.json())
		.catch(() => null);
	const realEvents = Array.isArray(realBoard?.events) ? realBoard.events : [];
	const PROCESSION = {
		event_id: 'bbbbbbbb-2222-4ccc-8ddd-eeeeeeeeee01',
		event_kind: 'procession',
		status: 'active',
		title: 'Smoke procession — N18 draft log (EMULATED)',
		name: 'Smoke procession — N18 draft log (EMULATED)',
		description: 'A synthetic public event so the desk can compose; nothing was written anywhere.',
		route_segment_ids: [1005, 1013],
		routes: [{ label: 'primary', segment_ids: [1005, 1013] }],
		phases: [{ label: 'procession', window_start: null, window_end: null, advance_closure_sec: 120 }],
		protection_class: 'none',
		crowd_class: 'LOW',
		metadata: {},
	};
	// the pursuit stubbed ACTIVE again (F-05: the strip carries only a pursuit under way), plus the procession
	stubBoard = { events: [...realEvents.map((e) => (strippedPursuit && e.event_id === strippedPursuit.event_id ? { ...e, status: 'active' } : e)), PROCESSION] };
	console.log(`note — N18: board stubbed with the real ${realEvents.length} event(s) + one synthetic public procession (read-only stub)`);
	await gotoPage('/comms', 1920, 1080, '[data-screen="comms"]');
	const publicPick = await p.evaluate(() => {
		const sel = document.querySelector('[data-testid="comms-event-select"]');
		if (!sel) return null;
		for (const o of sel.options) {
			if (!/pursuit|Pursuit|crime|Crime/i.test(o.textContent)) return { id: o.value, label: o.textContent.trim().slice(0, 50) };
		}
		return null;
	});
	if (publicPick) {
		await p.select('[data-testid="comms-event-select"]', publicPick.id);
		await sleep(5000);
		const pub = await p.evaluate(() => ({
			draftedCount: (document.body.innerText.match(/Drafted — not delivered/g) ?? []).length,
			noGateway: (document.body.innerText.match(/No message gateway is deployed/g) ?? []).length,
			withheldNodes: [...document.querySelectorAll('[data-lang]')].map((e) => e.getAttribute('data-withheld')),
		}));
		ok(
			`/comms public event (${publicPick.label}): "Drafted — not delivered" appears once (the review badge; the no-gateway line carries no second badge)`,
			pub.draftedCount === 1 && pub.noGateway >= 1 && pub.withheldNodes.every((w) => w === 'no'),
			JSON.stringify(pub),
		);
		// N18 (audit E-ASSIST R2): the draft log keeps its height cap with a LONG
		// session — generate repeatedly so the log holds more entries than fit,
		// then it must scroll INSIDE its capped section (max-height stays,
		// overflow-y auto), never pushing the dispatch threads down. (The
		// capped `ul.log` renders only once entries exist, so the kill needs
		// the generated entries — the stubbed public event above provides them.)
		// V3-P6A: the log is in the side sheet, whose body scrolls INSIDE the sheet (the desk behind it never moves)
		const logState = () =>
			p.evaluate(() => {
				const log = document.querySelector('[data-testid="comms-log"]');
				const body = document.querySelector('[data-testid="comms-sheet"] .body');
				if (!log || !body) return null;
				const cs = getComputedStyle(body);
				return { entries: log.children.length, maxH: cs.maxHeight === 'none' ? `${Math.round(body.getBoundingClientRect().height)}px` : cs.maxHeight, overflowY: cs.overflowY, scrolls: body.scrollHeight > body.clientHeight, h: Math.round(body.getBoundingClientRect().height) };
			});
		const genBtn = await p.$('button:has([data-testid="comms-generate"]), [data-testid="comms-generate"] button');
		if (genBtn) {
			const disabled = await genBtn.evaluate((b) => b.disabled || b.getAttribute('aria-disabled') === 'true');
			for (let i = 0; i < 12 && !disabled; i++) {
				await genBtn.click().catch(() => undefined);
				await sleep(150);
			}
			await sleep(600);
			await p.click('[data-testid="comms-open-log"]');
			await p.waitForSelector('[data-testid="comms-sheet"] [data-testid="comms-log"]', { timeout: 5000 }).catch(() => undefined);
			const logCap = await logState();
			ok(
				'/comms: a long draft log scrolls inside its capped section (audit N18)',
				!!logCap && logCap.entries >= 6 && logCap.maxH !== 'none' && parseFloat(logCap.maxH) > 0 && logCap.overflowY === 'auto' && logCap.scrolls,
				logCap ? `${logCap.entries} entries · max-height ${logCap.maxH} · overflow ${logCap.overflowY} · scrolls=${logCap.scrolls} · h=${logCap.h}px` : 'no log list',
			);
		} else {
			ok('/comms: a long draft log scrolls inside its capped section (audit N18)', false, 'no Generate control on the desk — the N18 kill did not run');
		}
	} else {
		ok('/comms: a long draft log scrolls inside its capped section (audit N18)', false, 'no public-kind event even on the stubbed board — the N18 kill did not run');
	}
	stubBoard = null;

	// ── /comms at 1366: the review badge above the fold (mutant 8c) ────────
	await p.setViewport({ width: 1366, height: 768 });
	await sleep(1200);
	const badge1366 = await p.evaluate(() => {
		const badge = [...document.querySelectorAll('[data-testid="comms-drafted"] , .review-line [data-ui="tag"], .review-line *')].find((e) => /Drafted — not delivered/.test(e.innerText ?? ''));
		return badge ? Math.round(badge.getBoundingClientRect().top) : null;
	});
	ok('/comms at 1366: the review badge stays above the fold', badge1366 !== null && badge1366 < 768, `badge top ${badge1366}, fold 768`);
	if (SHOTS) await shot('assistant-smoke-comms-1366.png');

	// ── an omnibar pick on /comms opens the object on / (nice-to-have) ─────
	await p.setViewport({ width: 1440, height: 900 });
	await sleep(800);
	const pal3 = await openOmnibar();
	if (pal3) {
		await pal3.click({ clickCount: 3 });
		await pal3.type('mh47', { delay: 25 });
		await sleep(2500);
		await p.keyboard.press('Enter');
		await sleep(4000);
		const nav = await p.evaluate(() => ({ path: location.pathname, sel: true }));
		ok('an omnibar pick on /comms opens the object on / (the desk has no inspector)', nav.path === WORKSPACE, JSON.stringify(nav));
	} else {
		ok('an omnibar pick on /comms opens the object on /', false, (await samePage()) ? 'no omnibar input after the navbar search / Ctrl+K' : 'no omnibar input — the page reloaded under the smoke (a dev-server full reload), not a product fault');
	}

	// A client-side arrival at '/' trips a PRE-EXISTING effect loop in the
	// workspace page (not this WP's file): reproduced on the round-1 code
	// before this smoke existed. Counted, reported, filtered here.
	const loopErrors = errors.filter((e) => e.includes('effect_update_depth_exceeded'));
	const otherErrors = errors.filter((e) => !e.includes('effect_update_depth_exceeded'));
	ok(
		'no page errors on /chat, / and /comms (the known pre-existing workspace effect loop on soft-nav to / is counted, not hidden)',
		otherErrors.length === 0,
		`${otherErrors.length} errors${otherErrors.length ? ': ' + otherErrors.slice(0, 3).join(' | ') : ''} · pre-existing loop fired ${loopErrors.length}×`,
	);
} finally {
	await signOut(session);
	await browser.close().catch(() => {});
}

if (failures > 0) {
	console.error(`assistant-smoke: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('ok   assistant-smoke — all assertions passed');
process.exit(0);
