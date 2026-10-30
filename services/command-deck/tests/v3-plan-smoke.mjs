/**
 * /plan smoke (V3-P4B; V3-SPEC §6.6, colleague review) — HERMETIC: every same-origin /api/* and /gods-eye/* GET is
 * answered in the browser from Home's fixture world (tests/home-smoke.mjs homeFixtures) with the escort lanes set
 * per scenario; EVERY non-GET is ABORTED in the browser before it leaves and counted as a would-be write; third
 * parties (map tiles) are aborted. Nothing reaches any backend.
 *
 *   node tests/v3-plan-smoke.mjs [deckUrl]          (default http://127.0.0.1:5473; a DEV deck of this tree)
 *
 * The plan document: Find routes is a real call to the corridor lifecycle — its POST is aborted, so no plan can
 * come back over the wire. The routes step is reached by handing the page's ONE escort lifecycle a fixture plan
 * document through the dev server's module graph (`import('/src/lib/corridor/escort-state.svelte.ts')` returns the
 * instance the page uses; no network, no write). A dev deck is therefore required (a production build has no
 * /src/ graph). The launch itself is the real lifecycle's launch() — its POST is aborted and counted.
 *
 * Asserts:
 *   header   one line, the same on /plan, /home and /decide: the search is the bar's widest control; no status
 *            sub-line, no language switch and no exercise tag ON the bar; ONE compact menu (v3-header-menu) that
 *            carries the exercise flask (feed-provenance, data-label) while closed and holds the status line, the
 *            language switch (data-lang-code) and the v2 Exercise data panel when open; alerts and the officer
 *            control (v3-officer) unchanged;
 *   where    the place search (type → filter → Enter picks), swap, the same-place and bad-time locks, the class
 *            cards (the protocol table's lane floors), the departure line; ZERO writes before Find routes;
 *   find     a DOUBLE click on Find routes sends ONE request (POST /api/convoy/movements, aborted) and the page says
 *            no answer came back — never "planned";
 *   routes   (fixture plan, conditional) three candidates best first; the recommended one tagged by Sajag AI; only
 *            the figures the plan reports (a candidate without a time shows no minutes); the plan's state in words;
 *            the SIMULATED traffic tag; choosing a card previews it (the recommended one still "runs"); no raw
 *            registration mark without an officer (the plan's notes carry one);
 *   launch   locked until the waiver is accepted AND an officer is named — the reason says which, and pressing it
 *            while locked sends NOTHING; a half-typed name unlocks nothing; with both, a DOUBLE click sends ONE
 *            POST /api/convoy/movements/<id>/escort; its failure is shown with the lifecycle's text VERBATIM
 *            ("no confirmation", never "refused"); a refusal in the brain's words is quoted verbatim and masks
 *            its mark again once the officer is cleared;
 *   live     (an escort running on the board) adopted; the open proposal links to its Decide home; the EMULATED
 *            position tag; Follow on the map and Open the operation; Stop locked without an officer (nothing
 *            sent), and with one a DOUBLE click sends ONE stop;
 *   i18n     the menu's हि / ગુ switch <html lang> and the plan's copy;
 *   pixels   the search box and every top-bar control at IDENTICAL pixels on /plan, /home, /decide (and /map,
 *            /assistant where the tree has them), at 1920 and 1366;
 *   total    zero page errors; the would-be writes are EXACTLY [create movement, launch escort, stop escort].
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { homeFixtures } from './home-smoke.mjs';
import { HOME } from './lib/routes.mjs';

export const PLAN_MOVEMENT = 'mv-plan-nabanna-airport-01';
export const PLAN_RAW_PLATE = 'MH01AB1234';

/**
 * The fixture plan: Nabanna (PLAN_POIS[1]) to Kolkata Airport (PLAN_POIS[12]), class Z+, CONDITIONAL (the last road
 * into the airport has 4 lanes; Z+ needs 6), three candidates on the sandbox's real road segments, the decider's pick
 * applied to the primary. The third candidate reports no time (so the page must show none).
 */
export function planDoc() {
	const v = { segment_id: 1029, type: 'ROAD_WIDTH', detail: 'Maa Flyover has 4 lanes; 6 required for Z+' };
	return {
		movement_id: PLAN_MOVEMENT,
		status: 'conditional',
		hold: false,
		event_id: '7e3a0000-0000-4000-8000-000000000901',
		overall_reasoning: `VIP Road carries the least cross traffic at this hour. Strand Road is slower: a stalled truck ${PLAN_RAW_PLATE} is reported near Moulali.`,
		decider_pick: { route_id: 'r-1', confidence: 0.82, tier: 'decider', applied: true, reason: 'least cross traffic' },
		primary_route: {
			route_id: 'r-1',
			segment_ids: [1043, 1027, 1029],
			road_names: ['VIP Road', 'AJC Bose Road Flyover', 'Maa Flyover'],
			distance_m: 7400,
			estimated_time_sec: 1140,
			route_tier: 'conditional',
			lane_violations: [v],
			reason: 'Fewest signals; one 4-lane stretch at the airport gate.',
		},
		alternate_routes: [
			{
				route_id: 'r-2',
				segment_ids: [1007, 1027, 1029],
				road_names: ['Vidyasagar Flyover Ramp', 'AJC Bose Road Flyover', 'Maa Flyover'],
				distance_m: 7900,
				estimated_time_sec: 1260,
				route_tier: 'conditional',
				lane_violations: [v],
				reason: 'Along the river; two more signals.',
			},
			{
				route_id: 'r-3',
				segment_ids: [1015, 1002, 1009, 1041, 1032, 1010, 1048, 1028, 1029],
				road_names: ['Queensway - Cathedral Road', 'Howrah Bridge', 'VIP Road', 'Rash Behari Avenue', 'Rani Rashmoni Avenue', 'Diamond Harbour Road', 'AJC Bose Road Flyover', 'Maa Flyover'],
				distance_m: 14800,
				route_tier: 'conditional',
				lane_violations: [v],
				reason: 'West of the river and over Diamond Harbour Road; long.',
			},
		],
		rejected_routes: [{ route_id: 'r-4', reason: 'Strand Road: below the lane floor for most of its length' }],
	};
}

/** Home's world with the escort lanes per scenario: 'none' (nothing to adopt) or 'running' (one escort to adopt). */
export function planFixtures(now = Date.now(), { escort = 'none' } = {}) {
	const fx = homeFixtures(now);
	const base = fx.answer('/api/convoy/escorts')?.body ?? { escorts: [] };
	const lanes = escort === 'running' ? { ...base, escorts: base.escorts.map((l) => ({ ...l, status: 'running', gps_mode: 'emulated', traffic_simulated: true })) } : { ...base, escorts: [] };
	return {
		...fx,
		answer(url) {
			const p = new URL(String(url), 'http://deck.local').pathname;
			if (p === '/api/convoy/escorts') return { status: 200, body: lanes };
			return fx.answer(url);
		},
	};
}

/** Hand the page's escort lifecycle a plan document (the dev module graph; no network). */
export async function injectPlan(page, doc, { vvipClass = 'Z+', originIdx = 1, destIdx = 12 } = {}) {
	await page.evaluate(
		async (d, c, o, t) => {
			const m = await import('/src/lib/corridor/escort-state.svelte.ts');
			const lc = m.escortLifecycle;
			lc.error = null;
			lc.launchRefusal = null;
			lc.originIdx = o;
			lc.destIdx = t;
			lc.vvipClass = c;
			lc.plannedDepartureMs = Date.now() + 30 * 60_000;
			lc.movementId = d.movement_id;
			lc.doc = d;
			lc.phase = 'planned';
		},
		doc,
		vvipClass,
		originIdx,
		destIdx,
	);
}

/** Start a puppeteer page whose same-origin GETs come from `fx`; every non-GET is aborted and pushed to `writes`. */
export async function hermeticPage(browser, origin, fx, { writes, errors, width = 1920, height = 1080, tiles = false, lang = 'en' }) {
	const page = await browser.newPage();
	await page.setViewport({ width, height });
	page.on('pageerror', (e) => errors.push(e.message.slice(0, 240)));
	await page.setRequestInterception(true);
	page.on('request', (req) => {
		const u = new URL(req.url());
		if (req.method() !== 'GET' && req.method() !== 'HEAD') {
			// every write, any origin: refused in the browser, counted
			writes.push(`${req.method()} ${u.pathname}`);
			return req.abort();
		}
		if (u.origin === origin && (u.pathname.startsWith('/api/') || u.pathname.startsWith('/gods-eye/'))) {
			const a = fx.answer(u.pathname + u.search);
			return req.respond(
				a ? { status: a.status, contentType: 'application/json', body: JSON.stringify(a.body) } : { status: 404, contentType: 'application/json', body: '{"detail":"Not Found"}' },
			);
		}
		if (u.origin !== origin) {
			// map tiles only when screenshotting (real OSM, GET); everything else third-party is refused
			if (tiles && /(^|\.)tile\.openstreetmap\.org$/.test(u.hostname)) return req.continue();
			return req.abort();
		}
		return req.continue();
	});
	await page.evaluateOnNewDocument(() => {
		try {
			localStorage.setItem('sajag.v3.onboarded', '1');
		} catch {
			// storage unavailable
		}
	});
	await page.setCookie({ name: 'sajag_lang', value: lang, url: origin });
	return page;
}

export function findPuppeteer(DECK) {
	for (const from of [process.env['PUPPETEER_FROM'], path.resolve(DECK, '../../frontend/package.json')].filter(Boolean)) {
		try {
			const req = createRequire(from);
			return req('puppeteer').default ?? req('puppeteer');
		} catch {
			// next candidate
		}
	}
	return null;
}

export const CHROME = [`${process.env.HOME}/.cache/puppeteer/chrome/linux_arm-153.0.8010.36/chrome-linux-arm64/chrome`].find((p) => existsSync(p));

// ─── the smoke ───────────────────────────────────────────────────────────────

const isMain = process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url;
if (isMain) await smoke();

async function smoke() {
	const HERE = path.dirname(fileURLToPath(import.meta.url));
	const DECK = path.resolve(HERE, '..');
	const base = (process.argv[2] ?? 'http://127.0.0.1:5473').replace(/\/$/, '');
	const origin = new URL(base).origin;
	if (/:(5273|8090|8091|8092)$/.test(origin)) {
		console.error('refusing a live port');
		process.exit(2);
	}
	const puppeteer = findPuppeteer(DECK);
	if (!puppeteer) {
		console.error('puppeteer not found');
		process.exit(1);
	}

	let failures = 0;
	const ok = (name, cond, detail = '') => {
		if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
		else {
			failures++;
			console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
		}
	};
	const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
	const writes = [];
	const errors = [];
	const hook = (page) => page.evaluate(() => window.__V3_PLAN__ ?? null);
	const waitStep = (page, s, timeout = 15_000) => page.waitForFunction((x) => window.__V3_PLAN__?.step === x, { timeout }, s).catch(() => {});
	const text = (page) => page.evaluate(() => document.body.innerText);
	/** Two clicks in the same task: the second lands before any await of the first resolves. */
	const doubleClick = (page, sel) =>
		page.evaluate((s) => {
			const b = document.querySelector(s);
			b?.click();
			b?.click();
		}, sel);

	const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--window-size=1920,1080'] });
	try {
		// ── A. the flow, nothing to adopt ─────────────────────────────────────
		const fx = planFixtures(Date.now(), { escort: 'none' });
		const page = await hermeticPage(browser, origin, fx, { writes, errors });
		await page.goto(`${base}/plan`, { waitUntil: 'networkidle2', timeout: 120_000 });
		await waitStep(page, 'where', 30_000);
		await page.waitForFunction(() => document.querySelector('[data-v3="plan"]')?.getAttribute('data-ready') === 'true', { timeout: 15_000 }).catch(() => {});
		await sleep(800);

		// header: one line, the search first, one compact menu
		const header = async (p) =>
			p.evaluate(() => {
				const bar = document.querySelector('[data-v3="top-bar"]');
				const r = (el) => Math.round(el?.getBoundingClientRect().width ?? 0);
				const search = bar?.querySelector('[data-shell="command-search"]');
				const kids = [...(bar?.querySelectorAll('button, a, input') ?? [])].filter((e) => e !== search);
				const menu = bar?.querySelector('[data-testid="v3-header-menu"]');
				return {
					bar: !!bar,
					title: bar?.querySelector('[data-v3="screen-title"]')?.textContent?.trim() ?? null,
					search: r(search),
					widest: Math.max(0, ...kids.map(r)),
					height: Math.round(bar?.getBoundingClientRect().height ?? 0),
					langOnBar: bar?.querySelectorAll('[data-lang-code]').length ?? -1,
					subOnBar: !!bar?.querySelector('.sub'),
					exerciseTagOnBar: !!bar?.querySelector('.tag.dashed'),
					menu: !!menu,
					flask: menu?.querySelector('[data-testid="feed-provenance"]')?.getAttribute('data-label') ?? null,
					alerts: !!bar?.querySelector('[data-testid="v3-alerts"]'),
					officer: !!bar?.querySelector('[data-testid="v3-officer"]'),
					text: bar?.innerText ?? '',
				};
			});
		const h0 = await header(page);
		ok('header: one bar, title "Plan a movement", alerts and the officer control in place', h0.bar && h0.title === 'Plan a movement' && h0.alerts && h0.officer, JSON.stringify({ title: h0.title, height: h0.height }));
		ok('header: the search is the bar\'s widest control', h0.search > h0.widest && h0.search >= 480, `search ${h0.search} px vs ${h0.widest} px`);
		ok('header: no status line, no language switch, no exercise tag on the bar', !h0.subOnBar && h0.langOnBar === 0 && !h0.exerciseTagOnBar && !/IST/.test(h0.text), JSON.stringify({ lang: h0.langOnBar, sub: h0.subOnBar }));
		ok('header: ONE compact menu that carries the exercise flask while closed (feed-provenance=simulated)', h0.menu && h0.flask === 'simulated', `flask ${h0.flask}`);
		await page.click('[data-testid="v3-header-menu"]');
		await page.waitForSelector('[data-v3="header-menu"]', { timeout: 5000 }).catch(() => {});
		const m0 = await page.evaluate(() => {
			const m = document.querySelector('[data-v3="header-menu"]');
			return {
				langs: [...(m?.querySelectorAll('[data-lang-code]') ?? [])].map((b) => b.getAttribute('data-lang-code')),
				exercise: !!m?.querySelector('[data-shell="exercise-panel"]'),
				status: m?.querySelector('[data-v3="screen-status"]')?.textContent ?? '',
				pressed: m?.querySelector('[data-lang-code][aria-pressed="true"]')?.getAttribute('data-lang-code') ?? null,
			};
		});
		ok('menu (open): the status line, the language switch (EN pressed) and the Exercise data panel', m0.langs.join() === 'en,hi,mr' && m0.exercise && /IST/.test(m0.status) && m0.pressed === 'en', JSON.stringify(m0));
		await page.keyboard.press('Escape');
		await sleep(200);

		// where to: the place search
		const fieldVal = (sel) => page.$eval(sel, (e) => Number(e.getAttribute('data-value')));
		const pickPlace = async (sel, q) => {
			await page.click(sel);
			await page.keyboard.type(q, { delay: 20 });
			await sleep(150);
			const first = await page.evaluate(() => document.querySelector('[data-testid="v3-plan-place"]')?.textContent?.trim() ?? null);
			await page.keyboard.press('Enter');
			await sleep(150);
			return first;
		};
		const firstPick = await pickPlace('[data-testid="v3-plan-from"]', 'sect');
		ok('place search: "sect" lists Sector V, Salt Lake first; Enter picks it', firstPick === 'Sector V, Salt Lake' && (await fieldVal('[data-testid="v3-plan-from"]')) === 11, `${firstPick} → ${await fieldVal('[data-testid="v3-plan-from"]')}`);
		await page.click('[data-testid="v3-plan-swap"]');
		await sleep(100);
		const swapped = [await fieldVal('[data-testid="v3-plan-from"]'), await fieldVal('[data-testid="v3-plan-to"]')];
		ok('swap exchanges start and destination', swapped[0] === 12 && swapped[1] === 11, swapped.join(' → '));
		await pickPlace('[data-testid="v3-plan-from"]', 'nab');
		await pickPlace('[data-testid="v3-plan-to"]', 'nab');
		const same = await page.evaluate(() => ({ disabled: document.querySelector('[data-testid="v3-plan-find"]')?.disabled, why: document.querySelector('#v3p-find-why')?.textContent?.trim() }));
		ok('the same place twice locks Find routes, with the reason', same.disabled === true && /two different places/.test(same.why ?? ''), JSON.stringify(same));
		await pickPlace('[data-testid="v3-plan-to"]', 'airport');
		ok('From Nabanna, To Kolkata Airport', (await fieldVal('[data-testid="v3-plan-from"]')) === 1 && (await fieldVal('[data-testid="v3-plan-to"]')) === 12);
		const classes = await page.$$eval('[data-testid="v3-plan-class"]', (bs) => bs.map((b) => `${b.getAttribute('data-class')}:${b.textContent.replace(/\s+/g, ' ').trim()}`));
		ok('the class cards carry the protocol table (Z+ 6 lanes 3 min · Z 4 · Y 2 · X 1, no closure)', /Z\+.*6-lane floor.*3 min/.test(classes[0] ?? '') && /4-lane/.test(classes[1] ?? '') && /2-lane/.test(classes[2] ?? '') && /1-lane.*No advance closure/.test(classes[3] ?? ''), classes.join(' | '));
		await page.click('[data-testid="v3-plan-class"][data-class="Z+"]');
		await page.click('[data-testid="v3-plan-when"][data-when="at"]');
		await page.type('[data-testid="v3-plan-time"]', '25:99');
		await page.keyboard.press('Enter');
		await sleep(150);
		const bad = await page.evaluate(() => ({ disabled: document.querySelector('[data-testid="v3-plan-find"]')?.disabled, t: document.body.innerText.includes('Write the time as hh:mm') }));
		ok('a bad time locks Find routes and says how to write it', bad.disabled === true && bad.t, JSON.stringify(bad));
		await page.click('[data-testid="v3-plan-time"]', { clickCount: 3 });
		await page.keyboard.type('23:30');
		await page.keyboard.press('Enter');
		await sleep(150);
		const leaves = await page.$eval('[data-testid="v3-plan-leaves"]', (e) => e.textContent.trim()).catch(() => '');
		ok('an IST time gives the departure line', /23:30 IST/.test(leaves), leaves);
		await page.click('[data-testid="v3-plan-when"][data-when="in30"]');
		ok('ZERO writes before Find routes', writes.length === 0, writes.join(' | '));

		// find routes: a double click, one request, no answer
		await doubleClick(page, '[data-testid="v3-plan-find"]');
		await page.waitForSelector('[data-testid="v3-plan-failure"]', { timeout: 10_000 }).catch(() => {});
		await sleep(300);
		const f1 = await page.evaluate(() => ({ kind: document.querySelector('[data-testid="v3-plan-failure"]')?.getAttribute('data-kind'), t: document.querySelector('[data-testid="v3-plan-failure"]')?.innerText ?? '', step: window.__V3_PLAN__?.step }));
		ok('Find routes ×2 → ONE request (POST /api/convoy/movements, aborted)', writes.length === 1 && writes[0] === 'POST /api/convoy/movements', writes.join(' | '));
		ok('…and the page says no answer came back (never "planned"), still on Where to', f1.kind === 'no-answer' && /No answer came back/.test(f1.t) && f1.step === 'where', JSON.stringify(f1));

		// routes: the fixture plan
		await injectPlan(page, planDoc());
		await waitStep(page, 'routes');
		await sleep(400);
		const r = await page.evaluate(() => {
			const cards = [...document.querySelectorAll('[data-testid="v3-plan-route"]')];
			return {
				hook: window.__V3_PLAN__,
				cards: cards.map((c) => ({ id: c.getAttribute('data-route-id'), rec: c.getAttribute('data-recommended'), min: !!c.querySelector('[data-fig="min"]'), km: !!c.querySelector('[data-fig="km"]'), checked: c.getAttribute('aria-checked') })),
				pick: document.querySelector('[data-testid="v3-plan-pick"]')?.getAttribute('data-by') ?? null,
				pickText: document.querySelector('[data-testid="v3-plan-pick"]')?.textContent?.trim() ?? '',
				state: document.querySelector('[data-testid="v3-plan-status"]')?.getAttribute('data-state'),
				stateText: document.querySelector('[data-testid="v3-plan-status"]')?.textContent?.trim(),
				sim: document.querySelector('[data-testid="v3-plan-sim"]')?.getAttribute('data-label') ?? null,
				simText: document.querySelector('[data-testid="v3-plan-sim"]')?.textContent?.trim() ?? '',
				lines: document.querySelectorAll('[data-v3="map-thumb"] path.ln-route').length,
				dashed: document.querySelectorAll('[data-v3="map-thumb"] path.ln-dashed').length,
			};
		});
		ok('routes: three candidates, best first; the primary recommended by Sajag AI (confidence shown)', r.cards.map((c) => c.id).join() === 'r-1,r-2,r-3' && r.cards[0].rec === 'true' && r.pick === 'decider' && /0\.82/.test(r.pickText), JSON.stringify(r.cards));
		ok('only the figures the plan reports: the third candidate has no time, every one its km', r.cards[0].min && r.cards[1].min && !r.cards[2].min && r.cards.every((c) => c.km));
		ok('the plan\'s state in words (conditional → "Needs a waiver")', r.state === 'conditional' && r.stateText === 'Needs a waiver', r.stateText);
		ok('the traffic is labelled SIMULATED (honest provenance)', r.sim === 'simulated' && r.simText === 'Simulated traffic', r.simText);
		ok('the map draws the recommended route lit and the others dashed', r.lines >= 1 && r.dashed >= 1, `${r.lines} lit · ${r.dashed} dashed`);
		await page.evaluate(() => [...document.querySelectorAll('details.more')].forEach((d) => (d.open = true)));
		await sleep(100);
		const t1 = await text(page);
		ok('no raw registration mark without an officer (the plan\'s notes carry one, masked)', !t1.includes(PLAN_RAW_PLATE) && /MH01AB•+4/.test(t1), t1.includes(PLAN_RAW_PLATE) ? 'RAW MARK SHOWN' : 'masked');
		await page.click('[data-testid="v3-plan-route"][data-route-id="r-2"]');
		await sleep(150);
		const p1 = await page.evaluate(() => ({ preview: window.__V3_PLAN__?.preview, rec: window.__V3_PLAN__?.recommended, checked: document.querySelector('[data-route-id="r-2"]')?.getAttribute('aria-checked'), key: document.querySelector('[data-testid="v3-plan-key"]')?.innerText ?? '' }));
		ok('choosing Alternate A previews it; the recommended route is still the one that runs', p1.preview === 'r-2' && p1.rec === 'r-1' && p1.checked === 'true' && /For comparison/.test(p1.key), JSON.stringify(p1));
		ok('ZERO writes while comparing routes', writes.length === 1);

		// launch: locked until the waiver AND a named officer
		await page.click('[data-testid="v3-plan-continue"]');
		await waitStep(page, 'launch');
		await sleep(200);
		const lock = () => page.evaluate(() => ({ dis: document.querySelector('[data-testid="v3-plan-launch"]')?.getAttribute('aria-disabled'), why: document.querySelector('[data-testid="v3-plan-lock"]')?.textContent?.trim() }));
		const l0 = await lock();
		ok('launch: locked with the waiver as the first reason', l0.dis === 'true' && /Accept the waiver first/.test(l0.why ?? ''), JSON.stringify(l0));
		await doubleClick(page, '[data-testid="v3-plan-launch"]');
		await sleep(300);
		ok('pressing a locked Start escort sends NOTHING', writes.length === 1, writes.join(' | '));
		await page.click('[data-testid="v3-plan-waiver"]');
		await sleep(150);
		const l1 = await lock();
		ok('waiver accepted → still locked: name the duty officer', l1.dis === 'true' && /Name the duty officer/.test(l1.why ?? ''), JSON.stringify(l1));
		await page.type('[data-testid="v3-plan-officer"]', 'R. Meh');
		await sleep(150);
		const l2 = await lock();
		ok('a half-typed name unlocks nothing (set on Continue, never per keystroke)', l2.dis === 'true' && !(await hook(page))?.officerOn, JSON.stringify(l2));
		await page.type('[data-testid="v3-plan-officer"]', 'ta');
		await page.click('[data-testid="v3-plan-officer-continue"]');
		await sleep(250);
		const l3 = await lock();
		const stamp = await page.$eval('[data-testid="v3-plan-waiver-by"]', (e) => e.textContent.trim()).catch(() => '');
		ok('officer named → unlocked; the waiver is stamped with the name', l3.dis === 'false' && /R\. Mehta/.test(stamp), `${JSON.stringify(l3)} · ${stamp}`);
		await doubleClick(page, '[data-testid="v3-plan-launch"]');
		await page.waitForSelector('[data-testid="v3-plan-refusal"]', { timeout: 10_000 }).catch(() => {});
		await sleep(300);
		ok('Start escort ×2 → ONE request (POST /api/convoy/movements/<id>/escort, aborted)', writes.length === 2 && writes[1] === `POST /api/convoy/movements/${PLAN_MOVEMENT}/escort`, writes.join(' | '));
		const rf = await page.evaluate(() => ({ kind: document.querySelector('[data-testid="v3-plan-refusal"]')?.getAttribute('data-kind'), lead: document.querySelector('[data-testid="v3-plan-refusal"]')?.innerText ?? '', txt: document.querySelector('[data-testid="v3-plan-refusal-text"]')?.textContent ?? null, store: window.__V3_PLAN__?.refusal, step: window.__V3_PLAN__?.step }));
		ok('its failure: "no confirmation came back" (never "refused"), the lifecycle\'s text verbatim, still on Launch', rf.kind === 'no-answer' && /No confirmation came back/.test(rf.lead) && !/refused/i.test(rf.lead) && rf.txt === rf.store && !!rf.store && rf.step === 'launch', JSON.stringify(rf));

		// a refusal in the brain's words: quoted verbatim, masked again once the officer is cleared
		const REFUSAL = `An escort is already running for this corridor; the lead vehicle ${PLAN_RAW_PLATE} is on AJC Bose Road Flyover. Stop it first.`;
		await page.evaluate(async (s) => {
			const m = await import('/src/lib/corridor/escort-state.svelte.ts');
			m.escortLifecycle.launchRefusal = s;
			m.escortLifecycle.error = s;
		}, REFUSAL);
		await sleep(200);
		const rv = await page.evaluate(() => ({ kind: document.querySelector('[data-testid="v3-plan-refusal"]')?.getAttribute('data-kind'), lead: document.querySelector('[data-testid="v3-plan-refusal"]')?.innerText ?? '', txt: document.querySelector('[data-testid="v3-plan-refusal-text"]')?.textContent ?? null }));
		ok('a refusal in words: "refused the launch, in its words" + the text VERBATIM', rv.kind === 'refused' && /refused the launch, in its words/.test(rv.lead) && rv.txt === REFUSAL, JSON.stringify(rv));
		await page.click('[data-testid="v3-officer"]');
		await page.waitForSelector('[data-testid="duty-officer"]', { timeout: 5000 });
		await page.click('[data-testid="duty-officer"]', { clickCount: 3 });
		await page.keyboard.press('Backspace');
		await page.keyboard.press('Escape');
		await sleep(300);
		const rm = await page.evaluate(() => document.querySelector('[data-testid="v3-plan-refusal-text"]')?.textContent ?? '');
		const lm = await lock();
		ok('officer cleared → the refusal\'s mark is masked again and the launch locks again', !rm.includes(PLAN_RAW_PLATE) && /MH01AB•+4/.test(rm) && lm.dis === 'true', `${rm.slice(0, 80)} · ${lm.why}`);
		const t2 = await text(page);
		ok('no raw registration mark anywhere without an officer', !t2.includes(PLAN_RAW_PLATE));
		await page.close();

		// ── B. live: an escort running on the board (adopted) ─────────────────
		const fx2 = planFixtures(Date.now(), { escort: 'running' });
		const E = fx2.expect;
		const live = await hermeticPage(browser, origin, fx2, { writes, errors });
		await live.goto(`${base}/plan`, { waitUntil: 'networkidle2', timeout: 120_000 });
		await waitStep(live, 'live', 30_000);
		await sleep(800);
		const lv = await live.evaluate(() => ({
			step: window.__V3_PLAN__?.step,
			proposal: document.querySelector('[data-testid="v3-plan-proposal"]')?.getAttribute('href') ?? null,
			emulated: !!document.querySelector('[data-testid="v3-plan-emulated"]'),
			follow: document.querySelector('[data-testid="v3-plan-follow"]')?.getAttribute('href') ?? null,
			op: document.querySelector('[data-testid="v3-plan-operation"]')?.getAttribute('href') ?? null,
			stop: document.querySelector('[data-testid="v3-plan-stop"]')?.getAttribute('aria-disabled'),
			timer: !!document.querySelector('[data-testid="v3-plan-proposal"] [role="timer"]'),
		}));
		ok('live: the running escort is adopted (step Live)', lv.step === 'live', lv.step);
		ok('live: its open proposal links to its one Decide home, with a countdown', lv.proposal === `/decide/${encodeURIComponent(`escort-proposal:${E.ids.approval}`)}` && lv.timer, lv.proposal ?? 'none');
		ok('live: the EMULATED position is labelled', lv.emulated);
		ok('live: Follow on the map and Open the operation', !!lv.follow && lv.op === `/o/event:${encodeURIComponent(E.ids.movementEvent)}`, `${lv.follow} · ${lv.op}`);
		ok('live: Stop is locked without an officer', lv.stop === 'true');
		await doubleClick(live, '[data-testid="v3-plan-stop"]');
		await sleep(300);
		ok('pressing a locked Stop sends NOTHING', writes.length === 2, writes.join(' | '));
		await live.type('[data-testid="v3-plan-officer"]', 'R. Mehta');
		await live.keyboard.press('Enter');
		await sleep(250);
		ok('live: officer named → Stop unlocked', (await live.$eval('[data-testid="v3-plan-stop"]', (e) => e.getAttribute('aria-disabled'))) === 'false');
		await doubleClick(live, '[data-testid="v3-plan-stop"]');
		await sleep(800);
		ok('Stop ×2 → ONE request (POST /api/convoy/movements/<id>/stop, aborted)', writes.length === 3 && writes[2] === 'POST /api/convoy/movements/mv-strand-z-01/stop', writes.join(' | '));
		const stopFail = await live.$eval('[data-testid="v3-plan-stop-failure"]', (e) => e.textContent.trim()).catch(() => '');
		ok('…its failure is shown, and the escort is still shown as running (never claimed stopped)', !!stopFail && (await hook(live))?.phase === 'escorting', stopFail);

		// i18n: the menu's language switch
		const pickLang = async (p, code) => {
			if (!(await p.$(`[data-v3="header-menu"] [data-lang-code="${code}"]`))) {
				await p.click('[data-testid="v3-header-menu"]');
				await p.waitForSelector(`[data-v3="header-menu"] [data-lang-code="${code}"]`, { timeout: 5000 });
			}
			await p.click(`[data-v3="header-menu"] [data-lang-code="${code}"]`);
			await p.waitForFunction((c) => document.documentElement.lang === c, { timeout: 10_000 }, code).catch(() => {});
			await sleep(300);
		};
		await pickLang(live, 'hi');
		const hi = await live.evaluate(() => ({ lang: document.documentElement.lang, h: document.querySelector('#v3p-heading')?.textContent?.trim(), code: document.querySelector('[data-testid="v3-header-menu"] .code')?.textContent?.trim() }));
		ok('हि (from the menu) switches <html lang>, the plan\'s copy and the menu\'s code', hi.lang === 'hi' && hi.h === 'एस्कॉर्ट जारी' && hi.code === 'हि', JSON.stringify(hi));
		await pickLang(live, 'mr');
		const mr = await live.evaluate(() => ({ lang: document.documentElement.lang, h: document.querySelector('#v3p-heading')?.textContent?.trim() }));
		ok('ગુ switches to Marathi', mr.lang === 'mr' && mr.h === 'एस्कॉर्ट सुरू आहे', JSON.stringify(mr));
		await pickLang(live, 'en');
		await live.close();

		// ── C. the same header on every V3 page, at the same pixels ───────────
		// the slim header (search widest, one menu, no switch or status on the bar) on every V3 page this tree has, and
		// the search box and every control at IDENTICAL pixels on all of them, at 1920 and 1366 (a page this tree does
		// not have — /map and /assistant before V3-P4 merges — answers without a top bar and is listed as skipped)
		const CONTROLS = ['[data-shell="command-search"]', '[data-testid="v3-header-menu"]', '[data-testid="v3-alerts"]', '[data-testid="v3-officer"]', '[data-v3="screen-title"]'];
		for (const [w, hgt] of [
			[1920, 1080],
			[1366, 768],
		]) {
			const seen = {};
			const skipped = [];
			for (const route of ['/plan', HOME, '/decide', '/map', '/assistant']) {
				const p = await hermeticPage(browser, origin, planFixtures(Date.now()), { writes, errors: route === '/map' ? [] : errors, width: w, height: hgt });
				const res = await p.goto(`${base}${route}`, { waitUntil: 'domcontentloaded', timeout: 120_000 });
				const has = await p.waitForSelector('[data-v3="top-bar"] [data-testid="v3-officer"]', { timeout: 30_000 }).then(() => true).catch(() => false);
				if (!has || (res && res.status() === 404)) {
					skipped.push(route);
					await p.close();
					continue;
				}
				await sleep(1500);
				const hh = await header(p);
				seen[route] = await p.evaluate((sels) => sels.map((q) => {
					const r = document.querySelector(`[data-v3="top-bar"] ${q}`)?.getBoundingClientRect();
					return r ? [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)].join(',') : 'missing';
				}), CONTROLS);
				if (route !== '/plan') ok(`${route} @${w}: the same slim header (search widest, one menu, no switch or status on the bar)`, hh.bar && hh.menu && hh.search > hh.widest && hh.langOnBar === 0 && !hh.subOnBar && hh.alerts && hh.officer, JSON.stringify({ search: hh.search, widest: hh.widest, lang: hh.langOnBar }));
				await p.close();
			}
			const ref = seen['/plan'];
			// every control but the title (whose WIDTH is the page's own words) at identical pixels; the title's x and y too
			const diffs = Object.entries(seen).filter(([, v]) => v.some((x, i) => (i === 4 ? x.split(',').slice(0, 2).join() !== ref[i].split(',').slice(0, 2).join() : x !== ref[i]))).map(([r, v]) => `${r} ${v.join(' ')}`);
			ok(`@${w}: the search box and every control at IDENTICAL pixels on ${Object.keys(seen).join(', ')}${skipped.length ? ` (not in this tree: ${skipped.join(', ')})` : ''}`, diffs.length === 0 && Object.keys(seen).length >= 3 && ref.every((x) => x !== 'missing'), diffs.join(' | ') || ref.join(' '));
		}

		ok('zero page errors', errors.length === 0, errors.slice(0, 3).join(' | '));
		const want = ['POST /api/convoy/movements', `POST /api/convoy/movements/${PLAN_MOVEMENT}/escort`, 'POST /api/convoy/movements/mv-strand-z-01/stop'];
		ok('the would-be writes are EXACTLY: create movement ×1, launch escort ×1, stop escort ×1 (all aborted)', JSON.stringify(writes) === JSON.stringify(want), writes.join(' | '));
	} finally {
		await browser.close();
	}
	console.log(failures ? `\n${failures} FAILED` : '\nv3-plan-smoke: ALL OK');
	process.exit(failures ? 1 : 0);
}
