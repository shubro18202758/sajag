/**
 * The decisions string pack (EN / HI / MR): decision units, the
 * ProposalCard and its footer, the Inbox, the /ops Decisions column, the
 * Pursuit section, the lifecycle action and the LiveStrip feed (UI-S5A).
 * Registered additively through registerPack(); the core packs stay
 * untouched. Every key starts with `dec_`.
 *
 * EN is sentence case, with no ALL-CAPS word outside the acronym allowlist,
 * at most one " · " per string, and titles of at most 32 characters
 * (tests/copy-lint.mjs, target file style-lint.targets/s5.json). HI and MR are
 * complete for every key. Copy describes only what the system does (SPEC
 * §9.1): naming an officer shows full marks on this console and records the
 * name; a stolen vehicle is never fined; one approval opens one pursuit; a
 * request waits for an officer's approval; nothing here applies itself.
 */
import { registerPack } from './strings';
import { langChunks } from './load';

type Fn = (...args: unknown[]) => string;
type Pack = Record<string, string | Fn>;

const n = (v: unknown) => Number(v);
const s = (v: unknown) => String(v ?? '');

const en = {
	// ── unit titles (imperative; a masked mark in the argument) ───────────
	dec_title_stolen: (plate: unknown) => `Authorise pursuit of ${s(plate)}`,
	dec_title_stolen_after: (plate: unknown) => `Dismiss earlier sightings of ${s(plate)}`,
	dec_title_pursuit: (plate: unknown) => `Open pursuit of ${s(plate)}`,
	dec_title_echallan: (plate: unknown) => `Decide e-challan for ${s(plate)}`,
	dec_title_echallan_stolen: (plate: unknown) => `Reject e-challan for ${s(plate)}`,
	dec_title_corridor: (unit: unknown) => `Decide the ambulance (108) corridor for ${s(unit)}`,

	// ── subtitles and row meta ─────────────────────────────────────────────
	dec_sub_stolen: (w: unknown) => `Proposed by the rules engine (stolen-vehicle sighting) · waiting ${s(w)}`,
	dec_sub_rule: (rule: unknown, w: unknown) => `Proposed by the rules engine (${s(rule)}) · waiting ${s(w)}`,
	dec_meta_echallan_stolen: 'Withheld: the vehicle is reported stolen (a rules-engine proposal)',
	dec_sub_pursuit: (ago: unknown) => `Offered by the watchlist rule · last read ${s(ago)}`,
	dec_sub_corridor: (by: unknown, w: unknown) => `Requested by ${s(by)} · waiting ${s(w)}`,
	dec_by_ai: 'Proposed by Sajag AI',
	dec_by_rule: 'Proposed by rule',
	dec_meta_sightings: (c: unknown) => `${n(c)} sighting${n(c) === 1 ? '' : 's'}`,
	dec_meta_newest: (x: unknown) => `newest ${s(x)}`,
	dec_meta_anchor: (road: unknown) => `anchor ${s(road)}`,
	dec_meta_movement_card: (meta: unknown) => `Decided in the movement card · ${s(meta)}`,
	dec_age_waiting: 'waiting',
	dec_age_expires: 'expires in',
	dec_age_ago: 'ago',
	dec_ago: (d: unknown) => `${s(d)} ago`,
	dec_ongoing: 'ongoing',
	dec_rule_unknown: 'a rule',
	dec_rule_r_spd_segment: 'segment speed rule',
	dec_rule_r_stolen_sighting: 'stolen-vehicle sighting',

	// ── tags ───────────────────────────────────────────────────────────────
	dec_tag_needs_decision: 'Needs decision',
	dec_tag_sightings: (c: unknown) => `${n(c)} sighting${n(c) === 1 ? '' : 's'}`,
	dec_tag_reported_stolen: 'Reported stolen',
	dec_tag_expires_in: (cd: unknown) => `Expires in ${s(cd)}`,
	dec_emulated_gps_tip: 'The convoy position comes from emulated GPS, not a field device.',

	// ── card sections ──────────────────────────────────────────────────────
	dec_what_changes: 'What changes',
	dec_col_object: 'Object',
	dec_col_now: 'Now',
	dec_col_after: 'After you decide',
	dec_no_change: 'No change',
	dec_unchanged: (list: unknown) => `Unchanged: ${s(list)}.`,
	dec_why: 'Why',
	dec_evidence: 'Evidence',
	dec_sightings_in_decision: (c: unknown) => `Sightings in this decision (${n(c)})`,
	dec_next_label: 'Next step:',
	dec_next_after_authorise: 'Next step after you authorise:',
	dec_next_now: 'Next step:',
	dec_next_open_pursuit_on: (road: unknown) => `Open pursuit on ${s(road)}, a separate decision, refused if the latest sighting has no road anchor.`,
	dec_next_open_pursuit: 'Open pursuit, a separate decision, refused if the latest sighting has no road anchor.',
	dec_next_pursuit_open: 'A pursuit is already open for this vehicle.',
	dec_next_after_pursuit: 'The interception plan ranks the choke junctions; request units from the Pursuit section.',
	dec_next_escort: 'Unanswered when the countdown ends, the current plan is held. An approval can come back not applied if the convoy has passed the branch point.',
	dec_next_dispatch: 'The unit then moves; its later steps are recorded in Dispatch.',
	dec_next_request: 'A duty officer approves or defers the request in Dispatch.',

	// ── What changes rows ──────────────────────────────────────────────────
	dec_row_newest_sighting: (x: unknown) => (s(x) ? `Newest sighting (${s(x)})` : 'Newest sighting'),
	dec_row_earlier_sightings: (c: unknown) => `${n(c)} earlier sighting${n(c) === 1 ? '' : 's'}`,
	dec_row_pending_sightings: (c: unknown) => `${n(c)} pending sighting${n(c) === 1 ? '' : 's'}`,
	dec_row_pursuit: 'Pursuit',
	dec_row_pursuit_event: 'Pursuit event',
	dec_row_interception: 'Interception plan',
	dec_row_approved_rec: 'Approved sighting',
	dec_row_watchlist: 'Watchlist entry',
	dec_row_echallan: (plate: unknown) => `E-challan for ${s(plate)}`,
	dec_row_convoy: 'Convoy',
	dec_row_route: 'Route',
	dec_row_closures: 'Closures',
	dec_row_signals: 'Signal plans',
	dec_row_signals_closures: 'Signal plans and closures',
	dec_row_proposal: 'Proposal',
	dec_row_dispatch: (unit: unknown) => `Dispatch of ${s(unit)}`,
	dec_row_dispatch_request: 'Dispatch request',
	dec_state_pending: 'Pending',
	dec_state_not_open: 'Not open',
	dec_state_none: 'None',
	dec_state_approved: 'Approved',
	dec_state_active: 'Active',
	dec_state_moving: 'Moving',
	dec_state_current: 'Current',
	dec_state_current_plan: 'Current plan',
	dec_state_open: 'Open',
	dec_state_requested: 'Requested',
	dec_after_approved: 'Approved, with your name',
	dec_after_rejected: 'Rejected, with your reason',
	dec_after_rejected_plain: 'Rejected, with your name',
	dec_after_deferred: 'Deferred, with your name',
	dec_after_opens_on: (road: unknown) => `Opens on ${s(road)}`,
	dec_after_opens: 'Opens',
	dec_after_plan_starts: 'Starts: ranked choke junctions',
	dec_after_holds: (road: unknown, sec: unknown) => `Holds short of ${s(road)}, up to ${s(sec)} s`,
	dec_after_route: (kind: unknown, via: unknown) => `${s(kind)} via ${s(via)}`,
	dec_after_closures: (added: unknown, lifted: unknown) => `${n(added)} new, ${n(lifted)} lifted`,
	dec_after_requested: (agency: unknown, at: unknown) => `Requested: ${s(agency)} to ${s(at)}`,
	dec_unchanged_earlier: 'the earlier sightings (they stay pending)',
	dec_unchanged_pursuit: 'the pursuit (not opened)',
	dec_unchanged_fine: 'any fine (none is ever issued)',
	dec_unchanged_watchlist: 'the watchlist entry',
	dec_unchanged_retention: 'the retention period',
	dec_unchanged_recs: 'the recommendations',
	dec_unchanged_other_recs: 'every other recommendation',
	dec_unchanged_other_proposals: 'the other proposals',
	dec_unchanged_route_signals: 'the route, signal plans and closures',
	dec_unchanged_other_dispatches: 'every other dispatch',
	dec_unchanged_pursuit_plan: 'the pursuit and its plan',

	// ── Why ────────────────────────────────────────────────────────────────
	dec_why_stolen_fir: (fir: unknown) => `Reported stolen (FIR ${s(fir)}).`,
	// an emulated vehicle's FIR is a scripted demo reference, never a real case (HON-4)
	dec_why_stolen_fir_demo: (fir: unknown) => `Reported stolen (demo FIR ${s(fir)} — exercise data).`,
	dec_why_stolen: 'Reported stolen.',
	dec_why_read_by: (c: unknown, span: unknown) => `Read by ${n(c)} camera${n(c) === 1 ? '' : 's'} ${s(span)} IST:`,
	dec_why_last_speed: (kmh: unknown) => `Last read at ${n(kmh)} km/h.`,
	dec_why_echallan: 'The rules engine filed this e-challan from an ANPR read.',
	dec_why_watchlisted: 'A watchlisted vehicle with a latest read and no open pursuit.',
	dec_why_last_read: (ago: unknown) => `Last read ${s(ago)}`,
	dec_why_anchor: (road: unknown, m: unknown) => `Anchor: ${s(road)}, ${n(m)} m from the latest read.`,
	dec_why_escort: (pct: unknown, roads: unknown) => `Congestion ${n(pct)}% ahead on the route, on ${s(roads)}.`,
	dec_why_escort_departure: (pct: unknown, roads: unknown) => `The departure is held: congestion ${n(pct)}% on ${s(roads)}.`,
	dec_why_escort_plain: 'The escort follower proposes a change to the current plan.',
	dec_why_escort_proposal: (text: unknown) => `Proposed: ${s(text)}`,
	dec_why_corridor: (agency: unknown, unit: unknown, by: unknown, at: unknown) => `${s(agency)} ${s(unit)}, requested by ${s(by)} at ${s(at)} IST.`,
	dec_why_corridor_event: (ev: unknown) => `For ${s(ev)}.`,
	dec_why_corridor_waypoint: (wp: unknown) => `Waypoint ${s(wp)}.`,
	dec_why_golden_hour: (gh: unknown) => `Golden hour ${s(gh)}.`,
	dec_kmh: (v: unknown) => `${n(v)} km/h`,
	dec_heading: (dir: unknown) => `heading ${s(dir)}`,
	dec_road_unknown: 'road not reported',
	dec_registration_mark: 'Registration mark',

	// ── rule notes ─────────────────────────────────────────────────────────
	dec_note_evidence_only: 'Evidence only:',
	dec_note_stolen: (fir: unknown) => `e-challan withheld (vehicle reported stolen${s(fir) ? `, FIR ${s(fir)}` : ''}). One approval opens one pursuit.`,
	dec_note_no_fine: 'No fine:',
	dec_note_rule_proposes: 'A rule proposes:',
	dec_note_echallan: 'a named officer decides; the decision is recorded with the name.',
	dec_note_one_pursuit_title: 'One approval, one pursuit:',
	dec_note_one_pursuit: 'a named officer opens it from a human-approved sighting; the machine never does.',
	dec_note_escort: 'Unanswered when the countdown ends, the current plan is held.',
	dec_note_corridor: 'Deciding changes this dispatch’s status only.',
	dec_note_since_stolen_title: 'Vehicle since reported stolen.',
	dec_note_since_stolen: 'This e-challan was decided before the theft report; the decision stands, and no new e-challan can be approved for this vehicle.',

	// ── evidence tables ────────────────────────────────────────────────────
	dec_ev_camera: 'Camera',
	dec_ev_road: 'Road',
	dec_ev_speed: 'Speed',
	dec_ev_limit: 'Limit',
	dec_ev_read: 'Read',
	dec_ev_rule: 'Rule',
	dec_ev_basis: 'Basis',
	dec_ev_approved_rec: 'Approved sighting',
	dec_ev_none: 'None',
	dec_ev_anchor: 'Anchor',
	dec_ev_dispatch: 'Dispatch',
	dec_ev_unit: 'Unit',
	dec_ev_requested_by: 'Requested by',
	dec_ev_note: 'Note',

	// ── footer ─────────────────────────────────────────────────────────────
	dec_officer_label: 'Duty officer',
	dec_officer_placeholder: 'Name as on the duty roster',
	dec_officer_helper: 'Shows full registration marks on this console and records the name with your decision. Attribution, not sign-in.',
	dec_reason_label: 'Reason',
	dec_reason_info_required: '(needed; sent with the decision)',
	dec_reason_info_optional: '(optional; sent with the decision)',
	dec_reason_info_dismiss: '(needed to dismiss; sent with the decision)',
	dec_reason_info_reject: '(needed to reject; sent with the decision)',
	dec_reason_info_defer: '(optional; sent with a deferral)',
	// FIX-E-DSSCARD item 8: a dss proposal's reject AND defer both need the note
	dec_reason_info_dss: '(needed to reject or defer; sent with the decision)',
	dec_reason_placeholder: 'e.g. duplicate read, wrong vehicle class',
	dec_reason_placeholder_echallan: 'e.g. emergency vehicle on duty, speed sign missing',
	dec_reason_placeholder_corridor: 'e.g. second unit already en route',
	dec_reason_placeholder_dss: 'e.g. awaiting the official confirmation',
	dec_view_evidence: 'Show the evidence on the map',
	dec_btn_approve: 'Approve',
	dec_btn_reject: 'Reject',
	dec_btn_defer: 'Defer',
	dec_btn_dismiss: 'Dismiss',
	dec_btn_dismiss_all: (c: unknown) => `Dismiss all ${n(c)}`,
	dec_btn_open_pursuit: 'Open pursuit',
	dec_btn_request_unit: 'Request unit',
	dec_reason_officer: 'Name a duty officer to decide.',
	dec_reason_officer_request: 'Name a duty officer to request a unit.',
	dec_reason_dismiss: 'Give a reason to dismiss.',
	dec_reason_reject: 'Give a reason to reject.',
	dec_reason_expired: 'This proposal has expired; the current plan is held.',
	dec_reason_passed: 'The vehicle has likely passed this junction.',
	dec_reason_busy: 'Another decision is being sent.',
	dec_outcome: (verb: unknown, who: unknown, at: unknown) => `${s(verb)} by ${s(who)} at ${s(at)} IST`,
	dec_outcome_by: (who: unknown) => `Recorded with ${s(who)}`,

	// ── outcomes (toasts and rows) ─────────────────────────────────────────
	dec_done_authorise_pursuit: 'Pursuit authorised',
	dec_done_dismiss_pursuit: 'Sightings dismissed',
	dec_done_open_pursuit: 'Pursuit opened',
	dec_done_approve_echallan: 'E-challan approved',
	dec_done_reject_echallan: 'E-challan rejected',
	dec_done_approve_escort: 'Escort proposal approved',
	dec_done_reject_escort: 'Escort proposal rejected',
	dec_done_approve_corridor: 'Ambulance (108) corridor approved',
	dec_done_defer_corridor: 'Ambulance (108) corridor deferred',
	dec_done_approve_pursuit: 'Approved',
	dec_done_request: 'Unit requested',
	dec_done_request_body: (agency: unknown, at: unknown) => `${s(agency)} to ${s(at)}; waits for a duty officer’s approval`,

	// ── refusals ───────────────────────────────────────────────────────────
	dec_refuse_officer: 'Name a duty officer to decide.',
	dec_refuse_reason: 'A reason is needed.',
	dec_refuse_decided: 'Already decided.',
	dec_refuse_authorised: 'The pursuit is already authorised for this vehicle.',
	dec_refuse_refused: 'The oracle refused this decision.',
	dec_refuse_stolen: 'The vehicle is reported stolen: an e-challan can only be rejected.',
	dec_refuse_no_anchor: 'No road anchor for the latest sighting.',
	dec_refuse_no_approval: 'No human-approved sighting for this vehicle.',
	dec_refuse_open: 'A pursuit is already open for this vehicle.',
	dec_refuse_expired: 'The proposal expired; the current plan is held.',
	dec_refuse_not_applied: 'Approved but not applied: the convoy had passed the branch point.',
	dec_refuse_event_closed: 'The pursuit event is closed.',

	// ── homes ──────────────────────────────────────────────────────────────
	dec_home_inbox: 'Decided in the Inbox',
	dec_home_decisions: 'Decided in Decisions on Situation',
	dec_home_movement: 'Decided in the movement card',
	dec_home_map: 'Decided on the map',
	// FIX-E-DSSCARD item 10: the /ops metric names the soonest decision's real kind
	// (fix round 2: the wall says it in words — the card itself says "Approve a response")
	dec_kind_dss: 'Response',
	dec_kind_corridor: 'Ambulance (108) decision',
	dec_m_soonest_expires: (kind: unknown, t: unknown) => `${s(kind)} expires in ${s(t)}`,

	// ── inbox ──────────────────────────────────────────────────────────────
	dec_tab_inbox: 'Inbox',
	dec_inbox: 'Inbox',
	dec_needs_decision: 'Needs your decision',
	dec_by_deadline: 'by deadline',
	dec_updates: 'Updates',
	dec_none_waiting: 'No decisions waiting',
	dec_none_waiting_hint: 'New proposals from the rules engine and Sajag AI appear here.',
	dec_nothing_new: 'Nothing new.',
	dec_mark_read_tip: 'Mark all read (E)',
	dec_back_tip: 'Back to the inbox (Esc)',
	dec_prev_tip: 'Previous (K)',
	dec_next_tip: 'Next (J)',
	dec_n_of_m: (i: unknown, c: unknown) => `${n(i)} of ${n(c)}`,
	dec_escort_home_note: 'Escort proposals are decided in the movement card, on its countdown.',
	dec_open_movement: 'Open the movement card',
	dec_upd_watch_read: 'Watchlist read',
	dec_upd_event_done: (name: unknown) => `${s(name)} completed`,
	dec_upd_emulated: 'Emulated',
	dec_upd_traffic_simulated: (c: unknown) => `Traffic is simulated on all ${n(c)} roads`,
	dec_upd_traffic_meta: 'Corridor feed, no field observations',

	// ── /ops Decisions column ──────────────────────────────────────────────
	dec_queue_tabs: 'Decisions',
	dec_tab_needs: 'Needs decision',
	dec_tab_approved: 'Approved',
	dec_tab_rejected: 'Rejected',
	dec_tab_expired: 'Expired',
	dec_view_options: 'View options',
	dec_hide_emulated: 'Hide emulated items',
	dec_no_emulated: 'No emulated items in the list',
	dec_sorted_by_deadline: 'Sorted by deadline, then severity',
	dec_sort_fixed: 'Decisions are always sorted by deadline',
	dec_hidden_emulated: (c: unknown) => `${n(c)} emulated item${n(c) === 1 ? '' : 's'} hidden`,
	dec_show: 'Show',
	dec_expand: 'Open this decision',
	dec_collapse: 'Close this decision',
	dec_empty_approved: 'No approvals on record',
	dec_empty_rejected: 'No rejections on record',
	dec_empty_expired: 'No expired proposals',
	dec_decided_pursuit: 'Pursuit authorised',
	dec_decided_sighting_dismissed: 'Sighting dismissed',
	dec_decided_echallan_approved: 'E-challan approved',
	dec_decided_echallan_rejected: 'E-challan rejected',
	dec_no_officer: 'No officer response',
	dec_rec_decided_by: 'Decided by',
	dec_rec_decided: 'Decided',
	dec_rec_road: 'Road',
	dec_rec_proposal: 'Proposal',
	dec_rec_pursuit: 'Pursuit',
	dec_rec_pursuit_state: (st: unknown) => `Pursuit event, ${s(st)}`,
	dec_rec_not_opened: 'Not opened',
	dec_rec_audit: 'Audit',
	dec_rec_entries: (c: unknown) => `${n(c)} entr${n(c) === 1 ? 'y' : 'ies'}`,

	// ── pursuit section ────────────────────────────────────────────────────
	dec_pursuit: 'Pursuit',
	dec_pursuit_open: 'Open',
	dec_pursuit_state_planned: 'Planned',
	dec_pursuit_state_active: 'Active',
	dec_pursuit_state_completed: 'Completed',
	dec_pursuit_state_cancelled: 'Cancelled',
	dec_since: (at: unknown) => `since ${s(at)}`,
	dec_anchor: 'Anchor',
	dec_heading_k: 'Heading',
	dec_basis_heading: 'by the read’s heading',
	dec_basis_oneway: 'by the one-way',
	dec_basis_dead_end: 'dead end',
	dec_basis_unknown: 'direction unknown',
	dec_last_read: 'Last read',
	dec_at: 'at',
	dec_stale: (d: unknown) => `Stale: the last read is older than ${s(d)}; the vehicle may be beyond every junction listed.`,
	dec_chokes_ranked: 'Choke junctions, ranked',
	dec_likely_passed: 'likely passed',
	dec_eta_s: (sec: unknown) => `ETA ${n(sec)} s`,
	dec_eta_none: 'ETA —',
	dec_hold: (v: unknown) => `hold cost ${s(v)}`,
	dec_signal_controlled: 'signal-controlled',
	dec_downstream: 'downstream',
	dec_against_oneway_tag: 'Against a one-way',
	dec_against_oneway: 'Read driving against a one-way segment; the plan projects it as the camera saw it.',
	dec_plan_elsewhere: 'The map follows another pursuit’s plan now.',
	dec_btn_show_plan: 'Show this plan',
	dec_no_chokes: 'No choke junction within reach of the last read.',
	dec_plan_loading: 'Loading the interception plan.',
	dec_plan_none: 'No interception plan: the pursuit is closed.',
	dec_plan_note: 'A named officer opened this pursuit. The plan assists the operator; it never dispatches on its own.',
	dec_req_agency: 'Agency',
	dec_req_unit: 'Unit',
	dec_req_waypoint: 'Waypoint',
	dec_req_cancel: 'Cancel',
	dec_req_hint: 'The request waits for a duty officer’s approval in Dispatch.',

	// ── lifecycle action ───────────────────────────────────────────────────
	dec_life_approved: 'Approve this event',
	dec_life_active: 'Activate this event',
	dec_life_completed: 'Complete this event',
	dec_life_cancelled: 'Cancel this event',

	// ── LiveStrip feed ─────────────────────────────────────────────────────
	dec_live_movement: (cls: unknown) => `Protected movement · ${s(cls)}`,
	dec_live_vehicle: 'vehicle',
	dec_live_band: (band: unknown) => `Band ${s(band)} during the movement`,
	dec_band_red: 'Red',
	dec_band_black: 'Black',
	dec_live_feed_lost: (name: unknown) => `Feed lost: ${s(name)}`,
	dec_feed_events: 'corridor events',
	dec_feed_band: 'band engine',
	dec_feed_escorts: 'escort follower',
	dec_feed_traffic: 'traffic feed',
};



registerPack('en', en as Pack);

/** The EN, HI and MR packs (tests assert they carry the same keys). */
export const DECISIONS_PACKS: Record<string, Pack> = { en: en as Pack };

/**
 * Register one language chunk (lib/i18n/load.ts's landing site; additive,
 * first registration wins — the core's documented semantics).
 */
export function adopt(code: 'hi' | 'mr', pack: Pack): void {
	DECISIONS_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (FIX-E-PERF2): this module's HI and MR strings live ONLY in
 * ./packs.decisions.hi.ts and ./packs.decisions.mr.ts. The server render and every non-production
 * run (vite dev, the node test harness) register both before this module
 * finishes evaluating (SSR paints the persisted language). The production
 * browser registers the loader instead and awaits the document's language
 * before this module finishes evaluating — hydration waits for it, so a cold
 * HI/MR load never flashes English — and the other language loads on the
 * first switch (lib/i18n/load.ts). The prod client build folds the condition
 * to its else branch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.decisions.hi')).hi);
	adopt('mr', (await import('./packs.decisions.mr')).mr);
} else {
	await langChunks('packs.decisions', (code) =>
		code === 'hi' ? import('./packs.decisions.hi').then((c) => adopt('hi', c.hi)) : import('./packs.decisions.mr').then((c) => adopt('mr', c.mr)),
	);
}
