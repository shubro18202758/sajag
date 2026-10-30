/**
 * V3 Home unit test (V3-P01; V3-SPEC §6.1, §10 P1) — zero browser.
 *
 *   node tests/home.unit.mjs
 *
 * esbuild bundles the REAL modules — src/lib/v3/home/{model, view}, src/lib/v3/map/{mercator, tiles},
 * src/lib/v3/shell/alerts.svelte, src/lib/v3/ui/redaction, decisions/{units, register}, the ops store,
 * the city registry, the workspace selectors and cardFigures — with `$lib` aliased, rune identity stubs
 * and every `.svelte` component stubbed (the decisions.unit.mjs harness). A fetch stub answers every GET
 * from the hermetic fixture world of tests/home-smoke.mjs (refusing any non-GET), so the units, events,
 * reports and counts are what the real parsers make of real wire shapes.
 *
 * Asserts:
 *   - pickFeatured: the soonest-deadline unit; the 15 s hysteresis keeps the featured unit against a
 *     new deadline < 15 s sooner and yields to one ≥ 15 s sooner; an expired or vanished unit yields;
 *     no deadline anywhere keeps the first in order; nothing waiting → null;
 *   - with the fixture world: decisionUnits() is in the expected order and the featured unit is the
 *     soonest-deadline one; railOrder puts it first;
 *   - counts equal the canonical selectors: selectors.decisionUnits() = decisionUnits() = 4; cardFigures
 *     reported = count(osint_event) = reportTally total; watchlisted; liveOpsOf 3; plannedOf 3;
 *   - no raw mark in any view model (titles, whys, hrefs, alt text, labels) without an officer; the
 *     stolen unit's chip is masked; a named officer gets the raw mark in the chip, and clearing the name
 *     masks it again; decision hrefs are the units' V3 home (/decide/<kind>:<id>);
 *   - provenance: one tag per card at most; the AI label only where a model proposed it;
 *   - Mercator: a known projection, a thumb never needs more than 6 tiles, toBox round trip;
 *   - the map grade: an OSM red / orange pixel comes out neutral (never reads as an alert or a decision);
 *   - the chime rule (chimeAllowed) and the alert priming (the units waiting at load never alert);
 *   - redactions: [PERSON] / [AGE] become withheld chips, other text is kept.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { homeFixtures } from './home-smoke.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const OUT = path.join(HERE, 'artifacts', 'home-bundle.mjs');

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
export * as model from './src/lib/v3/home/model';
export * as view from './src/lib/v3/home/view';
export * as merc from './src/lib/v3/map/mercator';
export * as tiles from './src/lib/v3/map/tiles';
export * as alerts from './src/lib/v3/shell/alerts.svelte';
export * as redaction from './src/lib/v3/ui/redaction';
export * as units from './src/lib/decisions/units';
export * as reg from './src/lib/decisions/register';
export * as opsStore from './src/lib/ops/store.svelte';
export * as cityReg from './src/lib/gods-eye/entities/registry.svelte';
export * as wsReg from './src/lib/workspace/registry';
export { selectors, liveWorld } from './src/lib/workspace/world.svelte';
export { cardFigures } from './src/lib/workspace/components/vitals/figures';
export { operatorSession } from './src/lib/shell/session.svelte';
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
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'home-entry.ts' },
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

// ─── the fixture world, served to the real clients ──────────────────────────

const NOW = Date.now();
const fx = homeFixtures(NOW);
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
const { model, view, merc, tiles, alerts, redaction, units: U } = M;
const { ops } = M.opsStore;
const registry = M.cityReg.cityRegistry;

// ─── pickFeatured (pure) ─────────────────────────────────────────────────────

{
	const u = (id, deadline, kind = 'escort-proposal') => ({ kind, id, deadline });
	const T = 1_000_000;
	const A = u('a', T + 48_000);
	const B = u('b', T + 55_000);
	const C = u('c', T + 90_000);
	const N = u('n', null, 'stolen-sighting');
	const pick = (list, prev) => model.pickFeatured(list, prev, T)?.id ?? null;
	ok('pickFeatured: no previous → the soonest-deadline unit', pick([A, B, C, N], null) === 'a');
	ok('pickFeatured: nothing waiting → null', pick([], 'escort-proposal:a') === null);
	ok('pickFeatured: hysteresis keeps the featured unit while the new soonest is < 15 s sooner', pick([A, B, C], 'escort-proposal:b') === 'b');
	ok('pickFeatured: a deadline ≥ 15 s sooner takes over', pick([A, B, C], 'escort-proposal:c') === 'a');
	ok('pickFeatured: an expired featured unit yields', model.pickFeatured([u('x', T - 1), A], 'escort-proposal:x', T)?.id === 'a');
	ok('pickFeatured: a vanished featured unit yields', pick([A, B], 'escort-proposal:gone') === 'a');
	ok('pickFeatured: a deadline beats a featured unit with none', pick([A, N], 'stolen-sighting:n') === 'a');
	ok('pickFeatured: no deadlines at all keeps the featured one', pick([N, u('m', null, 'echallan')], 'echallan:m') === 'm');
	ok('railOrder: the featured unit first, the rest in order', model.railOrder([A, B, C], B).map((x) => x.id).join('') === 'bac');
}

// ─── the fixture world through the real stores ──────────────────────────────

await M.operatorSession.refresh();
ops.applySession(M.operatorSession.gate, M.operatorSession.officer);
await ops.loadGeometry(true);
await registry.refresh();
for (const n of ['pollBoard', 'pollCityBand', 'pollRecommendations', 'pollApproved', 'pollEscorts', 'pollDispatches', 'pollWatchlist', 'pollTrafficFeed', 'pollBrain']) {
	try {
		await (n === 'pollBoard' ? ops.pollBoard(true) : ops[n]());
	} catch (e) {
		console.log(`note ${n}: ${e.message}`);
	}
}
M.reg.register();

const units = U.decisionUnits(ops);
ok('decisionUnits(): the fixture units, soonest deadline first', JSON.stringify(units.map((x) => x.kind)) === JSON.stringify(E.unitOrder), units.map((x) => x.kind).join(', '));
const featured = model.pickFeatured(units, null, Date.now());
const minDeadline = Math.min(...units.filter((x) => x.deadline != null).map((x) => x.deadline));
ok('the featured card is the soonest-deadline unit', featured?.kind === 'escort-proposal' && featured.deadline === minDeadline && featured.deadline === E.escortDeadline, featured ? model.unitKey(featured) : 'none');

// ─── counts = the canonical selectors (SPEC v2 §7.4) ─────────────────────────

const canon = M.selectors.decisionUnits();
ok('decisions: selectors.decisionUnits() = decisionUnits() (the count Home shows)', canon.length === units.length && units.length === E.units, `${canon.length}/${units.length}`);
const figures = M.cardFigures({ selectors: M.selectors, registry: M.liveWorld.registry(), unitSources: M.wsReg.registrySize().units, escortProposals: ops.escortProposals.length, corridorSimulated: true });
const reports = registry.byKind('osint_event');
const tally = model.reportTally(reports);
ok('reported: cardFigures = count(osint_event) = the report rail = the tally', figures.reported === reports.length && tally.total === reports.length && reports.length === E.reports, JSON.stringify(tally));
ok('reported tally: 1 official · 2 news · 1 unverified', tally.official === 1 && tally.news === 2 && tally.unverified === 1);
ok('watchlisted: cardFigures = count(vehicle)', figures.watchlisted === E.watchlisted);
ok('cameras answering: 28 of 28', figures.cameras.answering === 28 && figures.cameras.total === 28);
const live = model.liveOpsOf(ops.events);
const planned = model.plannedOf(ops.events, Date.now());
ok('live operations: the 3 active board events (movement and pursuit first)', live.length === E.liveOps && live[0].eventKind === 'protected_movement' && live[1].eventKind === 'vehicle_pursuit', live.map((e) => e.eventKind).join(', '));
ok('coming up: the 3 planned events within 72 h, soonest first', planned.length === E.planned && planned.every((e, i) => i === 0 || Date.parse(e.windowStart) >= Date.parse(planned[i - 1].windowStart)), planned.map((e) => e.eventKind).join(', '));

// ─── masked marks in every view model ────────────────────────────────────────

const RAW = new RegExp(E.rawPlate.split('').join('[ .-]?'), 'i');
const vms = () => ({
	decisions: units.map((u) => view.decisionVM(u, 'en', Date.now())),
	ops: live.map((e) => view.opVM(e, 'en', Date.now(), units)),
	reports: reports.map((e) => view.reportVM(e, 'en', Date.now(), units)),
	planned: planned.map((e) => view.plannedVM(e, 'en', Date.now())),
});
for (const lang of ['en', 'hi', 'mr']) {
	const all = JSON.stringify({ d: units.map((u) => view.decisionVM(u, lang, Date.now())), o: live.map((e) => view.opVM(e, lang, Date.now(), units)) });
	ok(`no raw mark in any view model without an officer (${lang})`, !RAW.test(all) && !ops.officerOn);
}
let V = vms();
const stolen = V.decisions.find((d) => d.kind === 'stolen-sighting');
ok('the stolen unit: the mark in a MASKED chip, the title without it', stolen?.plate?.masked === true && stolen.plate.mark === E.maskedPlate && !stolen.title.includes('WB'), JSON.stringify(stolen?.plate));
ok('decision hrefs: each unit\'s V3 home (/decide/<kind>:<id>), never a mark', V.decisions.every((d) => d.href === `/decide/${encodeURIComponent(d.key)}` && !RAW.test(d.href)));
ops.setDutyOfficer('Sandbox Officer');
V = vms();
const named = V.decisions.find((d) => d.kind === 'stolen-sighting');
ok('a named officer: the chip shows the full mark', ops.officerOn && named?.plate?.masked === false && named.plate.mark === E.rawPlate);
ops.setDutyOfficer('');
V = vms();
ok('clearing the officer masks it again', V.decisions.find((d) => d.kind === 'stolen-sighting')?.plate?.masked === true && !RAW.test(JSON.stringify(V)));

// ─── honesty: provenance, who proposed, the rule in words ────────────────────

ok('at most one provenance tag per card', [...V.decisions, ...V.ops, ...V.planned].every((x) => x.prov == null || typeof x.prov.text === 'string'));
const esc = V.decisions.find((d) => d.kind === 'escort-proposal');
ok('escort proposal: "Proposed by the convoy assistant" (a model proposed it), a provenance tag, the plan-kept rule', esc?.by.ai === true && /convoy assistant/.test(esc.by.text) && !!esc.prov && /current plan is kept/.test(esc.ifNot), `${esc?.by.text} · ${esc?.prov?.text}`);
ok('rules-engine and decision-support units are never labelled AI', V.decisions.filter((d) => d.kind !== 'escort-proposal').every((d) => d.by.ai === false));
ok('the accident report carries "Response proposed"; the unverified one "Verify before acting"', V.reports.some((r) => r.note === 'Response proposed') && V.reports.some((r) => r.verif.text === 'Unverified' && r.note === 'Verify before acting'));
ok('every report links its object page (never a news or social URL)', V.reports.every((r) => r.href.startsWith('/o/osint_event:') && !/https?:/.test(r.href)));
ok('no person field in any view model', !/(person_name|suspect|face_|biometric|author_handle|poster_)/i.test(JSON.stringify(V)));
ok('every thumb has alt text', [...V.decisions, ...V.ops, ...V.reports, ...V.planned].every((x) => typeof x.thumb.alt === 'string' && x.thumb.alt.length > 3));

// ─── Mercator and the tile budget ────────────────────────────────────────────

{
	const [x, y] = merc.project([0, 0], 1);
	ok('Mercator: (0, 0) at zoom 1 is the world centre', Math.abs(x - 256) < 1e-6 && Math.abs(y - 256) < 1e-6);
	const p = merc.project([88.3512, 22.5646], 15);
	ok('Mercator: Kolkata (Esplanade) at zoom 15 is tile 24425/14274 (the OSM grid)', Math.floor(p[0] / 256) === 24425 && Math.floor(p[1] / 256) === 14274, `${Math.floor(p[0] / 256)}/${Math.floor(p[1] / 256)}`);
	let worst = 0;
	for (const [lon, lat] of [[88.3447, 22.5856], [88.2730, 22.5473], [88.4430, 22.5632]])
		for (const z of [13, 14, 15, 16]) worst = Math.max(worst, merc.frame({ center: [lon, lat], zoom: z }, 410, 210)?.tiles.length ?? 99);
	ok('a card thumb (410×210) never needs more than 6 tiles', worst <= 6, `worst ${worst}`);
	const f = merc.frame({ bbox: [88.33, 22.55, 88.37, 22.59], maxTiles: 6 }, 410, 210);
	ok('a fitted frame stays within 6 tiles', !!f && f.tiles.length <= 6, `z${f?.z} · ${f?.tiles.length} tiles`);
	const b = merc.toBox([88.3499, 22.5582], f);
	ok('toBox lands inside the box for a point in the bbox', b[0] > 0 && b[0] < 410 && b[1] > 0 && b[1] < 210);
}

// ─── the map grade neutralises colour ────────────────────────────────────────

{
	// OSM's red (hospital / motorway) and orange (primary road), plus land and water
	const px = new Uint8ClampedArray([230, 60, 60, 255, 252, 214, 164, 255, 242, 239, 233, 255, 170, 211, 223, 255]);
	tiles.gradePixels(px, 4, 1, 'night');
	const hue = (i) => {
		const [r, g, b] = [px[i * 4], px[i * 4 + 1], px[i * 4 + 2]];
		return { r, g, b, redness: r - Math.max(g, b) };
	};
	const red = hue(0);
	const orange = hue(1);
	ok('the night grade: an OSM red pixel is never red (no alert colour on the map)', red.redness < 12, JSON.stringify(red));
	ok('the night grade: an OSM orange road is never orange (no decision colour on the map)', orange.redness < 12, JSON.stringify(orange));
	ok('the night grade is dark (every graded pixel below the light ink)', [0, 1, 2, 3].every((i) => Math.max(px[i * 4], px[i * 4 + 1], px[i * 4 + 2]) < 120));
}

// ─── the chime rule and the alert priming ───────────────────────────────────

{
	const { chimeAllowed, v3Alerts } = alerts;
	ok('chime: a new real decision chimes when the chime is on', chimeAllowed([{ emulated: false }], true, false));
	ok('chime: never when the officer turned it off', !chimeAllowed([{ emulated: false }], false, true));
	ok('chime: an emulated decision is silent unless the console declares exercise data', !chimeAllowed([{ emulated: true }], true, false) && chimeAllowed([{ emulated: true }], true, true));
	ok('chime: nothing new, no chime', !chimeAllowed([], true, true));
	const list = units.map((u) => ({ key: model.unitKey(u), title: u.title, href: '/ops', emulated: U.unitEmulated(u) }));
	v3Alerts.syncDecisions(list, false);
	ok('alerts: the units waiting at load prime the list (no alert, no chime)', v3Alerts.items.length === 0 && v3Alerts.played === 0);
	v3Alerts.syncDecisions([...list, { key: 'corridor-request:new', title: 'Decide the 108 corridor for 108-MH-11', href: '/ops', emulated: false }], false);
	ok('alerts: one new waiting decision → one alert, one chime', v3Alerts.items.length === 1 && v3Alerts.unread === 1 && v3Alerts.played === 1);
	v3Alerts.syncDecisions([...list, { key: 'corridor-request:new', title: 'x', href: '/ops', emulated: false }, { key: 'echallan:emu', title: 'x', href: '/ops', emulated: true }], false);
	ok('alerts: an emulated one is listed silently on a console not in an exercise', v3Alerts.items.length === 2 && v3Alerts.played === 1);
	ok('alerts: titles are the units\' stored, masked titles', !v3Alerts.items.some((i) => RAW.test(i.title)) && !list.some((i) => RAW.test(i.title)));
}

// ─── redactions ──────────────────────────────────────────────────────────────

{
	const parts = redaction.redactionParts('Robbery near Babughat; [PERSON], [AGE] named in report');
	ok('redactions: [PERSON] and [AGE] become chips, the rest stays text', parts.filter((p) => p.token).map((p) => redaction.redactionKey(p.token)).join(',') === 'v3_redact_name,v3_redact_age' && parts.map((p) => p.text).join('') === 'Robbery near Babughat; [PERSON], [AGE] named in report');
	ok('redactions: an ordinary bracket is kept as text', redaction.redactionParts('Ring Road [SP] closed').every((p) => p.token === null));
}

ok('the harness sent no write', writes.length === 0, writes.join(' | '));
console.log(failures ? `\n${failures} FAILED` : '\nhome.unit: ALL OK');
process.exit(failures ? 1 : 0);
