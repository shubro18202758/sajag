/**
 * The workspace views' string pack (EN / HI / MR): the Explorer, saved views
 * and watches, the Histogram, the ObjectTable and its CSV export, and the
 * City vitals card and Info tab (UI-S2X). Registered additively through
 * registerPack(); the core packs stay untouched. Every key starts `vw_`.
 *
 * EN is sentence case, with no ALL-CAPS word outside the acronym allowlist,
 * at most one " · " per string, and section titles of at most 32 characters
 * (tests/copy-lint.mjs, target file style-lint.targets/s2x.json). HI and MR
 * are complete for every key (tests/views.unit.mjs). Copy says only what the
 * system does: exports and saved views are always masked; a watch never
 * mutes an interrupt; nothing here approves, fines or unmasks.
 */
import { registerPack } from './strings';
import { langChunks } from './load';

type Fn = (...args: unknown[]) => string;
type Pack = Record<string, string | Fn>;

const one = (v: unknown) => Number(v) === 1;
/** A kind's plural, mid-sentence ("Reported events" → "reported events"; an acronym stays as it is). */
const lc = (v: unknown) => {
	const s = String(v ?? '');
	return /^[A-Z][a-z]/.test(s) ? `${s[0].toLowerCase()}${s.slice(1)}` : s;
};

const en = {
	// ── the left dock's tabs (registered by the pages) ───────────────────
	vw_tab_explorer: 'Explorer',
	vw_tab_histogram: 'Histogram',
	vw_tab_info: 'Info',

	// ── provenance words ─────────────────────────────────────────────────
	vw_src_live: 'Live',
	vw_src_emulated: 'Emulated',
	vw_src_simulated: 'Simulated',
	vw_src_test: 'Test',
	vw_src_osint: 'Open-source',

	// ── Explorer ─────────────────────────────────────────────────────────
	vw_ex_active_events: 'Active events',
	vw_ex_object_types: 'Object types',
	vw_ex_none: 'The city picture holds no objects yet.',
	vw_ex_open: (n: unknown) => `${n} open`,
	vw_ex_watchlist: 'on watchlist',
	vw_ex_unverified: (n: unknown) => `${n} unverified`,
	vw_ex_state_pending: (n: unknown) => `${n} pending`,
	vw_ex_state_requested: (n: unknown) => `${n} requested`,
	vw_ex_state_proposed: (n: unknown) => `${n} proposed`,
	vw_ex_state_active: (n: unknown) => `${n} active`,
	vw_ex_state_en_route: (n: unknown) => `${n} en route`,
	vw_ex_state_on_scene: (n: unknown) => `${n} on scene`,

	// ── saved views ──────────────────────────────────────────────────────
	vw_sv_title: 'Saved views',
	vw_sv_save: 'Save the current view',
	vw_sv_placeholder: 'Name this view',
	vw_sv_save_btn: 'Save',
	vw_sv_empty: 'No saved views. Save the current view to come back to it.',
	vw_sv_edited: 'edited',
	vw_sv_more: 'View options',
	vw_sv_open: 'Open',
	vw_sv_rename: 'Rename',
	vw_sv_delete: 'Delete',
	vw_sv_masked_hint: 'Saved in this browser only. A saved view always masks registration marks, whoever is on duty.',

	// ── watches ──────────────────────────────────────────────────────────
	vw_w_title: 'Watches',
	vw_w_decision: 'Decision needed',
	vw_w_reads: 'Watchlist reads, 24 h',
	vw_w_add: 'Add a watch',
	vw_w_add_selection: 'Watch the selected object',
	vw_w_add_selection_off: 'Select an object first',
	vw_w_add_filters: 'Watch the current filters',
	vw_w_add_filters_off: 'Add a filter first',
	vw_w_remove: 'Remove this watch',
	vw_w_hint: 'This list counts what changes for each watched object or filtered set. A watch never mutes an interrupt.',
	vw_w_empty: 'Watch an object or a filtered set to count its changes here.',
	vw_w_refused: 'This watch could not be saved.',
	vw_w_filters_title: 'Filtered set',
	vw_w_count_subject: (n: unknown) => (one(n) ? '1 feed row about it in 24 h' : `${n} feed rows about it in 24 h`),
	vw_w_count_filters: (n: unknown) => (one(n) ? '1 object matches now' : `${n} objects match now`),

	// ── Histogram ────────────────────────────────────────────────────────
	vw_h_rows: (n: unknown) => (one(n) ? '1 row in the table' : `${n} rows in the table`),
	vw_h_values: (n: unknown) => (one(n) ? '1 value' : `${n} values`),
	vw_h_kind: 'Kind',
	vw_h_state: 'State',
	vw_h_source: 'Source',
	vw_h_hour: 'Hour (IST)',
	vw_h_road: 'Road',
	vw_h_camera: 'Camera',
	vw_h_filter_to: 'Filter to',
	vw_h_filter_out: 'Filter out',
	vw_h_clear: 'Clear',
	vw_h_select_first: 'Select a value first',
	vw_h_out_inexact: 'Some rows here have no value, so they cannot be filtered out exactly. Use Filter to.',
	vw_h_show_more: (n: unknown) => `Show ${n} more`,
	vw_h_show_less: 'Show fewer',
	vw_h_missing: (n: unknown) => (one(n) ? '1 row without a value' : `${n} rows without a value`),
	vw_h_missing_time: (n: unknown) => (one(n) ? '1 row without a time' : `${n} rows without a time`),
	vw_h_missing_road: (n: unknown) => (one(n) ? '1 row records no road of its own' : `${n} rows record no road of their own`),
	vw_h_missing_road_hint:
		'A row counts under a road only when it records that road itself, the same road a filter keeps. The Place column also shows where a camera stands, so it can name a road for a row this group leaves out.',
	vw_h_empty: 'Nothing to count',
	vw_h_empty_hint: 'Select an object, explore a kind or search to fill the table.',
	vw_h_filtered: (label: unknown) => `Filtered: ${label}`,
	vw_h_osint_hint: 'The source filter keeps every open-source report, whatever its verification state.',
	vw_h_label_not: (w: unknown) => `Not ${w}`,
	vw_h_label_more: (n: unknown) => `+${n}`,
	vw_h_no_state: 'No verification state',
	vw_h_parts: (label: unknown) => `${label} by verification state`,

	// ── ObjectTable ──────────────────────────────────────────────────────
	vw_t_col_object: 'Object',
	vw_t_col_type: 'Type',
	vw_t_col_state: 'State',
	vw_t_col_time: 'Time (IST)',
	vw_t_col_place: 'Place',
	vw_t_col_speed: 'Speed',
	vw_t_col_links: 'Links',
	vw_t_col_source: 'Source',
	vw_t_linked: (n: unknown) => (one(n) ? 'and its 1 linked object' : `and its ${n} linked objects`),
	vw_t_rows: (n: unknown) => (one(n) ? '1 row' : `${n} rows`),
	vw_t_filter_urns: 'search results',
	vw_t_filter_kind: 'kind filter',
	vw_t_filter_state: 'state filter',
	vw_t_filter_source: 'source filter',
	vw_t_filter_hour: 'hour filter',
	vw_t_filter_road: 'road filter',
	vw_t_filter_camera: 'camera filter',
	vw_t_results: 'Search results',
	vw_t_all_objects: 'Every object',
	vw_t_selected: (n: unknown) => `${n} selected`,
	vw_t_columns: 'Columns',
	vw_t_export: 'Export',
	vw_t_export_hint: 'Download these rows as a .csv file. Registration marks are always masked; provenance and verification columns are kept.',
	vw_t_empty: 'No objects here. Select an object, explore a kind or search.',
	vw_t_caption: 'Objects',
	vw_t_window_hint: 'Rows outside the time window are faded, not removed. Live objects and infrastructure never fade.',
	vw_t_links_hint: 'Objects one link away',
	vw_t_source_hint: 'Where each row comes from. Live rows are unmarked.',
	vw_t_objects: 'Objects',
	vw_t_empty_kind: (kinds: unknown, subject: unknown) => `No ${lc(kinds)} are linked to ${subject}`,
	vw_t_empty_kind_hint: (kinds: unknown) => `The table lists the selection and its links. Clear the selection to see all ${lc(kinds)}.`,
	vw_t_clear_selection: 'Clear the selection',
	vw_t_credibility: (c: unknown) => `credibility ${c}`,
	vw_t_credibility_hint: 'Credibility of the open-source report, 0 to 1. It rises only when independent sources agree.',

	// ── CSV export ───────────────────────────────────────────────────────
	vw_csv_urn: 'Object ID',
	vw_csv_speed: 'Speed (km/h)',
	vw_csv_provenance: 'Provenance',
	vw_csv_verification: 'Verification',
	vw_csv_credibility: 'Credibility',
	vw_csv_test: 'Test',

	// ── City vitals: the card ────────────────────────────────────────────
	vw_v_title: 'City',
	vw_v_as_of: 'As of',
	vw_v_open_events: 'Open events',
	vw_v_open_events_hint: 'Corridor events planned, approved or running',
	vw_v_decisions: 'Decisions waiting',
	vw_v_decisions_hint: 'Decisions waiting for a named officer: the same count as the Inbox',
	vw_v_decisions_hint_registry: 'Decisions waiting for a named officer, counted from the city picture',
	vw_v_watchlisted: 'Watchlisted vehicles',
	vw_v_watchlisted_hint: 'Vehicles on the watchlist now: the same count as the Explorer',
	vw_v_cameras: 'Cameras answering',
	vw_v_cameras_hint: 'Cameras the camera registry lists as active, of all registered cameras',
	vw_v_anomalies: 'Feed anomalies, 15 min',
	vw_v_anomalies_hint: 'Roads with a feed anomaly in the last 15 min',
	vw_v_reported: 'Reported events',
	vw_v_reported_hint: 'Open-source reports about places in the city. Each carries its verification state.',
	vw_v_traffic_feed: 'Traffic feed',
	vw_v_live: 'Live',
	vw_v_replay_note: 'Live data; the replay shows the tape only',

	// ── City vitals: the Info tab ────────────────────────────────────────
	vw_i_title: 'City vitals',
	vw_i_objects: (n: unknown) => (one(n) ? '1 object' : `${n} objects`),
	vw_i_registry_hint: 'Objects in the city picture, and its age',
	vw_i_posture: 'Posture',
	vw_i_band_unknown: 'Unknown',
	vw_i_age_reading: (a: unknown) => `read ${a} ago`,
	vw_i_age_transition: (a: unknown) => `changed ${a} ago`,
	vw_i_stale: 'Stale',
	vw_i_stale_hint: 'The newest reading is over 10 min old',
	vw_i_stale_since: (at: unknown) => `Engine poll failing since ${at}`,
	vw_i_stale_plain: 'Engine poll failing',
	vw_i_held: (d: unknown, at: unknown) => `Held ${d} · since ${at}`,
	vw_i_posture_city: 'City band',
	vw_i_posture_writer: 'The band the signal writer acts on',
	vw_i_posture_none: 'No band reading yet',
	vw_i_events: 'Events',
	vw_i_events_none: 'No corridor events',
	vw_i_active: (n: unknown) => `${n} active`,
	vw_i_decisions: 'Decisions waiting',
	vw_i_decisions_records: (n) => (Number(n) === 1 ? '1 decision in the Inbox. The rows count the records behind it.' : `${String(n)} decisions in the Inbox. The rows count the records behind them.`),
	vw_i_decide: 'Decide',
	vw_i_escorts: 'Escort proposals',
	vw_i_escorts_hint: 'Route switches, holds and closures the escort proposes. An officer approves every switch.',
	vw_i_echallans: 'E-challans',
	vw_i_echallans_hint: 'Penal recommendations a named officer decides',
	vw_i_stolen: 'Stolen-vehicle sightings',
	vw_i_stolen_hint: 'Evidence only. No fine for a stolen vehicle’s owner; a sighting can only authorise one pursuit.',
	vw_i_withheld: 'Withheld, vehicle stolen',
	vw_i_withheld_hint: 'Penal rows for a vehicle reported stolen: they can only be rejected',
	vw_i_dispatch: 'Dispatch requests',
	vw_i_dispatch_hint: 'Unit requests waiting for a named officer',
	vw_i_ambulance: 'Of which ambulance (108)',
	vw_i_ambulance_hint: 'The 108 requests among the dispatch requests',
	vw_i_units_anpr: 'Units and ANPR',
	vw_i_units: 'Units fielded',
	vw_i_units_sub: (a: unknown, b: unknown) => `${a} en route, ${b} on scene`,
	vw_i_anpr: 'Watchlist hits, 15 min',
	vw_i_anpr_sub: (r: unknown, a: unknown, b: unknown) => `${r} reads, ${a} of ${b} cameras with a read in 15\u00a0min`,
	vw_i_ethics: 'Ethics rails',
	vw_i_ethics_line: 'Vehicles only. No faces. Penalties need a named officer.',
	vw_i_reaper: 'Auto-delete',
	vw_i_retention_k: 'Retention',
	vw_i_healthy: 'Healthy',
	vw_i_failing: 'Failing',
	vw_i_retention: (d: unknown, cap: unknown) => `${d} d, cap ${cap} d`,
	vw_i_last_reap: 'Last run',
	vw_i_reap_removed: (n: unknown) => `Removed ${n}`,
	vw_i_reap_skipped: 'Skipped',
	vw_i_ago: (a: unknown) => `${a} ago`,
	vw_i_lawful: 'Lawful basis',
	vw_i_marks: 'Marks',
	vw_i_marks_masked: 'Masked',
	vw_i_marks_shown: (name: unknown) => `Shown to ${name}`,
	vw_i_signals: 'Signals',
	vw_i_writer: 'Writer',
	vw_i_writer_on: 'Writer on',
	vw_i_writer_off: 'Writer off',
	vw_i_writer_hint: 'The signal-plan writer. A named officer commits every plan.',
	vw_i_twin_k: 'Twin gate',
	vw_i_twin: (n: unknown) => `${n} in flight`,
	vw_i_last_plan: 'Last plan',
	vw_i_plan_applied: (b: unknown) => `Applied ${b ?? ''}`.trim(),
	vw_i_plan_held: (r: unknown) => `Held: ${r}`,
	vw_i_fail_closed: 'fail-closed',
	vw_i_programs: 'Programs',
	vw_i_programs_n: (n: unknown, a: unknown, r: unknown) => `${n}, ${a} amber, ${r} lost`,
	vw_i_signals_pending: 'Waiting for the signal writer',
	vw_i_ai: 'AI tiers',
	vw_i_decider: 'Decision model',
	vw_i_tactical: 'Tactical model',
	vw_i_checks: 'Checks',
	vw_i_connected: 'Connected',
	vw_i_loading: 'Loading',
	vw_i_unreachable: 'Unreachable',
	vw_i_degraded: (r: unknown) => `Degraded: ${r}`,
	vw_i_novelty: (s: unknown) => `Novelty check ${s}`,
	vw_i_cache: (s: unknown) => `routine cache ${s}`,
	vw_i_on: 'on',
	vw_i_off: 'off',
	vw_i_unknown: 'unknown',
	vw_i_brain: 'Brain',
	vw_i_feeds: 'Feeds',
	vw_i_ingest: 'Ingest',
	vw_i_per_min: (n: unknown) => `${n}/min`,
	vw_i_bus_down: 'message bus down',
	vw_i_registry: 'City picture',
	vw_i_roads: 'Roads',
	vw_i_osm_traced: (n: unknown) => `${n} traced from OSM`,
	vw_i_schematic: (n: unknown) => `${n} schematic`,
	vw_i_newest_read: 'Newest read',
	vw_i_emulator: 'Emulator',
	vw_i_run: (id: unknown) => `Run ${id}`,
	vw_i_no_runs: 'No runs',
	vw_i_living: 'Living city',
	vw_i_slots: (n: unknown) => (one(n) ? '1 slot' : `${n} slots`),
	vw_i_waiting: 'Waiting for the first answer',
	vw_i_not_deployed: 'Not deployed',
	vw_i_signin: 'Operator sign-in required',
} satisfies Pack;

export type ViewsKey = keyof typeof en;



registerPack('en', en as Pack);

/** The EN, HI and MR packs (tests assert they carry the same keys). */
export const VIEWS_PACKS: Record<string, Pack> = { en: en as Pack };

/**
 * Register one language chunk (lib/i18n/load.ts's landing site; additive,
 * first registration wins — the core's documented semantics).
 */
export function adopt(code: 'hi' | 'mr', pack: Pack): void {
	VIEWS_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (FIX-E-PERF2): this module's HI and MR strings live ONLY in
 * ./packs.views.hi.ts and ./packs.views.mr.ts. The server render and every non-production
 * run (vite dev, the node test harness) register both before this module
 * finishes evaluating (SSR paints the persisted language). The production
 * browser registers the loader instead and awaits the document's language
 * before this module finishes evaluating — hydration waits for it, so a cold
 * HI/MR load never flashes English — and the other language loads on the
 * first switch (lib/i18n/load.ts). The prod client build folds the condition
 * to its else branch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.views.hi')).hi);
	adopt('mr', (await import('./packs.views.mr')).mr);
} else {
	await langChunks('packs.views', (code) =>
		code === 'hi' ? import('./packs.views.hi').then((c) => adopt('hi', c.hi)) : import('./packs.views.mr').then((c) => adopt('mr', c.mr)),
	);
}
