/**
 * The AI surfaces' rules (src/lib/ai) — zero browser, no network (fetch stubbed). Bundles labels, model, view,
 * poll, writer and the three packs with the vendored esbuild and holds them on REAL service outputs
 * (tests/fixtures/ai/*.json: the forecast, hydro and twin services' answers on the GB10, 28 Oct 2026, trimmed;
 * the replay's proposals are the hydro patch's .orchestration/patches/int-ops-hydro-replay-proposals.patch shape;
 * one word of the replay fixture normalised for the deck's own wording rule):
 *
 *   labels     every service label → its kind (LIVE, MODELLED (approximate), EMULATED, SIMULATED, OBSERVED,
 *              HINDSIGHT, ARCHIVE, RAIN-UNAVAILABLE); an unknown label is never guessed; the weakest wins
 *   forecast   p50 and the band at +30 / +60 / +120; a lead past the horizon is null; the threshold words
 *   hydro      risk counts; the tide state (next high water, gates); rain never shown as 0 without a feed
 *   cards      forecast / hydro / twin proposals → one decision card each (labels kept, decided ones left out, a
 *              road's waterlogging cards together, an exercise flagged), the queue's words, what changes (the record
 *              and the separate next step — never an action; the twin's timing "emulated: no controller changes")
 *   replay     the timeline (first flag 02:45, the gates, IMD's peak hour, the rising limb), classes at a moment
 *   writer     the decision body the oracle accepts (no unknown key), officer-required and reason-required before
 *              any request, the platform record, "kept on this console" when the log is not deployed (404/503),
 *              already-decided, an exercise never sent
 *   poll       back-off doubles to its cap
 *   packs      EN / HI / MR complete and equal in keys; no word the product must never say
 *
 * Run from services/command-deck:  node tests/ai-ops.unit.mjs
 */
import { mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DECK = path.resolve(HERE, '..');
const ARTIFACTS = path.join(HERE, 'artifacts');
mkdirSync(ARTIFACTS, { recursive: true });
const esbuild = await import(pathToFileURL(path.join(DECK, 'node_modules/esbuild/lib/main.js')).href);

const entry = [
	`export * as LB from ${JSON.stringify(path.join(DECK, 'src/lib/ai/labels.ts'))};`,
	`export * as MD from ${JSON.stringify(path.join(DECK, 'src/lib/ai/model.ts'))};`,
	`export * as VW from ${JSON.stringify(path.join(DECK, 'src/lib/ai/view.ts'))};`,
	`export * as PL from ${JSON.stringify(path.join(DECK, 'src/lib/ai/poll.ts'))};`,
	`export * as WR from ${JSON.stringify(path.join(DECK, 'src/lib/ai/writer.ts'))};`,
	`export * as CL from ${JSON.stringify(path.join(DECK, 'src/lib/ai/client.ts'))};`,
	`export { hi } from ${JSON.stringify(path.join(DECK, 'src/lib/ai/packs.ai.hi.ts'))};`,
	`export { mr } from ${JSON.stringify(path.join(DECK, 'src/lib/ai/packs.ai.mr.ts'))};`,
	`export * as STR from ${JSON.stringify(path.join(DECK, 'src/lib/i18n/strings.ts'))};`,
	`export * as PK from ${JSON.stringify(path.join(DECK, 'src/lib/ai/packs.ai.ts'))};`,
].join('\n');
const outfile = path.join(ARTIFACTS, 'ai-ops-unit-bundle.mjs');
await esbuild.build({
	stdin: { contents: entry, resolveDir: DECK, loader: 'ts', sourcefile: 'ai-ops-unit.entry.ts' },
	absWorkingDir: DECK,
	alias: { $lib: './src/lib' },
	bundle: true,
	platform: 'node',
	format: 'esm',
	outfile,
	logLevel: 'error',
	define: { 'import.meta.env.SSR': 'true' },
});
const M = await import(`${pathToFileURL(outfile).href}?t=${Date.now()}`);

let failures = 0;
function ok(name, cond, detail = '') {
	if (cond) console.log(`ok   ${name}${detail ? ` — ${detail}` : ''}`);
	else {
		failures++;
		console.error(`FAIL ${name}${detail ? ` — ${detail}` : ''}`);
	}
}
const fx = (n) => JSON.parse(readFileSync(path.join(HERE, 'fixtures', 'ai', `${n}.json`), 'utf8'));
const FC = fx('forecast');
const NC = fx('nowcast');
const TW = fx('twin');
const RP = fx('replay');
const TD = fx('tide');
const RN = fx('rain');
const L = (k, ...a) => M.STR.t('en', k, ...a);
const LB = (k, ...a) => M.STR.t('mr', k, ...a);

// ── labels ───────────────────────────────────────────────────────────────
{
	const { provOf, provList, weakest } = M.LB;
	ok(
		'labels: every service spelling → its kind',
		provOf('LIVE') === 'live' && provOf('MODELLED (approximate)') === 'modelled' && provOf('EMULATED (KMC FFEWS adapter stand-in)') === 'emulated' && provOf('SIMULATED') === 'simulated' && provOf('OBSERVED totals (IMD Alipore 3-hourly)') === 'observed' && provOf('HINDSIGHT — the observed rain …') === 'hindsight' && provOf('ARCHIVE (Open-Meteo historical archive)') === 'archive' && provOf('RAIN-UNAVAILABLE') === 'unavailable',
	);
	ok('labels: an unknown or empty label is never guessed', provOf('PROBABLY') === null && provOf('') === null && provOf(null) === null);
	ok('labels: a list keeps one of each, weakest last; the weakest wins a combined figure', JSON.stringify(provList(['MODELLED', 'SIMULATED', 'LIVE', 'MODELLED', 'nonsense'])) === JSON.stringify(['live', 'modelled', 'simulated']) && weakest(['LIVE', 'EMULATED']) === 'emulated' && weakest([]) === null);
}

// ── forecast ─────────────────────────────────────────────────────────────
{
	const seg = FC.segments[0];
	const pts = M.MD.forecastPoints(seg);
	ok('forecast: +30 / +60 / +120 min come from the service steps (p50 inside its band)', pts.length === 3 && pts.every((p) => p && p.vc.p10 <= p.vc.p50 && p.vc.p50 <= p.vc.p90) && pts.map((p) => p.lead).join() === '30,60,120', JSON.stringify(pts.map((p) => p?.vc.p50)));
	const short = { steps: seg.steps.filter((s) => s.lead_min <= 60) };
	ok('forecast: a lead past the horizon is null, never extrapolated', M.MD.forecastPoints(short)[2] === null && M.MD.forecastPoints(null).every((p) => p === null));
	ok('forecast: threshold words', M.MD.crossingWord({ p10: 0.81, p50: 0.9, p90: 1 }) === 'over' && M.MD.crossingWord({ p10: 0.7, p50: 0.82, p90: 0.9 }) === 'likely' && M.MD.crossingWord({ p10: 0.6, p50: 0.7, p90: 0.85 }) === 'possible' && M.MD.crossingWord({ p10: 0.4, p50: 0.5, p90: 0.6 }) === 'under');
}

// ── hydro: risk, tide, rain ──────────────────────────────────────────────
{
	const rc = M.MD.riskCounts(NC);
	ok('hydro: risk counts from the nowcast (a dry evening: nothing at risk)', rc && rc.roads === NC.segments.length && rc.deep + rc.impassable + rc.shallow === NC.segments.filter((s) => s.risk_class >= 1).length);
	ok('hydro: no nowcast → no counts (never a zero)', M.MD.riskCounts(null) === null);
	const now = Date.parse(TD.now.t);
	const ts = M.MD.tideState(TD, now);
	ok('hydro: the tide state — level, direction, gates, the next high water after now', ts && ts.level === TD.now.level_m && ts.gateClosed === TD.now.gate_closed && ts.nextHigh && ts.nextHigh.at > now && ts.closeLevel === 5, JSON.stringify(ts));
	ok('hydro: the next gate closure is a modelled quarter-hour after now (or none while shut)', ts.gateClosed ? ts.nextClose === null : ts.nextClose === null || ts.nextClose > now);
	const r = M.MD.rainNow(RN, Date.parse(RN.fetched_at));
	ok('hydro: rain now from the city-mean series; no feed → null, never 0', typeof r === 'number' && M.MD.rainNow({ city: { series: [] } }, Date.now()) === null && M.MD.rainNow(null, Date.now()) === null);
}

// ── the decision cards ───────────────────────────────────────────────────
const exercise = M.MD.replayProposals(RP);
{
	const fcCards = FC.proposals.map((p) => M.MD.cardFromProposal(p, 'forecast'));
	const c = fcCards[0];
	ok('cards: a forecast proposal keeps its numbers and its labels (Simulated, Modelled)', c && c.source === 'forecast' && c.fc.band.p50 === FC.proposals[0].situation.vc_p50 && c.fc.inMin === FC.proposals[0].situation.in_min && c.labels.includes('SIMULATED') && c.labels.includes('MODELLED'), JSON.stringify(c?.fc));
	const tw = M.MD.cardFromTwin(TW);
	ok('cards: a twin proposal → a card with the before / after and Modelled + the demand label', !TW.proposal || (tw && tw.source === 'twin' && tw.tw.before && tw.tw.after && tw.labels.includes('MODELLED') && typeof tw.tw.delayPct === 'number'), tw ? `${tw.place} ${tw.tw.delayPct}%` : 'hold');
	ok('cards: a twin hold (nothing passed the guards) is no card', M.MD.cardFromTwin({ proposal: null }) === null && M.MD.cardFromTwin({ proposal: { ...TW.proposal, status: 'HOLD' } }) === null);
	ok('cards: a decided, superseded or non-proposed proposal is no card', M.MD.cardFromProposal({ ...FC.proposals[0], state: 'approved' }, 'forecast') === null);
	ok('cards: the replay carries the hydro exercise (reroute, ambulance window, live wire, advisory)', exercise.length >= 4 && ['waterlogging_reroute', 'ambulance_window', 'live_wire_hazard', 'public_advisory_draft'].every((k) => exercise.some((p) => p.kind === k)), String(exercise.length));
	const all = M.MD.aiCards({ forecast: FC, nowcast: NC, exercise, twins: [TW], decided: new Set([FC.proposals[1].proposal_id]) });
	ok('cards: decided proposals are left out; each id once', !all.some((x) => x.id === FC.proposals[1].proposal_id) && new Set(all.map((x) => x.id)).size === all.length);
	ok('cards: the exercise is flagged (decisions stay on this console)', all.filter((x) => x.source === 'hydro').every((x) => x.exercise));
	const hyd = all.filter((x) => x.source === 'hydro' && x.segmentId != null);
	const firstRoad = hyd[0]?.segmentId;
	const runs = hyd.map((x) => x.segmentId).filter((v, i, a) => i === 0 || a[i - 1] !== v);
	ok('cards: one road’s waterlogging cards travel together, most severe road first', new Set(runs).size === runs.length && hyd[0].severity === 3 && hyd.filter((x) => x.segmentId === firstRoad).length === 3, runs.join(','));
	const wire = hyd.find((x) => x.kind === 'live_wire_hazard');
	ok('cards: the live-wire request takes its road’s deep-water time', wire && wire.hy.deepMin != null && M.VW.cardWhen(wire, L) === L('ai_w_deep_in', wire.hy.deepMin));
	ok('cards: impassable roads before forecast crossings before signal timing', all.findIndex((x) => x.source === 'hydro') < all.findIndex((x) => x.source === 'forecast'));
	const asks = M.MD.twinAsks(FC, 2);
	ok('cards: the twin is asked about the soonest crossings at distinct junctions', asks.length === 2 && asks[0].inMin <= asks[1].inMin && asks[0].junction !== asks[1].junction, JSON.stringify(asks));

	// words
	const reroute = hyd.find((x) => x.kind === 'waterlogging_reroute');
	ok('view: titles and kind lines in the reader’s language (Marathi place names when the service has them)', M.VW.cardTitle(reroute, 'en', L) === L('ai_t_waterlogging_reroute', reroute.place) && M.VW.cardKindKey(tw ?? reroute) === (tw ? 'ai_k_signal' : 'ai_k_waterlogging_reroute'));
	const what = M.VW.cardWhat(c, 'mr', LB);
	ok('view: the evidence is worded from the numbers in Marathi, never the service’s English', what.length >= 1 && /[ऀ-ॿ]/.test(what[0]) && what[0].includes(c.fc.band.p50.toFixed(2)), what[0]);
	const rows = M.VW.cardChanges(c, 'console', L);
	ok('view: what changes — the record (kept on this console while the log is not deployed), then a separate step that writes nothing', rows[0].after === L('ai_c_after_console') && rows[0].writes.length === 1 && rows.slice(1).every((r) => Array.isArray(r.writes) && r.writes.length === 0));
	if (tw) {
		const trows = M.VW.cardChanges(tw, 'platform', L);
		ok('view: an approved signal timing is recorded — the adapter is emulated, no controller changes', trows[0].after === L('ai_c_after_platform') && trows[1].after === L('ai_c_signal_after') && /emulated/.test(trows[1].after));
	}
	const adv = all.find((x) => x.kind === 'public_advisory_draft');
	ok('view: the advisory carries both drafts (Marathi with ।)', adv && /।/.test(adv.hy.textMr ?? '') && /advisory/i.test(adv.hy.textEn ?? '') && M.VW.cardChanges(adv, 'exercise', L)[0].after === L('ai_c_after_exercise'));
	const lines = new Map([[reroute.segmentId, [[88.36, 22.52], [88.37, 22.521]]]]);
	const area = new Map(adv.areaSegmentIds.map((id, i) => [id, [[88.3 + i / 100, 22.5], [88.31 + i / 100, 22.51]]]));
	const ovAdv = M.VW.cardOverlay(adv, area, new Map(), '');
	ok('view: the advisory’s map draws every road it names in the water style', adv.areaSegmentIds.length >= 2 && ovAdv.lines.length === adv.areaSegmentIds.length && ovAdv.lines.every((l) => l.style === 'flood') && ovAdv.points[0].glyph === 'megaphone', String(adv.areaSegmentIds.length));
	const ov = M.VW.cardOverlay(reroute, lines, new Map(), 'Gariahat');
	const ovDone = M.VW.cardOverlay(reroute, lines, new Map(), 'Gariahat', true);
	ok('view: the decision map — the road in the water style, a decision dot only while it waits', ov.lines.some((l) => l.style === 'flood') && ov.points[0].decide === true && ovDone.points[0].decide === false);
}

// ── the replay ───────────────────────────────────────────────────────────
{
	const tl = M.MD.replayTimeline(RP);
	ok('replay: the first flag is 02:45 IST (before IMD’s 03:00–04:00 peak hour)', tl && new Date(tl.firstFlag).toISOString() === '2025-09-22T21:15:00.000Z' && tl.peakHour && tl.firstFlag < tl.peakHour.from, tl && new Date(tl.firstFlag).toISOString());
	ok('replay: the modelled gate closure 00:15–04:30 IST is on the timeline', tl.gates.length >= 1 && new Date(tl.gates[0].from).toISOString() === '2025-09-22T18:45:00.000Z');
	const mono = tl.ticks.every((t, i) => i === 0 || t.deep + t.impassable >= tl.ticks[i - 1].deep + tl.ticks[i - 1].impassable);
	ok('replay: the rising limb only — roads under water never fall before the modelled peak (the scrubber stops there)', mono && tl.ticks[tl.ticks.length - 1].at <= tl.peak && tl.peak <= tl.end);
	ok('replay: 13 of 13 reported places on the network flagged, off-network ones listed, not scored', tl.hit.flagged === 13 && tl.hit.onNetwork === 13 && tl.offNetwork.length >= 1 && tl.reported.every((r) => r.flagged));
	ok('replay: the archive run’s rain is kept (the case for a gauge feed)', typeof tl.totals.archiveMm === 'number' && tl.totals.archiveMm < 50 && tl.totals.mm > 200);
	const s = { first_class1_ist: '2025-09-23 02:00', first_class2_ist: '2025-09-23 02:45', first_class3_ist: '2025-09-23 04:15' };
	const at = (hm) => Date.parse(`2025-09-23T${hm}:00+05:30`);
	ok('replay: a road’s class at a moment', M.MD.replayClassAt(s, at('01:45')) === 0 && M.MD.replayClassAt(s, at('02:00')) === 1 && M.MD.replayClassAt(s, at('03:00')) === 2 && M.MD.replayClassAt(s, at('05:00')) === 3);
	ok('replay: no replay → no timeline', M.MD.replayTimeline(null) === null && M.MD.replayProposals(null).length === 0);
	const nh = M.MD.nextHours({ forecast: FC, nowcast: NC, tide: TD, twinWaiting: 1, now: Date.parse(TD.now.t) });
	ok('home: the next two hours — top 3 crossings soonest first, risk, tide, twin waiting', nh.crossings.length === 3 && nh.crossings[0].inMin <= nh.crossings[1].inMin && nh.crossingCount === FC.proposals.length && nh.risk && nh.tide && nh.twinWaiting === 1 && nh.forecastLabels.includes('SIMULATED'));
	ok('home: no forecast yet → no count (never a zero)', M.MD.nextHours({ now: 0 }).crossingCount === null && M.MD.nextHours({ now: 0 }).risk === null);
}

// ── the writer ───────────────────────────────────────────────────────────
{
	const card = M.MD.cardFromProposal(FC.proposals[0], 'forecast');
	const body = M.WR.decisionBody(card, { decision: 'approve', officer: 'S. Haldar' });
	const allowedTop = ['proposal', 'decision', 'note', 'officer'];
	const allowedProp = ['proposal_id', 'source', 'kind', 'subject_urn', 'summary', 'labels', 'state', 'evidence'];
	ok('writer: the body the oracle accepts — no unknown key, state proposed, the proposal mapped (never forwarded raw)', Object.keys(body).every((k) => allowedTop.includes(k)) && Object.keys(body.proposal).every((k) => allowedProp.includes(k)) && body.proposal.state === 'proposed' && /^[A-Za-z0-9._:-]{1,160}$/.test(body.proposal.proposal_id) && /^[a-z0-9_]{1,60}$/.test(body.proposal.kind) && body.proposal.labels.length <= 8);
	ok('writer: no person key in the evidence', !/"(author|person|owner|name_of)"/i.test(JSON.stringify(body.proposal.evidence)));
	const calls = [];
	const fake = (status, doc) => async (url, init) => {
		calls.push({ url, body: JSON.parse(init.body) });
		return { ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(doc) };
	};
	let r = await M.WR.decideAiCard(card, { decision: 'approve', officer: ' ' }, fake(200, {}));
	ok('writer: no named officer → refused before any request', !r.ok && r.refusal === 'officer-required' && calls.length === 0);
	r = await M.WR.decideAiCard(card, { decision: 'reject', officer: 'S. Haldar', note: '  ' }, fake(200, {}));
	ok('writer: a reject without a reason → refused before any request', !r.ok && r.refusal === 'reason-required' && calls.length === 0);
	r = await M.WR.decideAiCard(card, { decision: 'approve', officer: 'S. Haldar' }, fake(200, { log_id: 7, proposal_id: card.id, source: 'forecast', kind: card.kind, decision: 'approve', officer: 'S. Haldar', decided_at: '2026-10-28T13:00:00Z', actuated: false, outcome: 'recorded' }));
	ok('writer: approve → POST /api/v1/ai-proposals/decision, recorded in the platform log', r.ok && r.row.recorded === 'platform' && r.row.log_id === 7 && calls[0].url === '/api/v1/ai-proposals/decision' && calls[0].body.decision === 'approve');
	r = await M.WR.decideAiCard(card, { decision: 'approve', officer: 'S. Haldar' }, fake(404, { detail: 'Not Found' }));
	ok('writer: the log not deployed (404) → kept on this console, and it says so', r.ok && r.row.recorded === 'console' && r.row.log_id === null);
	r = await M.WR.decideAiCard(card, { decision: 'approve', officer: 'S. Haldar' }, fake(503, { detail: 'ai proposal decision log not migrated (026)' }));
	ok('writer: the log not migrated (503) → kept on this console', r.ok && r.row.recorded === 'console');
	r = await M.WR.decideAiCard(card, { decision: 'approve', officer: 'S. Haldar' }, fake(409, { detail: 'already-decided', reason: 'decided', decision: 'reject', officer: 'R. Sen', decided_at: '2026-10-28T12:00:00Z' }));
	ok('writer: already decided elsewhere → refused with the earlier officer, never retried', !r.ok && r.refusal === 'already-decided' && r.row.officer === 'R. Sen' && r.row.decision === 'reject');
	r = await M.WR.decideAiCard(card, { decision: 'approve', officer: 'S. Haldar' }, fake(500, { detail: 'boom' }));
	ok('writer: a failure says so (nothing recorded)', !r.ok && r.refusal === 'failed' && /500/.test(r.detail));
	const before = calls.length;
	const ex = M.MD.cardFromProposal(exercise[0], 'hydro', { exercise: true });
	r = await M.WR.decideAiCard(ex, { decision: 'approve', officer: 'S. Haldar' }, fake(200, {}));
	ok('writer: an exercise decision never leaves the console', r.ok && r.row.recorded === 'console' && calls.length === before);
}

// ── poll ─────────────────────────────────────────────────────────────────
ok('poll: back-off doubles from the base to its cap', M.PL.backoffMs(1000, 0) === 1000 && M.PL.backoffMs(1000, 1) === 2000 && M.PL.backoffMs(1000, 3) === 8000 && M.PL.backoffMs(120_000, 5, 300_000) === 300_000);
ok('client: fixed same-origin prefixes only', Object.values(M.CL.AI_PATHS).every((p) => p.startsWith('/api/')));

// ── packs ────────────────────────────────────────────────────────────────
{
	const en = Object.keys(M.PK.AI_PACKS.en);
	const missing = (pack) => en.filter((k) => !(k in pack));
	ok('packs: HI and MR complete for every EN key, no extra key', missing(M.hi).length === 0 && missing(M.mr).length === 0 && Object.keys(M.hi).length === en.length && Object.keys(M.mr).length === en.length, `${missing(M.hi).join(',')} | ${missing(M.mr).join(',')}`);
	ok('packs: every key starts with ai_', en.every((k) => k.startsWith('ai_')));
	const words = new RegExp(['ub' + 'er', 'netf' + 'lix', '\\bve' + 'er\\b', 'hack' + 'athon', 'compet' + 'ition', 'ju' + 'dg'].join('|'), 'i');
	const text = [M.PK.AI_PACKS.en, M.hi, M.mr].flatMap((p) => Object.values(p).map((v) => (typeof v === 'function' ? v(1, 2, 3, 4, 5, 6) : v))).join('\n');
	ok('packs: no word the product must never say', !words.test(text));
	const bnSentences = Object.entries(M.mr).filter(([k, v]) => typeof v === 'string' && /[।.]$/.test(M.PK.AI_PACKS.en[k] ?? '') && /\.$/.test(M.PK.AI_PACKS.en[k]));
	ok('packs: a Marathi sentence ends with a full stop (Marathi does not use the danda)', bnSentences.every(([, v]) => /\.$/.test(v) && !/।/.test(v)), bnSentences.filter(([, v]) => !/\.$/.test(v) || /।/.test(v)).map(([k]) => k).join(','));
}

if (failures) {
	console.error(`\nFAIL ai-ops.unit — ${failures} assertion(s) failed`);
	process.exit(1);
}
console.log('\nai-ops.unit: ALL OK');
