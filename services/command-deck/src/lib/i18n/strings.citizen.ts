/**
 * Citizen-screens string pack (EN / HI / MR) — the public copy for the
 * rebuilt /citizen advisory, the /driver green-corridor flow, the (deck)
 * /comms advisory desk and the /chat console.
 *
 * The i18n CORE (strings.ts) is frozen per contract; this module registers
 * its keys additively via the design-shell `registerPack()` extension
 * point (idempotent, never overrides). `citizenT()` additionally resolves
 * against this pack FIRST and falls back to the core `t()` — the same
 * pattern as the ops stream's `tOps()` — so components have one resolver
 * and the frozen packs stay intact even if registration has not run.
 *
 * Copy rules (per the language spec): plain-language consequences, never
 * internal codes — citizens never see GREEN/AMBER/RED/BLACK; road names stay
 * transliterated as on city signage; every mutable number is localized by the
 * caller through localizeNumber().
 */

import { localizeNumber, registerPack, t, touchPacks } from './strings';
import { langChunks } from './load';

type Pack = Record<string, string | ((...args: unknown[]) => string)>;

// ─── EN ─────────────────────────────────────────────────────────────────────

const en: Pack = {
	// ── /citizen — "Your road, next 2 hours" ────────────────────────────
	citizen_kicker: 'Your road, next 2 hours',
	citizen_explainer_link: 'Why roads hold',
	strip_calm: 'No corridor holds announced right now.',
	strip_watch: 'An event route is active — expect short planned holds near it.',
	strip_hold: 'Planned holds are running on the routes below. They are planned to lift at the times shown.',
	strip_severe: 'Priority corridor traffic is running. Civilian holds are planned to be short and lifted junction by junction.',
	card_hold_label: 'Roads hold',
	card_window_at: (clock) => `around ${clock}`,
	card_now: 'Holding now',
	card_soon: 'Next',
	card_alt_label: 'Use instead',
	timeline_title: 'Today along your route',
	timeline_empty: 'No more corridor events scheduled today.',
	timeline_lifted: 'lifted',
	timeline_planned: 'planned',
	subscribe_demo_note: 'Demo prototype — no messages will ever be sent from this build.',
	footer_privacy: 'No location is collected. Advisories name stretches and times only.',

	// Plain-language consequences per event kind (why the road holds).
	consequence_protected_movement:
		'A protected movement is passing — holds lift as it clears each junction.',
	consequence_procession: 'A procession is walking the route — crossings close briefly while it passes.',
	consequence_mass_gathering: 'A large gathering is dispersing — traffic is metered for crowd safety.',
	consequence_race: 'A road race, such as the Mumbai Marathon, is on — the stretch stays closed until the last runner clears.',
	consequence_ceremonial: 'A ceremonial parade, such as the Republic Day parade at Shivaji Park, is passing — short rolling holds only.',
	consequence_egress_surge: 'Stadium crowds are leaving — exits are metered in waves.',
	consequence_emergency_evacuation:
		'Relief and emergency traffic has priority — civilian traffic is held briefly.',
	consequence_work_zone: 'Road work narrows the carriageway — traffic passes one lane at a time.',
	// Operator-only kinds never reach a public card (holds.ts allowlist);
	// the copy exists so no surface can ever render a raw key.
	consequence_vehicle_pursuit: 'A police operation is active here — follow officers’ directions.',
	consequence_crime_incident: 'An incident response is active here — follow officers’ directions.',
	consequence_unknown: 'A planned corridor operation is active — expect short holds.',
	card_hold_unknown: 'Hold length not published yet.',
	card_hold_from_policy: 'hold length from the event’s closure plan',
	card_hold_from_adaptive: 'hold length adapted to live traffic',
	card_hold_from_baseline: 'standard hold length — not yet adapted to live traffic',
	card_hold_unavailable: 'Hold length unavailable right now — check again in a minute.',
	card_alt_none: 'No signed alternate on the modelled roads — allow extra time.',
	card_alt_unavailable: 'Alternate route unavailable right now — check again in a minute.',
	card_alt_from_graph: 'alternate computed on the city road graph',
	citizen_feed_offline: 'Live advisories are unreachable — showing the labelled offline preview.',
	citizen_feed_connecting: 'Connecting to Sajag…',
	citizen_feed_stale: 'Live advisories are briefly unreachable — showing the last update.',
	citizen_none_now: 'No corridor events in the next 2 hours.',
	citizen_preview_none: 'No public corridor event to preview right now.',
	map_unavailable: 'Map unavailable',
	map_unavailable_hint: 'The map could not start on this device.',
	map_title: 'Map of the corridor',
	map_credits: 'Map credits',

	// ── /driver — "The Window" ──────────────────────────────────────────
	driver_kicker: 'Green corridor',
	golden_hour: 'Since your request',
	golden_elapsed: 'counted from your request; the golden hour began at the incident',
	golden_not_started: 'Starts when you send the request',
	phase_idle: 'idle',
	phase_evaluating: 'evaluating',
	phase_proposal: 'proposal',
	phase_open: 'window open',
	phase_deferred: 'deferred',
	doctrine_note: 'Green corridors open 60–180 seconds before the ambulance reaches each junction.',
	scripted_badge: 'Scripted fallback',
	scripted_note:
		'No live corridor event right now — this is the labelled scripted fallback: nothing is sent and every number is demo-scale.',
	corridor_map: 'Corridor map',
	corridor_granted_stretch: 'Granted stretch',
	unit_en_route: 'Traffic police unit en route',
	unit_on_scene: 'Traffic police unit on scene',
	units_note_fallback: 'Scripted fallback — this unit walk is simulated, not a live dispatch.',
	control_room: 'Control room',
	control_room_line: 'Follow your 108 control on your usual channel',
	after_action: 'Scripted run complete. No time saving is measured in the scripted flow.',
	map_note_fallback: 'Road geometry is unreachable — corridor lines are not drawn.',

	// ── /driver — the live request → human approval → window flow ───────
	driver_unit_label: 'Ambulance unit',
	driver_unit_hint: 'Your 108 unit number',
	driver_unit_invalid: 'Use your unit number, e.g. 108-14.',
	driver_stretch_option: (road, n) => `${road} · stretch ${n} of the route`,
	driver_stretch_unnamed: (n) => `Unnamed road · stretch ${n} of the route`,
	driver_event_label: (kind) => `through: ${kind}`,
	phase_requested: 'awaiting duty officer',
	phase_approved: 'approved',
	driver_awaiting_title: 'Awaiting duty officer',
	driver_awaiting_body:
		'Your request is on the control-room wall. The window opens only when a named duty officer approves it.',
	driver_request_ref: (id) => `request ${id}`,
	driver_deferred_body: 'The control room deferred this request — hold position and request again if needed.',
	driver_cancelled_body: 'The control room cancelled this request.',
	driver_primed_title: 'Approved: corridor being primed',
	driver_primed_countdown: (sec) => `Window opens in ${sec} s`,
	driver_primed_when: (clock) => `at ${clock} — timed to your arrival at the junction`,
	driver_window_from_policy: (sec) => `window ${sec} s — from the event’s closure plan`,
	driver_window_from_adaptive: (sec) => `window ${sec} s — adapted to live traffic`,
	driver_window_from_baseline: (sec) => `window ${sec} s — standard length, not yet adapted to live traffic`,
	driver_window_clamped: (raw) => `(event value ${raw} s, held to the 60–180 s doctrine)`,
	driver_window_anchor_eta: 'opens before the unit reaches the junction, closes as it arrives',
	driver_window_anchor_approval: 'runs from the officer’s approval — the unit’s arrival is not projected',
	driver_window_unpublished: 'Window length not published for this event — follow 108 control.',
	driver_unit_eta: (sec) => `unit ~${sec} s from the junction`,
	driver_unit_arrived: 'unit at the junction',
	driver_unit_no_position: 'unit position not projected yet',
	driver_unit_emulated: 'Emulated unit',
	driver_window_closed: 'Window closed — the corridor returns to its planned holds.',
	driver_request_failed: (msg) => `Request not sent — ${msg}`,
	driver_status_retry: 'Status feed unreachable — retrying…',
	driver_live_note:
		'Live: the request, the officer’s decision and every status change are recorded in the dispatch audit trail.',
	driver_scripted_approval: 'Scripted approval — no duty officer is in the loop (fallback only).',

	// Dispatch lifecycle words (units/router.py DISPATCH_TRANSITIONS).
	dispatch_status_requested: 'requested',
	dispatch_status_approved: 'approved',
	dispatch_status_en_route: 'en route',
	dispatch_status_on_scene: 'on scene',
	dispatch_status_completed: 'completed',
	dispatch_status_deferred: 'deferred',
	dispatch_status_cancelled: 'cancelled',

	// ── /comms — advisory desk (operator) ───────────────────────────────
	comms_title: 'Advisory desk',
	comms_sub: 'One fact, every audience, every language — drafted for an officer to send, never auto-sent.',
	comms_pick_event: 'Event',
	comms_generate: 'Generate advisory',
	comms_regenerate: 'Regenerate',
	comms_copy: 'Copy',
	comms_copied: 'Copied',
	comms_audience: 'Audience',
	audience_citizens: 'Citizens · SMS / WhatsApp',
	audience_zones: 'Zone officers',
	audience_108: '108 control',
	audience_municipal: 'Municipal',
	comms_preview_note: 'Preview — the exact text each audience would receive.',
	comms_template_title: 'Templates by event kind',
	comms_draft_log: 'Draft log',
	comms_drafted_badge: 'Drafted — not delivered',
	comms_no_gateway:
		'No message gateway is deployed. Drafts are prepared here for an officer to copy and send — nothing is delivered or written to the audit record.',
	comms_dispatch_threads: 'Dispatch threads',
	comms_dispatch_live: 'live',
	comms_dispatch_demo: 'scripted demo',
	comms_dispatch_none: 'No dispatches recorded for this event yet.',
	comms_all_clear: 'Draft all-clear',
	comms_session_only: 'Drafts stay in this browser tab — nothing is sent or written to the audit record.',
	comms_agencies: 'Agencies',
	comms_not_deployed: 'not deployed',
	comms_scope_event: 'This event',
	comms_scope_all: 'All events',
	comms_other_events: (n) => `${n} more on other events`,
	comms_withheld: 'Operator-only event kind — no citizen advisory is drafted for it.',
	comms_template_hint: 'Pick a kind to preview its citizen template.',

	// Generated advisory templates (args are already-localized strings).
	adv_citizen_hold: (kind, minutes, clock, alt) =>
		`${kind}: ~${minutes} min hold on the route from ${clock}. Use ${alt} instead. Roads reopen on time.`,
	adv_citizen_hold_noalt: (kind, minutes, clock) =>
		`${kind}: ~${minutes} min hold on the route from ${clock}. No signed alternate — allow extra time. Roads reopen on time.`,
	adv_citizen_hold_altunknown: (kind, minutes, clock) =>
		`${kind}: ~${minutes} min hold on the route from ${clock}. Allow extra time. Roads reopen on time.`,
	adv_citizen_clear: (kind) =>
		`${kind} has cleared. Roads are open on time. Thank you for your patience.`,
	adv_zone: (kind, seg, minutes) =>
		`Zone officers: ${kind} hold on stretch ${seg}, ~${minutes} min. Hold the line, then release on schedule.`,
	adv_108: (kind, seg) =>
		`108 control: ${kind} active on stretch ${seg}. Green-corridor requests are being answered for this stretch.`,
	adv_municipal: (kind, seg, minutes) =>
		`Municipal: ${kind} on stretch ${seg}, planned ~${minutes} min holds. Barricade teams release junction by junction.`,

	// ── /chat — agent console ───────────────────────────────────────────
	chat_title: 'Agent console',
	chat_sub: 'Corridor brain · streamed reasoning over the selected event',
	chat_context: 'Context',
	chat_context_none: 'No event selected — the console runs without event context.',
	chat_placeholder: 'Ask about the corridor…',
	chat_send: 'Send',
	chat_clear: 'Clear',
	chat_offline: 'Agent offline',
	chat_offline_note: 'The agent stream is not answering — the console is read-only until it returns.',
	chat_thoughts: 'Reasoning',
	chat_tools: 'Tool calls',
	chat_you: 'You',
	chat_agent: 'Agent',
	chat_tool_pending: 'pending',
	chat_tool_running: 'running',
	chat_tool_success: 'done',
	chat_tool_error: 'failed',
	chat_tiers: 'tiers',
	chat_tier_decider: 'decider',
	chat_tier_gemma: 'Gemma',
	chat_tier_heuristic: 'heuristic',
	chat_degraded_turn: 'degraded turn',
	chat_raw_envelope: 'No prose answer — the brain returned a raw JSON envelope (verbatim below).',
	chat_alerts: 'operator alerts',
	chat_session: 'session',
	chat_action: 'action',

	// ── wave 3: provenance, the 2 h horizon, event phases ───────────────
	citizen_emulated_badge: 'Simulated feed · emulated',
	citizen_emulated_note:
		'Cards marked “Simulated feed” are an event-emulator demonstration run — not real road holds.',
	citizen_later_title: 'Later — beyond the next 2 hours',
	citizen_later_note: 'Hold times are published closer to the start.',
	citizen_later_unscheduled: 'time not set',
	citizen_later_roads_withheld: 'route announced within 2 hours of the start',
	card_sim_now: 'Simulated · now',
	adv_emulated_prefix: '[SIMULATED FEED · EMULATED — exercise text, not a real road hold]',
	card_sim_soon: 'Simulated · next',
	citizen_unverified_badge: 'Position not verified',
	card_unv_now: 'Planned · now',
	card_unv_soon: 'Planned · next',
	consequence_planned_protected_movement:
		'A protected movement will pass — holds will lift as it clears each junction.',
	consequence_planned_procession: 'A procession will walk the route — crossings will close briefly while it passes.',
	consequence_planned_mass_gathering: 'A large gathering will disperse — traffic will be metered for crowd safety.',
	consequence_planned_race: 'A road race, such as the Mumbai Marathon, will run — the stretch will stay closed until the last runner clears.',
	consequence_planned_ceremonial: 'A ceremonial parade, such as the Republic Day parade at Shivaji Park, will pass — short rolling holds only.',
	consequence_planned_egress_surge: 'Stadium crowds will leave — exits will be metered in waves.',
	consequence_planned_emergency_evacuation:
		'Relief and emergency traffic will have priority — civilian traffic will be held briefly.',
	consequence_planned_work_zone: 'Road work will narrow the carriageway — traffic will pass one lane at a time.',
	consequence_planned_unknown: 'A planned corridor operation will run — expect short holds.',
	phase_closure: 'closure',
	phase_works: 'road works',
	phase_setup: 'set-up',
	phase_procession: 'procession',
	phase_assembly: 'assembly',
	phase_approach: 'approach',
	phase_transit: 'transit',
	phase_egress: 'egress',
	phase_dispersal: 'dispersal',
	phase_evacuation: 'evacuation',
	phase_parade: 'parade',
	phase_race: 'race',
	phase_movement_window: 'movement window',
	phase_generic: (n) => `phase ${n}`,
	driver_new_request: 'New request',
	driver_emulated_hidden: (n) =>
		`${n} simulated (emulated) corridor event(s) not offered — a request can only name a real corridor.`,
};

// ─── HI ─────────────────────────────────────────────────────────────────────


// ─── MR ─────────────────────────────────────────────────────────────────────


// ─── Registration + resolution ───────────────────────────────────────────────

const CITIZEN_PACKS: Record<string, Pack> = { en };

registerPack('en', en);

/**
 * Citizen-screens resolver: this pack first (per language, EN fallback),
 * then the frozen core pack — components never call two resolvers.
 */
export function citizenT(lang: string, key: string, ...args: unknown[]): string {
	// re-render signal, same contract as core t() (FIX-E-PERF2)
	touchPacks();
	const pack = CITIZEN_PACKS[lang] ?? CITIZEN_PACKS.en;
	const val = pack[key] ?? CITIZEN_PACKS.en[key];
	if (val != null) {
		return typeof val === 'function' ? String(val(...args)) : String(val);
	}
	return t(lang, key, ...args);
}

/**
 * Plain-language consequence for an event kind, with a fallback: the
 * generic wording when a kind has no copy — never the raw key. A PLANNED
 * event (not active yet) reads in the future tense: nothing is holding
 * the road yet, and the copy must not say it is.
 */
export function consequenceLabel(lang: string, kind: string | null | undefined, planned = false): string {
	const key = `consequence_${planned ? 'planned_' : ''}${kind ?? ''}`;
	const val = citizenT(lang, key);
	if (val !== key) return val;
	return citizenT(lang, planned ? 'consequence_planned_unknown' : 'consequence_unknown');
}

/** Event-phase labels the public copy knows (the oracle's phase vocabulary). */
const PHASE_KEYS = new Set([
	'closure',
	'works',
	'setup',
	'procession',
	'assembly',
	'approach',
	'transit',
	'egress',
	'dispersal',
	'evacuation',
	'parade',
	'race',
	'movement_window',
]);

/**
 * An event phase's label in the reader's language: a known label
 * ('closure', 'set-up', 'movement window' …) through citizenT('phase_<label>'),
 * anything else as the localized generic 'phase N' — never an English
 * operator string inside a Hindi or Marathi page.
 */
export function phaseLabelText(lang: string, label: string | null | undefined, n: number): string {
	const norm = (label ?? '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
	const key = norm === 'set_up' ? 'setup' : norm === 'road_works' ? 'works' : norm;
	if (PHASE_KEYS.has(key)) return citizenT(lang, `phase_${key}`);
	return citizenT(lang, 'phase_generic', localizeNumber(n, lang));
}

/** Whether a key is provided by this pack (used by the completeness gate). */
export function isCitizenKey(key: string): boolean {
	return key in en;
}

/**
 * Register one language chunk (lib/i18n/load.ts's landing site; additive,
 * first registration wins — the core's documented semantics).
 */
export function adopt(code: 'hi' | 'mr', pack: Pack): void {
	CITIZEN_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (FIX-E-PERF2): this module's HI and MR strings live ONLY in
 * ./strings.citizen.hi.ts and ./strings.citizen.mr.ts. The server render and every non-production
 * run (vite dev, the node test harness) register both before this module
 * finishes evaluating (SSR paints the persisted language). The production
 * browser registers the loader instead and awaits the document's language
 * before this module finishes evaluating — hydration waits for it, so a cold
 * HI/MR load never flashes English — and the other language loads on the
 * first switch (lib/i18n/load.ts). The prod client build folds the condition
 * to its else branch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./strings.citizen.hi')).hi);
	adopt('mr', (await import('./strings.citizen.mr')).mr);
} else {
	await langChunks('strings.citizen', (code) =>
		code === 'hi' ? import('./strings.citizen.hi').then((c) => adopt('hi', c.hi)) : import('./strings.citizen.mr').then((c) => adopt('mr', c.mr)),
	);
}
