/**
 * V3 object page unit test (V3-P3; V3-SPEC §5.4, §6.3, §6.4, §8) — zero browser.
 *
 *   node tests/object-page.unit.mjs
 *
 * esbuild bundles the REAL modules — src/lib/v3/object/{model, view, packs.object*}, the kind adapters, the
 * osint model, decisions/{units, register}, the ops store and the city registry — with `$lib` aliased, rune
 * identity stubs and every `.svelte` component stubbed (the home.unit.mjs harness). A fetch stub answers every
 * GET from the hermetic fixture world of tests/object-page-smoke.mjs (refusing any non-GET).
 *
 * Asserts:
 *   - the pack: EN / HI / MR carry the same `obj_` keys; every obj_ key the object code uses exists; ≤ one
 *     " · " per EN string; HI holds no Marathi and MR no Devanagari; HI / MR are translated
 *   - the route: objectHref ↔ urnFromParam round-trip; hostile parameters name nothing
 *   - tabs per kind; the tablist keys (→ ← wrap, Home, End)
 *   - provenance: ONE honest label — test first, then emulated, simulated, and an OSINT row's verification
 *     (a missing or unknown label reads Unverified, never more); a gazetteer place and a live record carry none
 *   - OSINT: a context member is never a reporting source, never counted, never makes "official" true;
 *     officialness rides the TIER (an aggregator on a .gov.in address is not official); a link only for an
 *     official tier's https url (never http:, javascript:, a news source); the ladder; the ring radius
 *   - art: every illustration the page can ask for exists in static/ (never a photo: SVG only)
 *   - the Map link: share-link grammar (style raw — never the thermal-style filter — layers, sel), no mark
 *   - with the fixture world: the report's decision card opens the DSS unit's one home; the vehicle's opens
 *     the stolen-sighting unit's; no raw mark in any view model (title, decision cards, activity, hero,
 *     facts, the adapter view) without an officer; a named officer unmasks; clearing masks again
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { objectFixtures } from './object-page-smoke.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const OUT = path.join(HERE, 'artifacts', 'object-page-bundle.mjs');
const OBJ = path.join(DECK, 'src/lib/v3/object');

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
export * as model from './src/lib/v3/object/model';
export * as view from './src/lib/v3/object/view';
export * as packs from './src/lib/v3/object/packs.object';
export { hi } from './src/lib/v3/object/packs.object.hi';
export { mr } from './src/lib/v3/object/packs.object.mr';
export * as osint from './src/lib/osint/model';
export * as share from './src/lib/gods-eye/share-link';
export * as kinds from './src/lib/workspace/kinds';
export * as units from './src/lib/decisions/units';
export * as reg from './src/lib/decisions/register';
export * as opsStore from './src/lib/ops/store.svelte';
export * as cityReg from './src/lib/gods-eye/entities/registry.svelte';
export { dossier } from './src/lib/gods-eye/entities/dossier.svelte';
export { liveWorld } from './src/lib/workspace/world.svelte';
export { operatorSession } from './src/lib/shell/session.svelte';
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
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'object-entry.ts' },
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

const NOW = Date.now();
const fx = objectFixtures(NOW);
const E = fx.expect;
const writes = [];
globalThis.fetch = async (url, init = {}) => {
	const method = (init.method ?? 'GET').toUpperCase();
	if (method !== 'GET') {
		writes.push(`${method} ${url}`);
		return new Response('{"detail":"refused"}', { status: 503 });
	}
	const a = fx.answer(String(url));
	return a
		? new Response(JSON.stringify(a.body), { status: a.status, headers: { 'content-type': 'application/json' } })
		: new Response('{"detail":"Not Found"}', { status: 404, headers: { 'content-type': 'application/json' } });
};

const M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
const { model, view, osint, share } = M;
const RAW_RE = /MH ?47 ?EM ?9001/i;

// ─── the pack ────────────────────────────────────────────────────────────────

{
	const en = Object.keys(M.packs.OBJ_PACKS.en);
	const same = (a, b) => a.length === b.length && a.every((k) => b.includes(k));
	ok('pack: EN / HI / MR carry the same keys, all obj_', same(en, Object.keys(M.hi)) && same(en, Object.keys(M.mr)) && en.every((k) => k.startsWith('obj_')), `${en.length} keys`);
	const files = [];
	const walk = (d) => {
		for (const f of readdirSync(d)) {
			const p = path.join(d, f);
			if (statSync(p).isDirectory()) walk(p);
			else if (/\.(svelte|ts)$/.test(f) && !/packs\.object/.test(f)) files.push(p);
		}
	};
	walk(OBJ);
	walk(path.join(DECK, 'src/routes/(v3)/o'));
	const used = new Set();
	for (const f of files) for (const m of readFileSync(f, 'utf8').matchAll(/['"`](obj_[a-z0-9_]+)['"`]/g)) used.add(m[1]);
	const dyn = ['obj_screen_osint_event', 'obj_screen_event', 'obj_screen_vehicle', 'obj_screen_place', 'obj_screen_convoy', 'obj_screen_junction', 'obj_screen_camera', 'obj_screen_dispatch', 'obj_screen_recommendation', 'obj_screen_sighting', 'obj_screen_other'];
	const missing = [...used, ...dyn, ...dyn.map((k) => k.replace('screen', 'sub'))].filter((k) => !en.includes(k));
	ok('pack: every obj_ key the object code uses exists', missing.length === 0, missing.join(', ') || `${used.size} used`);
	const text = (v) => (typeof v === 'function' ? v('‹x›', '‹y›') : v);
	const seps = Object.entries(M.packs.OBJ_PACKS.en).filter(([, v]) => (String(text(v)).match(/ · /g) ?? []).length > 1);
	ok('pack: at most one " · " per EN string', seps.length === 0, seps.map(([k]) => k).join(', '));
	const leak = Object.values(M.hi).map(text).some((s) => /[ঀ-৿]/.test(s)) || Object.values(M.mr).map(text).some((s) => /[ঀ-৿०-९]/.test(s));
	ok('pack: no Bengali script left in HI or MR, and MR keeps Latin digits (Marathi is Devanagari)', !leak);
	const untranslated = (pk) => en.filter((k) => k !== 'obj_ask_prompt' && String(text(M.packs.OBJ_PACKS.en[k])) === String(text(pk[k])) && /[a-z]{4}/.test(String(text(pk[k]))));
	ok('pack: HI and MR are translated', untranslated(M.hi).length === 0 && untranslated(M.mr).length === 0, [...untranslated(M.hi), ...untranslated(M.mr)].join(', '));
	const hexHit = files.filter((f) => /#[0-9a-fA-F]{3,8}\b/.test(readFileSync(f, 'utf8').replace(/\/\/.*$|\/\*[\s\S]*?\*\//gm, '').replace(/&#\d+;/g, '')));
	ok('no hex colour literal in the object code (tokens only)', hexHit.length === 0, hexHit.map((f) => path.basename(f)).join(', '));
	const anchors = files.filter((f) => /<a\b[^>]*href=\{[^}]*\.url\b/.test(readFileSync(f, 'utf8')));
	ok('no anchor binds a raw source url (only officialLink)', anchors.length === 0, anchors.map((f) => path.basename(f)).join(', '));
}

// ─── the route ───────────────────────────────────────────────────────────────

{
	const urns = Object.values(E.urns);
	ok('objectHref ↔ urnFromParam round-trips every fixture URN', urns.every((u) => model.urnFromParam(model.objectHref(u).slice(3)) === u), urns.length);
	const hostile = ['', 'not-a-urn', '../etc/passwd', 'javascript:alert(1)', 'osint_event:not-a-uuid', 'vehicle:MH47EM9001', `place:${'a'.repeat(300)}`, 'person:abc', '%E0%A4%A'];
	ok('a hostile parameter names nothing', hostile.every((h) => model.urnFromParam(h) === null), hostile.filter((h) => model.urnFromParam(h) !== null).join(' | '));
	ok('an encoded parameter decodes to its URN', model.urnFromParam('camera:EM%2DCAM%2D03') === 'camera:EM-CAM-03');
	ok('objectHref of a non-URN is null', model.objectHref('nope') === null && model.objectHref(null) === null);
}

// ─── tabs ────────────────────────────────────────────────────────────────────

{
	const c = { sources: 2, reads: 6, pursuit: true, timeline: 4, nearby: 3, record: 11 };
	const ids = (k, cc = c) => model.tabsFor(k, cc).map((x) => x.id).join(',');
	ok('tabs: a report has Sources', ids('osint_event') === 'overview,sources,timeline,nearby,record');
	ok('tabs: a vehicle has Reads and, with an open pursuit, Pursuit', ids('vehicle') === 'overview,reads,pursuit,timeline,nearby,record' && ids('vehicle', { ...c, pursuit: false }) === 'overview,reads,timeline,nearby,record');
	ok('tabs: a camera has the common four', ids('camera') === 'overview,timeline,nearby,record');
	ok('tabs: counts ride the pills', model.tabsFor('osint_event', c).find((x) => x.id === 'record').count === 11);
	const T = model.tabsFor('camera', c);
	ok('tablist keys: → ← wrap, Home, End', model.tabStep(T, 'record', 'ArrowRight') === 'overview' && model.tabStep(T, 'overview', 'ArrowLeft') === 'record' && model.tabStep(T, 'nearby', 'Home') === 'overview' && model.tabStep(T, 'overview', 'End') === 'record' && model.tabStep(T, 'overview', 'Enter') === null);
}

// ─── provenance ──────────────────────────────────────────────────────────────

{
	const p = (o) => model.provenanceOf({ kind: 'event', source: 'live', verification: null, test: false, ...o });
	ok('provenance: a live record carries none', p({}) === null);
	ok('provenance: emulated / simulated', p({ source: 'emulated' }) === 'EMULATED' && p({ source: 'simulated' }) === 'SIMULATED');
	ok('provenance: a test record says Test first (even emulated)', p({ source: 'emulated', test: true }) === 'TEST');
	ok('provenance: an OSINT report reads its verification', p({ kind: 'osint_event', source: 'osint', verification: 'NEWS-REPORTED' }) === 'NEWS-REPORTED' && p({ kind: 'osint_event', source: 'osint', verification: 'OFFICIAL-VERIFIED' }) === 'OFFICIAL-VERIFIED');
	ok('provenance: an OSINT row without (or with an unknown) label is Unverified, never more', p({ kind: 'osint_event', source: 'osint', verification: null }) === 'UNVERIFIED-OSINT' && p({ kind: 'osint_event', source: 'osint', verification: 'EMULATED' }) === 'UNVERIFIED-OSINT');
	ok('provenance: a gazetteer place carries none', p({ kind: 'place', source: 'osint' }) === null);
	const words = Object.values(model.PROVENANCE).map((s) => M.t('en', s.key));
	ok(
		'provenance: the labels say Emulated · Simulated · Test · Unverified · Unverified field report · Unverified camera reading · News-reported · Official · Confirmed',
		words.join('|') === 'Emulated|Simulated|Test|Unverified|Unverified field report|Unverified camera reading|News-reported|Official|Confirmed',
		words.join('|'),
	);
	// a board entry from a voice field report or a camera reading (lib/v3/field) is unverified until an officer confirms it
	const fm = (src) => p({ props: { metadata: { source: src } } });
	ok('provenance: a field / camera board entry is Unverified field report / Unverified camera reading; emulated and test still win', fm('field-voice') === 'UNVERIFIED-FIELD' && fm('camera-ai') === 'UNVERIFIED-CAMERA' && p({ source: 'emulated', props: { metadata: { source: 'field-voice' } } }) === 'EMULATED' && p({ kind: 'vehicle', props: { metadata: { source: 'field-voice' } } }) === null);
	ok('ladder: Unverified 0 · News-reported 1 · Official 2', model.ladderStep('UNVERIFIED-OSINT') === 0 && model.ladderStep('NEWS-REPORTED') === 1 && model.ladderStep('OFFICIAL-VERIFIED') === 2 && model.ladderStep(null) === 0);
}

// ─── OSINT rules ─────────────────────────────────────────────────────────────

{
	const snap = fx.answer('/api/v1/city/entities').body;
	const acc = snap.entities.find((e) => e.urn === E.urns.osint_event);
	const p = osint.readReport(acc.props);
	const rows = model.reportingSources(p);
	ok('context: the district warning is never a reporting source', rows.length === 2 && !rows.some((r) => r.publisher === 'sachet.ndma.gov.in'), rows.map((r) => r.publisher).join(', '));
	const tally = model.sourceTally(p);
	ok('context: never counted (2 publishers · 0 official · 1 context listed apart)', tally.publishers === 2 && tally.official === 0 && tally.context === 1, JSON.stringify(tally));
	const checks = Object.fromEntries(model.credibilityChecks(p, p.toponym).map((c) => [c.id, c.ok]));
	ok('context: an official-tier context member does not make "official" true', checks.official === false && checks.publishers === true && checks.place === true, JSON.stringify(checks));
	ok('a news source never gets a link (even with a leaked https url)', rows.every((r) => model.officialLink(r) === null));
	const w = snap.entities.find((e) => e.urn === E.urns.official);
	const pw = osint.readReport(w.props);
	const links = model.reportingSources(pw).map((r) => [r.publisher, model.officialLink(r)]);
	ok('official tier + https → the one link; official + http → none; aggregator on .gov.in → none', JSON.stringify(links) === JSON.stringify([['sachet.ndma.gov.in', 'https://sachet.ndma.gov.in/cap/alert/1'], ['mausam.imd.gov.in', null], ['wb.gov.in', null]]), JSON.stringify(links));
	ok('officialLink refuses http:, javascript:, data:, a malformed url and a non-official row', [
		{ official: true, url: 'http://mausam.imd.gov.in/nowcast' },
		{ official: true, url: 'javascript:alert(1)' },
		{ official: true, url: 'data:text/html,x' },
		{ official: true, url: 'https//broken' },
		{ official: false, url: 'https://sachet.ndma.gov.in/x' },
	].every((r) => model.officialLink(r) === null));
	const gov = { ...p, verification: 'NEWS-REPORTED', sources: [{ signalId: 's', publisher: 'wb.gov.in', tier: 'aggregator', title: null, fetchMode: null, url: 'https://wb.gov.in/x', linkNote: null }], provenance: { ...p.provenance, contextPublishers: [] } };
	ok('officialness rides the tier, never the domain', model.credibilityChecks(gov, 'x').find((c) => c.id === 'official').ok === false && model.sourceTally(gov).official === 0);
	ok('ring radius widens as the geocoder is less sure; district level is widest', model.ringRadiusM(0.9, false) < model.ringRadiusM(0.6, false) && model.ringRadiusM(0.6, false) < model.ringRadiusM(0.3, false) && model.ringRadiusM(0.3, false) < model.ringRadiusM(0.9, true));
	const tiles = model.effectTiles({ secondOrder: [...p.secondOrder, { kind: 'dispatch', urn: p.secondOrder[1].urn, segmentId: null, note: 'Second note' }] }, () => 'L');
	ok('effects: one tile per affected record, its notes joined', tiles.length === 2 && tiles[1].notes.length === 2 && tiles[1].glyph === 'ambulance' && tiles[0].glyph === 'convoy', JSON.stringify(tiles.map((x) => [x.glyph, x.notes.length])));
	ok('status: new / promoted / corroborates in words', model.reportStatusKey({ novel: true }) === 'obj_status_new' && model.reportStatusKey({ promotedEventId: 'x' }) === 'obj_status_promoted' && model.reportStatusKey({ corroboratesLiveUrn: 'e' }) === 'obj_status_corroborates');
}

// ─── art, links out ──────────────────────────────────────────────────────────

{
	const reqs = [
		model.vehicleArt('car'), model.vehicleArt('motorcycle'), model.vehicleArt('unknown'), model.vehicleArt(null),
		model.agencyArt('ambulance'), model.agencyArt('police'), model.agencyArt('jan_rakshak'), model.agencyArt('anything'),
		...['event', 'osint_event', 'vehicle', 'convoy', 'dispatch', 'sighting'].map((k) => model.artOf({ kind: k, props: { event_kind: 'work_zone', sajag_event_kind: 'road_accident', vehicle_class: 'suv', agency: 'fire' } }).src),
	];
	const missing = reqs.filter((r) => !existsSync(path.join(DECK, 'static', r)) || !r.endsWith('.svg'));
	ok('art: every illustration the page asks for exists (SVG, never a photo)', missing.length === 0, missing.join(', '));
	ok('art: a kind without an illustration gets a glyph tile', model.artOf({ kind: 'junction', props: {} }).src === null && model.artOf({ kind: 'junction', props: {} }).glyph === 'signal');
	const href = model.mapHref(E.urns.vehicle, [88.3499, 22.5582], 'vehicle');
	const parsed = share.parseShareHash(href.slice(href.indexOf('#')), [...model.MAP_LAYERS]);
	ok('Map link: share-link grammar, City map style (never thermal), clean layers, sel = the URN', href.startsWith('/gods-eye#') && parsed?.style === 'raw' && parsed.selected === E.urns.vehicle && parsed.layers.includes('osint') && !parsed.layers.includes('flow') && !RAW_RE.test(href), href);
	ok('Map link: no position → the Map as it is', model.mapHref('camera:X', null, 'camera') === '/gods-eye');
	ok('Analyst link carries the URN only', model.analystHref(E.urns.vehicle) === `/analyst#items=${encodeURIComponent(E.urns.vehicle)}`);
	ok('retention days left (rounded up; past → 0; no date → null)', model.retentionDaysLeft(new Date(NOW + 11.2 * 86400000).toISOString(), NOW) === 12 && model.retentionDaysLeft(new Date(NOW - 1000).toISOString(), NOW) === 0 && model.retentionDaysLeft(null, NOW) === null);
}

// ─── the fixture world through the real stores ──────────────────────────────

await M.operatorSession.refresh();
const { ops } = M.opsStore;
ops.applySession(M.operatorSession.gate, M.operatorSession.officer);
await ops.loadGeometry(true);
await M.cityReg.cityRegistry.refresh();
for (const n of ['pollBoard', 'pollRecommendations', 'pollApproved', 'pollEscorts', 'pollDispatches', 'pollWatchlist', 'pollTrafficFeed']) {
	try {
		await (n === 'pollBoard' ? ops.pollBoard(true) : ops[n]());
	} catch (e) {
		console.log(`note ${n}: ${e.message}`);
	}
}
M.reg.register();
const units = M.units.decisionUnits(ops);

{
	const acc = view.decisionsFor(E.urns.osint_event, 'en', Date.now(), units);
	ok('report: its decision card is the DSS unit, opening its one home', acc.length >= 1 && acc[0].kind === 'dss' && !acc[0].touches && [`/ops#unit=${encodeURIComponent(`dss:${E.ids.dss}`)}`, `/decide/${encodeURIComponent(`dss:${E.ids.dss}`)}`].includes(acc[0].href) && acc[0].recommended === 'Standard response', JSON.stringify(acc.map((c) => [c.kind, c.href])));
	const veh = view.decisionsFor(E.urns.vehicle, 'en', Date.now(), units);
	ok('vehicle: its decision card is the stolen-sighting unit', veh.some((c) => c.kind === 'stolen-sighting' && !c.touches), veh.map((c) => c.kind).join(', '));
	ok('a camera has no decision of its own', view.decisionsFor('camera:EM-BR-HOWRAH-E', 'en', Date.now(), units).filter((c) => !c.touches).length === 0);
}

async function vmsFor(urn) {
	const d = await M.dossier.peek(urn);
	const graph = M.liveWorld.graph();
	const row = graph.get(urn) ?? (d ? M.kinds.rowOf(d.entity) : null);
	const links = graph.links(urn);
	const now = Date.now();
	const v = M.kinds.adapterFor(row.kind).view(row, { lang: 'en', now, officer: ops.officerOn, plate: (r) => ops.plate(r), graph, links, dossier: d, publicKind: () => true });
	const report = row.kind === 'osint_event' ? osint.readReport(row.props) : null;
	return {
		row,
		v,
		title: view.titleText(row, v, now),
		kindLine: view.kindLine(row, v, report, 'en', now),
		ctas: view.decisionsFor(urn, 'en', now, units),
		activity: view.activityOf(d, 'en', now),
		hero: view.heroVM(row, links, report, true, 'x', 'en'),
		facts: report ? view.osintFacts(row, report, d, 'en', now) : [],
		reads: row.kind === 'vehicle' ? view.readsOf(urn, links) : [],
	};
}

{
	const masked = [];
	for (const k of ['vehicle', 'sighting', 'recommendation', 'event', 'osint_event']) {
		const vm = await vmsFor(E.urns[k]);
		// what the page renders (a linked row's raw `props` ride along as data and are never printed: ObjectTag shows the label)
		const blob = JSON.stringify({ title: vm.title, kindLine: vm.kindLine, ctas: vm.ctas, activity: vm.activity, hero: vm.hero, facts: vm.facts, v: vm.v, reads: vm.reads.map((r) => r.label) }, (k, val) => (k === 'props' ? undefined : val));
		if (RAW_RE.test(blob)) masked.push(k);
	}
	ok('no raw mark in any view model without an officer (title, cards, timeline, hero, facts, adapter view)', masked.length === 0, masked.join(', ') || 'clean');
	const vm = await vmsFor(E.urns.vehicle);
	ok('vehicle: the timeline masks a raw mark in the audit text', vm.activity.length === 2 && vm.activity.every((a) => !RAW_RE.test(`${a.text} ${a.full}`) && /MH47EM•••1/.test(a.full)), vm.activity.map((a) => a.full).join(' | '));
	ok('vehicle: the hero draws its lawful reads as a trail, newest ringed', vm.hero.overlay?.lines?.[0]?.style === 'trail' && vm.hero.overlay.points.at(-1).tone === 'alert', `${vm.reads.length} reads`);
	ops.setDutyOfficer('Sandbox Officer');
	const named = await vmsFor(E.urns.vehicle);
	ok('a named officer sees the full mark (view and timeline)', RAW_RE.test(JSON.stringify(named.v.plate)) && named.activity.some((a) => RAW_RE.test(a.full)), `${JSON.stringify(named.v.plate)} · officerOn ${ops.officerOn}`);
	ops.setDutyOfficer('');
	const again = await vmsFor(E.urns.vehicle);
	ok('clearing the officer masks it again', !RAW_RE.test(JSON.stringify({ v: again.v, a: again.activity }, (k, val) => (k === 'props' ? undefined : val))));
	const acc = await vmsFor(E.urns.osint_event);
	ok('report: title without the kind prefix; kind line names the kind and the window', acc.title === 'Sector V, Salt Lake' && /^Road accident · reported /.test(acc.kindLine), `${acc.title} | ${acc.kindLine}`);
	ok('report: the hero has the dashed ring and the road it sits on', acc.hero.overlay?.rings?.length === 1 && acc.hero.overlay.lines?.[0]?.style === 'road' && /72 %/.test(acc.hero.overlay.points[0].sub ?? ''));
	const srcFact = acc.facts.find((f) => f.key === 'Sources')?.value;
	ok('report: the Sources fact counts reporting publishers only', srcFact === '2 publishers · 0 official', srcFact);
}

ok('nothing was written (no non-GET from any model)', writes.length === 0, writes.join(' | '));
console.log(failures ? `\n${failures} FAILED` : '\nobject-page.unit: ALL OK');
process.exit(failures ? 1 : 0);
