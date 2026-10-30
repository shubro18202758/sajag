/**
 * OSINT deck unit test (OS-DECK-A) — the REAL modules, bundled with esbuild
 * (`$lib` aliased to src/lib; the ops store stubbed: a plain object; runes
 * as identity stubs), asserted hermetically (no browser, no network):
 *
 *   1. parseCityEntity (X4): the fixtures keep source 'osint' and their
 *      verification state; an OSINT row NEVER reads 'live', whatever the
 *      wire says; the snapshot's feeds carry held_social through extra;
 *   2. the generic ObjectRow for `osint_event` and `place` (source,
 *      verification, credibility) and the relName pairs from both ends
 *      (X5): Reported at / Reports here, Corroborates / Corroborated by,
 *      Promoted to / Promoted from, On road, At junction;
 *   3. the report section's view-model renders ONLY the whitelist (C-T
 *      field names + C-Q provenance): the poisoned fixture — which plants
 *      an `author` and a `byline` — shows neither key nor value anywhere;
 *   4. an area-level report carries the district note; a decision mark is
 *      drawn only for a proposed, unexpired DSS (the poisoned fixture's
 *      expired summary draws none); the geocode bucket mirrors the
 *      geocoder's own rule;
 *   5. registration is additive (R27): a second actions provider for
 *      `osint_event` under another id survives next to `osint.map`, and
 *      actionsFor returns both;
 *   6. packs.osint carries EN, HI and MR key parity (and `kindLabel`
 *      resolves the six reported-situation kinds in every language);
 *   7. a fetch recorder proves that registering the provider and building
 *      every section's view-model makes NO request — the one OSINT fetch
 *      is the dossier on selection, GET /city/entity/osint_event/{id}
 *      (X13: no new polled GET).
 *
 * Run from services/command-deck:   node tests/osint.unit.mjs
 * (bundle written to tests/artifacts/, which is gitignored)
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const ARTIFACTS = path.join(HERE, 'artifacts');
mkdirSync(ARTIFACTS, { recursive: true });

const FIXTURES = path.join(HERE, 'fixtures', 'osint');
const readFixture = (name) => JSON.parse(readFileSync(path.join(FIXTURES, name), 'utf8'));
const CORRELATED = readFixture('correlated.json');
const DISTRICT = readFixture('district.json');
const ROBBERY = readFixture('robbery.json');
const PLACE = readFixture('place.json');
const POISONED = readFixture('poisoned.json');

const createRequire = (await import('node:module')).createRequire;
const esbuild = createRequire(path.join(DECK, 'package.json'))('esbuild');

// the ops store stubbed (the register file reads its lang): a plain object;
// .svelte components stubbed too (the model and registry are what's tested)
const stubOps = {
	name: 'stub-ops-store',
	setup(build) {
		build.onResolve({ filter: /ops\/store\.svelte$/ }, () => ({ path: 'ops-store', namespace: 'stub' }));
	build.onLoad({ filter: /.*/, namespace: 'stub' }, () => ({
		// the lang is a getter: a test can flip the console's effective language (the
		// header state tag reads it — fix round 2's os_state_surfaced)
		contents: 'export const ops = { get lang() { return globalThis.__osint_lang || "en"; }, officerOn: false, dutyOfficer: "", watchlist: [] };',
		loader: 'js',
	}));
		build.onLoad({ filter: /\.svelte$/ }, () => ({ contents: 'export default function () {};', loader: 'js' }));
	},
};

const ENTRY = `
export * as cityApi from './src/lib/gods-eye/city-api';
export * as objects from './src/lib/workspace/objects';
export * as relations from './src/lib/workspace/relations';
export * as registry from './src/lib/workspace/registry';
export * as adapters from './src/lib/workspace/kinds';
export * as model from './src/lib/osint/model';
export * as actions from './src/lib/osint/actions';
export * as register from './src/lib/osint/register';
export * as osintLayer from './src/lib/gods-eye/layers/osint';
export { OSINT_PACKS } from './src/lib/i18n/packs.osint';
export { t, kindLabel } from './src/lib/i18n/strings';
export { selection } from './src/lib/gods-eye/entities/selection.svelte';
`;
const OUT = path.join(ARTIFACTS, 'osint-unit-bundle.mjs');
const built = await esbuild.build({
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'osint-entry.ts' },
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	outfile: OUT,
	logLevel: 'silent',
	plugins: [stubOps],
});

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);

ok('bundle builds (esbuild, $lib aliased, ops store stubbed)', built.errors.length === 0, built.errors.map((e) => e.text).slice(0, 3).join(' | '));

globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });

const M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
const { cityApi, objects, relations, registry, adapters, model, actions, register, osintLayer, OSINT_PACKS, t, kindLabel, selection } = M;

// ─── 1. the parsers keep OSINT honest (X4) ──────────────────────────────────

const ent = (raw) => cityApi.parseCityEntity(raw);
const correlated = ent(CORRELATED);
const district = ent(DISTRICT);
const robbery = ent(ROBBERY);
const place = ent(PLACE);
ok('fixtures parse (3 osint_event + 1 place)', !!correlated && !!district && !!robbery && !!place && place.kind === 'place');
ok(
	'the fixtures keep source "osint" and their verification state',
	correlated.source === 'osint' &&
		correlated.verificationState === 'NEWS-REPORTED' &&
		correlated.credibility === 0.65 &&
		district.source === 'osint' &&
		district.verificationState === 'OFFICIAL-VERIFIED' &&
		district.credibility === 0.95 &&
		place.source === 'osint' &&
		place.verificationState === null &&
		place.credibility === null,
	`${correlated.source}/${correlated.verificationState} · ${district.source}/${district.verificationState}`,
);
{
	// whatever the wire says, an OSINT row never reads live (the X4 coercion point)
	const hostile = ent({ ...CORRELATED, source: 'live' });
	const odd = ent({ ...CORRELATED, source: 'operator' });
	ok('an OSINT row NEVER yields source "live", whatever the wire says', hostile.source === 'osint' && odd.source === 'osint', `${hostile.source}, ${odd.source}`);
}
{
	// held_social rides the osint_event feed's extra (C-T: feeds are keyed by ENTITY kind)
	const snap = cityApi.parseCitySnapshot({
		as_of: '2026-10-25T01:39:01.433Z',
		entities: [CORRELATED, DISTRICT, ROBBERY, PLACE],
		feeds: { osint_event: { count: 3, status: 'ok', held_social: 2 } },
	});
	const f = snap.feeds['osint_event'];
	ok('held_social reaches the deck through feeds["osint_event"].extra (no feeds.osint key)', f?.extra?.held_social === 2 && !('osint' in snap.feeds), JSON.stringify(snap.feeds.osint_event?.extra));
}

// ─── 2. the generic ObjectRow and the relName pairs (X5) ────────────────────

const G = objects.buildObjectGraph({ entities: [correlated, district, robbery, place] });
const row = G.get(correlated.urn);
const placeRow = G.get(place.urn);
ok(
	'the generic ObjectRow carries source, verification and credibility for osint_event and place',
	row.source === 'osint' && row.verification === 'NEWS-REPORTED' && row.credibility === 0.65 && placeRow.source === 'osint' && placeRow.verification === null && placeRow.credibility === null,
	`${row.kind}: ${row.source}/${row.verification}/${row.credibility}`,
);
ok('a place row keeps its gazetteer props (feature type, surface forms, report count)', placeRow.props.feature_type === 'landmark' && Array.isArray(placeRow.props.surface_forms) && placeRow.props.osint_event_count === 1);
{
	const rn = (from, to) => relations.relName(from, to);
	const pairs = [
		['osint_event', 'place', 'Reported at'],
		['place', 'osint_event', 'Reports here'],
		['osint_event', 'event', 'Corroborates'],
		['event', 'osint_event', 'Corroborated by'],
		['osint_event', 'segment', 'On road'],
		['osint_event', 'junction', 'At junction'],
	];
	ok(
		'the OSINT relName pairs name the link from both ends (X5)',
		pairs.every(([a, b, want]) => rn(a, b) === want),
		pairs.map(([a, b]) => `${a}→${b}=${relations.relName(a, b)}`).join(', '),
	);
	const dossier = cityApi.parseDossier({
		entity: CORRELATED,
		related: [
			{ relation: 'reported_at', entity: PLACE },
			{ relation: 'on_road', entity: { urn: 'segment:1045', kind: 'segment', id: '1045', label: 'Sector V - New Town link', lon: 88.2769, lat: 22.5482, state: null, band: null, source: 'live', verification_state: null, credibility: null, t: null, age_sec: null, links: [], props: {} } },
		],
		audit: [],
	});
	const G2 = objects.buildObjectGraph({ dossiers: dossier ? [dossier] : [] });
	const reported = G2.links(dossier.entity.urn).find((l) => l.row.kind === 'place');
	const road = G2.links(dossier.entity.urn).find((l) => l.row.kind === 'segment');
	ok('a dossier\'s relations name the links (reported_at, on_road)', reported?.relation === 'reported_at' && road?.relation === 'on_road', `${reported?.relation}, ${road?.relation}`);
}

const NOW0 = Date.parse('2026-10-25T01:40:00.000Z');
// ─── 2b. the generic inspector view: the Sources figure counts REPORTS ──────
{
	// item 6 / audit M2b: reports = source_count − context_members (the oracle's own count),
	// falling back to the context publishers' length only when the prop is absent; the context
	// note is the deck's own translated key riding the figure's hint (never truncating)
	const ctx = { lang: 'en', now: NOW0, officer: false, plate: (raw) => raw ?? null, graph: objects.EMPTY_GRAPH };
	const figOf = (over) => {
		const e = cityApi.parseCityEntity({ ...CORRELATED, props: { ...CORRELATED.props, ...over } });
		return adapters.genericAdapter.view(objects.buildObjectGraph({ entities: [e] }).get(e.urn), ctx).figures;
	};
	const base = figOf({ source_count: 2, context_members: 1, provenance: { ...CORRELATED.props.provenance, context_publishers: ['sachet.ndma.gov.in'], context_note: 'District warning in effect' } });
	const sourcesFig = base.find((f) => f.caption === 'Sources');
	ok('the Sources figure counts REPORTS (source_count − context_members): "1 report", the context note on its visible sub line ("district warning in effect")', sourcesFig?.value === '1 report' && sourcesFig?.sub === 'district warning in effect' && sourcesFig?.hint == null, JSON.stringify(sourcesFig));
	const fallback = figOf({ source_count: 2, context_members: undefined, provenance: { ...CORRELATED.props.provenance, context_publishers: ['sachet.ndma.gov.in'], context_note: 'District warning in effect' } });
	ok('without the oracle prop the figure falls back to the context publishers\' length', fallback.find((f) => f.caption === 'Sources')?.value === '1 report', JSON.stringify(fallback.find((f) => f.caption === 'Sources')));
	const none = figOf({ source_count: 3, context_members: 0, provenance: { ...CORRELATED.props.provenance, context_publishers: [], context_note: null } });
	ok('no context member: the figure is just the count, no hint', none.find((f) => f.caption === 'Sources')?.value === '3 reports' && none.find((f) => f.caption === 'Sources')?.sub == null, JSON.stringify(none.find((f) => f.caption === 'Sources')));
	// fix round 2, item 4: the oracle's context_members PROP is the truth even when it
	// disagrees with the (distinct, capped) context publishers' length — and the report
	// wording reads the REPORT key, never the official one
	const two = figOf({ source_count: 3, context_members: 2, provenance: { ...CORRELATED.props.provenance, context_publishers: ['sachet.ndma.gov.in'], context_note: 'District warning in effect' } });
	ok('the figure counts source_count − context_members (2 members, ONE publisher): "1 report"', two.find((f) => f.caption === 'Sources')?.value === '1 report', JSON.stringify(two.find((f) => f.caption === 'Sources')));
	const reportNote = figOf({ source_count: 2, context_members: 1, provenance: { ...CORRELATED.props.provenance, context_publishers: ['sachet.ndma.gov.in'], context_note: 'District-level report in effect' } });
	ok('a report-wording context note reads the REPORT figure key ("district-level report in effect")', reportNote.find((f) => f.caption === 'Sources')?.sub === 'district-level report in effect', JSON.stringify(reportNote.find((f) => f.caption === 'Sources')));
	const hiCtx = { ...ctx, lang: 'hi' };
	const hiRow = (() => {
		const e = cityApi.parseCityEntity({ ...CORRELATED, props: { ...CORRELATED.props, source_count: 2, context_members: 1, provenance: { ...CORRELATED.props.provenance, context_publishers: ['sachet.ndma.gov.in'], context_note: 'District warning in effect' } } });
		return adapters.genericAdapter.view(objects.buildObjectGraph({ entities: [e] }).get(e.urn), hiCtx).figures.find((f) => f.caption === t('hi', 'ws_fig_sources'));
	})();
	ok('the context note translates in HI (never the EN oracle string)', hiRow?.sub != null && hiRow.sub !== 'district warning in effect' && hiRow.sub.length > 0, JSON.stringify(hiRow?.sub));
	// orchestrator make-up (audit E-OSINTDECK R2 must-fix 1): the visible second line is the figure's `sub`, set only by
	// the OSINT Sources figure; vehicle/camera tooltip prose stays in `hint` and never renders as a line
	{
		const { readFileSync, readdirSync } = await import('node:fs');
		const INSP = readFileSync(new URL('../src/lib/workspace/components/inspector/ObjectInspector.svelte', import.meta.url), 'utf8');
		ok('inspector: the visible figure line renders f.sub, never f.hint', INSP.includes('{#if f.sub}<div class="day" data-figure-sub>{f.sub}</div>{/if}') && !/\{#if f\.hint\}<div/.test(INSP));
		const kindsDir = new URL('../src/lib/workspace/kinds/', import.meta.url);
		const setters = readdirSync(kindsDir).filter((f) => f.endsWith('.ts') && /\bsub:(?!\s*maskHint)/.test(readFileSync(new URL(f, kindsDir), 'utf8')));
		ok('only the generic (OSINT) adapter sets a visible figure line', setters.length === 1 && setters[0] === 'generic.ts', setters.join(','));
		ok('pick card and layer line: the place fragment and the layer counts are carried in HI and MR', ['os_pick_at', 'os_layer_on_canvas', 'os_layer_area', 'os_layer_waiting', 'os_layer_unmapped', 'os_layer_down'].every((k) => ['hi', 'mr'].every((l) => t(l, k, 3) !== k && t(l, k, 3) !== t('en', k, 3))));
	}
	// de-duplicated generic view (item 7): credibility lives once (the header figure), the
	// Provenance group carries no verification word and no credibility row for a report
	const rowV = (() => {
		const e = cityApi.parseCityEntity(CORRELATED);
		return adapters.genericAdapter.view(objects.buildObjectGraph({ entities: [e] }).get(e.urn), ctx);
	})();
	ok('the generic view keeps the credibility figure exactly once', rowV.figures.filter((f) => f.caption === 'Credibility').length === 1, JSON.stringify(rowV.figures.map((f) => f.caption)));
	// fix round 2 (nice-to-have): the header state tag 'Surfaced' localizes — the osint pack
	// names the row state, and stateWord reads it in the console's effective language
	globalThis.__osint_lang = 'hi';
	try {
		const hiTags = (() => {
			const e = cityApi.parseCityEntity(CORRELATED);
			return adapters.genericAdapter.view(objects.buildObjectGraph({ entities: [e] }).get(e.urn), { ...ctx, lang: 'hi' }).tags;
		})();
		ok("the 'Surfaced' header state tag reads the osint pack in HI (never the EN fallback)", hiTags.some((tg) => tg.text === OSINT_PACKS.hi.os_state_surfaced) && !hiTags.some((tg) => tg.text === 'Surfaced'), JSON.stringify(hiTags.map((tg) => tg.text)));
	} finally {
		delete globalThis.__osint_lang;
	}
	const prov = rowV.groups.find((g) => g.title === 'Provenance');
	ok('the Provenance group has no Verification/Credibility rows for an OSINT report (the header tag and the section carry them once)', prov?.rows.every((r) => r.key !== 'Verification' && r.key !== 'Credibility') && prov?.rows.some((r) => r.key === 'Source'), JSON.stringify(prov?.rows.map((r) => r.key)));
}

// ─── 3. the report view-model renders ONLY the whitelist ────────────────────

const NOW = Date.parse('2026-10-25T01:40:00.000Z');
const T = (key, ...args) => {
	if (key.startsWith('os_event_kind_')) return kindLabel('en', key.slice('os_event_kind_'.length));
	return t('en', key, ...args);
};
const view = (raw, now = NOW, held = null) => model.reportView(model.readReport(raw.props), null, T, { lang: 'en', now, heldSocial: held });
const correlatedView = view(CORRELATED);

ok('the report view has the five groups in order', eq(correlatedView.sections.map((s) => s.title), ['Situation', 'Verification', 'Sources', 'Live state']), correlatedView.sections.map((s) => s.title).join(' · '));
{
	// item 7 (fix round 2): the compact section carries the ONE summary line — class,
	// subtype, correlated classes and the whole Location group read in the inspector's
	// Properties groups (generic.ts), so the tabs sit above the fold
	const sectionTitles = new Set(correlatedView.sections.map((s) => s.title));
	ok('the compact section carries no Location group (it moved to the Properties groups)', !sectionTitles.has('Location'), [...sectionTitles].join(' · '));
	ok('the compact Situation section is the ONE summary line', correlatedView.sections.find((s) => s.title === 'Situation')?.rows.every((r) => r.key === 'Summary') === true, JSON.stringify(correlatedView.sections.find((s) => s.title === 'Situation')?.rows.map((r) => r.key)));
	const ctx = { lang: 'en', now: NOW0, officer: false, plate: (raw) => raw ?? null, graph: objects.EMPTY_GRAPH, dossier: null };
	const gv = (raw) => adapters.genericAdapter.view(objects.buildObjectGraph({ entities: [cityApi.parseCityEntity(raw)] }).get(raw.urn), ctx);
	const groupsOf = (raw) => Object.fromEntries(gv(raw).groups.map((g) => [g.title, g.rows]));
	const identity = groupsOf(CORRELATED)['Identity'] ?? [];
	const location = groupsOf(CORRELATED)['Location'] ?? [];
	ok(
		'the Properties groups carry the situation class, subtype and correlated classes (moved from the section)',
		identity.some((r) => r.key === 'Class' && r.value.v === 'Road accident') && identity.some((r) => r.key === 'Subtype' && r.value.v === 'Affray collision') && identity.some((r) => r.key === 'Correlated classes'),
		JSON.stringify(identity.map((r) => r.key)),
	);
	ok(
		'the Properties groups carry the road and the geocode (moved from the section, with their testids)',
		location.some((r) => r.key === 'Road' && r.testid === 'osint-road') && location.some((r) => r.key === 'Geocode confidence' && /0.72 · medium/.test(r.value.v)),
		JSON.stringify(location.map((r) => r.key)),
	);
	const districtGroups = groupsOf(DISTRICT);
	const districtGeo = (districtGroups['Location'] ?? []).find((r) => r.key === 'Geocode confidence');
	ok('an area-level report carries the district note (the geocode row\'s visible hint)', districtGeo?.value.hint === 'District-level report: not a street location', JSON.stringify(districtGeo?.value));
	ok('a street-level report carries no district note', (groupsOf(CORRELATED)['Location'] ?? []).every((r) => !r.value.hint));
}
{
	const poisonedView = view(POISONED);
	const text = JSON.stringify(poisonedView);
	ok(
		'the poisoned fixture shows neither author nor byline (key or value) — the whitelist has no path for them',
		!text.includes('author') && !text.includes('byline') && !text.includes('Staff Correspondent') && !text.includes('A Reporter'),
		text.slice(0, 0) || 'clean',
	);
	// every key the view renders is one of the whitelist's own words
	const KEYS = new Set(Object.keys(model.readReport(POISONED.props)));
	const rendered = poisonedView.sections.flatMap((s) => s.rows.map((r) => r.key));
	ok('every rendered row key is a localized label (never a raw props key)', rendered.every((k) => !KEYS.has(k) || k === '—'), rendered.join(', '));
	// the parse-time redaction survives VERBATIM: [PERSON]/[AGE] are never reversed anywhere
	ok('[PERSON]/[AGE] summaries survive verbatim through readReport and the view', model.readReport(ROBBERY.props).summary === 'Jeweller Mr [PERSON], [AGE], robbed at gunpoint near Babughat (Strand Road)' && JSON.stringify(view(ROBBERY)).includes('[PERSON], [AGE]'), JSON.stringify(view(ROBBERY)).includes('[PERSON], [AGE]') ? 'verbatim' : 'altered');
}

// ─── 4. area note, decision dot, bucket, sources ────────────────────────────

{
	// the Verification section CARRIES the props' state (the tag renders it) — and, de-duplicated,
	// no credibility row and no situation-level tier row (the header figure and the per-source
	// tier tags carry those exactly once)
	const verif = correlatedView.sections.find((s) => s.title === 'Verification');
	ok('sections[Verification].verification equals the props\' state (NEWS-REPORTED)', verif?.verification === 'NEWS-REPORTED', String(verif?.verification));
	ok('the Verification section has no credibility row and no source-tiers row (the header figure and the per-source tags carry them once)', verif?.rows.every((r) => r.key !== 'Credibility' && r.key !== 'Source tiers'), verif?.rows.map((r) => r.key).join(', ') ?? '');
	ok('the Verification section still says independent publishers and cross-type corroboration', verif?.rows.some((r) => r.key === 'Independent publishers') && verif?.rows.some((r) => r.key === 'Cross-type corroboration'));
	const districtView = view(DISTRICT);
	ok('the district (official) report\'s Verification section carries OFFICIAL-VERIFIED', districtView.sections.find((s) => s.title === 'Verification')?.verification === 'OFFICIAL-VERIFIED');
}
{
	const now = NOW;
	ok(
		'the decision mark waits only for a proposed, unexpired DSS (correlated yes; the poisoned fixture\'s expired one no; district none)',
		model.dssWaiting(model.readReport(CORRELATED.props), now) === true && model.dssWaiting(model.readReport(POISONED.props), now) === false && model.dssWaiting(model.readReport(DISTRICT.props), now) === false,
	);
	const gen = Date.parse('2020-10-25T00:30:21.334Z');
	const horizon = 120 * 60_000;
	ok(
		'the expiry is checked as a time, not a state: the poisoned DSS waits within its horizon and not one ms past it',
		model.dssWaiting(model.readReport(POISONED.props), gen + horizon - 1) === true &&
			model.dssWaiting(model.readReport(POISONED.props), gen + horizon) === false &&
			model.dssWaiting(model.readReport(POISONED.props), NOW) === false,
	);
}

	ok(
		'classWord is SENTENCE case ("affray+collision" -> "Affray collision"; "road_accident" -> "Road accident")',
		model.classWord('affray+collision') === 'Affray collision' && model.classWord('road_accident') === 'Road accident',
		`${model.classWord('affray+collision')} / ${model.classWord('road_accident')}`,
	);
	{
		// one dss-waiting function: the expiry check lives in model.dssWaiting only; the layer
		// exports the set-BUILDER over it (an expired proposal never counts)
		const layerSrc = readFileSync(path.join(DECK, 'src/lib/gods-eye/layers/osint.ts'), 'utf8');
		ok('the layer has no dss-waiting function of its own (model.dssWaiting is the one)', !/function dssWaits|const dssWaits/.test(layerSrc) && layerSrc.includes("from '$lib/osint/model'"), layerSrc.includes('dssWaiting') ? 'uses model.dssWaiting' : 'no model import');
		const expired = { urn: 'osint_event:e-1', kind: 'osint_event', id: 'e-1', label: 'x', lon: 88.27, lat: 22.54, state: null, band: null, source: 'osint', t: null, ageSec: null, links: [], props: { dss: { dss_id: 'd', state: 'proposed', expires_at: new Date(NOW - 1000).toISOString() } } };
		const live = { ...expired, id: 'e-2', urn: 'osint_event:e-2', props: { dss: { dss_id: 'd', state: 'proposed', expires_at: new Date(NOW + 60_000).toISOString() } } };
		const urns = typeof osintLayer.dssWaitingUrns === 'function' ? osintLayer.dssWaitingUrns([expired, live, { ...expired, id: 'e-3', urn: 'osint_event:e-3', props: {} }], NOW) : null;
		ok('dssWaitingUrns keeps only the proposed AND unexpired (the expired DSS is not in the picture)', !!urns && urns.has('osint_event:e-2') && !urns.has('osint_event:e-1') && !urns.has('osint_event:e-3') && urns.size === 1, urns ? JSON.stringify([...urns]) : 'no dssWaitingUrns export');
	}

ok(
	'the geocode bucket mirrors the geocoder\'s own rule (≥0.75 high, ≥0.5 medium, else low)',
	model.geocodeBucket(0.8) === 'high' && model.geocodeBucket(0.719) === 'medium' && model.geocodeBucket(0.4) === 'low' && model.geocodeBucket(null) === null,
);
{
	// S1 + R2: the dossier's per-signal sources — each row's tier from source_notes keyed by
	// signal_id, its title and fetch mode, and a url on OFFICIAL tiers only
	const NEWS = '9a1b2c3d-0000-4c3c-8d4d-00000000a001';
	const WIRE = '9a1b2c3d-0000-4c3c-8d4d-00000000a002';
	const dossierProps = {
		...CORRELATED.props,
		sources: [
			{ signal_id: NEWS, source: 'google_news_rss', publisher: 'news-a.example', url: null, title: 'Car crashes near club; [AGE] rider hurt', fetch_mode: 'cached-sample', role: 'primary' },
			{ signal_id: WIRE, source: 'sachet_cap', publisher: 'sachet.ndma.gov.in', url: 'https://sachet.ndma.gov.in/cap/a92f', title: 'District warning: heavy rain', fetch_mode: 'cached-sample', role: 'corroborating' },
		],
		source_notes: [
			{ signal_id: NEWS, source_tier: 'aggregator', link_note: 'source link withheld — may name a person' },
			{ signal_id: WIRE, source_tier: 'official', link_note: null },
		],
	};
	const rows = model.sourceRows(model.readReport(dossierProps));
	ok(
		'per-signal source rows: each row\'s tier from source_notes keyed by signal_id; title and fetch mode carried',
		eq(rows.map((r) => r.publisher), ['news-a.example', 'sachet.ndma.gov.in']) && rows[0].tier === 'aggregator' && rows[1].tier === 'official' && rows.every((r) => r.fetchMode === 'cached-sample') && rows[0].title === 'Car crashes near club; [AGE] rider hurt',
		JSON.stringify(rows),
	);
	ok(
		'officialness rides the TIER, never the domain: the news url is withheld, the official tier\'s kept',
		rows[0].official === false && rows[0].url === null && rows[1].official === true && rows[1].url === 'https://sachet.ndma.gov.in/cap/a92f',
		JSON.stringify([rows[0].official, rows[0].url, rows[1].official, rows[1].url]),
	);
	{
		// the mutant trap: a government-domain publisher with a non-official tier is NOT official
		const trap = model.sourceRows(model.readReport({
			...dossierProps,
			sources: [{ signal_id: NEWS, source: 'google_news_rss', publisher: 'sachet.ndma.gov.in', url: null, title: 'x', fetch_mode: 'cached-sample', role: 'primary' }],
			source_notes: [{ signal_id: NEWS, source_tier: 'aggregator', link_note: 'source link withheld — may name a person' }],
		}));
		ok('a gov-domain publisher with a non-official tier is still not official (no url, withheld note)', trap[0].official === false && trap[0].url === null && trap[0].linkWithheld === true, JSON.stringify(trap));
	}
	// the snapshot fallback: publisher rows without a signal — tier NONE when unknown
	const fallback = model.sourceRows(model.readReport(CORRELATED.props));
	ok('snapshot-only rows: every reporting publisher once, no tier of its own, the withheld note kept', eq(fallback.map((r) => r.publisher), ['news-a.example', 'news-b.example']) && fallback.every((r) => r.tier === null && r.signalId === null && r.linkWithheld && !r.official && r.url === null), JSON.stringify(fallback));
	const districtSources = model.sourceRows(model.readReport(DISTRICT.props));
	ok('the official source row (snapshot fallback, gov domain): no tier of its own yet, not withheld', districtSources.length === 1 && districtSources[0].tier === null && districtSources[0].linkWithheld === false && districtSources[0].url === null, JSON.stringify(districtSources));
	{
		// fix round 2, item 8: a POISONED news/social url on the wire is dropped deck-side —
		// the row keeps no url and reads as withheld, whatever the dossier sent
		const poisoned = model.sourceRows(
			model.readReport({
				...dossierProps,
				sources: [
					{ signal_id: NEWS, source: 'reddit_rss', publisher: 'reddit.com', url: 'https://www.reddit.com/r/kolkata/comments/zz1/poisoned', title: 'Big crowd near Law Garden right now', fetch_mode: 'cached-sample', role: 'primary' },
					{ signal_id: WIRE, source: 'sachet_cap', publisher: 'sachet.ndma.gov.in', url: 'https://sachet.ndma.gov.in/cap/a92f', title: 'District warning: heavy rain', fetch_mode: 'cached-sample', role: 'corroborating' },
				],
				source_notes: [
					{ signal_id: NEWS, source_tier: 'social_unverified', link_note: 'source link withheld — may name a person' },
					{ signal_id: WIRE, source_tier: 'official', link_note: null },
				],
			}),
		);
		ok('a poisoned news-tier url on the wire is DROPPED: no url on the row, the withheld note set', poisoned[0].url === null && poisoned[0].linkWithheld === true && poisoned[0].official === false, JSON.stringify(poisoned[0]));
		ok('the official row beside it keeps its https url', poisoned[1].official === true && poisoned[1].url === 'https://sachet.ndma.gov.in/cap/a92f', JSON.stringify(poisoned[1]));
		// the only href the deck ever binds is https: — an official row whose url is http:
		// loses it like a withheld link
		const insecure = model.sourceRows(
			model.readReport({
				...dossierProps,
				sources: [{ signal_id: WIRE, source: 'sachet_cap', publisher: 'sachet.ndma.gov.in', url: 'http://sachet.ndma.gov.in/cap/a92f', title: 'District warning: heavy rain', fetch_mode: 'cached-sample', role: 'primary' }],
				source_notes: [{ signal_id: WIRE, source_tier: 'official', link_note: null }],
			}),
		);
		ok('an official row with an http: url loses the url (https: is the only scheme ever linked)', insecure[0].url === null, JSON.stringify(insecure[0]));
	}
	{
		// fix round 2, item 7: the tier words are LOCALIZED — EN/HI/MR carry os_tier_* for the
		// five tiers, and an unknown tier falls back to the sentence-case class word
		const Tl = (lang) => (key) => t(lang, key);
		ok(
			'tierWord reads the pack in every language (EN "News regional", HI and MR their own words)',
			model.tierWord('news_regional', 'en', Tl('en')) === 'News regional' &&
				model.tierWord('news_regional', 'hi', Tl('hi')) === OSINT_PACKS.hi.os_tier_news_regional &&
				model.tierWord('news_regional', 'mr', Tl('mr')) === OSINT_PACKS.mr.os_tier_news_regional &&
				model.tierWord('news_regional', 'hi', Tl('hi')) !== 'News regional',
			`${model.tierWord('news_regional', 'hi', Tl('hi'))} / ${model.tierWord('news_regional', 'mr', Tl('mr'))}`,
		);
		ok('an unknown tier falls back to the sentence-case class word, and null stays null', model.tierWord('weird_tier', 'en', Tl('en')) === 'Weird tier' && model.tierWord(null, 'en', Tl('en')) === null, String(model.tierWord('weird_tier', 'en', Tl('en'))));
		ok('the packs carry os_tier_* for the five tiers in EN, HI and MR', ['official', 'aggregator', 'news_regional', 'news_national', 'social_unverified'].every((k) => `os_tier_${k}` in OSINT_PACKS.en && `os_tier_${k}` in OSINT_PACKS.hi && `os_tier_${k}` in OSINT_PACKS.mr));
	}
}
{
	const ctxLine = model.contextLine(model.readReport(CORRELATED.props), T);
	ok('a context member is named apart ("District warning in effect · sachet.ndma.gov.in"), never a source row', ctxLine === 'District warning in effect · sachet.ndma.gov.in' && !correlatedView.sections.find((s) => s.title === 'Sources')?.sources?.some((s) => s.publisher === 'sachet.ndma.gov.in'), String(ctxLine));
	// the context note is the deck's OWN two keys (official vs report) — never the oracle's EN string
	const T2 = (lang) => (key, ...args) => t(lang, key, ...args);
	ok('the context note translates: HI reads the HI official key, not the EN oracle note', model.contextLine(model.readReport(CORRELATED.props), T2('hi')) === 'ज़िला चेतावनी लागू · sachet.ndma.gov.in', String(model.contextLine(model.readReport(CORRELATED.props), T2('hi'))));
	const reportNote = model.contextLine(model.readReport({ ...CORRELATED.props, provenance: { ...CORRELATED.props.provenance, context_note: 'District-level report in effect' } }), T);
	ok('a non-official context note reads the report key ("District-level report in effect")', reportNote === 'District-level report in effect · sachet.ndma.gov.in', String(reportNote));
}
{
	// R1: "n social posts held" is GONE from every per-report view (it implies corroboration
	// that does not exist); the count, if shown at all, lives once at layer level
	const heldView = view(CORRELATED);
	const all = JSON.stringify(heldView);
	ok('no "social posts held" line on ANY per-report view (R1)', !/social post/i.test(all), all.slice(0, 0) || 'clean');
	ok('the packs carry no held-social key any more', !('os_held_social' in OSINT_PACKS.en) && !('os_held_social' in OSINT_PACKS.hi) && !('os_held_social' in OSINT_PACKS.mr));
	// fix round 2, item 14 (replaces the round-1 vacuous probe): the layer's ONE city-wide
	// line is the packs' os_layer_held_* pair, in EN, HI and MR — the EN words are the ones
	// the canvas test pins
	ok(
		'the layer line localizes: os_layer_held_* in every language, EN matching the pinned wording',
		typeof OSINT_PACKS.en.os_layer_held_one === 'string' &&
			/1 single-post social report held city-wide \(never shown\)/.test(`1 ${OSINT_PACKS.en.os_layer_held_one}`) &&
			/2 single-post social reports held city-wide \(never shown\)/.test(`2 ${OSINT_PACKS.en.os_layer_held_many}`) &&
			OSINT_PACKS.hi.os_layer_held_many !== OSINT_PACKS.en.os_layer_held_many &&
			OSINT_PACKS.mr.os_layer_held_many !== OSINT_PACKS.en.os_layer_held_many,
		`${OSINT_PACKS.hi.os_layer_held_many}`,
	);
}
{
	// fix round 2, item 16: two second-order flags with the SAME words collapse into ONE
	// note with a count — two bare "On a 108 route" lines say nothing about which is which
	const dup = view({
		...ROBBERY,
		props: {
			...ROBBERY.props,
			second_order: [
				{ kind: 'ambulance_route', urn: 'segment:12', segment_id: 12, note: 'On a 108 route' },
				{ kind: 'ambulance_route', urn: 'segment:13', segment_id: 13, note: 'On a 108 route' },
			],
		},
	});
	const dupLive = dup.sections.find((s) => s.title === 'Live state');
	ok('duplicate second-order notes collapse into one counted note ("On a 108 route ×2")', eq(dupLive?.notes, ['On a 108 route ×2']), JSON.stringify(dupLive?.notes));
	const robberyView = view(ROBBERY);
	const live = robberyView.sections.find((s) => s.title === 'Live state');
	ok('a second-order flag is one neutral note in the server\'s words', live?.notes?.[0] === 'On a 108 route', live?.notes?.join(' | '));
	const mixed = view({
		...ROBBERY,
		props: {
			...ROBBERY.props,
			second_order: [
				{ kind: 'ambulance_route', urn: 'segment:12', segment_id: 12, note: 'On a 108 route' },
				{ kind: 'ambulance_route', urn: 'segment:13', segment_id: 13, note: 'On a 108 route' },
				{ kind: 'roadwork', urn: 'segment:14', segment_id: 14, note: 'Signed work zone ahead' },
			],
		},
	});
	ok('distinct wordings keep their own notes (only the repeated one gains a count)', eq(mixed.sections.find((s) => s.title === 'Live state')?.notes, ['On a 108 route ×2', 'Signed work zone ahead']), JSON.stringify(mixed.sections.find((s) => s.title === 'Live state')?.notes));
}

// ─── 5. registration is additive (R27) ──────────────────────────────────────

{
	registry.resetRegistry();
	register.register();
	const sections = registry.inspectorSectionsFor('osint_event');
	ok('register(): the report section is registered for osint_event under id osint-report', sections.some((s) => s.id === 'osint-report'), sections.map((s) => s.id).join(', '));
	ok('the place section is registered for place under id osint-place', registry.inspectorSectionsFor('place').some((s) => s.id === 'osint-place'));
	const row2 = { urn: 'osint_event:x', kind: 'osint_event', id: 'x', label: 'x', sublabel: null, icon: 'dot', state: null, stateIntent: 'none', t: null, end: null, lon: null, lat: null, source: 'osint', verification: null, credibility: null, test: false, masked: false, props: { toponym: 'Sector V (Salt Lake)' } };
	const own = registry.actionsFor(row2).map((a) => a.id);
	ok(
		'the osint.map actions are the two non-decision ones — no Show on map of its own (the workspace\'s core action exists once)',
		eq(own, ['osint.search-around', 'osint.sources']),
		own.join(', '),
	);
	// a second provider registers for the same kind under its own id (OS-DECK-B lands here)
	registry.registerActions('osint_event', () => [{ id: 'dss.review', label: 'Review', icon: 'diagram-tree', run() {} }], { id: 'osint.decisions', order: 20 });
	const both = registry.actionsFor(row2).map((a) => a.id);
	ok('with a second action provider under another id, actionsFor returns BOTH sets', both.includes('osint.search-around') && both.includes('dss.review') && both.length === 3, both.join(', '));
	registry.resetRegistry();
}

// ─── 6. EN / HI / MR parity ─────────────────────────────────────────────────

{
	const enKeys = Object.keys(OSINT_PACKS.en).sort();
	const parity = ['hi', 'mr'].every((l) => eq(Object.keys(OSINT_PACKS[l]).sort(), enKeys));
	ok('packs.osint: EN, HI and MR carry the same keys', parity, `${enKeys.length} keys`);
	const unresolved = enKeys.filter((k) => ['hi', 'mr'].some((l) => OSINT_PACKS[l][k] === undefined));
	ok('every key resolves in every language', unresolved.length === 0, unresolved.join(', ') || 'all');
	const kinds = ['reported_crime', 'public_disorder', 'road_accident', 'hazard', 'flooding', 'infra_failure'];
	ok(
		'kindLabel resolves the six reported-situation kinds in EN, HI and MR (never the raw key)',
		kinds.every((k) => ['en', 'hi', 'mr'].every((l) => kindLabel(l, k) !== 'Corridor event' && kindLabel(l, k) !== `kind_${k}`)),
		kinds.map((k) => `${k}=${kindLabel('en', k)}`).join(', '),
	);
	// fix round 2 (kills 8g): the HI and MR "Correlated classes" wording is pinned — the old
	// "Related reports" phrasing never comes back
	ok(
		'the correlated-classes wording is pinned in HI and MR (सहसंबद्ध वर्ग / संबंधित वर्ग)',
		OSINT_PACKS.hi.os_correlated === 'सहसंबद्ध वर्ग' && OSINT_PACKS.mr.os_correlated === 'संबंधित वर्ग',
		`${OSINT_PACKS.hi.os_correlated} / ${OSINT_PACKS.mr.os_correlated}`,
	);
}

// ─── 7. the fetch recorder: registration and rendering make no request (X13) ─

{
	const calls = [];
	globalThis.fetch = async (input) => {
		const url = typeof input === 'string' ? input : String(input?.url ?? input);
		calls.push(url);
		throw new Error(`unexpected fetch: ${url}`);
	};
	registry.resetRegistry();
	register.register();
	for (const raw of [CORRELATED, DISTRICT, ROBBERY, POISONED, PLACE]) {
		view(raw, NOW, 2);
	}
	registry.actionsFor(row);
	ok('registering the provider and rendering the sections makes NO request', calls.length === 0, calls.join(' | ') || 'none');
	// the one OSINT fetch is the dossier on selection: GET /city/entity/osint_event/{id}
	const dossierCalls = [];
	globalThis.fetch = async (input) => {
		dossierCalls.push(String(input));
		return { ok: true, status: 200, json: async () => ({ entity: CORRELATED, related: [], audit: [] }) };
	};
	await cityApi.fetchDossier(correlated.urn);
	ok(
		'selection loads ONE dossier: GET /api/v1/city/entity/osint_event/{id} (audit_limit), never a second polled GET',
		dossierCalls.length === 1 && /\/api\/v1\/city\/entity\/osint_event\/8ec6f567-9366-47ae-8fde-38aa421a3219\?audit_limit=60$/.test(dossierCalls[0]),
		dossierCalls.join(' | ') || 'none',
	);
	delete globalThis.fetch;
}

// ─── 8. the committed fixtures are ethics-clean (R13) — the poisoned one on purpose ──

{
	const PERSON_KEY_RE = /author|person|handle|username|byline|reporter|poster|uploader|suspect|accused|victim|owner|driver_name|face|biometric|individual_/i;
	const EXEMPT = new Set(['touches_persons', 'surface_forms', 'surfaced']);
	const OPAQUE = /^(?:[0-9a-f]{40}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/;
	for (const [name, fx] of [['correlated.json', CORRELATED], ['district.json', DISTRICT], ['robbery.json', ROBBERY], ['place.json', PLACE]]) {
		const bad = [];
		(function walk(o) {
			if (Array.isArray(o)) return o.forEach(walk);
			if (o && typeof o === 'object') {
				for (const [k, v] of Object.entries(o)) {
					if (!EXEMPT.has(k) && !OPAQUE.test(k) && PERSON_KEY_RE.test(k)) bad.push(k);
					walk(v);
				}
			}
		})(fx);
		ok(`fixture ${name}: no key matches the person-key regex`, bad.length === 0, bad.join(', ') || 'clean');
	}
	ok(
		'fixture poisoned.json: the planted author/byline keys are there ON PURPOSE (the whitelist\'s negative test)',
		PERSON_KEY_RE.test(Object.keys(POISONED.props).join(' ')) && typeof POISONED.props.author === 'string' && typeof POISONED.props.byline === 'string',
		Object.keys(POISONED.props).filter((k) => PERSON_KEY_RE.test(k)).join(', '),
	);
	const publishers = new Set();
	for (const fx of [CORRELATED, DISTRICT, ROBBERY, PLACE]) {
		(function walk(o) {
			if (Array.isArray(o)) return o.forEach(walk);
			if (o && typeof o === 'object') {
				for (const [k, v] of Object.entries(o)) {
					if ((k === 'publisher' || k === 'publishers' || k === 'context_publishers') && typeof v === 'string') publishers.add(v);
					if (Array.isArray(v) && k.endsWith('publishers')) v.forEach((p) => typeof p === 'string' && publishers.add(p));
					walk(v);
				}
			}
		})(fx);
	}
	ok(
		'every fixture publisher is *.example or sachet.ndma.gov.in (synthetic, R13)',
		[...publishers].every((p) => p.endsWith('.example') || p === 'sachet.ndma.gov.in'),
		[...publishers].join(', '),
	);
	// the harness page never loads the poisoned fixture
	const harness = readFileSync(path.join(DECK, 'src/routes/(deck)/design/osint/+page.svelte'), 'utf8');
	ok('the harness imports the four clean fixtures and never the poisoned one', harness.includes("fixtures/osint/correlated.json") && !harness.includes('poisoned.json'));
	ok('the harness pick list includes the robbery fixture', /harness-sel-robbery/.test(harness), /harness-sel-robbery/.test(harness) ? 'present' : 'missing');
	ok('the harness copy never leaks a CSS variable name (no "(--v-map-…)" in its legend)', !/(?<!var)\(--v-map-/.test(harness), harness.match(/(?<!var)\(--v-map-[^)]*\)/)?.[0] ?? 'clean');
	{
		// fix round 2, item 12 (ethics): the correlated fixture's SACHET district warning is its
		// CONTEXT member — the harness's correlated dossier must carry NO sachet source row
		// (context counted as corroboration is the forbidden conflation) — and the DISTRICT
		// dossier is where the official reporting source demos the link
		const sgBlock = /const SG_SOURCES = \{[\s\S]*?\n\t\};/.exec(harness)?.[0] ?? '';
		const diBlock = /const DISTRICT_SOURCES = \{[\s\S]*?\n\t\};/.exec(harness)?.[0] ?? '';
		ok('the harness correlated dossier carries NO sachet source row (sachet is context only)', sgBlock.length > 0 && !sgBlock.includes('sachet.ndma.gov.in'), sgBlock.slice(0, 80));
		ok('the harness DISTRICT dossier carries the official reporting source with its https url', diBlock.includes("source_tier: 'official'") && diBlock.includes('https://sachet.ndma.gov.in/'), diBlock.slice(0, 80));
		ok('the harness wires commandBar.onLangChange to ops.lang (HI/MR reach the OSINT surfaces)', harness.includes('commandBar.onLangChange = (l) => (ops.lang = l);'));
	}
	{
		// fix round 2, item 5 — thermal honesty (audit A cross-WP): the canvas never reads as a
		// thermal SENSOR. Every USER-FACING string in GodsEyeCanvas.svelte is free of the FLIR/
		// infrared vocabulary (the internal flir-* ids and the comments are not user-facing);
		// the doc names no removed menu.
		const canvasSrc = readFileSync(path.join(DECK, 'src/lib/gods-eye/GodsEyeCanvas.svelte'), 'utf8');
		const noComments = canvasSrc.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/(^|[^:'"\\])\/\/[^\n]*/g, '$1 ');
		const strings = [];
		for (const m of noComments.matchAll(/'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\]|\\.)*)`/g)) {
			const s = m[1] ?? m[2] ?? m[3] ?? '';
			// a SENTENCE is user-facing; id-ish tokens without a space (the internal flir-* keys,
			// the './shaders/flir' module path) are not
			if (/\s/.test(s.trim())) strings.push(s);
		}
		const hits = strings.filter((s) => /FLIR|infrared|thermal camera/i.test(s));
		ok('no user-facing string in GodsEyeCanvas reads FLIR/infrared/thermal camera (a visual filter is never a sensor)', hits.length === 0, hits.slice(0, 4).join(' | ') || 'clean');
		ok('the doc names no removed "More → Presentation" menu', !canvasSrc.includes('More → Presentation'));
		ok('the legacy HUD chip reads thermal-style wording (the internal flir-* ids kept)', /'flir-whot': 'Thermal-style·WHOT'/.test(canvasSrc) && /Thermal-style·IRON/.test(canvasSrc), 'SENSOR_LABEL thermal-style');
	}
}

if (failures) {
	console.error(`FAIL osint.unit.mjs — ${failures} failing assertion(s)`);
	process.exit(1);
}
console.log('ok   osint.unit.mjs — all assertions passed');
