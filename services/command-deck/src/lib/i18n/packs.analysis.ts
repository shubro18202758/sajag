/**
 * The analysis pack (EN / HI / MR): the timeline, the audit table and the AI
 * trace, the link graph and the replay mode (UI-S4). Registered additively
 * through registerPack(); every key starts with `an_`.
 *
 * EN is sentence case, with no ALL-CAPS word outside the acronym allowlist,
 * at most one " · " per string, and titles of at most 32 characters
 * (tests/copy-lint.mjs, target file style-lint.targets/s4.json). HI and MR
 * are complete for every key (tests/analysis.unit.mjs). Copy says only what
 * the system does: a replay plays a recorded emulator tape and never writes
 * anything; the audit is a view over server rows; masking is not a setting.
 */
import { registerPack } from './strings';
import { langChunks } from './load';

type Fn = (...args: unknown[]) => string;
type Pack = Record<string, string | Fn>;

const n = (v: unknown) => Number(v);
const rows = (v: unknown) => (n(v) === 1 ? 'row' : 'rows');

const en = {
	// ── the dock ───────────────────────────────────────────────────────────
	an_tab_timeline: 'Timeline',
	an_tab_audit: 'Audit',
	an_tab_ai: 'AI trace',
	an_dock_label: 'Time and audit',
	an_live: 'Live',
	an_live_on_tip: 'Following the latest data',
	an_live_off_tip: 'A time window is set. Switch on to return to live.',
	an_play: 'Play from the cursor',
	an_pause: 'Pause',
	an_step_back: 'Step back',
	an_step_fwd: 'Step forward',
	an_range: 'Range',
	an_range_1h: '1 h',
	an_range_6h: '6 h',
	an_range_24h: '24 h',
	an_range_7d: '7 d',
	an_fit: 'Fit to the data',
	an_expand: 'Expand',
	an_compact: 'Compact',
	an_ist: (r: unknown) => `${r} IST`,
	an_replay: 'Replay',
	an_replay_tip: 'Play a recorded emulator tape on its own time axis',
	an_replay_leave: 'Leave replay',
	an_replay_blocked_movement: 'A movement is live',
	an_replay_blocked_pursuit: 'A pursuit is open',

	// ── the timeline ───────────────────────────────────────────────────────
	an_tl_label: 'Timeline of the city feed',
	an_lane_event: 'Events',
	an_lane_enforcement: 'Enforcement',
	an_lane_anpr: 'ANPR reads',
	an_lane_dispatch: 'Dispatch',
	an_lane_signals: 'Signals',
	an_lane_ama: 'Band changes',
	an_lane_brain: 'AI decisions',
	an_tl_rows_in_view: 'Rows in view',
	an_tl_linked: 'Linked',
	an_tl_now: (hm: unknown) => `Now ${hm}`,
	an_tl_older: 'Older rows not loaded',
	an_tl_older_tip: 'The city feed returns its newest 500 rows. Rows older than the oldest loaded one were not read.',
	an_tl_key_officer: 'officer action',
	an_tl_key_linked: 'linked to the selection',
	an_tl_key_watch: 'watchlist read',
	an_tl_key_decision: 'needs a decision',
	an_tl_key_osint: 'open-source report',
	an_tl_bin_tip: (c: unknown, range: unknown) => `${c} ${rows(c)}, ${range} IST`,
	an_tl_bin_linked: (c: unknown) => `${c} linked to the selection`,
	an_tl_brush_hint: 'Drag across the histogram (or Shift-drag anywhere) to set a time window',
	an_tl_grip: 'Drag to move this edge of the window',
	an_tl_tape: 'Tape time',
	an_tl_tape_rows: 'Tape marks',
	an_tl_span: (title: unknown, range: unknown) => `${title}, ${range} IST`,
	an_tl_empty: 'No feed rows in this range',
	an_tl_empty_older: (t: unknown) => `No feed rows in this range. The newest loaded row is from ${t} IST.`,
	an_tl_feed_note: (note: unknown) => `City feed: ${note}`,

	// ── replay ─────────────────────────────────────────────────────────────
	an_rp_emulated: 'Emulated · replay',
	an_rp_emulated_tip: 'A tape is a recording of emulated causes. Nothing it shows happened on the road, and the replay writes nothing.',
	an_rp_run: 'Run',
	an_rp_run_n: (id: unknown) => `Run ${id}`,
	an_rp_run_replay: 'replay',
	an_rp_play: 'Play',
	an_rp_pause: 'Pause',
	an_rp_speed: 'Speed',
	an_rp_recorded: (t: unknown) => `recorded ${t} IST`,
	an_rp_counts: (r: unknown, h: unknown) => `${r} reads, ${h} hits`,
	an_rp_loading: 'Loading the tape',
	an_rp_empty: 'No recorded emulator run to replay',
	an_rp_note: 'Live data stays live: the replay shows the tape only.',
	an_rp_scrubber: 'Replay position in tape seconds',
	an_rp_latest: 'Latest on the tape',

	// ── the audit table and the AI trace ──────────────────────────────────
	an_au_title: 'Audit',
	an_au_time: 'Time',
	an_au_kind: 'Kind',
	an_au_actor: 'Actor',
	an_au_what: 'What happened',
	an_au_object: 'Object',
	an_au_source: 'Source',
	an_au_phase: 'Phase',
	an_au_tier: 'Tier',
	an_au_conf: 'Confidence',
	an_au_all: 'All',
	an_au_officers: 'Officers',
	an_au_machine: 'Machine',
	an_au_system: 'System',
	an_au_filter_label: 'Who acted',
	an_au_scope_label: 'Scope',
	an_au_scope_city: 'City',
	an_au_scope_event: 'Selected event',
	an_au_scope_object: 'Selection',
	an_au_scope_event_none: 'Select an event to follow its audit',
	an_au_view_city: 'Whole city',
	an_au_view_event: (name: unknown) => `Selected event: ${name}`,
	an_au_view_object: (name: unknown) => `Selection: ${name}`,
	an_au_view_legacy: 'Adaptive status (older oracle)',
	an_au_view_none: 'No narrative yet',
	an_au_counts: (shown: unknown, total: unknown) => (n(shown) < n(total) ? `Newest ${shown} of ${total}` : `${total} ${rows(total)}`),
	an_au_load_older: 'Load older',
	an_au_export: 'Export the rows',
	an_au_export_tip: 'A comma-separated file of the rows in view. Registration marks stay masked.',
	an_au_empty: 'No audit rows in this view',
	an_au_empty_hint: 'Rows appear as the oracle records them.',
	an_au_ai_empty: 'No model rows in this view',
	an_au_ai_empty_hint: 'Decisions, tool calls and answers of Sajag AI appear here.',
	an_au_masked: 'Registration marks masked',
	an_au_local: 'This console',
	an_au_local_tip: 'Written by this console (a refusal before the wire, a probe step, an echo that retires when its server row lands)',
	an_au_evidence: 'Evidence',
	an_au_evidence_title: (who: unknown) => `Evidence: ${who}`,
	an_au_probe: 'Ask why',
	an_au_probe_run: 'Ask',
	an_au_probe_clear: 'Clear local rows',
	an_au_probe_input: 'Question for the audit probe',
	an_au_probe_hint: (ev: unknown) => `A read of Sajag AI about ${ev}. No officer is needed and nothing is written.`,
	an_au_probe_answer: 'Answer, streamed as sent',
	an_au_probe_default: 'Audit the corridor: summarise the current situation band, closure parameters and any anomalies for the selected event.',
	an_au_probe_tiers: (t: unknown) => `Answered by ${t}`,
	an_au_probe_degraded: 'degraded',
	an_au_rung: (r: unknown) => `Updates: ${r}`,
	an_au_rung_poll: 'every 2 s',
	an_au_rung_ws: 'live socket',
	an_au_rung_down: 'unavailable',
	an_au_rung_connecting: 'connecting',

	an_kind_event: 'Event',
	an_kind_enforcement: 'Enforcement',
	an_kind_anpr: 'ANPR read',
	an_kind_dispatch: 'Dispatch',
	an_kind_signals: 'Signals',
	an_kind_ama: 'Band',
	an_kind_brain: 'AI decision',
	an_kind_osint: 'Open-source',
	an_level_tool: 'Tool call',
	an_level_model: 'AI answer',
	an_level_decision: 'Decision',
	an_level_band: 'Band',
	an_level_error: 'Error',
	an_level_info: 'Note',

	// ── the link graph ─────────────────────────────────────────────────────
	an_g_label: 'Link graph',
	an_g_search_around: 'Search around',
	an_g_search_from: (what: unknown) => `Link types of ${what}`,
	an_g_search_none: 'No link types to add here',
	an_g_search_added: 'shown',
	an_g_find_paths: 'Find paths',
	an_g_find_paths_need: 'Select exactly two objects (Shift-click) to find the chain between them',
	an_g_path: (k: unknown) => `Path of ${k} ${n(k) === 1 ? 'link' : 'links'}`,
	an_g_path_none: 'No chain of 6 links or fewer joins the two objects',
	an_g_path_clear: 'Clear path',
	an_g_expand: 'Expand merged',
	an_g_expand_tip: 'Show merged links one by one',
	an_g_collapse: 'Merge again',
	an_g_layout: 'Layout',
	an_g_layout_radial: 'Radial by link type',
	an_g_layout_force: 'Force',
	an_g_layout_hierarchical: 'Hierarchical',
	an_g_fit: 'Fit',
	an_g_stats_linked: (k: unknown) => `${k} linked`,
	an_g_stats_merged: (k: unknown) => `${k} merged`,
	an_g_pursuit: 'Pursuit',
	an_g_merged_label: (k: unknown, word: unknown) => `${k} ${word}`,
	an_g_merged_tip: (k: unknown, word: unknown) => `${k} ${word}, merged: more than 8 links of one type. Click or use Expand merged to show them.`,
	an_g_legend_watch: 'Watchlist',
	an_g_legend_pending: 'Pending',
	an_g_legend_approved: 'Approved',
	an_g_legend_glyph: 'Type is the glyph',
	an_g_empty: 'Select an object to see its links',
	an_g_empty_hint: 'Pick one on the map, in the table or with the omnibar.',
	an_g_missing: 'This object is not in the city picture now',
	an_g_laying_out: (k: unknown) => `Laying out ${k} objects`,
	an_g_edge_tip: (rel: unknown) => `Link: ${rel}`,

	// ── the inspector's activity strip ─────────────────────────────────────
	an_act_strip: (k: unknown) => `${k} ${rows(k)} in the last 6 h`,
	an_act_show: 'Show in the timeline',
};



registerPack('en', en as Pack);

/** The EN, HI and MR packs (tests assert they carry the same keys). */
export const ANALYSIS_PACKS: Record<string, Pack> = { en: en as Pack };

/**
 * Register one language chunk (lib/i18n/load.ts's landing site; additive,
 * first registration wins — the core's documented semantics).
 */
export function adopt(code: 'hi' | 'mr', pack: Pack): void {
	ANALYSIS_PACKS[code] = pack;
	registerPack(code, pack);
}

/*
 * Language chunks (FIX-E-PERF2): this module's HI and MR strings live ONLY in
 * ./packs.analysis.hi.ts and ./packs.analysis.mr.ts. The server render and every non-production
 * run (vite dev, the node test harness) register both before this module
 * finishes evaluating (SSR paints the persisted language). The production
 * browser registers the loader instead and awaits the document's language
 * before this module finishes evaluating — hydration waits for it, so a cold
 * HI/MR load never flashes English — and the other language loads on the
 * first switch (lib/i18n/load.ts). The prod client build folds the condition
 * to its else branch.
 */
if (process.env.NODE_ENV !== 'production' || import.meta.env.SSR !== false) {
	adopt('hi', (await import('./packs.analysis.hi')).hi);
	adopt('mr', (await import('./packs.analysis.mr')).mr);
} else {
	await langChunks('packs.analysis', (code) =>
		code === 'hi' ? import('./packs.analysis.hi').then((c) => adopt('hi', c.hi)) : import('./packs.analysis.mr').then((c) => adopt('mr', c.mr)),
	);
}
