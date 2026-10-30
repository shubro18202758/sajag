/**
 * The Plan string pack (V3-SPEC §6.6, §7.8; V3-P4B) — every string /plan prints. EN here; HI and MR in
 * ./packs.plan.hi.ts and ./packs.plan.mr.ts, complete for every key (tests/v3-plan.unit.mjs checks it).
 * Registered additively through registerPack(); no existing pack is edited. Every key starts with `v3p_`.
 *
 * Copy rules (v2 §11 + V3 §7.6): sentence case, no ALL-CAPS word outside the acronym list, at most one " · " per
 * string, titles (keys ending `heading`) ≤ 32 characters. Say what happens, what does not, and how sure. The
 * officer helper is §9.1's sentence, word for word. Numbers and times stay in Latin digits in all three languages.
 */
import { registerPack } from '$lib/i18n/strings';
import { langChunks } from '$lib/i18n/load';

type Fn = (...args: unknown[]) => string;
export type PlanPack = Record<string, string | Fn>;

const s = (v: unknown) => String(v ?? '');
const n = (v: unknown) => Number(v);
const pl = (v: unknown, one: string, many: string) => (n(v) === 1 ? one : many);

const en = {
	// ── the screen ──
	v3p_title: 'Plan a movement',
	v3p_steps: 'Planning steps',
	v3p_step_where: 'Where to',
	v3p_step_routes: 'Routes',
	v3p_step_launch: 'Launch',
	v3p_step_live: 'Live',

	// ── 1. where to ──
	v3p_where_heading: 'Where to?',
	v3p_where_lead: 'Pick the start, the destination and the class. Sajag proposes routes; a named officer starts the escort.',
	v3p_from: 'From',
	v3p_to: 'To',
	v3p_from_ph: 'Search a start place',
	v3p_to_ph: 'Search a destination',
	v3p_swap: 'Swap start and destination',
	v3p_no_match: (k: unknown) => `No place matches. The planner knows ${s(k)} places.`,
	v3p_same: 'Start and destination are the same place.',
	v3p_class_heading: 'Protection class',
	v3p_class_lanes: (k: unknown) => `${s(k)}-lane floor`,
	v3p_class_closure: (m: unknown) => `Roads close ${s(m)} min ahead`,
	v3p_class_closure_none: 'No advance closure',
	v3p_class_note: 'From the protocol table the planner applies.',
	v3p_when_heading: 'Departure',
	v3p_when_in30: 'In 30 min',
	v3p_when_in60: 'In 1 hour',
	v3p_when_at: 'At a time',
	v3p_when_at_label: 'Time (IST, 24-hour)',
	v3p_when_at_bad: 'Write the time as hh:mm, 24-hour.',
	v3p_leaves: (t: unknown) => `Leaves ${s(t)} IST`,
	v3p_leaves_tomorrow: (t: unknown) => `Leaves tomorrow ${s(t)} IST`,
	v3p_label_toggle: 'Add a test or rehearsal label',
	v3p_label: 'Label',
	v3p_label_ph: 'e.g. Shivaji Park parade rehearsal',
	v3p_label_hint: 'The label rides the movement as its title. A labelled movement is never shown as a real one.',
	v3p_find: 'Find routes',
	v3p_finding: 'Finding routes…',
	v3p_find_note: 'Finding routes registers the movement with the planner. Nothing moves until a named officer starts the escort.',
	v3p_find_locked_same: 'Pick two different places.',
	v3p_find_locked_time: 'Set a valid departure time.',
	v3p_find_locked_running: 'An escort is running. Stop it before planning another.',

	// ── a plan or a launch that did not go through (the server's words follow, verbatim) ──
	v3p_fail_plan_heading: 'No plan came back',
	v3p_fail_launch_heading: 'The escort did not start',
	v3p_fail_plan_none: 'No answer came back, so nothing is shown as planned.',
	v3p_fail_launch_none: 'No confirmation came back, so the escort is not shown as started.',
	v3p_fail_plan_refused: 'The planner answered:',
	v3p_fail_launch_refused: 'The brain refused the launch, in its words:',
	v3p_fail_error: 'The brain answered with an error:',
	v3p_fail_once: 'Nothing is retried on its own.',

	// ── 2. routes ──
	v3p_routes_found: (k: unknown) => `${s(k)} ${pl(k, 'route', 'routes')} found`,
	v3p_routes_lead: 'Best first. The escort runs the recommended route; the others are here to compare.',
	v3p_trip_class: (c: unknown) => `Class ${s(c)}`,
	v3p_edit: 'Change trip',
	v3p_state_approved: 'Ready to launch',
	v3p_state_conditional: 'Needs a waiver',
	v3p_state_hold: 'Held by the decider',
	v3p_state_no_route: 'No route',
	v3p_state_planned: 'Planned',
	v3p_rank_primary: 'Primary',
	v3p_rank_alt: (k: unknown) => `Alternate ${s(k)}`,
	v3p_pick_ai: 'Recommended by Sajag AI',
	v3p_pick_ai_conf: (c: unknown) => `Recommended by Sajag AI · confidence ${s(c)}`,
	v3p_pick_tactical: 'Recommended',
	v3p_fig_min: 'min',
	v3p_fig_km: 'km',
	v3p_fig_roads: (k: unknown) => pl(k, 'road', 'roads'),
	v3p_tier_ok: 'Meets the lane floor',
	v3p_tier_bad: (k: unknown) => `${s(k)} lane-floor ${pl(k, 'violation', 'violations')}`,
	v3p_adds: (roads: unknown) => `Adds ${s(roads)}`,
	v3p_adds_none: 'Adds no new road',
	v3p_runs: 'The escort runs this route',
	v3p_compare: 'For comparison',
	v3p_sim: 'Simulated traffic',
	v3p_sim_mixed: 'Partly simulated traffic',
	v3p_sim_unknown: 'Traffic source not reported',
	v3p_sim_tip: 'Times come from the traffic twin. They are estimates, not a live reading.',
	v3p_rejected: (k: unknown) => `${s(k)} ${pl(k, 'route', 'routes')} rejected`,
	v3p_notes: 'Planner notes',
	v3p_continue: 'Continue to launch',
	v3p_no_route_heading: 'No route for this trip',
	v3p_no_route_body: 'The planner found no route for this pair and class.',
	v3p_no_route_next: 'Pick another place or a lower class, then find routes again.',
	v3p_hold_heading: 'This plan is on hold',
	v3p_hold_body: (t: unknown) => `The decider delayed departure. It cannot launch; plan again after ${s(t)} IST.`,
	v3p_replan: 'Plan again',
	v3p_map_alt: (a: unknown, b: unknown) => `Map from ${s(a)} to ${s(b)}`,
	v3p_map_alt_routes: (k: unknown, a: unknown, b: unknown) => `Map of ${s(k)} ${pl(k, 'route', 'routes')} from ${s(a)} to ${s(b)}`,
	v3p_map_key_runs: 'Recommended route',
	v3p_map_key_other: 'Other candidates',

	// ── 3. launch ──
	v3p_launch_heading: 'Start the escort',
	v3p_launch_lead: (c: unknown, d: unknown) => `The class ${s(c)} movement goes to ${s(d)} on the recommended route.`,
	v3p_waiver_heading: 'Lane-floor waiver',
	v3p_waiver_lead: 'This plan breaks the lane floor on the roads below. An officer accepts it before launch.',
	v3p_waiver: 'I accept the listed lane-floor violations for this plan',
	v3p_waiver_by: (who: unknown) => `Accepted by ${s(who)}`,
	v3p_seg: (id: unknown) => `Segment ${s(id)}`,
	v3p_who: 'Who is launching?',
	v3p_who_live: 'Who is on duty?',
	v3p_as_live: 'On duty',
	v3p_who_ph: 'Your name, as on the duty roster',
	v3p_who_go: 'Continue',
	v3p_who_help: 'Naming yourself shows full registration marks on this console and records your name with the decision. Attribution, not sign-in.',
	v3p_as: 'Launching as',
	v3p_signed_as: 'Signed in as',
	v3p_change: 'Change',
	v3p_recorded: 'Recorded in the audit trail',
	v3p_launch: 'Start escort',
	v3p_launching: 'Starting…',
	v3p_once: 'One press sends one request.',
	v3p_lock_officer: 'Name the duty officer to launch.',
	v3p_lock_waiver: 'Accept the waiver first. The plan is conditional.',
	v3p_lock_hold: 'The decider held this plan. Plan again later.',
	v3p_lock_none: 'Find routes first.',
	v3p_back: 'Back to routes',

	// ── 4. live ──
	v3p_live_heading: 'Escort running',
	v3p_ended_heading: 'Escort ended',
	v3p_live_lead: (c: unknown, d: unknown) => `The class ${s(c)} movement is on its way to ${s(d)}.`,
	v3p_live_adopted: 'Picked up from the board: this escort was started elsewhere.',
	v3p_live_since: (t: unknown) => `Started ${s(t)} IST`,
	v3p_gps_emulated: 'Emulated position',
	v3p_gps_tip: 'The convoy position comes from the emulator, not a vehicle tracker.',
	v3p_proposal: 'A decision waits on this escort',
	v3p_proposal_open: 'Review in Decide',
	v3p_follow: 'Follow on the map',
	v3p_open_event: 'Open the operation',
	v3p_stop: 'Stop escort',
	v3p_stopping: 'Stopping…',
	v3p_lock_stop: 'Name the duty officer to stop the escort.',
	v3p_end_completed: 'The brain reports the escort completed.',
	v3p_end_stopped: 'The brain reports the escort stopped by an officer.',
	v3p_end_failed: 'The brain reports the escort failed.',
	v3p_end_unknown: 'The escort is no longer running.',
	v3p_clear: 'Clear the movement',
	v3p_clearing: 'Clearing…',
	v3p_clear_hint: 'Lifts the closures, restores the signal programs and closes the corridor event.',
	v3p_cleared: (to: unknown) => `Cleared. The corridor event is now ${s(to)}.`,
	v3p_clear_failed: 'Not cleared. The brain answered:',
	v3p_new: 'Plan another movement',
} satisfies PlanPack;

export type PlanKey = keyof typeof en;

registerPack('en', en);

export const PLAN_PACK_KEYS: readonly PlanKey[] = Object.keys(en) as PlanKey[];
export const PLAN_PACKS: Record<string, PlanPack> = { en };

/** Register one language chunk (lib/i18n/load.ts's landing site; additive, first registration wins). */
export function adopt(code: 'hi' | 'mr', pack: PlanPack): void {
	PLAN_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (the deck's FIX-E-PERF2 pattern, as packs.v3): HI and MR live only in their own files. The
 * server render and every non-production run register both before this module finishes evaluating; the
 * production browser awaits the document's language and loads the other on the first switch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.plan.hi')).hi);
	adopt('mr', (await import('./packs.plan.mr')).mr);
} else {
	await langChunks('packs.plan', (code) =>
		code === 'hi' ? import('./packs.plan.hi').then((c) => adopt('hi', c.hi)) : import('./packs.plan.mr').then((c) => adopt('mr', c.mr)),
	);
}
