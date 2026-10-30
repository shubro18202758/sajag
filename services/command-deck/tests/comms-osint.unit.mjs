/**
 * Comms OSINT unit test (FIX-AUDIT-C1; plan X17 — the public firewall's desk face).
 *
 *   node tests/comms-osint.unit.mjs
 *
 * esbuild bundles the REAL comms modules ($lib/comms/advisory.ts, facts.ts and
 * osint.ts, with holds.ts and the i18n packs) — `$lib` aliased to src/lib — and
 * drives them with plain facts and a stubbed global `fetch`: no network, no
 * oracle, no browser.
 *
 * An OSINT-sourced event (source_kind 'osint', or metadata.source 'osint') —
 * including a report a named officer PROMOTED to a public kind, here a
 * mass_gathering — is withheld from the citizen and the 108 audiences:
 *   - every citizen and 108 draft, in EN, HI and MR, is `withheld` (the desk's
 *     Copy button is disabled on it), its reason 'osint', and its text is the
 *     withheld notice naming the verification label in that language — no hold,
 *     no road, no clock is composed for them;
 *   - the citizen all-clear is withheld the same way;
 *   - the desk's withheld badge (commsWithholding) carries that label and names
 *     both audiences; a non-OSINT event has none;
 *   - zone and municipal drafts are still written, each opening with the label;
 *   - resolveFacts marks the event OSINT from the board row OR the raw
 *     /events/active row (either withholds), labelled by the raw row's state;
 *   - a non-OSINT public event is drafted normally, and an operator-only kind is
 *     still withheld for its own reason (the guards do not blur).
 *
 * The core assertions use the writer's long-standing API (composeAdvisory,
 * composeAllClear, resolveFacts), so they fail on the pre-change code too.
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
const OUT_DIR = path.join(HERE, 'artifacts');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

// ─── bundle the real modules ────────────────────────────────────────────────

mkdirSync(OUT_DIR, { recursive: true });
const esbuild = createRequire(path.join(TOOLS, 'package.json'))('esbuild');

async function bundle(entry, name) {
	const outfile = path.join(OUT_DIR, `${name}.mjs`);
	try {
		await esbuild.build({
			stdin: { contents: entry, resolveDir: DECK, loader: 'ts', sourcefile: `${name}-entry.ts` },
			absWorkingDir: DECK,
			alias: { $lib: './src/lib' },
			bundle: true,
			format: 'esm',
			platform: 'node',
			outfile,
			logLevel: 'silent',
		});
	} catch (err) {
		return { error: String(err?.message ?? err).split('\n')[0] };
	}
	return { mod: await import(`${pathToFileURL(outfile).href}?t=${Date.now()}`) };
}

const core = await bundle(
	`export * as adv from './src/lib/comms/advisory';\nexport * as facts from './src/lib/comms/facts';\n`,
	'comms-osint-core-bundle',
);
ok('bundle builds: comms advisory + facts (esbuild, $lib aliased)', !core.error, core.error ?? '0 errors');
if (core.error) process.exit(1);
const { adv, facts: factsMod } = core.mod;
const desk = await bundle(`export * from './src/lib/comms/osint';\n`, 'comms-osint-desk-bundle');
ok('bundle builds: comms osint rule ($lib/comms/osint)', !desk.error, desk.error ?? '0 errors');
const osint = desk.mod ?? null;

// ─── facts ──────────────────────────────────────────────────────────────────

const NOW = Date.parse('2026-10-25T09:30:00Z');
const LABELS = {
	'NEWS-REPORTED': { en: 'News-reported', hi: 'समाचार में रिपोर्ट', mr: 'बातम्यांमध्ये नोंदलेले' },
	'UNVERIFIED-OSINT': { en: 'Unverified OSINT', hi: 'असत्यापित OSINT', mr: 'न पडताळलेले OSINT' },
};
const ROAD = 'Vidyasagar Setu (NH12, Vidyasagar Flyover)';
const ALT = 'VIP Road (Kazi Nazrul Islam Avenue)';

function baseFacts(overrides = {}) {
	return {
		eventId: '00000003-1111-4222-8333-444455556666',
		eventKind: 'mass_gathering',
		stretch: { segmentId: 1003, roadName: ROAD },
		holdMinutes: 3,
		holdSource: 'closure_policy',
		alternate: [ALT],
		anchorMs: NOW + 10 * 60_000,
		unavailable: { hold: false, alternate: false },
		emulated: false,
		...overrides,
	};
}

/** An OSINT report a named officer promoted to a PUBLIC kind (the exact leak). */
const OSINT_PUBLIC = baseFacts({ osint: { verification: 'NEWS-REPORTED' } });
const PLAIN_PUBLIC = baseFacts({ eventId: '00000001-1111-4222-8333-444455556666' });

/** A composed hold advisory (not a notice): carries the road, the alternate or the hold. */
const carriesHoldFacts = (text) => text.includes(ROAD) || text.includes(ALT) || /[~3३૩]/.test(text);

// ─── 1. citizen + 108 drafts of an OSINT public-kind event are withheld ─────

for (const audience of ['citizens', 'ambulance108']) {
	const drafts = adv.composeAdvisoryTrilingual(OSINT_PUBLIC, audience);
	ok(`${audience}: one draft per language (en, hi, mr)`, drafts.map((d) => d.lang).join(',') === 'en,hi,mr', drafts.map((d) => d.lang).join(','));
	for (const d of drafts) {
		const label = LABELS['NEWS-REPORTED'][d.lang];
		ok(
			`${audience}/${d.lang}: an OSINT public-kind draft is withheld (no copyable text)`,
			d.withheld === true,
			JSON.stringify({ withheld: d.withheld, text: d.text }),
		);
		ok(`${audience}/${d.lang}: …for the OSINT reason`, d.withheldReason === 'osint', String(d.withheldReason));
		ok(`${audience}/${d.lang}: …its notice names the verification label "${label}"`, d.text.includes(label), d.text);
		ok(`${audience}/${d.lang}: …and composes no hold, road or alternate`, !carriesHoldFacts(d.text), d.text);
	}
}

{
	const meta = baseFacts({ eventKind: 'procession', osint: { verification: 'UNVERIFIED-OSINT' } });
	const d = adv.composeAdvisory(meta, 'citizens', 'en');
	ok(
		'an unverified OSINT procession: the citizen draft is withheld, labelled "Unverified OSINT"',
		d.withheld === true && d.text.includes('Unverified OSINT') && !carriesHoldFacts(d.text),
		d.text,
	);
	const unstated = adv.composeAdvisory(baseFacts({ osint: { verification: null } }), 'ambulance108', 'en');
	ok(
		'an OSINT event with no stated verification: the 108 draft is withheld, saying no verification is stated',
		unstated.withheld === true && unstated.text.includes('Open-source report') && unstated.text.includes('no verification stated'),
		unstated.text,
	);
}

// ─── 2. the citizen all-clear is withheld too ───────────────────────────────

{
	const mark = { verification: 'NEWS-REPORTED' };
	const texts = adv.composeAllClearTrilingual('mass_gathering', false, mark);
	ok(
		'the citizen all-clear of an OSINT event is the withheld notice, in every language',
		texts.length === 3 && texts.every((x) => x.text.includes(LABELS['NEWS-REPORTED'][x.lang]) && !/cleared/i.test(x.text)),
		JSON.stringify(texts),
	);
	ok(
		'…while a real event still gets its all-clear',
		/has cleared/.test(adv.composeAllClear('mass_gathering', 'en')),
		adv.composeAllClear('mass_gathering', 'en'),
	);
}

// ─── 3. the badge and its label ─────────────────────────────────────────────

if (osint) {
	for (const lang of ['en', 'hi', 'mr']) {
		const w = osint.commsWithholding({ verification: 'NEWS-REPORTED' }, lang);
		ok(
			`badge/${lang}: commsWithholding carries the verification label and both audiences`,
			!!w && w.label === LABELS['NEWS-REPORTED'][lang] && w.badge.includes(w.label) && w.audiences.join(',') === 'citizens,ambulance108',
			JSON.stringify(w),
		);
	}
	ok('badge: a non-OSINT event has none', osint.commsWithholding(null, 'en') === null);
	ok('badge: the EN badge says who it is withheld from', /withheld from citizens and 108/.test(osint.commsWithholding({ verification: null }, 'en')?.badge ?? ''));
	ok(
		'predicate: source_kind or metadata.source "osint" (the public firewall\'s own test)',
		osint.isOsintSourced({ sourceKind: 'osint' }) &&
			osint.isOsintSourced({ sourceKind: 'operator', metadata: { source: 'osint' } }) &&
			!osint.isOsintSourced({ sourceKind: 'operator', metadata: { source: 'event-emulator' } }) &&
			!osint.isOsintSourced(null),
	);
	ok(
		'the withheld audiences are exactly citizens and 108',
		osint.OSINT_WITHHELD_AUDIENCES.join(',') === 'citizens,ambulance108',
		osint.OSINT_WITHHELD_AUDIENCES.join(','),
	);
} else {
	ok('badge: $lib/comms/osint provides commsWithholding', false, 'module missing');
}

// ─── 4. zone and municipal drafts are still written, labelled ───────────────

for (const audience of ['zones', 'municipal']) {
	const d = adv.composeAdvisory(OSINT_PUBLIC, audience, 'en');
	ok(
		`${audience}: an OSINT event is still drafted for officers, opening with its label`,
		d.withheld === false && d.withheldReason === null && d.text.startsWith('[News-reported — open-source report]') && d.text.includes(ROAD),
		d.text,
	);
}

// ─── 5. the guards do not blur ──────────────────────────────────────────────

{
	const d = adv.composeAdvisory(PLAIN_PUBLIC, 'citizens', 'en');
	ok('a real public event: the citizen draft is composed', d.withheld === false && d.text.includes(ALT), d.text);
	const amb = adv.composeAdvisory(PLAIN_PUBLIC, 'ambulance108', 'en');
	ok('…and the 108 draft too', amb.withheld === false && amb.text.includes(ROAD), amb.text);
	const pursuit = adv.composeAdvisory(baseFacts({ eventKind: 'vehicle_pursuit' }), 'citizens', 'en');
	ok(
		'an operator-only kind is still withheld from citizens, for its own reason',
		pursuit.withheld === true && pursuit.withheldReason === 'operator-kind',
		JSON.stringify({ withheld: pursuit.withheld, reason: pursuit.withheldReason }),
	);
}

// ─── 6. resolveFacts marks the event from the board row OR the raw row ──────

/** A board event (ops CorridorEvent) as the desk lists it. */
function boardEvent(overrides = {}) {
	return {
		eventId: '00000003-1111-4222-8333-444455556666',
		name: 'Gathering near Law Garden',
		eventKind: 'mass_gathering',
		protectionClass: 'none',
		crowdClass: 'HIGH',
		state: 'active',
		routeSegmentIds: [1003, 1004],
		phases: [
			{
				label: 'w',
				startTime: new Date(NOW - 10 * 60_000).toISOString(),
				endTime: new Date(NOW + 2 * 3600_000).toISOString(),
				closurePolicy: { advanceClosureSec: 150 },
				state: 'active',
			},
		],
		currentPhase: null,
		band: null,
		windowStart: new Date(NOW - 10 * 60_000).toISOString(),
		windowEnd: new Date(NOW + 2 * 3600_000).toISOString(),
		description: null,
		source: 'live-events-api',
		emulated: false,
		sourceKind: 'operator',
		verificationState: null,
		metadata: { vehicleId: null, recommendationId: null, source: null, mode: null, runId: null, useCaseId: null, isReplay: null },
		...overrides,
	};
}

function stubOracle(activeRows) {
	globalThis.fetch = async (input) => {
		const u = new URL(String(input), 'http://deck.local');
		const body =
			u.pathname === '/api/v1/events/active'
				? { events: activeRows }
				: u.pathname === '/api/v1/spatial/segments'
					? { segments: [{ segment_id: 1003, road_name: ROAD }, { segment_id: 1039, road_name: ALT }] }
					: u.pathname === '/api/v1/graph/k-shortest-paths'
						? { paths: [[{ node: 1003 }, { node: 1039 }, { node: 1004 }]] }
						: null;
		return body
			? new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })
			: new Response('{"detail":"no fake route"}', { status: 404 });
	};
}

/** The raw /events/active row of a board event, with the provenance the oracle holds. */
const rawRow = (ev, extra = {}) => ({ event_id: ev.eventId, event_kind: ev.eventKind, metadata: {}, source_kind: 'operator', ...extra });

// The raw rows are memoised for 10 s, so the failing-oracle case runs first
// (a failed read is never memoised) and the answering oracle is stubbed once.
const BOARD_OSINT = boardEvent({ sourceKind: 'osint', verificationState: 'UNVERIFIED-OSINT' });
const BOARD_LAGGING = boardEvent({ eventId: '00000004-1111-4222-8333-444455556666', eventKind: 'procession' });
const BOARD_META_ONLY = boardEvent({
	eventId: '00000005-1111-4222-8333-444455556666',
	metadata: { vehicleId: null, recommendationId: null, source: 'osint', mode: null, runId: null, useCaseId: null, isReplay: null },
});
const BOARD_OPERATOR = boardEvent({ eventId: '00000006-1111-4222-8333-444455556666' });

{
	// The raw read fails: the board row's own mark still withholds (never fails open).
	globalThis.fetch = async () => new Response('{"detail":"down"}', { status: 503 });
	const f = await factsMod.resolveFacts(BOARD_META_ONLY, NOW);
	const d = adv.composeAdvisory(f, 'ambulance108', 'en');
	ok(
		"resolveFacts: oracle down, the board row's metadata.source 'osint' still withholds the 108 draft",
		d.withheld === true && d.withheldReason === 'osint',
		d.text,
	);
}

stubOracle([
	rawRow(BOARD_OSINT, { source_kind: 'osint', verification_state: 'NEWS-REPORTED' }),
	// The board row lags (no provenance yet); the raw row says metadata.source 'osint'.
	rawRow(BOARD_LAGGING, { metadata: { source: 'osint' }, verification_state: 'UNVERIFIED-OSINT' }),
	rawRow(BOARD_OPERATOR),
]);

{
	// The board row says OSINT (source_kind), the raw row agrees and states its label.
	const f = await factsMod.resolveFacts(BOARD_OSINT, NOW);
	const drafts = ['citizens', 'ambulance108'].map((a) => adv.composeAdvisory(f, a, 'en'));
	ok(
		'resolveFacts: an OSINT board event → its citizen and 108 drafts are withheld',
		drafts.every((d) => d.withheld === true),
		drafts.map((d) => d.text).join(' | '),
	);
	ok(
		"…labelled by the raw row's verification state (the oracle's current word)",
		f.osint?.verification === 'NEWS-REPORTED' && drafts.every((d) => d.text.includes('News-reported')),
		JSON.stringify(f.osint),
	);
}

{
	const f = await factsMod.resolveFacts(BOARD_LAGGING, NOW);
	const d = adv.composeAdvisory(f, 'citizens', 'en');
	ok(
		"resolveFacts: the raw row's metadata.source 'osint' withholds even when the board row lags",
		d.withheld === true && d.text.includes('Unverified OSINT'),
		d.text,
	);
}

{
	// Control: an operator public event resolves with no mark and is drafted.
	const f = await factsMod.resolveFacts(BOARD_OPERATOR, NOW);
	const d = adv.composeAdvisory(f, 'citizens', 'en');
	ok('resolveFacts: an operator event carries no OSINT mark and is drafted', !f.osint && d.withheld === false && d.text.includes(ALT), d.text);
}

// ─── done ───────────────────────────────────────────────────────────────────

if (failures) {
	console.error(`comms-osint.unit: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('comms-osint.unit: all green');
