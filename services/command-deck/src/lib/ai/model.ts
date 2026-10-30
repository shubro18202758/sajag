/**
 * The AI surfaces' pure rules — no store, no DOM, no strings (the components word them through packs.ai):
 *
 *   forecastPoints   a segment's p10 / p50 / p90 V/C at +30, +60 and +120 min (the selection card's band)
 *   riskCounts       how many roads are shallow / deep / impassable within the nowcast horizon
 *   tideState        the tide now, its direction, the gates, the next high water and the next gate closure
 *   rainNow          the city-mean rain at the current quarter-hour (null when the feed has none: never 0)
 *   aiCards          every waiting proposal (forecast, hydro, twin) as ONE decision-card model, soonest and
 *                    most severe first; decided ones (the decision record) are left out
 *   nextHours        Home's "Next 2 hours": top crossings, roads at risk, the tide, twin proposals waiting
 *   replayTimeline   the 19 Aug 2025 replay as a timeline: when each road first went deep / impassable, the
 *                    modelled gate closure, IMD's peak hour, and the reported places with their first flag
 *   replayClassAt    a road's modelled class at a moment of the replay night (rising limb only: the classes are
 *                    first-reached times, so the scrubber stops at the modelled peak)
 *
 * tests/ai-ops.unit.mjs holds every rule.
 */
import { FORECAST_LEADS, forecastPoints, istMs, replayClassAt, type LeadPoint } from './core';
export { FORECAST_LEADS, forecastPoints, istMs, replayClassAt, type LeadPoint };
import type {
	Band3,
	ForecastDoc,
	ForecastSegment,
	HydroNowcast,
	HydroRain,
	HydroReplay,
	HydroTide,
	ReplaySegment,
	ServiceProposal,
	TwinProposal,
	TwinResult,
	TwinSide,
} from './types';

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v.trim() : null);
const ms = (iso: string | null | undefined): number | null => {
	const t = iso ? Date.parse(iso) : NaN;
	return Number.isFinite(t) ? t : null;
};

// ── forecast ─────────────────────────────────────────────────────────────

/** Whether the band crosses the threshold (p50 at or over it: likely; only p90: possible). */
export function crossingWord(vc: Band3, threshold = 0.8): 'over' | 'likely' | 'possible' | 'under' {
	if (vc.p10 >= threshold) return 'over';
	if (vc.p50 >= threshold) return 'likely';
	if (vc.p90 >= threshold) return 'possible';
	return 'under';
}

// ── hydro ────────────────────────────────────────────────────────────────

export interface RiskCounts {
	shallow: number;
	deep: number;
	impassable: number;
	roads: number;
}

export function riskCounts(nc: Pick<HydroNowcast, 'segments'> | null | undefined): RiskCounts | null {
	if (!nc) return null;
	const out = { shallow: 0, deep: 0, impassable: 0, roads: nc.segments.length };
	for (const s of nc.segments) {
		if (s.risk_class >= 3) out.impassable++;
		else if (s.risk_class === 2) out.deep++;
		else if (s.risk_class === 1) out.shallow++;
	}
	return out;
}

export interface TideState {
	level: number;
	rising: boolean;
	gateClosed: boolean;
	closeLevel: number;
	nextHigh: { at: number; level: number } | null;
	/** The next quarter-hour the model shuts the gates (null: not in the series, or shut now). */
	nextClose: number | null;
}

export function tideState(tide: HydroTide | null | undefined, now: number): TideState | null {
	const level = num(tide?.now?.level_m);
	if (!tide || level == null) return null;
	const high = tide.extremes.filter((e) => e.kind === 'high' && (ms(e.at) ?? 0) > now).sort((a, b) => (ms(a.at) ?? 0) - (ms(b.at) ?? 0))[0];
	const closed = !!tide.now.gate_closed;
	const close = closed ? null : tide.series.find((p) => p.gate_closed && (ms(p.t) ?? 0) > now);
	return {
		level,
		rising: !!tide.now.rising,
		gateClosed: closed,
		closeLevel: num(tide.gate_close_level_m) ?? 5,
		nextHigh: high ? { at: ms(high.at) ?? 0, level: high.level_m } : null,
		nextClose: close ? ms(close.t) : null,
	};
}

/** The city-mean rain at the quarter-hour containing `now` (mm/h), or null without a feed. */
export function rainNow(rain: Pick<HydroRain, 'city' | 'error'> | null | undefined, now: number): number | null {
	const series = rain?.city?.series ?? [];
	if (!series.length) return null;
	let best: number | null = null;
	for (const p of series) {
		const t = ms(p.t);
		if (t != null && t <= now) best = p.mm_h;
	}
	return best ?? series[0].mm_h ?? null;
}

/** The rain the next hour brings, city mean (mm), or null. */
export function rainNextHour(rain: Pick<HydroRain, 'city'> | null | undefined, now: number): number | null {
	const series = (rain?.city?.series ?? []).filter((p) => {
		const t = ms(p.t);
		return t != null && t > now && t <= now + 3_600_000;
	});
	if (!series.length) return null;
	return Math.round(series.reduce((a, p) => a + p.mm_h / 4, 0) * 10) / 10;
}

// ── the decision cards ───────────────────────────────────────────────────

export type AiSource = 'forecast' | 'hydro' | 'twin';

export interface AiCard {
	id: string;
	source: AiSource;
	kind: string;
	/** The place (a crossing, a junction) and the road. */
	place: string;
	placeMr: string | null;
	road: string | null;
	subjectUrn: string;
	segmentId: number | null;
	junctionIds: number[];
	viaSegmentIds: number[];
	viaNames: string[];
	/** The roads an advisory names (its area on the decision map). */
	areaSegmentIds: number[];
	labels: string[];
	generatedAt: number | null;
	/** When it matters (the forecast crossing, deep water): epoch ms, or null. */
	dueAt: number | null;
	/** 3 most severe … 0. */
	severity: number;
	/** The service's own sentence (English), shown as its evidence line. */
	summary: string;
	/** An exercise (the replay's hindsight proposals): decisions stay on this console, never in the decision log. */
	exercise: boolean;
	fc: { vcNow: number | null; band: Band3 | null; inMin: number | null; threshold: number; share: number | null; detour: boolean } | null;
	hy: { risk: number; band: string; leadMin: number | null; deepMin: number | null; agency: string | null; passableMin: number | null; textEn: string | null; textMr: string | null; detourM: number | null } | null;
	tw: {
		junction: string;
		junctionMr: string | null;
		change: string;
		changeMr: string | null;
		durationMin: number;
		delayPct: number;
		crossPct: number;
		networkPct: number;
		queueM: number;
		before: TwinSide | null;
		after: TwinSide | null;
		confidence: { score: number; level: string } | null;
		demand: string | null;
		rationaleEn: string | null;
		rationaleMr: string | null;
	} | null;
}

const KIND_SEVERITY: Readonly<Record<string, number>> = {
	live_wire_hazard: 3,
	waterlogging_reroute: 2,
	ambulance_window: 2,
	public_advisory_draft: 1,
	pre_emptive_diversion: 1,
};

function viaOf(p: ServiceProposal): { ids: number[]; names: string[]; detourM: number | null } {
	for (const a of p.actions ?? []) {
		const ids = Array.isArray(a.params?.via_segment_ids) ? (a.params!.via_segment_ids as unknown[]).filter((x): x is number => typeof x === 'number') : [];
		const names = Array.isArray(a.params?.via_names) ? (a.params!.via_names as unknown[]).filter((x): x is string => typeof x === 'string') : [];
		if (ids.length || names.length) return { ids, names, detourM: num(a.params?.detour_length_m) };
	}
	return { ids: [], names: [], detourM: null };
}

const segOf = (urn: string): number | null => {
	const m = /^segment:(\d+)$/.exec(urn);
	return m ? Number(m[1]) : null;
};

/** One forecast or hydro proposal → its card (null when it is not a waiting proposal). */
export function cardFromProposal(p: ServiceProposal, source: 'forecast' | 'hydro', extra: { exercise?: boolean; placeMr?: Map<number, string> } = {}): AiCard | null {
	if (!p || p.state !== 'proposed' || !str(p.proposal_id)) return null;
	const sit = (p.situation ?? {}) as Record<string, unknown>;
	const via = viaOf(p);
	const segmentId = num(sit.segment_id) ?? segOf(p.subject_urn ?? '');
	const gen = ms(p.generated_at);
	const base = {
		id: p.proposal_id,
		source,
		kind: p.kind,
		place: str(sit.place) ?? str(p.subject_urn) ?? '—',
		placeMr: segmentId != null ? (extra.placeMr?.get(segmentId) ?? null) : null,
		road: str(sit.road_name),
		subjectUrn: p.subject_urn,
		segmentId,
		junctionIds: num(sit.junction_id) != null ? [num(sit.junction_id)!] : [],
		viaSegmentIds: via.ids,
		viaNames: via.names,
		areaSegmentIds: (p.actions ?? []).flatMap((a) => (Array.isArray(a.params?.segment_ids) ? (a.params!.segment_ids as unknown[]).filter((x): x is number => typeof x === 'number') : [])),
		labels: Array.isArray(p.labels) ? p.labels.filter((l) => typeof l === 'string') : [],
		generatedAt: gen,
		summary: p.summary ?? '',
		exercise: !!extra.exercise,
		fc: null,
		hy: null,
		tw: null,
	};
	if (source === 'forecast') {
		const inMin = num(sit.in_min);
		const band = num(sit.vc_p50) != null ? { p10: num(sit.vc_p10) ?? num(sit.vc_p50)!, p50: num(sit.vc_p50)!, p90: num(sit.vc_p90) ?? num(sit.vc_p50)! } : null;
		return {
			...base,
			dueAt: ms(str(sit.crossing_at)) ?? (gen != null && inMin != null ? gen + inMin * 60_000 : null),
			severity: band && band.p50 >= 0.9 ? 2 : 1,
			fc: { vcNow: num(sit.vc_now), band, inMin, threshold: num(sit.threshold) ?? 0.8, share: num(p.expected_effect?.suggested_share), detour: p.actions.some((a) => a.verb === 'diversion') },
		};
	}
	// hydro: the situation rides on the reroute; the other kinds name the segment and their own params
	const act = p.actions?.[0];
	const risk = num(sit.risk_class) ?? (/risk (\d)/.exec(p.summary ?? '') ? Number(/risk (\d)/.exec(p.summary ?? '')![1]) : 0);
	const band = str(sit.expected_depth_band) ?? (/\(([^)]*cm)\)/.exec(p.summary ?? '')?.[1] ?? '');
	const deepMin = num(sit.lead_time_deep_min) ?? num(act?.params?.passable_for_min);
	const leadMin = num(sit.lead_time_min);
	const place = base.place === p.subject_urn ? (/^([^(:—]+?)\s*\(/.exec((p.summary ?? '').replace(/^[^—]*—\s*/, ''))?.[1]?.trim() ?? base.place) : base.place;
	const road = base.road ?? /\(([^)]+)\)/.exec((p.summary ?? '').replace(/^[^—]*—\s*/, ''))?.[1] ?? null;
	return {
		...base,
		place: p.kind === 'public_advisory_draft' ? '' : place,
		road: p.kind === 'public_advisory_draft' ? null : road,
		dueAt: gen != null && deepMin != null ? gen + deepMin * 60_000 : null,
		severity: Math.max(KIND_SEVERITY[p.kind] ?? 1, risk >= 3 ? 3 : risk >= 2 ? 2 : 1),
		hy: {
			risk,
			band,
			leadMin,
			deepMin,
			agency: str(act?.params?.to_agency),
			passableMin: num(act?.params?.passable_for_min),
			textEn: str(p.text?.en) ?? str(act?.params?.text_en),
			textMr: str(p.text?.mr) ?? str(act?.params?.text_mr),
			detourM: via.detourM,
		},
	};
}

/** A twin result → its card (null for a hold: nothing passed the twin's guards). */
export function cardFromTwin(r: TwinResult | null | undefined): AiCard | null {
	const p: TwinProposal | null | undefined = r?.proposal;
	if (!p || !str(p.proposal_id) || String(p.status).toUpperCase() !== 'PROPOSED') return null;
	const j = p.junctions?.[0];
	const m = p.twin_metrics;
	const labels = [p.verification_state, r?.labels?.demand ?? null].filter((x): x is string => !!x);
	return {
		id: p.proposal_id,
		source: 'twin',
		kind: p.kind,
		place: j?.name ?? `junction ${p.junction_ids?.[0] ?? ''}`,
		placeMr: j?.name_mr ?? null,
		road: null,
		subjectUrn: p.targets?.[0] ?? `junction:${p.junction_ids?.[0] ?? ''}`,
		segmentId: null,
		junctionIds: p.junction_ids ?? [],
		viaSegmentIds: [],
		viaNames: [],
		areaSegmentIds: [],
		labels,
		generatedAt: null,
		dueAt: null,
		severity: Math.abs(m?.delay_change_pct ?? 0) >= 15 ? 2 : 1,
		summary: p.change?.summary ?? '',
		exercise: false,
		fc: null,
		hy: null,
		tw: {
			junction: j?.name ?? '—',
			junctionMr: j?.name_mr ?? null,
			change: p.change?.summary ?? '',
			changeMr: p.change?.summary_mr ?? null,
			durationMin: num(p.duration_min) ?? 0,
			delayPct: num(m?.delay_change_pct) ?? 0,
			crossPct: num(m?.cross_street_delay_change_pct) ?? 0,
			networkPct: num(m?.network_delay_change_pct) ?? 0,
			queueM: num(m?.max_queue_change_m) ?? 0,
			before: m?.do_nothing ?? null,
			after: m?.with_change ?? null,
			confidence: p.confidence ? { score: p.confidence.score, level: p.confidence.level } : null,
			demand: r?.labels?.demand ?? null,
			rationaleEn: p.rationale?.en ?? null,
			rationaleMr: p.rationale?.mr ?? null,
		},
	};
}

/**
 * Every waiting card: the forecast's proposals (its latest run), the hydro nowcast's (or the replay's hindsight
 * exercise), the twin's — minus the decided ones, de-duplicated by id, most severe then soonest first.
 */
export function aiCards(input: {
	forecast?: Pick<ForecastDoc, 'proposals'> | null;
	nowcast?: Pick<HydroNowcast, 'proposals' | 'segments'> | null;
	exercise?: ServiceProposal[] | null;
	twins?: readonly (TwinResult | null)[];
	decided?: ReadonlySet<string>;
}): AiCard[] {
	const out = new Map<string, AiCard>();
	const mr = new Map<number, string>();
	for (const s of input.nowcast?.segments ?? []) if (s.place_mr) mr.set(s.segment_id, s.place_mr);
	const add = (c: AiCard | null) => {
		if (c && !input.decided?.has(c.id) && !out.has(c.id)) out.set(c.id, c);
	};
	for (const p of input.nowcast?.proposals ?? []) add(cardFromProposal(p, 'hydro', { placeMr: mr }));
	for (const p of input.exercise ?? []) add(cardFromProposal(p, 'hydro', { exercise: true, placeMr: mr }));
	for (const p of input.forecast?.proposals ?? []) add(cardFromProposal(p, 'forecast', { placeMr: mr }));
	for (const r of input.twins ?? []) add(cardFromTwin(r));
	// one road's waterlogging cards travel together: the road's severity and its deep-water time order them, and
	// a card that does not carry the time (the live-wire request) takes it from its road's reroute
	const road = new Map<number, { severity: number; due: number | null; deepMin: number | null }>();
	for (const c of out.values()) {
		if (c.source !== 'hydro' || c.segmentId == null) continue;
		const r = road.get(c.segmentId) ?? { severity: 0, due: null, deepMin: null };
		r.severity = Math.max(r.severity, c.severity);
		if (c.dueAt != null) r.due = r.due == null ? c.dueAt : Math.min(r.due, c.dueAt);
		if (c.hy?.deepMin != null) r.deepMin = r.deepMin == null ? c.hy.deepMin : Math.min(r.deepMin, c.hy.deepMin);
		road.set(c.segmentId, r);
	}
	const cards = [...out.values()].map((c) => {
		const r = c.segmentId != null ? road.get(c.segmentId) : undefined;
		if (!r || !c.hy) return c;
		return { ...c, severity: r.severity, dueAt: c.dueAt ?? r.due, hy: { ...c.hy, deepMin: c.hy.deepMin ?? r.deepMin } };
	});
	const SRC: Record<AiSource, number> = { hydro: 0, forecast: 1, twin: 2 };
	const KIND: Record<string, number> = { waterlogging_reroute: 0, ambulance_window: 1, live_wire_hazard: 2, public_advisory_draft: 3 };
	const groupDue = (c: AiCard) => (c.segmentId != null ? (road.get(c.segmentId)?.due ?? c.dueAt) : c.dueAt) ?? Infinity;
	return cards.sort(
		(a, b) =>
			b.severity - a.severity ||
			groupDue(a) - groupDue(b) ||
			SRC[a.source] - SRC[b.source] ||
			(a.segmentId ?? 0) - (b.segmentId ?? 0) ||
			(KIND[a.kind] ?? 9) - (KIND[b.kind] ?? 9) ||
			a.id.localeCompare(b.id),
	);
}

/** The forecast crossings worth asking the twin about: signalised focus junctions, soonest first (at most `n`). */
export function twinAsks(doc: Pick<ForecastDoc, 'proposals'> | null | undefined, n = 2): { proposalId: string; junction: number; segmentId: number | null; vc: number; inMin: number }[] {
	const out: { proposalId: string; junction: number; segmentId: number | null; vc: number; inMin: number }[] = [];
	const seen = new Set<number>();
	const list = [...(doc?.proposals ?? [])].sort((a, b) => (num(a.situation?.in_min) ?? 999) - (num(b.situation?.in_min) ?? 999));
	for (const p of list) {
		const j = num(p.situation?.junction_id);
		const vc = num(p.situation?.vc_p50);
		if (j == null || vc == null || seen.has(j)) continue;
		seen.add(j);
		out.push({ proposalId: p.proposal_id, junction: j, segmentId: num(p.situation?.segment_id), vc, inMin: num(p.situation?.in_min) ?? 30 });
		if (out.length >= n) break;
	}
	return out;
}

// ── Home: the next two hours ─────────────────────────────────────────────

export interface NextHours {
	crossings: { place: string; road: string | null; inMin: number | null; vc: number | null; segmentId: number | null }[];
	crossingCount: number | null;
	risk: RiskCounts | null;
	tide: TideState | null;
	twinWaiting: number | null;
	forecastLabels: string[];
}

export function nextHours(input: { forecast?: ForecastDoc | null; nowcast?: HydroNowcast | null; tide?: HydroTide | null; twinWaiting?: number | null; now: number }): NextHours {
	const f = input.forecast;
	const crossings = (f?.proposals ?? [])
		.map((p) => ({ place: str(p.situation?.place) ?? '—', road: str(p.situation?.road_name), inMin: num(p.situation?.in_min), vc: num(p.situation?.vc_p50), segmentId: num(p.situation?.segment_id) }))
		.sort((a, b) => (a.inMin ?? 999) - (b.inMin ?? 999) || (b.vc ?? 0) - (a.vc ?? 0));
	return {
		crossings: crossings.slice(0, 3),
		crossingCount: f ? crossings.length : null,
		risk: riskCounts(input.nowcast ?? null),
		tide: tideState(input.tide ?? null, input.now),
		twinWaiting: input.twinWaiting ?? null,
		forecastLabels: f?.data_labels ?? [],
	};
}

// ── the 19 Aug 2025 replay ───────────────────────────────────────────────

export interface ReplayTick {
	at: number;
	deep: number;
	impassable: number;
}

export interface ReplayTimeline {
	start: number;
	end: number;
	/** The modelled peak (the scrubber stops here: after it the classes are not followed down). */
	peak: number;
	gates: { from: number; to: number }[];
	peakHour: { from: number; to: number } | null;
	ticks: ReplayTick[];
	firstFlag: number | null;
	reported: { place: string; flagged: boolean; at: number | null; maxClass: number | null; sources: string[] }[];
	offNetwork: string[];
	hit: { flagged: number; onNetwork: number };
	totals: { mm: number | null; peakMmH: number | null; archiveMm: number | null; archiveFlagged: number | null };
	counts: { deep: number; impassable: number; roads: number };
}

export function replayTimeline(rep: HydroReplay | null | undefined, stepMin = 15): ReplayTimeline | null {
	const run = rep?.runs?.imd_gauge_anchored;
	const start = istMs(rep?.window_ist?.[0]);
	const end = istMs(rep?.window_ist?.[1]);
	if (!rep || !run || start == null || end == null) return null;
	const segs = run.segments ?? [];
	const peaks = segs.map((s) => (s.peak_class >= 1 ? istMs(s.peak_at_ist) : null)).filter((x): x is number => x != null);
	const peak = peaks.length ? Math.max(...peaks) : end;
	const ticks: ReplayTick[] = [];
	for (let t = start; t <= Math.min(end, peak); t += stepMin * 60_000) {
		let deep = 0;
		let impassable = 0;
		for (const s of segs) {
			const c = replayClassAt(s, t);
			if (c >= 3) impassable++;
			else if (c === 2) deep++;
		}
		ticks.push({ at: t, deep, impassable });
	}
	const ph = /(\d{2}):(\d{2})\s*[–-]\s*(\d{2}):(\d{2})/.exec(rep.official?.peak_hour ?? '');
	const day = rep.official?.to?.slice(0, 10) ?? null;
	const peakHour = ph && day ? { from: istMs(`${day} ${ph[1]}:${ph[2]}`)!, to: istMs(`${day} ${ph[3]}:${ph[4]}`)! } : null;
	const items = run.reported_check?.items ?? [];
	return {
		start,
		end,
		peak,
		gates: (rep.tide?.gate_closed_ist ?? []).map(([a, b]) => ({ from: istMs(a) ?? 0, to: istMs(b) ?? 0 })).filter((g) => g.from && g.to),
		peakHour: peakHour && peakHour.from && peakHour.to ? peakHour : null,
		ticks,
		firstFlag: istMs(run.earliest_flag_ist),
		reported: items
			.filter((i) => i.on_network)
			.map((i) => ({ place: i.reported, flagged: !!i.flagged, at: istMs(i.first_flag_ist), maxClass: i.max_class ?? null, sources: i.sources ?? [] }))
			.sort((a, b) => (a.at ?? Infinity) - (b.at ?? Infinity)),
		offNetwork: items.filter((i) => !i.on_network).map((i) => i.reported),
		hit: { flagged: run.reported_check?.flagged ?? 0, onNetwork: run.reported_check?.on_network ?? 0 },
		totals: {
			mm: num(run.observed_window_total_mm ?? run.alipore_window_total_mm),
			peakMmH: num(run.observed_peak_mm_h ?? run.alipore_peak_mm_h),
			archiveMm: num(rep.runs.open_meteo_archive?.window_total_mm_city_mean),
			archiveFlagged: num(rep.runs.open_meteo_archive?.flagged_segments),
		},
		counts: { deep: Number(run.peak_class_counts?.['2'] ?? 0), impassable: Number(run.peak_class_counts?.['3'] ?? 0), roads: segs.length },
	};
}

/** The replay's hindsight proposals (present once the hydro service returns them; empty otherwise). */
export function replayProposals(rep: HydroReplay | null | undefined): ServiceProposal[] {
	const snap = rep?.runs?.imd_gauge_anchored?.snapshot as { proposals?: unknown } | undefined;
	return Array.isArray(snap?.proposals) ? (snap!.proposals as ServiceProposal[]) : [];
}
