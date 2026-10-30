/**
 * /decide smoke (V3-P2; V3-SPEC §6.2, §7.1, §7.7, §10 P2) — HERMETIC. Every same-origin /api/* and /gods-eye/*
 * GET is answered IN THE BROWSER from the fixture world below (Home's world, tests/home-smoke.mjs, plus an
 * e-challan, an e-challan on the stolen vehicle, a pursuit opening and the decision-support object), OSM tiles
 * and every third party are aborted, and EVERY non-GET is intercepted before it leaves the browser and
 * counted: what Decide WOULD send. By default the request is aborted; where a check needs the server's answer
 * (a success, a 409 refusal) the browser is handed a canned reply — nothing ever reaches a backend.
 *
 *   node tests/decide-smoke.mjs [deckUrl]          (default http://127.0.0.1:5470; a dev deck of this tree)
 *
 * Asserts:
 *   1. the page renders with zero page errors; the queue is decisionUnits() order (soonest deadline first),
 *      its `queue-card` count = selectors.decisionUnits() = the Decide badge; every queue-card carries the
 *      unit's data-* hooks; it opens on the soonest deadline (the escort proposal);
 *   2. masking: no raw registration mark in innerText without an officer; naming one unmasks; clearing the
 *      name (top bar) masks again;
 *   3. the officer gate: before a name, every button is visible but aria-disabled with the reason; clicks,
 *      Enter, digits and letters send NOTHING;
 *   4. keyboard: J / K move the selection and the URL (/decide/<kind>:<id>, never a mark); Enter only focuses
 *      the primary; 1–4 choose a response option; R opens the reason; no single key approves;
 *   5. one POST per double click — escort approve, 108 approve, stolen authorise (a triple click each);
 *   6. the chosen response option drives the button label AND the POST body (coa_id);
 *   7. refusals verbatim, in the sheet: a decision-support 409 and an e-challan 409 print the server's own
 *      words (`decision-refusal`); an aborted request says no confirmation came back; a refused e-challan
 *      offers no Approve again; an e-challan on a stolen vehicle offers Reject only;
 *   8. a verb that needs a reason (dismiss, reject, defer) opens the reason field first — no POST without it;
 *   9. a pursuit opening refused before the wire (no approved sighting) is disabled with its reason;
 *  10. an answered escort stays locked (another click sends nothing); after a decision the sheet collapses to
 *      the outcome (verb, officer, time) with "Next decision";
 *  11. an escort proposal that runs out keeps the plan: "plan kept", buttons locked, no POST; when the brain
 *      closes it the sheet says "No one answered in time";
 *  12. deep links: /decide/<kind>:<id> opens that unit; a hostile key opens the soonest;
 *  13. accessibility: the timer is role="timer", the options a radiogroup of radios, aria-current on the
 *      selected row, every <img> has alt, the officer field is labelled;
 *  14. EN / HI / MR: the language switch translates the sheet;
 *  15. the exact list of non-GET requests Decide would have sent.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { homeFixtures } from './home-smoke.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');

/**
 * Home's world plus what Decide needs: every unit kind waits.
 *   escort-proposal   the hold at Howrah Station (Howrah Bridge, Howrah end) (48 s, or `escortIn` s)
 *   corridor-request  a 108 request (golden hour)
 *   dss               the road accident near Sector V (the C-U object: tests/fixtures/dss/dss_road_accident.json)
 *   stolen-sighting   the stolen car, two pending reads
 *   pursuit           a flagged (warrant) vehicle with a read and no approved sighting → refused before the wire
 *   echallan ×2       a speeding e-challan on a plain vehicle; a red-light e-challan on the stolen vehicle (Reject only)
 */
export function decideFixtures(now = Date.now(), opts = {}) {
	const fx = homeFixtures(now);
	const E = fx.expect;
	const iso = (ms) => new Date(ms).toISOString();
	const ago = (s) => iso(now - s * 1000);
	const id = (n) => `7e3a0000-0000-4000-8000-${String(n).padStart(12, '0')}`;
	const VEH_B = id(11);
	const VEH_C = id(12);
	const PLATE_B = 'MH01KD4521';
	const PLATE_C = 'MH08BX7730';
	const REC_SPEED = id(22);
	const REC_STOLEN_PENAL = id(23);
	const escortDeadline = opts.escortIn != null ? now + opts.escortIn * 1000 : E.escortDeadline;
	const state = { escortClosed: false };

	const penal = (rid, veh, plate, rule, text, ageS, cam) => ({
		recommendation_id: rid,
		sighting_id: null,
		vehicle_id: veh,
		plate,
		rule_id: rule,
		recommendation: text,
		evidence: { source: 'emulated_anpr', camera_id: cam, plate, speed_kmh: 82, t: ago(ageS) },
		status: 'pending',
		decided_by: null,
		decided_at: null,
		audit_tail: [],
		created_at: ago(ageS),
		pursuit: null,
	});
	const EXTRA_RECS = [
		penal(REC_SPEED, VEH_B, PLATE_B, 'R_SPEED_LIMIT', `Speed 82 km/h in a 60 km/h zone at EM-CAM-02, ${PLATE_B}`, 9 * 60, 'EM-CAM-02'),
		penal(REC_STOLEN_PENAL, E.ids.vehicle, E.rawPlate, 'R_RED_LIGHT', `Red light at EM-J05, ${E.rawPlate}`, 11 * 60, 'EM-J05'),
	];
	const VEH_C_ROW = {
		vehicle_id: VEH_C,
		plate: PLATE_C,
		vehicle_class: 'suv',
		earmark_state: 'flagged',
		earmark_reason: 'Warrant watch — court order 118/2026',
		lawful_basis: 'warrant',
		retention_until: iso(now + 20 * 86400_000),
		last_sighting: { t: ago(6 * 60), position: [88.3499, 22.5647], speed_kmh: 44, heading: 80, source: 'emulated_anpr', camera_id: 'EM-CAM-02', matched_plate_hit: 'watchlist' },
		source: 'emulated_anpr',
	};
	const dssRaw = JSON.parse(readFileSync(path.join(HERE, 'fixtures/dss/dss_road_accident.json'), 'utf8'));
	const DSS = { ...dssRaw, dss_id: E.ids.dss, event_urn: `osint_event:${E.ids.accident}`, generated_at: ago(26 * 60), expires_at: iso(E.dssExpires), state: 'proposed' };

	function answer(url) {
		let p = String(url);
		try {
			const u = new URL(p, 'http://deck.local');
			p = u.pathname + u.search;
		} catch {
			/* a bare path */
		}
		if (p === `/api/v1/decision-support/${E.ids.dss}`) return { status: 200, body: DSS };
		const a = fx.answer(p);
		if (!a) return null;
		if (/^\/api\/v1\/enforcement\/recommendations\?status=pending\b/.test(p)) return { status: 200, body: { recommendations: [...a.body.recommendations, ...EXTRA_RECS] } };
		if (/^\/api\/v1\/vehicles(\?earmark=(watch|flagged|any))?$/.test(p)) return { status: 200, body: { ...a.body, vehicles: [...a.body.vehicles, VEH_C_ROW] } };
		if (p === '/api/convoy/escorts') {
			const body = JSON.parse(JSON.stringify(a.body));
			const lane = body.escorts[0];
			if (state.escortClosed) {
				lane.approval_outcomes = [{ ...lane.pending_approval, status: 'expired', expiry_reason: 'no officer response — current plan held', decided_by: null, decided_at: null }];
				lane.pending_approval = null;
				body.pending = 0;
			} else lane.pending_approval.expires_at = iso(escortDeadline);
			return { status: 200, body };
		}
		return a;
	}

	return {
		answer,
		state,
		expect: {
			...E,
			units: 7,
			unitOrder: ['escort-proposal', 'corridor-request', 'dss', 'stolen-sighting', 'pursuit', 'echallan', 'echallan'],
			rawPlates: [E.rawPlate, PLATE_B, PLATE_C],
			ids: { ...E.ids, vehicleB: VEH_B, vehicleC: VEH_C, recSpeed: REC_SPEED, recStolenPenal: REC_STOLEN_PENAL, recNewest: id(20) },
			escortDeadline,
			movement: 'mv-strand-z-01',
		},
	};
}

// ─── the smoke ───────────────────────────────────────────────────────────────


export function loadPuppeteer() {
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

/**
 * Wire a page to a fixture world: GETs answered in the browser, non-GETs counted (and aborted, unless
 * `replies(method, path, body)` hands back a canned {status, body, delayMs}), tiles and third parties
 * aborted unless `tiles` (screenshots only: tile GETs to the public OSM servers).
 */
export async function hermetic(page, origin, fx, { writes, replies = () => null, tiles = false }) {
	await page.setRequestInterception(true);
	page.on('request', (req) => {
		const u = new URL(req.url());
		const method = req.method();
		if (u.origin === origin && (u.pathname.startsWith('/api/') || u.pathname.startsWith('/gods-eye/'))) {
			if (method !== 'GET' && method !== 'HEAD') {
				const body = req.postData() ?? '';
				writes.push({ method, path: u.pathname, body });
				const r = replies(method, u.pathname, body);
				if (!r) return req.abort();
				const send = () => req.respond({ status: r.status, contentType: 'application/json', body: JSON.stringify(r.body ?? {}) }).catch(() => {});
				return r.delayMs ? void setTimeout(send, r.delayMs) : send();
			}
			const a = fx.answer(u.pathname + u.search);
			return req.respond(
				a ? { status: a.status, contentType: 'application/json', body: JSON.stringify(a.body) } : { status: 404, contentType: 'application/json', body: '{"detail":"Not Found"}' },
			);
		}
		if (u.origin !== origin) {
			if (tiles && method === 'GET' && /(^|\.)tile\.openstreetmap\.org$/.test(u.hostname)) return req.continue();
			return req.abort();
		}
		if (method !== 'GET' && method !== 'HEAD') {
			writes.push({ method, path: u.pathname, body: req.postData() ?? '' });
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
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function smoke() {
	const base = (process.argv[2] ?? 'http://127.0.0.1:5470').replace(/\/$/, '');
	const origin = new URL(base).origin;
	if (/:(5273|8090|8091|8092)$/.test(origin)) {
		console.error('refusing a live port');
		process.exit(2);
	}
	const puppeteer = loadPuppeteer();
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

	const fx = decideFixtures(Date.now());
	const E = fx.expect;
	const writes = [];
	const errors = [];
	/** Canned replies, swapped per check (null = abort). */
	let reply = () => null;
	const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--window-size=1920,1080'] });

	const key = (kind, idv) => `${kind}:${idv}`;
	const K = {
		escort: key('escort-proposal', E.ids.approval),
		corridor: key('corridor-request', E.ids.dispatch108),
		dss: key('dss', E.ids.dss),
		stolen: key('stolen-sighting', E.ids.vehicle),
		pursuit: key('pursuit', E.ids.vehicleC),
		speed: key('echallan', E.ids.recSpeed),
		stolenPenal: key('echallan', E.ids.recStolenPenal),
	};

	const hook = (page) => page.evaluate(() => window.__V3_DECIDE__ ?? null);
	const sheet = (page) =>
		page.evaluate(() => {
			const s = document.querySelector('[data-testid="v3-decision-sheet"]');
			const p = document.querySelector('[data-testid="v3-primary"]');
			return {
				kind: s?.getAttribute('data-kind') ?? null,
				phase: s?.getAttribute('data-phase') ?? null,
				primary: p ? { label: p.textContent.trim(), disabled: p.getAttribute('aria-disabled') === 'true', action: p.getAttribute('data-action') } : null,
				secondary: [...document.querySelectorAll('[data-testid="v3-secondary"]')].map((b) => ({ action: b.getAttribute('data-action'), label: b.textContent.trim(), disabled: b.getAttribute('aria-disabled') === 'true' })),
				block: document.querySelector('[data-testid="v3-block-reason"]')?.textContent.trim() ?? null,
				refusal: document.querySelector('[data-testid="decision-refusal"]')?.textContent.replace(/\s+/g, ' ').trim() ?? null,
				outcome: document.querySelector('[data-testid="v3-outcome"]')?.getAttribute('data-mode') ?? null,
				outcomeText: document.querySelector('[data-testid="v3-outcome"]')?.textContent.replace(/\s+/g, ' ').trim() ?? null,
				reason: !!document.querySelector('[data-testid="decision-reason"], [data-testid="stolen-dismiss-reason"]'),
				changes: document.querySelector('[data-v3="change-list"] .sec-t')?.textContent.trim() ?? null,
				text: document.body.innerText,
			};
		});
	const select = async (page, k) => {
		await page.click(`[data-key="${k}"]`);
		await page.waitForFunction((x) => window.__V3_DECIDE__?.selected === x, { timeout: 5000 }, k).catch(() => {});
		await wait(250);
	};
	const posts = (re) => writes.filter((w) => re.test(w.path));

	try {
		const page = await browser.newPage();
		await page.setViewport({ width: 1920, height: 1080 });
		page.on('pageerror', (e) => errors.push(e.message.slice(0, 240)));
		await hermetic(page, origin, fx, { writes, replies: (m, p, b) => reply(m, p, b) });
		await page.setCookie({ name: 'sajag_lang', value: 'en', url: origin });
		await page.goto(`${base}/decide`, { waitUntil: 'networkidle2', timeout: 120_000 });
		await page.waitForFunction((n) => (window.__V3_DECIDE__?.units?.length ?? 0) >= n && document.querySelectorAll('[data-testid="queue-card"]').length >= n, { timeout: 40_000 }, E.units).catch(() => {});
		await wait(1500);

		// ── 1. render, order, counts, hooks ──────────────────────────────────
		const q = await page.evaluate(() =>
			[...document.querySelectorAll('[data-testid="queue-card"]')].map((a) => ({ key: a.getAttribute('data-key'), kind: a.dataset.kind, id: a.dataset.id, href: a.getAttribute('href'), current: a.getAttribute('aria-current') })),
		);
		const h = await hook(page);
		ok('the queue renders every unit kind, in decisionUnits() order (soonest deadline first, none last)', JSON.stringify(q.map((x) => x.kind)) === JSON.stringify(E.unitOrder), q.map((x) => x.kind).join(', '));
		ok('queue order = the page\'s decisionUnits() order', JSON.stringify(q.map((x) => x.key)) === JSON.stringify(h?.units ?? []));
		const badge = await page.evaluate(() => Number(document.querySelector('[data-testid="v3-decide-badge"]')?.getAttribute('data-count') ?? NaN));
		const count = await page.evaluate(() => Number(document.querySelector('[data-testid="v3-queue-count"]')?.textContent ?? NaN));
		ok('queue-cards = queue count = Decide badge = selectors.decisionUnits()', [q.length, count, badge].every((n) => n === h?.canonical) && h?.canonical === E.units, JSON.stringify({ cards: q.length, count, badge, canonical: h?.canonical }));
		ok('every queue-card carries its unit\'s data-kind / data-id hooks', q.every((x) => x.kind && x.id && x.key === `${x.kind}:${x.id}`));
		const stolenHooks = await page.evaluate((k) => {
			const a = document.querySelector(`[data-key="${k}"]`);
			return { count: a?.dataset.count, recIds: a?.dataset.recIds };
		}, K.stolen);
		ok('the stolen vehicle\'s queue-card keeps data-count and data-rec-ids (v2 contract)', stolenHooks.count === '2' && (stolenHooks.recIds ?? '').split(' ').length === 2, JSON.stringify(stolenHooks));
		ok('opens on the soonest deadline (the escort proposal), aria-current on its row', h?.selected === K.escort && q[0].current === 'true', h?.selected);
		ok('queue links are /decide/<kind>:<id> deep links that carry no mark', q.every((x) => x.href?.startsWith('/decide/') && !/(?:WB|MH)\d/i.test(decodeURIComponent(x.href))), q.map((x) => x.href).join(' '));

		// ── 2. masking ───────────────────────────────────────────────────────
		let s = await sheet(page);
		ok('no raw registration mark in innerText without an officer', E.rawPlates.every((r) => !s.text.includes(r)), E.rawPlates.filter((r) => s.text.includes(r)).join(', ') || 'clean');
		ok('the masked mark shows in a masked chip', s.text.includes(E.maskedPlate) && (await page.$$('[data-v3="plate"][data-masked="true"]')).length > 0);

		// ── 3. the officer gate ──────────────────────────────────────────────
		ok('before a name: "Who is deciding?" with the §9.1 helper, word for word', /Who is deciding\?/.test(s.text) && s.text.includes('Naming yourself shows full registration marks on this console and records your name with the decision. Attribution, not sign-in.'));
		ok('before a name: the primary is visible, aria-disabled, with the reason', !!s.primary && s.primary.disabled && /Name yourself/.test(s.block ?? ''), JSON.stringify(s.primary) + ' · ' + s.block);
		ok('the escort\'s primary says what it does ("Approve the hold")', s.primary?.label === 'Approve the hold', s.primary?.label);
		const w0 = writes.length;
		await page.click('[data-testid="v3-primary"]', { clickCount: 2 });
		await page.click('[data-testid="v3-secondary"]');
		await page.focus('[data-v3="decide"]').catch(() => {});
		await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
		for (const k of ['Enter', '1', 'a', 'y', ' ', 'Enter']) await page.keyboard.press(k);
		await wait(400);
		ok('no officer: clicks, Enter, digits and letters send NOTHING', writes.length === w0, writes.slice(w0).map((w) => `${w.method} ${w.path}`).join(' | '));

		// ── 4. keyboard ──────────────────────────────────────────────────────
		await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
		await page.keyboard.press('j');
		await wait(300);
		let h2 = await hook(page);
		const url1 = page.url();
		ok('J selects the next waiting unit and swaps the URL in place', h2?.selected === K.corridor && decodeURIComponent(url1).endsWith(`/decide/${K.corridor}`), `${h2?.selected} · ${url1}`);
		await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
		await page.keyboard.press('k');
		await wait(300);
		h2 = await hook(page);
		ok('K goes back', h2?.selected === K.escort, h2?.selected);
		await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
		await page.keyboard.press('Enter');
		const focused = await page.evaluate(() => document.activeElement?.getAttribute('data-testid'));
		ok('Enter focuses the primary button (and presses nothing)', focused === 'v3-primary' && writes.length === w0, focused ?? 'none');

		// ── name the officer (the gate) ─────────────────────────────────────
		await page.type('[data-testid="decision-officer"]', 'R. Mehta');
		await page.click('[data-testid="v3-officer-continue"]');
		await page.waitForSelector('[data-testid="v3-officer-named"]', { timeout: 5000 }).catch(() => {});
		s = await sheet(page);
		ok('named: "Deciding as R. Mehta · Change · Recorded in the audit trail"', /Deciding as R\. Mehta/.test(s.text) && /Recorded in the audit trail/.test(s.text));
		ok('named: the escort primary is enabled', s.primary && !s.primary.disabled, JSON.stringify(s.primary));
		ok('named: the stolen vehicle\'s full mark shows in the queue (officer named)', s.text.includes(E.rawPlate));

		const wN = writes.length;
		await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
		await page.keyboard.press('Enter');
		await wait(300);
		const fN = await page.evaluate(() => document.activeElement?.getAttribute('data-testid'));
		ok('named: Enter still only FOCUSES the primary — nothing is sent', fN === 'v3-primary' && writes.length === wN && !(await page.$('[data-testid="v3-outcome"]')), `${fN} · ${writes.length - wN} write(s)`);
		await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());

		// ── 5/10. escort: one POST per triple click, then locked ─────────────
		reply = (m, p) => (/\/escort\/approvals\//.test(p) ? { status: 200, body: { status: 'approved', action: 'hold_position' }, delayMs: 500 } : null);
		await page.click('[data-testid="v3-primary"]', { clickCount: 3 });
		await page.waitForSelector('[data-testid="v3-outcome"]', { timeout: 8000 }).catch(() => {});
		s = await sheet(page);
		const escortPosts = posts(/\/api\/convoy\/movements\/.*\/escort\/approvals\//);
		ok('escort approve: a triple click sends ONE POST', escortPosts.length === 1, `${escortPosts.length} POST(s)`);
		ok('the POST names the proposal and the officer', escortPosts[0] && escortPosts[0].path.endsWith(`/${E.ids.approval}`) && /"decision":"approve"/.test(escortPosts[0].body) && /R\. Mehta/.test(escortPosts[0].body), escortPosts[0]?.body);
		ok('the sheet collapses to the outcome: verb, officer, time, Next decision', s.outcome === 'done' && /Escort proposal approved/.test(s.outcomeText ?? '') && /Recorded with R\. Mehta at \d{2}:\d{2} IST/.test(s.outcomeText ?? '') && !!(await page.$('[data-testid="v3-next-decision"]')), s.outcomeText);
		const doneRow = await page.evaluate((k) => document.querySelector(`[data-key="${k}"]`)?.getAttribute('data-state'), K.escort);
		ok('the queue row turns to its outcome', doneRow === 'done', doneRow);
		await page.click('[data-testid="v3-next-decision"]');
		await wait(300);
		await select(page, K.escort);
		s = await sheet(page);
		ok('an answered escort stays locked: re-opening shows the outcome, no buttons, no second POST', s.outcome === 'done' && !s.primary && posts(/\/escort\/approvals\//).length === 1);

		// ── 8/5. 108 corridor: Defer needs a reason; approve once ───────────
		await select(page, K.corridor);
		const wC = writes.length;
		await page.click('[data-testid="v3-secondary"][data-action="defer"]');
		await wait(200);
		s = await sheet(page);
		ok('108 Defer opens the reason field first and sends nothing', s.reason && writes.length === wC, `reason ${s.reason}`);
		ok('108 primary says "Approve the corridor"', s.primary?.label === 'Approve the corridor', s.primary?.label);
		await page.keyboard.press('Escape');
		reply = (m, p) => (p === `/api/v1/dispatches/${E.ids.dispatch108}/decision` ? { status: 200, body: { dispatch_id: E.ids.dispatch108, event_id: E.ids.movementEvent, agency: 'ambulance', status: 'approved', unit_id: '108-MH-04', audit: [] }, delayMs: 400 } : null);
		await page.click('[data-testid="v3-primary"]', { clickCount: 2 });
		await page.waitForSelector('[data-testid="v3-outcome"]', { timeout: 8000 }).catch(() => {});
		const cPosts = posts(new RegExp(`/api/v1/dispatches/${E.ids.dispatch108}/decision$`));
		ok('108 approve: a double click sends ONE POST', cPosts.length === 1 && /"action":"approve"/.test(cPosts[0]?.body ?? ''), `${cPosts.length} · ${cPosts[0]?.body}`);
		s = await sheet(page);
		ok('108: the outcome says "ambulance (108) corridor approved"', /(?:\(108\)|108) corridor approved/i.test(s.outcomeText ?? ''), s.outcomeText);

		// ── 6/7/13. decision support: options, label, POST body, 409 verbatim ─
		await select(page, K.dss);
		await page.waitForSelector('[data-testid="v3-option"]', { timeout: 10_000 }).catch(() => {});
		s = await sheet(page);
		const opts = await page.evaluate(() => ({
			group: document.querySelector('[role="radiogroup"][data-testid="dss-coa-list"]') ? true : false,
			radios: [...document.querySelectorAll('[data-testid="v3-option"]')].map((o) => ({ id: o.getAttribute('data-coa-id'), role: o.getAttribute('role'), checked: o.getAttribute('aria-checked'), rec: o.getAttribute('data-recommended') })),
			blocked: [...document.querySelectorAll('[data-testid="v3-blocked-option"]')].map((b) => ({ id: b.getAttribute('data-coa-id'), best: b.getAttribute('data-best'), text: b.textContent.replace(/\s+/g, ' ').trim() })),
			floor: document.querySelector('[data-testid="dss-safety-floor"]')?.textContent.trim() ?? null,
			redaction: document.querySelectorAll('[data-v3="redaction"]').length,
		}));
		ok('DSS: the selectable options are radios in a radiogroup, the engine\'s pick preselected and marked Recommended', opts.group && opts.radios.length === 4 && opts.radios.every((r) => r.role === 'radio') && opts.radios[0].id === 'coa_std' && opts.radios[0].checked === 'true' && opts.radios[0].rec === 'true', JSON.stringify(opts.radios));
		ok('DSS: the blocked stronger option is stated (what it needs) with "Request a unit"; the vetoed one with its reason', opts.blocked.some((b) => b.id === 'coa_agg' && b.best === 'true' && /police: need 2, 1 free/.test(b.text)) && opts.blocked.some((b) => b.id === 'coa_stop_vehicles' && b.best === 'false'), JSON.stringify(opts.blocked));
		ok('DSS: the public-safety floor and the redaction chip show', !!opts.floor && opts.redaction > 0, opts.floor ?? 'none');
		const label0 = s.primary?.label;
		await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
		await page.keyboard.press('2');
		await wait(300);
		s = await sheet(page);
		const checked = await page.evaluate(() => document.querySelector('[data-testid="v3-option"][aria-checked="true"]')?.getAttribute('data-coa-id'));
		ok('key 2 chooses the second option; the button label and the change list follow it', checked === 'coa_info' && s.primary?.label !== label0 && /verify first/i.test(s.primary?.label ?? '') && /verify first/i.test(s.changes ?? ''), `${label0} → ${s.primary?.label} · ${s.changes}`);
		const DETAIL = 'decision support is no longer proposed: approved by S. Rao at 19:40';
		reply = (m, p) => (p === `/api/v1/decision-support/${E.ids.dss}/decision` ? { status: 409, body: { detail: DETAIL }, delayMs: 300 } : null);
		await page.click('[data-testid="v3-primary"]', { clickCount: 2 });
		await page.waitForSelector('[data-testid="decision-refusal"]', { timeout: 8000 }).catch(() => {});
		const dPosts = posts(new RegExp(`/api/v1/decision-support/${E.ids.dss}/decision$`));
		s = await sheet(page);
		ok('DSS approve: ONE POST, carrying the CHOSEN option (coa_id coa_info)', dPosts.length === 1 && /"coa_id":"coa_info"/.test(dPosts[0]?.body ?? '') && /"decision":"approve"/.test(dPosts[0]?.body ?? ''), dPosts.map((p) => p.body).join(' | '));
		ok('DSS 409: the server\'s own words, verbatim, IN the sheet (no toast)', (s.refusal ?? '').includes(DETAIL) && !(await page.$('[data-testid="toast"]')), s.refusal);
		// Reject: reason first, then one POST (aborted → "no confirmation came back")
		const wR = writes.length;
		await page.click('[data-testid="v3-secondary"][data-action="reject"]');
		await wait(200);
		ok('DSS Reject opens the reason field first (no POST)', (await sheet(page)).reason && writes.length === wR);
		reply = () => null;
		await page.type('[data-testid="decision-reason"]', 'duplicate of an official report');
		await page.click('[data-testid="v3-secondary"][data-action="reject"]');
		await page.waitForFunction(() => /No confirmation came back|did not go through|unreachable/i.test(document.querySelector('[data-testid="decision-refusal"]')?.textContent ?? ''), { timeout: 8000 }).catch(() => {});
		s = await sheet(page);
		const rPosts = posts(new RegExp(`/api/v1/decision-support/${E.ids.dss}/decision$`)).slice(1);
		ok('DSS Reject: ONE POST with the reason as the note', rPosts.length === 1 && /"decision":"reject"/.test(rPosts[0]?.body ?? '') && /duplicate of an official report/.test(rPosts[0]?.body ?? ''), rPosts.map((p) => p.body).join(' | '));
		ok('an aborted request is never shown as decided: it says the decision did not go through, with the client\'s own words', /No confirmation came back|did not go through/.test(s.refusal ?? '') && /unreachable/.test(s.refusal ?? '') && s.outcome === null, s.refusal);

		// ── 8/5. stolen: Dismiss needs a reason (R key too); authorise once ─
		await select(page, K.stolen);
		s = await sheet(page);
		ok('stolen: "Authorise pursuit", "Dismiss all 2…", the two steps, "Evidence only"', s.primary?.label === 'Authorise pursuit' && s.secondary[0]?.label === 'Dismiss all 2…' && /Open the pursuit/.test(s.text) && /Evidence only\./.test(s.text), JSON.stringify(s.secondary));
		ok('stolen (emulated): the FIR reads as a demo reference, never a real case (HON-4)', /demo FIR 4401\/2026/.test(s.text) && !/Reported stolen · FIR 4401/.test(s.text), (s.text.match(/[^\n]*FIR[^\n]*/g) ?? []).slice(0, 2).join(' | '));
		ok('stolen: step 2 keeps its pursuit hooks (data-kind=pursuit, data-refusal, data-step=2)', !!(await page.$(`[data-testid="pursuit-step"][data-kind="pursuit"][data-id="${E.ids.vehicle}"][data-step="2"]`)));
		const wS = writes.length;
		await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
		await page.keyboard.press('r');
		await wait(200);
		const rFocus = await page.evaluate(() => document.activeElement?.getAttribute('data-testid'));
		ok('R opens the reason field and focuses it — and sends nothing', rFocus === 'stolen-dismiss-reason' && writes.length === wS, rFocus ?? 'none');
		await page.keyboard.press('Escape');
		await page.click('[data-testid="v3-secondary"][data-action="dismiss"]');
		await wait(200);
		ok('Dismiss without a reason sends nothing', writes.length === wS);
		await page.keyboard.press('Escape');
		reply = (m, p) => (p === `/api/v1/enforcement/recommendations/${E.ids.recNewest}/decision` ? { status: 200, body: { status: 'approved' }, delayMs: 400 } : null);
		await page.click('[data-testid="v3-primary"]', { clickCount: 3 });
		await page.waitForSelector('[data-testid="v3-outcome"]', { timeout: 8000 }).catch(() => {});
		const sPosts = posts(/\/api\/v1\/enforcement\/recommendations\/[^/]+\/decision$/);
		ok('stolen authorise: a triple click sends ONE POST, for the NEWEST sighting', sPosts.length === 1 && sPosts[0].path.includes(E.ids.recNewest) && /"decision":"approve"/.test(sPosts[0]?.body ?? ''), sPosts.map((p) => p.path).join(' '));
		s = await sheet(page);
		ok('stolen: the outcome says "Pursuit authorised"', /Pursuit authorised/.test(s.outcomeText ?? ''), s.outcomeText);

		// ── 9. pursuit refused before the wire ─────────────────────────────
		await select(page, K.pursuit);
		s = await sheet(page);
		const wP = writes.length;
		await page.click('[data-testid="v3-primary"]').catch(() => {});
		await wait(300);
		ok('pursuit without an approved sighting: disabled, the reason inline, nothing sent', s.primary?.disabled && /No human-approved sighting/.test(s.block ?? '') && writes.length === wP, s.block);

		// ── 7. e-challans: 409 verbatim; stolen → Reject only ─────────────────
		await select(page, K.stolenPenal);
		s = await sheet(page);
		ok('an e-challan on a stolen vehicle offers Reject only, with the reason said', !s.primary && s.secondary.length === 1 && s.secondary[0].action === 'reject' && /can only be rejected/.test(s.text), JSON.stringify(s.secondary));
		await select(page, K.speed);
		s = await sheet(page);
		ok('a plain e-challan: "Approve the e-challan" and Reject', s.primary?.label === 'Approve the e-challan' && s.secondary[0]?.action === 'reject', s.primary?.label);
		const ECH = 'e-challan withheld: the camera calibration certificate for EM-CAM-02 has lapsed';
		reply = (m, p) => (p === `/api/v1/enforcement/recommendations/${E.ids.recSpeed}/decision` ? { status: 409, body: { detail: ECH, reason: 'calibration' }, delayMs: 300 } : null);
		await page.click('[data-testid="v3-primary"]', { clickCount: 2 });
		await page.waitForSelector('[data-testid="decision-refusal"]', { timeout: 8000 }).catch(() => {});
		await wait(600);
		s = await sheet(page);
		const ePosts = posts(new RegExp(`/api/v1/enforcement/recommendations/${E.ids.recSpeed}/decision$`));
		ok('e-challan approve: ONE POST; the 409 printed verbatim in the sheet', ePosts.length === 1 && (s.refusal ?? '').includes(ECH), `${ePosts.length} · ${s.refusal}`);
		ok('a refused e-challan never offers Approve again (never retried)', !s.primary, JSON.stringify(s.primary));

		// ── 2. clear the name (top bar) → masked again ──────────────────────
		await page.click('[data-testid="v3-officer"]');
		await page.waitForSelector('[data-testid="duty-officer"]', { timeout: 5000 });
		await page.click('[data-testid="duty-officer"]', { clickCount: 3 });
		await page.keyboard.press('Backspace');
		await page.keyboard.press('Escape');
		await page.waitForFunction((raws) => raws.every((r) => !document.body.innerText.includes(r)), { timeout: 5000 }, E.rawPlates).catch(() => {});
		s = await sheet(page);
		ok('clearing the officer masks every mark again, and the gate returns', E.rawPlates.every((r) => !s.text.includes(r)) && !!(await page.$('[data-testid="v3-officer-gate"]')));

		// ── 13. accessibility ───────────────────────────────────────────────
		await select(page, K.escort);
		await page.click('[data-testid="v3-next-decision"]').catch(() => {});
		await wait(200);
		const a11y = await page.evaluate(() => ({
			imgsNoAlt: [...document.querySelectorAll('img')].filter((i) => !i.hasAttribute('alt')).length,
			label: !!document.querySelector('label[for]') && !!document.querySelector(`#${CSS.escape(document.querySelector('[data-testid="decision-officer"]')?.id ?? 'x')}`),
			map: document.querySelector('[data-v3="map-thumb"] [role="img"]')?.getAttribute('aria-label') ?? '',
			current: document.querySelectorAll('[aria-current="true"]').length,
			btnNames: [...document.querySelectorAll('.sheet button, [data-testid="v3-sheet"] button')].every((b) => (b.textContent ?? '').trim().length > 0 || b.getAttribute('aria-label')),
		}));
		ok('a11y: every <img> has alt; the officer field is labelled; the map is a labelled image; one aria-current row; named buttons', a11y.imgsNoAlt === 0 && a11y.label && a11y.map.length > 3 && a11y.current === 1 && a11y.btnNames, JSON.stringify(a11y));
		await page.keyboard.press('Tab');

		// ── 14. language ────────────────────────────────────────────────────
		/** The language switch lives in the top bar's one compact menu (V3-P4B): open it when the choice is not showing. */
		const pickLang = async (code) => {
			if (!(await page.$(`[data-v3="header-menu"] [data-lang-code="${code}"]`))) {
				await page.click('[data-testid="v3-header-menu"]');
				await page.waitForSelector(`[data-v3="header-menu"] [data-lang-code="${code}"]`, { timeout: 5000 });
			}
			await page.click(`[data-v3="header-menu"] [data-lang-code="${code}"]`);
		};
		await select(page, K.dss);
		await pickLang('hi');
		await page.waitForFunction(() => document.documentElement.lang === 'hi', { timeout: 10_000 }).catch(() => {});
		await wait(500);
		s = await sheet(page);
		ok('हि: the sheet speaks Hindi (Who is deciding? / Pick a response)', /निर्णय कौन ले रहा है/.test(s.text) && /एक प्रतिक्रिया चुनें/.test(s.text), (s.primary?.label ?? '').slice(0, 60));
		await pickLang('mr');
		await page.waitForFunction(() => document.documentElement.lang === 'mr', { timeout: 10_000 }).catch(() => {});
		await wait(500);
		s = await sheet(page);
		ok('मरा: the sheet speaks Marathi', /निर्णय कोण घेत आहे/.test(s.text) && /प्रतिसाद निवडा/.test(s.text));
		await pickLang('en');
		await wait(300);

		ok('zero page errors (main run)', errors.length === 0, errors.slice(0, 3).join(' | '));

		// ── 12. deep links ──────────────────────────────────────────────────
		const page2 = await browser.newPage();
		await page2.setViewport({ width: 1366, height: 768 });
		page2.on('pageerror', (e) => errors.push(`deep: ${e.message.slice(0, 200)}`));
		await hermetic(page2, origin, fx, { writes, replies: () => null });
		await page2.goto(`${base}/decide/${encodeURIComponent(K.dss)}`, { waitUntil: 'networkidle2', timeout: 120_000 });
		await page2.waitForFunction(() => window.__V3_DECIDE__?.mode === 'sheet', { timeout: 30_000 }).catch(() => {});
		const d1 = await hook(page2);
		ok('deep link /decide/<kind>:<id> opens that unit (at 1366 the queue stays labelled: art only below 1280)', d1?.selected === K.dss && (await page2.evaluate(() => getComputedStyle(document.querySelector('[data-testid="queue-card"] .txt')).display)) !== 'none', d1?.selected);
		await page2.goto(`${base}/decide/${encodeURIComponent('<img src=x onerror=alert(1)>')}`, { waitUntil: 'networkidle2', timeout: 120_000 });
		await page2.waitForFunction(() => window.__V3_DECIDE__?.mode === 'sheet', { timeout: 30_000 }).catch(() => {});
		const d2 = await hook(page2);
		ok('a hostile deep link opens the soonest instead', d2?.selected === K.escort, d2?.selected);
		await page2.close();

		// ── 11. expiry keeps the plan ───────────────────────────────────────
		const fx3 = decideFixtures(Date.now(), { escortIn: 14 });
		const page3 = await browser.newPage();
		await page3.setViewport({ width: 1920, height: 1080 });
		page3.on('pageerror', (e) => errors.push(`expiry: ${e.message.slice(0, 200)}`));
		const w3 = [];
		await hermetic(page3, origin, fx3, { writes: w3, replies: () => null });
		await page3.goto(`${base}/decide`, { waitUntil: 'networkidle2', timeout: 120_000 });
		await page3.waitForFunction(() => window.__V3_DECIDE__?.mode === 'sheet', { timeout: 30_000 }).catch(() => {});
		await page3.type('[data-testid="decision-officer"]', 'R. Mehta');
		await page3.keyboard.press('Enter');
		const ring = await page3.evaluate(() => ({ timer: !!document.querySelector('[role="timer"]'), ifnot: document.querySelector('[data-testid="v3-if-no-one"]')?.textContent.trim() ?? '' }));
		ok('a time-boxed escort: role="timer" ring and "If no one answers in time, the current plan is kept"', ring.timer && /If no one answers in time/.test(ring.ifnot) && /current plan is kept/.test(ring.ifnot), ring.ifnot);
		await page3.waitForSelector('[data-testid="v3-plan-kept"]', { timeout: 30_000 }).catch(() => {});
		const ex = await sheet(page3);
		await page3.click('[data-testid="v3-primary"]', { clickCount: 2 }).catch(() => {});
		await page3.click('[data-testid="v3-secondary"]').catch(() => {});
		await wait(400);
		ok('expired: "plan kept", the buttons locked with the reason, NOTHING sent', ex.phase === 'expired' && ex.primary?.disabled && /current plan is held|plan is kept/i.test(`${ex.block} ${ex.text}`) && w3.length === 0, `${ex.phase} · ${ex.block} · ${w3.length} write(s)`);
		fx3.state.escortClosed = true;
		await page3.waitForFunction(() => window.__V3_DECIDE__?.mode === 'expired', { timeout: 45_000 }).catch(() => {});
		const ex2 = await sheet(page3);
		const tally = (await hook(page3))?.tally;
		ok('closed by the brain: "No one answered in time · the current plan was kept"; tallied as expired', ex2.outcome === 'expired' && /No one answered in time/.test(ex2.outcomeText ?? '') && tally?.expired === 1, `${ex2.outcome} · ${JSON.stringify(tally)}`);
		ok('the expiry page sent ZERO non-GET requests', w3.length === 0, w3.map((w) => `${w.method} ${w.path}`).join(' | '));
		await page3.close();

		// ── 15. the exact list of what Decide would have sent ───────────────
		const list = writes.map((w) => `${w.method} ${w.path}`);
		const expected = [
			`POST /api/convoy/movements/${E.movement}/escort/approvals/${E.ids.approval}`,
			`POST /api/v1/dispatches/${E.ids.dispatch108}/decision`,
			`POST /api/v1/decision-support/${E.ids.dss}/decision`,
			`POST /api/v1/decision-support/${E.ids.dss}/decision`,
			`POST /api/v1/enforcement/recommendations/${E.ids.recNewest}/decision`,
			`POST /api/v1/enforcement/recommendations/${E.ids.recSpeed}/decision`,
		];
		const sorted = (a) => [...a].sort();
		ok('exactly six writes, one per decision taken (and none from any gate, key or locked card)', JSON.stringify(sorted(list)) === JSON.stringify(sorted(expected)), list.join(' | '));
		ok('zero page errors', errors.length === 0, errors.slice(0, 3).join(' | '));
	} finally {
		await browser.close();
	}
	console.log(failures ? `\n${failures} FAILED` : '\ndecide-smoke: ALL OK');
	process.exit(failures ? 1 : 0);
}

const isMain = process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url;
if (isMain) await smoke();
