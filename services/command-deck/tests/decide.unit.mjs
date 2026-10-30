/**
 * V3 Decide unit test (V3-P2; V3-SPEC §5.3, §6.2, §7.1, §9.1) — zero browser.
 *
 *   node tests/decide.unit.mjs
 *
 * esbuild bundles the REAL modules — src/lib/v3/decide/{model, run, session.svelte, packs.decide*},
 * decisions/{units, writers, register}, the ops store, the dss store and the city registry — with `$lib`
 * aliased, rune identity stubs and every `.svelte` component stubbed (the home.unit.mjs harness). A fetch
 * stub answers every GET from the hermetic fixture world of tests/decide-smoke.mjs and RECORDS every
 * non-GET (answering it with a canned reply where a check needs the server's words; nothing leaves the
 * process), so "one POST" is counted, not assumed.
 *
 * Asserts:
 *   - the pack: EN / HI / MR carry the same keys, every key starts with v3d_, EN copy rules (≤ one " · ",
 *     titles ≤ 32, no ALL-CAPS word outside the acronyms), HI / MR translated and in their own script, the
 *     officer helper is §9.1's sentence word for word;
 *   - keyIntent: J / K / ↑ / ↓ move, 1–4 choose, Enter only focuses, R opens the reason — NO key approves;
 *     modifiers and typing are ignored; stepKey wraps;
 *   - actionsOf for every unit kind in UNIT_KINDS (from the fixture world): the primary and secondaries,
 *     each one backed by an EXISTING writer; an e-challan on a stolen vehicle and a refused one offer no
 *     Approve; needsReason; the escort phase (open → expired → answered);
 *   - coaFigure (one figure per option; watching is no action), whenOf, the countdown ring, deep links
 *     (a hostile or unknown key is refused; hrefs never carry a mark);
 *   - runDecision through the real writers: no officer → nothing sent; a double run → ONE POST; a repeat
 *     after success → refused, nothing sent; the chosen course of action is the one posted; a vetoed one
 *     is refused before the wire; a 409 is kept verbatim and never retried; a reason-needing verb without
 *     a reason sends nothing; an e-challan on a stolen vehicle is never approved; "failed" with no words
 *     says no confirmation came back; the session tally counts what was done;
 *   - masking: the change rows and the recorded outcome carry no raw mark without an officer.
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { existsSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { decideFixtures } from './decide-smoke.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const OUT = path.join(HERE, 'artifacts', 'decide-bundle.mjs');

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
export * as model from './src/lib/v3/decide/model';
export * as run from './src/lib/v3/decide/run';
export * as session from './src/lib/v3/decide/session.svelte';
export * as pack from './src/lib/v3/decide/packs.decide';
export { hi } from './src/lib/v3/decide/packs.decide.hi';
export { mr } from './src/lib/v3/decide/packs.decide.mr';
export * as units from './src/lib/decisions/units';
export * as writers from './src/lib/decisions/writers';
export * as reg from './src/lib/decisions/register';
export * as dss from './src/lib/dss/dss-store.svelte';
export * as opsStore from './src/lib/ops/store.svelte';
export * as cityReg from './src/lib/gods-eye/entities/registry.svelte';
export { t } from './src/lib/i18n/strings';
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
	stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'decide-entry.ts' },
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

// ─── the fixture world, served to the real clients; every write recorded ────

const NOW = Date.now();
const fx = decideFixtures(NOW);
const E = fx.expect;
const writes = [];
/** Canned replies for writes (null → 503, i.e. the write "did not go through"). */
let reply = () => null;
globalThis.fetch = async (url, init = {}) => {
	const method = (init.method ?? 'GET').toUpperCase();
	const u = new URL(String(url), 'http://deck.local');
	if (method !== 'GET') {
		writes.push({ method, path: u.pathname, body: typeof init.body === 'string' ? init.body : '' });
		const r = reply(method, u.pathname, init.body);
		if (r?.delayMs) await new Promise((res) => setTimeout(res, r.delayMs));
		return r ? new Response(JSON.stringify(r.body ?? {}), { status: r.status, headers: { 'content-type': 'application/json' } }) : new Response('', { status: 503 });
	}
	const a = fx.answer(u.pathname + u.search);
	return a
		? new Response(JSON.stringify(a.body), { status: a.status, headers: { 'content-type': 'application/json' } })
		: new Response('{"detail":"Not Found"}', { status: 404, headers: { 'content-type': 'application/json' } });
};

const M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
const { model, run, session, pack, units: U, writers: W } = M;
const { ops } = M.opsStore;
const registry = M.cityReg.cityRegistry;
const L = (k, ...a) => M.t('en', k, ...a);

// ─── 1. the pack ─────────────────────────────────────────────────────────────

{
	const en = pack.DECIDE_PACKS.en;
	const keys = Object.keys(en);
	const same = (a, b) => a.length === b.length && a.every((k) => b.includes(k));
	ok('pack: EN / HI / MR carry the same keys', same(keys, Object.keys(M.hi)) && same(keys, Object.keys(M.mr)), `${keys.length} keys`);
	ok('pack: every key starts with v3d_', keys.every((k) => k.startsWith('v3d_')));
	const text = (v) => (typeof v === 'function' ? v('‹x›', '‹y›', '‹z›') : v);
	const ACR = new Set('FIR ANPR IST VVIP AI ID OSM ETA OSINT ICCC IMD DSS SMS GPS API PIN CCTV SG CG SP'.split(' '));
	const bad = [];
	for (const [k, v] of Object.entries(en)) {
		const s = String(text(v));
		if ((s.match(/ · /g) ?? []).length > 1) bad.push(`${k}: separator`);
		if (/(title|heading)$/.test(k) && s.length > 32) bad.push(`${k}: title > 32`);
		for (const w of s.split(/[^A-Za-z0-9•]+/)) if (w.length > 1 && /^[A-Z]+$/.test(w) && !ACR.has(w)) bad.push(`${k}: ALL-CAPS ${w}`);
	}
	ok('pack EN copy rules: ≤ one " · ", titles ≤ 32, no ALL-CAPS word outside the acronyms', bad.length === 0, bad.slice(0, 6).join(' | '));
	const untranslated = (p) => keys.filter((k) => {
		const a = String(text(en[k]));
		return a === String(text(p[k])) && /[a-z]{4}/.test(a);
	});
	ok('pack: HI and MR are translated (no EN sentence left in place)', untranslated(M.hi).length === 0 && untranslated(M.mr).length === 0, [...untranslated(M.hi), ...untranslated(M.mr)].join(', '));
	const leakHi = Object.values(M.hi).map(text).filter((s) => /[ঀ-৿]/.test(String(s)));
	const leakMr = Object.values(M.mr).map(text).filter((s) => /[ঀ-৿०-९]/.test(String(s)));
	ok('pack: no Bengali script left in HI or MR, and MR keeps Latin digits (Marathi is Devanagari)', leakHi.length === 0 && leakMr.length === 0);
	ok('the officer helper is §9.1\'s sentence, word for word', en.v3d_officer_helper === 'Naming yourself shows full registration marks on this console and records your name with the decision. Attribution, not sign-in.');
	ok('the expiry copy says the plan is kept', /current plan is kept/.test(en.v3d_ifnot_escort) && /current plan is kept/i.test(en.v3d_expired_text) && /kept/.test(en.v3d_q_expired));
}

// ─── 2. the keyboard ─────────────────────────────────────────────────────────

{
	const k = (key, extra = {}) => model.keyIntent({ key, ...extra }, false)?.kind ?? null;
	ok('J / ↓ next, K / ↑ previous', k('j') === 'next' && k('J') === 'next' && k('ArrowDown') === 'next' && k('k') === 'prev' && k('ArrowUp') === 'prev');
	ok('1–4 choose an option (index 0–3)', [1, 2, 3, 4].every((n) => model.keyIntent({ key: String(n) }, false)?.index === n - 1) && k('5') === null);
	ok('Enter only focuses the primary; R opens the reason', k('Enter') === 'focus-primary' && k('r') === 'reason');
	const every = [];
	for (let c = 32; c < 127; c++) every.push(model.keyIntent({ key: String.fromCharCode(c) }, false)?.kind ?? null);
	for (const key of ['Enter', ' ', 'Escape', 'Tab', 'ArrowLeft', 'ArrowRight', 'Home', 'End', 'PageDown']) every.push(model.keyIntent({ key }, false)?.kind ?? null);
	ok('NO key maps to approve, dispatch or unmask (every printable key and the navigation keys)', every.every((x) => x === null || ['next', 'prev', 'option', 'focus-primary', 'reason'].includes(x)) && !every.includes('approve'));
	ok('keys with Ctrl / ⌘ / Alt, keys while typing, and keys another handler took are ignored', k('j', { ctrlKey: true }) === null && k('j', { metaKey: true }) === null && k('1', { altKey: true }) === null && model.keyIntent({ key: 'j' }, true) === null && k('j', { defaultPrevented: true }) === null);
	const list = [{ kind: 'a', id: '1' }, { kind: 'a', id: '2' }, { kind: 'a', id: '3' }];
	ok('stepKey: next, previous and wrap; the first (or last) when nothing is current', model.stepKey(list, 'a:1', 1) === 'a:2' && model.stepKey(list, 'a:3', 1) === 'a:1' && model.stepKey(list, 'a:1', -1) === 'a:3' && model.stepKey(list, null, 1) === 'a:1' && model.stepKey(list, null, -1) === 'a:3' && model.stepKey([], 'x', 1) === null);
}

// ─── 3. deep links, rings, figures ───────────────────────────────────────────

{
	ok('parseDeepLink: <kind>:<id> (encoded or not) for a known kind', JSON.stringify(model.parseDeepLink(encodeURIComponent('dss:abc-1'))) === '{"kind":"dss","id":"abc-1"}' && model.parseDeepLink('echallan:r1')?.kind === 'echallan');
	ok('parseDeepLink: a hostile, malformed or unknown key is refused', [null, '', '<img src=x>', 'dss:', ':x', 'nosuchkind:1', '%E0%A4%A', 'dss:../../etc', 'dss:a b'].every((v) => model.parseDeepLink(v) === null));
	ok('decideHref: /decide/<kind>:<id>, never a mark', model.decideHref({ kind: 'stolen-sighting', id: 'v-1' }) === `/decide/${encodeURIComponent('stolen-sighting:v-1')}`);
	ok('ringFraction drains from 1 to 0 (90 s default window)', model.ringFraction(90, 90) === 1 && model.ringFraction(45, 90) === 0.5 && model.ringFraction(-3, 90) === 0 && model.ringFraction(45, null) === 0.5);
	ok('the ring announces once at 30 s and once at 10 s, never every second', model.announceAt(31, 30) === 30 && model.announceAt(30, 29) === null && model.announceAt(11, 10) === 10 && model.announceAt(null, 30) === null && model.announceAt(5, 4) === null);
	const coa = (o) => ({ coaId: 'c', kind: 'standard', label: 'x', actions: [], dispatches: [], responseToSceneSec: null, etaToSceneSec: null, timeToEffectSec: null, feasible: true, vetoed: false, ...o });
	ok('coaFigure: time to the scene as m:ss', model.coaFigure(coa({ actions: [{ verb: 'dispatch', params: {} }], responseToSceneSec: 393 })).value === '6:33' && model.coaFigure(coa({ actions: [{ verb: 'dispatch', params: {} }], responseToSceneSec: 393 })).labelKey === 'v3d_opt_to_scene');
	ok('coaFigure: watching is "no action" (never a 0:00 clock)', model.coaFigure(coa({ actions: [{ verb: 'monitor', params: {} }], timeToEffectSec: 0 })).labelKey === 'v3d_opt_no_action');
	ok('coaFigure: an advisory takes effect; nothing measured → "no units"', model.coaFigure(coa({ actions: [{ verb: 'advisory', params: {} }], timeToEffectSec: 120 })).value === '2:00' && model.coaFigure(coa({ actions: [{ verb: 'advisory', params: {} }] })).labelKey === 'v3d_opt_no_units');
}

// ─── 4. the fixture world through the real stores ────────────────────────────

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
const all = () => U.decisionUnits(ops);
const unit = (kind, id) => all().find((u) => u.kind === kind && (!id || u.id === id));
const units = all();
ok('the fixture world: every unit kind waits, soonest deadline first', JSON.stringify(units.map((u) => u.kind)) === JSON.stringify(E.unitOrder), units.map((u) => u.kind).join(', '));
ok('every kind in UNIT_KINDS is in the world', Object.keys(U.UNIT_KINDS).every((k) => units.some((u) => u.kind === k)), Object.keys(U.UNIT_KINDS).join(', '));

{
	const A = (u) => JSON.stringify(model.actionsOf(u));
	const esc = unit('escort-proposal');
	ok('actions: escort → approve · reject', A(esc) === '{"primary":"approve","secondary":["reject"]}');
	ok('actions: 108 → approve · defer', A(unit('corridor-request')) === '{"primary":"approve","secondary":["defer"]}');
	ok('actions: decision support → approve · reject, defer', A(unit('dss')) === '{"primary":"approve","secondary":["reject","defer"]}');
	ok('actions: stolen vehicle → authorise · dismiss', A(unit('stolen-sighting')) === '{"primary":"authorise","secondary":["dismiss"]}');
	ok('actions: pursuit → open', A(unit('pursuit')) === '{"primary":"open","secondary":[]}');
	ok('actions: e-challan → approve · reject; on a stolen vehicle → reject ONLY', A(unit('echallan', E.ids.recSpeed)) === '{"primary":"approve","secondary":["reject"]}' && A(unit('echallan', E.ids.recStolenPenal)) === '{"primary":null,"secondary":["reject"]}');
	const missing = [];
	for (const u of units) {
		const a = model.actionsOf(u);
		for (const v of [a.primary, ...a.secondary].filter(Boolean)) if (!model.writerOf(u, v)) missing.push(`${u.kind}.${v}`);
	}
	ok('every verb Decide offers runs an EXISTING writer (decisions/writers.ts)', missing.length === 0, missing.join(', ') || `${units.length} units`);
	ok('Open pursuit runs the pursuit writer, whatever the unit', model.writerKindOf(unit('stolen-sighting'), 'open') === 'pursuit' && model.writerOf(unit('stolen-sighting'), 'open') === W.WRITERS['pursuit.open']);
	ok('needsReason: dismiss, reject (not the escort\'s), defer', model.needsReason(unit('stolen-sighting'), 'dismiss') && model.needsReason(unit('dss'), 'reject') && model.needsReason(unit('dss'), 'defer') && model.needsReason(unit('corridor-request'), 'defer') && !model.needsReason(esc, 'reject') && !model.needsReason(esc, 'approve'));
	ok('escortPhase: open before the deadline, expired after it, answered once answered', model.escortPhase(esc, NOW, () => false) === 'open' && model.escortPhase(esc, esc.deadline + 1, () => false) === 'expired' && model.escortPhase(esc, NOW, () => true) === 'answered');
	const w1 = model.whenOf(esc, esc.deadline - 47_000, 'en', L);
	const w2 = model.whenOf(unit('dss'), unit('dss').deadline - (94 * 60_000), 'en', L);
	const w3 = model.whenOf(unit('stolen-sighting'), NOW, 'en', L);
	const w4 = model.whenOf(esc, esc.deadline + 5, 'en', L);
	ok('whenOf: "0:47 left" (urgent < 1 min), "1 h 34 min left", "waiting 14 min", "Time is up"', w1.text === '0:47 left' && w1.urgent && w2.text === '1 h 34 min left' && /^waiting 14 min$/.test(w3.text) && w4.text === 'Time is up', [w1.text, w2.text, w3.text, w4.text].join(' | '));
}

// ─── 5. masking in what Decide prints ─────────────────────────────────────────

const RAW = E.rawPlates.map((p) => new RegExp(p.split('').join('[ .-]?'), 'i'));
const hasRaw = (s) => RAW.some((r) => r.test(s));
{
	const rows = [];
	for (const u of units) for (const v of [model.actionsOf(u).primary, ...model.actionsOf(u).secondary].filter(Boolean)) rows.push(...(model.writerOf(u, v)?.changes(u) ?? []));
	ok('no raw mark in any change row without an officer', !ops.officerOn && rows.length > 0 && !hasRaw(JSON.stringify(rows)), `${rows.length} rows`);
	ops.setDutyOfficer('R. Mehta');
	const named = JSON.stringify(model.writerOf(unit('echallan', E.ids.recSpeed), 'approve').changes(unit('echallan', E.ids.recSpeed)));
	ok('a named officer sees the e-challan\'s full mark in its row', /MH01KD4521/.test(named), named.slice(0, 120));
	ops.setDutyOfficer('');
	ok('clearing the officer masks the rows again', !hasRaw(JSON.stringify(model.writerOf(unit('echallan', E.ids.recSpeed), 'approve').changes(unit('echallan', E.ids.recSpeed)))));
}

// ─── 6. deciding, through the real writers ────────────────────────────────────

W.resetWriterGuards();
session.decideSession.reset();
const sent = (re) => writes.filter((w) => re.test(w.path));

{
	// no officer: nothing leaves
	const before = writes.length;
	const o = await run.runDecision(unit('escort-proposal'), 'approve');
	const o2 = await run.runDecision(unit('dss'), 'approve', { coaId: 'coa_std' });
	ok('no officer: the writer refuses before any request (nothing sent)', writes.length === before && o?.ok === false && o.posts === 0 && o2?.ok === false && o2.posts === 0, `${o?.refusal} · ${o2?.refusal}`);
	ok('no officer: the refusal says to name a duty officer', /Name a duty officer/.test(o?.refusal ?? ''), o?.refusal);
}

ops.setDutyOfficer('R. Mehta');

{
	// escort: two runs at once → one POST; a third after success → nothing
	reply = (m, p) => (/\/escort\/approvals\//.test(p) ? { status: 200, body: { status: 'approved', action: 'hold_position' }, delayMs: 60 } : null);
	const u = unit('escort-proposal');
	const [a, b] = await Promise.all([run.runDecision(u, 'approve'), run.runDecision(u, 'approve')]);
	ok('escort: a double run sends ONE POST and both callers get the same outcome', sent(/\/escort\/approvals\//).length === 1 && a === b && a?.ok === true, `${sent(/\/escort\/approvals\//).length} POST(s)`);
	ok('escort: the outcome is "Escort proposal approved", with the officer and the next step', a?.verb === 'Escort proposal approved' && a.officer === 'R. Mehta' && !!a.next);
	const c = await run.runDecision(u, 'approve');
	const d = await run.runDecision(u, 'reject');
	ok('escort: once answered it stays locked — approve or reject again sends nothing', sent(/\/escort\/approvals\//).length === 1 && c?.ok === false && d?.ok === false && ops.escortAnswered(E.ids.approval), `${c?.refusal} · ${d?.refusal}`);
}

{
	// decision support: the chosen option is posted; a vetoed one never leaves; a 409 is verbatim
	const u = unit('dss');
	await M.dss.ensureDssObject(u.id);
	ok('the decision-support object loads through the dss store (one GET)', !!M.dss.dssState.objects[u.id]);
	const DET = 'decision support is no longer proposed: approved by S. Rao at 19:40';
	reply = (m, p) => (/\/decision-support\/[^/]+\/decision$/.test(p) ? { status: 409, body: { detail: DET } } : null);
	const before = writes.length;
	const v = await run.runDecision(u, 'approve', { coaId: 'coa_stop_vehicles' });
	const i = await run.runDecision(u, 'approve', { coaId: 'coa_agg' });
	ok('a vetoed or under-resourced option is refused before the wire', writes.length === before && v?.ok === false && i?.ok === false, `${v?.refusal} · ${i?.refusal}`);
	const o = await run.runDecision(u, 'approve', { coaId: 'coa_info' });
	const posted = sent(/\/decision-support\/[^/]+\/decision$/);
	ok('the CHOSEN option is the one posted (coa_id coa_info)', posted.length === 1 && JSON.parse(posted[0].body).coa_id === 'coa_info' && JSON.parse(posted[0].body).decision === 'approve', posted[0]?.body);
	ok('a 409: the server\'s own words, verbatim, kept on the outcome (not done)', o?.ok === false && o.detail === DET, `${o?.refusal} · ${o?.detail}`);
	const r0 = writes.length;
	const r = await run.runDecision(u, 'reject', { note: '' });
	ok('reject without a reason sends nothing', writes.length === r0 && r?.ok === false && /reason/i.test(r.refusal ?? ''), r?.refusal);
}

{
	// e-challans: 409 verbatim and never retried; a stolen vehicle's is never approved
	const ECH = 'e-challan withheld: the camera calibration certificate for EM-CAM-02 has lapsed';
	reply = (m, p) => (p.endsWith(`/recommendations/${E.ids.recSpeed}/decision`) ? { status: 409, body: { detail: ECH, reason: 'calibration' } } : null);
	const u = unit('echallan', E.ids.recSpeed);
	const o = await run.runDecision(u, 'approve');
	ok('e-challan 409: ONE POST, the oracle\'s sentence verbatim', sent(new RegExp(`${E.ids.recSpeed}/decision$`)).length === 1 && o?.ok === false && o.detail === ECH, o?.detail);
	const again = await run.runDecision(unit('echallan', E.ids.recSpeed), 'approve');
	ok('a refused e-challan is never retried (nothing sent), and no longer offers Approve', sent(new RegExp(`${E.ids.recSpeed}/decision$`)).length === 1 && again?.ok === false && model.actionsOf(unit('echallan', E.ids.recSpeed)).primary === null);
	const s0 = writes.length;
	const st = await run.runDecision(unit('echallan', E.ids.recStolenPenal), 'approve');
	ok('an e-challan on a stolen vehicle is never approved (refused before the wire)', writes.length === s0 && st?.ok === false && /stolen/i.test(st.refusal ?? ''), st?.refusal);
}

{
	// stolen vehicle: dismiss needs a reason; authorise posts the NEWEST sighting once
	const u = unit('stolen-sighting');
	const d0 = writes.length;
	const d = await run.runDecision(u, 'dismiss', { note: '  ' });
	ok('dismiss without a reason sends nothing', writes.length === d0 && d?.ok === false);
	reply = (m, p) => (p.endsWith(`/recommendations/${E.ids.recNewest}/decision`) ? { status: 200, body: { status: 'approved' }, delayMs: 40 } : null);
	const [a, b] = await Promise.all([run.runDecision(u, 'authorise'), run.runDecision(u, 'authorise')]);
	ok('authorise: a double run → ONE POST, for the newest sighting', sent(new RegExp(`${E.ids.recNewest}/decision$`)).length === 1 && a === b && a?.ok === true && a.verb === 'Pursuit authorised');
	const p0 = writes.length;
	const p = await run.runDecision(unit('pursuit'), 'open');
	ok('a pursuit opening with no approved sighting is refused before the wire', writes.length === p0 && p?.ok === false && /human-approved/.test(p.refusal ?? ''), p?.refusal);
}

{
	// 108: approve once; a failure with no words says no confirmation came back
	reply = () => null;
	const u = unit('corridor-request');
	const o = await run.runDecision(u, 'approve');
	ok('a write that fails with no words is never shown as decided: "No confirmation came back"', o?.ok === false && /No confirmation came back/.test(o.refusal ?? ''), o?.refusal);
	reply = (m, p) => (p.endsWith(`/dispatches/${E.ids.dispatch108}/decision`) ? { status: 200, body: { dispatch_id: E.ids.dispatch108, status: 'approved', agency: 'ambulance', audit: [] } } : null);
	W.resetWriterGuards();
	const n0 = sent(new RegExp(`/dispatches/${E.ids.dispatch108}/decision$`)).length;
	const [a, b] = await Promise.all([run.runDecision(u, 'approve'), run.runDecision(u, 'approve')]);
	ok('108 approve: a double run → ONE POST', sent(new RegExp(`/dispatches/${E.ids.dispatch108}/decision$`)).length === n0 + 1 && a === b && a?.ok === true && a.verb === 'Ambulance (108) corridor approved');
}

{
	const t = session.decideSession.tally;
	ok('the session tally counts what this console did (3 approved; refusals not counted)', t.approved === 3 && t.rejected === 0 && t.deferred === 0, JSON.stringify(t));
	session.decideSession.markExpired('escort-proposal:x', unit('escort-proposal'), NOW);
	session.decideSession.markExpired('escort-proposal:x', unit('escort-proposal'), NOW);
	ok('an expiry is tallied once ("expired, plan kept")', session.decideSession.tally.expired === 1);
	const outs = Object.values(session.decideSession.outcomes);
	ops.setDutyOfficer('');
	ok('no raw mark in any recorded outcome\'s title, refusal or next step', !hasRaw(JSON.stringify(outs.map((o) => [o.unit.title, o.refusal, o.next, o.verb]))));
	ok('every refusal kept the server\'s words verbatim or said none came', outs.filter((o) => !o.ok).every((o) => (o.refusal ?? '').length > 0));
}

const nonGet = writes.map((w) => `${w.method} ${w.path}`);
const expected = [
	`POST /api/convoy/movements/${E.movement}/escort/approvals/${E.ids.approval}`,
	`POST /api/v1/decision-support/${E.ids.dss}/decision`,
	`POST /api/v1/enforcement/recommendations/${E.ids.recSpeed}/decision`,
	`POST /api/v1/enforcement/recommendations/${E.ids.recNewest}/decision`,
	`POST /api/v1/dispatches/${E.ids.dispatch108}/decision`,
	`POST /api/v1/dispatches/${E.ids.dispatch108}/decision`,
];
ok('exactly the writes this test meant: one per decision sent (the 108 twice: the failed try, then the success)', JSON.stringify(nonGet) === JSON.stringify(expected), nonGet.join(' | '));

console.log(failures ? `\n${failures} FAILED` : '\ndecide.unit: ALL OK');
process.exit(failures ? 1 : 0);
