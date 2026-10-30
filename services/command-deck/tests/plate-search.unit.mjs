/**
 * Officer-only full-mark lookup unit test (FIX-C-PLATESEARCH; FIX-E-LOOKUP
 * tightened the offer and the presenter; SPEC §8.1, §9, §16.4 — "any plate,
 * once an officer is named").
 *
 *   node tests/plate-search.unit.mjs
 *
 * esbuild bundles the REAL modules — workspace/search.ts (isFullMark,
 * lookupOfferActive, the unchanged watchlist search), workspace/mask.ts
 * (read-only: hasRawMark for parity), workspace/vehicle-lookup.ts (the
 * client + presenter) and the i18n packs (`$lib` aliased to src/lib, the
 * tests/plates.unit.mjs pattern) — in memory, nothing written to disk —
 * with globalThis.fetch swapped for a stub that records the request, and
 * asserts, hermetically:
 *
 *   1. isFullMark's truth table: a COMPLETE mark in any case or spelling
 *      (space, dash, dot — what normMark strips), 1–4 trailing digits, no
 *      series, a month-series, and the BH series — and NOT a prefix, a
 *      short string, a date, or a query whose separators the oracle refuses
 *      ("/", "_": mirrored plates.py, so a full mark here is a 422-free
 *      mark there);
 *   2. the offer's gate (lookupOfferActive): officer × full mark × the mask's
 *      STATE-CODE mark rule on the raw text (audit E round 2 — round 1 used
 *      hasRawMark, whose upper-case superset pass still offered "ON 12 OCT
 *      2026" and refused "MH01AB123"): a date phrase is never offered ("on 12
 *      oct 2026", and its all-caps spellings), every mark spelling and the BH
 *      series are;
 *      never a command query (mark: null), never a prefix, never without an
 *      officer; TRUE for the PRIMARY case of a full mark with NO watchlist
 *      match (search() sets mark, groups: []);
 *   3. no officer → today's behaviour exactly: a full mark matches the
 *      watchlist only (never reads or recommendations), the offer stays
 *      off, and the stubbed fetch is NEVER called (the offer's run() is
 *      the omnibar's only call path and lookupOfferActive gates it);
 *   4. parity with mask.ts's hasRawMark, RE-SCOPED to the rows where the
 *      two rules are one rule (real state code, 4-digit number, separators
 *      space/dash/dot): the contract's full-table pin is unpassable —
 *      mask.ts structurally refuses BH series, 1–3-digit numbers and
 *      non-state heads that plates.py accepts (CONTRACT.md risk note;
 *      13/39 shared rows disagree, proven in
 *      evidence/FIX-C-PLATESEARCH/scratch/parity-check.mjs) — so isFullMark
 *      (the oracle's mirror) is the gate and parity is asserted where the
 *      mask is the authority: every mark the mask would leave raw on the
 *      console is a full mark, and everything both refuse stays refused;
 *   5. the stubbed-fetch path (vehicle-lookup.ts — the deck proxies
 *      /api/v1 and hooks.server.ts attaches x-sajag-officer server-side, so
 *      the request is a same-origin relative GET with NO client-set
 *      officer header): 200-found renders the unmasked mark, the watchlist
 *      line with the HUMAN basis label (never the raw enum), the ALWAYS
 *      dated lawful reads and the quiet "Lookup recorded by <officer> ·
 *      <time>" line from the response's audit object; 200-not-found; the
 *      no-basis note through its TRANSLATED key; a 422 through the
 *      translated invalid-mark copy (never the server detail); 409 renders
 *      the officer-required copy and never a mark; a missing route (the
 *      sandbox oracle runs main's code), a non-JSON body and a network drop
 *      degrade to an honest error state — never a throw.
 *
 * The Svelte wiring (the offer's section, the mark-empty guard that
 * unlocks it and the result block's markup) is pinned by
 * tests/omnibar-lookup.unit.mjs and shown on the dev deck — this unit test
 * covers the logic it calls.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const show = (rows, max = 6) => rows.slice(0, max).join(' | ') + (rows.length > max ? ` | … ${rows.length - max} more` : '');

// ─── bundle the real modules (in memory) ────────────────────────────────────

const esbuild = createRequire(path.join(DECK, 'package.json'))('esbuild');
const ENTRY = `
import './src/lib/i18n/packs';
export * as search from './src/lib/workspace/search';
export * as mask from './src/lib/workspace/mask';
export * as lookup from './src/lib/workspace/vehicle-lookup';
export { t } from './src/lib/i18n/strings';
`;
const built = await esbuild.build({
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'plate-search-entry.ts' },
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	write: false,
	logLevel: 'silent',
});
ok('bundle builds (esbuild, $lib aliased, in memory)', built.errors.length === 0 && built.outputFiles.length === 1, built.errors.map((e) => e.text).join('; ') || 'search.ts + mask.ts + vehicle-lookup.ts + i18n packs');

// Svelte 5 runes are compiler macros: identity stubs (the workspace.unit.mjs pattern)
globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });

const { search: SR, mask: MK, lookup: VL, t } = await import(`data:text/javascript;base64,${Buffer.from(built.outputFiles[0].text).toString('base64')}`);

// ─── the stubbed fetch (the omnibar's only network path is lookupVehicle) ───

const calls = [];
let responder = null;
globalThis.fetch = async (url, init) => {
	calls.push({ url: String(url), init });
	if (!responder) throw new Error(`unexpected fetch: ${url}`);
	return responder(String(url), init);
};
const json = (status, body) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

// ─── 1. isFullMark: the oracle's plates.py, mirrored ────────────────────────

const FULL = [
	'MH47EM9001', 'mh47em9001', 'Mh47Em9001', 'mh 47 em 9001', 'Mh 47 Em 9001', 'MH-01-AB-1234', 'mh-01-xx-0007',
	'MH.47.EM.9001', 'mh.47.em.9001', 'MH - 47 - EM - 9001', 'mH01.xX 0007', 'mh 01-xx 0007',
	'tg09ab1234', 'Dl3CAB1234', 'mh12ab1234', 'up14ab2211', 'mh1a1234', 'mh 1 2345', 'TN 9 1234',
	'dl8sep1234', 'ka05may1234', 'MH.01.MAY.1234', 'MH.12.JAN.4321', 'mh01oct1234',
	'MH47EM901', 'MH47EM9', // 1–3-digit numbers are plates.py marks too
	'22BH1234AA', '22BH1234A', '22bh1234aa', // the BH series
	'mh06', 'on 12 oct 2026', // plates.py accepts these after its own normalisation (MH-2-7, ON-12-OCT-2026): the mirror must too
];
const NOT_FULL = [
	'MH06EM', 'MH47EM9?', 'wb', 'J15', 'em-cam', 'strand road', // prefixes without a number, words
	'24 Oct 2026', '2026-10-24', // the oracle refuses these shapes (a leading number)
	'MH/47/EM/9001', 'mh/12/ab/1234', 'MH_47_EM_9001', 'ka_05_mm_1234', // the oracle 422s "/" and "_"
	'ZZ01AB1234A', 'MH47EM12345', '22BH1234', '22BH1234AAA', // one element short or long
];
const fullBad = FULL.filter((q) => !SR.isFullMark(q)).map((q) => `${q} → false`);
ok('isFullMark: a complete mark in any case or spelling, 1–4 trailing digits, month series and BH series', fullBad.length === 0, show(fullBad) || `${FULL.length} spellings`);
const notFullBad = NOT_FULL.filter((q) => SR.isFullMark(q)).map((q) => `${q} → true`);
ok('isFullMark: prefixes, words, dates, "/" and "_" (the oracle refuses them) and one-element-off shapes are not full marks', notFullBad.length === 0, show(notFullBad) || `${NOT_FULL.length} refusals`);

// ─── 2. the offer's gate ────────────────────────────────────────────────────

// a watchlisted vehicle and rows that must never match a mark query
const WATCHED = { kind: 'vehicle', urn: 'vehicle:00000000-0000-4000-8000-000000000007', id: '00000000-0000-4000-8000-000000000007', label: 'MH01XX•••7', props: { plate: 'MH01XX0007', plate_masked: 'MH01XX•••7' } };
const READ_OF_IT = { kind: 'sighting', urn: 'sighting:00000000-0000-4000-8000-000000000008', id: '00000000-0000-4000-8000-000000000008', label: 'EM-CAM-01', props: { plate: 'MH01XX0007', camera_id: 'EM-CAM-01' } };
const REC_OF_IT = { kind: 'recommendation', urn: 'recommendation:00000000-0000-4000-8000-000000000009', id: '00000000-0000-4000-8000-000000000009', label: 'Speeding on segment · EM-CAM-03', props: { plate: 'MH01XX0007', rule_id: 'R_SPD_SEGMENT' } };
const ROWS = [WATCHED, READ_OF_IT, REC_OF_IT];

const fullResult = SR.search(ROWS, 'MH01XX0007');
const emptyMarkResult = SR.search(ROWS, 'MH47EM9001'); // a full mark nothing watches
const prefixResult = SR.search(ROWS, 'MH01XX');
const commandResult = SR.search(ROWS, 'fly to MH01XX0007'); // commands return mark: null
ok(
	'lookupOfferActive: officer × full mark — true even with no watchlist match (the primary case), and for a watched one',
	SR.lookupOfferActive(emptyMarkResult, 'MH47EM9001', true) === true && SR.lookupOfferActive(fullResult, 'MH01XX0007', true) === true && SR.lookupOfferActive(emptyMarkResult, 'mh 47 em 9001', true) === true,
	`watched: ${fullResult.mark?.matches.length} match(es) · unwatched: ${emptyMarkResult.mark?.matches.length}`,
);
ok(
	'lookupOfferActive: never without an officer, never for a prefix, never for a command query',
	!SR.lookupOfferActive(fullResult, 'MH01XX0007', false) && !SR.lookupOfferActive(emptyMarkResult, 'MH47EM9001', false) && !SR.lookupOfferActive(prefixResult, 'MH01XX', true) && !SR.lookupOfferActive(commandResult, 'fly to MH01XX0007', true) && !SR.lookupOfferActive(null, 'J15', true),
	'commands and non-marks refuse on the query alone (FIX-E-LOOKUP: the gate no longer needs result.mark — the watchlist search never sets mark for a BH query, and the BH series must offer)',
);

// FIX-E-LOOKUP: a date phrase is never a vehicle lookup. isFullMark alone
// read "on 12 oct 2026" as ON-12-OCT-2026 (a month-series mark); round 1
// added the RAW mark shape (mask.ts's hasRawMark) — but its upper-case
// superset pass still OFFERED the all-caps spellings ("ON 12 OCT 2026") and
// refused 1–3-digit marks plates.py accepts ("MH01AB123"). Round 2 (audit E)
// bases the offer on the mask's STATE-CODE rule instead: the truth rows below
// are the auditor's, verbatim.
const DATES = ['on 12 oct 2026', 'on 12 Oct 2026', 'up 12 dec 2026', 'UP 12 dec 2026', 'dl 8 sep 1234', 'ON 12 OCT 2026', 'ON 1 OCT 2026', 'BY 12 JAN 2027'];
const dateBad = DATES.filter((q) => SR.lookupOfferActive(SR.search(ROWS, q), q, true));
ok(
	'dates are never offered, in any case (the upper-case spellings the mask\'s superset pass used to offer included)',
	dateBad.length === 0,
	show(dateBad) || `${DATES.length} date phrases refused`,
);
const STILL_OFFER = ['MH47EM9001', 'mh 47 em 9001', 'DL 8 SEP 1234', 'dl8sep1234', '22BH1234AA', '22bh1234aa', 'MH01AB123', 'MH 1 AB 1', 'MH 01 1234', 'MH011234'];
const stillBad = STILL_OFFER.filter((q) => !SR.lookupOfferActive(SR.search(ROWS, q), q, true));
ok('the raw-mark shape and the BH series still offer: 1–4-digit marks (the auditor\'s MH01AB123/MH 1 AB 1 rows) and every BH spelling', stillBad.length === 0, show(stillBad) || `${STILL_OFFER.length} spellings kept`);

// ─── 3. no officer: today's behaviour exactly ───────────────────────────────

ok(
	'a full mark still matches the watchlist only (never reads or recommendations), shown masked',
	!!fullResult.mark && fullResult.total === 1 && fullResult.groups.length === 1 && fullResult.groups[0].kind === 'vehicle' && fullResult.groups[0].items[0].urn === WATCHED.urn && fullResult.groups[0].items[0].label === 'MH01XX•••7',
	`${fullResult.total} match: ${fullResult.groups.flatMap((g) => g.items.map((r) => r.kind)).join(',')}`,
);
const offerOffBad = [...FULL, 'MH01XX0007'].filter((q) => SR.lookupOfferActive(SR.search(ROWS, q), q, false));
ok('no officer named: the offer stays off for every mark spelling (and fetch was never called)', offerOffBad.length === 0 && calls.length === 0, show(offerOffBad) || `${FULL.length + 1} spellings, 0 fetches`);

// ─── 4. parity with mask.ts's hasRawMark, re-scoped ─────────────────────────
// Where the two rules are one rule — a real state code, a 4-digit number, separators
// space/dash/dot (what normMark strips for the oracle) — every spelling the mask
// would leave raw on the console is a full mark. Outside that scope they differ BY
// DESIGN (BH series, 1–3-digit numbers, non-state heads: plates.py accepts, the
// mask refuses; "/" and "_": the mask accepts, plates.py refuses) — see the header.

const PARITY_RAW = FULL.filter((q) => /^[A-Za-z0-9\s.\-]*$/.test(q)).filter((q) => {
	const n = q.replace(/[\s.\-]/g, '').toUpperCase();
	return MK.STATE_CODES.includes(n.slice(0, 2)) && !/^\d{2}BH/.test(n) && /\d{4}$/.test(n);
});
const parityBad = PARITY_RAW.filter((q) => MK.hasRawMark(q) !== SR.isFullMark(q) || !MK.hasRawMark(q)).map((q) => `${q}: hasRawMark=${MK.hasRawMark(q)} isFullMark=${SR.isFullMark(q)}`);
ok('parity: every raw-mark spelling the mask recognises (real state code, 4-digit number, space/dash/dot) is a full mark', PARITY_RAW.length >= 20 && parityBad.length === 0, show(parityBad) || `${PARITY_RAW.length} rows agree`);
const PARITY_NEITHER = ['24 Oct 2026', '2026-10-24', 'J15', 'MH06EM', 'em-cam', 'ZZ01AB1234A', ''];
const neitherBad = PARITY_NEITHER.filter((q) => MK.hasRawMark(q) !== SR.isFullMark(q));
ok('parity: dates, prefixes and non-marks are refused by both', neitherBad.length === 0, show(neitherBad) || `${PARITY_NEITHER.length} rows refused`);

// ─── 5. the stubbed-fetch path ──────────────────────────────────────────────

const NOW = Date.UTC(2026, 9, 24, 12, 0, 0); // 17:30 IST, 24 Oct 2026
const LOOKED_AT = '2026-10-24T14:05:00Z'; // 19:35 IST, the same IST day
const istDay = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short' });
const istHm = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const dated = (iso) => `${istDay.format(Date.parse(iso))} ${istHm.format(Date.parse(iso))}`;
const NO_BASIS_NOTE = "No lawful basis to show this vehicle's camera reads — earmark it with a lawful basis to proceed";
const FOUND_BODY = {
	found: true,
	mark: 'MH47EM9001',
	mark_masked: 'MH47EM•••1',
	vehicle_id: '11111111-1111-4111-8111-111111111111',
	vehicle_class: 'car',
	earmark: { state: 'watch', reason: 'Stolen MH47EM9001 reported — FIR 4401/2026', lawful_basis: 'stolen_vehicle_fir', retention_until: '2026-11-23T00:00:00Z' },
	open_recommendations: [{ recommendation_id: '22222222-2222-4222-8222-222222222222', rule_id: 'R_SPD_SEGMENT', status: 'pending' }],
	open_pursuits: [{ event_id: '33333333-3333-4333-8333-333333333333', status: 'approved', recommendation_id: '22222222-2222-4222-8222-222222222222' }],
	disclosure: 'active_earmark',
	reads: [
		{ sighting_id: 's1', plate: 'MH47EM9001', camera_id: 'EM-CAM-03', t: '2026-10-24T13:00:00Z', position: [88.3499, 22.5582], speed_kmh: 95, heading: 180, vehicle_class: 'car', source: 'emulated_anpr', run_id: null, matched_plate_hit: true },
		{ sighting_id: 's2', plate: 'MH47EM9001', camera_id: 'EM-CAM-01', t: '2026-10-24T13:40:00Z', position: [88.3399, 22.5682], speed_kmh: 61, heading: 90, vehicle_class: 'car', source: 'emulated_anpr', run_id: null, matched_plate_hit: true },
	],
	note: null,
	source: 'emulated_anpr',
	audit: { officer: 'Duty Officer A', looked_up_at: LOOKED_AT, mark_masked: 'MH47EM•••1', found: true, disclosure: 'active_earmark' },
};
const NONE_BODY = { found: false, mark: 'MH47XX1234', mark_masked: 'MH47XX•••4', vehicle_id: null, vehicle_class: null, earmark: null, open_recommendations: [], open_pursuits: [], disclosure: 'none', reads: [], note: null, source: 'emulated_anpr', audit: { officer: 'Duty Officer A', looked_up_at: LOOKED_AT, mark_masked: 'MH47XX•••4', found: false, disclosure: 'none' } };
const NO_BASIS_BODY = { ...FOUND_BODY, earmark: null, disclosure: 'none', reads: [], note: NO_BASIS_NOTE, audit: { ...FOUND_BODY.audit, disclosure: 'none' } };
const OFFICER_REQUIRED_BODY = { detail: { error: 'officer-required', reason: 'x-sajag-officer header absent - a full-mark vehicle lookup is officer-only and audited; nothing was looked up and nothing was written' } };

// 5a. the found path: the request, and the block's lines
responder = () => json(200, FOUND_BODY);
const found = await VL.lookupVehicle('MH47EM9001');
ok(
	'the request is exactly GET /api/v1/vehicles/lookup?plate=<mark>, same-origin relative, with NO client-set officer header',
	calls.length === 1 && calls[0].url === '/api/v1/vehicles/lookup?plate=MH47EM9001' && !calls[0].init?.headers && !JSON.stringify(calls[0].init ?? {}).includes('x-sajag-officer'),
	`${calls[0]?.url} · init ${JSON.stringify(calls[0]?.init ?? {})}`,
);
const fv = VL.lookupView(found, 'en', NOW);
ok(
	'found: the block shows the unmasked mark (mono is the omnibar’s), the watchlist line with its HUMAN basis label (never the raw enum), the lawful reads and their rows',
	found.ok && fv.state === 'found' && fv.mark === 'MH47EM9001' && fv.heading === `Watchlisted · Stolen vehicle (FIR)` && !fv.heading.includes('stolen_vehicle_fir') && fv.reads === 2 && fv.readRows[0] === `EM-CAM-03 · ${dated('2026-10-24T13:00:00Z')}` && fv.readRows[0].includes('24 Oct'),
	`${fv.mark} · ${fv.heading} · ${fv.reads} reads · ${fv.readRows.join(' / ')}`,
);
ok(
	'found: the block serves the actions and the whole trail — the vehicle URN to open, the reads’ sighting URNs to highlight',
	fv.vehicleUrn === `vehicle:${FOUND_BODY.vehicle_id}` && fv.readUrns.join(',') === 'sighting:s1,sighting:s2' && fv.moreReads === null,
	`${fv.vehicleUrn} · ${(fv.readUrns ?? []).join(',')}`,
);
ok(
	'found: open recommendations and pursuits are counted, and the quiet "Lookup recorded" line carries the audit object’s officer and time',
	fv.recommendations === 1 && fv.pursuits === 1 && fv.recorded === `Lookup recorded by Duty Officer A at ${istHm.format(Date.parse(LOOKED_AT))}`,
	fv.recorded,
);
ok(
	'the offer’s label and the honest copies come from the pack (EN pinned; HI and MR registered too)',
	t('en', 'ws_lookup_offer', 'MH47EM9001') === 'Look up vehicle MH47EM9001' && t('hi', 'ws_lookup_offer', 'MH47EM9001').includes('MH47EM9001') && t('mr', 'ws_lookup_offer', 'MH47EM9001').includes('MH47EM9001') && ['ws_lookup_offer', 'ws_lookup_offer_detail', 'ws_lookup_running', 'ws_lookup_officer_required', 'ws_lookup_error', 'ws_lookup_none', 'ws_lookup_watchlist', 'ws_lookup_unwatched', 'ws_lookup_reads', 'ws_lookup_recommendations', 'ws_lookup_pursuits', 'ws_lookup_recorded', 'ws_lookup_heading', 'ws_lookup_k_mark', 'ws_lookup_k_status', 'ws_lookup_open_vehicle', 'ws_lookup_show_trail', 'ws_lookup_more_reads', 'ws_lookup_nobasis', 'ws_lookup_invalid_plate', 'ws_basis_stolen_vehicle_fir'].every((k) => ['en', 'hi', 'mr'].every((l) => t(l, k, 'M', 'T') !== k)),
);

// 5b. not found
responder = () => json(200, NONE_BODY);
const none = await VL.lookupVehicle('MH47XX1234');
const nv = VL.lookupView(none, 'en', NOW);
ok('not found: the honest sentence, the officer’s own mark, no reads, still recorded', none.ok && nv.state === 'none' && nv.mark === 'MH47XX1234' && nv.heading === t('en', 'ws_lookup_none') && nv.reads === null && nv.readRows.length === 0 && nv.vehicleUrn === null && nv.recorded === `Lookup recorded by Duty Officer A at ${istHm.format(Date.parse(LOOKED_AT))}`, nv.heading);

// 5c. found but no lawful basis: the note through its translated key, zero reads
responder = () => json(200, NO_BASIS_BODY);
const nobasis = await VL.lookupVehicle('MH47EM9001');
const bv = VL.lookupView(nobasis, 'en', NOW);
const bvHi = VL.lookupView(nobasis, 'hi', NOW);
ok(
	'no lawful basis: reads [] and the note through the TRANSLATED key (EN identical to the server sentence; HI and MR in their own words, never the EN sentence) — identity and counts still shown',
	bv.state === 'found' && bv.reads === null && bv.readRows.length === 0 && bv.note === t('en', 'ws_lookup_nobasis') && bv.note === NO_BASIS_NOTE && bvHi.note === t('hi', 'ws_lookup_nobasis') && bvHi.note !== NO_BASIS_NOTE && t('mr', 'ws_lookup_nobasis') !== NO_BASIS_NOTE && bv.mark === 'MH47EM9001' && bv.recommendations === 1,
	bv.note,
);

// 5d. 409: the officer-required copy, never a mark
responder = () => json(409, OFFICER_REQUIRED_BODY);
const gate = await VL.lookupVehicle('MH47EM9001');
const gv = VL.lookupView(gate, 'en', NOW);
ok(
	'409 officer-required: officerRequired flagged, the honest copy rendered, never a mark, nothing recorded',
	!gate.ok && gate.httpStatus === 409 && gate.officerRequired === true && gv.state === 'officer-required' && gv.mark === null && gv.heading === t('en', 'ws_lookup_officer_required') && !gv.heading.includes('MH47EM9001') && gv.recorded === null,
	gv.heading,
);

// 5d2. 422: the translated invalid-mark copy — never the server detail
// (pre-FIX-E the 422 detail echoed the input and named a full mark)
responder = () => json(422, { detail: "not a registration plate: 'mh 12 oct 2026!' (expected e.g. MH47EM9001 or a BH-series plate such as 22BH1234AA)" });
const invalid = await VL.lookupVehicle('mh 12 oct 2026!');
const iv = VL.lookupView(invalid, 'en', NOW);
ok(
	'422: the translated invalid-mark copy — never the server detail, never the input, never a full mark',
	!invalid.ok && invalid.httpStatus === 422 && iv.state === 'error' && iv.detail === t('en', 'ws_lookup_invalid_plate') && !iv.detail.includes('mh 12 oct 2026!') && !iv.detail.includes('MH47EM9001') && !iv.detail.includes('22BH1234AA'),
	iv.detail,
);

// 5e. a missing route and a broken transport degrade honestly — never a throw
responder = () => json(404, { detail: 'Not Found' });
const missing = await VL.lookupVehicle('MH47EM9001');
const mv = VL.lookupView(missing, 'en', NOW);
ok('route missing (the sandbox oracle runs main’s code): "Lookup failed" + the server’s detail, never a mark, never a crash', !missing.ok && missing.httpStatus === 404 && missing.officerRequired !== true && mv.state === 'error' && mv.heading === 'Lookup failed' && mv.mark === null && mv.detail === 'Not Found', `${mv.heading}: ${mv.detail}`);
responder = () => new Response('<html>502 bad gateway</html>', { status: 502 });
const html = await VL.lookupVehicle('MH47EM9001');
const hv = VL.lookupView(html, 'en', NOW);
ok('a non-JSON body (a proxy error page): the error state with the text as the detail, no throw', !html.ok && html.httpStatus === 502 && hv.state === 'error' && hv.detail === '<html>502 bad gateway</html>', hv.detail);
responder = () => Promise.reject(new Error('network down'));
const down = await VL.lookupVehicle('MH47EM9001');
const dv = VL.lookupView(down, 'en', NOW);
ok('a network drop: httpStatus 0, the error state, never a throw', !down.ok && down.httpStatus === 0 && down.detail === 'network down' && dv.state === 'error' && dv.mark === null, down.detail);

// 5f. with no officer the omnibar never calls fetch: the gate is false for every
// spelling (group 3), and the only caller of lookupVehicle is the offer's run()
// (Omnibar.svelte gates it behind lookupOffer) — the counter above stayed 0 until
// this section's explicit calls; the officer-side calls are all accounted for.
const explicit = calls.length;
ok('every fetch this test made was the explicit officer-side call above (none leaked from search/gating)', explicit === 8, `${explicit} calls`);

if (failures) {
	console.error(`\n${failures} check(s) failed`);
	process.exit(1);
}
console.log('\nok   plate search — officer × full mark offers the audited lookup (dates never); no officer keeps the frozen watchlist-only search; the stubbed path renders found/none/no-basis/422/409/missing honestly');
process.exit(0);
