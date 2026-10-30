/**
 * V3 Plan unit test (V3-P4B; V3-SPEC §6.6, §9.1) — zero browser.
 *
 *   node tests/v3-plan.unit.mjs
 *
 * esbuild bundles the REAL modules — src/lib/v3/plan/{model, packs.plan*}, the corridor's plan state machine
 * (corridor/plan.ts) and its ONE escort lifecycle (corridor/escort-state.svelte.ts), the ops store and the API
 * client — with `$lib` aliased, rune identity stubs and every `.svelte` component stubbed (the decide.unit.mjs
 * harness). A fetch stub answers every GET from the hermetic fixture world (tests/v3-plan-smoke.mjs planFixtures)
 * and RECORDS every non-GET, answering it with a canned reply where a check needs the server's words (nothing
 * leaves the process), so "one POST" is counted, not assumed.
 *
 * Asserts:
 *   - the pack: EN / HI / MR carry the same keys, every key starts with v3p_, EN copy rules (≤ one " · ", headings
 *     ≤ 32, no ALL-CAPS word outside the acronyms), HI / MR translated and in their own script; the officer helper
 *     is §9.1's sentence word for word (the same words as Decide's, in all three languages);
 *   - the class table IS the planner's protocol table (shared/schemas/protocol_params.json: lane floor and
 *     advance-closure floor for Z+, Z, Y, X);
 *   - stepOf (where → routes → launch → live, editing and a launch in flight), matchPlaces, departureMs and the
 *     "tomorrow" rule, routeFigures (never an invented figure), previewRouteId, routeLine / planOverlay (the
 *     previewed route lit, the rest dashed), waiverLines (each violation once), stateKey / stateTone,
 *     trafficTagKey (simulated says so; unknown is not called live), failKind / failLeadKey (no answer is never
 *     "refused"), proposalHref / eventHref (never a mark), planEventId;
 *   - the REAL lifecycle through the stub: Find routes ×2 at once → ONE create + ONE plan; launch without an
 *     officer → NOTHING sent; launch ×2 at once with an officer → ONE POST; a 409's words kept VERBATIM (and
 *     masked by ops.text once the officer is cleared); a 503 is an "error", a dropped request "no answer";
 *     the launch gate's reasons in the page's words (waiver first, then the officer, a hold locks); the exact
 *     list of writes the test caused.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { planFixtures, planDoc, PLAN_MOVEMENT, PLAN_RAW_PLATE } from './v3-plan-smoke.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const OUT = path.join(HERE, 'artifacts', 'v3-plan-bundle.mjs');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

// ─── bundle the real modules ────────────────────────────────────────────────

mkdirSync(path.dirname(OUT), { recursive: true });
const esbuild = createRequire(path.join(DECK, 'package.json'))('esbuild');
const ENTRY = `
export * as model from './src/lib/v3/plan/model';
export * as pack from './src/lib/v3/plan/packs.plan';
export { hi } from './src/lib/v3/plan/packs.plan.hi';
export { mr } from './src/lib/v3/plan/packs.plan.mr';
export * as decidePack from './src/lib/v3/decide/packs.decide';
export { hi as decideHi } from './src/lib/v3/decide/packs.decide.hi';
export { mr as decideMr } from './src/lib/v3/decide/packs.decide.mr';
export * as corridor from './src/lib/corridor/plan';
export * as escort from './src/lib/corridor/escort-state.svelte';
export * as opsStore from './src/lib/ops/store.svelte';
export { t } from './src/lib/i18n/strings';
`;
const svelteStub = {
	name: 'svelte-component-stub',
	setup(build) {
		build.onResolve({ filter: /\.svelte$/ }, (args) => {
			const file = args.path.startsWith('$lib/') ? path.join(DECK, 'src/lib', args.path.slice(5)) : path.resolve(args.resolveDir, args.path);
			if (existsSync(`${file}.ts`) || existsSync(`${file}.js`)) return undefined;
			return { path: file, namespace: 'svelte-stub' };
		});
		build.onLoad({ filter: /.*/, namespace: 'svelte-stub' }, (args) => ({
			contents: `export default function ${path.basename(args.path, '.svelte').replace(/[^A-Za-z0-9_]/g, '_')}() {}`,
			loader: 'js',
		}));
	},
};
const built = await esbuild.build({
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'v3-plan-entry.ts' },
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	outfile: OUT,
	logLevel: 'silent',
	plugins: [svelteStub],
});
ok('bundle builds (esbuild, $lib aliased, .svelte stubbed)', built.errors.length === 0, `${built.errors.length} errors`);

globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });

// ─── the fixture world; every write recorded ───────────────────────────────

const fx = planFixtures(Date.now(), { escort: 'none' });
const writes = [];
/** (method, path, body) → {status, body} | 'drop' (the request never answers: a network error) | null (503). */
let reply = () => null;
globalThis.fetch = async (url, init = {}) => {
	const method = (init.method ?? 'GET').toUpperCase();
	const u = new URL(String(url), 'http://deck.local');
	if (method !== 'GET') {
		writes.push(`${method} ${u.pathname}`);
		await new Promise((r) => setTimeout(r, 5));
		const r = reply(method, u.pathname, init.body);
		if (r === 'drop') throw new TypeError('Failed to fetch');
		return r ? new Response(JSON.stringify(r.body ?? {}), { status: r.status, headers: { 'content-type': 'application/json' } }) : new Response('{"detail":"unavailable"}', { status: 503, statusText: 'Service Unavailable', headers: { 'content-type': 'application/json' } });
	}
	const a = fx.answer(u.pathname + u.search);
	return a
		? new Response(JSON.stringify(a.body), { status: a.status, headers: { 'content-type': 'application/json' } })
		: new Response('{"detail":"Not Found"}', { status: 404, headers: { 'content-type': 'application/json' } });
};

const M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
const { model } = M;
const { ops } = M.opsStore;
const lc = M.escort.escortLifecycle;
const L = (k, ...a) => M.t('en', k, ...a);

// ─── 1. the pack ─────────────────────────────────────────────────────────────

{
	const en = M.pack.PLAN_PACKS.en;
	const keys = Object.keys(en);
	const same = (a, b) => a.length === b.length && a.every((k) => b.includes(k));
	ok('pack: EN / HI / MR carry the same keys', same(keys, Object.keys(M.hi)) && same(keys, Object.keys(M.mr)), `${keys.length} keys`);
	ok('pack: every key starts with v3p_', keys.every((k) => k.startsWith('v3p_')));
	const text = (v) => String(typeof v === 'function' ? v('‹x›', '‹y›', '‹z›') : v);
	const ACR = new Set('FIR ANPR IST VVIP AI ID OSM ETA OSINT ICCC IMD DSS SMS GPS API PIN CCTV SG CG SP'.split(' '));
	const bad = [];
	for (const [k, v] of Object.entries(en)) {
		const s = text(v);
		if ((s.match(/ · /g) ?? []).length > 1) bad.push(`${k}: separator`);
		if (/heading$/.test(k) && s.length > 32) bad.push(`${k}: heading > 32`);
		for (const w of s.split(/[^A-Za-z0-9•]+/)) if (w.length > 1 && /^[A-Z]+$/.test(w) && !ACR.has(w)) bad.push(`${k}: ALL-CAPS ${w}`);
	}
	ok('EN copy rules: ≤ one " · ", headings ≤ 32, no ALL-CAPS word outside the acronyms', bad.length === 0, bad.slice(0, 6).join(' | '));
	const untranslated = (p) => keys.filter((k) => text(en[k]) === text(p[k]) && /[a-z]{4}/.test(text(en[k])));
	ok('HI and MR are translated (no EN sentence left in place)', untranslated(M.hi).length === 0 && untranslated(M.mr).length === 0, [...untranslated(M.hi), ...untranslated(M.mr)].join(', '));
	const leakHi = Object.values(M.hi).map(text).filter((s) => /[ঀ-৿]/.test(s));
	const leakMr = Object.values(M.mr).map(text).filter((s) => /[ঀ-৿०-९]/.test(s));
	ok('no Bengali script left in the HI or MR pack, and MR keeps Latin digits (Marathi is Devanagari)', leakHi.length === 0 && leakMr.length === 0);
	ok(
		'the officer helper is §9.1\'s sentence word for word (and Decide\'s words in HI / MR)',
		en.v3p_who_help === 'Naming yourself shows full registration marks on this console and records your name with the decision. Attribution, not sign-in.' &&
			M.hi.v3p_who_help === M.decideHi.v3d_officer_helper &&
			M.mr.v3p_who_help === M.decideMr.v3d_officer_helper,
	);
	ok('the pack is registered: t() resolves EN / HI / MR', M.t('en', 'v3p_title') === 'Plan a movement' && M.t('hi', 'v3p_title') === M.hi.v3p_title && M.t('mr', 'v3p_title') === M.mr.v3p_title);
}

// ─── 2. the class table = the planner's protocol table ─────────────────────

{
	const table = JSON.parse(readFileSync(path.resolve(DECK, '../../shared/schemas/protocol_params.json'), 'utf8')).protection_classes;
	const drift = model.PROTECTION_CLASSES.filter((c) => table[c.id]?.min_lanes !== c.minLanes || (table[c.id]?.advance_closure_floor_sec ?? null) !== c.advanceClosureSec);
	ok('the class cards = shared/schemas/protocol_params.json (lane floor, advance-closure floor)', drift.length === 0 && model.PROTECTION_CLASSES.map((c) => c.id).join() === 'Z+,Z,Y,X', drift.map((c) => c.id).join(', ') || 'Z+ 6/180 · Z 4/120 · Y 2/60 · X 1/none');
}

// ─── 3. the pure rules ───────────────────────────────────────────────────────

{
	const s = (o) => model.stepOf({ phase: 'idle', hasDoc: false, offered: false, confirming: false, editing: false, ...o });
	ok(
		'stepOf: where → routes → launch → live; editing goes back; a launch in flight stays on Launch; a plan that cannot depart never reaches Launch',
		s({}) === 'where' &&
			s({ phase: 'planning' }) === 'where' &&
			s({ phase: 'planned', hasDoc: true }) === 'routes' &&
			s({ phase: 'idle', hasDoc: true }) === 'routes' &&
			s({ phase: 'planned', hasDoc: true, offered: true, confirming: true }) === 'launch' &&
			s({ phase: 'planned', hasDoc: true, offered: false, confirming: true }) === 'routes' &&
			s({ phase: 'planned', hasDoc: true, editing: true }) === 'where' &&
			s({ phase: 'starting', hasDoc: true }) === 'launch' &&
			s({ phase: 'escorting' }) === 'live' &&
			s({ phase: 'stopping', hasDoc: true }) === 'live' &&
			s({ phase: 'ended' }) === 'live',
	);
	const POIS = M.escort.PLAN_POIS;
	const names = (q) => model.matchPlaces(q, POIS).map((i) => POIS[i].name);
	ok('matchPlaces: name start first, then a word start, then contains; empty lists all; no match is empty', names('mant')[0] === 'Mantralaya' && names('')?.length === POIS.length && names('zzz').length === 0 && names('bandra').slice(0, 2).sort().join() === 'Bandra Kurla Complex (BKC),Kalanagar (Bandra East)' && names('wank')[0] === 'Wankhede Stadium' && names('port').join() === 'Mumbai Airport T2' && names('hospital').join() === 'KEM Hospital,Sion Hospital (LTMGH)' && names('MUMBAI')[0] === 'Mumbai Airport T2', names('bandra').join(', '));
	const now = Date.parse('2026-10-26T14:00:00Z'); // 19:30 IST
	const ist = (hhmm, anchor) => Date.parse(`${new Date(anchor + 5.5 * 3600_000).toISOString().slice(0, 10)}T${hhmm}:00+05:30`);
	const at = model.departureMs('at', '21:15', now, ist);
	const past = model.departureMs('at', '08:00', now, ist);
	ok(
		'departureMs: +30 min (the planner\'s default), +1 h, an IST time today; a time already past is tomorrow (and says so); no time is NaN',
		model.departureMs('in30', null, now, ist) === now + 1800_000 &&
			model.departureMs('in60', null, now, ist) === now + 3600_000 &&
			at === Date.parse('2026-10-26T21:15:00+05:30') &&
			!model.isLaterIstDay(at, now) &&
			past === Date.parse('2026-10-27T08:00:00+05:30') &&
			model.isLaterIstDay(past, now) &&
			Number.isNaN(model.departureMs('at', null, now, ist)),
	);
	const doc = planDoc();
	const [r1, r2, r3] = [doc.primary_route, ...doc.alternate_routes];
	const f3 = model.routeFigures(r3);
	ok('routeFigures: only what the plan reports — no time on the third candidate, never 0 or NaN', JSON.stringify(model.routeFigures(r1)) === JSON.stringify({ minutes: 19, km: '7.4', roads: 3 }) && f3.minutes === null && f3.km === '14.8' && JSON.stringify(model.routeFigures({ route_id: 'x', segment_ids: [], distance_m: 0, estimated_time_sec: NaN })) === JSON.stringify({ minutes: null, km: null, roads: null }));
	const cands = [r1, r2, r3];
	ok('previewRouteId: the officer\'s pick while it is a candidate, else the recommended one', model.previewRouteId(cands, 'r-2', 'r-1') === 'r-2' && model.previewRouteId(cands, 'gone', 'r-1') === 'r-1' && model.previewRouteId(cands, null, null) === 'r-1' && model.previewRouteId([], null, null) === null);
	const segs = [
		{ segmentId: 1043, coordinates: [[88.3499, 22.5582], [88.3599, 22.5982]] },
		{ segmentId: 1027, coordinates: [[88.3599, 22.5982], [88.3799, 22.6182]] },
		{ segmentId: 1007, coordinates: [[88.3499, 22.5582], [88.3599, 22.5982]] },
	];
	const ov = model.planOverlay({ from: { name: 'A', coord: [88.3499, 22.5582] }, to: { name: 'B', coord: [88.3899, 22.6082] }, candidates: cands, previewId: 'r-1', segments: segs });
	ok(
		'routeLine / planOverlay: segments it does not know are skipped; the previewed route is lit (teal), the others dashed, drawn under it; start and destination pinned',
		model.routeLine(r1, segs).length === 2 &&
			ov.lines.filter((l) => l.style === 'route').length === 2 &&
			ov.lines.filter((l) => l.style === 'dashed').length === 2 &&
			ov.lines[ov.lines.length - 1].style === 'route' &&
			ov.points.length === 2 &&
			model.planOverlay({ from: { name: 'A', coord: [1, 2] }, to: { name: 'A', coord: [1, 2] }, candidates: [], previewId: null, segments: [] }).points.length === 1,
	);
	const lines = model.waiverLines(M.corridor.planViolations(doc), (id) => (id === 1029 ? 'Maa Flyover' : null), (id) => `Segment ${id}`);
	ok('waiverLines: each violation once (three candidates share it), no repeated road name', lines.length === 1 && lines[0] === 'Maa Flyover has 4 lanes; 6 required for Z+' && model.waiverLines([{ segmentId: 7, detail: 'too narrow' }], () => null, (id) => `Segment ${id}`)[0] === 'Segment 7: too narrow', lines.join(' | '));
	ok('stateKey / stateTone: ready is green, a waiver or a hold is orange, no route is ink (never red)', model.stateKey('approved') === 'v3p_state_approved' && model.stateTone('approved') === 'ok' && model.stateTone('conditional') === 'decide' && model.stateTone('hold') === 'decide' && model.stateTone('no_route') === 'neutral' && model.stateKey('weird') === 'v3p_state_planned');
	ok('trafficTagKey: simulated and mixed say so; live has no tag; an unknown feed is never called live', model.trafficTagKey('simulated') === 'v3p_sim' && model.trafficTagKey('mixed') === 'v3p_sim_mixed' && model.trafficTagKey('live') === null && model.trafficTagKey(null) === 'v3p_sim_unknown');
	ok(
		'failKind: no answer is never "refused"; an HTTP error is an error; words are a refusal',
		model.failKind('Failed to fetch') === 'no-answer' &&
			model.failKind('TypeError: NetworkError when attempting to fetch resource.') === 'no-answer' &&
			model.failKind('503 Service Unavailable: {"detail":"x"}') === 'error' &&
			model.failKind('An escort is already running for this corridor.') === 'refused' &&
			model.failKind('') === null &&
			model.failLeadKey('no-answer', 'launch') === 'v3p_fail_launch_none' &&
			model.failLeadKey('refused', 'launch') === 'v3p_fail_launch_refused' &&
			model.failLeadKey('error', 'plan') === 'v3p_fail_error',
	);
	ok('links: the proposal opens its Decide home, the operation its object page; neither carries a mark', model.proposalHref('esc-1') === '/decide/escort-proposal%3Aesc-1' && model.eventHref('7e3a/1') === '/o/event:7e3a%2F1');
	ok('planEventId: the plan\'s own event, else the board\'s event for the movement', model.planEventId(doc, [], null) === doc.event_id && model.planEventId(null, [{ eventId: 'e1', movementId: 'm1' }], 'm1') === 'e1' && model.planEventId(null, [], 'm1') === null);
}

// ─── 4. the real lifecycle, through the stub ──────────────────────────────────

{
	const copy = { waiverNeeded: L('v3p_lock_waiver'), holdLocked: L('v3p_lock_hold'), officerNeeded: L('v3p_lock_officer'), noPlan: L('v3p_lock_none') };
	const doc = planDoc();
	const g0 = M.corridor.launchGate(doc, { waiverAccepted: false, officerNamed: false }, copy);
	const g1 = M.corridor.launchGate(doc, { waiverAccepted: true, officerNamed: false }, copy);
	const g2 = M.corridor.launchGate(doc, { waiverAccepted: true, officerNamed: true }, copy);
	const gh = M.corridor.launchGate({ ...doc, hold: true }, { waiverAccepted: true, officerNamed: true }, copy);
	ok('the launch gate, in the page\'s words: waiver first, then the officer; open with both; a hold locks', g0.launchLockReason === copy.waiverNeeded && g1.launchLockReason === copy.officerNeeded && !g2.launchLocked && gh.launchLocked && gh.launchLockReason === copy.holdLocked);

	// Find routes ×2 at once → one create + one plan
	reply = (m, p) => (p === '/api/convoy/movements' ? { status: 200, body: { movement_id: PLAN_MOVEMENT } } : p === `/api/convoy/movements/${PLAN_MOVEMENT}/plan` ? { status: 200, body: doc } : null);
	const req = { originIdx: 1, destIdx: 12, vvipClass: 'Z+', departureIso: new Date(Date.now() + 1800_000).toISOString(), label: '' };
	await Promise.all([lc.plan(req), lc.plan(req)]);
	ok('Find routes ×2 at once → ONE create + ONE plan; the plan document lands in the lifecycle', JSON.stringify(writes) === JSON.stringify(['POST /api/convoy/movements', `POST /api/convoy/movements/${PLAN_MOVEMENT}/plan`]) && lc.doc?.movement_id === PLAN_MOVEMENT && lc.phase === 'planned', writes.join(' | '));
	const n0 = writes.length;

	// launch without an officer: nothing sent
	ops.setDutyOfficer('');
	await lc.launch();
	ok('launch without a named officer → NOTHING sent', writes.length === n0 && lc.phase === 'planned', writes.slice(n0).join(' | '));

	// a 409 in words: verbatim; masked once the officer is cleared
	ops.setDutyOfficer('R. Mehta');
	const WORDS = `An escort is already running for this corridor; the lead vehicle ${PLAN_RAW_PLATE} is on AJC Bose Road Flyover.`;
	reply = (m, p) => (p.endsWith('/escort') ? { status: 409, body: { detail: WORDS } } : null);
	await Promise.all([lc.launch(), lc.launch()]);
	ok('launch ×2 at once with an officer → ONE POST /movements/<id>/escort', writes.slice(n0).join() === `POST /api/convoy/movements/${PLAN_MOVEMENT}/escort`, writes.slice(n0).join(' | '));
	ok('a 409\'s words are kept VERBATIM and read as a refusal; nothing is retried', lc.launchRefusal === WORDS && model.failKind(lc.launchRefusal) === 'refused' && lc.phase === 'planned' && writes.length === n0 + 1, lc.launchRefusal);
	ops.setDutyOfficer('');
	const masked = ops.text(lc.launchRefusal);
	ok('officer cleared → the page\'s ops.text masks the refusal\'s mark', !masked.includes(PLAN_RAW_PLATE) && /MH01AB•+4/.test(masked), masked);

	// a 503 and a dropped request
	ops.setDutyOfficer('R. Mehta');
	reply = () => null;
	await lc.launch();
	ok('a 503 is "the brain answered with an error" (its text verbatim)', model.failKind(lc.launchRefusal) === 'error' && /^503 /.test(lc.launchRefusal ?? ''), lc.launchRefusal);
	reply = () => 'drop';
	await lc.launch();
	ok('a dropped request is "no confirmation came back" — never "refused"', model.failKind(lc.launchRefusal) === 'no-answer', lc.launchRefusal);

	// a success: the escort runs; a third press is refused before the wire
	reply = (m, p) => (p.endsWith('/escort') ? { status: 202, body: { movement_id: PLAN_MOVEMENT, status: 'running', task_id: 't-1' } } : null);
	await lc.launch();
	const before = writes.length;
	await lc.launch();
	ok('a running escort: Live; another launch sends NOTHING', lc.phase === 'escorting' && writes.length === before, `${lc.phase} · ${writes.length - before}`);
	const want = [
		'POST /api/convoy/movements',
		`POST /api/convoy/movements/${PLAN_MOVEMENT}/plan`,
		`POST /api/convoy/movements/${PLAN_MOVEMENT}/escort`,
		`POST /api/convoy/movements/${PLAN_MOVEMENT}/escort`,
		`POST /api/convoy/movements/${PLAN_MOVEMENT}/escort`,
		`POST /api/convoy/movements/${PLAN_MOVEMENT}/escort`,
	];
	ok('the writes this test caused, exactly (create, plan, 409, 503, dropped, 202)', JSON.stringify(writes) === JSON.stringify(want), writes.join(' | '));
	M.escort.escortLifecycle.reset();
}

console.log(failures ? `\n${failures} FAILED` : '\nv3-plan.unit: ALL OK');
process.exit(failures ? 1 : 0);
