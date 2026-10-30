/**
 * /comms (Advisories) smoke (V3-P6A; V3-SPEC §6.7, §8) — HERMETIC: the board (GET /api/v1/events/active) and the dispatch list
 * (GET /api/v1/dispatches) are answered IN THE BROWSER from the fixtures below; every other same-origin /api and /gods-eye GET is
 * answered 404/keyless; tiles and third parties are aborted; EVERY non-GET is aborted and counted (the page may send none).
 *
 *   node tests/v3-comms-smoke.mjs [deckUrl]       (default http://127.0.0.1:5482; a dev deck of this tree)
 *   V3_SHOTS=<dir> node tests/v3-comms-smoke.mjs …  also saves screenshots
 *
 * Asserts, in EN at 1366×768 (and the checks marked * again in HI and MR at 1366, and at 1920):
 *   1. the V3 shell wraps the page exactly once (rail + slim top bar; no v2 navbar), Advisories lit in the rail, command theme;
 *   2. the events are cards in a radiogroup (the first selected), the same choice answers through comms-event-select;
 *   3. * three draft columns EN · HI · MR side by side inside the viewport, none clipped, same facts in all three;
 *   4. "Drafted — not delivered" is stated ONCE; Copy puts the WHOLE draft on the clipboard;
 *   5. an EMULATED event: the exercise prefix is a quiet tag on screen and the first thing in the copied string;
 *   6. the OPERATOR-ONLY arm (a pursuit): one badge (operator-kind), three withheld columns that are empty, Copy-less and
 *      data-facts-less, no citizen all-clear, the badge stated once;
 *   7. the OSINT arm: citizens → ONE badge (osint) carrying the verification label, the columns hidden, Copy disabled, no
 *      all-clear; zone officers → a draft that opens with the label;
 *   8. the draft log and the dispatch threads are in the side sheet: Escape closes it and returns focus; the threads ladder
 *      mirrors the backend; the audit/analysis tables are NOT on the page;
 *   9. keyboard: arrow keys move the event selection (a radio group), the audience buttons are pressed-state buttons;
 *  10. the page makes no request but GETs (zero would-be writes), no page error.
 *
 * Exit 0 with `ok <name>` lines; exit 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');

const PROC = 'eeeeeeee-bbbb-4ccc-8ddd-eeeeeeeeeeee';
const EMU = 'dddddddd-bbbb-4ccc-8ddd-eeeeeeeeeeee';
const OSNT = 'cccccccc-bbbb-4ccc-8ddd-eeeeeeeeeeee';
const PURS = 'ffffffff-bbbb-4ccc-8ddd-eeeeeeeeeeee';
const PH = (adv) => [{ label: 'w', start_time: null, end_time: null, window_start: null, window_end: null, closure_policy: { advance_closure_sec: adv } }];

/** The hermetic world: the board, the dispatches and three road segments (so the event map has something to draw). */
export function commsFixtures() {
	const board = {
		events: [
			{ event_id: PROC, event_kind: 'procession', protection_class: 'none', title: 'Procession · Smoke Puja immersion', name: 'Procession · Smoke Puja immersion', status: 'active', routes: [{ label: 'r', segment_ids: [1003, 1004] }], route_segment_ids: [1003, 1004], phases: PH(150) },
			{ event_id: EMU, event_kind: 'mass_gathering', protection_class: 'none', title: 'Mass gathering · Smoke Strand', name: 'Mass gathering · Smoke Strand', status: 'active', metadata: { source: 'event-emulator' }, routes: [{ label: 'r', segment_ids: [1004] }], route_segment_ids: [1004], phases: PH(120) },
			{ event_id: OSNT, event_kind: 'mass_gathering', protection_class: 'none', title: 'Mass gathering · Smoke crowd report', name: 'Mass gathering · Smoke crowd report', status: 'active', source_kind: 'osint', verification_state: 'NEWS-REPORTED', metadata: { source: 'osint' }, routes: [{ label: 'r', segment_ids: [1003] }], route_segment_ids: [1003], phases: PH(120) },
			{ event_id: PURS, event_kind: 'vehicle_pursuit', protection_class: 'none', title: 'Vehicle pursuit · Smoke pursuit', name: 'Vehicle pursuit · Smoke pursuit', status: 'active', routes: [{ label: 'b', segment_ids: [1003] }], route_segment_ids: [1003], phases: PH(120) },
		],
	};
	const audit = (steps) => steps.map((to, i) => ({ from_status: i ? steps[i - 1] : null, to_status: to, actor: 'smoke', note: null, at: new Date(Date.now() - (steps.length - i) * 60_000).toISOString() })).reverse();
	const dispatches = {
		dispatches: [
			{ dispatch_id: '11111111-1111-4111-8111-111111111111', event_id: PROC, agency: 'ambulance', agency_label: '108 Ambulance', unit_id: '108-14', status: 'completed', audit: audit(['requested', 'approved', 'en_route', 'on_scene', 'completed']) },
			{ dispatch_id: '22222222-2222-4222-8222-222222222222', event_id: 'other-event', agency: 'jan_rakshak', agency_label: 'Civic Volunteers', unit_id: 'JR-EM-01', status: 'cancelled', audit: audit(['requested', 'approved', 'cancelled']) },
		],
		count: 2,
	};
	const seg = (id, name, a, b) => ({ segment_id: id, road_name: name, road_class: 'primary', geometry: { type: 'LineString', coordinates: [a, b] } });
	const segments = { segments: [seg(1003, 'Vidyasagar Setu (NH12, Vidyasagar Flyover)', [88.3264, 22.5687], [88.3324, 22.5717]), seg(1004, 'Strand Road', [88.3324, 22.5717], [88.3384, 22.5727])] };
	return { board, dispatches, segments, ids: { PROC, EMU, OSNT, PURS } };
}

export async function main() {
	const base = (process.argv[2] ?? 'http://127.0.0.1:5482').replace(/\/$/, '');
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
	const fx = commsFixtures();
	const writes = [];
	const errors = [];

	const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox'] });
	async function open(lang, w, h) {
		const page = await browser.newPage();
		await page.setViewport({ width: w, height: h });
		await page.setRequestInterception(true);
		page.on('request', (req) => {
			const u = new URL(req.url());
			const json = (status, body) => req.respond({ status, contentType: 'application/json', body: JSON.stringify(body) });
			if (req.method() !== 'GET' && req.method() !== 'HEAD') {
				writes.push(`${req.method()} ${u.pathname}`);
				return req.abort();
			}
			if (u.origin !== origin) return req.abort(); // tiles and third parties: hermetic
			if (u.pathname === '/api/v1/events/active') return json(200, fx.board);
			if (u.pathname === '/api/v1/dispatches') return json(200, fx.dispatches);
			if (u.pathname === '/api/v1/spatial/segments') return json(200, fx.segments);
			if (u.pathname === '/gods-eye/mode') return json(200, { mode: 'keyless-osm' });
			if (u.pathname.startsWith('/api/') || u.pathname.startsWith('/gods-eye/')) return json(404, {});
			return req.continue();
		});
		await page.evaluateOnNewDocument(() => {
			try {
				localStorage.setItem('sajag.v3.onboarded', '1');
			} catch {}
			// capture what Copy puts on the clipboard (no real clipboard in headless)
			window.__copied = [];
			Object.defineProperty(navigator, 'clipboard', { value: { writeText: (t) => (window.__copied.push(String(t)), Promise.resolve()) }, configurable: true });
		});
		await page.setCookie({ name: 'sajag_lang', value: lang, url: origin });
		page.on('pageerror', (e) => errors.push(String(e.message).slice(0, 200)));
		await page.goto(`${base}/comms`, { waitUntil: 'domcontentloaded', timeout: 90000 });
		await page.waitForSelector('[data-screen="comms"] [data-testid="comms-event-row"]', { timeout: 40000 });
		return page;
	}
	const pick = async (page, id) => {
		await page.select('[data-testid="comms-event-select"]', id);
		await page.waitForFunction((i) => document.querySelector(`[data-testid="comms-event-row"][data-event-id="${i}"]`)?.getAttribute('aria-checked') === 'true', { timeout: 10000 }, id);
		await page.waitForFunction(() => document.querySelector('[data-testid="comms-trilingual"]')?.getAttribute('data-ready') === 'yes', { timeout: 20000 });
		await sleep(400);
	};
	const audience = async (page, a) => {
		await page.click(`[data-audience="${a}"]`);
		await sleep(400);
	};
	const read = (page) =>
		page.evaluate(() => {
			const cols = [...document.querySelectorAll('[data-testid="comms-trilingual"] [data-lang]')];
			return {
				cols: cols.map((c) => {
					const r = c.getBoundingClientRect();
					const p = c.querySelector('.adv-text');
					const copy = c.querySelector('button.copy, button[data-copy]');
					return { lang: c.getAttribute('data-lang'), withheld: c.getAttribute('data-withheld'), factsRaw: c.getAttribute('data-facts'), text: p?.textContent?.trim() ?? '', shown: r.width > 0 && r.height > 0, left: Math.round(r.left), right: Math.round(r.right), copy: copy ? { disabled: copy.disabled } : null };
				}),
				badges: [...document.querySelectorAll('[data-testid="comms-withheld-badge"]')].map((b) => ({ reason: b.getAttribute('data-withheld-reason'), text: b.textContent.trim() })),
				vw: window.innerWidth,
				bodyText: document.body.innerText,
			};
		});

	try {
		// ── EN at 1366 ────────────────────────────────────────────────────────
		const p = await open('en', 1366, 768);
		const shell = await p.evaluate(() => ({
			v3: document.querySelectorAll('[data-shell="v3"]').length,
			command: document.querySelectorAll('[data-shell="command"], [data-shell="command-bar"]').length,
			active: document.querySelector('[data-v3="rail"] [aria-current="page"], nav [aria-current="page"]')?.getAttribute('href') ?? null,
			theme: document.documentElement.dataset.theme,
			title: document.title,
			top: Math.round(document.querySelector('[data-v3="top-bar"]')?.getBoundingClientRect().height ?? 0),
		}));
		ok('1. the V3 shell wraps /comms exactly once (rail + slim top bar), no v2 navbar; Advisories lit; command theme', shell.v3 === 1 && shell.command === 0 && shell.active === '/comms' && shell.theme === 'command' && shell.top === 60, JSON.stringify(shell));
		ok('1. the tab title is the Advisories title', shell.title === 'Advisories · Sajag', shell.title);

		const radios = await p.$$eval('[role="radiogroup"] [role="radio"]', (els) => els.map((e) => ({ id: e.getAttribute('data-event-id'), on: e.getAttribute('aria-checked'), tab: e.tabIndex })));
		ok('2. the events are cards in a radiogroup, the first selected (one tab stop)', radios.length === 4 && radios[0].on === 'true' && radios.filter((r) => r.tab === 0).length === 1 && radios[0].id === PROC, JSON.stringify(radios));
		const selVal = await p.$eval('[data-testid="comms-event-select"]', (e) => e.value);
		ok('2. the same choice answers through comms-event-select, which is out of sight and out of the tab order', selVal === PROC && (await p.$eval('[data-testid="comms-event-select"]', (e) => e.tabIndex === -1 && e.getAttribute('aria-hidden') === 'true')));

		await pick(p, PROC);
		let r = await read(p);
		const three = r.cols.length === 3 && r.cols.every((c) => c.shown) && r.cols.map((c) => c.lang).join() === 'en,hi,mr';
		const side = three && r.cols[0].right <= r.cols[1].left + 1 && r.cols[1].right <= r.cols[2].left + 1 && r.cols[2].right <= r.vw;
		ok('3. three draft columns EN · HI · MR side by side inside the viewport at 1366', side, r.cols.map((c) => `${c.lang}:${c.left}-${c.right}`).join(' '));
		const facts = r.cols.map((c) => c.factsRaw);
		ok('3. the same facts in all three languages; HI is Devanagari, MR Marathi', !!facts[0] && facts[0] === facts[1] && facts[0] === facts[2] && /[ऀ-ॿ]/.test(r.cols[1].text) && /[ऀ-ॿ]/.test(r.cols[2].text) && !/[ঀ-৿]/.test(r.cols[2].text));
		ok('3. the drafts are written for the policy hold (3 min)', JSON.parse(facts[0]).minutes === 3);
		const metrics = await p.evaluate(() => [...document.querySelectorAll('[data-testid="comms-trilingual"] .adv-text')].map((e) => ({ lang: e.lang, fs: parseFloat(getComputedStyle(e).fontSize), lh: parseFloat(getComputedStyle(e).lineHeight) })));
		ok('3. draft type: 16/26 for English, 17/29 for Hindi and Marathi', metrics.length === 3 && metrics[0].fs === 16 && metrics[0].lh === 26 && metrics.slice(1).every((m) => m.fs === 17 && m.lh === 29), JSON.stringify(metrics));

		// 4 · Drafted — not delivered once; Copy puts the whole draft on the clipboard
		const said = (r.bodyText.match(/Drafted — not delivered/g) ?? []).length;
		ok('4. "Drafted — not delivered" is stated ONCE on the desk (before any toast)', said === 1, `${said}`);
		await p.click('[data-copy="en"]');
		await sleep(200);
		const copied = await p.evaluate(() => window.__copied.slice());
		ok('4. Copy puts the WHOLE English draft on the clipboard', copied.length === 1 && copied[0] === r.cols[0].text.replace(/\s+/g, ' ') || (copied.length === 1 && copied[0].trim() === r.cols[0].text.trim()), JSON.stringify(copied).slice(0, 120));
		await p.click('[data-testid="comms-generate"]');
		await sleep(700);
		const logged = await p.evaluate(() => document.body.innerText.includes('Drafted — not delivered'));
		ok('4. generating logs a draft (the toast restates it transiently; the desk still says it once)', logged);

		// 5 · EMULATED event: prefix tag + string
		await pick(p, EMU);
		r = await read(p);
		const marker = await p.$eval('[data-testid="comms-trilingual"] [data-lang="en"] .marker', (e) => e.textContent.trim()).catch(() => null);
		await p.click('[data-copy="en"]');
		await sleep(200);
		const copiedEmu = (await p.evaluate(() => window.__copied.slice())).at(-1) ?? '';
		ok('5. an EMULATED event: the exercise prefix is a quiet tag on the draft and the FIRST thing in the copied string', !!marker && /SIMULATED FEED/.test(marker) && copiedEmu.startsWith(marker) && !!(await p.$('[data-testid="comms-emulated-badge"]')), `${marker} | ${copiedEmu.slice(0, 60)}`);
		for (const l of ['hi', 'mr']) ok(`5. the ${l} draft carries the prefix too`, !!(await p.$(`[data-lang="${l}"] .marker`)));

		// 6 · operator-only arm
		await pick(p, PURS);
		r = await read(p);
		const opOk =
			r.cols.length === 3 &&
			r.cols.every((c) => c.withheld === 'yes' && c.text === '' && !c.copy && (c.factsRaw ?? '') === '') &&
			r.badges.length === 1 &&
			r.badges[0].reason === 'operator-kind' &&
			r.badges[0].text.length > 0;
		ok('6. operator-only kind: ONE badge, three withheld columns — empty, Copy-less, no data-facts', opOk, JSON.stringify({ badges: r.badges, cols: r.cols.map((c) => [c.withheld, c.text.length, !!c.copy]) }));
		ok('6. …the withheld columns are not on screen', r.cols.every((c) => !c.shown));
		ok('6. …no citizen all-clear, Regenerate demoted and disabled', await p.evaluate(() => document.querySelector('[data-testid="comms-all-clear"]')?.disabled === true && document.querySelector('[data-testid="comms-generate"]')?.closest('button')?.disabled === true && document.querySelector('[data-testid="comms-generate"]')?.getAttribute('data-demoted') === 'yes'));
		ok('6. …the citizen template preview takes the drafts\' place', !!(await p.$('[data-testid="comms-template-centre"]')));

		// 7 · OSINT arm
		await pick(p, OSNT);
		await audience(p, 'citizens');
		r = await read(p);
		const osOk = r.cols.length === 3 && r.cols.every((c) => c.withheld === 'yes' && !c.shown && c.copy?.disabled === true) && r.badges.length === 1 && r.badges[0].reason === 'osint' && /News-reported/.test(r.badges[0].text);
		ok('7. an OSINT event, citizens: ONE badge naming the verification label; columns hidden; Copy disabled', osOk, JSON.stringify({ badges: r.badges, cols: r.cols.map((c) => [c.withheld, c.shown, c.copy]) }));
		ok('7. …all-clear refused (disabled)', await p.evaluate(() => document.querySelector('[data-testid="comms-all-clear"]')?.disabled === true));
		const regen = () => p.evaluate(() => { const b = document.querySelector('[data-testid="comms-generate"]'); return { disabled: b.closest('button').disabled, demoted: b.getAttribute('data-demoted') }; });
		const rc = await regen();
		ok('7. …Regenerate is demoted and disabled for the withheld audience (nothing to generate, said by the badge)', rc.disabled === true && rc.demoted === 'yes', JSON.stringify(rc));
		await audience(p, 'ambulance108');
		r = await read(p);
		ok('7. an OSINT event, 108 control: withheld the same way', r.cols.every((c) => c.withheld === 'yes' && !c.shown) && r.badges.length === 1);
		await audience(p, 'zones');
		const rz = await regen();
		ok('7. …Regenerate is the one primary again for zone officers (a draft exists)', rz.disabled === false && rz.demoted === 'no', JSON.stringify(rz));
		r = await read(p);
		ok('7. an OSINT event, zone officers: a draft that OPENS with the verification label, Copy enabled', r.cols.every((c) => c.withheld === 'no' && c.shown && c.copy?.disabled === false) && /^\[News-reported/.test(r.cols[0].text), r.cols[0].text.slice(0, 70));
		await audience(p, 'citizens');

		// 8 · the side sheet
		await pick(p, PROC);
		await p.click('[data-testid="comms-generate"]');
		await sleep(500);
		ok('8. the draft log is not on the desk until the sheet opens', !(await p.$('[data-testid="comms-sheet"]')) && !(await p.$('ul.log')));
		await p.click('[data-testid="comms-open-log"]');
		await p.waitForSelector('[data-testid="comms-sheet"]');
		const logRows = await p.$$eval('[data-testid="comms-log"] > li', (e) => e.length);
		ok('8. the draft log lists what was generated (two entries: step 4 and this one), in the sheet', logRows === 2, `${logRows}`);
		await p.click('[data-testid="comms-tab-threads"]');
		await p.waitForSelector('.thread');
		const steps = await p.$$eval('.thread .th-step.reached', (e) => e.length);
		ok('8. the threads ladder mirrors the backend (completed reaches 5 steps)', steps === 5, `${steps}`);
		await p.click('[data-scope="all"]');
		await sleep(300);
		const exits = await p.$$eval('.th-exit', (e) => e.map((x) => x.getAttribute('data-step')));
		ok('8. the all-events view shows the cancelled exit chip', exits.includes('cancelled'), exits.join());
		await p.keyboard.press('Escape');
		await sleep(400);
		const afterEsc = await p.evaluate(() => ({ sheet: !!document.querySelector('[data-testid="comms-sheet"]'), focus: document.activeElement?.getAttribute('data-testid') }));
		ok('8. Escape closes the sheet and returns focus to the button that opened it', !afterEsc.sheet && afterEsc.focus === 'comms-open-log', JSON.stringify(afterEsc));
		ok('8. no audit or analysis table on the page (no tables at all)', (await p.$$('table')).length === 0);

		// 9 · keyboard
		await p.focus('[data-testid="comms-event-row"][aria-checked="true"]');
		await p.keyboard.press('ArrowDown');
		await sleep(300);
		const moved = await p.$eval('[data-testid="comms-event-row"][aria-checked="true"]', (e) => e.getAttribute('data-event-id'));
		ok('9. ArrowDown moves the selection to the next event (a radio group) and focus follows', moved === EMU && (await p.evaluate(() => document.activeElement?.getAttribute('data-event-id'))) === EMU, moved);
		const pressed = await p.$$eval('[data-audience]', (e) => e.map((x) => x.getAttribute('aria-pressed')));
		ok('9. the audience buttons carry their pressed state (words, not colour alone)', pressed.length === 4 && pressed.filter((x) => x === 'true').length === 1, pressed.join());
		if (SHOTS) await p.screenshot({ path: path.join(SHOTS, 'v3-comms-en-1366.png') });
		await p.close();

		// ── HI and MR at 1366: three columns still side by side ────────────────
		for (const [lang, script] of [['hi', /[ऀ-ॿ]/], ['mr', /[ऀ-ॿ]/]]) {
			const q = await open(lang, 1366, 768);
			await pick(q, PROC);
			const rr = await read(q);
			const sideLang = rr.cols.length === 3 && rr.cols.every((c) => c.shown) && rr.cols[2].right <= rr.vw && rr.cols[0].right <= rr.cols[1].left + 1;
			const bar = await q.$eval('[data-v3="screen-title"]', (e) => e.textContent.trim());
			ok(`3. ${lang}: three columns side by side at 1366; the shell and the page speak ${lang}`, sideLang && script.test(bar), `title '${bar}'`);
			ok(`3. ${lang}: nothing on the desk spills sideways`, await q.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1 && !document.querySelector('.desk') || document.querySelector('.desk').scrollWidth <= document.querySelector('.desk').clientWidth + 1));
			if (SHOTS) await q.screenshot({ path: path.join(SHOTS, `v3-comms-${lang}-1366.png`) });
			await q.close();
		}

		// ── 1920 ──────────────────────────────────────────────────────────────
		const big = await open('en', 1920, 1080);
		await pick(big, PROC);
		const rb = await read(big);
		ok('3. 1920: three columns side by side, inside the viewport', rb.cols.length === 3 && rb.cols.every((c) => c.shown) && rb.cols[2].right <= rb.vw);
		if (SHOTS) await big.screenshot({ path: path.join(SHOTS, 'v3-comms-en-1920.png') });
		await big.close();

		// 10 · no writes, no page error
		ok('10. zero would-be writes: every non-GET was aborted and none was attempted', writes.length === 0, writes.join(' | '));
		const real = errors.filter((e) => !/Failed to fetch|NetworkError|tile/i.test(e));
		ok('10. no page error', real.length === 0, real.slice(0, 3).join(' | '));
	} finally {
		await browser.close().catch(() => {});
	}
	if (failures > 0) {
		console.error(`v3-comms-smoke: ${failures} FAILURE(S)`);
		process.exit(1);
	}
	console.log('ok   v3-comms-smoke — all assertions passed');
	process.exit(0);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
