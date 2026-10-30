/**
 * /o/<urn> smoke (V3-P3; V3-SPEC §5.4, §6.3, §6.4, §8, §10 P3) — HERMETIC: every same-origin /api/* and
 * /gods-eye/* GET is answered in the browser from the fixture world below (404 for what the page does not
 * need), every non-GET is REFUSED (aborted) and counted, every third-party request (map tiles) is aborted —
 * the hero then draws the deck's own road network.
 *
 *   node tests/object-page-smoke.mjs [deckUrl]       (default http://127.0.0.1:5471; a dev deck of this tree)
 *
 * The fixture world is Home's (tests/home-smoke.mjs homeFixtures: units, events, a stolen vehicle and its
 * lawful reads, a 108 request, four OSINT reports, cameras, junctions, real sandbox road geometry) plus what
 * an object page reads beyond Home: one dossier per record (GET /city/entity/{kind}/{id}: entity, related,
 * audit), a named place, and OSINT per-source rows built to break every link rule:
 *
 *   the accident (NEWS-REPORTED)   two news sources — one LEAKS an https url (must never become a link) —
 *                                  and a CONTEXT member on an official tier (a district warning: must never
 *                                  be a source row, never counted, never make "official" true); the summary
 *                                  carries [AGE]; its audit text carries a raw mark
 *   the weather (OFFICIAL-VERIFIED) an official https source (the ONE link, rel="noopener noreferrer"), an
 *                                  official source with an http url (no link), an aggregator on a .gov.in
 *                                  address with an https url (no link: officialness rides the tier)
 *   the robbery                    a [PERSON] redaction
 *   a sighting                     its dossier answers 404 → "Withheld: no lawful basis"
 *
 * Asserts, per kind (event, report, vehicle, place, operation, junction, camera, dispatch, recommendation,
 * sighting): the page renders its title, ONE provenance tag with the honest label, its tabs, and the Record
 * tab holds every property row the adapter's inspector view has; zero page errors; ZERO non-GET on load.
 * Then the rules:
 *   - masking: no raw mark in innerText on the vehicle, sighting, recommendation and event pages without an
 *     officer (masked chips with their lock); naming the officer through the top bar shows it; clearing masks
 *   - OSINT DOM: no a[href] to any news / social host anywhere; the only off-site links are the official
 *     tier's https link (rel noopener noreferrer) and the OSM credit; redactions render as chips, never the
 *     bracketed code; the context member is listed apart and not counted
 *   - one-POST rules: Ask about it sends exactly one POST per press (a second press while it streams sends
 *     none); a lifecycle verb without an officer sends none; with one, a double press sends exactly one
 *   - keyboard: the tablist has one tab stop, → / ← / End move and select, the panel follows
 *   - a11y: the hero is role="img" with a label; tabs have aria-controls; every <img> has alt; the Ask and More
 *     buttons are named; the decision card's countdown is role="timer"; the decision link opens its one home
 *   - language: हि turns the tabs to Hindi
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { homeFixtures } from './home-smoke.mjs';

/** Home's world + dossiers, a place and the OSINT source rows (see the header). */
export function objectFixtures(now = Date.now()) {
	const fx = homeFixtures(now);
	const E = fx.expect;
	const iso = (ms) => new Date(ms).toISOString();
	const ago = (s) => iso(now - s * 1000);
	const snap = fx.answer('/api/v1/city/entities').body;
	const segs = fx.answer('/api/v1/spatial/segments?min_lon=0').body.segments;
	const byUrn = (u) => snap.entities.find((e) => e.urn === u);
	const ids = E.ids;
	const RAW = E.rawPlate;

	// ── the OSINT reports, made richer ─────────────────────────────────────
	const accident = byUrn(`osint_event:${ids.accident}`);
	Object.assign(accident.props, {
		correlated_classes: ['road_accident', 'public_conflict'],
		independent_publishers: 2,
		source_count: 3,
		context_members: 1,
		sources: [
			{ signal_id: 'sig-a1', publisher: 'news-a.example', title: 'Car crashes into three vehicles near club; [AGE] rider hurt', fetch_mode: 'cached-sample', url: 'https://news-a.example/story/123' },
			{ signal_id: 'sig-b1', publisher: 'news-b.example', title: 'Sector V - New Town link pile-up near Salt Lake slows evening traffic', fetch_mode: 'live', url: null },
			{ signal_id: 'sig-ctx', publisher: 'sachet.ndma.gov.in', title: 'District warning', fetch_mode: 'live', url: 'https://sachet.ndma.gov.in/cap/ctx' },
		],
		source_notes: [
			{ signal_id: 'sig-a1', source_tier: 'aggregator', link_note: 'source link withheld — may name a person' },
			{ signal_id: 'sig-b1', source_tier: 'aggregator', link_note: 'source link withheld — may name a person' },
			{ signal_id: 'sig-ctx', source_tier: 'official' },
		],
		second_order: [
			{ kind: 'event', urn: `event:${ids.movementEvent}`, segment_id: 1045, note: 'On an active protected-movement corridor' },
			{ kind: 'dispatch', urn: `dispatch:${ids.dispatch108}`, segment_id: 1045, note: 'On a 108 corridor route' },
		],
	});
	Object.assign(accident.props.provenance, { context_publishers: ['sachet.ndma.gov.in'], context_note: 'District warning in effect' });
	const weatherId = snap.entities.find((e) => e.kind === 'osint_event' && e.verification_state === 'OFFICIAL-VERIFIED').id;
	const weather = byUrn(`osint_event:${weatherId}`);
	Object.assign(weather.props, {
		independent_publishers: 1,
		sources: [
			{ signal_id: 'sig-w1', publisher: 'sachet.ndma.gov.in', title: 'Light rain likely at isolated places over Kolkata district', fetch_mode: 'live', url: 'https://sachet.ndma.gov.in/cap/alert/1' },
			{ signal_id: 'sig-w2', publisher: 'mausam.imd.gov.in', title: 'District nowcast', fetch_mode: 'live', url: 'http://mausam.imd.gov.in/nowcast' },
			{ signal_id: 'sig-w3', publisher: 'wb.gov.in', title: 'Press note on the rain', fetch_mode: 'live', url: 'https://wb.gov.in/press/1' },
		],
		source_notes: [
			{ signal_id: 'sig-w1', source_tier: 'official' },
			{ signal_id: 'sig-w2', source_tier: 'official' },
			{ signal_id: 'sig-w3', source_tier: 'aggregator', link_note: 'source link withheld — may name a person' },
		],
	});
	const robbery = snap.entities.find((e) => e.kind === 'osint_event' && /Robbery/.test(e.props.summary ?? ''));
	robbery.props.summary = 'Robbery reported at a shop near Babughat (Strand Road); shopkeeper [PERSON] unhurt';

	// ── a named place (gazetteer) ──────────────────────────────────────────
	const PLACE = {
		urn: 'place:sector_v_salt_lake', kind: 'place', id: 'sector_v_salt_lake', label: 'Sector V', lon: 88.4414, lat: 22.5799, state: null, band: null,
		source: 'osint', verification_state: null, credibility: null, t: null, age_sec: null, links: [`osint_event:${ids.accident}`, 'segment:1045'],
		props: { feature_type: 'landmark', canonical_name: 'Sector V', surface_forms: ['Sector V', 'Sector V Salt Lake', 'সেক্টর ফাইভ'], segment_id: 1045, osint_event_count: 1 },
	};
	snap.entities.push(PLACE);
	accident.links = [...new Set([...(accident.links ?? []), 'place:sector_v_salt_lake'])];

	// ── segments as entities (the dossier's related "on_road") ──────────────
	const segEntity = (n) => {
		const s = segs.find((x) => x.segment_id === n);
		const c = s.geometry.coordinates[Math.floor(s.geometry.coordinates.length / 2)];
		return { urn: `segment:${n}`, kind: 'segment', id: String(n), label: s.road_name, lon: c[0], lat: c[1], state: 'flowing', band: null, source: 'live', verification_state: null, credibility: null, t: null, age_sec: null, links: [], props: { road_name: s.road_name, road_class: s.road_class, lanes: s.lanes } };
	};

	// ── audit rows (wire FeedItems) ─────────────────────────────────────────
	const feed = (id, sAgo, kind, urns, actor, actorKind, text, extra = {}) => ({
		id, t: ago(sAgo), kind, urns, actor, actor_kind: actorKind, text, source: extra.source ?? 'live', verification_state: extra.verification ?? null, credibility: extra.credibility ?? null, severity: 'info', props: {},
	});
	const AUDIT = {
		[accident.urn]: [
			feed('os-1', 46 * 60, 'osint', [accident.urn], 'osint-ingress', 'machine', 'First report published (news-a.example)', { source: 'osint', verification: 'NEWS-REPORTED' }),
			feed('os-2', 34 * 60, 'osint', [accident.urn], 'osint-ingress', 'machine', 'Second publisher agrees (news-b.example)', { source: 'osint', verification: 'NEWS-REPORTED' }),
			feed('os-3', 27 * 60, 'osint', [accident.urn, 'segment:1045'], 'osint-geo', 'machine', 'Place matched: Sector V - New Town link', { source: 'osint', verification: 'NEWS-REPORTED' }),
			feed('os-4', 26 * 60, 'osint', [accident.urn], 'decision-support', 'machine', 'Decision support ranked 6 responses; 1 blocked for lack of units', { source: 'osint', verification: 'NEWS-REPORTED' }),
		],
		[`vehicle:${ids.vehicle}`]: [
			feed('v-1', 40 * 60, 'enforcement', [`vehicle:${ids.vehicle}`], 'traffic-oracle', 'machine', `Stolen vehicle ${RAW} sighted at EM-BR-SETU-E — e-challan withheld`, { source: 'emulated' }),
			feed('v-2', 14 * 60, 'enforcement', [`vehicle:${ids.vehicle}`], 'traffic-oracle', 'machine', `Stolen vehicle ${RAW} sighted at EM-CAM-03 — awaiting a duty officer`, { source: 'emulated' }),
		],
		[`event:${ids.movementEvent}`]: [feed('e-1', 9 * 60, 'event', [`event:${ids.movementEvent}`], 'R. Mehta', 'human', 'Activated the Class Z movement')],
	};

	const RELATION = (from, to) => {
		const fk = from.split(':')[0];
		const tk = to.split(':')[0];
		if (tk === 'segment') return fk === 'event' || fk === 'convoy' ? 'route_segment' : 'on_road';
		if (fk === 'place' && tk === 'osint_event') return 'reports_here';
		if (fk === 'osint_event' && tk === 'place') return 'reported_at';
		if (tk === 'camera') return 'seen_by_camera';
		return tk;
	};
	/** The sighting whose dossier answers 404 (no lawful basis): the oldest read. */
	const withheldSighting = snap.entities.filter((e) => e.kind === 'sighting').sort((a, b) => Date.parse(a.t) - Date.parse(b.t))[0].urn;

	function dossierOf(urn) {
		if (urn === withheldSighting) return null;
		const ent = byUrn(urn) ?? (urn.startsWith('segment:') ? segEntity(Number(urn.slice(8))) : null);
		if (!ent) return null;
		const related = [];
		for (const l of ent.links ?? []) {
			const other = byUrn(l) ?? (l.startsWith('segment:') ? segEntity(Number(l.slice(8))) : null);
			if (other) related.push({ relation: RELATION(urn, l), entity: other });
		}
		return { entity: ent, related, audit: AUDIT[urn] ?? [], audit_sources: [] };
	}

	function answer(url) {
		let p = String(url);
		try {
			const u = new URL(p, 'http://deck.local');
			p = u.pathname + u.search;
		} catch {
			/* a bare path */
		}
		const m = /^\/api\/v1\/city\/entity\/([a-z_]+)\/([^?]+)/.exec(p);
		if (m) {
			const d = dossierOf(`${m[1]}:${decodeURIComponent(m[2])}`);
			return d ? { status: 200, body: d } : null;
		}
		return fx.answer(url);
	}

	const urnOf = (kind, pick = () => true) => snap.entities.find((e) => e.kind === kind && pick(e))?.urn;
	return {
		answer,
		expect: {
			...E,
			withheldSighting,
			urns: {
				osint_event: accident.urn,
				official: weather.urn,
				robbery: robbery.urn,
				event: `event:${ids.workZoneEvent}`,
				planning: `event:${E.ids.movementEvent.replace(/1$/, '4')}`,
				vehicle: `vehicle:${ids.vehicle}`,
				place: PLACE.urn,
				convoy: urnOf('convoy'),
				junction: 'junction:2',
				camera: 'camera:EM-CAM-03',
				dispatch: `dispatch:${ids.dispatch108}`,
				recommendation: urnOf('recommendation'),
				sighting: snap.entities.filter((e) => e.kind === 'sighting').sort((a, b) => Date.parse(b.t) - Date.parse(a.t))[0].urn,
			},
		},
	};
}

// ─── the smoke ───────────────────────────────────────────────────────────────

const isMain = process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url;
if (isMain) await smoke();

async function smoke() {
	const HERE = path.dirname(fileURLToPath(import.meta.url));
	const DECK = path.resolve(HERE, '..');
	const base = (process.argv[2] ?? 'http://127.0.0.1:5471').replace(/\/$/, '');
	const origin = new URL(base).origin;
	if (/:(5273|8090|8091|8092)$/.test(origin)) {
		console.error('refusing a live port');
		process.exit(2);
	}
	let puppeteer = null;
	for (const from of [process.env['PUPPETEER_FROM'], path.resolve(DECK, '../../frontend/package.json')].filter(Boolean)) {
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

	const fx = objectFixtures(Date.now());
	const E = fx.expect;
	const U = E.urns;
	const writes = [];
	const errors = [];
	const offsite = [];
	const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--window-size=1920,1080'] });
	const page = await browser.newPage();
	await page.setViewport({ width: 1920, height: 1080 });
	page.on('pageerror', (e) => errors.push(e.message.slice(0, 240)));
	await page.setRequestInterception(true);
	page.on('request', (req) => {
		const u = new URL(req.url());
		if (u.origin === origin && (u.pathname.startsWith('/api/') || u.pathname.startsWith('/gods-eye/'))) {
			if (req.method() !== 'GET' && req.method() !== 'HEAD') {
				writes.push(`${req.method()} ${u.pathname}`);
				// a chat turn is held 1.5 s before it is refused, so "a second press while it streams" is real
				if (/\/chat\/stream$/.test(u.pathname)) return void setTimeout(() => req.abort().catch(() => {}), 1500);
				return req.abort();
			}
			const a = fx.answer(u.pathname + u.search);
			return req.respond(a ? { status: a.status, contentType: 'application/json', body: JSON.stringify(a.body) } : { status: 404, contentType: 'application/json', body: '{"detail":"Not Found"}' });
		}
		if (u.origin !== origin) {
			offsite.push(u.host);
			return req.abort(); // hermetic: no tile server, no third party
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
	await page.setCookie({ name: 'sajag_lang', value: 'en', url: origin });

	const href = (urn) => `${base}/o/${urn.slice(0, urn.indexOf(':'))}:${encodeURIComponent(urn.slice(urn.indexOf(':') + 1))}`;
	async function openPage(urn, ready = true) {
		await page.goto(href(urn), { waitUntil: 'networkidle2', timeout: 120_000 });
		if (ready) await page.waitForFunction(() => ['ok', 'withheld', 'not-found'].includes(window.__V3_OBJECT__?.state ?? '') && !!document.querySelector('[data-testid="obj-title"], [data-testid="obj-withheld"], [data-testid="obj-missing"]'), { timeout: 30_000 }).catch(() => {});
		await new Promise((r) => setTimeout(r, 700));
	}
	const snapshot = () =>
		page.evaluate(() => {
			const q = (s) => [...document.querySelectorAll(s)];
			return {
				hook: window.__V3_OBJECT__,
				title: document.querySelector('[data-testid="obj-title"]')?.textContent?.trim() ?? '',
				prov: q('[data-testid="obj-provenance"]').map((e) => ({ v: e.getAttribute('data-provenance'), text: e.textContent?.trim() })),
				tabs: q('[role="tab"]').map((tb) => ({ id: tb.getAttribute('data-tab'), selected: tb.getAttribute('aria-selected'), controls: tb.getAttribute('aria-controls'), tabindex: tb.getAttribute('tabindex') })),
				text: document.body.innerText,
				links: q('a[href]').map((a) => ({ href: a.getAttribute('href'), abs: a.href, rel: a.getAttribute('rel') ?? '', testid: a.getAttribute('data-testid') })),
				imgsNoAlt: q('img').filter((i) => !i.hasAttribute('alt')).length,
				heroImg: q('[data-testid="obj-hero"] [role="img"]').map((m) => m.getAttribute('aria-label') ?? ''),
				masked: q('[data-v3="plate"][data-masked="true"]').length,
				redactions: q('[data-v3="redaction"]').map((r) => r.textContent?.trim()),
			};
		});
	const RAW_RE = /(?:WB ?06|MH ?47) ?EM ?9001/i;

	try {
		// ── 1. every kind renders ───────────────────────────────────────────
		const KINDS = [
			['osint_event', U.osint_event, 'NEWS-REPORTED'],
			['event', U.event, null],
			['vehicle', U.vehicle, 'EMULATED'],
			['place', U.place, null],
			['convoy', U.convoy, 'EMULATED'],
			['junction', U.junction, null],
			['camera', U.camera, 'EMULATED'],
			['dispatch', U.dispatch, null],
			['recommendation', U.recommendation, 'EMULATED'],
			['sighting', U.sighting, 'EMULATED'],
		];
		for (const [kind, urn, provExpect] of KINDS) {
			const w0 = writes.length;
			await openPage(urn);
			const s = await snapshot();
			ok(`${kind}: the page renders its record (title, tabs, kind)`, s.hook?.kind === kind && s.title.length > 1 && s.tabs.length >= 4, `${urn} · "${s.title.slice(0, 50)}" · tabs ${s.tabs.map((t) => t.id).join(',')}`);
			ok(`${kind}: one honest provenance tag (${provExpect ?? 'none for a live record'})`, provExpect ? s.prov.length === 1 && s.prov[0].v === provExpect : s.prov.length === 0, JSON.stringify(s.prov));
			ok(`${kind}: the hero map is role="img" with a label; every <img> has alt`, s.heroImg.length === 1 && s.heroImg[0].length > 5 && s.imgsNoAlt === 0, `${s.heroImg[0] ?? 'none'} · ${s.imgsNoAlt} img without alt`);
			ok(`${kind}: tabs carry aria-controls and ONE tab stop`, s.tabs.every((t) => t.controls === `obj-panel-${t.id}`) && s.tabs.filter((t) => t.tabindex === '0').length === 1);
			if (['vehicle', 'sighting', 'recommendation', 'event'].includes(kind)) ok(`${kind}: no raw registration mark in innerText without an officer`, !RAW_RE.test(s.text), RAW_RE.test(s.text) ? 'RAW MARK SHOWN' : `clean · ${s.masked} masked chip(s)`);
			// Record holds every property row of the adapter's view
			await page.click('[role="tab"][data-tab="record"]');
			await new Promise((r) => setTimeout(r, 400));
			const rec = await page.evaluate(() => ({ rows: document.querySelectorAll('[data-testid="obj-props"] tr th.k').length, hook: window.__V3_OBJECT__?.record ?? -1 }));
			ok(`${kind}: Record shows every property row of the inspector view (${rec.hook})`, rec.hook > 0 && rec.rows === rec.hook, `${rec.rows}/${rec.hook}`);
			ok(`${kind}: loading the page wrote nothing`, writes.length === w0, writes.slice(w0).join(' | '));
		}

		// ── 2. the withheld sighting ─────────────────────────────────────────
		await openPage(E.withheldSighting);
		const wh = await snapshot();
		ok('a sighting the oracle may not show reads "Withheld: no lawful basis"', wh.hook?.state === 'withheld' && /Withheld: no lawful basis/.test(wh.text) && !RAW_RE.test(wh.text), wh.hook?.state);

		// ── 3. OSINT rules on the report pages ───────────────────────────────
		const offsiteLinks = (s) => s.links.filter((l) => /^https?:/i.test(l.href ?? '') && !l.abs.startsWith(origin));
		await openPage(U.osint_event);
		let s = await snapshot();
		ok('report: [AGE] reads as an "age withheld" chip, never the code', s.redactions.includes('age withheld') && !/\[AGE\]/.test(s.text), JSON.stringify(s.redactions));
		ok('report: the verification ladder lights News-reported', (await page.$eval('[data-testid="obj-ladder"]', (e) => e.getAttribute('data-step'))) === '1');
		const checks = await page.$$eval('[data-testid="obj-credibility"] [data-check]', (els) => Object.fromEntries(els.map((e) => [e.getAttribute('data-check'), e.getAttribute('data-ok')])));
		ok('report: an official-tier CONTEXT member does not make "official" true', checks.official === 'false' && checks.publishers === 'true', JSON.stringify(checks));
		ok('report: the sources fact counts reporting publishers only (2 · 0 official)', /2 publishers · 0 official/.test(s.text), (s.text.match(/\d+ publishers? · \d+ official/) ?? ['none'])[0]);
		ok('report: the response waits → one white primary to its one home, a decision card with a timer', !!(await page.$('[data-testid="obj-primary"]')) && !!(await page.$('[data-testid="obj-decision"] [role="timer"]')));
		const dHref = await page.$eval('[data-testid="obj-decision-link"]', (a) => a.getAttribute('href'));
		// the unit's ONE home: the /ops Decisions column on this base, /decide/<unit> once V3-P2's Decide is on main
		const homes = [`/ops#unit=${encodeURIComponent(`dss:${E.ids.dss}`)}`, `/decide/${encodeURIComponent(`dss:${E.ids.dss}`)}`];
		ok('report: the decision link opens the unit\'s one home (Decide / Decisions) and carries no mark', homes.includes(dHref) && !RAW_RE.test(dHref), dHref);
		ok('report: no off-site link but the OSM credit', offsiteLinks(s).every((l) => /openstreetmap\.org\/copyright$/.test(l.abs)), offsiteLinks(s).map((l) => l.abs).join(' '));
		await page.click('[role="tab"][data-tab="sources"]');
		await new Promise((r) => setTimeout(r, 400));
		s = await snapshot();
		const srcRows = await page.$$eval('[data-testid="obj-source"]', (els) => els.map((e) => e.getAttribute('data-publisher')));
		ok('report Sources: the context member is NOT a source row; it is listed apart', srcRows.length === 2 && !srcRows.includes('sachet.ndma.gov.in') && !!(await page.$('[data-testid="obj-context"]')), srcRows.join(', '));
		ok('report Sources: no a[href] to a news / social source (a leaked https url stays unlinked)', !s.links.some((l) => /news-[abc]\.example/.test(l.abs)) && offsiteLinks(s).every((l) => /openstreetmap\.org\/copyright$/.test(l.abs)), offsiteLinks(s).map((l) => l.abs).join(' '));
		ok('report Sources: "Link not kept: it may name a person" on the news rows; "Official sources · none yet"', (s.text.match(/Link not kept: it may name a person/g) ?? []).length === 2 && /none yet/.test(s.text));
		ok('report Sources: the title\'s [AGE] is a chip', s.redactions.filter((r) => r === 'age withheld').length >= 1 && !/\[AGE\]/.test(s.text));
		await page.click('[role="tab"][data-tab="record"]');
		await new Promise((r) => setTimeout(r, 600));
		s = await snapshot();
		ok('report Record (v2 sections composed): still no news / social link', !s.links.some((l) => /news-[abc]\.example/.test(l.abs)) && !!(await page.$('[data-testid="osint-report"]')), offsiteLinks(s).map((l) => l.abs).join(' '));

		await openPage(U.official);
		await page.click('[role="tab"][data-tab="sources"]');
		await new Promise((r) => setTimeout(r, 400));
		s = await snapshot();
		const off = offsiteLinks(s).filter((l) => !/openstreetmap\.org/.test(l.abs));
		ok('official report: exactly ONE off-site link — the official tier\'s https url, rel="noopener noreferrer"', off.length === 1 && off[0].abs === 'https://sachet.ndma.gov.in/cap/alert/1' && /noopener/.test(off[0].rel) && /noreferrer/.test(off[0].rel), JSON.stringify(off));
		ok('official report: an official http url and an aggregator on a .gov.in address are NOT links', !s.links.some((l) => /mausam\.imd|wb\.gov\.in/.test(l.abs)));
		ok('official report: provenance OFFICIAL-VERIFIED, the ladder at Official', (await page.evaluate(() => window.__V3_OBJECT__?.provenance)) === 'OFFICIAL-VERIFIED');

		await openPage(U.robbery);
		s = await snapshot();
		ok('report: [PERSON] reads as a "name withheld" chip, never the code', s.redactions.includes('name withheld') && !/\[PERSON\]/.test(s.text), JSON.stringify(s.redactions));

		// ── 4. keyboard ──────────────────────────────────────────────────────
		await openPage(U.osint_event);
		await page.focus('[role="tab"][aria-selected="true"]');
		await page.keyboard.press('ArrowRight');
		await new Promise((r) => setTimeout(r, 200));
		let k = await page.evaluate(() => ({ focus: document.activeElement?.getAttribute('data-tab'), selected: document.querySelector('[role="tab"][aria-selected="true"]')?.getAttribute('data-tab'), panel: document.querySelector('[role="tabpanel"]')?.id }));
		ok('keyboard: → moves focus and selection to the next tab; the panel follows', k.focus === 'sources' && k.selected === 'sources' && k.panel === 'obj-panel-sources', JSON.stringify(k));
		await page.keyboard.press('End');
		await new Promise((r) => setTimeout(r, 200));
		k = await page.evaluate(() => document.activeElement?.getAttribute('data-tab'));
		ok('keyboard: End jumps to the last tab (Record)', k === 'record', k);
		await page.keyboard.press('ArrowRight');
		k = await page.evaluate(() => document.activeElement?.getAttribute('data-tab'));
		ok('keyboard: → wraps to Overview', k === 'overview', k);
		const named = await page.evaluate(() => ({ ask: document.querySelector('[data-testid="obj-ask-btn"]')?.getAttribute('aria-label'), more: document.querySelector('[data-testid="obj-more"]')?.getAttribute('aria-label') }));
		ok('a11y: Ask and More are named buttons', !!named.ask && !!named.more, JSON.stringify(named));

		// ── 5. one-POST rules ────────────────────────────────────────────────
		let w0 = writes.length;
		await page.evaluate(() => {
			const b = document.querySelector('[data-testid="obj-ask-btn"]');
			b?.click();
			b?.click();
		});
		await new Promise((r) => setTimeout(r, 400));
		await page.click('[data-testid="obj-ask-btn"]'); // a third press, while the first turn still streams
		await new Promise((r) => setTimeout(r, 2200));
		const askPosts = writes.slice(w0).filter((w) => /chat\/stream/.test(w));
		ok('Ask about it: presses while a turn streams send exactly ONE chat POST (read-only turn)', askPosts.length === 1 && writes.length - w0 === 1, writes.slice(w0).join(' | '));
		const askState = await page.$eval('[data-testid="obj-ask-answer"]', (e) => e.getAttribute('data-status'));
		ok('Ask about it: a refused turn says so honestly (nothing changed)', askState === 'error', askState);

		const planning = `event:${E.ids.movementEvent.slice(0, -1)}4`;
		await openPage(planning);
		w0 = writes.length;
		const verb = await page.$('[data-testid="event-verbs"] [data-verb="approved"] button');
		ok('event (planning): the lifecycle verbs are composed (v2 LifecycleVerbs)', !!verb);
		if (verb) await verb.click().catch(() => {});
		await new Promise((r) => setTimeout(r, 600));
		ok('event: without a named officer a verb sends NO request', writes.length === w0, writes.slice(w0).join(' | '));
		await page.click('[data-testid="v3-officer"]');
		await page.waitForSelector('[data-testid="duty-officer"]', { timeout: 5000 });
		await page.type('[data-testid="duty-officer"]', 'Sandbox Officer');
		await page.keyboard.press('Escape');
		await new Promise((r) => setTimeout(r, 500));
		w0 = writes.length;
		await page.evaluate(() => {
			const b = document.querySelector('[data-testid="event-verbs"] [data-verb="approved"] button');
			b?.click();
			b?.click();
		});
		await new Promise((r) => setTimeout(r, 1200));
		const lifePosts = writes.slice(w0);
		ok('event: with an officer, a double press sends exactly ONE status POST', lifePosts.length === 1 && /\/events\/[^/]+\/status$/.test(lifePosts[0]), lifePosts.join(' | '));

		// ── 6. the officer unmasks; clearing masks again (vehicle) ──────────
		await openPage(U.vehicle);
		if (!(await page.evaluate((raw) => document.body.innerText.includes(raw), E.rawPlate))) {
			await page.click('[data-testid="v3-officer"]');
			await page.waitForSelector('[data-testid="duty-officer"]', { timeout: 5000 });
			await page.type('[data-testid="duty-officer"]', 'Sandbox Officer');
			await page.keyboard.press('Escape');
		}
		await page.waitForFunction((raw) => document.body.innerText.includes(raw), { timeout: 8000 }, E.rawPlate).catch(() => {});
		s = await snapshot();
		ok('vehicle: a named officer sees the full mark (chip unmasked)', s.text.includes(E.rawPlate) && (await page.$$('[data-v3="plate"][data-masked="false"]')).length > 0);
		await page.click('[data-testid="v3-officer"]');
		await page.waitForSelector('[data-testid="duty-officer"]', { timeout: 5000 });
		await page.click('[data-testid="duty-officer"]', { clickCount: 3 });
		await page.keyboard.press('Backspace');
		await page.keyboard.press('Escape');
		await page.waitForFunction((raw) => !document.body.innerText.includes(raw), { timeout: 8000 }, E.rawPlate).catch(() => {});
		s = await snapshot();
		ok('vehicle: clearing the officer masks every mark again (title, timeline, facts)', !RAW_RE.test(s.text) && s.masked > 0, `${s.masked} masked`);
		ok('vehicle: the lawful-reads tab lists the reads', (await page.$$eval('[role="tab"][data-tab="reads"] .n', (e) => Number(e[0]?.textContent ?? 0))) >= 1);
		ok('vehicle: the stolen rule is said (evidence only, no e-challan)', /Evidence only/.test(s.text) && /No e-challan/.test(s.text));

		// ── 7. language ──────────────────────────────────────────────────────
		/** The language switch lives in the top bar's one compact menu (V3-P4B): open it when the choice is not showing. */
		const pickLang = async (code) => {
			if (!(await page.$(`[data-v3="header-menu"] [data-lang-code="${code}"]`))) {
				await page.click('[data-testid="v3-header-menu"]');
				await page.waitForSelector(`[data-v3="header-menu"] [data-lang-code="${code}"]`, { timeout: 5000 });
			}
			await page.click(`[data-v3="header-menu"] [data-lang-code="${code}"]`);
		};
		await pickLang('hi');
		await page.waitForFunction(() => document.documentElement.lang === 'hi', { timeout: 10_000 }).catch(() => {});
		await new Promise((r) => setTimeout(r, 600));
		const hiTab = await page.$eval('[role="tab"][data-tab="overview"]', (e) => e.textContent?.trim());
		ok('हि switches the page: the Overview tab reads सारांश', /सारांश/.test(hiTab ?? ''), hiTab);
		await pickLang('en');

		// ── 8. a link that names nothing ─────────────────────────────────────
		await page.goto(`${base}/o/not-a-urn`, { waitUntil: 'networkidle2', timeout: 60_000 });
		ok('a link that names no record says so (no fetch of it)', !!(await page.$('[data-testid="obj-bad"]')));

		ok('zero page errors', errors.length === 0, errors.slice(0, 3).join(' | '));
		const unexpected = writes.filter((w) => !/chat\/stream|\/events\/[^/]+\/status$/.test(w));
		ok('no non-GET beyond the two pressed on purpose (all refused)', unexpected.length === 0, unexpected.join(' | '));
		ok('no third-party request other than map tiles', offsite.every((h) => /tile\.openstreetmap\.org|tile\.osm\.org|openstreetmap/.test(h)), [...new Set(offsite)].join(', '));
	} finally {
		await browser.close();
	}
	console.log(failures ? `\n${failures} FAILED` : '\nobject-page-smoke: ALL OK');
	process.exit(failures ? 1 : 0);
}
