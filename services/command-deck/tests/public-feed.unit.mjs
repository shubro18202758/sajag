/**
 * Public-feed unit test (UI-S6B; plan X17 — the public OSINT firewall).
 *
 *   node tests/public-feed.unit.mjs
 *
 * esbuild bundles the REAL projection module ($lib/citizen/public-api.server.ts,
 * with holds.ts and public-model.ts) — `$lib` aliased to src/lib — and drives it
 * through a fake `fetch`: no network, no oracle, no browser.
 *
 * The fake oracle's active-events list MIXES provenance — live, emulated and
 * OSINT-sourced rows, including an OSINT row of a PUBLIC kind (a mass_gathering)
 * — and asserts:
 *   - no OSINT row (source_kind 'osint' or metadata.source 'osint') appears in
 *     the projection, WHATEVER its kind — a promoted OSINT report never becomes
 *     a citizen hold card;
 *   - emulated rows keep their labelling (`emulated: true`, and the envelope's
 *     `emulated_labelling: true`, contract C-M);
 *   - the six OSINT reported-situation kinds (021) never appear, whatever their
 *     source — PUBLIC_EVENT_KINDS stays the one allowlist;
 *   - the wire shapes are kept (PublicFeedWire / PublicEventWire fields);
 *   - an OSINT row of a public kind that starts BEYOND the 2 h horizon is dropped
 *     from the dated Later list too (the filter runs before the horizon split —
 *     the audit's surviving mutant M5 applied it to the in-horizon rows only);
 *   - publicDispatchStatus answers the SAME 404-shaped "not found" body it gives
 *     an unknown dispatch when the dispatch's event row is OSINT-sourced (read
 *     BY ID from the oracle, GET /events/{id} — not the client's query string,
 *     not a window of recent rows), and the normal body for an ambulance
 *     dispatch on a live event;
 *   - it FAILS CLOSED (audit C, firewall-failopen.log): an unreadable event row
 *     (503, a timeout-shaped failure, an oracle without the route, a body for
 *     another event) answers 503 'temporarily unavailable' and never the
 *     dispatch body; an absent event answers not-found; an OSINT event older
 *     than the newest 200 rows answers not-found; a failed read is cached for
 *     the 2 s poll window like a good one (polling never multiplies reads).
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// P6A_TREE: the mutation harness points the SOURCES at a scratch copy (the tools stay the real deck's)
const TOOLS = path.resolve(HERE, '..');
const DECK = process.env.P6A_TREE ? path.resolve(process.env.P6A_TREE) : TOOLS;
const OUT = path.join(HERE, 'artifacts', 'public-feed-bundle.mjs');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

// ─── bundle the real module ─────────────────────────────────────────────────

mkdirSync(path.dirname(OUT), { recursive: true });
const esbuild = createRequire(path.join(TOOLS, 'package.json'))('esbuild');
const ENTRY = `
export * as pub from './src/lib/citizen/public-api.server';
export * as holds from './src/lib/citizen/holds';
`;
const built = await esbuild.build({
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'public-feed-entry.ts' },
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	outfile: OUT,
	logLevel: 'silent',
});
ok('bundle builds (esbuild, $lib aliased)', built.errors.length === 0, `${built.errors.length} errors`);

const M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
const { pub, holds } = M;

// ─── the fake oracle ────────────────────────────────────────────────────────

const NOW = Date.parse('2026-10-25T09:30:00Z');
const iso = (offMs) => new Date(NOW + offMs).toISOString();
const UUID = (n) => `${String(n).padStart(8, '0')}-1111-4222-8333-444455556666`;

/** A public-kind event row as /api/v1/events/active carries it (spine + closure plan). */
function eventRow(overrides = {}) {
	return {
		event_id: UUID(1),
		event_kind: 'procession',
		title: 'Test procession',
		status: 'active',
		movement_id: null,
		protection_class: 'none',
		planned_start: iso(-10 * 60_000),
		planned_end: iso(2 * 3600_000),
		routes: [{ label: 'primary', segment_ids: [1003, 1004] }],
		route_segment_ids: [1003, 1004],
		phases: [
			{
				label: 'w',
				window_start: iso(-10 * 60_000),
				window_end: iso(2 * 3600_000),
				closure_policy: { advance_closure_sec: 150 },
			},
		],
		source_kind: 'operator',
		verification_state: null,
		credibility: null,
		...overrides,
	};
}

const LIVE = eventRow({ event_id: UUID(1) });
const EMU = eventRow({
	event_id: UUID(2),
	event_kind: 'mass_gathering',
	metadata: { source: 'event-emulator' },
	source_kind: 'emulator',
});
/** An OSINT report promoted to a PUBLIC kind: the exact leak the firewall stops. */
const OSINT_PUBLIC_KIND = eventRow({
	event_id: UUID(3),
	event_kind: 'mass_gathering',
	source_kind: 'osint',
	verification_state: 'NEWS-REPORTED',
	credibility: 0.65,
});
const OSINT_META = eventRow({
	event_id: UUID(4),
	event_kind: 'protected_movement',
	source_kind: 'operator',
	metadata: { source: 'osint' },
});
/** The six reported-situation kinds (021): operator-only whatever their source. */
const NEW_KIND_LIVE = eventRow({ event_id: UUID(5), event_kind: 'road_accident', source_kind: 'operator' });
const NEW_KIND_OSINT = eventRow({
	event_id: UUID(6),
	event_kind: 'flooding',
	source_kind: 'osint',
	verification_state: 'UNVERIFIED-OSINT',
	credibility: 0.4,
});

function res(status, body) {
	return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

/**
 * One fake fetch: path → status/body, with the reads the projection makes
 * besides events (spatial names, signals, k-shortest-paths, the adaptive
 * layer, the escort GPS listing, the dispatch and its event row). The
 * matcher sees the URL's PATHNAME; the query string never selects a route.
 */
function fakeFetch(routes) {
	const calls = [];
	const fn = async (input) => {
		const u = new URL(input, 'http://deck.local');
		calls.push(u.pathname + (u.search || ''));
		for (const [match, answer] of routes) {
			if (match(u.pathname, u.searchParams)) {
				const a = answer();
				return res(a.status, a.body);
			}
		}
		return res(404, { detail: `no fake route: ${u.pathname}` });
	};
	fn.calls = calls;
	return fn;
}

const SEGMENTS = {
	status: 200,
	body: {
		segments: [
			{ segment_id: 1003, road_name: 'Vidyasagar Setu (NH12, Vidyasagar Flyover)', geometry: { coordinates: [[88.3199, 22.5682], [88.3259, 22.5692]] } },
			{ segment_id: 1004, road_name: 'Strand Road', geometry: { coordinates: [[88.3259, 22.5692], [88.3299, 22.5702]] } },
			{ segment_id: 1039, road_name: 'VIP Road (Kazi Nazrul Islam Avenue)', geometry: { coordinates: [[88.3199, 22.5582], [88.3219, 22.5592]] } },
		],
	},
};
const LAST_RESORT = [
	// The reads a candidate event makes beyond the events list: answered,
	// never hanging (a real 404 degrades to "unavailable", which is fine).
	[(p) => p === '/api/v1/signals/state', () => ({ status: 200, body: { junctions: [{ junction_id: 6, lon: 88.3259, lat: 22.5692 }] } })],
	[(p) => p.startsWith('/api/v1/graph/k-shortest-paths'), () => ({ status: 200, body: { paths: [[{ node: 1003 }, { node: 1039 }, { node: 1004 }]] } })],
	[(p) => p.startsWith('/api/v1/adaptive/params'), () => ({ status: 200, body: { params: { advance_closure_sec: 120 }, source: 'baseline' } })],
	[(p) => p.startsWith('/api/v1/adaptive/situation_log'), () => ({ status: 200, body: { entries: [] } })],
	[(p) => p === '/api/convoy/escorts', () => ({ status: 200, body: { escorts: [] } })],
];

// ─── 1. the feed drops OSINT rows before projection ─────────────────────────

{
	pub.resetPublicCaches();
	const fn = fakeFetch([
		[(p) => p === '/api/v1/events/active', () => ({ status: 200, body: { events: [LIVE, EMU, OSINT_PUBLIC_KIND, OSINT_META, NEW_KIND_LIVE, NEW_KIND_OSINT] } })],
		[(p) => p === '/api/v1/spatial/segments', () => SEGMENTS],
		...LAST_RESORT,
	]);
	const res = await pub.buildPublicFeed(fn, NOW);
	ok('feed answers 200 with the envelope', res.status === 200, `status ${res.status}`);
	const body = res.body;
	ok('emulated_labelling stays true (C-M)', body.emulated_labelling === true);
	const ids = body.events.map((e) => e.event_id);
	ok(
		'no OSINT row reaches the projection, not even a public kind',
		!ids.includes(UUID(3)) && !ids.includes(UUID(4)),
		ids.join(' | '),
	);
	ok(
		'the six reported-situation kinds never appear, whatever their source',
		!ids.includes(UUID(5)) && !ids.includes(UUID(6)),
		ids.join(' | '),
	);
	ok('a live public event is still projected', ids.includes(UUID(1)), ids.join(' | '));
	const live = body.events.find((e) => e.event_id === UUID(1));
	ok(
		'the live row keeps the wire shape (stretches, hold, alternate, tier, unavailable)',
		Array.isArray(live.stretches) &&
			live.stretches[0]?.road_name === 'Vidyasagar Setu (NH12, Vidyasagar Flyover)' &&
			live.hold?.minutes === 3 &&
			live.hold?.source === 'closure_policy' &&
			live.alternate?.road_names?.[0] === 'VIP Road (Kazi Nazrul Islam Avenue)' &&
			typeof live.unavailable === 'object' &&
			typeof live.emulated === 'boolean',
		JSON.stringify(live),
	);
	ok(
		'the emulated row is projected with its labelling kept',
		ids.includes(UUID(2)) && body.events.find((e) => e.event_id === UUID(2)).emulated === true,
	);
	const segCalls = fn.calls.filter((c) => c.startsWith('/api/v1/spatial/segments')).length;
	ok('the OSINT reads cost no extra signage reads (dropped before projection)', segCalls === 1, `${segCalls} segment reads`);
}

// ─── 2. an OSINT-only feed projects nothing, but stays honest ───────────────

{
	pub.resetPublicCaches();
	const fn = fakeFetch([
		[(p) => p === '/api/v1/events/active', () => ({ status: 200, body: { events: [OSINT_PUBLIC_KIND, NEW_KIND_OSINT] } })],
		...LAST_RESORT,
	]);
	const res = await pub.buildPublicFeed(fn, NOW);
	ok('an OSINT-only feed answers 200', res.status === 200);
	ok(
		'…with no events and no Later rows',
		res.body.events.length === 0 && res.body.later.length === 0,
		JSON.stringify({ events: res.body.events.length, later: res.body.later.length }),
	);
}

// ─── 2b. an OSINT row beyond the horizon never reaches the Later list ───────

{
	pub.resetPublicCaches();
	/** A real procession 5 h ahead: the Later list is not empty, so the split runs. */
	const LATER_LIVE = eventRow({
		event_id: UUID(7),
		status: 'approved',
		planned_start: iso(5 * 3600_000),
		planned_end: iso(6 * 3600_000),
		phases: [],
	});
	/** A PROMOTED OSINT report of a public kind, also 5 h ahead (the M5 survivor). */
	const LATER_OSINT = eventRow({
		event_id: UUID(8),
		event_kind: 'mass_gathering',
		status: 'approved',
		planned_start: iso(5 * 3600_000),
		planned_end: iso(6 * 3600_000),
		phases: [],
		source_kind: 'osint',
		verification_state: 'UNVERIFIED-OSINT',
		credibility: 0.4,
	});
	const LATER_OSINT_META = eventRow({
		event_id: UUID(9),
		event_kind: 'work_zone',
		status: 'planning',
		planned_start: iso(7 * 3600_000),
		planned_end: iso(8 * 3600_000),
		phases: [],
		source_kind: 'operator',
		metadata: { source: 'osint' },
	});
	const fn = fakeFetch([
		[(p) => p === '/api/v1/events/active', () => ({ status: 200, body: { events: [LIVE, LATER_LIVE, LATER_OSINT, LATER_OSINT_META] } })],
		[(p) => p === '/api/v1/spatial/segments', () => SEGMENTS],
		...LAST_RESORT,
	]);
	const res = await pub.buildPublicFeed(fn, NOW);
	const later = (res.body.later ?? []).map((e) => e.event_id);
	ok('a real event beyond the horizon sits in the Later list', res.status === 200 && later.includes(UUID(7)), later.join(' | '));
	ok(
		"an OSINT public-kind row beyond the horizon never reaches the Later list (source_kind 'osint')",
		!later.includes(UUID(8)),
		later.join(' | '),
	);
	ok("…nor one marked metadata.source 'osint'", !later.includes(UUID(9)), later.join(' | '));
	ok(
		'…and neither reaches the hold cards',
		!res.body.events.some((e) => e.event_id === UUID(8) || e.event_id === UUID(9)),
		res.body.events.map((e) => e.event_id).join(' | '),
	);
}

// ─── 3. the driver's own dispatch status ────────────────────────────────────

const DISPATCH_LIVE = UUID(10);
const DISPATCH_OSINT = UUID(11);
const DISPATCH_UNKNOWN = UUID(12);
const UNIT_ROWS = [];

async function dispatchStatus(fn, dispatchId, eventId) {
	return pub.publicDispatchStatus(fn, dispatchId, eventId, NOW);
}

{
	pub.resetPublicCaches();
	const fn = fakeFetch([
		[
			(p) => p === `/api/v1/dispatches/${DISPATCH_LIVE}`,
			() => ({
				status: 200,
				body: {
					dispatch_id: DISPATCH_LIVE,
					event_id: UUID(1),
					agency: 'ambulance',
					unit_id: '108-14',
					status: 'approved',
					approved_at: iso(-30_000),
					created_at: iso(-60_000),
					updated_at: iso(-30_000),
				},
			}),
		],
		[(p) => p === `/api/v1/events/${UUID(1)}`, () => ({ status: 200, body: LIVE })],
		[(p) => p === `/api/v1/events/${UUID(3)}`, () => ({ status: 200, body: OSINT_PUBLIC_KIND })],
		[(p) => p === '/api/v1/units', () => ({ status: 200, body: { units: UNIT_ROWS } })],
	]);
	const res = await dispatchStatus(fn, DISPATCH_LIVE, UUID(1));
	ok(
		'an ambulance dispatch on a LIVE event answers normally',
		res.status === 200 && res.body.dispatch.dispatch_id === DISPATCH_LIVE && res.body.dispatch.status === 'approved',
		`status ${res.status} · ${JSON.stringify(res.body).slice(0, 140)}`,
	);
	ok(
		'…with no officer names, notes or audit tails in the body',
		!('audit' in res.body.dispatch) && !('note' in res.body.dispatch) && !('officer' in res.body.dispatch),
		JSON.stringify(Object.keys(res.body.dispatch)),
	);
	ok(
		'the event row was read from the oracle BY ID (GET /events/{id}), not a window of recent rows',
		fn.calls.includes(`/api/v1/events/${UUID(1)}`) && !fn.calls.some((c) => c.startsWith('/api/v1/events?')),
		fn.calls.join(' | '),
	);
}

{
	pub.resetPublicCaches();
	const fn = fakeFetch([
		[
			(p) => p === `/api/v1/dispatches/${DISPATCH_OSINT}`,
			() => ({
				status: 200,
				body: {
					dispatch_id: DISPATCH_OSINT,
					event_id: UUID(3),
					agency: 'ambulance',
					unit_id: '108-15',
					status: 'approved',
					approved_at: iso(-30_000),
				},
			}),
		],
		[(p) => p === `/api/v1/events/${UUID(3)}`, () => ({ status: 200, body: OSINT_PUBLIC_KIND })],
		[(p) => p === '/api/v1/units', () => ({ status: 200, body: { units: UNIT_ROWS } })],
	]);
	const res = await dispatchStatus(fn, DISPATCH_OSINT, UUID(3));
	ok(
		"a dispatch whose event row is source_kind 'osint' answers the same not-found body",
		res.status === 404 && res.body.detail === 'no such ambulance request for this event',
		`status ${res.status} · ${JSON.stringify(res.body)}`,
	);
}

{
	pub.resetPublicCaches();
	const osintMetaEvent = eventRow({
		event_id: UUID(4),
		event_kind: 'procession',
		source_kind: 'operator',
		metadata: { source: 'osint' },
	});
	const fn = fakeFetch([
		[(p) => p.startsWith('/api/v1/dispatches/'), () => ({ status: 200, body: { dispatch_id: DISPATCH_OSINT, event_id: UUID(4), agency: 'ambulance', status: 'approved' } })],
		[(p) => p === `/api/v1/events/${UUID(4)}`, () => ({ status: 200, body: osintMetaEvent })],
		[(p) => p === '/api/v1/units', () => ({ status: 200, body: { units: UNIT_ROWS } })],
	]);
	const res = await dispatchStatus(fn, DISPATCH_OSINT, UUID(4));
	ok(
		"a dispatch whose event carries metadata.source 'osint' answers not-found too",
		res.status === 404 && res.body.detail === 'no such ambulance request for this event',
		`status ${res.status}`,
	);
}

{
	pub.resetPublicCaches();
	const fn = fakeFetch([
		[(p) => p.startsWith('/api/v1/dispatches/'), () => ({ status: 404, body: { detail: 'dispatch not found' } })],
		[(p) => p === `/api/v1/events/${UUID(1)}`, () => ({ status: 200, body: LIVE })],
	]);
	const res = await dispatchStatus(fn, DISPATCH_UNKNOWN, UUID(1));
	ok('an unknown dispatch still answers the plain not-found', res.status === 404 && res.body.detail === 'no such ambulance request for this event');
}

{
	pub.resetPublicCaches();
	// A police dispatch on a live event is never readable here (unchanged rule).
	const fn = fakeFetch([
		[(p) => p.startsWith('/api/v1/dispatches/'), () => ({ status: 200, body: { dispatch_id: DISPATCH_LIVE, event_id: UUID(1), agency: 'police', status: 'approved' } })],
		[(p) => p === `/api/v1/events/${UUID(1)}`, () => ({ status: 200, body: LIVE })],
	]);
	const res = await dispatchStatus(fn, DISPATCH_LIVE, UUID(1));
	ok('a police dispatch is still refused (108 only)', res.status === 404 && res.body.detail === 'no such ambulance request for this event');
}

// ─── 3b. the dispatch firewall FAILS CLOSED (audit C, firewall-failopen.log) ─

/** The approved 108 dispatch on UUID(1) / UUID(3), as GET /dispatches/{id} answers it. */
const dispatchRoute = (dispatchId, eventId) => [
	(p) => p === `/api/v1/dispatches/${dispatchId}`,
	() => ({
		status: 200,
		body: {
			dispatch_id: dispatchId,
			event_id: eventId,
			agency: 'ambulance',
			unit_id: '108-14',
			status: 'approved',
			approved_at: iso(-30_000),
		},
	}),
];
const UNITS_ROUTE = [(p) => p === '/api/v1/units', () => ({ status: 200, body: { units: UNIT_ROWS } })];
const noDispatchBody = (res) => !('dispatch' in (res.body ?? {})) && !('unit' in (res.body ?? {}));

{
	pub.resetPublicCaches();
	// The oracle hiccups: every events read answers 503 (list and by-id alike).
	const fn = fakeFetch([
		dispatchRoute(DISPATCH_OSINT, UUID(3)),
		[(p) => p.startsWith('/api/v1/events'), () => ({ status: 503, body: { detail: 'database pool unavailable' } })],
		UNITS_ROUTE,
	]);
	const res = await dispatchStatus(fn, DISPATCH_OSINT, UUID(3));
	ok(
		'events read 503 → 503 temporarily unavailable, never the dispatch body',
		res.status === 503 && /temporarily unavailable/.test(res.body.detail ?? '') && noDispatchBody(res),
		`status ${res.status} · ${JSON.stringify(res.body).slice(0, 160)}`,
	);
	const eventReads = () => fn.calls.filter((c) => c.startsWith('/api/v1/events')).length;
	const first = eventReads();
	await dispatchStatus(fn, DISPATCH_OSINT, UUID(3));
	await dispatchStatus(fn, DISPATCH_OSINT, UUID(3));
	ok(
		'…the failed read is cached for the 2 s poll window (polling never multiplies upstream reads)',
		first === 1 && eventReads() === 1,
		`${eventReads()} events reads over 3 polls`,
	);
	ok('…and the units projection is never read for it', !fn.calls.includes('/api/v1/units'), fn.calls.join(' | '));
}

{
	pub.resetPublicCaches();
	// An oracle without GET /events/{id} answers FastAPI's plain 404: unreadable, not "absent".
	const fn = fakeFetch([
		dispatchRoute(DISPATCH_LIVE, UUID(1)),
		[(p) => p === `/api/v1/events/${UUID(1)}`, () => ({ status: 404, body: { detail: 'Not Found' } })],
		[(p) => p === '/api/v1/events', () => ({ status: 200, body: { events: [LIVE], count: 1 } })],
		UNITS_ROUTE,
	]);
	const res = await dispatchStatus(fn, DISPATCH_LIVE, UUID(1));
	ok(
		'an oracle without the by-id route → 503, never the dispatch body (no list fallback)',
		res.status === 503 && noDispatchBody(res),
		`status ${res.status} · ${JSON.stringify(res.body).slice(0, 160)}`,
	);
}

{
	pub.resetPublicCaches();
	// A body that is not THIS event's row (another event, a list) is unreadable.
	const fn = fakeFetch([
		dispatchRoute(DISPATCH_LIVE, UUID(1)),
		[(p) => p === `/api/v1/events/${UUID(1)}`, () => ({ status: 200, body: { ...LIVE, event_id: UUID(2) } })],
		UNITS_ROUTE,
	]);
	const res = await dispatchStatus(fn, DISPATCH_LIVE, UUID(1));
	ok('an event read answering another event → 503, never the dispatch body', res.status === 503 && noDispatchBody(res), `status ${res.status}`);
}

{
	pub.resetPublicCaches();
	// The event is gone: the oracle's own words, 404 'event … not found'.
	const fn = fakeFetch([
		dispatchRoute(DISPATCH_LIVE, UUID(1)),
		[(p) => p === `/api/v1/events/${UUID(1)}`, () => ({ status: 404, body: { detail: `event ${UUID(1)} not found` } })],
		[(p) => p === '/api/v1/events', () => ({ status: 200, body: { events: [], count: 0 } })],
		UNITS_ROUTE,
	]);
	const res = await dispatchStatus(fn, DISPATCH_LIVE, UUID(1));
	ok(
		'event absent → the plain not-found (NO_SUCH), never the dispatch body',
		res.status === 404 && res.body.detail === 'no such ambulance request for this event' && noDispatchBody(res),
		`status ${res.status} · ${JSON.stringify(res.body).slice(0, 160)}`,
	);
}

{
	pub.resetPublicCaches();
	// The OSINT event is OLDER than the newest 200 rows: a recent-rows window
	// misses it (the audit's second leak); the by-id read never does.
	const newest = Array.from({ length: 200 }, (_, i) => eventRow({ event_id: `${String(100 + i).padStart(8, '0')}-9999-4222-8333-444455556666` }));
	const fn = fakeFetch([
		dispatchRoute(DISPATCH_OSINT, UUID(3)),
		[(p) => p === `/api/v1/events/${UUID(3)}`, () => ({ status: 200, body: OSINT_PUBLIC_KIND })],
		[(p) => p === '/api/v1/events', () => ({ status: 200, body: { events: newest, count: newest.length } })],
		UNITS_ROUTE,
	]);
	const res = await dispatchStatus(fn, DISPATCH_OSINT, UUID(3));
	ok(
		'an OSINT event beyond the newest 200 rows → NO_SUCH, never the dispatch body',
		res.status === 404 && res.body.detail === 'no such ambulance request for this event' && noDispatchBody(res),
		`status ${res.status} · ${JSON.stringify(res.body).slice(0, 160)}`,
	);
}

{
	pub.resetPublicCaches();
	// Many drivers polling one live dispatch: one dispatch + event + units read per 2 s.
	const fn = fakeFetch([
		dispatchRoute(DISPATCH_LIVE, UUID(1)),
		[(p) => p === `/api/v1/events/${UUID(1)}`, () => ({ status: 200, body: LIVE })],
		UNITS_ROUTE,
	]);
	const first = await dispatchStatus(fn, DISPATCH_LIVE, UUID(1));
	const reads = fn.calls.length;
	for (let i = 0; i < 5; i++) await dispatchStatus(fn, DISPATCH_LIVE, UUID(1));
	ok(
		'a live dispatch answers 200, and polling shares one read set per 2 s',
		first.status === 200 && reads === 3 && fn.calls.length === reads,
		`${reads} first-poll reads, ${fn.calls.length - reads} extra · ${fn.calls.join(' | ')}`,
	);
}

// ─── 4. the allowlist stays exactly as it is ────────────────────────────────

ok(
	'PUBLIC_EVENT_KINDS is unchanged (the eight public kinds)',
	JSON.stringify([...holds.PUBLIC_EVENT_KINDS]) === JSON.stringify([
		'protected_movement',
		'procession',
		'mass_gathering',
		'race',
		'ceremonial',
		'egress_surge',
		'emergency_evacuation',
		'work_zone',
	]),
	holds.PUBLIC_EVENT_KINDS.join(','),
);

// ─── F-CONN-03: a movement whose position source the brain could not report ──
// The citizen feed asks the brain which escorts drive on its EMULATED GPS
// walker. When that read FAILS, the movement's position is UNKNOWN: it must
// be labelled (position_unverified), never vouched for as live, and never
// set the city strip's tier. With the brain up the answer stands as given.

{
	const MOVE = eventRow({
		event_id: UUID(7),
		event_kind: 'protected_movement',
		title: 'Test protected movement',
		protection_class: 'Z',
		movement_id: 'mv-7',
		source_kind: 'operator',
	});
	const BAND_RED = { status: 200, body: { entries: [{ situation_class: 'RED', observed_at: iso(-30_000), timestamp_utc: iso(-30_000) }] } };
	const run = async (escorts) => {
		pub.resetPublicCaches();
		const fn = fakeFetch([
			[(p) => p === '/api/v1/events/active', () => ({ status: 200, body: { events: [MOVE] } })],
			[(p) => p === '/api/v1/spatial/segments', () => SEGMENTS],
			[(p) => p.startsWith('/api/v1/adaptive/situation_log'), () => BAND_RED],
			[(p) => p === '/api/convoy/escorts', escorts],
			...LAST_RESORT,
		]);
		return (await pub.buildPublicFeed(fn, NOW)).body;
	};
	const down = await run(() => ({ status: 503, body: { detail: 'brain down' } }));
	const evDown = down.events.find((e) => e.event_id === UUID(7));
	ok(
		'F-CONN-03: brain DOWN → the movement is position_unverified, not emulated-claimed, and out of the strip tier',
		!!evDown && evDown.position_unverified === true && evDown.emulated === false && down.tier === 'calm',
		JSON.stringify({ unverified: evDown?.position_unverified, emulated: evDown?.emulated, tier: down.tier, rowTier: evDown?.tier }),
	);
	const upLive = await run(() => ({ status: 200, body: { escorts: [] } }));
	const evLive = upLive.events.find((e) => e.event_id === UUID(7));
	ok(
		'F-CONN-03: brain UP, no emulated escort → the movement is live (no unverified flag) and sets the tier',
		!!evLive && evLive.position_unverified === undefined && evLive.emulated === false && upLive.tier !== 'calm',
		JSON.stringify({ unverified: evLive?.position_unverified, tier: upLive.tier }),
	);
	const upEmu = await run(() => ({ status: 200, body: { escorts: [{ event_id: UUID(7), gps_mode: 'emulated' }] } }));
	const evEmu = upEmu.events.find((e) => e.event_id === UUID(7));
	ok(
		'F-CONN-03: brain UP with an emulated escort → emulated (labelled), out of the tier',
		!!evEmu && evEmu.emulated === true && evEmu.position_unverified === undefined && upEmu.tier === 'calm',
		JSON.stringify({ emulated: evEmu?.emulated, tier: upEmu.tier }),
	);
	ok(
		'F-CONN-03: the escort read failing is "unknown" (null), never an empty set read as live',
		(await pub.loadEmulatedPositionEvents(fakeFetch([[(p) => p === '/api/convoy/escorts', () => ({ status: 502, body: {} })]]))) === null,
	);
}

// ─── FIX-G-ORACLE: emulated EVIDENCE makes the event emulated (HON-4) ─────────
ok(
	'isEmulatedRow: metadata.evidence_source "emulated" (an emulated vehicle\'s pursuit opened by an officer) is emulated',
	pub.isEmulatedRow({ metadata: { source: 'deck', evidence_source: 'emulated' } }) === true &&
		pub.isEmulatedRow({ metadata: { source: 'deck' } }) === false &&
		pub.isEmulatedRow({ metadata: { mode: 'living_city' } }) === true,
);

// ─── done ───────────────────────────────────────────────────────────────────

if (failures) {
	console.error(`public-feed.unit: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('public-feed.unit: all green');
