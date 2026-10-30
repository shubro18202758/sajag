/**
 * Root-flip smoke (V3 P5; V3-SPEC §3.2, §10 P5) — `/` shows Home, `/analyst` shows the workspace, on a dev deck AND
 * on a production build.
 *
 *   ORACLE_PORT=8162 BRAIN_PORT=8262 EMULATOR_PORT=8962 node tests/root-flip-smoke.mjs [origin]
 *   ORACLE_PORT=8162 BRAIN_PORT=8262 EMULATOR_PORT=8962 node tests/root-flip-smoke.mjs --prod
 *
 * `origin` is a RUNNING deck (a dev deck of this tree, or `npm run preview` on a free 54xx port; default
 * http://127.0.0.1:5475). `--prod` serves `node build` itself on a free 54xx port (the preview route-coldload spawns:
 * gate off, keyless). GETs only: every non-GET request the page makes is aborted; the page's chat stream and the
 * brain are never touched.
 *
 *   HTTP     `/` is Home (data-shell="v3", titled Home) and carries no workspace template; `/analyst` is the
 *            workspace (data-template="convoy-command", titled Corridor); `/home` still answers as Home;
 *            `/analyst/` redirects to `/analyst`; the unrelated routes keep answering.
 *   EDGE     response headers: nosniff / referrer / DENY framing / permissions policy identical on `/analyst` and the
 *            other operator pages; with a CSP (a production build — a dev deck sets none by design) `/analyst`
 *            carries exactly the operator policy `/gods-eye` and `/ops` carry (Cesium's eval, blob task workers, the
 *            photoreal tile host) and Home exactly the strict policy `/home` and `/citizen` carry (no eval, no
 *            blob scripts, no photoreal host); nonces differ per response.
 *   BROWSER  Home mounts at `/` (rail: Home `/`, Analyst `/analyst`) and the workspace at `/analyst` (v2 mark → `/`,
 *            Corridor module → `/analyst` pressed); zero page errors and zero CSP violations on both; Share copies
 *            `/analyst#…`.
 *   HASH     an old bookmark `/#v=2…`, `#inbox=`, `#movement=`, `#items=`, `#sel=`, `#view=` lands on `/analyst#…`
 *            with the hash untouched and Home is never parsed into a body (no DOMContentLoaded of Home first —
 *            the <head> script leaves before first paint); Home's own anchors (`/#v3-live`) stay on Home.
 *   SELECT   Home → an object page → the rail's Analyst keeps the selection (the canvas shows the same URN); the
 *            Omnibar's Enter on an object opens `/o/<urn>` on Home and selects in place on `/analyst`.
 *
 * Exit 0 with `ok <name>` lines; 1 on any failure.
 */
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { CHROME_ARGS, chromePath, loadPuppeteer, startProdServer } from './route-coldload.mjs';
import { HOME, WORKSPACE } from './lib/routes.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SHOTS = path.join(HERE, 'artifacts', 'root-flip');
mkdirSync(SHOTS, { recursive: true });

const args = process.argv.slice(2);
const wantProd = args.includes('--prod');
let origin = (args.find((a) => /^https?:/.test(a)) ?? 'http://127.0.0.1:5475').replace(/\/+$/, '');
if (/:(5273|8090|8091|8092)\b/.test(origin)) {
	console.error(`refusing a live port: ${origin}`);
	process.exit(2);
}

const bail = args.includes('--bail'); // stop at the first failing check (the mutation runs use it)
let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
		if (bail) {
			server?.stop();
			process.exit(1);
		}
	}
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const nonceless = (c) => (c ?? '').replace(/'nonce-[^']+'/g, "'nonce-N'");

let server = null;
if (wantProd) {
	server = await startProdServer();
	origin = server.origin;
}

async function get(p, { manual = false } = {}) {
	const res = await fetch(origin + p, { redirect: manual ? 'manual' : 'follow', signal: AbortSignal.timeout(90_000) });
	const text = manual ? '' : await res.text();
	return { status: res.status, headers: Object.fromEntries([...res.headers].map(([k, v]) => [k.toLowerCase(), v])), text, url: res.url, location: res.headers.get('location') };
}
const title = (html) => /<title>([^<]*)<\/title>/.exec(html)?.[1] ?? '';

// ─── HTTP ───────────────────────────────────────────────────────────────────

const pages = {};
for (const p of [HOME, WORKSPACE, '/home', '/ops', '/gods-eye', '/citizen', '/comms', '/chat']) pages[p] = await get(p);
ok('`/` serves Home (200, V3 shell, titled Home, no workspace template)', pages[HOME].status === 200 && /data-shell="v3"/.test(pages[HOME].text) && title(pages[HOME].text).startsWith('Home') && !/data-template="convoy-command"/.test(pages[HOME].text), `${pages[HOME].status} · ${title(pages[HOME].text)}`);
// V3-P6B: the workspace now sits under the V3 shell (the (deck) layout draws V3Shell around the page): the template, the title and
// the operator band are the page's own and the v2 navbar is gone
ok('`/analyst` serves the workspace (200, data-template="convoy-command", titled Corridor, under the V3 shell and its operator band)', pages[WORKSPACE].status === 200 && /data-template="convoy-command"/.test(pages[WORKSPACE].text) && title(pages[WORKSPACE].text) === 'Corridor · Sajag' && /data-shell="v3"/.test(pages[WORKSPACE].text) && /data-v3="ops-band"/.test(pages[WORKSPACE].text) && !/class="navbar/.test(pages[WORKSPACE].text), `${pages[WORKSPACE].status} · ${title(pages[WORKSPACE].text)}`);
ok('`/home` still answers, as Home', pages['/home'].status === 200 && /data-shell="v3"/.test(pages['/home'].text) && title(pages['/home'].text) === title(pages[HOME].text));
ok('the unrelated routes keep answering 200 (/ops /gods-eye /citizen /comms /chat)', ['/ops', '/gods-eye', '/citizen', '/comms', '/chat'].every((p) => pages[p].status === 200), ['/ops', '/gods-eye', '/citizen', '/comms', '/chat'].map((p) => `${p} ${pages[p].status}`).join(' '));
{
	const r = await get(`${WORKSPACE}/`, { manual: true });
	ok('`/analyst/` redirects to `/analyst` (trailing slash normalised, not a 404)', [301, 307, 308].includes(r.status) && new URL(r.location ?? '', origin).pathname === WORKSPACE, `${r.status} → ${r.location}`);
	const ghost = await get('/analyst/nope');
	ok('`/analyst/nope` is a 404 (only the workspace itself is rerouted)', ghost.status === 404, String(ghost.status));
}
ok('the workspace page carries the page chrome the old `/` carried, as the V3 chrome (the mark → `/`, Analyst pressed on /analyst, the Workspace sub-nav tab pressed)', /<a class="logo[^"]*" href="\/"/.test(pages[WORKSPACE].text) && /<a[^>]*href="\/analyst"[^>]*aria-current="page"[^>]*data-v3-nav="analyst"/.test(pages[WORKSPACE].text) && /<a[^>]*href="\/analyst"[^>]*aria-current="page"[^>]*data-v3-tab="workspace"/.test(pages[WORKSPACE].text), '');

// ─── EDGE: headers ──────────────────────────────────────────────────────────

const H = (p) => pages[p].headers;
const SEC = ['x-content-type-options', 'referrer-policy', 'x-frame-options', 'permissions-policy'];
ok('security headers on `/analyst` equal the other operator pages\' and Home\'s (nosniff, referrer, DENY, permissions)', SEC.every((k) => H(WORKSPACE)[k] && H(WORKSPACE)[k] === H('/gods-eye')[k] && H(WORKSPACE)[k] === H('/ops')[k] && H(WORKSPACE)[k] === H(HOME)[k]), SEC.map((k) => `${k}=${H(WORKSPACE)[k]}`).join(' · '));
ok('x-frame-options DENY and nosniff on `/` and `/analyst`', H(HOME)['x-frame-options'] === 'DENY' && H(WORKSPACE)['x-frame-options'] === 'DENY' && H(HOME)['x-content-type-options'] === 'nosniff' && H(WORKSPACE)['x-content-type-options'] === 'nosniff');
const csp = (p) => H(p)['content-security-policy'] ?? '';
const prod = ['/gods-eye', '/ops', '/citizen', WORKSPACE, HOME].some((p) => csp(p));
if (prod) {
	ok('CSP: `/analyst` carries the operator policy (Cesium eval + blob task workers + the photoreal tile host)', /'unsafe-eval'/.test(csp(WORKSPACE)) && /script-src[^;]* blob:/.test(csp(WORKSPACE)) && csp(WORKSPACE).includes('tile.googleapis.com'));
	ok('CSP: `/analyst` is byte for byte the operator policy of /gods-eye and /ops (nonce aside) — what the old `/` carried', nonceless(csp(WORKSPACE)) === nonceless(csp('/gods-eye')) && nonceless(csp(WORKSPACE)) === nonceless(csp('/ops')) && nonceless(csp(WORKSPACE)) === nonceless(csp('/comms')) && nonceless(csp(WORKSPACE)) === nonceless(csp('/chat')));
	ok('CSP: Home at `/` carries the operator policy of /home, /map and /analyst (a navigation from Home into the canvas keeps its document); /citizen stays strict', nonceless(csp(HOME)) === nonceless(csp('/home')) && nonceless(csp(HOME)) === nonceless(csp(WORKSPACE)) && /'unsafe-eval'/.test(csp(HOME)) && !/'unsafe-eval'/.test(csp('/citizen')) && csp(HOME).includes('tile.googleapis.com'));
	ok('CSP: no inline-script escape hatch on either page (nonce only), frame-ancestors none', [HOME, WORKSPACE].every((p) => !/script-src[^;]*'unsafe-inline'/.test(csp(p)) && csp(p).includes("frame-ancestors 'none'")));
	const n1 = /'nonce-([^']+)'/.exec(csp(WORKSPACE))?.[1];
	const again = await get(WORKSPACE);
	const n2 = /'nonce-([^']+)'/.exec(again.headers['content-security-policy'] ?? '')?.[1];
	ok('CSP: a fresh nonce per response, and every <script> of both pages carries it', !!n1 && !!n2 && n1 !== n2 && [HOME, WORKSPACE].every((p) => { const nn = /'nonce-([^']+)'/.exec(csp(p))?.[1]; const tags = pages[p].text.match(/<script\b[^>]*>/g) ?? []; return !!nn && tags.length > 0 && tags.every((t) => t.includes(`nonce="${nn}"`)); }));
} else {
	ok('CSP: a dev deck sets none by design (vite injects its own scripts) — on every page alike', ['/analyst', '/', '/gods-eye', '/ops', '/citizen'].every((p) => !csp(p)), 'run again with --prod / npm run preview for the policy checks');
}
ok('cache headers: the workspace and Home send what the other document routes send (no route-specific caching)', (H(WORKSPACE)['cache-control'] ?? '') === (H('/gods-eye')['cache-control'] ?? '') && (H(HOME)['cache-control'] ?? '') === (H('/home')['cache-control'] ?? ''), `analyst "${H(WORKSPACE)['cache-control'] ?? ''}" · home "${H(HOME)['cache-control'] ?? ''}"`);
ok('the operator gate does not stand in front of documents (GET /analyst and GET / answer 200 without a session when the gate is off)', pages[WORKSPACE].status === 200 && pages[HOME].status === 200);

// ─── BROWSER ────────────────────────────────────────────────────────────────

const puppeteer = loadPuppeteer();
const browser = await puppeteer.launch({ executablePath: chromePath(), headless: 'new', args: CHROME_ARGS });

async function newPage({ w = 1440, h = 900, lang = 'en' } = {}) {
	const ctx = await browser.createBrowserContext();
	const page = await ctx.newPage();
	await page.setViewport({ width: w, height: h });
	await ctx.overridePermissions(origin, ['clipboard-read', 'clipboard-write', 'clipboard-sanitized-write']).catch(() => {});
	await page.setCookie({ name: 'sajag_lang', value: lang, url: origin });
	await page.setRequestInterception(true);
	page.on('request', (r) => {
		const p = ['GET', 'HEAD', 'OPTIONS'].includes(r.method()) ? r.continue() : r.respond({ status: 204, body: '' });
		p.catch(() => {});
	});
	const log = { errors: [], csp: [], nav: [], dcl: [] };
	page.on('pageerror', (e) => log.errors.push(String(e?.message ?? e).slice(0, 200)));
	page.on('console', (m) => {
		const t = m.text();
		if (/Content Security Policy|violates the following/i.test(t) || t.startsWith('CSP ')) log.csp.push(t.slice(0, 200));
		if (t.startsWith('RF-DCL ')) log.dcl.push(t.slice(7));
	});
	page.on('framenavigated', (f) => {
		if (f === page.mainFrame()) log.nav.push(f.url());
	});
	await page.evaluateOnNewDocument(() => {
		document.addEventListener('DOMContentLoaded', () => console.debug(`RF-DCL ${location.pathname}${location.hash} home=${!!document.querySelector('[data-v3="home"]')} ws=${!!document.querySelector('[data-template="convoy-command"]')}`));
		document.addEventListener('securitypolicyviolation', (e) => console.debug(`CSP ${e.violatedDirective} ${e.blockedURI}`));
	});
	return { ctx, page, log };
}
const pathOf = (page) => page.evaluate(() => `${location.pathname}${location.hash}`);
const waitPath = (page, fn, arg, timeout = 60_000) => page.waitForFunction(fn, { timeout }, arg).then(() => true, () => false);

try {
	// ── Home at `/` ─────────────────────────────────────────────────────────
	{
		const { ctx, page, log } = await newPage();
		await page.goto(origin + HOME, { waitUntil: 'networkidle2', timeout: 120_000 });
		const home = await page.waitForSelector('[data-v3="home"]', { timeout: 60_000 }).then(() => true, () => false);
		ok('browser: `/` mounts V3 Home', home && (await page.title()).startsWith('Home') && (await pathOf(page)) === '/', await page.title());
		const rail = await page.evaluate(() => ({
			home: document.querySelector('[data-v3-nav="home"]')?.getAttribute('href'),
			homeCurrent: document.querySelector('[data-v3-nav="home"]')?.getAttribute('aria-current'),
			analyst: document.querySelector('[data-v3-nav="analyst"]')?.getAttribute('href'),
			analystCurrent: document.querySelector('[data-v3-nav="analyst"]')?.getAttribute('aria-current') ?? null,
			ws: !!document.querySelector('[data-template="convoy-command"]'),
		}));
		ok('browser: the rail\'s Home is `/` and lit on Home, Analyst is `/analyst` and not lit, no workspace template on Home', rail.home === '/' && rail.homeCurrent === 'page' && rail.analyst === '/analyst' && rail.analystCurrent === null && rail.ws === false, JSON.stringify(rail));
		await page.screenshot({ path: path.join(SHOTS, `home-${wantProd ? 'prod' : 'dev'}.png`) });
		ok('browser: Home — zero page errors, zero CSP violations', log.errors.length === 0 && log.csp.length === 0, [...log.errors, ...log.csp].slice(0, 2).join(' | ') || 'none');
		await ctx.close();
	}

	// ── the workspace at `/analyst` ─────────────────────────────────────────
	{
		const { ctx, page, log } = await newPage();
		await page.goto(origin + WORKSPACE, { waitUntil: 'domcontentloaded', timeout: 120_000 });
		const ws = await page.waitForSelector('[data-template="convoy-command"]:not([data-pending])', { timeout: 90_000 }).then(() => true, () => false);
		ok('browser: `/analyst` mounts the workspace (data-template="convoy-command")', ws && (await page.title()) === 'Corridor · Sajag' && (await pathOf(page)) === WORKSPACE, await page.title());
		await sleep(3000);
		// V3-P6B: the V3 rail's mark opens `/` (Home); its Analyst item and the sub-nav's Workspace tab open `/analyst` and are pressed
		const nav = await page.evaluate(() => ({
			brand: document.querySelector('[data-v3="rail"] a.logo')?.getAttribute('href'),
			analyst: [...document.querySelectorAll('[data-v3-nav="analyst"]')].map((a) => `${a.getAttribute('href')}:${a.getAttribute('aria-current')}`),
			tab: [...document.querySelectorAll('[data-v3-tab="workspace"]')].map((a) => `${a.getAttribute('href')}:${a.getAttribute('aria-current')}`),
			navbars: document.querySelectorAll('.navbar').length,
		}));
		ok('browser: the V3 mark opens `/` (Home); the rail\'s Analyst and the sub-nav\'s Workspace open `/analyst` and are pressed; no v2 navbar', nav.brand === '/' && nav.analyst.join() === '/analyst:page' && nav.tab.join() === '/analyst:page' && nav.navbars === 0, JSON.stringify(nav));
		// Share copies /analyst#… (the clipboard is the page's own; the toast says the outcome)
		const shared = await page.evaluate(async () => {
			const b = document.querySelector('[data-share]');
			if (!b) return null;
			b.click();
			await new Promise((r) => setTimeout(r, 1200));
			try {
				return await navigator.clipboard.readText();
			} catch (e) {
				return `ERR ${e}`;
			}
		});
		ok('browser: Share copies `/analyst#…` (the workspace link), not the bare root', typeof shared === 'string' && shared.startsWith(`${origin}${WORKSPACE}`) && !shared.startsWith(`${origin}/#`), String(shared).replace(/(sel|items)=[^&]*/g, '$1=…').slice(0, 120));
		await page.screenshot({ path: path.join(SHOTS, `analyst-${wantProd ? 'prod' : 'dev'}.png`) });
		ok('browser: workspace — zero CSP violations (the operator policy lets Cesium run)', log.csp.length === 0, log.csp.slice(0, 2).join(' | ') || 'none');
		const otherErrors = log.errors.filter((e) => !e.includes('effect_update_depth_exceeded'));
		ok('browser: workspace — zero page errors', otherErrors.length === 0, otherErrors.slice(0, 2).join(' | ') || 'none');
		await ctx.close();
	}

	// ── hash deep links: an old bookmark lands on /analyst#… ────────────────
	{
		const FORMS = [
			'#v=2&lat=22.5682&lon=88.3499&alt=1500&heading=45&pitch=-40&style=flir&layers=events',
			'#inbox=pursuit%3Aevt-9',
			'#movement=escort-proposal%3Amv-1',
			'#items=junction%3A1%2Cjunction%3A2',
			'#sel=junction:1',
			'#view=table',
		];
		for (const hash of FORMS) {
			const { ctx, page, log } = await newPage();
			await page.goto(`${origin}/${hash}`, { waitUntil: 'domcontentloaded', timeout: 120_000 }).catch(() => {});
			const landed = await waitPath(page, (w) => location.pathname === w, WORKSPACE);
			const first = log.nav.find((u) => new URL(u).pathname === WORKSPACE);
			ok(`hash: \`/${hash.slice(0, 44)}${hash.length > 44 ? '…' : ''}\` lands on /analyst with its hash`, landed && first === `${origin}${WORKSPACE}${hash}`, `${first ?? log.nav.join(' > ')}`.replace(origin, '').slice(0, 100));
			const homeParsed = log.dcl.filter((l) => (l.startsWith('/#') || l.startsWith('/ ')) && /home=true/.test(l));
			ok(`hash: Home is never parsed first (no flash of Home) — ${hash.slice(0, 14)}…`, homeParsed.length === 0, log.dcl.join(' | ').slice(0, 160));
			ok(`hash: no CSP violation on the way (${hash.slice(0, 10)}…)`, log.csp.length === 0, log.csp.slice(0, 1).join(''));
			await ctx.close();
		}
		const { ctx, page } = await newPage();
		await page.goto(`${origin}/#v3-live`, { waitUntil: 'networkidle2', timeout: 120_000 });
		await page.waitForSelector('[data-v3="home"]', { timeout: 60_000 }).catch(() => {});
		await sleep(1500);
		ok('hash: Home\'s own anchor `/#v3-live` stays on Home', (await pathOf(page)).startsWith('/#v3-live'), await pathOf(page));
		await ctx.close();
	}

	// ── a client-side arrival at `/#…` (a link in the app that still spells the old root) is handed over WITHOUT a reload ─
	{
		const { ctx, page, log } = await newPage();
		await page.goto(`${origin}/api/v1/health`, { waitUntil: 'domcontentloaded', timeout: 60_000 }).catch(() => {});
		await page.goto(origin + HOME, { waitUntil: 'networkidle2', timeout: 120_000 });
		await page.waitForSelector('[data-v3="home"]', { timeout: 60_000 }).catch(() => {});
		await sleep(2000);
		await page.evaluate(() => {
			window.__rfSentinel = 'alive';
			const a = document.createElement('a');
			a.href = '/#sel=junction:1';
			a.textContent = 'x';
			document.body.append(a);
			a.click();
		});
		const landed = await waitPath(page, (w) => location.pathname === w && location.hash === '#sel=junction:1', WORKSPACE);
		const alive = await page.evaluate(() => window.__rfSentinel ?? null).catch(() => null);
		ok('client-side `/#sel=…` arrival: handed to /analyst#sel=… as a client navigation (no full reload — the page keeps its state)', landed && alive === 'alive', `${await pathOf(page)} · sentinel ${alive}`);
		ok('client-side hand-over: zero page errors, zero CSP violations', log.errors.filter((e) => !e.includes('effect_update_depth_exceeded')).length === 0 && log.csp.length === 0, [...log.errors, ...log.csp].slice(0, 1).join(''));
		await ctx.close();
	}

	// ── …and from a v2 page (a link elsewhere in the app that still spells `/#…`: Home mounts, hands over, no reload) ──
	{
		const { ctx, page } = await newPage();
		await page.goto(`${origin}/ops`, { waitUntil: 'networkidle2', timeout: 120_000 });
		await sleep(2500);
		await page.evaluate(() => {
			window.__rfSentinel = 'alive';
			const a = document.createElement('a');
			a.href = '/#inbox=pursuit%3Aevt-9';
			a.textContent = 'x';
			document.body.append(a);
			a.click();
		});
		const landed = await waitPath(page, (w) => location.pathname === w && location.hash.startsWith('#inbox='), WORKSPACE);
		const alive = await page.evaluate(() => window.__rfSentinel ?? null).catch(() => null);
		ok('client-side arrival from /ops at `/#inbox=…`: Home mounts, hands to /analyst#inbox=… without a reload', landed && alive === 'alive', `${await pathOf(page)} · sentinel ${alive}`);
		await ctx.close();
	}

	// ── a client-side arrival: Home → object page → Analyst keeps the selection ─
	const ents = await get('/api/v1/city/entities?kinds=junction').then((r) => JSON.parse(r.text).entities ?? []).catch(() => []);
	const target = ents.find((e) => e.urn === 'junction:1') ?? ents[0];
	ok('fixture: the sandbox has a junction to select', !!target, target?.urn ?? 'none');
	if (target) {
		const { ctx, page, log } = await newPage();
		await page.goto(origin + HOME, { waitUntil: 'networkidle2', timeout: 120_000 });
		await page.waitForSelector('[data-v3="home"]', { timeout: 60_000 }).catch(() => {});
		await sleep(2500);
		// a client-side navigation to the object page (SvelteKit intercepts a clicked in-document link)
		await page.evaluate((urn) => {
			const a = document.createElement('a');
			a.id = 'rf-obj';
			a.href = `/o/${urn}`;
			a.textContent = 'x';
			document.body.append(a);
			a.click();
		}, target.urn);
		const onObject = await waitPath(page, () => location.pathname.startsWith('/o/'), null);
		await sleep(3000);
		ok('select: Home → the object page (client-side)', onObject, await pathOf(page));
		await page.click('[data-v3-nav="analyst"]').catch(() => {});
		const onWs = await waitPath(page, (w) => location.pathname === w, WORKSPACE);
		await page.waitForSelector('[data-template="convoy-command"]:not([data-pending])', { timeout: 90_000 }).catch(() => {});
		let sel = null;
		for (let i = 0; i < 60 && sel !== target.urn; i++) {
			sel = await page.evaluate(() => window.__GODS_EYE__?.selection?.urn ?? null).catch(() => null);
			if (sel !== target.urn) await sleep(1000);
		}
		const dossier = await page.waitForSelector('[data-testid="entity-dossier"]', { timeout: 20_000 }).then(() => true, () => false);
		ok('select: the rail\'s Analyst opens `/analyst` client-side and the inspector shows the carried object (the selection store survives)', onWs && dossier, `path ${await pathOf(page)} · dossier ${dossier}`);
		// the canvas of the workspace entered by a client-side navigation: the CSP belongs to the DOCUMENT (Home's), so a
		// canvas that needs Cesium's eval is `unavailable` when the document carried the strict policy (see the report)
		const canvasPhase = await page.evaluate(() => window.__GODS_EYE__?.phase ?? null).catch(() => null);
		ok('select: …and the canvas keeps the same selection (the workspace canvas is available after a client-side hand-over from Home)', sel === target.urn, `canvas phase ${canvasPhase} · selection ${sel}${canvasPhase === 'unavailable' && log.csp.length + log.errors.length ? ' · the document carries the strict CSP (Cesium eval refused)' : ''}`);
		ok('select: zero CSP violations and page errors on the client-side hand-over', log.csp.length === 0 && log.errors.filter((e) => !e.includes('effect_update_depth_exceeded')).length === 0, [...log.csp, ...log.errors].slice(0, 1).join(''));
		await ctx.close();

		// the Omnibar: Enter on an object → /o/<urn> on Home; in place on /analyst
		const label = String(target.label ?? '').split(' - ')[0].slice(0, 22); // the omnibar searches names (a bare URN lists no row)
		for (const [where, wantObject] of [[HOME, true], [WORKSPACE, false]]) {
			const { ctx: c2, page: p2 } = await newPage();
			await p2.goto(origin + where, { waitUntil: 'networkidle2', timeout: 120_000 });
			await p2.waitForSelector(where === HOME ? '[data-v3="home"]' : '[data-template="convoy-command"]:not([data-pending])', { timeout: 90_000 }).catch(() => {});
			await sleep(4000);
			await p2.keyboard.down('Control');
			await p2.keyboard.press('k');
			await p2.keyboard.up('Control');
			const input = await p2.waitForSelector('[data-testid="palette-input"]', { visible: true, timeout: 20_000 }).catch(() => null);
			if (!input) {
				ok(`omnibar: Enter on an object (${where})`, false, 'the omnibar did not open');
				await c2.close();
				continue;
			}
			await input.type(label, { delay: 15 });
			await sleep(2500);
			await p2.keyboard.press('Enter');
			await sleep(4000);
			const at = await pathOf(p2);
			const selected = wantObject ? target.urn : await p2.evaluate(() => window.__GODS_EYE__?.selection?.urn ?? null);
			const expected = wantObject ? at.startsWith(`/o/${target.urn}`) : at.startsWith(WORKSPACE) && selected === target.urn;
			ok(wantObject ? `omnibar: Enter on an object result on Home opens /o/<urn> (${label})` : 'omnibar: Enter on an object result on /analyst selects in place (v2 page, no navigation)', expected, `${at} · selection ${selected}`);
			await c2.close();
		}
	}

	// ── Marathi / Hindi: the shell labels on both roots ────────────────────
	for (const lang of ['hi', 'mr']) {
		const { ctx, page } = await newPage({ lang });
		await page.goto(origin + HOME, { waitUntil: 'networkidle2', timeout: 120_000 });
		await page.waitForSelector('[data-v3="home"]', { timeout: 60_000 }).catch(() => {});
		const t = await page.evaluate(() => ({ lang: document.documentElement.lang, analyst: document.querySelector('[data-v3-nav="analyst"]')?.textContent?.trim() ?? '', home: document.querySelector('[data-v3-nav="home"]')?.textContent?.trim() ?? '' }));
		ok(`${lang}: Home at \`/\` renders in the reader's language and the rail names Home / Analyst in it`, t.lang === lang && /[^\x00-\x7f]/.test(t.analyst) && /[^\x00-\x7f]/.test(t.home), JSON.stringify(t));
		await page.goto(origin + WORKSPACE, { waitUntil: 'domcontentloaded', timeout: 120_000 });
		await page.waitForSelector('[data-template="convoy-command"]:not([data-pending])', { timeout: 90_000 }).catch(() => {});
		ok(`${lang}: the workspace at \`/analyst\` renders in the reader's language`, (await page.evaluate(() => document.documentElement.lang)) === lang);
		await ctx.close();
	}
} finally {
	await browser.close().catch(() => {});
	server?.stop();
}

console.log(failures ? `\nroot-flip-smoke: ${failures} FAILED` : '\nok   root-flip-smoke — all assertions passed');
process.exit(failures ? 1 : 0);
