/**
 * The situation wall's unit test (UI-S5B; SPEC §5.3 "Situation wall parts",
 * §6.3, §12.3).
 *
 *   node tests/wall.unit.mjs
 *
 * esbuild bundles the REAL wall modules (src/lib/decisions/wall: metrics,
 * band-chart, feeds, range, wall-data's history parser, the units bridge)
 * with `$lib` aliased to src/lib and the Svelte runes stubbed as plain
 * values (the workspace.unit.mjs pattern). A second bundle compiles the
 * wall's Svelte components for the SERVER (svelte/compiler, generate:
 * 'server') and renders them with svelte/server, so the assertions read the
 * markup the page ships, not a model of it.
 *
 * Asserts:
 *   metric strip   eight cells in the §6.3 order; EXACTLY FOUR carry a
 *                  counter (active-events, pending-decisions,
 *                  units-dispatched, ambulance-windows); the rendered strip
 *                  has exactly four `data-prim="data-tile"`, each with
 *                  `data-counter` and `data-value`, and nothing else is a
 *                  data tile; a zero recedes (`data-zero="true"`, never the
 *                  warning ink) and a non-zero does not; sparklines render
 *                  only on a wide strip
 *   band chart     a real IST axis (aligned ticks, hh:mm labels, ≥ 64 px
 *                  apart, inside the plot; day labels on a 7 d range);
 *                  nothing drawn before the first reading; repeats collapse
 *                  to steps with a join at each change; BLACK is the
 *                  translucent fill WITH the 1 px hairline, every other
 *                  band has no stroke — in the model and in the rendered SVG
 *   feeds          the status mapping of every source (waiting / ok /
 *                  simulated / emulated / degraded / down), the Data
 *                  popover's three-step scale and worst dot, the rows in
 *                  their fixed order, and the rendered section's tags
 *   range          hostile stored values fall back to 6 h; the window
 *   history        the event history parser (closed events included,
 *                  newest change first, a non-event dropped)
 *   units bridge   one stolen vehicle is ONE unit whatever its sightings;
 *                  e-challans, escort proposals (with their deadline) and
 *                  requested dispatches are units; decided rows are not
 *   provenance     a promoted OSINT event states its verification VISIBLY
 *                  ("News-reported", …) and "credibility 0.65"; an unknown
 *                  state claims none; a non-OSINT event has none — in the
 *                  model and in the rendered row (EventProvenance)
 *   row marks      a TEST row always shows a VISIBLE "Test" tag (the .text
 *                  label, never only the hidden .sr one); a uniformly
 *                  emulated list states it once in the header and its rows
 *                  carry no glyph; a mixed list marks each emulated row with
 *                  the compact glyph; test rows are kept out of the counts;
 *                  the row's state word for planning matches the inspector
 *   hand-off       Open in workspace / the Mode chip carry the operator's
 *                  pick, else the docked inspector's object, never a bad URN
 *   pack           packs.wall.ts: HI and MR cover every EN key
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import { mkdirSync, readFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
// the bundles go to the OS temp dir (never tests/artifacts/**); WALL_UNIT_OUT overrides
const OUT_DIR = process.env.WALL_UNIT_OUT ?? path.join(os.tmpdir(), 'sajag-wall-unit');
const OUT = path.join(OUT_DIR, 'wall-bundle.mjs');
const OUT_SSR = path.join(OUT_DIR, 'wall-ssr-bundle.mjs');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const count = (s, re) => (s.match(re) ?? []).length;

mkdirSync(OUT_DIR, { recursive: true });
const require = createRequire(path.join(DECK, 'package.json'));
const esbuild = require('esbuild');

// ─── 1. the wall's pure modules ─────────────────────────────────────────────

const ENTRY = `
export * as metrics from './src/lib/decisions/wall/metrics';
export * as chart from './src/lib/decisions/wall/band-chart';
export * as feeds from './src/lib/decisions/wall/feeds';
export * as range from './src/lib/decisions/wall/range';
export * as data from './src/lib/decisions/wall/wall-data.svelte';
export * as units from './src/lib/decisions/wall/units-bridge';
export * as prov from './src/lib/decisions/wall/provenance';
export * as share from './src/lib/decisions/wall/share';
export * as pack from './src/lib/i18n/packs.wall';
export { t } from './src/lib/i18n/strings';
`;
const built = await esbuild.build({
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'wall-entry.ts' },
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	outfile: OUT,
	logLevel: 'silent',
	// the units bridge registers a Svelte component (the pursuit bridge is not bundled); none is rendered here
	loader: { '.svelte': 'empty' },
});
ok('bundle builds (esbuild, $lib aliased)', built.errors.length === 0, `${built.errors.length} errors`);

// Svelte 5 runes are compiler macros: identity stubs run the stores as plain classes.
globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });

const M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
const { metrics, chart, feeds, range, data, units, prov, share, pack, t } = M;

// ─── metric strip (model) ───────────────────────────────────────────────────

const NOW = Date.parse('2026-10-24T21:00:00Z'); // 02:30 IST, 25 Oct
const base = {
	lang: 'en',
	now: NOW,
	active: 0,
	open: 1,
	history: 18,
	units: 4,
	soonestDeadline: null,
	oldestWaiting: NOW - 6 * 3_600_000,
	dispatched: 0,
	dispatchesClosed: 9,
	ambulance: 2,
	ambulanceClosed: 3,
	speedKmh: 53.5,
	speedSource: 'simulated',
	speedSamples: [52, 53, 53.5, 54],
	roads: 49,
	congested: 0,
	critical: 0,
	reads24: 19,
	readVehicles: 1,
	lastRead: NOW - 3_600_000,
	readBins: metrics.hourlyBins([NOW - 3_600_000, NOW - 3_500_000, NOW - 20 * 3_600_000], NOW),
	anomalies: 23,
};
const cells = metrics.metricCells(base);
ok('metric strip: eight cells in the §6.3 order', cells.length === 8 && cells.map((c) => c.key).join(',') === 'active,decisions,units,ambulance,speed,congested,reads,anomalies', cells.map((c) => c.key).join(','));
const counters = cells.filter((c) => c.counter);
ok('metric strip: exactly four cells are counters', counters.length === 4, counters.map((c) => c.counter).join(','));
ok('metric strip: the counters are the commander four, in order', counters.map((c) => c.counter).join(',') === metrics.COUNTER_KEYS.join(',') && metrics.COUNTER_KEYS.join(',') === 'active-events,pending-decisions,units-dispatched,ambulance-windows');
ok('metric strip: a zero recedes (zero flag on every 0)', cells.filter((c) => c.value === 0).every((c) => c.zero) && cells.filter((c) => c.value !== 0).every((c) => !c.zero), cells.map((c) => `${c.key}=${c.value}${c.zero ? '(zero)' : ''}`).join(' '));
ok('metric strip: "Decisions waiting" is the only warning cell', cells.filter((c) => c.intent === 'warning').map((c) => c.key).join(',') === 'decisions');
ok('metric strip: sparklines only on corridor speed and watchlist reads', cells.filter((c) => c.spark).map((c) => c.key).join(',') === 'speed,reads');
ok('metric strip: hourly bins count the last 24 h, oldest first', base.readBins.length === 24 && base.readBins[23] === 2 && base.readBins[4] === 1 && base.readBins.reduce((a, b) => a + b, 0) === 3, base.readBins.join(''));
const sub = Object.fromEntries(cells.map((c) => [c.key, c.sub]));
ok('metric strip: sub lines say their scope', sub.active === '1 open · 18 in history' && sub.decisions === 'Oldest waiting 6 h' && sub.units === '9 dispatches closed' && sub.reads === '1 vehicle · last 01:30', JSON.stringify(sub));
const expiring = metrics.metricCells({ ...base, soonestDeadline: NOW + 47_000 });
ok('metric strip: a time-boxed decision shows its countdown', expiring[1].sub === 'Escort proposal expires in 0:47', expiring[1].sub);
const none = metrics.metricCells({ ...base, units: 0, active: 0, dispatched: 0, ambulance: 0, speedKmh: null, speedSamples: [], congested: null, roads: null, reads24: 0, readBins: new Array(24).fill(0), anomalies: 0, history: null });
ok('metric strip: nothing waiting is said, never orange (zero recedes)', none[1].sub === 'Nothing waits for an officer' && none[1].zero === true);
ok('metric strip: an unknown speed is a dash, never 0 km/h', none[4].value === '—' && none[4].unit === null && none[4].zero === false && none[4].spark === null);

// ─── band chart (model) ─────────────────────────────────────────────────────

const H = 3_600_000;
const win = [NOW - 6 * H, NOW];
const m = chart.bandChart(
	[
		{ ts: NOW - 4 * H, band: 'GREEN' },
		{ ts: NOW - 3.5 * H, band: 'GREEN' },
		{ ts: NOW - 3 * H, band: 'AMBER' },
		{ ts: NOW - 2 * H, band: 'BLACK' },
		{ ts: NOW - 1 * H, band: 'RED' },
	],
	win,
	{ width: 400 },
);
const ticks = m.ticks;
const istMinute = (ms) => new Date(ms + 330 * 60_000).getUTCMinutes();
ok('band chart: the axis has IST-aligned ticks across the range', ticks.length >= 3 && ticks.every((tk) => istMinute(tk.t) === 0 && tk.t >= win[0] && tk.t <= win[1]), ticks.map((tk) => tk.label).join(' '));
ok('band chart: tick labels are IST hh:mm', ticks.every((tk) => /^\d{2}:\d{2}$/.test(tk.label)) && ticks[ticks.length - 1].label === '02:00', ticks.map((tk) => tk.label).join(' '));
ok('band chart: ticks sit inside the plot, at least 64 px apart', ticks.every((tk) => tk.x >= m.plot.x0 && tk.x <= m.plot.x1) && ticks.slice(1).every((tk, i) => tk.x - ticks[i].x >= 63.9), ticks.map((tk) => tk.x).join(' '));
const week = chart.axisTicks(NOW - 7 * 24 * H, NOW, 52, 392);
ok('band chart: a 7 d range labels days', week.length >= 2 && week.every((tk) => /^\d{1,2} [A-Z][a-z]{2}$/.test(tk.label)), week.map((tk) => tk.label).join(' '));
ok('band chart: four ladder rows, Black on top, Green at the bottom', m.rows.map((r) => r.band).join(',') === 'BLACK,RED,AMBER,GREEN' && m.rows[0].y < m.rows[3].y);
ok('band chart: repeats collapse into steps (4 changes → 4 segments, 3 joins)', m.segments.length === 4 && m.joins.length === 3, m.segments.map((s) => s.band).join(','));
ok('band chart: nothing is drawn before the first reading', Math.min(...m.segments.map((s) => s.x)) > m.plot.x0 + 100, `first x ${m.segments[0]?.x}`);
const black = m.segments.find((s) => s.band === 'BLACK');
ok('band chart: BLACK is the translucent fill with the 1 px hairline', black?.fill === 'var(--v-band-black-fill)' && black.stroke === 'var(--v-band-black-hairline)' && chart.BLACK_HAIRLINE === 'var(--v-band-black-hairline)');
ok('band chart: every other band has no stroke', m.segments.filter((s) => s.band !== 'BLACK').every((s) => s.stroke === null && s.fill === `var(--v-band-${s.band.toLowerCase()})`));
ok('band chart: the newest band holds to the end of the window', Math.abs(m.segments[m.segments.length - 1].x + m.segments[m.segments.length - 1].w - m.plot.x1) < 0.2);
const sinceOnly = chart.bandChart([], win, { width: 400, current: { band: 'GREEN', since: NOW - 1.5 * H } });
ok('band chart: the committed band from its entry time when no reading came yet', sinceOnly.segments.length === 1 && sinceOnly.segments[0].band === 'GREEN' && !sinceOnly.empty);
ok('band chart: no reading at all is empty, never a guessed Green', chart.bandChart([], win, { width: 400 }).empty === true);

// ─── feeds (status mapping) ─────────────────────────────────────────────────

const F = feeds;
const table = [
	['registry idle', F.registryStatus('idle', null), 'waiting'],
	['registry ok', F.registryStatus('ok', null, 0.1), 'ok'],
	['registry ok, mostly emulated', F.registryStatus('ok', null, 0.8), 'emulated'],
	['registry blip (ok with a note)', F.registryStatus('ok', 'city fusion API blip', 0), 'degraded'],
	['registry down', F.registryStatus('down', 'unreachable'), 'down'],
	['registry not deployed', F.registryStatus('not-deployed', 'x'), 'down'],
	['city feed idle', F.cityFeedStatus('idle', null), 'waiting'],
	['city feed ok', F.cityFeedStatus('ok', null), 'ok'],
	['city feed ok with a note', F.cityFeedStatus('ok', 'blip'), 'degraded'],
	['city feed down', F.cityFeedStatus('down', 'x'), 'down'],
	['traffic simulated', F.trafficStatus('simulated', null), 'simulated'],
	['traffic mixed', F.trafficStatus('mixed', null), 'degraded'],
	['traffic live', F.trafficStatus('live', null), 'ok'],
	['traffic none', F.trafficStatus('none', null), 'down'],
	['traffic not read yet', F.trafficStatus(null, null), 'waiting'],
	['traffic read failed', F.trafficStatus(null, 'HTTP 502'), 'down'],
	['cameras emulated', F.kindFeedStatus({ status: 'ok', count: 28 }, 'emulated'), 'emulated'],
	['cameras live', F.kindFeedStatus({ status: 'ok', count: 28 }, 'live'), 'ok'],
	['cameras unavailable', F.kindFeedStatus({ status: 'unavailable', count: 0 }, null), 'down'],
	['model not read', F.modelStatus(null, null), 'waiting'],
	['model loaded, full tier', F.modelStatus({ reachable: true, decider: { state: 'loaded' } }, 'FULL'), 'ok'],
	['model loaded, tactical fallback', F.modelStatus({ reachable: true, decider: { state: 'loaded' } }, 'TACTICAL_FALLBACK'), 'degraded'],
	['model loading', F.modelStatus({ reachable: true, decider: { state: 'loading' } }, 'FULL'), 'degraded'],
	['model unreachable', F.modelStatus({ reachable: false, decider: { state: 'unknown' } }, null), 'down'],
	['emulator not probed', F.emulatorStatus(false, 0), 'waiting'],
	['emulator online', F.emulatorStatus(true, NOW), 'emulated'],
	['emulator offline', F.emulatorStatus(false, NOW), 'down'],
	['board not read', F.boardStatus('offline', 0), 'waiting'],
	['board live', F.boardStatus('live', NOW), 'ok'],
	['board with fixtures', F.boardStatus('mixed', NOW), 'degraded'],
	['board offline', F.boardStatus('offline', NOW), 'down'],
];
const wrong = table.filter(([, got, want]) => got !== want);
ok('feeds: every source maps to its status', wrong.length === 0, wrong.map(([n, g, w]) => `${n}: ${g} ≠ ${w}`).join(' | ') || `${table.length} cases`);
ok('feeds: provenance is not a fault (ok / simulated / emulated → ok on the Data scale)', ['ok', 'simulated', 'emulated'].every((s) => F.toFeedStatus(s) === 'ok'));
ok('feeds: waiting and degraded read degraded, down reads down', F.toFeedStatus('waiting') === 'degraded' && F.toFeedStatus('degraded') === 'degraded' && F.toFeedStatus('down') === 'down');
const fx = {
	now: NOW,
	registry: { status: 'ok', note: null, size: 312, updatedAt: NOW - 2000, emulatedShare: 0.3 },
	cityFeed: { status: 'ok', note: null, rows: 115, updatedAt: NOW - 1000 },
	traffic: { label: 'simulated', note: null, segments: 49, dataAgeSec: 1.4 },
	cameras: { feed: { status: 'ok', count: 28, ageSec: 4 }, source: 'emulated' },
	board: { status: 'live', updated: NOW - 3000, open: 1 },
	model: { brain: { reachable: true, decider: { state: 'loaded', p95Ms: 2300 }, checkedAt: NOW - 5000 }, tier: 'FULL' },
	emulator: { online: true, lastChecked: NOW - 6000, tapes: 10 },
};
const rows = F.feedRows(fx, 'en');
ok('feeds: seven sources in a fixed order', rows.map((r) => r.id).join(',') === 'registry,city-feed,traffic,cameras,events,model,emulator', rows.map((r) => r.id).join(','));
ok('feeds: volumes and ages', rows[0].volume === '312 objects' && rows[0].ageSec === 2 && rows[2].volume === '49 roads' && rows[2].ageSec === 1 && rows[5].volume === 'p95 2.3 s', rows.map((r) => `${r.id}:${r.volume}/${r.ageSec}`).join(' '));
ok('feeds: the worst status is ok on a healthy simulated city', F.worstStatus(rows) === 'ok');
ok('feeds: one source down makes the Data dot down', F.worstStatus(F.feedRows({ ...fx, emulator: { online: false, lastChecked: NOW, tapes: 0 } }, 'en')) === 'down');
const df = F.dataFeeds(rows, 'en');
ok('feeds: the Data popover rows carry the same names and the provenance in their label', df.length === 6 && df[2].name === 'Traffic flow' && df[2].status === 'ok' && df[2].label === '49 roads, simulated', JSON.stringify(df[2]));
// F-21: the popover's own model block states the decision model; no second "Decision model" row graded on the tier
{
	const degradedTier = F.feedRows({ ...fx, model: { ...fx.model, tier: 'DEGRADED' } }, 'en');
	ok(
		'F-21: the Data popover carries no "Decision model" feed row (its model block says it once), yet the model still grades the Data dot',
		!F.dataFeeds(degradedTier, 'en').some((r) => r.name === 'Decision model') && degradedTier.some((r) => r.id === 'model' && r.status === 'degraded') && F.worstStatus(degradedTier) === 'degraded',
		F.dataFeeds(degradedTier, 'en').map((r) => r.name).join(', '),
	);
}
// F-04: a page that reads no registry, city feed or cameras says so — never "waiting · degraded"
{
	const chat = F.feedRows({ ...fx, registry: null, cityFeed: null, cameras: null }, 'en');
	const byId = Object.fromEntries(chat.map((r) => [r.id, r]));
	const pop = F.dataFeeds(chat, 'en');
	const notRead = pop.filter((r) => r.status === 'none');
	ok(
		'F-04: unread sources are "not read here" (status none, no volume, no age), never waiting or degraded; they never grade the Data dot',
		['registry', 'city-feed', 'cameras'].every((id) => byId[id].status === 'not_read' && byId[id].volume === null && byId[id].ageSec === null) &&
			notRead.length === 3 && notRead.every((r) => r.label === '') && F.statusWord('en', 'not_read') === 'Not read here' && F.worstStatus(chat) === 'ok',
		JSON.stringify(pop.map((r) => [r.name, r.status, r.label])),
	);
	ok('F-04: "not read here" in HI and MR too', !/not read/i.test(F.statusWord('hi', 'not_read')) && !/not read/i.test(F.statusWord('mr', 'not_read')), `${F.statusWord('hi', 'not_read')} / ${F.statusWord('mr', 'not_read')}`);
}

// ─── range ──────────────────────────────────────────────────────────────────

ok('range: presets 1 h / 6 h / 24 h / 7 d, 6 h by default', range.RANGES.join(',') === '1h,6h,24h,7d' && range.DEFAULT_RANGE === '6h');
ok('range: a hostile stored value falls back to the default', range.asRange('<img src=x>') === '6h' && range.asRange(null) === '6h' && range.asRange('24h') === '24h');
const w24 = range.rangeWindow('24h', NOW);
ok('range: the window ends now', w24[1] === NOW && w24[1] - w24[0] === 24 * H);

// ─── event history ──────────────────────────────────────────────────────────

const hist = data.parseHistory({
	events: [
		{ event_id: 'e-1', event_kind: 'procession', title: 'Procession', status: 'completed', updated_at: '2026-10-24T10:00:00Z', actual_start: '2026-10-24T08:00:00Z', actual_end: '2026-10-24T10:00:00Z' },
		{ event_id: 'e-2', event_kind: 'vehicle_pursuit', title: 'PURSUIT — stolen MH47EM•••1', status: 'cancelled', updated_at: '2026-10-24T12:00:00Z' },
		{ title: 'no id: not an event' },
	],
});
ok('history: closed events kept, newest change first, a non-event dropped', hist.length === 2 && hist[0].event.eventId === 'e-2' && hist[0].event.state === 'cancelled' && hist[1].event.state === 'completed', hist.map((h) => `${h.event.eventId}:${h.event.state}`).join(' '));
ok('history: the actual window is read', hist[1].actualStart === Date.parse('2026-10-24T08:00:00Z') && hist[1].actualEnd === Date.parse('2026-10-24T10:00:00Z') && hist[0].actualEnd === null);

// ─── the units bridge ───────────────────────────────────────────────────────

const rec = (id, vehicleId, ruleId, status = 'pending', plate = 'MH47EM•••1') => ({ recommendationId: id, sightingId: null, vehicleId, plate, ruleId, recommendation: null, evidence: null, status, decidedBy: null, decidedAt: null, auditTail: [], createdAt: null });
const u = units.unitsFrom({
	recommendations: [rec('r1', 'v1', 'R_STOLEN_SIGHTING'), rec('r2', 'v1', 'R_STOLEN_SIGHTING'), rec('r3', 'v1', 'R_STOLEN_SIGHTING'), rec('r4', 'v2', 'R_SPD_SEGMENT'), rec('r5', 'v3', 'R_SPD_SEGMENT', 'approved')],
	escorts: [{ approvalId: 'a1', movementId: 'm1', kind: 'hold', expiresAt: NOW + 47_000 }],
	dispatches: [{ dispatchId: 'd1', status: 'requested', unitId: '108-14' }, { dispatchId: 'd2', status: 'completed', unitId: 'JR-1' }],
	plate: (p) => p,
});
const byKind = (k) => u.filter((x) => x.kind === k);
ok('units: three sightings of one stolen vehicle are ONE unit', byKind('stolen-sighting').length === 1 && byKind('stolen-sighting')[0].subjectUrn === 'vehicle:v1');
ok('units: a pending e-challan is a unit, a decided one is not', byKind('echallan').length === 1 && byKind('echallan')[0].id === 'r4');
ok('units: an escort proposal is a unit with its deadline (home: the Decisions column on /ops)', byKind('escort-proposal').length === 1 && byKind('escort-proposal')[0].deadline === NOW + 47_000 && byKind('escort-proposal')[0].homes['/ops'] === 'decisions');
ok('units: a requested dispatch is a unit, a closed one is not', byKind('corridor-request').length === 1 && byKind('corridor-request')[0].id === 'd1');
ok('units: units = vehicles-with-pending + e-challans + escorts + requests', u.length === 4, `${u.length} units`);

// ─── OSINT provenance (ethics rule 7, OSINT SPEC §0.5) ───────────────────────

const news = prov.eventProvenance({ sourceKind: 'osint', verificationState: 'NEWS-REPORTED', credibility: 0.65 }, 'en');
ok('provenance: a news-reported OSINT event reads "News-reported" and "credibility 0.65"', news?.label === 'News-reported' && news?.verification === 'NEWS-REPORTED' && news?.credibilityText === 'credibility 0.65', JSON.stringify(news));
const labels4 = ['UNVERIFIED-OSINT', 'NEWS-REPORTED', 'OFFICIAL-VERIFIED', 'CONFIRMED'].map((v) => prov.eventProvenance({ sourceKind: 'osint', verificationState: v, credibility: null }, 'en')?.label);
ok('provenance: the four states have four distinct labels', labels4.join('|') === 'Unverified OSINT|News-reported|Official, verified|Confirmed by officer', labels4.join('|'));
const odd = prov.eventProvenance({ sourceKind: 'osint', verificationState: 'EMULATED', credibility: 1.7 }, 'en');
ok('provenance: an unknown state claims none ("Open-source"); credibility out of 0..1 is not shown', odd?.verification === null && odd?.label === 'Open-source' && odd?.credibilityText === null, JSON.stringify(odd));
ok('provenance: a non-OSINT event has no open-source provenance', prov.eventProvenance({ sourceKind: 'operator', verificationState: 'NEWS-REPORTED', credibility: 0.65 }, 'en') === null && prov.eventProvenance({ sourceKind: null, verificationState: null, credibility: null }, 'en') === null);
ok('provenance: HI label is localized', prov.eventProvenance({ sourceKind: 'osint', verificationState: 'NEWS-REPORTED', credibility: 0.65 }, 'hi')?.label !== 'News-reported');

// ─── the hand-off to / (Open in workspace, the Mode chip) ───────────────────

const EV_A = 'event:6f1c2a3b-4d5e-4f60-8a71-92b3c4d5e6f7';
const EV_B = 'event:0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d';
ok('hand-off: the operator pick wins', share.carriedUrn(EV_A, EV_B) === EV_A);
ok('hand-off: else the docked inspector object', share.carriedUrn(null, EV_B) === EV_B);
ok('hand-off: a malformed URN is never carried', share.carriedUrn('nonsense', null) === null && share.carriedUrn(null, 'MH01 AB 1234') === null && share.carriedUrn(null, null) === null);

// ─── the pack ───────────────────────────────────────────────────────────────

const enKeys = pack.WALL_PACK_KEYS;
const missing = (lang) => enKeys.filter((k) => t(lang, k) === t('en', k) && !/^wall_(range_|unit_|m_congested_of|watch_count|ops_col_window|feed_p95|emu_library_waiting)/.test(k) && typeof t('en', k) === 'string' && !/^\W*$/.test(t('en', k)));
ok('pack: every key starts with wall_', enKeys.length > 300 && enKeys.every((k) => k.startsWith('wall_')), `${enKeys.length} keys`);
ok('pack: HI and MR cover every EN key', missing('hi').length === 0 && missing('mr').length === 0, [...missing('hi').slice(0, 4), ...missing('mr').slice(0, 4)].join(', ') || 'complete');

// ─── 2. the rendered components (svelte/server) ─────────────────────────────

const { compile, compileModule } = require('svelte/compiler');
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
const SSR_ENTRY = `
export { render } from 'svelte/server';
export { default as MetricStrip } from './src/lib/decisions/wall/MetricStrip.svelte';
export { default as BandHistoryChart } from './src/lib/decisions/wall/BandHistoryChart.svelte';
export { default as FeedsSection } from './src/lib/decisions/wall/FeedsSection.svelte';
export { default as EventProvenance } from './src/lib/decisions/wall/EventProvenance.svelte';
export { default as RowProvenance } from './src/lib/decisions/wall/RowProvenance.svelte';
export { metricCells } from './src/lib/decisions/wall/metrics';
export { feedRows } from './src/lib/decisions/wall/feeds';
`;
let S = null;
try {
	const ssr = await esbuild.build({
		stdin: { contents: SSR_ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'wall-ssr-entry.ts' },
		absWorkingDir: DECK,
		alias: { $lib: './src/lib' },
		bundle: true,
		format: 'esm',
		platform: 'node',
		conditions: ['svelte', 'node'],
		outfile: OUT_SSR,
		logLevel: 'silent',
		plugins: [sveltePlugin],
	});
	ok('server bundle builds (svelte/compiler, generate: server)', ssr.errors.length === 0, `${ssr.errors.length} errors`);
	S = await import(`${pathToFileURL(OUT_SSR).href}?t=${Date.now()}`);
} catch (err) {
	ok('server bundle builds (svelte/compiler, generate: server)', false, String(err?.message ?? err).slice(0, 400));
}

if (S) {
	// the markup without Svelte's hydration markers
	const html = (C, props) => S.render(C, { props }).body.replace(/<!--[\s\S]*?-->/g, '');

	const strip = html(S.MetricStrip, { cells: S.metricCells(base), wide: true });
	ok('rendered strip: exactly four data tiles', count(strip, /data-prim="data-tile"/g) === 4, `${count(strip, /data-prim="data-tile"/g)} data tiles`);
	const tiles = [...strip.matchAll(/<div[^>]*data-prim="data-tile"[^>]*>/g)].map((x) => x[0]);
	ok('rendered strip: every data tile carries data-counter and data-value', tiles.length === 4 && tiles.every((x) => /data-counter="[a-z-]+"/.test(x) && /data-value="[^"]*"/.test(x)), tiles.map((x) => (x.match(/data-counter="([a-z-]+)"/) ?? [])[1]).join(','));
	ok('rendered strip: the counters carry their values', /data-counter="active-events"[^>]*data-value="0"|data-value="0"[^>]*data-counter="active-events"/.test(strip) && /data-counter="pending-decisions"[^>]*data-value="4"|data-value="4"[^>]*data-counter="pending-decisions"/.test(strip));
	ok('rendered strip: eight metric cards', count(strip, /data-ui="metric-card"/g) === 8);
	const cardOf = (key) => (strip.split(`data-metric="${key}"`)[1] ?? '').split('data-metric=')[0];
	ok('rendered strip: a zero recedes (data-zero)', /data-zero="true"/.test(cardOf('active')) && /data-zero="true"/.test(cardOf('units')) && /data-zero="true"/.test(cardOf('congested')));
	ok('rendered strip: a non-zero does not recede', !/data-zero="true"/.test(cardOf('decisions')) && !/data-zero="true"/.test(cardOf('anomalies')));
	const zeroDecisions = html(S.MetricStrip, { cells: S.metricCells({ ...base, units: 0 }), wide: true });
	const zd = (zeroDecisions.split('data-metric="decisions"')[1] ?? '').split('data-metric=')[0];
	ok('rendered strip: "Decisions waiting 0" recedes, never orange', /data-zero="true"/.test(zd) && /class="[^"]*\bzero\b/.test(zd));
	ok('rendered strip: sparklines on a wide strip only', count(strip, /<svg[^>]*class="spark/g) === 2 && count(html(S.MetricStrip, { cells: S.metricCells(base), wide: false }), /<svg[^>]*class="spark/g) === 0);

	const svg = html(S.BandHistoryChart, {
		readings: [
			{ ts: NOW - 3 * H, band: 'AMBER' },
			{ ts: NOW - 2 * H, band: 'BLACK' },
			{ ts: NOW - 1 * H, band: 'GREEN' },
		],
		window: win,
		lang: 'en',
		scope: 'City',
	});
	const blackRect = (svg.match(/<rect[^>]*data-band="BLACK"[^>]*>/) ?? [''])[0];
	ok('rendered chart: the BLACK bar has the fill and the 1 px hairline', /fill="var\(--v-band-black-fill\)"/.test(blackRect) && /stroke="var\(--v-band-black-hairline\)"/.test(blackRect) && /stroke-width="1"/.test(blackRect), blackRect);
	const amberRect = (svg.match(/<rect[^>]*data-band="AMBER"[^>]*>/) ?? [''])[0];
	ok('rendered chart: other bands draw no stroke', /stroke="none"/.test(amberRect), amberRect);
	const labels = [...svg.matchAll(/<text[^>]*class="tick-label[^"]*"[^>]*>([^<]*)<\/text>/g)].map((x) => x[1]);
	ok('rendered chart: a real axis (IST hh:mm tick labels)', labels.length >= 3 && labels.every((l) => /^\d{2}:\d{2}$/.test(l)), labels.join(' '));
	ok('rendered chart: the ladder is labelled', ['Black', 'Red', 'Amber', 'Green'].every((w) => svg.includes(`>${w}<`)));

	const sect = html(S.FeedsSection, { rows: S.feedRows(fx, 'en'), lang: 'en' });
	ok('rendered feeds: a panel titled "Feeds and services" (h2)', /data-prim="panel"/.test(sect) && /<h2[^>]*>Feeds and services<\/h2>/.test(sect));
	ok('rendered feeds: one row per source with its status', count(sect, /<tr data-feed=/g) === 7 && /data-feed="traffic" data-status="simulated"/.test(sect) && /data-feed="model" data-status="ok"/.test(sect));
	ok('rendered feeds: provenance reads as a provenance tag, health as a tag', /data-source="simulated"/.test(sect) && /data-source="emulated"/.test(sect) && sect.includes('Answering'));
}

if (S) {
	const html = (C, props) => S.render(C, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
	// the row markup EventBoard renders for a promoted OSINT event
	const row = html(S.EventProvenance, { event: { sourceKind: 'osint', verificationState: 'NEWS-REPORTED', credibility: 0.65 }, lang: 'en' });
	const tag = (row.match(/<span[^>]*data-ui="provenance-tag"[^>]*>[\s\S]*?<\/span>\s*<\/span>/) ?? [''])[0];
	ok('rendered row: the OSINT tag is not compact', /data-source="osint"/.test(tag) && /data-verification="NEWS-REPORTED"/.test(tag) && !/class="[^"]*\bcompact\b/.test(tag), tag.slice(0, 200));
	ok('rendered row: "News-reported" is VISIBLE text (not the visually hidden .sr label)', /<span class="text[^"]*">News-reported<\/span>/.test(row) && !/class="sr[^"]*">News-reported/.test(row));
	ok('rendered row: "credibility 0.65" is visible', /data-testid="event-credibility"[^>]*>credibility 0\.65<\/span>/.test(row));
	const unverified = html(S.EventProvenance, { event: { sourceKind: 'osint', verificationState: 'UNVERIFIED-OSINT', credibility: 0.2 }, lang: 'en' });
	ok('rendered row: an unverified report reads differently from a verified one', /<span class="text[^"]*">Unverified OSINT<\/span>/.test(unverified) && !unverified.includes('News-reported'));
	const live = html(S.EventProvenance, { event: { sourceKind: 'operator', verificationState: null, credibility: null }, lang: 'en' });
	ok('rendered row: a non-OSINT event renders no provenance', !/provenance-tag|event-credibility/.test(live), live.slice(0, 120));
}

// ─── row marks (SPEC §9.2) ──────────────────────────────────────────────────

{
	const live = { name: 'Sea Link closure', metadata: {}, emulated: false, source: 'live' };
	const emu = { name: 'Drill closure (Emulated)', metadata: {}, emulated: false, source: 'live' };
	const flagged = { name: 'Drill closure', metadata: {}, emulated: true, source: 'live' };
	const labelled = { name: 'Rehearsal escort', metadata: { label: 'TEST' }, emulated: false, source: 'live' };
	ok('row marks: a metadata label makes a test event', prov.isTestEvent(labelled) && !prov.isTestEvent(live));
	ok('row marks: "(Emulated)" in the title or the flag makes an emulated event', prov.isEmulatedEvent(emu) && prov.isEmulatedEvent(flagged) && !prov.isEmulatedEvent(live));
	ok('row marks: a list that is all emulated is uniform', prov.uniformProvenance([emu, flagged]) === 'emulated');
	ok('row marks: a mixed list is not uniform, nor is an empty one', prov.uniformProvenance([emu, live]) === null && prov.uniformProvenance([]) === null);
	ok('row marks: test rows are kept out of the counts', prov.countable([live, labelled, emu]).length === 2);
	ok('row marks: the header says it once ("All 3 emulated", or "Emulated" for one row)', prov.uniformLabel(3, 'en') === 'All 3 emulated' && prov.uniformLabel(1, 'en') === 'Emulated' && prov.uniformLabel(3, 'hi') !== 'All 3 emulated');
	ok('row marks: the planning state reads "Planning", as the inspector does', t('en', 'wall_state_planning') === 'Planning' && t('en', 'wall_state_planning') === t('en', 'ws_state_planning'));
}

if (S) {
	const html = (C, props) => S.render(C, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
	const base = { name: 'Rehearsal escort', metadata: { label: 'TEST' }, emulated: false, source: 'live', sourceKind: null, verificationState: null, credibility: null };
	const testRow = html(S.RowProvenance, { event: base, lang: 'en' });
	const testTag = (testRow.match(/<span[^>]*data-source="test"[^>]*>[\s\S]*?<\/span>\s*<\/span>/) ?? [''])[0];
	ok('rendered row: a TEST row shows a visible "Test" tag (.text, not only the .sr label)', /<span class="text[^"]*">Test<\/span>/.test(testRow) && !/class="sr[^"]*">Test</.test(testRow) && !/class="[^"]*\bcompact\b/.test(testTag), testTag.slice(0, 200));
	ok('rendered row: the Test tag carries data-testid="event-test"', /data-testid="event-test"/.test(testTag));
	const testUniform = html(S.RowProvenance, { event: { ...base, emulated: true }, lang: 'en', uniform: true });
	ok('rendered row: a test row in a uniform list still shows its Test tag', /<span class="text[^"]*">Test<\/span>/.test(testUniform) && !/data-source="emulated"/.test(testUniform));
	const emuMixed = html(S.RowProvenance, { event: { ...base, name: 'Drill', metadata: {}, emulated: true }, lang: 'en' });
	ok('rendered row: in a mixed list an emulated row carries the compact glyph', /data-source="emulated"[^>]*class="[^"]*\bcompact\b|class="[^"]*\bcompact\b[^"]*"[^>]*data-source="emulated"/.test(emuMixed) && /class="sr[^"]*">Emulated</.test(emuMixed), emuMixed.slice(0, 200));
	const emuUniform = html(S.RowProvenance, { event: { ...base, name: 'Drill', metadata: {}, emulated: true }, lang: 'en', uniform: true });
	ok('rendered row: in a uniform list an emulated row carries nothing', !/provenance-tag/.test(emuUniform), emuUniform.slice(0, 120));
	const liveRow = html(S.RowProvenance, { event: { ...base, name: 'Sea Link closure', metadata: {} }, lang: 'en' });
	ok('rendered row: a live row is unmarked', !/provenance-tag|data-ui="tag"/.test(liveRow), liveRow.slice(0, 120));
	const osint = html(S.RowProvenance, { event: { ...base, name: 'Waterlogging at Thanthania', metadata: {}, sourceKind: 'osint', verificationState: 'NEWS-REPORTED', credibility: 0.65 }, lang: 'en', uniform: true });
	ok('rendered row: an OSINT row keeps its visible verification and credibility', /<span class="text[^"]*">News-reported<\/span>/.test(osint) && /credibility 0\.65/.test(osint));
}

console.log(failures ? `\n${failures} FAILED` : '\nall wall checks passed');
process.exit(failures ? 1 : 0);
