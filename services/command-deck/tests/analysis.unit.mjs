/**
 * Analysis unit test (UI-S4; SPEC §5.3 Timeline / AuditTable / LinkGraph,
 * §7.1, §7.4, §8.3–8.4, §13.6, §13.9; plan X8).
 *
 *   node tests/analysis.unit.mjs
 *
 * esbuild bundles the REAL modules — src/lib/analysis/{graph/graph, graph/
 * layout, graph/force, graph/worker, timeline/bins, timeline/brush,
 * timeline/lanes, audit/rows, history-api}, the workspace's object model and
 * store, and the analysis pack — with `$lib` aliased to src/lib; `$state` is
 * an identity stub so the rune classes run as plain classes.
 *
 * Fixtures: the vehicle fixture tests/fixtures/workspace/captured.json (the
 * prototype's emulated, masked capture: MH47EM•••1, 51 linked objects, 189
 * feed rows) and UI-S7A's contract fixture tests/contract/fixtures/
 * events_history.sandbox.json (GET /events?limit=200).
 *
 * Asserts:
 *   graph     built from the fixture's objects: 51 linked; > 8 rejected
 *             recommendations merge into ONE node "14 rejected" (pending
 *             ones never merge); Expand merged reverses it; roles by link
 *             type (6 cameras on the ring, reads on arcs outside their
 *             camera, recommendations outside their evidence, pursuits on
 *             the inner ring); Find paths over two selected objects
 *   layout    radial, deterministic, no overlapping labels and no label over
 *             a disc at 500 × 600 and wider (and in the hierarchical and
 *             force layouts); events labelled before cameras (both pursuits
 *             at 500 × 600, a shorter form when the full one does not fit); a
 *             label set apart from its disc sits nearer it than any other;
 *             R = min(W, 1.1 H)/2 − 36; ≤ 80 nodes laid out
 *             synchronously in < 30 ms; ≤ 60 nodes end to end in < 300 ms;
 *             the blob-worker source is self-contained; a large force layout
 *             runs its ticks in slices with the same result as one run
 *   timeline  binning (counts, the last bin holds `end`, linked overlay);
 *             the brush maths (a click is not a window, sorted and clamped);
 *             a window turns Live off and returnToLive clears it on the real
 *             workspace store; the seven lanes with osint → Events (X8) while
 *             the rail's kind counts keep osint apart; an osint row's tooltip
 *             ends in its X2 verification label ("News-reported", "Open-source"
 *             without a state); tick colours; "older rows not loaded"; IST axis
 *             ticks and the tape axis
 *   feed      the city-feed poll never repeats a row id, also when its rows
 *             were seeded from outside (a /design harness) before the poll
 *   audit     rows from the feed and from the ops ledger: actor kinds kept,
 *             humanised text with the officer's words verbatim in the
 *             tooltip, provenance only on non-live rows (osint with its
 *             label), one item per id, the uniform-list provenance (SPEC §9.2),
 *             filters, the AI trace without officer rows, the CSV masked
 *   masking   no row text, tooltip, CSV or history string carries a raw mark
 *             in any case or spelling (mh47em9001, MH.01.XX.0007,
 *             MH_47_EM_9001 …) without a named officer (FIX-B-DECK, §9.3)
 *   history   the contract fixture parses (18 events, newest first, closed
 *             spans), junk is dropped, marks are masked at any depth
 *   vendor    each vendored folder holds its LICENSE, VENDORED.md and src
 *   packs     EN, HI and MR carry the same keys
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const OUT = path.join(HERE, 'artifacts', 'analysis-bundle.mjs');
const FIXTURE = path.join(HERE, 'fixtures', 'workspace', 'captured.json');
const HISTORY = path.join(HERE, 'contract', 'fixtures', 'events_history.sandbox.json');

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
export * as cityApi from './src/lib/gods-eye/city-api';
export * as objects from './src/lib/workspace/objects';
export * as ws from './src/lib/workspace/workspace.svelte';
export * as graph from './src/lib/analysis/graph/graph';
export * as force from './src/lib/analysis/graph/force';
export * as feedStore from './src/lib/gods-eye/hud/feed.svelte';
export * as layout from './src/lib/analysis/graph/layout';
export * as worker from './src/lib/analysis/graph/worker';
export * as bins from './src/lib/analysis/timeline/bins';
export * as brush from './src/lib/analysis/timeline/brush';
export * as lanes from './src/lib/analysis/timeline/lanes';
export * as tip from './src/lib/analysis/timeline/tip';
export * as audit from './src/lib/analysis/audit/rows';
export * as history from './src/lib/analysis/history-api';
export * as packs from './src/lib/i18n/packs.analysis';
export { t } from './src/lib/i18n/strings';
`;
const built = await esbuild.build({
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'analysis-entry.ts' },
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	outfile: OUT,
	logLevel: 'silent',
});
ok('bundle builds (esbuild, $lib aliased)', built.errors.length === 0, `${built.errors.length} errors`);

globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });

const M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
const { cityApi, objects, ws, graph: G, force: FO, feedStore: FS, layout: L, worker: WK, bins: B, brush: BR, lanes: LN, tip: TIP, audit: AU, history: HI, packs, t: tr } = M;

// ─── the vehicle fixture as the object model ───────────────────────────────

const FX = JSON.parse(readFileSync(FIXTURE, 'utf8'));
const AS_OF = Date.parse(FX.as_of);
const VEHICLE = FX.vehicle;
const FEED = cityApi.parseFeedRows({ items: FX.feed.items });
const feedById = new Map(FX.feed.items.map((i) => [i.id, i]));
const snap = cityApi.parseCitySnapshot(FX.snapshot);
const dossiers = FX.dossiers
	.map((d) => cityApi.parseDossier({ ...d, audit: d.audit.map((a) => (typeof a === 'string' ? feedById.get(a) : a)).filter(Boolean) }, AS_OF))
	.filter(Boolean);
const OG = objects.buildObjectGraph({ entities: snap.entities, dossiers });

// ─── graph ──────────────────────────────────────────────────────────────────

const g = G.buildGraph(OG, VEHICLE, { lang: 'en', anchor: AS_OF });
ok('graph: built around the vehicle', !!g && g.focus === VEHICLE);
ok('graph: 51 linked (the selectors’ count)', g.stats.linked === 51, `${g.stats.linked}`);
const agg = g.nodes.filter((n) => n.role === 'merged');
ok('graph: the 14 rejected recommendations merge into ONE node', agg.length === 1 && agg[0].agg.count === 14 && agg[0].agg.state === 'rejected', agg.map((a) => `${a.id}=${a.agg.count}`).join(','));
ok('graph: the merged node reads "14 rejected"', agg[0]?.labelText === '14 rejected', agg[0]?.labelText);
ok('graph: stats "51 linked · 14 merged"', g.stats.merged === 14, JSON.stringify(g.stats));
const recs = g.nodes.filter((n) => n.kind === 'recommendation' && n.role !== 'merged');
ok('graph: pending and approved recommendations are never merged', recs.filter((n) => n.row.state === 'pending').length === 6 && recs.filter((n) => n.row.state === 'approved').length === 2, recs.map((n) => n.row.state).join(','));
ok('graph: a pending recommendation carries the orange dot, an approved one the green', recs.every((n) => n.dot === (n.row.state === 'pending' ? 'pending' : n.row.state === 'approved' ? 'approved' : null)));
const hubs = g.nodes.filter((n) => n.role === 'hub');
ok('graph: 6 cameras on the ring', hubs.length === 6 && hubs.every((n) => n.kind === 'camera'), hubs.map((n) => n.row.id).join(','));
const sats = g.nodes.filter((n) => n.role === 'satellite');
ok('graph: the 21 reads sit on arcs outside their camera', sats.filter((n) => n.kind === 'sighting').length === 21 && sats.every((n) => n.parent && n.parent.startsWith('camera:') && (n.kind !== 'sighting' || n.parent === `camera:${n.row.props.camera_id}`)), `${sats.length} satellites`);
const tert = g.nodes.filter((n) => n.role === 'tertiary');
ok('graph: recommendations sit outside their evidence read', tert.length > 0 && tert.every((n) => n.kind === 'recommendation' && n.parent === `sighting:${n.row.props.sighting_id}`), `${tert.length} tertiary`);
const inner = g.nodes.filter((n) => n.role === 'inner');
ok('graph: the pursuits are on the inner ring', inner.filter((n) => n.kind === 'event').length === 2, inner.map((n) => n.kind).join(','));
ok('graph: the vehicle is ringed red (watchlist)', g.nodes[0].alert === true && g.nodes[0].role === 'focus');
ok('graph: edges name their link type', g.edges.length >= g.nodes.length - 1 && g.edges.every((e) => typeof e.label === 'string' && e.label.length > 0), `${g.edges.length} edges · e.g. ${g.edges.slice(0, 3).map((e) => e.label).join(' / ')}`);
ok('graph: the pursuit links the recommendation that authorised it', g.edges.some((e) => e.a.startsWith('event:') && e.b.startsWith('recommendation:')));
const gx = G.buildGraph(OG, VEHICLE, { lang: 'en', anchor: AS_OF, expandMerged: true });
ok('graph: Expand merged shows every link (no merged node, 22 recommendations)', !gx.nodes.some((n) => n.role === 'merged') && gx.nodes.filter((n) => n.kind === 'recommendation').length === 22 && gx.stats.merged === 0 && gx.stats.mergeable === 14);
const keepRejected = g.nodes.length ? [...OG.links(VEHICLE)].find((l) => l.row.kind === 'recommendation' && l.row.state === 'rejected')?.row.urn : null;
const gk = G.buildGraph(OG, VEHICLE, { lang: 'en', anchor: AS_OF, keep: [keepRejected] });
ok('graph: a selected object is never swallowed by a merge', gk.nodes.some((n) => n.id === keepRejected) && gk.nodes.find((n) => n.role === 'merged')?.agg.count === 13);

// Find paths over two selected objects
const camera = hubs[0].id;
const pending = recs.find((n) => n.row.state === 'pending').id;
const p1 = G.findPath(OG, camera, pending);
ok('find paths: a chain joins a camera and a pending recommendation', Array.isArray(p1) && p1[0] === camera && p1[p1.length - 1] === pending && p1.length >= 2 && p1.length <= 7, p1?.join(' → '));
let chainOk = !!p1;
for (let i = 1; p1 && i < p1.length; i++) if (!OG.links(p1[i - 1]).some((l) => l.row.urn === p1[i])) chainOk = false;
ok('find paths: every step of the chain is a real link', chainOk);
const pursuit = inner.find((n) => n.kind === 'event').id;
const read = sats.find((n) => n.kind === 'sighting').id;
const p2 = G.findPath(OG, pursuit, read);
ok('find paths: the shortest chain (pursuit → vehicle → read)', p2?.length === 3 && p2[1] === VEHICLE, p2?.join(' → '));
ok('find paths: none for the same object, none past the hop limit', G.findPath(OG, read, read) === null && G.findPath(OG, pursuit, read, 1) === null);
const gp = G.buildGraph(OG, camera, { lang: 'en', anchor: AS_OF, paths: [p1] });
ok('find paths: the chain is added to the graph and its edges marked', gp.edges.filter((e) => e.path).length === p1.length - 1 && p1.every((u) => gp.nodes.some((n) => n.id === u)), `${gp.edges.filter((e) => e.path).length} path edges`);
const types = G.linkTypes(OG, camera, new Set(gp.nodes.map((n) => n.id)), 'en');
ok('search around: a camera lists its link types with counts', types.length > 0 && types.every((x) => x.count > 0 && x.label), types.map((x) => `${x.label} ${x.count}`).join(', '));
const gc = G.buildGraph(OG, camera, { lang: 'en', anchor: AS_OF });
const sa = G.buildGraph(OG, camera, { lang: 'en', anchor: AS_OF, expansions: new Map([[VEHICLE, new Set(['seen_by_camera'])]]) });
const addedCams = sa.nodes.filter((n) => n.role === 'extra' && n.kind === 'camera');
ok(
	'search around: adds one link type from one object (the vehicle’s other cameras), nothing else',
	addedCams.length === 5 && sa.nodes.filter((n) => n.role === 'extra').length === 5 && addedCams.every((n) => n.parent === VEHICLE) && sa.edges.filter((e) => e.a === VEHICLE && e.b.startsWith('camera:')).length >= 5,
	`${gc.nodes.length} → ${sa.nodes.length} nodes`,
);

// ─── layout ─────────────────────────────────────────────────────────────────

const toInput = (model, W, H, mode = 'radial') => ({
	mode,
	W,
	H,
	focus: model.focus,
	nodes: model.nodes.map((n) => ({ id: n.id, role: n.role, parent: n.parent, r: n.r, order: n.order, labelW: n.labelW, shortW: n.shortW, wantLabel: n.wantLabel, priority: n.priority })),
});
function labelCheck(model, out, W, H) {
	const ids = Object.keys(out.labels);
	const boxes = ids.map((id) => out.labels[id]);
	let overlap = 0;
	let overDisc = 0;
	let outside = 0;
	for (let i = 0; i < boxes.length; i++) {
		const a = boxes[i];
		if (a.x < 0 || a.y < 0 || a.x + a.w > W || a.y + a.h > H) outside++;
		for (let j = i + 1; j < boxes.length; j++) if (L.boxesOverlap(a, boxes[j])) overlap++;
		for (const n of model.nodes) {
			const p = out.pos[n.id];
			const disc = { x: p.x - n.r, y: p.y - n.r, w: 2 * n.r, h: 2 * n.r };
			if (L.boxesOverlap(a, disc)) overDisc++;
		}
	}
	return { placed: ids.length, overlap, overDisc, outside, focus: !!out.labels[model.focus] };
}
for (const [W, H] of [
	[500, 600],
	[640, 600],
	[900, 700],
	[1280, 760],
	[1920, 900],
]) {
	const out = L.computeLayout(toInput(g, W, H));
	const c = labelCheck(g, out, W, H);
	ok(`layout ${W}×${H}: no overlapping labels, none over a disc, none outside`, c.overlap === 0 && c.overDisc === 0 && c.outside === 0 && c.focus && c.placed >= 8, `${c.placed} labels · overlaps ${c.overlap} · over discs ${c.overDisc} · outside ${c.outside} · discs overlapping ${out.overlaps}`);
	ok(`layout ${W}×${H}: R = min(W, 1.1 H)/2 − 36`, Math.abs(out.R - Math.max(80, Math.min(W, 1.1 * H) / 2 - 36)) < 1e-9, `R=${out.R.toFixed(1)}`);
}
{
	// SPEC §5.3 priority order (focus, selection, merged, events, cameras): an event wins a label over a camera
	const pursuits = g.nodes.filter((n) => n.kind === 'event' && n.wantLabel);
	const gapTo = (b, q, r) => Math.max(0, Math.hypot(Math.max(b.x - q.x, 0, q.x - (b.x + b.w)), Math.max(b.y - q.y, 0, q.y - (b.y + b.h))) - r);
	for (const [W, H] of [[500, 600], [498, 558], [640, 600], [900, 700], [1920, 900]]) {
		const out = L.computeLayout(toInput(g, W, H));
		const evLabelled = pursuits.filter((n) => out.labels[n.id]).length;
		const camsLabelled = hubs.filter((h) => out.labels[h.id]).length;
		ok(`layout ${W}×${H}: every event is labelled before any camera is`, evLabelled === pursuits.length || camsLabelled === 0, `${evLabelled}/${pursuits.length} events · ${camsLabelled}/${hubs.length} cameras`);
		// a label set apart from its disc (more than the 4 px beside it) must sit nearer its own disc than any other
		const strays = [];
		for (const n of g.nodes) {
			const b = out.labels[n.id];
			if (!b) continue;
			const own = gapTo(b, out.pos[n.id], n.r);
			if (own <= 5) continue;
			for (const m of g.nodes) if (m.id !== n.id && gapTo(b, out.pos[m.id], m.r) < own - 0.5) strays.push(`${n.labelText} (${own.toFixed(0)} px) nearer ${m.labelText}`);
		}
		ok(`layout ${W}×${H}: a label set apart from its node sits nearer it than any other node`, strays.length === 0, strays.slice(0, 2).join(' · ') || 'none');
	}
	ok('graph: an event has a shorter label form (no day), a camera none', pursuits.every((n) => n.shortLabel && n.shortW < n.labelW && !/\d{1,2} [A-Z][a-z]{2}$/.test(n.shortLabel[0].text)) && hubs.every((h) => h.shortLabel === null), pursuits.map((n) => n.shortLabel?.[0]?.text).join(' | '));
	// crowded events: three on the inner ring of a small pane — each keeps a label in its shorter form rather than lose one
	const crowd = (shortW) => ({ mode: 'radial', W: 300, H: 300, focus: 'f', nodes: [{ id: 'f', role: 'focus', parent: null, r: 20, order: 0, labelW: 70, wantLabel: true, priority: 9 }, ...[0, 1, 2].map((i) => ({ id: `e${i}`, role: 'inner', parent: null, r: 11, order: i, labelW: 240, shortW, wantLabel: true, priority: 5 }))] });
	const withShort = L.computeLayout(crowd(60));
	const without = L.computeLayout(crowd(null));
	const shorts = Object.values(withShort.labels).filter((b) => b.short).length;
	ok('layout: crowded events take their shorter form rather than lose a label', Object.keys(withShort.labels).length === 4 && shorts >= 1 && Object.keys(without.labels).length < 4, `${Object.keys(withShort.labels).length} labels (${shorts} short) · ${Object.keys(without.labels).length} without a short form`);
}
const o1 = L.computeLayout(toInput(g, 500, 600));
const o2 = L.computeLayout(toInput(g, 500, 600));
ok('layout: deterministic (same input → same positions)', JSON.stringify(o1.pos) === JSON.stringify(o2.pos) && JSON.stringify(o1.labels) === JSON.stringify(o2.labels));
ok('layout: discs do not overlap after relaxation', o1.overlaps === 0, `${o1.overlaps}`);
const fpos = o1.pos[VEHICLE];
const camD = hubs.map((h) => Math.hypot(o1.pos[h.id].x - fpos.x, o1.pos[h.id].y - fpos.y));
const satD = sats.filter((s) => s.kind === 'sighting').map((s) => Math.hypot(o1.pos[s.id].x - o1.pos[s.parent].x, o1.pos[s.id].y - o1.pos[s.parent].y));
const innD = inner.map((n) => Math.hypot(o1.pos[n.id].x - fpos.x, o1.pos[n.id].y - fpos.y));
ok('layout: radial by link type (inner ring nearer than the camera ring; reads beside their camera)', Math.max(...innD) < Math.min(...camD) && Math.max(...satD) < Math.min(...camD), `inner ≤ ${Math.max(...innD).toFixed(0)} · cameras ≥ ${Math.min(...camD).toFixed(0)} · reads ≤ ${Math.max(...satD).toFixed(0)} from their camera`);
for (const mode of ['hierarchical']) {
	const out = L.computeLayout(toInput(g, 900, 700, mode));
	const c = labelCheck(g, out, 900, 700);
	ok(`layout ${mode}: no overlapping labels`, c.overlap === 0 && c.overDisc === 0 && c.placed >= 6, `${c.placed} labels`);
}
const fo = WK.layoutSync({ key: 'f', mode: 'force', W: 900, H: 700, focus: g.focus, nodes: toInput(g, 900, 700).nodes, edges: g.edges.map((e) => ({ a: e.a, b: e.b })) });
const fc = labelCheck(g, fo, 900, 700);
ok('layout force (vendored d3-force): no overlapping labels, deterministic', fc.overlap === 0 && fc.overDisc === 0 && fc.placed >= 6 && JSON.stringify(WK.layoutSync({ key: 'f2', mode: 'force', W: 900, H: 700, focus: g.focus, nodes: toInput(g, 900, 700).nodes, edges: g.edges.map((e) => ({ a: e.a, b: e.b })) }).pos) === JSON.stringify(fo.pos), `${fc.placed} labels · ${fo.ms.toFixed(1)} ms`);

// performance: ≤ 60 nodes end to end < 300 ms; ≤ 80 nodes synchronous < 30 ms
{
	const t0 = performance.now();
	const model = G.buildGraph(OG, VEHICLE, { lang: 'en', anchor: AS_OF });
	const out = L.computeLayout(toInput(model, 900, 700));
	const total = performance.now() - t0;
	ok(`perf: ${model.nodes.length} nodes (≤ 60) build + layout end to end < 300 ms`, model.nodes.length <= 60 && total < 300, `${total.toFixed(1)} ms (layout ${out.ms.toFixed(1)} ms)`);
	const big = G.buildGraph(OG, VEHICLE, { lang: 'en', anchor: AS_OF, expandMerged: true });
	// 80 nodes: the expanded vehicle graph plus fictional satellites of its cameras
	const nodes80 = toInput(big, 900, 700).nodes;
	let k = 0;
	while (nodes80.length < 80) nodes80.push({ id: `x:${k}`, role: 'satellite', parent: hubs[k % hubs.length].id, r: 8, order: 100 + k++, labelW: 60, wantLabel: false, priority: 1 });
	const runs = [];
	for (let i = 0; i < 5; i++) runs.push(L.computeLayout({ mode: 'radial', W: 900, H: 700, focus: VEHICLE, nodes: nodes80 }).ms);
	runs.sort((a, b) => a - b);
	ok(`perf: 80 nodes laid out synchronously < 30 ms (median of 5)`, runs[2] < 30, runs.map((x) => x.toFixed(1)).join(' / ') + ' ms');
	console.log(`perf-log graph nodes=${model.nodes.length} end_to_end_ms=${total.toFixed(2)} layout_ms=${out.ms.toFixed(2)} sync80_median_ms=${runs[2].toFixed(2)} force_ms=${fo.ms.toFixed(2)}`);
}
{
	// the worker body is computeLayout's own source: it must reference nothing outside itself
	const src = L.computeLayout.toString();
	const body = new Function(`return (${src})`)();
	const out = body(toInput(g, 500, 600));
	ok('worker: computeLayout runs from its own source text (blob: worker body)', Object.keys(out.pos).length === g.nodes.length && JSON.stringify(out.labels) === JSON.stringify(o1.labels));
	ok('worker: SYNC_MAX_NODES is 80', L.SYNC_MAX_NODES === 80);
}
{
	// SPEC §13.6: a large force layout never holds the main thread for the whole run — the same ticks, in slices
	const nodesF = toInput(g, 900, 700).nodes;
	const edgesF = g.edges.map((e) => ({ a: e.a, b: e.b }));
	const seed = L.computeLayout({ mode: 'radial', W: 900, H: 700, focus: g.focus, nodes: nodesF }).pos;
	const one = FO.forcePositions(nodesF, edgesF, g.focus, seed);
	let yields = 0;
	const ticker = setInterval(() => yields++, 0);
	const sliced = await FO.forcePositionsSliced(nodesF, edgesF, g.focus, seed);
	clearInterval(ticker);
	ok('force: the sliced run gives the same positions as one run, and yields between slices', JSON.stringify(sliced) === JSON.stringify(one) && yields > 0, `${FO.FORCE_TICKS} ticks in slices of ${FO.FORCE_SLICE_TICKS} · the event loop ran ${yields}×`);
	// above 80 nodes the force request goes the sliced way (no Worker in node: the off-thread passes fall back in place)
	const bigN = nodesF.slice();
	let q = 0;
	while (bigN.length < 90) bigN.push({ id: `y:${q}`, role: 'satellite', parent: hubs[q % hubs.length].id, r: 8, order: 200 + q++, labelW: 60, wantLabel: false, priority: 1 });
	const req = { key: 'force-90', mode: 'force', W: 900, H: 700, focus: g.focus, nodes: bigN, edges: edgesF };
	const ans = await WK.layoutGraph(req);
	WK.clearLayoutCache();
	const ref = WK.layoutSync({ ...req, key: 'force-90-ref' });
	ok('force: above 80 nodes the layout is the same as the in-place one', ans.via === 'fallback' && JSON.stringify(ans.out.pos) === JSON.stringify(ref.pos) && JSON.stringify(ans.out.labels) === JSON.stringify(ref.labels), `via ${ans.via}`);
}

// ─── the city-feed poll: never a repeated row id ───────────────────────────
{
	// /design/workspace seeds fusionFeed.rows with fixture rows, then a registered analysis tab starts the
	// real poll: the poll must not merge a second copy of a row already held (keyed views crash on it)
	const feed = FS.fusionFeed;
	const seeded = FEED.slice(0, 40);
	const wire = [...FX.feed.items.slice(20, 60), ...FX.feed.items.slice(30, 35), { ...FX.feed.items[0], id: 'event_status_log:new-1', t: new Date(AS_OF + 1000).toISOString() }];
	const realFetch = globalThis.fetch;
	let calls = 0;
	globalThis.fetch = async () => {
		calls++;
		return new Response(JSON.stringify({ items: wire }), { status: 200, headers: { 'content-type': 'application/json' } });
	};
	try {
		feed.rows = seeded;
		feed.start();
		for (let i = 0; i < 50 && feed.updatedAt === 0; i++) await new Promise((r) => setTimeout(r, 10));
		feed.stop();
	} finally {
		globalThis.fetch = realFetch;
	}
	const ids = feed.rows.map((r) => r.id);
	const want = new Set([...seeded.map((r) => r.id), ...wire.map((r) => r.id)]);
	ok('feed: a poll over rows seeded from outside never repeats a row id', calls >= 1 && feed.status === 'ok' && new Set(ids).size === ids.length && ids.length === want.size, `${ids.length} rows, ${new Set(ids).size} distinct, ${want.size} expected (${calls} read)`);
	ok('feed: the new row from the wire joins, the seeded ones stay', ids.includes('event_status_log:new-1') && seeded.every((r) => ids.includes(r.id)));
}

// ─── timeline: bins, brush, lanes ───────────────────────────────────────────

const START = AS_OF - 6 * B.HOUR;
const related = new Set([VEHICLE, ...OG.links(VEHICLE).map((l) => l.row.urn)]);
const h = B.binRows(FEED, START, AS_OF, related);
ok('bins: 96 bins over 6 h; every row of the fixture counted once', h.bins === 96 && h.all.reduce((s, x) => s + x, 0) === h.total && h.total === FEED.filter((f) => f.t >= START && f.t <= AS_OF).length, `${h.total} rows in view`);
ok('bins: the linked overlay is a subset ("Linked 54")', h.linked.every((x, i) => x <= h.all[i]) && h.linkedTotal === 54, `linked ${h.linkedTotal}`);
ok('bins: a row on the end falls in the last bin; outside is -1', B.binIndex(AS_OF, START, AS_OF) === 95 && B.binIndex(START, START, AS_OF) === 0 && B.binIndex(START - 1, START, AS_OF) === -1 && B.binIndex(AS_OF + 1, START, AS_OF) === -1);
ok('bins: max ≥ 1 on an empty range', B.binRows([], START, AS_OF).max === 1);
ok('bins: range presets 1 h, 6 h, 24 h, 7 d', B.RANGES.map((r) => r.id).join(',') === '1h,6h,24h,7d' && B.rangeMs('7d') === 7 * B.DAY);
ok('bins: "older rows not loaded" only for a capped feed and a range before its oldest row', B.olderNotLoaded(START, START + 1000, 500) && !B.olderNotLoaded(START, START + 1000, 499) && !B.olderNotLoaded(START + 2000, START + 1000, 500) && !B.olderNotLoaded(START, null, 500));
const fit = B.fitRange(FEED, [], AS_OF);
ok('bins: Fit to the data covers the oldest row and ends now', fit[1] === AS_OF && fit[0] <= B.oldestOf(FEED));
const ticks = B.axisTicks(START, AS_OF, 1200);
ok('bins: IST axis ticks on the hour, 00:00 carries its day', ticks.length >= 5 && ticks.some((x) => x.label === '00:00 24 Oct') && ticks.every((x) => /^\d\d:\d\d( \d+ \w{3})?$/.test(x.label)), ticks.map((x) => x.label).join(' '));
ok('bins: the replay axis is tape time (t+mm:ss), never IST', B.tapeLabel(75) === 't+01:15' && B.tapeTicks(600, 800).every((x) => x.label.startsWith('t+')));

const S = { start: START, end: AS_OF, x0: 136, x1: 1136 };
ok('brush: x ↔ t round trip', Math.abs(BR.tOf(S, BR.xOf(S, START + 3 * B.HOUR)) - (START + 3 * B.HOUR)) < 1);
ok('brush: a press under 4 px is a click, not a window', BR.brushWindow(S, 500, 503) === null);
const bw = BR.brushWindow(S, 900, 700);
ok('brush: a drag gives a sorted window', !!bw && bw[0] < bw[1] && Math.abs(bw[0] - BR.tOf(S, 700)) <= 1);
const bc = BR.brushWindow(S, 20, 2000);
ok('brush: clamped to the plot', bc[0] === START && bc[1] === AS_OF);
ok('brush: a grip drag never inverts the window', BR.moveEdge([1000, 2000], 'start', 5000)[0] === 2000 - BR.MIN_WINDOW_MS && BR.moveEdge([1000, 2000], 'end', 0)[1] === 1000 + BR.MIN_WINDOW_MS);
ok('brush: a window shifted past now is live again', BR.shiftWindow([AS_OF - 600_000, AS_OF - 60_000], 120_000, AS_OF) === null && BR.shiftWindow([AS_OF - 600_000, AS_OF - 300_000], 60_000, AS_OF)[1] === AS_OF - 240_000);
ok('brush: grips hit within 6 px, inside between them', BR.hitWindow(S, bw, BR.xOf(S, bw[0]) + 3) === 'start' && BR.hitWindow(S, bw, (BR.xOf(S, bw[0]) + BR.xOf(S, bw[1])) / 2) === 'inside' && BR.hitWindow(S, null, 500) === null);
{
	const store = new ws.Workspace({ world: () => ({ graph: () => OG, registry: () => [], feed: () => FEED, units: () => [], now: () => AS_OF }), storage: () => null, now: () => AS_OF });
	ok('live: no window ⇔ Live', store.live === true && store.timeWindow === null && BR.isLive(store.timeWindow));
	BR.applyBrush(store, bw);
	ok('live: brushing sets the window and turns Live off', store.live === false && store.timeWindow[0] === bw[0] && store.timeWindow[1] === bw[1]);
	BR.applyBrush(store, null);
	ok('live: a click (no window) changes nothing', store.live === false);
	store.returnToLive();
	ok('live: returnToLive clears the window (Live on, cursor "Now")', store.live === true && store.timeWindow === null && BR.cursorOf(store.timeWindow, AS_OF, 123) === AS_OF);
	store.setTimeWindow(AS_OF, AS_OF - 1000);
	ok('live: reversed ends are swapped', store.timeWindow[0] === AS_OF - 1000);
}

ok('lanes: seven, in order', LN.LANE_IDS.join(',') === 'event,enforcement,anpr,dispatch,signals,ama,brain');
const osintRow = cityApi.parseFeedRow({ id: 'osint:1', t: new Date(AS_OF - 3_600_000).toISOString(), kind: 'osint', urns: ['osint_event:6f1c2a9e-3b7d-4e21-9a55-0c8e7d4b1f20'], actor: 'osint-ingress (system)', actor_kind: 'system', text: 'Road accident reported near Sector V', source: 'live', verification_state: 'NEWS-REPORTED', credibility: 0.65, severity: 'warn', props: {} });
ok('lanes: osint → the Events lane (X8)', LN.laneOf(osintRow) === 'event' && LN.isOsint(osintRow) && osintRow.source === 'osint');
{
	// X8 + ethics rule 7: an open-source mark carries its verification label (the X2 words)
	const tipNews = TIP.rowTip(osintRow, AS_OF, 'en');
	const parts = TIP.rowTipParts(osintRow, AS_OF, 'en');
	ok('timeline: an osint tick’s tooltip ends in its verification label', tipNews.endsWith(' · News-reported') && parts.label === 'News-reported' && !parts.text.includes('News-reported'), tipNews);
	const states = { 'UNVERIFIED-OSINT': 'Unverified OSINT', 'NEWS-REPORTED': 'News-reported', 'OFFICIAL-VERIFIED': 'Official, verified', CONFIRMED: 'Confirmed by officer' };
	ok('timeline: the four X2 verification labels, and "Open-source" without a state', Object.entries(states).every(([k, v]) => TIP.osintLabel(k, 'en') === v && TIP.osintVerification(k) === k) && TIP.osintLabel(null, 'en') === 'Open-source' && TIP.osintLabel('EMULATED', 'en') === 'Open-source' && TIP.osintVerification('EMULATED') === null);
	const bare = cityApi.parseFeedRow({ id: 'osint:2', t: new Date(AS_OF - 60_000).toISOString(), kind: 'osint', urns: [], actor: 'osint-ingress (system)', actor_kind: 'system', text: 'Waterlogging reported near the Thanthania crossing', source: 'live', severity: 'info', props: {} });
	ok('timeline: an osint row with no state still says it is open-source', TIP.rowTip(bare, AS_OF, 'en').endsWith(' · Open-source'), TIP.rowTip(bare, AS_OF, 'en'));
	ok('timeline: the label is translated (HI, MR)', TIP.osintLabel('NEWS-REPORTED', 'hi') !== 'News-reported' && TIP.osintLabel('NEWS-REPORTED', 'mr') !== 'News-reported' && TIP.osintLabel('NEWS-REPORTED', 'hi') !== 'ui_verif_news');
	const live = FEED.find((f) => f.kind === 'event');
	ok('timeline: a live row’s tooltip carries no provenance label', TIP.rowTipParts(live, AS_OF, 'en').label === null && !/Open-source|News-reported/.test(TIP.rowTip(live, AS_OF, 'en')));
}
const lc = LN.laneCounts([...FEED, osintRow]);
const kc = LN.kindCounts([...FEED, osintRow]);
ok('lanes: counts per lane include the osint row in Events; the kind counts keep it apart', lc.event === 55 && kc.event === 54 && kc.osint === 1 && lc.enforcement === 37 && lc.anpr === 19 && lc.dispatch === 13 && lc.signals === 0 && lc.ama === 18 && lc.brain === 48, JSON.stringify(lc));
const anpr = FEED.find((f) => f.kind === 'anpr');
const pend = FEED.find((f) => f.kind === 'enforcement' && f.props.status === 'pending');
const rej = FEED.find((f) => f.kind === 'enforcement' && f.props.status === 'rejected' && f.actorKind === 'machine');
const ama = FEED.find((f) => f.kind === 'ama' && f.severity === 'critical');
ok('lanes: a watchlist read is red, a waiting decision orange, a band change neutral', LN.toneOf(anpr, null) === 'watch' && LN.toneOf(pend, null) === 'decision' && LN.toneOf(rej, null) === 'neutral' && LN.toneOf(ama, null) === 'neutral');
ok('lanes: a row linked to the selection is blue, whatever else it is', LN.toneOf(anpr, related) === 'linked');
ok('lanes: an officer action is the tall tick', FEED.filter(LN.isOfficerAction).every((f) => f.actorKind === 'human') && FEED.some(LN.isOfficerAction));

// ─── audit rows ─────────────────────────────────────────────────────────────

const items = FEED.map((f) => AU.itemFromFeed(f, { officer: false, lang: 'en' }));
ok('audit: one item per feed row, ids and urns kept', items.length === FEED.length && items.every((it, i) => it.feedId === FEED[i].id && it.rowId === FEED[i].id && it.urn === (FEED[i].urns[0] ?? null)));
ok('audit: actor kinds as the oracle recorded them', items.every((it, i) => it.actorKind === FEED[i].actorKind));
ok('audit: actors humanised (traffic-oracle → Rules engine, convoy-brain → Sajag AI)', items.some((it) => it.actor === 'Rules engine') && items.some((it) => it.actor === 'Sajag AI'));
const emu = items.filter((it) => it.source === 'emulated');
ok('audit: provenance only on non-live rows', items.filter((it) => it.source === 'live').every((it) => it.prov === null) && emu.every((it) => it.prov?.source === 'emulated'));
ok('audit: one item per id (a repeated row is kept once, the first)', AU.uniqueById([...items, ...items.slice(0, 7)]).length === items.length && AU.uniqueById([{ id: 'a', n: 1 }, { id: 'a', n: 2 }])[0].n === 1);
ok('audit: a uniform list states its provenance once (SPEC §9.2); a mixed or all-live list does not', AU.uniformProv(emu)?.source === 'emulated' && AU.uniformProv(items) === null && AU.uniformProv(items.filter((it) => it.source === 'live')) === null && AU.uniformProv([]) === null && AU.provWord({ source: 'emulated', verification: null }, 'en') === 'Emulated' && AU.provWord({ source: 'osint', verification: 'NEWS-REPORTED' }, 'en') === 'News-reported');
const osItem = AU.itemFromFeed(osintRow, { officer: false, lang: 'en' });
ok('audit: an osint row carries its verification label', osItem.prov?.source === 'osint' && osItem.prov?.verification === 'NEWS-REPORTED' && osItem.kindLabel === 'Open-source');
const human = FX.feed.items.find((i) => i.actor_kind === 'human' && i.kind === 'enforcement' && /dismissed by/.test(i.text));
const hItem = AU.itemFromFeed(cityApi.parseFeedRow(human), { officer: false, lang: 'en' });
ok('audit: the server sentence stays whole in the tooltip (the officer’s words verbatim)', hItem.full === human.text && hItem.full.includes(': stale EMULATED sighting'));
ok('audit: filters (all / officers / machine / system)', AU.filterItems(items, 'officers').every((x) => x.actorKind === 'human') && AU.filterItems(items, 'machine').every((x) => x.actorKind === 'machine') && AU.filterItems(items, 'system').every((x) => x.actorKind === 'system') && AU.filterItems(items, 'all').length === items.length);
const ai = AU.aiTrace(items);
ok('audit: the AI trace holds model rows only, no officer row', ai.length === 48 && ai.every((x) => x.actorKind !== 'human' && x.kind === 'brain'), `${ai.length} rows`);
const brainRow = cityApi.parseFeedRow({ id: 'decisions_log:x', t: new Date(AS_OF).toISOString(), kind: 'brain', urns: [], actor: 'convoy-brain', actor_kind: 'machine', text: 'Decider checkpoint (approach): tier decider', source: 'live', severity: 'info', props: { phase: 'decider_checkpoint', tier: 'decider', confidence: 0.81 } });
const bi = AU.itemFromFeed(brainRow, { officer: false, lang: 'en' });
ok('audit: AI rows carry phase, tier and confidence', bi.phase === 'Decider checkpoint' && bi.tier === 'decider' && bi.confidence === 0.81, `${bi.phase} · ${bi.tier} · ${bi.confidence}`);
const ledger = [
	{ id: 1, ts: AS_OF - 5000, source: 'audit-poll', level: 'decision', actor: 'Duty Officer', text: 'e-challan APPROVED by Duty Officer (R_SPD_SEGMENT)', actorKind: 'human', serverId: 'enforcement_recommendations:x:2', kind: 'enforcement', emulated: true, urns: ['recommendation:00000000-0000-4000-8000-000000000001'] },
	{ id: 2, ts: AS_OF - 4000, source: 'ndjson-chat', level: 'tool', actor: 'mcp:get_active_events', text: 'result · 3 events', actorKind: 'machine' },
	{ id: 3, ts: AS_OF - 3000, source: 'operator', level: 'info', actor: 'operator (unnamed)', text: 'audit probe: "why?"', actorKind: 'human' },
];
const li = ledger.map((e) => AU.itemFromEntry(e, { lang: 'en' }));
ok('audit: ledger rows keep data-row-id for server rows only', li[0].rowId === 'enforcement_recommendations:x:2' && li[1].rowId === null && li[2].rowId === null && li[1].local && !li[0].local);
ok('audit: a tool step reads as words (get_active_events → "…active events")', /active events/i.test(li[1].actor), li[1].actor);
ok('audit: the ledger AI trace drops officer rows', AU.aiTrace(li).length === 1 && AU.aiTrace(li)[0].id === li[1].id);
const csv = AU.toCsv([...items.slice(0, 5), hItem], 'en');
ok('audit: CSV has a provenance column and no raw mark', csv.split('\n')[0].includes('Source') && !/\b[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{4}\b/.test(csv) && csv.includes('MH47EM•••1'));

// ─── ethics: no raw mark in any row text, in any case or spelling ──────────
// (FIX-B-DECK, SPEC §9.3: an officer's typed note or a model's answer can carry
// a mark the oracle's upper-case mask never saw — mh47em9001, MH.01.XX.0007,
// MH_47_EM_9001 — and no row may print it without a named officer)
{
	const RAW = ['mh47em9001', 'MH.01.XX.0007', 'MH_47_EM_9001', 'Mh 47 Em 9001', 'MH/01/XX/0007'];
	const leaks = (s) => RAW.filter((r) => String(s).includes(r)).concat(/9001|0007/.test(String(s).replace(/•••[0-9]/g, '')) ? ['digits'] : []);
	const note = `Stolen-vehicle sighting of MH47EM•••1 dismissed by Sandbox Officer: seen ${RAW.join(', ')} twice`;
	const fr = cityApi.parseFeedRow({ id: 'enf:raw', t: new Date(AS_OF).toISOString(), kind: 'enforcement', urns: [VEHICLE], actor: 'Sandbox Officer', actor_kind: 'human', text: note, source: 'emulated', severity: 'info', props: { note: `seen ${RAW.join(', ')} twice` } });
	const fi = AU.itemFromFeed(fr, { officer: false, lang: 'en' });
	ok('masking: a feed row’s text and tooltip carry no raw mark in lower case, dotted, underscored or slashed spelling', leaks(fi.text).length === 0 && leaks(fi.full).length === 0 && (fi.full.match(/•••/g) ?? []).length >= RAW.length + 1, fi.full.slice(-120));
	const ei = AU.itemFromEntry({ id: 9, ts: AS_OF, source: 'operator', level: 'decision', actor: 'Sandbox Officer', text: `note: ${RAW.join(' ')}`, actorKind: 'human' }, { lang: 'en', officer: false });
	ok('masking: a ledger row (a local echo) is masked in every spelling', leaks(ei.text).length === 0 && leaks(ei.full).length === 0, ei.text);
	const ar = AU.itemFromFeed(cityApi.parseFeedRow({ id: 'ama:raw-actor', t: new Date(AS_OF).toISOString(), kind: 'ama', urns: [], actor: 'operator mh47em9001', actor_kind: 'system', text: 'band note', source: 'live', severity: 'info', props: {} }), { officer: false, lang: 'en' });
	ok('masking: a feed row’s shown actor name is masked too', leaks(ar.actor).length === 0 && leaks(ar.actorRaw).length === 0, ar.actor);
	ok('masking: the CSV export never carries a raw mark', leaks(AU.toCsv([fi, ei], 'en')).length === 0);
	ok('masking: a timeline tooltip never carries a raw mark', leaks(TIP.rowTip(fr, AS_OF, 'en')).length === 0, TIP.rowTip(fr, AS_OF, 'en'));
	ok('masking: masked() hides every spelling unless an officer is named', leaks(AU.masked(RAW.join(' '), false)).length === 0 && AU.masked('mh47em9001', true) === 'mh47em9001');
	const hr = HI.parseEventHistoryRow({ event_id: 'abc-2', title: 'pursuit of mh47em9001', updated_at: '2026-10-23T10:00:00Z', metadata: { note: 'MH.01.XX.0007 and MH_47_EM_9001' } });
	ok('masking: the event history masks every spelling at any depth', leaks(JSON.stringify(hr)).length === 0, hr.title);
	const officerItem = AU.itemFromFeed(cityApi.parseFeedRow({ id: 'anpr:raw', t: new Date(AS_OF).toISOString(), kind: 'anpr', urns: [], actor: 'EM-CAM-03', actor_kind: 'machine', text: 'ANPR hit · MH47EM•••1 at EM-CAM-03', source: 'emulated', severity: 'critical', props: { plate: 'MH47EM9001', plate_masked: 'MH47EM•••1' } }), { officer: true, lang: 'en' });
	ok('masking: a named officer sees the raw mark only from the row’s own props.plate', officerItem.full.includes('MH47EM9001'));
}

// ─── history client ─────────────────────────────────────────────────────────

const HX = JSON.parse(readFileSync(HISTORY, 'utf8'));
const hist = HI.parseEventHistory(HX);
ok('history: the contract fixture parses (18 events)', hist.length === 18 && hist.every((r) => r.urn === `event:${r.eventId}`), `${hist.length} rows`);
ok('history: newest first by update', hist.every((r, i) => i === 0 || (hist[i - 1].updatedAt ?? 0) >= (r.updatedAt ?? 0)));
ok('history: closed events have an end; an open one runs to now', hist.filter((r) => ['completed', 'cancelled'].includes(r.status)).every((r) => r.end != null && r.end >= r.start) && hist.filter((r) => r.status === 'planning').every((r) => r.end == null || r.end >= r.start));
ok(
	'history: the timeline spans only events that ran (actual start) or are still planned; a cancelled-before-start or timeless one has none',
	hist.filter((r) => r.raw.actual_start).every((r) => r.span && r.span[0] === Date.parse(r.raw.actual_start)) &&
		hist.filter((r) => !r.raw.actual_start && ['completed', 'cancelled'].includes(r.status)).every((r) => r.span === null) &&
		hist.find((r) => r.kind === 'vehicle_pursuit')?.span === null,
	`${hist.filter((r) => r.span).length} of ${hist.length} with a span`,
);
ok('history: emulator runs read emulated', hist.filter((r) => r.raw.metadata?.source === 'event-emulator').every((r) => r.source === 'emulated') && hist.some((r) => r.source === 'live'));
ok('history: a bare array, junk rows and duplicates are tolerated', HI.parseEventHistory([...HX.events, null, 7, { title: 'no id' }, HX.events[0]]).length === 18 && HI.parseEventHistory({}).length === 0 && HI.parseEventHistory('nope').length === 0);
const raw = HI.parseEventHistoryRow({ event_id: 'abc-1', title: 'PURSUIT — stolen MH47EM9001', updated_at: '2026-10-23T10:00:00Z', metadata: { note: 'seen MH01AB1234 twice' } });
ok('history: a raw mark is masked at any depth', raw.title.includes('MH47EM•••1') && !JSON.stringify(raw).includes('9001') && !JSON.stringify(raw).includes('1234'));

// ─── vendored ISC sources ───────────────────────────────────────────────────

const VEND = path.join(DECK, 'src', 'lib', 'vendor');
const want = { 'd3-force': '3.0.0', 'd3-quadtree': '3.0.1', 'd3-dispatch': '3.0.1', 'd3-timer': '3.0.1' };
for (const [name, ver] of Object.entries(want)) {
	const dir = path.join(VEND, name);
	const lic = existsSync(path.join(dir, 'LICENSE')) ? readFileSync(path.join(dir, 'LICENSE'), 'utf8') : '';
	const md = existsSync(path.join(dir, 'VENDORED.md')) ? readFileSync(path.join(dir, 'VENDORED.md'), 'utf8') : '';
	const src = existsSync(path.join(dir, 'src')) ? readdirSync(path.join(dir, 'src')) : [];
	const bare = src.filter((f) => /from "d3-/.test(readFileSync(path.join(dir, 'src', f), 'utf8')));
	ok(`vendor ${name}@${ver}: LICENSE (ISC, Mike Bostock), VENDORED.md with its sha256, src with no bare import`, /Mike Bostock/.test(lic) && /ISC|Permission to use, copy, modify/.test(lic) && md.includes(ver) && /sha256/i.test(md) && /[0-9a-f]{64}/.test(md) && src.includes('index.js') && bare.length === 0 && src.every((f) => readFileSync(path.join(dir, 'src', f), 'utf8').startsWith('// @ts-nocheck')), `${src.length} files`);
}

// ─── packs ──────────────────────────────────────────────────────────────────

const { en, hi, mr } = packs.ANALYSIS_PACKS;
const ek = Object.keys(en).sort().join();
ok('packs: EN, HI and MR carry the same keys', ek === Object.keys(hi).sort().join() && ek === Object.keys(mr).sort().join(), `${Object.keys(en).length} keys`);
ok('packs: every key starts with an_', Object.keys(en).every((k) => k.startsWith('an_')));
ok('packs: the stats read "51 linked · 14 merged"', `${tr('en', 'an_g_stats_linked', 51)} · ${tr('en', 'an_g_stats_merged', 14)}` === '51 linked · 14 merged');

console.log(`\n${failures === 0 ? 'PASS' : 'FAIL'} analysis.unit — ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
