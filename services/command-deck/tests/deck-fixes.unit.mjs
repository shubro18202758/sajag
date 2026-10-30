/**
 * The deck's pre-release audit fixes, unit level (FIX-H-DECK: F-UI, F-HONEST,
 * F-CONN, FIX-G-ORACLE / FIX-G-BRAIN deck items).
 *
 *   node tests/deck-fixes.unit.mjs
 *
 * esbuild bundles the REAL modules (`$lib` aliased to src/lib, the runes as
 * identity stubs — the workspace.unit pattern) into a temp dir, and a few
 * structural reads cover what only a page's markup holds. Each group names
 * the finding it pins; each assertion fails on the pre-fix tree. The DOM
 * behaviour a browser must show (the omnibar's ask, the driver clock, the
 * share toast, the 1366 layout, the production 404s) is the smokes'.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */

import { createRequire } from 'node:module';
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from 'node:fs';
import { EventEmitter } from 'node:events';
import { spawnSync } from 'node:child_process';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const SRC = path.join(DECK, 'src');
const read = (rel) => readFileSync(path.join(DECK, rel), 'utf8');

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}

/**
 * One finding's assertions. A group that THROWS (a helper the tree does not
 * have, a shape it does not produce) reports a FAIL with the error and the
 * run goes on — every finding is reported, never hidden behind the first crash.
 */
async function group(fn) {
	try {
		await fn();
	} catch (err) {
		ok(`a group threw: ${String(err?.message ?? err).split('\n')[0].slice(0, 160)}`, false);
	}
}

// ─── bundle the real modules (into a temp dir, never the checkout) ──────────

const require = createRequire(path.join(DECK, 'package.json'));
const esbuild = require('esbuild');
const OUT_DIR = mkdtempSync(path.join(os.tmpdir(), 'sajag-deck-fixes-'));
process.on('exit', () => rmSync(OUT_DIR, { recursive: true, force: true }));
const OUT = path.join(OUT_DIR, 'deck-fixes-bundle.mjs');
const ENTRY = `
export * as display from './src/lib/workspace/display';
export * as generic from './src/lib/workspace/kinds/generic';
export * as common from './src/lib/workspace/kinds/common';
export * as adapters from './src/lib/workspace/kinds';
export * as objects from './src/lib/workspace/objects';
export * as vocab from './src/lib/workspace/vocabulary';
export * as search from './src/lib/workspace/search';
export * as ama from './src/lib/decisions/wall/ama';
export * as prov from './src/lib/decisions/wall/provenance';
export * as metrics from './src/lib/decisions/wall/metrics';
export * as dss from './src/lib/dss/dss-data';
export * as evsrc from './src/lib/ops/event-source';
export * as client from './src/lib/ops/client';
export * as answer from './src/lib/assistant/answer';
export * as limits from './src/lib/shell/proxy-limits';
export * as harness from './src/lib/shell/design-harness';
export * as gate from './src/lib/shell/operator-session.server';
export * as pubModel from './src/lib/citizen/public-model';
export * as apiClient from './src/lib/api/client';
export { t, kindLabel } from './src/lib/i18n/strings';
export { citizenT } from './src/lib/i18n/strings.citizen';
export { tOps } from './src/lib/i18n/strings.ops';
import './src/lib/i18n/packs';
import './src/lib/i18n/packs.ui';
import './src/lib/i18n/packs.wall';
import './src/lib/i18n/packs.views';
import './src/lib/i18n/packs.decisions';
import './src/lib/i18n/packs.assistant';
import './src/lib/i18n/packs.osint';
import './src/lib/i18n/packs.map';
import './src/lib/i18n/packs.workspace';
`;
const svelteStub = {
	name: 'svelte-component-stub',
	setup(build) {
		build.onResolve({ filter: /\.svelte$/ }, (args) => {
			const file = args.path.startsWith('$lib/') ? path.join(DECK, 'src/lib', args.path.slice(5)) : path.resolve(args.resolveDir, args.path);
			if (existsSync(`${file}.ts`) || existsSync(`${file}.js`)) return undefined;
			return { path: file, namespace: 'svelte-stub' };
		});
		build.onLoad({ filter: /.*/, namespace: 'svelte-stub' }, () => ({ contents: 'export default function C() {}', loader: 'js' }));
		build.onResolve({ filter: /^\$app\// }, (a) => ({ path: a.path, namespace: 'app-stub' }));
		build.onLoad({ filter: /.*/, namespace: 'app-stub' }, () => ({ contents: 'export const browser = false, dev = false; export const goto = async () => {};', loader: 'js' }));
	},
};
const built = await esbuild.build({
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'deck-fixes-entry.ts' },
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	format: 'esm',
	platform: 'node',
	outfile: OUT,
	logLevel: 'silent',
	plugins: [svelteStub],
});
ok('bundle builds (esbuild, $lib aliased, temp dir)', built.errors.length === 0, `${built.errors.length} errors`);

globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => v });
globalThis.$derived = Object.assign((v) => v, { by: (f) => f() });
globalThis.$effect = Object.assign(() => {}, { root: () => () => {}, pre: () => {} });

const M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
const { display: D, generic: G, common: C, adapters: A, objects: O, vocab: V, search: SR, ama, prov, metrics, dss, evsrc, client, answer, limits, harness, gate, pubModel, apiClient, t, citizenT, tOps } = M;
const LANGS = ['en', 'hi', 'mr'];
const NOW = Date.now();

/** The key resolves in every language, to its own words (never the key, never the EN text in HI/MR). */
function localised(fn, key, ...args) {
	const en = fn('en', key, ...args);
	return LANGS.every((l) => fn(l, key, ...args) !== key) && fn('hi', key, ...args) !== en && fn('mr', key, ...args) !== en;
}

// ─── a minimal city picture for the inspector views ──────────────────────────

const PURSUIT_ID = '4508d86d-566b-438f-8414-b3d67fd7e6e4';
const pursuitEntity = (props = {}, extra = {}) => ({
	urn: `event:${PURSUIT_ID}`,
	kind: 'event',
	id: PURSUIT_ID,
	label: 'PURSUIT — stolen MH47EM•••1 (FIR 4401/2026)',
	lon: 88.3599,
	lat: 22.5582,
	state: 'active',
	source: 'live',
	// the oracle's entity t: the row's LAST CHANGE (band re-evaluated every few seconds), not its start
	t: new Date(NOW - 2_000).toISOString(),
	links: [],
	props: { event_kind: 'vehicle_pursuit', title: 'PURSUIT — stolen MH47EM•••1 (FIR 4401/2026)', status: 'active', crowd_class: 'low', protection_class: 'none', route_spines: [], metadata: {}, ...props },
	...extra,
});
const viewOf = (entity, lang = 'en') => {
	const graph = O.buildObjectGraph({ entities: [entity] });
	const row = graph.get(entity.urn);
	return { row, view: A.adapterFor(entity.kind).view(row, { lang, now: NOW, officer: false, plate: (p) => p, graph, links: graph.links(entity.urn), dossier: null }) };
};

// ─── F-02 · a pursuit with no start never shows NOW as its start ────────────
await group(async () => {
	const { row, view } = viewOf(pursuitEntity());
	const figs = view.figures.map((f) => f.caption);
	const winRow = view.groups.flatMap((g) => g.rows).find((r) => r.key === 'Window');
	ok(
		'F-02: no actual/planned start → no Start time anywhere (figures, Window, subtitle), the Window says "Not started"',
		!view.figures.some((f) => f.caption === 'Start' && f.time != null) &&
			winRow?.value?.t === 'text' &&
			winRow.value.v === 'Not started' &&
			!view.subtitle.flat().some((r) => 'time' in r || 'start' in r),
		`row.t ${row.t ? new Date(row.t).toISOString() : null} · figures ${figs.join(',')} · window ${JSON.stringify(winRow?.value)}`,
	);
	const started = viewOf(pursuitEntity({ actual_start: new Date(NOW - 3_600_000).toISOString() })).view;
	const win = started.groups.flatMap((g) => g.rows).find((r) => r.key === 'Window');
	ok('F-02: with an actual start, the window starts at THAT time (not the row\'s last change)', win?.value?.t === 'range' && win.value.a === NOW - 3_600_000, JSON.stringify(win?.value));
	ok('F-02: "Not started" in HI and MR', localised(t, 'ws_v_not_started'));
	// ── F-27 · a pursuit has no crowd ──
	ok('F-27: a pursuit\'s view carries no Crowd figure (crowd_class says nothing about a chase)', !started.figures.some((f) => f.caption === 'Crowd'), started.figures.map((f) => f.caption).join(','));
	const procession = viewOf(pursuitEntity({ event_kind: 'procession', actual_start: new Date(NOW - 3_600_000).toISOString() })).view;
	ok('F-27: a procession keeps its Crowd figure', procession.figures.some((f) => f.caption === 'Crowd'));
	// ── F-16 · "Pursuit of" in the reader's language ──
	const hiView = viewOf(pursuitEntity({ actual_start: new Date(NOW - 3_600_000).toISOString() }), 'hi').view;
	const hiTitle = hiView.title.map((r) => r.text ?? '').join('');
	ok('F-16: the pursuit\'s inspector title is localised (HI)', !/Pursuit of/.test(hiTitle) && hiTitle.includes('MH47EM•••1') && hiTitle.includes('पीछा'), hiTitle);
	const raw = 'PURSUIT — stolen MH47EM•••1 (FIR 4401/2026)';
	ok(
		'F-16: displayTitle(pursuit, lang) reads in EN/HI/MR; other titles stay as sent',
		D.displayTitle(raw) === 'Pursuit of MH47EM•••1' && D.displayTitle(raw, 'mr') === 'MH47EM•••1 चा पाठलाग' && D.displayTitle(raw, 'hi') === 'MH47EM•••1 का पीछा' && D.displayTitle('Visarjan procession', 'hi') === 'Visarjan procession' && D.localTitle('Pursuit of MH47EM•••1', 'mr') === 'MH47EM•••1 चा पाठलाग',
		`${D.displayTitle(raw, 'hi')} / ${D.displayTitle(raw, 'mr')}`,
	);
	const callers = ['src/lib/ops/components/EventBoard.svelte', 'src/lib/corridor/ActiveEvents.svelte', 'src/lib/ops/components/DispatchTiles.svelte', 'src/lib/assistant/AssistantPanel.svelte'];
	ok('F-16: the event lists pass the console language to displayTitle', callers.every((f) => !/displayTitle\([^()]*\)(?!\s*,)/.test(read(f).replace(/displayTitle\(ops\.text\(([^()]|\([^()]*\))*\),\s*lang\)/g, '').replace(/displayTitle\([^()]*,\s*lang\)/g, ''))), callers.join(', '));
});

// ─── F-15 / FIX-G-ORACLE · state words (planned, planned_green, planned_lost) ─
await group(async () => {
	ok('F-15: the "planned" state reads "Planning" in EN and in HI/MR words (never English "Planned")', G.stateWord('planned', 'en') === 'Planning' && G.stateWord('planned', 'hi') === t('hi', 'ws_state_planning') && G.stateWord('planned', 'mr') === t('mr', 'ws_state_planning'), `${G.stateWord('planned', 'hi')} / ${G.stateWord('planned', 'mr')}`);
	ok(
		'FIX-G-ORACLE: a junction\'s planned_green / planned_lost read as PLANNED program phases in EN/HI/MR and the vocabulary',
		['planned_green', 'planned_lost'].every((s) => /^Planned /.test(G.stateWord(s, 'en')) && localised(t, `ws_state_${s}`) && /signal program/.test(V.HUMAN[s] ?? '')),
		['planned_green', 'planned_lost'].map((s) => `${G.stateWord(s, 'en')} | ${G.stateWord(s, 'hi')}`).join(' · '),
	);
	const jn = {
		urn: 'junction:15', kind: 'junction', id: '15', label: 'Moulali', lon: 88.3684, lat: 22.5571, state: 'planned_green', source: 'live', t: new Date(NOW).toISOString(), links: [],
		props: { name: 'Moulali', junction_type: 'roundabout', signal_control: true, cycle_sec: 110, green_ratio: 0.42, active_phase: { index: 1, remaining_sec: 31 }, phase_basis: 'program_clock', phase_status: 'planned (signal program)', live_phase: false },
	};
	const jv = viewOf(jn).view;
	const ps = jv.groups.flatMap((g) => g.rows).find((r) => r.key === 'Phase status');
	ok('FIX-G-ORACLE: the junction view says the phase is planned from the stored program (a phase_status row)', ps?.value?.t === 'text' && /not controller telemetry/.test(ps.value.v), JSON.stringify(ps?.value));
	ok('FIX-G-ORACLE: the design fixtures carry the oracle\'s planned_green state (never a bare "green")', /state: 'planned_green'/.test(read('src/routes/(deck)/design/workspace/+page.svelte')) && !/kind: 'junction'[^\n]*state: 'green'/.test(read('src/routes/(deck)/design/workspace/+page.svelte')) && !/kind: 'junction'[^\n]*state: 'green'/.test(read('src/routes/(deck)/design/views/+page.svelte')));
	// baseRow: synthetic → simulated, whatever the kind
	const cam = { urn: 'camera:EM-CAM-09', kind: 'camera', id: 'EM-CAM-09', label: 'EM-CAM-09', lon: 88.37, lat: 22.54, state: null, source: 'live', t: null, links: [], props: { data_quality: 'synthetic' } };
	const real = { ...cam, urn: 'camera:CAM-1', id: 'CAM-1', props: { data_quality: 'real' } };
	const anm = { urn: 'anomaly:9', kind: 'anomaly', id: '9', label: 'Congestion outlier', lon: 88.37, lat: 22.54, state: null, source: 'emulated', t: null, links: [], props: { data_quality: 'synthetic', anomaly_type: 'congestion_outlier' } };
	const emu = { ...cam, urn: 'camera:EM-CAM-03', id: 'EM-CAM-03', source: 'emulated', props: {} };
	ok(
		'FIX-G-ORACLE: baseRow reads data_quality "synthetic" as SIMULATED for any kind (a camera too, an anomaly the oracle tags emulated); real stays live, emulated without it stays emulated',
		C.baseRow(cam).source === 'simulated' && C.baseRow(anm).source === 'simulated' && C.baseRow(real).source === 'live' && C.baseRow(emu).source === 'emulated',
		`${C.baseRow(cam).source} / ${C.baseRow(anm).source} / ${C.baseRow(real).source} / ${C.baseRow(emu).source}`,
	);
});

// ─── FIX-G-ORACLE · emulated evidence makes the event emulated (ops board) ──
await group(async () => {
	const row = (metadata) => client.mapEventRow({ event_id: PURSUIT_ID, title: 'PURSUIT — stolen MH47EM•••1', event_kind: 'vehicle_pursuit', status: 'active', metadata }, 'live-events-api');
	ok(
		'FIX-G-ORACLE: ops/client marks an event emulated on metadata.evidence_source "emulated" (HON-4), as the oracle\'s event_source does',
		row({ source: 'deck', evidence_source: 'emulated' })?.emulated === true && row({ source: 'event-emulator' })?.emulated === true && row({ source: 'deck' })?.emulated === false && evsrc.emulatedByMetadata({ mode: 'living_city' }) === true,
	);
});

// ─── F-17 / F-19 · the pursuit plan's note and its opener ───────────────────
await group(async () => {
	ok('F-17: server text never shows an internal contract code ("(C6)", "(C-F)")', D.displayText('pursuits are human-initiated (C6); this plan assists the operator') === 'pursuits are human-initiated; this plan assists the operator' && !/\(C-?[A-Z0-9]+\)/.test(D.displayText('a rule (C-F) and (C-D2)')), D.displayText('pursuits are human-initiated (C6); this plan assists the operator'));
	const plan = read('src/lib/decisions/sections/PursuitPlan.svelte');
	ok('F-17: the plan\'s note is the console\'s own localised sentence (never the oracle\'s English note)', /L\('dec_plan_note'\)/.test(plan) && !/plan\.note/.test(plan) && localised(t, 'dec_plan_note'));
	ok('F-19: the opener shows through displayActor (the demo scenario\'s name dropped)', /displayActor\(openedBy, lang\)/.test(plan) && D.displayActor('Sandbox Officer (God’s Eye Morning)') === 'Sandbox Officer', D.displayActor('Sandbox Officer (God’s Eye Morning)'));
});

// ─── F-20 · the omnibar's templates never answer "No matches" ───────────────
await group(async () => {
	const heads = { 'ask ': 'ask', 'fly to ': 'fly', 'show police units near ': 'units', 'layer ': 'layer', 'layer events': 'layer', 'sensor ': 'sensor', '> ask': 'ask' };
	const got = Object.fromEntries(Object.keys(heads).map((q) => [q, SR.parseCommand(q)]));
	ok(
		'F-20: a template typed up to its argument parses as "incomplete" (the row says what to type), never a search for "ask"',
		Object.entries(heads).every(([q, tpl]) => got[q]?.type === 'incomplete' && got[q].template === tpl && typeof SR.COMMAND_EXAMPLES[tpl] === 'string'),
		JSON.stringify(got),
	);
	ok('F-20: complete commands still parse as before', SR.parseCommand('ask why is the band amber')?.type === 'ask' && SR.parseCommand('layer events on')?.type === 'layer' && SR.parseCommand('fly to Strand Road')?.type === 'fly' && SR.parseCommand('Moulali') === null);
	ok('F-20: the "keep typing" line is localised', localised(t, 'ws_cmd_incomplete', 'ask how is traffic'));
	const omni = read('src/lib/workspace/components/omnibar/Omnibar.svelte');
	ok('F-20: the omnibar renders the incomplete template as its own row', /case 'incomplete':/.test(omni) && /ws_cmd_incomplete/.test(omni));
});

// ─── F-01 · the omnibar never claims a question was sent before it was ──────
await group(async () => {
	const omni = read('src/lib/workspace/components/omnibar/Omnibar.svelte');
	const ask = omni.slice(omni.indexOf('function ask(question: string)'), omni.indexOf('function legacyItems'));
	const beforeStream = ask.slice(0, ask.indexOf('void streamChat('));
	ok('F-01: no "Sent to the assistant" before the stream answers; it is set on the first token / done only', !/\n\t\tnote = L\('ws_cmd_sent'\);/.test(ask) && /\n\t\tnote = null;/.test(beforeStream) && /onToken[\s\S]{0,120}arrived\(\)/.test(ask) && /onDone[\s\S]{0,120}arrived\(\)/.test(ask));
	ok('F-01: a failed stream (callback error or rejected fetch) answers "assistant unreachable" and clears the note', /onError: \(\) => unreachable\(\)/.test(ask) && /\.catch\(\(\) => unreachable\(\)\)/.test(ask) && /answer = L\('ws_cmd_unreachable'\)/.test(ask) && localised(t, 'ws_cmd_unreachable'));
});

// ─── F-12 · the AMA shadow-evaluation row ───────────────────────────────────
await group(async () => {
	const baseline = ama.shadowRow({ newest: { shadowEval: 'unavailable', shadowEvalDetail: 'shadow_eval_not_required', ts: '2026-10-26T08:22:21Z' }, evidence: null });
	ok('F-12: a baseline set (unavailable + shadow_eval_not_required) reads NOT REQUIRED, with no "why"', baseline?.state === 'not_required' && baseline.why === null && baseline.publishedAt === '2026-10-26T08:22:21Z', JSON.stringify(baseline));
	const failed = ama.shadowRow({ newest: { shadowEval: 'failed_closed', shadowEvalDetail: 'twin_not_calibrated', ts: 1 }, evidence: null });
	ok('F-12: a real failure keeps its word and reason', failed?.state === 'failed_closed' && failed.why === 'twin_not_calibrated');
	const ev = ama.shadowRow({ newest: null, evidence: { shadowEval: 'passed', failClosedReason: null } });
	ok('F-12: a word from the band evidence carries NO publish time (no stale time beside it)', ev?.state === 'passed' && ev.publishedAt === null);
	const card = read('src/lib/ops/components/AMAModuleCard.svelte');
	ok('F-12: the card shows the publish time dated (fmtStamp) and labelled', /wall_ama_published/.test(card) && /fmtStamp\(shadowState\.publishedAt\)/.test(card) && !/fmtTime\(newest\.ts\)/.test(card) && localised(t, 'wall_ama_published', '23 Oct 12:56'));
});

// ─── F-13 · "N in history" counts what the open count counts ────────────────
await group(async () => {
	const ev = (name, metadata = {}) => ({ event: { name, metadata } });
	ok('F-13: historyCount leaves test and rehearsal rows out', prov.historyCount([ev('Visarjan procession'), ev('ACCEPTANCE TEST — corridor'), ev('Drill', { label: 'rehearsal' }), ev('PURSUIT — stolen MH47EM•••1')]) === 2);
	ok('F-13: the wall feeds the metric strip historyCount(), never the raw history length', /history: wallData\.historyUpdated \? historyCount\(wallData\.history\)/.test(read('src/routes/(deck)/ops/+page.svelte')));
});

// ─── F-14 · vitals: decisions vs the records behind them ────────────────────
await group(async () => {
	const v = read('src/lib/workspace/components/vitals/VitalsInfo.svelte');
	ok('F-14: the vitals section says the header counts decisions and the rows the records behind them', /vitals-decisions-records/.test(v) && /vw_i_decisions_records', d\.units/.test(v) && localised(t, 'vw_i_decisions_records', 4));
	ok('F-14: the 108 row reads as a subset ("Of which …"), not a fifth kind', /^Of which/.test(t('en', 'vw_i_ambulance')));
});

// ─── F-26 · a stolen vehicle's e-challan meta line ──────────────────────────
ok('F-26: the withheld e-challan has its own meta line in EN/HI/MR (never "e-challan recommended" under "Reject")', localised(t, 'dec_meta_echallan_stolen') && !/recommended/i.test(t('en', 'dec_meta_echallan_stolen')) && /if \(d\.stolen\) return t\(lang, 'dec_meta_echallan_stolen'\)/.test(read('src/lib/decisions/cards/meta.ts')));

// ─── F-03 / F-25 · every page title is a real key, in every language ────────
await group(async () => {
	const pages = ['src/routes/(deck)/+page.svelte', 'src/routes/(deck)/ops/+page.svelte', 'src/routes/(deck)/gods-eye/+page.svelte', 'src/routes/(deck)/chat/+page.svelte', 'src/routes/(deck)/comms/+page.svelte', 'src/routes/(public)/citizen/+page.svelte', 'src/routes/(public)/driver/+page.svelte'];
	const bad = [];
	for (const p of pages) {
		const m = /<title>\{(t|L|citizenT)\((?:lang|ops\.lang), '([\w]+)'\)\} · Sajag<\/title>/.exec(read(p)) ?? /<title>\{(L)\('([\w]+)'\)\} · Sajag<\/title>/.exec(read(p));
		if (!m) {
			bad.push(`${p}: no translated title`);
			continue;
		}
		const fn = m[1] === 'citizenT' ? citizenT : t;
		const key = m[2];
		if (!LANGS.every((l) => fn(l, key) !== key)) bad.push(`${p}: ${key} unresolved`);
		else if (fn('hi', key) === fn('en', key) || fn('mr', key) === fn('en', key)) bad.push(`${p}: ${key} English in HI/MR`);
	}
	ok('F-03/F-25: every operator and public page\'s tab title is a translated key that resolves in EN/HI/MR', bad.length === 0, bad.join(' | ') || `${pages.length} pages`);
});

// ─── F-09 / COPY-2 / COPY-5 / COPY-7 / COPY-6 / COPY-4 · honest citizen copy ─
await group(async () => {
	const seconds = /seconds|सेकंड|सेकंद/;
	ok('COPY-2/F-09: no response time is promised to a driver (EN/HI/MR emergencyBody, driverSub)', LANGS.every((l) => !seconds.test(t(l, 'emergencyBody')) && !seconds.test(t(l, 'driverSub'))) && LANGS.every((l) => /108/.test(t(l, 'driverSub'))));
	ok('F-09: with no live corridor event the citizen page says there is none (no "the active event")', localised(t, 'emergencyBodyNone') && !/the active event/.test(t('en', 'emergencyBodyNone')) && /liveCount > 0 \? 'emergencyBody' : 'emergencyBodyNone'/.test(read('src/lib/citizen/CitizenAdvisory.svelte')));
	ok('F-09: the driver header promises the officer\'s queue only in the live flow (never over the scripted fallback)', /\{#if !scripted\}<p data-testid="driver-sub">/.test(read('src/lib/citizen/GreenCorridorDriver.svelte')));
	ok('COPY-5: the citizen page connects to Sajag (not a control room); the 108 line claims no channel', !/control room/i.test(citizenT('en', 'citizen_feed_connecting')) && !/stay on channel/i.test(citizenT('en', 'control_room_line')) && localised(citizenT, 'citizen_feed_connecting'));
	ok('COPY-7: holds are PLANNED to lift (no guarantee of field execution)', !/lift on schedule|stay short/i.test(citizenT('en', 'strip_hold') + citizenT('en', 'strip_severe')) && /planned to/i.test(citizenT('en', 'strip_hold')) && /planned to/i.test(citizenT('en', 'strip_severe')));
	ok('COPY-6: the comms log is a draft log (nothing is sent)', !/send/i.test(citizenT('en', 'comms_draft_log')) && localised(citizenT, 'comms_draft_log'));
	const drv = read('src/lib/citizen/GreenCorridorDriver.svelte');
	ok('COPY-4: the scripted run states no "minutes returned / saved" figure', !/minutesSaved|minutesReturned/.test(drv) && typeof citizenT('en', 'after_action') === 'string' && !/saved|returned|\d/.test(citizenT('en', 'after_action')) && t('en', 'minutesReturned') === 'minutesReturned');
	ok('F-08: the driver clock counts from THIS request (never from page load) and says the golden hour began earlier', /requestedAtMs == null \? null/.test(drv) && !/goldenElapsed \+= 1/.test(drv) && /golden_not_started/.test(drv) && localised(citizenT, 'golden_not_started') && /incident/.test(citizenT('en', 'golden_elapsed')));
	ok('F-24: a stretch is named by road and its place on the route, never by segment id', /driver_stretch_unnamed/.test(drv) && !/freezeZone'\)\} \$\{seg\}/.test(drv) && citizenT('en', 'driver_stretch_unnamed', 2) === 'Unnamed road · stretch 2 of the route' && !/stretchName\(h\.roadName, h\.segmentId\)/.test(read('src/lib/citizen/CitizenAdvisory.svelte')));
});

// ─── COPY-1 · the wall's unit and ANPR counters say their source ────────────
await group(async () => {
	ok('COPY-1: sourceMix — all emulated, some, none, empty', metrics.sourceMix([true, true]) === 'emulated' && metrics.sourceMix([true, false]) === 'mixed' && metrics.sourceMix([false]) === 'live' && metrics.sourceMix([]) === null);
	const base = { lang: 'en', now: NOW, active: 1, open: 1, history: 3, units: 0, soonestDeadline: null, oldestWaiting: null, dispatched: 2, dispatchesClosed: 9, ambulance: 1, ambulanceClosed: 3, speedKmh: 40, speedSource: 'simulated', speedSamples: [], roads: 49, congested: 0, critical: 0, reads24: 4, readVehicles: 1, lastRead: NOW - 60_000, readBins: [], anomalies: 2 };
	const cells = Object.fromEntries(metrics.metricCells({ ...base, unitsSource: 'emulated', ambulanceSource: 'mixed', readsSource: 'emulated' }).map((c) => [c.key, c.sub]));
	ok('COPY-1: emulated units, partly emulated 108 units and emulated ANPR reads are said in the sub line', /^Emulated units · 9 closed$/.test(cells.units) && /^Partly emulated units · 3 closed$/.test(cells.ambulance) && /^Emulated ANPR · last /.test(cells.reads), JSON.stringify(cells));
	ok('COPY-1: the source words are localised', ['wall_m_src_emulated_units', 'wall_m_src_mixed_units', 'wall_m_src_emulated_reads', 'wall_m_src_mixed_reads'].every((k) => LANGS.every((l) => t(l, k) !== k)) && localised(t, 'wall_m_units_src', 'x', 9));
	ok('COPY-1: the wall page derives the sources from the unit feed and the reads', /unitsSource: sourceMix\(/.test(read('src/routes/(deck)/ops/+page.svelte')) && /readsSource: sourceMix\(reads\.map/.test(read('src/routes/(deck)/ops/+page.svelte')));
});

// ─── HON-9 · the 108 delay only for a COA that sends a 108 ───────────────────
await group(async () => {
	const fx = JSON.parse(read('tests/fixtures/dss/dss_road_accident.json'));
	const parsed = client.parseDecisionSupport(fx);
	const byId = Object.fromEntries((parsed?.coaSet ?? []).map((c) => [c.coaId, c]));
	const stop = byId.coa_stop_vehicles ? { ...byId.coa_stop_vehicles, ambulanceDelaySec: 240 } : null;
	ok(
		'HON-9: a COA with no 108 dispatch shows no "ambulance ±N s", whatever delay an older engine sent; a 108 COA keeps its own',
		!!stop && dss.ambulanceDelayOf(stop) === null && dss.ambulanceDelayOf(byId.coa_std) === -60 && dss.ambulanceDelayOf(byId.coa_agg) === 180,
		`stop ${stop && dss.ambulanceDelayOf(stop)} · std ${dss.ambulanceDelayOf(byId.coa_std)} · agg ${dss.ambulanceDelayOf(byId.coa_agg)}`,
	);
	ok('HON-9: the COA row renders through ambulanceDelayOf (never the raw field)', /ambulanceDelayOf\(c\)/.test(read('src/lib/dss/DssProposalBody.svelte')) && !/c\.ambulanceDelaySec\}/.test(read('src/lib/dss/DssProposalBody.svelte')));
});

// ─── FIX-G-BRAIN · the assistant's answer vs the lookups' detail ────────────
await group(async () => {
	const prose = 'No road segment named Fake Street is in the city road network. What the lookups returned: city_query_entities: 0 rows; predict_eta refused: route_length_m not grounded.';
	const s = answer.splitLookups(prose);
	ok('FIX-G-BRAIN: the answer is the prose before "What the lookups returned"; the tool detail goes to the steps', s.answer === 'No road segment named Fake Street is in the city road network.' && s.lookups === 'city_query_entities: 0 rows; predict_eta refused: route_length_m not grounded' && !/city_query_entities|predict_eta/.test(s.answer), JSON.stringify(s));
	ok('FIX-G-BRAIN: a prose without the marker is the whole answer', answer.splitLookups('Traffic on Strand Road is 34 km/h.').lookups === null);
	const g = answer.groundingOf({ operatorAlerts: ['ungrounded_claims_removed: 2 claim(s) no tool reported were removed from the answer', 'decider_unavailable: timeout — tactical'], groundingRemoved: null });
	ok('FIX-G-BRAIN: the grounding removals are ONE plain line (the raw alert is not repeated in the list)', g.removed === 2 && g.alerts.length === 1 && /^decider_unavailable/.test(g.alerts[0]) && t('en', 'asst_grounding_removed', 2) === '2 statements removed: not in the lookups' && localised(t, 'asst_grounding_removed', 2));
	ok('FIX-G-BRAIN: done.grounding.removed (a list) is read as a count', answer.groundingOf({ operatorAlerts: [], groundingRemoved: 3 }).removed === 3);
	const panel = read('src/lib/assistant/AssistantPanel.svelte');
	ok('FIX-G-BRAIN: the panel shows split.answer as the answer and the lookups inside the collapsed steps', /\{ops\.text\(split\?\.answer \?\? answer\.prose\)\}/.test(panel) && /data-testid="chat-lookups" hidden=\{!showSteps\}/.test(panel) && /data-testid="chat-grounding-removed"/.test(panel));
	// the stream's done line carries grounding.removed through
	let done = null;
	apiClient.dispatchChatEvent({ type: 'done', data: { session_id: 's', tiers_used: [], operator_alerts: [], degraded: false, citations: [], grounding: { removed: ['a', 'b'] } } }, { onDone: (d) => (done = d), onToken() {}, onError() {} });
	ok('FIX-G-BRAIN: dispatchChatEvent passes done.grounding.removed as groundingRemoved', done?.groundingRemoved === 2, JSON.stringify(done));
});

// ─── OSINT-8 · the district report says what is drawn ───────────────────────
ok('OSINT-8: the district pick text says "reference point" in EN, and no language claims it is drawn as an area', /reference point/.test(t('en', 'os_pick_district')) && !/drawn as an area/.test(t('en', 'os_pick_district')) && localised(t, 'os_pick_district') && localised(t, 'os_pick_area_ring'));

// ─── F-CONN-03 · the citizen model labels an unverified position ─────────────
await group(async () => {
	const w = { event_id: PURSUIT_ID, event_kind: 'protected_movement', status: 'active', stretches: [], phases: [], hold: {}, alternate: null, tier: 'hold', unavailable: [], emulated: false, position_unverified: true };
	ok('F-CONN-03: position_unverified maps to source "unverified" (never "live")', pubModel.mapPublicEvent(w)?.source === 'unverified' && pubModel.mapPublicEvent({ ...w, position_unverified: undefined })?.source === 'live' && localised(citizenT, 'citizen_unverified_badge'));
	const adv = read('src/lib/citizen/CitizenAdvisory.svelte');
	ok('F-CONN-03: the citizen card badges an unverified position and never says "Holding now" for it', /data-source-badge="unverified"/.test(adv) && /unverified \? 'card_unv_now'/.test(adv));
});

// ─── F-CONN-04 / F-CONN-05 · the proxy's limits ─────────────────────────────
await group(async () => {
	ok(
		'F-CONN-05: the twin, the twin comparison and a DSS generation get ≥ the client\'s 120 s; the brain 300 s; the rest 60 s',
		limits.proxyBudgetMs('/api/v1', '/api/v1/simulate/twin') >= 120_000 &&
			limits.proxyBudgetMs('/api/v1', '/api/v1/simulate/twin/compare') >= 120_000 &&
			limits.proxyBudgetMs('/api/v1', '/api/v1/decision-support/osint_event:abc/generate') >= 120_000 &&
			limits.proxyBudgetMs('/api/convoy', '/api/convoy/chat/stream') === 300_000 &&
			limits.proxyBudgetMs('/api/v1', '/api/v1/events/active') === 60_000,
	);
	const socket = new EventEmitter();
	socket.destroyed = false;
	const req = new Request('http://deck.local/api/v1/events/active');
	const watch = limits.clientAbort({ request: req, platform: { req: { socket } } });
	ok('F-CONN-04: not aborted while the client is connected', watch.signal.aborted === false);
	socket.emit('close');
	ok('F-CONN-04: the upstream signal aborts when the client\'s connection closes (a GET has no body to watch)', watch.signal.aborted === true);
	const socket2 = new EventEmitter();
	const w2 = limits.clientAbort({ request: req, platform: { req: { socket: socket2 } } });
	w2.release();
	socket2.emit('close');
	ok('F-CONN-04: a released watch (the answer was streamed) leaves a keep-alive socket alone', w2.signal.aborted === false && socket2.listenerCount('close') === 0);
	const ac = new AbortController();
	const w3 = limits.clientAbort({ request: new Request('http://deck.local/x', { signal: ac.signal }) });
	ac.abort();
	ok('F-CONN-04: the request\'s own abort signal is honoured too', w3.signal.aborted === true);
	const hooks = read('src/hooks.server.ts');
	ok('F-CONN-04/05: the proxy fetch uses the per-path budget AND the client-abort signal', /proxyBudgetMs\(rule\.prefix, event\.url\.pathname\)/.test(hooks) && /AbortSignal\.any\(\[AbortSignal\.timeout\(budgetMs\), client\.signal\]\)/.test(hooks));
});

// ─── F-CONN-11 · the gate allow-list holds no route that does not exist ─────
await group(async () => {
	const prev = process.env.SAJAG_OPERATOR_PIN;
	ok('F-CONN-11: anonymous GET /api/v1/health is denied (the oracle has no such route); the real probes pass', gate.gateDecision('GET', '/api/v1/health') === 'deny' && gate.gateDecision('GET', '/api/convoy/health') === 'allow' && gate.gateDecision('GET', '/api/emulator/health') === 'allow' && gate.gateDecision('GET', '/api/v1/spatial/segments') === 'allow');
	void prev;
});

// ─── F-07 · /design/** is a dev surface ─────────────────────────────────────
await group(async () => {
	ok('F-07: the harness is served under vite dev, or in production only with SAJAG_DESIGN_HARNESS=1 exactly', harness.designHarnessOn(true, undefined) && !harness.designHarnessOn(false, undefined) && !harness.designHarnessOn(false, 'true') && !harness.designHarnessOn(false, '0') && harness.designHarnessOn(false, '1'));
	const lay = path.join(SRC, 'routes/(deck)/design/+layout.server.ts');
	ok('F-07: every /design route runs the guard (a +layout.server.ts at the design root answers 404)', existsSync(lay) && /designHarnessOn\(dev, env\.SAJAG_DESIGN_HARNESS\)/.test(readFileSync(lay, 'utf8')) && /error\(404/.test(readFileSync(lay, 'utf8')));
	ok('F-07: scripts/verify_all.sh serves its gate-off previews with the harness on (its smokes drive /design)', /"SAJAG_DESIGN_HARNESS=1"\)/.test(readFileSync(path.resolve(DECK, '../../scripts/verify_all.sh'), 'utf8')));
});

// ─── F-10 · /chat and /comms show the sign-in card with the gate on ─────────
await group(async () => {
	for (const [page, testid, key] of [['src/routes/(deck)/chat/+page.svelte', 'chat-signin-required', 'chatSigninBody'], ['src/routes/(deck)/comms/+page.svelte', 'comms-signin-required', 'commsSigninBody']]) {
		const src = read(page);
		const markup = src.slice(src.indexOf('</svelte:head>'));
		ok(`F-10: ${page.split('/').at(-2)} mounts only the sign-in card while signInRequired (no panel of refused reads)`, /^\s*\{#if ops\.signInRequired\}/.test(markup.slice('</svelte:head>'.length)) && markup.includes(`testid="${testid}"`) && localised(tOps, key));
	}
});

// ─── F-22 / F-23 / F-30 ─────────────────────────────────────────────────────
await group(async () => {
	const root = read('src/routes/(deck)/+page.svelte');
	const share = root.slice(root.indexOf('async function share()'), root.indexOf('async function share()') + 900);
	ok('F-22: Share on / says its outcome (a toast for the copy, one for the refusal)', /toasts\.push\(\{ kind: 'info', title: L\('wall_share_done'\)/.test(share) && /toasts\.push\(\{ kind: 'error', title: L\('wall_share_failed'\) \}\)/.test(share));
	const err = path.join(SRC, 'routes/+error.svelte');
	ok('F-23: an error page exists, titled and localised, with a way back', existsSync(err) && /ui_err_404_title/.test(readFileSync(err, 'utf8')) && /href="\/"/.test(readFileSync(err, 'utf8')) && ['ui_err_404_title', 'ui_err_404_body', 'ui_err_title', 'ui_err_body', 'ui_err_home'].every((k) => localised(t, k)));
	ok('F-30: the components nothing mounted are gone', !existsSync(path.join(SRC, 'lib/gods-eye/hud/EntityDossier.svelte')) && !existsSync(path.join(SRC, 'lib/primitives/Toast.svelte')));
});

// ─── F-28 · no local audit row for a write the oracle refused ───────────────
await group(async () => {
	const store = read('src/lib/ops/store.svelte.ts');
	const fn = (name) => store.slice(store.indexOf(`async ${name}(`), store.indexOf('\n\t}\n', store.indexOf(`async ${name}(`)));
	const req = fn('requestDispatchUnit');
	const dec = fn('decideDispatchAction');
	ok('F-28: the "requested" / "approved" rows are written only after the oracle accepted the request (behind the await)', req.indexOf('await requestDispatch(') < req.indexOf("'decision',") && dec.indexOf('await decideDispatch(') < dec.indexOf("'decision', officer"));
});

// ─── F-29 · nothing truncates mid-word at 1366 (the rules; the smoke measures) ─
await group(async () => {
	ok('F-29: the map rule chip has a short form in EN/HI/MR and switches to it when the full line does not fit', localised(t, 'map_rule_note_short') && /use:fitRule/.test(read('src/lib/gods-eye/hud/map/MapReadout.svelte')));
	ok('F-29: Inbox titles wrap (a verb is never cut), the mark keeps its box', /flex-wrap: wrap/.test(read('src/lib/decisions/InboxRow.svelte')) && !/\.t-pre,\n\t\.t-post \{[^}]*text-overflow: ellipsis/.test(read('src/lib/decisions/Inbox.svelte')));
	ok('F-29: the anomaly cell\'s sub line is short enough for a 1366 strip (≤ 22 characters in EN)', t('en', 'wall_m_anomalies_sub').length <= 22, t('en', 'wall_m_anomalies_sub'));
});

// ─── COPY-9 · no competition wording in the deck's source, tests or fixtures ─
await group(async () => {
	const WORDS = new RegExp(['judg', 'mentor', 'submission', 'problem[ _-]?statement', 'ps-?18', 'hack' + 'athon', 'competition', '\\bjury\\b'].join('|'), 'i');
	const SELF = path.join(HERE, 'deck-fixes.unit.mjs');
	const hits = [];
	const walk = (dir) => {
		for (const d of readdirSync(dir, { withFileTypes: true })) {
			const p = path.join(dir, d.name);
			if (d.isDirectory()) {
				if (['node_modules', 'artifacts', '.svelte-kit', 'build'].includes(d.name)) continue;
				walk(p);
			} else if (/\.(ts|js|mjs|svelte|json|py|css|html)$/.test(d.name) && p !== SELF && !p.endsWith('LICENSE-blueprint.txt') && statSync(p).size < 4_000_000) {
				const lines = readFileSync(p, 'utf8').split('\n');
				lines.forEach((l, i) => {
					if (WORDS.test(l)) hits.push(`${path.relative(DECK, p)}:${i + 1}`);
				});
			}
		}
	};
	walk(SRC);
	walk(HERE);
	walk(path.join(DECK, 'static'));
	ok('COPY-9: no judge/judging/mentor/submission/problem-statement/ps18 wording in src/, tests/ (fixtures included) or static/', hits.length === 0, hits.slice(0, 6).join(' | ') || 'none');
});

// ─── F-CONN-10 · the dead client functions are gone ─────────────────────────
await group(async () => {
	const api = read('src/lib/api/client.ts');
	const exported = [...api.matchAll(/^export (?:async )?function (\w+)/gm)].map((m) => m[1]);
	const srcFiles = [];
	(function walk(dir) {
		for (const d of readdirSync(dir, { withFileTypes: true })) {
			const p = path.join(dir, d.name);
			if (d.isDirectory()) walk(p);
			else if (/\.(ts|svelte)$/.test(d.name) && !p.endsWith(path.join('lib', 'api', 'client.ts'))) srcFiles.push(readFileSync(p, 'utf8'));
		}
	})(SRC);
	const unused = exported.filter((f) => !srcFiles.some((s) => new RegExp(`\\b${f}\\b`).test(s)) && (api.match(new RegExp(`\\b${f}\\b`, 'g')) ?? []).length < 2);
	ok('F-CONN-10: every lib/api/client.ts export is used (the 11 dead calls are gone)', unused.length === 0, unused.join(', ') || `${exported.length} exports used`);
	ok('F-CONN-10: ops/client.ts has no fetchAdaptiveParams (a GET that writes an override row per call)', !/fetchAdaptiveParams/.test(read('src/lib/ops/client.ts')));
});

// ─── F-CONN-09 · the contract runner never defaults to a live oracle ────────
await group(async () => {
	const env = { ...process.env };
	delete env.ORACLE_PORT;
	// the child's network is cut BEFORE run.mjs loads (a preloaded fetch that refuses everything): on a
	// tree without the fix, the old runner would otherwise read the live :8091 oracle by default
	const NO_NET = 'data:text/javascript,globalThis.fetch=async()=>{throw new Error("network blocked by deck-fixes.unit")}';
	const r = spawnSync(process.execPath, ['--import', NO_NET, 'tests/contract/run.mjs', '--live'], { cwd: DECK, env, encoding: 'utf8', timeout: 60_000 });
	ok('F-CONN-09: --live with no URL and no ORACLE_PORT refuses before any request (no live default)', r.status === 2 && /no oracle given/.test(r.stderr) && /Nothing was requested/.test(r.stderr), `exit ${r.status} ${r.stderr.trim().slice(0, 120)}`);
	const run = read('tests/contract/run.mjs');
	ok('F-CONN-09: ORACLE_PORT names the oracle; the bundle goes to a temp dir, never tests/artifacts', /env\.ORACLE_PORT/.test(run) && /mkdtempSync\(path\.join\(os\.tmpdir\(\)/.test(run) && !/path\.join\(DECK, 'tests', 'artifacts', 'contract-bundle\.mjs'\)/.test(run) && !/127\.0\.0\.1:8091'\)/.test(run));
});

// ─── F-CONN-16 · vite dev binds loopback and names its backends ─────────────
await group(async () => {
	const out = path.join(OUT_DIR, 'vite-config.mjs');
	// the config's own logic, with vite and the SvelteKit plugin stubbed (no server is started)
	const stubVite = {
		name: 'stub-vite',
		setup(b) {
			b.onResolve({ filter: /^(vite|@sveltejs\/kit\/vite)$/ }, (a) => ({ path: a.path, namespace: 'stub-vite' }));
			b.onLoad({ filter: /.*/, namespace: 'stub-vite' }, (a) => ({ contents: a.path === 'vite' ? 'export const defineConfig = (c) => c;' : "export const sveltekit = () => ({ name: 'sveltekit' });", loader: 'js' }));
		},
	};
	const vb = await esbuild.build({ entryPoints: [path.join(DECK, 'vite.config.ts')], bundle: true, format: 'esm', platform: 'node', outfile: out, logLevel: 'silent', plugins: [stubVite], absWorkingDir: DECK });
	const cfgMod = await import(pathToFileURL(out).href);
	let threw = null;
	try {
		cfgMod.devBackends({});
	} catch (e) {
		threw = e.message;
	}
	const b = cfgMod.devBackends({ ORACLE_PORT: '8162', BRAIN_PORT: '8262', EMULATOR_PORT: '8962' });
	ok('F-CONN-16: devBackends refuses missing ports (no live default) and pins loopback', vb.errors.length === 0 && /ORACLE_PORT/.test(threw ?? '') && b.oracle === 'http://127.0.0.1:8162' && b.brain === 'http://127.0.0.1:8262' && b.emulator === 'http://127.0.0.1:8962', threw ?? 'no throw');
	const dev = cfgMod.default({ command: 'serve', mode: 'development', isPreview: false });
	const hook = dev.plugins.flat().find((p) => p?.name === 'sajag-require-dev-backends');
	let startErr = null;
	const saved = { o: process.env.ORACLE_PORT, b: process.env.BRAIN_PORT, e: process.env.EMULATOR_PORT };
	try {
		hook?.configureServer?.();
	} catch (e) {
		startErr = e.message;
	}
	ok('F-CONN-16: the dev server binds 127.0.0.1, and refuses to START without the ports (config loaders need none)', dev.server.host === '127.0.0.1' && (saved.o ? startErr === null && !!dev.server.proxy : /ORACLE_PORT/.test(startErr ?? '') && dev.server.proxy === undefined), `host ${dev.server.host} · start ${startErr ?? 'ok'}`);
	const build = cfgMod.default({ command: 'build', mode: 'production', isPreview: false });
	ok('F-CONN-16: a build needs no ports and carries no dev proxy', build.server.proxy === undefined);
});

// ─── D-07 · the unused kickoff-baseline lookup is gone ──────────────────────
ok('D-07: route-budget.unit and route-coldload define no unused findBaseline', !/function findBaseline/.test(read('tests/route-budget.unit.mjs')) && !/function findBaseline/.test(read('tests/route-coldload.mjs')));

// ─── done ───────────────────────────────────────────────────────────────────
if (failures) {
	console.error(`deck-fixes.unit: ${failures} FAILURE(S)`);
	process.exit(1);
}
console.log('deck-fixes.unit: all green');
