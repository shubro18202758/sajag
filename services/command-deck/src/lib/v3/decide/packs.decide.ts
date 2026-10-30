/**
 * The Decide string pack (V3-SPEC §6.2, §7.8) — every string /decide prints that the v2 decision packs
 * (packs.decisions, packs.dss) and the V3 pack (packs.v3) do not already say. EN here; HI and MR in
 * ./packs.decide.hi.ts and ./packs.decide.mr.ts, complete for every key (tests/decide.unit.mjs checks it).
 * Registered additively through registerPack(); no existing pack is edited. Every key starts with `v3d_`.
 *
 * Copy rules (v2 §11 + V3 §7.6): sentence case, no ALL-CAPS word outside the acronym list, at most one
 * " · " per string, titles ≤ 32 characters. Say what happens, what does not, and how sure. The officer
 * helper is §9.1's sentence, word for word. Numbers and times stay in Latin digits in all three languages.
 */
import { registerPack } from '$lib/i18n/strings';
import { langChunks } from '$lib/i18n/load';

type Fn = (...args: unknown[]) => string;
export type DecidePack = Record<string, string | Fn>;

const s = (v: unknown) => String(v ?? '');
const n = (v: unknown) => Number(v);
const pl = (v: unknown, one: string, many: string) => (n(v) === 1 ? one : many);
const lowerFirst = (v: unknown) => {
	const x = s(v);
	return x && !/^[A-Z0-9]{2}/.test(x) ? x.charAt(0).toLowerCase() + x.slice(1) : x;
};

const en = {
	// ── the screen ──
	v3d_sub: (k: unknown) => `${s(k)} waiting · one at a time, soonest first`,
	v3d_sub_none: 'Nothing is waiting',
	v3d_center: 'The decision',
	v3d_loading: 'Loading the decision',
	v3d_clear_body: 'No decision is waiting. A new one opens here, soonest deadline first.',
	v3d_back_home: 'Back to Home',

	// ── the queue ──
	v3d_waiting: 'Waiting',
	v3d_soonest_first: 'soonest first',
	v3d_empty: 'Nothing needs your decision.',
	v3d_when_left: (at: unknown) => `${s(at)} left`,
	v3d_when_waiting: (at: unknown) => `waiting ${s(at)}`,
	v3d_when_expired: 'Time is up',
	v3d_q_expired: 'Expired, plan kept',
	v3d_q_refused: 'Refused, see the card',
	v3d_decided_here: 'Decided on this console',
	v3d_tally_approved: 'Approved',
	v3d_tally_rejected: 'Rejected or dismissed',
	v3d_tally_deferred: 'Deferred',
	v3d_tally_expired: 'Expired, plan kept',
	v3d_full_record: 'Full record in Analyst',

	// ── the sheet: tags and words ──
	v3d_tag_class: (c: unknown) => `Class ${s(c)}`,
	v3d_tag_cred: (c: unknown) => `Credibility ${s(c)}`,
	v3d_tag_cred_pubs: (c: unknown, k: unknown) => `Credibility ${s(c)} · ${s(k)} ${pl(k, 'publisher', 'publishers')}`,
	v3d_tag_stolen: 'Reported stolen',
	v3d_tag_stolen_fir: (fir: unknown) => `Reported stolen · FIR ${s(fir)}`,
	v3d_tag_stolen_fir_demo: (fir: unknown) => `Reported stolen · demo FIR ${s(fir)}`,
	v3d_tag_watchlisted: 'Watchlisted vehicle',
	v3d_tag_changes: 'changes',
	v3d_tag_next: 'next',
	v3d_becomes: 'becomes',
	v3d_no_change_still: (now: unknown) => `No change · still ${lowerFirst(now)}`,
	v3d_fact_waypoint: 'waypoint junction',

	// what changes
	v3d_changes: 'What changes',
	v3d_changes_approve: 'What changes if you approve',
	v3d_changes_reject: 'What changes if you reject',
	v3d_changes_defer: 'What changes if you defer',
	v3d_changes_authorise: 'What changes if you authorise',
	v3d_changes_open: 'What changes if you open it',
	v3d_changes_dismiss: 'What changes if you dismiss',
	v3d_changes_coa: (label: unknown) => `What changes if you approve ${lowerFirst(label)}`,

	// the rule notes
	v3d_ifnot_lead: 'If no one answers in time,',
	v3d_ifnot_escort: 'the current plan is kept and nothing is applied. The convoy may wait at the signal.',
	v3d_expired_lead: 'No one answered in time.',
	v3d_expired_text: 'The current plan is kept. Nothing was applied, and this proposal can no longer be approved.',
	v3d_evidence_lead: 'Evidence only.',
	v3d_evidence_text: 'No fine is ever issued for a stolen vehicle. One approval opens one pursuit.',
	v3d_evidence_pursuit: 'Opening a pursuit plans an interception on the road graph. It issues no fine.',
	v3d_stolen_lead: 'Reported stolen.',
	v3d_echallan_stolen: 'Its owner is the theft victim, so this e-challan can only be rejected.',

	// the stolen vehicle
	v3d_class_car: 'Car',
	v3d_class_suv: 'Sport utility vehicle',
	v3d_class_bus: 'Bus',
	v3d_class_truck: 'Truck',
	v3d_class_tempo: 'Tempo',
	v3d_class_two_wheeler: 'Two-wheeler',
	v3d_class_auto_rickshaw: 'Auto-rickshaw',
	v3d_mark_shown: 'registration mark shown',
	v3d_mark_masked_body: 'Full mark shows when a duty officer is named. Vehicles only: cameras read plates, never people.',
	v3d_mark_shown_body: (who: unknown) => `Shown because ${s(who)} is named on this console. Vehicles only: cameras read plates, never people.`,
	v3d_steps: 'Two steps',
	v3d_step_authorise: 'Authorise',
	v3d_step_open: 'Open the pursuit',
	v3d_reads: (r: unknown, k: unknown, m: unknown) => `In this decision: ${s(r)} ${pl(r, 'read', 'reads')} by ${s(k)} ${pl(k, 'camera', 'cameras')} over ${s(m)} min`,

	// decision support
	v3d_pick: 'Pick a response',
	v3d_ranked: 'ranked by decision support',
	v3d_opt_recommended: 'Recommended',
	v3d_opt_to_scene: 'to the scene',
	v3d_opt_to_effect: 'to take effect',
	v3d_opt_no_units: 'no units',
	v3d_opt_no_action: 'no action',
	v3d_opt_dispatch: (agency: unknown, k: unknown) => `${s(agency)} × ${s(k)}`,
	v3d_opt_nothing: 'Watch the reports; nothing moves.',
	v3d_blocked_best: 'One stronger option is blocked:',
	v3d_blocked: 'Not available:',
	v3d_request_unit: 'Request a unit',
	v3d_request_after: 'Units are requested once the report is a corridor event.',
	v3d_why_this: 'Why this one',
	v3d_ai_view: 'Sajag AI',
	v3d_full_analysis: 'Open the full analysis in Analyst',

	// escort: how the assistant worked it out
	v3d_how: 'How the assistant worked this out',
	v3d_how_decider: (who: unknown) => `Proposed by ${s(who)}.`,
	v3d_how_congestion: (pct: unknown) => `Congestion ahead peaks at ${s(pct)}%.`,
	v3d_how_simulated: 'Its traffic figures come from a simulated feed.',

	// ── who is deciding ──
	v3d_who: 'Who is deciding?',
	v3d_who_placeholder: 'Your name, as on the duty roster',
	v3d_continue: 'Continue',
	v3d_officer_helper: 'Naming yourself shows full registration marks on this console and records your name with the decision. Attribution, not sign-in.',
	v3d_deciding_as: 'Deciding as',
	v3d_signed_as: 'Signed in as',
	v3d_change: 'Change',
	v3d_recorded: 'Recorded in the audit trail',

	// ── the buttons ──
	v3d_btn_approve_hold: 'Approve the hold',
	v3d_btn_approve_route: 'Approve the new route',
	v3d_btn_approve_coa: (label: unknown) => `Approve ${lowerFirst(label)}`,
	v3d_btn_approve_corridor: 'Approve the corridor',
	v3d_btn_approve_echallan: 'Approve the e-challan',
	v3d_btn_authorise: 'Authorise pursuit',
	v3d_btn_open_pursuit: 'Open the pursuit',
	v3d_btn_dismiss: 'Dismiss…',
	v3d_btn_dismiss_all: (k: unknown) => `Dismiss all ${s(k)}…`,
	v3d_reason_officer: 'Name yourself above to decide.',
	v3d_reason_loading: 'The options are still loading.',
	v3d_reason_answered: 'Already answered from this console.',
	v3d_reason_defer: 'Give a reason to defer.',
	v3d_reason_label: (verb: unknown) => `Reason to ${lowerFirst(verb)} (sent with the decision)`,
	v3d_refuse_failed: 'No confirmation came back, so it is not shown as decided. Check the full record before you try again.',
	v3d_refuse_said: 'Not done. The service answered:',
	v3d_answered_here: 'Answered from this console. It is final and is never sent twice.',

	// ── after deciding ──
	v3d_recorded_with: (who: unknown, at: unknown) => `Recorded with ${s(who)} at ${s(at)} IST.`,
	v3d_expired_title: 'No one answered in time',
	v3d_expired_body: 'The current plan was kept. Nothing was applied.',
	v3d_gone_title: 'No longer waiting',
	v3d_gone_body: 'This decision was closed elsewhere or is no longer offered. The full record is in Analyst.',
	v3d_next_decision: 'Next decision',
	v3d_all_done: 'Nothing else is waiting.',

	// ── the countdown ──
	v3d_ring_label: (at: unknown) => `Time left to decide: ${s(at)}`,
	v3d_ring_announce: (sec: unknown) => `${s(sec)} seconds left to decide`,

	// ── the map ──
	v3d_map_escort: 'Protected movement · route and the junction in question',
	v3d_map_dss: (place: unknown) => `Where it was reported · ${s(place)}`,
	v3d_map_reads: 'Lawful reads of one watchlisted vehicle · cameras read plates only',
	v3d_map_corridor: 'The 108 unit and its waypoint',
	v3d_map_place: 'The place in question',
	v3d_map_reported_here: (place: unknown) => `Reported here · ${s(place)}`,
	v3d_map_last_read: 'Last read',
	v3d_map_data: 'Map data',
	v3d_lg_route: 'Route',
	v3d_lg_reads: 'Camera reads',
	v3d_lg_decision: 'Decision waits',
} satisfies DecidePack;

export type DecideKey = keyof typeof en;

registerPack('en', en);

export const DECIDE_PACK_KEYS: readonly DecideKey[] = Object.keys(en) as DecideKey[];
export const DECIDE_PACKS: Record<string, DecidePack> = { en };

/** Register one language chunk (lib/i18n/load.ts's landing site; additive, first registration wins). */
export function adopt(code: 'hi' | 'mr', pack: DecidePack): void {
	DECIDE_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (the deck's FIX-E-PERF2 pattern, as packs.v3): HI and MR live only in their own files.
 * The server render and every non-production run register both before this module finishes evaluating;
 * the production browser awaits the document's language and loads the other on the first switch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.decide.hi')).hi);
	adopt('mr', (await import('./packs.decide.mr')).mr);
} else {
	await langChunks('packs.decide', (code) =>
		code === 'hi' ? import('./packs.decide.hi').then((c) => adopt('hi', c.hi)) : import('./packs.decide.mr').then((c) => adopt('mr', c.mr)),
	);
}
