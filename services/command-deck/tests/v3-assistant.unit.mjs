/**
 * V3 Assistant unit test (V3-P4; V3-SPEC §5.7, §7.6, §8) — zero browser.
 *
 *   node tests/v3-assistant.unit.mjs
 *
 * esbuild bundles the REAL modules ($lib aliased; .svelte and .svelte.ts compiled for the server with svelte/compiler,
 * the assistant.unit pattern); a fetch stub answers POST /api/convoy/chat/stream with canned NDJSON turns and RECORDS
 * every request (nothing leaves the process; no model is called).
 *
 *   pack      EN / HI / MR carry the same keys, every key starts with v3a_; EN copy rules; HI / MR translated; every
 *             caution and every brain tool has its words in all three; no string claims Apply/Approve as the
 *             assistant's own verb
 *   cautions  each brain code (decider_gemma_disagreement, low_confidence_decision, novel_situation_confident_answer,
 *             decider_unavailable, novelty_check_unavailable) → its ONE sentence; an unknown code → the generic
 *             sentence, never the code; ungrounded_claims_removed is the grounding note, not a caution; a gemma-only
 *             turn → "Answered by the backup model"; degraded → the reduced-mode sentence; duplicates fold
 *   words     scrubCodes leaves no brain tool name or alert code in the prose (and leaves other prose alone);
 *             humaniseLookups leaves no snake_case identifier; toolLabel never prints an underscore; modelKey never
 *             returns a model id; segmentProse round-trips the text, longest label first, short labels never chips
 *   session   the SHARED ChatSession (the one AssistantPanel runs): one POST per send; a second send while
 *             streaming sends nothing; tokens accumulate on the proxied entry; done keeps the brain session and the
 *             follow-up carries it; a new event scope drops it; a directive is queued on the canvas bus for a human
 *             (never applied); a failed stream marks the turn and the session degraded; clear forgets; release keeps
 *             the conversation for the next mount and marks a cut-off turn
 *   render    BotTurn / ProposalCard / ContextPanel / Thread render on the server: the answer with its object chips,
 *             the steps folded after the answer, the cautions as sentences, "Open to decide" → /decide/…, "Show on
 *             map"; NO Apply, NO Approve; no raw code or model id anywhere in the HTML
 *   wiring    AssistantPanel and the V3 page both run ChatSession (no copied stream logic: no streamChat call and no
 *             PROSE_FIELDS outside session.svelte.ts); AssistantPanel keeps every chat-* test id; the rail's
 *             Assistant item is /assistant; no V3 assistant module is imported outside /assistant
 *
 * Exits 0 with `ok <name>` lines, 1 on any failure.
 */
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
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

const NAV_STUB = path.join(OUT_DIR, 'v3a-navigation-stub.mjs');
writeFileSync(NAV_STUB, ['globalThis.__goto_calls ??= [];', 'export function goto(h) { globalThis.__goto_calls.push(String(h)); return Promise.resolve(); }', 'export function beforeNavigate() {}', 'export function afterNavigate() {}', 'export function onNavigate() {}', 'export function replaceState() {}'].join('\n'));

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
export * as model from './src/lib/v3/assistant/model';
export * as pack from './src/lib/v3/assistant/packs.asst3';
export { hi } from './src/lib/v3/assistant/packs.asst3.hi';
export { mr } from './src/lib/v3/assistant/packs.asst3.mr';
export * as session from './src/lib/assistant/session.svelte';
export * as conv from './src/lib/assistant/conversation';
export { canvasBus } from './src/lib/gods-eye/canvas-bus.svelte';
export { t } from './src/lib/i18n/strings';
import './src/lib/i18n/packs.assistant';
export { default as BotTurn } from './src/lib/v3/assistant/BotTurn.svelte';
export { default as Thread } from './src/lib/v3/assistant/Thread.svelte';
export { default as ContextPanel } from './src/lib/v3/assistant/ContextPanel.svelte';
export { default as ProposalCard } from './src/lib/v3/assistant/ProposalCard.svelte';
`;
const OUT = path.join(OUT_DIR, 'v3-assistant-bundle.mjs');
let M = null;
try {
	const built = await esbuild.build({
		stdin: { contents: ENTRY, resolveDir: DECK, loader: 'ts', sourcefile: 'v3a-entry.ts' },
		absWorkingDir: DECK,
		alias: { $lib: './src/lib', '$app/navigation': NAV_STUB },
		bundle: true,
		format: 'esm',
		platform: 'node',
		conditions: ['svelte', 'node'],
		outfile: OUT,
		logLevel: 'silent',
		plugins: [sveltePlugin],
	});
	ok('bundle builds (the real model, packs, session and components; svelte/server)', built.errors.length === 0, `${built.errors.length} errors`);
	M = await import(`${pathToFileURL(OUT).href}?t=${Date.now()}`);
} catch (err) {
	ok('bundle builds (the real model, packs, session and components; svelte/server)', false, String(err?.message ?? err).slice(0, 400));
}
if (!M) {
	console.log(`\n${failures} failure(s)`);
	process.exit(1);
}
const { model, pack } = M;
const L = (k, ...a) => M.t('en', k, ...a);
const text = (v) => (typeof v === 'function' ? String(v('‹x›', '‹y›')) : String(v));
const RAW_CODES = [...model.BRAIN_TOOLS, ...Object.keys(model.CAUTION_KEY), 'ungrounded_claims_removed'];

// ─── pack ────────────────────────────────────────────────────────────────────
{
	const en = pack.ASST3_PACKS.en;
	const keys = Object.keys(en);
	const same = (a, b) => a.length === b.length && a.every((k) => b.includes(k));
	ok('pack: EN / HI / MR carry the same keys', same(keys, Object.keys(M.hi)) && same(keys, Object.keys(M.mr)), `${keys.length} keys`);
	ok('pack: every key starts with v3a_', keys.every((k) => k.startsWith('v3a_')));
	const ACR = new Set(['AI', 'ID', 'IST', 'OK']);
	const caps = keys.filter((k) => text(en[k]).split(/[\s,.:;()·/—?’'-]+/).some((w) => w.length > 1 && /^[A-Z]+$/.test(w) && !ACR.has(w)));
	ok('pack: no ALL-CAPS word outside the acronyms (EN)', caps.length === 0, caps.join(','));
	ok('pack: at most one " · " per EN string', keys.filter((k) => text(en[k]).split(' · ').length > 2).length === 0);
	const same3 = keys.filter((k) => text(M.hi[k]) === text(en[k]) || text(M.mr[k]) === text(en[k]));
	ok('pack: HI and MR are translated', same3.length === 0, same3.join(','));
	ok('pack: every caution has its sentence in EN, HI and MR', Object.values(model.CAUTION_KEY).concat(['v3a_caution_degraded', 'v3a_caution_other']).every((k) => en[k] && M.hi[k] && M.mr[k]));
	ok('pack: every brain tool has its words in EN, HI and MR', model.BRAIN_TOOLS.filter((x) => !['get_corridor_summary', 'get_city_band', 'list_active_events', 'plan_corridor'].includes(x)).every((x) => en[`v3a_tool_${x}`] && M.hi[`v3a_tool_${x}`] && M.mr[`v3a_tool_${x}`]));
	ok('pack: §7.6 sentences word for word', text(en.v3a_caution_disagree) === 'Two of my models disagreed on the next step; I used the cautious one. Check before acting.' && text(en.v3a_caution_low_conf) === 'I’m not confident here; treat this as a starting point.' && text(en.v3a_caution_backup) === 'Answered by the backup model.');
	ok('pack: the rule says it cannot approve, dispatch or unmask', /can’t approve, dispatch or show full registration marks/.test(text(en.v3a_rule)) && /cannot approve, unmask or dispatch/.test(text(en.v3a_scope)));
	const all = [en, M.hi, M.mr].flatMap((p) => Object.values(p).map(text)).join('\n');
	ok('pack: no raw code or tool name in any string', !RAW_CODES.some((c) => all.includes(c)));
}

// ─── cautions and words ──────────────────────────────────────────────────────
{
	const done = (alerts, tiers = ['decider:m'], degraded = false) => ({ operatorAlerts: alerts, tiersUsed: tiers, degraded });
	ok('caution: each brain code → its sentence', Object.entries(model.CAUTION_KEY).every(([code, key]) => JSON.stringify(model.cautionsOf(done([`${code}: detail — action`]))) === JSON.stringify([key])));
	ok('caution: an unknown code → the generic sentence, never the code', JSON.stringify(model.cautionsOf(done(['tier_mystery_flag: x']))) === JSON.stringify(['v3a_caution_other']));
	ok('caution: the grounding removal is not a caution (it is the grounding note)', model.cautionsOf(done(['ungrounded_claims_removed: 2 claim(s) no tool reported were removed from the answer'])).length === 0);
	ok('caution: a gemma-only turn → the backup model', JSON.stringify(model.cautionsOf(done([], ['gemma:g']))) === JSON.stringify(['v3a_caution_backup']));
	ok('caution: a disagreement does not also say "backup"', JSON.stringify(model.cautionsOf(done(['decider_gemma_disagreement: x'], ['gemma:g']))) === JSON.stringify(['v3a_caution_disagree']));
	ok('caution: degraded → the reduced mode; duplicates fold', JSON.stringify(model.cautionsOf(done(['low_confidence_decision: a', 'low_confidence_decision: b'], ['decider:m'], true))) === JSON.stringify(['v3a_caution_low_conf', 'v3a_caution_degraded']));
	ok('caution: a rules-only answer has none', model.cautionsOf(done([], ['heuristic'])).length === 0 && model.cautionsOf(null).length === 0);
	const prose = 'I ran list_enforcement_recommendations and city_get_dossier; decider_gemma_disagreement was flagged. The road_name field stays.';
	const scrubbed = model.scrubCodes(prose, L);
	ok('words: scrubCodes leaves no tool name or alert code in the prose', !RAW_CODES.some((c) => scrubbed.includes(c)) && scrubbed.includes('listed the decisions waiting'), scrubbed);
	ok('words: scrubCodes leaves the rest of the prose alone', scrubbed.endsWith('The road_name field stays.'));
	const look = model.humaniseLookups('list_enforcement_recommendations 4 rows; predict_eta refused: route_length_m', L);
	ok('words: humaniseLookups leaves no snake_case identifier', !/[a-z]+_[a-z]+/.test(look), look);
	ok('words: an unknown tool reads in words, never with an underscore', !model.toolLabel('mystery_new_tool', L).includes('_') && model.toolLabel('simulate_twin', L) === 'Ran the plan in the traffic twin');
	ok('words: the twin steps are the simulated ones', model.SIMULATED_TOOLS.has('simulate_twin') && model.SIMULATED_TOOLS.has('evaluate_scenarios') && !model.SIMULATED_TOOLS.has('get_live_traffic'));
	ok('model line: kinds in words, never the model id', model.modelKey(['decider:pplx-decider-v1-27b']) === 'v3a_model_decider' && model.modelKey(['decider:confirmed_by_gemma']) === 'v3a_model_decider_checked' && model.modelKey(['gemma:x']) === 'v3a_model_backup' && model.modelKey(['heuristic']) === 'v3a_model_rules' && model.modelKey([]) === 'v3a_model_none');
	const segs = model.segmentProse('Pursue MH47EM•••1 past EM-CAM-03 and EM-CAM-03 again; ok', [
		{ urn: 'camera:EM-CAM-03', label: 'EM-CAM-03' },
		{ urn: 'vehicle:v', label: 'MH47EM•••1' },
		{ urn: 'x:y', label: 'ok' },
	]);
	const round = segs.map((s) => ('chip' in s ? s.chip.label : s.text)).join('');
	ok('chips: the prose round-trips; every occurrence is a chip; a 2-letter label never is', round === 'Pursue MH47EM•••1 past EM-CAM-03 and EM-CAM-03 again; ok' && segs.filter((s) => 'chip' in s).length === 3 && segs.filter((s) => 'chip' in s && s.chip.urn === 'x:y').length === 0);
	const nested = model.segmentProse('Western Express Highway and Bandra–Worli Sea Link', [
		{ urn: 'a', label: 'Bandra–Worli Sea Link' },
		{ urn: 'b', label: 'Western Express Highway' },
	]);
	ok('chips: the longest label wins where two start together', 'chip' in nested[0] && nested[0].chip.urn === 'b');
	ok('map proposal: the verb is dropped from its words', model.directiveLabel('fly to EM-CAM-03') === 'EM-CAM-03');
}

// ─── the shared session ─────────────────────────────────────────────────────
{
	globalThis.$state = Object.assign((v) => v, { raw: (v) => v, snapshot: (v) => JSON.parse(JSON.stringify(v)) });
	const calls = [];
	let script = null;
	let gate = null;
	const nd = (rows) => rows.map((r) => JSON.stringify(r)).join('\n') + '\n';
	const turn = (sid, extra = []) =>
		nd([
			{ type: 'tool_call', data: { id: 'c1', name: 'list_enforcement_recommendations', args: {} } },
			{ type: 'tool_result', data: { id: 'c1', name: 'list_enforcement_recommendations', ok: true, summary: '4 rows' } },
			{ type: 'token', data: 'Four decisions ' },
			{ type: 'token', data: 'are waiting.' },
			...extra,
			{ type: 'done', data: { session_id: sid, tiers_used: ['decider:m'], operator_alerts: [], degraded: false, citations: [] } },
		]);
	globalThis.fetch = async (url, init = {}) => {
		calls.push({ url: String(url), method: init.method ?? 'GET', body: init.body ? JSON.parse(init.body) : null });
		if (gate) await gate;
		if (script === 'fail') return new Response('upstream down', { status: 502, statusText: 'Bad Gateway' });
		return new Response(script, { status: 200, headers: { 'content-type': 'application/x-ndjson' } });
	};
	const settle = () => new Promise((r) => setTimeout(r, 30));
	const S = M.session;
	const WIRE = { movementId: null, vvipClass: null, eventId: null, contextUrn: null };
	const chat = new S.ChatSession(null);
	script = turn('sess-1', [{ type: 'directive', data: { id: 'd1', verb: 'canvas_fly_to', args: { lon: 72.8355, lat: 18.9398 }, label: 'fly to the old city', provenance: { session_id: 'sess-1', tier: 'decider' } } }]);
	let release;
	gate = new Promise((r) => (release = r));
	const first = chat.send('What needs me?', WIRE, 'What needs me in the next hour?');
	const second = chat.send('Again', WIRE);
	release();
	gate = null;
	await settle();
	ok('session: one POST per send; a second send while streaming sends nothing', first === true && second === false && calls.length === 1 && calls[0].method === 'POST' && calls[0].url.endsWith('/chat/stream'), `${calls.length} call(s)`);
	ok('session: the bubble says the label, the wire carries the question', chat.messages[0].text === 'What needs me in the next hour?' && calls[0].body.message === 'What needs me?' && !('session_id' in calls[0].body));
	const a = chat.messages[1];
	ok('session: tokens accumulate on the turn; steps recorded; done kept', a.text === 'Four decisions are waiting.' && a.toolCalls.length === 1 && a.toolCalls[0].state === 'success' && a.done?.sessionId === 'sess-1' && chat.streaming === false);
	ok('session: a map directive is QUEUED on the canvas bus for a human (never applied here)', a.directives.length === 1 && M.canvasBus.pending.some((d) => d.id === 'd1'));
	script = turn('sess-1');
	chat.send('And now?', WIRE);
	await settle();
	ok('session: the follow-up carries the brain session', calls[1]?.body?.session_id === 'sess-1');
	chat.rescope('event-A');
	chat.rescope('event-B');
	ok('session: a new event scope drops the brain session', chat.sessionId === null);
	script = 'fail';
	chat.send('Fails', WIRE);
	await settle();
	ok('session: a failed stream marks the turn and the session degraded', !!chat.messages.at(-1).error && chat.degraded === true && chat.streaming === false);
	script = turn('sess-9');
	gate = new Promise(() => {}); // never answers: the page leaves mid-turn
	chat.send('Cut off', WIRE);
	chat.release('unit-test', 'Stopped');
	gate = null;
	const kept = M.conv.keptConversation('unit-test');
	ok('session: release keeps the conversation and marks the cut-off turn', kept && kept.messages.length === chat.messages.length && kept.messages.at(-1).error === 'Stopped');
	chat.clear('unit-test');
	ok('session: clear forgets the turns, the session and the kept copy', chat.messages.length === 0 && chat.sessionId === null && M.conv.keptConversation('unit-test') === null);
	ok('answer: an old brain’s JSON envelope gives its prose field; a bare envelope gives none', M.session.answerOf({ text: '{"answer":"Hello"}', done: {}, error: null }).prose === 'Hello' && M.session.answerOf({ text: '{"action":"x"}', done: {}, error: null }).prose === null);
}

// ─── render ──────────────────────────────────────────────────────────────────
{
	const html = (C, props) => M.render(C, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
	const noop = () => {};
	const chipOf = (c) => ({ glyph: c.urn.startsWith('vehicle') ? 'car' : 'anpr', decide: c.urn.startsWith('vehicle') });
	const prose = 'Authorise the pursuit of MH47EM•••1, last read on EM-CAM-03.';
	const turnVM = {
		id: 2,
		role: 'agent',
		text: prose,
		segments: model.segmentProse(prose, [
			{ urn: 'vehicle:v1', label: 'MH47EM•••1' },
			{ urn: 'camera:EM-CAM-03', label: 'EM-CAM-03' },
		]),
		at: '19:42',
		working: false,
		steps: [{ label: model.toolLabel('list_enforcement_recommendations', L), state: 'success', simulated: false, summary: '4 rows' }, { label: model.toolLabel('simulate_twin', L), state: 'success', simulated: true, summary: null }],
		lookups: model.humaniseLookups('list_enforcement_recommendations 4 rows', L),
		stepsSummary: L('v3a_steps', 3),
		noProse: false,
		error: null,
		grounding: L('asst_grounding_removed', 1),
		cautions: model.cautionsOf({ operatorAlerts: ['decider_gemma_disagreement: decider hold vs Gemma release — acted'], tiersUsed: ['decider:pplx-decider-v1-27b'], degraded: false }).map((k) => ({ key: k, text: L(k) })),
		proposals: [
			{ key: 'stolen-sighting:v1', kind: 'decision', thumb: null, tag: L('v3a_waiting'), ai: false, timer: null, title: 'Authorise pursuit', why: 'Reported stolen.', openHref: '/decide/stolen-sighting%3Av1', urn: 'vehicle:v1' },
			{ key: 'dir:d1', kind: 'map', thumb: null, tag: L('v3a_map_proposal'), ai: true, timer: null, title: 'EM-CAM-03', why: L('v3a_map_proposal_body'), openHref: null, urn: null },
		],
	};
	const bot = html(M.BotTurn, { turn: turnVM, L, chipOf, onopen: noop, onshowmap: noop });
	ok('render: the answer with its objects as chips (the one waiting on a decision orange-bordered)', (bot.match(/data-testid="v3-obj-chip"/g) ?? []).length === 2 && /data-decide="true"/.test(bot));
	ok('render: the steps fold once answered (closed <details>), the twin step says "simulated"', /<details[^>]*data-testid="v3-steps-fold"(?![^>]*\bopen)/.test(bot) && /simulated/.test(bot));
	ok('render: the caution is a sentence and the grounding note is kept', /Two of my models disagreed/.test(bot) && /1 statement removed: not in the lookups/.test(bot));
	ok('render: "Open to decide" → its home in Decide; "Show on map"; the rule under the cards', /data-testid="v3-proposal-open"[^>]*href="\/decide\/stolen-sighting%3Av1"|href="\/decide\/stolen-sighting%3Av1"[^>]*data-testid="v3-proposal-open"/.test(bot) && (bot.match(/data-testid="v3-proposal-map"/g) ?? []).length === 2 && /can’t approve, dispatch or show full registration marks/.test(bot));
	ok('render: NO Apply and NO Approve anywhere in a turn', !/>\s*(Apply|Approve)\b/i.test(bot.replace(/<[^>]+>/g, (m) => (m.startsWith('<button') || m.startsWith('<a') ? '>' : ''))));
	const plain = bot.replace(/<[^>]+>/g, ' ');
	ok('render: no raw tool name, alert code or model id in the turn', !RAW_CODES.some((c) => plain.includes(c)) && !/pplx-|decider:|gemma:/i.test(plain));
	const working = html(M.BotTurn, { turn: { ...turnVM, working: true, segments: [], steps: [{ label: 'Read live traffic', state: 'running', simulated: false, summary: null }], proposals: [], cautions: [], grounding: null }, L, chipOf, onopen: noop, onshowmap: noop });
	ok('render: while working the steps show open with a spinner', /data-testid="v3-steps"[^>]*data-open="true"/.test(working) && /class="spin/.test(working) && /Reading the city/.test(working));
	const ctx = html(M.ContextPanel, { items: [{ urn: 'vehicle:v1', label: 'MH47EM•••1', meta: 'Vehicle · a decision waits', art: '/illustrations/vehicles/car.svg', decide: true }], modelLine: L('v3a_model_decider'), lastAnswer: L('v3a_last_answer', '2.3'), L, onopen: noop });
	ok('render: the context lists the named objects (decision dot) and the model in words', /data-testid="v3-context-item"[^>]*data-decide="true"/.test(ctx) && /Decision model · Last answer took 2.3 s/.test(ctx) && !/pplx|gemma/i.test(ctx));
	const empty = html(M.Thread, { turns: [], L, chipOf, onopen: noop, onshowmap: noop });
	ok('render: the empty thread says what it reads and that it cannot approve', /Ask about the city/.test(empty) && /cannot approve anything/.test(empty) && /alt=""/.test(empty));
}

// ─── wiring (source) ─────────────────────────────────────────────────────────
{
	const read = (p) => readFileSync(path.join(SRC, p), 'utf8');
	const panel = read('lib/assistant/AssistantPanel.svelte');
	const page = read('lib/v3/assistant/AssistantPage.svelte');
	ok('shared: AssistantPanel and the V3 page both run ChatSession', /new ChatSession\(/.test(panel) && /new ChatSession\(/.test(page));
	const walk = (d) => readdirSync(d).flatMap((f) => (statSync(path.join(d, f)).isDirectory() ? walk(path.join(d, f)) : [path.join(d, f)]));
	const files = walk(path.join(SRC, 'lib')).filter((f) => /\.(svelte|ts)$/.test(f));
	const streamers = files.filter((f) => (f.includes(`${path.sep}lib${path.sep}assistant${path.sep}`) || f.includes(`${path.sep}v3${path.sep}assistant${path.sep}`)) && /\bstreamChat\(/.test(readFileSync(f, 'utf8')));
	ok('shared: one stream implementation for the assistant surfaces (streamChat only in session.svelte.ts)', streamers.length === 1 && streamers[0].endsWith(path.join('assistant', 'session.svelte.ts')), streamers.map((f) => path.relative(DECK, f)).join(','));
	ok('shared: no copied prose-field logic', files.filter((f) => /PROSE_FIELDS\s*=/.test(readFileSync(f, 'utf8'))).length === 1);
	const ids = ['chat-stream', 'chat-input', 'chat-answer', 'chat-tiers', 'chat-session', 'chat-tool-card', 'chat-lookups', 'chat-grounding-removed', 'chat-context', 'chat-suggestions', 'chat-degraded', 'chat-no-prose', 'chat-context-event'];
	ok('panel: every chat-* test id stays', ids.every((id) => panel.includes(`data-testid="${id}"`)), ids.filter((id) => !panel.includes(`data-testid="${id}"`)).join(','));
	ok('rail: Assistant is /assistant', /id: 'assistant', href: '\/assistant'/.test(read('lib/v3/shell/nav.ts')));
	ok('/assistant mounts the V3 page', /AssistantPage/.test(read('routes/(v3)/assistant/+page.svelte')));
	const importers = walk(SRC)
		.filter((f) => /\.(svelte|ts)$/.test(f) && !f.includes(`${path.sep}lib${path.sep}v3${path.sep}assistant${path.sep}`) && !f.includes(`(v3)${path.sep}assistant`))
		.filter((f) => /v3\/assistant\//.test(readFileSync(f, 'utf8')));
	ok('budget: no V3 assistant module is imported outside /assistant', importers.length === 0, importers.map((f) => path.relative(DECK, f)).join(','));
	ok('page: proposals never Apply/Approve (no such verb in the V3 assistant sources)', !walk(path.join(SRC, 'lib/v3/assistant')).some((f) => />\s*\{?L\('v3a_(apply|approve)/.test(readFileSync(f, 'utf8'))) && !/v3a_(apply|approve)\b/.test(read('lib/v3/assistant/packs.asst3.ts')));
}

console.log(failures ? `\nv3-assistant.unit: ${failures} failure(s)` : '\nv3-assistant.unit: ALL OK');
process.exit(failures ? 1 : 0);
