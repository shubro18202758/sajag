/**
 * The decision-support string pack (EN / HI / MR) — the `dss` decision unit,
 * its ProposalCard body (COA review), the inspector section, the promote
 * action and the client refusals (OS-DECK-B; plan X22, contracts C-U/C-T).
 * Registered additively through registerPack(); the core packs stay
 * untouched. Every key starts with `dss_`.
 *
 * The rule note is pinned VERBATIM by tests/dss.unit.mjs (plan X22):
 * "The engine proposes; a named officer decides. Approving creates dispatch
 * requests (each decided on its own) and, when the response needs a corridor
 * event, promotes this report to one."
 *
 * `dec_done_reject_pursuit` / `dec_done_defer_pursuit` live here (additively;
 * the decisions pack does not define them): the ProposalCard's outcome verb
 * for every non-escort, non-corridor, non-e-challan kind reads the
 * `…_pursuit` suffix, and a rejected or deferred proposal must not render a
 * raw key.
 *
 * EN is sentence case, at most one " · " per string, no ALL-CAPS word
 * outside the acronym allowlist (DSS, COA, ICCC, AHP pass; tests/copy-lint.mjs
 * over tests/style-lint.targets/dss.json). HI and MR are complete for every
 * key. Copy describes only what the system does: approving creates dispatch
 * requests (each decided on its own) and, when the response needs a corridor
 * event, promotes the report to one; nothing applies itself.
 */
import { registerPack } from './strings';
import { langChunks } from './load';

type Fn = (...args: unknown[]) => string;
type Pack = Record<string, string | Fn>;

const s = (v: unknown) => String(v ?? '');
const n = (v: unknown) => Number(v);

const en = {
	// ── the unit ───────────────────────────────────────────────────────────
	dss_title: (label: unknown) => `Approve a response to ${s(label)}`,
	dss_by_engine: 'Proposed by the decision-support engine',
	dss_credibility: (c: unknown) => `credibility ${s(c)}`,
	dss_meta_top: (label: unknown) => `top ${s(label)}`,
	dss_meta_report: 'open-source report',
	dss_state_proposed: 'proposed',
	dss_now_none: 'none',
	dss_now_report: 'an open-source report',
	dss_row_decision: 'Decision support',
	dss_row_report: 'OSINT report',
	dss_row_dispatch: (agency: unknown, count: unknown) => `Dispatch request · ${s(agency)} × ${n(count)}`,
	dss_after_approved: (coa: unknown) => `approved (${s(coa)}, you, now)`,
	dss_after_promoted: (kind: unknown) => `promoted to a corridor event (${s(kind)}, verification state kept)`,
	dss_after_requested: 'created as requested; decided separately as a corridor request',
	dss_after_rejected: 'rejected',
	dss_after_rejected_note: (reason: unknown) => `rejected (${s(reason)})`,
	dss_after_deferred: 'deferred',
	dss_after_deferred_note: (reason: unknown) => `deferred (${s(reason)})`,
	dss_unchanged_coas: 'the other courses of action',
	dss_unchanged_units: "every unit's status until its own decision",
	dss_unchanged_subject: 'the report and its sources',
	dss_verb_advisory: 'Advisory (draft)',
	dss_verb_signal_hold: 'Signal hold',
	dss_verb_closure: 'Closure',
	dss_verb_diversion: 'Diversion',
	dss_verb_escort_switch: 'Escort switch',
	dss_verb_request_cctv: 'Situation check at the junction (ICCC)',
	dss_next_advisory: 'Advisories (draft only)',
	dss_next_signal: 'City signal plans (writer off by default)',
	dss_next_corridor: 'Corridor operations',
	dss_next_movement: 'the Movement tab',
	dss_next_iccc: 'ICCC outside Sajag (situation check at the junction, no identification)',
	dss_agency_ambulance: 'Ambulance (108)',
	dss_agency_police: 'Police',
	dss_agency_traffic: 'Traffic police',
	dss_agency_jan_rakshak: 'Civic Volunteers',
	dss_agency_fire: 'Fire and emergency',

	// ── the COA review (the card body) ─────────────────────────────────────
	dss_coa_list: 'Courses of action',
	dss_coa_rank: (rank: unknown) => `rank ${s(rank)}`,
	dss_coa_closeness: (c: unknown) => `closeness ${s(c)}`,
	dss_coa_time_to_scene: (sec: unknown) => `time to scene ${s(sec)} s`,
	dss_coa_disruption: (mean: unknown, p90: unknown) => `disruption ${s(mean)} veh·h (p90 ${s(p90)})`,
	dss_coa_spillover: (mean: unknown) => `spillover ${s(mean)} veh·h`,
	dss_coa_ambulance: (sec: unknown) => (n(sec) > 0 ? `ambulance +${s(sec)} s` : n(sec) < 0 ? `ambulance ${s(sec)} s` : ''),
	dss_coa_officer_gesture: 'needs you',
	dss_feasible: 'Feasible',
	dss_infeasible: (shortfalls: unknown) => `Resource-infeasible: ${s(shortfalls)}`,
	dss_infeasible_unstated: 'Resource-infeasible this cycle',
	dss_vetoed: (reason: unknown) => `Vetoed: ${s(reason)}`,
	dss_veto_persons: 'Vetoed: it would touch or identify people — Sajag acts on vehicles and roads, never persons',
	dss_best_blocked: (label: unknown, missing: unknown, unblock: unknown) => `Best response blocked: ${s(label)} — ${s(missing)} · ${s(unblock)}`,
	dss_unblock_default: 'request the units, then regenerate',
	dss_unblock_request_units: 'request the missing units in Dispatch, then regenerate',
	dss_best_blocked_open_dispatch: 'Open Dispatch to request the units',
	dss_best_blocked_needs_event: 'Units can be requested in Dispatch once this report becomes a corridor event.',
	dss_floor_hold:
		'Public-safety floor: people are reported hurt or public safety is at stake, and the report is credible enough to act on — so doing nothing ranks below every feasible response, even one that scores lower.',
	dss_floor_verify: 'Public-safety floor: the stake is public safety but the report is below the act-on-it threshold — verify first.',
	dss_ai_pick: (kind: unknown) => `Sajag AI's pick: ${s(kind)}`,
	dss_ai_pick_c: (kind: unknown, c: unknown) => `Sajag AI's pick: ${s(kind)} · confidence ${s(c)}`,
	dss_pick_mismatch: (picked: unknown) => `The engine's ranked pick (${s(picked)}) cannot be resourced this cycle; the highest-ranked feasible response is pre-selected`,
	dss_why_evoi: (why: unknown) => `Why act or wait: ${s(why)}`,
	dss_why_criteria: 'Weights and scores',
	dss_why_criteria_ahp: (cr: unknown) => `AHP weights (consistency ratio ${s(cr)}, acceptable) scored by TOPSIS closeness; a criterion every COA shares cannot change the ranking and is reported as a gate`,
	dss_why_dissent: 'The dissent (why not the runner-up)',
	dss_rule_note:
		'The engine proposes; a named officer decides. Approving creates dispatch requests (each decided on its own) and, when the response needs a corridor event, promotes this report to one.',
	dss_defer: 'Defer',
	dss_defer_hint: 'needs a reason (the Reason field below)',
	dss_provenance: 'Provenance',
	dss_provenance_feeds: (feeds: unknown) => `Feeds: ${s(feeds)}`,
	dss_provenance_publishers: (p: unknown) => `Publishers: ${s(p)}`,
	dss_provenance_wargame: 'Simulated outcomes',
	dss_provenance_wargame_tip: 'Outcome numbers are simulated by a seeded surrogate or twin, never sensor readings',
	dss_generated: (ago: unknown) => `generated ${s(ago)} ago`,
	dss_generated_at: (at: unknown) => `generated ${s(at)} IST`,
	dss_horizon: (min: unknown) => `horizon ${s(min)} min`,
	dss_load_failed: 'The oracle did not answer — the proposal cannot be shown.',
	dss_retry: 'Try again',
	dss_loading: 'Loading the proposal…',

	// ── the inspector section ──────────────────────────────────────────────
	dss_section_proposed: (top: unknown) => `A response is proposed — top course: ${s(top)}`,
	dss_link_inbox: 'Approve a response · in the Inbox',
	dss_link_decisions: 'Approve a response · in Decisions',
	dss_generate: 'Generate decision support',
	dss_generate_hint: 'Compute only — nothing is written until you decide',
	dss_generate_working: 'Computing…',
	dss_generate_failed: 'The oracle could not compute a proposal.',
	dss_generate_closed: 'The event is closed; a proposal would not be actionable.',
	dss_promoted_line: 'Promoted to a corridor event — see the linked event',
	dss_decided_line: (state: unknown) => `Decided: ${s(state)}`,

	// ── promote (the officer-gated action) ─────────────────────────────────
	dss_promote_label: 'Promote to corridor event',
	dss_promote_reason_officer: 'Name a duty officer to promote.',
	dss_promote_dialog: (kind: unknown, label: unknown) => `Creates a corridor event of kind ${s(kind)} from this report, keeping its verification state (${s(label)}). Recorded with your name.`,
	dss_promote_confirm: 'Promote',
	dss_promote_note: 'Note (sent with the promotion)',
	dss_promote_busy: 'Promoting…',

	// ── refusals (plain language; the server's own sentence prints verbatim) ──
	dss_refuse_officer: 'Name a duty officer to decide.',
	dss_refuse_reason: 'A reason is needed.',
	dss_refuse_not_proposed: 'This proposal is no longer waiting — it was decided or has expired.',
	dss_refuse_coa_vetoed: 'That course of action is vetoed and cannot be approved.',
	dss_refuse_coa_infeasible: 'That course of action cannot be resourced this cycle.',
	dss_refuse_unknown_coa: 'Choose one of the listed courses of action.',
	dss_refuse_no_anchor: 'The report has no road anchor; a corridor response cannot start from it.',
	dss_refuse_refused: 'The oracle refused this decision.',
	dss_refuse_failed: 'The decision did not go through.',

	// ── verification labels (subtitle text; X2 wording) ────────────────────
	dss_verif_EMULATED: 'Emulated',
	dss_verif_SIMULATED: 'Simulated',
	dss_verif_UNVERIFIED_OSINT: 'Unverified OSINT',
	dss_verif_NEWS_REPORTED: 'News-reported',
	dss_verif_OFFICIAL_VERIFIED: 'Official, verified',
	dss_verif_CONFIRMED: 'Confirmed by officer',
	dss_verif_none: 'Open-source',

	// ── the shell's outcome verb for this kind (dec_done_reject_pursuit et al) ──
	dec_done_reject_pursuit: 'Rejected',
	dec_done_defer_pursuit: 'Deferred',

	// ── view-model reasons ────────────────────────────────────────────────
	dss_reason_officer: 'Name a duty officer to approve a response.',
	dss_reason_officer_defer: 'Name a duty officer to defer.',
	dss_reason_no_coa: 'Choose a feasible, non-vetoed course of action.',
} satisfies Pack;



export const DSS_PACKS: Record<string, Pack> = { en };

registerPack('en', en as Pack);

/**
 * Register one language chunk (lib/i18n/load.ts's landing site; additive,
 * first registration wins — the core's documented semantics).
 */
export function adopt(code: 'hi' | 'mr', pack: Pack): void {
	DSS_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (FIX-E-PERF2): this module's HI and MR strings live ONLY in
 * ./packs.dss.hi.ts and ./packs.dss.mr.ts. The server render and every non-production
 * run (vite dev, the node test harness) register both before this module
 * finishes evaluating (SSR paints the persisted language). The production
 * browser registers the loader instead and awaits the document's language
 * before this module finishes evaluating — hydration waits for it, so a cold
 * HI/MR load never flashes English — and the other language loads on the
 * first switch (lib/i18n/load.ts). The prod client build folds the condition
 * to its else branch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.dss.hi')).hi);
	adopt('mr', (await import('./packs.dss.mr')).mr);
} else {
	await langChunks('packs.dss', (code) =>
		code === 'hi' ? import('./packs.dss.hi').then((c) => adopt('hi', c.hi)) : import('./packs.dss.mr').then((c) => adopt('mr', c.mr)),
	);
}
