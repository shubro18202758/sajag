/**
 * DSS card headless smoke (fix round 2, audit S2: the defects lived in the
 * .svelte wiring, which the component-stubbed unit bundles cannot see).
 *
 *   node tests/dss-card-smoke.mjs [deckUrl]        (default http://127.0.0.1:5422)
 *
 * Drives the /design/dss harness on a dev deck (the harness seeds both dss
 * fixtures offline; nothing is polled) and asserts the CARD WIRING end to
 * end, under SwiftShader. EVERY non-GET /api request is refused with a 503
 * and logged — this smoke NEVER writes; the single POST it expects is the
 * officer's Defer click, and the refusal it provokes is part of the check.
 *
 * Asserts:
 *   1. the harness mounts and the dss proposal card renders;
 *   2. with a named officer and NO note, Defer is disabled while Approve is
 *      ENABLED — the gates differ (mutant 1c);
 *   3. with a note, Defer is enabled and its click sends EXACTLY ONE POST,
 *      carrying decision "defer", the officer and the note (mutants 1b, 1d);
 *   4. the refused (503) defer shows the writer's failure line in the card —
 *      not an unhandled rejection (fix round 2, audit item 9);
 *   5. the blocked-best banner sits ABOVE "What changes" (mutant 6a);
 *   6. the raw engine enum `request_units` appears nowhere in the DOM, and
 *      the banner links Dispatch instead of writing (fix round 2, item 2);
 *   7. the reason label and placeholder are the dss-specific ones, not the
 *      deferral-optional fallback (mutants 8a, 8b);
 *   8. each infeasible/vetoed COA row states its reason EXACTLY once
 *      (mutant 7b);
 *   9. the public-safety floor line is visible for the road fixture and
 *      absent for the weather fixture (fix round 2, item 5);
 *  10. clicking the inspector section's `dss-link` keeps location.pathname
 *      and opens the Inbox with the card (mutant 2b);
 *  11. zero page errors for the whole run.
 *
 * On a harness without the officer toggle / fixture switch (an older page),
 * the smoke falls back to `?officer=1` and skips the fixture sub-check, so
 * the card assertions still run against it.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');

// Puppeteer + cached Chrome live in the repo's frontend/ tree (the same
// candidates as tests/design-smoke.mjs).
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

/** The pinned dss reason copy (packs.decisions EN) — the per-kind strings, and the wrong fallbacks. */
const DSS_HINT = '(needed to reject or defer; sent with the decision)';
const DSS_PLACEHOLDER = 'e.g. awaiting the official confirmation';
const FALLBACK_HINT = '(optional; sent with a deferral)';
const FALLBACK_PLACEHOLDER = 'e.g. duplicate read, wrong vehicle class';
const NOTE = 'awaiting the official confirmation';
const OFFICER = 'Sandbox Officer';

const origin = (process.argv[2] ?? 'http://127.0.0.1:5422').replace(/\/+$/, '');
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(origin)) throw new Error(`dev deck URL only, got ${origin}`);

const browser = await puppeteer.launch({ executablePath, headless: 'new', args: SWIFTSHADER_ARGS });
let pageerrors = 0;

/** The card's live wiring, read in one pass. The queue column renders its own
 * collapsed dss card (w=0): everything card-scoped reads the VISIBLE one. */
async function scan(p) {
	return p.evaluate(() => {
		const vis = (el) => {
			const r = el.getBoundingClientRect();
			return r.width > 0 && r.height > 0;
		};
		const T = (e) => (e?.textContent ?? '').trim().replace(/\s+/g, ' ');
		const card = [...document.querySelectorAll('[data-testid="proposal-card"][data-kind="dss"]')].find(vis) ?? null;
		const btn = (re, root = document) => [...root.querySelectorAll('button')].filter(vis).find((b) => re.test(T(b)));
		const disabledOf = (b) => !!b && (b.disabled || b.getAttribute('aria-disabled') === 'true');
		const defer = card ? btn(/^\s*Defer\s*$/, card) : btn(/^\s*Defer\s*$/);
		const approve = card ? btn(/^\s*Approve\s*$/, card) : null;
		const banner = card ? card.querySelector('[data-testid="dss-best-blocked"]') : document.querySelector('[data-testid="dss-best-blocked"]');
		const whatChanges = card ? [...card.querySelectorAll('h4, .lbl')].find((e) => /What changes/i.test(T(e))) : null;
		const labels = card ? [...card.querySelectorAll('label')].map(T) : [];
		const reasonInput = card?.querySelector('[data-testid="decision-reason"]');
		const html = document.documentElement.outerHTML;
		return {
			pathname: location.pathname,
			cardMounted: !!card,
			deferDisabled: disabledOf(defer),
			approveDisabled: disabledOf(approve),
			banner: banner ? { text: T(banner).slice(0, 140), bottom: Math.round(banner.getBoundingClientRect().bottom), link: banner.querySelector('a')?.getAttribute('href') ?? null, needsEvent: !!banner.querySelector('[data-testid="dss-dispatch-needs-event"]') } : null,
			whatChangesTop: whatChanges ? Math.round(whatChanges.getBoundingClientRect().top) : null,
			rawEnumInDom: (html.match(/request_units/g) || []).length,
			reasonLabelText: labels.find((t) => t.startsWith('Reason')) ?? null,
			reasonPlaceholder: reasonInput?.getAttribute('placeholder') ?? null,
			coaRows: [...document.querySelectorAll('[data-testid="dss-coa"]')]
				.filter(vis)
				.map((e) => {
					const t = T(e);
					return {
						id: e.dataset.coaId,
						selectable: e.dataset.selectable,
						infeasible: (t.match(/Resource-infeasible/g) || []).length,
						vetoed: (t.match(/Vetoed/g) || []).length,
					};
				}),
			floor: [...document.querySelectorAll('[data-testid="dss-safety-floor"]')].filter(vis).map((e) => T(e).slice(0, 100)),
			refusalLine: !!card?.querySelector('[data-testid="decision-refusal"]'),
			officerToggle: document.querySelector('[data-testid="harness-officer"]')?.getAttribute('data-on') ?? null,
			fixtureButtons: [...document.querySelectorAll('[data-testid="harness-fixture"]')].map((b) => b.getAttribute('data-fixture')),
			dssLink: [...document.querySelectorAll('[data-testid="dss-link"]')].filter(vis).map((e) => T(e).slice(0, 60)),
			rightPanel: document.querySelector('[data-right-panel]')?.getAttribute('data-right-panel') ?? null,
			inboxCardMounted: !!document.querySelector('[data-testid="proposal-card"][data-kind="dss"]'),
			subjectLabel: card?.querySelector('.ttl')?.textContent?.trim().slice(0, 60) ?? null,
		};
	});
}

try {
	const page = await browser.newPage();
	await page.setViewport({ width: 1920, height: 1080 });
	// bound every action/evaluate: a wedged page fails loudly instead of hanging the run
	page.setDefaultTimeout(45000);
	page.setDefaultNavigationTimeout(90000);
	const refused = [];
	await page.setRequestInterception(true);
	page.on('request', (req) => {
		const u = new URL(req.url());
		if (u.pathname.startsWith('/api/') && req.method() !== 'GET') {
			refused.push(`${req.method()} ${u.pathname} body=${(req.postData() || '').slice(0, 300)}`);
			return req.respond({ status: 503, contentType: 'application/json', body: '{"error":"smoke: writes refused"}' });
		}
		return req.continue();
	});
	page.on('pageerror', (e) => {
		pageerrors++;
		console.error(`     pageerror: ${e.message.slice(0, 200)}`);
	});

	// 1. the harness mounts, the card renders
	await page.goto(`${origin}/design/dss?open=1`, { waitUntil: 'networkidle2', timeout: 120000 }).catch(() => {});
	await sleep(9000);
	let s = await scan(page);
	ok('harness: the page mounts and the dss proposal card renders', s.cardMounted, s.cardMounted ? s.subjectLabel : 'no dss card');

	// officer: the harness toggle, else the ?officer=1 fallback (an older harness page)
	if (s.officerToggle != null) {
		for (let i = 0; i < 3 && s.officerToggle !== '1'; i++) {
			await page.click('[data-testid="harness-officer"]');
			await sleep(1200);
			s = await scan(page);
		}
	} else {
		await page.goto(`${origin}/design/dss?open=1&officer=1`, { waitUntil: 'networkidle2', timeout: 120000 }).catch(() => {});
		await sleep(9000);
		s = await scan(page);
	}
	ok('harness: the duty officer is named', s.officerToggle === '1' || s.officerToggle == null, `toggle=${String(s.officerToggle)}`);

	// 2. with an officer and NO note: Defer disabled, Approve enabled (the gates differ)
	ok('defer: disabled with no note while Approve is enabled (the COA rules do not gate Defer)', s.deferDisabled && !s.approveDisabled, `deferDisabled=${s.deferDisabled} approveDisabled=${s.approveDisabled}`);

	// 3. with a note: Defer enabled; the click sends ONE POST with the decision, officer and note
	{
		const rs = await page.evaluateHandle(() => {
			const card = [...document.querySelectorAll('[data-testid="proposal-card"][data-kind="dss"]')].find((e) => e.getBoundingClientRect().width > 0);
			return card?.querySelector('[data-testid="decision-reason"]') ?? null;
		});
		const rsEl = rs.asElement();
		if (!rsEl) throw new Error('the visible dss card has no reason input');
		await rsEl.click();
		await rsEl.type(NOTE, { delay: 4 });
	}
	await sleep(900);
	s = await scan(page);
	ok('defer: enabled once the footer reason is typed', !s.deferDisabled, `deferDisabled=${s.deferDisabled}`);
	const before = refused.length;
	const deferBtn = await page.evaluateHandle(() => {
		const card = [...document.querySelectorAll('[data-testid="proposal-card"][data-kind="dss"]')].find((e) => e.getBoundingClientRect().width > 0);
		return [...(card?.querySelectorAll('button') ?? [])].find((b) => /^\s*Defer\s*$/.test(b.textContent || '')) ?? null;
	});
	const clickable = await page.evaluate((b) => !!b && !b.disabled, deferBtn);
	if (clickable) {
		await deferBtn.asElement().click();
		await sleep(2500);
	}
	const posts = refused.slice(before);
	ok('defer: the click sends EXACTLY ONE POST', posts.length === 1, `${posts.length} POST(s): ${posts[0] ?? ''}`);
	const body = (() => {
		try {
			return JSON.parse((posts[0]?.split('body=')[1] ?? '{}').replace(/,ucid=\d+$/, ''));
		} catch {
			return {};
		}
	})();
	ok('defer: the POST carries decision defer, the officer and the note', body.decision === 'defer' && body.officer === OFFICER && body.note === NOTE, JSON.stringify(body).slice(0, 160));

	// 4. the refused defer shows the writer's failure line — never a silent unhandled rejection
	s = await scan(page);
	ok('defer: the refused (503) decision shows the failure line in the card', s.refusalLine, `refusalLine=${s.refusalLine}`);

	// 5. the banner sits ABOVE "What changes"
	ok('banner: the blocked-best banner renders above "What changes"', !!s.banner && s.whatChangesTop != null && s.banner.bottom <= s.whatChangesTop, `banner.bottom=${s.banner?.bottom} whatChanges.top=${s.whatChangesTop}`);

	// 6. no raw enum anywhere; the banner links Dispatch instead of writing
	ok('banner: the raw engine enum request_units appears nowhere in the DOM', s.rawEnumInDom === 0, `${s.rawEnumInDom} occurrence(s)`);
	// the harness subject is an UNPROMOTED OSINT report: there is no corridor event to request units against, so the
	// banner says so honestly instead of linking a Dispatch form bound to some other event (orchestrator make-up, R2)
	ok('banner: an unpromoted report offers no Dispatch link and says units come once it is a corridor event', !s.banner?.link && s.banner?.needsEvent === true, `link=${String(s.banner?.link)} needsEvent=${s.banner?.needsEvent}`);

	// 7. the reason label and placeholder are the dss-specific ones
	ok(
		'reason: the label is the dss hint (reject AND defer), not the deferral-optional fallback',
		typeof s.reasonLabelText === 'string' && s.reasonLabelText.includes(DSS_HINT) && !s.reasonLabelText.includes(FALLBACK_HINT),
		String(s.reasonLabelText),
	);
	ok('reason: the placeholder is the dss example, not the generic fallback', s.reasonPlaceholder === DSS_PLACEHOLDER && s.reasonPlaceholder !== FALLBACK_PLACEHOLDER, String(s.reasonPlaceholder));

	// 8. each infeasible/vetoed row states its reason EXACTLY once
	{
		const blocked = s.coaRows.filter((r) => r.selectable === '0');
		ok('coas: the infeasible and vetoed rows render', blocked.length >= 2, JSON.stringify(s.coaRows));
		ok('coas: each blocked row states its reason EXACTLY once', blocked.length > 0 && blocked.every((r) => r.infeasible === 1 || r.vetoed === 1), JSON.stringify(blocked));
	}

	// 9. the public-safety floor line: visible for the road fixture, absent for the weather one
	ok('floor: the public-safety floor line is visible for the road fixture', s.floor.length === 1 && s.floor[0].startsWith('Public-safety floor'), JSON.stringify(s.floor));
	const fixtures = s.fixtureButtons;
	if (fixtures.includes('weather_hazard')) {
		await page.click('[data-testid="harness-fixture"][data-fixture="weather_hazard"]');
		await sleep(2000);
		s = await scan(page);
		ok('floor: no floor line for the weather fixture (floor none)', (s.floor ?? []).length === 0 && (s.subjectLabel ?? '').includes('Weather hazard'), `floor=${JSON.stringify(s.floor)} subject=${s.subjectLabel}`);
		await page.click('[data-testid="harness-fixture"][data-fixture="road_accident"]');
		await sleep(2000);
		s = await scan(page);
		ok('floor: the road fixture shows the line again after the switch back', s.floor.length === 1, JSON.stringify(s.floor));
	} else {
		console.log('skip  floor: fixture switch (no harness-fixture buttons on this page)');
	}

	// 10. the inspector section's dss-link keeps the path and opens the Inbox
	{
		const tabs = await page.evaluateHandle(() => [...document.querySelectorAll('button')].find((b) => /Inspector sections/.test(b.textContent || '')));
		if (await page.evaluate((b) => !!b, tabs)) {
			await tabs.asElement().click();
			await sleep(1200);
			s = await scan(page);
			ok('inspector: the dss section renders with its link card', s.dssLink.length === 1, JSON.stringify(s.dssLink));
			// the section's own hook (SPEC §12.4 `dss-section`, audit E-S7B D1): the link card sits INSIDE it
			const sec = await page.evaluate(() => ({ n: document.querySelectorAll('[data-testid="dss-section"]').length, linkInside: !!document.querySelector('[data-testid="dss-section"] [data-testid="dss-link"]') }));
			ok('inspector: the Decision support section carries data-testid="dss-section" with the link card inside it', sec.n >= 1 && sec.linkInside, JSON.stringify(sec));
			const link = await page.$('[data-testid="dss-link"]');
			await link?.click();
			await sleep(2500);
			s = await scan(page);
			ok('inspector: the dss-link click KEEPS the route (no navigation)', s.pathname === '/design/dss', s.pathname);
			ok('inspector: the dss-link click opens the Inbox with the card', s.rightPanel === 'inbox' && s.inboxCardMounted, `panel=${s.rightPanel} card=${s.inboxCardMounted}`);
		} else {
			ok('inspector: the sections tab exists', false, 'no "Inspector sections" tab');
		}
	}

	// 11. zero page errors for the whole run
	ok('shell: zero page errors for the whole run', pageerrors === 0, `${pageerrors} pageerror(s)`);
	// and nothing but the officer's own defer POST was ever attempted
	ok('shell: the smoke wrote nothing but the one refused defer POST', refused.length === 1 && (refused[0] ?? '').includes('/decision'), `${refused.length} write(s) attempted`);

	await page.screenshot({ path: path.join(DECK, 'tests/artifacts/dss-card-smoke.png') }).catch(() => {});
	await page.close();
} finally {
	await browser.close();
}

if (failures) {
	console.error(`dss-card-smoke: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('ok   dss-card-smoke — all assertions passed');
process.exit(0);
