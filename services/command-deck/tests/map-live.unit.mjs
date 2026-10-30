/**
 * The live map (29 Oct): the City Pack places, the live readings at their places, the coloured roads with moving
 * traffic and names, the gliding units and the legend's data clock.
 *
 *   node tests/map-live.unit.mjs
 *
 *   1. src/lib/city/places.generated.ts is what scripts/gen_deck_places.mjs makes from the pack today (byte for byte),
 *      and holds the canonical landmarks (the Bandra–Worli Sea Link, CSMT, Hindmata, King's Circle, Wankhede, the BMC
 *      pumping stations …), areas, police / fire stations and hospitals — every one inside the city box, names in EN/MR/HI;
 *   2. the label budget (placeLabels): priority order, no overlap, the page's panels count as taken, a cap;
 *   3. the traffic motion comes from the data: dot spacing from congestion, V/C → the band ladder, never orange/blue;
 *   4. the live readings: every row carries its value AND its provenance word (emulated pumps, modelled tide and heat,
 *      live gauges and satellite spots), regional feeds stay in the region, nothing is invented from an empty answer;
 *   5. a unit's tag says what it is doing and that it is emulated; the canvas words exist in EN, MR and HI;
 *   6. the new layers are registered, on by default, and draw with primitive collections (no entity per place).
 *
 * esbuild bundles the REAL modules ($lib aliased, the runes stores stubbed) in memory.
 */

import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const REPO = path.resolve(DECK, '..', '..');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

// ─── 1. the generated places ─────────────────────────────────────────────────

const generated = readFileSync(path.join(DECK, 'src/lib/city/places.generated.ts'), 'utf8');
let fresh = '';
try {
	fresh = execFileSync(process.execPath, [path.join(DECK, 'scripts/gen_deck_places.mjs'), '--stdout'], { encoding: 'utf8' });
} catch (e) {
	fresh = `generator failed: ${e.message}`;
}
ok('places.generated.ts matches the City Pack (node scripts/gen_deck_places.mjs to refresh)', generated === fresh, `${generated.length} / ${fresh.length} bytes`);

const esbuild = createRequire(path.join(DECK, 'package.json'))('esbuild');
const STUBS = {
	'ops-store': 'export const ops = { lang: "en", officerOn: false };',
	'city-registry': 'export const cityRegistry = { byKind: () => [], version: 0 };',
	'gods-eye-store': 'export const godsEye = { units: [], segments: [], unitsFeed: { status: "ok" }, segmentsFeed: { status: "ok" } };',
};
const stub = {
	name: 'stub-runes',
	setup(build) {
		build.onResolve({ filter: /ops\/store\.svelte$/ }, () => ({ path: 'ops-store', namespace: 'stub' }));
		build.onResolve({ filter: /entities\/registry\.svelte$/ }, () => ({ path: 'city-registry', namespace: 'stub' }));
		build.onResolve({ filter: /store\.svelte$/ }, () => ({ path: 'gods-eye-store', namespace: 'stub' }));
		build.onResolve({ filter: /\.svelte$/ }, () => ({ path: 'svelte-component', namespace: 'stub' }));
		build.onLoad({ filter: /.*/, namespace: 'stub' }, (a) => ({ contents: STUBS[a.path] ?? 'export default {};', loader: 'js' }));
	},
};
const ENTRY = `
export * as places from './src/lib/city/places';
export * as city from './src/lib/city';
export * as marks from './src/lib/gods-eye/hud/map/live-marks';
export * as motion from './src/lib/gods-eye/layers/flow-motion';
export * as live from './src/lib/gods-eye/layers/live-values';
export * as flow from './src/lib/gods-eye/layers/traffic-flow';
export * as lm from './src/lib/gods-eye/layers/landmarks';
export * as pack from './src/lib/gods-eye/hud/map/packs.livemap';
export { t } from './src/lib/i18n/strings';
`;
let M = null;
try {
	const built = await esbuild.build({
		stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'map-live-entry.ts' },
		absWorkingDir: DECK,
		alias: { $lib: './src/lib' },
		bundle: true,
		format: 'esm',
		platform: 'node',
		write: false,
		logLevel: 'silent',
		plugins: [stub],
		define: { 'import.meta.env.SSR': 'true', 'import.meta.env.DEV': 'false' },
	});
	M = await import(`data:text/javascript;base64,${Buffer.from(built.outputFiles[0].text).toString('base64')}`);
	ok('bundle builds (esbuild, $lib aliased, runes stores stubbed)', !!M);
} catch (e) {
	ok('bundle builds (esbuild, $lib aliased, runes stores stubbed)', false, String(e?.message ?? e).slice(0, 400));
}

if (M) {
	const P = M.places.PLACE_MARKS;
	const byEn = (n) => P.find((p) => p.en === n);
	const want = ['Bandra–Worli Sea Link', 'CSMT (Chhatrapati Shivaji Maharaj Terminus)', 'Hindmata (Dadar East)', "King's Circle (Matunga)", 'Wankhede Stadium', 'Haji Ali pumping station', 'Andheri Subway'];
	ok('the canonical landmarks are labelled places (tier 1)', want.every((n) => byEn(n)?.tier === 1), want.map((n) => `${n}:${byEn(n)?.tier ?? '—'}`).join(' '));
	const counts = M.places.placeMarkCounts();
	ok('areas, police, fire stations and hospitals come from the pack', counts.area >= 40 && counts.police >= 20 && counts.fire >= 4 && counts.hospital >= 10 && P.length >= 180, JSON.stringify(counts));
	ok('every place lies in the city box, with EN/MR/HI names and a unique id', P.every((p) => M.city.inBox(p.lon, p.lat) && p.en && p.mr && p.hi) && new Set(P.map((p) => p.id)).size === P.length);
	ok('placeMarkName follows the UI language', M.places.placeMarkName(byEn('Bandra–Worli Sea Link'), 'mr') === byEn('Bandra–Worli Sea Link').mr && M.places.placeMarkName(byEn('Bandra–Worli Sea Link'), 'xx') === 'Bandra–Worli Sea Link');
	const lmIds = JSON.parse(readFileSync(path.join(REPO, 'cities/mumbai/landmarks.json'), 'utf8')).landmarks.map((l) => `lm_${l.id}`);
	ok('every landmarks.json id is a place mark (lm_<id>)', lmIds.every((id) => P.some((p) => p.id === id)), `${lmIds.length} landmarks`);

	// ─── 2. the label budget ────────────────────────────────────────────────
	const it = (key, priority, x, y, w = 100, h = 20) => ({ key, priority, x, y, w, h });
	const shown = M.marks.placeLabels([it('area', 4, 500, 300), it('landmark', 1, 520, 305), it('alert', 0, 900, 300), it('far', 1, 5000, 300)], { w: 1920, h: 1080 });
	ok('placeLabels: priority first, an overlapping lower label hidden, off-screen skipped', shown.has('alert') && shown.has('landmark') && !shown.has('area') && !shown.has('far'), [...shown].join(','));
	const kept = M.marks.placeLabels([it('under-panel', 1, 100, 100), it('clear', 1, 900, 600)], { w: 1920, h: 1080 }, 90, [[0, 0, 400, 400]]);
	ok('placeLabels: the page panels count as taken (keep-out)', !kept.has('under-panel') && kept.has('clear'));
	const many = M.marks.placeLabels(Array.from({ length: 300 }, (_, i) => it(`k${i}`, 2, 60 + (i % 20) * 95, 40 + Math.floor(i / 20) * 70, 80, 18)), { w: 1920, h: 1080 }, 50);
	ok('placeLabels: a cap on how many show at once', many.size === 50);
	const box = M.marks.labelBox('Bandra–Worli Sea Link\n31 km/h', 12);
	ok('labelBox sizes from the widest line and the line count', box.w > 80 && box.h >= 2 * 15);
	ok('median ignores non-finite samples', M.marks.median([3, Number.NaN, 1, 2]) === 2 && Number.isNaN(M.marks.median([])));

	// ─── 3. traffic motion from the data ────────────────────────────────────
	ok('dot spacing: a jam is a dense queue, a free road a few dots', M.motion.dotGapM(0.9) < M.motion.dotGapM(0.1) && M.motion.dotsFor(1000, 0.9) > M.motion.dotsFor(1000, 0.1) && M.motion.dotsFor(10, 0.5) === 1);
	ok('time-lapse and cap are stated constants', M.motion.FLOW_TIME_LAPSE === 20 && M.motion.FLOW_MAX_DOTS <= 2000);
	ok('V/C → the ramp: < 0.6 free, 0.6–0.8 slow, 0.8–1 heavy, ≥ 1 jammed', [0.3, 0.65, 0.85, 1.2].map((v) => M.flow.vcInk(M.flow.vcRampIdx(v)).token).join(',') === '--v-band-green,--v-band-amber,--v-band-red,--v-band-red');
	ok('the road ink is the band ladder only, never orange (decide) or blue (AI, route), and never under 3 px', [0, 0.3, 0.5, 0.7, 0.95].every((c) => /^--v-band-(green|amber|red)$/.test(M.flow.vcInk(c).token) && M.flow.vcInk(c).width >= 3));

	// ─── 4. the live readings ───────────────────────────────────────────────
	const pumps = M.live.rowsOf('pumps', { label: 'EMULATED', stations: [{ id: 'haji_ali', name: 'Haji Ali storm-water pumping station', lat: 18.981, lon: 72.813, pumps_total: 8, pumps_available: 3 }, { id: 'x', name: 'No position' }] }, 'en');
	ok('pumps: one row per placed station, value and "(emulated)" in the label, few pumps up is an alert', pumps.length === 1 && pumps[0].text === 'Haji Ali · pumps 3/8 (emulated)' && pumps[0].tone === 'alert', pumps[0]?.text);
	const tide = M.live.rowsOf('tide', { now: { level_m: 3.04, rising: false, gate_closed: false }, gate_close_level_m: 5 }, 'en');
	ok('tide: at the pack’s Apollo Bunder tide station, modelled, its direction', tide.length === 1 && /^Apollo Bunder · 3\.04 m falling \(modelled\)$/.test(tide[0].text) && JSON.stringify([tide[0].lon, tide[0].lat]) === JSON.stringify(M.city.landmarkLonLat('apollo_bunder')), tide[0]?.text);
	const tideMr = M.live.rowsOf('tide', { now: { level_m: 3.04, rising: true, gate_closed: false } }, 'hi');
	ok('tide: the station named in the reader’s language, without the long form', tideMr.length === 1 && tideMr[0].text.startsWith('अपोलो बंदर ') && !/स्टेशन/.test(tideMr[0].text), tideMr[0]?.text);
	const shut = M.live.rowsOf('tide', { now: { level_m: 5.2, rising: true, gate_closed: true } }, 'en');
	ok('tide: the outfall gates shut is an alert', shut[0].tone === 'alert' && /outfall gates shut/.test(shut[0].text));
	const heat = M.live.rowsOf('heat', { points: [{ id: 'santacruz', name: 'Santacruz (IMD observatory)', lat: 19.0883, lon: 72.8519, now: { temp: 25.9, band: 'normal' } }] }, 'en');
	ok('heat: the observatory, its temperature, modelled', heat.length === 1 && heat[0].text === 'Santacruz · 25.9 °C (modelled)', heat[0]?.text);
	const river = M.live.rowsOf('river', { stations: [{ code: 'far', name: 'Godavari at Nashik', lat: 20.0, lon: 73.79, level_m: 147.3, status: 'normal' }, { code: 'near', name: 'Mithi at Kurla', lat: 19.073, lon: 72.878, level_m: 4.1, status: 'warning' }] }, 'en');
	ok('river: only the gauges in the region, the live gauge word, a warning rises in priority', river.length === 1 && river[0].text === 'Mithi at Kurla · 4.10 m (live gauge)' && river[0].tone === 'warn' && river[0].priority < 1, river.map((r) => r.text).join(' | '));
	const fires = M.live.rowsOf('fires', { features: [{ geometry: { coordinates: [72.85, 19.05] }, properties: { at: new Date(Date.now() - 3 * 3600_000).toISOString() } }, { geometry: { coordinates: [80, 15] }, properties: {} }] }, 'en');
	ok('fires: a satellite heat spot in the city, how long ago, live; one far away is not drawn', fires.length === 1 && fires[0].text === 'Satellite heat spot · 3 h ago (live)' && fires[0].tone === 'alert', fires.map((r) => r.text).join(' | '));
	ok('an empty or broken answer draws nothing (never an invented value)', ['pumps', 'tide', 'heat', 'river', 'fires', 'quakes'].every((s) => M.live.rowsOf(s, null, 'en').length === 0 && M.live.rowsOf(s, {}, 'en').length === 0));
	ok('shortPlace keeps the place name', M.live.shortPlace('Palmer Bazar (Palmer Bridge) pumping station') === 'Palmer Bazar' && M.live.shortPlace('Rabindra Bharati University (B T Road)') === 'Rabindra Bharati University');
	ok('a fresh item pulses for 20 minutes of its own time', M.live.FRESH_MS === 20 * 60_000);

	// ─── 5. units and words ─────────────────────────────────────────────────
	ok('unit tag: id, what it is doing, emulated', M.marks.unitTag({ unitId: 'KTP-EM-LC3', status: 'patrol', emulated: true }) === 'KTP-EM-LC3 · patrol (emulated)' && M.marks.unitTag({ unitId: 'X', status: null }) === 'X');
	ok('units glide over one poll and jump on a reassignment', M.marks.UNIT_GLIDE_MS >= 3000 && M.marks.UNIT_GLIDE_MS <= 6000 && M.marks.UNIT_JUMP_M >= 500);
	const keys = (o) => Object.keys(o).sort().join(',');
	ok('canvas words: EN, MR and HI hold the same keys', keys(M.pack.en) === keys(M.pack.mr) && keys(M.pack.en) === keys(M.pack.hi), `${Object.keys(M.pack.en).length} keys`);
	ok('canvas words: the Marathi and Hindi pumps label say emulated in their language', /एम्युलेटेड/.test(M.t('mr', 'lm_pumps', 'हाजी अली', 7, 8)) && /अनुकृत/.test(M.t('hi', 'lm_pumps', 'हाजी अली', 7, 8)));

	// ─── 6. registered, on, primitives ──────────────────────────────────────
	const index = readFileSync(path.join(DECK, 'src/lib/gods-eye/layers/index.ts'), 'utf8');
	const on = (f) => /\n\tdefaultOn: true,\n/.test(readFileSync(path.join(DECK, 'src/lib/gods-eye/layers', f), 'utf8'));
	ok('the landmarks and live-readings layers are registered and on by default (with air and flow)', /\tlandmarksLayer,\n\tliveValuesLayer,/.test(index) && ['landmarks.ts', 'live-values.ts', 'air.ts', 'traffic-flow.ts'].every(on) && M.lm.landmarksLayer.defaultOn && M.live.liveValuesLayer.defaultOn);
	const src = ['layers/landmarks.ts', 'layers/live-values.ts', 'layers/flow-motion.ts'].map((f) => readFileSync(path.join(DECK, 'src/lib/gods-eye', f), 'utf8')).join('\n');
	ok('they draw with primitive collections, never one entity per place or dot', /LabelCollection/.test(src) && /BillboardCollection/.test(src) && /PointPrimitiveCollection/.test(src) && !/viewer\.entities\.add|entities\.add\(/.test(src));
}

if (failures) {
	console.error(`map-live.unit: ${failures} failure(s)`);
	process.exit(1);
}
console.log('map-live.unit: all green');
