/**
 * The V3 string pack (V3-SPEC §7.8) — every string the V3 shell, Home and the V3 gallery print, in
 * EN here and HI / MR in ./packs.v3.hi.ts and ./packs.v3.mr.ts (complete for every key: tests/v3-tokens.unit.mjs
 * checks it). Registered additively through registerPack(); no existing pack is edited. Every key starts
 * with `v3_`.
 *
 * Copy rules (v2 §11 + V3 §7.6): sentence case, no ALL-CAPS word outside the acronym list, at most one
 * " · " per string (a run-time join puts the separators between facts), titles ≤ 32 characters. Say what
 * happens, what does not, and how sure. Numbers and times stay in Latin digits in all three languages.
 */
import { registerPack } from '$lib/i18n/strings';
import { langChunks } from '$lib/i18n/load';

type Fn = (...args: unknown[]) => string;
type V3Pack = Record<string, string | Fn>;

const s = (v: unknown) => String(v ?? '');
const n = (v: unknown) => Number(v);
const pl = (v: unknown, one: string, many: string) => (n(v) === 1 ? one : many);

const en = {
	// ── the shell ──
	v3_nav_main: 'Main',
	v3_nav_home: 'Home',
	v3_nav_map: 'Map',
	v3_nav_decide: 'Decide',
	v3_nav_assistant: 'Assistant',
	v3_nav_advisories: 'Advisories',
	v3_nav_analyst: 'Analyst',
	v3_nav_analyst_tip: 'The full workspace: graph, table, timeline, audit and the situation wall',
	v3_nav_badge: (k: unknown) => `${s(k)} ${pl(k, 'decision waiting', 'decisions waiting')}`,
	v3_home_link: 'Sajag home',
	v3_skip: 'Skip to main content',
	v3_search: 'Search a place, road, event or vehicle mark',
	v3_search_open: 'Open search',
	v3_exercise_tip: 'This console runs on exercise data. Every record says where it came from.',
	v3_lang: 'Language',
	v3_nav_plan: 'Plan',
	v3_nav_plan_tip: 'Plan a protected movement: where to, the class, the routes, then launch',
	// the header menu: language, exercise data and the data status, one compact control
	v3_menu: 'Language and data',
	v3_menu_tip: 'Language, exercise data and data status',
	v3_menu_exercise: 'Exercise data in use',
	v3_menu_screen: 'This screen',
	v3_menu_lang: 'Language',
	v3_menu_data: 'Data status',

	// ── alerts and the chime ──
	v3_alerts: 'Alerts',
	v3_alerts_new: (k: unknown) => `Alerts: ${s(k)} new`,
	v3_alerts_title: 'Alerts',
	v3_alerts_today: 'Today',
	v3_alerts_earlier: 'Earlier',
	v3_alerts_read: 'Mark all read',
	v3_alerts_empty: 'Nothing new. A decision that starts waiting shows here.',
	v3_alert_decision: 'New decision waiting',
	v3_alert_review: 'Review',
	v3_chime: 'Alert chime',
	v3_chime_on: 'On',
	v3_chime_off: 'Off',
	v3_chime_help: 'A soft chime for each new decision that waits. Remembered in this browser.',
	v3_chime_rule: 'Emulated and test decisions chime only while the console says it runs on exercise data.',
	v3_chime_toggle_on: 'Turn the alert chime on',
	v3_chime_toggle_off: 'Turn the alert chime off',

	// ── the officer control ──
	v3_officer_none: 'Name the duty officer',
	v3_officer_plates: 'Plates hidden',
	v3_officer_on: 'On duty',
	v3_officer_signed: 'Signed in',
	v3_officer_title: 'Who is on duty?',
	v3_officer_tip_none: 'Name the duty officer to decide. Until then, registration marks stay masked on this console.',

	// ── the top bar ──
	v3_greet_morning: 'Good morning',
	v3_greet_afternoon: 'Good afternoon',
	v3_greet_evening: 'Good evening',

	// ── Home: the featured decision ──
	v3_hero_now: 'Needs you now',
	v3_hero_left: 'left to decide',
	v3_hero_waiting: 'waiting',
	v3_hero_review: 'Review now',
	v3_hero_stack: (i: unknown, k: unknown) => `${s(i)} of ${s(k)}`,
	v3_hero_stack_aria: (i: unknown, k: unknown) => `Decision ${s(i)} of ${s(k)}, soonest deadline first`,
	v3_ifnot_escort: 'If no one answers, the current plan is kept. Nothing changes without a named officer.',
	v3_ifnot_expires: 'If no one answers before it expires, nothing is applied. Nothing changes without a named officer.',
	v3_ifnot_waits: 'It keeps waiting until an officer decides. Nothing changes without a named officer.',
	v3_hero_clear: 'Nothing needs you right now',
	v3_hero_clear_sub: 'No decision is waiting. New ones appear here, soonest deadline first.',
	v3_hero_next: 'Coming up next',
	v3_hero_none_planned: 'Nothing is planned in the next 72 hours.',
	v3_open_map: 'Open map',

	// who proposed it
	v3_by_ai: 'Proposed by the convoy assistant',
	v3_by_rule: 'Proposed by a rule',
	v3_by_dss: 'Decision support',
	v3_by_rules: 'Rules engine',
	v3_by_108: '108 driver app',
	v3_by_officer: 'Requested by an officer',

	// the unit kinds (the micro line above a title)
	v3_kind_escort: 'Escort proposal',
	v3_kind_dss: 'Choose a response',
	v3_kind_stolen: 'Stolen vehicle',
	v3_kind_pursuit: 'Pursuit',
	v3_kind_echallan: 'E-challan',
	v3_kind_corridor: '108 corridor request',
	v3_kind_decision: 'Decision',

	// titles that carry their mark in a chip beside them (masked, with a lock, until an officer is named)
	v3_title_stolen: 'Authorise pursuit',
	v3_title_stolen_after: 'Dismiss earlier sightings',
	v3_title_pursuit: 'Open the pursuit',
	v3_title_echallan: 'Decide the e-challan',
	v3_title_echallan_stolen: 'Reject the e-challan',
	v3_why_reads: (k: unknown, ago: unknown) => `Read ${s(k)} times, the latest ${s(ago)}.`,
	v3_why_reads_road: (k: unknown, ago: unknown, road: unknown) => `Read ${s(k)} times, the latest on ${s(road)} ${s(ago)}.`,
	v3_fact_recommended: 'recommended',

	// the facts (value + label)
	v3_fact_congestion: 'congestion ahead',
	v3_fact_hold: 'longest hold',
	v3_fact_convoy_to: (j: unknown) => `convoy to ${s(j)}`,
	v3_fact_speed: 'convoy speed',
	v3_fact_reads: 'camera reads',
	v3_fact_last_read: 'since the last read',
	v3_fact_credibility: 'credibility',
	v3_fact_golden: 'golden hour left',
	v3_fact_unit: 'ambulance',

	// ── Home: the city pulse ──
	v3_city_green: 'The city is steady',
	v3_city_amber: 'Traffic is building',
	v3_city_red: 'The city is under strain',
	v3_city_black: 'Roads are at a standstill',
	v3_city_unknown: 'City band not known yet',
	v3_band_since: (b: unknown, at: unknown) => `Band ${s(b)} since ${s(at)}`,
	v3_band_stale: 'The band engine is not answering',
	v3_updated: (at: unknown) => `updated ${s(at)} IST`,
	v3_band_green: 'green',
	v3_band_amber: 'amber',
	v3_band_red: 'red',
	v3_band_black: 'black',
	v3_band_ring: (b: unknown) => `City band ${s(b)}`,
	v3_pulse_aria: 'City at a glance',

	v3_stat_decisions: (k: unknown) => pl(k, 'decision needs you', 'decisions need you'),
	v3_stat_soonest: (at: unknown) => `soonest in ${s(at)}`,
	v3_stat_oldest: (at: unknown) => `oldest waiting ${s(at)}`,
	v3_stat_none_waiting: 'nothing is waiting',
	v3_stat_live: (k: unknown) => pl(k, 'live operation', 'live operations'),
	v3_stat_live_movements: (k: unknown) => `${s(k)} protected ${pl(k, 'movement', 'movements')}`,
	v3_stat_live_pursuits: (k: unknown) => `${s(k)} ${pl(k, 'pursuit', 'pursuits')}`,
	v3_stat_live_none: 'no live operations',
	v3_stat_reported: (k: unknown) => pl(k, 'reported event', 'reported events'),
	v3_stat_rep_official: (k: unknown) => `${s(k)} official`,
	v3_stat_rep_news: (k: unknown) => `${s(k)} news`,
	v3_stat_rep_unverified: (k: unknown) => `${s(k)} unverified`,
	v3_stat_rep_none: 'none reported',
	v3_stat_watch: (k: unknown) => pl(k, 'watchlisted vehicle', 'watchlisted vehicles'),
	v3_stat_watch_masked: 'plates hidden until an officer is named',
	v3_stat_watch_named: (who: unknown) => `plates shown to ${s(who)}`,

	v3_sys_cameras: (a: unknown, k: unknown) => `${s(a)} of ${s(k)} cameras answering`,
	v3_sys_cameras_none: 'No camera feed yet',
	v3_sys_sim: (k: unknown) => `Traffic simulated on ${s(k)} roads`,
	v3_sys_mixed: (pct: unknown) => `Traffic partly simulated (${s(pct)}% synthetic)`,
	v3_sys_live: 'Traffic from live feeds',
	v3_sys_details: 'System details',
	v3_sys_down: (feed: unknown, at: unknown) => `${s(feed)} not answering since ${s(at)}`,
	v3_sys_down_now: (feed: unknown) => `${s(feed)} not answering`,
	v3_sys_still: 'Decisions still work',
	v3_sys_retry: 'Retry',
	v3_feed_city: 'The city picture',
	v3_feed_events: 'The events feed',

	// ── Home: the rails ──
	v3_rail_decide: 'Needs your decision',
	v3_rail_decide_sub: 'soonest deadline first',
	v3_rail_decide_more: 'Review all in order',
	v3_rail_live: 'Live operations',
	v3_rail_live_more: 'See them on the map',
	v3_rail_reported: 'Reported in the city',
	v3_rail_reported_sub: 'from news, official alerts and public reports, about places, never people',
	v3_rail_reported_more: 'All reports',
	v3_rail_planned: 'Coming up',
	v3_rail_planned_sub: 'next 72 hours',
	v3_rail_planned_more: 'Plan a movement',
	v3_rail_prev: 'Scroll back',
	v3_rail_next: 'Scroll on',
	v3_rail_count: (k: unknown) => `${s(k)} in this list`,
	v3_rail_empty_decide: 'Nothing needs your decision.',
	v3_rail_empty_reported: 'Nothing reported right now.',
	v3_rail_empty_planned: 'Nothing planned in the next 72 hours.',
	v3_rail_loading: 'Loading',

	// ── Home: cards ──
	v3_card_left: (at: unknown) => `${s(at)} left`,
	v3_card_waiting: (at: unknown) => `Waiting ${s(at)}`,
	v3_card_review: 'Review',
	v3_card_open: 'Open',
	v3_card_decision_aria: (kind: unknown, title: unknown, when: unknown) => `Decision, ${s(kind)}: ${s(title)}, ${s(when)}`,
	v3_card_aria: (kind: unknown, title: unknown) => `${s(kind)}: ${s(title)}`,
	v3_op_live: 'Live',
	v3_op_open: 'Open',
	v3_op_active: 'Active',
	v3_op_movement: (c: unknown) => `Protected movement, class ${s(c)}`,
	v3_op_pursuit: 'Vehicle pursuit',
	v3_op_event: 'Corridor event',
	v3_op_progress: (pct: unknown) => `${s(pct)}% of the route done`,
	v3_op_next: (j: unknown, at: unknown) => `Next: ${s(j)} in ${s(at)}`,
	v3_op_eta: (at: unknown) => `Arrives ${s(at)} IST`,
	v3_op_speed: (k: unknown) => `${s(k)} km/h`,
	v3_op_since: (at: unknown) => `Since ${s(at)} IST`,
	v3_op_last_read: (ago: unknown) => `Last read ${s(ago)} ago`,
	v3_op_decision_waits: (k: unknown) => `${s(k)} ${pl(k, 'decision waits', 'decisions wait')}`,
	v3_rep_official: 'Official',
	v3_rep_news: 'News-reported',
	v3_rep_unverified: 'Unverified',
	v3_rep_confirmed: 'Confirmed by an officer',
	v3_cred: 'Credibility',
	v3_cred_tip: (v: unknown) => `Credibility ${s(v)}: how far the sources agree, not whether it happened`,
	v3_rep_note_response: 'Response proposed',
	v3_rep_note_verify: 'Verify before acting',
	v3_rep_note_official: 'From an official source',
	v3_rep_kind: 'Reported situation',
	v3_when_today: (at: unknown) => `Today ${s(at)}`,
	v3_when_tomorrow: (at: unknown) => `Tomorrow ${s(at)}`,
	v3_when_now: 'Starting now',
	v3_plan_approved: 'Plan approved',
	v3_plan_planning: 'Plan in progress',
	v3_plan_window: (a: unknown, b: unknown) => `${s(a)} to ${s(b)} IST`,

	// provenance (one tag per card)
	v3_prov_emulated: 'Emulated',
	v3_prov_simulated: 'Simulated',
	v3_prov_test: 'Test',
	v3_prov_emulated_tip: 'From the scenario emulator. Not a field reading.',
	v3_prov_simulated_tip: 'Its figures come from a simulated traffic feed.',
	v3_prov_test_tip: 'Rehearsal or test data.',
	v3_masked: 'registration mark masked',
	v3_redact_name: 'name withheld',
	v3_redact_age: 'age withheld',
	v3_redact_other: 'detail withheld',

	// ── Home: the footer and the map credit ──
	v3_rule_vehicles: 'Vehicles only. Plates stay masked until a duty officer is named.',
	v3_rule_ai: 'The assistant proposes. A named officer decides every action.',
	v3_policies: 'Policies',
	v3_maps_credit: 'Maps',
	v3_map_alt: (place: unknown) => `Map of ${s(place)}`,
	v3_map_alt_plain: 'Map of the place',
	v3_map_convoy: 'Convoy',
	v3_map_convoy_in: (at: unknown) => `Convoy, ${s(at)} away`,
	v3_map_offline: 'Map tiles not loading: the roads are drawn from the deck’s own network',

	// ── first run ──
	v3_onb_title: 'How Sajag works',
	v3_onb_1: 'Glance: what needs you, what is live, what is coming.',
	v3_onb_2: 'Decide: one card, one button, your name on it.',
	v3_onb_3: 'The assistant proposes. You decide.',
	v3_onb_dismiss: 'Got it',

	// ── the gallery (/v3-gallery) ──
	v3_gal_title: 'V3 design gallery',
	v3_gal_lead: 'The mark, the glyphs, the illustrations and the type scale of the V3 console.',
	v3_gal_mark: 'Mark and wordmark',
	v3_gal_glyphs: (k: unknown) => `Glyphs (${s(k)})`,
	v3_gal_events: 'Event art',
	v3_gal_vehicles: 'Vehicle classes',
	v3_gal_agencies: 'Agency marks',
	v3_gal_empty: 'Empty states',
	v3_gal_onboarding: 'Onboarding',
	v3_gal_type: 'Type scale',
	v3_gal_colour: 'Colour roles',
	v3_gal_sample: 'Hold cross traffic at the crossing',


	// ── kind words and the living city's causes, in the reader's language (Home, Map, object pages) ──
	v3_k_weather_hazard: 'Weather hazard',
	v3_k_road_closure: 'Road closure',
	v3_k_urban_flooding: 'Urban flooding',
	v3_k_flooding: 'Flooding',
	v3_k_waterlogging: 'Waterlogging',
	v3_k_public_conflict: 'Public conflict',
	v3_k_public_gathering: 'Public gathering',
	v3_k_public_disorder: 'Public disorder',
	v3_k_fire: 'Fire',
	v3_k_unrest: 'Unrest',
	v3_k_general_news: 'General news',
	v3_k_procession: 'Procession',
	v3_k_reported_crime: 'Reported crime',
	v3_k_crime_incident: 'Crime incident',
	v3_k_road_accident: 'Road accident',
	v3_k_accident: 'Accident',
	v3_k_hazard: 'Hazard',
	v3_k_infra_failure: 'Infrastructure failure',
	v3_k_infrastructure_failure: 'Infrastructure failure',
	v3_k_traffic_jam: 'Traffic jam',
	v3_k_tree_fall: 'Tree fall',
	v3_k_road_blocked: 'Road blocked',
	v3_k_live_wire: 'Live wire',
	v3_k_work_zone: 'Work zone',
	v3_k_mass_gathering: 'Mass gathering',
	v3_k_egress_surge: 'Egress surge',
	v3_cause_k_market_spillover: 'Market spill-over',
	v3_cause_k_signal_fault: 'Signal fault',
	v3_cause_k_breakdown: 'Vehicle breakdown',
	v3_cause_k_waterlogging: 'Waterlogging',
	v3_cause_k_school_egress: 'School rush',
	v3_cause_k_office_rush: 'Office rush',
	v3_cause_k_it_shift_change: 'Tech-park shift change',
	v3_cause_k_festival_crowd: 'Festival crowd',
	v3_cause_market_spillover: 'Hawkers and shoppers spill off the footpath onto the carriageway',
	v3_cause_signal_fault: 'A junction signal is dark; a traffic constable holds it on manual control',
	v3_cause_breakdown: 'A broken-down vehicle blocks a lane until the tow clears it',
	v3_cause_waterlogging: 'Rain waterlogs a low-lying stretch; one lane is barricaded until it drains',
	v3_cause_school_egress: 'School run: pool cars, school buses and parents crowd the approach',
	v3_cause_office_rush: 'Office-hour rush into or out of the business district; turns are held in waves',
	v3_cause_it_shift_change: 'A tech-park shift change: office cabs and buses queue at the campus gates',
	v3_cause_festival_crowd: 'Festival crowds overflow the footpaths; vehicles are held back from the crowd',
	v3_op_cause: (v: unknown) => `Emulated city cause: ${s(v)}`,
	v3_rep_news_withheld: 'A news report about this place: open it for the source',
	v3_text_in_mr: (official: unknown) => (official ? 'Official text in Marathi: open it to read the original' : 'Reported in Marathi: open it to read the original'),
	v3_text_in_hi: (official: unknown) => (official ? 'Official text in Hindi: open it to read the original' : 'Reported in Hindi: open it to read the original'),
	v3_text_original_mr: 'Original text, in Marathi (not translated)',
	v3_text_original_hi: 'Original text, in Hindi (not translated)',
	v3_text_brief_mr: 'In Marathi: open it for the original text',
	v3_text_brief_hi: 'In Hindi: open it for the original text',
	v3_ech_speed: (m: unknown, v: unknown, lim: unknown) => `e-challan recommended: ${s(m)} read at ${s(v)} km/h in a ${s(lim)} km/h segment`,
	v3_ech_red: (m: unknown, j: unknown) => `e-challan recommended: ${s(m)} crossed junction ${s(j)} on red`,
	v3_req_108_control: '108 control',
	v3_req_108_control_emu: '108 control (emulated)',
	v3_road_primary: 'Primary road',
	v3_road_secondary: 'Secondary road',
	v3_road_trunk: 'Trunk road',
	v3_road_tertiary: 'Tertiary road',
	v3_road_residential: 'Residential road',
	v3_road_motorway: 'Expressway',
} satisfies V3Pack;

export type V3Key = keyof typeof en;

registerPack('en', en);

/** For tests and the gallery: the key list and the packs. */
export const V3_PACK_KEYS: readonly V3Key[] = Object.keys(en) as V3Key[];
export const V3_PACKS: Record<string, V3Pack> = { en };

/** Register one language chunk (lib/i18n/load.ts's landing site; additive, first registration wins). */
export function adopt(code: 'hi' | 'mr', pack: V3Pack): void {
	V3_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (the deck's FIX-E-PERF2 pattern): HI and MR live only in ./packs.v3.hi.ts and
 * ./packs.v3.mr.ts. The server render and every non-production run register both before this module
 * finishes evaluating; the production browser awaits the document's language and loads the other on
 * the first switch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.v3.hi')).hi);
	adopt('mr', (await import('./packs.v3.mr')).mr);
} else {
	await langChunks('packs.v3', (code) =>
		code === 'hi' ? import('./packs.v3.hi').then((c) => adopt('hi', c.hi)) : import('./packs.v3.mr').then((c) => adopt('mr', c.mr)),
	);
}
