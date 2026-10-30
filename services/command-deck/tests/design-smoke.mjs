/**
 * Design-shell headless smoke — the design-system gallery (/design) plus the
 * route-topology tripwire. Builds nothing itself: serves the adapter-node
 * build/ output (spawning `PORT=5199 node build` when nothing answers,
 * gods-eye-smoke pattern) and asserts under SwiftShader:
 *
 *   1. `/analyst` (WORKSPACE, tests/lib/routes.mjs) IS the restored Convoy Command cockpit (the VVIP template
 *      home): 200 + the template root in the server render (the frame
 *      scripts/showcase_run.sh greps for), and the cockpit MOUNTS in the
 *      browser once the operator gate's state is known, as /ops does —
 *      the smoke signs in when the origin's gate is on (tests/lib/
 *      operator-session.mjs: one attempt, PIN read at run time, never
 *      logged, cookie set before navigation, revoked on exit), so the
 *      cockpit itself must mount; only a sign-in card counts as a failure
 *   2. the live URLs return 200 (/, /ops, /gods-eye, /comms, /chat,
 *      /citizen, /driver) — a URL that resolves twice or zero times fails
 *      sync; this is the tripwire
 *   3. /design: every legacy primitive mounts ([data-prim])
 *   4. token parity BOTH themes via getComputedStyle on the two
 *      [data-theme-preview] boxes, values compared against tokens.css; the
 *      operator base is 14 px (SPEC §2.2)
 *   5. the BLACK chip is an inverted chip: 1px hairline + TRANSLUCENT
 *      fill (never an opaque void)
 *   6. modal opens and closes on Escape (focus trap mounts)
 *   7. toasts push and render in the shell's [data-shell=toaster] region
 *      (src/lib/ui's Toaster wired to the toast store; max 3)
 *   8. reduced motion calms the deck: --v-dur-wipe → 64ms and BLACK's
 *      breathing animation is removed (static hairline)
 *   9. '/' opens the page's omnibar on the workspace (the V3 top bar's one search:
 *      V3-P6B retired the navbar's own route-search field; the omnibar holds
 *      the routes); the band tag renders its honest hollow "Band —"
 *      (data-band="pending") when no page assigns a band (R3)
 *  10. src/lib/ui (SPEC §5.1, §6.7): every primitive mounts in the gallery,
 *      each static one in BOTH theme columns, and the overlays open and
 *      close (Popover, Tooltip, Dialog, Alert, Drawer, HotkeysDialog —
 *      Escape closes the topmost and focus returns); a portalled overlay
 *      keeps its theme; a nested popover keeps its parent open; the
 *      primitives' copy follows the language context, switched by the
 *      shell's ONE language switch (EN · हि · ગુ in the top bar's menu); the virtualised table keeps the DOM
 *      small; the compact provenance tag's hidden label is its textContent,
 *      an unknown source says so and a live row is unmarked; the colour
 *      roles hold (decision verbs neutral left of one primary, data states
 *      neutral); no command text renders under 12 px; a selected row has
 *      one veil; the type scale prints what each theme renders; property
 *      rows are 30 px; a removable CompoundTag's ✕ removes its filter; a
 *      zero MetricCard recedes to ink-2 at 400 whatever its intent; a click
 *      popover takes focus (Enter, then ArrowDown walks its Menu; Escape and
 *      Tab hand focus back to the target); a Tree has one tab stop and a
 *      collapsible Section keeps its heading; at 1366 px no DataTable
 *      column is narrower than its minimum (the table scrolls sideways)
 *  11. fonts are self-hosted: no request to fonts.googleapis.com or
 *      fonts.gstatic.com while /design loads, the faces come from /fonts/,
 *      and Inter is the face of the primitives
 *  12. fictional data only: every plate on /design is a masked mark
 *      (MH01XX•••7 style) and no full registration mark appears in its text
 *  13. UI-S1B: the legacy primitives are rebuilt on src/lib/ui (Badge a Tag,
 *      Panel a Section with an h2, Button a ui Button, DataTile a MetricCard,
 *      EmptyState a NonIdealState, FeedItem the AuditTable row, LayerRail
 *      with EyeToggles; data-prim kept), sentence case with no uppercase
 *      transform or tracking, the BLACK chip reads "Black"; the toaster is
 *      the shell's region; the application shell on /design/shell (the
 *      harness supplying every commandBar field with fictional data), now the
 *      V3 chrome (V3-P6B): the V3 top bar (68 px from 1500 px, 60 px below)
 *      with the search (command-search), the menu carrying feed-provenance and
 *      the officer pill, and the operator band under it (52 / 46 px) with
 *      brain-posture (data-decider, data-tier and the "p95 2.3 s … novelty
 *      check on" summary), band-tag (data-band, ticking data-age-sec, read
 *      twice), the Inbox and More; no horizontal overflow at 1920, 1680, 1440
 *      and 1366 px, and the LiveStrip (clock, movement, pursuit, the 0:47
 *      countdown with Review); the duty officer is the pill whose popover holds
 *      the one duty-officer input at every width (focused, the §9.1 helper as
 *      its description, a clear button that empties it; gate on: locked to the
 *      signed-in officer) and closes on Esc without navigating; no control of
 *      either bar is ever clipped from 1280 to 1920 px with every field plus
 *      the legacy Share and/or the operator gate's control (faked per page by
 *      answering GET /api/session): the search stays at least 240 px, the
 *      Policies label stays, and the legacy Share is drawn nowhere in the
 *      chrome (it lives in the view header); and (13c) the
 *      rebuilt primitives in squeezed hosts (/design/shell?squeeze=1): a
 *      fixed-height rail of two panels spills nothing over the next panel
 *      (the scrolling panel's body scrolls inside it, the glass panel
 *      clips), and audit rows in a fixed-height scroller are never squeezed
 *      under their own text
 *
 * Usage: node tests/design-smoke.mjs [origin]    # default http://127.0.0.1:5199
 * Env:   SAJAG_OPERATOR_PIN, else SAJAG_OPERATOR_PIN_FILE, else sajag.env — read
 *        only when the origin's operator gate is on. ORACLE_PORT, BRAIN_PORT
 *        and EMULATOR_PORT are required only when nothing answers on the
 *        origin and the smoke must spawn its own preview (it never falls
 *        back to hooks.server.ts's live defaults)
 * Exit 0 with `ok <name> — <detail>` lines; exit 1 on any failure.
 */

import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { puppeteerCookies, signIn, signOut } from './lib/operator-session.mjs';
import { HOME, WORKSPACE } from './lib/routes.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');

// Puppeteer + cached Chrome live in the repo's frontend/ tree (the e2e
// harness pattern; the same candidates as tests/gods-eye-smoke.mjs): this
// checkout's frontend first, then the argus tree — never the retired one.
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
	path.join(os.homedir(), '.cache/puppeteer/chrome/linux_arm-146.0.7680.76/chrome-linux-arm64/chrome')
].filter(Boolean);
const executablePath = CHROME_CANDIDATES.find(existsSync);
if (!executablePath) throw new Error('no Chrome binary found (set CHROME_PATH)');

const SWIFTSHADER_ARGS = [
	'--no-sandbox',
	'--disable-setuid-sandbox',
	'--disable-dev-shm-usage',
	'--enable-unsafe-swiftshader',
	'--use-gl=angle',
	'--use-angle=swiftshader'
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

/** SPEC §9.1, verbatim: every duty-officer field says what naming an officer does. */
const OFFICER_HELPER = 'Shows full registration marks on this console and records the name with your decision. Attribution, not sign-in.';
/** A fictional name, typed into the /design/shell harness only. */
const SMOKE_OFFICER = 'Insp. Smoke Check (fictional)';

/**
 * §13 on /design/shell at width `w` (the page just loaded, nothing named yet), under the V3 chrome: the top bar's
 * officer pill opens a popover holding the one duty-officer input at EVERY width (it was an inline input from
 * 1440 px and an avatar popover below, on the v2 navbar). The input takes a name and stays an input (the value
 * kept, a clear button that empties it, the §9.1 helper as its description), the pill then carries the name,
 * and Esc closes the popover without navigating. With the operator gate on, the field is locked to the
 * signed-in officer instead.
 */
async function checkOfficer(page, w) {
	const pill = '[data-v3="top-bar"] [data-testid="v3-officer"]';
	const read = () =>
		page.evaluate(() => {
			const els = [...document.querySelectorAll('input[data-testid="duty-officer"]')];
			const el = els[0] ?? null;
			if (!el) return { count: 0 };
			const help = document.getElementById(el.getAttribute('aria-describedby') ?? '');
			return {
				count: els.length,
				tag: el.tagName,
				value: el.value,
				readonly: el.readOnly,
				locked: el.getAttribute('data-locked'),
				focused: document.activeElement === el,
				inPopover: !!el.closest('[data-ui="popover"]'),
				clear: !!el.closest('[data-ui="input"], .officer-input')?.querySelector('button.clear'),
				help: help?.textContent?.replace(/\s+/g, ' ').trim() ?? null,
				harness: document.querySelector('[data-design="officer-value"]')?.textContent?.trim() ?? null
			};
		});
	const before = page.url();
	const inline = await page.evaluate(() => !!document.querySelector('[data-v3="top-bar"] input[data-testid="duty-officer"], [data-shell="command-bar"] input[data-testid="duty-officer"]'));
	await page.click(pill);
	await page.waitForSelector('[data-ui="popover"] input[data-testid="duty-officer"]', { timeout: 5000 }).catch(() => null);
	await sleep(250);
	const open = await read();
	if (session.gate) {
		ok(
			`shell ${w}: gate on — the officer pill's popover holds the duty-officer input, locked to the signed-in officer`,
			!inline && open.count === 1 && open.inPopover && open.readonly && open.locked === 'true' && open.value === session.officer,
			JSON.stringify(open)
		);
	} else {
		await page.keyboard.type(SMOKE_OFFICER, { delay: 2 });
		await sleep(250);
		const named = await read();
		const pillText = await page.$eval(pill, (el) => el.textContent?.replace(/\s+/g, ' ').trim() ?? '');
		await page.click('[data-ui="popover"] button.clear').catch(() => null);
		await sleep(250);
		const cleared = await read();
		await page.click('[data-ui="popover"] input[data-testid="duty-officer"]');
		await page.keyboard.type(SMOKE_OFFICER, { delay: 2 });
		await sleep(250);
		await page.keyboard.press('Escape');
		await sleep(400);
		const after = await page.evaluate((sel) => ({ input: document.querySelectorAll('input[data-testid="duty-officer"]').length, pill: document.querySelector(sel)?.textContent?.replace(/\s+/g, ' ').trim() ?? null }), pill);
		ok(
			`shell ${w}: the officer pill opens a popover holding the one duty-officer input (focused, the §9.1 helper, a clear button that empties it), it takes a name and Esc closes it without navigating`,
			!inline &&
				open.count === 1 &&
				open.inPopover &&
				open.focused &&
				!open.readonly &&
				open.help === OFFICER_HELPER &&
				named.tag === 'INPUT' &&
				named.value === SMOKE_OFFICER &&
				named.harness === SMOKE_OFFICER &&
				named.clear &&
				pillText.includes(SMOKE_OFFICER) &&
				cleared.count === 1 &&
				cleared.value === '' &&
				cleared.harness === 'none' &&
				after.input === 0 &&
				(after.pill ?? '').includes(SMOKE_OFFICER) &&
				page.url() === before,
			JSON.stringify({ inline, open, named: named.value, cleared: { value: cleared.value, harness: cleared.harness }, after, navigated: page.url() !== before })
		);
		// leave the harness with nobody named, as it started
		await page.click(pill);
		await page.waitForSelector('[data-ui="popover"] input[data-testid="duty-officer"]', { timeout: 5000 }).catch(() => null);
		await page.click('[data-ui="popover"] button.clear').catch(() => null);
	}
	await page.keyboard.press('Escape');
}

async function originAlive(origin) {
	try {
		const res = await fetch(`${origin}/design`, { redirect: 'manual', signal: AbortSignal.timeout(3000) });
		return res.status < 500;
	} catch {
		return false;
	}
}

async function ensureOrigin(origin, port) {
	if (await originAlive(origin)) return null;
	// A spawned preview proxies hooks.server.ts's upstreams, whose defaults are
	// the LIVE stack's ports. Spawn one only when the caller names them
	// (scripts/verify_all.sh always does; a sandbox run exports the sandbox's
	// ports), never on those defaults by omission.
	const unnamed = ['ORACLE_PORT', 'BRAIN_PORT', 'EMULATOR_PORT'].filter((k) => !process.env[k]);
	if (unnamed.length) {
		throw new Error(
			`nothing answers on ${origin}, and the preview this smoke would spawn has no ${unnamed.join(', ')}: ` +
				'export them (a sandbox’s ports) instead of letting it proxy the live defaults'
		);
	}
	if (!existsSync(path.join(DECK, 'build', 'index.js'))) {
		throw new Error('no build/ output — run `npx vite build` first');
	}
	// A preview this smoke spawns is private: gate off and keyless, whatever
	// this shell exported (the PIN, the session secret and the ion token stay
	// with the deployed deck).
	const env = { ...process.env, PORT: String(port), HOST: '127.0.0.1' };
	for (const k of ['SAJAG_OPERATOR_PIN', 'SAJAG_OPERATOR_PIN_FILE', 'SAJAG_SESSION_SECRET', 'SAJAG_SESSION_SECURE', 'SAJAG_CESIUM_ION_TOKEN']) delete env[k];
	const proc = spawn('node', ['build'], {
		cwd: DECK,
		env,
		stdio: ['ignore', 'pipe', 'pipe']
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

/** tokens.css declared values, whitespace-normalised (the parity source). */
function declaredTokens() {
	const css = readFileSync(path.join(DECK, 'src/lib/design/tokens.css'), 'utf8');
	const grab = (from, to) => {
		const a = css.indexOf(from);
		const b = css.indexOf(to, a);
		const map = {};
		for (const m of css.slice(a, b).replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/(--v-[a-z0-9-]+)\s*:\s*([^;]+);/g)) {
			map[m[1]] = m[2].replace(/\s+/g, ' ').trim();
		}
		return map;
	};
	return {
		command: grab("[data-theme='command'] {", "[data-theme='daylight']"),
		daylight: grab("[data-theme='daylight'] {", '@media')
	};
}

/** The primitive names src/lib/ui/index.ts exports (UI_PRIMITIVES), read as text. */
function uiPrimitives() {
	const src = readFileSync(path.join(DECK, 'src/lib/ui/index.ts'), 'utf8');
	const block = /UI_PRIMITIVES\s*=\s*\[([\s\S]*?)\]/.exec(src)?.[1] ?? '';
	return [...block.matchAll(/'([a-z-]+)'/g)].map((m) => m[1]);
}

const DECLARED = declaredTokens();
const UI_NAMES = uiPrimitives();
const OVERLAY_NAMES = new Set(['popover', 'tooltip', 'dialog', 'alert', 'drawer', 'hotkeys-dialog']);
const normColor = (s) =>
	s
		.replace(/\s+/g, '')
		.toLowerCase();

const browser = await puppeteer.launch({ executablePath, headless: 'new', args: SWIFTSHADER_ARGS });
let deckProc = null;
let session = null;

try {
	const portArg = process.argv[2] ? Number(new URL(process.argv[2]).port) : 5199;
	const origin = (process.argv[2] ?? `http://127.0.0.1:${portArg}`).replace(/\/+$/, '');
	deckProc = await ensureOrigin(origin, portArg);
	ok('deck-origin up', true, origin);
	session = await signIn(origin, 'Design smoke (automated check)');
	ok('operator gate', true, session.gate ? 'on — signed in' : 'off');

	// ── 1: the workspace (WORKSPACE) IS the restored Convoy Command cockpit (the VVIP template
	// home, rebuilt on the live stack) ──────────────────────────────────
	const root = await fetch(`${origin}${WORKSPACE}`, { redirect: 'manual' });
	const rootHtml = root.ok ? await root.text() : '';
	{
		const cockpit = await browser.newPage();
		await cockpit.setViewport({ width: 1440, height: 900 });
		if (session.gate) await cockpit.setCookie(...puppeteerCookies(session));
		await cockpit.goto(`${origin}${WORKSPACE}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
		const mountedAs = await cockpit
			.waitForSelector('[data-template="convoy-command"]:not([data-pending]), [data-testid="cockpit-signin-required"]', { timeout: 20000 })
			.then((el) => el?.evaluate((e) => (e.dataset.template ? 'cockpit' : 'gate sign-in')))
			.catch(() => null);
		ok(
			`${WORKSPACE} is the Convoy Command cockpit (200, template mounted)`,
			root.status === 200 && rootHtml.includes('data-template="convoy-command"') && (session.gate ? mountedAs === 'cockpit' : !!mountedAs),
			`status=${root.status} server-render template=${rootHtml.includes('data-template="convoy-command"')} · mounted=${mountedAs ?? 'nothing'}`
		);
		await cockpit.close();
	}

	// ── 2: the live URLs ─────────────────────────────────────────────────
	const EIGHT = [WORKSPACE, HOME, '/ops', '/gods-eye', '/comms', '/chat', '/citizen', '/driver'];
	for (const url of EIGHT) {
		const res = await fetch(`${origin}${url}`, { redirect: 'manual' });
		ok(`url 200 ${url}`, res.status === 200, `status=${res.status}`);
	}
	const designRes = await fetch(`${origin}/design`, { redirect: 'manual' });
	const designHtml = designRes.ok ? await designRes.text() : '';
	ok('url 200 /design', designRes.status === 200, `status=${designRes.status}`);

	// ── /design: primitives, parity, BLACK chip, modal, toast, motion ────
	// A context of its own: a cold cache, so every font /design needs is a
	// request this smoke sees (the cockpit page above shares no cache with it).
	const designContext = await browser.createBrowserContext();
	const page = await designContext.newPage();
	await page.setViewport({ width: 1440, height: 1000 });
	if (session.gate) await page.setCookie(...puppeteerCookies(session));
	const consoleErrors = [];
	page.on('pageerror', (e) => consoleErrors.push(`pageerror: ${String(e).slice(0, 200)}`));
	const requests = [];
	page.on('request', (r) => requests.push(r.url()));
	const fontResponses = [];
	page.on('response', (r) => {
		if (/\/fonts\/[^/]+\.woff2$/.test(new URL(r.url()).pathname)) fontResponses.push(`${new URL(r.url()).pathname} ${r.status()}`);
	});

	await page.goto(`${origin}/design`, { waitUntil: 'networkidle2', timeout: 60000 });
	await page.evaluate(() => document.fonts.ready);
	await sleep(500);

	// ── 11: fonts are self-hosted ────────────────────────────────────────
	{
		const cdn = requests.filter((u) => /fonts\.(googleapis|gstatic)\.com/.test(u));
		const fonts = await page.evaluate(() => {
			const btn = document.querySelector('[data-specimen-theme="command"] [data-ui="button"]');
			return {
				inter: document.fonts.check('14px Inter'),
				mono: document.fonts.check('12px "JetBrains Mono"'),
				buttonFace: btn ? getComputedStyle(btn).fontFamily.split(',')[0].trim() : null
			};
		});
		ok(
			'fonts: no request to fonts.googleapis.com or fonts.gstatic.com while /design loads',
			cdn.length === 0 && !/fonts\.(googleapis|gstatic)\.com/.test(designHtml),
			cdn.length ? cdn.slice(0, 3).join(' | ') : `${requests.length} requests, none to a font CDN`
		);
		// 200 (or 304 when a dev server revalidates a face the page asked for twice)
		const served = fontResponses.filter((r) => / (200|304)$/.test(r));
		ok(
			'fonts: Inter and JetBrains Mono load from /fonts/ (self-hosted WOFF2) and Inter is the primitives’ face',
			served.some((r) => r.startsWith('/fonts/inter-latin.woff2')) && served.some((r) => r.startsWith('/fonts/jetbrains-mono-latin.woff2')) && fonts.inter && fonts.mono && fonts.buttonFace === 'Inter',
			`${fontResponses.join(', ') || 'no font response'} · face=${fonts.buttonFace}`
		);
	}

	const PRIMS = [
		'panel',
		'band-chip',
		'badge',
		'button',
		'data-tile',
		'feed-item',
		'audit-row',
		'map-legend',
		'layer-rail',
		'empty-state',
		'band-masthead',
		'decision-card',
		'event-dossier'
	];
	const mounted = await page.evaluate((ids) => {
		const out = {};
		for (const id of ids) out[id] = document.querySelectorAll(`[data-prim="${id}"]`).length;
		out['panel-shell-via-panel'] = document.querySelectorAll('[data-prim="panel"]').length >= 2;
		out['command-bar'] = document.querySelectorAll('[data-shell="command-bar"]').length;
		out['band-pending-chip'] = document.querySelectorAll('[data-band="pending"]').length;
		return out;
	}, PRIMS);
	for (const id of PRIMS) ok(`primitive mounts: ${id}`, mounted[id] > 0, `count=${mounted[id]}`);

	// ── 3b: the legacy primitives are rebuilt on src/lib/ui (SPEC §5.2) ──
	{
		const rebuilt = await page.evaluate(() => {
			const q = (sel) => Array.from(document.querySelectorAll(sel));
			const is = (sel, ui) => q(sel).length > 0 && q(sel).every((el) => el.getAttribute('data-ui') === ui);
			const has = (sel, ui) => q(sel).length > 0 && q(sel).every((el) => el.getAttribute('data-ui') === ui || !!el.querySelector(`[data-ui="${ui}"]`));
			const upper = q('[data-prim], [data-prim] *').filter((el) => getComputedStyle(el).textTransform === 'uppercase').length;
			const tracked = q('[data-prim], [data-prim] *').filter((el) => {
				const ls = getComputedStyle(el).letterSpacing;
				return ls !== 'normal' && parseFloat(ls) !== 0;
			}).length;
			return {
				badge: is('[data-prim="badge"]', 'tag'),
				panel: is('[data-prim="panel"]', 'section'),
				panelTitleH2: q('[data-prim="panel"]').every((el) => !!el.querySelector('h2')),
				button: is('[data-prim="button"]', 'button'),
				dataTile: has('[data-prim="data-tile"]', 'metric-card'),
				emptyState: is('[data-prim="empty-state"]', 'non-ideal-state'),
				decisionCard: has('[data-prim="decision-card"]', 'button'),
				feedItem: has('[data-prim="feed-item"]', 'time'),
				layerRail: has('[data-prim="layer-rail"]', 'eye-toggle'),
				dossier: has('[data-prim="event-dossier"]', 'id'),
				black: document.querySelector('[data-prim="band-chip"][data-band="BLACK"]')?.textContent?.trim() ?? null,
				upper,
				tracked
			};
		});
		const { black, upper, tracked, ...flags } = rebuilt;
		const off = Object.entries(flags).filter(([, v]) => !v).map(([k]) => k);
		ok(
			'legacy primitives rebuilt on src/lib/ui (Tag, Section h2, Button, MetricCard, NonIdealState, the AuditTable row, EyeToggle, Id), data-prim kept',
			off.length === 0,
			off.length ? `not rebuilt: ${off.join(', ')}` : Object.keys(flags).join(' ')
		);
		ok(
			'legacy primitives: sentence case, no uppercase transform, no tracking; the BLACK chip reads "Black"',
			upper === 0 && tracked === 0 && black === 'Black',
			`uppercase=${upper} tracked=${tracked} black=${black}`
		);
	}
	ok('PanelShell mounts (alias of Panel)', mounted['panel-shell-via-panel']);
	ok('command bar mounts', mounted['command-bar'] === 1);
	ok(
		"R3 hollow state is honest: 'band —' chip renders when nothing assigns band",
		mounted['band-pending-chip'] >= 1,
		`count=${mounted['band-pending-chip']}`
	);

	// ── 4: token parity BOTH themes via getComputedStyle ─────────────────
	const parity = await page.evaluate(async () => {
		const read = (sel) => {
			const el = document.querySelector(sel);
			const cs = getComputedStyle(el);
			return {
				canvas: cs.getPropertyValue('--v-canvas').trim(),
				ink1: cs.getPropertyValue('--v-ink-1').trim(),
				textBase: cs.getPropertyValue('--v-text-base').trim(),
				bandGreen: cs.getPropertyValue('--v-band-green').trim(),
				fontMono: cs.getPropertyValue('--v-font-mono').replace(/\s+/g, ' ').trim()
			};
		};
		return {
			command: read('[data-theme-preview="command"]'),
			daylight: read('[data-theme-preview="daylight"]'),
			root: read('html')
		};
	}, DECLARED);

	const themesDiffer =
		normColor(parity.command.canvas) !== normColor(parity.daylight.canvas) &&
		normColor(parity.command.bandGreen) !== normColor(parity.daylight.bandGreen) &&
		parity.command.textBase !== parity.daylight.textBase;
	ok('themes differ (command vs daylight)', themesDiffer, JSON.stringify(parity.command));
	ok(
		'command tokens computed === declared',
		normColor(parity.command.canvas) === normColor(DECLARED.command['--v-canvas']) &&
			normColor(parity.command.bandGreen) === normColor(DECLARED.command['--v-band-green']) &&
			parity.command.textBase === DECLARED.command['--v-text-base'],
		`canvas=${parity.command.canvas} base=${parity.command.textBase}`
	);
	ok(
		'operator base text is 14 px (SPEC §2.2), computed and declared',
		parity.command.textBase === '14px' && DECLARED.command['--v-text-base'] === '14px' && parity.root.textBase === '14px',
		`preview=${parity.command.textBase} root=${parity.root.textBase} declared=${DECLARED.command['--v-text-base']}`
	);
	ok(
		'daylight tokens computed === declared (16px citizen base)',
		normColor(parity.daylight.canvas) === normColor(DECLARED.daylight['--v-canvas']) &&
			normColor(parity.daylight.bandGreen) === normColor(DECLARED.daylight['--v-band-green']) &&
			parity.daylight.textBase === DECLARED.daylight['--v-text-base'],
		`canvas=${parity.daylight.canvas} base=${parity.daylight.textBase}`
	);
	ok(
		'root defaults to command (first paint, no flash)',
		normColor(parity.root.canvas) === normColor(DECLARED.command['--v-canvas']),
		`root canvas=${parity.root.canvas}`
	);

	// ── 5: the BLACK chip — 1px hairline + translucent fill ──────────────
	const blackChip = await page.evaluate(() => {
		const el = document.querySelector('[data-prim="band-chip"][data-band="BLACK"]');
		if (!el) return null;
		const cs = getComputedStyle(el);
		const fill = cs.backgroundColor;
		let alpha = 1;
		const m = fill.match(/rgba?\([^)]*,\s*([\d.]+)\s*\)/);
		if (m) alpha = parseFloat(m[1]);
		return {
			borderTopWidth: cs.borderTopWidth,
			borderTopStyle: cs.borderTopStyle,
			borderTopColor: norm0(cs.borderTopColor),
			fill,
			alpha
		};
		function norm0(c) {
			return c.replace(/\s+/g, '').toLowerCase();
		}
	});
	ok(
		'BLACK chip: 1px hairline + translucent fill (never an opaque void)',
		blackChip !== null &&
			blackChip.borderTopWidth === '1px' &&
			blackChip.borderTopStyle === 'solid' &&
			blackChip.alpha < 1 &&
			blackChip.alpha > 0,
		blackChip
			? `border=${blackChip.borderTopWidth} ${blackChip.borderTopStyle} ${blackChip.borderTopColor} fill=${blackChip.fill} alpha=${blackChip.alpha}`
			: 'chip not found'
	);

	// ── 6: modal open + Escape close (focus trap mounts) ────────────────
	await page.evaluate(() => {
		const btns = Array.from(document.querySelectorAll('button'));
		(document.querySelector('[data-design-legacy="modal"]') ?? btns.find((b) => /open evidence modal/i.test(b.textContent ?? '')))?.click();
	});
	await sleep(400);
	let modalCount = await page.evaluate(() => document.querySelectorAll('[data-prim="modal"]').length);
	ok('modal opens', modalCount === 1, `count=${modalCount}`);
	await page.keyboard.press('Escape');
	await sleep(300);
	modalCount = await page.evaluate(() => document.querySelectorAll('[data-prim="modal"]').length);
	ok('modal closes on Escape', modalCount === 0, `count=${modalCount}`);

	// ── 7: toast push renders in the region ─────────────────────────────
	await page.evaluate(() => {
		const btns = Array.from(document.querySelectorAll('button'));
		(document.querySelector('[data-design-legacy="toast-act"]') ?? btns.find((b) => /toast · act/i.test(b.textContent ?? '')))?.click();
	});
	await sleep(400);
	const toast = await page.evaluate(() => ({
		count: document.querySelectorAll('[data-shell="toaster"] [data-ui="toast"]').length,
		region: document.querySelector('[data-shell="toaster"]')?.getAttribute('data-ui') ?? null
	}));
	ok(
		"toast pushes and renders in the shell's region (src/lib/ui Toaster wired to the toast store)",
		toast.count === 1 && toast.region === 'toaster',
		JSON.stringify(toast)
	);

	// ── 10: src/lib/ui — every primitive, both themes, overlays ──────────
	{
		const STATIC = UI_NAMES.filter((n) => !OVERLAY_NAMES.has(n));
		const counts = await page.evaluate((names) => {
			const out = {};
			for (const n of names) {
				out[n] = {
					command: document.querySelectorAll(`[data-specimen-theme="command"] [data-ui="${n}"]`).length,
					daylight: document.querySelectorAll(`[data-specimen-theme="daylight"] [data-ui="${n}"]`).length
				};
			}
			return out;
		}, STATIC);
		const missing = STATIC.filter((n) => !(counts[n].command > 0 && counts[n].daylight > 0));
		ok(
			`ui: every static src/lib/ui primitive mounts in BOTH theme columns (${STATIC.length} of ${UI_NAMES.length}; the ${OVERLAY_NAMES.size} overlays open below)`,
			UI_NAMES.length >= 40 && missing.length === 0,
			missing.map((n) => `${n} c=${counts[n].command} d=${counts[n].daylight}`).join(' | ') || STATIC.join(' ')
		);

		const themed = await page.evaluate(() => {
			const bg = (sel) => {
				const el = document.querySelector(sel);
				return el ? getComputedStyle(el).backgroundColor : null;
			};
			return {
				command: bg('[data-specimen-theme="command"] [data-ui="button"].primary'),
				daylight: bg('[data-specimen-theme="daylight"] [data-ui="button"]:not(.primary):not(.minimal):not(.outlined)'),
				commandDefault: bg('[data-specimen-theme="command"] [data-ui="button"]:not(.primary):not(.minimal):not(.outlined)')
			};
		});
		ok(
			'ui: the theme columns really differ (a default button is dark in command, light in daylight)',
			!!themed.commandDefault && !!themed.daylight && themed.commandDefault !== themed.daylight,
			JSON.stringify(themed)
		);

		const prov = await page.evaluate(() => {
			const el = document.querySelector('[data-specimen-theme="command"] [data-design="prov-compact"]');
			const rect = el?.getBoundingClientRect();
			const osint = document.querySelector('[data-specimen-theme="command"] [data-ui="provenance-tag"][data-source="osint"][data-verification="NEWS-REPORTED"]');
			return {
				text: el?.textContent?.trim() ?? null,
				source: el?.getAttribute('data-source') ?? null,
				width: rect?.width ?? 0,
				osint: osint?.textContent?.trim() ?? null
			};
		});
		ok(
			'ui: compact ProvenanceTag — 16 px glyph with a hidden text label read through textContent (X2)',
			prov.text === 'Emulated' && prov.source === 'emulated' && prov.width > 0 && prov.osint === 'News-reported',
			JSON.stringify(prov)
		);

		const vt = await page.evaluate(() => ({
			rows: document.querySelectorAll('[data-design="virtual-table"] tr.row').length,
			count: Number(document.querySelector('[data-design="virtual-table"] table')?.getAttribute('aria-rowcount') ?? 0)
		}));
		ok('ui: DataTable virtualises past 200 rows (500 rows, a small DOM)', vt.count === 501 && vt.rows > 0 && vt.rows < 80, JSON.stringify(vt));

		// colour roles (SPEC §2.4, §1.7): the gallery is the reference later slices copy
		const roles = await page.evaluate(() => {
			const out = { coloured: [], verbs: [], decision: null, tags: null, callouts: null };
			for (const th of ['command', 'daylight']) {
				for (const b of document.querySelectorAll(`[data-specimen-theme="${th}"] [data-ui="button"]`)) {
					const hue = ['success', 'warning', 'danger'].find((c) => b.classList.contains(c));
					const where = b.closest('[data-design="button-intents"]') ? 'intents' : b.getAttribute('data-design') ?? '';
					if (hue && where !== 'intents' && !(hue === 'warning' && where === 'inbox-decision') && !(hue === 'danger' && where === 'inbox-watchlist')) {
						out.coloured.push(`${th}:${hue}:${b.textContent?.trim()}`);
					}
					if (/^(reject|dismiss|cancel|keep it)/i.test(b.textContent?.trim() ?? '') && ['primary', 'success', 'warning', 'danger'].some((c) => b.classList.contains(c))) {
						out.verbs.push(`${th}:${b.textContent?.trim()}`);
					}
				}
			}
			const row = document.querySelector('[data-specimen-theme="command"] [data-design="decision-row"]');
			const btns = row ? Array.from(row.querySelectorAll('[data-ui="button"]')) : [];
			const reject = btns.findIndex((b) => b.getAttribute('data-design-decision') === 'reject');
			const approve = btns.findIndex((b) => b.getAttribute('data-design-decision') === 'approve');
			out.decision = {
				primaries: btns.filter((b) => b.classList.contains('primary')).length,
				rejectNeutral: reject >= 0 && !['primary', 'success', 'warning', 'danger'].some((c) => btns[reject].classList.contains(c)),
				rejectLeftOfPrimary: reject >= 0 && approve > reject && btns[approve].classList.contains('primary')
			};
			const active = document.querySelector('[data-specimen-theme="command"] [data-design-tag="active"]');
			out.tags = { activeClass: active?.className ?? null };
			const intentOf = (sel) => document.querySelector(`[data-specimen-theme="command"] ${sel}`)?.getAttribute('data-intent') ?? null;
			out.callouts = { feedLost: intentOf('[data-design-callout="feed-lost"]'), exercise: intentOf('[data-design-callout="exercise"]') };
			return out;
		});
		ok(
			'colour roles: decision verbs are neutral, left of ONE primary; success/warning/danger fills only in the intents row and the Inbox states',
			roles.coloured.length === 0 && roles.verbs.length === 0 && roles.decision.primaries === 1 && roles.decision.rejectNeutral && roles.decision.rejectLeftOfPrimary,
			JSON.stringify(roles.coloured.length || roles.verbs.length ? { coloured: roles.coloured, verbs: roles.verbs } : roles.decision)
		);
		ok(
			'colour roles: a data state (Active) is a neutral tag; Feed lost and Exercise data are neutral callouts',
			roles.tags.activeClass !== null && !/\bi-(primary|success|warning|danger)\b/.test(roles.tags.activeClass) && roles.callouts.feedLost === 'none' && roles.callouts.exercise === 'none',
			JSON.stringify(roles)
		);

		// the 12 px operator floor on rendered text (component CSS included)
		const floor = await page.evaluate(() => {
			const small = [];
			for (const el of document.querySelectorAll('[data-specimen-theme="command"] *')) {
				const own = Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim() !== '');
				if (!own) continue;
				const fs = parseFloat(getComputedStyle(el).fontSize);
				if (fs < 12) small.push(`${el.tagName.toLowerCase()}.${String(el.className).split(' ')[0]}="${el.textContent.trim().slice(0, 16)}" ${fs}px`);
			}
			const sfx = Array.from(document.querySelectorAll('[data-specimen-theme="command"] [data-design="small-times"] .sfx')).map((s) => parseFloat(getComputedStyle(s).fontSize));
			return { small, sfx };
		});
		ok(
			'type floor: no text in the command specimens renders under 12 px (the IST suffix stays at 12 px in a 12 px line)',
			floor.small.length === 0 && floor.sfx.length === 2 && floor.sfx.every((v) => v >= 12),
			floor.small.slice(0, 4).join(' | ') || `suffixes ${floor.sfx.join(', ')} px`
		);

		// one selection veil per DataTable row (no double veil from the global rule)
		await page.mouse.move(2, 2);
		const veil = await page.evaluate(() => {
			const tr = document.querySelector('[data-specimen-theme="command"] [data-design="sightings-table"] tr.row.is-selected');
			if (!tr) return null;
			const tds = Array.from(tr.querySelectorAll(':scope > td'));
			// resolve the token through a probe in the same theme (a minified build
			// serialises the declared value differently: "rgba(45, 114, 210, .2)")
			const probe = document.createElement('div');
			probe.style.backgroundColor = 'var(--v-primary-veil)';
			tr.closest('[data-specimen-theme]').appendChild(probe);
			const veil = getComputedStyle(probe).backgroundColor;
			probe.remove();
			return {
				row: getComputedStyle(tr).backgroundColor,
				cells: [...new Set(tds.map((td) => getComputedStyle(td).backgroundColor))],
				veil
			};
		});
		ok(
			'ui: a selected DataTable row carries ONE primary veil (on the row; its cells stay clear)',
			!!veil && veil.cells.length === 1 && /rgba\(0, 0, 0, 0\)|transparent/.test(veil.cells[0]) && normColor(veil.row) === normColor(veil.veil),
			JSON.stringify(veil)
		);

		// the type scale prints what each theme renders
		const scale = await page.evaluate(() =>
			Array.from(document.querySelectorAll('[data-ts-sample]')).map((el) => {
				const cs = getComputedStyle(el);
				const [size, line, weight] = (el.getAttribute('data-ts-sample') ?? '').match(/\d+/g) ?? [];
				const th = el.closest('[data-specimen-theme]')?.getAttribute('data-specimen-theme');
				const got = `${parseFloat(cs.fontSize)}/${parseFloat(cs.lineHeight)}/${cs.fontWeight}`;
				return { th, want: `${size}/${line}/${weight}`, got };
			})
		);
		const scaleBad = scale.filter((s) => s.want !== s.got);
		ok(
			'foundations: the type scale prints the size, line height and weight each theme renders',
			scale.length === 12 && scaleBad.length === 0 && new Set(scale.map((s) => s.th)).size === 2,
			scaleBad.map((s) => `${s.th} printed ${s.want} rendered ${s.got}`).join(' | ') || `${scale.length} samples`
		);

		// property rows are 30 px (SPEC §3.6)
		const props = await page.evaluate(() =>
			Array.from(document.querySelectorAll('[data-design-section="data"] [data-specimen-theme="command"] [data-ui="property-table"] tbody tr:not(.grp)')).map(
				(tr) => Math.round(tr.getBoundingClientRect().height * 100) / 100
			)
		);
		ok('ui: PropertyTable rows are 30 px in the command theme', props.length > 0 && props.every((h) => h === 30), `${props.length} rows: ${[...new Set(props)].join(', ')} px`);

		// provenance never borrows another source's label
		const provFb = await page.evaluate(() => {
			const unk = document.querySelector('[data-specimen-theme="command"] [data-design="prov-unknown"]');
			const live = document.querySelector('[data-specimen-theme="command"] [data-design="prov-live"]');
			return {
				unknown: unk?.textContent?.trim() ?? null,
				source: unk?.getAttribute('data-source') ?? null,
				liveTags: live ? live.querySelectorAll('[data-ui="provenance-tag"]').length : -1
			};
		});
		ok(
			"ui: an unrecognised provenance reads 'Unknown source' (raw data-source kept); a live row carries no tag",
			provFb.unknown === 'Unknown source' && provFb.source === 'fixture' && provFb.liveTags === 0,
			JSON.stringify(provFb)
		);

		// a removable CompoundTag (SPEC §5.1 `removable`): its ✕ removes that filter only
		{
			const chipState = () =>
				page.evaluate(() => {
					const list = (th) => Array.from(document.querySelectorAll(`[data-specimen-theme="${th}"] [data-design="filter-chips"] [data-ui="compound-tag"]`));
					const cmd = list('command');
					return {
						command: cmd.map((c) => c.getAttribute('data-design-chip')),
						daylight: list('daylight').length,
						crosses: cmd.filter((c) => c.querySelector('.v button[aria-label="Remove"]')).length
					};
				});
			const before = await chipState();
			await (await page.$('[data-specimen-theme="command"] [data-design-chip="Kind"] button[aria-label="Remove"]'))?.click();
			await sleep(200);
			const after = await chipState();
			await (await page.$('[data-specimen-theme="command"] [data-design="reset-filters"]'))?.click();
			await sleep(200);
			const reset = await chipState();
			ok(
				'ui: a removable CompoundTag carries a Remove ✕ that fires onremove (that filter only, in its column)',
				before.command.length === 3 &&
					before.crosses === 3 &&
					after.command.join() === 'Window,List' &&
					after.daylight === 3 &&
					reset.command.length === 3,
				JSON.stringify({ before, after, reset: reset.command })
			);
		}

		// a zero recedes (SPEC §3.2) whatever the intent: never an orange "0 waiting"
		{
			const zeros = await page.evaluate(() =>
				Array.from(document.querySelectorAll('[data-specimen-theme] [data-ui="metric-card"][data-zero="true"]')).map((card) => {
					const probe = document.createElement('span');
					probe.style.color = 'var(--v-ink-2)';
					card.appendChild(probe);
					const ink2 = getComputedStyle(probe).color;
					probe.remove();
					const val = getComputedStyle(card.querySelector('.val'));
					return {
						th: card.closest('[data-specimen-theme]').getAttribute('data-specimen-theme'),
						intent: (String(card.className).match(/\bi-(warning|danger|success|primary)\b/) ?? [])[1] ?? 'none',
						caption: card.querySelector('.cap')?.textContent?.trim(),
						recedes: val.color === ink2 && val.fontWeight === '400',
						color: val.color
					};
				})
			);
			const bad = zeros.filter((z) => !z.recedes);
			const withIntent = new Set(zeros.filter((z) => z.intent !== 'none').map((z) => `${z.th}:${z.intent}`));
			ok(
				'ui: a zero MetricCard value is ink-2 at 400 whatever its intent ("Decisions waiting 0" with intent warning)',
				zeros.length >= 6 && bad.length === 0 && ['command:warning', 'command:danger', 'daylight:warning', 'daylight:danger'].every((k) => withIntent.has(k)),
				bad.map((z) => `${z.th} ${z.caption} (${z.intent}) ${z.color}`).join(' | ') || `${zeros.length} zero cards, intents ${[...withIntent].join(' ')}`
			);
		}

		// one roving tab stop per Tree; a collapsible Section's heading holds its toggle
		{
			const a11y = await page.evaluate(() => ({
				trees: Array.from(document.querySelectorAll('[data-specimen-theme] [data-ui="tree"]')).map((t) => t.querySelectorAll('[data-tree-row][tabindex="0"]').length),
				sections: Array.from(document.querySelectorAll('[data-ui="section"] button[aria-expanded]')).map((b) => ({
					inHeading: !!b.parentElement?.matches('h2, h3, h4, h5, h6'),
					headingInside: !!b.querySelector('h1, h2, h3, h4, h5, h6'),
					labelled: !!document.getElementById(b.closest('[data-ui="section"]').getAttribute('aria-labelledby') ?? '')?.closest('button')
				}))
			}));
			ok(
				'ui: every Tree has exactly ONE tab stop (roving tabindex)',
				a11y.trees.length >= 2 && a11y.trees.every((n) => n === 1),
				`tab stops per tree: ${a11y.trees.join(', ')}`
			);
			ok(
				'ui: a collapsible Section is a disclosure: <hN><button aria-expanded>, no heading inside the button',
				a11y.sections.length >= 3 && a11y.sections.every((x) => x.inHeading && !x.headingInside && x.labelled),
				JSON.stringify(a11y.sections)
			);
		}

		// overlays: open, assert, Escape closes the topmost, focus returns
		const openClose = async (trigger, sel, label, extra) => {
			const btn = await page.$(trigger);
			if (!btn) {
				ok(`ui: ${label} opens and closes on Escape`, false, `trigger ${trigger} not found`);
				return;
			}
			await btn.click();
			const shown = await page.waitForSelector(sel, { timeout: 4000 }).then(() => true).catch(() => false);
			const info = shown ? await page.evaluate(extra ?? (() => ({})), sel) : {};
			await page.keyboard.press('Escape');
			await sleep(300);
			const after = await page.evaluate((s) => ({ left: document.querySelectorAll(s).length, focus: document.activeElement?.getAttribute('data-design-open') ?? null }), sel);
			ok(`ui: ${label} opens and closes on Escape`, shown && after.left === 0 && (info.ok ?? true), `${JSON.stringify(info)} · after=${JSON.stringify(after)}`);
			return after;
		};
		const theme = (sel) => {
			const el = document.querySelector(sel);
			return { theme: el?.closest('[data-theme]')?.getAttribute('data-theme') ?? null, ok: !!el };
		};
		const dlg = await openClose('[data-specimen-theme="command"] [data-design-open="dialog"]', '[data-ui="dialog"]', 'Dialog', theme);
		ok('ui: Dialog gives focus back to its opener', dlg?.focus === 'dialog', `focus=${dlg?.focus}`);
		await openClose('[data-specimen-theme="command"] [data-design-open="alert"]', '[data-ui="alert"]', 'Alert', theme);
		await openClose('[data-specimen-theme="command"] [data-design-open="drawer"]', '[data-ui="drawer"]', 'Drawer', theme);
		await openClose('[data-specimen-theme="command"] [data-design-open="hotkeys"]', '[data-ui="hotkeys-dialog"]', 'HotkeysDialog (with its no-single-key rule)', (sel) => {
			const t = document.querySelector(sel)?.closest('[data-ui="dialog"]')?.textContent ?? '';
			return { ok: /No single key approves, unmasks, penalises, dispatches or publishes/.test(t) };
		});
		await openClose('[data-specimen-theme="daylight"] [data-design-open="popover"]', '[data-ui="popover"]', 'Popover (a Menu, portalled with its daylight theme)', (sel) => {
			const el = document.querySelector(sel);
			return {
				theme: el?.getAttribute('data-theme'),
				menu: !!el?.querySelector('[data-ui="menu"]'),
				ok: el?.getAttribute('data-theme') === 'daylight' && !!el?.querySelector('[data-ui="menu"]')
			};
		});

		// nesting: a popover opened from inside a popover keeps its parent open
		// (a pointer inside an overlay above is never "outside" the one below)
		{
			const click = async (sel) => (await page.$(sel))?.click();
			await click('[data-specimen-theme="command"] [data-design-open="nested"]');
			const parentShown = await page.waitForSelector('[data-design-popover="parent"]', { timeout: 4000 }).then(() => true).catch(() => false);
			await sleep(150);
			await click('[data-design-popover="parent"] [data-design-open="nested-child"]');
			const childShown = await page.waitForSelector('[data-design-popover="child"]', { timeout: 4000 }).then(() => true).catch(() => false);
			await sleep(150);
			await click('[data-design-popover="child"] [data-design-window="24h"]');
			await sleep(300);
			const state = await page.evaluate(() => ({
				parent: document.querySelectorAll('[data-design-popover="parent"]').length,
				child: document.querySelectorAll('[data-design-popover="child"]').length,
				label: document.querySelector('[data-design-popover="parent"] [data-design-open="nested-child"]')?.textContent?.trim() ?? null
			}));
			await page.keyboard.press('Escape');
			await sleep(300);
			const after = await page.evaluate(() => document.querySelectorAll('[data-design-popover="parent"]').length);
			ok(
				'ui: a popover opened inside a popover keeps its parent open while used; Escape then closes the parent',
				parentShown && childShown && state.parent === 1 && state.child === 0 && state.label === 'Last 24 hours' && after === 0,
				JSON.stringify({ parentShown, childShown, ...state, after })
			);
		}

		// keyboard-first (SPEC §1.9): a click popover takes focus once it shows
		{
			const ACTIONS = '[data-specimen-theme="command"] [data-design-open="popover"]';
			const where = () =>
				page.evaluate(() => {
					const a = document.activeElement;
					return {
						inPopover: !!a?.closest('[data-ui="popover"]'),
						item: a?.getAttribute('data-menu-item') ?? null,
						trigger: a?.getAttribute('data-design-open') ?? null,
						open: document.querySelectorAll('[data-ui="popover"]').length
					};
				});
			await page.focus(ACTIONS);
			await page.keyboard.press('Enter');
			await sleep(400);
			const opened = await where();
			await page.keyboard.press('ArrowDown');
			await sleep(100);
			const down = await where();
			await page.keyboard.press('Escape');
			await sleep(300);
			const escaped = await where();
			ok(
				"ui: Enter on a popover's target puts focus in its Menu (the current choice), ArrowDown walks it, Escape gives focus back",
				opened.inPopover && opened.item === 'w6' && down.item === 'w24' && escaped.open === 0 && escaped.trigger === 'popover',
				JSON.stringify({ opened, down, escaped })
			);
			await (await page.$(ACTIONS))?.click();
			await sleep(400);
			const clicked = await where();
			await page.keyboard.press('Tab');
			await sleep(300);
			const tabbed = await where();
			ok(
				'ui: a clicked-open popover has focus too; Tab past its Menu closes it and returns focus to the target',
				clicked.inPopover && clicked.item === 'w6' && tabbed.open === 0 && tabbed.trigger === 'popover',
				JSON.stringify({ clicked, tabbed })
			);
		}

		const tipTarget = await page.$('[data-specimen-theme="command"] [data-design-tooltip]');
		await tipTarget?.hover();
		const tip = await page.waitForSelector('[data-ui="tooltip"]', { timeout: 3000 }).then((el) => el.evaluate((e) => e.textContent?.trim())).catch(() => null);
		await page.mouse.move(2, 600);
		await sleep(300);
		const tipGone = await page.evaluate(() => document.querySelectorAll('[data-ui="tooltip"]').length === 0);
		ok('ui: Tooltip shows on hover and hides on leave (inverted, portalled)', !!tip && tipGone, `text=${tip}`);

		// the primitives' copy follows the language context (EN → HI → EN),
		// switched with the page's ONE language switch: the shell's (the top bar's menu, V3-P6B)
		const pick = async (code) => {
			if (!(await page.$('[data-v3="header-menu"]'))) await page.click('[data-testid="v3-header-menu"]');
			await page.waitForSelector(`[data-v3="header-menu"] [data-lang-code="${code}"]`, { timeout: 5000 });
			await page.click(`[data-v3="header-menu"] [data-lang-code="${code}"]`);
			await sleep(300);
			return page.evaluate(() => ({
				prov: document.querySelector('[data-specimen-theme="command"] [data-design="prov-compact"]')?.textContent?.trim() ?? null,
				html: document.documentElement.lang,
				// every language switch on the page (the menu is open): the shell's is the only one
				switches: document.querySelectorAll('[data-lang-code="hi"], button[lang="hi"]').length
			}));
		};
		const hi = await pick('hi');
		const en = await pick('en');
		await page.keyboard.press('Escape');
		await sleep(200);
		ok('ui: internal copy comes from packs.ui in the provided language (no store)', hi.prov === 'इम्युलेटेड' && en.prov === 'Emulated', `hi=${hi.prov} en=${en.prov}`);
		ok(
			"ui: ONE language switch (the shell's) drives the chrome and the primitives",
			hi.switches === 1 && en.switches === 1 && hi.html === 'hi' && en.html === 'en',
			JSON.stringify({ hi, en })
		);

		// SPEC §3.7's narrowest operator width: a DataTable never crushes a
		// column below its minimum; past the floor it scrolls sideways
		await page.setViewport({ width: 1366, height: 768 });
		await sleep(500);
		const narrow = await page.evaluate(() => {
			const out = { checked: 0, bad: [], road: [], clipped: [], scroll: [] };
			for (const th of document.querySelectorAll('[data-specimen-theme] [data-ui="data-table"] th[data-min-width]')) {
				const min = Number(th.getAttribute('data-min-width'));
				const w = th.getBoundingClientRect().width;
				const theme = th.closest('[data-specimen-theme]').getAttribute('data-specimen-theme');
				out.checked++;
				if (w + 0.5 < min) out.bad.push(`${theme}:${th.textContent.trim() || '(untitled)'} ${w.toFixed(1)} < ${min}`);
				if (th.textContent.trim() !== 'Road') continue;
				out.road.push(Math.round(w));
				// every road name in that column reads in full
				const col = Array.from(th.parentElement.children).indexOf(th);
				for (const tr of th.closest('table').querySelectorAll('tbody tr.row')) {
					const txt = tr.children[col]?.querySelector('.txt');
					if (txt && txt.scrollWidth > txt.clientWidth + 1) out.clipped.push(`${theme}:${txt.textContent}`);
				}
			}
			// (headless Chrome hides scrollbars, so the bar itself is not measured here)
			for (const t of document.querySelectorAll('[data-design="sightings-table"] [data-ui="data-table"]')) out.scroll.push(`${t.scrollWidth}/${t.clientWidth}`);
			return out;
		});
		await page.setViewport({ width: 1440, height: 1000 });
		await sleep(400);
		ok(
			'ui: at 1366 px no DataTable column is narrower than its minimum, and every road name reads in full (the table scrolls instead)',
			narrow.checked >= 20 && narrow.bad.length === 0 && narrow.road.length === 2 && narrow.road.every((w) => w >= 176) && narrow.clipped.length === 0,
			narrow.bad.concat(narrow.clipped).slice(0, 6).join(' | ') ||
				`${narrow.checked} columns at or over their minimum · Road ${narrow.road.join('/')} px · sightings scroll ${narrow.scroll.join(', ')}`
		);
	}

	// ── 13: the application shell on /design/shell (UI-S1B harness, fictional) ──
	{
		const shell = await designContext.newPage();
		if (session.gate) await shell.setCookie(...puppeteerCookies(session));
		const shellErrors = [];
		shell.on('pageerror', (e) => shellErrors.push(String(e).slice(0, 200)));
		for (const [w, h] of [
			[1920, 1080],
			[1680, 1050],
			[1440, 900],
			[1366, 768]
		]) {
			await shell.setViewport({ width: w, height: h });
			await shell.goto(`${origin}/design/shell`, { waitUntil: 'networkidle2', timeout: 60000 });
			await shell.waitForSelector('[data-testid="live-strip"]', { timeout: 15000 }).catch(() => null);
			await sleep(600);
			const nav = await shell.evaluate(() => {
				const top = document.querySelector('[data-v3="top-bar"]');
				const bar = document.querySelector('[data-shell="command-bar"]');
				const q = (sel) => bar?.querySelector(sel) ?? null;
				const posture = q('[data-testid="brain-posture"]');
				const band = q('[data-testid="band-tag"]');
				const strip = document.querySelector('[data-testid="live-strip"]');
				const search = top?.querySelector('[data-shell="command-search"]');
				return {
					overflow: document.documentElement.scrollWidth - window.innerWidth,
					topHeight: top ? Math.round(top.getBoundingClientRect().height) : 0,
					height: bar ? Math.round(bar.getBoundingClientRect().height) : 0,
					officer: top?.querySelector('[data-testid="v3-officer"]') ? 'pill' : null,
					inlineOfficer: !!document.querySelector('input[data-testid="duty-officer"]'),
					posture: posture ? { decider: posture.dataset.decider, tier: posture.dataset.tier, text: posture.textContent.replace(/\s+/g, ' ').trim() } : null,
					provenance: top?.querySelector('[data-testid="feed-provenance"]')?.getAttribute('data-label') ?? null,
					band: band ? { band: band.dataset.band, age: band.getAttribute('data-age-sec') } : null,
					search: search ? (search.disabled ? 'disabled' : 'button') : null,
					inbox: q('[data-inbox-intent]')?.getAttribute('data-count') ?? null,
					more: !!q('[aria-label="More"], [data-menu="more"]'),
					strip: strip
						? {
								clock: strip.querySelector('[data-live-clock]')?.textContent?.trim() ?? null,
								movement: !!strip.querySelector('[data-live-seg="movement"]'),
								pursuit: !!strip.querySelector('[data-live-seg="pursuit"]'),
								countdown: strip.querySelector('[data-live-seg="decision"] .cd')?.textContent?.trim() ?? null,
								review: strip.querySelector('[data-testid="interrupt"]')?.textContent?.trim() ?? null
							}
						: null
				};
			});
			// the band age TICKS: a second read 1.2 s later is larger (not a value read once)
			await sleep(1200);
			const age2 = await shell.evaluate(() => document.querySelector('[data-shell="command-bar"] [data-testid="band-tag"]')?.getAttribute('data-age-sec') ?? null);
			ok(
				`shell ${w}: band-tag data-age-sec ticks (two reads 1.2 s apart)`,
				Number(nav.band?.age) >= 12 && Number(age2) > Number(nav.band?.age),
				`${nav.band?.age} → ${age2}`
			);
			// V3 chrome (V3-P6B): the top bar is 68 px from 1500 px and 60 px below, the operator band 52 / 46 px
			const wantTop = w >= 1500 ? 68 : 60;
			const wantBand = w >= 1500 ? 52 : 46;
			ok(
				`shell ${w}: the V3 top bar (${wantTop} px) carries the search, the officer pill and feed-provenance; the operator band (${wantBand} px) carries brain-posture (data attributes + summary), band-tag, the Inbox and More; no inline duty-officer input; no horizontal overflow`,
				nav.overflow <= 0 &&
					nav.topHeight === wantTop &&
					nav.height === wantBand &&
					nav.officer === 'pill' &&
					!nav.inlineOfficer &&
					nav.posture?.decider === 'loaded' &&
					nav.posture?.tier === 'FULL' &&
					/p95 2\.3 s/.test(nav.posture?.text ?? '') &&
					/novelty check on/.test(nav.posture?.text ?? '') &&
					nav.provenance === 'simulated' &&
					nav.band?.band === 'GREEN' &&
					Number(nav.band?.age) >= 12 &&
					nav.search === 'button' &&
					nav.inbox === '2' &&
					nav.more,
				JSON.stringify({ ...nav, strip: undefined })
			);
			ok(
				`shell ${w}: the LiveStrip shows the IST clock, the movement, the pursuit and the 0:47 countdown with Review`,
				!!nav.strip && /^\d{2}:\d{2}:\d{2}$/.test(nav.strip.clock ?? '') && nav.strip.movement && nav.strip.pursuit && nav.strip.countdown === '0:47' && nav.strip.review === 'Review',
				JSON.stringify(nav.strip)
			);
			await checkOfficer(shell, w);
		}
		// '?' opens the shortcuts sheet: only keys that work here (Ctrl K with the page's omnibar; no dock or list keys)
		await shell.setViewport({ width: 1920, height: 1080 });
		await shell.goto(`${origin}/design/shell`, { waitUntil: 'networkidle2', timeout: 60000 });
		await shell.waitForSelector('[data-shell="command-bar"]', { timeout: 15000 });
		await sleep(500);
		await shell.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
		await shell.keyboard.press('?');
		const sheet = await shell
			.waitForSelector('[data-shell="hotkeys"]', { timeout: 5000 })
			.then(() => shell.evaluate(() => document.querySelector('[data-shell="hotkeys"]')?.textContent?.replace(/\s+/g, ' ') ?? ''))
			.catch(() => null);
		ok(
			"shell: '?' opens the shortcuts sheet listing only working keys (Ctrl K for the page's omnibar, '/', '?', Esc, G then H / M / D / P / A / V: the V3 rail's chords replace the v2 navbar's Alt 1–5)",
			!!sheet && /Ctrl\s*K/.test(sheet) && /G\s*H/.test(sheet) && /G\s*V/.test(sheet) && !/Alt\s*\d/.test(sheet) && !/dock|timeline|Next item/i.test(sheet),
			sheet ? sheet.slice(0, 160) : 'no sheet'
		);
		await shell.keyboard.press('Escape');
		ok('no page errors on /design/shell', shellErrors.length === 0, shellErrors.slice(0, 3).join(' | ') || 'none');
		await shell.close();

		// ── 13b: no control of the V3 chrome is ever clipped (every field + the legacy Share
		// and/or the operator gate's control; the gate is faked by answering GET
		// /api/session in this page only, so no PIN is involved). The v2 navbar FOLDED its
		// controls to fit; the V3 bars fold nothing (fixed controls, the title truncates),
		// so what is held is the outcome: nothing clipped, nothing overflowing ──
		const fitScenarios = [
			{ id: 'share', share: true, gate: null },
			{ id: 'share+gate-signed-out', share: true, gate: { officer: null } },
			{ id: 'gate-signed-in', share: false, gate: { officer: 'Insp. Fit Check Longname (fictional)' } }
		];
		for (const sc of fitScenarios) {
			const ctx = await browser.createBrowserContext();
			const fp = await ctx.newPage();
			const fitErrors = [];
			fp.on('pageerror', (e) => fitErrors.push(String(e).slice(0, 200)));
			if (session.gate && !sc.gate) await fp.setCookie(...puppeteerCookies(session));
			if (sc.gate) {
				await fp.setRequestInterception(true);
				fp.on('request', (req) => {
					if (req.method() === 'GET' && new URL(req.url()).pathname === '/api/session') {
						return req.respond({ status: 200, contentType: 'application/json', body: JSON.stringify({ gate: true, officer: sc.gate.officer, expires_at: null }) });
					}
					return req.continue();
				});
			}
			await fp.setViewport({ width: 1680, height: 1050 });
			await fp.goto(`${origin}/design/shell${sc.share ? '?share=1' : ''}`, { waitUntil: 'networkidle2', timeout: 60000 });
			await fp.waitForSelector('[data-testid="live-strip"]', { timeout: 15000 }).catch(() => null);
			if (sc.gate && sc.gate.officer) await fp.waitForFunction((n) => document.querySelector('[data-v3="top-bar"] [data-testid="v3-officer"]')?.textContent?.includes(n), { timeout: 15000 }, sc.gate.officer).catch(() => null);
			const rows = [];
			let bad = 0;
			for (const w of [1920, 1760, 1680, 1600, 1440, 1366, 1280]) {
				await fp.setViewport({ width: w, height: 900 });
				await sleep(400);
				const m = await fp.evaluate(() => {
					const top = document.querySelector('[data-v3="top-bar"]');
					const bar = document.querySelector('[data-shell="command-bar"]');
					const clippedIn = (root) => {
						const r = root.getBoundingClientRect();
						return [...root.querySelectorAll('button, a, input, [data-testid]')]
							.filter((el) => el.getClientRects().length > 0 && el.getBoundingClientRect().width > 0)
							.filter((el) => el.getBoundingClientRect().right > r.right + 0.5 || el.getBoundingClientRect().left < r.left - 0.5)
							.map((el) => el.getAttribute('data-testid') ?? el.getAttribute('data-shell') ?? el.getAttribute('aria-label') ?? el.tagName);
					};
					const lastRight = (root) => Math.max(...[...root.children].filter((c) => c.getBoundingClientRect().width > 0).map((c) => c.getBoundingClientRect().right));
					const pol = bar.querySelector('.policies .lbl');
					const pill = top.querySelector('[data-testid="v3-officer"]');
					return {
						search: Math.round(top.querySelector('[data-shell="command-search"]')?.getBoundingClientRect().width ?? 0),
						topEnd: Math.round(lastRight(top)),
						topRight: Math.round(top.getBoundingClientRect().right),
						barEnd: Math.round(lastRight(bar)),
						barRight: Math.round(bar.getBoundingClientRect().right),
						clipped: [...clippedIn(top), ...clippedIn(bar)],
						policies: !!pol && getComputedStyle(pol).display !== 'none',
						pill: pill?.textContent?.replace(/\s+/g, ' ').trim() ?? null,
						share: !!top.querySelector('.share, [data-share]') || !!bar.querySelector('.share, [data-share]'),
						overflow: document.documentElement.scrollWidth - window.innerWidth
					};
				});
				const good =
					m.topEnd <= m.topRight &&
					m.barEnd <= m.barRight &&
					m.clipped.length === 0 &&
					m.search >= 240 &&
					m.overflow <= 0 &&
					m.policies &&
					// the legacy Share (a page still supplying onShare) is drawn nowhere in the chrome: it lives in the view header
					!m.share &&
					// the long signed-in name shows in the pill (truncated by the pill, never by the bar)
					(!sc.gate?.officer || (m.pill ?? '').includes(sc.gate.officer));
				if (!good) bad++;
				rows.push(`${w}:${good ? '' : 'BAD '}search ${m.search} top ${m.topEnd}/${m.topRight} band ${m.barEnd}/${m.barRight}${m.clipped.length ? ` clipped ${m.clipped.join('+')}` : ''}`);
			}
			ok(
				`shell fit (${sc.id}): from 1280 to 1920 px both bars end inside their box, no control is clipped, the search stays ≥ 240 px, the Policies label stays and the legacy Share is drawn nowhere in the chrome`,
				bad === 0 && fitErrors.length === 0,
				rows.join(' · ') + (fitErrors.length ? ` · page errors: ${fitErrors.slice(0, 2).join(' | ')}` : '')
			);
			await ctx.close();
		}

		// ── 13c: the rebuilt primitives in squeezed hosts never spill or squeeze ──
		const sq = await designContext.newPage();
		if (session.gate) await sq.setCookie(...puppeteerCookies(session));
		const sqErrors = [];
		sq.on('pageerror', (e) => sqErrors.push(String(e).slice(0, 200)));
		for (const [w, h] of [
			[1440, 900],
			[1366, 768]
		]) {
			await sq.setViewport({ width: w, height: h });
			await sq.goto(`${origin}/design/shell?squeeze=1`, { waitUntil: 'networkidle2', timeout: 60000 });
			await sq.waitForSelector('[data-design="squeeze-rail"] [data-prim="panel"]', { timeout: 15000 }).catch(() => null);
			await sq.evaluate(() => document.querySelector('[data-design="squeeze"]')?.scrollIntoView({ block: 'start' }));
			await sleep(400);
			const m = await sq.evaluate(() => {
				const rail = document.querySelector('[data-design="squeeze-rail"]');
				const feed = document.querySelector('[data-design="squeeze-feed"]');
				if (!rail || !feed) return null;
				/** Elements of `panel` drawn below its box with no clipping ancestor up to the panel (they paint over the next one). */
				const spills = (panel) => {
					const box = panel.getBoundingClientRect();
					const out = [];
					for (const el of panel.querySelectorAll('*')) {
						const r = el.getBoundingClientRect();
						if (!r.height || r.bottom <= box.bottom + 0.5) continue;
						let clipped = false;
						for (let a = el.parentElement; a && a !== panel.parentElement; a = a.parentElement) {
							const cs = getComputedStyle(a);
							if (cs.overflowY !== 'visible' || cs.overflowX !== 'visible') {
								clipped = true;
								break;
							}
						}
						if (!clipped) out.push((el.textContent ?? '').trim().slice(0, 30) || el.tagName);
					}
					return out;
				};
				const panels = [...rail.querySelectorAll(':scope > [data-prim="panel"]')];
				const [p1, p2] = panels;
				const scroller = p1?.querySelector('.body.scroll');
				const title2 = p2?.querySelector('h2');
				const t2 = title2?.getBoundingClientRect();
				const hit = t2 ? document.elementFromPoint(t2.left + Math.min(20, t2.width / 2), t2.top + t2.height / 2) : null;
				const rows = [...feed.querySelectorAll('[data-prim="feed-item"]')];
				const squeezed = rows.filter((r) => r.scrollHeight > r.clientHeight + 1).map((r) => `${Math.round(r.clientHeight)}/${r.scrollHeight}`);
				return {
					panels: panels.map((p) => Math.round(p.getBoundingClientRect().height)),
					inRail: panels.every((p) => p.getBoundingClientRect().bottom <= rail.getBoundingClientRect().bottom + 0.5),
					spill1: p1 ? spills(p1) : ['no panel'],
					spill2: p2 ? spills(p2) : ['no panel'],
					scrolls: scroller ? scroller.scrollHeight > scroller.clientHeight && scroller.getBoundingClientRect().bottom <= p1.getBoundingClientRect().bottom + 0.5 : false,
					titleOnTop: !!hit && !!p2 && p2.contains(hit),
					rows: rows.length,
					squeezed,
					feedScrolls: feed.scrollHeight > feed.clientHeight
				};
			});
			ok(
				`shell squeeze ${w}: two panels in a fixed-height rail stay in their boxes (the scrolling body scrolls inside its panel, the glass panel clips; nothing paints over the next panel's title)`,
				!!m && m.inRail && m.spill1.length === 0 && m.spill2.length === 0 && m.scrolls && m.titleOnTop,
				m ? JSON.stringify({ panels: m.panels, spill1: m.spill1.slice(0, 3), spill2: m.spill2.slice(0, 3), scrolls: m.scrolls, titleOnTop: m.titleOnTop }) : 'no fixture'
			);
			ok(
				`shell squeeze ${w}: audit rows in a fixed-height scroller keep their height (none squeezed under its text; the scroller scrolls)`,
				!!m && m.rows >= 6 && m.squeezed.length === 0 && m.feedScrolls,
				m ? `${m.rows} rows, squeezed ${m.squeezed.length ? m.squeezed.join(', ') : 'none'}, scroller scrolls ${m.feedScrolls}` : 'no fixture'
			);
		}
		ok('no page errors on /design/shell?squeeze=1', sqErrors.length === 0, sqErrors.slice(0, 3).join(' | ') || 'none');
		await sq.close();
	}

	// ── 12: fictional data only — masked marks, no full mark in the text ──
	{
		const plates = await page.evaluate(() => ({
			marks: Array.from(document.querySelectorAll('[data-ui="plate"]')).map((p) => ({ text: p.textContent?.trim(), masked: p.getAttribute('data-masked') })),
			text: document.querySelector('[data-design="gallery"]')?.innerText ?? ''
		}));
		const bad = plates.marks.filter((p) => p.masked !== 'true' || !/^MH\d{2}[A-Z]{1,3}•{3}\d$/.test(p.text ?? ''));
		const full = plates.text.match(/\bGJ\s?\d{2}\s?[A-Z]{1,3}\s?\d{3,4}\b/g) ?? [];
		ok(
			'fictional data: every Plate on /design is a masked mark (MH01XX•••7) and no full registration mark appears',
			plates.marks.length > 0 && bad.length === 0 && full.length === 0,
			`${plates.marks.length} plates, e.g. ${plates.marks[0]?.text}${bad.length ? ` · bad=${JSON.stringify(bad.slice(0, 2))}` : ''}${full.length ? ` · full marks=${full.length}` : ''}`
		);
	}

	// ── 8: reduced motion calms the deck (doctrine) ─────────────────────
	await page.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'reduce' }]);
	const reduced = await page.evaluate(() => {
		const root = getComputedStyle(document.documentElement);
		// switch the masthead to BLACK so the breathing hairline exists
		const black =
			document.querySelector('[data-band-cycle="BLACK"]') ??
			Array.from(document.querySelectorAll('button')).find((b) => /^black$/i.test(b.textContent?.trim() ?? ''));
		black?.click();
		const mast = document.querySelector('[data-prim="band-masthead"]');
		const hair = mast ? getComputedStyle(mast.querySelector('.hairline')) : null;
		return {
			wipe: root.getPropertyValue('--v-dur-wipe').trim(),
			breathe: root.getPropertyValue('--v-dur-breathe').trim(),
			hairAnimation: hair ? hair.animationName : 'none',
			button: black?.textContent?.trim() ?? null
		};
	});
	await page.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'no-preference' }]);
	ok(
		'reduced motion: wipe → 64ms, breathing → static hairline',
		reduced.wipe === '64ms' && reduced.breathe === '0ms' && reduced.hairAnimation === 'none' && reduced.button === 'Black',
		JSON.stringify(reduced)
	);
	const full = await page.evaluate(() => {
		const root = getComputedStyle(document.documentElement);
		const mast = document.querySelector('[data-prim="band-masthead"]');
		const hair = getComputedStyle(mast.querySelector('.hairline'));
		return { wipe: root.getPropertyValue('--v-dur-wipe').trim(), hairAnimation: hair.animationName, band: mast.getAttribute('data-band') };
	});
	// Chrome serializes 600ms as ".6s" and prefixes scoped keyframes
	// ("svelte-xxxx-breathe") — compare semantically, not textually.
	const wipeMs = full.wipe.endsWith('ms')
		? parseFloat(full.wipe)
		: Math.round(parseFloat(full.wipe) * 1000);
	ok(
		'motion restored: 600ms wipe + BLACK breathing hairline (the only breathing element)',
		wipeMs === 600 && full.hairAnimation.includes('breathe') && full.band === 'BLACK',
		JSON.stringify(full)
	);

	// ── 9: '/' opens the page's omnibar ──────────────────────────────────
	// V3-P6B: the navbar's own route-search field is retired with the navbar; the V3 top bar's one search opens the
	// page's omnibar (which holds the routes). The behaviour the assertion held — '/' reaches search from anywhere — is
	// checked on the page that has an omnibar, the workspace, and the search control is the shell's one.
	{
		const ws = await designContext.newPage();
		if (session.gate) await ws.setCookie(...puppeteerCookies(session));
		await ws.setViewport({ width: 1440, height: 900 });
		await ws.goto(`${origin}${WORKSPACE}`, { waitUntil: 'networkidle2', timeout: 60000 });
		await ws.waitForFunction(() => document.querySelector('[data-shell="command-search"]') && !document.querySelector('[data-shell="command-search"]').disabled, { timeout: 30000 }).catch(() => null);
		await sleep(1500);
		await ws.evaluate(() => (document.activeElement instanceof HTMLElement ? document.activeElement.blur() : null));
		await ws.keyboard.press('/');
		const opened = await ws.waitForSelector('[data-testid="palette-input"]', { visible: true, timeout: 15000 }).then(() => true).catch(() => false);
		await ws.keyboard.press('Escape');
		const searches = await ws.evaluate(() => document.querySelectorAll('[data-shell="command-search"]').length);
		ok("keyboard: '/' opens the omnibar (the top bar's one search control)", opened && searches === 1, `omnibar=${opened} controls=${searches}`);
		await ws.close();
	}

	ok(
		'no page errors on /design',
		consoleErrors.length === 0,
		consoleErrors.slice(0, 3).join(' | ') || 'none'
	);
} finally {
	await signOut(session);
	await browser.close().catch(() => {});
	if (deckProc) deckProc.kill();
}

if (failures > 0) {
	console.error(`design-smoke: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('ok   design-smoke — all assertions passed');
process.exit(0);
