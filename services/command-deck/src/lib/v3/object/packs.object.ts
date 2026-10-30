/**
 * The object-page string pack (V3-SPEC §6.3, §6.4, §7.8) — every string /o/<urn> prints, in EN here and HI /
 * MR in ./packs.object.hi.ts and ./packs.object.mr.ts (complete for every key: tests/object-page.unit.mjs
 * checks it). Registered additively through registerPack(); no existing pack is edited. Every key starts
 * with `obj_` (the `v3_` prefix belongs to packs.v3, which this phase may not edit).
 *
 * Copy rules (v2 §11 + V3 §7.6): sentence case, at most one " · " per string (a run-time join puts the
 * separators between facts), say what happens, what does not, and how sure. Numbers and times stay in
 * Latin digits in all three languages.
 */
import { registerPack } from '$lib/i18n/strings';
import { langChunks } from '$lib/i18n/load';

type Fn = (...args: unknown[]) => string;
type ObjPack = Record<string, string | Fn>;

const s = (v: unknown) => String(v ?? '');
const n = (v: unknown) => Number(v);

const en = {
	// ── the top bar, per kind ──
	obj_screen_osint_event: 'Reported event',
	obj_screen_event: 'Corridor event',
	obj_screen_vehicle: 'Vehicle',
	obj_screen_place: 'Named place',
	obj_screen_convoy: 'Operation',
	obj_screen_junction: 'Junction',
	obj_screen_camera: 'ANPR camera',
	obj_screen_dispatch: 'Unit request',
	obj_screen_recommendation: 'Recommendation',
	obj_screen_sighting: 'Camera read',
	obj_screen_other: 'Details',
	obj_sub_osint_event: 'Open-source report · about a place, never a person',
	obj_sub_event: 'A corridor event and what it needs',
	obj_sub_vehicle: 'Vehicles only · marks masked until an officer is named',
	obj_sub_place: 'A place in the city gazetteer',
	obj_sub_convoy: 'A protected movement and its route',
	obj_sub_junction: 'A junction and its signals',
	obj_sub_camera: 'A roadside camera · it reads vehicles, never people',
	obj_sub_dispatch: 'A unit request and where it stands',
	obj_sub_recommendation: 'A rule proposes · a named officer decides',
	obj_sub_sighting: 'One lawful camera read of a vehicle',
	obj_sub_other: 'Everything Sajag knows about it',

	// ── the hero ──
	obj_crumb_home: 'Home',
	obj_open_map: 'Open in the map',
	obj_hero_reported: 'Reported here',
	obj_hero_here: 'Here',
	obj_hero_last_read: 'Last lawful read',
	obj_hero_matched: (p: unknown) => `place matched with ${s(p)} % confidence`,
	obj_hero_area: 'district level, not an exact place',
	obj_hero_alt: (title: unknown) => `Map of the place: ${s(title)}`,
	obj_maps_credit: 'Map data',

	// ── the title bar ──
	obj_reported_at: (when: unknown) => `reported ${s(when)}`,
	obj_cred: (v: unknown) => `Credibility ${s(v)}`,
	obj_tag_response_waits: 'Response waits for you',
	obj_tag_decision_waits: 'A decision waits for you',
	obj_prov_emulated: 'Emulated',
	obj_prov_simulated: 'Simulated',
	obj_prov_test: 'Test',
	obj_prov_unverified: 'Unverified',
	obj_prov_news: 'News-reported',
	obj_prov_official: 'Official',
	obj_prov_confirmed: 'Confirmed',
	obj_prov_emulated_tip: 'Made by the scenario emulator, not by a real sensor',
	obj_prov_simulated_tip: 'Its figures come from a simulated traffic feed',
	obj_prov_test_tip: 'A rehearsal or test record',
	obj_prov_unverified_tip: 'Open-source and not yet backed by any publisher or official',
	obj_prov_news_tip: 'Reported by news publishers; no official source yet',
	obj_prov_official_tip: 'From an official source, by its tier and never by its web address',
	obj_prov_confirmed_tip: 'Confirmed by an officer',
	obj_act_review_response: 'Review the response',
	obj_act_review: 'Review and decide',
	obj_act_ask: 'Ask about it',
	obj_act_more: 'More actions',
	obj_act_copy: 'Copy link',
	obj_act_copied: 'Link copied. It names the record only, never a registration mark.',
	obj_act_copy_failed: 'The browser did not allow copying.',
	obj_act_analyst: 'Open in Analyst',
	obj_act_record: 'Show everything on record',

	// ── ask about it (the assistant, read only) ──
	obj_ask_by: 'Assistant · read only',
	obj_ask_working: 'Working it out…',
	obj_ask_failed: 'The assistant could not answer just now. Nothing was changed.',
	obj_ask_stop: 'Stop',
	obj_ask_close: 'Close',
	obj_ask_masked: 'Registration marks stay masked until a duty officer is named.',
	obj_ask_prompt:
		'Explain this for the duty officer: what it is, its current state and source, what the city picture links it to, and what (if anything) waits on a named officer. Use names and labels, never ids.',

	// ── tabs ──
	obj_tabs_label: 'About this',
	obj_tab_overview: 'Overview',
	obj_tab_sources: 'Sources',
	obj_tab_reads: 'Reads',
	obj_tab_pursuit: 'Pursuit',
	obj_tab_timeline: 'Timeline',
	obj_tab_nearby: 'Nearby',
	obj_tab_record: 'Record',

	// ── a reported situation: what, how sure, what it may affect ──
	obj_reported_h: 'What is reported',
	obj_redact_note: 'Names and ages are removed from every report before it is stored. Sajag records what happened at a place, never who was involved.',
	obj_no_summary: 'No summary was kept for this report.',
	obj_sure_h: 'How sure are we',
	obj_gauge_aria: (v: unknown) => `Credibility ${s(v)} of 1`,
	obj_chk_pubs: (k: unknown) => (n(k) === 2 ? 'Two independent publishers say the same thing' : `${s(k)} independent publishers say the same thing`),
	obj_chk_pubs_one: 'Only one publisher so far',
	obj_chk_place: (where: unknown, p: unknown) => `Place matched to ${s(where)}, ${s(p)} % confidence`,
	obj_chk_place_loose: (where: unknown, p: unknown) => `Place matched only loosely to ${s(where)}, ${s(p)} % confidence`,
	obj_chk_place_area: 'Only the district is known, not the exact place',
	obj_chk_place_none: 'The place is not matched yet',
	obj_chk_official_yes: 'An official source reports it',
	obj_chk_official_no: 'No official source yet (police, 108, municipal)',
	obj_chk_cross_yes: 'Another kind of source agrees (a camera or sensor)',
	obj_chk_cross_no: 'No other kind of source agrees (no camera or sensor report)',
	obj_verif: 'Verification',
	obj_ladder_unverified: 'Unverified',
	obj_ladder_news: 'News-reported',
	obj_ladder_official: 'Official',
	obj_cred_note: 'Credibility says how far the sources agree. It does not say the report is true; an officer decides what to do with it.',
	obj_affect_h: 'What it may affect',
	obj_affect_note: 'Flagged where the reported place meets live operations right now. These are flags, not forecasts.',
	obj_affect_none: 'Nothing live runs through this place right now.',
	obj_context_note: 'Context, not corroboration: an alert in effect for the district is listed apart and never counted.',

	// ── sources ──
	obj_src_h: 'Who reported it',
	obj_src_link_withheld: 'Link not kept: it may name a person',
	obj_src_cached: 'cached sample',
	obj_src_official_h: 'Official sources',
	obj_src_none_yet: 'none yet',
	obj_src_official_hint: 'An official alert, if one arrives, is linked here and raises the verification to Official.',
	obj_src_open: 'Open the official record',
	obj_src_snapshot: 'The per-source details load with the full report.',
	obj_src_context_h: 'In effect for the district',

	// ── key facts ──
	obj_facts_h: 'Key facts',
	obj_f_place: 'Place',
	obj_f_road: 'Road',
	obj_f_when: 'When',
	obj_f_kind: 'Kind',
	obj_f_status: 'Status',
	obj_f_sources: 'Sources',
	obj_f_also: (k: unknown) => `also ${s(k)}`,
	obj_status_new: 'New situation, not yet an event',
	obj_status_promoted: 'Promoted to a corridor event',
	obj_status_corroborates: 'Adds to a live event',
	obj_status_seen: 'Reported, not yet linked to an event',
	obj_src_publishers: (k: unknown) => (n(k) === 1 ? '1 publisher' : `${s(k)} publishers`),
	obj_src_official_n: (k: unknown) => `${s(k)} official`,
	obj_figs_h: 'At a glance',

	// ── decisions ──
	obj_cta_left: (t: unknown) => `${s(t)} left`,
	obj_cta_waiting: (d: unknown) => `waiting ${s(d)}`,
	obj_cta_dss: 'Decision support',
	obj_cta_decision: 'Decision',
	obj_cta_recommended: (label: unknown) => `Recommended: ${s(label)}`,
	obj_cta_ifnot: 'If no one answers, the current plan is kept.',
	obj_cta_touches: 'Touches this record',
	obj_dss_h: 'Decision support',

	// ── activity, nearby, record ──
	obj_recent_h: 'Recent activity',
	obj_tl_h: 'What happened, in order',
	obj_tl_empty: 'No activity is recorded for this yet.',
	obj_tl_all: 'Full timeline',
	obj_tl_now: 'now',
	obj_near_h: 'Linked to this',
	obj_near_empty: 'Nothing else is linked to this yet.',
	obj_near_graph: 'Open in the graph',
	obj_near_more: (k: unknown) => `${s(k)} more in Analyst`,
	obj_rec_h: 'Everything on record',
	obj_rec_sub: 'Every field the Analyst inspector shows, with where it came from.',
	obj_rec_system_show: 'Show system fields',
	obj_rec_system_hide: 'Hide system fields',

	// ── a vehicle ──
	obj_veh_h: 'The vehicle',
	obj_veh_title_watch: 'Watchlisted vehicle',
	obj_veh_basis: 'Lawful basis',
	obj_veh_retention: (d: unknown) => (n(d) === 1 ? 'Kept 1 more day' : `Kept ${s(d)} more days`),
	obj_veh_last: 'Last lawful read',
	obj_veh_masked: 'Registration mark masked until a duty officer is named.',
	obj_veh_named: 'Shown in full to the named duty officer; every view is recorded.',
	obj_reads_h: 'Lawful reads',
	obj_reads_note: 'Only reads with a lawful basis are listed; any other read is withheld.',
	obj_reads_empty: 'No lawful reads are listed for this vehicle.',
	obj_read_at: (cam: unknown) => `at ${s(cam)}`,
	obj_pursuit_none: 'No pursuit is open for this vehicle.',

	// ── an event, an operation, a place ──
	obj_ev_actions_h: 'What you can do',
	obj_ev_actions_note: 'Each step is recorded under the named duty officer.',
	obj_op_progress: (p: unknown) => `${s(p)} % of the route done`,
	obj_op_next: (name: unknown) => `Next: ${s(name)}`,
	obj_op_h: 'Progress',
	obj_place_h: 'The place',
	obj_place_reports_h: 'Reported here',
	obj_place_reports_none: 'No open-source report names this place right now.',

	// ── states ──
	obj_withheld_h: 'Withheld',
	obj_withheld: 'Withheld: no lawful basis to show individual reads.',
	obj_notfound_h: 'Not in the city picture',
	obj_notfound: 'Sajag has no record of this right now. It may have closed, or the link may be old.',
	obj_bad_h: 'Not a record',
	obj_bad: 'This link does not name anything Sajag keeps.',
	obj_down: 'The city feed is not answering. Showing what was last known.',
	obj_loading: 'Loading…',
	obj_back_home: 'Back to Home',

	// ── rule notes ──
	obj_rule_osint: 'A reported situation, kept for response. Sajag never identifies people, and no news or social link is stored or shown.',
	obj_rule_vehicle: 'Vehicles only. A mark is shown in full only to a named duty officer, and every lookup is recorded.',
	obj_rule_default: 'The assistant proposes; a named officer decides. Every action here is recorded.',
} satisfies ObjPack;

export type ObjKey = keyof typeof en;

registerPack('en', en);

/** For tests: the key list and the packs. */
export const OBJ_PACK_KEYS: readonly ObjKey[] = Object.keys(en) as ObjKey[];
export const OBJ_PACKS: Record<string, ObjPack> = { en };

/** Register one language chunk (lib/i18n/load.ts's landing site; additive, first registration wins). */
export function adopt(code: 'hi' | 'mr', pack: ObjPack): void {
	OBJ_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (the deck's FIX-E-PERF2 pattern, as packs.v3): HI and MR live only in their own modules. The
 * server render and every non-production run register both before this module finishes evaluating; the
 * production browser awaits the document's language and loads the other on the first switch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.object.hi')).hi);
	adopt('mr', (await import('./packs.object.mr')).mr);
} else {
	await langChunks('packs.object', (code) =>
		code === 'hi' ? import('./packs.object.hi').then((c) => adopt('hi', c.hi)) : import('./packs.object.mr').then((c) => adopt('mr', c.mr)),
	);
}
