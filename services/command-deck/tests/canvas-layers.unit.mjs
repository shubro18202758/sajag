/**
 * Canvas layer unit test — the REAL draping helpers, pursuit overlay and
 * traffic-flow / camera / signal layers against a fake Cesium.
 *
 * Bundles src/lib/gods-eye/layers/draping.ts, pursuit.ts, layers/
 * traffic-flow.ts, layers/cameras.ts and layers/signal-network.ts with the
 * vendored esbuild (`$lib` aliased to src/lib; the God's-eye store stubbed:
 * a plain object the test fills; `fetch` stubbed), then asserts,
 * hermetically (no browser, no network):
 *
 *   1. draping helpers (WP-22 — overlays ON the photoreal 3D city): a draped
 *      polyline is a ground polyline (clampToGround, classificationType BOTH,
 *      the DRAPE_Z ground order, the enum values of the vendored 1.146 build
 *      when the global lacks them); markers are clamped to the terrain with
 *      the depth test off at every distance, labels nudged toward the camera;
 *      a DOT is billboard graphics with an explicit size (never a clamped
 *      `point`: Cesium pools that billboard and never resets its size); a
 *      ground ellipse has no height and no outline; a ring is a closed loop
 *      at its radius; the drape audit reads draped / clamped / floating
 *      graphics back from plain and Property-wrapped entities;
 *   2. pursuit: the 45 m sighting ring is a RING — a draped rim in the full
 *      data colour over a 15 % veil filled on the ground — so the vehicle
 *      mark and the selection halo inside stay visible; a STALE sighting's
 *      rim and veil go dim (ink); a Cesium build without Color.withAlpha /
 *      TRANSPARENT draws the rim alone — never an opaque disc; the growing
 *      rim and the head-first trace land on constant positions; the future
 *      arc marches through a time-varying dash length INSIDE its material;
 *      every pursuit graphic is draped or clamped, and the overlay's own
 *      audit() (published by the canvas as layerStats.pursuit) says so;
 *   3. traffic-flow (contract C-P): /traffic/live `emulated_observations`
 *      colour their segment while fresh, badged EMULATED · SIMULATED FEED
 *      on the pick card with the ingest plane's own reading beside it, and
 *      the hint / detail count them ('n EMULATED'); a stale showcase row
 *      hands the segment back to the ingest plane; a row's road_name names
 *      a segment the segment feed left unnamed; an oracle without the
 *      emulated plane draws exactly as before; every segment is DRAPED at
 *      the bottom of the ground order — real OSM geometry ('osm',
 *      'osm_display') solid, only 'schematic' dashed — and the layer reports
 *      floating 0;
 *   4. cameras + signal network: every marker is clamped billboard graphics
 *      (no entity carries a `point`, none carries two billboards), drape
 *      audit floating 0;
 *   5. overlay labels (layers/labels.ts): every overlay label's translucent
 *      canvas plate; a feed anomaly in the operator's words in EN / HI / MR
 *      ('Speed jump ×6', never 'speed_jump') and an unknown id humanised,
 *      never snake_case; a site label folds identical lines into one with a
 *      count ('STOLEN · NO FINE · PENDING ×2') and counts the readings left
 *      over in '+n more'.
 *   6. the map's v2 rules (UI-S3, SPEC §5.3, §7.3): clustering (strictly
 *      under 22 px, the selection's member leads, grid-bucketed above 50
 *      markers = the pairwise answer), greedy label placement (8 candidates,
 *      occupied boxes, the view, priority, dropped labels), the view's
 *      opacities (selection dimming, the time window's fading, protected
 *      objects and infrastructure never fading, the kind filter);
 *   7. the share link passes through the keys it does not own (R24) under
 *      the hostile-hash guards;
 *   8. the registry: the required layer ids and unique pick prefixes (never
 *      an exact count, X7/X14), every layer in a LayerTree group, the
 *      reserved osint / places ids and prefixes;
 *   9. the flow ramp under chrome v2 (live map, 29 Oct: the band ladder green / amber / red by V/C or congestion, the
 *      neutral ramp's widths, never under 3 px): flowStyle(flowStop(c)) widths
 *      and luminance, the casing from stop 3, a NO DATA trace dimmer than
 *      free, 60 % and 0.5 px thinner under a selection;
 *  10. every layer under chrome v2 reads --v-map-* / --v-flow-* and never
 *      --v-act, --v-data or --v-tool (the token reads instrumented), tags
 *      its markers (type glyph, role, cluster, labels) and draws no Cesium
 *      label of its own; one decision dot per object (the vehicle, never one
 *      per sighting); the selected vehicle's track (latest pass / window);
 *      LEGACY INVARIANCE: the same fixtures under the legacy chrome read the
 *      same tokens and draw what they drew before (pins, rings, labels);
 *  11. the label policy: no v2 label or pick text stacks status words;
 *      the KIND FILTER hides every layer's own lines too (flow, spines,
 *      zones, the convoy's route and detours, the track, the dispatch
 *      line, the pursuit heading) while the legacy chrome ignores it; a
 *      proposed detour previews in the route turquoise, never orange; a
 *      read from another day is dated; the painted-image cache is bounded;
 *      a pursuit's choke squares anchor the clusters at their junctions;
 *  12. LEGACY INVARIANCE AGAINST A RECORD: every legacy layer and the
 *      legacy pursuit overlay draw one fixed city picture (frozen clock,
 *      real token values); each entity's normalized graphics and each
 *      layer's coverage stats are fingerprinted and compared with the
 *      recorded fingerprints (`--record-legacy` prints a new record).
 *
 * Run from services/command-deck:   node tests/canvas-layers.unit.mjs
 * (bundle written to tests/artifacts/, which is gitignored)
 */

import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const ARTIFACTS = path.join(HERE, 'artifacts');
mkdirSync(ARTIFACTS, { recursive: true });

const esbuild = await import(pathToFileURL(path.join(DECK, 'node_modules/esbuild/lib/main.js')).href);

// The runes stores need the Svelte compiler; the layers read a few fields of
// each: plain objects the test fills (the gods-eye store, the ops store, the
// city registry, the escort follower, the corridor summary).
const STUBS = {
	'ops-store': [
		'export const ops = { officerOn: false, lang: "en", watchlist: [], events: [], interception: null,',
		'  eventById(id) { return this.events.find((e) => e.eventId === id) ?? null; } };',
	],
	'city-registry': [
		'const rows = {}; const feeds = {};',
		'export const cityRegistry = { rows, feeds, status: "ok", note: null, version: 1,',
		'  byKind: (k) => rows[k] ?? [], served: () => true, refresh: async () => true, related: () => [],',
		'  feed: (k) => feeds[k] ?? null,',
		'  get: (urn) => Object.values(rows).flat().find((e) => e.urn === urn) ?? null };',
	],
	escort: ['export const escortFollower = { movementId: null, status: null };'],
	corridor: ['export const corridor = { provenance: "live", start() {}, stop() {}, traffic: [], signal: null, junctions: [] };'],
	'gods-eye-store': [
		'const feed = () => ({ status: "ok", note: null, updatedAt: Date.now(), total: 0 });',
		'export const godsEye = { segments: [], segmentsFeed: { status: "ok" }, pollSegments: async () => {},',
		'  get segmentById() { return new Map(this.segments.map((s) => [s.segmentId, s])); },',
		'  cameras: [], camerasFeed: feed(), pollCameras: async () => {},',
		'  signals: [], signalsFeed: feed(), pollSignals: async () => {},',
		'  vehicles: [], vehiclesFeed: feed(), pollVehicles: async () => {}, traces: new Map(),',
		'  registryTrace(id) { return this.traces.get(id) ?? null; },',
		'  units: [], unitsFeed: feed(), pollUnits: async () => {},',
		'  imageryMode: "keyless-osm", imageryToken: null, via: () => "city" };',
		'export function feedError() { return null; }',
		'export function feedHint() { return null; }',
	],
};
const stubStore = {
	name: 'stub-runes-stores',
	setup(build) {
		const to = (name) => () => ({ path: name, namespace: 'stub' });
		build.onResolve({ filter: /ops\/store\.svelte$/ }, to('ops-store'));
		build.onResolve({ filter: /entities\/registry\.svelte$/ }, to('city-registry'));
		build.onResolve({ filter: /template\/escort\.svelte$/ }, to('escort'));
		build.onResolve({ filter: /template\/corridor\.svelte$/ }, to('corridor'));
		build.onResolve({ filter: /store\.svelte$/ }, to('gods-eye-store'));
		build.onLoad({ filter: /.*/, namespace: 'stub' }, (args) => ({ contents: STUBS[args.path].join('\n'), loader: 'js' }));
	},
};

const entry = [
	`export * from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/layers/draping.ts'))};`,
	`export * from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/pursuit.ts'))};`,
	`export * from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/layers/traffic-flow.ts'))};`,
	`export { camerasLayer } from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/layers/cameras.ts'))};`,
	`export { signalNetworkLayer } from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/layers/signal-network.ts'))};`,
	`export { godsEye } from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/store.svelte'))};`,
	`export * from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/layers/labels.ts'))};`,
	`export { ops } from ${JSON.stringify(path.join(DECK, 'src/lib/ops/store.svelte'))};`,
	`export { cityRegistry } from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/entities/registry.svelte'))};`,
	`export { escortFollower } from ${JSON.stringify(path.join(DECK, 'src/lib/ops/components/template/escort.svelte'))};`,
	`export * as V from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/hud/map/view.ts'))};`,
	`export * as SYM from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/hud/map/symbols.ts'))};`,
	`export * as CL from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/hud/map/cluster.ts'))};`,
	`export * as LP from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/hud/map/labels.ts'))};`,
	`export * as SL from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/share-link.ts'))};`,
	`export * as REG from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/registry.ts'))};`,
	`export * as IDX from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/layers/index.ts'))};`,
	`export * as ENF from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/layers/enforcement.ts'))};`,
	`export * as OSI from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/layers/osint.ts'))};`,
	`export * as TR from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/layers/vehicle-traces.ts'))};`,
	`export * as TOK from ${JSON.stringify(path.join(DECK, 'src/lib/design/tokens.ts'))};`,
	`export * as ICONS from ${JSON.stringify(path.join(DECK, 'src/lib/design/icons.ts'))};`,
	`export * as WL from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/layers/waterlogging.ts'))};`,
	`export * as FL from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/layers/forecast.ts'))};`,
	`export * as AQ from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/layers/air.ts'))};`,
	`export * as CY from ${JSON.stringify(path.join(DECK, 'src/lib/gods-eye/layers/cyclone.ts'))};`,
	`export * as HS from ${JSON.stringify(path.join(DECK, 'src/lib/ai/hindsight.ts'))};`,
].join('\n');
const outfile = path.join(ARTIFACTS, 'canvas-layers-unit-bundle.mjs');
await esbuild.build({
	stdin: { contents: entry, resolveDir: DECK, loader: 'ts', sourcefile: 'canvas-layers-unit.entry.ts' },
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	platform: 'node',
	format: 'esm',
	outfile,
	logLevel: 'error',
	plugins: [stubStore],
});
const M = await import(`${pathToFileURL(outfile).href}?t=${Date.now()}`);

let failures = 0;
function check(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const tick = () => new Promise((r) => setTimeout(r, 0));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ── the fake Cesium ─────────────────────────────────────────────────────────

function makeCesium({ withAlpha = true, transparent = true, enums = false, cartesianClass = false } = {}) {
	class Color {
		constructor(r, g, b, a = 1) {
			Object.assign(this, { r, g, b, a });
		}
		static fromCssColorString(css) {
			const c = new Color(0.5, 0.5, 0.5, 1);
			c.css = css;
			return c;
		}
	}
	if (withAlpha) {
		Color.prototype.withAlpha = function (a) {
			const c = new Color(this.r, this.g, this.b, a);
			c.name = this.name;
			return c;
		};
	}
	const named = (name, r, g, b) => Object.assign(new Color(r, g, b, 1), { name });
	Color.CYAN = named('CYAN', 0, 1, 1);
	Color.ORANGE = named('ORANGE', 1, 0.65, 0);
	Color.LIGHTGRAY = named('LIGHTGRAY', 0.83, 0.83, 0.83);
	Color.GRAY = named('GRAY', 0.5, 0.5, 0.5);
	Color.LIME = named('LIME', 0, 1, 0);
	Color.RED = named('RED', 1, 0, 0);
	Color.WHITE = named('WHITE', 1, 1, 1);
	Color.BLACK = named('BLACK', 0, 0, 0);
	if (transparent) Color.TRANSPARENT = Object.assign(new Color(0, 0, 0, 0), { name: 'TRANSPARENT' });
	const fromDegrees = (lon, lat, h = 0) => ({ lon, lat, h });
	const fromDegreesArray = (flat) => {
		const out = [];
		for (let i = 0; i < flat.length; i += 2) out.push({ lon: flat[i], lat: flat[i + 1], h: 0 });
		return out;
	};
	const Cartesian3 = cartesianClass
		? Object.assign(
				class {
					constructor(x, y, z) {
						Object.assign(this, { x, y, z });
					}
				},
				{ fromDegrees, fromDegreesArray },
			)
		: { fromDegrees, fromDegreesArray };
	return {
		Color,
		Cartesian2: class {
			constructor(x, y) {
				Object.assign(this, { x, y });
			}
		},
		Cartesian3,
		CallbackProperty: class {
			constructor(fn) {
				this.fn = fn;
			}
		},
		// Cesium's signature: the colour itself (an options object painted the trace white)
		ColorMaterialProperty: class {
			constructor(color) {
				if (color && typeof color === 'object' && 'color' in color && !('r' in color)) throw new TypeError('ColorMaterialProperty takes a Color, not options');
				this.color = color;
			}
		},
		PolylineDashMaterialProperty: class {
			constructor(opts) {
				Object.assign(this, opts, { dashed: true });
			}
		},
		PolylineOutlineMaterialProperty: class {
			constructor(opts) {
				Object.assign(this, opts, { outlined: true });
			}
		},
		DistanceDisplayCondition: class {
			constructor(near, far) {
				Object.assign(this, { near, far });
			}
		},
		NearFarScalar: class {
			constructor(near, nearValue, far, farValue) {
				Object.assign(this, { near, nearValue, far, farValue });
			}
		},
		PolylineArrowMaterialProperty: class {
			constructor(color) {
				Object.assign(this, { color, arrow: true });
			}
		},
		PolylineGlowMaterialProperty: class {
			constructor(opts) {
				Object.assign(this, opts, { glow: true });
			}
		},
		...(enums
			? {
					HeightReference: { NONE: 10, CLAMP_TO_GROUND: 11, RELATIVE_TO_GROUND: 12, CLAMP_TO_TERRAIN: 13 },
					ClassificationType: { TERRAIN: 20, CESIUM_3D_TILE: 21, BOTH: 22 },
				}
			: {}),
	};
}

function makeViewer() {
	const byId = new Map();
	return {
		byId,
		entities: {
			add(e) {
				byId.set(e.id, e);
				return e;
			},
			removeById(id) {
				return byId.delete(id);
			},
			getById: (id) => byId.get(id),
		},
	};
}

/**
 * A stable, comparable rendering of an entity graph: keys sorted, numbers to
 * 1e-6, a time-varying CallbackProperty reduced to its marker (never sampled
 * — its value moves with the clock), functions to '[fn]', the fake classes
 * named. `omit` drops top-level keys (the pick text, when the clock moves).
 */
function normGraph(v, omit = [], depth = 0) {
	if (depth > 8) return '…';
	if (v === null || v === undefined) return null;
	if (typeof v === 'number') return Number.isFinite(v) ? Math.round(v * 1e6) / 1e6 : String(v);
	if (typeof v === 'string' || typeof v === 'boolean') return v;
	if (typeof v === 'function') return '[fn]';
	if (Array.isArray(v)) return v.map((x) => normGraph(x, [], depth + 1));
	const cls = v.constructor?.name;
	if (cls === 'CallbackProperty') return '[callback]';
	const out = cls && cls !== 'Object' ? { $: cls } : {};
	for (const k of Object.keys(v).sort()) if (!(depth === 0 && omit.includes(k))) out[k] = normGraph(v[k], [], depth + 1);
	return out;
}

// ── 1. draping helpers ───────────────────────────────────────────────────────

{
	const cesium = makeCesium();
	const material = { m: 1 };
	const line = M.drapedPolyline(cesium, { positions: [1, 2], width: 6, material, z: M.DRAPE_Z.flow });
	check(
		'drapedPolyline: a ground polyline on terrain AND 3D tiles',
		line.clampToGround === true && line.classificationType === 2 && line.zIndex === M.DRAPE_Z.flow,
		JSON.stringify({ c: line.clampToGround, k: line.classificationType, z: line.zIndex }),
	);
	check('drapedPolyline: keeps width / material / positions, drops z', line.width === 6 && line.material === material && line.positions.length === 2 && !('z' in line));
	check(
		'the 1.146 enum values back the helpers (HeightReference CLAMP_TO_TERRAIN 3, ClassificationType BOTH 2)',
		M.HEIGHT_REFERENCE.CLAMP_TO_GROUND === 1 && M.HEIGHT_REFERENCE.CLAMP_TO_TERRAIN === 3 && M.CLASSIFICATION_TYPE.BOTH === 2,
	);
	const z = M.DRAPE_Z;
	check(
		'ground order: flow < spines < RECOMMENDED < traces < dispatch < convoy < pursuit; fixtures below live',
		z.flow < z.spine && z.spine < z.recommended && z.recommended < z.trace && z.trace < z.dispatch && z.dispatch < z.convoy && z.convoy < z.pursuit && z.fixtureSpine < z.spine && z.superseded < z.spine,
	);

	const label = M.clampedLabel(cesium, { text: 'x', pixelOffset: { x: 0, y: 10 } });
	check(
		'clampedLabel: clamped to the terrain, depth test off at every distance, caller offset kept',
		label.heightReference === 3 && label.disableDepthTestDistance === Number.POSITIVE_INFINITY && label.pixelOffset.y === 10 && label.text === 'x',
	);
	check('clampedLabel: no eye offset when the build cannot construct a Cartesian3', !('eyeOffset' in label));
	const nudged = M.clampedLabel(makeCesium({ cartesianClass: true }), { text: 'y' });
	check('clampedLabel: nudged toward the camera (eye offset z < 0)', nudged.eyeOffset?.z === -M.LABEL_EYE_OFFSET_M && M.LABEL_EYE_OFFSET_M > 0);

	const dot = M.clampedDot(cesium, { pixelSize: 9, color: cesium.Color.CYAN, outlineColor: cesium.Color.BLACK, outlineWidth: 2, scaleByDistance: 'sbd' });
	check(
		'clampedDot: billboard graphics with an explicit size (pixelSize + 2·rim), clamped, depth test off',
		dot.width === 13 && dot.height === 13 && dot.heightReference === 3 && dot.disableDepthTestDistance === Number.POSITIVE_INFINITY,
		JSON.stringify({ w: dot.width, h: dot.height, r: dot.heightReference }),
	);
	check('clampedDot: no point vocabulary leaks onto the billboard, extra options kept', !('pixelSize' in dot) && !('color' in dot) && dot.scaleByDistance === 'sbd');
	const pulsing = M.clampedDot(cesium, { pixelSize: 10, color: 'orange', pulse: 'pulse-prop' });
	check('clampedDot: a pulse drives the billboard scale', pulsing.scale === 'pulse-prop' && pulsing.width === 10);

	const keyed = makeCesium({ enums: true });
	const kl = M.drapedPolyline(keyed, { positions: [], width: 1, material: null, z: 0 });
	const kd = M.clampedDot(keyed, { pixelSize: 4, color: 'red' });
	check('the global enums win when the build has them', kl.classificationType === 22 && kd.heightReference === 13);

	const veil = M.drapedEllipse(cesium, { radiusM: 45, material: 'veil', z: M.DRAPE_Z.pursuit });
	check(
		'drapedEllipse: a ground fill (no height, no outline), classified BOTH',
		veil.semiMajorAxis === 45 && veil.semiMinorAxis === 45 && veil.fill === true && veil.outline === false && !('height' in veil) && veil.classificationType === 2,
	);
	const zone = M.drapedPolygon(cesium, { positions: [1, 2, 3], material: 'm', z: M.DRAPE_Z.zone });
	check('drapedPolygon: a ground fill (no height / extrusion)', zone.hierarchy.positions.length === 3 && !('height' in zone) && !('extrudedHeight' in zone) && zone.outline === false);

	const ring = M.ringCoords(88.3499, 22.5582, 100, 48);
	const kx = 111_320 * Math.cos((22.5582 * Math.PI) / 180);
	const radii = ring.map(([lon, lat]) => Math.hypot((lon - 88.3499) * kx, (lat - 22.5582) * 111_320));
	check('ringCoords: a closed loop (first vertex repeated last)', ring.length === 49 && ring[0][0] === ring[48][0] && ring[0][1] === ring[48][1]);
	check('ringCoords: every vertex at the radius', radii.every((r) => Math.abs(r - 100) < 0.5), `${Math.min(...radii).toFixed(2)}–${Math.max(...radii).toFixed(2)} m`);
	check('ringCoords: at least 8 segments', M.ringCoords(0, 0, 10, 2).length === 9);
	const dr = M.drapedRing(cesium, { lon: 88.3499, lat: 22.5582, radiusM: 55, width: 2, material: 'c', z: M.DRAPE_Z.dispatch });
	check('drapedRing: a draped closed polyline at ground height', dr.clampToGround === true && dr.positions.length === M.RING_SEGMENTS + 1 && dr.positions.every((p) => p.h === 0));

	// the audit, on plain fakes and on Property-wrapped values
	const prop = (v) => ({ getValue: () => v });
	const v = makeViewer();
	v.entities.add({ id: 'a', polyline: { clampToGround: prop(true) } });
	v.entities.add({ id: 'b', polyline: { clampToGround: false } });
	v.entities.add({ id: 'c', billboard: { heightReference: prop(3), disableDepthTestDistance: prop(Number.POSITIVE_INFINITY) }, label: M.clampedLabel(cesium, {}) });
	v.entities.add({ id: 'd', point: { heightReference: 0, disableDepthTestDistance: Number.POSITIVE_INFINITY } });
	v.entities.add({ id: 'e', ellipse: { height: 4 } });
	v.entities.add({ id: 'f', ellipse: M.drapedEllipse(cesium, { radiusM: 10, material: null, z: 0 }) });
	v.entities.add({ id: 'g', billboard: { heightReference: 3 } }); // clamped but depth-tested: a building can hide it
	v.entities.add({ id: 'h', polygon: { height: 0, extrudedHeight: 140 } });
	const audit = M.drapeAudit(v, ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'missing']);
	check('drapeAudit: draped / clamped / floating read back', audit.draped === 2 && audit.clamped === 1 && audit.floating === 5, JSON.stringify(audit));
}

// ── 2. the pursuit overlay ───────────────────────────────────────────────────

const PLAN = {
	eventId: 'evt-1',
	vehicleId: 'veh-1',
	latestSighting: {
		sightingId: 's-1',
		plate: 'MH47EM9001',
		t: '2026-10-23T05:00:00Z',
		position: [88.3498, 22.5823],
		speedKmh: 40,
		heading: 90,
		source: 'emulated_anpr',
	},
	seedSegmentId: 1015,
	maxCostSec: 600,
	chokes: [
		{ rank: 1, junctionId: 15, junctionType: 'signalized', position: [88.3549, 22.5682], graphCostSec: 120, score: 0.9, signalControl: true },
		{ rank: 2, junctionId: 8, junctionType: 'priority', position: [88.3599, 22.5582], graphCostSec: 200, score: 0.7, signalControl: false },
	],
	note: null,
};
const TRACE = [
	[88.4102, 22.5536],
	[88.3449, 22.5602],
	[88.3498, 22.5823],
];

function overlayOf(cesium, opts = {}) {
	const viewer = makeViewer();
	const overlay = M.createPursuitOverlay(cesium, viewer);
	overlay.show({ plan: PLAN, trace: [], ...opts });
	return { viewer, overlay };
}

{
	const cesium = makeCesium();
	const { viewer, overlay } = overlayOf(cesium);
	const rim = viewer.byId.get('pursuit:ring')?.polyline;
	const veil = viewer.byId.get('pursuit:veil')?.ellipse;
	check('pursuit ring drawn as a draped rim + a ground veil', !!rim && !!veil && rim.clampToGround === true && rim.zIndex === M.DRAPE_Z.pursuit);
	check(
		'pursuit veil is a 15 % fill of the data colour on the ground, never an opaque disc',
		veil.fill === true && veil.outline === false && veil.material?.color?.a === M.PURSUIT_RING_FILL_ALPHA && M.PURSUIT_RING_FILL_ALPHA <= 0.2 && veil.material.color.name === 'CYAN' && veil.semiMajorAxis === M.PURSUIT_RING_RADIUS_M,
		`fill alpha ${veil.material?.color?.a}`,
	);
	check('pursuit rim keeps the full-colour data accent', rim.material?.name === 'CYAN' && rim.material?.a === 1);
	check('pursuit rim grows (a time-varying rim while it does)', rim.positions instanceof cesium.CallbackProperty);
	await sleep(M.PURSUIT_MOTION.ringMs + 120);
	const landed = viewer.byId.get('pursuit:ring')?.polyline?.positions;
	check(
		'pursuit rim lands on constant positions (a dynamic ground line would rebuild every frame)',
		Array.isArray(landed) && landed.length === M.RING_SEGMENTS + 1 && landed.every((p) => p.h === 0),
	);
	overlay.destroy();

	const stale = overlayOf(cesium, {
		detail: {
			eventId: 'evt-1',
			vehicleId: 'veh-1',
			sightingId: 's-1',
			cameraId: 'EM-CAM-03',
			sightingAgeSec: 1800,
			stale: true,
			staleAfterSec: 600,
			seedSegmentId: 1015,
			direction: null,
			chokes: [],
			note: null,
		},
	});
	const sRim = stale.viewer.byId.get('pursuit:ring').polyline;
	const sVeil = stale.viewer.byId.get('pursuit:veil').ellipse;
	check(
		'a STALE sighting ring goes dim (ink) — rim and veil',
		sRim.material?.name === 'LIGHTGRAY' && sVeil.material?.color?.name === 'LIGHTGRAY' && sVeil.material.color.a === M.PURSUIT_RING_FILL_ALPHA,
	);
	check('a STALE sighting draws no future arc', !stale.viewer.byId.has('pursuit:future'));
	stale.overlay.destroy();

	const bare = overlayOf(makeCesium({ withAlpha: false, transparent: false }));
	check('no veil colour on the build → the rim alone (no fill entity)', !bare.viewer.byId.has('pursuit:veil') && bare.viewer.byId.get('pursuit:ring')?.polyline?.clampToGround === true);
	bare.overlay.destroy();
	const clear = overlayOf(makeCesium({ withAlpha: false, transparent: true }));
	check('no withAlpha → a transparent veil, never the opaque data colour', clear.viewer.byId.get('pursuit:veil')?.ellipse?.material?.color?.a === 0);
	clear.overlay.destroy();
}

{
	// the whole cinematic: trace, comet, chokes, fan, arc — draped or clamped
	const cesium = makeCesium();
	const segments = new Map([[1016, { segmentId: 1016, roadName: 'Strand Road', coordinates: [[88.3498, 22.5823], [88.3549, 22.5652]] }]]);
	const detail = {
		eventId: 'evt-1',
		vehicleId: 'veh-1',
		sightingId: 's-1',
		cameraId: 'EM-CAM-03',
		sightingAgeSec: 30,
		stale: false,
		staleAfterSec: 600,
		seedSegmentId: 1015,
		direction: { basis: 'heading', againstOneway: false, onwardSegmentIds: [1016], towardsJunctionIds: [15] },
		chokes: [{ junctionId: 15, name: 'Sea Link, Worli end', likelyPassed: false }],
		note: null,
	};
	const { viewer, overlay } = overlayOf(cesium, { trace: TRACE, detail, segments });
	await sleep(M.PURSUIT_MOTION.chokeStaggerMs * 3);
	const sight = viewer.byId.get('pursuit:sight');
	check('sighting: a clamped dot (billboard) + a clamped label, no point', !!sight?.billboard && !sight.point && sight.billboard.heightReference === 3 && sight.label.heightReference === 3);
	const trace = viewer.byId.get('pursuit:trace')?.polyline;
	check('trace: draped on top of the ground order, drawn head-first', trace?.clampToGround === true && trace.zIndex === M.DRAPE_Z.pursuit && trace.positions instanceof cesium.CallbackProperty);
	check('trace: in the act colour (a Color handed to the material, never an options object)', trace.material?.color?.name === 'ORANGE', String(trace.material?.color?.name));
	const arc = viewer.byId.get('pursuit:future')?.polyline;
	check(
		'future arc: draped, marching through a time-varying dash length INSIDE the material',
		arc?.clampToGround === true && arc.material?.dashed === true && arc.material.dashLength instanceof cesium.CallbackProperty,
	);
	const march = arc.material.dashLength.fn();
	check('the march stays within 18–28 px (never a blink)', march >= 18 && march <= 28, march.toFixed(1));
	check('onward fan: draped dashes', viewer.byId.get('pursuit:onward-1016')?.polyline?.clampToGround === true);
	check('chokes: clamped dots + labels', ['pursuit:choke-15', 'pursuit:choke-8'].every((id) => viewer.byId.get(id)?.billboard?.heightReference === 3 && !viewer.byId.get(id)?.point));
	const comet = viewer.byId.get('pursuit:comet');
	check('comet: a clamped dot riding the tip', comet?.billboard?.heightReference === 3);
	await sleep(M.PURSUIT_MOTION.traceDrawMs + 120);
	const settled = viewer.byId.get('pursuit:trace')?.polyline?.positions;
	check('trace: constant positions once the head-first draw is done (whole trace)', Array.isArray(settled) && settled.length === TRACE.length);
	check('comet gone after its ride', !viewer.byId.has('pursuit:comet'));
	const ids = [...viewer.byId.keys()];
	const audit = M.drapeAudit(viewer, ids);
	check('every pursuit graphic is draped or clamped (floating 0)', audit.floating === 0 && audit.draped + audit.clamped === ids.length, JSON.stringify(audit));
	const own = overlay.audit();
	check(
		"the overlay's own audit (the canvas publishes it as layerStats.pursuit) matches, over exactly its entities",
		own.floating === 0 && own.draped === audit.draped && own.clamped === audit.clamped && own.draped + own.clamped === overlay.count(),
		JSON.stringify({ own, count: overlay.count() }),
	);
	overlay.destroy();
	check('destroy clears the overlay', viewer.byId.size === 0);
}

// ── 3. the traffic-flow layer ────────────────────────────────────────────────

const NOW = Date.now();
const line = (lon) => [
	[lon, 22.5582],
	[lon + 0.01, 22.5582],
];
M.godsEye.segments.push(
	{ segmentId: 1005, roadName: 'Strand Road', roadClass: 'primary', coordinates: line(88.3499), geometryBasis: 'schematic' },
	{ segmentId: 1015, roadName: null, roadClass: 'trunk', coordinates: line(88.3399), geometryBasis: 'osm_display' },
	{ segmentId: 1006, roadName: 'Bandra–Worli Sea Link', roadClass: 'primary', coordinates: line(88.3299), geometryBasis: 'osm_display' },
);

const liveRow = (sid, speed, cong, ageSec = 5) => ({
	segment_id: sid,
	speed_kmh: speed,
	congestion_idx: cong,
	timestamp_ms: NOW - ageSec * 1000,
	source: 'signal-ingress',
	data_quality: 'synthetic',
	origin: 'live',
	road_name: null,
});
const emuRow = (sid, speed, cong, ageSec = 5, road = null) => ({
	segment_id: sid,
	speed_kmh: speed,
	congestion_idx: cong,
	timestamp_ms: NOW - ageSec * 1000,
	source: 'event-emulator',
	data_quality: 'synthetic',
	origin: 'emulated',
	emulated: true,
	road_name: road,
});

async function flowWith(body) {
	globalThis.fetch = async () => ({ ok: true, json: async () => body });
	const viewer = makeViewer();
	const layer = M.trafficFlowLayer.create();
	layer.init({ cesium: makeCesium(), viewer, fetchJson: async () => ({}), notify() {} });
	layer.activate();
	for (let i = 0; i < 5; i++) await tick(); // the first poll lands
	layer.refresh(); // redraw over the landed rows
	const stats = layer.coverageStats();
	const cards = Object.fromEntries([...viewer.byId.entries()].map(([id, e]) => [id, e.description ?? '']));
	const lines = Object.fromEntries([...viewer.byId.entries()].map(([id, e]) => [id, e.polyline]));
	layer.deactivate();
	for (let i = 0; i < 5; i++) await tick();
	return { stats, cards, lines };
}

{
	// before C-P (no emulated plane): exactly the ingest picture
	const { stats, cards } = await flowWith({ observations: [liveRow(1005, 41, 0.35), liveRow(1006, 30, 0.5)] });
	check('no emulated plane: ingest rows colour their segments', stats.detail.coloured === 2 && stats.detail.emulated === 0, JSON.stringify(stats.detail));
	check('no emulated plane: no EMULATED tag anywhere', !/EMULATED/.test(stats.hint) && !Object.values(cards).some((c) => /EMULATED/.test(c)), stats.hint);
}

{
	const { stats, cards, lines } = await flowWith({
		observations: [liveRow(1005, 41, 0.35), liveRow(1006, 30, 0.5)],
		emulated_observations: [emuRow(1005, 8, 0.92), emuRow(1015, 12, 0.85, 5, 'Queensway - Cathedral Road'), emuRow(1006, 20, 0.7, 900)],
	});
	const c1005 = cards['seg:1005'];
	check('a fresh showcase row colours its segment (1005 at 92 %)', /8\.0 km\/h · congestion 92%/.test(c1005), c1005.slice(0, 120));
	// the label policy retires stacked status words (SPEC §10.2): the legacy card still names the
	// emulated run and the simulated feed (legacy invariance), matched as facts, not as a word stack
	check('…named as an emulated run on a simulated feed, the ingest reading beside it', /emulated/i.test(c1005) && /simulated feed/i.test(c1005) && /ingest plane: 41\.0 km\/h, 35%/.test(c1005), c1005.slice(0, 220));
	check(
		'a showcase row on a segment the ingest plane has nothing for still draws (1015)',
		/12\.0 km\/h · congestion 85%/.test(cards['seg:1015']) && !/ingest plane/.test(cards['seg:1015']),
	);
	check("road_name names a segment the segment feed left unnamed", cards['seg:1015'].startsWith('Queensway - Cathedral Road'), cards['seg:1015'].slice(0, 60));
	check(
		'a stale showcase row hands the segment back to the ingest plane (1006)',
		/30\.0 km\/h · congestion 50%/.test(cards['seg:1006']) && !/EMULATED/.test(cards['seg:1006']),
		cards['seg:1006'].slice(0, 140),
	);
	check('hint + detail count the EMULATED rows', stats.detail.emulated === 2 && / · 2 EMULATED/.test(stats.hint) && stats.detail.coloured === 3, `${stats.hint} · ${JSON.stringify(stats.detail)}`);
	check('every coloured row reads SIMULATED (the chip SIM tag)', stats.detail.simulated === 3);
	check('the geometry basis counts survive in the hint', stats.hint.includes('2 OSM-traced · 1 schematic (dashed)'), stats.hint);

	// draping (WP-22)
	const all = Object.values(lines);
	check(
		'every segment is DRAPED at the bottom of the ground order',
		all.length === 3 && all.every((l) => l.clampToGround === true && l.classificationType === 2 && l.zIndex === M.DRAPE_Z.flow),
	);
	check('…on ground positions (the surface supplies the height)', all.every((l) => l.positions.every((p) => p.h === 0)));
	check('only the SCHEMATIC chord is dashed (its gaps carry the casing)', lines['seg:1005'].material?.dashed === true && !!lines['seg:1005'].material.gapColor);
	check(
		'OSM geometry is SOLID: a coloured road wears the dark casing, never dashes',
		lines['seg:1006'].material?.outlined === true && lines['seg:1015'].material?.outlined === true && !lines['seg:1006'].material.dashed,
	);
	check('coloured width readable from the overview (≥ 5 px)', lines['seg:1006'].width === M.FLOW_WIDTH.coloured && M.FLOW_WIDTH.coloured >= 5);
	check('the layer reports every segment draped, none floating', stats.detail.draped === 3 && stats.detail.floating === 0, JSON.stringify(stats.detail));
}

{
	// WP-20 serves geometry_basis 'osm' (real routing geometry): solid, never dashed
	M.godsEye.segments.push({ segmentId: 1041, roadName: 'VIP Road (Kazi Nazrul Islam Avenue)', roadClass: 'primary', coordinates: line(88.3199), geometryBasis: 'osm' });
	const { lines, stats } = await flowWith({ observations: [liveRow(1041, 33, 0.3)] });
	check("geometry_basis 'osm' renders solid (casing outline, not dashes)", lines['seg:1041'].material?.outlined === true && !lines['seg:1041'].material.dashed);
	check('a NO DATA segment is a neutral draped hairline', lines['seg:1006'].clampToGround === true && lines['seg:1006'].width === M.FLOW_WIDTH.noData && !lines['seg:1006'].material?.dashed);
	check("'osm' counts as OSM-traced in the hint", stats.hint.includes('3 OSM-traced · 1 schematic (dashed)'), stats.hint);
	M.godsEye.segments.pop();
}

{
	// only the emulated plane answers: the layer is fed, not 'empty'
	const { stats } = await flowWith({ observations: [], emulated_observations: [emuRow(1005, 8, 0.92)] });
	check('an emulated-only answer is a fed layer, not an empty feed', stats.error === null && /1\/3 segments on the congestion ramp/.test(stats.hint), stats.hint);
}

// ── 4. cameras + the signal network ──────────────────────────────────────────

{
	M.godsEye.cameras.push(
		{ cameraId: 'EM-CAM-01', label: 'Sea Link, Worli end', lon: 88.3499, lat: 22.5582, kind: 'anpr', source: 'emulated', junctionId: 15, reads15m: 3, hits15m: 1, lastReadT: NOW, status: null },
		{ cameraId: 'EM-CAM-02', label: null, lon: 88.3499, lat: 22.5582, kind: 'cctv', source: 'emulated', junctionId: 15, reads15m: 0, hits15m: 0, lastReadT: null, status: null },
	);
	M.godsEye.signals.push(
		{ junctionId: 15, name: 'Sea Link, Worli end', lon: 88.3499, lat: 22.5592, phaseIndex: 1, phaseLost: false, greenSec: 30, cycleSec: 90, activePhase: 'NS', phaseMovements: ['NS'], movementStates: { NS: 'green' }, remainingSec: 12, offsetSec: 0, greenRatio: 0.33, source: 'osm_assumed' },
		{ junctionId: 16, name: null, lon: 88.3599, lat: 22.5682, phaseIndex: null, phaseLost: false, greenSec: null, cycleSec: null, activePhase: null, phaseMovements: [], movementStates: {}, remainingSec: null, offsetSec: null, greenRatio: null, source: null },
	);
	for (const layer of [M.camerasLayer, M.signalNetworkLayer]) {
		const viewer = makeViewer();
		const inst = layer.create();
		inst.init({ cesium: makeCesium(), viewer, fetchJson: async () => ({}), notify() {} });
		inst.activate();
		const ents = [...viewer.byId.values()];
		check(`${layer.id}: every marker is clamped billboard graphics (no entity carries a point)`, ents.length > 0 && ents.every((e) => !e.point && e.billboard?.heightReference === 3), `${ents.length} entities`);
		const stats = inst.coverageStats();
		check(`${layer.id}: drape audit floating 0`, stats.detail.floating === 0 && stats.detail.clamped === ents.length, JSON.stringify(stats.detail));
		inst.deactivate();
	}
	const viewer = makeViewer();
	const cams = M.camerasLayer.create();
	cams.init({ cesium: makeCesium(), viewer, fetchJson: async () => ({}), notify() {} });
	cams.activate();
	const hot = viewer.byId.get('cam:EM-CAM-01')?.billboard;
	check('a camera with watchlist hits pulses through the billboard scale (peak-size dot)', hot?.scale instanceof Object && typeof hot.scale.fn === 'function' && hot.scale.fn() <= 1 && hot.width >= 14);
	cams.deactivate();
}

// ── 5. overlay labels: the plate, the anomaly words, the site lines ─────────
{
	const cesium = makeCesium();
	const plate = M.labelPlate(cesium);
	check('label plate: showBackground with a canvas-colour background and padding', plate.showBackground === true && plate.backgroundColor instanceof cesium.Color && plate.backgroundPadding?.x === 4 && plate.backgroundPadding?.y === 2, JSON.stringify(plate));
	check('label plate opacity is the overlay labels\' one (0.72)', M.LABEL_PLATE_ALPHA === 0.72);
	check("anomaly: 'speed_jump' ×6 reads 'Speed jump ×6' (never the wire id)", M.anomalyLabel('speed_jump', 6) === 'Speed jump ×6', M.anomalyLabel('speed_jump', 6));
	check("anomaly: 'congestion_outlier' once reads 'Congestion outlier'", M.anomalyLabel('congestion_outlier', 1) === 'Congestion outlier');
	const vocab = M.ANOMALY_TYPES.map((t) => [t, M.anomalyWord(t, 'en'), M.anomalyWord(t, 'hi'), M.anomalyWord(t, 'mr')]);
	const raw = vocab.filter(([, ...words]) => words.some((w) => /_/.test(w) || !w));
	check('anomaly: every C-H type has a human word in en, hi and mr (no snake_case)', raw.length === 0, raw.map((r) => r[0]).join(', ') || `${vocab.length} types × 3`);
	check('anomaly: hi / mr words differ from en (localised, not copied)', vocab.every(([, en, hi, mr]) => hi !== en && mr !== en && hi !== mr));
	check("anomaly: an unknown id is humanised ('some_new_flag' → 'Some new flag')", M.anomalyWord('some_new_flag', 'hi') === 'Some new flag' && M.anomalyWord(null) === 'Feed anomaly');
	// the label policy retires stacked status words (SPEC §10.2): the fold is checked on readings
	const folded = M.collapseLines(['Stolen-vehicle sighting', 'Stolen-vehicle sighting', 'Speeding +55 km/h']);
	check('site lines: identical lines fold into one with a count, first occurrence first', folded.length === 2 && folded[0].count === 2 && folded[1].count === 1 && folded[1].line.startsWith('Speeding'), JSON.stringify(folded));
	check(
		"site label: 'Stolen-vehicle sighting ×2' once, never the same line twice",
		M.siteLabelText(['Stolen-vehicle sighting', 'Stolen-vehicle sighting'], 3) === 'Stolen-vehicle sighting ×2',
		JSON.stringify(M.siteLabelText(['Stolen-vehicle sighting', 'Stolen-vehicle sighting'], 3)),
	);
	const many = M.siteLabelText(['A', 'B', 'B', 'C', 'D', 'D', 'E'], 3);
	check("site label: at most 3 distinct lines, '+n more' counts the readings left over", many === 'A\nB ×2\nC\n+3 more', JSON.stringify(many));
	check('site label: a single reading reads as itself', M.siteLabelText(['Red-light violation'], 3) === 'Red-light violation');
}

// ── 6. the map's v2 rules: clustering, label placement, the view's opacities ──

/** A small deterministic PRNG (mulberry32) for the clustering cross-check. */
function mulberry(seed) {
	let a = seed >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) >>> 0;
		let t = a;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

/** The pairwise reference: lead order, first cluster whose lead is strictly within r. */
function referenceClusters(points, r) {
	const order = (a, b) => Number(!!b.lead) - Number(!!a.lead) || (b.weight ?? 0) - (a.weight ?? 0) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
	const out = [];
	for (const p of [...points].sort(order)) {
		const hit = out.find((c) => Math.hypot(c.x - p.x, c.y - p.y) < r);
		if (hit) hit.members.push(p.id);
		else out.push({ lead: p.id, members: [p.id], x: p.x, y: p.y });
	}
	return out;
}

{
	const { clusterMarkers, spiderOffsets, CLUSTER_RADIUS_PX, CLUSTER_GRID_ABOVE } = M.CL;
	check('clustering: the merge distance is 22 px (SPEC §5.3)', CLUSTER_RADIUS_PX === 22);
	const two = clusterMarkers([
		{ id: 'a', x: 100, y: 100 },
		{ id: 'b', x: 121, y: 100 },
	]);
	check('clustering: markers 21 px apart merge into one disc', two.length === 1 && two[0].members.length === 2, JSON.stringify(two));
	const apart = clusterMarkers([
		{ id: 'a', x: 100, y: 100 },
		{ id: 'b', x: 122, y: 100 },
	]);
	check('clustering: markers 22 px apart stay apart (strictly under the radius)', apart.length === 2);
	const led = clusterMarkers([
		{ id: 'a', x: 100, y: 100 },
		{ id: 'b', x: 105, y: 100, lead: true },
		{ id: 'c', x: 95, y: 104, weight: 5 },
	]);
	check("clustering: the member on the selection's track leads (drawn where it is)", led.length === 1 && led[0].lead === 'b' && led[0].x === 105 && led[0].members[0] === 'b', JSON.stringify(led));
	const weighted = clusterMarkers([
		{ id: 'a', x: 0, y: 0 },
		{ id: 'z', x: 3, y: 0, weight: 2 },
	]);
	check('clustering: else the heavier (a waiting decision) leads, then the id', weighted[0].lead === 'z');
	check('clustering: a non-finite position is left out', clusterMarkers([{ id: 'n', x: Number.NaN, y: 0 }, { id: 'm', x: 0, y: 0 }]).length === 1);
	const rnd = mulberry(7);
	const pts = Array.from({ length: 180 }, (_, i) => ({
		id: `p${String(i).padStart(3, '0')}`,
		x: Math.round(rnd() * 900),
		y: Math.round(rnd() * 500),
		lead: i % 37 === 0,
		weight: i % 5 === 0 ? 1 : 0,
	}));
	const ref = referenceClusters(pts, 22);
	const got = clusterMarkers(pts, 22);
	check(`clustering: grid-bucketed above ${CLUSTER_GRID_ABOVE} markers gives the pairwise answer`, JSON.stringify(got) === JSON.stringify(ref), `${got.length} clusters of 180 markers`);
	const sp = spiderOffsets(6);
	const chord = Math.min(...sp.map((p, i) => Math.hypot(p.x - sp[(i + 1) % 6].x, p.y - sp[(i + 1) % 6].y)));
	check("spiderfy: members fan ≥ 26 px apart, the first at 12 o'clock", sp.length === 6 && chord >= 25.9 && sp[0].x === 0 && sp[0].y < 0, `chord ${chord.toFixed(1)} px`);

	// a pursuit's choke squares are cluster ANCHORS: what sits at the junction joins them (review r1)
	const { clusterAround } = M.CL;
	const keep = (p) => !!p.lead || (p.weight ?? 0) >= 2;
	const around = clusterAround(
		[
			{ id: 'choke-1', x: 100, y: 100 },
			{ id: 'choke-2', x: 112, y: 100 },
		],
		[
			{ id: 'cam-a', x: 103, y: 101 },
			{ id: 'cam-b', x: 113, y: 99, weight: 0 },
			{ id: 'cam-rel', x: 99, y: 100, lead: true },
			{ id: 'rec-dec', x: 101, y: 98, weight: 2 },
			{ id: 'cam-far', x: 300, y: 300 },
			{ id: 'cam-far2', x: 305, y: 300 },
		],
		22,
		keep,
	);
	const byLead = Object.fromEntries(around.map((c) => [c.lead, c.members]));
	check(
		'choke anchors: a camera at the junction joins the NEAREST choke, which leads (the square drawn on top, the camera behind its count chip)',
		JSON.stringify(byLead['choke-1']) === JSON.stringify(['choke-1', 'cam-a']) && JSON.stringify(byLead['choke-2']) === JSON.stringify(['choke-2', 'cam-b']),
		JSON.stringify(byLead),
	);
	check('choke anchors: two chokes never merge, even 12 px apart', around.filter((c) => c.lead.startsWith('choke-')).length === 2 && !around.some((c) => c.members.filter((m) => m.startsWith('choke-')).length > 1));
	const keptOut = around.find((c) => c.members.includes('cam-rel'));
	check(
		"choke anchors: the selection's marker and one with a waiting decision are never absorbed (they cluster as usual, the selection's leading)",
		keptOut?.lead === 'cam-rel' && keptOut.members.includes('rec-dec') && !byLead['choke-1'].includes('rec-dec'),
		JSON.stringify(keptOut),
	);
	check('choke anchors: the rest cluster as clusterMarkers does', JSON.stringify(byLead['cam-far']) === JSON.stringify(['cam-far', 'cam-far2']));
	check('choke anchors: without anchors it IS clusterMarkers', JSON.stringify(clusterAround([], pts, 22)) === JSON.stringify(got));
}

{
	const { placeLabels, discBox, boxesOverlap, LABEL_POSITIONS, LABEL_MAX } = M.LP;
	check('labels: eight candidate positions, right of the marker first', LABEL_POSITIONS.length === 8 && LABEL_POSITIONS[0] === 'r');
	const view = { width: 400, height: 300 };
	const one = placeLabels([{ id: 'a', x: 100, y: 100, w: 60, h: 20, r: 10 }], [], view);
	check('labels: a free label takes the first candidate, clear of its disc', one.placed.get('a')?.pos === 'r' && one.placed.get('a').box.x >= 114, JSON.stringify([...one.placed.values()]));
	const blocked = placeLabels([{ id: 'a', x: 100, y: 100, w: 60, h: 20, r: 10 }], [{ x: 112, y: 85, w: 80, h: 30 }], view);
	check('labels: an occupied box (a disc, a label) moves it to the next candidate', blocked.placed.get('a')?.pos === 'l', blocked.placed.get('a')?.pos);
	const boxed = placeLabels([{ id: 'a', x: 100, y: 100, w: 60, h: 20, r: 10 }], [{ x: 0, y: 0, w: 400, h: 300 }], view);
	check('labels: a label that fits nowhere is dropped (the canvas shows it on hover)', boxed.placed.size === 0 && boxed.dropped[0] === 'a');
	const pair = placeLabels(
		[
			{ id: 'low', x: 100, y: 100, w: 60, h: 20, r: 10, priority: 1 },
			{ id: 'high', x: 100, y: 100, w: 60, h: 20, r: 10, priority: 9 },
		],
		[],
		view,
	);
	check('labels: the higher priority places first, the next avoids it', pair.placed.get('high')?.pos === 'r' && pair.placed.get('low')?.pos === 'l' && !boxesOverlap(pair.placed.get('high').box, pair.placed.get('low').box));
	const edge = placeLabels([{ id: 'e', x: 395, y: 150, w: 60, h: 20, r: 10 }], [], view);
	check('labels: never outside the view (an edge marker labels inward)', edge.placed.get('e')?.pos === 'l', edge.placed.get('e')?.pos);
	const crowd = Array.from({ length: 130 }, (_, i) => ({ id: `c${i}`, x: (i % 13) * 30, y: Math.floor(i / 13) * 30, w: 20, h: 10 }));
	const capped = placeLabels(crowd, [], { width: 10_000, height: 10_000 });
	check(`labels: at most ${LABEL_MAX} per pass (SPEC §13.5)`, capped.placed.size <= LABEL_MAX && capped.placed.size + capped.dropped.length === 130, `${capped.placed.size} placed`);
	const read = placeLabels([{ id: 'p', x: 100, y: 100, w: 40, h: 20, r: 3, prefer: ['br', 'bl'] }], [], view);
	check('labels: a read label takes its own candidate order (below right first)', read.placed.get('p')?.pos === 'br');
	check('labels: a disc keeps out its square', JSON.stringify(discBox(10, 20, 5)) === JSON.stringify({ x: 5, y: 15, w: 10, h: 10 }));
}

{
	const { markerStyle, emptyView, MAP_OPACITY, flowDim, inWindow } = M.V;
	const base = emptyView('v2');
	const view = (over) => ({ ...base, ...over });
	const W = [1_000, 2_000];
	const w = view({ window: W, protected: new Set(['vehicle:P']) });
	check('window: a time-bearing object outside it fades to 30 %', markerStyle({ urn: 'anomaly:1', kind: 'anomaly', t: 5_000 }, w).alpha === 0.3 && MAP_OPACITY.outsideWindow === 0.3);
	check('window: inside it, full strength', markerStyle({ urn: 'anomaly:2', kind: 'anomaly', t: 1_500 }, w).alpha === 1);
	check('window: a PROTECTED object never fades', markerStyle({ urn: 'vehicle:P', kind: 'vehicle', t: 5_000 }, w).alpha === 1);
	check('window: infrastructure (cameras, junctions, roads) never fades', ['camera', 'junction', 'segment'].every((k) => markerStyle({ urn: `${k}:9`, kind: k, t: 5_000 }, w).alpha === 1));
	check('window: an object with no time of its own is never outside it', markerStyle({ urn: 'unit:1', kind: 'unit', t: null }, w).alpha === 1 && inWindow(null, W));
	const s = view({ selection: 'vehicle:V', items: ['vehicle:V'], related: new Set(['camera:R']) });
	check('selection: the selection and its links keep full strength', markerStyle({ urn: 'vehicle:V', kind: 'vehicle' }, s).alpha === 1 && markerStyle({ urn: 'camera:R', kind: 'camera' }, s).alpha === 1);
	check('selection: unrelated cameras step back to 50 %', markerStyle({ urn: 'camera:X', kind: 'camera' }, s).alpha === 0.5);
	check('selection: unrelated infrastructure to 30 %', ['junction', 'anomaly'].every((k) => markerStyle({ urn: `${k}:X`, kind: k }, s).alpha === 0.3));
	check('selection: the flow layer to 60 % and 0.5 px thinner', JSON.stringify(flowDim(s)) === JSON.stringify({ alpha: 0.6, thinPx: 0.5 }) && flowDim(base).alpha === 1 && flowDim(base).thinPx === 0);
	const marked = markerStyle({ urn: 'vehicle:V', kind: 'vehicle' }, view({ selection: 'vehicle:V', items: ['vehicle:V'], decisions: new Set(['vehicle:V']) }));
	check('selection: the selected object is marked, its waiting decision too', marked.selected && marked.decision);
	const k = view({ kinds: new Set(['camera']), protected: new Set(['vehicle:P']) });
	check('kind filter: other kinds hide, protected ones too (the page warns)', !markerStyle({ urn: 'vehicle:P', kind: 'vehicle' }, k).show && markerStyle({ urn: 'camera:1', kind: 'camera' }, k).show);
	const { kindShown, kindsSignature } = M.V;
	check(
		'kind filter: kindShown answers for markers and lines alike; no filter shows every kind; the signature is order-free',
		kindShown(k, 'camera') &&
			!kindShown(k, 'segment') &&
			kindShown(base, 'segment') &&
			JSON.stringify(kindsSignature(view({ kinds: new Set(['vehicle', 'camera']) }))) === JSON.stringify(['camera', 'vehicle']) &&
			kindsSignature(base) === null,
	);
	const both = markerStyle({ urn: 'anomaly:3', kind: 'anomaly', t: 5_000 }, view({ window: W, selection: 'vehicle:V', items: ['vehicle:V'] }));
	check('window and selection compose (the lower opacity wins)', both.alpha === 0.3);
}

// ── 7. the share link passes the workspace's keys through (R24) ─────────────

{
	const { buildShareHash, parseShareHash, shareHashExtras, EXTRA_VALUE_MAX, EXTRA_MAX } = M.SL;
	const ids = ['events', 'flow'];
	const cam = { lat: 22.5582, lon: 88.3499, alt: 2000, heading: 20, pitch: -40, roll: 0, style: 'raw', bhot: false, layers: ['flow'] };
	const hash = buildShareHash({ ...cam, selected: 'vehicle:abc-1', extra: { view: 'split', t0: '1700000000000', f: 'eyJraW5kIjpbXX0' } }, ids);
	const p = new URLSearchParams(hash);
	check('share link: the camera, layers and sel keys as before', p.get('v') === '2' && p.get('layers') === 'flow' && p.get('sel') === 'vehicle:abc-1' && p.get('style') === 'raw', hash);
	check("share link: keys it does not own pass through (the workspace's view, t0, f)", p.get('view') === 'split' && p.get('t0') === '1700000000000' && p.get('f') === 'eyJraW5kIjpbXX0');
	const keys = [...p.keys()];
	check('share link: its own keys first, then the passed-through ones', keys.indexOf('sel') < keys.indexOf('view'));
	const parsed = parseShareHash(`#${hash}`, ids);
	check('share link: the parser preserves the keys it does not know', parsed?.extra?.view === 'split' && parsed.extra.t0 === '1700000000000' && parsed.extra.f === 'eyJraW5kIjpbXX0' && !('lat' in parsed.extra));
	const round = new URLSearchParams(buildShareHash(parsed, ids));
	check('share link: parse → build round-trips the foreign keys', round.get('view') === 'split' && round.get('f') === 'eyJraW5kIjpbXX0' && round.get('sel') === 'vehicle:abc-1');
	check('share link: a workspace-only hash keeps its keys (no camera hash)', JSON.stringify(shareHashExtras('#view=table&dock=left')) === JSON.stringify({ view: 'table', dock: 'left' }) && parseShareHash('#view=table', ids) === null);
	const inherited = shareHashExtras('#constructor=a&toString=b&hasOwnProperty=c&valueOf=d');
	check(
		"share link: a key named like an Object.prototype member ('constructor', 'toString') passes through like any other",
		JSON.stringify(inherited) === JSON.stringify({ constructor: 'a', toString: 'b', hasOwnProperty: 'c', valueOf: 'd' }),
		JSON.stringify(inherited),
	);
	const roundInherited = new URLSearchParams(buildShareHash(parseShareHash(`#${buildShareHash({ ...cam, extra: inherited }, ids)}`, ids), ids));
	check('share link: … and round-trips', roundInherited.get('constructor') === 'a' && roundInherited.get('toString') === 'b');
	const hostile = shareHashExtras(`#lat=1&evil key=1&__proto__=x&ok=1&long=${'x'.repeat(EXTRA_VALUE_MAX + 1)}&%3Cscript%3E=1`);
	check('share link: hostile keys, over-long values and its own keys never pass through', JSON.stringify(Object.keys(hostile)) === JSON.stringify(['ok']), JSON.stringify(Object.keys(hostile)));
	const many = shareHashExtras(`#${Array.from({ length: EXTRA_MAX + 5 }, (_, i) => `k${i}=v`).join('&')}`);
	check(`share link: at most ${EXTRA_MAX} keys pass through`, Object.keys(many).length === EXTRA_MAX);
	const override = new URLSearchParams(buildShareHash({ ...cam, extra: { lat: '0', sel: 'vehicle:evil', layers: 'x' } }, ids));
	check('share link: an extra never overrides a key the link owns', override.get('lat') === '22.5582' && override.get('sel') === null && override.get('layers') === 'flow');
	check('share link: the hostile camera guards stay', parseShareHash('#v=2&lat=Infinity&lon=72', ids) === null && parseShareHash('#v=2&lat=95&lon=72', ids) === null);
}

// ── 8. the registry: required ids, unique prefixes, groups, reserved ids ────

{
	const { GODS_EYE_LAYERS } = M.IDX;
	const { validateLayers, LAYER_GROUPS, RESERVED_LAYERS } = M.REG;
	const REQUIRED_IDS = ['events', 'flow', 'traces', 'enforcement', 'signals', 'units', 'dispatch', 'convoy', 'cameras', 'anomalies', 'photoreal-3d'];
	const ids = GODS_EYE_LAYERS.map((l) => l.id);
	check('registry: every required layer id is registered (presence, never an exact count — X7/X14)', REQUIRED_IDS.every((id) => ids.includes(id)), ids.join(', '));
	const prefixes = GODS_EYE_LAYERS.map((l) => l.pickPrefix);
	const overlap = prefixes.filter((a, i) => prefixes.some((b, j) => i !== j && (a.startsWith(b) || b.startsWith(a))));
	check('registry: the pick prefixes are unique (none a prefix of another)', overlap.length === 0, prefixes.join(' '));
	check('registry: every layer sits in a LayerTree group, in the frozen order', GODS_EYE_LAYERS.every((l) => LAYER_GROUPS.includes(l.group)) && LAYER_GROUPS.join() === 'traffic,enforcement,response,corridors,intelligence');
	check('registry: the photoreal city is the base map (the Photoreal option), not a row', GODS_EYE_LAYERS.find((l) => l.id === 'photoreal-3d')?.basemap === true && GODS_EYE_LAYERS.filter((l) => l.basemap).length === 1);
	check(
		'registry: the OS-DECK-A layers sit in the intelligence group under their reserved prefixes',
		ids.includes('osint') &&
			ids.includes('places') &&
			GODS_EYE_LAYERS.find((l) => l.id === 'osint')?.pickPrefix === 'osint:' &&
			GODS_EYE_LAYERS.find((l) => l.id === 'osint')?.group === 'intelligence' &&
			GODS_EYE_LAYERS.find((l) => l.id === 'places')?.pickPrefix === 'place:' &&
			GODS_EYE_LAYERS.find((l) => l.id === 'places')?.group === 'intelligence' &&
			GODS_EYE_LAYERS.find((l) => l.id === 'places')?.defaultOn === false,
		ids.join(', '),
	);
	const layer = (id, pickPrefix, group = 'intelligence') => ({ id, name: id, label: id, requiresKeyId: null, pickPrefix, defaultOn: true, group, create: () => ({}) });
	const throws = (fn) => {
		try {
			fn();
			return false;
		} catch {
			return true;
		}
	};
	check('validateLayers: the osint and places layers may take their prefixes', !throws(() => validateLayers([layer('osint', 'osint:'), layer('places', 'place:')])));
	check('validateLayers: no other layer takes a reserved prefix, and the reserved ids keep theirs', throws(() => validateLayers([layer('news', 'osint:')])) && throws(() => validateLayers([layer('osint', 'osi:')])) && throws(() => validateLayers([layer('pins', 'place:x:')])));
	check('validateLayers: a layer without a valid group is refused', throws(() => validateLayers([layer('x', 'x:', 'nowhere')])) && throws(() => validateLayers([{ ...layer('y', 'y:'), group: undefined }])));
}

// ── 9. the NEUTRAL flow ramp under chrome v2 ───────────────────────────────

const TOKENS = M.TOK.TOKENS.command;
const cssOfColor = (c) => c?.css ?? null;

async function flowV2(body, view) {
	globalThis.fetch = async () => ({ ok: true, json: async () => body });
	const viewer = makeViewer();
	const layer = M.trafficFlowLayer.create();
	layer.init({ cesium: makeCesium(), viewer, fetchJson: async () => ({}), notify() {}, chrome: 'v2', view: () => view });
	layer.activate();
	for (let i = 0; i < 5; i++) await tick();
	layer.refresh();
	const lines = Object.fromEntries([...viewer.byId.entries()].map(([id, e]) => [id, e.polyline]));
	const cards = Object.fromEntries([...viewer.byId.entries()].map(([id, e]) => [id, e.description ?? '']));
	layer.deactivate();
	for (let i = 0; i < 5; i++) await tick();
	return { lines, cards };
}

{
	const free = M.TOK.flowStyle(1);
	const mid = M.TOK.flowStyle(3);
	const jam = M.TOK.flowStyle(5);
	const live = M.V.emptyView('v2');
	const { lines, cards } = await flowV2({ observations: [liveRow(1005, 50, 0.1), liveRow(1006, 8, 0.95), liveRow(1015, 20, 0.5)] }, live);
	// live map (29 Oct): a road's congestion reads in the band ladder — green free, amber slow, red jammed — and in width
	const band = (k) => TOKENS[k].toLowerCase();
	const j = lines['seg:1006'];
	check(
		'v2 flow: a jammed road comes forward — stop 5 width (≥ 3 px) + the dark casing, --v-band-red opaque',
		j?.material?.outlined === true && j.width === Math.max(3, jam.width) + 2.5 && j.material.outlineWidth === 2.5 && cssOfColor(j.material.color) === M.SYM.inkAlpha(band('--v-band-red'), 1),
		JSON.stringify({ w: j?.width, c: cssOfColor(j?.material?.color), o: j?.material?.outlineWidth }),
	);
	const m = lines['seg:1015'];
	check('v2 flow: a slow road (stop 3) is --v-band-amber on the casing', m?.material?.outlined === true && m.width === Math.max(3, mid.width) + 2.5 && cssOfColor(m.material.color) === M.SYM.inkAlpha(band('--v-band-amber'), 1));
	const f = lines['seg:1005'];
	check(
		'v2 flow: a free road stays legible — stop 1, at least 3 px, --v-band-green at 95 %, its dashes on the dark ground casing (a schematic chord stays dashed)',
		f?.material?.dashed === true && f.width === Math.max(3, free.width) && cssOfColor(f.material.color) === M.SYM.inkAlpha(band('--v-band-green'), 0.95) && !!f.material.gapColor,
		JSON.stringify({ w: f?.width, c: cssOfColor(f?.material?.color) }),
	);
	const used = Object.values(lines).flatMap((l) => [cssOfColor(l.material?.color ?? l.material)].filter(Boolean));
	const ladder = ['--v-band-green', '--v-band-amber', '--v-band-red'].map((k) => M.SYM.inkAlpha(band(k), 1).replace(/, [\d.]+\)$/, ''));
	const neutralTrace = (css) => {
		const mm = /rgba\((\d+), (\d+), (\d+)/.exec(css);
		return !!mm && Math.max(+mm[1], +mm[2], +mm[3]) - Math.min(+mm[1], +mm[2], +mm[3]) <= 30;
	};
	check('v2 flow: every coloured road is a step of the band ladder (green, amber, red); a road without a reading stays a neutral trace', used.every((css) => ladder.some((h) => css.startsWith(h)) || neutralTrace(css)), used.join(' | '));
	const hues = ['--v-act', '--v-data', '--v-tool'].map((k) => M.SYM.inkAlpha(TOKENS[k].toLowerCase(), 1).replace(/, [\d.]+\)$/, ''));
	check('v2 flow: never the decision orange, the data or the tool blue on the roads', !used.some((css) => hues.some((h) => css.startsWith(h))));
	const sel = await flowV2({ observations: [liveRow(1006, 8, 0.95)] }, { ...live, selection: 'vehicle:X', items: ['vehicle:X'], version: 2 });
	const js = sel.lines['seg:1006'];
	check('v2 flow: under a selection 60 % and 0.5 px thinner', js?.width === Math.max(3, jam.width) - 0.5 + 2.5 && cssOfColor(js.material.color) === M.SYM.inkAlpha(band('--v-band-red'), 1 * 0.6), JSON.stringify({ w: js?.width, c: cssOfColor(js?.material?.color) }));
	const nd = sel.lines['seg:1015'];
	check('v2 flow: a NO DATA road is a 1 px trace dimmer than free', nd?.width === 1 && cssOfColor(nd.material) === M.SYM.inkAlpha(free.color, 0.35 * 0.6), JSON.stringify({ w: nd?.width, c: cssOfColor(nd?.material) }));
	const emu = await flowV2({ observations: [liveRow(1005, 41, 0.35)], emulated_observations: [emuRow(1005, 8, 0.92)] }, live);
	const card = emu.cards['seg:1005'];
	check('v2 flow: the pick text names the emulated run and the simulated feed in plain words', /emulated run, simulated feed/.test(card) && /ingest plane reads 41\.0 km\/h, 35 %/.test(card), card.slice(0, 160));
	check('v2 flow: no stacked status words on the pick text', !/[A-Z]{3,} · [A-Z]{3,}/.test(card) && !/EMULATED|SIMULATED FEED|NO DATA|SCHEMATIC/.test(card));
}

// ── 9b. a reading that moves without changing the picture never rebuilds the network (review r1) ──
//
// Removing and re-adding every segment on each poll made Cesium rebuild the
// draped primitives — and it drops a build still in flight when the next
// change lands, so on a loaded box the network could stay off the map for
// tens of seconds. Same picture → the pick texts move in place; a ramp step
// that changes → the network is redrawn.

async function flowSequence(chrome) {
	let body = { observations: [liveRow(1006, 8, 0.95), liveRow(1005, 50, 0.1)] };
	globalThis.fetch = async () => ({ ok: true, json: async () => body });
	const timers = [];
	const realSetInterval = globalThis.setInterval;
	globalThis.setInterval = (fn, ms) => {
		timers.push({ fn, ms });
		return 0;
	};
	const viewer = makeViewer();
	const layer = M.trafficFlowLayer.create();
	layer.init({ cesium: makeCesium(), viewer, fetchJson: async () => ({}), notify() {}, ...(chrome ? { chrome, view: () => M.V.emptyView(chrome) } : {}) });
	try {
		layer.activate();
	} finally {
		globalThis.setInterval = realSetInterval;
	}
	const poll = timers.find((t) => t.ms === 8000)?.fn;
	const redraw = timers.find((t) => t.ms === 2000)?.fn;
	const step = async () => {
		poll();
		for (let i = 0; i < 6; i++) await tick();
		redraw();
	};
	for (let i = 0; i < 6; i++) await tick();
	redraw();
	const first = viewer.byId.get('seg:1006');
	const firstText = String(first?.description ?? '');
	body = { observations: [liveRow(1006, 9, 0.96), liveRow(1005, 51, 0.12)] }; // a new speed, the same ramp step
	await step();
	const same = viewer.byId.get('seg:1006');
	body = { observations: [liveRow(1006, 30, 0.5), liveRow(1005, 51, 0.12)] }; // a new ramp step
	await step();
	const next = viewer.byId.get('seg:1006');
	const other = viewer.byId.get('seg:1005');
	layer.deactivate();
	return { first, firstText, same, next, other };
}

// the theme's real inks (the legacy picture keys on the resolved ramp colour)
globalThis.document = { documentElement: { dataset: {} }, hidden: false, createElement: () => ({ getContext: () => null }) };
globalThis.getComputedStyle = () => ({ getPropertyValue: (name) => M.TOK.TOKENS.command[name] ?? '' });
for (const chrome of [null, 'v2']) {
	const name = chrome ?? 'legacy';
	const r = await flowSequence(chrome);
	check(
		`${name} flow: a speed that moves within the same ramp step keeps the drawn segment (no rebuild) and rewrites its pick text in place`,
		!!r.first && r.same === r.first && /8\.0 km\/h/.test(r.firstText) && /9\.0 km\/h/.test(String(r.same.description)),
		`${r.firstText.slice(0, 60)} → ${String(r.same?.description ?? '').slice(0, 60)}`,
	);
	check(
		`${name} flow: a reading that crosses into another ramp step redraws the network`,
		!!r.next && r.next !== r.same && JSON.stringify(normGraph(r.next.polyline)) !== JSON.stringify(normGraph(r.same.polyline)) && /30\.0 km\/h/.test(String(r.next.description)) && !!r.other,
	);
}

// v2: while a draped build is still in flight (Cesium's clockViewModel.canAnimate false), a READING that
// changes the picture waits (the build is not thrown away); the build landing lets it through; a
// change of structure (the view's dim) never waits; the legacy chrome never waits.
async function flowWhileBuilding(chrome) {
	let body = { observations: [liveRow(1006, 8, 0.95), liveRow(1005, 50, 0.1)] };
	globalThis.fetch = async () => ({ ok: true, json: async () => body });
	const timers = [];
	const realSetInterval = globalThis.setInterval;
	globalThis.setInterval = (fn, ms) => {
		timers.push({ fn, ms });
		return 0;
	};
	const viewer = { ...makeViewer(), clockViewModel: { canAnimate: true } };
	let view = M.V.emptyView('v2');
	const layer = M.trafficFlowLayer.create();
	layer.init({ cesium: makeCesium(), viewer, fetchJson: async () => ({}), notify() {}, ...(chrome ? { chrome, view: () => view } : {}) });
	try {
		layer.activate();
	} finally {
		globalThis.setInterval = realSetInterval;
	}
	const poll = timers.find((t) => t.ms === 8000)?.fn;
	const redraw = timers.find((t) => t.ms === 2000)?.fn;
	const step = async () => {
		poll();
		for (let i = 0; i < 6; i++) await tick();
		redraw();
	};
	for (let i = 0; i < 6; i++) await tick();
	redraw();
	const drawn = viewer.byId.get('seg:1006');
	viewer.clockViewModel.canAnimate = false; // a draped build is in flight
	// 1006 crosses into another ramp step; 1005 moves within its own
	body = { observations: [liveRow(1006, 30, 0.5), liveRow(1005, 51, 0.12)] };
	await step();
	const waiting = viewer.byId.get('seg:1006');
	const waitingText = String(waiting?.description ?? '');
	const sameStepText = String(viewer.byId.get('seg:1005')?.description ?? '');
	redraw(); // still building: still waits
	const stillWaiting = viewer.byId.get('seg:1006');
	viewer.clockViewModel.canAnimate = true; // the build landed
	redraw();
	const landed = viewer.byId.get('seg:1006');
	const landedText = String(landed?.description ?? '');
	viewer.clockViewModel.canAnimate = false;
	view = { ...view, selection: 'vehicle:X', items: ['vehicle:X'], version: 9 }; // the view's dim: structure
	layer.restyle();
	const restyled = viewer.byId.get('seg:1006');
	layer.deactivate();
	return { drawn, waiting, waitingText, sameStepText, stillWaiting, landed, landedText, restyled };
}

{
	const v = await flowWhileBuilding('v2');
	check(
		'v2 flow: a reading that changes the picture WAITS while a draped build is in flight (the drawn segment kept)',
		!!v.drawn && v.waiting === v.drawn && v.stillWaiting === v.drawn,
	);
	check(
		'v2 flow: … while it waits, the waiting segment keeps the pick text of the step it still shows (never a reading its line contradicts); a segment whose step held takes its new reading in place',
		/8\.0 km\/h/.test(v.waitingText) && !/30\.0 km\/h/.test(v.waitingText) && /51\.0 km\/h/.test(v.sameStepText),
		`${v.waitingText.slice(0, 60)} | ${v.sameStepText.slice(0, 60)}`,
	);
	check(
		'v2 flow: … and is drawn, with its new reading, once the build lands',
		!!v.landed && v.landed !== v.drawn && JSON.stringify(normGraph(v.landed.polyline)) !== JSON.stringify(normGraph(v.drawn.polyline)) && /30\.0 km\/h/.test(v.landedText),
	);
	check('v2 flow: a change of structure (the selection dims the layer) never waits', !!v.restyled && v.restyled !== v.landed);
	const l = await flowWhileBuilding(null);
	check('legacy flow: never waits (the picture follows every reading as before)', !!l.drawn && l.waiting !== l.drawn && /30\.0 km\/h/.test(String(l.waiting?.description ?? '')));
}

delete globalThis.document;
delete globalThis.getComputedStyle;

// ── 10. every layer under chrome v2: tokens, tags, decisions, the track — and legacy invariance ──

const MINUTE = 60_000;
{
	// one city picture for every layer: a stolen vehicle with reads and two pending sightings,
	// an e-challan (and one withheld on the stolen vehicle), an anomaly, a requested dispatch,
	// a unit, a convoy on a protected movement with a hold proposal, a pursuit
	const R = M.cityRegistry.rows;
	const ent = (kind, id, over = {}) => ({ urn: `${kind}:${id}`, kind, id, label: `${kind} ${id}`, lon: 88.3499, lat: 22.5632, state: null, band: null, source: 'emulated', t: NOW - 5 * MINUTE, ageSec: 300, links: [], props: {}, ...over });
	R.recommendation = [
		ent('recommendation', 'r-1', { state: 'pending', links: ['vehicle:veh-1'], props: { rule_id: 'R_STOLEN_SIGHTING', vehicle_id: 'veh-1', camera_id: 'EM-CAM-03' } }),
		ent('recommendation', 'r-2', { state: 'pending', lon: 88.3549, links: ['vehicle:veh-1'], props: { rule_id: 'R_STOLEN_SIGHTING', vehicle_id: 'veh-1', camera_id: 'EM-CAM-01' } }),
		ent('recommendation', 'r-3', { state: 'pending', lon: 88.3599, props: { rule_id: 'R_SPD_SEGMENT', vehicle_id: 'veh-2', camera_id: 'EM-CAM-05', evidence: { speed_kmh: 92, speed_limit_kmh: 60, road_name: 'Strand Road' } } }),
		ent('recommendation', 'r-4', { state: 'pending', lon: 88.3649, props: { rule_id: 'R_SPD_SEGMENT', vehicle_id: 'veh-1', camera_id: 'EM-CAM-03', evidence: { speed_kmh: 80, speed_limit_kmh: 60 } } }),
	];
	R.anomaly = [ent('anomaly', '7', { state: 'high', t: NOW, props: { anomaly_type: 'speed_jump', count_15m: 6, data_quality: 'synthetic', road_name: 'Strand Road' } })];
	// the OSINT picture (OS-DECK-A): a correlated report with a proposed, unexpired DSS (the
	// decision mark), a district-level area report (the ring), a report without a city point
	// (counted "not mapped"), a place (the places layer, a small neutral marker)
	const os = (id, over = {}) => ({
		urn: `osint_event:${id}`,
		kind: 'osint_event',
		id,
		label: 'Road accident · Sector V (Salt Lake)',
		lon: 88.2799,
		lat: 22.5482,
		state: 'surfaced',
		band: null,
		source: 'osint',
		t: NOW - 40 * MINUTE,
		ageSec: 2400,
		links: [],
		props: {},
		...over,
	});
	const DSS_WAITING = { dss_id: 'd-1', state: 'proposed', top_coa_id: 'coa_base', top_coa_label: 'Monitor only (do nothing)', generated_at: new Date(NOW - 5 * MINUTE).toISOString(), horizon_min: 120, expires_at: new Date(NOW + 115 * MINUTE).toISOString() };
	R.osint_event = [
		os('a1a2a3a4-b1b2-4c3c-8d4d-000000000001', {
			label: 'Road accident · Sector V (Salt Lake)',
			props: { area_level: false, verification_state: 'NEWS-REPORTED', credibility: 0.65, toponym: 'Sector V (Salt Lake)', dss: DSS_WAITING },
		}),
		os('a1a2a3a4-b1b2-4c3c-8d4d-000000000002', {
			label: 'Weather hazard · Mumbai City district',
			lon: 88.3413,
			lat: 22.5607,
			t: NOW - 3 * 60 * MINUTE,
			props: { area_level: true, verification_state: 'OFFICIAL-VERIFIED', credibility: 0.95, toponym: 'Mumbai City (district)' },
		}),
		os('a1a2a3a4-b1b2-4c3c-8d4d-000000000003', {
			label: 'State-wide nowcast',
			lon: null,
			lat: null,
			props: { area_level: true, verification_state: 'OFFICIAL-VERIFIED', credibility: 0.9 },
		}),
		// a PROPOSED-but-EXPIRED decision support: never a waiting decision on the map (FIX-E)
		os('a1a2a3a4-b1b2-4c3c-8d4d-000000000004', {
			label: 'Expired proposal report',
			lon: 88.37,
			lat: 22.5682,
			props: { area_level: false, verification_state: 'NEWS-REPORTED', credibility: 0.6, dss: { dss_id: 'd-9', state: 'proposed', top_coa_id: 'coa_base', top_coa_label: 'Monitor only (do nothing)', generated_at: new Date(NOW - 6 * 3_600_000).toISOString(), horizon_min: 120, expires_at: new Date(NOW - 5 * 60_000).toISOString() } },
		}),
	];
	// R1: the city-wide held-social count rides the feed's extra, shown ONCE at layer level
	M.cityRegistry.feeds['osint_event'] = { count: 3, status: 'ok', extra: { held_social: 2 } };
	R.place = [
		{ urn: 'place:sector_v_salt_lake_106', kind: 'place', id: 'sector_v_salt_lake_106', label: 'Sector V (Salt Lake)', lon: 88.4414, lat: 22.5799, state: 'landmark', band: null, source: 'osint', t: NOW - 40 * MINUTE, ageSec: 2400, links: [], props: { feature_type: 'landmark', osint_event_count: 1 } },
	];
	R.dispatch = [
		ent('dispatch', 'd-1', { state: 'requested', props: { agency: 'police', unit_id: 'U-1', waypoint_junction: 15, event_title: 'Pursuit' } }),
		// a unit out on its way: the v2 dashed line from the unit to its waypoint
		ent('dispatch', 'd-2', { state: 'en_route', lon: 88.37, props: { agency: 'ems', unit_id: 'U-2', event_title: 'Pursuit', decided_by: 'duty-officer-2' } }),
	];
	R.unit = [ent('unit', 'U-2', { lon: 88.4102, lat: 22.5536, props: { agency: 'ems' } })];
	R.convoy = [ent('convoy', 'm-1', { label: 'Z movement', state: 'moving', t: NOW, props: { speed_kmh: 38, heading: 45, progress: 0.31, event_id: 'ev-pm', segment_id: 1015 } })];
	M.ops.watchlist = [{ vehicleId: 'veh-1', lawfulBasis: 'stolen_vehicle_fir' }];
	const ev = (eventId, eventKind, segs, over = {}) => ({
		eventId,
		name: eventKind === 'vehicle_pursuit' ? 'PURSUIT — stolen MH47EM9001' : 'Z protected movement',
		eventKind,
		state: 'active',
		source: 'live-events-api',
		routeSegmentIds: segs,
		routes: [],
		routeHistory: [],
		windowStart: new Date(NOW - 60 * MINUTE).toISOString(),
		windowEnd: null,
		band: 'GREEN',
		currentPhase: null,
		description: null,
		...over,
	});
	M.ops.events = [ev('ev-pm', 'protected_movement', [1005, 1015, 1006]), ev('ev-pu', 'vehicle_pursuit', [1006])];
	M.ops.interception = { ...PLAN, vehicleId: 'veh-1' };
	M.godsEye.vehicles.length = 0;
	M.godsEye.vehicles.push({
		vehicleId: 'veh-1',
		plate: 'MH47EM9001',
		earmarkState: 'flagged',
		retentionUntil: null,
		lawfulBasis: 'stolen_vehicle_fir',
		lastSighting: { t: NOW - MINUTE, lon: 88.3549, lat: 22.5652, source: 'emulated_anpr', cameraId: 'EM-CAM-01', hit: 'stolen_vehicle' },
	});
	const hop = (seq, ago, lon, lat, cameraId) => ({ seq, t: NOW - ago * MINUTE, lon, lat, cameraId, speedKmh: 40, source: 'emulated_anpr', sightingId: `s-${seq}` });
	const hops = [hop(1, 50, 88.3299, 22.5482, 'EM-CAM-09'), hop(2, 20, 88.4102, 22.5536, 'EM-CAM-02'), hop(3, 10, 88.3499, 22.5632, 'EM-CAM-03'), hop(4, 1, 88.3549, 22.5652, 'EM-CAM-01')];
	M.godsEye.traces.set('veh-1', { vehicleId: 'veh-1', coordinates: hops.map((h) => [h.lon, h.lat]), hops, latestT: NOW - MINUTE, via: 'city', source: 'emulated_anpr', status: null, disclosure: null });
	M.godsEye.units.length = 0;
	M.godsEye.units.push({ unitId: 'U-1', agency: 'police', lon: 88.3509, lat: 22.5592, emulated: true, status: 'en_route', etaSec: 90, progress: 0.4, label: 'Police 12', arrived: false, assignedEventId: 'ev-pu', dispatchId: 'd-1', speedKmh: 30, source: 'emulated' });
	M.escortFollower.movementId = 'm-1';
	M.escortFollower.status = { status: 'running', pendingApprovals: [{ approvalId: 'a-1', action: 'hold_short', reason: 'congestion 86 %', raisedAt: NOW, tier: 'strategic', confidence: 0.81, segmentIds: [1006], detourSegmentIds: [1015], detourM: 1200, remainingM: 3400, simulated: true }] };
	globalThis.fetch = async () => ({ ok: true, json: async () => ({ observations: [liveRow(1005, 41, 0.35), liveRow(1006, 8, 0.95)], zones: [] }) });

	// every custom property read goes through getComputedStyle: record the names
	const reads = new Set();
	// a 2D context that accepts every call, so the painters run (and read their tokens)
	const fakeCanvas = () => {
		const el = { width: 0, height: 0, toDataURL: () => 'data:image/png;base64,c3R1Yg==' };
		const ctx = new Proxy(
			{ canvas: el },
			{
				get(target, prop) {
					if (prop in target) return target[prop];
					if (prop === 'measureText') return (t) => ({ width: String(t).length * 6.5 });
					return () => {};
				},
				set(target, prop, value) {
					target[prop] = value;
					return true;
				},
			},
		);
		el.getContext = () => ctx;
		return el;
	};
	globalThis.document = { documentElement: { dataset: {} }, hidden: false, createElement: () => fakeCanvas() };
	globalThis.getComputedStyle = () => ({
		getPropertyValue(name) {
			reads.add(String(name));
			return '';
		},
	});
	const selectedView = { ...M.V.emptyView('v2'), selection: 'vehicle:veh-1', items: ['vehicle:veh-1'], related: new Set(['camera:EM-CAM-03']), decisions: new Set(['vehicle:veh-1']), version: 3 };
	// the pursuit's zone (the events board's zone_geojson): a violet fill and rim under v2
	const ZONED = [{ event_id: 'ev-pu', state: 'active', zone_geojson: { type: 'Polygon', coordinates: [[[88.3499, 22.5582], [88.3599, 22.5582], [88.3599, 22.5682], [88.3499, 22.5582]]] } }];
	async function drawLayer(layer, chrome, view = selectedView) {
		reads.clear();
		const viewer = makeViewer();
		const inst = layer.create();
		inst.init({ cesium: makeCesium({ cartesianClass: true }), viewer, fetchJson: async () => ({ zones: [], events: ZONED }), notify() {}, ...(chrome ? { chrome, view: () => view } : {}) });
		inst.activate();
		for (let i = 0; i < 10; i++) await tick();
		inst.refresh();
		for (let i = 0; i < 10; i++) await tick();
		const ents = [...viewer.byId.values()];
		const stats = inst.coverageStats();
		const tokenReads = [...reads];
		inst.deactivate();
		for (let i = 0; i < 5; i++) await tick();
		return { ents, stats, tokenReads };
	}
	const FORBIDDEN = /^--v-(act|data|tool)(-|$)/;
	const layers = M.IDX.GODS_EYE_LAYERS.filter((l) => l.id !== 'photoreal-3d');
	const v2 = {};
	const legacy = {};
	for (const layer of layers) {
		v2[layer.id] = await drawLayer(layer, 'v2');
		legacy[layer.id] = await drawLayer(layer, null);
	}
	const pursuitDraw = (chrome, kinds = null) => {
		reads.clear();
		const viewer = makeViewer();
		const overlay = M.createPursuitOverlay(makeCesium({ cartesianClass: true }), viewer, chrome ? { chrome } : {});
		overlay.show({
			plan: M.ops.interception,
			trace: [],
			kinds,
			detail: { eventId: 'evt-1', vehicleId: 'veh-1', sightingId: 's-1', cameraId: 'EM-CAM-03', sightingAgeSec: 30, stale: false, staleAfterSec: 600, seedSegmentId: 1015, direction: { basis: 'heading', againstOneway: false, onwardSegmentIds: [], towardsJunctionIds: [15] }, chokes: [{ junctionId: 15, name: 'Sea Link, Worli end', likelyPassed: false }, { junctionId: 8, name: 'Bowbazar', likelyPassed: true }], note: null },
		});
		const out = { ents: [...viewer.byId.values()], tokenReads: [...reads], count: overlay.count(), audit: overlay.audit() };
		overlay.destroy();
		return out;
	};
	v2.pursuit = pursuitDraw('v2');
	legacy.pursuit = pursuitDraw(null);

	const bad = Object.entries(v2).flatMap(([id, d]) => d.tokenReads.filter((n) => FORBIDDEN.test(n)).map((n) => `${id}:${n}`));
	check('v2: NO layer reads --v-act, --v-data or --v-tool (every token read recorded)', bad.length === 0, bad.join(', ') || `${Object.keys(v2).length} layers + the pursuit overlay clean`);
	const mapReads = Object.entries(v2).filter(([, d]) => d.ents.length > 0 && d.tokenReads.some((n) => /^--v-(map|flow)-/.test(n)));
	check('v2: the drawing layers read the --v-map-* / --v-flow-* tokens', mapReads.length >= 8, mapReads.map(([id]) => id).join(', '));
	const legacyHue = Object.entries(legacy).filter(([, d]) => d.tokenReads.some((n) => FORBIDDEN.test(n))).map(([id]) => id);
	check('legacy invariance: the legacy chrome still reads the tokens it read before (act, data, tool)', ['cameras', 'enforcement', 'events', 'traces', 'anomalies'].every((id) => legacyHue.includes(id)) && legacyHue.includes('pursuit'), legacyHue.join(', '));

	const metaOf = (e) => M.SYM.markerMeta(e);
	const drawnEnts = Object.values(v2).flatMap((d) => d.ents);
	const v2Labels = drawnEnts.filter((e) => e.label);
	check('v2: no layer draws a Cesium label of its own (the canvas places every label)', v2Labels.length === 0, v2Labels.map((e) => e.id).join(', '));
	const markers = drawnEnts.filter((e) => e.billboard);
	const untagged = markers.filter((e) => !metaOf(e) && !/heading-head$/.test(e.id));
	check('v2: every marker is tagged (URN, kind, type glyph) for the canvas pass', markers.length > 10 && untagged.length === 0, untagged.map((e) => e.id).join(', ') || `${markers.length} markers`);
	check('v2: every marker glyph is a real icon (type is the glyph)', markers.filter(metaOf).every((e) => M.ICONS.isIconName(metaOf(e).glyph)));
	check('v2: every marker is painted (a data URL image, the same box in every state)', markers.filter(metaOf).every((e) => typeof e.billboard.image === 'string' && e.billboard.image.startsWith('data:image/png')));
	const cams = v2.cameras.ents.map((e) => [e.id, metaOf(e)]);
	check('v2 cameras: neutral discs with the camera glyph that cluster (no hue role)', cams.length > 0 && cams.every(([, m]) => m?.kind === 'camera' && m.glyph === M.ICONS.kindIcon('camera') && m.cluster === true && !m.role));
	const p01 = v2.cameras.ents.find((e) => e.id === 'cam:EM-CAM-01')?.position;
	const p02 = v2.cameras.ents.find((e) => e.id === 'cam:EM-CAM-02')?.position;
	const l01 = legacy.cameras.ents.find((e) => e.id === 'cam:EM-CAM-01')?.position;
	const l02 = legacy.cameras.ents.find((e) => e.id === 'cam:EM-CAM-02')?.position;
	check('v2 cameras: co-located cameras keep their true position (the canvas clusters them); legacy still fans them out', JSON.stringify(p01) === JSON.stringify(p02) && JSON.stringify(l01) !== JSON.stringify(l02));

	const pin = v2.traces.ents.find((e) => e.id === 'veh:mark-veh-1');
	const pm = pin && metaOf(pin);
	check('v2 vehicle: the offset pin — tip on the last read, head 46 px up-left, red ring (alert role)', pm?.shape === 'pin' && pm.role === 'alert' && pm.click?.x === -26 && pm.click?.y === -38 && Math.round(Math.hypot(pm.click.x, pm.click.y)) === 46);
	check('v2 vehicle: its label is the masked mark with the lock, shown when selected', pm?.label?.[0]?.id === 'MH47EM•••1' && pm.labelLock === true && pm.labelWhen === 'selected');
	const trace = v2.traces.ents.find((e) => e.id === 'veh:trace-veh-1');
	const tm = trace && M.SYM.trackMeta(trace);
	check(
		'v2 vehicle track: the selected vehicle only — a 3 px alert core in a 7 px casing',
		trace?.polyline?.width === M.TR.TRACK_WIDTH.casing && trace.polyline.material?.outlined === true && trace.polyline.material.outlineWidth === M.TR.TRACK_WIDTH.casing - M.TR.TRACK_WIDTH.line && M.TR.TRACK_WIDTH.line === 3 && M.TR.TRACK_WIDTH.casing === 7,
		JSON.stringify({ w: trace?.polyline?.width, o: trace?.polyline?.material?.outlineWidth }),
	);
	check('v2 vehicle track: the latest pass (reads within 30 min of the newest), tagged for direction arrows', tm?.coords?.length === 3 && v2.traces.ents.filter((e) => /^veh:hop-/.test(e.id)).length === 3, `${tm?.coords?.length} points`);
	const hopMeta = v2.traces.ents.filter((e) => /^veh:hop-/.test(e.id)).map(metaOf);
	check("v2 reads: each read's label is its camera id (identifier face) and its time (Inter)", hopMeta.every((m) => m.label?.[0]?.id?.startsWith('EM-CAM-') && typeof m.label?.[1]?.time === 'number' && m.labelWhen === 'always'));
	const windowed = M.TR.trackHops(hops, [NOW - 15 * MINUTE, NOW - 5 * MINUTE]);
	check('v2 vehicle track: with a window, only the reads inside it', windowed.length === 1 && windowed[0].cameraId === 'EM-CAM-03');
	check('legacy invariance: the legacy traces still draw every hop with its numbered label', legacy.traces.ents.some((e) => /^veh:hop-/.test(e.id) && e.label) && !legacy.traces.ents.some((e) => metaOf(e)));

	// ── the track's direction arrows: keyed by each span's own geometry (review r2) ──
	// A read in, a read out of the 30-min pass or another window redraws the
	// track under the same entity id: an arrow keyed by the span INDEX stayed on
	// a span no longer drawn and the newest span had none. trackArrows keys
	// each arrow by its span's endpoints (and the scale its arms were sized
	// for), so the canvas keeps the arrows it still wants and drops the rest.
	{
		const { trackArrows, TRACK_ARROW, groundMetres, bearingDeg } = M.SYM;
		const flat = (k = 1) => (lon, lat) => ({ x: (lon - 88.27) * 1e5 * k, y: (22.64 - lat) * 1e5 * k });
		const screen = { width: 1e6, height: 1e6 };
		const P = { A: [88.3299, 22.5482], B: [88.4102, 22.5536], C: [88.3499, 22.5632], D: [88.3549, 22.5652], E: [88.3599, 22.5682] };
		const key = (p, q) => `${p[0].toFixed(6)},${p[1].toFixed(6)}>${q[0].toFixed(6)},${q[1].toFixed(6)}@`;
		const spans = (arrows) => arrows.map((a) => a.id.slice(0, a.id.indexOf('@') + 1));
		const before = trackArrows([P.A, P.B, P.C, P.D], flat(), screen);
		const after = trackArrows([P.B, P.C, P.D, P.E], flat(), screen);
		const keptIds = after.filter((a) => before.some((b) => b.id === a.id)).map((a) => a.id);
		check(
			'track arrows: one per span drawn ≥ 60 px, keyed by the span (A>B, B>C, C>D)',
			TRACK_ARROW.minPx === 60 && JSON.stringify(spans(before)) === JSON.stringify([key(P.A, P.B), key(P.B, P.C), key(P.C, P.D)]),
			spans(before).join(' '),
		);
		check(
			'track arrows: read E in and read A out — the B>C and C>D arrows keep their ids, A>B is no longer wanted, the newest span D>E gets its own',
			keptIds.length === 2 && !spans(after).includes(key(P.A, P.B)) && spans(after).includes(key(P.D, P.E)) && after.length === 3,
			spans(after).join(' '),
		);
		const windowed = trackArrows([P.B, P.C], flat(), screen);
		check('track arrows: a window that keeps one span keeps one arrow, on that span', windowed.length === 1 && spans(windowed)[0] === key(P.B, P.C));
		check('track arrows: none on a span drawn under 60 px, none with its midpoint off screen', trackArrows([P.C, P.D], flat(0.05), screen).length === 0 && trackArrows([P.A, P.B], flat(), { width: 100, height: 100 }).length === 0);
		const ab = before[0];
		const metres = groundMetres(P.A, P.B);
		const px = Math.hypot(...[0, 1].map((i) => (P.B[i] - P.A[i]) * 1e5));
		const armM = groundMetres(ab.chevron[1], ab.chevron[0]);
		const want = (TRACK_ARROW.armPx * metres) / px;
		check(
			`track arrows: a chevron of ${TRACK_ARROW.armPx} px arms at the span's scale (quarter-octave steps), tip ahead of the midpoint along the span, both arms behind it`,
			armM / want > 2 ** -0.13 && armM / want < 2 ** 0.13 &&
				Math.abs(bearingDeg(ab.mid, ab.chevron[1]) - bearingDeg(P.A, P.B)) < 0.5 &&
				Math.abs(groundMetres(ab.chevron[1], ab.chevron[2]) - armM) < 1e-6 * armM + 1e-6 &&
				groundMetres(ab.chevron[0], P.A) < groundMetres(ab.chevron[1], P.A),
			`arm ${armM.toFixed(2)} m for ${want.toFixed(2)} m`,
		);
		const nudged = trackArrows([P.A, P.B], flat(1.02), screen);
		const zoomed = trackArrows([P.A, P.B], flat(1.6), screen);
		check('track arrows: a small zoom keeps the arrow; a zoom past a step re-sizes it (a new id on the same span)', nudged[0]?.id === ab.id && zoomed[0]?.id !== ab.id && spans(zoomed)[0] === key(P.A, P.B), `${ab.id} | ${nudged[0]?.id} | ${zoomed[0]?.id}`);
	}

	const dec = M.ENF.decisionUrns(R.recommendation, new Set(['veh-1']));
	check('decision dots: ONE per object — the vehicle for its two sightings, the pending e-challan; the withheld one none', JSON.stringify([...dec].sort()) === JSON.stringify(['recommendation:r-3', 'vehicle:veh-1']), JSON.stringify([...dec]));
	{
		// fix round 2, R3: the canvas pass's decision set is the layers' PURE builder — the
		// waiting OSINT URN must ride the view.decisions it feeds (that is what keeps the dot
		// on a selected or clustered marker), the expired one must not, and the enforcement
		// and dispatch behaviour it absorbed keeps working
		const now = NOW + MINUTE;
		const urns = M.OSI.cityDecisionUrns({
			recommendations: R.recommendation,
			stolen: new Set(['veh-1']),
			dispatches: R.dispatch,
			osint: R.osint_event,
			enforcementOn: true,
			now,
		});
		check(
			'cityDecisionUrns: the waiting osint URN is in the view\'s decision set, the expired one is not',
			urns.has('osint_event:a1a2a3a4-b1b2-4c3c-8d4d-000000000001') &&
				!urns.has('osint_event:a1a2a3a4-b1b2-4c3c-8d4d-000000000004') &&
				urns.has('recommendation:r-3') &&
				urns.has('vehicle:veh-1') &&
				urns.has('dispatch:d-1'),
			JSON.stringify([...urns].sort()),
		);
		const off = M.OSI.cityDecisionUrns({ recommendations: R.recommendation, stolen: new Set(['veh-1']), dispatches: R.dispatch, osint: R.osint_event, enforcementOn: false, now });
		check('cityDecisionUrns: enforcement off keeps the dispatch and the waiting osint only', !off.has('recommendation:r-3') && !off.has('vehicle:veh-1') && off.has('dispatch:d-1') && off.has('osint_event:a1a2a3a4-b1b2-4c3c-8d4d-000000000001'), JSON.stringify([...off].sort()));
	}
	{
		// orchestrator make-up (audit E-OSINTDECK R2 must-fix 2): the canvas wiring and the cluster-lead rule
		const { readFileSync } = await import('node:fs');
		const CANVAS = readFileSync(new URL('../src/lib/gods-eye/GodsEyeCanvas.svelte', import.meta.url), 'utf8');
		check('canvas: decisionSet feeds the live OSINT situations into the decision set', /function decisionSet[\s\S]{0,400}osint: cityRegistry\.byKind\('osint_event'\)/.test(CANVAS));
		check('canvas: the marker decision state goes through markShowsDecision with the cluster members', CANVAS.includes('decision: markShowsDecision(m.st.decision, isLead, spreadOut, clusterOf.get(m.e.id)?.members, memberWaits),'));
		const waits = (id) => id === 'm2';
		check('markShowsDecision: a collapsed cluster lead shows a waiting member\'s dot', M.OSI.markShowsDecision(false, true, false, ['m1', 'm2'], waits) === true);
		check('markShowsDecision: no waiting member, no dot; own decision always shows', M.OSI.markShowsDecision(false, true, false, ['m1'], waits) === false && M.OSI.markShowsDecision(true, false, false, undefined, waits) === true);
		check('markShowsDecision: a non-lead or a spread-out cluster never borrows a member\'s dot', M.OSI.markShowsDecision(false, false, false, ['m2'], waits) === false && M.OSI.markShowsDecision(false, true, true, ['m2'], waits) === false);
	}
	const enfIds = v2.enforcement.ents.map((e) => e.id);
	check('v2 enforcement: the map shows what waits — no marker per sighting, none for the withheld fine', JSON.stringify(enfIds) === JSON.stringify(['rec:r-3']) && v2.enforcement.stats.count === 2, `${enfIds.join(',')} · count ${v2.enforcement.stats.count}`);
	check('legacy invariance: the legacy enforcement layer still draws every pin with its site label', legacy.enforcement.ents.length === 4 && legacy.enforcement.ents.some((e) => e.label) && legacy.enforcement.stats.count === 4);

	const cv = v2.convoy.ents.find((e) => e.id === 'cvy:m-1');
	check('v2 convoy: the turquoise marker "Convoy · 38 km/h"', metaOf(cv)?.role === 'route' && M.SYM.labelText(metaOf(cv).label) === 'Convoy · 38 km/h' && metaOf(cv).labelWhen === 'always');
	const ahead = v2.convoy.ents.filter((e) => /^cvy:ahead-/.test(e.id)).map((e) => e.id);
	const done = v2.convoy.ents.filter((e) => /^cvy:done-/.test(e.id)).map((e) => e.id);
	check('v2 convoy: the route ahead (turquoise, cased) and the route travelled (dimmed)', ahead.join() === 'cvy:ahead-m-1-1015,cvy:ahead-m-1-1006' && done.join() === 'cvy:done-m-1-1005', `${ahead} | ${done}`);
	const hold = v2.convoy.ents.find((e) => /^cvy:hold-/.test(e.id));
	check('v2 convoy: the hold proposal is an orange ring with a pause glyph, "Hold proposed"', metaOf(hold)?.role === 'decision' && metaOf(hold).glyph === 'pause' && M.SYM.labelText(metaOf(hold).label) === 'Hold proposed');

	const spines = v2.events.ents.filter((e) => /^ev:spine-/.test(e.id) || /spine-/.test(e.id));
	const rgbOf = (css) => (/rgba?\((\d+), (\d+), (\d+)/.exec(css ?? '') ?? []).slice(1, 4).join(',');
	const routeInk = rgbOf(M.SYM.inkAlpha(TOKENS['--v-map-route'], 1));
	const eventInk = rgbOf(M.SYM.inkAlpha(TOKENS['--v-map-event'], 1));
	const inkOf = (e) => rgbOf(cssOfColor(e.polyline?.material?.color ?? e.polyline?.material));
	check('v2 events: corridor events violet, a protected movement turquoise', spines.some((e) => /ev-pm/.test(e.id) && inkOf(e) === routeInk) && spines.some((e) => /ev-pu/.test(e.id) && inkOf(e) === eventInk), spines.map((e) => `${e.id}:${inkOf(e)}`).join(' '));
	const evMarks = v2.events.ents.filter(metaOf).map(metaOf);
	check('v2 events: a marker with the event kind glyph per event', evMarks.length === 2 && evMarks.some((m) => m.glyph === M.ICONS.eventKindIcon('vehicle_pursuit')) && evMarks.some((m) => m.glyph === M.ICONS.eventKindIcon('protected_movement')));

	check('v2 anomalies: a small neutral diamond, no pulse ring', v2.anomalies.ents.length === 1 && metaOf(v2.anomalies.ents[0])?.shape === 'diamond' && !v2.anomalies.ents.some((e) => /pulse/.test(e.id)));

	// ── the OSINT layers (OS-DECK-A) ──
	const osMarkWaiting = v2.osint.ents.find((e) => e.id === 'osint:a1a2a3a4-b1b2-4c3c-8d4d-000000000001');
	const osMarkArea = v2.osint.ents.find((e) => e.id === 'osint:a1a2a3a4-b1b2-4c3c-8d4d-000000000002');
	const osWaitingLabel = M.SYM.labelText(metaOf(osMarkWaiting)?.label ?? []);
	check(
		'v2 osint: a tagged neutral disc with the report glyph that clusters; the hover label is the situation\'s name (no status word)',
		!!osMarkWaiting &&
			metaOf(osMarkWaiting)?.kind === 'osint_event' &&
			metaOf(osMarkWaiting).glyph === M.ICONS.kindIcon('osint_event') &&
			metaOf(osMarkWaiting).cluster === true &&
			metaOf(osMarkWaiting).shape === 'disc' &&
			osWaitingLabel === 'Road accident · Sector V (Salt Lake)',
		`${osWaitingLabel} · ${JSON.stringify(metaOf(osMarkWaiting))}`,
	);
	check(
		'v2 osint: ONE decision mark (--v-map-decision) on the report whose DSS waits, the others neutral — and NO decision ROLE on the ring (the role painted a second orange mark; fix round 2, item 10)',
		metaOf(osMarkWaiting)?.role === undefined &&
			metaOf(osMarkArea)?.role === undefined &&
			metaOf(v2.osint.ents.find((e) => e.id === 'osint:a1a2a3a4-b1b2-4c3c-8d4d-000000000004'))?.role === undefined &&
			v2.osint.stats.detail.waiting === 1 &&
			v2.osint.stats.detail.drawn === 3 &&
			v2.osint.tokenReads.includes('--v-map-decision') &&
			!v2.osint.tokenReads.some((n) => /^--v-(act|data|tool)(-|$)/.test(n)),
		`reads=[${v2.osint.tokenReads.filter((n) => n.startsWith('--v-map')).join(' ')}] · roles=${v2.osint.ents.filter(metaOf).map((e) => metaOf(e).role ?? 'none').join(',')} · ${JSON.stringify(v2.osint.stats.detail)}`,
	);
	check(
		'v2 osint: the pick card names the verification state in words (never the raw enum)',
		/Road accident \u00b7 Sector V \(Salt Lake\)/.test(osMarkWaiting.description ?? '') && /Reported \(News-reported\)/.test(osMarkWaiting.description ?? '') && !/NEWS-REPORTED/.test(osMarkWaiting.description ?? ''),
		String(osMarkWaiting.description ?? '').slice(0, 160),
	);
	check(
		'v2 osint: the layer hint carries the city-wide held social count ONCE (never on a per-report view)',
		/2 single-post social reports held city-wide \(never shown\)/.test(v2.osint.stats.hint ?? ''),
		String(v2.osint.stats.hint),
	);
	check(
		'v2 osint: the area-level report draws the same glyph inside its area ring; the state-level row is counted not mapped, never drawn',
		!!osMarkArea && v2.osint.ents.some((e) => e.id === 'osint:area-a1a2a3a4-b1b2-4c3c-8d4d-000000000002') && v2.osint.stats.detail.notMapped === 1 && !v2.osint.ents.some((e) => /000000000003/.test(e.id)),
		JSON.stringify(v2.osint.stats.detail),
	);
	check(
		'OSINT-8: a district-level report says what is drawn — the marker and its ring sit at the district\'s reference point, never "drawn as an area"',
		(() => {
			const ring = v2.osint.ents.find((e) => e.id === 'osint:area-a1a2a3a4-b1b2-4c3c-8d4d-000000000002');
			const pick = String(osMarkArea?.description ?? '');
			const ringPick = String(ring?.description ?? '');
			return /reference point/.test(pick) && !/drawn as an area/i.test(pick) && /reference point/.test(ringPick) && /not the area the report covers/.test(ringPick);
		})(),
		String(osMarkArea?.description ?? '').slice(0, 200),
	);
	check(
		'v2 osint: the area ring is a draped neutral line (never a hue, never a pin); under the selection it dims with its marker (unrelated 0.5)',
		(() => {
			const ring = v2.osint.ents.find((e) => e.id === 'osint:area-a1a2a3a4-b1b2-4c3c-8d4d-000000000002')?.polyline;
			return !!ring && ring.clampToGround === true && cssOfColor(ring.material?.color ?? ring.material) === M.SYM.inkAlpha(TOKENS['--v-map-marker'], 0.4 * M.V.MAP_OPACITY.unrelated);
		})(),
	);
	{
		const legacyWaiting = legacy.osint.ents.find((e) => e.id === 'osint:a1a2a3a4-b1b2-4c3c-8d4d-000000000001');
		const legacyNeutral = legacy.osint.ents.find((e) => e.id === 'osint:a1a2a3a4-b1b2-4c3c-8d4d-000000000004');
		check(
			'legacy osint: the same neutral markers and the area ring; both chromes draw',
			legacy.osint.ents.some((e) => /^osint:a1a2a3a4/.test(e.id) && e.billboard && e.label) &&
				legacy.osint.ents.some((e) => /^osint:area-/.test(e.id) && e.polyline?.clampToGround === true) &&
				legacy.osint.stats.count === 3 &&
				v2.osint.stats.count === 3,
			`${legacy.osint.ents.length} legacy ents · ${v2.osint.ents.length} v2 ents`,
		);
		check(
			'legacy osint: the waiting decision draws its decision mark too, with NO ring role (the dot is the one mark; fix round 2, item 10)',
			!!legacyWaiting && !!legacyNeutral && metaOf(legacyWaiting)?.role === undefined && metaOf(legacyNeutral)?.role === undefined && /Reported \(News-reported\)/.test(legacyWaiting.description ?? '') && !/NEWS-REPORTED/.test(legacyWaiting.description ?? ''),
			`waiting role=${metaOf(legacyWaiting)?.role} · neutral role=${metaOf(legacyNeutral)?.role} · ${legacy.osint.stats.detail?.waiting} waiting`,
		);
		// R3b: the legacy decision mark is BAKED INTO THE IMAGE (markerBillboard's decision
		// state keys a distinct markerImage painting). A clean-cache legacy draw paints TWO
		// marker images — the waiting one's and the neutral one's — never one.
		M.SYM.clearMapImages();
		{
			const viewer2 = makeViewer();
			const inst2 = M.IDX.GODS_EYE_LAYERS.find((l) => l.id === 'osint').create();
			inst2.init({ cesium: makeCesium({ cartesianClass: true }), viewer: viewer2, fetchJson: async () => ({ zones: [], events: [] }), notify() {} });
			inst2.activate();
			for (let i = 0; i < 10; i++) await tick();
			const painted = M.SYM.mapImageCacheSize();
			inst2.deactivate();
			for (let i = 0; i < 5; i++) await tick();
			M.SYM.clearMapImages();
			check('legacy osint: the decision state paints its own marker image (waiting + neutral, two cache keys — R3b)', painted === 2, `${painted} painted marker images`);
		}
		// fix round 2, item 8: the pick card is LOCALIZED — a language switch redraws (ops.lang
		// rides the layer's draw signature) and the HI card reads the HI words, never the EN ones
		{
			const en = M.ops.lang;
			M.ops.lang = 'hi';
			const hi = await drawLayer(M.IDX.GODS_EYE_LAYERS.find((l) => l.id === 'osint'), 'v2');
			M.ops.lang = en;
			const hiWaiting = hi.ents.find((e) => e.id === 'osint:a1a2a3a4-b1b2-4c3c-8d4d-000000000001');
			check(
				'v2 osint HI: the pick card redraws in HI (report word, credibility, place sentence — never the EN words)',
				/रिपोर्ट किया गया \(समाचार में रिपोर्ट\)/.test(hiWaiting?.description ?? '') && /विश्वसनीयता/.test(hiWaiting?.description ?? '') && !/Reported \(News-reported\)/.test(hiWaiting?.description ?? '') && !/credibility/.test(hiWaiting?.description ?? ''),
				String(hiWaiting?.description ?? '').slice(0, 200),
			);
			check(
				'v2 osint HI: the doubled toponym is gone in every language (the label already names the place)',
				!/at Sector V \(Salt Lake\)/.test(hiWaiting?.description ?? '') && !/at Sector V \(Salt Lake\)/.test(osMarkWaiting?.description ?? ''),
				String(hiWaiting?.description ?? '').slice(0, 120),
			);
		}
	}
	{
		const osLayer = M.IDX.GODS_EYE_LAYERS.find((l) => l.id === 'osint');
		const plLayer = M.IDX.GODS_EYE_LAYERS.find((l) => l.id === 'places');
		const osInst = osLayer.create();
		osInst.init({ cesium: makeCesium(), viewer: makeViewer(), fetchJson: async () => ({}), notify() {} });
		const plInst = plLayer.create();
		plInst.init({ cesium: makeCesium(), viewer: makeViewer(), fetchJson: async () => ({}), notify() {} });
		check(
			'urnOf: every osint / places pick maps to its C-C URN (the area ring to the same report, the place to its slug)',
			osInst.urnOf('osint:a1a2a3a4-b1b2-4c3c-8d4d-000000000001') === 'osint_event:a1a2a3a4-b1b2-4c3c-8d4d-000000000001' &&
				osInst.urnOf('osint:area-a1a2a3a4-b1b2-4c3c-8d4d-000000000002') === 'osint_event:a1a2a3a4-b1b2-4c3c-8d4d-000000000002' &&
				osInst.urnOf('evt:mark-x') === null &&
				plInst.urnOf('place:sector_v_salt_lake_106') === 'place:sector_v_salt_lake_106' &&
				plInst.urnOf('osint:x') === null,
		);
	}
	const plMark = v2.places.ents.find((e) => e.id === 'place:sector_v_salt_lake_106');
	check(
		'v2 places: a smaller neutral marker with the map-marker glyph, tagged for the pass; the layer is off by default',
		!!plMark && metaOf(plMark)?.glyph === M.ICONS.kindIcon('place') && metaOf(plMark).size === 17 && M.IDX.GODS_EYE_LAYERS.find((l) => l.id === 'places')?.defaultOn === false,
		JSON.stringify(metaOf(plMark)),
	);

	check('legacy invariance: the legacy anomaly still pulses with its labelled dot', legacy.anomalies.ents.some((e) => /pulse/.test(e.id)) && legacy.anomalies.ents.some((e) => e.label));
	check('v2 units and dispatch: neutral markers with their type glyphs', metaOf(v2.units.ents[0])?.glyph === M.ICONS.kindIcon('unit') && v2.dispatch.ents.some((e) => metaOf(e)?.glyph === M.ICONS.kindIcon('dispatch')));
	check('v2 signals: a junction is a small neutral dot', v2.signals.ents.length > 0 && v2.signals.ents.every((e) => metaOf(e)?.shape === 'dot' && metaOf(e).kind === 'junction'));

	// every LayerTree row drawing emulated data carries the compact provenance glyph (SPEC §5.3, §9.2; ethics rule 7; review r2):
	// the canvas gives a row `emulated` when its layer publishes an emulated count
	const EMULATING = ['cameras', 'traces', 'enforcement', 'units', 'dispatch', 'convoy'];
	const prov = EMULATING.map((id) => [id, v2[id].stats.detail?.emulated]);
	check("v2 provenance: every layer that draws emulated data publishes its emulated count (the row's Emulated glyph)", prov.every(([, n]) => typeof n === 'number' && n > 0), JSON.stringify(Object.fromEntries(prov)));
	check(
		'v2 provenance: the counts are the truth — 2 emulated cameras, 1 vehicle on emulated reads, 2 waiting decisions on emulated rows, both dispatches',
		v2.cameras.stats.detail.emulated === M.godsEye.cameras.filter((c) => c.source === 'emulated').length && v2.traces.stats.detail.emulated === 1 && v2.enforcement.stats.detail.emulated === 2 && v2.dispatch.stats.detail.emulated === v2.dispatch.stats.count,
		JSON.stringify(Object.fromEntries(prov)),
	);
	const legacyProv = ['cameras', 'traces', 'enforcement', 'units', 'dispatch', 'convoy'].filter((id) => 'emulated' in (legacy[id].stats.detail ?? {}));
	check('legacy invariance: the legacy coverage stats gain no emulated count (the chips read as before)', legacyProv.length === 0, legacyProv.join(', '));

	const pv = v2.pursuit;
	const chokes = pv.ents.filter((e) => /^pursuit:choke-/.test(e.id));
	check('v2 pursuit: the ranked chokes are rounded squares with the junction glyph, "Choke n"', chokes.length === 2 && chokes.every((e) => metaOf(e)?.shape === 'square' && metaOf(e).glyph === M.ICONS.kindIcon('junction')) && M.SYM.labelText(metaOf(chokes[0]).label) === 'Choke 1');
	check('v2 pursuit: a likely-passed choke is dimmed (its label on hover)', metaOf(pv.ents.find((e) => e.id === 'pursuit:choke-8'))?.passed === true && metaOf(pv.ents.find((e) => e.id === 'pursuit:choke-8')).labelWhen === 'hover');
	check('v2 pursuit: the observed heading is a red arrow from the last read', ['pursuit:heading', 'pursuit:heading-casing', 'pursuit:heading-head'].every((id) => pv.ents.some((e) => e.id === id)) && cssOfColor(pv.ents.find((e) => e.id === 'pursuit:heading').polyline.material) === TOKENS['--v-map-alert']);
	check('v2 pursuit: no comet, ring or marching arc (no ambient motion)', !pv.ents.some((e) => /pursuit:(trace|comet|ring|veil|future)/.test(e.id)) && pv.audit.floating === 0);
	check('legacy invariance: the legacy pursuit still draws its ring and marching arc', legacy.pursuit.ents.some((e) => e.id === 'pursuit:ring') && legacy.pursuit.ents.some((e) => e.id === 'pursuit:future'));
	const drapes = Object.entries(v2).filter(([id]) => id !== 'pursuit').map(([id, d]) => [id, M.drapeAudit({ entities: { getById: (x) => d.ents.find((e) => e.id === x) } }, d.ents.map((e) => e.id))]);
	check('v2: every graphic is draped or clamped (floating 0 on the 3D city)', drapes.every(([, a]) => a.floating === 0), drapes.map(([id, a]) => `${id}:${a.floating}`).join(' '));

	// ── the kind filter hides every layer's own lines too (SPEC §5.3; review r1) ──
	// The pass hides the tagged markers by kind (markerStyle().show); each layer
	// skips its lines, zones and routes for the kinds left out: the flow network
	// ('segment'), event spines, superseded routes and zones ('event'), the
	// convoy's route and detours ('convoy'), the selected vehicle's track and the
	// pursuit heading ('vehicle'), a unit's way to its waypoint ('dispatch').
	const LINES = /^(seg:|evt:(spine|old|zone|rim)-|cvy:(ahead|done|detour)-|veh:trace-|dsp:line-|pursuit:heading)/;
	const lineIds = (set) => Object.values(set).flatMap((d) => d.ents.map((e) => e.id)).filter((id) => LINES.test(id));
	const shownBefore = lineIds(v2);
	check(
		'kind filter (the fixture draws them unfiltered): flow, spines, a zone, the convoy route and detour, the track, the dispatch line, the heading',
		['seg:', 'evt:spine-', 'evt:zone-', 'evt:rim-', 'cvy:ahead-', 'cvy:done-', 'cvy:detour-', 'veh:trace-', 'dsp:line-', 'pursuit:heading'].every((p) => shownBefore.some((id) => id.startsWith(p))),
		`${shownBefore.length} line entities`,
	);
	const camerasOnly = { ...selectedView, kinds: new Set(['camera']), version: 4 };
	const realNow = Date.now;
	Date.now = () => NOW; // the legacy comparison below reads pick texts with ages in them
	const filtered = {};
	const legacyFiltered = {};
	const legacyAgain = {};
	for (const layer of layers) {
		filtered[layer.id] = await drawLayer(layer, 'v2', camerasOnly);
		legacyFiltered[layer.id] = await drawLayer(layer, 'legacy', camerasOnly);
		legacyAgain[layer.id] = await drawLayer(layer, null);
	}
	filtered.pursuit = pursuitDraw('v2', camerasOnly.kinds);
	legacyFiltered.pursuit = pursuitDraw('legacy', camerasOnly.kinds);
	legacyAgain.pursuit = pursuitDraw(null);
	Date.now = realNow;
	const leaked = lineIds(filtered);
	check("kind filter {'camera'}: NO layer draws a flow, spine, zone, route, detour, track, dispatch or heading line", leaked.length === 0, leaked.join(', ') || `${shownBefore.length} → 0 line entities`);
	const kept = ['cam:', 'veh:mark-', 'evt:mark-', 'cvy:m-1', 'cvy:hold-', 'pursuit:choke-'].filter((p) => !Object.values(filtered).some((d) => d.ents.some((e) => e.id.startsWith(p) && M.SYM.markerMeta(e))));
	check('kind filter: the tagged markers stay for the pass, which hides them by kind (markerStyle().show)', kept.length === 0, kept.join(', ') || 'cameras, the pin, event markers, the convoy and its hold, the chokes');
	const legacySame = Object.keys(legacyAgain).filter((id) => JSON.stringify(legacyFiltered[id].ents.map((e) => normGraph(e))) !== JSON.stringify(legacyAgain[id].ents.map((e) => normGraph(e))));
	check('kind filter: the legacy chrome ignores it (every layer draws exactly what it draws without one)', legacySame.length === 0, legacySame.join(', ') || `${Object.keys(legacyAgain).length} layers + the pursuit overlay identical`);
	const detour = v2.convoy.ents.find((e) => /^cvy:detour-/.test(e.id));
	const detourInk = cssOfColor(detour?.polyline?.material?.color);
	check(
		'v2 convoy: a proposed detour previews DASHED in the route turquoise, never the decision orange (SPEC §2.4: orange stays off lines)',
		detour?.polyline?.material?.dashed === true && rgbOf(detourInk) === routeInk && rgbOf(detourInk) !== rgbOf(M.SYM.inkAlpha(TOKENS['--v-map-decision'], 1)),
		detourInk,
	);

	// ── 11. the label policy: no label or pick text stacks status words ────────
	const STATUS = /\b(STOLEN|PENDING|EMULATED|SIMULATED|WITHHELD|APPROVED|SUPERSEDED|FLAGGED|WATCH|RECOMMENDED|LIKELY PASSED|NO FINE|NO DATA|CHOKE|ESCORT LIVE|ACTIVE|SPEEDING|RED LIGHT)\b/;
	const labelTexts = drawnEnts.map(metaOf).filter((m) => m?.label?.length).map((m) => M.SYM.labelText(m.label));
	check('label policy: no v2 label stacks status words', labelTexts.every((t) => !STATUS.test(t) && (t.match(/ · /g) ?? []).length <= 1), labelTexts.join(' | '));
	const texts = drawnEnts.map((e) => String(e.description ?? '')).filter(Boolean);
	const stacked = texts.filter((t) => / · [A-Z]{3,}/.test(t) || /\b(STOLEN|PENDING|WITHHELD|SUPERSEDED|EMULATED|SIMULATED FEED|NO DATA|LIKELY PASSED)\b/.test(t));
	check('label policy: no v2 pick text stacks status words', stacked.length === 0, stacked.slice(0, 2).join(' | ') || `${texts.length} texts`);

	// a read's time: the clock alone today, dated for an older read (the formatter's stamp; review r1)
	const hopTimes = v2.traces.ents.filter((e) => /^veh:hop-/.test(e.id)).map((e) => metaOf(e).label?.[1]);
	check("v2 reads: each read's time carries the draw time as its anchor (dated when it is not today's)", hopTimes.length === 3 && hopTimes.every((p) => typeof p?.anchor === 'number'));
	const HOUR = 3_600_000;
	const today = M.SYM.labelText([{ id: 'EM-CAM-03' }, { time: NOW, anchor: NOW }]);
	const older = M.SYM.labelText([{ id: 'EM-CAM-03' }, { time: NOW - 30 * HOUR, anchor: NOW }]);
	check('v2 reads: "EM-CAM-03 22:08" today, "EM-CAM-03 23 Oct 22:08" for a read from another day', /^EM-CAM-03 \d{2}:\d{2}$/.test(today) && /^EM-CAM-03 \d{1,2} [A-Z][a-z]{2} \d{2}:\d{2}$/.test(older), `${today} | ${older}`);

	// the painted-image cache is bounded (labels are keyed by their text: plates, ids, times; review r1)
	const { labelImage, mapImageCacheSize, MAP_IMAGE_CACHE_MAX } = M.SYM;
	const cold = labelImage([{ text: 'cold label' }]);
	const hot = labelImage([{ text: 'hot label' }]);
	for (let i = 0; i < MAP_IMAGE_CACHE_MAX + 200; i++) {
		labelImage([{ id: `MH01AB${String(i).padStart(4, '0')}` }]);
		if (i % 50 === 0) labelImage([{ text: 'hot label' }]);
	}
	check(
		`symbols: the image cache stays within ${MAP_IMAGE_CACHE_MAX} entries, least recently used out (a hot image stays, a cold one is repainted)`,
		MAP_IMAGE_CACHE_MAX === 512 && mapImageCacheSize() <= MAP_IMAGE_CACHE_MAX && !!hot && labelImage([{ text: 'hot label' }]) === hot && !!cold && labelImage([{ text: 'cold label' }]) !== cold,
		`${mapImageCacheSize()} cached`,
	);

	delete globalThis.document;
	delete globalThis.getComputedStyle;
}

// ── 12. legacy invariance against a RECORDED baseline (review r1) ────────────
//
// The legacy chrome must draw what it drew before UI-S3. Every legacy layer
// and the legacy pursuit overlay draw one fixed city picture — a frozen
// clock, the command theme's real token values — and each entity's
// normalized graphics (normGraph: ids, materials, colours, widths, label
// text and font, pick text; a time-varying callback reduced to its marker)
// is fingerprinted, with each layer's coverage stats (the chip's count and
// hint), and compared with the record below. The record is this WP's legacy
// output, taken after a differential run against the pre-WP base showed the
// only differences to be the declared label font (monospace → the UI face,
// the S1A style lint) and two animation callbacks sampled at different
// instants. A legacy change that is MEANT updates its fingerprints (run with
// --record-legacy and paste the printed object) and says so in its review;
// the normalized output of a mismatching layer is written to
// tests/artifacts/canvas-layers-legacy-<layer>.json for the diff.
// 2026-10-26 (V3 P0 integration): 37 entity fingerprints re-recorded — ONLY the command theme's --v-* colour values
// changed (V3-SPEC §4.2); every layer's stats fingerprint is unchanged.
// 2026-10-27 (neutral grounds): fingerprints re-recorded — ONLY colour values changed (neutral grey flow ramp and
// casings, corridor events in the accent blue instead of violet, a white selection); every stats fingerprint unchanged.
// 2026-10-28 (Marathi replaces Gujarati): fingerprints re-recorded — ONLY the label font stack changed (the token
// stack now reads 'Noto Sans Bengali', 'Noto Sans Devanagari' where it read 'Noto Sans Devanagari', 'Noto Sans
// Gujarati'; a differential run with the previous tokens.ts passes unchanged); every stats fingerprint unchanged.

// 2026-10-28 (Kolkata): fingerprints re-recorded — the fixed city picture moved to Kolkata: coordinates on the
// Kolkata network, place and road names by id (cities/kolkata/network.json), WB registration marks; colours,
// widths, materials and the layers' logic unchanged.

// 2026-10-28 (int-ops): the waterlogging and forecast layers join the record — each draws nothing from the fixed
// picture (no hydro or forecast rows in it), so only their coverage stats are fingerprinted; every other entry unchanged.
// 2026-10-28 (city-feeds): the air-quality and cyclone layers join the record — each draws nothing from the fixed
// picture (no city-feeds answer in it), so only their coverage stats are fingerprinted; every other entry unchanged.
// 2026-10-29 (live map): the City Pack places and the live readings join the record — each draws nothing from the
// fixed picture (no primitive collections in the test double), so only their coverage stats are fingerprinted; the
// flow layer's stats gain its moving-dot and V/C counts; every legacy entity fingerprint unchanged.
// 2026-10-30 (lang, Mumbai): the label font stack drops 'Noto Sans Bengali' (Marathi is Devanagari, one face with Hindi).
// 2026-10-30 (Mumbai): fingerprints re-recorded — the fixed picture's registration marks are MH (WB 06 → MH 47, the
// other RTO numbers kept) and the cyclone hint names the city from the pack and the Arabian Sea; coordinates, colours,
// widths, materials and the layers' logic unchanged.
const LEGACY_RECORD = {
	"events": {
		"ents": {
			"evt:mark-ev-pm": "92016f51aefa",
			"evt:mark-ev-pu": "e9800a083419",
			"evt:rim-ev-pu": "504ce3498897",
			"evt:spine-ev-pm-1005": "299c15ada894",
			"evt:spine-ev-pm-1006": "d7e5a0b7e352",
			"evt:spine-ev-pm-1015": "996094aac37d",
			"evt:spine-ev-pu-1006": "822855b10246",
			"evt:zone-ev-pu": "2883acf91401"
		},
		"stats": "68fce663c8ff"
	},
	"flow": {
		"ents": {
			"seg:1005": "d8dfa88e1629",
			"seg:1006": "90c06769e31f",
			"seg:1015": "2742ac3bfa15"
		},
		"stats": "f4cdc722f001"
	},
	"waterlog": {
		"ents": {},
		"stats": "86507be7e01c"
	},
	"forecast": {
		"ents": {},
		"stats": "6d993a9e8762"
	},
	"traces": {
		"ents": {
			"veh:hop-veh-1-1": "0aed00762cc5",
			"veh:hop-veh-1-2": "6ae4132937f6",
			"veh:hop-veh-1-3": "e7db41387652",
			"veh:hop-veh-1-4": "085b6b95539e",
			"veh:mark-veh-1": "fcbcc9d89814",
			"veh:mark-veh-2": "5240b582bb81",
			"veh:trace-veh-1": "d64fc723ca00"
		},
		"stats": "9135137131c6"
	},
	"enforcement": {
		"ents": {
			"rec:r-1": "5d1fcdca3607",
			"rec:r-2": "5359825e9aa6",
			"rec:r-3": "f9d55f765c72",
			"rec:r-4": "55b34be3438d"
		},
		"stats": "ae620314b64a"
	},
	"signals": {
		"ents": {
			"sig:15": "31ff88a17dfc",
			"sig:8": "39f4f4427c7b"
		},
		"stats": "257772cd33df"
	},
	"units": {
		"ents": {
			"unit:U-2": "b5070decc29c"
		},
		"stats": "169990fcf739"
	},
	"dispatch": {
		"ents": {
			"dsp:line-d-2": "9d5cbdb68f66",
			"dsp:ring-d-1": "5de08208bbd4",
			"dsp:ring-d-2": "3f9dc6477958",
			"dsp:wp-d-1": "9c43b2e844bd",
			"dsp:wp-d-2": "790ca02dc4d9"
		},
		"stats": "d5f6e753ebc4"
	},
	"convoy": {
		"ents": {
			"cvy:detour-m-1-a-1-1015": "9f1a83a814a6",
			"cvy:hdg-m-1": "b4404e0e1375",
			"cvy:m-1": "ab45d1ae4f95",
			"cvy:ring-m-1": "59d4c06791d9"
		},
		"stats": "d38bcda4d817"
	},
	"cameras": {
		"ents": {
			"cam:CAM-77": "19d405d1a2d0",
			"cam:EM-CAM-01": "55a40f07a36d",
			"cam:EM-CAM-02": "28fd824d0be5"
		},
		"stats": "ab0b8bee337f"
	},
	"anomalies": {
		"ents": {
			"anm:7": "fdfadf69090f"
		},
		"stats": "26ce0455d624"
	},
	"osint": {
		"ents": {
			"osint:a1a2a3a4-b1b2-4c3c-8d4d-000000000001": "1bf037e94e9c",
			"osint:a1a2a3a4-b1b2-4c3c-8d4d-000000000002": "882fb765ef78",
			"osint:area-a1a2a3a4-b1b2-4c3c-8d4d-000000000002": "8f84db8f375a"
		},
		"stats": "1e483ba83510"
	},
	"air": {
		"ents": {},
		"stats": "2d557e31b97f"
	},
	"cyclone": {
		"ents": {},
		"stats": "f4616f3ca950"
	},
	"places": {
		"ents": {
			"place:sector_v_salt_lake_106": "85ba31d7415f"
		},
		"stats": "344cd5eb5c4d"
	},
	"landmarks": {
		"ents": {},
		"stats": "29c64145b87a"
	},
	"livevalues": {
		"ents": {},
		"stats": "0b21936679dd"
	},
	"pursuit": {
		"ents": {
			"pursuit:choke-15": "77b4729ddfb1",
			"pursuit:comet": "2b4e63ca1d86",
			"pursuit:future": "934f8d0d4e5f",
			"pursuit:onward-1015": "033739d60c02",
			"pursuit:ring": "f7dcf11a514e",
			"pursuit:sight": "080621e62b2e",
			"pursuit:trace": "3e1af54494f1",
			"pursuit:veil": "f60b80af9a80"
		},
		"stats": "7d4fd20ab1af"
	}
};

{
	const { createHash } = await import('node:crypto');
	const { writeFileSync } = await import('node:fs');
	const fp = (v) => createHash('sha256').update(JSON.stringify(v)).digest('hex').slice(0, 12);
	const T0 = Date.parse('2026-10-24T06:30:00Z'); // 12:00 IST
	const MIN = 60_000;
	const realNow = Date.now;
	Date.now = () => T0;
	const TK = M.TOK.TOKENS.command;
	globalThis.document = { documentElement: { dataset: {} }, hidden: false, createElement: () => ({ getContext: () => null }) };
	globalThis.getComputedStyle = () => ({ getPropertyValue: (name) => TK[name] ?? '' });

	// one fixed city picture (fictional names; a protected movement with its convoy and a hold
	// proposal, a pursuit with two chokes, a stolen and a watched vehicle, e-challans, an
	// anomaly, two dispatches, cameras, signals, the flow network on both planes)
	const seg = (lon) => [
		[lon, 22.5582],
		[lon + 0.004, 22.5622],
	];
	M.godsEye.segments.length = 0;
	M.godsEye.segments.push(
		{ segmentId: 1005, roadName: 'Strand Road', coordinates: seg(88.3499), geometryBasis: 'schematic' },
		{ segmentId: 1006, roadName: 'Indira Gandhi Sarani (Red Road)', coordinates: seg(88.3599), geometryBasis: 'osm' },
		{ segmentId: 1015, roadName: 'Station Road', coordinates: seg(88.37), geometryBasis: 'osm_display' },
	);
	const R = M.cityRegistry.rows;
	for (const k of Object.keys(R)) delete R[k];
	const ent = (kind, id, over = {}) => ({ urn: `${kind}:${id}`, kind, id, label: `${kind} ${id}`, lon: 88.3499, lat: 22.5632, state: null, band: null, source: 'emulated', t: T0 - 5 * MIN, ageSec: 300, links: [], props: {}, ...over });
	R.recommendation = [
		ent('recommendation', 'r-1', { state: 'pending', links: ['vehicle:veh-1'], props: { rule_id: 'R_STOLEN_SIGHTING', vehicle_id: 'veh-1', camera_id: 'EM-CAM-03', plate: 'MH47EM9001' } }),
		ent('recommendation', 'r-2', { state: 'pending', lon: 88.3549, links: ['vehicle:veh-1'], props: { rule_id: 'R_STOLEN_SIGHTING', vehicle_id: 'veh-1', camera_id: 'EM-CAM-01', plate: 'MH47EM9001' } }),
		ent('recommendation', 'r-3', { state: 'pending', lon: 88.3599, props: { rule_id: 'R_SPD_SEGMENT', vehicle_id: 'veh-2', camera_id: 'EM-CAM-05', plate: 'MH01AB1234', evidence: { speed_kmh: 92, speed_limit_kmh: 60, road_name: 'Strand Road' } } }),
		ent('recommendation', 'r-4', { state: 'approved', lon: 88.3649, props: { rule_id: 'R_SPD_SEGMENT', vehicle_id: 'veh-1', camera_id: 'EM-CAM-03', decided_by: 'duty-officer-1', evidence: { speed_kmh: 80, speed_limit_kmh: 60 } } }),
	];
	R.anomaly = [ent('anomaly', '7', { state: 'high', t: T0, props: { anomaly_type: 'speed_jump', count_15m: 6, data_quality: 'synthetic', road_name: 'Strand Road' } })];
	R.dispatch = [
		ent('dispatch', 'd-1', { state: 'requested', props: { agency: 'police', unit_id: 'U-1', waypoint_junction: 15, event_title: 'Pursuit' } }),
		ent('dispatch', 'd-2', { state: 'en_route', lon: 88.37, props: { agency: 'ems', unit_id: 'U-2', event_title: 'Pursuit', decided_by: 'duty-officer-2' } }),
	];
	R.unit = [ent('unit', 'U-2', { lon: 88.4102, lat: 22.5536, props: { agency: 'ems' } })];
	R.convoy = [ent('convoy', 'm-1', { label: 'Z movement', state: 'moving', t: T0, props: { speed_kmh: 38, heading: 45, progress: 0.31, event_id: 'ev-pm', segment_id: 1015 } })];
	// the OSINT picture (OS-DECK-A, recorded here like every other legacy layer): a report whose
	// DSS waits (the decision mark), a district-level area report (the ring), and one place
	R.osint_event = [
		ent('osint_event', 'a1a2a3a4-b1b2-4c3c-8d4d-000000000001', {
			label: 'Road accident · Sector V (Salt Lake)',
			source: 'osint',
			t: T0 - 40 * MIN,
			props: {
				area_level: false,
				verification_state: 'NEWS-REPORTED',
				credibility: 0.65,
				toponym: 'Sector V (Salt Lake)',
				dss: { dss_id: 'd-1', state: 'proposed', top_coa_id: 'coa_base', top_coa_label: 'Monitor only (do nothing)', generated_at: new Date(T0 - 5 * MIN).toISOString(), horizon_min: 120, expires_at: new Date(T0 + 115 * MIN).toISOString() },
			},
		}),
		ent('osint_event', 'a1a2a3a4-b1b2-4c3c-8d4d-000000000002', {
			label: 'Weather hazard · Mumbai City district',
			lon: 88.3413,
			lat: 22.5607,
			source: 'osint',
			t: T0 - 3 * 60 * MIN,
			props: { area_level: true, verification_state: 'OFFICIAL-VERIFIED', credibility: 0.95, toponym: 'Mumbai City (district)' },
		}),
	];
	R.place = [ent('place', 'sector_v_salt_lake_106', { label: 'Sector V (Salt Lake)', lon: 88.4414, lat: 22.5799, source: 'osint', t: T0 - 40 * MIN, props: { feature_type: 'landmark', osint_event_count: 1 } })];
	M.ops.officerOn = false;
	M.ops.watchlist = [{ vehicleId: 'veh-1', lawfulBasis: 'stolen_vehicle_fir' }];
	const ev = (eventId, eventKind, segs) => ({
		eventId,
		name: eventKind === 'vehicle_pursuit' ? 'PURSUIT — stolen MH47EM9001' : 'Z protected movement',
		eventKind,
		state: 'active',
		source: 'live-events-api',
		routeSegmentIds: segs,
		routes: [],
		routeHistory: [],
		windowStart: new Date(T0 - 60 * MIN).toISOString(),
		windowEnd: null,
		band: 'GREEN',
		currentPhase: null,
		description: null,
	});
	M.ops.events = [ev('ev-pm', 'protected_movement', [1005, 1015, 1006]), ev('ev-pu', 'vehicle_pursuit', [1006])];
	const plan = { ...PLAN, vehicleId: 'veh-1', latestSighting: { ...PLAN.latestSighting, t: new Date(T0 - 2 * MIN).toISOString() } };
	M.ops.interception = plan;
	M.godsEye.vehicles.length = 0;
	M.godsEye.vehicles.push(
		{ vehicleId: 'veh-1', plate: 'MH47EM9001', earmarkState: 'flagged', retentionUntil: null, lawfulBasis: 'stolen_vehicle_fir', lastSighting: { t: T0 - MIN, lon: 88.3549, lat: 22.5652, source: 'emulated_anpr', cameraId: 'EM-CAM-01', hit: 'stolen_vehicle' } },
		{ vehicleId: 'veh-2', plate: 'MH01AB1234', earmarkState: 'watch', retentionUntil: null, lawfulBasis: null, lastSighting: { t: T0 - 3 * MIN, lon: 88.3599, lat: 22.5582, source: 'live_anpr', cameraId: 'EM-CAM-05', hit: null } },
	);
	const hop = (seq, ago, lon, lat, cameraId) => ({ seq, t: T0 - ago * MIN, lon, lat, cameraId, speedKmh: 40, source: 'emulated_anpr', sightingId: `s-${seq}` });
	const hops = [hop(1, 50, 88.3299, 22.5482, 'EM-CAM-09'), hop(2, 20, 88.4102, 22.5536, 'EM-CAM-02'), hop(3, 10, 88.3499, 22.5632, 'EM-CAM-03'), hop(4, 1, 88.3549, 22.5652, 'EM-CAM-01')];
	M.godsEye.traces.clear();
	M.godsEye.traces.set('veh-1', { vehicleId: 'veh-1', coordinates: hops.map((h) => [h.lon, h.lat]), hops, latestT: T0 - MIN, via: 'city', source: 'emulated_anpr', status: null, disclosure: null });
	M.godsEye.units.length = 0;
	M.godsEye.units.push({ unitId: 'U-2', agency: 'ems', lon: 88.3509, lat: 22.5592, emulated: true, status: 'en_route', etaSec: 90, progress: 0.4, label: 'EMS 12', arrived: false, assignedEventId: 'ev-pu', dispatchId: 'd-2', speedKmh: 30, source: 'emulated' });
	M.godsEye.cameras.length = 0;
	M.godsEye.cameras.push(
		{ cameraId: 'EM-CAM-01', label: 'Moulali gate', kind: 'anpr', lon: 88.3549, lat: 22.5652, junctionId: 15, reads15m: 3, hits15m: 1, lastReadT: T0 - MIN, status: null, source: 'emulated' },
		{ cameraId: 'EM-CAM-02', label: null, kind: 'anpr', lon: 88.3549, lat: 22.5652, junctionId: 15, reads15m: 0, hits15m: 0, lastReadT: null, status: 'quiet', source: 'emulated' },
		{ cameraId: 'CAM-77', label: 'Strand Road east', kind: 'cctv', lon: 88.3599, lat: 22.5682, junctionId: null, reads15m: 12, hits15m: 0, lastReadT: T0 - 2 * MIN, status: null, source: 'osm' },
	);
	M.godsEye.signals.length = 0;
	M.godsEye.signals.push(
		{ junctionId: 15, name: 'Sea Link, Worli end', lon: 88.3499, lat: 22.5682, phaseIndex: 1, phaseLost: false, greenSec: 30, cycleSec: 90, activePhase: 'NS', phaseMovements: ['NS'], movementStates: { NS: 'green' }, remainingSec: 12, offsetSec: 0, greenRatio: 0.33, source: 'osm_assumed' },
		{ junctionId: 8, name: null, lon: 88.3599, lat: 22.5582, phaseIndex: null, phaseLost: true, greenSec: null, cycleSec: 60, activePhase: 'lost', phaseMovements: [], movementStates: { through: 'amber' }, remainingSec: null, offsetSec: 0, greenRatio: null, source: 'sim' },
	);
	M.escortFollower.movementId = 'm-1';
	M.escortFollower.status = { status: 'running', pendingApprovals: [{ approvalId: 'a-1', action: 'hold_short', reason: 'congestion 86 %', raisedAt: T0, tier: 'strategic', confidence: 0.81, segmentIds: [1006], detourSegmentIds: [1015], detourM: 1200, remainingM: 3400, simulated: true }] };
	const obs = (sid, speed, cong, ageSec = 5) => ({ segment_id: sid, speed_kmh: speed, congestion_idx: cong, timestamp_ms: T0 - ageSec * 1000, data_quality: 'synthetic', source: 'signal-ingress', origin: 'live', road_name: null });
	globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ observations: [obs(1005, 41, 0.35), obs(1006, 8, 0.95)], emulated_observations: [{ ...obs(1015, 12, 0.85), origin: 'emulated' }], zones: [], events: [], hops }) });
	const ZONE = [{ event_id: 'ev-pu', state: 'active', zone_geojson: { type: 'Polygon', coordinates: [[[88.3499, 22.5582], [88.3599, 22.5582], [88.3599, 22.5682], [88.3499, 22.5582]]] } }];

	const got = {};
	const dumps = {};
	for (const layer of M.IDX.GODS_EYE_LAYERS) {
		if (layer.id === 'photoreal-3d') continue;
		const viewer = makeViewer();
		const inst = layer.create();
		inst.init({ cesium: makeCesium({ cartesianClass: true }), viewer, fetchJson: async () => ({ zones: [], events: ZONE }), notify() {} });
		inst.activate();
		for (let i = 0; i < 10; i++) await tick();
		inst.refresh?.();
		for (let i = 0; i < 10; i++) await tick();
		const ents = [...viewer.byId.values()].map((e) => normGraph(e)).sort((a, b) => String(a.id).localeCompare(String(b.id)));
		const stats = normGraph(inst.coverageStats());
		dumps[layer.id] = { ents, stats };
		got[layer.id] = { ents: Object.fromEntries(ents.map((e) => [e.id, fp(e)])), stats: fp(stats) };
		inst.deactivate();
		for (let i = 0; i < 5; i++) await tick();
	}
	{
		const viewer = makeViewer();
		const overlay = M.createPursuitOverlay(makeCesium({ cartesianClass: true }), viewer);
		overlay.show({
			plan,
			trace: TRACE,
			segments: M.godsEye.segmentById,
			officer: false,
			detail: { eventId: 'evt-1', vehicleId: 'veh-1', sightingId: 's-1', cameraId: 'EM-CAM-03', sightingAgeSec: 30, stale: false, staleAfterSec: 600, seedSegmentId: 1015, direction: { basis: 'heading', againstOneway: false, onwardSegmentIds: [1015], towardsJunctionIds: [15] }, chokes: [{ junctionId: 15, name: 'Sea Link, Worli end', likelyPassed: false }, { junctionId: 8, name: 'Bowbazar', likelyPassed: true }], note: null },
		});
		const ents = [...viewer.byId.values()].map((e) => normGraph(e)).sort((a, b) => String(a.id).localeCompare(String(b.id)));
		const stats = normGraph({ count: overlay.count(), audit: overlay.audit() });
		dumps.pursuit = { ents, stats };
		got.pursuit = { ents: Object.fromEntries(ents.map((e) => [e.id, fp(e)])), stats: fp(stats) };
		overlay.destroy();
	}
	Date.now = realNow;
	delete globalThis.document;
	delete globalThis.getComputedStyle;

	if (process.argv.includes('--record-legacy')) {
		console.log(`LEGACY_RECORD = ${JSON.stringify(got, null, '\t')}`);
	} else {
		const changed = [];
		for (const id of new Set([...Object.keys(LEGACY_RECORD), ...Object.keys(got)])) {
			const want = LEGACY_RECORD[id];
			const have = got[id];
			const what = [];
			if (!want) what.push('not in the record');
			else if (!have) what.push('no longer drawn');
			else {
				for (const e of new Set([...Object.keys(want.ents), ...Object.keys(have.ents)])) {
					if (!(e in have.ents)) what.push(`${e} gone`);
					else if (!(e in want.ents)) what.push(`${e} new`);
					else if (want.ents[e] !== have.ents[e]) what.push(`${e} changed`);
				}
				if (want.stats !== have.stats) what.push('coverage stats changed');
			}
			if (what.length) {
				changed.push(`${id}: ${what.join(', ')}`);
				if (have) writeFileSync(path.join(ARTIFACTS, `canvas-layers-legacy-${id}.json`), JSON.stringify(dumps[id], null, 1));
			}
		}
		const n = Object.values(got).reduce((a, l) => a + Object.keys(l.ents).length, 0);
		check(
			'legacy invariance (recorded): every legacy layer and the pursuit overlay draw exactly the recorded entities — ids, graphics, materials, colours, widths, label text, pick text — and coverage stats',
			changed.length === 0,
			changed.join(' | ') || `${Object.keys(got).length} layers + overlay · ${n} entities match the record`,
		);
	}
}


// ── 13. the AI layers: waterlogging risk (hydro nowcast) and the traffic forecast (int-ops) ─────────────────
//
// waterlogging: ONE semantic hue (--v-map-water) stepped by width and opacity per class (1 thin 45 %, 2 6 px in
// the casing, 3 9 px opaque in the casing); a dry road draws nothing; a road without platform geometry is counted,
// never placed; the kind filter hides it; picks map to segment:<id>; the 19 Aug 2025 hindsight draws the replay's
// class at the chosen moment and says "Hindsight … Not today's city". forecast: roads whose median V/C reaches
// the threshold, DASHED in the neutral flow ink (never a hue), labelled simulated while the history is.
{
	const reads = new Set();
	globalThis.document = { documentElement: { dataset: {} }, hidden: false };
	globalThis.getComputedStyle = () => ({ getPropertyValue: (n) => (reads.add(String(n)), '') });
	M.godsEye.segments.length = 0;
	const seg = (id, coords) => ({ segmentId: id, roadName: `road ${id}`, roadClass: 'primary', coordinates: coords, geometryBasis: 'osm_display' });
	M.godsEye.segments.push(seg(1005, [[88.35, 22.55], [88.36, 22.551]]), seg(1006, [[88.36, 22.551], [88.37, 22.552]]), seg(1001, [[88.34, 22.58], [88.35, 22.583]]));
	const hy = (id, cls) => ({ segment_id: id, road_name: `road ${id}`, place: `place ${id}`, lat: 22.55, lon: 88.35, risk_class: cls, risk_class_now: 0, expected_depth_band: ['0–2 cm', '2–10 cm', '10–30 cm', '> 30 cm'][cls], modelled_peak_depth_cm: cls * 10, lead_time_min: 30, lead_time_deep_min: cls >= 2 ? 30 : null, elevated: false, drivers: { rain: { label: 'LIVE', next_2h_mm: 40 }, tide: { label: 'MODELLED (approximate)', level_m: 5.2, gate_closed_now: true }, pumps: { label: 'EMULATED', station: 'Ballygunge', pumps_available: 4, pumps_total: 5 } } });
	const NOWCAST = { generated_at: '', now: '', horizon_min: 120, labels: { rain: 'LIVE' }, rain_feed: { city_now_mm_h: 22 }, counts_by_class: {}, flagged: [], proposals: [], segments: [hy(1005, 3), hy(1006, 2), hy(1015, 1), hy(1001, 0)] };
	const drawAi = async (layerDef, body, view = M.V.emptyView('v2'), chrome = 'v2') => {
		reads.clear();
		globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => body });
		const viewer = makeViewer();
		const inst = layerDef.create();
		inst.init({ cesium: makeCesium({ cartesianClass: true }), viewer, fetchJson: async () => ({}), notify() {}, ...(chrome ? { chrome, view: () => view } : {}) });
		inst.activate();
		for (let i = 0; i < 10; i++) await tick();
		await sleep(20);
		inst.restyle?.();
		const ents = Object.fromEntries([...viewer.byId.entries()]);
		const stats = inst.coverageStats();
		const urn = inst.urnOf?.('wl:1005') ?? inst.urnOf?.('fc:1005');
		inst.deactivate();
		return { ents, stats, urn, reads: [...reads], left: viewer.byId.size };
	};
	const water = M.TOK.TOKENS.command['--v-map-water'];
	const w = await drawAi(M.WL.waterloggingLayer, NOWCAST);
	const l3 = w.ents['wl:1005']?.polyline;
	const l2 = w.ents['wl:1006']?.polyline;
	check(
		'waterlog: class 3 is 9 px opaque in the casing, class 2 6 px at 85 % in the casing — one water hue',
		l3?.material?.outlined === true && l3.width === 9 + 3 && l3.material.color.css === M.SYM.inkAlpha(water, 1) && l2?.width === 6 + 3 && l2.material.color.css === M.SYM.inkAlpha(water, 0.85),
		JSON.stringify({ w3: l3?.width, c3: l3?.material?.color?.css, w2: l2?.width, c2: l2?.material?.color?.css }),
	);
	check('waterlog: a dry road draws nothing; a road without platform geometry is counted, not placed', !w.ents['wl:1001'] && !w.ents['wl:1015'] && w.stats.detail.not_drawn === 1 && w.stats.count === 3 && w.stats.detail.impassable === 1 && w.stats.detail.deep === 1 && w.stats.detail.shallow === 1, JSON.stringify(w.stats.detail));
	check('waterlog: draped at the zone order, the hint in plain words, picks → segment URN', l3?.clampToGround === true && /3 roads at risk within 2 h \(modelled\)/.test(w.stats.hint) && w.urn === 'segment:1005' && w.left === 0, w.stats.hint);
	check('waterlog: the pick text names every driver with its label (rain live, tide modelled, pumps emulated)', /risk 3, impassable/.test(w.ents['wl:1005'].description) && /Rain live/.test(w.ents['wl:1005'].description) && /Tide modelled/.test(w.ents['wl:1005'].description) && /Pumps emulated/.test(w.ents['wl:1005'].description));
	check('waterlog: reads --v-map-water and the casing, never --v-act, --v-data or --v-tool', w.reads.includes('--v-map-water') && !w.reads.some((n) => /^--v-(act|data|tool)(-|$)/.test(n)), w.reads.join(' '));
	const hidden = await drawAi(M.WL.waterloggingLayer, NOWCAST, { ...M.V.emptyView('v2'), kinds: new Set(['vehicle']) });
	check('waterlog: the kind filter that hides roads hides it', Object.keys(hidden.ents).length === 0 && hidden.stats.count === 3);
	const under = await drawAi(M.WL.waterloggingLayer, NOWCAST, { ...M.V.emptyView('v2'), selection: 'vehicle:X', items: ['vehicle:X'], version: 2 });
	check('waterlog: under a selection it steps back like the flow layer (60 %, 0.5 px thinner)', under.ents['wl:1005']?.polyline.width === 9 - 0.5 + 3 && under.ents['wl:1005'].polyline.material.color.css === M.SYM.inkAlpha(water, 0.6));
	const DRY = { ...NOWCAST, segments: [hy(1005, 0), hy(1006, 0)] };
	const dry = await drawAi(M.WL.waterloggingLayer, DRY);
	check('waterlog: a dry city draws nothing and says so (never a zero shown as data)', Object.keys(dry.ents).length === 0 && /no road at risk within 2 h/.test(dry.stats.hint), dry.stats.hint);
	const rs = (id, c1, c2, c3) => ({ segment_id: id, road_name: `road ${id}`, place: `place ${id}`, rain_total_mm: 200, peak_class: c3 ? 3 : c2 ? 2 : 1, peak_depth_cm: 30, peak_band: '> 30 cm', peak_at_ist: '2025-09-23 05:30', first_class1_ist: c1, first_class2_ist: c2, first_class3_ist: c3, elevated: false });
	M.HS.showHindsight([rs(1005, '2025-09-23 02:00', '2025-09-23 02:45', '2025-09-23 04:15'), rs(1006, '2025-09-23 03:00', null, null)], Date.parse('2025-09-23T03:30:00+05:30'));
	const hs = await drawAi(M.WL.waterloggingLayer, DRY);
	M.HS.hideHindsight();
	check(
		'waterlog: hindsight draws the replay class at the moment (rising limb) and says so — never today',
		hs.ents['wl:1005']?.polyline.width === 6 + 3 && hs.ents['wl:1006']?.polyline.width === 3 && /^Hindsight 19 Aug 2025 03:30 IST/.test(hs.stats.hint) && /Not today's city/.test(hs.ents['wl:1005'].description) && hs.stats.via === 'hydro/replay',
		hs.stats.hint,
	);
	const step = (lead, p50) => ({ t: '', lead_min: lead, vc: { p10: p50 - 0.05, p50, p90: p50 + 0.05 }, speed_kmh: { p10: 20, p50: 22, p90: 24 } });
	const fseg = (id, peak) => ({ segment_id: id, road_name: `road ${id}`, place: `place ${id}`, data_label: 'SIMULATED', now: { t: '', vc: 0.7, speed_kmh: 25 }, crossing: peak >= 0.8 ? { in_min: 30 } : null, above_threshold_now: false, steps: [15, 30, 45, 60, 90, 120].map((l) => step(l, l === 60 ? peak : 0.7)) });
	const FDOC = { generated_at: '', origin: '', step_min: 15, threshold_vc: 0.8, model: 'chronos-2', model_note: null, data_labels: ['SIMULATED'], data_note: '', segments: [fseg(1005, 0.92), fseg(1006, 0.75)], proposals: [], crossings: 1, horizon_min: 120 };
	const f = await drawAi(M.FL.forecastLayer, FDOC);
	const fl = f.ents['fc:1005']?.polyline;
	const neutral = /rgba\((\d+), (\d+), (\d+)/.exec(fl?.material?.color?.css ?? '');
	check('forecast: a road whose median reaches 0.8 is DASHED in the neutral ink (heavy at 0.9), the others not drawn', fl?.material?.dashed === true && fl.width === 5 + 2 && !f.ents['fc:1006'] && !!neutral && Math.max(+neutral[1], +neutral[2], +neutral[3]) - Math.min(+neutral[1], +neutral[2], +neutral[3]) <= 30, JSON.stringify({ w: fl?.width, c: fl?.material?.color?.css }));
	check('forecast: labelled simulated while the history is (the sheet tag), the band in the pick text, picks → segment URN', f.stats.detail.simulated === 1 && /simulated traffic history/.test(f.ents['fc:1005'].description) && /\+60 min 0\.92 \(0\.87–0\.97\)/.test(f.ents['fc:1005'].description) && f.urn === 'segment:1005', f.ents['fc:1005']?.description);
	check('forecast: never --v-act, --v-data or --v-tool', !f.reads.some((n) => /^--v-(act|data|tool)(-|$)/.test(n)), f.reads.join(' '));

	// ── 14. the city-feed layers (city-feeds): air quality at the monitoring sites, the active cyclone ───────────
	// air: each site a dot on the EXISTING band ladder that also grows with the band (colour never alone), a 450 m veil
	// and "AQI n"; pick text says indicative, modelled, not the station's reading. cyclone: buffers on the band ladder,
	// the track, positions and a bearing marker at the city centre naming the storm; none active → nothing drawn, says so.
	globalThis.document.createElement = () => ({ getContext: () => null }); // dots fall back to the plain billboard
	const site = (id, aqi, band, lon) => ({ id, name: `site ${id}`, name_mr: 'সাইট', lat: 22.55, lon, coord_source: 'landmark', now: {}, pm25_24h: 40, pm10_24h: 60, naqi: { aqi, band, band_en: band, band_mr: band, band_hi: band, prominent: 'PM2.5', health: '', label: 'INDICATIVE' }, forecast: [] });
	const AIR = { label: 'MODELLED', stations: [site('victoria_memorial', 62, 'satisfactory', 88.34), site('ghusuri', 230, 'poor', 88.35), site('belur_math', 420, 'severe', 88.36)], city: { aqi: 420, band: 'severe', band_en: 'Severe', worst_site_name: 'site belur_math' } };
	const a = await drawAi(M.AQ.airLayer, AIR);
	const dot = (id) => a.ents[`aq:${id}`]?.billboard;
	check('air: one dot, one veil and a "place · AQI n" label per site (the label joins the map\'s one label budget); a worse band draws a larger dot', !!dot('victoria_memorial') && !!a.ents['aq:veil-ghusuri']?.ellipse && M.AQ.airLabel(AIR.stations[2], 'en') === 'site belur_math · AQI 420 (modelled)' && dot('belur_math').width > dot('ghusuri').width && dot('ghusuri').width > dot('victoria_memorial').width, JSON.stringify([dot('victoria_memorial')?.width, dot('ghusuri')?.width, dot('belur_math')?.width]));
	check('air: the band ladder tokens only (green · red · the black fill with its hairline), never --v-act, --v-data or --v-tool', a.reads.includes('--v-band-green') && a.reads.includes('--v-band-red') && a.reads.includes('--v-band-black-fill') && !a.reads.some((n) => /^--v-(act|data|tool)(-|$)/.test(n)), a.reads.join(' '));
	check('air: the pick text is honest (indicative, modelled, not the station reading) and picks → a place URN', /indicative National AQI 230, poor/.test(a.ents['aq:ghusuri'].description) && /not the station's own reading/.test(a.ents['aq:ghusuri'].description) && a.stats.count === 3 && a.stats.detail.worst_band === 5 && a.left === 0);
	check('air: urnOf maps a site pick to place:aq_<site>', M.AQ.airLayer.create().urnOf('aq:ghusuri') === 'place:aq_ghusuri');
	const CYC = {
		type: 'FeatureCollection', label: 'LIVE',
		features: [
			{ type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[81, 15], [83, 15], [83, 17], [81, 17], [81, 15]]] }, properties: { kind: 'wind_buffer', level: 'red', wind_kmh: 120, eventid: 7 } },
			{ type: 'Feature', geometry: { type: 'LineString', coordinates: [[84, 16], [82, 16.3]] }, properties: { kind: 'track', category: 'TS', eventid: 7 } },
			{ type: 'Feature', geometry: { type: 'Point', coordinates: [81.8, 16.4] }, properties: { kind: 'position', label: '28/10 06:00 UTC', forecast: false, eventid: 7 } },
		],
		active: [{}], nearest: { name: 'TEST-26', alertlevel: 'red', distance_km: 972, bearing: 'SW', bearing_deg: 226, position: { lat: 16.4, lon: 81.8, at: null }, closest_approach: { distance_km: 700 }, kolkata_in_wind_buffer_kmh: null, severity: null, report: null },
	};
	const c = await drawAi(M.CY.cycloneLayer, CYC);
	check('cyclone: buffer, track, position and the bearing marker at the city centre naming the storm', !!c.ents['cy:buffer-1']?.polygon && !!c.ents['cy:track-2']?.polyline && !!c.ents['cy:pos-3']?.billboard && !!c.ents['cy:bearing-shaft']?.polyline && c.ents['cy:bearing-label'].label.text === 'TEST-26 · 972 km SW' && c.stats.count === 1 && c.left === 0, Object.keys(c.ents).join(' '));
	check('cyclone: the alert level on the band ladder, never --v-act, --v-data or --v-tool; the pick text points to IMD RSMC', c.reads.includes('--v-band-red') && !c.reads.some((n) => /^--v-(act|data|tool)(-|$)/.test(n)) && /IMD RSMC New Delhi/.test(c.ents['cy:bearing-shaft'].description));
	const none = await drawAi(M.CY.cycloneLayer, { type: 'FeatureCollection', label: 'LIVE', features: [], active: [], nearest: null });
	check('cyclone: no active cyclone → nothing drawn, and the hint says so', Object.keys(none.ents).length === 0 && none.stats.count === 0 && /No active cyclone/.test(none.stats.hint), none.stats.hint);
	M.godsEye.segments.length = 0;
	delete globalThis.document;
	delete globalThis.getComputedStyle;
}

if (failures) {
	console.error(`\nFAIL canvas-layers — ${failures} assertion(s) failed`);
	process.exit(1);
}
console.log('ok   canvas-layers — all assertions passed');
process.exit(0);
