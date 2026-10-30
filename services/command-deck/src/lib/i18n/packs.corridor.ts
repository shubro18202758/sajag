/**
 * The corridor string pack (EN / HI / MR) — the corridor workspace's own
 * words (UI-S6A): the left dock's Plan tab, the Movement tab's ConvoyCard
 * and Active events. Registered additively through registerPack(); the core
 * packs stay untouched. Every key starts with `cor_`.
 *
 * EN is sentence case, no ALL-CAPS word outside the acronym allowlist, at
 * most one " · " per string, section titles of at most 32 characters
 * (tests/copy-lint.mjs, targets file s6a.json). Copy describes only what
 * the system does (SPEC §9.1): naming an officer shows full registration
 * marks on this console and records the name; the AI or a rule proposes and
 * a named officer decides; a plan that cannot depart never launches.
 */
import { registerPack } from './strings';
import { langChunks } from './load';

type Pack = Record<string, string | ((...args: unknown[]) => string)>;

const s = (v: unknown) => String(v ?? '');
const n = (v: unknown) => Number(v);

const en: Pack = {
	// ── tabs (the frame's rail and right dock) ─────────────────────────────
	cor_tab_plan: 'Plan',
	cor_tab_layers: 'Layers',
	cor_tab_movement: 'Movement',

	// ── the Plan tab ────────────────────────────────────────────────────────
	cor_plan_section: 'Plan a corridor',
	cor_plan_from: 'From',
	cor_plan_to: 'To',
	cor_plan_class: 'Class',
	cor_plan_departure: 'Departure (IST)',
	cor_plan_label: 'Label',
	cor_label_placeholder: 'e.g. Ganeshotsav visarjan route rehearsal',
	cor_plan_label_hint: 'A test or rehearsal label rides the movement as its title — it is never shown as a real movement',
	cor_plan_officer: 'Duty officer',
	cor_plan_btn: 'Plan corridor',
	cor_plan_btn_busy: 'Planning…',
	cor_plan_none: 'No plan yet — choose an origin and a destination, then plan.',

	// plan states (planner-status)
	cor_status_approved: 'Security compliant',
	cor_status_conditional: 'Conditional',
	cor_status_hold: 'Hold',
	cor_status_no_route: 'No route',
	cor_status_unknown: 'Planned',

	// CONDITIONAL: the waiver (capability 15)
	cor_waiver: 'I accept the listed lane-floor violations for this plan',
	cor_waiver_stamped: (who: unknown) => `${s(who)} accepted the lane-floor violations`,

	// HOLD (capability 16)
	cor_hold_replan: (at: unknown) => `Re-plan after ${s(at)}`,
	cor_hold_note: 'The decider delayed departure. This plan cannot launch.',

	// NO ROUTE (capability 16)
	cor_no_route_note: 'The planner found no route for this pair and class.',
	cor_no_route_next: 'Next: pick another origin or destination, or a lower protection class, and plan again.',

	// launch (criteria and Reason)
	cor_launch: 'Start escort',
	cor_launch_starting: 'Starting…',
	cor_launch_criteria: (cls: unknown, dest: unknown) => `Escorts the ${s(cls)} movement to ${s(dest)} under the named duty officer`,
	cor_launch_locked_waiver: 'Accept the lane-floor violations first — the plan is conditional.',
	cor_launch_locked_hold: 'The decider held this plan — re-plan for a later departure.',
	cor_launch_locked_officer: 'Name the duty officer to launch.',
	cor_launch_locked_no_plan: 'Plan a corridor first.',
	cor_stop: 'Stop escort',
	cor_stopping: 'Stopping…',
	cor_clear: 'Clear',
	cor_clearing: 'Clearing…',
	cor_clear_hint: 'Post-clearance restoration: closures lifted, signal programs restored, the corridor event closed',

	// candidates (planner-candidates / planner-candidate)
	cor_cand_primary: 'Primary',
	cor_cand_alternate: (k: unknown) => `Alternate ${s(k)}`,
	cor_cand_adds: (roads: unknown) => `adds ${s(roads)}`,
	cor_cand_compliant: 'Meets the lane floor',
	cor_cand_violations: (c: unknown) => `${n(c)} lane-floor violation${n(c) === 1 ? '' : 's'}`,
	cor_cand_ai_pick: (conf: unknown) => `Sajag AI's pick · confidence ${s(conf)}`,
	cor_cand_tactical_pick: 'Tactical primary',
	cor_cand_rejected: (c: unknown) => `Rejected routes (${n(c)})`,
	cor_cand_adds_none: 'adds no new road',
	cor_cand_roads: (c: unknown) => `${n(c)} road${n(c) === 1 ? '' : 's'}`,

	// the escort proposal lives in the Movement tab (never decided here)
	cor_proposal_link: (title: unknown) => `Escort proposal waiting: ${s(title)}`,
	cor_proposal_open: 'Decide it in the Movement tab',

	// ── the Movement tab (ConvoyCard) ──────────────────────────────────────
	cor_hud_escort_live: 'Escorting',
	cor_hud_planned: 'Escorting planned',
	cor_hud_completed: 'Escort completed',
	cor_hud_stopped: 'Escort stopped',
	cor_hud_failed: 'Escort failed',
	cor_hud_speed: 'Speed',
	cor_hud_speed_corridor: 'Corridor average',
	cor_hud_progress: 'Progress',
	cor_hud_eta: 'ETA',
	cor_hud_eta_planned: 'planned',
	cor_hud_hold: 'Hold',
	cor_hud_hold_none: 'None',
	cor_hud_hold_yes: 'Held',
	cor_hud_next_junction: (name: unknown, t: unknown) => `Next junction ${s(name)} · in ${s(t)}`,
	cor_hud_awaiting_gps: 'Awaiting GPS',
	cor_hud_destination: 'Destination',
	cor_hud_min: (m: unknown) => `${n(m)} min`,
	cor_hud_sec: (v: unknown) => `${n(v)} s`,
	cor_hud_legacy_brain: 'This brain predates escort control — it ran its loop inline and it ended at once.',
	cor_hud_officer_note: 'Naming a duty officer decides the escort; the AI never applies anything itself.',
	cor_hud_nofigures: 'No live figures on this console — open the Movement tab',

	// ── Active events ───────────────────────────────────────────────────────
	cor_events_none: 'No live corridor events',
	cor_events_focus: 'Show on the map',
	cor_events_focus_locked: 'Locked',
	cor_events_focus_locating: 'Locating…',
	cor_events_no_spine: 'No spine on canvas',
	cor_events_no_canvas: 'Canvas unavailable',
	cor_events_test_tip: (label: unknown) => `Labelled test or rehearsal movement — not a real movement: ${s(label)}`,
	cor_events_promoted: 'Promoted from an open-source report',
	cor_events_test: 'Test',

	// ── the lazy tab's failure line (plan R9's loader) ──────────────────────
	cor_tab_failed: 'Failed to load this panel.'
};



/** The raw packs, for tests/corridor.unit.mjs's HI/MR parity rule. */
export const languages: Record<string, Pack> = { en };

registerPack('en', en);

/**
 * Register one language chunk (lib/i18n/load.ts's landing site; additive,
 * first registration wins — the core's documented semantics).
 */
export function adopt(code: 'hi' | 'mr', pack: Pack): void {
	languages[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (FIX-E-PERF2): this module's HI and MR strings live ONLY in
 * ./packs.corridor.hi.ts and ./packs.corridor.mr.ts. The server render and every non-production
 * run (vite dev, the node test harness) register both before this module
 * finishes evaluating (SSR paints the persisted language). The production
 * browser registers the loader instead and awaits the document's language
 * before this module finishes evaluating — hydration waits for it, so a cold
 * HI/MR load never flashes English — and the other language loads on the
 * first switch (lib/i18n/load.ts). The prod client build folds the condition
 * to its else branch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.corridor.hi')).hi);
	adopt('mr', (await import('./packs.corridor.mr')).mr);
} else {
	await langChunks('packs.corridor', (code) =>
		code === 'hi' ? import('./packs.corridor.hi').then((c) => adopt('hi', c.hi)) : import('./packs.corridor.mr').then((c) => adopt('mr', c.mr)),
	);
}
