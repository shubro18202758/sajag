/**
 * Workspace core unit test (UI-S2; SPEC §7, §8.1, §12.6; plan X4–X6, X12, R24, R27).
 *
 *   node tests/workspace.unit.mjs
 *
 * esbuild bundles the REAL modules — gods-eye/city-api.ts, entities/
 * selection.svelte.ts, and src/lib/workspace/{objects, selectors, display,
 * vocabulary, search, hash, registry, workspace.svelte, relations} with the
 * inspector's pure model — with `$lib` aliased to src/lib; `$state` is an
 * identity stub so the rune classes run as plain classes (the canvas-bus
 * pattern). providers.ts is never bundled (esbuild has no import.meta.glob).
 *
 * The selector fixture is tests/fixtures/workspace/captured.json (the
 * prototype's emulated, masked capture, reduced; committed so CI runs it).
 *
 * Asserts: the selectors reconcile on the fixture (linked = Σ groups = 51;
 * table rows = (selection ∪ linked) ∩ filters; units counted once from two
 * sources; reads 21; feedIn 189; watchReads 19; linked feed 54; the registry
 * counts); relName from both ends with the OSINT pairs, never "Linked", and
 * on the graph a promoted report reads "Promoted to" / "Promoted from" and a
 * corroborated event "Corroborates" / "Corroborated by" from snapshot rows
 * alone; the display layer and every exemption, brief() classifying
 * enforcement rows on structured fields and the oracle's fixed openings
 * (never the officer's note), in EN/HI/MR; the omnibar (matched span, full
 * marks against the watchlist only, the honest empty state verbatim, a
 * haystack free of raw marks on rows that carry one, < 5 ms a keystroke);
 * inWindow with protected objects; the multi-select API; the share hash with
 * hostile values and masked egress — a mark typed in lower case, mixed case
 * or with dots or spaces is masked in a filter label, the share hash, a
 * saved view, a watch and a name, and carriesRawMark() refuses it; Explore
 * never labels a filter with a typed mark; officer notes reach the Activity
 * row's full text byte for byte (props.note or the oracle's fixed words),
 * the oracle's words before them humanised; the X4 coercion; registry multiplicity
 * (R27); the store API (X6) with saved views composing the page hash; the
 * navbar-officer read (X12); the inspector's model (key figures: 2–4 or
 * none, no empty figure, a time off the anchor day carries its day); the
 * fixture's ethics; and that no separator space in the workspace's markup
 * sits where the Svelte compiler drops it.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import { mkdirSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { WORKSPACE } from './lib/routes.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const OUT = path.join(HERE, 'artifacts', 'workspace-bundle.mjs');
const FIXTURE = path.join(HERE, 'fixtures', 'workspace', 'captured.json');

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
export * as cityApi from './src/lib/gods-eye/city-api';
export * as sel from './src/lib/gods-eye/entities/selection.svelte';
export * as objects from './src/lib/workspace/objects';
export * as selectors from './src/lib/workspace/selectors';
export * as display from './src/lib/workspace/display';
export * as vocab from './src/lib/workspace/vocabulary';
export * as search from './src/lib/workspace/search';
export * as hash from './src/lib/workspace/hash';
export * as mask from './src/lib/workspace/mask';
export * as sv from './src/lib/workspace/saved-views';
export * as registry from './src/lib/workspace/registry';
export * as ws from './src/lib/workspace/workspace.svelte';
export * as relations from './src/lib/workspace/relations';
export * as model from './src/lib/workspace/components/inspector/model';
export * as officer from './src/lib/workspace/components/inspector/officer';
export * as adapters from './src/lib/workspace/kinds';
export * as packs from './src/lib/i18n/packs.workspace';
export { commandBar } from './src/lib/shell/command-bar.svelte';
export { t } from './src/lib/i18n/strings';
`;
const built = await esbuild.build({
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'workspace-entry.ts' },
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	outfile: OUT,
	logLevel: 'silent',
});
ok('bundle builds (esbuild, $lib aliased; providers.ts left out)', built.errors.length === 0, `${built.errors.length} errors`);

// Svelte 5 runes are compiler macros: identity stubs run the stores as plain classes.
globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });

const M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
const { cityApi, sel, objects, selectors: S, display: D, vocab, search: SR, hash: H, mask: MK, sv: SV, registry: R, ws, relations, model, officer, packs, commandBar, adapters, t: tr } = M;
const { selection } = sel;

// ─── the fixture (committed; never the prototype's directory) ───────────────

ok('the fixture is the committed file', FIXTURE.endsWith(path.join('tests', 'fixtures', 'workspace', 'captured.json')) && !FIXTURE.includes('sajag-orchestration'), path.relative(DECK, FIXTURE));
const RAW = readFileSync(FIXTURE, 'utf8');
const FX = JSON.parse(RAW);
ok('fixture ≤ 150 KB', Buffer.byteLength(RAW) <= 150 * 1024, `${(Buffer.byteLength(RAW) / 1024).toFixed(1)} KB`);

// ethics: no person key, every human actor the fictional Sandbox Officer, no raw mark
const PERSON_KEY_RE = /author|person|handle|username|byline|reporter|poster|uploader|suspect|accused|victim|owner|driver_name|face|biometric|individual_/i;
const EXEMPT_KEYS = new Set(['touches_persons', 'surface_forms', 'surfaced']);
const OPAQUE_ID_RE = /^(?:[0-9a-f]{40}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/;
const RAW_MARK_RE = /\b[A-Z]{2}[ -]?\d{1,2}[ -]?(?:[A-Z]{1,3}[ -]?)?\d{4}\b/;
const badKeys = [];
const humans = new Set();
let rawMarks = 0;
let plateKeys = 0;
(function walk(o) {
	if (Array.isArray(o)) return o.forEach(walk);
	if (o && typeof o === 'object') {
		for (const [k, v] of Object.entries(o)) {
			if (!EXEMPT_KEYS.has(k) && !OPAQUE_ID_RE.test(k) && PERSON_KEY_RE.test(k)) badKeys.push(k);
			if (k === 'plate') plateKeys++;
			walk(v);
		}
		if (o.actor_kind === 'human') humans.add(o.actor);
		for (const k of ['decided_by', 'requested_by', 'opened_by', 'officer']) if (typeof o[k] === 'string') humans.add(o[k]);
	} else if (typeof o === 'string' && RAW_MARK_RE.test(o)) rawMarks++;
})(FX);
ok('fixture: no key matches the person-key regex', badKeys.length === 0, badKeys.join(', ') || 'clean');
ok('fixture: every human actor and officer value is "Sandbox Officer"', humans.size === 1 && humans.has('Sandbox Officer'), [...humans].join(' | '));
ok('fixture: marks masked, no raw-mark field', rawMarks === 0 && plateKeys === 0, `${rawMarks} raw marks, ${plateKeys} plate keys`);

// the wire → the parsers → the graph (a dossier audit entry that is a string is a feed row's id)
const NOW = Date.parse(FX.as_of);
const V = FX.vehicle;
const feedById = new Map(FX.feed.items.map((i) => [i.id, i]));
const SNAP = cityApi.parseCitySnapshot(FX.snapshot);
const DOSSIERS = FX.dossiers.map((d) => cityApi.parseDossier({ ...d, audit: d.audit.map((a) => (typeof a === 'string' ? feedById.get(a) : a)) }, NOW));
const FEED = cityApi.parseFeedRows(FX.feed);
ok('fixture parses (snapshot, dossiers, feed)', SNAP.entities.length > 0 && DOSSIERS.every(Boolean) && FEED.length === FX.feed.items.length, `${SNAP.entities.length} entities · ${DOSSIERS.length} dossiers · ${FEED.length} feed rows`);
const G = objects.buildObjectGraph({ entities: SNAP.entities, dossiers: DOSSIERS });
const REGISTRY_ROWS = SNAP.entities.map((e) => G.get(e.urn)).filter(Boolean);
const world = { graph: () => G, registry: () => REGISTRY_ROWS, feed: () => FEED, units: () => R.unitSourceRows(), now: () => NOW };
const Q = S.createSelectors(() => world);

// ─── 1. canonical selectors reconcile (SPEC §7.4) ───────────────────────────

const linked = Q.linked(V);
const groups = Q.linkGroups(V);
const sigma = [...groups.values()].reduce((n, g) => n + g.length, 0);
const byRel = Object.fromEntries([...groups.entries()].map(([k, v]) => [k, v.length]));
ok('linked(MH47EM•••1) = 51', linked.length === 51, `${linked.length}`);
ok('linked = Σ groups', sigma === linked.length, `Σ ${sigma}`);
ok('groups: 21 reads, 6 cameras, 22 recommendations, 2 pursuits', eq(byRel, { sighting: 21, seen_by_camera: 6, recommendation: 22, pursuit: 2 }) || (byRel.sighting === 21 && byRel.seen_by_camera === 6 && byRel.recommendation === 22 && byRel.pursuit === 2), JSON.stringify(byRel));
ok('the selection itself is never in linked', !linked.some((o) => o.urn === V));
ok('reads(vehicle) = 21 lawful reads, oldest first', Q.reads(V).length === 21 && Q.reads(V).every((r, i, a) => i === 0 || (a[i - 1].t ?? 0) <= (r.t ?? 0)));
const sixH = NOW - 6 * 3600e3;
ok('feedIn(6 h) = 189 ("Rows in view")', Q.feedIn(sixH, NOW).length === 189, `${Q.feedIn(sixH, NOW).length}`);
ok('watchReads(24 h) = 19', Q.watchReads(NOW - 24 * 3600e3, NOW).length === 19, `${Q.watchReads(NOW - 24 * 3600e3, NOW).length}`);
ok('linkedFeedIn(6 h) = 54 ("Linked")', Q.linkedFeedIn(V, sixH, NOW).length === 54, `${Q.linkedFeedIn(V, sixH, NOW).length}`);
// the fixture's registry snapshot holds 1 vehicle, 8 sightings, 6 cameras and 8 recommendations (the dossiers add
// older reads and decisions, which count(kind) must NOT count: it is the layer tree's number)
const regCounts = Object.fromEntries(['vehicle', 'sighting', 'camera', 'recommendation', 'event'].map((k) => [k, Q.count(k)]));
ok('count(kind) is the registry snapshot\'s count, not the graph\'s (1 vehicle, 8 sightings, 6 cameras, 8 recommendations, 0 events)', eq(regCounts, { vehicle: 1, sighting: 8, camera: 6, recommendation: 8, event: 0 }) && G.byKind('sighting').length > 8, `${JSON.stringify(regCounts)} · graph sightings ${G.byKind('sighting').length}`);
ok('scope words in labels', S.linkedLabel(51) === '51 linked' && S.readsLabel(21) === 'Reads 21' && S.inWindowLabel(18, 51) === '18 of 51 linked in window' && S.inViewLabel(189) === 'Rows in view 189' && S.decisionsLabel(1) === '1 decision' && S.watchReadsLabel(19) === '19 watchlist reads, 24 h' && S.countLabel('sighting', 22) === 'Sightings 22');

// ─── 2. relations named from both ends (X5) ─────────────────────────────────

const rn = relations.relName;
const PAIRS = [
	['vehicle', 'sighting', null, 'Lawful reads'],
	['sighting', 'vehicle', null, 'Vehicle'],
	['vehicle', 'camera', null, 'Seen by cameras'],
	['camera', 'vehicle', null, 'Vehicles seen'],
	['vehicle', 'event', null, 'Pursuits'],
	['event', 'vehicle', null, 'Pursued vehicle'],
	['recommendation', 'sighting', null, 'Evidence read'],
	['sighting', 'recommendation', null, 'Recommendations'],
	['camera', 'sighting', null, 'Recent watchlist hits'],
	['osint_event', 'place', null, 'Reported at'],
	['place', 'osint_event', null, 'Reports here'],
	['osint_event', 'event', null, 'Corroborates'],
	['osint_event', 'event', 'promoted_to', 'Promoted to'],
	['event', 'osint_event', null, 'Corroborated by'],
	['event', 'osint_event', 'promoted_from', 'Promoted from'],
	['osint_event', 'segment', null, 'On road'],
	['osint_event', 'junction', null, 'At junction'],
];
const pairBad = PAIRS.filter(([a, b, h, want]) => rn(a, b, h) !== want).map(([a, b, h, want]) => `${a}→${b}${h ? `(${h})` : ''}=${rn(a, b, h)} want ${want}`);
ok('relName from both ends, with the OSINT pairs', pairBad.length === 0, pairBad.join(' | ') || `${PAIRS.length} pairs`);
ok(
	'reverse of a named variant: promoted_to ↔ promoted_from, corroborates ↔ corroborated_by',
	relations.reverseRel('promoted_to', 'osint_event', 'event') === 'promoted_from' && relations.reverseRel('corroborates', 'osint_event', 'event') === 'corroborated_by',
);
// X5 on the graph, from snapshot rows alone (no dossier): a report PROMOTED to an event reads "Promoted to" /
// "Promoted from", the live event it CORROBORATES reads "Corroborates" / "Corroborated by" — even when the
// snapshot's own unnamed links between the same objects arrive first
const RPT = '7a1c2a9e-3b7d-4e21-9a55-0c8e7d4b1f21';
const PROMOTED = '8b2d3b0f-4c8e-4f32-8b66-1d9f8e5c2a31';
const LIVE = '9c3e4c1a-5d9f-4a43-9c77-2e0a9f6d3b41';
const RU = `osint_event:${RPT}`;
const PU = `event:${PROMOTED}`;
const LU = `event:${LIVE}`;
const osintGraph = (withLinks) =>
	objects.buildObjectGraph({
		entities: [
			{ kind: 'osint_event', id: RPT, label: 'Road accident · Sector V - New Town link', source: 'osint', verification_state: 'NEWS-REPORTED', links: withLinks ? [PU, LU] : [], props: { promoted_event_id: PROMOTED, attach: { novel: false, corroborates_live_urn: LU } } },
			{ kind: 'event', id: PROMOTED, label: 'Road accident on the New Town link', source: 'live', links: withLinks ? [RU] : [], props: { event_kind: 'road_accident', status: 'active' } },
			{ kind: 'event', id: LIVE, label: 'Metro work zone', source: 'live', links: withLinks ? [RU] : [], props: { event_kind: 'work_zone', status: 'active' } },
		].map((e) => cityApi.parseCityEntity(e)),
	});
const relOf = (g, a, b) => g.links(a).find((l) => l.row.urn === b)?.relation ?? 'none';
const osintCases = [true, false].map((withLinks) => {
	const g = osintGraph(withLinks);
	return [relOf(g, RU, PU), relOf(g, PU, RU), relOf(g, RU, LU), relOf(g, LU, RU)].join(',');
});
ok(
	'a promoted report: "Promoted to" / "Promoted from"; the corroborated live event: "Corroborates" / "Corroborated by" (snapshot links first, or none)',
	osintCases.every((c) => c === 'promoted_to,promoted_from,corroborates,corroborated_by') &&
		relations.relLabel('promoted_to', 'event') === 'Promoted to' &&
		relations.relLabel('promoted_from', 'osint_event') === 'Promoted from' &&
		relations.relLabel('corroborates', 'event') === 'Corroborates' &&
		relations.relLabel('corroborated_by', 'osint_event') === 'Corroborated by',
	osintCases.join(' | '),
);
const fromEvent = objects.buildObjectGraph({
	entities: [
		{ kind: 'osint_event', id: RPT, label: 'Road accident · Sector V - New Town link', source: 'osint', links: [PU] },
		{ kind: 'event', id: PROMOTED, label: 'Road accident on the New Town link', links: [RU], props: { event_kind: 'road_accident', provenance: { osint_event_id: RPT } } },
	].map((e) => cityApi.parseCityEntity(e)),
});
ok('…and from the event\'s side alone (provenance.osint_event_id): "Promoted from" / "Promoted to"', relOf(fromEvent, PU, RU) === 'promoted_from' && relOf(fromEvent, RU, PU) === 'promoted_to', `${relOf(fromEvent, PU, RU)} / ${relOf(fromEvent, RU, PU)}`);
const byDossier = objects.buildObjectGraph({
	dossiers: [cityApi.parseDossier({ entity: { kind: 'osint_event', id: RPT, label: 'Road accident · Sector V - New Town link', props: { promoted_event_id: PROMOTED } }, related: [{ relation: 'corroborates', entity: { kind: 'event', id: PROMOTED, label: 'Road accident on the New Town link' } }], audit: [] }, NOW)],
});
ok('the oracle\'s dossier relation still outranks what the props imply', relOf(byDossier, RU, PU) === 'corroborates' && relOf(byDossier, PU, RU) === 'corroborated_by', `${relOf(byDossier, RU, PU)} / ${relOf(byDossier, PU, RU)}`);
const kinds = cityApi.ENTITY_KINDS;
const linkedNamed = [];
for (const a of kinds) for (const b of kinds) {
	const name = rn(a, b);
	if (!name || /^linked$/i.test(name)) linkedNamed.push(`${a}→${b}`);
}
ok('no pair of kinds is ever named "Linked"', linkedNamed.length === 0, linkedNamed.join(', ') || `${kinds.length ** 2} pairs`);
const readUrns = new Set(Q.reads(V).map((r) => r.urn));
const misfiled = G.links(V).filter((l) => l.row.kind === 'sighting' && l.relation !== 'sighting');
ok('every read of the vehicle is under its reads (never "Linked")', misfiled.length === 0 && readUrns.size === 21, misfiled.map((l) => l.relation).join(', ') || 'all under "sighting"');

// ─── 3. the display layer (SPEC §3.4) ───────────────────────────────────────

const titleCases = [
	['PURSUIT — stolen MH47EM•••1 (FIR 4401/2026, Hare Street PS)', 'Pursuit of MH47EM•••1'],
	['TIER-0 GATE TEST · VVIP MOVEMENT TO AIRPORT', 'VVIP movement to airport'],
	['ACCEPTANCE TEST — Metro work zone (Emulated)', 'Metro work zone'],
	['Visarjan procession (Emulated)', 'Visarjan procession'],
	['escort · VVIP movement — smoke escort', 'Escort · VVIP movement — smoke escort'],
	['Closure on Sector V - New Town link (northbound))', 'Closure on Sector V - New Town link (northbound)'],
];
const titleBad = titleCases.filter(([raw, want]) => D.displayTitle(raw) !== want).map(([raw, want]) => `"${raw}" → "${D.displayTitle(raw)}" want "${want}"`);
ok('displayTitle: test labels, (Emulated), pursuits, ALL-CAPS, ))', titleBad.length === 0, titleBad.join(' | ') || `${titleCases.length} titles`);
const pp = D.titleParts('PURSUIT — stolen MH47EM•••1 (FIR 4401/2026, Hare Street PS)');
ok('the pursuit title moves its FIR to Properties', pp.fir === '4401/2026, Hare Street PS', String(pp.fir));
ok('test and provenance labels become tags', D.titleParts('TIER-0 GATE TEST · VVIP MOVEMENT').test === true && D.titleParts('Visarjan procession (Emulated)').emulated === true);
const textCases = [
	['ANPR hit · STOLEN VEHICLE · MH47EM•••1 at EM-CAM-03 (95 km/h)', 'ANPR hit · Stolen vehicle · MH47EM•••1 at EM-CAM-03 (95 km/h)'],
	['Plan held (twin_not_calibrated: residual 0.4)', 'Plan held (twin not calibrated)'],
	['Band RED, none:HEAVY:CLEAR:MEDIUM', 'Band RED'.replace('RED', 'red')],
	['R_STOLEN_SIGHTING filed at EM-J05', 'Stolen-vehicle sighting filed at EM-J05'],
	['signal_plan restored on junction_cluster', 'signal plan restored on junction cluster'],
	['Event opened — emulator run 30: scenario tick 4', 'Event opened'],
	['Dispatch approved (PCR-12) by Sandbox Officer', 'Dispatch approved (PCR-12)'],
];
const textBad = textCases.filter(([raw, want]) => D.displayText(raw) !== want).map(([raw, want]) => `"${raw}" → "${D.displayText(raw)}" want "${want}"`);
ok('displayText: words, codes, machine codes and suffixes', textBad.length === 0, textBad.join(' | ') || `${textCases.length} texts`);
const exempt = [
	'e-challan withheld (vehicle reported stolen, FIR 120/2026)',
	'[SIMULATED FEED · EMULATED — exercise text, not a real road hold] Road hold on Strand Road',
	'EM-CAM-03 MH47EM•••1 J15 4401/2026',
	'FIR ANPR IST VVIP AMA PS CCTV MV BNSS GPS ETA AI ID OSM SVPI CG SG GIDC RTO GJ UTC OSINT ICCC SACHET IMD NDMA SDMA GDELT CAP AMC COA AHP TOPSIS EVOI DSS',
];
const exemptBad = exempt.filter((s) => D.displayText(s) !== s && !(s.startsWith('[SIMULATED') && D.displayText(s).startsWith('[SIMULATED FEED · EMULATED — exercise text, not a real road hold]')));
ok('never altered: the withheld note, the exercise marker, ids and marks, acronyms', exemptBad.length === 0, exemptBad.join(' | ') || `${exempt.length} exemptions`);
ok('the exercise marker keeps its words inside the text', D.displayText(exempt[1]).startsWith('[SIMULATED FEED · EMULATED — exercise text, not a real road hold]'));
const actorCases = [
	['traffic-oracle', 'Rules engine'],
	['convoy-brain', 'Sajag AI'],
	['event-emulator (system)', 'Scenario emulator'],
	['AMA policy', 'Adaptation policy'],
	['system:event_closed', 'System'],
	["Sandbox Officer (God's Eye Morning)", 'Sandbox Officer'],
	['Sandbox Officer (demo reset)', 'Sandbox Officer'],
	['Acceptance Tester', 'Acceptance tester'],
];
const actorBad = actorCases.filter(([raw, want]) => D.displayActor(raw) !== want).map(([raw, want]) => `${raw} → ${D.displayActor(raw)} want ${want}`);
ok('displayActor: system names in words, scenario suffixes dropped', actorBad.length === 0, actorBad.join(' | ') || `${actorCases.length} actors`);
ok('a scenario suffix is kept apart (shown muted, never lost)', D.actorParts("Sandbox Officer (God's Eye Morning)").scenario === "(God's Eye Morning)");
ok('test actors get a Test tag', D.actorParts('Scripted demo officer (demo reset)').test === true && D.actorParts('traffic-oracle').test === false);
ok("displayReason keeps the first clause", D.displayReason("STOLEN VEHICLE reported — FIR 4401/2026, Hare Street PS; God's Eye Morning flagship") === 'Stolen vehicle reported · FIR 4401/2026, Hare Street PS', D.displayReason("STOLEN VEHICLE reported — FIR 4401/2026, Hare Street PS; God's Eye Morning flagship"));
// brief(row): structured fields first (rule_id, action), else the oracle's FIXED openings
// (traffic_oracle/city/feed.py enforcement_items) — never a keyword in the officer's note
const fxEnf = FX.feed.items.filter((i) => i.kind === 'enforcement' && i.text);
const fxRejected = fxEnf.find((i) => i.text.startsWith('e-challan REJECTED by'));
const briefs = [
	[{ kind: 'anpr', text: 'ANPR hit · STOLEN VEHICLE · MH47EM•••1 at EM-CAM-03 (95 km/h)' }, 'read the vehicle at 95 km/h'],
	[{ kind: 'anpr', text: 'ANPR hit · STOLEN VEHICLE · MH47EM•••1 at EM-CAM-03', props: { speed_kmh: 88.6 } }, 'read the vehicle at 89 km/h'],
	[{ kind: 'enforcement', text: 'Stolen vehicle MH47EM•••1 (FIR 4401/2026) sighted at EM-CAM-03 on Diamond Harbour Road' }, 'filed a stolen-vehicle sighting at EM-CAM-03'],
	[{ kind: 'enforcement', text: 'Stolen vehicle MH47EM•••1 sighted at a camera — e-challan withheld, vehicle reported stolen; awaiting a duty officer' }, 'filed a stolen-vehicle sighting'],
	[{ kind: 'enforcement', text: 'Stolen-vehicle sighting of MH47EM•••1 dismissed by Sandbox Officer: stale EMULATED sighting' }, 'dismissed a sighting'],
	[{ kind: 'enforcement', text: 'Stolen-vehicle sighting of MH47EM•••1 confirmed by Sandbox Officer — pursuit authorised; e-challan withheld: pursuit approved' }, 'confirmed a sighting'],
	// (a) the fixture's own e-challan rejection: its note says "dismissed during demo reset" — still an e-challan decision
	[fxRejected, 'rejected an e-challan'],
	// (b) an approved fine is an e-challan approval, never "approved a sighting"
	[{ kind: 'enforcement', text: 'e-challan APPROVED by Sandbox Officer (R_SPD_SEGMENT, MH47EM•••1)', props: { rule_id: 'R_SPD_SEGMENT', status: 'approved' } }, 'approved an e-challan'],
	[{ kind: 'enforcement', text: 'e-challan APPROVED by Sandbox Officer (R_SPD_SEGMENT, MH47EM•••1): the sighting was dismissed and rejected earlier' }, 'approved an e-challan'],
	[{ kind: 'enforcement', text: 'e-challan recommended (R_SPD_SEGMENT) for MH47EM•••1 — 95 km/h in a 50 km/h zone on Strand Road — awaiting a human decision' }, 'recommended an e-challan'],
	// the structured fields win over any wording (the live oracle sends props.action)
	[{ kind: 'enforcement', text: 'note: dismissed, rejected, sighted at EM-CAM-01', props: { rule_id: 'R_SPD_SEGMENT', action: 'decision:approved', status: 'approved' } }, 'approved an e-challan'],
	[{ kind: 'enforcement', text: 'note: approved', props: { rule_id: 'R_STOLEN_SIGHTING', action: 'decision:rejected', status: 'rejected' } }, 'dismissed a sighting'],
	// props.status is the recommendation's state NOW, not this row's step: a filed row of a since-rejected sighting is still "filed"
	[{ kind: 'enforcement', text: 'Stolen vehicle MH47EM•••1 (FIR 4401/2026) sighted at EM-J05 on Diamond Harbour Road', props: { rule_id: 'R_STOLEN_SIGHTING', status: 'rejected' } }, 'filed a stolen-vehicle sighting at EM-J05'],
];
const briefBad = briefs.filter(([row, want]) => !row || D.brief(row) !== want).map(([row, want]) => `${row ? D.brief(row) : 'no fixture row'} want ${want}`);
ok('brief(row): one verb phrase per row, from structured fields and the fixed openings', briefBad.length === 0, briefBad.join(' | ') || `${briefs.length} rows`);
// over the whole fixture: a penal rule's row always speaks of an e-challan, a sighting rule's of a sighting,
// and appending a note full of decision words never changes a row's phrase
const NOTE = ': approved — dismissed, rejected; sighted at EM-CAM-09; e-challan APPROVED by nobody';
const enfBad = fxEnf.filter((i) => {
	const b = D.brief(i);
	const onRule = i.props.rule_id === 'R_STOLEN_SIGHTING' ? /sighting/.test(b) && !/e-challan/.test(b) : /e-challan/.test(b) && !/sighting/.test(b);
	return !onRule || D.brief({ ...i, text: `${i.text}${NOTE}` }) !== b;
});
ok('every fixture enforcement row: the phrase follows its rule, and a note never changes it', fxEnf.length >= 30 && enfBad.length === 0, enfBad.map((i) => `${D.brief(i)} ← ${i.text.slice(0, 48)}`).join(' | ') || `${fxEnf.length} rows`);
ok('brief(row, lang): the phrase in Hindi and Marathi (packs.workspace)', D.brief(fxRejected, 'hi') === packs.WORKSPACE_PACKS.hi.ws_brief_challan_rejected && D.brief(fxRejected, 'mr') === packs.WORKSPACE_PACKS.mr.ws_brief_challan_rejected && D.brief(fxRejected, 'hi') !== D.brief(fxRejected), D.brief(fxRejected, 'hi'));
// officer notes (SPEC §3.4 "never altered"): the oracle appends ": <note>" (enforcement) or " — <note>" (event,
// dispatch) after its own words; the Activity row's full text humanises only those words and keeps the note
// byte for byte — located by props.note (the live oracle) or, without it, by the oracle's fixed words
const noteRow = (kind, text, note, actorKind = 'human') => ({ id: `n:${kind}:${text.length}`, t: NOW, kind, feedKind: kind, urns: [], actor: 'Sandbox Officer', actorKind, text, source: 'live', verificationState: null, credibility: null, severity: 'info', props: note == null ? {} : { note } });
const CLIP = `e-challan REJECTED by Sandbox Officer (R_SPD_SEGMENT, MH47EM•••1): `;
const longNote = `RADAR_FAULT on SG_Highway, ${'CHECK THE GANTRY CAMERA AND RE-READ; '.repeat(16)}`;
const clipped = (CLIP + longNote).slice(0, 600);
const notes = [
	// [row, the note as the text carries it, the full text wanted (or null), the brief wanted (or null)]
	// the reviewer's two rows (props.note present)
	[noteRow('enforcement', 'Stolen-vehicle sighting of MH47EM•••1 dismissed by Sandbox Officer: WRONG READ at junction_cluster, CHECK CCTV', 'WRONG READ at junction_cluster, CHECK CCTV'), 'WRONG READ at junction_cluster, CHECK CCTV', 'Stolen-vehicle sighting of MH47EM•••1 dismissed by Sandbox Officer: WRONG READ at junction_cluster, CHECK CCTV', 'dismissed a sighting'],
	[noteRow('event', 'Event cancelled: Metro work zone (active → cancelled) by Sandbox Officer — DUPLICATE ENTRY, see signal_plan', 'DUPLICATE ENTRY, see signal_plan'), 'DUPLICATE ENTRY, see signal_plan', 'Event cancelled: Metro work zone (active → cancelled) — DUPLICATE ENTRY, see signal_plan', 'cancelled Metro work zone'],
	// a dispatch row and an e-challan decision
	[noteRow('dispatch', '108 Ambulance 108-ACCTEST-WP10B → J5: requested → cancelled by Sandbox Officer — WRONG UNIT, use pcr_unit', 'WRONG UNIT, use pcr_unit'), 'WRONG UNIT, use pcr_unit', null, null],
	[noteRow('enforcement', 'e-challan REJECTED by Sandbox Officer (R_SPD_SEGMENT, MH47EM•••1): RADAR_FAULT at signal_plan J5', 'RADAR_FAULT at signal_plan J5'), 'RADAR_FAULT at signal_plan J5', `${D.displayText('e-challan REJECTED by Sandbox Officer (R_SPD_SEGMENT, MH47EM•••1)')}: RADAR_FAULT at signal_plan J5`, 'rejected an e-challan'],
	// a note carrying a mark: the text holds it as the oracle sent it (masked), props.note raw — the full text is the sent one
	[noteRow('enforcement', 'Stolen-vehicle sighting of MH47EM•••1 dismissed by Sandbox Officer: SAW MH47EM•••1 at junction_cluster', 'SAW MH47EM9001 at junction_cluster'), 'SAW MH47EM•••1 at junction_cluster', 'Stolen-vehicle sighting of MH47EM•••1 dismissed by Sandbox Officer: SAW MH47EM•••1 at junction_cluster', 'dismissed a sighting'],
	// a text the oracle clipped at 600 characters: the note still starts where it started
	[noteRow('enforcement', clipped, longNote), clipped.slice(CLIP.length), `${D.displayText(CLIP.slice(0, -2))}: ${clipped.slice(CLIP.length)}`, 'rejected an e-challan'],
	// no props.note (a reduced capture): the oracle's fixed words before a note
	[noteRow('event', 'Event cancelled: Metro work zone (active → cancelled) by Sandbox Officer — DUPLICATE ENTRY, see signal_plan', null), 'DUPLICATE ENTRY, see signal_plan', 'Event cancelled: Metro work zone (active → cancelled) — DUPLICATE ENTRY, see signal_plan', 'cancelled Metro work zone'],
	[noteRow('enforcement', 'Stolen-vehicle sighting of MH47EM•••1 confirmed by Sandbox Officer — pursuit authorised; e-challan withheld: PURSUIT_OK, unit on SG_Highway', null), 'PURSUIT_OK, unit on SG_Highway', 'Stolen-vehicle sighting of MH47EM•••1 confirmed by Sandbox Officer — pursuit authorised; e-challan withheld: PURSUIT_OK, unit on SG_Highway', 'confirmed a sighting'],
];
const noteBad = [];
for (const [row, sentNote, wantFull, wantBrief] of notes) {
	const [a] = model.activityRows([row], 'all', NOW);
	const split = D.noteOf(row);
	const byteForByte = !!split && split.note === sentNote && a.full.endsWith(`${split.sep}${sentNote}`) && !MK.hasRawMark(a.full);
	if (!byteForByte || (wantFull != null && a.full !== wantFull) || (wantBrief != null && a.brief !== wantBrief)) noteBad.push(`${row.kind}: "${a.full.slice(0, 90)}" / "${a.brief}" / note "${split?.note?.slice(0, 40)}"`);
}
const disp = model.activityRows([notes[2][0]], 'all', NOW)[0];
ok(
	'officer notes survive byte for byte in the Activity row\'s full text (props.note, a clipped text, or the oracle\'s fixed words); the oracle\'s words before them are humanised; the brief is unchanged',
	noteBad.length === 0 && disp.full.endsWith(' — WRONG UNIT, use pcr_unit') && !disp.brief.includes('WRONG UNIT'),
	noteBad.join(' | ') || `${notes.length} rows`,
);
ok(
	'a machine row\'s note is not an officer\'s: "— emulator run N: …" is still dropped',
	model.activityRows([noteRow('event', 'Event opened — emulator run 30: scenario tick 4', 'emulator run 30: scenario tick 4', 'system')], 'all', NOW)[0].full === 'Event opened',
);
ok(
	'the trailing-actor rule never eats a note: "…) by <actor> — <note>" keeps the note words even as plain text',
	/duplicate entry, see signal plan$/i.test(D.displayText('Event cancelled: Metro work zone (active → cancelled) by Sandbox Officer — DUPLICATE ENTRY, see signal_plan')) && D.displayText('Dispatch approved (PCR-12) by Sandbox Officer') === 'Dispatch approved (PCR-12)',
	D.displayText('Event cancelled: Metro work zone (active → cancelled) by Sandbox Officer — DUPLICATE ENTRY, see signal_plan'),
);
// the fixture's own decided rows (their notes kept in the text, props.note reduced away): every note survives as sent
const fxNoted = FEED.filter((r) => r.actorKind === 'human' && D.noteOf(r));
const fxNoteBad = fxNoted.filter((r) => {
	const a = model.activityRows([r], 'all', NOW)[0];
	const n = D.noteOf(r);
	return !a.full.endsWith(`${n.sep}${n.note}`) || !r.text.endsWith(n.note);
});
ok(
	'every fixture row with an officer note keeps it as sent ("stale EMULATED sighting …" is never sentence-cased)',
	fxNoted.length >= 10 && fxNoteBad.length === 0 && fxNoted.some((r) => /EMULATED/.test(D.noteOf(r).note)) && model.activityRows(fxNoted, 'all', NOW).some((a) => /: stale EMULATED sighting/.test(a.full)),
	fxNoteBad.map((r) => r.text.slice(0, 60)).join(' | ') || `${fxNoted.length} noted rows`,
);
const ruleNames = vocab.ACTOR_RULES.filter(([, name, key]) => packs.WORKSPACE_PACKS.en[`ws_actor_name_${key}`] !== name).map(([, name, key]) => `${key}≠${name}`);
ok('system actor names: the EN words are the pack\'s, and they translate (a person\'s name never does)', ruleNames.length === 0 && D.displayActor('traffic-oracle', 'hi') === packs.WORKSPACE_PACKS.hi.ws_actor_name_rules && D.displayActor('Sandbox Officer', 'hi') === 'Sandbox Officer', ruleNames.join(', ') || `${vocab.ACTOR_RULES.length} rules`);
ok("displayTool: city_get_dossier → Read the object's dossier", D.displayTool('city_get_dossier') === "Read the object's dossier" && D.displayTool('plan_corridor') === 'Planned a corridor');
ok('results are cached per raw string', D.titleParts('PURSUIT — stolen MH47EM•••1 (FIR 4401/2026, Hare Street PS)') === pp);
const copyLint = readFileSync(path.join(HERE, 'copy-lint.mjs'), 'utf8');
const lintList = /'(FIR ANPR[^']*)'\s*\+\s*'([^']*)'/.exec(copyLint);
const lintAcr = lintList ? new Set(`${lintList[1]} ${lintList[2]}`.trim().split(/\s+/)) : new Set();
ok('the acronym allowlist is identical to copy-lint\'s (X3)', lintAcr.size > 0 && lintAcr.size === vocab.ACRONYMS.size && [...lintAcr].every((a) => vocab.ACRONYMS.has(a)), `${vocab.ACRONYMS.size} acronyms`);

// ─── 4. the omnibar search (SPEC §8.1) ──────────────────────────────────────

const rows = G.all();
const wb = SR.search(rows, 'mh47');
const wbKinds = wb.groups.map((g) => g.kind);
ok('"mh47" lists vehicles, events, sightings and recommendations, grouped with counts', ['vehicle', 'event', 'sighting', 'recommendation'].every((k) => wbKinds.includes(k)) && wb.groups.every((g) => g.total >= g.items.length), wb.groups.map((g) => `${g.kind} ${g.total}`).join(' · '));
ok('the vehicle group leads and shows the masked mark', wb.groups.find((g) => g.kind === 'vehicle')?.items[0]?.label === 'MH47EM•••1');
ok('exactly the matched span is marked', eq(SR.highlight('MH47EM•••1', ['mh47']), [{ text: 'MH47', mark: true }, { text: 'EM•••1', mark: false }]) && eq(SR.highlight('Pursuit of MH47EM•••1', ['mh47']), [{ text: 'Pursuit of ', mark: false }, { text: 'MH47', mark: true }, { text: 'EM•••1', mark: false }]));
ok('"Explore all" carries every matching URN', wb.urns.length === wb.total && wb.total > 0, `${wb.total} results`);
const kindTok = SR.search(rows, 'kind:camera em-cam');
ok('kind: tokens filter', kindTok.groups.length === 1 && kindTok.groups[0].kind === 'camera', kindTok.groups.map((g) => g.kind).join(','));
ok('state: tokens filter', SR.search(rows, 'state:pending').groups.every((g) => g.items.every((o) => String(o.state).startsWith('pending'))));
// a full mark: the watchlist only, never reads or recommendations
const watched = { ...G.get(V), urn: 'vehicle:00000000-0000-4000-8000-000000000007', id: '00000000-0000-4000-8000-000000000007', label: 'MH01XX•••7', props: { plate: 'MH01XX0007', plate_masked: 'MH01XX•••7', lawful_basis: 'watch' } };
const readOfIt = { ...G.get(Q.reads(V)[0].urn), urn: 'sighting:00000000-0000-4000-8000-000000000008', label: 'EM-CAM-01', props: { plate: 'MH01XX0007', plate_masked: 'MH01XX•••7', camera_id: 'EM-CAM-01' } };
const recOfIt = { ...G.byKind('recommendation')[0], urn: 'recommendation:00000000-0000-4000-8000-000000000009', props: { plate: 'MH01XX0007', plate_masked: 'MH01XX•••7' } };
const withWatched = [...rows, watched, readOfIt, recOfIt];
const full = SR.search(withWatched, 'MH01XX0007');
ok('a full mark matches only the watchlisted vehicle', !!full.mark && full.total === 1 && full.groups.length === 1 && full.groups[0].items[0].urn === watched.urn, `${full.total} match(es): ${full.groups.flatMap((g) => g.items.map((o) => o.kind)).join(',')}`);
ok('…and it is shown masked', full.groups[0]?.items[0]?.label === 'MH01XX•••7');
const prefix = SR.search(rows, 'MH47EM');
ok('a 6+ character prefix matches the watchlist only', !!prefix.mark && prefix.groups.length === 1 && prefix.groups[0].kind === 'vehicle' && prefix.total === 1, `${prefix.total} · ${prefix.groups.map((g) => g.kind).join(',')}`);
const none = SR.search(rows, 'MH01XX0007');
const es = SR.markEmptyState('en');
ok('no watchlisted vehicle: the honest empty state, verbatim (§8.1)', !!none.mark && none.total === 0 && `${es.title}. ${es.body}` === 'No watchlisted vehicle has this registration mark. Full marks are matched against the watchlist only, never against reads. A match is shown masked until a duty officer is named.' && `${es.title}. ${es.body}` === SR.MARK_EMPTY_EN, `${es.title}. ${es.body}`);
// the rows that DO carry a raw mark (props.plate 'MH01XX0007'): a haystack that indexed props.plate would fail here.
// A haystack is lower case, so it is read back in upper case (ids — uuids — taken out first: they are not marks)
const UUIDS_G = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
const hayHoldsMark = (o) => RAW_MARK_RE.test(SR.haystack(o).replace(UUIDS_G, '').toUpperCase());
const rawCarriers = withWatched.filter((o) => typeof o.props.plate === 'string' && RAW_MARK_RE.test(o.props.plate));
ok(
	'there is no person search: the haystack never holds a raw mark (rows carrying one included)',
	// the check itself catches a raw mark (self-check); and since review r3 the haystack is masked whole, so even a
	// row whose label carried one (a registered source's) never indexes it
	rawCarriers.length === 3 && withWatched.every((o) => !hayHoldsMark(o)) && RAW_MARK_RE.test(`${watched.label} mh01xx0007`.toUpperCase()) && !hayHoldsMark({ ...watched, label: `${watched.label} mh01xx0007` }),
	`${rawCarriers.length} rows carry a raw mark; the check catches one; a raw label is masked in the haystack`,
);
ok('fly to <a mark nobody watches>: a mark query with no watchlisted match (the omnibar shows its §8.1 empty state)', SR.isMarkQuery('MH01XX0007') && SR.matchMark(rows, 'MH01XX0007').length === 0 && SR.matchMark(withWatched, 'MH01XX0007').length === 1 && !SR.isMarkQuery('J15'));
ok('the legacy grammar parses with and without ">"', eq(SR.parseCommand('fly to MH47EM9001'), { type: 'fly', target: 'MH47EM9001' }) && eq(SR.parseCommand('> layer cameras off'), { type: 'layer', id: 'cameras', on: false }) && eq(SR.parseCommand('show police units near Strand Road'), { type: 'units', agency: 'police', road: 'Strand Road' }) && SR.parseCommand('ask why is the band amber')?.type === 'ask' && SR.parseCommand('sensor flir-iron')?.type === 'sensor');
const typed = ['w', 'wb', 'wb2', 'mh47', 'mh47e', 'em-', 'em-cam', 'em-cam-0', 'sarang', 'pursuit', 'kind:camera', 'state:pend'];
// each keystroke's cost is its best of five rounds (what the search costs; a GC pause or a busy box is not the search),
// the budget holds for the slowest keystroke
const best = new Map(typed.map((q) => [q, Infinity]));
for (let round = 0; round < 5; round++) {
	for (const q of typed) {
		const t0 = performance.now();
		SR.search(withWatched, q);
		best.set(q, Math.min(best.get(q), performance.now() - t0));
	}
}
const worst = Math.max(...best.values());
const fresh = objects.buildObjectGraph({ entities: SNAP.entities, dossiers: DOSSIERS });
const t0 = performance.now();
for (const q of typed) SR.search(fresh.all(), q);
const cold = (performance.now() - t0) / typed.length;
ok('< 5 ms per keystroke', worst < 5 && cold < 5, `worst ${worst.toFixed(2)} ms warm · ${cold.toFixed(2)} ms cold (${rows.length} objects)`);

// ─── 5. inWindow and protected objects (§7.3) ───────────────────────────────

// an IST wall time on the capture night (00:00 IST, 24 Oct = 18:30Z, 23 Oct; evening hours fall the day before)
const ist = (h, m) => Date.parse('2026-10-23T18:30:00Z') + ((h >= 12 ? h - 24 : h) * 60 + m) * 60e3;
const W = [ist(1, 20), ist(1, 42)];
const inWin = linked.filter((o) => Q.inWindow(o, W)).length;
ok('18 of 51 linked in window 01:20–01:42 IST', inWin === 18, `${inWin}`);
ok('no window: everything is in it', linked.every((o) => Q.inWindow(o, null)));
const camera = linked.find((o) => o.kind === 'camera');
ok('infrastructure never fades', !!camera && Q.inWindow(camera, [ist(3, 0), ist(3, 1)]));
const outside = linked.find((o) => o.kind === 'recommendation' && !Q.inWindow(o, W));
R.resetRegistry();
R.registerDecisionUnits(() => (outside ? [{ kind: 'echallan', id: outside.id, subjectUrn: outside.urn, title: 'Decide', deadline: null, severity: 1, homes: { '/': 'inbox', '/gods-eye': 'inbox', '/ops': 'decisions' } }] : []), { id: 'test-protect' });
ok('an object with a waiting decision never fades (protected)', !!outside && Q.inWindow(outside, W) && linked.filter((o) => Q.inWindow(o, W)).length === 19, outside ? `${outside.urn.slice(0, 30)}… now in window` : 'no recommendation outside the window');
R.resetRegistry();
const pursuitRow = { ...G.byKind('event')[0], urn: 'event:11111111-1111-4111-8111-111111111111', id: '11111111-1111-4111-8111-111111111111', state: 'active', t: ist(0, 10), end: null, props: { event_kind: 'vehicle_pursuit', metadata: { vehicle_id: V.split(':')[1] } } };
const G2 = objects.buildObjectGraph({ entities: SNAP.entities, dossiers: DOSSIERS, rows: [pursuitRow] });
const Q2 = S.createSelectors(() => ({ ...world, graph: () => G2 }));
ok('an open pursuit and its vehicle are protected', Q2.protectedUrns().has(pursuitRow.urn) && Q2.protectedUrns().has(V) && Q2.inWindow(pursuitRow, W));
const recentRead = { id: 'anpr:recent', t: NOW - 5 * 60e3, kind: 'anpr', feedKind: 'anpr', urns: [V], actor: 'EM-CAM-03', actorKind: 'machine', text: '', source: 'emulated', verificationState: null, credibility: null, severity: 'critical', props: {} };
const Q3 = S.createSelectors(() => ({ ...world, feed: () => [...FEED, recentRead] }));
ok('a vehicle read on the watchlist in the last 30 min is protected', Q3.protectedUrns().has(V) && !Q.protectedUrns().has(V));

// ─── 6. multi-select (§7.1) ─────────────────────────────────────────────────

const reads = Q.reads(V).map((r) => r.urn);
selection.clear();
selection.select(V);
ok('select(urn): replace → items [urn], current urn', eq(selection.items, [V]) && selection.current === V);
selection.select(reads[0], { mode: 'add', source: 'omnibar' });
ok('add: appended, the new object is the primary', eq(selection.items, [V, reads[0]]) && selection.current === reads[0] && selection.source === 'omnibar');
selection.select(reads[1], { mode: 'toggle' });
selection.select(reads[0], { mode: 'toggle' });
ok('toggle: adds when absent, removes when present', eq(selection.items, [V, reads[1]]) && selection.current === reads[1]);
selection.select(reads[1], { mode: 'toggle' });
ok('toggling the primary off hands the primary to the last remaining item', eq(selection.items, [V]) && selection.current === V);
selection.select('javascript:alert(1)', { mode: 'add' });
ok('a hostile URN never enters the selection', eq(selection.items, [V]));
const many = Array.from({ length: 60 }, (_, i) => `junction:${i + 1}`);
selection.selectMany([...many, 'person:1', many[3]], { source: 'lasso', primary: 'junction:9' });
ok('selectMany: deduplicated, invalid dropped, ≤ 50, the primary kept', selection.items.length === 50 && selection.current === 'junction:9' && !selection.items.includes('person:1') && selection.source === 'lasso', `${selection.items.length} items`);
selection.select(V);
for (const u of many) selection.select(u, { mode: 'add' });
ok('adding past 50 drops the oldest, never the primary', selection.items.length === 50 && selection.current === many[59] && !selection.items.includes(V), `${selection.items.length} · primary ${selection.current}`);
selection.clear();
ok('clear(): nothing selected', selection.items.length === 0 && selection.current === null);
selection.select(V, { fly: true });
ok('every existing caller keeps working (fly, source default map)', selection.flySeq > 0 && selection.flyUrn === V && selection.source === 'map');

// ─── 7. the share hash (R24): hostile values, masked egress ─────────────────

const enc = H.encodeWorkspaceKeys({
	view: 'table',
	timeWindow: W,
	filters: [{ id: 'x', field: 'kind', values: ['vehicle', 'sighting'], label: 'Kind is vehicle, sighting' }, { id: 'y', field: 'road', values: ['MH47EM9001 road'], label: 'Near MH47EM9001' }],
	docks: { left: true, right: false, bottom: 'full' },
	items: [V, 'javascript:alert(1)', reads[0]],
});
const dec = H.decodeWorkspaceKeys(enc);
ok('round trip: view, window, filters, docks, items', dec.view === 'table' && eq(dec.timeWindow, W) && dec.filters?.length === 2 && eq(dec.docks, { left: true, right: false, bottom: 'full' }) && eq(dec.items, [V, reads[0]]), enc.slice(0, 80));
ok('egress masked: no raw mark in the hash, in the filters or their labels', !H.carriesRawMark(enc) && dec.filters?.[1].label === 'Near MH47EM•••1' && dec.filters?.[1].values[0] === 'MH47EM•••1 road');
const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
const hostile = [
	['oversize f', `f=${'A'.repeat(5000)}`],
	['bad base64', 'f=%%%not-base64'],
	['a script in a label', `f=${b64([{ field: 'kind', values: ['vehicle'], label: '<script>alert(1)</script>' }])}`],
	['a javascript: value', `f=${b64([{ field: 'road', values: ['javascript:alert(1)'], label: 'x' }])}`],
	['an unknown field', `f=${b64([{ field: 'person', values: ['x'], label: 'x' }])}`],
	['a bad urn', `f=${b64([{ field: 'urns', values: ['vehicle:../../etc'], label: 'x' }])}`],
	['too many filters', `f=${b64(Array.from({ length: 20 }, () => ({ field: 'kind', values: ['camera'], label: 'k' })))}`],
];
const leaked = hostile.filter(([, q]) => H.decodeWorkspaceKeys(q).filters !== undefined).map(([n]) => n);
ok('hostile filters are dropped, never applied', leaked.length === 0, leaked.join(', ') || `${hostile.length} cases`);
const junk = H.decodeWorkspaceKeys('view=evil&t0=1&t1=99999999999999&dock=xyz&items=javascript:alert(1),person:1');
ok('a hostile view, window, dock or item is dropped', junk.view === undefined && junk.timeWindow === undefined && junk.docks === undefined && junk.items === undefined, JSON.stringify(junk));
ok('a reversed or month-long window is dropped', H.decodeWorkspaceKeys(`t0=${W[1]}&t1=${W[0]}`).timeWindow === undefined && H.decodeWorkspaceKeys(`t0=${W[0]}&t1=${W[0] + 40 * 86400e3}`).timeWindow === undefined);

// ─── 8. the X4 coercion ─────────────────────────────────────────────────────

const OS = '6f1c2a9e-3b7d-4e21-9a55-0c8e7d4b1f20';
const oe = cityApi.parseCityEntity({ kind: 'osint_event', id: OS, label: 'Road accident · Sector V - New Town link', source: 'osint', verification_state: 'NEWS-REPORTED', credibility: 0.65 });
ok('source "osint" survives parseCityEntity, with verificationState and credibility', oe?.source === 'osint' && oe.verificationState === 'NEWS-REPORTED' && oe.credibility === 0.65 && oe.urn === `osint_event:${OS}`);
ok('an OSINT kind is never live (the wire said live)', cityApi.parseCityEntity({ kind: 'place', id: 'sector_v_new_town_link', label: 'Sector V - New Town link', source: 'live' })?.source === 'osint');
ok('an unknown source becomes live', cityApi.parseCityEntity({ kind: 'camera', id: 'EM-CAM-01', label: 'x', source: 'bogus' })?.source === 'live' && cityApi.parseCityEntity({ kind: 'camera', id: 'EM-CAM-01', label: 'x' })?.verificationState === null);
ok('an unknown verification state or credibility is null', cityApi.parseCityEntity({ kind: 'osint_event', id: OS, verification_state: 'MADE-UP', credibility: 7 })?.verificationState === null && cityApi.parseCityEntity({ kind: 'osint_event', id: OS, credibility: 7 })?.credibility === null);
const fo = cityApi.parseFeedRow({ id: 'osint:1', t: FX.as_of, kind: 'osint', urns: [`osint_event:${OS}`], actor: 'osint-ingress (system)', actor_kind: 'system', text: 'Road accident reported on Sector V - New Town link', source: 'osint', verification_state: 'UNVERIFIED-OSINT', credibility: 0.4 });
ok('source "osint" survives parseFeedRow; the row rides the Events lane, its wire kind kept', fo?.source === 'osint' && fo.feedKind === 'osint' && fo.kind === 'event' && fo.verificationState === 'UNVERIFIED-OSINT' && fo.credibility === 0.4);
ok('a feed row with an unknown source is live', cityApi.parseFeedRow({ id: 'a:1', t: FX.as_of, kind: 'anpr', source: 'bogus' })?.source === 'live');
ok('URNs: osint_event takes a uuid, place a lower-case slug', !!cityApi.parseUrn(`osint_event:${OS}`) && !!cityApi.parseUrn('place:sector_v_new_town_link') && !cityApi.parseUrn('place:Sector V - New Town link') && !cityApi.parseUrn('osint_event:42'));
const genericRow = adapters.rowOf(oe);
ok('the generic adapter gives OSINT a row (glyph, provenance, verification, credibility)', genericRow.icon === 'geosearch' && genericRow.source === 'osint' && genericRow.verification === 'NEWS-REPORTED' && genericRow.credibility === 0.65);

// ─── 9. registry multiplicity (R27) ─────────────────────────────────────────

R.resetRegistry();
const act = (id) => ({ id, label: id, icon: 'arrow-up', run() {} });
R.registerActions('osint_event', () => [act('promote'), act('shared')], { id: 'osint-deck-a', order: 20 });
R.registerActions('osint_event', () => [act('dss-open'), act('shared')], { id: 'osint-deck-b', order: 10 });
let ids = R.actionsFor(genericRow).map((a) => a.id);
ok('two providers for one kind: both appear, by order then id', eq(ids, ['dss-open', 'shared', 'promote']), ids.join(','));
ok('a repeated action.id across providers appears once', ids.filter((x) => x === 'shared').length === 1);
R.registerActions('osint_event', () => [act('promote-v2')], { id: 'osint-deck-a', order: 20 });
ids = R.actionsFor(genericRow).map((a) => a.id);
ok('registering an id again replaces its entry (HMR, a second registerProviders)', eq(ids, ['dss-open', 'shared', 'promote-v2']), ids.join(','));
R.registerActions('osint_event', () => [act('tie')], { id: 'aaa-provider', order: 10 });
ok('equal order sorts by id', R.actionsFor(genericRow)[0].id === 'tie');
const compA = function PursuitSection() {};
const compB = function DssSection() {};
R.registerInspectorSection('event', compB, { id: 'dss-section', order: 20, ownsUnitKinds: ['dss'] });
R.registerInspectorSection('event', compA, { id: 'pursuit-section', order: 10 });
R.registerInspectorSection('event', compA, { id: 'pursuit-section', order: 10 });
const secs = R.inspectorSectionsFor('event');
ok('two inspector sections for event both render, once each', eq(secs.map((s) => s.id), ['pursuit-section', 'dss-section']), secs.map((s) => s.id).join(','));
const ev = `event:${OS}`;
const unit = (kind, id) => ({ kind, id, subjectUrn: ev, title: `Decide ${kind}`, deadline: null, severity: 1, homes: { '/': 'inbox', '/gods-eye': 'inbox', '/ops': 'decisions' } });
const cards = model.linkCards(ev, [unit('dss', 'd1'), unit('corridor-request', 'c1')], R.ownedUnitKinds('event'));
ok('ownsUnitKinds [dss]: no Actions-tab card for the dss unit, one for other kinds', eq(cards.map((c) => c.kind), ['corridor-request']));
ok('…and an object kind with no such section keeps every card', model.linkCards(ev, [unit('dss', 'd1')], R.ownedUnitKinds('vehicle')).length === 1);
R.registerLeftTab({ id: 'explorer', label: 'Explorer', icon: 'diagram-tree', component: compA, order: 10 });
R.registerLeftTab({ id: 'explorer', label: 'Explorer', icon: 'diagram-tree', component: compA, order: 10 });
R.registerLeftTab({ id: 'plan', label: 'Plan', icon: 'route', component: compA, order: 5, when: (c) => c.route === '/' });
ok('tabs: id-keyed (no duplicate), sorted, filtered by when(ctx)', eq(R.leftTabsFor().map((x) => x.id), ['plan', 'explorer']) && eq(R.leftTabsFor({ route: '/gods-eye', mode: 'map', live: { movement: false, pursuit: false } }).map((x) => x.id), ['explorer']));
R.registerDecisionUnits(() => [unit('stolen-sighting', V), unit('echallan', 'e1')], { id: 'decisions' });
R.registerDecisionUnits(() => [unit('stolen-sighting', V), unit('dss', 'd1')], { id: 'osint-dss' });
ok('decisionUnits(): two sources concatenated, each unit counted once', Q.decisionUnits().length === 3, Q.decisionUnits().map((u) => `${u.kind}:${u.id}`).join(','));
R.resetRegistry();
ok('decisionUnits() is 0 with no source', Q.decisionUnits().length === 0 && !R.hasProviders());

// ─── 10. the store (X6) ─────────────────────────────────────────────────────

const store = new Map();
const storage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) };
const W1 = new ws.Workspace({ world: () => world, storage: () => storage, now: () => NOW });
selection.clear();
selection.select(V);
const base = W1.objectSet.length;
ok('objectSet = the selection ∪ its linked objects', base === 52, `${base}`);
const f = W1.addFilter({ field: 'kind', values: ['vehicle', 'sighting', 'camera', 'recommendation'], label: 'Kind is vehicle, sighting, camera, recommendation' });
const want = [V, ...linked.map((o) => o.urn)].filter((u) => ['vehicle', 'sighting', 'camera', 'recommendation'].includes(u.split(':')[0])).length;
ok('addFilter returns an id and changes objectSet: table rows = (selection ∪ linked) ∩ filters', typeof f.id === 'string' && f.id.length > 0 && W1.objectSet.length === want && want === 50, `${W1.objectSet.length} rows (want ${want})`);
W1.removeFilter(f.id);
ok('removeFilter restores it', W1.objectSet.length === base);
W1.addFilter({ field: 'state', values: ['pending'], label: 'Pending' });
W1.addFilter({ field: 'source', values: ['emulated'], label: 'Emulated' });
W1.clearFilters();
ok('clearFilters restores it', W1.objectSet.length === base && W1.filters.length === 0);
selection.clear();
ok('nothing selected: every object (≤ 500)', W1.objectSet.length === G.size || W1.objectSet.length === 500, `${W1.objectSet.length} of ${G.size}`);
const explore = W1.addFilter({ field: 'urns', values: reads.slice(0, 5), label: 'Results' });
ok('a urns filter (Explore all) is exactly those objects', W1.objectSet.length === 5);
W1.removeFilter(explore.id);
selection.select(V);
W1.setTimeWindow(W[1], W[0]);
ok('setTimeWindow orders the ends and turns live off', eq(W1.timeWindow, W) && W1.live === false);
W1.returnToLive();
ok('returnToLive clears it', W1.timeWindow === null && W1.live === true);
W1.view = 'table';
W1.addFilter({ field: 'road', values: ['MH47EM9001 near Strand Road'], label: 'Watching MH47EM9001' });
const sv = W1.saveView('Night watch MH47EM9001');
const stored = store.get('sajag.workspace.savedViews.v1') ?? '';
ok('saveView: persisted, name and hash masked (URNs only)', sv.name === 'Night watch MH47EM•••1' && stored.includes(sv.id) && !RAW_MARK_RE.test(stored) && !H.carriesRawMark(sv.hash) && sv.hash.includes('sel='), stored.slice(0, 120));
// a saved view is the camera, the layers, the selection, the filters (SPEC §7.5): the page's hash is composed in,
// its stale `sel` replaced by the current selection, and a mark that reached the page hash is masked
globalThis.location = { hash: '#v=2&lat=22.5582&lon=88.3599&alt=900&layers=events,cameras&sel=junction:15&note=MH47EM9001', origin: 'http://127.0.0.1', pathname: WORKSPACE };
const svPage = W1.saveView('With the camera');
delete globalThis.location;
const svp = new URLSearchParams(svPage.hash);
ok('saveView carries S3\'s camera and layers keys and the current selection, masked', svp.get('lat') === '22.5582' && svp.get('layers') === 'events,cameras' && svp.get('sel') === V && svp.get('view') === 'table' && !H.carriesRawMark(svPage.hash), svPage.hash.slice(0, 110));
W1.deleteView(svPage.id);
W1.renameView(sv.id, 'Haji Ali at night');
const W2 = new ws.Workspace({ world: () => world, storage: () => storage, now: () => NOW });
ok('renameView: persisted (a new store reads it back)', W2.savedViews.length === 1 && W2.savedViews[0].name === 'Haji Ali at night');
W2.clearFilters();
W2.view = 'map';
selection.clear();
W2.applyView(sv.id);
ok('applyView: the view, the filters and the selection come back', W2.view === 'table' && W2.filters.length === 1 && W2.filters[0].label === 'Watching MH47EM•••1' && selection.current === V);
W2.deleteView(sv.id);
const W3 = new ws.Workspace({ world: () => world, storage: () => storage, now: () => NOW });
ok('deleteView: persisted', W3.savedViews.length === 0);
const wt = W3.addWatch({ title: 'MH47EM9001 sightings', subjectUrn: V, filters: [] });
ok('addWatch: masked, persisted', wt.title === 'MH47EM•••1 sightings' && new ws.Workspace({ world: () => world, storage: () => storage }).watches.length === 1 && !RAW_MARK_RE.test(store.get('sajag.workspace.watches.v1') ?? ''));
W3.removeWatch(wt.id);
ok('removeWatch: persisted', new ws.Workspace({ world: () => world, storage: () => storage }).watches.length === 0);
const broken = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } };
const W4 = new ws.Workspace({ world: () => world, storage: () => broken });
ok('a blocked storage never breaks the workspace', W4.savedViews.length === 0 && W4.saveView('x').name === 'x');
W3.openOmnibar('mh47');
ok("openOmnibar('mh47') → {open: true, query: 'mh47'}", eq(W3.omnibar, { open: true, query: 'mh47' }));
W3.closeOmnibar();
ok('closeOmnibar() resets it', eq(W3.omnibar, { open: false, query: '' }));
selection.select(V);
W3.openOmnibar();
ok('Esc closes (the omnibar), then clears (the selection); never navigates', W3.escape() === true && W3.omnibar.open === false && selection.current === V && W3.escape() === true && selection.current === null && W3.escape() === false);
W3.pin(V);
for (const u of reads.slice(0, 8)) W3.pin(u);
ok('pinned ≤ 6', W3.pinned.length === 6 && !W3.pinned.includes(V));
W3.setDock('left', true, 1600);
W3.setDock('right', true, 1600);
ok('≥ 1440 px: both side docks may be open', W3.docks.left && W3.docks.right);
W3.setDock('left', true, 1366);
ok('< 1440 px: opening one side dock closes the other', W3.docks.left && !W3.docks.right);
W3.toggleDock('bottom');
const off = W3.docks.bottom;
W3.toggleDock('bottom');
ok('\\ hides and shows the bottom dock', off === 'off' && W3.docks.bottom === 'compact');
const hx = W3.toHash('v=2&lat=22.5582&lon=88.3599&alt=900&heading=0&pitch=-35&roll=0&style=raw&layers=events');
ok('toHash composes the camera keys with the workspace keys and sel', hx.startsWith('v=2&lat=22.5582') && hx.includes('dock=') && !H.carriesRawMark(hx));

// ─── 10b. egress in any case and spelling (C6, SPEC §7.5; review r2) ───────
// An operator types a mark however they like: lower case, mixed case, with dots, dashes or spaces. None of it may
// leave the console raw — a filter label, the share hash, a saved view (localStorage), a watch, a view's name — and
// carriesRawMark() (Copy link's last check) must refuse such a link. The check reads a text the way the reviewer did:
// separators out, upper case, the typed mark searched for.
const TYPED = ['mh01xx0007', 'Mh01Xx0007', 'MH.01.XX.0007', 'mh 01 xx 0007', 'MH-01-XX-0007', 'mH01.xX 0007', 'MH01XX0007'];
const normM = (x) => String(x).replace(/[\s.\-]/g, '').toUpperCase();
const holds = (text, typed) => normM(text).includes(normM(typed));
const b64dec = (q) => {
	const f = new URLSearchParams(q).get('f');
	return f ? Buffer.from(f.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8') : '';
};
const egressBad = [];
for (const typed of TYPED) {
	store.clear();
	const W5 = new ws.Workspace({ world: () => world, storage: () => storage, now: () => NOW });
	selection.clear();
	selection.select(V);
	// what Explore all did before the fix: the typed query inside the label
	const flt = W5.addFilter({ field: 'urns', values: [V], label: tr('en', 'ws_filter_results', typed) });
	const val = W5.addFilter({ field: 'road', values: [`near ${typed}`], label: 'Road' });
	const hsh = W5.toHash('');
	const view = W5.saveView(`Night ${typed}`);
	const watch = W5.addWatch({ title: `${typed} sightings`, subjectUrn: V, filters: [] });
	const storedViews = store.get('sajag.workspace.savedViews.v1') ?? '';
	const storedWatches = store.get('sajag.workspace.watches.v1') ?? '';
	const decoded = H.decodeWorkspaceKeys(`f=${b64([{ field: 'kind', values: ['vehicle'], label: `Kind ${typed}` }])}`);
	const checks = {
		label: !holds(flt.label, typed) && flt.label.endsWith('•••7”'),
		value: !holds(val.values[0], typed),
		hashF: !holds(b64dec(hsh), typed) && !H.carriesRawMark(hsh),
		savedName: !holds(view.name, typed),
		savedStore: !holds(storedViews, typed) && !holds(b64dec(JSON.parse(storedViews)[0].hash), typed),
		watchTitle: !holds(watch.title, typed) && !holds(storedWatches, typed),
		cleanName: !holds(SV.cleanName(`My ${typed}`) ?? typed, typed),
		decodeIn: !!decoded.filters && !holds(decoded.filters[0].label, typed),
		refused: H.carriesRawMark(`sel=junction:1&note=${encodeURIComponent(typed)}`) && H.carriesRawMark(`http://127.0.0.1:5404/gods-eye#v=2&f=${b64([{ field: 'urns', values: [V], label: `Results for “${typed}”` }])}`),
	};
	const failed = Object.entries(checks).filter(([, v]) => !v).map(([k]) => k);
	if (failed.length) egressBad.push(`${typed}: ${failed.join(',')}`);
	W5.deleteView(view.id);
	W5.removeWatch(watch.id);
}
selection.clear();
ok(
	'a mark typed in lower case, mixed case, with dots, dashes or spaces is masked in the filter label and value, the share hash, the saved view (and localStorage), the watch, a name and an incoming hash; carriesRawMark() refuses a link that holds one',
	egressBad.length === 0,
	egressBad.join(' | ') || `${TYPED.length} spellings × 9 egress paths`,
);
// the mask itself: every spelling hides the number but its last digit, keeps the rest; ids are never marks
const UUIDISH = 'vehicle:0f4c5a2e-ab12-3456-8333-944455556666';
ok(
	'maskMarks: any case and spelling → …•••7; a URN\'s UUID (even a hex group like "ab12-3456") is never touched or flagged',
	TYPED.every((x) => MK.maskMarks(x).endsWith('•••7') && !MK.hasRawMark(MK.maskMarks(x))) &&
		MK.maskMarks('MH47EM•••1 at EM-CAM-03, J15, 4401/2026') === 'MH47EM•••1 at EM-CAM-03, J15, 4401/2026' &&
		MK.maskMarks(UUIDISH) === UUIDISH && !MK.hasRawMark(UUIDISH) && !H.carriesRawMark(`sel=${UUIDISH}&items=${UUIDISH}`) &&
		!!cityApi.parseUrn(UUIDISH),
	TYPED.map((x) => MK.maskMarks(x)).join(' · '),
);
// Explore all: the label never quotes a typed mark; a mark query is labelled with the matched vehicles' masked marks
const exploreBad = [];
for (const typed of TYPED) {
	const res = SR.search(withWatched, typed);
	const lbl = SR.exploreLabel(res, 'en');
	if (!res.mark || lbl !== 'Watchlist match: MH01XX•••7' || holds(lbl, typed)) exploreBad.push(`${typed} → ${lbl}`);
}
const noWatch = SR.exploreLabel(SR.search(rows, 'mh01xx0007'), 'en');
const plainQ = SR.exploreLabel({ query: 'stolen mh01xx0007 near Strand Road', mark: null }, 'en');
const longQ = SR.exploreLabel({ query: `strand road ${'x'.repeat(80)}`, mark: null }, 'en');
ok(
	'Explore all: a mark query (any spelling) is labelled "Watchlist match: MH01XX•••7", never the typed mark; any other query is quoted masked and clipped to fit',
	exploreBad.length === 0 && noWatch === '0 watchlist matches' && plainQ === 'Results for “stolen mh01xx•••7 near Strand Road”' && longQ.length <= 80 && longQ.endsWith('…”'),
	exploreBad.join(' | ') || `${noWatch} · ${plainQ} · ${longQ.length} chars`,
);
ok('"Explore 1 result in a table" (singular), "Explore all 2 results in a table"', tr('en', 'ws_omni_explore', 1) === 'Explore 1 result in a table' && tr('en', 'ws_omni_explore', 2) === 'Explore all 2 results in a table');

// ─── 10c. raw marks inside server props (C6, SPEC §9.3; review r3 must-fix 1) ─
// The oracle sends some props with a RAW mark inside free text: an e-challan's proposal ("e-challan recommended:
// {plate} read at …", enforcement/rules.py), a vehicle's officer-typed earmark_reason (city/entities.py) and a
// dispatch's event_title (a pursuit's is "PURSUIT — {plate}", city/entities.py, ops/client.ts). The committed fixture
// carries none, so these entities do. With NO officer named, no view field, no row label or sublabel, no haystack()
// and no search result may hold the mark (a query of "0007" must not find the dispatch through it: a digit-by-digit
// oracle); with an officer named the inspector shows it, as main's EntityDossier did (plates.ts displayText).
const RM = 'MH01XX0007';
const RM_RE = /MH[\s.\-/_]*01[\s.\-/_]*XX[\s.\-/_]*0007/i;
const RM_T = '2026-10-24T11:50:00Z';
const RM_VEH = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee';
const RM_PROPOSAL = `e-challan recommended: ${RM} read at 72 km/h in a 50 km/h segment`;
const rawWire = [
	{
		urn: 'recommendation:11111111-2222-4333-8444-555555555555', kind: 'recommendation', id: '11111111-2222-4333-8444-555555555555', label: 'Speeding on segment · EM-CAM-03',
		lon: 88.3499, lat: 22.5582, state: 'pending', source: 'emulated', t: RM_T, links: [`vehicle:${RM_VEH}`],
		props: { rule_id: 'R_SPD_SEGMENT', status: 'pending', recommendation: RM_PROPOSAL, created_at: RM_T, vehicle_id: RM_VEH, camera_id: 'EM-CAM-03', plate: RM, plate_masked: 'MH01XX•••7', evidence: { speed_kmh: 72, speed_limit_kmh: 50, road_name: 'Sector V - New Town link', camera_id: 'EM-CAM-03' } },
	},
	{
		urn: `vehicle:${RM_VEH}`, kind: 'vehicle', id: RM_VEH, label: 'MH01XX•••7', lon: 88.3499, lat: 22.5582, state: 'active', source: 'emulated', t: RM_T, links: [],
		props: { plate: RM, plate_masked: 'MH01XX•••7', earmark_state: 'active', lawful_basis: 'stolen_vehicle_fir', earmark_reason: `Stolen ${RM} reported — FIR 9/2026, Hare Street PS; Sandbox`, privacy_note: `Reads of ${RM} are kept 30 days`, retention_until: '2026-11-24T00:00:00Z' },
	},
	{
		urn: 'dispatch:2d4b8f61-7a3c-4c19-b0e2-91f5a6c3d7e8', kind: 'dispatch', id: '2d4b8f61-7a3c-4c19-b0e2-91f5a6c3d7e8', label: 'Police · PCR-12', state: 'requested', source: 'live', t: '2026-10-24T11:00:00Z', links: [],
		props: { agency: 'police', agency_label: 'Police', unit_id: 'PCR-12', status: 'requested', event_id: '11111111-1111-4111-8111-111111111111', waypoint_junction: 15, requested_by: 'Sandbox Officer', created_at: '2026-10-24T11:00:00Z', event_title: `PURSUIT — ${RM}` },
	},
];
// rows known only from history, and a registered source's row that names the mark in its label and sublabel
const rawHistory = [
	objects.recommendationRow({ recommendation_id: '22222222-3333-4444-8555-666666666666', rule_id: 'R_SPD_SEGMENT', status: 'approved', recommendation: RM_PROPOSAL, plate: RM, created_at: RM_T, evidence: { road_name: `Sector V - New Town link near ${RM}`, camera_id: 'EM-CAM-03' } }),
	objects.dispatchRow({ dispatch_id: '3e5c9a72-8b4d-4d2a-91f3-a2b6c7d8e9f0', agency: 'police', agency_label: 'Police', unit_id: 'PCR-14', status: 'approved', created_at: RM_T, event_title: `PURSUIT — stolen ${RM} (FIR 9/2026, Hare Street PS)` }),
	{ urn: 'event:44444444-5555-4666-8777-888888888888', kind: 'event', id: '44444444-5555-4666-8777-888888888888', label: `PURSUIT — ${RM}`, sublabel: `Pursuit of ${RM}`, icon: 'dot', state: 'active', stateIntent: 'none', t: NOW, end: null, lon: null, lat: null, source: 'live', verification: null, credibility: null, test: false, masked: false, props: {} },
];
const RGraph = objects.buildObjectGraph({ entities: rawWire.map((w) => cityApi.parseCityEntity(w)), rows: rawHistory });
const rawCtx = (r, on) => ({ lang: 'en', now: NOW, officer: on, plate: (p) => (on ? p : MK.maskMarks(p)), graph: RGraph, links: RGraph.links(r.urn), dossier: null });
/** Every path in a view that holds the raw mark (a linked row's props are data, never rendered: skipped). */
function rawPaths(o, at = 'view', out = []) {
	if (typeof o === 'string') {
		if (RM_RE.test(o)) out.push(at);
	} else if (Array.isArray(o)) o.forEach((v, i) => rawPaths(v, `${at}[${i}]`, out));
	else if (o && typeof o === 'object') for (const [k, v] of Object.entries(o)) if (k !== 'props') rawPaths(v, `${at}.${k}`, out);
	return out;
}
const textOfRow = (view, key) => view.groups.flatMap((g) => g.rows).find((r) => r.key === key)?.value?.v ?? null;
const leakNoOfficer = [];
for (const r of RGraph.all()) {
	for (const p of rawPaths(adapters.adapterFor(r.kind).view(r, rawCtx(r, false)))) leakNoOfficer.push(`${r.kind} ${p}`);
	if (RM_RE.test(r.label) || RM_RE.test(r.sublabel ?? '')) leakNoOfficer.push(`${r.kind} row label/sublabel`);
	if (RM_RE.test(SR.haystack(r))) leakNoOfficer.push(`${r.kind} haystack`);
}
const rmRec = RGraph.byKind('recommendation').find((r) => r.id === '11111111-2222-4333-8444-555555555555');
const rmVeh = RGraph.get(`vehicle:${RM_VEH}`);
const rmDisp = RGraph.get('dispatch:2d4b8f61-7a3c-4c19-b0e2-91f5a6c3d7e8');
const recView = adapters.adapterFor('recommendation').view(rmRec, rawCtx(rmRec, false));
const vehView = adapters.adapterFor('vehicle').view(rmVeh, rawCtx(rmVeh, false));
const dispView = adapters.adapterFor('dispatch').view(rmDisp, rawCtx(rmDisp, false));
ok(
	'no officer named: a raw mark in props.recommendation, earmark_reason, privacy_note or event_title reaches no view field, row label or sublabel, or haystack() — every kind, history and registered rows too',
	RGraph.all().length === 6 && leakNoOfficer.length === 0,
	leakNoOfficer.join(' | ') || `${RGraph.all().length} rows`,
);
ok(
	'no officer named: the Proposal, Reported and For rows show the mark masked, the rest of the text as before',
	textOfRow(recView, 'Proposal') === 'E-challan recommended: MH01XX•••7 read at 72 km/h in a 50 km/h segment' &&
		textOfRow(vehView, 'Reported') === 'Stolen MH01XX•••7 reported · FIR 9/2026, Hare Street PS' &&
		textOfRow(dispView, 'For event') === 'Pursuit of MH01XX•••7' &&
		rmDisp.sublabel === 'Pursuit of MH01XX•••7',
	`${textOfRow(recView, 'Proposal')} · ${textOfRow(vehView, 'Reported')} · ${rmDisp.sublabel}`,
);
const q0007 = SR.search(RGraph.all(), '0007');
const qPursuit = SR.search(RGraph.all(), 'pursuit');
const shownBySearch = [q0007, qPursuit].flatMap((res) => res.groups.flatMap((g) => g.items)).filter((r) => RM_RE.test(`${r.label} ${r.sublabel ?? ''}`));
ok(
	'the omnibar search is no digit-by-digit oracle: "0007" finds nothing through a raw mark, and no result (label or subtitle) shows one',
	q0007.total === 0 && qPursuit.total >= 2 && shownBySearch.length === 0,
	`"0007" → ${q0007.total} · "pursuit" → ${qPursuit.total}: ${qPursuit.groups.flatMap((g) => g.items.map((r) => r.sublabel ?? r.label)).join(' | ')}`,
);
const recOn = adapters.adapterFor('recommendation').view(rmRec, rawCtx(rmRec, true));
const vehOn = adapters.adapterFor('vehicle').view(rmVeh, rawCtx(rmVeh, true));
const dispOn = adapters.adapterFor('dispatch').view(rmDisp, rawCtx(rmDisp, true));
ok(
	'a named duty officer sees the mark as sent (Proposal, Reported, For, the title plate); rows stay masked whoever is on console (they reach search, table and CSV)',
	textOfRow(recOn, 'Proposal') === `E-challan recommended: ${RM} read at 72 km/h in a 50 km/h segment` &&
		textOfRow(vehOn, 'Reported') === `Stolen ${RM} reported · FIR 9/2026, Hare Street PS` &&
		textOfRow(dispOn, 'For event') === `Pursuit of ${RM}` &&
		vehOn.plate?.mark === RM && vehOn.plate?.masked === false &&
		!RM_RE.test(rmDisp.sublabel ?? '') && RGraph.all().every((r) => !RM_RE.test(`${r.label} ${r.sublabel ?? ''}`)),
	`${textOfRow(recOn, 'Proposal')?.replace(RM, '<raw>')} · ${textOfRow(vehOn, 'Reported')?.replace(RM, '<raw>')}`,
);

// ─── 10d. the mask reads real Indian marks only (review r3 must-fix 2) ──────
// The mask runs over officer notes, the Explain answer and the omnibar's AI answer when no officer is named (SPEC
// §9.3: no raw mark in DOM text). SPEC §3.4 says those are never altered: so a text without a real mark — a date, a
// time, a year — must come back byte for byte (the same string), while every typed spelling of a mark still masks
// and carriesRawMark() still refuses a link that holds one.
const NOT_MARKS = [
	'As of 24 Oct 2026, the vehicle was last read at EM-CAM-03.',
	'Retention ends on 22 Nov 2026.',
	'Checked on 12 Oct 2026, CCTV clear',
	'Waterlogging reported on 23 Oct 2026 near Thanthania',
	'Road closed till 30 Nov 2026',
	'Plan review at 10 am 2026',
	'Diversion via NH 48 since 2024',
	'FIR 4401/2026, Hare Street PS',
	'Filed at 01 38 2026',
	'Closed 23 or 24 Oct 2026, held up 12 Oct 2026',
	'AS 24 Oct 2026 · as 1 jan 2027 · up 12 Dec 2026',
	// the orchestrator's cases (a month in mixed or lower case is a date, whatever the state-code word's case)
	'As 24 Oct 2026',
	'as of 24 Oct 2026',
	'on 12 oct 2026',
	'AS 24 Oct 2026',
	'From 23-Oct-2026 to UP-24-Oct-2026, then 12/10/2026',
	'Opened by Sandbox Officer from the watchlist console (recommendation 3f2a…)',
];
const notMarkBad = NOT_MARKS.filter((x) => MK.maskMarks(x) !== x || MK.hasRawMark(x) || H.carriesRawMark(`note=${encodeURIComponent(x)}`));
const MORE_TYPED = ['MH/01/XX/0007', 'MH_01_XX_0007', 'mh 01-xx/0007'];
const typedBad = [...TYPED, ...MORE_TYPED].filter(
	(x) => !MK.maskMarks(x).endsWith('•••7') || MK.hasRawMark(MK.maskMarks(x)) || !MK.hasRawMark(x) || !H.carriesRawMark(`sel=junction:1&note=${encodeURIComponent(x)}`) || !H.carriesRawMark(`#v=2&f=${b64([{ field: 'urns', values: [V], label: `Near ${x}` }])}`),
);
ok(
	'maskMarks: dates, times and years stay byte for byte (none is a mark; carriesRawMark lets them pass); all 7 typed spellings (and "/", "_") still mask and carriesRawMark() refuses them',
	notMarkBad.length === 0 && typedBad.length === 0,
	notMarkBad.concat(typedBad).map((x) => `${x} → ${MK.maskMarks(x)}`).join(' | ') || `${NOT_MARKS.length} phrases unchanged · ${TYPED.length + MORE_TYPED.length} spellings masked`,
);
ok(
	'the state code is a real one, any case (WB, mh, Tg, DL …); a series glued to its number still masks even when it spells a month (DL8SEP1234)',
	MK.maskMarks('MH12AB1234 · tg09ab1234 · Dl3CAB1234 · DL8SEP1234 · KA05MAY1234 · up 14 ab 2211') === 'MH12AB•••4 · tg09ab•••4 · Dl3CAB•••4 · DL8SEP•••4 · KA05MAY•••4 · up 14 ab •••1' &&
		MK.STATE_CODES.includes('WB') && MK.STATE_CODES.length === 39,
	MK.maskMarks('MH12AB1234 · tg09ab1234 · Dl3CAB1234 · DL8SEP1234 · KA05MAY1234 · up 14 ab 2211'),
);
// the orchestrator's decision (review r3 follow-up): the case tells a mark from a date. An UPPER-case state code with
// an UPPER-case series is a mark even when the series spells a month, spaced or not — the ethics rail prefers masking
const UPPER_MONTH = [
	['MH 01 MAY 1234', 'MH 01 MAY •••4'],
	['DL 8 SEP 1234', 'DL 8 SEP •••4'],
	['MH-01-OCT-1234', 'MH-01-OCT-•••4'],
	['MH.12.JAN.4321', 'MH.12.JAN.•••1'],
];
const upperBad = UPPER_MONTH.filter(([x, want]) => MK.maskMarks(x) !== want || !MK.hasRawMark(x) || MK.hasRawMark(MK.maskMarks(x)) || !H.carriesRawMark(`sel=junction:1&note=${encodeURIComponent(x)}`));
ok(
	'an upper-case state code with an upper-case series that spells a month is a mark, spaced or not ("MH 01 MAY 1234", "DL 8 SEP 1234"): masked, and carriesRawMark() refuses it',
	upperBad.length === 0,
	upperBad.map(([x]) => `${x} → ${MK.maskMarks(x)}`).join(' | ') || UPPER_MONTH.map(([x]) => MK.maskMarks(x)).join(' · '),
);
// officer notes and AI answers through the console's mask (no officer: maskMarks): a date is never touched
const noteWithDate = noteRow('enforcement', 'Stolen-vehicle sighting of MH47EM•••1 dismissed by Sandbox Officer: Checked on 12 Oct 2026 at 10 am, CCTV clear', 'Checked on 12 Oct 2026 at 10 am, CCTV clear');
const [noteAct] = model.activityRows([noteWithDate], 'all', NOW);
const ANSWER = 'As of 24 Oct 2026 the vehicle MH47EM•••1 was last read at EM-CAM-03; retention ends on 22 Nov 2026.';
const ANSWER_RAW = 'mh01xx0007 was read on 24 Oct 2026 at 10 am';
ok(
	'officer notes and streamed answers are never altered by the mask but for a mark: a note or an answer with dates comes back byte for byte; a lower-case raw mark in an answer is still masked',
	MK.maskMarks(noteAct.full) === noteAct.full && noteAct.full.endsWith(': Checked on 12 Oct 2026 at 10 am, CCTV clear') && MK.maskMarks(noteAct.brief) === noteAct.brief &&
		MK.maskMarks(ANSWER) === ANSWER && MK.maskMarks(ANSWER_RAW) === 'mh01xx•••7 was read on 24 Oct 2026 at 10 am',
	`${noteAct.full.slice(-46)} · ${MK.maskMarks(ANSWER_RAW)}`,
);

// ─── 11. the navbar-officer read (X12) ──────────────────────────────────────

delete commandBar.officer;
const absent = officer.navbarOfficer();
const showAbsent = officer.showLegacyOfficer();
commandBar.officer = null;
const isNull = officer.navbarOfficer();
const showNull = officer.showLegacyOfficer();
commandBar.officer = { value: 'Sandbox Officer' };
const present = officer.navbarOfficer();
const showPresent = officer.showLegacyOfficer();
delete commandBar.officer;
ok('navbarOfficer(): null without the field (today), null when null, the value when present', absent === null && isNull === null && present?.value === 'Sandbox Officer');
ok('the inspector shows dossier-officer exactly when the page has no navbar officer', showAbsent === true && showNull === true && showPresent === false);

// ─── 12. the inspector's model ──────────────────────────────────────────────

const lg = model.linkGroups(G.links(V), 'en', NOW);
const recGroup = lg.find((g) => g.relation === 'recommendation');
ok('Links: groups by relation, a mixed group states no shared state, one time format per group', lg.length === 4 && recGroup && recGroup.sharedState === null && new Set(recGroup.times.map((s) => /^\d\d:\d\d$/.test(s))).size === 1, lg.map((g) => `${g.relation} ${g.rows.length}`).join(' · '));
const acts = model.activityRows(DOSSIERS[0].audit, 'all', NOW);
const counts = model.activityCounts(DOSSIERS[0].audit);
ok('Activity: one line per row, filters partition the rows', acts.length === DOSSIERS[0].audit.length && counts.human + counts.machine + counts.system === counts.all && acts.every((a) => a.brief.length > 0), `${counts.all} rows · ${counts.human} officer · ${counts.machine} machine · ${counts.system} system`);
ok('Activity actors in words, AI attributed with its glyph', acts.some((a) => a.who === 'Rules engine') && model.actorGlyph('machine', 'convoy-brain').ai === true && model.actorGlyph('human', 'Sandbox Officer').glyph === 'user');
const vview = adapters.adapterFor('vehicle').view(G.get(V), { lang: 'en', now: NOW, officer: false, plate: (p) => p, graph: G, links: G.links(V), dossier: DOSSIERS[0] });
ok('the vehicle view: masked mark title, red ring, 4 key figures (Reads 21), one rule note', vview.plateTitle && vview.title[0].masked === true && vview.alert && vview.figures.length === 4 && vview.figures.find((x) => x.caption === 'Reads')?.value === 21 && !!vview.note);
// SPEC §5.3: two to four key figures, numbers and times; a state is the header's tag, never a figure beside it
const figureFaults = [];
for (const r of G.all()) {
	const v = adapters.adapterFor(r.kind).view(r, { lang: 'en', now: NOW, officer: false, plate: (p) => p, graph: G, links: G.links(r.urn), dossier: DOSSIERS.find((d) => d.entity.urn === r.urn) ?? null });
	const tagWords = new Set(v.tags.map((t) => t.text));
	const n = v.figures.length;
	if ((n !== 0 && (n < 2 || n > 4)) || v.figures.some((f) => typeof f.value === 'string' && tagWords.has(f.value))) figureFaults.push(`${r.urn} (${n} figures)`);
}
ok('every view: none or two to four key figures, none repeating a header tag', figureFaults.length === 0, figureFaults.slice(0, 4).join(', ') || `${G.all().length} objects`);
// SPEC §3.3 in the key figures: a time off the anchor's IST day carries its day; a figure with no value is not shown
const istDayOf = (ms) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(ms);
const viewOf = (r) => adapters.adapterFor(r.kind).view(r, { lang: 'en', now: NOW, officer: false, plate: (p) => p, graph: G, links: G.links(r.urn), dossier: DOSSIERS.find((d) => d.entity.urn === r.urn) ?? null });
let offDay = 0;
const bareClock = [];
const emptyFigures = [];
for (const r of G.all()) {
	for (const f of viewOf(r).figures) {
		if (f.time == null && (f.value == null || f.value === '—' || f.value === '')) emptyFigures.push(`${r.kind} ${f.caption}`);
		if (f.time == null) continue;
		const off = istDayOf(f.time) !== istDayOf(NOW);
		if (off) offDay++;
		if (off !== (model.figureDay(f.time, NOW) != null)) bareClock.push(`${r.kind} ${f.caption}`);
	}
}
const pursuitView = viewOf(G.byKind('event')[0]);
// the fixture's pursuit was cancelled before it started (actual_end only): its End is dated; it has no Start time
const endFig = pursuitView.figures.find((f) => f.caption === 'End');
ok('a key-figure time on an earlier IST day carries its day ("23:55" over "23 Oct"), never a bare clock', offDay > 10 && bareClock.length === 0 && !!endFig && model.figureDay(endFig.time, NOW) === '23 Oct' && model.figureDay(NOW - 60e3, NOW) === null, bareClock.join(', ') || `${offDay} time figures off the anchor day, each dated`);
// F-02: a pursuit with no start of its own reads "Not started" — never its row time (the entity's last
// change, re-stamped on every band evaluation) presented as a start
{
	const evRow0 = G.byKind('event')[0];
	const live = viewOf({ ...evRow0, t: NOW, end: null, props: { ...evRow0.props, actual_start: null, planned_start: null, actual_end: null, planned_end: null, status: 'active' } });
	const startF = live.figures.find((f) => f.caption === 'Start');
	const win = live.groups.flatMap((g) => g.rows).find((r) => r.key === 'Window')?.value;
	ok(
		'F-02: a pursuit with no start (its row stamped now) shows "Not started" — no Start time, no window run, no time in the subtitle',
		(startF === undefined || (startF.time == null && startF.value === 'Not started')) && win?.t === 'text' && win.v === 'Not started' && !live.subtitle.flat().some((r) => 'time' in r || 'start' in r),
		JSON.stringify({ startF, win }),
	);
}
ok('no key figure without a value ("Class —", "Decided —", "Heading —" are gone)', emptyFigures.length === 0 && !pursuitView.figures.some((f) => f.caption === 'Class'), emptyFigures.slice(0, 4).join(', ') || 'none');
const pendingRec = G.byKind('recommendation').find((r) => r.state === 'pending');
const camView = viewOf(G.byKind('camera')[0]);
ok('an undecided proposal has no "Decided" figure; a camera\'s counts carry their window in the caption', !!pendingRec && !viewOf(pendingRec).figures.some((f) => f.caption === 'Decided') && camView.figures.some((f) => f.caption === 'Reads, 15 min' && f.unit == null), camView.figures.map((f) => `${f.caption}${f.unit ? ` [${f.unit}]` : ''}`).join(' · '));
{
	// the window comes from the event's OWN start and end (props), one run at one precision
	const evRow0 = G.byKind('event')[0];
	const started = viewOf({ ...evRow0, props: { ...evRow0.props, actual_start: new Date(ist(23, 40)).toISOString(), actual_end: new Date(ist(23, 55)).toISOString() } });
	ok('the pursuit\'s window is ONE run at one precision (no "23 Oct 23:55–23 Oct 23:55")', started.subtitle.flat().filter((r) => 'time' in r || 'start' in r).length === 1 && pursuitView.subtitle.flat().filter((r) => 'time' in r || 'start' in r).length === 0);
}
ok('the vehicle\'s "Reads" figure is the canonical reads() count', vview.figures.find((x) => x.caption === 'Reads')?.value === Q.reads(V).length && S.readsOf(G.links(V), V).length === Q.reads(V).length);

// a window that opened and closed within one minute reads the same at hh:mm: one stamp, no End figure
const evRow = G.byKind('event')[0];
// the window is the event's own start/end (props), never the row's sort time (F-02)
const withWindow = (a, b) => ({ ...evRow, props: { ...evRow.props, actual_start: new Date(a).toISOString(), actual_end: new Date(b).toISOString() } });
const subMin = viewOf(withWindow(ist(23, 55) + 10e3, ist(23, 55) + 40e3));
const twoMin = viewOf(withWindow(ist(23, 55) + 10e3, ist(23, 57)));
const windowOf = (v) => v.groups.flatMap((g) => g.rows).find((r) => r.key === 'Window')?.value;
ok(
	'a sub-minute window is ONE stamp: no End figure, a Window row with no end, one time run (never "23:55–23:55"); two minutes stay a range',
	!subMin.figures.some((f) => f.caption === 'End') && windowOf(subMin)?.b === null && subMin.subtitle.flat().some((r) => 'time' in r) && !subMin.subtitle.flat().some((r) => 'start' in r) &&
		twoMin.subtitle.flat().some((r) => 'start' in r) && windowOf(twoMin)?.b != null,
	subMin.figures.map((f) => f.caption).join(' · '),
);
// Activity: once the rows span days every row carries its day under its clock (one format); an OSINT row its verification
const actDays = model.activityRows(DOSSIERS[0].audit, 'all', NOW);
const actToday = model.activityRows(DOSSIERS[0].audit.map((r) => ({ ...r, t: NOW - 60e3 })), 'all', NOW);
const osintAct = model.activityRows([fo], 'all', NOW)[0];
ok(
	'Activity rows: a clock on every row, the day under it on every row once the days differ (none when all today); an OSINT row keeps its verification label',
	actDays.every((a) => /^\d\d:\d\d$/.test(a.clock) && /^\d{1,2} \w{3}$/.test(a.day ?? '')) && actToday.every((a) => a.day === null) && osintAct.verification === 'UNVERIFIED-OSINT' && actDays.every((a) => a.verification === null),
	`${actDays[0]?.clock} / ${actDays[0]?.day} · osint ${osintAct.verification}`,
);
const proposal = G.byKind('recommendation').map((r) => viewOf(r).groups.flatMap((g) => g.rows).find((x) => x.key === 'Proposal')?.value?.v).find(Boolean);
ok('a recommendation\'s Proposal reads as a sentence ("Stolen vehicle (FIR …) sighted at …")', !!proposal && /^[A-Z]/.test(proposal), proposal?.slice(0, 50));

// ─── 13. packs ──────────────────────────────────────────────────────────────

const enKeys = Object.keys(packs.WORKSPACE_PACKS.en).sort();
const parity = ['hi', 'mr'].every((l) => eq(Object.keys(packs.WORKSPACE_PACKS[l]).sort(), enKeys));
ok('packs.workspace: EN, HI and MR carry the same keys', parity, `${enKeys.length} keys`);

// ─── 14. separators that survive the compiler ───────────────────────────────
// Svelte 5 removes the whitespace at the start and end of every block, element,
// component and snippet body: `{a}{#if b} <span>…` renders "a<span>…" and
// `<span> · </span>` renders "·" (city-command-smoke once read a decided row as
// "Officer(Scenario)"). A space that must survive is an expression — {' '} or
// {` · ${x}`}. The workspace's markup keeps no same-line space at an edge.

const { parse: parseSvelte } = createRequire(path.join(DECK, 'package.json'))('svelte/compiler');
const svelteFiles = (dir) =>
	readdirSync(dir, { withFileTypes: true }).flatMap((d) =>
		d.isDirectory() ? svelteFiles(path.join(dir, d.name)) : d.name.endsWith('.svelte') ? [path.join(dir, d.name)] : [],
	);
const MARKUP = [
	...svelteFiles(path.join(DECK, 'src/lib/workspace')),
	path.join(DECK, 'src/routes/(deck)/design/workspace/+page.svelte'),
	path.join(DECK, 'src/lib/gods-eye/hud/CommandPalette.svelte'),
];
const trimmed = [];
for (const file of MARKUP) {
	const src = readFileSync(file, 'utf8');
	const where = (pos) => `${path.relative(DECK, file)}:${src.slice(0, pos).split('\n').length}`;
	const edges = (frag) => {
		const nodes = frag?.nodes ?? [];
		const first = nodes[0];
		const last = nodes[nodes.length - 1];
		// a same-line space at an edge is dropped; an edge that starts or ends with a newline is layout
		if (first?.type === 'Text' && /^[ \t]+(?!\s)/.test(first.data) && (nodes.length > 1 || /\S/.test(first.data))) trimmed.push(where(first.start));
		if (last?.type === 'Text' && /(?<!\s)[ \t]+$/.test(last.data) && (nodes.length > 1 || /\S/.test(last.data))) trimmed.push(where(last.end));
	};
	const walk = (node) => {
		if (!node || typeof node !== 'object') return;
		if (Array.isArray(node)) return node.forEach(walk);
		switch (node.type) {
			case 'IfBlock':
				edges(node.consequent);
				edges(node.alternate);
				return [node.consequent, node.alternate].forEach(walk);
			case 'EachBlock':
				edges(node.body);
				edges(node.fallback);
				return [node.body, node.fallback].forEach(walk);
			case 'SnippetBlock':
				edges(node.body);
				return walk(node.body);
			case 'AwaitBlock':
				return [node.pending, node.then, node.catch].forEach((f) => (edges(f), walk(f)));
			case 'Fragment':
				return walk(node.nodes);
			default:
				if (node.fragment) {
					edges(node.fragment);
					walk(node.fragment);
				}
		}
	};
	walk(parseSvelte(src, { modern: true }).fragment);
}
ok('no separator space sits where the compiler drops it (block, element, component and snippet edges)', trimmed.length === 0, trimmed.length ? trimmed.join(', ') : `${MARKUP.length} components scanned`);

if (failures > 0) {
	console.error(`\n${failures} workspace failure(s)`);
	process.exit(1);
}
console.log('\nall workspace assertions passed');
