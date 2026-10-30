/**
 * Workspace views unit test (UI-S2X; SPEC §5.3, §6.2, §7.3–§7.5, §8.8–8.9, §9.2).
 *
 *   node tests/views.unit.mjs
 *
 * esbuild bundles the REAL modules — the Histogram's bins, the table's model
 * and CSV, the Explorer's model, the vitals card's figures, the selectors,
 * the object graph, the workspace store and the views pack — with `$lib`
 * aliased to src/lib; `$state` is an identity stub, so the rune classes run
 * as plain classes (the workspace.unit pattern). The fixture is the
 * committed tests/fixtures/workspace/captured.json (the prototype's
 * emulated, masked capture) plus fictional rows of mixed provenance.
 *
 * Asserts:
 *   - Histogram: six groups; Hour bins sorted BY TIME across midnight; "1
 *     value" / "n values" (never "1 values") counting filter values; ONE
 *     bar per filter value, and each bar's count is exactly what a filter
 *     on its value keeps (no summing); a selection becomes one filter per
 *     group (values OR-ed) that keeps exactly the selected bars' rows; the
 *     open-source bar ("Open-source") carries its rows by verification
 *     state as a read-only breakdown while its filter keeps every
 *     open-source row; "Filter out" only where it is exact; a long label
 *     stays within the store's 80 characters
 *   - table rows = (selection ∪ linked) ∩ filters (the store's objectSet and
 *     selectionRows agree, with and without a kind filter); an Explorer
 *     kind's rows
 *   - the shared table scope: the Histogram counts the rows IN THE TABLE —
 *     what a mounted table publishes (the page's rows included), the
 *     default scope otherwise; two tables never blank each other; a click in
 *     the table (a Ctrl+click that empties the selection included) never
 *     re-scopes it, another view's pick or clear does
 *   - the header: the selection names only its own scope; passed rows are
 *     named by their kind or "Objects"; an empty explored kind explains
 *     itself
 *   - the Source column only for MIXED rows; a uniform list's provenance once
 *   - fading: protected objects and infrastructure never fade; other timed
 *     rows outside the window do
 *   - CSV: marks masked even with an officer named, any spelling; a
 *     provenance, verification and credibility column; IST stamps; formula
 *     cells guarded; quoting
 *   - the vitals card: watchlisted = count('vehicle') = the Explorer's
 *     figure on the same fixture; decisions are decisionUnits() once a unit
 *     source is registered, else the §7.4 unit rule on the registry — and
 *     the Watches' "Decision needed" is the same figure either way
 *   - the vitals store: seed() drops the timers and the visibility listener
 *     and ignores answers in flight; unseed() polls again with ONE listener;
 *     the snapshot is cleared only when the last variant detaches
 *   - the Explorer: canonical kinds plus any registry kind (osint_event and
 *     place included), one state word each; a saved view reads "edited"
 *     only once the workspace moves away from it; a watch title the store
 *     accepts from any label (long, or with < > `)
 *   - labels: masked marks as a Plate run, identifiers as an Id run
 *   - the pack: EN/HI/MR carry the same keys, every `vw_` key the views use
 *     exists, no person field in the harness fixtures
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const OUT = path.join(HERE, 'artifacts', 'views-bundle.mjs');
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
export * as registry from './src/lib/workspace/registry';
export * as ws from './src/lib/workspace/workspace.svelte';
export * as watches from './src/lib/workspace/watches';
export * as mask from './src/lib/workspace/mask';
export * as bins from './src/lib/workspace/components/histogram/bins';
export * as tm from './src/lib/workspace/components/table/model';
export * as csv from './src/lib/workspace/components/table/csv';
export * as scope from './src/lib/workspace/components/table/scope.svelte';
export * as ex from './src/lib/workspace/components/explorer/model';
export * as fig from './src/lib/workspace/components/vitals/figures';
export * as vit from './src/lib/gods-eye/hud/vitals.svelte';
export * as packs from './src/lib/i18n/packs.views';
export { commandBar } from './src/lib/shell/command-bar.svelte';
export { t } from './src/lib/i18n/strings';
`;
const built = await esbuild.build({
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'views-entry.ts' },
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	outfile: OUT,
	logLevel: 'silent',
});
ok('bundle builds (esbuild, $lib aliased)', built.errors.length === 0, `${built.errors.length} errors`);

// Svelte 5 runes are compiler macros: identity stubs run the stores as plain classes.
globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });

const M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
const { cityApi, sel, objects, selectors: S, registry: R, ws, watches: W, mask, bins: B, tm, csv: C, scope: SC, ex: EX, fig: F, vit: VIT, packs: P, commandBar, t } = M;
const { selection } = sel;

// ─── the fixture world ──────────────────────────────────────────────────────

const FX = JSON.parse(readFileSync(FIXTURE, 'utf8'));
const NOW = Date.parse(FX.as_of);
const V = FX.vehicle;
const feedById = new Map(FX.feed.items.map((i) => [i.id, i]));
const MIN = 60_000;
const iso = (off) => new Date(NOW + off).toISOString();
const NEWS = '6c5d9f41-2e70-4cad-9f54-8a9b0c1d2e34';
const SOCIAL = '7d6e0a52-3f81-4dbe-8a65-9b0c1d2e3f45';
/** Fictional objects of mixed provenance (as the harness adds them). */
const EXTRAS = [
	{ kind: 'junction', id: '15', label: 'Hindmata', lon: 72.8607, lat: 19.0021, state: 'green', source: 'live', t: iso(-40_000), links: ['segment:1049'], props: { junction_type: 'roundabout' } },
	{ kind: 'segment', id: '1049', label: 'Dr Ambedkar Road (Parel flyover)', lon: 72.8584, lat: 19.0033, state: 'flowing', source: 'live', t: null, links: [], props: { road_name: 'Dr Ambedkar Road (Parel flyover)', data_quality: 'synthetic' } },
	{ kind: 'anomaly', id: '7622', label: 'speed_jump · medium', lon: 72.8322, lat: 18.9932, state: 'medium', source: 'live', t: iso(-6 * MIN), links: [], props: { road_name: 'Eastern Metropolitan Bypass', data_quality: 'synthetic' } },
	{ kind: 'osint_event', id: NEWS, label: 'Road accident · BKC connector', lon: 72.7701, lat: 19.0335, state: 'surfaced', source: 'osint', verification_state: 'NEWS-REPORTED', credibility: 0.65, t: iso(-35 * MIN), links: ['place:bkc_connector'], props: { toponym: 'BKC connector', window_start: iso(-48 * MIN), window_end: iso(-35 * MIN) } },
	{ kind: 'osint_event', id: SOCIAL, label: 'Waterlogging · Hindmata', lon: 72.8284, lat: 18.9940, state: 'surfaced', source: 'osint', verification_state: 'UNVERIFIED-OSINT', credibility: 0.35, t: iso(-22 * MIN), links: [], props: { toponym: 'Hindmata' } },
	{ kind: 'place', id: 'bkc_connector', label: 'BKC connector', lon: 72.7701, lat: 19.0335, state: null, source: 'osint', t: iso(-35 * MIN), links: [`osint_event:${NEWS}`], props: { feature_type: 'road', canonical_name: 'BKC connector' } },
];
const SNAP = cityApi.parseCitySnapshot({ ...FX.snapshot, entities: [...FX.snapshot.entities, ...EXTRAS] });
const DOSSIERS = FX.dossiers.map((d) => cityApi.parseDossier({ ...d, audit: d.audit.map((a) => (typeof a === 'string' ? feedById.get(a) : a)) }, NOW));
const FEED = cityApi.parseFeedRows(FX.feed);
const G = objects.buildObjectGraph({ entities: SNAP.entities, dossiers: DOSSIERS });
const REG = SNAP.entities.map((e) => G.get(e.urn)).filter(Boolean);
let UNITS = [];
const world = { graph: () => G, registry: () => REG, feed: () => FEED, units: () => UNITS, now: () => NOW };
const Q = S.createSelectors(() => world);
ok('fixture world builds (capture + mixed-provenance extras)', G.size > 50 && REG.length === FX.snapshot.entities.length + EXTRAS.length, `${G.size} objects · ${REG.length} registry rows`);

const memory = () => {
	const m = new Map();
	return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k) };
};

// ─── 1. Histogram ───────────────────────────────────────────────────────────

const ALL = G.all();
const groups = B.histogram(ALL, 'en');
ok('six groups in order: Kind, State, Source, Hour (IST), Road, Camera', eq(groups.map((g) => g.title), ['Kind', 'State', 'Source', 'Hour (IST)', 'Road', 'Camera']));

// hours sorted by TIME across midnight (lexicographic order would put 00:00 first)
const istHM = (h, m, day) => Date.parse(`2026-10-${day}T${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00+05:30`);
const night = [
	[23, 50, 23],
	[0, 10, 24],
	[1, 40, 24],
	[23, 20, 23],
	[0, 55, 24],
].map(([h, m, d], i) => ({ ...REG[0], urn: `sighting:00000000-0000-4000-8000-00000000000${i}`, kind: 'sighting', t: istHM(h, m, d), props: {} }));
const hourG = B.histogram(night, 'en').find((g) => g.field === 'hour');
ok('Hour bins are sorted by time across midnight (23:00, 00:00, 01:00)', eq(hourG.bins.map((b) => b.label), ['23:00', '00:00', '01:00']) && eq(hourG.bins.map((b) => b.n), [2, 2, 1]), hourG.bins.map((b) => `${b.label}×${b.n}`).join(' '));
const fxHours = groups.find((g) => g.field === 'hour').bins;
ok(
	'…and on the fixture (hours seen on several days) the bars follow the 24-hour cycle ending at the newest row',
	eq(fxHours.map((b) => b.label), ['20:00', '22:00', '23:00', '00:00', '01:00', '02:00', '03:00']) && fxHours.every((b, i) => i === 0 || (fxHours[i - 1].cycle ?? 0) < (b.cycle ?? 0)),
	fxHours.map((b) => b.label).join(' '),
);
ok('"1 value", "4 values" — never "1 values" (EN, HI, MR)', B.valuesLabel(1) === '1 value' && B.valuesLabel(4) === '4 values' && B.valuesLabel(1, 'hi') === '1 मान' && B.valuesLabel(1, 'mr') === '1 मूल्य' && !/1 values/.test(B.valuesLabel(1)));
ok('one-row groups say "1 value" in the Histogram sub', groups.every((g) => B.valuesLabel(g.bins.length) === (g.bins.length === 1 ? '1 value' : `${g.bins.length} values`)));

// ONE bar per filter value, and each bar counts exactly what a filter on its value keeps (no summing)
const hourOf = M.ws.hourOf;
const exact = [];
for (const g of groups) {
	const values = g.bins.map((b) => b.value);
	if (new Set(values).size !== values.length) exact.push(`${g.field}: two bars share a filter value (${values.join(',')})`);
	for (const b of g.bins) {
		const kept = ALL.filter((r) => W.passesFilter(r, { id: 'x', field: g.field, values: [b.value], label: '' }, hourOf)).length;
		if (kept !== b.n) exact.push(`${g.field}=${b.value}: bar ${b.n}, filter keeps ${kept}`);
	}
	const counted = g.bins.reduce((s, b) => s + b.n, 0) + g.missing;
	if (counted !== ALL.length) exact.push(`${g.field}: ${counted} counted of ${ALL.length}`);
	if (B.groupValues(g).length !== g.bins.length) exact.push(`${g.field}: ${B.groupValues(g).length} filter values, ${g.bins.length} bars`);
}
ok('one bar per filter value; every bar counts exactly the rows its filter keeps; bars + "without a value" = the rows', exact.length === 0, exact.slice(0, 4).join(' | ') || `${groups.reduce((n, g) => n + g.bins.length, 0)} bars`);

// a selection becomes filters: one per group, values OR-ed, groups AND-ed
const pick = new Map([
	['kind', new Set(['sighting', 'camera'])],
	['source', new Set(['emulated'])],
]);
const toF = B.filtersTo(groups, pick, 'en');
const keptTo = ALL.filter((r) => W.passesFilters(r, toF.map((f, i) => ({ ...f, id: `f${i}` })), hourOf));
const want = ALL.filter((r) => (r.kind === 'sighting' || r.kind === 'camera') && r.source === 'emulated');
ok(
	'"Filter to": one filter per group with a pick (Kind: Sighting, Camera · Source: Emulated); it keeps exactly the picked rows',
	toF.length === 2 && toF[0].field === 'kind' && eq([...toF[0].values].sort(), ['camera', 'sighting']) && toF[0].label === 'Sighting, Camera' && toF[1].label === 'Emulated' && keptTo.length === want.length && keptTo.length > 0,
	`${toF.map((f) => `${f.field}: ${f.label}`).join(' · ')} → ${keptTo.length} rows`,
);
const store = new ws.Workspace({ world: () => world, storage: memory, now: () => NOW });
const added = toF.map((f) => store.addFilter(f));
ok('"Filter to" goes through workspace.addFilter (labels kept, ids issued)', added.every((f) => typeof f.id === 'string' && f.id.startsWith('flt-')) && added[0].label === toF[0].label, added.map((f) => `${f.id} ${f.label}`).join(', '));

// ONE open-source bar; its verification states are a breakdown to read, never a value to pick
const src = groups.find((g) => g.field === 'source');
const osintBins = src.bins.filter((b) => b.value === 'osint');
const osBar = osintBins[0];
const parts = osBar?.parts ?? [];
ok(
	'one open-source bar, "Open-source", with its rows by verification state (News-reported 1, Unverified OSINT 1, No verification state 1)',
	osintBins.length === 1 &&
		osBar.label === 'Open-source' &&
		osBar.n === 3 &&
		eq(parts.map((p) => [p.verification, p.label, p.n]), [['NEWS-REPORTED', 'News-reported', 1], ['UNVERIFIED-OSINT', 'Unverified OSINT', 1], [null, 'No verification state', 1]]) &&
		parts.reduce((n, p) => n + p.n, 0) === osBar.n &&
		src.bins.every((b) => (b.value === 'osint') === (b.parts !== null)),
	`${osBar?.label} ${osBar?.n}: ${parts.map((p) => `${p.label} ${p.n}`).join(' | ')}`,
);
const srcValues = new Set(ALL.map((r) => r.source));
ok('the Source header counts the values a filter can keep ("n values" = distinct sources, one bar each)', src.bins.length === srcValues.size && B.valuesLabel(src.bins.length) === `${srcValues.size} values`, `${B.valuesLabel(src.bins.length)}: ${[...srcValues].join(', ')}`);
const osintF = B.filtersTo(groups, new Map([['source', new Set(['osint'])]]), 'en');
ok('…and its filter keeps exactly the bar\'s rows, every open-source row whatever the state', osintF.length === 1 && eq(osintF[0].values, ['osint']) && osintF[0].label === 'Open-source' && ALL.filter((r) => W.passesFilter(r, { ...osintF[0], id: 'o' }, hourOf)).length === osBar.n);
const strongFirst = B.verificationParts([{ verification: null }, { verification: 'UNVERIFIED-OSINT' }, { verification: 'CONFIRMED' }, { verification: 'NEWS-REPORTED' }, { verification: 'OFFICIAL-VERIFIED' }, { verification: 'UNVERIFIED-OSINT' }], 'en');
ok('the breakdown lists the strongest state first, rows without one last (Confirmed … Unverified, then none)', eq(strongFirst.map((p) => p.verification), ['CONFIRMED', 'OFFICIAL-VERIFIED', 'NEWS-REPORTED', 'UNVERIFIED-OSINT', null]) && strongFirst[3].n === 2, strongFirst.map((p) => `${p.label} ${p.n}`).join(' | '));
// the reviewer's case: picking the open-source bar and "Filter to" keeps the bar's 3 rows, no more
const pickOsint = B.filtersTo(groups, new Map([['source', new Set(['osint'])]]), 'en');
ok('a pick of the open-source bar is one value: "Filter to" keeps exactly its rows', pickOsint.length === 1 && pickOsint[0].values.length === 1 && ALL.filter((r) => W.passesFilters(r, pickOsint.map((f, i) => ({ ...f, id: `p${i}` })), hourOf)).length === osBar.n);

// a pick whose value is gone (the rows changed under it) no longer counts: "Filter to" never stays primary over nothing
const camOnly = ALL.filter((r) => r.kind === 'camera');
const stalePick = { kind: ['sighting'], source: ['emulated'] };
const liveHere = B.livePicks(groups, stalePick);
const liveThere = B.livePicks(B.histogram(camOnly, 'en'), { kind: ['sighting'] });
ok(
	'a stale pick drops out: a value that is no longer a bar is no pick, and "Filter to" has nothing to apply',
	B.hasPicks(liveHere) && liveHere.get('kind').has('sighting') && !B.hasPicks(liveThere) && B.filtersTo(B.histogram(camOnly, 'en'), liveThere, 'en').length === 0,
	`${camOnly.length} camera rows; kind picks there: ${liveThere.get('kind').size}`,
);

// "Filter out" only where exact
const kindG = groups.find((g) => g.field === 'kind');
const stateG = groups.find((g) => g.field === 'state');
const outK = B.filtersOut(groups, new Map([['kind', new Set(['camera'])]]), 'en');
ok('"Filter out" Camera = filter to the other kinds, labelled "Not Camera"', !!outK && outK[0].label === 'Not Camera' && !outK[0].values.includes('camera') && outK[0].values.length === B.groupValues(kindG).length - 1);
ok('"Filter out" is refused where rows have no value (State: some rows have none)', stateG.missing > 0 && B.filtersOut(groups, new Map([['state', new Set([stateG.bins[0].value])]]), 'en') === null && !B.canFilterOut(stateG, new Set([stateG.bins[0].value])));
const many = B.joinWords(Array.from({ length: 30 }, (_, i) => `Synthetic road number ${i}`), 'en');
ok('a long filter label stays within the store\'s 80 characters ("…, +n")', many.length <= 80 && /\+\d+$/.test(many), `${many.length} chars: ${many}`);

// ─── 2. Table rows = (selection ∪ linked) ∩ filters ─────────────────────────

const linked = Q.linked(V);
selection.select(V, { source: 'table' });
const W1 = new ws.Workspace({ world: () => world, storage: memory, now: () => NOW });
const manual = (filters) => [G.get(V), ...linked].filter((r) => W.passesFilters(r, filters, hourOf));
const set1 = W1.objectSet.map((r) => r.urn);
ok('no filter: the table holds the selection and its linked objects (1 + linked)', set1.length === 1 + linked.length && set1[0] === V && eq(new Set(set1), new Set(manual([]).map((r) => r.urn))), `${set1.length} rows = 1 + ${linked.length} linked`);
const kf = W1.addFilter({ field: 'kind', values: ['sighting', 'camera'], label: 'Sighting, Camera' });
const set2 = W1.objectSet.map((r) => r.urn);
const viaModel = tm.selectionRows(G, (u) => Q.linked(u), V, selection.items, W1.filters).map((r) => r.urn);
ok(
	'with a kind filter: (selection ∪ linked) ∩ filters — the store, the table model and a by-hand count agree',
	eq(set2, viaModel) && eq(new Set(set2), new Set(manual(W1.filters).map((r) => r.urn))) && set2.length === 27,
	`${set2.length} rows (21 reads + 6 cameras)`,
);
ok('the header meta reads "27 rows · kind filter"', tm.headerMeta(set2.length, W1.filters, 'en').join(' · ') === '27 rows · kind filter');
ok('the header title reads "and its 51 linked objects" (1: "and its 1 linked object")', t('en', 'vw_t_linked', 51) === 'and its 51 linked objects' && t('en', 'vw_t_linked', 1) === 'and its 1 linked object');
W1.removeFilter(kf.id);
// the table's default rows: the same rule over a scope the table's own clicks never move
const scoped = tm.scopedRows(G, (u) => Q.linked(u), { primary: V, items: selection.items }, []).map((r) => r.urn);
ok('the table scope\'s rows = the store\'s objectSet for a selection made elsewhere', eq(scoped, W1.objectSet.map((r) => r.urn)), `${scoped.length} rows`);
const aCamera = linked.find((r) => r.kind === 'camera').urn;
selection.select(V, { source: 'map' });
const s0 = SC.tableScope.scope?.primary;
selection.select(aCamera, { source: 'table' });
const s1 = SC.tableScope.scope?.primary;
const objectSetMoved = W1.objectSet[0]?.urn;
selection.select(aCamera, { mode: 'toggle', source: 'table' });
selection.select(aCamera, { source: 'map' });
const s2 = SC.tableScope.scope?.primary;
selection.clear();
const s3 = SC.tableScope.scope;
ok(
	'a click in the table changes the selection, never the table: the scope stays; another view\'s pick moves it; clearing empties it',
	s0 === V && s1 === V && objectSetMoved === aCamera && s2 === aCamera && s3 === null,
	`${s0 === V} · ${s1 === V} (objectSet moved to ${objectSetMoved === aCamera ? 'the camera' : objectSetMoved}) · ${s2 === aCamera} · ${s3}`,
);
// a Ctrl+click that empties the selection keeps the scope (the store forgets the source on an empty selection)
selection.select(V, { source: 'map' });
const k0 = SC.tableScope.scope?.primary;
SC.tableScope.select(V, 'toggle');
const k1 = SC.tableScope.scope?.primary;
const emptied = selection.current === null && selection.items.length === 0;
selection.clear();
const k2 = SC.tableScope.scope;
ok('a Ctrl+click that empties the selection keeps the table\'s scope; a clear from another view then empties it', k0 === V && emptied && k1 === V && k2 === null, `${k0 === V} · emptied ${emptied} · kept ${k1 === V} · ${k2}`);
// a lasso, then a Ctrl+click on its primary in the table: the primary moves inside the selection, the scope stays
const lassoed = linked.filter((r) => r.kind === 'camera').slice(0, 3).map((r) => r.urn);
selection.selectMany(lassoed, { source: 'lasso' });
const l0 = SC.tableScope.scope?.primary;
SC.tableScope.select(lassoed[0], 'toggle');
const l1 = SC.tableScope.scope?.primary;
ok('a Ctrl+click on a lasso\'s primary in the table moves the primary, never the table', l0 === lassoed[0] && selection.current !== lassoed[0] && l1 === lassoed[0], `${l0 === lassoed[0]} · primary now ${selection.current?.slice(0, 14)} · scope ${l1 === lassoed[0]}`);
selection.clear();

// the rows IN THE TABLE: the mounted table's (whatever the page passed it), else the default scope
selection.select(V, { source: 'map' });
const defaultRows = SC.tableScope.rows();
const before = SC.tableScope.inTable();
const pageRows = tm.kindRows(G, 'sighting');
const tA = Symbol('a');
const tB = Symbol('b');
SC.tableScope.publish(tA, pageRows);
const withA = SC.tableScope.inTable();
SC.tableScope.publish(tB, defaultRows);
const withB = SC.tableScope.inTable();
SC.tableScope.release(tB);
const afterB = SC.tableScope.inTable();
SC.tableScope.release(tA);
const afterA = SC.tableScope.inTable();
ok(
	'the Histogram\'s rows are the table\'s: a page\'s rows while that table is mounted (2nd table newest), the default scope once none is',
	eq(before.map((r) => r.urn), defaultRows.map((r) => r.urn)) && withA === pageRows && withB === defaultRows && afterB === pageRows && SC.tableScope.shown === null && eq(afterA.map((r) => r.urn), defaultRows.map((r) => r.urn)) && pageRows.length !== defaultRows.length,
	`default scope ${defaultRows.length} (node's live world is empty) · page ${pageRows.length} · one table leaving never blanks the other`,
);
// the reviewer's case: a 500-row table passed by the page and a Histogram without props count the same rows
const synth = Array.from({ length: 500 }, (_, i) => ({ ...G.get(V), urn: `sighting:00000000-0000-4000-8000-${String(i).padStart(12, '0')}`, kind: 'sighting', id: String(i) }));
const tSynth = Symbol('synthetic');
SC.tableScope.publish(tSynth, synth);
const histRows = SC.tableScope.inTable();
const histTotal = B.histogram(histRows, 'en').find((g) => g.field === 'kind').bins.reduce((n, b) => n + b.n, 0);
SC.tableScope.release(tSynth);
ok('a page\'s 500-row table: the prop-less Histogram counts all 500 (never the default scope\'s rows)', histRows.length === 500 && histTotal === 500 && defaultRows.length !== 500, `table 500 · histogram ${histRows.length}`);
selection.clear();

ok('no scope, or the omnibar\'s results explored: every object ∩ filters', tm.scopedRows(G, (u) => Q.linked(u), null, []).length === G.size && tm.scopedRows(G, (u) => Q.linked(u), { primary: V, items: [V] }, [{ id: 'u', field: 'urns', values: [aCamera], label: '' }]).map((r) => r.urn).join() === aCamera);
selection.select(V, { source: 'table' });
const camRows = tm.kindRows(G, 'camera');
ok('an Explorer kind\'s rows: every object of the kind (filters applied)', camRows.length === G.byKind('camera').length && camRows.every((r) => r.kind === 'camera'), `${camRows.length} cameras`);
ok('a click replaces, Ctrl/Cmd toggles, Shift adds; a key replaces', tm.clickMode({}) === 'replace' && tm.clickMode({ ctrlKey: true }) === 'toggle' && tm.clickMode({ metaKey: true }) === 'toggle' && tm.clickMode({ shiftKey: true }) === 'add' && tm.clickMode({ type: 'keydown', shiftKey: true }) === 'replace');
selection.clear();

// ─── 3. The Source column only for mixed rows ───────────────────────────────

// the vehicle, its reads and its cameras are all emulated; its pursuits are live rows
const uniformRows = [G.get(V), ...linked].filter((r) => r.kind !== 'event');
const mixedRows = ALL;
ok('a uniform list (the vehicle, its reads, cameras and recommendations, all emulated): no Source column; provenance once in the header', !tm.isMixed(uniformRows) && tm.uniformSource(uniformRows) === 'emulated' && !tm.columnKeys(uniformRows).includes('source'), `${uniformRows.length} rows`);
ok('the vehicle with ALL its links (two live pursuits among them) is mixed: the Source column shows', tm.isMixed([G.get(V), ...linked]) && tm.columnKeys([G.get(V), ...linked]).includes('source'));
ok('a mixed list (live, emulated, simulated, open-source): the Source column, before Links', tm.isMixed(mixedRows) && tm.uniformSource(mixedRows) === null && eq(tm.columnKeys(mixedRows), ['icon', 'label', 'kind', 'state', 't', 'place', 'speed', 'source', 'links']));
ok('…and a narrow pane sets Place, Speed and Links aside, never Source', eq(tm.columnKeys(mixedRows, () => false), ['icon', 'label', 'kind', 'state', 't', 'source']) && eq(tm.columnKeys(uniformRows, () => false), ['icon', 'label', 'kind', 'state', 't']));
const osintOnly = ALL.filter((r) => r.kind === 'osint_event' && r.verification === 'NEWS-REPORTED');
ok('a uniform open-source list states its verification once (tagVerification)', tm.uniformSource(osintOnly) === 'osint' && tm.tagVerification('osint', tm.uniformVerification(osintOnly)) === 'NEWS-REPORTED' && tm.tagVerification('emulated', 'NEWS-REPORTED') === null && tm.tagVerification('osint', 'EMULATED') === null);

// ethics rule 7: an open-source list whose states differ shows each row's own state (the header cannot state one)
const osintMixedVerif = ALL.filter((r) => r.kind === 'osint_event');
const headerVerif = (rows) => (tm.uniformSource(rows) === 'osint' ? tm.tagVerification('osint', tm.uniformVerification(rows)) : null);
const hvMixed = headerVerif(osintMixedVerif);
const shownMixed = osintMixedVerif.map((r) => tm.rowVerification(r, hvMixed));
ok(
	'open-source rows with different states (News-reported, Unverified OSINT): the header states none, so every row shows its own',
	osintMixedVerif.length === 2 && tm.uniformSource(osintMixedVerif) === 'osint' && hvMixed === null && eq(shownMixed, osintMixedVerif.map((r) => r.verification)) && eq([...shownMixed].sort(), ['NEWS-REPORTED', 'UNVERIFIED-OSINT']),
	osintMixedVerif.map((r, i) => `${r.label}: ${shownMixed[i]}`).join(' | '),
);
ok('…one shared state is stated once, in the header, and no row repeats it', headerVerif(osintOnly) === 'NEWS-REPORTED' && osintOnly.every((r) => tm.rowVerification(r, headerVerif(osintOnly)) === null));
ok(
	'…and in a mixed list each open-source row shows its state beside the Source glyph; other rows show none',
	headerVerif(mixedRows) === null &&
		mixedRows.filter((r) => r.source === 'osint' && r.verification).every((r) => tm.rowVerification(r, null) === r.verification) &&
		mixedRows.filter((r) => r.source !== 'osint').every((r) => tm.rowVerification(r, null) === null),
);

// the header names the rows honestly
const T = (o) => tm.tableTitle({ header: null, selectionScope: true, hasSubject: true, exploring: false, exploredKind: null, passed: false, rows: [], ...o });
ok(
	'the title: the selection names only its own scope; passed rows go by their kind or "Objects"; a header and search results win',
	T({}).kind === 'subject' &&
		T({ selectionScope: false, passed: true, rows: camRows }).kind === 'kind' &&
		T({ selectionScope: false, passed: true, rows: camRows }).of === 'camera' &&
		T({ selectionScope: false, passed: true, rows: ALL }).kind === 'objects' &&
		T({ selectionScope: false, passed: true, rows: ALL, exploredKind: 'osint_event' }).of === 'osint_event' &&
		T({ hasSubject: false }).kind === 'every' &&
		T({ header: 'Synthetic rows' }).text === 'Synthetic rows' &&
		T({ exploring: true }).kind === 'results' &&
		T({ exploredKind: 'osint_event' }).kind === 'subject',
);
ok('the store\'s objectSet passed through is the selection\'s scope (one identity while nothing changes)', W1.objectSet === W1.objectSet);
ok(
	'an explored kind with none linked to the selection explains itself ("No reported events are linked to MH47EM•••1"), and offers to clear the selection',
	tm.emptyReason({ rows: 0, exploredKind: 'osint_event', subject: true }) === 'kind-not-linked' &&
		tm.emptyReason({ rows: 0, exploredKind: null, subject: true }) === 'none' &&
		tm.emptyReason({ rows: 3, exploredKind: 'osint_event', subject: true }) === null &&
		t('en', 'vw_t_empty_kind', 'Reported events', 'MH47EM•••1') === 'No reported events are linked to MH47EM•••1' &&
		t('en', 'vw_t_empty_kind_hint', 'Reported events').endsWith('Clear the selection to see all reported events.') &&
		t('en', 'vw_t_empty_kind', 'ANPR reads', 'X') === 'No ANPR reads are linked to X',
	t('en', 'vw_t_empty_kind', 'Reported events', 'MH47EM•••1'),
);
ok('an open-source row states its credibility ("credibility 0.65")', t('en', 'vw_t_credibility', (0.65).toFixed(2)) === 'credibility 0.65' && ALL.find((r) => r.urn === `osint_event:${NEWS}`).credibility === 0.65);

// ─── 4. Fading obeys protected objects ──────────────────────────────────────

// a window at 00:00–00:30 IST on the capture day: the vehicle's newest reads (01:24–01:38) fall outside
const w = [Date.parse('2026-10-24T00:00:00+05:30'), Date.parse('2026-10-24T00:30:00+05:30')];
const pendingRec = linked.find((r) => r.kind === 'recommendation' && r.state === 'pending');
const otherRec = linked.find((r) => r.kind === 'recommendation' && r.urn !== pendingRec.urn && (r.t ?? 0) > w[1]);
const aRead = linked.find((r) => r.kind === 'sighting' && (r.t ?? 0) > w[1]);
const aCam = linked.find((r) => r.kind === 'camera');
UNITS = [];
const fadedBefore = tm.fades(pendingRec, w, Q.inWindow);
UNITS = [{ kind: 'echallan', id: pendingRec.id, subjectUrn: pendingRec.urn, title: 'Decide', deadline: null, severity: 1, homes: { '/': 'inbox', '/gods-eye': 'inbox', '/ops': 'decisions' } }];
const Qp = S.createSelectors(() => world);
ok(
	'outside the window: a read and a decided recommendation fade; a camera (infrastructure) never does',
	tm.fades(aRead, w, Qp.inWindow) && tm.fades(otherRec, w, Qp.inWindow) && !tm.fades(aCam, w, Qp.inWindow),
	`read ${tm.fades(aRead, w, Qp.inWindow)} · rec ${tm.fades(otherRec, w, Qp.inWindow)} · camera ${tm.fades(aCam, w, Qp.inWindow)}`,
);
ok('a protected object (a waiting decision\'s subject) never fades, though outside the window', fadedBefore === true && tm.fades(pendingRec, w, Qp.inWindow) === false && Qp.protectedUrns().has(pendingRec.urn));
ok('no window: nothing fades', ALL.every((r) => !tm.fades(r, null, Qp.inWindow)));

// ─── 5. CSV: always masked, with provenance and verification ────────────────

commandBar.officer = { value: 'Sandbox Officer', fromSession: false, set() {} };
const leaky = [
	{ ...G.get(V), label: 'MH47EM9001', sublabel: 'mh 47 em 9001', props: { ...G.get(V).props, last_camera_id: 'EM-CAM-03' } },
	{ ...ALL.find((r) => r.kind === 'recommendation'), label: 'Stolen MH.47.EM.9001 at EM-CAM-03', props: { evidence: { road_name: 'near MH-01-AB-1234', speed_kmh: 95 } } },
	{ ...ALL.find((r) => r.urn === `osint_event:${NEWS}`) },
	{ ...ALL.find((r) => r.kind === 'camera'), label: '=HYPERLINK("x")' },
];
const out = C.toCsv(leaky, { lang: 'en', get: (u) => G.get(u), links: (u) => Q.linked(u).length });
const lines = out.trimEnd().split('\r\n');
ok('CSV: no raw registration mark, in any spelling, even with an officer named', commandBar.officer?.value === 'Sandbox Officer' && !mask.hasRawMark(out) && out.includes('MH47EM•••1') && out.includes('MH.47.EM.•••1') && out.includes('MH-01-AB-•••4'), lines[1]);
const header = lines[0].split(',');
ok('CSV: a header line with Provenance, Verification and Credibility columns', eq(header, ['Object ID', 'Object', 'Type', 'State', 'Time (IST)', 'Place', 'Speed (km/h)', 'Links', 'Provenance', 'Verification', 'Credibility', 'Test']), lines[0]);
const osintLine = lines.find((l) => l.includes(`osint_event:${NEWS}`));
const vehLine = lines.find((l) => l.startsWith(V));
ok('CSV: an open-source row carries Open-source, NEWS-REPORTED and 0.65; an emulated row Emulated and no verification', /,Open-source,NEWS-REPORTED,0\.65,/.test(osintLine ?? '') && /,Emulated,,,/.test(vehLine ?? ''), `${osintLine} | ${vehLine}`);
ok('CSV: times in IST ("2026-10-24 01:38:37")', (vehLine ?? '').includes(C.istStamp(G.get(V).t)) && C.istStamp(Date.parse('2026-10-23T20:08:37.889Z')) === '2026-10-24 01:38:37');
ok('CSV: a formula-looking cell is guarded with an apostrophe and quoted when it holds a quote', out.includes(`"'=HYPERLINK(""x"")"`) && C.csvCell('a,b') === '"a,b"' && C.csvCell('+1') === "'+1" && C.csvCell(12) === '12');
ok('CSV: one line per row plus the header, CRLF line ends', lines.length === leaky.length + 1 && out.endsWith('\r\n'));
ok('CSV: the file name is IST-stamped', /^sajag-objects-\d{4}-\d{2}-\d{2}-\d{4}-ist\.csv$/.test(C.csvFileName(NOW)), C.csvFileName(NOW));
commandBar.officer = null;

// ─── 6. The vitals card and the Explorer read one selector ──────────────────

UNITS = [];
const card = F.cardFigures({ selectors: Q, registry: REG, unitSources: 0 });
const kinds = EX.explorerKinds(REG, (k) => Q.count(k), 'en');
const exVehicles = kinds.find((k) => k.kind === 'vehicle');
ok('the card\'s watchlisted vehicles = count(\'vehicle\') = the Explorer\'s Vehicles figure', card.watchlisted === Q.count('vehicle') && exVehicles.n === card.watchlisted && card.watchlisted === 1, `card ${card.watchlisted} · count ${Q.count('vehicle')} · Explorer ${exVehicles.n}`);
ok('the card: cameras answering of all, feed anomalies, reported events, simulated traffic feed', card.cameras.total === Q.count('camera') && card.cameras.answering === REG.filter((r) => r.kind === 'camera' && r.state === 'active').length && card.anomalies === 1 && card.reported === 2 && card.trafficSimulated === true, JSON.stringify(card));
ok('decisions waiting, no unit source: the §7.4 rule on the registry (6 pending sightings of one vehicle = 1 unit)', card.decisions === 1 && card.decisionsFromUnits === false);
UNITS = [
	{ kind: 'stolen_sightings', id: V, subjectUrn: V, title: 'a', deadline: null, severity: 2, homes: {} },
	{ kind: 'echallan', id: 'e1', subjectUrn: 'recommendation:x', title: 'b', deadline: null, severity: 1, homes: {} },
];
const card2 = F.cardFigures({ selectors: Q, registry: REG, unitSources: 1, escortProposals: 3 });
ok('decisions waiting with a unit source registered: decisionUnits() (escorts are units there already)', card2.decisions === Q.decisionUnits().length && card2.decisions === 2 && card2.decisionsFromUnits);
ok('the registry rule counts escorts and dispatch requests as units', F.registryUnits(REG, 2) === 3 && F.registryUnits([{ ...REG[0], kind: 'dispatch', state: 'requested', test: false, props: {} }]) === 1);
// the Watches' "Decision needed" is the card's figure, with and without a unit source (never 0 beside a 4)
const watchNoSource = F.decisionsWaiting({ selectors: Q, registry: REG, unitSources: 0, escortProposals: 3 });
const cardNoSource = F.cardFigures({ selectors: Q, registry: REG, unitSources: 0, escortProposals: 3 });
const watchSource = F.decisionsWaiting({ selectors: Q, registry: REG, unitSources: 1, escortProposals: 3 });
ok(
	'Watches "Decision needed" = the card\'s "Decisions waiting": the registry rule before a unit source loads, decisionUnits() after',
	watchNoSource.n === cardNoSource.decisions && watchNoSource.n === 4 && !watchNoSource.fromUnits && watchSource.n === card2.decisions && watchSource.fromUnits,
	`no source: watches ${watchNoSource.n} · card ${cardNoSource.decisions}; with a source: ${watchSource.n} · ${card2.decisions}`,
);
UNITS = [];

// ─── 7. The Explorer ────────────────────────────────────────────────────────

const kindIds = kinds.map((k) => k.kind);
ok('the Explorer lists the canonical kinds, open-source reports and places included', EX.KIND_ORDER.every((k) => kindIds.includes(k)) && kindIds.includes('osint_event') && kindIds.includes('place'));
const withFuture = EX.explorerKinds([...REG, { ...REG[0], urn: 'future_kind:1', kind: 'future_kind', test: false }], (k) => (k === 'future_kind' ? 1 : Q.count(k)), 'en');
ok('…and any other kind the registry holds (the generic adapter)', withFuture.some((k) => k.kind === 'future_kind' && k.n === 1 && k.label === 'Future kind'), withFuture.at(-1)?.label);
const word = (k) => kinds.find((x) => x.kind === k)?.word;
ok('one state word each: "6 pending", "on watchlist", "1 unverified", "6 active"', word('recommendation') === '6 pending' && word('vehicle') === 'on watchlist' && word('osint_event') === '1 unverified' && word('camera') === '6 active', `${word('recommendation')} · ${word('vehicle')} · ${word('osint_event')} · ${word('camera')}`);
ok('a kind with nothing in the registry reads 0 (dimmed) with no state word', kinds.find((k) => k.kind === 'convoy').n === 0 && kinds.find((k) => k.kind === 'convoy').word === null);
ok('the explored kind is one kind filter with one value', EX.exploredKind([{ id: 'a', field: 'kind', values: ['camera'], label: '' }]) === 'camera' && EX.exploredKind([{ id: 'a', field: 'kind', values: ['camera', 'vehicle'], label: '' }]) === null && EX.exploredKind([]) === null);

// saved views: "edited" only once the workspace moves away
const W2 = new ws.Workspace({ world: () => world, storage: memory, now: () => NOW });
selection.select(V, { source: 'table' });
W2.view = 'table';
const saved = W2.saveView('Haji Ali · stolen vehicle');
const sigNow = () => EX.viewSignature({ view: W2.view, timeWindow: W2.timeWindow, filters: W2.filters, items: selection.items, sel: selection.current });
const same = EX.savedSignature(saved.hash) === sigNow();
W2.addFilter({ field: 'kind', values: ['camera'], label: 'Camera' });
const moved = EX.savedSignature(saved.hash) !== sigNow();
W2.clearFilters();
W2.applyView(saved.id);
const back = EX.savedSignature(saved.hash) === sigNow();
ok('a saved view is not "edited" as saved, is once a filter is added, and is not again once applied', same && moved && back, `${same} · ${moved} · ${back}`);
const named = W2.saveView('Watch mh 47 em 9001');
ok('a saved view\'s name is masked by the store (any spelling)', !mask.hasRawMark(named.name) && !mask.hasRawMark(named.hash), named.name);
selection.clear();

// a watch on any selected object: a long label, or one with < > `, becomes a title the store accepts (never a throw)
const longLabel = `Road accident · ${'BKC connector service lane near the flyover '.repeat(3)}`;
const odd = 'Waterlogging <near> the `underpass`';
const longTitle = EX.watchTitle(longLabel);
const oddTitle = EX.watchTitle(odd);
let threw = null;
let added2 = [];
try {
	added2 = [W2.addWatch({ title: longTitle, subjectUrn: `osint_event:${NEWS}`, filters: [] }), W2.addWatch({ title: oddTitle, subjectUrn: `osint_event:${SOCIAL}`, filters: [] })];
} catch (e) {
	threw = e;
}
ok(
	'a watch title from any label: cut to 80 characters with an ellipsis, < > ` dropped, and the store keeps it',
	longTitle.length <= 80 && longTitle.length >= 72 && longTitle.endsWith('…') && oddTitle === 'Waterlogging near the underpass' && !threw && added2.length === 2 && W.cleanWatch({ id: 'w', title: longLabel, subjectUrn: V, filters: [] }) === null && EX.watchTitle('  ') === null && EX.watchTitle('Report <x>') === 'Report x',
	`${longTitle.length} chars · "${oddTitle}" · ${threw ? `threw: ${threw.message}` : 'no throw'}`,
);

// ─── 7b. The vitals store: a seeded harness, one listener, the snapshot ─────

const listeners = new Set();
const realDocument = globalThis.document;
const realFetch = globalThis.fetch;
globalThis.document = { hidden: false, addEventListener: (k, f) => k === 'visibilitychange' && listeners.add(f), removeEventListener: (k, f) => listeners.delete(f) };
// no request leaves this process: every poll is answered by a refusal, a few ms later
globalThis.fetch = () => new Promise((_, reject) => setTimeout(() => reject(new Error('unit test: no network')), 5));
const cv = new VIT.cityVitals.constructor();
cv.start();
const startedTimers = cv.timers.length;
const startedListeners = listeners.size;
const FIX = { msgsPerMin: 42, lastMsgAgeSec: 2, connected: true, enabled: true, subscribed: true, emulatedLastMsgAgeSec: 3, rowsWritten5m: 1, subjects: [] };
cv.seed({ ingest: FIX });
const seededListeners = listeners.size;
const seededTimers = cv.timers.length;
await new Promise((r) => setTimeout(r, 40)); // the polls start() fired settle (refused) while seeded
const keptFixture = cv.ingest.state === 'ok' && cv.ingest.value === FIX && cv.brain.state === 'idle';
cv.unseed();
const unseededListeners = listeners.size;
const unseededTimers = cv.timers.length;
cv.stop();
ok(
	'seed() drops the timers and the visibility listener, and answers in flight never replace the fixture',
	startedTimers === 4 && startedListeners === 1 && seededListeners === 0 && seededTimers === 0 && keptFixture,
	`started ${startedTimers} timers/${startedListeners} listener · seeded ${seededTimers}/${seededListeners} · fixture kept ${keptFixture}`,
);
ok('unseed() polls again for the page that holds the store, with ONE listener; stop() drops it', unseededListeners === 1 && unseededTimers === 4 && listeners.size === 0 && cv.timers.length === 0, `unseeded ${unseededTimers}/${unseededListeners} · stopped ${cv.timers.length}/${listeners.size}`);
await new Promise((r) => setTimeout(r, 20));
globalThis.document = realDocument;
globalThis.fetch = realFetch;
const va = Symbol('card');
const vb = Symbol('info');
const n1 = cv.attach(va);
const n2 = cv.attach(vb);
cv.shown = { posture: null };
cv.detach(va);
const keptShown = cv.shown !== null;
cv.detach(vb);
ok('two mounted variants: attach() says 2 (the page bug the component warns about); the snapshot goes only with the last one', n1 === 1 && n2 === 2 && keptShown && cv.shown === null);

// ─── 8. Labels through the formatter ────────────────────────────────────────

const runs = tm.labelRuns('Pursuit of MH47EM•••1 near EM-CAM-03');
ok('a label: text, the masked mark as a Plate run, the camera as an Id run', eq(runs, [{ text: 'Pursuit of ' }, { plate: 'MH47EM•••1', masked: true }, { text: ' near ' }, { id: 'EM-CAM-03' }]), JSON.stringify(runs));
ok('a raw mark in a label is masked before it becomes a run', eq(tm.labelRuns('MH47EM9001'), [{ plate: 'MH47EM•••1', masked: true }]));
ok('plain words stay text ("BKC connector" is not an id)', eq(tm.labelRuns('Road accident · BKC connector'), [{ text: 'Road accident · BKC connector' }]));
ok(
	'place and speed: a read at its camera\'s road, a recommendation at its evidence road, a report at its place',
	tm.placeOf(linked.find((r) => r.kind === 'sighting'), (u) => G.get(u)) === G.get(`camera:${linked.find((r) => r.kind === 'sighting').props.camera_id}`)?.sublabel &&
		tm.placeOf(ALL.find((r) => r.kind === 'recommendation')) === ALL.find((r) => r.kind === 'recommendation').props.evidence.road_name &&
		tm.placeOf(ALL.find((r) => r.urn === `osint_event:${NEWS}`)) === 'BKC connector' &&
		tm.speedOf(ALL.find((r) => r.kind === 'recommendation')) === 95,
);

// ─── 9. The pack and the ethics of the fixtures ─────────────────────────────

const { en, hi, mr } = P.VIEWS_PACKS;
const enKeys = Object.keys(en).sort();
ok('EN, HI and MR carry the same keys', eq(enKeys, Object.keys(hi).sort()) && eq(enKeys, Object.keys(mr).sort()), `${enKeys.length} keys`);
const SRC_FILES = [];
(function walk(dir) {
	for (const f of readdirSync(dir)) {
		const p = path.join(dir, f);
		if (statSync(p).isDirectory()) walk(p);
		else if (/\.(svelte|ts)$/.test(f)) SRC_FILES.push(p);
	}
})(path.join(DECK, 'src/lib/workspace/components'));
SRC_FILES.push(path.join(DECK, 'src/lib/gods-eye/hud/CityVitals.svelte'), path.join(DECK, 'src/routes/(deck)/design/views/+page.svelte'));
const used = new Set();
for (const f of SRC_FILES) for (const m of readFileSync(f, 'utf8').matchAll(/['"`](vw_[a-z0-9_]+)['"`]/g)) used.add(m[1]);
const dynamic = ['vw_ex_state_', 'vw_i_', 'vw_src_', 'vw_t_col_', 'vw_t_filter_'];
ok('the new keys exist in EN, HI and MR', ['vw_h_missing_road', 'vw_h_missing_road_hint', 'vw_h_no_state', 'vw_h_parts', 'vw_t_objects', 'vw_t_empty_kind', 'vw_t_empty_kind_hint', 'vw_t_clear_selection', 'vw_t_credibility', 'vw_t_credibility_hint', 'vw_w_refused', 'vw_w_filters_title'].every((k) => k in P.VIEWS_PACKS.en && k in P.VIEWS_PACKS.hi && k in P.VIEWS_PACKS.mr));
ok('the Watches copy promises nothing the Inbox does not do (no "Inbox" in the hint or the empty text)', !/inbox/i.test(t('en', 'vw_w_hint')) && !/inbox/i.test(t('en', 'vw_w_empty')) && /never mutes an interrupt/.test(t('en', 'vw_w_hint')));
const missing = [...used].filter((k) => !dynamic.includes(k) && !(k in en));
ok('every vw_ key the views use exists in the pack', missing.length === 0 && used.size > 100, missing.join(', ') || `${used.size} keys used`);
const dyn = ['vw_ex_state_pending', 'vw_ex_state_requested', 'vw_ex_state_proposed', 'vw_ex_state_active', 'vw_ex_state_en_route', 'vw_ex_state_on_scene', 'vw_i_connected', 'vw_i_loading', 'vw_i_unreachable', 'vw_src_live', 'vw_src_emulated', 'vw_src_simulated', 'vw_src_test', 'vw_src_osint', 'vw_t_col_place', 'vw_t_col_speed', 'vw_t_col_links', 'vw_t_filter_urns', 'vw_t_filter_kind', 'vw_t_filter_state', 'vw_t_filter_source', 'vw_t_filter_hour', 'vw_t_filter_road', 'vw_t_filter_camera'];
ok('…and every key built at run time', dyn.every((k) => k in en), dyn.filter((k) => !(k in en)).join(', ') || `${dyn.length} keys`);
ok('the held line reads as the smoke expects ("Held 3 h 50 min · since 21:41 IST")', /^held (?:3h5\dm|3 h 5\d min) · since \d{2}:\d{2} IST$/i.test(t('en', 'vw_i_held', '3 h 50 min', '21:41 IST')));
const PERSON_KEY_RE = /author|person|handle|username|byline|reporter|poster|uploader|suspect|accused|victim|owner|driver_name|face|biometric|individual_/i;
const harness = readFileSync(path.join(DECK, 'src/routes/(deck)/design/views/+page.svelte'), 'utf8');
const keysIn = [...harness.matchAll(/\b([a-z_]+):\s/g)].map((m) => m[1]);
ok('the harness fixtures carry no person field and no raw mark', !keysIn.some((k) => PERSON_KEY_RE.test(k)) && !mask.hasRawMark(harness) && !EXTRAS.some((e) => Object.keys(e.props).some((k) => PERSON_KEY_RE.test(k))));

console.log(failures ? `\n${failures} failure(s)` : '\nviews.unit: all green');
process.exit(failures ? 1 : 0);
