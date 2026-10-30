/**
 * Decisions core unit test (UI-S5A; SPEC §5.3, §5.4, §7.3, §9; plan X6, X9,
 * X10, X21, R27).
 *
 *   node tests/decisions.unit.mjs
 *
 * esbuild bundles the REAL modules — decisions/{units, writers, homes, live,
 * register, cards/index, cards/meta, sections/{lifecycle.svelte, follow.svelte,
 * links}}, the ops
 * store and client, ops/format, workspace/{mask, registry, selectors} and the
 * decisions pack — with `$lib` aliased to src/lib; `$state` is an identity
 * stub so the rune classes run as plain classes, and every `.svelte`
 * component import is replaced by a stub (no compiler in this test). A
 * fetch stub answers the GETs from a fixture world and RECORDS every POST,
 * so each writer is held to the client call it makes.
 *
 * Asserts (iterating the tables, so a kind added later — the DSS's `dss` —
 * is covered by the same checks):
 *   - units from fixtures: two pending R_STOLEN_SIGHTING rows of one vehicle
 *     are ONE unit (data-count 2, data-rec-ids); a stolen vehicle's pursuit
 *     opening is folded into its unit, never a second one; pursuit, e-challan,
 *     escort and 108 units and their data hooks; sorted by deadline, then
 *     severity; titles masked; no person field anywhere in a unit;
 *   - homes: every kind has exactly one home per route; every unit kind has
 *     a home; the decisions provider adds no decision action to a link
 *     surface (no second Approve); link targets carry no mark;
 *   - WRITERS: each kind's What-changes rows equal the client calls its run()
 *     makes (the ids POSTed = the ids its changed rows name): Authorise
 *     touches ONE recommendation (the newest); Dismiss all rejects each under
 *     one reason and stops at the first failure; Open pursuit is separate and
 *     refuses no-anchor and no-approved-recommendation before any request; an
 *     e-challan on a stolen vehicle offers Reject only; a 409 is kept verbatim
 *     and never retried; escort, 108, Request unit; no officer → nothing sent;
 *   - a double click sends ONE POST;
 *   - ops.pursuitFor and the plan following the vehicle — with TWO open
 *     pursuits the most recent intent wins: selecting vehicle B loads and
 *     polls B's plan while pursuit A is the board's selection, and a later
 *     board pick of A replaces it (the interception-plan GETs are recorded);
 *   - liveStripFeed: the soonest decision by deadline, the pursuit's mark
 *     masked, null when nothing is live; interrupts never muted by watches;
 *   - register(): the inbox tab (/ and /gods-eye only), the Pursuit section
 *     for vehicle and event, the decision link section (recommendation,
 *     vehicle, event, dispatch, junction: a stolen vehicle's sighting opened
 *     on its own links to its ONE unit), the lifecycle actions (the cancel
 *     arm clears after ARM_MS), the units source counted by
 *     selectors.decisionUnits(); idempotent (R27);
 *   - ops/format.ts masks marks by the workspace rule (lockstep with
 *     workspace/mask.ts) and clipText never cuts a mark;
 *   - the decisions pack: EN/HI/MR carry the same keys, every key the
 *     source uses exists.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const OUT = path.join(HERE, 'artifacts', 'decisions-bundle.mjs');

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
export * as live from './src/lib/decisions/live';
export * as reg from './src/lib/decisions/register';
export * as cards from './src/lib/decisions/cards/index';
export * as meta from './src/lib/decisions/cards/meta';
export * as lifecycle from './src/lib/decisions/sections/lifecycle.svelte';
export * as follow from './src/lib/decisions/sections/follow.svelte';
export * as links from './src/lib/decisions/sections/links';
export * as opsStore from './src/lib/ops/store.svelte';
export * as format from './src/lib/ops/format';
export * as mask from './src/lib/workspace/mask';
export * as registry from './src/lib/workspace/registry';
export * as selectors from './src/lib/workspace/selectors';
export * as objects from './src/lib/workspace/objects';
export * as ws from './src/lib/workspace/workspace.svelte';
export * as packs from './src/lib/i18n/packs.decisions';
export * as strings from './src/lib/i18n/strings';
export * as wallMetrics from './src/lib/decisions/wall/metrics';
export * as fmt from './src/lib/ui/format/format';
export * as cityReg from './src/lib/gods-eye/entities/registry.svelte';
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
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'decisions-entry.ts' },
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

// Svelte 5 runes are compiler macros: identity stubs run the stores as plain classes.
globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });

// ─── the fixture world and the fetch stub (every POST recorded) ─────────────

const NOW = Date.now();
const iso = (msAgo) => new Date(NOW - msAgo).toISOString();
const id = (n) => `5a1e0000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const V = (n) => id(100 + n);
const R = (n) => id(200 + n);
const D = (n) => id(300 + n);
const P = id(401);
const P_OLD = id(402);
const PM = id(403);
const NEWP = id(404);
const MVMT = 'mvmt-unit-01';
const OFFICER = 'Sandbox Officer';

/** Road 1013 (Strand Road) runs east-west along lat 22.5644. */
const SEGMENTS = [{ segmentId: 1013, roadName: 'Strand Road', roadClass: 'secondary', coordinates: [[88.3520, 22.5644], [88.3650, 22.5644]] }];
const ON_ROAD = [88.3579, 22.5645];
const OFF_ROAD = [88.47, 22.6882];

const sight = (at, msAgo = 180_000) => (at ? { t: iso(msAgo), lon: at[0], lat: at[1], speedKmh: 88, heading: 78, source: 'emulated_anpr' } : null);
const WATCH = [
	{ vehicleId: V(1), plate: 'MH47EM9001', earmarkState: 'flagged', earmarkReason: 'stolen — FIR 4401/2026', lawfulBasis: 'stolen_vehicle_fir', retentionUntil: iso(-86_400_000), lastSighting: sight(ON_ROAD) },
	{ vehicleId: V(2), plate: 'MH01AB1234', earmarkState: 'flagged', earmarkReason: 'stolen — FIR 77/2026', lawfulBasis: 'stolen_vehicle_fir', retentionUntil: iso(-86_400_000), lastSighting: sight(OFF_ROAD) },
	{ vehicleId: V(3), plate: 'MH05CD5678', earmarkState: 'flagged', earmarkReason: 'stolen — FIR 81/2026', lawfulBasis: 'stolen_vehicle_fir', retentionUntil: iso(-86_400_000), lastSighting: sight(ON_ROAD) },
	{ vehicleId: V(5), plate: 'MH07GH2468', earmarkState: 'flagged', earmarkReason: 'stolen — FIR 90/2026', lawfulBasis: 'stolen_vehicle_fir', retentionUntil: iso(-86_400_000), lastSighting: sight(ON_ROAD) },
	{ vehicleId: V(6), plate: 'MH01KL7777', earmarkState: 'watch', earmarkReason: 'court warrant watch', lawfulBasis: 'court_warrant', retentionUntil: iso(-86_400_000), lastSighting: null },
	{ vehicleId: V(8), plate: 'MH01PQ8080', earmarkState: 'flagged', earmarkReason: 'stolen — FIR 120/2026', lawfulBasis: 'stolen_vehicle_fir', retentionUntil: iso(-86_400_000), lastSighting: null },
	{ vehicleId: V(10), plate: 'MH08EF4321', earmarkState: 'flagged', earmarkReason: 'stolen — FIR 133/2026', lawfulBasis: 'stolen_vehicle_fir', retentionUntil: iso(-86_400_000), lastSighting: sight(ON_ROAD) },
];

const recRow = (rid, vehicleId, plate, status, text, rule = 'R_SPD_SEGMENT', createdMsAgo = 900_000, extra = {}) => ({
	recommendation_id: rid,
	sighting_id: `${rid}-s`,
	vehicle_id: vehicleId,
	plate,
	rule_id: rule,
	recommendation: text,
	evidence: { source: 'emulated_anpr', camera_id: 'EM-CAM-03', plate, speed_kmh: 92, t: iso(createdMsAgo), ...(rule === 'R_STOLEN_SIGHTING' ? { fir_ref: '120/2026' } : {}) },
	status,
	decided_by: status === 'approved' ? 'Duty Officer R. Mehta' : null,
	decided_at: status === 'approved' ? iso(createdMsAgo - 20_000) : null,
	audit_tail: [],
	created_at: iso(createdMsAgo),
	...extra,
});

const world = {
	recs: [
		recRow(R(1), V(1), 'MH47EM9001', 'pending', 'MH47EM9001 read at 92 km/h in a 40 km/h segment'),
		recRow(R(3), V(6), 'MH01KL7777', 'pending', 'MH01KL7777 read at 78 km/h in a 40 km/h segment'),
		recRow(R(4), V(7), 'MH01RS4545', 'pending', 'MH01RS4545 read at 74 km/h in a 40 km/h segment'),
		recRow(R(5), V(5), 'MH07GH2468', 'approved', 'Stolen vehicle MH07GH2468 sighted (FIR 90/2026)', 'R_STOLEN_SIGHTING'),
		recRow(R(9), V(8), 'MH01PQ8080', 'approved', 'Stolen vehicle MH01PQ8080 sighted (FIR 120/2026)', 'R_STOLEN_SIGHTING', 2_400_000, { pursuit: { event_id: id(499), status: 'cancelled' } }),
		recRow(R(6), V(8), 'MH01PQ8080', 'pending', 'Stolen vehicle MH01PQ8080 sighted at EM-CAM-04 (FIR 120/2026)', 'R_STOLEN_SIGHTING', 300_000),
		recRow(R(7), V(8), 'MH01PQ8080', 'pending', 'Stolen vehicle MH01PQ8080 sighted at EM-CAM-05 (FIR 120/2026)', 'R_STOLEN_SIGHTING', 100_000),
		recRow(R(10), V(10), 'MH08EF4321', 'pending', 'Stolen vehicle MH08EF4321 sighted (FIR 133/2026)', 'R_STOLEN_SIGHTING', 200_000),
	],
	posts: [],
	/** Event ids whose interception plan was asked for (GET), in order. */
	planGets: [],
	/** path → {status, body}: the next POST to it is answered so. */
	failOnce: new Map(),
};

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
		let hit;
		if ((hit = u.match(/\/enforcement\/recommendations\/([^/]+)\/decision$/))) {
			const r = world.recs.find((x) => x.recommendation_id === hit[1]);
			if (r) Object.assign(r, { status: body.decision === 'approve' ? 'approved' : 'rejected', decided_by: body.officer, decided_at: new Date().toISOString() });
			return json({ status: r?.status ?? 'approved' });
		}
		if (/\/api\/v1\/events$/.test(u)) return json({ event_id: NEWP });
		if ((hit = u.match(/\/api\/v1\/events\/([^/]+)\/dispatch$/))) return json({ dispatch_id: D(9), event_id: hit[1], agency: body.agency, unit_id: body.unit_id, status: 'requested', requested_by: body.requested_by, waypoint_junction: body.waypoint_junction ?? null, audit: [] });
		if ((hit = u.match(/\/api\/v1\/dispatches\/([^/]+)\/decision$/))) return json({ dispatch_id: hit[1], agency: 'ambulance', status: body.action === 'approve' ? 'approved' : 'deferred', audit: [] });
		if (/\/escort\/approvals\/[^/]+$/.test(u)) return json({ status: body.decision === 'approve' ? 'approved' : 'rejected', action: 'hold_position' });
		return json({ detail: 'Not Found' }, 404);
	}
	if (u.startsWith('/api/v1/enforcement/recommendations?')) {
		const status = new URL(u, 'http://x').searchParams.get('status') ?? 'pending';
		return json({ recommendations: world.recs.filter((r) => r.status === status) });
	}
	if (u.startsWith('/api/v1/dispatches?')) return json({ dispatches: [] });
	let plan;
	if ((plan = u.match(/\/api\/v1\/events\/([^/?]+)\/interception-plan/))) {
		world.planGets.push(plan[1]);
		return json({ vehicle_id: null, interception_junctions: [{ junction_id: 11, junction_type: 'junction', graph_cost_sec: 70, choke_weight: 1, score: 0.123, position: [88.37, 22.5582] }], latest_sighting: null, stale: false, stale_after_sec: 600 });
	}
	return json({ detail: 'Not Found' }, 404);
};

const M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
const { units: U, writers: W, homes: H, live: LV, reg, cards, lifecycle, follow, links: LK, opsStore, format: F, mask: MK, registry: RG, selectors: SEL, objects: OBJ, ws, packs, cityReg: CR, commandBar } = M;
const { ops } = opsStore;

const postsTo = (re) => world.posts.filter((p) => re.test(p.path));
const clearPosts = () => (world.posts.length = 0);

// ─── the store's state: recommendations from the stub, the rest set as the polls would ──

function event(eventId, kind, name, state, extra = {}) {
	return {
		eventId,
		name,
		eventKind: kind,
		protectionClass: kind === 'protected_movement' ? 'Z' : 'none',
		crowdClass: 'LOW',
		state,
		status: state === 'planned' ? 'planning' : state,
		routeSegmentIds: [1013],
		phases: [{ label: 'p', startTime: iso(600_000), endTime: null, closurePolicy: null, state: 'active' }],
		currentPhase: null,
		band: null,
		windowStart: iso(600_000),
		windowEnd: null,
		description: null,
		source: 'live-events-api',
		...extra,
	};
}

const EVENTS = [
	event(P, 'vehicle_pursuit', 'PURSUIT — stolen MH47EM•••1', 'active', { metadata: { vehicleId: V(1), recommendationId: R(0), source: null, mode: null, runId: null, useCaseId: null, isReplay: null }, windowStart: iso(300_000) }),
	event(P_OLD, 'vehicle_pursuit', 'PURSUIT — stolen MH47EM•••1 (closed)', 'completed', { metadata: { vehicleId: V(1), recommendationId: R(0), source: null, mode: null, runId: null, useCaseId: null, isReplay: null }, windowStart: iso(9_000_000) }),
];

const escortLane = (expiresInMs) => ({
	movementId: MVMT,
	eventId: PM,
	status: 'escorting',
	alive: true,
	officer: null,
	gpsMode: 'emulated',
	trafficSimulated: true,
	timeoutSec: 90,
	outcomes: [],
	proposal: {
		movementId: MVMT,
		eventId: PM,
		approvalId: 'esc-unit-1',
		action: 'hold_position',
		kind: 'hold',
		summary: 'hold short of Strand Road',
		reason: null,
		trigger: 'incident_detected',
		tier: 'decider',
		confidence: 0.93,
		createdAt: NOW - 30_000,
		expiresAt: NOW + expiresInMs,
		timeoutSec: 90,
		segmentIds: [1013],
		peakCongestion: 0.86,
		simulated: true,
		proposed: { routeSource: null, segmentIds: [], tailSegmentIds: [], roadNames: [], viaSegmentIds: [], viaRoadNames: [], remainingM: null, newRemainingM: null, avoids: [], longDetour: false, closureType: null, closuresNew: [], closuresLifted: [], holdSegmentIds: [1013], maxHoldSec: 180, replan: false },
	},
});

const DISPATCHES = [
	{ dispatchId: D(1), eventId: PM, agency: 'ambulance', agencyLabel: '108 Ambulance', unitId: '108-14', waypointJunction: 5, status: 'requested', requestedBy: '108-driver', decidedBy: null, decisionNote: null, approvedAt: null, createdAt: iso(50_000), updatedAt: iso(50_000), audit: [] },
	{ dispatchId: D(2), eventId: PM, agency: 'jan_rakshak', agencyLabel: 'Civic Volunteers', unitId: 'JR-EM-02', waypointJunction: 3, status: 'requested', requestedBy: OFFICER, decidedBy: null, decisionNote: null, approvedAt: null, createdAt: iso(70_000), updatedAt: iso(70_000), audit: [] },
];

async function seed() {
	ops.setDutyOfficer(OFFICER);
	ops.watchlist = WATCH;
	ops.segmentLines = SEGMENTS;
	ops.events = EVENTS;
	ops.escorts = [escortLane(60_000)];
	ops.dispatches = DISPATCHES;
	ops.recommendationRefusals = {};
	await ops.pollRecommendations();
	await ops.pollApproved();
}
await seed();

// ─── the dss unit kind (OS-DECK-B): decision units from the city registry ───
// One osint_event and one event entity carrying the SAME props.dss: exactly
// ONE unit (an object is one decision, whatever surface carries its summary).

const DSS_NOW = Date.now();
const DSS_SUMMARY = {
	dss_id: id(602),
	state: 'proposed',
	top_coa_id: 'coa_min',
	top_coa_label: 'Driver advisory only (VMS + app push)',
	generated_at: new Date(DSS_NOW - 600_000).toISOString(),
	horizon_min: 120,
	expires_at: new Date(DSS_NOW + 6_600_000).toISOString(),
};
const osintProps = {
	label: 'Road accident · Babughat (Strand Road)',
	summary: 'Two vehicles collide near the ring road circle; [AGE] rider hurt',
	event_class: 'road_accident',
	sajag_event_kind: 'road_accident',
	verification_state: 'NEWS-REPORTED',
	credibility: 0.6,
	second_order: [],
	promoted_event_id: null,
	segment_id: null,
	junction_id: 11,
	dss: DSS_SUMMARY,
};
CR.cityRegistry.seed({
	asOf: DSS_NOW,
	entities: [
		{
			urn: `osint_event:${id(601)}`,
			kind: 'osint_event',
			id: id(601),
			label: 'Road accident · Babughat (Strand Road)',
			lon: 88.4299,
			lat: 22.5682,
			state: null,
			band: null,
			source: 'osint',
			verificationState: 'NEWS-REPORTED',
			credibility: 0.6,
			t: DSS_NOW - 1_800_000,
			ageSec: 1800,
			links: [],
			props: osintProps,
		},
		{
			urn: `event:${id(603)}`,
			kind: 'event',
			id: id(603),
			label: 'Road accident (promoted)',
			lon: 88.4299,
			lat: 22.5682,
			state: 'active',
			band: null,
			source: 'osint',
			verificationState: 'NEWS-REPORTED',
			credibility: 0.6,
			t: DSS_NOW - 60_000,
			ageSec: 60,
			links: [],
			props: { label: 'Road accident (promoted)', second_order: [], dss: DSS_SUMMARY },
		},
	],
	feeds: {},
	tookMs: 1,
});


// ─── units ──────────────────────────────────────────────────────────────────

const all = U.decisionUnits();
const byKind = (k) => all.filter((u) => u.kind === k);
const dssUnits = byKind('dss');
const dssOf = dssUnits[0];
ok('dss: a DSS carried on BOTH the osint_event and the event is counted ONCE in decisionUnits()', dssUnits.length === 1, `${dssUnits.length} dss units`);
ok('dss: id = the dss id, subject = the osint urn, deadline = expires_at', !!dssOf && dssOf.id === id(602) && dssOf.subjectUrn === `osint_event:${id(601)}` && dssOf.deadline === Date.parse(DSS_SUMMARY.expires_at), dssOf?.subjectUrn);
ok('dss: the title is the imperative "Approve a response to <label>"', !!dssOf && dssOf.title === 'Approve a response to Road accident · Babughat (Strand Road)', dssOf?.title);
const stolen = byKind('stolen-sighting');
const v8 = stolen.find((u) => u.id === V(8));
ok('units: two pending R_STOLEN_SIGHTING rows of one vehicle are ONE unit', !!v8 && stolen.filter((u) => u.id === V(8)).length === 1, `${stolen.length} stolen units`);
const v8hooks = v8 ? U.UNIT_KINDS['stolen-sighting'].dataHooks(v8) : {};
ok('units: …data-count 2 and data-rec-ids name both rows', v8hooks.count === '2' && v8hooks['rec-ids'].split(' ').sort().join(' ') === [R(6), R(7)].sort().join(' '), JSON.stringify(v8hooks));
ok('units: …the newest sighting is the one Authorise approves', v8 && U.stolenOf(v8).newest.recommendationId === R(7));
ok("units: …a spent approval (closed pursuit) never stands in for the officer's authorisation", v8 && U.stolenOf(v8).approved === null);
ok('units: …its FIR from the evidence', v8 && U.stolenOf(v8).fir === '120/2026', v8 && U.stolenOf(v8).fir);
const v10 = stolen.find((u) => u.id === V(10));
ok('units: a stolen vehicle\'s pursuit opening is step 2 of its unit (no second unit)', !!v10 && !byKind('pursuit').some((u) => u.id === V(10)) && U.stolenOf(v10).step.refusal === 'no-approved-recommendation', v10 ? JSON.stringify(U.stolenOf(v10).step.refusal) : 'no unit');
const pursuits = Object.fromEntries(byKind('pursuit').map((u) => [u.id, U.pursuitOf(u).refusal ?? '']));
ok('units: an open pursuit hides its vehicle (no pursuit unit for V1)', !(V(1) in pursuits));
ok('units: no road anchor → refusal no-anchor', pursuits[V(2)] === 'no-anchor');
ok('units: no approved sighting → refusal no-approved-recommendation', pursuits[V(3)] === 'no-approved-recommendation');
ok('units: anchored and approved → offered (no refusal)', pursuits[V(5)] === '');
const ech = Object.fromEntries(byKind('echallan').map((u) => [u.id, U.UNIT_KINDS.echallan.dataHooks(u)]));
ok('units: an e-challan on a reported-stolen vehicle carries data-stolen 1', ech[R(1)]?.stolen === '1' && ech[R(3)]?.stolen === '', JSON.stringify(ech[R(1)]));
ok('units: a 108 ambulance request is a unit; another agency\'s request is not', byKind('corridor-request').map((u) => u.id).join() === D(1));
ok('units: the escort proposal is a unit with its deadline', byKind('escort-proposal').length === 1 && byKind('escort-proposal')[0].deadline === NOW + 60_000);
const order = all.map((u) => u.kind);
ok('units: sorted by deadline, then severity (escort, 108, stolen, pursuit, e-challan)', order[0] === 'escort-proposal' && order[1] === 'corridor-request' && order.indexOf('stolen-sighting') < order.indexOf('pursuit') && order.lastIndexOf('pursuit') < order.indexOf('echallan'), order.join(' '));
ok('units: every deadline-less unit sorts after every unit with a deadline', all.findIndex((u) => u.deadline == null) > all.findLastIndex((u) => u.deadline != null));
const RAW_MARK_RE = /\b[A-Z]{2}[ -]?\d{1,2}[ -]?(?:[A-Z]{1,3}[ -]?)?\d{4}\b/;
ok('units: every unit title is masked (no raw mark)', all.every((u) => !RAW_MARK_RE.test(u.title)), all.map((u) => u.title).find((x) => RAW_MARK_RE.test(x)) ?? 'clean');
ok('units: the stolen unit\'s title is the imperative "Authorise pursuit of MH01PQ•••0"', v8?.title === 'Authorise pursuit of MH01PQ•••0', v8?.title);
const PERSON_KEY_RE = /\b(?:author|person|handle|username|byline|reporter|poster|uploader|suspect|accused|victim|owner|driver_name|face|biometric)\b|individual_/i;
const keysOf = (v, depth = 0, out = new Set()) => {
	if (depth > 6 || !v || typeof v !== 'object') return out;
	for (const [k, x] of Object.entries(v)) {
		out.add(k);
		keysOf(x, depth + 1, out);
	}
	return out;
};
const personKeys = [...keysOf(all.map((u) => u.data))].filter((k) => PERSON_KEY_RE.test(k.replace(/([A-Z])/g, '_$1').toLowerCase()));
ok('ethics: no person field in any unit (vehicles only)', personKeys.length === 0, personKeys.join(',') || 'none');
for (const [kind, spec] of Object.entries(U.UNIT_KINDS)) {
	const list = byKind(kind);
	ok(`table: ${kind} — collect/title/deadline/severity/dataHooks agree on every unit`, list.every((u) => spec.dataHooks(u).kind === kind && spec.deadline(u) === u.deadline && spec.severity(u) === u.severity && typeof spec.title(u, 'en') === 'string'), `${list.length} units`);
}

// ─── homes ──────────────────────────────────────────────────────────────────

const ROUTES = ['/', '/gods-eye', '/ops'];
const HOME_SET = new Set(['inbox', 'decisions', 'movement', 'map']);
for (const [kind, homes] of Object.entries(H.HOMES)) {
	ok(`homes: ${kind} — exactly one home per route`, eq(Object.keys(homes).sort(), [...ROUTES].sort()) && Object.values(homes).every((h) => HOME_SET.has(h)), JSON.stringify(homes));
}
ok('homes: every unit kind has its homes', Object.keys(U.UNIT_KINDS).every((k) => k in H.HOMES), Object.keys(U.UNIT_KINDS).filter((k) => !(k in H.HOMES)).join(',') || 'all');
ok('homes: escort proposals live in the movement card on / and in Decisions on /ops', H.HOMES['escort-proposal']['/'] === 'movement' && H.HOMES['escort-proposal']['/ops'] === 'decisions');
ok('homes: every other unit kind is decided in the Inbox on / and /gods-eye, in Decisions on /ops', ['stolen-sighting', 'pursuit', 'echallan', 'corridor-request'].every((k) => H.HOMES[k]['/'] === 'inbox' && H.HOMES[k]['/gods-eye'] === 'inbox' && H.HOMES[k]['/ops'] === 'decisions'));
const links = all.flatMap((u) => ROUTES.map((r) => H.homeLink(u.kind, u.id, r)));
ok('homes: homeLink gives an href and a label for every unit on every route, never a mark', links.every((l) => l.href.startsWith('/') && l.label.startsWith('Decided') && !RAW_MARK_RE.test(l.href)), links[0]?.href);
ok('homes: a hostile id gives no deep-link key', H.unitKey('echallan', '../etc/passwd') === null && H.parseUnitKey('echallan:../x') === null && H.parseUnitKey(`echallan:${R(3)}`)?.id === R(3));

// ─── register: the provider's slots (R27) ───────────────────────────────────

RG.resetRegistry();
reg.register();
const sizes1 = JSON.stringify(RG.registrySize());
reg.register();
ok('register: idempotent (a second call replaces its own entries)', JSON.stringify(RG.registrySize()) === sizes1, sizes1);
const ctx = (route) => ({ route, mode: 'workspace', live: { movement: false, pursuit: false } });
ok('register: the Inbox tab on / and /gods-eye, never on /ops', RG.rightTabsFor(ctx('/')).some((t) => t.id === 'inbox') && RG.rightTabsFor(ctx('/gods-eye')).some((t) => t.id === 'inbox') && !RG.rightTabsFor(ctx('/ops')).some((t) => t.id === 'inbox'));
ok('register: the Pursuit section for vehicle and event (id pursuit, order 10)', ['vehicle', 'event'].every((k) => RG.inspectorSectionsFor(k).some((s) => s.id === 'pursuit' && s.order === 10)));
const sel = SEL.createSelectors(() => ({ graph: () => OBJ.EMPTY_GRAPH, registry: () => [], feed: () => [], units: () => RG.unitSourceRows(), now: () => Date.now() }));
ok('register: selectors.decisionUnits() counts the units (navbar, Inbox tab, /ops metric, LiveStrip)', sel.decisionUnits().length === all.length, `${sel.decisionUnits().length} = ${all.length}`);
ok('register: each summary carries its homes from HOMES', RG.unitSourceRows().every((s) => eq(s.homes, H.HOMES[s.kind])));
const row = (kind, rid) => ({ urn: `${kind}:${rid}`, kind, id: rid, label: '', sublabel: null, icon: 'dot', state: null, stateIntent: 'none', t: null, end: null, lon: null, lat: null, source: 'live', verification: null, credibility: null, test: false, masked: false, props: {} });
const linkSurfaces = ['vehicle', 'recommendation', 'dispatch', 'junction', 'camera', 'sighting'].flatMap((k) => RG.actionsFor(row(k, V(1))));
ok('homes: the decisions provider adds no decision action to a link surface (no second Approve)', !linkSurfaces.some((a) => a.id.startsWith('decisions.')), linkSurfaces.map((a) => a.id).join(',') || 'none');
ok('register: the decision link section for recommendation, vehicle, event, dispatch and junction (id decisions.links)', LK.LINK_KINDS.every((k) => RG.inspectorSectionsFor(k).some((s) => s.id === 'decisions.links')) && eq([...LK.LINK_KINDS], ['recommendation', 'vehicle', 'event', 'dispatch', 'junction']));
{
	const stolenU = all.find((u) => u.kind === 'stolen-sighting' && U.stolenOf(u).recs.length >= 2);
	const recUrn = stolenU ? `recommendation:${U.stolenOf(stolenU).recs[1].recommendationId}` : '';
	const refd = LK.unitsReferencing(recUrn, all);
	ok("links: a stolen vehicle's pending sighting opened on its own links to its vehicle's ONE unit", !!stolenU && refd.length === 1 && refd[0] === stolenU, recUrn);
	ok('links: the unit ABOUT an object is never linked twice (the Actions tab links it)', all.every((u) => LK.unitsReferencing(u.subjectUrn, all).every((x) => x.subjectUrn !== u.subjectUrn)));
	const ech = all.find((u) => u.kind === 'echallan');
	ok('links: an e-challan links from the vehicle it would fine', !!ech && LK.unitsReferencing(`vehicle:${U.echallanOf(ech).rec.vehicleId}`, all).includes(ech));
	const sum = stolenU ? LK.summaryOf(stolenU) : null;
	ok('links: the summary carries the homes from HOMES and a masked title', !!sum && eq(sum.homes, H.HOMES['stolen-sighting']) && !RAW_MARK_RE.test(sum.title), sum?.title);
	ok('links: an unknown or empty URN links nothing', LK.unitsReferencing('', all).length === 0 && LK.unitsReferencing('recommendation:nope', all).length === 0);
}
const evActions = RG.actionsFor(row('event', P));
ok('register: the event lifecycle action (the C-F verbs only, never a decision writer)', evActions.length > 0 && evActions.filter((a) => a.id.startsWith('decisions.')).every((a) => a.id.startsWith('decisions.lifecycle.')), evActions.map((a) => a.id).join(','));
ok('lifecycle: an active event offers complete and cancel', eq(evActions.filter((a) => a.id.startsWith('decisions.')).map((a) => a.id), ['decisions.lifecycle.completed', 'decisions.lifecycle.cancelled']));
{
	const timers = [];
	const realSetTimeout = globalThis.setTimeout;
	globalThis.setTimeout = (fn, ms) => (timers.push({ fn, ms }), 0);
	const postsBefore = world.posts.length;
	const sent = await lifecycle.runLifecycle(P, 'cancelled');
	globalThis.setTimeout = realSetTimeout;
	ok('lifecycle: the first Cancel arms ("Confirm cancel"), nothing sent, a disarm timer of ARM_MS', !sent && lifecycle.lifecycleArm.eventId === P && world.posts.length === postsBefore && timers.length === 1 && timers[0].ms === lifecycle.ARM_MS);
	const armedLabel = lifecycle.lifecycleActions(row('event', P)).find((a) => a.id === 'decisions.lifecycle.cancelled')?.label;
	timers[0].fn();
	const label = lifecycle.lifecycleActions(row('event', P)).find((a) => a.id === 'decisions.lifecycle.cancelled')?.label;
	ok('lifecycle: after ARM_MS the arm clears, so the label reverts (a later click arms again, never sends)', lifecycle.lifecycleArm.eventId === null && armedLabel !== label && label === 'Cancel this event', `${armedLabel} → ${label}`);
}

// ─── WRITERS: the table, then each entry against the client call it makes ──

ok('writers: every unit kind has its actions and each action its WRITERS entry', Object.keys(U.UNIT_KINDS).every((k) => k in W.ACTIONS && [W.ACTIONS[k].primary, W.ACTIONS[k].secondary].filter(Boolean).every((a) => W.writerFor(a === 'open' ? 'pursuit' : k, a))));
ok('cards: every unit kind has its ProposalCard body', Object.keys(U.UNIT_KINDS).every((k) => typeof cards.CARD_BODIES[k] === 'function'));
for (const [key, entry] of Object.entries(W.WRITERS)) {
	const kind = key.split('.')[0];
	const u = byKind(kind)[0] ?? byKind('stolen-sighting')[0];
	let rows = [];
	try {
		rows = entry.changes(u, { eventId: P, junctionId: 11, agency: 'police' });
	} catch (e) {
		rows = [{ error: String(e) }];
	}
	ok(
		`writers: ${key} — rows are Object | Now | After (null = No change), refusals name officer-required`,
		rows.length > 0 && rows.every((r) => typeof r.object === 'string' && typeof r.now === 'string' && (r.after === null || typeof r.after === 'string')) && typeof entry.refusals['officer-required'] === 'string' && Array.isArray(entry.unchanged(u)),
		JSON.stringify(rows).slice(0, 120),
	);
}

/** The ids a writer's changed rows name (what its POSTs may touch). */
const writes = (rows) => rows.filter((r) => r.after != null).flatMap((r) => r.writes ?? []);

// Stolen · Authorise pursuit: ONE recommendation, the newest; double click = ONE POST
{
	W.resetWriterGuards();
	clearPosts();
	const w = W.WRITERS['stolen-sighting.authorise'];
	const rows = w.changes(v8);
	ok('stolen authorise: What changes touches ONE recommendation (the newest)', eq(writes(rows), [R(7)]) && rows.filter((r) => r.after != null).length === 1, JSON.stringify(rows.map((r) => [r.object, r.after])));
	const [a, b] = await Promise.all([w.run(v8, OFFICER, {}), w.run(v8, OFFICER, {})]);
	const sent = postsTo(/\/recommendations\/[^/]+\/decision$/);
	ok('stolen authorise: a double click sends ONE POST', sent.length === 1 && a.ok && b.ok, `${sent.length} POST`);
	ok('stolen authorise: …approving the newest sighting under the named officer (= the rows)', sent[0]?.path.endsWith(`/${R(7)}/decision`) && sent[0].body.decision === 'approve' && sent[0].body.officer === OFFICER && eq(sent.map((p) => p.path.split('/').at(-2)), writes(rows)));
	const late = await w.run(v8, OFFICER, {});
	ok('stolen authorise: a late third click is refused, nothing sent', !late.ok && late.refusal === 'already-decided' && postsTo(/\/decision$/).length === 1);
	const after = U.decisionUnits().find((u) => u.kind === 'stolen-sighting' && u.id === V(8));
	ok('stolen authorise: the unit stays (an earlier sighting pends) and reads "Dismiss earlier sightings"', !!after && U.stolenOf(after).approved?.recommendationId === R(7) && after.title.startsWith('Dismiss earlier sightings of'), after?.title);
}

// Stolen · Dismiss all: each pending sighting under ONE reason, stopping at the first failure
{
	W.resetWriterGuards();
	clearPosts();
	world.recs.push(
		recRow(R(11), V(3), 'MH05CD5678', 'pending', 'Stolen vehicle sighted (FIR 81/2026)', 'R_STOLEN_SIGHTING', 400_000),
		recRow(R(12), V(3), 'MH05CD5678', 'pending', 'Stolen vehicle sighted (FIR 81/2026)', 'R_STOLEN_SIGHTING', 300_000),
		recRow(R(13), V(3), 'MH05CD5678', 'pending', 'Stolen vehicle sighted (FIR 81/2026)', 'R_STOLEN_SIGHTING', 200_000),
	);
	await ops.pollRecommendations();
	const u = U.decisionUnits().find((x) => x.kind === 'stolen-sighting' && x.id === V(3));
	const w = W.WRITERS['stolen-sighting.dismiss'];
	const rows = w.changes(u);
	ok('stolen dismiss: What changes rejects every pending sighting', eq([...writes(rows)].sort(), [R(11), R(12), R(13)].sort()), JSON.stringify(writes(rows)));
	const noReason = await w.run(u, OFFICER, { note: '  ' });
	ok('stolen dismiss: refused without a reason, nothing sent', !noReason.ok && noReason.refusal === 'reason-required' && world.posts.length === 0);
	const order3 = U.stolenOf(u).recs.map((r) => r.recommendationId);
	world.failOnce.set(`/api/v1/enforcement/recommendations/${order3[1]}/decision`, { status: 500, body: { detail: 'boom' } });
	const res = await w.run(u, OFFICER, { note: 'duplicate read' });
	const sent = postsTo(/\/decision$/);
	ok('stolen dismiss: stops at the first failure (2 POSTs, not 3)', !res.ok && sent.length === 2 && res.posts === 2, `${sent.length} POST`);
	ok('stolen dismiss: …each a reject under the ONE reason', sent.every((p) => p.body.decision === 'reject' && p.body.note === 'duplicate read' && p.body.officer === OFFICER));
	ok('stolen dismiss: …every POST is one the rows name', sent.every((p) => writes(rows).includes(p.path.split('/').at(-2))));
	W.resetWriterGuards();
	clearPosts();
	await ops.pollRecommendations();
	const u2 = U.decisionUnits().find((x) => x.kind === 'stolen-sighting' && x.id === V(3));
	const ok2 = await w.run(u2, OFFICER, { note: 'duplicate read' });
	ok('stolen dismiss: a retry rejects what still pends (a reason, each once)', ok2.ok && postsTo(/\/decision$/).length === U.stolenOf(u2).recs.length);
}

// Pursuit · Open pursuit: separate; refused inline before any request
{
	W.resetWriterGuards();
	clearPosts();
	ops.events = EVENTS;
	const w = W.WRITERS['pursuit.open'];
	const pu = (vid) => U.decisionUnits().find((x) => x.kind === 'pursuit' && x.id === vid);
	const r2 = await w.run(pu(V(2)), OFFICER, {});
	const r3 = await w.run(pu(V(3)) ?? { kind: 'pursuit', id: V(3), data: {} }, OFFICER, {});
	ok('open pursuit: no road anchor → refused no-anchor, nothing sent', !r2.ok && r2.refusal === 'no-anchor' && world.posts.length === 0);
	ok('open pursuit: no approved sighting → refused no-approved-recommendation, nothing sent', !r3.ok && r3.refusal === 'no-approved-recommendation' && world.posts.length === 0, r3.refusal);
	const r10 = await w.run(v10, OFFICER, {});
	ok("open pursuit: a stolen vehicle's step 2 is refused until its sighting is approved (never on an e-challan)", !r10.ok && r10.refusal === 'no-approved-recommendation' && world.posts.length === 0);
	const u5 = pu(V(5));
	const rows = w.changes(u5);
	const r5 = await w.run(u5, OFFICER, {});
	const sent = postsTo(/\/api\/v1\/events$/);
	ok('open pursuit: an anchored, approved vehicle → ONE POST /api/v1/events', r5.ok && sent.length === 1 && world.posts.length === 1, `${world.posts.length} POST`);
	ok('open pursuit: …a vehicle_pursuit on the read\'s road, citing the approved sighting, under the officer (= the rows)', sent[0]?.body.event_kind === 'vehicle_pursuit' && sent[0].body.route_spines?.[0]?.segment_ids?.[0] === 1013 && sent[0].body.metadata?.vehicle_id === V(5) && sent[0].body.metadata?.recommendation_id === R(5) && sent[0].body.officer === OFFICER && eq(writes(rows), [V(5)]), JSON.stringify(sent[0]?.body).slice(0, 160));
	ok('open pursuit: it is not an authorisation (no recommendation decision sent)', postsTo(/\/decision$/).length === 0);
	ops.events = EVENTS;
}

// E-challan: Reject only on a stolen vehicle; the 409 verbatim, never retried
{
	W.resetWriterGuards();
	clearPosts();
	await ops.pollRecommendations();
	const e = (rid) => U.decisionUnits().find((x) => x.kind === 'echallan' && x.id === rid);
	const approve = W.WRITERS['echallan.approve'];
	const r1 = await approve.run(e(R(1)), OFFICER, {});
	ok('e-challan: Approve on a reported-stolen vehicle is refused before the wire', !r1.ok && r1.refusal === 'vehicle-stolen' && world.posts.length === 0);
	const rows = approve.changes(e(R(3)));
	const [a] = await Promise.all([approve.run(e(R(3)), OFFICER, {}), approve.run(e(R(3)), OFFICER, {})]);
	const sent = postsTo(/\/decision$/);
	ok('e-challan approve: a double click sends ONE POST, that recommendation only (= the rows)', a.ok && sent.length === 1 && sent[0].path.endsWith(`/${R(3)}/decision`) && sent[0].body.decision === 'approve' && eq(writes(rows), [R(3)]));
	clearPosts();
	const VERBATIM = 'e-challan withheld — vehicle reported stolen';
	world.failOnce.set(`/api/v1/enforcement/recommendations/${R(4)}/decision`, { status: 409, body: { detail: VERBATIM, reason: 'stolen_vehicle_fir' } });
	const u4 = e(R(4));
	const r4 = await approve.run(u4, OFFICER, {});
	ok("e-challan: the oracle's 409 is kept verbatim", !r4.ok && r4.refusal === 'refused' && r4.detail === VERBATIM && ops.recommendationRefusals[R(4)]?.detail === VERBATIM, r4.detail);
	W.resetWriterGuards();
	const again = await approve.run(u4, OFFICER, {});
	ok('e-challan: …and never retried (ONE POST in all)', !again.ok && postsTo(new RegExp(`/${R(4)}/decision$`)).length === 1);
	const refusedUnit = e(R(4));
	ok('e-challan: the refused unit carries data-refused 1 and offers Reject only', U.UNIT_KINDS.echallan.dataHooks(refusedUnit).refused === '1');
	clearPosts();
	const reject = W.WRITERS['echallan.reject'];
	const noReason = await reject.run(e(R(1)), OFFICER, {});
	const withReason = await reject.run(e(R(1)), OFFICER, { note: 'vehicle reported stolen — owner is the victim' });
	const rj = postsTo(/\/decision$/);
	ok('e-challan reject: needs a reason, then ONE POST with it as the note', !noReason.ok && noReason.refusal === 'reason-required' && withReason.ok && rj.length === 1 && rj[0].body.decision === 'reject' && rj[0].body.note === 'vehicle reported stolen — owner is the victim');
}

// Escort, 108 corridor, Request unit
{
	W.resetWriterGuards();
	clearPosts();
	ops.escorts = [escortLane(60_000)];
	const esc = U.decisionUnits().find((x) => x.kind === 'escort-proposal');
	const ew = W.WRITERS['escort-proposal.approve'];
	const rows = ew.changes(esc);
	await Promise.all([ew.run(esc, OFFICER, {}), ew.run(esc, OFFICER, {})]);
	const sent = postsTo(/\/escort\/approvals\//);
	ok('escort approve: a double click sends ONE POST {decision, officer} (= the rows)', sent.length === 1 && sent[0].path === `/api/convoy/movements/${MVMT}/escort/approvals/esc-unit-1` && eq(sent[0].body, { decision: 'approve', officer: OFFICER }) && eq(writes(rows), ['esc-unit-1']));
	ok('escort approve: the hold says where and for how long; route and signals unchanged', rows[0].after?.includes('Strand Road') && rows[0].after?.includes('180') && rows.slice(1).every((r) => r.after === null), JSON.stringify(rows.map((r) => r.after)));

	clearPosts();
	const cr = U.decisionUnits().find((x) => x.kind === 'corridor-request');
	const cw = W.WRITERS['corridor-request.approve'];
	const crows = cw.changes(cr);
	await Promise.all([cw.run(cr, OFFICER, {}), cw.run(cr, OFFICER, {})]);
	const cs = postsTo(/\/dispatches\/[^/]+\/decision$/);
	ok('108 approve: a double click sends ONE POST {action approve, officer}, that dispatch only (= the rows)', cs.length === 1 && cs[0].path.endsWith(`/${D(1)}/decision`) && cs[0].body.action === 'approve' && cs[0].body.officer === OFFICER && eq(writes(crows), [D(1)]));
	W.resetWriterGuards();
	clearPosts();
	await W.WRITERS['corridor-request.defer'].run(cr, OFFICER, { note: 'second unit en route' });
	const ds = postsTo(/\/decision$/);
	ok('108 defer: ONE POST {action defer} with the reason as the note', ds.length === 1 && ds[0].body.action === 'defer' && ds[0].body.note === 'second unit en route');

	clearPosts();
	const rq = W.WRITERS['pursuit.request-unit'];
	const pursuitUnit = { kind: 'pursuit', id: V(1), subjectUrn: `event:${P}`, title: '', deadline: null, severity: 2, data: {} };
	const rqRows = rq.changes(pursuitUnit, { eventId: P, junctionId: 11, junctionName: 'Moulali', agency: 'Police' });
	await Promise.all([rq.run(pursuitUnit, OFFICER, { eventId: P, junctionId: 11, agency: 'police', unitId: 'PCR-EM-01' }), rq.run(pursuitUnit, OFFICER, { eventId: P, junctionId: 11, agency: 'police', unitId: 'PCR-EM-01' })]);
	const rs = postsTo(/\/events\/[^/]+\/dispatch$/);
	ok('request unit: ONE dispatch REQUEST on the pursuit event with the choke as the waypoint (= the rows)', rs.length === 1 && rs[0].path === `/api/v1/events/${P}/dispatch` && rs[0].body.waypoint_junction === 11 && rs[0].body.agency === 'police' && rs[0].body.requested_by === OFFICER && eq(writes(rqRows), [P]));
	clearPosts();
	W.resetWriterGuards();
	const closed = await rq.run(pursuitUnit, OFFICER, { eventId: P_OLD, junctionId: 11, agency: 'police', unitId: 'PCR-EM-01' });
	ok('request unit: refused on a closed pursuit, nothing sent', !closed.ok && closed.refusal === 'event-closed' && world.posts.length === 0);
}

// No officer named: every writer refuses before the wire (ethics rule 6)
{
	W.resetWriterGuards();
	clearPosts();
	ops.setDutyOfficer('');
	ops.events = EVENTS;
	ops.escorts = [escortLane(60_000)];
	await ops.pollRecommendations();
	const results = [];
	for (const [key, entry] of Object.entries(W.WRITERS)) {
		const kind = key.split('.')[0];
		const u = U.decisionUnits().find((x) => x.kind === kind && !(kind === 'pursuit' && U.pursuitOf(x).refusal)) ?? (kind === 'pursuit' ? { kind: 'pursuit', id: V(5), subjectUrn: `event:${P}`, title: '', deadline: null, severity: 2, data: {} } : null);
		if (!u) continue;
		results.push([key, (await entry.run(u, '', { note: 'a reason', eventId: P, junctionId: 11, agency: 'police', unitId: 'PCR-EM-01' })).refusal]);
	}
	ok('ethics: with no named officer every writer refuses (officer-required or an earlier refusal), nothing sent', world.posts.length === 0 && results.every(([, r]) => typeof r === 'string' && r.length > 0), JSON.stringify(results));
	ok('ethics: …and the reason given is officer-required wherever no other rule refused first', results.filter(([k]) => !['echallan.approve', 'pursuit.open'].includes(k)).every(([, r]) => r === 'officer-required'), JSON.stringify(results));
	ops.setDutyOfficer(OFFICER);
	ops.events = EVENTS;
}

// ─── pursuitFor and the plan following the vehicle ──────────────────────────

ops.events = EVENTS;
ok('pursuitFor: the OPEN vehicle_pursuit whose metadata names the vehicle', ops.pursuitFor(V(1))?.eventId === P);
ok('pursuitFor: a closed pursuit never counts; no pursuit → null; empty id → null', ops.pursuitFor(V(5)) === null && ops.pursuitFor(null) === null && ops.pursuitFor('') === null);
ops.selectedEventId = null;
ops.followVehicle(V(1));
ok("follow: selecting the vehicle follows its open pursuit's plan (planEventId)", ops.followedVehicleId === V(1) && ops.planEventId === P);
ops.followVehicle('../hostile id');
ok('follow: a hostile id is ignored (nothing followed)', ops.followedVehicleId === null && ops.planEventId === null);
ops.followVehicle(V(1));
ops.selectedEventId = P;
ok('follow: the selected pursuit event is the plan as well (same event)', ops.planEventId === P);
ops.selectedEventId = null;
ops.followVehicle(null);
ok('follow: selecting anything else stops following', ops.planEventId === null);
{
	// Two open pursuits: A (the board's automatic pick) and B. Selecting vehicle B shows B's plan.
	const PA = P;
	const PB = id(405);
	const pursuitB = event(PB, 'vehicle_pursuit', 'PURSUIT — stolen MH01PQ•••0', 'active', { metadata: { vehicleId: V(8), recommendationId: R(9), source: null, mode: null, runId: null, useCaseId: null, isReplay: null }, windowStart: iso(120_000) });
	ops.events = [...EVENTS, pursuitB];
	ops.selectedEventId = PA;
	world.planGets.length = 0;
	ops.followVehicle(V(8));
	ok('follow (two pursuits): pursuitFor(B) is B; selecting vehicle B makes B the plan although A is the selected event', ops.pursuitFor(V(8))?.eventId === PB && ops.selectedEventId === PA && ops.planEventId === PB);
	await new Promise((r) => setTimeout(r, 0));
	await ops.pollInterception();
	ok("follow (two pursuits): B's plan is the one loaded and polled (ops.interception follows B)", world.planGets.length >= 1 && world.planGets.every((e) => e === PB) && ops.interception?.eventId === PB, `${world.planGets.join(',')} → ${ops.interception?.eventId}`);
	ok('follow (two pursuits): the choke carries its hold cost (score × 100)', ops.interception?.chokes[0]?.score === 0.123 && ops.interception?.chokes[0]?.chokeWeight === 1);
	world.planGets.length = 0;
	ops.selectEvent(PA);
	ok('follow (two pursuits): picking pursuit A on the board afterwards stops following B (the most recent intent wins)', ops.followedVehicleId === null && ops.planEventId === PA);
	await new Promise((r) => setTimeout(r, 0));
	ok("follow (two pursuits): …and A's plan replaces B's", world.planGets.length >= 1 && world.planGets.every((e) => e === PA) && ops.interception?.eventId === PA, `${world.planGets.join(',')} → ${ops.interception?.eventId}`);
	ops.followVehicle(V(8));
	ok('follow (two pursuits): selecting vehicle B again follows B again', ops.planEventId === PB);
	ops.followVehicle(V(5));
	ok('follow (two pursuits): a vehicle with no open pursuit falls back to the selected pursuit (A)', ops.planEventId === PA);
	ops.followVehicle(null);
	ops.selectedEventId = null;
	ops.events = EVENTS;
}
ok('follow: the selection sync reads a vehicle URN only', follow.followedVehicleOf(`vehicle:${V(1)}`) === V(1) && follow.followedVehicleOf(`event:${P}`) === null && follow.followedVehicleOf('vehicle:../x') === null);

// ─── liveStripFeed (X21) and interrupts (§7.3) ──────────────────────────────

{
	const t0 = Date.now();
	const mv = event(PM, 'protected_movement', 'Z protected movement', 'active', { movementId: MVMT });
	ops.events = [...EVENTS, mv];
	ops.escorts = [escortLane(45_000)];
	ops.dispatches = DISPATCHES;
	const feed = LV.liveStripFeed({ route: '/', now: t0 });
	ok('live: a movement and a pursuit are live → a feed', !!feed && !!feed.movement && feed.pursuits.length === 1);
	ok('live: the movement reads "Protected movement · Z"', feed?.movement?.label === 'Protected movement · Z', feed?.movement?.label);
	ok("live: the pursuit's mark is ALREADY masked", feed?.pursuits[0]?.plateMasked === 'MH47EM•••1' && !RAW_MARK_RE.test(JSON.stringify(feed?.pursuits)), feed?.pursuits[0]?.plateMasked);
	ok('live: the soonest decision is the earliest deadline (the escort, before the 108 golden hour)', feed?.soonest?.deadlineMs === NOW + 45_000, feed?.soonest?.title);
	ops.escorts = [];
	const feed2 = LV.liveStripFeed({ route: '/', now: t0 });
	ok('live: …then the next deadline (the 108 request\'s golden hour)', feed2?.soonest?.deadlineMs === Date.parse(DISPATCHES[0].createdAt) + U.GOLDEN_HOUR_MS);
	ops.cityBand = { band: 'RED', since: null, subjects: null, simulatedFeed: null, stale: false, staleSince: null, staleReason: null };
	const withBand = LV.liveStripFeed({ route: '/', now: t0 });
	ok('live: band RED during a movement is an interrupt', withBand?.interrupts.some((i) => i.kind === 'band' && i.band === 'RED'));
	const before = JSON.stringify(withBand?.interrupts.map((i) => [i.kind, i.text]));
	ws.workspace.addWatch({ title: 'Strand Road events', subjectUrn: null, filters: [{ id: 'w1', field: 'kind', values: ['event'], label: 'Events' }] });
	ws.workspace.addWatch({ title: 'MH47EM•••1', subjectUrn: `vehicle:${V(1)}`, filters: [] });
	const afterWatch = JSON.stringify(LV.liveStripFeed({ route: '/', now: t0 })?.interrupts.map((i) => [i.kind, i.text]));
	ok('live: watches never mute an interrupt', before === afterWatch && withBand.interrupts.length > 0, afterWatch);
	ops.events = EVENTS.filter((e) => e.eventId === P);
	ok('live: no movement → no interrupts (a pursuit alone keeps the strip)', LV.liveStripFeed({ route: '/', now: t0 })?.interrupts.length === 0);
	ops.events = [];
	ok('live: nothing live → no feed (null)', LV.liveStripFeed({ route: '/', now: t0 }) === null);
	ops.cityBand = null;
	ops.events = EVENTS;
	ops.escorts = [escortLane(60_000)];
}

// ─── the mask rule (ops/format.ts ↔ workspace/mask.ts, lockstep) ────────────

const CORPUS = [
	'MH47EM9001',
	'mh47em9001',
	'Mh 47 Em 9001',
	'MH-47-EM-9001',
	'MH.47.EM.9001',
	'MH/47/EM/9001',
	'MH_47_EM_9001',
	'PURSUIT — stolen MH47EM9001 (FIR 4401/2026, Hare Street PS)',
	'decider: hold MH47EM9001 at Howrah Bridge, Kolkata end',
	'As of 24 Oct 2026',
	'AS 24 Oct 2026',
	'MH 01 MAY 1234',
	'DL8SEP1234',
	'event 5a1e0000-0000-4000-8000-0000000000ab-1234',
	'XX12AB1234',
	'no mark here',
];
const mism = CORPUS.filter((s) => F.maskPlatesInText(s) !== MK.maskMarks(s));
ok('mask: ops/format.ts masks by the workspace rule (any case, . - / _ separators, real state codes, dates and UUIDs held out)', mism.length === 0, mism.join(' | ') || `${CORPUS.length} strings agree`);
ok('mask: a lower-case mark is masked on the wall too', F.maskPlatesInText('mh47em9001') === 'mh47em•••1' && F.maskPlate('MH47EM9001') === 'MH47EM•••1');
const clipped = ['seen mh 47 em 9001 near Moulali', 'hold MH-47-EM-9001 at the junction'].map((s) => F.clipText(s, 12));
ok('mask: clipText never cuts inside a mark (any spelling)', clipped.every((c) => !/\d{1,3}$/.test(c) || MK.hasRawMark(c) || F.maskPlatesInText(c) !== c), JSON.stringify(clipped));
const fmtSrc = readFileSync(path.join(DECK, 'src/lib/ops/format.ts'), 'utf8');
const maskSrc = readFileSync(path.join(DECK, 'src/lib/workspace/mask.ts'), 'utf8');
ok('mask: format.ts mirrors mask.ts\'s separator class and state codes (lockstep)', fmtSrc.includes("const SEP = '[\\\\s.\\\\-/_]{0,3}';") && maskSrc.includes("const SEP = '[\\\\s.\\\\-/_]{0,3}';") && fmtSrc.includes('STATE_CODES'));

// ─── the decisions pack ─────────────────────────────────────────────────────

const P_EN = Object.keys(packs.DECISIONS_PACKS.en).sort();
ok('pack: EN, HI and MR carry the same keys', eq(P_EN, Object.keys(packs.DECISIONS_PACKS.hi).sort()) && eq(P_EN, Object.keys(packs.DECISIONS_PACKS.mr).sort()), `${P_EN.length} keys`);
const walk = (dir) => readdirSync(dir).flatMap((f) => (statSync(path.join(dir, f)).isDirectory() ? walk(path.join(dir, f)) : [path.join(dir, f)]));
const SRC_FILES = [...walk(path.join(DECK, 'src/lib/decisions')), path.join(DECK, 'src/lib/ops/components/DecisionQueue.svelte')];
const used = new Set();
for (const f of SRC_FILES) for (const m of readFileSync(f, 'utf8').matchAll(/'(dec_[a-z0-9_]+)'/g)) used.add(m[1]);
const DYN = {
	dec_basis_: ['heading', 'oneway', 'dead_end', 'unknown'],
	dec_empty_: ['approved', 'rejected', 'expired'],
	dec_home_: ['inbox', 'decisions', 'movement', 'map'],
	dec_life_: ['approved', 'active', 'completed', 'cancelled'],
	dec_pursuit_state_: ['planned', 'active', 'completed', 'cancelled'],
	dec_btn_: ['reject', 'defer', 'dismiss'],
	dec_band_: ['red', 'black'],
};
for (const [pre, list] of Object.entries(DYN)) for (const x of list) used.add(`${pre}${x}`);
for (const verb of ['authorise_pursuit', 'dismiss_pursuit', 'open_pursuit', 'approve_echallan', 'reject_echallan', 'approve_escort', 'reject_escort', 'approve_corridor', 'defer_corridor']) used.add(`dec_done_${verb}`);
const missing = [...used].filter((k) => !P_EN.includes(k));
ok('pack: every key the decisions source uses exists (EN)', missing.length === 0, missing.join(',') || `${used.size} keys`);

// ─── the per-kind reason copy and the metric's soonest kind (FIX-E-DSSCARD items 8, 10) ──

{
	const S = M.strings;
	ok('reason copy: the dss hint names reject AND defer, with its own placeholder (per-kind copy)', S.t('en', 'dec_reason_info_dss') === '(needed to reject or defer; sent with the decision)' && S.t('en', 'dec_reason_placeholder_dss') === 'e.g. awaiting the official confirmation', S.t('en', 'dec_reason_info_dss'));
	ok('reason copy: carried in HI and MR', S.t('hi', 'dec_reason_info_dss').length > 8 && S.t('mr', 'dec_reason_info_dss').length > 8 && S.t('hi', 'dec_reason_info_dss') !== S.t('en', 'dec_reason_info_dss'), S.t('hi', 'dec_reason_info_dss'));

	const escortU = byKind('escort-proposal')[0];
	const corridorU = byKind('corridor-request')[0];
	const input = (over = {}) => ({
		lang: 'en',
		now: NOW,
		active: 1,
		open: 2,
		history: 3,
		units: all.length,
		soonestDeadline: null,
		oldestWaiting: null,
		dispatched: 1,
		dispatchesClosed: 0,
		ambulance: 1,
		ambulanceClosed: 0,
		speedKmh: null,
		speedSource: null,
		speedSamples: [],
		roads: null,
		congested: null,
		critical: null,
		reads24: 0,
		readVehicles: 0,
		lastRead: null,
		readBins: new Array(24).fill(0),
		anomalies: 0,
		...over,
	});
	const subOf = (over) => M.wallMetrics.metricCells(input(over))[1].sub;
	// the DSS unit (seeded above) is the soonest decision → its REAL kind is named, not the escort
	const dssSub = subOf({ soonestDeadline: dssOf?.deadline, now: DSS_NOW });
	ok('metric: the soonest decision-support response is named as such, never "Escort proposal"', typeof dssSub === 'string' && dssSub.startsWith('Response expires in ') && dssSub.length <= 32 && dssSub === `Response expires in ${M.fmt.fmtCountdown((dssOf?.deadline - DSS_NOW) / 1000)}`, dssSub);
	ok('metric: the escort sentence keeps the pinned wall copy', escortU && subOf({ soonestDeadline: escortU.deadline, now: NOW }) === `Escort proposal expires in ${M.fmt.fmtCountdown((escortU.deadline - NOW) / 1000)}`, subOf({ soonestDeadline: escortU.deadline, now: NOW }));
	ok('metric: a 108 decision is named as such', corridorU && subOf({ soonestDeadline: corridorU.deadline, now: NOW }) === `Ambulance (108) decision expires in ${M.fmt.fmtCountdown((corridorU.deadline - NOW) / 1000)}`, subOf({ soonestDeadline: corridorU.deadline, now: NOW }));
	ok('metric: a deadline with no matching unit keeps the legacy escort sentence (the wall contract)', subOf({ soonestDeadline: NOW + 47_000 }) === 'Escort proposal expires in 0:47', subOf({ soonestDeadline: NOW + 47_000 }));
	ok('metric: the DSS sentence is carried in HI', subOf({ lang: 'hi', soonestDeadline: dssOf?.deadline, now: DSS_NOW }) === `${S.t('hi', 'dec_kind_dss')} ${M.fmt.fmtCountdown((dssOf?.deadline - DSS_NOW) / 1000)} में समाप्त`, subOf({ lang: 'hi', soonestDeadline: dssOf?.deadline, now: DSS_NOW }));
	// fix round 2: the page may NAME the soonest kind (soonestKind) — it wins over the ±1 s lookup,
	// which no longer has to match anything
	ok('metric: an explicit soonestKind names the kind even when no unit matches the deadline', subOf({ soonestDeadline: NOW + 47_000, soonestKind: 'dss' }) === `Response expires in 0:47` && subOf({ soonestDeadline: NOW + 47_000, soonestKind: 'corridor-request' }) === `Ambulance (108) decision expires in 0:47` && subOf({ soonestDeadline: NOW + 47_000, soonestKind: 'escort-proposal' }) === 'Escort proposal expires in 0:47', subOf({ soonestDeadline: NOW + 47_000, soonestKind: 'dss' }));
	ok('metric: a named stolen sighting is not folded into the escort sentence', subOf({ soonestDeadline: NOW + 47_000, soonestKind: 'stolen-sighting' }) === `${S.kindLabel('en', 'stolen-sighting')} expires in 0:47`, subOf({ soonestDeadline: NOW + 47_000, soonestKind: 'stolen-sighting' }));
}

// ─── FIX-H-DECK ─────────────────────────────────────────────────────────────

// F-26: a stolen vehicle's e-challan is withheld — its meta line never reads the oracle's "e-challan recommended"
{
	const S = M.strings;
	// a fresh speeding e-challan on the stolen V1 (its FIR is on the watchlist) and one on an ordinary vehicle
	const tpl = ops.recommendations.find((r) => r.ruleId === 'R_SPD_SEGMENT') ?? ops.recommendations[0];
	ops.recommendations = [
		...ops.recommendations,
		{ ...tpl, recommendationId: id(901), vehicleId: V(1), plate: 'MH47EM9001', ruleId: 'R_SPD_SEGMENT', status: 'pending', recommendation: 'e-challan recommended: MH47EM9001 read at 92 km/h', decidedBy: null, decidedAt: null },
		{ ...tpl, recommendationId: id(902), vehicleId: V(7), plate: 'MH01RS4545', ruleId: 'R_SPD_SEGMENT', status: 'pending', recommendation: 'e-challan recommended: MH01RS4545 read at 74 km/h', decidedBy: null, decidedAt: null },
	];
	const stolenEch = U.decisionUnits().find((u) => u.kind === 'echallan' && u.id === id(901));
	const plainEch = U.decisionUnits().find((u) => u.kind === 'echallan' && u.id === id(902));
	const m = stolenEch ? M.meta.rowMeta(stolenEch, 'en', NOW) : '';
	ok(
		'F-26: the withheld (stolen) e-challan\'s meta line says it is withheld, not "recommended", under its "Reject" title',
		!!stolenEch && /^Reject e-challan/.test(U.unitTitle(stolenEch, 'en')) && !/recommended/i.test(m) && m === S.t('en', 'dec_meta_echallan_stolen') && M.meta.rowMeta(stolenEch, 'hi', NOW) === S.t('hi', 'dec_meta_echallan_stolen'),
		`${stolenEch ? U.unitTitle(stolenEch, 'en') : 'no stolen e-challan'} · ${m}`,
	);
	ok('F-26: an ordinary e-challan keeps the oracle\'s proposal text', !!plainEch && M.meta.rowMeta(plainEch, 'en', NOW).length > 0 && M.meta.rowMeta(plainEch, 'en', NOW) !== S.t('en', 'dec_meta_echallan_stolen'));
}

// F-28: a refused request / decision leaves NO local "requested" / "approved" decision row
{
	ops.setDutyOfficer(OFFICER);
	const local = () => ops['localAudit'];
	const decisionsFor = (re) => local().filter((a) => a.level === 'decision' && re.test(a.text));
	const reqBefore = decisionsFor(/requested/).length;
	world.failOnce.set(`/api/v1/events/${P}/dispatch`, { status: 503, body: { detail: 'oracle unavailable' } });
	const okReq = await ops.requestDispatchUnit(P, { agency: 'police', unitId: 'PCR-12', waypointJunction: 11 });
	ok(
		'F-28: a dispatch request the oracle refused writes no "requested" decision row (only the error row)',
		okReq === false && decisionsFor(/requested/).length === reqBefore && local().some((a) => a.level === 'error' && /dispatch request failed/.test(a.text)),
		local().slice(-3).map((a) => `${a.level}:${a.text}`).join(' | '),
	);
	const okReq2 = await ops.requestDispatchUnit(P, { agency: 'police', unitId: 'PCR-12', waypointJunction: 11 });
	ok('F-28: an accepted request writes its "requested" decision row', okReq2 === true && decisionsFor(/requested/).length === reqBefore + 1 && decisionsFor(/PCR-12 requested/).length === 1);
	const decBefore = decisionsFor(/^dispatch .* approved$/).length;
	world.failOnce.set(`/api/v1/dispatches/${D(9)}/decision`, { status: 409, body: { detail: 'already decided' } });
	const okDec = await ops.decideDispatchAction(D(9), 'approve');
	ok('F-28: a dispatch decision the oracle refused writes no "approved" decision row', okDec === false && decisionsFor(/^dispatch .* approved$/).length === decBefore, local().slice(-2).map((a) => `${a.level}:${a.text}`).join(' | '));
}

// ─── done ───────────────────────────────────────────────────────────────────

if (failures) {
	console.error(`decisions.unit: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('ok   decisions.unit — all assertions passed');
process.exit(0);
