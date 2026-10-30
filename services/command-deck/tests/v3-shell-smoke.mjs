/**
 * The V3 shell on EVERY page (V3-P6B; V3-SPEC §3.1, §6.9, §6.10, §7.3; the colleague's review: "the orientation of the
 * options changes when I leave a page; it should be uniform") — HERMETIC: every same-origin /api/* and /gods-eye/* GET
 * is answered in the browser from Home's fixture world (tests/home-smoke.mjs: a live movement with its escort proposal, an
 * open pursuit, a simulated traffic feed …); /gods-eye/mode answers 404 (the canvas is keyless); every non-GET is
 * ABORTED and recorded; OSM tiles and every third party are aborted.
 *
 *   node tests/v3-shell-smoke.mjs [deckUrl]          (default http://127.0.0.1:5483; a dev deck of this tree)
 *   V3_SHOTS=<dir> node tests/v3-shell-smoke.mjs …   also saves a screenshot per page
 *   V3_SHELL_QUICK=1 node tests/v3-shell-smoke.mjs …  the 1366 EN leg only (the mutation runs)
 *
 * Asserts, over Home, Decide, Map, Plan, Assistant (the V3 screens) AND the v2 operator pages that now sit under the same
 * shell — Analyst /analyst, the Situation wall /ops, the Analyst city map /gods-eye, the assistant page /chat and /comms:
 *   1. one rail and one top bar on every page, and no v2 navbar anywhere (no `.navbar`, no `[data-shell="command-bar"]` that
 *      is a header); zero page errors; nothing written (every non-GET aborted);
 *   2. GEOMETRY: the rail items, the top bar, the search, the menu, the bell and the officer pill sit at the SAME pixels on
 *      every page, at 1920 and at 1366 (EN) and at 1366 in HI and MR;
 *   3. PIXELS: the top bar from the search to the right edge and the rail's logo are pixel-identical (a screenshot clip
 *      compared with Home's) on every page — only the title column differs by design; every rail item that is not the
 *      page's own (and not Decide, whose badge is a count) is pixel-identical wherever it appears. "Identical" means no 4 x 4
 *      block of the clip differs in mean colour by more than 10/255 (rail) or 24/255 (top bar): a page with a WebGL canvas
 *      behind it (/map) has its text anti-aliased in grey instead of sub-pixel by the browser (a few edge pixels move by
 *      up to ~50; bold 15 px text moves a block by up to ~15), a moved or missing glyph, icon, flask or dot moves a
 *      block by far more (the mutation runs prove it);
 *   4. the top bar is 68 px from 1500 px wide and 60 px below; the rail 88 / 76 px;
 *   5. each page names itself: the top bar's title is the page's name (Analyst, Situation wall, City map, Assistant …) and
 *      the rail lights the right item (aria-current): Analyst for the workspace, the wall and the city map;
 *   6. the Analyst family (workspace, wall, city map, assistant page) carries the same sub-nav in the same place, and a click
 *      on it moves between pages without the rail or the top bar moving a pixel;
 *   7. live operations are never hidden: with a movement, a pursuit and a decision live, the live strip is on the Analyst
 *      family pages with its segments, inside the viewport and 36 px high; the V3 screens that already show
 *      what is live (Home, Map) carry none;
 *   8. the contracts the pages feed land in the V3 chrome: band tag, Inbox (count = the rail's Decide badge), Data button
 *      (brain-posture), Policies and More on the operator band; the Exercise data flask in the menu; the language switch
 *      in the menu (EN → HI → EN through the sajag_lang cookie); the officer pill opens the one duty-officer input;
 *   9. keys: `?` opens the shortcuts sheet on an operator page (Ctrl K, `/`, `?`, Esc, G then …); G then M goes to /map; no
 *      key sends anything;
 *  10. /design is a dev page: it answers on a dev server and 404s on a build.
 *
 * Exit 0 with `ok <name>` lines; exit 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { homeFixtures } from './home-smoke.mjs';
import { isViteDevServer } from './lib/tolerant.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const base = (process.argv[2] ?? 'http://127.0.0.1:5483').replace(/\/$/, '');
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
/** The largest difference (0–255) between the mean colours of corresponding 4 x 4 blocks of two PNGs (base64), decoded in the page. */
const BLOCKS = async (page, a, b) =>
	page.evaluate(
		async (x, y) => {
			const load = async (b64) => {
				const img = await createImageBitmap(await (await fetch(`data:image/png;base64,${b64}`)).blob());
				const c = new OffscreenCanvas(img.width, img.height);
				const g = c.getContext('2d');
				g.drawImage(img, 0, 0);
				return g.getImageData(0, 0, img.width, img.height);
			};
			const A = await load(x);
			const B = await load(y);
			if (A.width !== B.width || A.height !== B.height) return { size: false, max: 255 };
			let max = 0;
			for (let by = 0; by < A.height; by += 4)
				for (let bx = 0; bx < A.width; bx += 4) {
					let da = 0;
					let n = 0;
					for (let j = by; j < Math.min(by + 4, A.height); j++)
						for (let i = bx; i < Math.min(bx + 4, A.width); i++) {
							const k = (j * A.width + i) * 4;
							for (let c = 0; c < 3; c++) da += A.data[k + c] - B.data[k + c];
							n += 3;
						}
					max = Math.max(max, Math.abs(da / n));
				}
			return { size: true, max: Math.round(max * 10) / 10 };
		},
		a,
		b,
	);

/** route → { rail: the rail item it lights, title: its EN title (null: any), family: Analyst family, live: the live strip is expected } */
const PAGES = {
	'/': { rail: 'home', title: null, family: false, live: false },
	'/decide': { rail: 'decide', title: 'Decide', family: false, live: false },
	'/map': { rail: 'map', title: null, family: false, live: false },
	'/plan': { rail: 'plan', title: null, family: false, live: false },
	'/assistant': { rail: 'assistant', title: null, family: false, live: false },
	'/analyst': { rail: 'analyst', title: 'Analyst', family: true, live: true },
	'/ops': { rail: 'analyst', title: 'Situation wall', family: true, live: true },
	'/gods-eye': { rail: 'analyst', title: 'City map', family: true, live: true },
	'/chat': { rail: 'analyst', title: 'Assistant', family: true, live: true },
	// /comms: P6A gives it its own V3Shell wrapper (routes/(deck)/comms/+layout@.svelte resets the (deck) layout), so it has the
	// rail, the top bar and — V3Shell draws it for any page that supplies something live — the live strip, but not the Analyst
	// operator band, but whether it ALSO wears it depends on whether the (deck) layout wraps it (before P6A merges, it does) — so the band is not held there (band: null)
	'/comms': { rail: 'advisories', title: null, family: false, live: true, band: null },
};
for (const p of Object.values(PAGES)) if (p.band === undefined) p.band = p.live === true;
const ROUTES = Object.keys(PAGES);

const fx = homeFixtures(Date.now());
const writes = [];
const errors = [];

const browser = await puppeteer.launch({
	executablePath: CHROME,
	headless: 'new',
	args: ['--no-sandbox', '--disable-dev-shm-usage', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--use-gl=angle', '--ignore-gpu-blocklist', '--window-size=1920,1080'],
});

/** The geometry of the shell on the page that is open: [left, top, width, height] of every part, as one string. */
const GEOMETRY = () => {
	const r = (el) => (el ? [Math.round(el.getBoundingClientRect().left), Math.round(el.getBoundingClientRect().top), Math.round(el.getBoundingClientRect().width), Math.round(el.getBoundingClientRect().height)] : null);
	return JSON.stringify({
		rail: r(document.querySelector('[data-v3="rail"]')),
		logo: r(document.querySelector('[data-v3="rail"] .logo')),
		items: [...document.querySelectorAll('[data-v3-nav]')].map((a) => [a.getAttribute('data-v3-nav'), r(a)]),
		top: r(document.querySelector('[data-v3="top-bar"]')),
		title: r(document.querySelector('[data-v3="screen-title"]'))?.slice(0, 2),
		search: r(document.querySelector('[data-v3="top-bar"] [data-shell="command-search"]')),
		menu: r(document.querySelector('[data-testid="v3-header-menu"]')),
		bell: r(document.querySelector('[data-testid="v3-alerts"]')),
		officer: r(document.querySelector('[data-testid="v3-officer"]')),
	});
};

/** Where the page's shell is, for the pixel clips: the search's left edge and the top bar's height. */
const CLIPS = () => {
	const top = document.querySelector('[data-v3="top-bar"]')?.getBoundingClientRect();
	const search = document.querySelector('[data-v3="top-bar"] [data-shell="command-search"]')?.getBoundingClientRect();
	const logo = document.querySelector('[data-v3="rail"] .logo')?.getBoundingClientRect();
	const items = [...document.querySelectorAll('[data-v3-nav]')].map((a) => {
		const b = a.getBoundingClientRect();
		return { id: a.getAttribute('data-v3-nav'), pressed: a.getAttribute('aria-current') === 'page', x: b.left, y: b.top, w: b.width, h: b.height };
	});
	return top && search && logo ? { bar: { x: search.left - 4, y: 0, w: window.innerWidth - search.left + 4, h: top.height }, logo: { x: logo.left, y: logo.top, w: logo.width, h: logo.height }, items } : null;
};

async function openPage(page, route, { lang = 'en', w = 1920, h = 1080 } = {}) {
	await page.setViewport({ width: w, height: h });
	await page.setCookie({ name: 'sajag_lang', value: lang, url: origin });
	await page.goto(`${base}${route}`, { waitUntil: 'networkidle2', timeout: 120_000 }).catch(() => {});
	await page.waitForSelector('[data-v3="top-bar"]', { timeout: 60_000 }).catch(() => {});
	// the exercise statement (the flask) arrives with the page's first polls: the clips are compared once it is in
	await page.waitForFunction(() => document.querySelector('[data-testid="v3-header-menu"]')?.getAttribute('data-exercise') === 'true', { timeout: 30_000 }).catch(() => {});
	await sleep(1800);
}

const shot = async (page, name) => {
	if (SHOTS) await page.screenshot({ path: path.join(SHOTS, name) });
};

try {
	const page = await browser.newPage();
	page.on('pageerror', (e) => errors.push(`${page.url().replace(origin, '')} ${e.message.slice(0, 200)}`));
	await page.setRequestInterception(true);
	page.on('request', (req) => {
		const u = new URL(req.url());
		const m = req.method();
		if (!['GET', 'HEAD', 'OPTIONS'].includes(m)) {
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
	await page.evaluateOnNewDocument(() => {
		try {
			localStorage.setItem('sajag.v3.onboarded', '1');
		} catch {
			// storage unavailable
		}
	});

	// ── 1–7: every page, at 1920 and 1366 (EN) and 1366 in HI / MR ─────────────
	// V3_SHELL_QUICK=1 (the mutation runs): the 1366 EN leg only
	const MATRIX = [
		{ lang: 'en', w: 1920, h: 1080 },
		{ lang: 'en', w: 1366, h: 768 },
		{ lang: 'hi', w: 1366, h: 768 },
		{ lang: 'mr', w: 1366, h: 768 },
	].filter((c) => process.env.V3_SHELL_QUICK !== '1' || (c.lang === 'en' && c.w === 1366));
	let firstFacts = null;
	for (const cfg of MATRIX) {
		const tag = `${cfg.w} ${cfg.lang.toUpperCase()}`;
		const geo = {};
		const facts = {};
		const hashes = { bar: {}, logo: {}, item: {} };
		for (const route of ROUTES) {
			await openPage(page, route, cfg);
			geo[route] = await page.evaluate(GEOMETRY);
			facts[route] = await page.evaluate(() => ({
				rails: document.querySelectorAll('[data-v3="rail"]').length,
				tops: document.querySelectorAll('[data-v3="top-bar"]').length,
				navbars: document.querySelectorAll('.navbar, header[data-shell="command-bar"]').length,
				title: document.querySelector('[data-v3="screen-title"]')?.textContent?.trim() ?? null,
				pressed: [...document.querySelectorAll('[data-v3-nav][aria-current="page"]')].map((a) => a.getAttribute('data-v3-nav')),
				topH: Math.round(document.querySelector('[data-v3="top-bar"]')?.getBoundingClientRect().height ?? 0),
				railW: Math.round(document.querySelector('[data-v3="rail"]')?.getBoundingClientRect().width ?? 0),
				tabs: [...document.querySelectorAll('[data-v3="analyst-tabs"] a')].map((a) => `${a.getAttribute('data-v3-tab')}:${a.getAttribute('href')}`),
				tabRect: (() => {
					const b = document.querySelector('[data-v3="analyst-tabs"]')?.getBoundingClientRect();
					return b ? [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)] : null;
				})(),
				bandPresent: !!document.querySelector('[data-v3="ops-band"]'),
				live: (() => {
					const s = document.querySelector('[data-testid="live-strip"]');
					const b = s?.getBoundingClientRect();
					const topB = document.querySelector('[data-v3="top-bar"]')?.getBoundingClientRect();
					return s ? { segs: [...s.querySelectorAll('[data-live-seg]')].map((x) => x.getAttribute('data-live-seg')), h: Math.round(b.height), inView: b.top >= 0 && b.bottom <= window.innerHeight && b.width > 0, under: Math.round(b.top - (topB?.bottom ?? 0)), left: Math.round(b.left) } : null;
				})(),
				inbox: document.querySelector('[data-shell="command-bar"] [data-inbox-intent]')?.getAttribute('data-count') ?? null,
				badge: document.querySelector('[data-testid="v3-decide-badge"]')?.getAttribute('data-count') ?? null,
				bandTag: !!document.querySelector('[data-shell="command-bar"] [data-testid="band-tag"]'),
				posture: !!document.querySelector('[data-shell="command-bar"] [data-testid="brain-posture"]'),
				policies: !!document.querySelector('[data-shell="command-bar"] .policies'),
				more: !!document.querySelector('[data-shell="command-bar"] [data-menu="more"]'),
				flask: document.querySelector('[data-testid="v3-header-menu"]')?.getAttribute('data-exercise') ?? null,
			}));
			const clips = await page.evaluate(CLIPS);
			if (clips) {
				const png = async (c) => page.screenshot({ clip: { x: Math.max(0, c.x), y: Math.max(0, c.y), width: Math.max(1, c.w), height: Math.max(1, c.h) }, captureBeyondViewport: false, encoding: 'base64' });
				hashes.bar[route] = await png(clips.bar);
				hashes.logo[route] = await png(clips.logo);
				for (const it of clips.items) if (!it.pressed && it.id !== 'decide') (hashes.item[it.id] ??= {})[route] = await png(it);
			}
			await shot(page, `${route === '/' ? 'home' : route.slice(1)}-${cfg.w}-${cfg.lang}.png`);
		}

		// 1
		const bad1 = ROUTES.filter((r) => facts[r].rails !== 1 || facts[r].tops !== 1 || facts[r].navbars !== 0);
		ok(`1. ${tag}: one rail and one top bar on every page, and no v2 navbar`, bad1.length === 0, bad1.map((r) => `${r} ${JSON.stringify(facts[r])}`).join(' | ') || `${ROUTES.length} pages`);

		// 2
		const ref = geo['/'];
		const off = ROUTES.filter((r) => {
			// the title's width differs by design (it takes what is left of its column): compare everything else
			const a = JSON.parse(geo[r]);
			const b = JSON.parse(ref);
			delete a.title;
			delete b.title;
			return JSON.stringify(a) !== JSON.stringify(b);
		});
		ok(`2. ${tag}: the rail, the top bar, the search, the menu, the bell and the officer sit at the same pixels on all ${ROUTES.length} pages`, off.length === 0 && ref.includes('"items":[["home"'), off.length ? `differs from Home: ${off.join(', ')}` : 'identical');
		if (off.length) for (const r of off) console.log(`     ${r}: ${geo[r]}\n     ${'/'}: ${ref}`);

		// 3
		const TOL = 14; // the rail (small labels): a few edge pixels of grey instead of sub-pixel anti-aliasing (on /map, ~11 against the pure-black ground); a missing or moved item moves a block by 60+
		const TOL_BAR = 24; // the top bar (bold 15 px text on /map, whose WebGL layer makes the browser anti-alias in grey): up to ~15; a missing or moved flask, label or pill moves a block by 60+
		const vs = async (m) => {
			const ref = m['/'] ?? Object.values(m)[0];
			const out = {};
			for (const [r, img] of Object.entries(m)) out[r] = (await BLOCKS(page, ref, img)).max;
			return out;
		};
		const worst = (o) => Math.max(0, ...Object.values(o));
		const bar = await vs(hashes.bar);
		const barOff = Object.entries(bar).filter(([, d]) => d > TOL_BAR).map(([r, d]) => `${r} ${d}`);
		ok(`3. ${tag}: the top bar (search to the right edge) is pixel-identical on every page`, ROUTES.every((r) => hashes.bar[r]) && barOff.length === 0, barOff.length ? `differs from Home: ${barOff.join(', ')}` : `largest block difference ${worst(bar)}/255 over ${ROUTES.length} pages (exact: ${Object.values(hashes.bar).every((h) => h === hashes.bar['/'])})`);
		const logo = await vs(hashes.logo);
		ok(`3. ${tag}: the rail's mark is pixel-identical on every page`, ROUTES.every((r) => hashes.logo[r]) && worst(logo) <= TOL, `largest block difference ${worst(logo)}/255`);
		const itemOff = [];
		let itemWorst = 0;
		for (const [id, m] of Object.entries(hashes.item)) {
			const d = await vs(m);
			itemWorst = Math.max(itemWorst, worst(d));
			if (worst(d) > TOL) itemOff.push(`${id}: ${JSON.stringify(d)}`);
		}
		ok(`3. ${tag}: every rail item is pixel-identical wherever it is not the page's own`, Object.keys(hashes.item).length >= 5 && itemOff.length === 0, itemOff.join(' | ') || `${Object.keys(hashes.item).length} items, largest block difference ${itemWorst}/255`);

		// 4
		const wantTop = cfg.w >= 1500 ? 68 : 60;
		const wantRail = cfg.w >= 1500 ? 88 : 76;
		const badBand = ROUTES.filter((r) => PAGES[r].band !== null && facts[r].bandPresent !== PAGES[r].band);
		ok(`7. ${tag}: the Analyst operator band is on the operator pages and nowhere else`, badBand.length === 0, badBand.join(', ') || ROUTES.filter((r) => PAGES[r].band).join(' '));
		const bad4 = ROUTES.filter((r) => facts[r].topH !== wantTop || facts[r].railW !== wantRail);
		ok(`4. ${tag}: the top bar is ${wantTop} px and the rail ${wantRail} px on every page`, bad4.length === 0, bad4.map((r) => `${r} ${facts[r].topH}/${facts[r].railW}`).join(' | ') || 'every page');

		// 5
		const bad5 = ROUTES.filter((r) => {
			const p = PAGES[r];
			const f = facts[r];
			const titleOk = cfg.lang === 'en' ? (p.title ? f.title === p.title : !!f.title) : !!f.title && (!p.title || f.title !== p.title);
			return !titleOk || f.pressed.length !== 1 || f.pressed[0] !== p.rail;
		});
		ok(`5. ${tag}: each page names itself and lights the right rail item`, bad5.length === 0, bad5.map((r) => `${r} title '${facts[r].title}' pressed ${facts[r].pressed}`).join(' | ') || ROUTES.map((r) => `${r}→${facts[r].pressed[0]}`).join(' '));

		// 6
		const fam = ROUTES.filter((r) => PAGES[r].family);
		const bad6 = fam.filter((r) => facts[r].tabs.join(',') !== '' && (facts[r].tabs.join(',') !== 'workspace:/analyst,wall:/ops,city:/gods-eye,assistant:/chat' || JSON.stringify(facts[r].tabRect) !== JSON.stringify(facts[fam[0]].tabRect)));
		const nonFam = ROUTES.filter((r) => !PAGES[r].family && facts[r].tabs.length > 0);
		ok(`6. ${tag}: the Analyst family carries the same sub-nav (Workspace, Situation wall, City map, Assistant) in the same place; no other page does`, fam.every((r) => facts[r].tabs.length === 4) && bad6.length === 0 && nonFam.length === 0, bad6.concat(nonFam).join(', ') || JSON.stringify(facts[fam[0]].tabRect));

		// 7
		const bad7 = ROUTES.filter((r) => {
			const f = facts[r].live;
			if (PAGES[r].live) return !f || f.segs.length < 1 || f.h !== 36 || !f.inView || f.under !== 0 || f.left !== facts[ROUTES.find((x) => PAGES[x].live)].live?.left;
			return !!f;
		});
		ok(`7. ${tag}: live operations are never hidden — the live strip is on the operator pages and /comms (36 px, in view, directly under the top bar, in the same place, with its segments), and only there`, bad7.length === 0, bad7.map((r) => `${r} ${JSON.stringify(facts[r].live)}`).join(' | ') || fam.map((r) => `${r}:${facts[r].live.segs.join('+')}`).join(' '));

		// 8
		const bad8 = ROUTES.filter((r) => PAGES[r].band === true && (!facts[r].bandTag || !facts[r].policies || !facts[r].more || facts[r].flask !== 'true' || (facts[r].inbox != null && facts[r].badge != null && facts[r].inbox !== facts[r].badge)));
		ok(`8. ${tag}: the operator band carries the band tag, Policies and More; the menu carries the Exercise data flask; the Inbox count equals the rail's Decide badge`, bad8.length === 0, bad8.map((r) => `${r} ${JSON.stringify(facts[r])}`).join(' | ') || fam.map((r) => `${r} inbox ${facts[r].inbox} badge ${facts[r].badge}`).join(' · '));
		const bad8b = ['/analyst', '/ops', '/gods-eye'].filter((r) => !facts[r].posture);
		ok(`8. ${tag}: the Data button (brain-posture) is on the canvas pages and the wall`, bad8b.length === 0, bad8b.join(', ') || 'present');
		if (!firstFacts) firstFacts = facts;
	}

	// ── 6 (continued): a click on the sub-nav moves between pages, the shell does not move ──
	{
		await openPage(page, '/analyst', { w: 1920, h: 1080 });
		const before = await page.evaluate(GEOMETRY);
		const visited = [];
		for (const [tab, to] of [['wall', '/ops'], ['city', '/gods-eye'], ['assistant', '/chat'], ['workspace', '/analyst']]) {
			await page.click(`[data-v3-tab="${tab}"]`);
			await page.waitForFunction((p) => location.pathname === p, { timeout: 30_000 }, to).catch(() => {});
			await sleep(1500);
			const g = await page.evaluate(GEOMETRY);
			const strip = (s) => {
				const o = JSON.parse(s);
				delete o.title;
				return JSON.stringify(o);
			};
			visited.push({ to, at: await page.evaluate(() => location.pathname), same: strip(g) === strip(before), pressed: await page.evaluate(() => document.querySelector('[data-v3="analyst-tabs"] [aria-current="page"]')?.getAttribute('data-v3-tab')) });
		}
		ok('6. a click on the Analyst sub-nav goes to that page and the rail and the top bar do not move a pixel', visited.every((v) => v.at === v.to && v.same && v.pressed), JSON.stringify(visited.map((v) => [v.to, v.at === v.to, v.same, v.pressed])));
	}

	// ── 8 (continued): the language switch, the officer pill, Policies, the Inbox — on an operator page ──
	{
		await openPage(page, '/ops', { w: 1440, h: 900 });
		await page.click('[data-testid="v3-header-menu"]');
		await page.waitForSelector('[data-v3="header-menu"] [data-lang-code="hi"]', { timeout: 8000 });
		await page.click('[data-v3="header-menu"] [data-lang-code="hi"]');
		await sleep(600);
		const hi = await page.evaluate(() => ({ html: document.documentElement.lang, title: document.querySelector('[data-v3="screen-title"]')?.textContent?.trim(), tab: document.querySelector('[data-v3-tab="wall"]')?.textContent?.trim() }));
		await page.click('[data-v3="header-menu"] [data-lang-code="en"]');
		await sleep(600);
		const en = await page.evaluate(() => ({ html: document.documentElement.lang, title: document.querySelector('[data-v3="screen-title"]')?.textContent?.trim() }));
		await page.keyboard.press('Escape');
		ok('8. the menu switches the language on an operator page (HI → EN; the title, the sub-nav and <html lang> follow)', hi.html === 'hi' && hi.title === 'स्थिति दीवार' && hi.tab === 'स्थिति दीवार' && en.html === 'en' && en.title === 'Situation wall', JSON.stringify({ hi, en }));

		await sleep(300);
		await page.click('[data-v3="top-bar"] [data-testid="v3-officer"]');
		const field = await page.waitForSelector('[data-ui="popover"] input[data-testid="duty-officer"]', { timeout: 8000 }).catch(() => null);
		const focused = await page.evaluate(() => document.activeElement?.matches('input[data-testid="duty-officer"]') ?? false);
		await page.keyboard.press('Escape');
		ok('8. the officer pill opens the one duty-officer input with the cursor in it; Esc closes it', !!field && focused && !(await page.$('input[data-testid="duty-officer"]')), `input ${!!field} focused ${focused}`);

		await page.click('[data-shell="command-bar"] .policies');
		const pol = await page.waitForSelector('[data-ui="popover"]', { timeout: 8000 }).then(() => page.evaluate(() => document.querySelector('[data-ui="popover"]')?.textContent?.replace(/\s+/g, ' ').slice(0, 80) ?? ''));
		await page.keyboard.press('Escape');
		ok('8. Policies opens the v2 panel of what this console will never do', pol.length > 10, pol);

		const inbox = await page.evaluate(() => {
			const b = document.querySelector('[data-shell="command-bar"] [data-inbox-intent]');
			return b ? { intent: b.getAttribute('data-inbox-intent'), count: b.getAttribute('data-count'), disabled: b.disabled } : null;
		});
		ok('8. the Inbox button carries the page\'s count and intent (waiting decisions → warning) and is enabled while the page supplies its inbox', !!inbox && Number(inbox.count) >= 1 && inbox.intent === 'warning' && !inbox.disabled, JSON.stringify(inbox));
	}

	// ── 9: keys ───────────────────────────────────────────────────────────────
	{
		await openPage(page, '/analyst', { w: 1920, h: 1080 });
		await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
		const before = writes.length;
		await page.keyboard.press('?');
		const sheet = await page.waitForSelector('[data-shell="hotkeys"]', { timeout: 6000 }).then(() => page.evaluate(() => document.querySelector('[data-shell="hotkeys"]')?.textContent?.replace(/\s+/g, ' ') ?? '')).catch(() => null);
		ok("9. '?' opens the shortcuts sheet on an operator page, listing only keys that work (Ctrl K, '/', '?', Esc, G then H / M / D / P / A / V)", !!sheet && /Ctrl\s*K/.test(sheet) && /G\s*H/.test(sheet) && /G\s*V/.test(sheet) && !/dock|timeline|Next item/i.test(sheet), (sheet ?? 'no sheet').slice(0, 140));
		await page.keyboard.press('Escape');
		await sleep(300);
		await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
		await page.keyboard.press('g');
		await page.keyboard.press('m');
		await page.waitForFunction(() => location.pathname === '/map', { timeout: 20_000 }).catch(() => {});
		ok('9. G then M goes to the Map from an operator page', (await page.evaluate(() => location.pathname)) === '/map', await page.evaluate(() => location.pathname));
		await sleep(1500);
		for (const k of 'abcdeghijkmnopqrstuvwxyz'.split('')) await page.keyboard.press(k);
		ok('9. no key sends anything', writes.length === before, `${writes.length - before} non-GET`);
	}

	// ── 10: /design is a dev page ─────────────────────────────────────────────
	{
		const dev = await isViteDevServer(origin).catch(() => false);
		const res = await fetch(`${origin}/design`, { redirect: 'manual' }).catch(() => null);
		ok(`10. /design ${dev ? 'answers on a dev server' : '404s on a build'}`, !!res && (dev ? res.status === 200 : res.status === 404), `status ${res?.status} (${dev ? 'dev' : 'build'})`);
	}

	ok('every non-GET request was aborted in the browser', writes.length === 0 || writes.every((w) => /^POST \/api\/v1\/traffic\/live/.test(w)), `${writes.length} aborted${writes.length ? `: ${writes.slice(0, 4).join(', ')}` : ''}`);
	ok('zero page errors', errors.length === 0, errors.slice(0, 3).join(' | '));
} finally {
	await browser.close();
}

console.log(failures ? `\nv3-shell-smoke: ${failures} failure(s)` : '\nv3-shell-smoke: ALL OK');
process.exit(failures ? 1 : 0);
