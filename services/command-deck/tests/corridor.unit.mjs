/**
 * Corridor unit test (UI-S6A; SPEC §5.3 PlanPanel [S6] and ConvoyCard [S6],
 * §9.2; plan X6, X9, R12) — the corridor's pure logic, bundled with esbuild
 * the deck's `*.unit.mjs` way: `corridor/plan.ts` (the plan state machine),
 * `corridor/events.ts` (the Active events' row facts), `corridor/
 * escort-state.svelte.ts` (the legacy referred-actions rule), the S5A
 * decisions tables the ConvoyCard reads (units + WRITERS) and the corridor
 * pack.
 *
 *   node tests/corridor.unit.mjs
 *
 * `.svelte` imports are stubbed (no compiler here); `$state` is an identity
 * stub so the rune modules run as plain code. A second bundle compiles the
 * corridor's Svelte components for the SERVER (svelte/compiler, generate:
 * 'server') and renders them with svelte/server, so the assertions read the
 * markup the page ships (the wall.unit.mjs pattern). Asserts, from fixtures:
 *   - the plan states: Approved; CONDITIONAL (Launch locked until the
 *     waiver is accepted AND an officer is named — the Reason says which
 *     first); HOLD (locked, whatever the tier says); NO ROUTE (no
 *     candidates, Launch hidden); a hold riding a conditional plan wins;
 *   - the candidate labels: an alternate "adds <roads>" from the roads it
 *     takes that the primary does not (two names, then +n); no invented
 *     adds when the plan reports no road names; the flow's provenance label
 *     is the metric strip's derivation (the feed's label, else the summary's
 *     with 'emulated' read as 'simulated') and 'mixed' rides through;
 *   - the /ops wall reads the lanes: `laneRunning` answers from
 *     `ops.escortsDeployed` alone, and the wall block never starts the
 *     shared follower (it borrows one the cockpit's lifecycle runs);
 *   - the ConvoyCard's What-changes rows equal S5A's
 *     `WRITERS['escort-proposal.approve']` entry for the same unit (the
 *     card hosts the ProposalCard, which renders that table): a hold shows
 *     the convoy holding short of the road with the bound, and the route
 *     and signal plans unchanged;
 *   - the legacy referred-actions list is ABSENT when the escort reports
 *     proposals (the lanes are deployed, or the followed document reports
 *     authority), and present otherwise, and only while the escort runs;
 *   - RENDERED ActiveEvents (audit C S2/S3): the highlight comes from
 *     `selection.current === 'event:<id>'` — not `ops.selectedEventId` —
 *     rows show LABELS, never a raw `vehicle_pursuit` / `planned`, the
 *     emulated glyph's hidden text is exactly "Emulated" and the rehearsal
 *     tag reads exactly "Test" in the shipped markup;
 *   - RENDERED ConvoyCard on the wall (/ops): the lanes' running escort is
 *     phase 'escorting' with the key figures (the follower's document: speed,
 *     progress, ETA, hold — a hold renders on the wall), the provenance tags
 *     come from the LANE when no follower document exists, missing figures
 *     say so plainly (never a row of dashes), and the wall carries ONE
 *     attribution and ONE countdown (the pinned header stays on the
 *     Movement tab);
 *   - RENDERED PlanPanel: "Plan corridor" is a full-width primary (fill),
 *     the recommended pick states itself (no tooltip), no "N seg" jargon,
 *     and NO ROUTE is neutral ink (no danger intent);
 *   - RENDERED MapTile legend: the simulated-flow item is the prop's alone;
 *   - the corridor pack: EN, HI and MR carry the same keys, the lazy tab's
 *     failure line resolves in all three (and differs from EN), and the
 *     route pages carry the audit-C/audit-E structure (no escort auto-open
 *     of the left dock, no unregistered 'movement' seed, the Inbox default,
 *     the one-line credit plate with no clamp, the 36 px map-mode bottom
 *     dock, the collapsed card below the toolbar, the scrolling dock-tab row
 *     with a pinned hide button);
 *   - the audit-C colour rails in the corridor's COMPILED CSS: the Test tag,
 *     the protection class, a <15 s countdown and refusals are neutral/ink
 *     (never warning/danger var()).
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const OUT = path.join(HERE, 'artifacts', 'corridor-bundle.mjs');
// the rendered-components bundle goes to the OS temp dir (never tests/artifacts/**)
const OUT_SSR = path.join(process.env.CORRIDOR_UNIT_OUT ?? path.join(os.tmpdir(), 'sajag-corridor-unit'), 'corridor-ssr-bundle.mjs');

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
export * as plan from './src/lib/corridor/plan';
export * as events from './src/lib/corridor/events';
export * as escortState from './src/lib/corridor/escort-state.svelte';
export * as units from './src/lib/decisions/units';
export * as writers from './src/lib/decisions/writers';
export * as opsStore from './src/lib/ops/store.svelte';
export * as strings from './src/lib/i18n/strings';
export * as packs from './src/lib/i18n/packs.corridor';
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
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'corridor-entry.ts' },
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

// Svelte 5 runes are compiler macros: identity stubs run the rune modules as plain code.
globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });

const mod = await import(OUT);
const { plan, events, escortState, units, writers, packs } = mod;

// ─── fixtures (contract C-I documents; marks masked) ───────────────────────

const candidate = (over = {}) => ({
	route_id: 'r1',
	segment_ids: [1013],
	road_names: ['Strand Road'],
	distance_m: 4300,
	estimated_time_sec: 420,
	route_tier: 'compliant',
	...over,
});

const DOC_APPROVED = {
	movement_id: 'mv-1',
	status: 'approved',
	security_compliant: true,
	security_score: 0.9,
	primary_route: candidate(),
	alternate_routes: [
		candidate({ route_id: 'r2', road_names: ['Strand Road', 'Kidderpore Road'], route_tier: 'conditional', lane_violations: [{ segment_id: 1045, detail: 'lane floor 2 below the Z floor' }] }),
	],
	decider_pick: { route_id: 'r1', confidence: 0.93, tier: 'strategic', applied: true },
};

const DOC_CONDITIONAL = {
	...DOC_APPROVED,
	movement_id: 'mv-2',
	status: 'conditional',
	security_compliant: false,
	primary_route: candidate({ route_id: 'r1', route_tier: 'conditional', lane_violations: [{ segment_id: 1045, detail: 'lane floor 2 below the Z floor' }] }),
	alternate_routes: [candidate({ route_id: 'r2', road_names: ['Strand Road', 'Kidderpore Road'] })],
};

const DOC_HOLD = { ...DOC_APPROVED, movement_id: 'mv-3', status: 'hold' };
const DOC_HOLD_RIDING = { ...DOC_CONDITIONAL, movement_id: 'mv-4', hold: true };
const DOC_NO_ROUTE = { movement_id: 'mv-5', status: 'no_route', primary_route: null, alternate_routes: [], overall_reasoning: 'no corridor road connects the pair within the class floor' };

const GATE_COPY = {
	waiverNeeded: 'Accept the lane-floor violations first — the plan is conditional.',
	holdLocked: 'The decider held this plan — re-plan for a later departure.',
	officerNeeded: 'Name the duty officer to launch.',
	noPlan: 'Plan a corridor first.',
};

// ─── 1. the plan state machine ──────────────────────────────────────────────

{
	const g = (doc, o = {}) => plan.launchGate(doc, { waiverAccepted: false, officerNamed: false, ...o }, GATE_COPY);

	const approved = g(DOC_APPROVED);
	ok('plan: approved — security compliant, escort offered, launch locked on the officer only', plan.planStateOf(DOC_APPROVED) === 'approved' && approved.escortOffered && !approved.held && approved.launchLockReason === GATE_COPY.officerNeeded);

	const named = g(DOC_APPROVED, { officerNamed: true });
	ok('plan: approved + a named officer — launch unlocked', !named.launchLocked && named.launchLockReason === null);

	const conditional = g(DOC_CONDITIONAL);
	ok(
		'plan: conditional — the violations listed, launch locked on the waiver first',
		plan.planStateOf(DOC_CONDITIONAL) === 'conditional' && conditional.needsWaiver && conditional.launchLockReason === GATE_COPY.waiverNeeded && plan.planViolations(DOC_CONDITIONAL).length === 1,
	);
	const waivedNoOfficer = g(DOC_CONDITIONAL, { waiverAccepted: true });
	ok('plan: conditional + waiver but no officer — still locked (the Reason names the officer)', waivedNoOfficer.needsWaiver === false && waivedNoOfficer.launchLockReason === GATE_COPY.officerNeeded);
	const waivedNamed = g(DOC_CONDITIONAL, { waiverAccepted: true, officerNamed: true });
	ok('plan: conditional + waiver + officer — launch unlocks', !waivedNamed.launchLocked);

	const hold = g(DOC_HOLD);
	ok('plan: hold — launch locked with the hold reason', plan.planStateOf(DOC_HOLD) === 'hold' && hold.held && !hold.escortOffered && hold.launchLockReason === GATE_COPY.holdLocked);
	const holdNamed = g(DOC_HOLD, { officerNamed: true, waiverAccepted: true });
	ok('plan: hold + officer + waiver — STILL locked (a plan that cannot depart never launches)', holdNamed.launchLocked && holdNamed.launchLockReason === GATE_COPY.holdLocked);

	const riding = g(DOC_HOLD_RIDING);
	ok('plan: a hold riding a conditional plan wins', plan.planStateOf(DOC_HOLD_RIDING) === 'hold' && riding.held && !riding.escortOffered);

	const noRoute = g(DOC_NO_ROUTE);
	ok('plan: no route — no candidates, escort NOT offered (launch hidden)', plan.planStateOf(DOC_NO_ROUTE) === 'no_route' && plan.routeCandidates(DOC_NO_ROUTE).length === 0 && !noRoute.escortOffered);

	ok('plan: no document yet — state none, nothing offered', plan.planStateOf(null) === 'none' && g(null).escortOffered === false && g(null).launchLockReason === GATE_COPY.noPlan);
}

// ─── 2. the candidate labels: "adds <roads>" ────────────────────────────────

{
	const primary = candidate({ route_id: 'r1', road_names: ['Strand Road', 'Eastern Metropolitan Bypass'] });
	const alt = candidate({ route_id: 'r2', road_names: ['Strand Road', 'Kidderpore Road', 'Karl Marx Sarani', 'Hastings crossing'] });
	const adds = plan.candidateAdds(alt, primary);
	ok('candidates: adds names the alternate roads the primary lacks, in order', eq(adds, ['Kidderpore Road', 'Karl Marx Sarani', 'Hastings crossing']));
	ok('candidates: the adds text shows two roads then +n', plan.addsText(adds) === 'Kidderpore Road, Karl Marx Sarani +1');
	ok('candidates: two roads render uncut', plan.addsText(['A Road', 'B Road']) === 'A Road, B Road');
	ok('candidates: a route adds nothing against itself, and with no road names nothing is invented', plan.candidateAdds(primary, primary).length === 0 && plan.candidateAdds(candidate({ road_names: undefined }), primary).length === 0);
}

// ─── 2b. the flow's provenance (the /ops legend rides the metric strip's derivation)

{
	// audit C S2 item 6: the map tile's legend says "Simulated flow" from the SAME
	// derivation as the metric strip — the feed's label wins; before it answers the
	// corridor summary's provenance stands in ('emulated' reads as 'simulated');
	// 'mixed' rides through (a partly simulated feed is still a simulated flow)
	const fp = (a, b) => (typeof events.flowProvenance === 'function' ? events.flowProvenance(a, b) : undefined);
	ok('flow: the feed label wins over the summary', fp('simulated', 'emulated') === 'simulated' && fp('live', 'emulated') === 'live');
	ok('flow: before the feed answers, an emulated summary reads as simulated', fp(null, 'emulated') === 'simulated' && fp(undefined, 'emulated') === 'simulated');
	ok('flow: mixed rides through — a partly simulated flow is still flagged', fp('mixed', null) === 'mixed' && fp(null, 'mixed') === 'mixed');
	ok('flow: nothing reported, nothing claimed', fp(null, null) === null && fp(null, undefined) === null);
}

// ─── 2c. the /ops wall reads the lanes (ops.escortsDeployed) ────────────────

{
	const laneRunning = (...a) => (typeof escortState.laneRunning === 'function' ? escortState.laneRunning(...a) : undefined);
	const lanes = (over = []) => [
		{ movementId: 'mv-live', status: 'running', proposal: null, outcomes: [] },
		{ movementId: 'mv-wait', status: 'waiting_for_gps', proposal: null, outcomes: [] },
		{ movementId: 'mv-done', status: 'completed', proposal: null, outcomes: [] },
		...over,
	];
	ok('wall lanes: a running escort is lane-live only when the lanes are deployed', laneRunning(true, lanes(), 'mv-live') === true && laneRunning(true, lanes(), 'mv-wait') === true && laneRunning(true, lanes(), 'mv-done') === false);
	ok('wall lanes: not deployed, not running (an older brain or the first read pending)', laneRunning(null, lanes(), 'mv-live') === false && laneRunning(false, lanes(), 'mv-live') === false);
	ok('wall lanes: no movement, no answer', laneRunning(true, lanes(), null) === false && laneRunning(true, lanes(), undefined) === false);
	// the wall BORROWS the shared follower, never starts it: its effect leaves
	// the follower alone (no fan-out polls beside the lifecycle's own)
	ok(
		'wall lanes: the wall block never starts the per-movement poll (it borrows the follower)',
		/if \(wall\) return;/.test(readSrc('src/lib/corridor/ConvoyCard.svelte')) && !/escortFollower\.follow\(/.test((readSrc('src/lib/corridor/ConvoyCard.svelte').match(/if \(wall\) \{[\s\S]{0,200}/) ?? [''])[0]),
	);
}

// ─── 3. the ConvoyCard's What changes = the WRITERS entry ───────────────────

{
	// a hold proposal on a live movement, exactly as the escort lanes report it
	const NOW = Date.now();
	const PROPOSAL = {
		movementId: 'mv-hold-1',
		eventId: null,
		approvalId: 'apr-unit-test-1',
		action: 'hold_position',
		kind: 'hold',
		summary: 'hold the convoy short of Strand Road (congestion 86%) until it clears · up to 180 s',
		reason: 'strategic tier unavailable',
		trigger: 'incident_detected',
		tier: 'none',
		confidence: null,
		createdAt: NOW - 30_000,
		expiresAt: NOW + 60_000,
		timeoutSec: 90,
		segmentIds: [1013],
		peakCongestion: 0.86,
		simulated: true,
		proposed: { holdSegmentIds: [1013], maxHoldSec: 180, viaRoadNames: [], viaSegmentIds: [], closuresNew: [], closuresLifted: [] },
	};
	const state = {
		lang: 'en',
		escortProposals: [PROPOSAL],
		escorts: [{ movementId: 'mv-hold-1', proposal: PROPOSAL, gpsMode: 'emulated' }],
		eventById: () => null,
		roadName: (id) => (id === 1013 ? 'Strand Road' : null),
		escortProposalText: null, // filled below: units.ts only calls it while collecting
	};
	// escortTitle uses state.escortProposalText (the store's); a fixture stand-in with the same words
	state.escortProposalText = (p) => p.summary ?? p.action;

	const collected = units.decisionUnits(state).filter((u) => u.kind === 'escort-proposal');
	ok('units: the escort unit is collected from the lanes (one per proposal, masked title)', collected.length === 1 && collected[0].id === 'apr-unit-test-1' && !collected[0].title.includes('WB'));

	const unit = collected[0];
	const entry = writers.WRITERS['escort-proposal.approve'];
	const rows = entry.changes(unit);
	// the same rows the ProposalCard inside the ConvoyCard renders (writerFor('escort-proposal','approve'))
	ok(
		"convoy: What changes = the WRITERS entry — the convoy holds short of the road (up to 180 s); route and signals unchanged",
		rows.length === 3 &&
			rows[0].object === 'Convoy' &&
			rows[0].now === 'Moving' &&
			/Holds short of .+, up to 180 s/.test(rows[0].after ?? '') &&
			rows[1].object === 'Route' &&
			rows[1].after === null &&
			rows[2].object === 'Signal plans and closures' &&
			rows[2].after === null &&
			eq(rows[0].writes, ['apr-unit-test-1']),
		JSON.stringify(rows),
	);
	// the rows are byte-identical to a fresh evaluation of the entry (deterministic, no hidden state)
	eq(rows, entry.changes(unit));
	ok('convoy: the rows are the entry\'s own output, and the unchanged list and next step come from the entry', entry.unchanged(unit).length === 1 && typeof entry.nextStep(unit) === 'string' && /countdown/.test(entry.nextStep(unit)));
	// rejecting: the proposal closes, the convoy keeps its current plan
	const rej = writers.WRITERS['escort-proposal.reject'].changes(unit);
	ok('convoy: reject — the proposal closes, the convoy keeps its plan', rej.length === 2 && rej[1].after === null && rej[0].writes?.[0] === 'apr-unit-test-1');
}

// ─── 4. the legacy approvals list: absent when proposals are reported ──────

{
	const status = (over = {}) => ({
		movementId: 'mv-1',
		eventId: null,
		status: 'running',
		iteration: null,
		position: null,
		progress: null,
		etaSec: null,
		activeDiversions: 0,
		lastDecision: null,
		startedAt: null,
		updatedAt: null,
		detail: null,
		hold: null,
		pendingApprovals: [{ approvalId: 'apr-legacy-1', action: 'activate_plan_b', reason: null, raisedAt: null, tier: null, confidence: null, segmentIds: [], detourSegmentIds: [], detourM: null, remainingM: null, simulated: false }],
		authority: null,
		proposalsReported: false,
		gpsMode: 'emulated',
		trafficSimulated: false,
		note: null,
		...over,
	});

	ok(
		'legacy: the list is ABSENT while the lanes are deployed (the proposal is authoritative)',
		eq(escortState.legacyApprovals(true, status({ proposalsReported: false }), true), []),
	);
	ok(
		'legacy: …and ABSENT when the followed document reports escort authority, whatever the lanes say',
		eq(escortState.legacyApprovals(false, status({ proposalsReported: true }), true), []),
	);
	const legacy = escortState.legacyApprovals(false, status(), true);
	ok('legacy: an older brain (no lanes, no authority) — the referred actions show, while the escort runs', legacy.length === 1 && legacy[0].approvalId === 'apr-legacy-1');
	ok('legacy: not while the escort is idle (nothing is awaiting anyone)', escortState.legacyApprovals(false, status({ status: 'completed' }), false).length === 0);
}

// ─── 5. Active events: provenance and the Test tag ──────────────────────────

{
	const ev = (over = {}) => ({
		eventId: 'e1',
		name: 'VVIP movement · Z',
		eventKind: 'protected_movement',
		protectionClass: 'Z',
		crowdClass: 'LOW',
		state: 'active',
		routeSegmentIds: [],
		phases: [],
		currentPhase: null,
		band: null,
		windowStart: null,
		windowEnd: null,
		description: null,
		source: 'live-events-api',
		...over,
	});

	ok('events: the emulated glyph text is exactly "Emulated"', events.EMULATED_TEXT === 'Emulated');
	ok('events: the rehearsal tag reads exactly "Test"', events.TEST_TEXT === 'Test');
	ok('events: an emulated row is marked emulated', events.eventProvenance(ev({ emulated: true })) === 'emulated');
	ok('events: a live row is unmarked', events.eventProvenance(ev()) === null);
	ok(
		'events: a promoted OSINT event carries its verification state',
		events.eventProvenance(ev({ sourceKind: 'osint', verificationState: 'NEWS-REPORTED' })) === 'osint' && events.eventVerification(ev({ sourceKind: 'osint', verificationState: 'NEWS-REPORTED' })) === 'NEWS-REPORTED',
	);
	ok('events: the rehearsal label comes from the metadata', events.eventTestLabel(ev({ metadata: { label: 'JOURNEY CHECK (automated)' } })) === 'JOURNEY CHECK (automated)' && events.eventTestLabel(ev()) === null);
	const rows = events.activeEventRows([ev({ eventId: 'b', state: 'planning' }), ev({ eventId: 'a', state: 'active' }), ev({ eventId: 'c', source: 'offline-fixture' })]);
	ok('events: rows are live board rows, openest first, fixtures dropped', rows.map((r) => r.eventId).join(',') === 'a,b');
}

// ─── 6. the corridor pack: EN / HI / MR complete ────────────────────────────

{
	const langs = ['en', 'hi', 'mr'];
	const resolves = (l, k) => mod.strings.t(l, k) !== k;
	ok('pack: the corridor pack registers all three languages (its keys resolve)', ['cor_tab_plan', 'cor_tab_movement', 'cor_events_test'].every((k) => langs.every((l) => resolves(l, k))));
	ok('pack: the tab keys exist in every language', ['cor_tab_plan', 'cor_tab_movement', 'cor_tab_layers'].every((k) => langs.every((l) => resolves(l, k))));
	ok('pack: the state words and the waiver exist in every language', ['cor_status_approved', 'cor_status_conditional', 'cor_status_hold', 'cor_status_no_route', 'cor_waiver', 'cor_hud_next_junction'].every((k) => langs.every((l) => resolves(l, k))));
	// audit C S3 item 11: the lazy tab's failure line is the corridor's copy, in all three
	ok('pack: the lazy tab failure line exists in every language', langs.every((l) => resolves(l, 'cor_tab_failed')));
	ok('pack: the candidate roads figure exists in every language (no "N seg" jargon)', langs.every((l) => resolves(l, 'cor_cand_roads')));
	// every EN key is covered by HI and MR (the wall.unit pack rule)
	const enKeys = Object.keys(mod.packs.languages?.en ?? {});
	const missing = (l) => enKeys.filter((k) => !(k in (mod.packs.languages?.[l] ?? {})));
	ok('pack: HI and MR cover every EN key', enKeys.length > 0 && missing('hi').length === 0 && missing('mr').length === 0, `hi: ${missing('hi').slice(0, 5)} · mr: ${missing('mr').slice(0, 5)}`);
}

// ─── 7. the rendered components (svelte/server) ─────────────────────────────
// The markup the page ships (the wall.unit.mjs pattern): ActiveEvents and the
// ConvoyCard's /ops wall block, with the stores seeded through their exports.

const { compile, compileModule } = createRequire(path.join(DECK, 'package.json'))('svelte/compiler');
/** Compiled component CSS by file (the computed-CSS colour rails read it). */
const CSS_BY_FILE = new Map();
/** Components whose graph is too heavy for the unit bundle (the canvas pulls the whole HUD). */
const STUBBED = ['GodsEyeCanvas.svelte'];
const sveltePlugin = {
	name: 'corridor-ssr',
	setup(b) {
		b.onResolve({ filter: /^\$app\// }, (args) => ({ path: args.path, namespace: 'app-stub' }));
		b.onLoad({ filter: /.*/, namespace: 'app-stub' }, () => ({
			contents: 'export const goto = () => {}; export const invalidate = () => {}; export const beforeNavigate = () => {}; export const afterNavigate = () => {};',
			loader: 'js',
		}));
		b.onLoad({ filter: /\.svelte$/ }, async (args) => {
			const name = path.basename(args.path);
			if (STUBBED.includes(name)) {
				return { contents: `export default function ${name.replace(/[^A-Za-z0-9_]/g, '_')}() {}`, loader: 'js' };
			}
			const src = readFileSync(args.path, 'utf8');
			const { js, css } = compile(src, { filename: args.path, generate: 'server', dev: false });
			if (css) CSS_BY_FILE.set(args.path, typeof css === 'string' ? css : css.code);
			return { contents: js.code, loader: 'js', resolveDir: path.dirname(args.path) };
		});
		b.onLoad({ filter: /\.svelte\.ts$/ }, async (args) => {
			const src = readFileSync(args.path, 'utf8');
			const plain = (await esbuild.transform(src, { loader: 'ts' })).code;
			const { js } = compileModule(plain, { filename: args.path, generate: 'server', dev: false });
			return { contents: js.code, loader: 'js', resolveDir: path.dirname(args.path) };
		});
	},
};
const SSR_ENTRY = `
export { render } from 'svelte/server';
export { default as ActiveEvents } from './src/lib/corridor/ActiveEvents.svelte';
export { default as ConvoyCard } from './src/lib/corridor/ConvoyCard.svelte';
export { default as PlanPanel } from './src/lib/corridor/PlanPanel.svelte';
export { default as LazyTab } from './src/lib/corridor/lazy/LazyTab.svelte';
export { default as MapTile } from './src/lib/decisions/wall/MapTile.svelte';
export * as selectionMod from './src/lib/gods-eye/entities/selection.svelte';
export * as opsMod from './src/lib/ops/store.svelte';
export * as stringsMod from './src/lib/i18n/strings';
export * as followerMod from './src/lib/ops/components/template/escort.svelte';
export * as corridorMod from './src/lib/ops/components/template/corridor.svelte';
export * as escortStateMod from './src/lib/corridor/escort-state.svelte';
`;
mkdirSync(path.dirname(OUT_SSR), { recursive: true });
let S = null;
try {
	const ssr = await esbuild.build({
		stdin: { contents: SSR_ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'corridor-ssr-entry.ts' },
		absWorkingDir: DECK,
		alias: { $lib: './src/lib' },
		bundle: true,
		format: 'esm',
		platform: 'node',
		conditions: ['svelte', 'node'],
		outfile: OUT_SSR,
		logLevel: 'silent',
		plugins: [sveltePlugin],
	});
	ok('server bundle builds (svelte/compiler, generate: server)', ssr.errors.length === 0, `${ssr.errors.length} errors`);
	S = await import(`${pathToFileURL(OUT_SSR).href}?t=${Date.now()}`);
} catch (err) {
	ok('server bundle builds (svelte/compiler, generate: server)', false, String(err?.message ?? err).slice(0, 400));
}

// (module scope: §7 and §9 both render)
const html = S ? (C, props) => S.render(C, { props }).body.replace(/<!--[\s\S]*?-->/g, '') : null;
const count = (s, re) => (s.match(re) ?? []).length;

if (S) {

	// a live emulated pursuit row and a labelled rehearsal movement, as the board carries them
	const boardEvent = (over = {}) => ({
		eventId: 'e1',
		name: 'PURSUIT — stolen MH47EM•••1 (FIR 4401/2026, Hare Street PS)',
		eventKind: 'vehicle_pursuit',
		protectionClass: null,
		crowdClass: null,
		state: 'planned',
		routeSegmentIds: [],
		phases: [],
		currentPhase: null,
		band: null,
		windowStart: null,
		windowEnd: null,
		description: null,
		source: 'live-events-api',
		...over,
	});

	{
		const opsS = S.opsMod.ops;
		const selS = S.selectionMod.selection;
		opsS.lang = 'en';
		opsS.events = [
			boardEvent(),
			boardEvent({ eventId: 'e2', name: 'VVIP movement · Z', eventKind: 'protected_movement', state: 'active', emulated: true }),
			boardEvent({ eventId: 'e3', name: 'Journey check', eventKind: 'protected_movement', state: 'planning', metadata: { label: 'JOURNEY CHECK (automated)' } }),
		];
		// the BOARD's pick differs from the workspace selection: the highlight must
		// follow the selection (the assistant's scope source), never the board's id
		opsS.selectedEventId = 'e2';
		selS.current = 'event:e1';
		selS.items = ['event:e1'];

		const out = html(S.ActiveEvents, {});
		const rowTag = (id) => (out.match(new RegExp(`<button[^>]*data-event-id="${id}"[^>]*>`, 'g')) ?? []).join(' ');
		ok('rendered events: the selected row follows the workspace selection (selection.current)', /\bselected\b/.test(rowTag('e1')), rowTag('e1'));
		ok('rendered events: the board pick alone does NOT highlight (never ops.selectedEventId)', !/\bselected\b/.test(rowTag('e2')), rowTag('e2'));
		ok('rendered events: no raw event kind reaches the page (labels, not enums)', !out.includes('vehicle_pursuit') && !out.includes('protected_movement'), out.includes('vehicle_pursuit') ? 'raw vehicle_pursuit in DOM' : '');
		ok('rendered events: no raw state word reaches the page', !/>\s*planned\s*</.test(out) && !/>\s*planning\s*</.test(out));
		ok('rendered events: the pursuit row is labelled', out.includes('Vehicle pursuit'), '');
		// audit E item 5: the display-title layer rides the row — a pursuit's raw
		// server title never reaches the page
		ok('rendered events: the pursuit title rides the display-title layer ("Pursuit of …", never the raw PURSUIT — stolen …)', out.includes('Pursuit of') && !out.includes('PURSUIT — stolen'), out.match(/class="ev-name[^<]*</)?.[0]?.slice(0, 80) ?? 'no ev-name');
		ok('rendered events: the emulated glyph text is exactly "Emulated" in the markup', /data-testid="liverail-emulated"[^>]*>.*?Emulated/s.test(out));
		ok('rendered events: the rehearsal tag reads exactly "Test" in the markup', /data-testid="liverail-test"[^>]*>[^<]*Test/.test(out));
		selS.current = null;
		selS.items = [];
		opsS.events = [];
		opsS.selectedEventId = null;
	}

	// the /ops wall block: the lanes answer (deployed, running) with an open proposal
	{
		const opsS = S.opsMod.ops;
		const NOW = Date.now();
		const PROPOSAL = {
			movementId: 'mv-wall-1',
			eventId: 'evw',
			approvalId: 'apr-wall-1',
			action: 'hold_position',
			kind: 'hold',
			summary: 'hold the convoy short of Strand Road (congestion 86%) until it clears · up to 180 s',
			reason: null,
			trigger: 'incident_detected',
			tier: 'none',
			confidence: null,
			createdAt: NOW - 30_000,
			expiresAt: NOW + 120_000,
			timeoutSec: 90,
			segmentIds: [1013],
			peakCongestion: 0.86,
			simulated: true,
			proposed: { holdSegmentIds: [1013], maxHoldSec: 180, viaRoadNames: [], viaSegmentIds: [], closuresNew: [], closuresLifted: [] },
		};
		opsS.lang = 'en';
		opsS.events = [boardEvent({ eventId: 'evw', eventKind: 'protected_movement', state: 'active', movementId: 'mv-wall-1', name: 'VVIP movement · Z', protectionClass: 'Z' })];
		opsS.selectedEventId = null;
		opsS.escortsDeployed = true;
		opsS.escorts = [{ movementId: 'mv-wall-1', eventId: 'evw', status: 'running', alive: true, officer: 'R. Mehta', gpsMode: 'emulated', trafficSimulated: true, proposal: PROPOSAL, outcomes: [], timeoutSec: 90 }];
		opsS.escortDecisions = {};
		// the shared follower is this console's read of the escort: with it, the
		// wall shows the escort's own figures and hold (audit E item 2)
		const fw = S.followerMod.escortFollower;
		fw.movementId = 'mv-wall-1';
		fw.status = {
			movementId: 'mv-wall-1', eventId: 'evw', status: 'running', iteration: 14,
			position: { lon: 88.3559, lat: 22.5577, speedKmh: 31, heading: 95 },
			progress: 0.42, etaSec: 420, activeDiversions: 0, lastDecision: null, startedAt: null, updatedAt: null, detail: null,
			hold: { segmentIds: [1013], orderedBy: 'officer R. Mehta', reason: 'queue ahead on Indira Gandhi Sarani (Red Road)', peakCongestion: 0.82, since: null, maxSec: 120 },
			pendingApprovals: [], authority: null, proposalsReported: true, gpsMode: 'emulated', trafficSimulated: true, note: null,
		};

		const out = html(S.ConvoyCard, { variant: 'wall', lang: 'en', now: NOW });
		const phase = (out.match(/data-template="convoy-hud"[^>]*data-phase="([^"]*)"/) ?? [])[1];
		ok('rendered wall: the lanes know the escort as running — the phase is escorting, never a planned shell', phase === 'escorting', `phase ${phase}`);
		// audit E item 2 / mutant 4c: the hold line renders on the WALL (the followed document's hold)
		const holdFig = (out.match(/data-testid="convoy-hud-hold-state"[^>]*>[\s\S]*?<span class="v[^"]*">([^<]*)</) ?? [])[1];
		ok('rendered wall: the key figures ride the wall block (speed, progress, ETA, hold)', ['convoy-hud-speed', 'convoy-hud-progress', 'convoy-hud-eta', 'convoy-hud-hold-state'].every((id) => out.includes(`data-testid="${id}"`)));
		ok('rendered wall: the hold line renders on the wall (the followed document reports a hold)', /data-testid="convoy-hud-hold"/.test(out) && holdFig === 'Held', `hold figure ${holdFig ?? '—'}`);
		// mutant 4d: the figures are the escort's own numbers, never hard-wired dashes
		const speedFig = (out.match(/data-testid="convoy-hud-speed"[\s\S]*?<span class="v[^"]*">([^<]*)</) ?? [])[1];
		const progressFig = (out.match(/data-testid="convoy-hud-progress"[\s\S]*?<span class="v[^"]*">([^<]*)</) ?? [])[1];
		ok('rendered wall: the figures are the escort\'s own (speed 31, progress 42%), never a dash shell', speedFig === '31' && progressFig === '42%', `speed ${speedFig} · progress ${progressFig}`);
		// audit E item 2: ONE attribution and ONE countdown on the wall — the
		// ProposalCard's own; the pinned header stays on the Movement tab only
		ok(
			'rendered wall: ONE attribution and ONE countdown (no pinned header beside the ProposalCard\'s)',
			!/data-testid="convoy-hud-proposal-tag"/.test(out) && !/class="pr-count"/.test(out) && count(out, /Expires in/g) === 1 && count(out, /data-testid="convoy-hud-proposal-decider"/g) === 1,
			`tags ${(out.match(/convoy-hud-proposal-tag/g) ?? []).length} · counts ${count(out, /Expires in/g)}`,
		);
		ok('rendered wall: the proposal names its proposer (the AI/rule attribution)', /data-testid="convoy-hud-proposal-tag"|Proposed by/.test(out));
		ok('rendered wall: the proposal carries the decider line', /data-testid="convoy-hud-proposal-decider"/.test(out));

		// the lanes ALONE (no follower document on this console): the provenance
		// tags still come from the lane (gpsMode/trafficSimulated) and the missing
		// figures say so plainly instead of a row of dashes (audit E item 2)
		fw.movementId = null;
		fw.status = null;
		const laneOnly = html(S.ConvoyCard, { variant: 'wall', lang: 'en', now: NOW });
		const phase2 = (laneOnly.match(/data-template="convoy-hud"[^>]*data-phase="([^"]*)"/) ?? [])[1];
		ok('rendered wall (lane only): still live from the lanes — phase escorting', phase2 === 'escorting', `phase ${phase2}`);
		ok(
			'rendered wall (lane only): the provenance tags come from the lane (Emulated GPS + Simulated feed)',
			/data-testid="convoy-hud-emulated"/.test(laneOnly) && /data-testid="convoy-hud-simulated"/.test(laneOnly),
		);
		ok(
			'rendered wall (lane only): no live figures says so plainly — never a row of dashes',
			/data-testid="convoy-hud-nofigures"/.test(laneOnly) && !/data-testid="convoy-hud-speed"/.test(laneOnly),
			'nofigures line present, figures grid absent',
		);

		// orchestrator make-up (audit E-WORKSPACE R2 S2): a LIVE corridor feed must not stand in for the escort's own
		// readout — without the follower the wall says so, never "Corridor average · Hold None · ETA · planned"
		S.corridorMod.corridor.row = { status: 'ok', avgSpeedKmh: 53, provenance: 'live', emulatedSegments: 0, syntheticRows: 0 };
		const liveCorr = html(S.ConvoyCard, { variant: 'wall', lang: 'en', now: NOW });
		ok(
			'rendered wall (lane only, live corridor feed): the honest no-figures line, no corridor average, no "None", no "planned"',
			/data-testid="convoy-hud-nofigures"/.test(liveCorr) && !/data-testid="convoy-hud-speed"/.test(liveCorr) && !/data-testid="convoy-hud-hold-state"/.test(liveCorr) && !/planned/i.test(liveCorr.replace(/data-phase="[^"]*"/g, '')),
			liveCorr.includes('convoy-hud-nofigures') ? 'nofigures' : 'figures shown',
		);
		S.corridorMod.corridor.row = null;

		// audit C S3 item 9: the convoy feed's provenance states ONCE — header tags only
		opsS.events = [boardEvent({ eventId: 'evm', eventKind: 'protected_movement', state: 'active', movementId: 'mv-wall-2', name: 'VVIP movement · Z', protectionClass: 'Z' })];
		opsS.escorts = [{ movementId: 'mv-wall-2', eventId: 'evm', status: 'running', alive: true, officer: 'R. Mehta', gpsMode: 'emulated', trafficSimulated: true, proposal: null, outcomes: [], timeoutSec: null }];
		opsS.escortsDeployed = false;
		fw.movementId = 'mv-wall-2';
		fw.status = { movementId: 'mv-wall-2', eventId: 'evm', status: 'running', iteration: null, position: null, progress: null, etaSec: null, activeDiversions: 0, lastDecision: null, startedAt: null, updatedAt: null, detail: null, hold: null, pendingApprovals: [], authority: null, proposalsReported: false, gpsMode: 'emulated', trafficSimulated: true, note: null };
		const mv = html(S.ConvoyCard, { variant: 'movement', lang: 'en', now: NOW });
		const n = count(mv, /Emulated GPS/g) + count(mv, /Simulated feed/g);
		fw.movementId = null;
		fw.status = null;
		opsS.escorts = [];
		opsS.escortsDeployed = null;
		ok('rendered movement card: the provenance states once (no footer copy beside the header tags)', n === 2, `${n} provenance pills in the movement card`);
		{
			// orchestrator make-up (audit E-WORKSPACE R2 S3): WITH a proposal the hosted ProposalCard and its Evidence do not
			// repeat the header's provenance — "Emulated GPS" reads ONCE in the movement card
			opsS.escortsDeployed = true;
			opsS.escorts = [{ movementId: 'mv-wall-2', eventId: 'evm', status: 'running', alive: true, officer: 'R. Mehta', gpsMode: 'emulated', trafficSimulated: true, proposal: { ...PROPOSAL, movementId: 'mv-wall-2', simulated: true }, outcomes: [], timeoutSec: 90 }];
			fw.movementId = 'mv-wall-2';
			fw.status = { movementId: 'mv-wall-2', eventId: 'evm', status: 'running', iteration: null, position: null, progress: null, etaSec: null, activeDiversions: 0, lastDecision: null, startedAt: null, updatedAt: null, detail: null, hold: null, pendingApprovals: [], authority: null, proposalsReported: true, gpsMode: 'emulated', trafficSimulated: true, note: null };
			const mvp = html(S.ConvoyCard, { variant: 'movement', lang: 'en', now: NOW });
			fw.movementId = null;
			fw.status = null;
			ok('rendered movement card WITH a proposal: "Emulated GPS" reads once', /data-testid="proposal-card"/.test(mvp) && count(mvp, /Emulated GPS/g) === 1, `${count(mvp, /Emulated GPS/g)} × Emulated GPS · proposal card ${/data-testid="proposal-card"/.test(mvp)}`);
			opsS.escorts = [];
			opsS.escortsDeployed = null;
		}
		opsS.events = [];
		opsS.escorts = [];
		opsS.escortsDeployed = null;
	}
}

// ─── 8. the audit-C/audit-E structure of the route pages ────────────────────

{
	const pageSrc = readSrc('src/routes/(deck)/+page.svelte');
	const geSrc = readSrc('src/routes/(deck)/gods-eye/+page.svelte');
	const opsSrc = readSrc('src/routes/(deck)/ops/+page.svelte');
	const frameSrc = readSrc('src/lib/workspace/components/WorkspaceFrame.svelte');
	const lazySrc = readSrc('src/lib/corridor/lazy/LazyTab.svelte');

	// audit E round 2, mutant 1a: the escort never opens a dock on its own —
	// the page never sets the Plan tab (the operator opens it from the rail)
	ok('route /: no escort auto-open of the left dock (the operator opens the Plan tab)', !/escortRunning\s*&&\s*!workspace\.docks\.left/.test(pageSrc) && !/leftTab = 'plan'/.test(pageSrc));
	// mutants 2a/2b: no unregistered 'movement' seed, and the Inbox default comes
	// from the reactive chain (units waiting → 'inbox')
	ok('route /: no unregistered rightTab=\'movement\' seed (the Inbox default comes from the reactive effect)', !/rightTab \|\|= 'movement'/.test(pageSrc) && !/rightTab = 'movement'/.test(pageSrc));
	ok('route /: with decisions waiting the reactive default is the Inbox', /units\.length \? 'inbox' : null/.test(pageSrc));
	ok('route /: the Active events card collapses below ~900 px pane width (Split view)', /const aeCompact = \$derived\(paneW < 900\)/.test(pageSrc) && /collapsible=\{aeCompact\}/.test(pageSrc));
	// audit E item 4: the collapsed card starts BELOW the canvas toolbar in Split
	ok('route /: the collapsed Active events card drops below the canvas toolbar row', /overlay:has\(\.ae-card\.compact\)\)[\s\S]{0,40}top: 52px/.test(pageSrc));
	// audit E item 3 (mutant 12a): the credits are ONE compact line — the plate
	// rule is keyed to the v2 chrome and the inner credit text never wraps into
	// a clamped scroll box (no max-height, no overflow:auto anywhere on it)
	ok(
		'route /: the Cesium credits are one compact line (logos + attribution link), never a clamped box',
		/\.page :global\(\.ge-wrap\[data-chrome='v2'\] \.ge-canvas \.cesium-viewer-bottom\)/.test(pageSrc) &&
			/cesium-viewer-bottom[\s\S]{0,900}white-space:\s*nowrap/.test(pageSrc) &&
			!/cesium-viewer-bottom[\s\S]{0,900}max-height/.test(pageSrc) &&
			!/cesium-viewer-bottom[\s\S]{0,900}overflow:\s*auto/.test(pageSrc),
	);
	// mutant 5a: the map-mode bottom dock pins to its 36 px header (no min-height sneaks in)
	{
		const m = geSrc.match(/\.ws\.map-mode \.bottom\[data-size='compact'\]\)\s*\{([^}]*)\}/);
		ok('route /gods-eye: the bottom dock collapses to its 36 px header (map mode override, no min-height)', !!m && /height:\s*36px/.test(m[1]) && !/min-height/.test(m[1]), m ? m[1].replace(/\s+/g, ' ').trim() : 'rule not found');
	}
	ok('route /gods-eye: a live replay gets its bar back (the dock grows while replaying)', /data-mode='replay'/.test(geSrc));
	// audit E round 2, mutant 1b: the card stands down through the frame's
	// empty-tab resolution (leftTabId), not the raw leftTab
	ok('route /gods-eye: the vitals card follows the resolved Info tab (leftTabId)', /const cardMounted = \$derived\(!\(leftOpen && leftTabId === 'info'\)\)/.test(geSrc));
	// mutants 6a/6b: the legend's simulated-flow item rides the metric strip's
	// derivation — 'mixed' included, never the feed alone
	ok('route /ops: the legend provenance rides the metric strip derivation (flowProvenance, mixed included)', /flowProvenance/.test(opsSrc) && /simulatedFlow=\{flowLabel === 'simulated' \|\| flowLabel === 'mixed'\}/.test(opsSrc));
	// audit E item 3 (mutant 12b): the /ops plate is one compact line, no clamp
	ok(
		'route /ops: the Cesium credits are one compact line in the tile corner, never a clamped box',
		/\.wall :global\(\.ge-wrap\[data-chrome='v2'\] \.ge-canvas \.cesium-viewer-bottom\)/.test(opsSrc) &&
			/cesium-viewer-bottom[\s\S]{0,900}white-space:\s*nowrap/.test(opsSrc) &&
			!/cesium-viewer-bottom[\s\S]{0,900}max-height/.test(opsSrc) &&
			!/cesium-viewer-bottom[\s\S]{0,900}overflow:\s*auto/.test(opsSrc),
	);
	ok('route /ops: every import is indented like the file around it', opsSrc.split('\n').every((l) => !/^import\b/.test(l)));
	// audit E item 9: the ConvoyCard's imports are indented and merged (one line for escort-state)
	{
		const ccSrc = readSrc('src/lib/corridor/ConvoyCard.svelte');
		ok('convoy card: the import block is indented like the file around it', ccSrc.split('\n').every((l) => !/^import\b/.test(l)));
		ok('convoy card: the escort-state import is merged (one line, three names)', (ccSrc.match(/import \{[^}]*\} from '\.\/escort-state\.svelte';/g) ?? []).length === 1 && /import \{ escortLifecycle, laneRunning, legacyApprovals \} from '\.\/escort-state\.svelte';/.test(ccSrc));
	}
	// audit E item 7: the dock's tab row scrolls; the hide button never gives way
	ok(
		'workspace frame: the right dock tabs scroll in their row and the hide button is pinned',
		/class="dt-row"/.test(frameSrc) && /class="dt-hide"/.test(frameSrc) && /\.dt-row \{[\s\S]{0,240}overflow-x:\s*auto/.test(frameSrc) && /\.dt-hide \{\s*flex:\s*0 0 auto;/.test(frameSrc),
	);
	// mutant 11b: the lazy failure line is the pack's copy, never a literal
	ok('lazy tab: the failure line is the pack\'s key', /data-testid="lazy-failed">\{t\(lang, 'cor_tab_failed'\)\}/.test(lazySrc));
	// the round-1 audit-C S3 layout rails on the PlanPanel (no mutants this round; kept green)
	{
		const planSrc = readSrc('src/lib/corridor/PlanPanel.svelte');
		ok(
			'plan panel: helpers are helper lines, the empty state quiet, the proposal title wraps (audit C S3)',
			!/labelInfo=\{L\('ws_officer_helper'\)\}/.test(planSrc) && !/labelInfo=\{L\('cor_plan_label_hint'\)\}/.test(planSrc) && /iconSize=\{20\}/.test(planSrc) && /pl-what[^}]*white-space:\s*normal/.test(planSrc),
		);
	}
	// mutant 11c: the failure line is translated (HI/MR are not the EN string)
	{
		const en = mod.packs.languages?.en?.cor_tab_failed;
		const hi = mod.packs.languages?.hi?.cor_tab_failed;
		const mr = mod.packs.languages?.mr?.cor_tab_failed;
		ok('pack: the lazy failure line is translated in HI and MR (never the EN string)', !!en && hi !== en && mr !== en, `hi=${hi} mr=${mr}`);
	}
}

// ─── 9. the PlanPanel and the wall legend, RENDERED + the colour rails ──────

if (S) {
	// ── rendered PlanPanel (mutants 8b, 10a, 10b, 10c) ──────────────────────
	const lc = S.escortStateMod.escortLifecycle;
	const pp = () => html(S.PlanPanel, { lang: 'en' });
	{
		const opsS = S.opsMod.ops;
		opsS.lang = 'en';
		// an approved plan with a decider pick and road names, like the brain answers
		const doc = {
			movement_id: 'mv-pp-1',
			status: 'approved',
			security_compliant: true,
			security_score: 0.9,
			primary_route: { route_id: 'r1', segment_ids: [1013], road_names: ['Strand Road', 'Eastern Metropolitan Bypass'], distance_m: 4300, estimated_time_sec: 420, route_tier: 'compliant' },
			alternate_routes: [],
			decider_pick: { route_id: 'r1', confidence: 0.93, tier: 'strategic', applied: true },
		};
		lc.doc = doc;
		lc.phase = 'planned';
		const out = pp();
		// mutant 10a: "Plan corridor" is the full-width primary (the Button's fill class)
		const planBtn = (out.match(/<button[^>]*class="[^"]*plan-btn[^"]*"[^>]*>/g) ?? []).join(' ');
		ok('rendered plan: "Plan corridor" is a full-width primary (fill class on the button)', /\bfill\b/.test(planBtn), planBtn.slice(0, 120));
		// mutant 10b: the recommended pick states itself — the pick tag keeps its
		// class and no tooltip wrapper sits around it (candidates block only: the
		// Launch/Clear controls keep their own tooltips)
		const candStart = out.indexOf('planner-candidates');
		const candEnd = out.indexOf('<div class="actions', candStart);
		const candPart = candEnd > candStart ? out.slice(candStart, candEnd) : '';
		ok('rendered plan: the recommended pick states itself (pick tag, no tooltip around it)', /class="[^"]*\bpick\b[^"]*"/.test(candPart) && !/class="tt"/.test(candPart) && !/data-ui="tooltip"/.test(candPart), candPart.slice(0, 80));
		// mutant 10c: no "N seg" jargon; the roads figure only what the plan reports
		ok('rendered plan: no "N seg" jargon (the roads figure the plan reports)', !/>[0-9]+ segs?</.test(out) && /2 roads</.test(out));
		// mutant 8b: NO ROUTE is a fact in ink — the status tag carries no danger intent
		lc.doc = { ...doc, movement_id: 'mv-pp-2', status: 'no_route', primary_route: null, alternate_routes: [], overall_reasoning: 'no corridor road connects the pair within the class floor' };
		const noRoute = pp();
		const statusTag = (noRoute.match(/<[^>]*data-testid="planner-status"[^>]*>/g) ?? []).join(' ');
		ok('rendered plan: NO ROUTE is neutral ink (no danger intent on the status tag)', !!statusTag && !/i-danger/.test(statusTag) && /data-intent="none"/.test(statusTag), statusTag.slice(0, 120));
		lc.doc = null;
		lc.phase = 'idle';
	}

	// ── rendered MapTile legend (mutants 6a/6b) ─────────────────────────────
	{
		const withSim = html(S.MapTile, { lang: 'en', simulatedFlow: true, focusUrn: null });
		const withoutSim = html(S.MapTile, { lang: 'en', simulatedFlow: false, focusUrn: null });
		const label = S.stringsMod.t('en', 'wall_legend_simulated');
		ok('rendered legend: the simulated-flow item shows when the derivation flags it', label !== 'wall_legend_simulated' && withSim.includes(label), label);
		ok('rendered legend: the item is the prop\'s alone (absent when the derivation says nothing)', !withoutSim.includes(label));
	}

	// ── the colour rails in the components' own compiled CSS (mutants 8a-8e) ─
	{
		const cssOf = (file) => CSS_BY_FILE.get(path.join(DECK, file)) ?? '';
		const rule = (css, sel) => {
			const m = css.match(new RegExp(`[^{}]*${sel}[^{}]*\\{([^}]*)\\}`));
			return m ? m[1] : null;
		};
		const bad = (body) => /var\(--v-(warning|danger)/.test(body ?? '');
		const convoyCss = cssOf('src/lib/corridor/ConvoyCard.svelte');
		const eventsCss = cssOf('src/lib/corridor/ActiveEvents.svelte');
		ok('colour rails: the Test tag is neutral ink (never warning) — computed CSS', !bad(rule(eventsCss, '\\.ev-test')), rule(eventsCss, '\\.ev-test')?.replace(/\s+/g, ' ') ?? 'rule not found');
		ok('colour rails: the protection class is neutral ink — computed CSS', !bad(rule(convoyCss, '\\.cls')), rule(convoyCss, '\\.cls')?.replace(/\s+/g, ' ') ?? 'rule not found');
		ok('colour rails: a countdown under 15 s stays ink (never warning/danger) — computed CSS', !bad(rule(convoyCss, '\\.pr-count\\.urgent')), rule(convoyCss, '\\.pr-count\\.urgent')?.replace(/\s+/g, ' ') ?? 'rule not found');
		ok('colour rails: refusals are neutral ink (never danger) — computed CSS', !bad(rule(convoyCss, '\\.ap-out\\.err')), rule(convoyCss, '\\.ap-out\\.err')?.replace(/\s+/g, ' ') ?? 'rule not found');
		// the PlanPanel's own countdown stays ink too
		const planCss = cssOf('src/lib/corridor/PlanPanel.svelte');
		ok('colour rails: the proposal link countdown stays ink — computed CSS', !bad(rule(planCss, '\\.pl-left\\.urgent')), rule(planCss, '\\.pl-left\\.urgent')?.replace(/\s+/g, ' ') ?? 'rule not found');
	}
}

/** A deck source file, read from this repo (the structure asserts above). */
function readSrc(rel) {
	return readFileSync(path.join(DECK, rel), 'utf8');
}

// ─── done ───────────────────────────────────────────────────────────────────

if (failures) {
	console.error(`corridor.unit: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('corridor.unit: all green');
