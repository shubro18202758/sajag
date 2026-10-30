/**
 * The on-prem AI services as the console reads them (typed, tolerant): only the fields the deck shows.
 *
 *   forecast  services/forecast (Chronos-2): p10 / p50 / p90 V/C and speed per segment in 15-minute steps, the
 *             crossings of 0.8 V/C and the pre-emptive diversion proposals. History SIMULATED until Mumbai
 *             traffic is recorded (the service says so in data_labels / data_note).
 *   hydro     services/hydro: per-segment waterlogging risk 0–3, depth band, lead time, four labelled drivers
 *             (rain LIVE · tide MODELLED · susceptibility MODELLED · pumps EMULATED), the tide model, the rain
 *             nowcast, the 18–19 Aug 2025 replay and the proposals (reroute, ambulance window, live-wire hazard
 *             request, Marathi + English advisory draft).
 *   twin      services/twin: ranked signal-timing proposals checked in a cell-transmission twin (MODELLED),
 *             "requires named officer approval"; it never writes a signal.
 *
 * Every proposal is a PROPOSAL (state proposed, human_gate with no officer): the console shows it, a named
 * officer decides, and the decision is recorded (writer.ts) — nothing here actuates anything.
 */

/** The proposals' common shape (the oracle's decision-support vocabulary, osint_common C-U). */
export interface CoaActionDoc {
	verb: string;
	target_urn?: string | null;
	params?: Record<string, unknown>;
	requires_officer?: boolean;
	reversible?: boolean;
}

export interface ServiceProposal {
	proposal_id: string;
	kind: string;
	subject_urn: string;
	state: string;
	generated_at?: string;
	expires_at?: string | null;
	summary: string;
	actions: CoaActionDoc[];
	labels: string[];
	situation?: Record<string, unknown>;
	text?: { en?: string; mr?: string } | null;
	expected_effect?: { suggested_share?: number; note?: string } | null;
	human_gate?: { state?: string; required_role?: string; officer?: string | null; decided_at?: string | null } | null;
	for_officer_approval?: boolean;
}

// ── forecast ─────────────────────────────────────────────────────────────

export interface Band3 {
	p10: number;
	p50: number;
	p90: number;
}

export interface ForecastStep {
	t: string;
	lead_min: number;
	vc: Band3;
	speed_kmh: Band3;
	baseline_vc_p50?: number | null;
}

export interface ForecastSegment {
	segment_id: number;
	road_name: string;
	place: string;
	data_label: string;
	now: { t: string; vc: number; speed_kmh: number } | null;
	crossing: { at?: string; in_min?: number; vc_p50?: number } | null;
	above_threshold_now: boolean;
	steps: ForecastStep[];
	model?: string;
}

export interface ForecastDoc {
	generated_at: string;
	origin: string;
	step_min: number;
	threshold_vc: number;
	model: string;
	model_note: string | null;
	data_labels: string[];
	data_note: string | null;
	segments: ForecastSegment[];
	proposals: ServiceProposal[];
	crossings: number;
	horizon_min: number;
}

// ── hydro ────────────────────────────────────────────────────────────────

export interface HydroSegment {
	segment_id: number;
	road_name: string;
	place: string;
	place_mr?: string | null;
	lat: number;
	lon: number;
	risk_class: number;
	risk_class_now: number;
	expected_depth_band: string;
	modelled_peak_depth_cm: number;
	lead_time_min: number;
	lead_time_deep_min: number | null;
	peak_at?: string;
	elevated: boolean;
	drivers: {
		rain?: { label: string; past_1h_mm?: number; next_1h_mm?: number; next_2h_mm?: number; peak_next_2h_mm_h?: number };
		tide?: { label: string; level_m?: number; gate_closed_now?: boolean; gate_closed_minutes_in_horizon?: number; next_high_water?: { at: string; level_m: number } | null };
		susceptibility?: { label: string; score?: number | null; nearest_hotspot?: string | null; dist_hotspot_m?: number | null };
		pumps?: { label: string; station?: string | null; pumps_available?: number | null; pumps_total?: number | null; availability?: number };
	};
}

export interface HydroNowcast {
	generated_at: string;
	now: string;
	horizon_min: number;
	labels: Record<string, string>;
	rain_feed: { city_now_mm_h?: number; stale?: boolean; error?: string | null; fetched_at?: string } | null;
	counts_by_class: Record<string, number>;
	flagged: number[];
	segments: HydroSegment[];
	proposals: ServiceProposal[];
}

export interface TidePoint {
	t: string;
	level_m: number;
	gate_closed: boolean;
}

export interface HydroTide {
	label: string;
	station: string;
	now: { t: string; level_m: number; gate_closed: boolean; rising: boolean };
	gate_close_level_m: number;
	series: TidePoint[];
	extremes: { kind: 'high' | 'low'; at: string; level_m: number }[];
}

export interface HydroRain {
	label: string;
	stale: boolean;
	error: string | null;
	fetched_at: string;
	city: { series: { t: string; mm_h: number }[] };
}

export interface HydroPumps {
	label: string;
	stations: { available?: number; pumps_available?: number; pumps_total?: number; running?: boolean }[];
}

export interface ReplaySegment {
	segment_id: number;
	road_name: string;
	place: string;
	rain_total_mm: number;
	peak_class: number;
	peak_depth_cm: number;
	peak_band: string;
	peak_at_ist: string | null;
	first_class1_ist: string | null;
	first_class2_ist: string | null;
	first_class3_ist: string | null;
	elevated: boolean;
}

export interface ReplayReported {
	reported: string;
	sources: string[];
	segments: number[];
	on_network: boolean;
	flagged: boolean;
	first_flag_ist: string | null;
	max_class: number | null;
}

export interface ReplayRun {
	label: string;
	peak_class_counts: Record<string, number>;
	flagged_segments: number;
	earliest_flag_ist: string | null;
	reported_check: { on_network: number; flagged: number; hit_rate: number; items: ReplayReported[]; off_network?: unknown[] };
	segments: ReplaySegment[];
	window_total_mm_city_mean?: number;
	/** The observatory's measured window total and peak hour (city-neutral names; the older run's alipore_* below). */
	observed_window_total_mm?: number;
	observed_peak_mm_h?: number;
	alipore_window_total_mm?: number;
	alipore_peak_mm_h?: number;
	finding?: string;
	snapshot?: {
		at_ist: string;
		label: string;
		flagged_within_horizon: number;
		lead_time_to_deep_min?: { min: number; median: number; max: number };
		advisory_draft?: { en: string; mr: string } | null;
	};
}

export interface HydroReplay {
	event: string;
	title: string;
	window_ist: [string, string];
	official: { observed_24h_mm?: number; alipore_24h_mm?: number; to: string; peak_hour: string; source?: { publisher: string; date: string; url: string } };
	tide: { label: string; gate_closed_ist: [string, string][]; reported?: string };
	runs: { open_meteo_archive?: ReplayRun; imd_gauge_anchored?: ReplayRun };
	honesty?: string;
}

// ── twin ─────────────────────────────────────────────────────────────────

export interface TwinSide {
	focus_delay_veh_h?: number;
	network_delay_veh_h?: number;
	cross_street_delay_veh_h?: number;
	max_queue_m?: number;
	cross_street_max_queue_m?: number;
	spillback_min?: number;
}

export interface TwinProposal {
	proposal_id: string;
	kind: string;
	junction_ids: number[];
	junctions: { junction_id: number; key?: string; name: string; name_mr?: string | null; control?: string }[];
	targets: string[];
	change: { kind: string; summary: string; summary_mr?: string | null };
	duration_min: number;
	twin_metrics: {
		horizon_min: number;
		delay_change_pct: number;
		network_delay_change_pct: number;
		cross_street_delay_change_pct: number;
		max_queue_change_m: number;
		spillback_change_min?: number;
		do_nothing?: TwinSide;
		with_change?: TwinSide;
	};
	confidence: { score: number; level: string; basis?: string[]; note?: string };
	assumptions?: string[];
	verification_state: string;
	requires?: string;
	status: string;
	if_no_decision?: string;
	rationale?: { en?: string; mr?: string; source?: Record<string, string> } | null;
}

export interface TwinResult {
	focus: { junction_ids: number[]; auto_selected?: boolean };
	proposal: TwinProposal | null;
	labels: { result?: string; demand?: string; note?: string };
	demand?: { label?: string; start_ist?: string };
	recommendation?: string;
	/** Which forecast crossing (proposal id) asked the twin, when one did (set by the console). */
	asked_for?: string | null;
}

// ── the decision record (oracle ai-proposals; patch int-ops-oracle-ai-proposals) ──

export interface AiDecisionRow {
	log_id: number | null;
	proposal_id: string;
	source: string;
	kind: string;
	subject_urn: string;
	decision: 'approve' | 'reject';
	officer: string;
	note: string | null;
	decided_at: string;
	/** Where it was recorded: the platform's decision log, or this console only (log not deployed yet). */
	recorded: 'platform' | 'console';
}
