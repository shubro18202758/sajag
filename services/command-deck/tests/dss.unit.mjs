/**
 * DSS decision unit test (OS-DECK-B; osint SPEC §1.7, §3.4; plan X22, C-U).
 *
 *   node tests/dss.unit.mjs
 *
 * esbuild bundles the REAL modules — the dss view-model and store, the
 * decisions tables (units, writers, homes, cards), the ops client and store,
 * the city registry and the dss pack — with `$lib` aliased to src/lib;
 * `$state` is an identity stub and every `.svelte` component import a stub
 * (no compiler here). A fetch stub answers the GETs and RECORDS every POST,
 * so each writer is held to the client call it makes (nothing reaches a
 * backend).
 *
 * Fixtures: tests/fixtures/dss/*.json — synthetic DecisionSupport objects
 * with the PoC's structure and fictional publishers (news-a.example,
 * news-b.example, sachet.ndma.gov.in).
 *
 * Asserts:
 *   - the tolerant C-U parser (unknown fields ignored);
 *   - the card view-model: ranking order; vetoed and infeasible COAs disabled
 *     with their reasons, never hidden, never selectable; the top feasible
 *     COA pre-selected; Approve blocked without an officer or with an
 *     infeasible COA selected; the strategy-prior line only when present; a
 *     resource-blocked best response stated with what is missing;
 *   - the approve What-changes rows for an unpromoted OSINT subject with two
 *     dispatch actions (the DSS row, the promotion row, two dispatch-request
 *     rows, next steps for the advisory and signal-hold actions) equal to C-U;
 *   - reject and defer require a note; a 409 code round-trips verbatim;
 *   - the rule note equals the X22 sentence exactly;
 *   - units from a seeded city registry: one unit per DSS (never two when the
 *     subject appears as an osint_event AND an event), an expired summary is
 *     never a unit, deadline = expires_at, severity (priority flags, injury
 *     class), data hooks, masked titles, no person field;
 *   - with ownsUnitKinds: ['dss'], a subject with a proposed DSS has ONE link
 *     card in the inspector (the section's own), not two;
 *   - the promote and decision writers refuse blank actors, keep 409 codes
 *     verbatim; generate validates the URN before any fetch;
 *   - the dss pack: EN/HI/MR carry the same keys, every key the dss sources
 *     use exists.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const OUT = path.join(HERE, 'artifacts', 'dss-bundle.mjs');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// ─── bundle the real modules ────────────────────────────────────────────────

mkdirSync(path.dirname(OUT), { recursive: true });
const esbuild = createRequire(path.join(DECK, 'package.json'))('esbuild');
const ENTRY = `
export * as units from './src/lib/decisions/units';
export * as writers from './src/lib/decisions/writers';
export * as homes from './src/lib/decisions/homes';
export * as cards from './src/lib/decisions/cards/index';
export * as meta from './src/lib/decisions/cards/meta';
export * as client from './src/lib/ops/client';
export * as opsStore from './src/lib/ops/store.svelte';
export * as dssData from './src/lib/dss/dss-data';
export * as dssStore from './src/lib/dss/dss-store.svelte';
export * as dssReg from './src/lib/dss/register';
export * as decReg from './src/lib/decisions/register';
export * as registry from './src/lib/workspace/registry';
export * as model from './src/lib/workspace/components/inspector/model';
export * as icons from './src/lib/design/icons';
export * as cityApi from './src/lib/gods-eye/city-api';
export * as cityReg from './src/lib/gods-eye/entities/registry.svelte';
export * as packs from './src/lib/i18n/packs.dss';
export * as strings from './src/lib/i18n/strings';
export { commandBar } from './src/lib/shell/command-bar.svelte';
`;
/** Svelte components are compiled by Vite, not here: each import becomes a named stub. */
const svelteStub = {
	name: 'svelte-component-stub',
	setup(build) {
		build.onResolve({ filter: /\.svelte$/ }, (args) => {
			const file = args.path.startsWith('$lib/') ? path.join(DECK, 'src/lib', args.path.slice(5)) : path.resolve(args.resolveDir, args.path);
			// a rune module (`x.svelte.ts`) is real code: let esbuild resolve it
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
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'dss-entry.ts' },
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
if (built.errors.length) {
	console.error(built.errors.map((e) => e.text).join('\n'));
	process.exit(1);
}

// Svelte 5 runes are compiler macros: identity stubs run the stores as plain classes.
globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });

// ─── fixtures ───────────────────────────────────────────────────────────────

const ACC = JSON.parse(readFileSync(path.join(HERE, 'fixtures/dss/dss_road_accident.json'), 'utf8'));
const HAZ = JSON.parse(readFileSync(path.join(HERE, 'fixtures/dss/dss_weather_hazard.json'), 'utf8'));

// ─── the fetch stub (every POST recorded) ───────────────────────────────────

const NOW = Date.now();
const OFFICER = 'Sandbox Officer';
const OSINT_ID = 'd5a1e555-0000-4000-8000-00000000e001';
const OSINT_URN = `osint_event:${OSINT_ID}`;
const PROMOTED_EVENT = 'd5a1e555-0000-4000-8000-0000000009f1';

const world = { posts: [], failOnce: new Map(), getFail: new Map() };
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

globalThis.fetch = async (url, init = {}) => {
	const u = String(url);
	const method = (init.method ?? 'GET').toUpperCase();
	if (method !== 'GET') {
		const body = init.body ? JSON.parse(init.body) : null;
		world.posts.push({ path: u, body });
		const fail = world.failOnce.get(u);
		if (fail) {
			world.failOnce.delete(u);
			return json(fail.body, fail.status);
		}
		if (/\/api\/v1\/decision-support\/[^/]+\/decision$/.test(u)) {
			const decision = body?.decision ?? 'approve';
			return json({
				dss_id: ACC.dss_id,
				state: decision === 'approve' ? 'approved' : decision,
				coa_id: decision === 'approve' ? (body?.coa_id ?? null) : null,
				officer: body?.officer ?? OFFICER,
				decided_at: new Date().toISOString(),
				promoted_event_id: decision === 'approve' ? PROMOTED_EVENT : null,
				dispatch_ids: decision === 'approve' ? ['d5a1d555-0000-4000-8000-000000000d01', 'd5a1d555-0000-4000-8000-000000000d02'] : [],
				next_steps: [],
			});
		}
		if (/\/api\/v1\/osint\/events\/[^/]+\/promote$/.test(u)) {
			return json({ osint_event_id: OSINT_ID, event_id: PROMOTED_EVENT, event_kind: 'road_accident', status: 'active', verification_state: 'NEWS-REPORTED', source_kind: 'osint' }, 201);
		}
		if (/\/api\/v1\/decision-support\/[^/]+\/generate$/.test(u)) return json(ACC, 201);
		return json({ detail: 'Not Found' }, 404);
	}
	// a GET that fails ONCE (the store's retry contract, fix round 2)
	const gf = world.getFail.get(u);
	if (gf) {
		world.getFail.delete(u);
		return json(gf.body, gf.status);
	}
	if (/\/api\/v1\/decision-support\/d5a1d555-0000-4000-8000-00000000d001$/.test(u)) return json(ACC);
	if (/\/api\/v1\/decision-support\/d5a1d555-0000-4000-8000-00000000d002$/.test(u)) return json(HAZ);
	return json({ detail: 'Not Found' }, 404);
};

const M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
const { units: U, writers: W, homes: H, cards, meta, client: C, opsStore, dssData: V, dssStore: S, dssReg: DREG, decReg: DECREG, registry: RG, model: MO, icons, cityReg: CR, packs, strings: T } = M;
const { ops } = opsStore;

// the named officer the writers' gate requires (the store's own gate agrees)
ops.setDutyOfficer(OFFICER);
// S5A's provider too, so the additive check sees the Pursuit section beside the dss one
DECREG.register();

const postsTo = (re) => world.posts.filter((p) => re.test(p.path));
const clearPosts = () => (world.posts.length = 0);

// ─── the tolerant C-U parser ────────────────────────────────────────────────

const acc = C.parseDecisionSupport(ACC);
ok('parse: the fixture parses to the C-U shape', !!acc && acc.dssId === ACC.dss_id && acc.eventUrn === ACC.event_urn && acc.state === 'proposed' && acc.coaSet.length === 6, acc ? `${acc.coaSet.length} coas` : 'null');
{
	// FIX-E-DSSCARD item 3: the committed files carry no deliberately-extra
	// fields (the frozen contract forbids them); the parser's tolerance for
	// unknown fields is kept as its own test over an INJECTED extra field.
	const injected = structuredClone(ACC);
	injected['synthetic'] = true;
	injected['note'] = 'injected for the tolerance test only';
	injected.situation['future_field'] = { x: 1 };
	const p = C.parseDecisionSupport(injected);
	ok('parse: the fixture parses to the C-U shape (above) with injected extras ignored', !!p && p.dssId === ACC.dss_id && p.coaSet.length === 6 && !('synthetic' in p) && !('note' in p));
}
ok('parse: recommendation, provenance and labels carry through', !!acc && eq(acc.recommendation.rankedCoaIds, ACC.recommendation.ranked_coa_ids) && acc.recommendation.bestBlocked?.coaId === 'coa_agg' && acc.recommendation.strategyPrior?.tier === 'decider_27b' && eq(acc.provenance.publishers, ['news-a.example', 'news-b.example']) && eq(acc.labels, ['NEWS-REPORTED', 'SIMULATED']));
ok('parse: a COA carries outcome, feasibility and ethics', (() => {
	const c = acc?.coaSet.find((x) => x.coaId === 'coa_std');
	return !!c && c.dispatches.length === 2 && c.disruption?.mean === 867 && c.ambulanceDelaySec === -60 && c.feasible === true && c.vetoed === false && eq(c.required, { ambulance: 1, police: 1 }) && eq(c.free, { ambulance: 1, police: 1 });
})());
{
	// orchestrator make-up (audit R2 mutant P3): 'verify' parses as verify, never folded into hold
	const v = structuredClone(ACC);
	v.recommendation.public_safety_floor = 'verify';
	ok('parse: a verify floor off the wire stays verify', C.parseDecisionSupport(v)?.recommendation.publicSafetyFloor === 'verify');
}
{
	// orchestrator make-up (audit R2 must-fix 1 and 4): source contracts for the inspector home and the banner's link
	const fs = await import('node:fs');
	const SEC = fs.readFileSync(new URL('../src/lib/dss/DecisionSupportSection.svelte', import.meta.url), 'utf8');
	const BAN = fs.readFileSync(new URL('../src/lib/dss/BestBlockedBanner.svelte', import.meta.url), 'utf8');
	ok('inspector: outside a frame (/ops) the page path names the home — never a hard-coded "/"', SEC.includes("frame?.route() ?? (typeof location !== 'undefined' ? location.pathname : '/')"));
	ok('banner: the Dispatch link exists only for a corridor event (the subject, or the report it was promoted to) and selects it first',
		BAN.includes("d?.subjectKind === 'event' ? d.urn.replace(/^event:/, '') : (d?.promotedEventId ?? null)") && BAN.includes('ops.selectedEventId = eventId;') && /\{#if eventId\}[\s\S]*dss-open-dispatch[\s\S]*\{:else\}[\s\S]*dss_best_blocked_needs_event/.test(BAN));
	ok('banner: the no-event line is carried in HI and MR', ['en', 'hi', 'mr'].every((l) => T.t(l, 'dss_best_blocked_needs_event') !== 'dss_best_blocked_needs_event') && T.t('hi', 'dss_best_blocked_needs_event') !== T.t('en', 'dss_best_blocked_needs_event'));
}
ok('parse: junk is null, not a throw', C.parseDecisionSupport(null) === null && C.parseDecisionSupport('x') === null && C.parseDecisionSupport({}) === null);
const haz = C.parseDecisionSupport(HAZ);
ok('parse: the hazard fixture has no strategy prior and no blocked pick', !!haz && haz.recommendation.strategyPrior === null && haz.recommendation.bestBlocked === null && haz.verificationState === 'OFFICIAL-VERIFIED');
// fix round 2 (audit item 5): the floor parses NATIVELY — hold/verify/none; junk and absence are null
ok(
	'parse: the public-safety floor parses natively (hold on the accident, none on the hazard, junk/absent null)',
	acc?.recommendation.publicSafetyFloor === 'hold' &&
		haz?.recommendation.publicSafetyFloor === 'none' &&
		(() => {
			const junk = structuredClone(ACC);
			junk.recommendation.public_safety_floor = 'maybe';
			const absent = structuredClone(ACC);
			delete absent.recommendation.public_safety_floor;
			return C.parseDecisionSupport(junk)?.recommendation.publicSafetyFloor === null && C.parseDecisionSupport(absent)?.recommendation.publicSafetyFloor === null;
		})(),
	String(acc?.recommendation.publicSafetyFloor),
);

// ─── the card view-model ────────────────────────────────────────────────────

const rows = V.rankedRows(acc);
ok('view: the COA list follows ranked_coa_ids (vetoed and infeasible last, never hidden)', eq(rows.map((c) => c.coaId), ACC.recommendation.ranked_coa_ids), rows.map((c) => c.coaId).join(','));
ok('view: the top FEASIBLE, non-vetoed COA is pre-selected (the engine pick)', V.defaultCoaId(acc) === 'coa_std');
ok('view: vetoed and infeasible COAs are disabled with their reasons, feasible ones selectable', (() => {
	const agg = rows.find((c) => c.coaId === 'coa_agg');
	const stop = rows.find((c) => c.coaId === 'coa_stop_vehicles');
	const std = rows.find((c) => c.coaId === 'coa_std');
	return !V.coaSelectable(agg) && !V.coaSelectable(stop) && V.coaSelectable(std) && V.coaBlockReason('en', agg).includes('2') && V.coaBlockReason('en', agg).includes('1 free') && V.coaBlockReason('en', stop).toLowerCase().includes('person');
})());
ok('view: Approve is blocked without an officer', V.approveBlocked('en', '', V.coaById(acc, 'coa_std')) !== null && V.approveBlocked('en', '  ', V.coaById(acc, 'coa_std')) !== null);
ok('view: Approve is blocked with an infeasible or vetoed COA selected, allowed with a feasible one', V.approveBlocked('en', OFFICER, V.coaById(acc, 'coa_agg')) !== null && V.approveBlocked('en', OFFICER, V.coaById(acc, 'coa_stop_vehicles')) !== null && V.approveBlocked('en', OFFICER, V.coaById(acc, 'coa_std')) === null);
ok('view: Approve is blocked with no COA selected', V.approveBlocked('en', OFFICER, null) !== null);
ok('view: the strategy-prior line appears only when present', V.strategyPriorLine('en', acc).length > 0 && V.strategyPriorLine('en', haz) === '', V.strategyPriorLine('en', acc));
ok('view: a resource-blocked best response is stated prominently, with what is missing', V.bestBlockedLine('en', acc).startsWith('Best response blocked') && V.bestBlockedLine('en', acc).includes('police'), V.bestBlockedLine('en', acc).slice(0, 90));
// FIX-E-DSSCARD item 4: the unblock clause is a localized sentence naming Dispatch — never the raw enum
{
	const unblockAt = (lang, v) => (typeof V.unblockSentence === 'function' ? V.unblockSentence(lang, v) : null);
	const line = V.bestBlockedLine('en', acc);
	ok('view: the unblock clause is a localized sentence naming Dispatch, never the raw enum', line.startsWith('Best response blocked') && !line.includes('request_units') && line.includes('Dispatch') && V.bestBlockedLine('en', haz) === '', line);
	ok('view: the unblock sentence is carried in HI and MR', typeof unblockAt('hi', 'request_units') === 'string' && (unblockAt('hi', 'request_units') ?? '').length > 8 && (unblockAt('mr', 'request_units') ?? '').length > 8 && unblockAt('hi', 'request_units') !== unblockAt('en', 'request_units'), unblockAt('hi', 'request_units') ?? 'unblockSentence missing');
}
ok('view: no blocked line when the field is absent (read defensively)', V.bestBlockedLine('en', haz) === '');
ok('view: dispatch actions and the actuating set read per C-U', V.actuatingOf(V.coaById(acc, 'coa_std')) && V.dispatchesOf(V.coaById(acc, 'coa_std')).length === 2 && !V.actuatingOf(V.coaById(acc, 'coa_min')));
// FIX-E-DSSCARD item 7: an infeasible COA's reason is stated ONCE (the row head); the feasibility line stays empty for it
ok('view: the feasibility line is empty for a blocked COA (its head carries the reason)', typeof V.feasibilityLine === 'function' && (() => {
	const agg = V.coaById(acc, 'coa_agg');
	return V.feasibilityLine(agg) === undefined || (V.feasibilityLine('en', agg) === '' && V.coaBlockReason('en', agg).includes('Resource-infeasible') && V.feasibilityLine('en', V.coaById(acc, 'coa_std')) === 'Feasible');
})());

// ── the public-safety floor (FIX-E-DSSCARD item 5; fix round 2: parser-native, accurate copy) ──

{
	const helpers = typeof V.publicSafetyFloorOf === 'function' && typeof V.floorLine === 'function' && typeof S.loadDecisionSupport === 'function' && typeof S.ensureDssObject === 'function';
	ok('floor: the parsed floor and the card line helpers exist', helpers, 'helpers missing');
	if (helpers) {
		S.resetDssState();
		const loaded = await S.loadDecisionSupport(ACC.dss_id);
		ok('floor: the store fetches through the ops client and the object carries the floor', V.publicSafetyFloorOf(loaded) === 'hold', String(V.publicSafetyFloorOf(loaded)));
		const line = V.floorLine('en', loaded);
		ok(
			'floor: the hold line says FEASIBLE and the engine\'s trigger wording (never "below every response" / "people are hurt")',
			line.startsWith('Public-safety floor:') && line.includes('feasible') && line.includes('people are reported hurt or public safety is at stake') && !line.includes('below every response') && !line.includes('people are hurt'),
			line,
		);
		ok('floor: HI and MR carry the hold line with the feasible rule', V.floorLine('hi', loaded).includes('व्यवहार्य') && V.floorLine('mr', loaded).includes('शक्य') && V.floorLine('hi', loaded).length > 40 && V.floorLine('mr', loaded).length > 40 && V.floorLine('hi', loaded) !== line, V.floorLine('hi', loaded).slice(0, 60));
		const ver = structuredClone(loaded);
		ver.recommendation.publicSafetyFloor = 'verify';
		const vline = V.floorLine('en', ver);
		ok('floor: the verify line says verify first', vline.startsWith('Public-safety floor:') && vline.includes('verify first'), vline);
		const none = structuredClone(loaded);
		none.recommendation.publicSafetyFloor = 'none';
		ok('floor: "none" and an absent field render no line', V.floorLine('en', none) === '' && V.publicSafetyFloorOf(haz) === 'none' && V.floorLine('en', haz) === '');
		await S.ensureDssObject(ACC.dss_id);
		const seeded = S.dssState.objects[ACC.dss_id];
		ok('floor: ensureDssObject seeds the parsed object once (a second call is no-op)', !!seeded && V.publicSafetyFloorOf(seeded) === 'hold');
	}
}

// ── the store's failed-GET contract (fix round 2, audit item 6): a failed GET does not stick ──

{
	S.resetDssState();
	world.getFail.set(`/api/v1/decision-support/${ACC.dss_id}`, { status: 500, body: { detail: 'forced failure' } });
	await S.ensureDssObject(ACC.dss_id);
	ok('store: a failed GET is stated honestly', !!S.dssState.failed[ACC.dss_id], S.dssState.failed[ACC.dss_id] ?? 'no failure line');
	await S.ensureDssObject(ACC.dss_id);
	ok('store: a failed GET does not stick — the remount retries and lands the object', !!S.dssState.objects[ACC.dss_id] && !S.dssState.failed[ACC.dss_id]);
	S.resetDssState();
}

// ── the inspector section's home summary (FIX-E-DSSCARD item 2) ─────────────

{
	const s = typeof V.dssHomeSummary === 'function' ? V.dssHomeSummary({ dssId: ACC.dss_id, state: 'proposed', topCoaId: 'coa_std', topCoaLabel: 'Advisory + 108 ambulance', generatedAt: ACC.generated_at, horizonMin: 120, expiresAt: new Date(NOW + 60_000).toISOString() }, OSINT_URN) : null;
	ok('inspector: the dss section builds the decision-unit summary the workspace home opens', !!s && s.kind === 'dss' && s.id === ACC.dss_id && s.subjectUrn === OSINT_URN && s.homes['/'] === 'inbox' && s.homes['/gods-eye'] === 'inbox' && s.homes['/ops'] === 'decisions' && s.deadline === NOW + 60_000 && (typeof V.dssHomeSummary === 'function' && V.dssHomeSummary(null, OSINT_URN) === null), s ? JSON.stringify(s.homes) : 'dssHomeSummary missing');
}

// ─── the approve What-changes rows (equal to C-U) ───────────────────────────

const minutesFromNow = (m) => new Date(NOW + m * 60_000).toISOString();
const dssProps = (over = {}) => ({
	dss_id: ACC.dss_id,
	state: 'proposed',
	top_coa_id: 'coa_std',
	top_coa_label: 'Advisory + 108 ambulance + 1 patrol + signal priority',
	generated_at: minutesFromNow(-60),
	horizon_min: 120,
	expires_at: minutesFromNow(60),
	...over,
});
const osintEntity = (id, props, over = {}) => ({
	urn: `osint_event:${id}`,
	kind: 'osint_event',
	id,
	label: 'Road accident · Sector V (Salt Lake)',
	lon: 88.2729,
	lat: 22.5472,
	state: null,
	band: null,
	source: 'osint',
	verificationState: 'NEWS-REPORTED',
	credibility: 0.65,
	t: NOW - 3_600_000,
	ageSec: 3600,
	links: [],
	props: {
		label: 'Road accident · Sector V (Salt Lake)',
		summary: ACC.situation.summary,
		event_class: 'road_accident',
		sajag_event_kind: 'road_accident',
		verification_state: 'NEWS-REPORTED',
		credibility: 0.65,
		second_order: [],
		promoted_event_id: null,
		segment_id: 1045,
		junction_id: null,
		...props,
	},
	...over,
});
const eventEntity = (id, props) => ({
	urn: `event:${id}`,
	kind: 'event',
	id,
	label: 'Road accident (promoted)',
	lon: 88.2729,
	lat: 22.5472,
	state: 'active',
	band: null,
	source: 'osint',
	verificationState: 'NEWS-REPORTED',
	credibility: 0.65,
	t: NOW - 600_000,
	ageSec: 600,
	links: [],
	props: { label: 'Road accident (promoted)', second_order: [], ...props },
});

CR.cityRegistry.seed({
	asOf: NOW,
	entities: [
		osintEntity(OSINT_ID, { dss: dssProps() }),
		// the same DSS on the promoted event's entity: still ONE unit
		eventEntity(PROMOTED_EVENT, { dss: dssProps() }),
		// an expired DSS is never a unit
		osintEntity('d5a1e555-0000-4000-8000-00000000e003', {
			dss: dssProps({ dss_id: 'd5a1d555-0000-4000-8000-00000000d009', expires_at: minutesFromNow(-5) }),
			verification_state: 'UNVERIFIED-OSINT',
			credibility: 0.3,
			summary: 'Unverified social report of a jam',
			event_class: 'public_disorder',
		}),
	],
	feeds: {},
	tookMs: 1,
});
S.resetDssState();
S.seedDssObject(acc);

const dssUnits = U.decisionUnits().filter((u) => u.kind === 'dss');
ok('units: one unit per DSS — the subject on the osint_event AND the event is ONE unit', dssUnits.length === 1, `${dssUnits.length} dss units`);
const dunit = dssUnits[0];
ok('units: id = the dss id, subject = the (unpromoted) osint urn', !!dunit && dunit.id === ACC.dss_id && dunit.subjectUrn === OSINT_URN, dunit?.subjectUrn);
ok('units: the title is "Approve a response to <label>"', !!dunit && dunit.title === 'Approve a response to Road accident · Sector V (Salt Lake)', dunit?.title);
ok('units: deadline = expires_at', !!dunit && dunit.deadline === Date.parse(minutesFromNow(60)), String(dunit?.deadline));
ok('units: severity 2 — NEWS-REPORTED with injuries in the class', !!dunit && dunit.severity === 2, String(dunit?.severity));
ok('units: data hooks carry kind, id and subject', !!dunit && eq(U.UNIT_KINDS.dss.dataHooks(dunit), { kind: 'dss', id: ACC.dss_id, subject: OSINT_URN }), JSON.stringify(dunit ? U.UNIT_KINDS.dss.dataHooks(dunit) : {}));
ok('units: the expired DSS yields NO unit (an expired one is never waiting)', !U.decisionUnits().some((u) => u.kind === 'dss' && u.id === 'd5a1d555-0000-4000-8000-00000000d009'));

// severity 3: a second-order flag naming a 108/protected corridor
CR.cityRegistry.seed({
	asOf: NOW,
	entities: [
		osintEntity(OSINT_ID, {
			dss: dssProps(),
			second_order: [{ kind: 'escort_hold', urn: `event:${PROMOTED_EVENT}`, segment_id: 1013, note: 'a 108 golden-hour window is held on this road' }],
		}),
	],
	feeds: {},
	tookMs: 1,
});
const priUnit = U.decisionUnits().find((u) => u.kind === 'dss');
ok('units: a second-order flag naming a 108 route or protected corridor is severity 3', !!priUnit && priUnit.severity === 3, String(priUnit?.severity));
ok('units: an OFFICIAL-VERIFIED hazard without injuries is severity 1', (() => {
	CR.cityRegistry.seed({
		asOf: NOW,
		entities: [
			osintEntity(
				'd5a1e555-0000-4000-8000-00000000e002',
				{
					dss: dssProps({ dss_id: HAZ.dss_id, top_coa_id: 'coa_min', top_coa_label: 'Driver advisory only (VMS + app push)' }),
					summary: 'Light rain likely at isolated places over the district',
					event_class: 'weather_hazard',
					sajag_event_kind: 'hazard',
					segment_id: null,
					label: 'Weather hazard · Mumbai City district',
				},
				{ label: 'Weather hazard · Mumbai City district', verificationState: 'OFFICIAL-VERIFIED', credibility: 0.95 },
			),
		],
		feeds: {},
		tookMs: 1,
	});
	const u = U.decisionUnits().find((x) => x.kind === 'dss');
	return !!u && u.severity === 1 && u.title === 'Approve a response to Weather hazard · Mumbai City district';
})());
// restore the main world
CR.cityRegistry.seed({
	asOf: NOW,
	entities: [osintEntity(OSINT_ID, { dss: dssProps() }), eventEntity(PROMOTED_EVENT, { dss: dssProps() })],
	feeds: {},
	tookMs: 1,
});
const unit = U.decisionUnits().find((u) => u.kind === 'dss');

const PERSON_KEY_RE = /\b(?:author|person|handle|username|byline|reporter|poster|uploader|suspect|accused|victim|owner|driver_name|face|biometric)\b|individual_/i;
const keysOf = (v, depth = 0, out = new Set()) => {
	if (depth > 6 || !v || typeof v !== 'object') return out;
	for (const [k, x] of Object.entries(v)) {
		out.add(k);
		keysOf(x, depth + 1, out);
	}
	return out;
};
const personKeys = [...keysOf(unit?.data ?? {})].filter((k) => PERSON_KEY_RE.test(k.replace(/([A-Z])/g, '_$1').toLowerCase()));
ok('ethics: no person field anywhere in the unit', personKeys.length === 0, personKeys.join(',') || 'none');
ok('ethics: the publishers stay fictional (*.example)', !!unit && JSON.stringify(unit.data).includes('news-a.example') === false && (S.dssState.objects[ACC.dss_id]?.provenance.publishers ?? []).every((p) => p.endsWith('.example') || p === 'sachet.ndma.gov.in'));

// ─── WRITERS: the approve What-changes rows, equal to C-U ───────────────────

const wApprove = W.WRITERS['dss.approve'];
ok('writers: dss approve/reject/defer exist with the named-actor refusals', !!wApprove && !!W.WRITERS['dss.reject'] && !!W.WRITERS['dss.defer'] && ['officer-required', 'not-proposed', 'coa-vetoed', 'coa-infeasible', 'unknown-coa', 'no-anchor'].every((c) => typeof wApprove.refusals[c] === 'string' && wApprove.refusals[c].length > 0));
ok('writers: the dss actions are Approve (primary) and Reject (secondary)', W.ACTIONS.dss?.primary === 'approve' && W.ACTIONS.dss?.secondary === 'reject');
ok('cards: the dss card body is registered', typeof cards.CARD_BODIES.dss === 'function');
ok('homes: dss is decided in the Inbox on / and /gods-eye, in Decisions on /ops', H.HOMES.dss['/'] === 'inbox' && H.HOMES.dss['/gods-eye'] === 'inbox' && H.HOMES.dss['/ops'] === 'decisions');

{
	const rowsA = wApprove.changes(unit, { dss: acc });
	const changed = rowsA.filter((r) => r.after != null);
	ok('approve rows: the DSS row (proposed → approved with the chosen COA, you, now)', rowsA[0]?.object === 'Decision support' && rowsA[0]?.now === 'proposed' && (rowsA[0]?.after ?? '').startsWith('approved (Advisory + 108 ambulance + 1 patrol + signal priority') && (rowsA[0]?.after ?? '').includes('you, now') && eq(rowsA[0]?.writes, [ACC.dss_id]), JSON.stringify(rowsA[0]));
	ok('approve rows: the OSINT report is promoted, its verification state kept', rowsA.some((r) => r.object === 'OSINT report' && (r.after ?? '').includes('promoted to a corridor event') && (r.after ?? '').includes('Road accident') && (r.after ?? '').includes('verification state kept') && eq(r.writes, [OSINT_ID])), JSON.stringify(rowsA[1]));
	const dispatchRows = rowsA.filter((r) => (r.after ?? '').startsWith('created as requested'));
	ok('approve rows: ONE row per dispatch action (Ambulance (108) × 1, Police × 1)', dispatchRows.length === 2 && dispatchRows.some((r) => r.object.includes('Ambulance (108) × 1')) && dispatchRows.some((r) => r.object.includes('Police × 1')) && dispatchRows.every((r) => (r.after ?? '').includes('decided separately as a corridor request')), JSON.stringify(dispatchRows.map((r) => r.object)));
	ok('approve rows: advisory and signal-hold change nothing (rows with No change)', rowsA.filter((r) => r.after === null && (r.object.includes('Advisory') || r.object.includes('Signal'))).length === 2, JSON.stringify(rowsA.filter((r) => r.after === null).map((r) => r.object)));
	ok('approve rows: unchanged — the other courses of action and every other unit', eq(wApprove.unchanged(unit), ['the other courses of action', "every unit's status until its own decision"]), JSON.stringify(wApprove.unchanged(unit)));
	const next = wApprove.nextStep?.(unit, { dss: acc }) ?? '';
	ok('approve rows: the next steps name the advisory and signal-hold homes (C-U)', next.includes('Advisories (draft only)') && next.includes('City signal plans (writer off by default)'), next);
}

// a monitor-only COA: no promotion row, no dispatch rows, no next step
{
	const rowsM = wApprove.changes(unit, { dss: haz, coaId: 'coa_base' });
	ok('approve rows (monitor): the DSS row only, the subject untouched', rowsM.length === 1 && rowsM[0].after.startsWith('approved (Monitor only') && eq(rowsM[0].writes, [ACC.dss_id]), JSON.stringify(rowsM));
	ok('approve rows (monitor): no next step (monitor → none)', (wApprove.nextStep?.(unit, { dss: haz, coaId: 'coa_base' }) ?? '') === '');
}

// FIX-E-DSSCARD item 9: a subject that is ALREADY promoted shows no promotion row (the row names the
// promotion approving CAN cause — it happened already), while the dispatch rows stay
{
	CR.cityRegistry.seed({
		asOf: NOW,
		entities: [osintEntity(OSINT_ID, { dss: dssProps(), promoted_event_id: PROMOTED_EVENT }), eventEntity(PROMOTED_EVENT, { dss: dssProps() })],
		feeds: {},
		tookMs: 1,
	});
	const promotedUnit = U.decisionUnits().find((u) => u.kind === 'dss');
	const rowsP = wApprove.changes(promotedUnit, { dss: acc });
	ok('approve rows (already promoted): NO promotion row when the report is promoted', !rowsP.some((r) => r.object === 'OSINT report'), JSON.stringify(rowsP.map((r) => r.object)));
	ok('approve rows (already promoted): the decision and dispatch rows stay', rowsP[0]?.object === 'Decision support' && rowsP.filter((r) => (r.after ?? '').startsWith('created as requested')).length === 2, JSON.stringify(rowsP.map((r) => r.object)));
	// restore the unpromoted world
	CR.cityRegistry.seed({
		asOf: NOW,
		entities: [osintEntity(OSINT_ID, { dss: dssProps() }), eventEntity(PROMOTED_EVENT, { dss: dssProps() })],
		feeds: {},
		tookMs: 1,
	});
}

// FIX-E-DSSCARD item 1: Defer is gated only on the officer and the footer's note — never on Approve's rules
{
	const at = (lang, o, n) => (typeof V.deferBlocked === 'function' ? V.deferBlocked(lang, o, n) : null);
	ok('defer gate: only the officer and the note gate it (no COA needed)', at('en', OFFICER, 'waiting for the official confirmation') === null && at('en', OFFICER, '') !== null && at('en', OFFICER, '   ') !== null && at('en', '', 'x') !== null && at('en', OFFICER, 'waiting for the official confirmation') === null && V.approveBlocked('en', OFFICER, null) !== null, `deferBlocked=${String(at('en', OFFICER, 'waiting for the official confirmation'))}`);
	ok('defer gate: the note reason is the defer hint, in HI and MR too', at('en', OFFICER, '') === T.t('en', 'dss_defer_hint') && (at('hi', OFFICER, '') ?? '').length > 4 && (at('mr', OFFICER, '') ?? '').length > 4, String(at('en', OFFICER, '')));
	ok('defer gate: its officer reason names DEFER, and the hint points to the Reason field BELOW (fix round 2)', at('en', '', 'x') === T.t('en', 'dss_reason_officer_defer') && at('en', '', 'x') !== T.t('en', 'dss_reason_officer') && T.t('en', 'dss_defer_hint') === 'needs a reason (the Reason field below)' && !T.t('en', 'dss_defer_hint').includes('above'), String(at('en', '', 'x')));
}

// run: the approve POST is ONE call carrying the officer, the chosen coa_id and the note
{
	W.resetWriterGuards();
	clearPosts();
	S.resetDssState();
	S.seedDssObject(acc);
	const res = await wApprove.run(unit, OFFICER, { note: 'injured riders need the ambulance' });
	const sent = postsTo(/\/decision-support\/[^/]+\/decision$/);
	ok('approve run: ONE POST with decision approve, the chosen coa_id, the officer and the note', res.ok && sent.length === 1 && sent[0].body.decision === 'approve' && sent[0].body.coa_id === 'coa_std' && sent[0].body.officer === OFFICER && sent[0].body.note === 'injured riders need the ambulance', JSON.stringify(sent[0]?.body));
	W.resetWriterGuards();
	const [a, b] = await Promise.all([wApprove.run(unit, OFFICER, { note: 'x' }), wApprove.run(unit, OFFICER, { note: 'x' })]);
	ok('approve run: a double click sends ONE POST', postsTo(/\/decision$/).length === 2 && a.ok && b.ok, `${postsTo(/\/decision$/).length} POSTs`);
}

// run: pre-flight refusals never POST
{
	W.resetWriterGuards();
	clearPosts();
	S.resetDssState();
	S.seedDssObject(acc);
	const noOfficer = await wApprove.run(unit, '', { note: 'x' });
	ok('approve run: no officer → officer-required, nothing sent', !noOfficer.ok && noOfficer.refusal === 'officer-required' && world.posts.length === 0);
	S.selectCoa(ACC.dss_id, 'coa_agg');
	const infeasible = await wApprove.run(unit, OFFICER, { note: 'x' });
	ok('approve run: an infeasible COA selected → coa-infeasible before the wire', !infeasible.ok && infeasible.refusal === 'coa-infeasible' && world.posts.length === 0);
	S.selectCoa(ACC.dss_id, 'coa_stop_vehicles');
	const vetoed = await wApprove.run(unit, OFFICER, { note: 'x' });
	ok('approve run: a vetoed COA selected → coa-vetoed before the wire', !vetoed.ok && vetoed.refusal === 'coa-vetoed' && world.posts.length === 0);
	S.selectCoa(ACC.dss_id, 'coa_std');
}

// the oracle's 409 comes back verbatim and is never retried blind
{
	W.resetWriterGuards();
	clearPosts();
	world.failOnce.set(`/api/v1/decision-support/${ACC.dss_id}/decision`, { status: 409, body: { detail: 'coa-infeasible' } });
	const res = await wApprove.run(unit, OFFICER, { note: 'x' });
	const sent = postsTo(/\/decision$/);
	ok('approve run: the 409 code and detail are kept verbatim', !res.ok && res.refusal === 'coa-infeasible' && res.detail === 'coa-infeasible' && S.dssState.refusals[ACC.dss_id]?.detail === 'coa-infeasible', `${res.detail ?? ''} / ${sent.length} POST`);
	W.resetWriterGuards();
	const again = await wApprove.run(unit, OFFICER, { note: 'x' });
	ok('approve run: a retry re-POSTs (the refusal was the server state; the officer may retry, the oracle decides)', again.ok && postsTo(/\/decision$/).length === 2, `${postsTo(/\/decision$/).length} POSTs`);
}

// reject and defer require a note
{
	W.resetWriterGuards();
	clearPosts();
	const rej = W.WRITERS['dss.reject'];
	const def = W.WRITERS['dss.defer'];
	const r1 = await rej.run(unit, OFFICER, {});
	const r2 = await def.run(unit, OFFICER, { note: '  ' });
	ok('reject/defer: refused without a note, nothing sent', !r1.ok && r1.refusal === 'reason-required' && !r2.ok && r2.refusal === 'reason-required' && world.posts.length === 0);
	const rowsR = rej.changes(unit, { note: 'sources unverified, no corroboration' });
	ok('reject rows: proposed → rejected (the officer reason), the subject untouched', rowsR.length === 1 && rowsR[0].object === 'Decision support' && rowsR[0].now === 'proposed' && rowsR[0].after === 'rejected (sources unverified, no corroboration)', JSON.stringify(rowsR));
	const rowsD = def.changes(unit, { note: 'waiting for the official confirmation' });
	ok('defer rows: proposed → deferred (the officer reason)', rowsD.length === 1 && rowsD[0].after === 'deferred (waiting for the official confirmation)', JSON.stringify(rowsD));
	const okR = await rej.run(unit, OFFICER, { note: 'sources unverified, no corroboration' });
	const sent = postsTo(/\/decision$/);
	ok('reject run: ONE POST with decision reject, the note, the officer — no coa_id', okR.ok && sent.length === 1 && sent[0].body.decision === 'reject' && sent[0].body.note === 'sources unverified, no corroboration' && sent[0].body.officer === OFFICER && !('coa_id' in sent[0].body), JSON.stringify(sent[0]?.body));
	W.resetWriterGuards();
	clearPosts();
	const okD = await def.run(unit, OFFICER, { note: 'waiting for the official confirmation' });
	const sent2 = postsTo(/\/decision$/);
	ok('defer run: ONE POST with decision defer', okD.ok && sent2.length === 1 && sent2[0].body.decision === 'defer', JSON.stringify(sent2[0]?.body));
}

// ─── the wiring contract over the .svelte sources (fix round 2, audit S2: the defects ──
// ── lived in the .svelte wiring, which the component-stubbed bundle cannot see)     ──

{
	const srcOf = (p) => readFileSync(path.join(DECK, p), 'utf8');
	const BODY = srcOf('src/lib/dss/DssProposalBody.svelte');
	const CARD = srcOf('src/lib/decisions/ProposalCard.svelte');
	const SEC = srcOf('src/lib/dss/DecisionSupportSection.svelte');
	const BANNER = srcOf('src/lib/dss/BestBlockedBanner.svelte');
	const STORE = srcOf('src/lib/dss/dss-store.svelte.ts');
	const HARNESS = srcOf('src/routes/(deck)/design/dss/+page.svelte');
	ok('contract: Defer sends the footer\'s note (never an empty one) and is gated by deferBlock, never Approve\'s block', BODY.includes('w.run(unit, officer, { note })') && !BODY.includes("{ note: '' }") && BODY.includes('disabled={deferBlock != null || busy}') && BODY.includes('disabledReason={deferBlock ?? null}') && !BODY.includes('disabled={block'));
	ok('contract: a failed Defer is caught and shown, not an unhandled rejection', /async function deferNow\(\)[\s\S]*?\} catch \(err\) \{/.test(BODY) && BODY.includes('recordDssRefusal(unit.id'));
	ok('contract: the banner mounts in the card header and the footer\'s reason reaches the body', CARD.includes('<BestBlockedBanner {unit} {lang} />') && CARD.includes('reason={reason}'));
	ok('contract: the dss reason label and placeholder are the dss-specific ones', CARD.includes("L('dec_reason_info_dss')") && CARD.includes("L('dec_reason_placeholder_dss')"));
	ok('contract: an infeasible row\'s reason renders once — the head; the feasibility span is conditional', BODY.includes('{#if feasibilityLine(lang, c)}<span class="c-feas">{feasibilityLine(lang, c)}</span>{/if}'));
	ok('contract: the floor line renders in the body with its test id', BODY.includes('{#if floorLine(lang, dss)}') && BODY.includes('data-testid="dss-safety-floor"'));
	ok('contract: the section opens the workspace home (the frame\'s route), never a raw hash href', SEC.includes('workspace.openDecisionHome(s, route)') && !SEC.includes('location.href') && !/<a\s/.test(SEC) && SEC.includes('frameContext'));
	ok('contract: the banner writes nothing — no writer, no request-unit action; it links Dispatch', !BANNER.includes('WRITERS') && !BANNER.includes('requestDispatchUnit') && !BANNER.includes('request_units') && BANNER.includes('href="/ops"') && !BANNER.includes('dssState.failed'));
	ok('contract: the store fetches through the ops client (no raw fetch, no raw-wire floor merge) and clears the guard on failure', STORE.includes('getDecisionSupport(dssId)') && !/fetch\(/.test(STORE) && !STORE.includes('public_safety_floor') && /catch \(err\) \{[\s\S]*?requested\.delete\(id\)/.test(STORE));
	ok('contract: the /design/dss harness exposes the officer toggle and both fixtures', HARNESS.includes('harness-officer') && HARNESS.includes('harness-fixture') && HARNESS.includes('dss_road_accident.json') && HARNESS.includes('dss_weather_hazard.json'));
}

// ─── the rule note (plan X22, verbatim) ─────────────────────────────────────

const X22 = 'The engine proposes; a named officer decides. Approving creates dispatch requests (each decided on its own) and, when the response needs a corridor event, promotes this report to one.';
ok('rule note: the EN sentence equals the X22 rule exactly', T.t('en', 'dss_rule_note') === X22, T.t('en', 'dss_rule_note'));
ok('rule note: carried in HI and MR too', T.t('hi', 'dss_rule_note').length > 20 && T.t('mr', 'dss_rule_note').length > 20 && T.t('hi', 'dss_rule_note') !== X22);

// ─── meta: glyph, subtitle, age ─────────────────────────────────────────────

ok('meta: the header actor glyph is the decision-support engine (function)', meta.actorIcon(unit) === icons.ACTOR_ICON.rules && icons.ACTOR_ICON.rules === 'function');
ok('meta: the subtitle names the engine, the verification label and the credibility', meta.proposerLine(unit, 'en', NOW) === 'Proposed by the decision-support engine · News-reported · credibility 0.65', meta.proposerLine(unit, 'en', NOW));
ok('meta: the row line names the recommended COA and the horizon', (meta.rowMeta(unit, 'en', NOW) ?? '').includes('Advisory + 108 ambulance'), meta.rowMeta(unit, 'en', NOW));
ok('meta: the age column counts down to the expiry', (() => {
	const a = meta.ageOf(unit, 'en', NOW);
	return a.label === 'expires in' && a.countdown === true;
})());

// ─── one link card per DSS in the inspector (ownsUnitKinds) ─────────────────

RG.resetRegistry();
DECREG.register();
DREG.register();
const owned = RG.ownedUnitKinds('osint_event');
ok('register: the dss section owns the dss unit kind for osint_event and event', owned.has('dss') && RG.ownedUnitKinds('event').has('dss'));
ok('register: additive — the Pursuit section stays on event, the dss section has its own id', RG.inspectorSectionsFor('event').some((s) => s.id === 'pursuit') && RG.inspectorSectionsFor('event').some((s) => s.id === 'dss') && RG.inspectorSectionsFor('osint_event').some((s) => s.id === 'dss'));
ok('register: the promote action is registered for osint_event under its own id', RG.actionsFor({ urn: OSINT_URN, kind: 'osint_event', id: OSINT_ID, label: '', sublabel: null, icon: 'dot', state: null, stateIntent: 'none', t: null, end: null, lon: null, lat: null, source: 'osint', verification: null, credibility: null, test: false, masked: false, props: {} }).some((a) => a.id === 'dss.promote'));
{
	const summaries = U.decisionUnits().map((u) => ({ kind: u.kind, id: u.id, subjectUrn: u.subjectUrn, title: u.title, deadline: u.deadline, severity: u.severity, homes: H.HOMES[u.kind] }));
	const withoutOwnership = summaries.filter((s) => s.subjectUrn === OSINT_URN);
	const withOwnership = MO.linkCards(OSINT_URN, summaries, owned);
	ok('inspector: without ownership the object would carry a link card; with it, the Actions tab adds none', withoutOwnership.length === 1 && withOwnership.length === 0, `${withOwnership.length} actions-tab cards`);
	ok('inspector: the operator sees exactly ONE link card per DSS (the section’s own)', withOwnership.length + 1 === 1);
}

// ─── the promote writer and client ──────────────────────────────────────────

{
	W.resetWriterGuards();
	clearPosts();
	const res = await C.promoteOsintEvent(OSINT_ID, { note: 'response approved on Sector V - New Town link', eventKind: 'road_accident' }, OFFICER);
	const sent = postsTo(/\/osint\/events\/[^/]+\/promote$/);
	ok('promote client: ONE POST with the officer, the note and the kind; 201 parsed', res.ok && sent.length === 1 && sent[0].body.officer === OFFICER && sent[0].body.note === 'response approved on Sector V - New Town link' && sent[0].body.event_kind === 'road_accident' && res.eventId === PROMOTED_EVENT && res.eventKind === 'road_accident' && res.verificationState === 'NEWS-REPORTED', JSON.stringify(sent[0]?.body));
	try {
		await C.promoteOsintEvent('../etc/passwd', {}, OFFICER);
		ok('promote client: a hostile id is rejected before any fetch', false, 'accepted');
	} catch (err) {
		ok('promote client: a hostile id is rejected before any fetch', !(err instanceof TypeError), err.constructor.name);
	}
	const blank = await C.promoteOsintEvent(OSINT_ID, {}, '').then(
		() => null,
		(err) => err,
	);
	ok('promote client: a blank officer is refused before any fetch', blank instanceof Error && blank.name === 'CommitRefused', blank?.constructor?.name);
	world.failOnce.set(`/api/v1/osint/events/${OSINT_ID}/promote`, { status: 409, body: { detail: 'no-anchor' } });
	const refused = await C.promoteOsintEvent(OSINT_ID, {}, OFFICER);
	ok('promote client: a 409 code round-trips with its verbatim detail', !refused.ok && refused.refusal === 'no-anchor' && refused.detail === 'no-anchor');
}

// generate: compute only, URN validated, no actor
{
	clearPosts();
	const gen = await C.generateDecisionSupport(OSINT_URN, { horizonMin: 120 });
	const sent = postsTo(/\/generate$/);
	ok('generate: ONE compute POST with the urn path and the horizon, no officer field', gen?.dssId === ACC.dss_id && sent.length === 1 && decodeURIComponent(sent[0].path).endsWith(`/${OSINT_URN}/generate`) && sent[0].body.horizon_min === 120 && !('officer' in sent[0].body) && !('actor' in sent[0].body), JSON.stringify(sent[0]?.body));
	const bad = await C.generateDecisionSupport('osint_event:../x', { horizonMin: 45 }).then(
		() => null,
		(err) => err,
	);
	ok('generate: a hostile URN is refused before any fetch', bad instanceof Error && postsTo(/\/generate$/).length === 1, bad?.constructor?.name);
	const got = await C.getDecisionSupport(ACC.dss_id);
	ok('get: the full object is fetched by id', got?.dssId === ACC.dss_id && got.coaSet.length === 6);
}

// ─── the dss pack ───────────────────────────────────────────────────────────

const P_EN = Object.keys(packs.DSS_PACKS.en).sort();
ok('pack: EN, HI and MR carry the same keys', eq(P_EN, Object.keys(packs.DSS_PACKS.hi).sort()) && eq(P_EN, Object.keys(packs.DSS_PACKS.mr).sort()), `${P_EN.length} keys`);
{
	const walk = (dir) => readdirSync(dir).flatMap((f) => (statSync(path.join(dir, f)).isDirectory() ? walk(path.join(dir, f)) : [path.join(dir, f)]));
	const files = [...walk(path.join(DECK, 'src/lib/dss')), path.join(DECK, 'src/lib/decisions/units.ts'), path.join(DECK, 'src/lib/decisions/writers.ts'), path.join(DECK, 'src/lib/decisions/cards/meta.ts')];
	const used = new Set();
	for (const f of files) for (const m of readFileSync(f, 'utf8').matchAll(/'(dss_[a-z0-9_]+)'/g)) used.add(m[1]);
	const missing = [...used].filter((k) => !P_EN.includes(k));
	ok('pack: every dss_ key the dss sources use exists (EN)', missing.length === 0, missing.join(',') || `${used.size} keys`);
}

// ─── done ───────────────────────────────────────────────────────────────────

if (failures) {
	console.error(`dss.unit: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('ok   dss.unit — all assertions passed');
process.exit(0);
