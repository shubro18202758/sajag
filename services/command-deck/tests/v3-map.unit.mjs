/**
 * V3 Map unit test (V3-P4; V3-SPEC §5.6, §6.5, §7.1, §8) — zero browser.
 *
 *   node tests/v3-map.unit.mjs
 *
 * esbuild bundles the REAL modules ($lib aliased; .svelte compiled for the server with svelte/compiler, the
 * assistant.unit pattern) and drives them:
 *
 *   pack       EN / HI / MR carry the same keys, every key starts with v3m_; EN copy rules (≤ one " · ", no ALL-CAPS
 *              word outside the acronyms); HI / MR translated and in their own script; the honesty words hold in all
 *              three: the thermal-style view is a visual filter with no thermal sensor, the 3D city is not a live
 *              image, Vehicles only and no faces kept; no string says infrared / FLIR / thermal camera / night vision
 *   defaults   V3_DEFAULT_LAYERS is §5.6's five + the live city (flow, cameras, units); V3_OFF_LAYERS the four others; together they are every canvas layer
 *              but the photoreal city (read from layers/*.ts); the Layers sheet lists exactly the OFF ones
 *   groups     groupLayerState: a layer two groups draw stays while either is on; every group's layers exist
 *   now items  nowFrom* keep Home's masked titles and provenance; pickItem prefers the officer's row, then live →
 *              reported → planned → decision; aliasUrn maps a convoy to its movement
 *   figures    movementStats shows only what the convoy feed reports (never a guessed figure)
 *   rules      replayBlock (a live movement / an open pursuit wait it), detailsHref (urn only, never a mark),
 *              isOfficialWeather (official only), nextSensor (off ↔ the last palette), mapKey (L, F, 3 only; never
 *              with a modifier or while typing — no key approves), entityArt (vehicle silhouettes, agency marks: no
 *              person)
 *   render     the components render on the server: MapTools has ONE thermal button with the honest tooltip, pressed
 *              while on; the 3D button is disabled with its reason without the key; SelectionCard has one primary
 *              verb, no Approve / Apply, a masked mark in a PlateChip; LayersSheet has the switches with roles and the
 *              Vehicles-only rule; NowPanel hides a group that is off and disables Replay with its reason
 *   wiring     the canvas: chrome 'v3' draws the v2 symbology without the v2 canvas chrome, attaches `act`, takes the
 *              defaultLayers; /gods-eye still mounts chrome="v2"; the rail's Map item is /map; no v3 map module is
 *              imported outside /map (so none loads on /gods-eye, /, /ops)
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const SRC = path.join(DECK, 'src');
const OUT_DIR = path.join(HERE, 'artifacts');
mkdirSync(OUT_DIR, { recursive: true });

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

const req = createRequire(path.join(DECK, 'package.json'));
const esbuild = req('esbuild');
const { compile, compileModule } = req('svelte/compiler');

globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });
globalThis.$props = () => ({});
globalThis.$bindable = (v) => v;

const sveltePlugin = {
	name: 'svelte-ssr',
	setup(b) {
		b.onLoad({ filter: /\.svelte$/ }, async (args) => {
			const src = readFileSync(args.path, 'utf8');
			const { js } = compile(src, { filename: args.path, generate: 'server', css: 'injected', dev: false });
			return { contents: js.code, loader: 'js', resolveDir: path.dirname(args.path) };
		});
		b.onLoad({ filter: /\.svelte\.(ts|js)$/ }, async (args) => {
			const src = readFileSync(args.path, 'utf8');
			const plain = args.path.endsWith('.ts') ? (await esbuild.transform(src, { loader: 'ts' })).code : src;
			const { js } = compileModule(plain, { filename: args.path, generate: 'server', dev: false });
			return { contents: js.code, loader: 'js', resolveDir: path.dirname(args.path) };
		});
	},
};

const ENTRY = `
export { render } from 'svelte/server';
export * as model from './src/lib/v3/map/model';
export * as pack from './src/lib/v3/map/packs.map3';
export { hi } from './src/lib/v3/map/packs.map3.hi';
export { mr } from './src/lib/v3/map/packs.map3.mr';
export { t } from './src/lib/i18n/strings';
export { default as MapTools } from './src/lib/v3/map/MapTools.svelte';
export { default as SelectionCard } from './src/lib/v3/map/SelectionCard.svelte';
export { default as LayersSheet } from './src/lib/v3/map/LayersSheet.svelte';
export { default as NowPanel } from './src/lib/v3/map/NowPanel.svelte';
export { default as MapChips } from './src/lib/v3/map/MapChips.svelte';
export { default as Legend3 } from './src/lib/v3/map/Legend3.svelte';
export { default as StatsPanel } from './src/lib/v3/map/StatsPanel.svelte';
export * as glass from './src/lib/v3/map/glass';
export * as tokens from './src/lib/v3/tokens';
export * as view from './src/lib/gods-eye/hud/map/view';
`;
const OUT = path.join(OUT_DIR, 'v3-map-bundle.mjs');
let M = null;
try {
	const built = await esbuild.build({
		stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'v3-map-entry.ts' },
		absWorkingDir: DECK,
		alias: { $lib: './src/lib' },
		bundle: true,
		format: 'esm',
		platform: 'node',
		conditions: ['svelte', 'node'],
		outfile: OUT,
		logLevel: 'silent',
		plugins: [sveltePlugin],
	});
	ok('bundle builds (the real model, packs and components; svelte/server)', built.errors.length === 0, `${built.errors.length} errors`);
	M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
} catch (err) {
	ok('bundle builds (the real model, packs and components; svelte/server)', false, String(err?.message ?? err).slice(0, 400));
}
if (!M) {
	console.log(`\n${failures} failure(s)`);
	process.exit(1);
}
const { model, pack } = M;
const L = (k, ...a) => M.t('en', k, ...a);
const text = (v) => (typeof v === 'function' ? String(v('‹x›', '‹y›')) : String(v));

// ─── pack ────────────────────────────────────────────────────────────────────
{
	const en = pack.MAP3_PACKS.en;
	const keys = Object.keys(en);
	const same = (a, b) => a.length === b.length && a.every((k) => b.includes(k));
	ok('pack: EN / HI / MR carry the same keys', same(keys, Object.keys(M.hi)) && same(keys, Object.keys(M.mr)), `${keys.length} keys`);
	ok('pack: every key starts with v3m_', keys.every((k) => k.startsWith('v3m_')));
	const ACR = new Set(['ANPR', 'ETA', 'IST', 'OSM', 'AI', 'ID', 'FIR', 'GPS', '3D', 'OK']);
	const caps = keys.filter((k) => text(en[k]).split(/[\s,.:;()·/—-]+/).some((w) => w.length > 1 && /^[A-Z]+$/.test(w) && !ACR.has(w)));
	ok('pack: no ALL-CAPS word outside the acronyms (EN)', caps.length === 0, caps.join(','));
	const dots = keys.filter((k) => text(en[k]).split(' · ').length > 2);
	ok('pack: at most one " · " per EN string', dots.length === 0, dots.join(','));
	const untranslated = keys.filter((k) => !/^v3m_stat_eta$/.test(k) && (text(M.hi[k]) === text(en[k]) || text(M.mr[k]) === text(en[k])));
	ok('pack: HI and MR are translated (not the EN words)', untranslated.length === 0, untranslated.join(','));
	ok('pack: HI and MR are in Devanagari (Hindi and Marathi), no Bengali script left', keys.filter((k) => !/[ऀ-ॿ]/.test(text(M.hi[k])) && /[a-z]{3}/i.test(text(en[k])) && k !== 'v3m_stat_eta').length === 0 && keys.filter((k) => (!/[ऀ-ॿ]/.test(text(M.mr[k])) || /[ঀ-৿]/.test(text(M.mr[k]))) && /[a-z]{3}/i.test(text(en[k])) && k !== 'v3m_stat_eta').length === 0);
	ok('pack: the thermal-style label says a visual filter, no thermal sensor (EN)', /visual filter, no thermal sensor/.test(text(en.v3m_thermal_on)));
	ok('pack: the thermal-style label keeps "filter" and "no sensor" in HI and MR', /फ़िल्टर/.test(text(M.hi.v3m_thermal_on)) && /सेंसर नहीं/.test(text(M.hi.v3m_thermal_on)) && /फिल्टर/.test(text(M.mr.v3m_thermal_on)) && /सेन्सर नाही/.test(text(M.mr.v3m_thermal_on)));
	ok('pack: the 3D city is "not a live image" in all three', /not a live image/.test(text(en.v3m_credit_3d)) && /लाइव चित्र नहीं/.test(text(M.hi.v3m_credit_3d)) && /थेट प्रतिमा नाही/.test(text(M.mr.v3m_credit_3d)));
	ok('pack: Vehicles only, no faces kept (EN)', /^Vehicles only\./.test(text(en.v3m_vehicles_only)) && /no images, frames or faces are kept/.test(text(en.v3m_vehicles_only)));
	const all = [en, M.hi, M.mr].flatMap((p) => Object.values(p).map(text)).join('\n');
	ok('pack: no string claims a sensor (infrared, FLIR, thermal camera/imaging, night vision)', !/infra-?red|\bFLIR\b|\bIR\b|thermal (camera|imaging)|night vision|इन्फ्रारेड|ইনফ্রারেড/i.test(all));
	ok('pack: no person word in the layer copy (vehicles only)', !/\b(person|people tracking|face match|suspect)\b/i.test(keys.filter((k) => k.startsWith('v3m_l_')).map((k) => text(en[k])).join(' ')));
}

// ─── defaults and groups ────────────────────────────────────────────────────
{
	const ids = readdirSync(path.join(SRC, 'lib/gods-eye/layers'))
		.filter((f) => f.endsWith('.ts'))
		.flatMap((f) => [...readFileSync(path.join(SRC, 'lib/gods-eye/layers', f), 'utf8').matchAll(/^\tid: '([a-z0-9-]+)',$/gm)].map((m) => m[1]));
	const layerIds = new Set(ids.filter((x) => x !== 'photoreal-3d'));
	ok(
		'defaults: §5.6 — events, convoy, traces, enforcement, osint on, plus the live city (flow, cameras, units, dispatches, City Pack places, live readings, air quality) and the waterlogging nowcast',
		JSON.stringify([...model.V3_DEFAULT_LAYERS].sort()) === JSON.stringify(['air', 'cameras', 'convoy', 'dispatch', 'enforcement', 'events', 'flow', 'landmarks', 'livevalues', 'osint', 'traces', 'units', 'waterlog']),
	);
	ok('defaults: signals, anomalies, the gazetteer places, the traffic forecast and the cyclone off (the live city opens on)', JSON.stringify([...model.V3_OFF_LAYERS].sort()) === JSON.stringify(['anomalies', 'cyclone', 'forecast', 'places', 'signals']) && model.V3_SHEET_ON.every((l) => model.V3_DEFAULT_LAYERS.includes(l)));
	const union = new Set([...model.V3_DEFAULT_LAYERS, ...model.V3_OFF_LAYERS]);
	ok('defaults: on + off = every canvas layer but the photoreal city (layers/*.ts)', union.size === layerIds.size && [...layerIds].every((x) => union.has(x)), [...layerIds].sort().join(','));
	ok('sheet: lists the layers that start off plus the live-city layers that open on', JSON.stringify([...model.SHEET_LAYER_IDS].sort()) === JSON.stringify([...model.V3_OFF_LAYERS, ...model.V3_SHEET_ON].sort()));
	const fcSec = model.SHEET.find((x) => x.key === 'ai_sheet');
	ok('sheet: a Forecasts section holds the waterlogging risk and the traffic forecast', !!fcSec && JSON.stringify(fcSec.rows.map((r) => r.id)) === JSON.stringify(['waterlog', 'forecast']));
	const cfSec = model.SHEET.find((x) => x.key === 'cf_sheet');
	ok('sheet: a City feeds section holds the air-quality (opens on) and cyclone (off) layers', !!cfSec && JSON.stringify(cfSec.rows.map((r) => r.id)) === JSON.stringify(['air', 'cyclone']) && model.V3_DEFAULT_LAYERS.includes('air') && model.V3_OFF_LAYERS.includes('cyclone') && ['air', 'cyclone'].every((x) => layerIds.has(x)));
	const L = (k, ...a) => `${k}${a.length ? `(${a.join(',')})` : ''}`;
	ok(
		'sheet: the city-feed rows say what they hold — off: what they would show; on: sites and the worst band; no cyclone says so; a feed error',
		model.aiLayerSub('air', { visible: false, count: 0, error: null }, false, L) === 'cf_l_air_about' &&
			model.aiLayerSub('air', { visible: true, count: 10, error: null, detail: { worst_band: 2 } }, false, L) === 'cf_l_air_sub(10,cf_naqi_moderate)' &&
			model.aiLayerSub('cyclone', { visible: true, count: 0, error: null }, false, L) === 'cf_l_cyc_none' &&
			model.aiLayerSub('cyclone', { visible: true, count: 1, error: null, detail: { distance_km: 972 } }, false, L) === 'cf_l_cyc_sub(1,972)' &&
			model.aiLayerSub('cyclone', { visible: true, count: 0, error: 'down' }, false, L) === 'cf_l_feed',
	);
	ok(
		'sheet: the AI rows say what they hold — off: what they would show; on: the count, dry, the replay; a feed error',
		model.aiLayerSub('waterlog', { visible: false, count: 0, error: null }, false, L) === 'ai_l_waterlog_about' &&
			model.aiLayerSub('waterlog', { visible: true, count: 0, error: null }, false, L) === 'ai_l_waterlog_dry' &&
			model.aiLayerSub('waterlog', { visible: true, count: 7, error: null }, false, L) === 'ai_l_waterlog_sub(7)' &&
			model.aiLayerSub('waterlog', { visible: true, count: 60, error: null }, true, L) === 'ai_l_waterlog_hs(60)' &&
			model.aiLayerSub('forecast', { visible: true, count: 3, error: null }, false, L) === 'ai_l_forecast_sub(3)' &&
			model.aiLayerSub('forecast', { visible: true, count: 0, error: 'down' }, false, L) === 'v3m_l_feed' &&
			model.aiLayerSub('flow', { visible: true, count: 3, error: null }, false, L) === null,
	);
	ok('groups: every group layer is a real layer and on by default', Object.values(model.GROUP_LAYERS).flat().every((x) => layerIds.has(x) && model.V3_DEFAULT_LAYERS.includes(x)));
	const st = (o) => model.groupLayerState({ live: true, decide: true, reported: true, planned: true, ...o });
	ok('groups: Live off keeps events (Coming up still draws them), drops convoy and traces', st({ live: false }).events === true && st({ live: false }).convoy === false && st({ live: false }).traces === false);
	ok('groups: Coming up off keeps events while Live operations draws them', st({ planned: false }).events === true && st({ planned: false }).convoy === true);
	ok('groups: Live AND Coming up off drop events', st({ live: false, planned: false }).events === false);
	ok('groups: Reported off drops osint only', st({ reported: false }).osint === false && st({ reported: false }).enforcement === true);
}

// ─── now items, selection, figures ─────────────────────────────────────────
{
	const prov = { text: 'Emulated', tone: 'dashed' };
	const op = model.nowFromOp({ key: 'event:e1', kindLine: 'Protected movement, class Z', title: 'Science City to Red Road', state: { text: 'Live', tone: 'route' }, meta: 'Arrives 18:22 IST', next: '', progress: 62, art: '/a.svg', href: '/ops', prov, thumb: {}, decisions: 1 }, '/decide/x');
	const dec = model.nowFromDecision({ key: 'escort-proposal:p1', kind: 'escort-proposal', kindLine: 'Escort proposal', title: 'Hold', plate: { mark: 'MH47EM•••1', masked: true }, why: '', by: { text: 'Proposed by the convoy assistant', ai: true }, art: '/a.svg', href: '/decide/escort-proposal%3Ap1', deadline: 1, since: null, timeBoxed: true, prov, thumb: {}, facts: [], ifNot: '', maskedTitle: 'Hold', emulated: true }, 'event:e1');
	const rep = model.nowFromReport({ key: 'osint_event:o1', kindLine: 'Road accident', title: 'Sector V', verif: { text: 'News-reported', tone: 'ghost' }, meta: '', cred: 0.654, note: '', art: '/a.svg', href: '/', thumb: {} }, null);
	const plan = model.nowFromPlanned({ key: 'event:e9', kindLine: 'Procession', title: 'Kumartuli', when: '—', meta: '07:00–09:00 IST', next: 'Planning', art: '/a.svg', href: '/', prov: null, thumb: {} });
	ok('now: an operation row keeps its state word, provenance and review home', op.group === 'live' && op.right.text === 'Live' && op.right.tone === 'route' && op.prov === prov && op.review === '/decide/x');
	ok('now: a decision row selects its subject, keeps its masked mark and its one home', dec.urn === 'event:e1' && dec.plate.masked === true && dec.review.startsWith('/decide/') && dec.meta === 'Escort proposal · Proposed by the convoy assistant');
	ok('now: a report row says its verification and credibility (2 decimals)', rep.meta === 'News-reported · 0.65' && rep.right === null);
	ok('now: a plan without a known start shows its window, never a dash', plan.meta === '07:00–09:00 IST');
	const items = [dec, op, rep, plan];
	ok('select: the officer’s row wins while it names the selection', model.pickItem(items, 'escort-proposal:p1', 'event:e1')?.key === 'escort-proposal:p1');
	ok('select: a map pick shows the operation before the decision on the same object', model.pickItem(items, null, 'event:e1')?.key === 'event:e1');
	ok('select: a stale row key gives way to the selection', model.pickItem(items, 'escort-proposal:p1', 'osint_event:o1')?.key === 'osint_event:o1');
	ok('select: nothing selected → no card', model.pickItem(items, 'event:e1', null) === null);
	ok('select: a convoy stands for its movement', model.aliasUrn('convoy:m1', { event_id: 'e1' }) === 'event:e1' && model.aliasUrn('camera:C1', {}) === 'camera:C1');
	const fmt = { time: (ms) => `T${Math.round(ms / 1000)}`, dur: (s) => `${s}s` };
	const full = model.movementStats({ eta_sec: 60, progress: 0.62, next_junction_in_sec: 180, next_junction_name: 'Bandra (Sea Link, Bandra end)' }, 0, fmt, L);
	ok('figures: ETA, % done, time to the next junction — from the convoy feed', full.length === 3 && full[0].value === 'T60' && full[1].value === '62 %' && full[2].label === 'to Bandra (Sea Link, Bandra end)', JSON.stringify(full));
	ok('figures: a figure the feed does not report is left out, never guessed', model.movementStats({ progress: 40 }, 0, fmt, L).length === 1 && model.movementStats(null, 0, fmt, L).length === 0);
}

// ─── rules ───────────────────────────────────────────────────────────────────
{
	ok('replay: a live movement holds it', model.replayBlock([{ eventKind: 'protected_movement', state: 'active' }]) === 'v3m_replay_live_move');
	ok('replay: an open pursuit holds it', model.replayBlock([{ eventKind: 'vehicle_pursuit', state: 'active' }]) === 'v3m_replay_live_pursuit');
	ok('replay: planned work and offline fixtures do not', model.replayBlock([{ eventKind: 'protected_movement', state: 'planned' }, { eventKind: 'vehicle_pursuit', state: 'active', source: 'offline-fixture' }]) === null);
	const dh = model.detailsHref('vehicle:1b94e9d2-7e11-4174-a735-7dd3be3189cf');
	ok('details: the link carries the urn only (never a mark)', (dh.startsWith('/#items=') || dh.startsWith('/o/')) && dh.includes('1b94e9d2-7e11-4174-a735-7dd3be3189cf') && !/(?:WB|MH)\d/.test(decodeURIComponent(dh)));
	ok('weather: only an OFFICIAL weather report becomes the chip', model.isOfficialWeather({ verificationState: 'OFFICIAL-VERIFIED', label: 'Weather hazard · Mumbai City district', props: {} }) && !model.isOfficialWeather({ verificationState: 'NEWS-REPORTED', label: 'Heavy rain', props: {} }) && !model.isOfficialWeather({ verificationState: 'OFFICIAL-VERIFIED', label: 'Road closure', props: {} }));
	ok('thermal: off → white-hot; on → normal colours; the last palette is remembered', model.nextSensor('raw', null) === 'flir-whot' && model.nextSensor('flir-iron', 'flir-iron') === 'raw' && model.nextSensor('raw', 'flir-iron') === 'flir-iron' && model.nextSensor('raw', 'bogus') === 'flir-whot');
	const keys = 'abcdefghijklmnopqrstuvwxyz0123456789'.split('').concat(['Enter', ' ', 'Escape', 'Delete']);
	const acts = keys.map((k) => model.mapKey({ key: k }, false)).filter(Boolean);
	ok('keys: only L, F and 3 do anything (layers, follow, 3D) — no key approves, unmasks or dispatches', JSON.stringify(acts) === JSON.stringify(['follow', 'layers', '3d']), JSON.stringify(acts));
	ok('keys: nothing while typing or with a modifier', model.mapKey({ key: 'l' }, true) === null && model.mapKey({ key: 'l', ctrlKey: true }, false) === null && model.mapKey({ key: '3', metaKey: true }, false) === null);
	const arts = ['vehicle', 'unit', 'dispatch', 'camera', 'junction', 'anomaly', 'convoy', 'osint_event', 'event', 'place'].map((k) => model.entityArt(k, { vehicle_class: k === 'vehicle' ? 'suv' : undefined, agency: 'police' }, (x) => `/illustrations/events/${x ?? 'advisory'}.svg`));
	ok('art: vehicle silhouettes and agency marks only (no person art)', arts[0] === '/illustrations/vehicles/suv.svg' && arts[1] === '/illustrations/agencies/police.svg' && arts.every((a) => /^\/illustrations\/(vehicles|agencies|events)\//.test(a) && !/person|people|face/.test(a)), arts.join(' '));
	ok('art: an unknown vehicle class falls back to the car', model.entityArt('vehicle', { vehicle_class: '../../x' }, () => '') === '/illustrations/vehicles/car.svg');
}

// ─── glass (review item 6): contrast over the darkest and the lightest map pixel ───────────────
{
	const rgb = (h) => {
		const m = /^#([0-9a-f]{6})$/i.exec(h);
		if (m) return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16)).concat(1);
		const r = /rgba?\(([^)]+)\)/.exec(h);
		const p = r[1].split(',').map((x) => parseFloat(x));
		return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
	};
	const lum = ([r, g, b]) => {
		const f = (v) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
		return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
	};
	const cr = (a, b) => (Math.max(lum(a), lum(b)) + 0.05) / (Math.min(lum(a), lum(b)) + 0.05);
	const over = (fg, bg) => [0, 1, 2].map((i) => fg[i] * fg[3] + bg[i] * (1 - fg[3]));
	const night = M.tokens.v3Tokens('night');
	const inks = M.tokens.TEXT_INKS.map((k) => [k, rgb(night[k])]);
	const glassBg = rgb(M.glass.GLASS.bg);
	const glassSolid = rgb(M.glass.GLASS.solid);
	// the darkest and the lightest pixel any map can put under the glass (night OSM, photoreal city, white-hot filter)
	const UNDER = { darkest: [0, 0, 0], lightest: [255, 255, 255] };
	const worst = [];
	for (const [name, under] of Object.entries(UNDER)) {
		const comp = over(glassBg, under);
		for (const [k, ink] of inks) worst.push([cr(ink, comp), `${k} over the glass on the ${name} tile`]);
	}
	worst.sort((a, b) => a[0] - b[0]);
	ok('glass: every V3 text ink ≥ 4.5:1 on the translucent glass over the darkest AND the lightest map pixel (no blur assumed)', worst[0][0] >= 4.5, `worst ${worst[0][0].toFixed(2)} — ${worst[0][1]}`);
	const solidWorst = Math.min(...inks.map(([, ink]) => cr(ink, glassSolid.slice(0, 3))));
	ok('glass: the solid fallback holds every ink ≥ 4.5:1', solidWorst >= 4.5, solidWorst.toFixed(2));
	ok('glass: grey-tinted and translucent (alpha < 1), the fallback opaque, a blur declared, no hex', glassBg[3] < 1 && glassBg[3] >= 0.85 && glassSolid[3] === 1 && /^blur\(\d+px\)/.test(M.glass.GLASS.blur) && !/#/.test(JSON.stringify(M.glass.GLASS)));
	ok('glass: the tokens are --v3-glass-bg / -solid / -border / -blur', ['--v3-glass-bg:', '--v3-glass-solid:', '--v3-glass-border:', '--v3-glass-blur:'].every((k) => M.glass.glassVars().includes(k)));
}

// ─── focus mode (review item 1) ───────────────────────────────────────────────
{
	const V = M.view;
	const base = { ...V.emptyView('v2'), selection: 'event:a', items: ['event:a'], related: new Set(['convoy:a']), protected: new Set(['event:p']) };
	const v2 = V.markerStyle({ urn: 'event:b', kind: 'event' }, base).alpha;
	const f = { ...base, focus: true };
	ok('focus: with a selection, an unrelated event steps far back (v3 focus) — further than the v2 hierarchy', V.markerStyle({ urn: 'event:b', kind: 'event' }, f).alpha === V.MAP_OPACITY.focusUnrelated && V.MAP_OPACITY.focusUnrelated < v2);
	ok('focus: the selection and what it links to stay at full strength', V.markerStyle({ urn: 'event:a', kind: 'event' }, f).alpha === 1 && V.markerStyle({ urn: 'convoy:a', kind: 'convoy' }, f).alpha === 1);
	ok('focus: a protected object (a live movement, an open pursuit, a waiting decision) is dimmed less, never hidden — still clearly on the map', V.markerStyle({ urn: 'event:p', kind: 'event' }, f).alpha === V.MAP_OPACITY.focusProtected && V.MAP_OPACITY.focusProtected >= 0.5 && V.MAP_OPACITY.focusProtected > V.MAP_OPACITY.focusUnrelated && V.markerStyle({ urn: 'event:p', kind: 'event' }, f).show === true);
	ok('focus: nothing selected → nothing dimmed', V.markerStyle({ urn: 'event:b', kind: 'event' }, { ...V.emptyView('v2'), focus: true }).alpha === 1);
	ok('focus: the v2 map (no focus flag) keeps its own numbers', v2 === V.MAP_OPACITY.unrelated && V.markerStyle({ urn: 'event:p', kind: 'event' }, base).alpha === 1);
}

// ─── render ──────────────────────────────────────────────────────────────────
{
	const html = (C, props) => M.render(C, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
	const noop = () => {};
	const toolsProps = { is3d: false, can3d: false, why3d: 'Needs the Cesium ion key on this deck', sensor: 'raw', tool: 'select', follow: { pressed: false, disabled: true, title: 'Select something to follow' }, heading: 0, statsOpen: false, legendOpen: true, lang: 'en', on3d: noop, onthermal: noop, onmeasure: noop, onfollow: noop, onzoom: noop, onnorth: noop, onstats: noop, onlegend: noop };
	const off = html(M.MapTools, toolsProps);
	const on = html(M.MapTools, { ...toolsProps, sensor: 'flir-iron' });
	const thermalBtn = (h) => (h.match(/<button[^>]*data-map-tool="thermal"[^>]*>/g) ?? []);
	ok('tools: ONE thermal-style button with the honest tooltip', thermalBtn(off).length === 1 && /title="Thermal-style view — a visual filter, no thermal sensor"/.test(thermalBtn(off)[0]), thermalBtn(off)[0]?.slice(0, 160));
	ok('tools: the thermal button is pressed while a palette is on, not while off', /aria-pressed="false"/.test(thermalBtn(off)[0] ?? '') && /aria-pressed="true"/.test(thermalBtn(on)[0] ?? ''));
	const b3 = (off.match(/<button[^>]*data-map-tool="3d"[^>]*>/) ?? [''])[0];
	ok('tools: without the key the 3D city is disabled with its reason', /aria-disabled="true"/.test(b3) && /Needs the Cesium ion key/.test(b3));
	const onB = html(M.MapTools, { ...toolsProps, can3d: true, is3d: true });
	const offB = html(M.MapTools, { ...toolsProps, can3d: true, is3d: false });
	const b3on = (onB.match(/<button[^>]*data-map-tool="3d"[^>]*>/) ?? [''])[0];
	const b3off = (offB.match(/<button[^>]*data-map-tool="3d"[^>]*>/) ?? [''])[0];
	ok('tools: the 3D tool is a one-tap switch — satellite 3D pressed says "Switch to the city map", the city map says "Switch to satellite 3D"', /aria-pressed="true"/.test(b3on) && /title="Switch to the city map"/.test(b3on) && /aria-pressed="false"/.test(b3off) && /title="Switch to satellite 3D"/.test(b3off) && /aria-label="Satellite 3D"/.test(b3on));
	ok('tools: 3D, thermal, corridor stats, legend, measure, follow, zoom in/out, north — in that order', JSON.stringify([...off.matchAll(/data-map-tool="([a-z-0-9]+)"/g)].map((m) => m[1])) === JSON.stringify(['3d', 'thermal', 'stats', 'legend', 'measure', 'follow', 'zoom-in', 'zoom-out', 'north']));
	const sb = (off.match(/<button[^>]*data-map-tool="stats"[^>]*>/) ?? [''])[0];
	const lb = (off.match(/<button[^>]*data-map-tool="legend"[^>]*>/) ?? [''])[0];
	ok('tools: the stats toggle is closed by default (aria-pressed false), the legend toggle reflects it shown', /aria-pressed="false"/.test(sb) && /aria-controls="v3-stats-panel"/.test(sb) && /aria-pressed="true"/.test(lb));
	ok('tools: every tool button sits on the glass surface', (off.match(/class="[^"]*\btb\b[^"]*v3-glass|class="[^"]*v3-glass[^"]*\btb\b/g) ?? []).length >= 7);

	const card = html(M.SelectionCard, {
		art: '/a.svg',
		kind: 'Vehicle pursuit',
		title: 'Pursuit of',
		plate: { mark: 'MH47EM•••1', masked: true },
		tags: [{ text: 'Reported stolen', tone: 'alert' }, { text: 'Authorise pursuit waits', tone: 'decide' }, { text: 'third', tone: 'neutral' }],
		stats: [{ value: '14 min', label: 'since the last read' }, { value: '95 km/h', label: 'last speed' }, { value: '3', label: 'junctions' }, { value: 'x', label: 'fourth' }],
		primary: { href: '/decide/stolen-sighting%3Av1', text: 'Review' },
		details: '/#items=vehicle%3Av1',
		follow: { pressed: false, disabled: false, title: 'Follow the selection' },
		lang: 'en',
		onclose: noop,
		onfollow: noop,
	});
	ok('card: at most 2 tags and 3 figures', (card.match(/data-tone=/g) ?? []).length === 2 && (card.match(/class="stat svelte/g) ?? []).length === 3);
	ok('card: one primary verb → its home in Decide; no Approve / Apply', (card.match(/data-testid="v3-selection-primary"/g) ?? []).length === 1 && /href="\/decide\/stolen-sighting%3Av1"/.test(card) && !/>\s*(Approve|Apply)\b/i.test(card));
	ok('card: the mark is masked in a PlateChip with its screen-reader words', /data-v3="plate" data-masked="true"/.test(card) && /registration mark masked/.test(card) && !/MH06EM\d{4}/.test(card));

	const rows = [
		{ id: 'units', label: 'Units', group: 'response', count: 0, hint: '', error: null, visible: false, empty: true, simulated: false, emulated: false, paused: false },
		{ id: 'cameras', label: 'Cameras', group: 'traffic', count: 28, hint: '', error: null, visible: true, empty: false, simulated: false, emulated: true, paused: false },
		{ id: 'flow', label: 'Flow', group: 'traffic', count: 49, hint: '', error: null, visible: true, empty: false, simulated: true, emulated: false, paused: false },
		{ id: 'waterlog', label: 'Waterlogging', group: 'traffic', count: 7, hint: '', error: null, visible: true, empty: false, simulated: false, emulated: false, paused: false },
		{ id: 'forecast', label: 'Forecast', group: 'traffic', count: 0, hint: '', error: null, visible: false, empty: true, simulated: false, emulated: false, paused: false },
	];
	const sheet = html(M.LayersSheet, { rows, is3d: false, can3d: false, why3d: 'Needs the key', lang: 'en', onlayer: noop, on3d: noop, onclose: noop });
	ok('sheet: base map as radios, layers as switches with their state', (sheet.match(/role="radio"/g) ?? []).length === 2 && (sheet.match(/role="switch"/g) ?? []).length === 13 && /data-layer="cameras"[^>]*|aria-checked="true"[^>]*data-layer="cameras"/.test(sheet));
	ok('sheet: the waterlogging row says what it holds and that it is modelled; the forecast row (off) what it would show', /7 roads at risk in the next 2 hours/.test(sheet) && /Modelled/.test(sheet) && /Roads forecast to cross 0\.8 V\/C within 2 hours/.test(sheet));
	const sheetHs = html(M.LayersSheet, { rows, is3d: false, can3d: false, why3d: 'Needs the key', lang: 'en', onlayer: noop, on3d: noop, onclose: noop, hindsightOn: true });
	ok('sheet: on the replay night the waterlogging row says Hindsight, never live', /7 roads under water in the replay/.test(sheetHs) && /Hindsight/.test(sheetHs));
	ok('sheet: provenance in words — the simulated feed and the emulated cameras', /Simulated on 49 roads/.test(sheet) && /Emulated/.test(sheet) && /Simulated/.test(sheet));
	ok('sheet: an OFF layer says what it would show, never "none"', /Police, traffic and 108 units/.test(sheet));
	{
		const cfRows = [...rows, { id: 'cyclone', label: 'Cyclone', group: 'intelligence', count: 0, hint: '', error: null, visible: true, empty: true, simulated: false, emulated: false, paused: false }];
		const cfSheet = html(M.LayersSheet, { rows: cfRows, is3d: false, can3d: false, why3d: 'Needs the key', lang: 'en', onlayer: noop, on3d: noop, onclose: noop });
		ok('sheet: the City feeds rows appear with their honest tags, and the cyclone row says "No active cyclone"', /City feeds/.test(cfSheet) && /data-layer="air"/.test(cfSheet) && /data-layer="cyclone"/.test(cfSheet) && /No active cyclone/.test(cfSheet) && /Not an official CPCB AQI/.test(cfSheet) && /From GDACS, a live open feed/.test(cfSheet));
	}
	ok('sheet: the Vehicles-only rule closes it', /Vehicles only\. Cameras read registration marks; no images, frames or faces are kept\./.test(sheet));

	const item = (k, g) => ({ key: k, group: g, urn: k, art: '/a.svg', kind: '', title: k, plate: null, meta: 'm', right: null, deadline: null, since: null, decisions: 0, review: null, prov: null });
	const panel = html(M.NowPanel, { items: [item('a', 'live'), item('b', 'reported')], on: { live: true, decide: true, reported: false, planned: true }, selKey: 'a', now: 0, clock: '19:42:06', lang: 'en', replaying: false, replayBlocked: 'v3m_replay_live_move', onselect: noop, onreplay: noop, onlive: noop });
	ok('now: a hidden group leaves the list; the selected row is aria-current', !/data-group="reported"/.test(panel) && /aria-current="true"[^>]*data-key="a"/.test(panel));
	ok('now: Replay is disabled with its reason while a movement is live', /data-testid="v3-now-replay"[^>]*aria-disabled="true"|aria-disabled="true"[^>]*data-testid="v3-now-replay"/.test(panel) && /A movement is live/.test(panel));
	const chips = html(M.MapChips, { on: { live: true, decide: false, reported: true, planned: true }, counts: { live: 3, decide: 4, reported: 4, planned: 3 }, layersOn: 2, sheetOpen: false, lang: 'hi', ontoggle: noop, onlayers: noop });
	ok('chips: toggles with aria-pressed and their counts, in HI', (chips.match(/aria-pressed="(true|false)"/g) ?? []).length === 4 && /data-group="decide"[^>]*data-count="4"|aria-pressed="false"[^>]*data-group="decide"/.test(chips) && /आपके निर्णय की प्रतीक्षा/.test(chips) && /2 चालू/.test(chips));
	ok('legend: three state lines and the data clock (waiting until a live feed answers)', (html(M.Legend3, { lang: 'en' }).match(/<span[ >]/g) ?? []).length === 4 && /data-legend="updated"[^>]*>.*Waiting for the first reading/s.test(html(M.Legend3, { lang: 'en' })));
	{
		const live = html(M.Legend3, { lang: 'en', flow: true, units: true, live: true, updatedAt: '20:41:07' });
		ok(
			'legend: the live city adds its lines (road colour, moving dots at 20×, emulated units, pulses) and "Map data updated hh:mm:ss IST"',
			['flow', 'dots', 'units', 'pulse'].every((k) => new RegExp(`data-legend="${k}"`).test(live)) && /Map data updated 20:41:07 IST/.test(live) && /simulated feed, 20× speed/.test(live) && /\(emulated\)/.test(live),
		);
	}
	const lg = html(M.Legend3, { lang: 'en', hideLabel: 'Hide the legend', onhide: noop });
	ok('legend: terse (a few words per entry), on glass, with its own hide button', /v3-glass/.test(lg) && /aria-label="Hide the legend"/.test(lg) && ['v3m_lg_decide', 'v3m_lg_alert', 'v3m_lg_route'].every((k) => text(M.pack.MAP3_PACKS.en[k]).split(' ').length <= 4));
	const sp = html(M.StatsPanel, {
		sections: [
			{ key: 'band', title: 'Signal band', figures: [{ value: 'Green', label: 'since 14:37 IST' }], tags: [], note: null },
			{ key: 'traffic', title: 'Traffic on the corridors', figures: model.trafficFigures({ avgSpeedKmh: 31.6, avgCongestionIdx: 0.42, congestedSegments: 7, criticalSegments: 2, totalSegments: 49, status: 'amber' }, L).figures, tags: [{ text: 'Simulated', tone: 'dashed' }], note: null },
		],
		title: 'Corridor stats',
		closeLabel: 'Close the corridor stats',
		analystLabel: 'Full analysis in Analyst',
		onclose: noop,
	});
	ok('stats: the corridor figures with their provenance, on glass, one link to Analyst — no table', /32 km\/h/.test(sp) && /42 %/.test(sp) && /7 \/ 49/.test(sp) && /Simulated/.test(sp) && /v3-glass/.test(sp) && /href="\/analyst"/.test(sp) && !/<table/.test(sp));
	ok('stats: no fresh reading says so (never a number)', model.trafficFigures({ avgSpeedKmh: 0, avgCongestionIdx: 0, congestedSegments: 0, criticalSegments: 0, totalSegments: 49, status: 'no_data' }, L).figures.length === 0 && model.trafficFigures(null, L).note === 'Not read yet.');
	ok('stats: the duplicate finder catches a figure shown twice', model.repeatedFigures([{ value: '3 min', label: 'to X' }], [{ value: '3 min', label: 'to X' }, { value: '9', label: 'y' }]).length === 1);
}

// ─── wiring (source) ─────────────────────────────────────────────────────────
{
	const read = (p) => readFileSync(path.join(SRC, p), 'utf8');
	const walkDir = (d) => readdirSync(d).flatMap((f) => (statSync(path.join(d, f)).isDirectory() ? walkDir(path.join(d, f)) : [path.join(d, f)]));
	const canvas = read('lib/gods-eye/GodsEyeCanvas.svelte');
	ok('canvas: chrome "v3" is accepted and draws with the v2 symbology', /chrome\?: 'legacy' \| 'v2' \| 'v3'/.test(canvas) && /const chrome: 'legacy' \| 'v2' = v3 \? 'v2'/.test(canvas));
	ok('canvas: under v3 the v2 toolbar, layer panel, legend, nav and readout are not drawn', /\{#if !v3\}\s*<MapToolbar/.test(canvas) && /\{#if !v3\}\s*\{#if layersOpen && !onLayers\}/.test(canvas));
	ok('canvas: v3 tools go through mapChrome.act; defaultLayers seed the layers', /act: v3 \? v3Act : undefined/.test(canvas) && /untrack\(\(\) => defaultLayers\)/.test(canvas));
	ok('canvas: the Layers and Legend panels load on first open (off the first paint of every route)', !/import LayerTree from/.test(canvas) && !/import MapLegend from/.test(canvas) && /import\('\.\/hud\/map\/LayerTree\.svelte'\)/.test(canvas));
	ok('/gods-eye still mounts the canvas with chrome="v2" (unchanged)', /chrome="v2"/.test(read('routes/(deck)/gods-eye/+page.svelte')));
	const page = read('lib/v3/map/MapPage.svelte');
	ok('focus: the canvas runs v3 in focus mode; Show all clears and returns to the city', /focus: v3/.test(canvas) && /what === 'home'\) flyHome/.test(canvas) && /function showAll\(\)[\s\S]{0,80}closeCard\(\);[\s\S]{0,40}mapChrome\.act\('home'\)/.test(page));
	ok('stats: closed by default; the layers and stats panels live in the LEFT column', /let statsOpen = \$state\(false\)/.test(page) && /<div class="left"[\s\S]*<LayersSheet[\s\S]*<StatsPanel[\s\S]*<div class="now">/.test(page));
	ok('no threat posture, no audit or analysis table on /map', !/AMA|posture|threat|<table|AuditTable|AnalysisDock|DecisionLog/i.test(walkDir(path.join(SRC, 'lib/v3/map')).map((f) => readFileSync(f, 'utf8').replace(/\/\*[\s\S]*?\*\/|\/\/.*|<!--[\s\S]*?-->/g, '')).join('\n')));
	ok('/map mounts the V3 map page', /MapPage/.test(read('routes/(v3)/map/+page.svelte')) && /chrome="v3"/.test(read('lib/v3/map/MapPage.svelte')) && /defaultLayers=\{canvasLayers\}/.test(read('lib/v3/map/MapPage.svelte')) && /startLayers\(V3_DEFAULT_LAYERS,/.test(read('lib/v3/map/MapPage.svelte')));
	ok('rail: Map is /map', /id: 'map', href: '\/map'/.test(read('lib/v3/shell/nav.ts')));
	const walk = (d) => readdirSync(d).flatMap((f) => (statSync(path.join(d, f)).isDirectory() ? walk(path.join(d, f)) : [path.join(d, f)]));
	const importers = walk(SRC)
		.filter((f) => /\.(svelte|ts)$/.test(f) && !f.includes(`${path.sep}lib${path.sep}v3${path.sep}map${path.sep}`) && !f.includes(`(v3)${path.sep}map`) && !f.includes(`${path.sep}lib${path.sep}v3${path.sep}assistant${path.sep}`))
		.filter((f) => /v3\/map\/(MapPage|MapChips|NowPanel|SelectionCard|MapTools|LayersSheet|WeatherChip|Legend3|StatsPanel|glass|model|packs\.map3)/.test(readFileSync(f, 'utf8')));
	ok('budget: no V3 map module is imported outside /map (none can load on /gods-eye, /, /ops)', importers.length === 0, importers.map((f) => path.relative(DECK, f)).join(','));
}

console.log(failures ? `\nv3-map.unit: ${failures} failure(s)` : '\nv3-map.unit: ALL OK');
process.exit(failures ? 1 : 0);
