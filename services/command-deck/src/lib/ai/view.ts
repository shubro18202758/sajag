/**
 * The AI cards as the console words and draws them (pure; the strings through packs.ai via the caller's L):
 *
 *   cardArt / cardBanner   the 64 px illustration and the 16:9 key art per kind (water, the ambulance corridor,
 *                          a hazard, an advisory)
 *   cardKindKey            the kind line's pack key (a twin kind is "Signal timing")
 *   cardTitle              the imperative title ("Hazra crossing: reroute around water")
 *   cardWhen               the queue's timer line (crosses in 15 min · deep water in 45 min · delay −20.3% in the twin)
 *   cardWhat               the evidence sentences in the reader's language, from the numbers (never the service's
 *                          English pasted into a Marathi screen)
 *   cardChanges            "What changes if you approve": the decision record row, then the separate next step —
 *                          nothing is actuated by the console
 *   cardOverlay            the decision map: the road (water or dashed), the detour, the junction, a decision dot
 */
import type { LonLat } from '$lib/v3/map/mercator';
import type { ThumbOverlay } from '$lib/v3/map/overlay';
import type { AiCard } from './model';

type L = (key: string, ...a: unknown[]) => string;

export function cardArt(c: AiCard): string {
	if (c.source === 'hydro') {
		if (c.kind === 'ambulance_window') return '/illustrations/events/green_corridor.svg';
		if (c.kind === 'live_wire_hazard') return '/illustrations/events/hazard.svg';
		if (c.kind === 'public_advisory_draft') return '/illustrations/events/advisory.svg';
		return '/illustrations/events/flooding.svg';
	}
	if (c.source === 'twin') return '/illustrations/events/infra_failure.svg';
	return '/illustrations/events/egress_surge.svg';
}

export function cardBanner(c: AiCard): string {
	if (c.source === 'hydro') {
		if (c.kind === 'ambulance_window') return '/artwork/events/green_corridor.svg';
		if (c.kind === 'live_wire_hazard') return '/artwork/events/hazard.svg';
		if (c.kind === 'public_advisory_draft') return '/artwork/events/advisory.svg';
		return '/artwork/events/flooding.svg';
	}
	if (c.source === 'twin') return '/artwork/events/work_zone.svg';
	return '/artwork/events/egress_surge.svg';
}

const HYDRO_KINDS = new Set(['waterlogging_reroute', 'ambulance_window', 'live_wire_hazard', 'public_advisory_draft']);

export function cardKindKey(c: AiCard): string {
	if (c.source === 'twin') return 'ai_k_signal';
	if (c.source === 'forecast') return 'ai_k_pre_emptive_diversion';
	return HYDRO_KINDS.has(c.kind) ? `ai_k_${c.kind}` : 'ai_k_waterlogging_reroute';
}

/** The place in the reader's language (the city's Marathi names when the service carries them). */
export function cardPlace(c: AiCard, lang: string): string {
	if (lang === 'mr' && c.placeMr) return c.placeMr;
	return c.place;
}

export function cardTitle(c: AiCard, lang: string, L: L): string {
	const place = cardPlace(c, lang);
	if (c.source === 'twin') return L('ai_t_signal', place);
	if (c.source === 'forecast') return L('ai_t_pre_emptive_diversion', place);
	if (c.kind === 'public_advisory_draft') return L('ai_t_public_advisory_draft');
	return L(`ai_t_${HYDRO_KINDS.has(c.kind) ? c.kind : 'waterlogging_reroute'}`, place);
}

const sgn = (v: number) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(1)}`;

export function cardWhen(c: AiCard, L: L): string {
	if (c.tw) return L('ai_w_twin', sgn(c.tw.delayPct));
	if (c.fc?.inMin != null) return L('ai_w_in', c.fc.inMin);
	if (c.hy) {
		if (c.kind === 'public_advisory_draft') return L('ai_w_draft');
		if (c.hy.deepMin === 0) return L('ai_w_deep_now');
		if (c.hy.deepMin != null) return L('ai_w_deep_in', c.hy.deepMin);
	}
	return L('ai_w_draft');
}

const via = (c: AiCard) => c.viaNames.join(' → ');

/** The evidence sentences (the reader's language, from the numbers). */
export function cardWhat(c: AiCard, lang: string, L: L): string[] {
	const out: string[] = [];
	if (c.fc) {
		const b = c.fc.band;
		if (b && c.fc.vcNow != null && c.fc.inMin != null) out.push(L('ai_s_what_fc', c.road ?? c.place, c.fc.vcNow.toFixed(2), b.p50.toFixed(2), c.fc.inMin, b.p10.toFixed(2), b.p90.toFixed(2)));
		out.push(c.fc.detour && c.viaNames.length ? L('ai_s_what_fc_detour', via(c)) : L('ai_s_what_fc_nodetour'));
		return out;
	}
	if (c.tw) {
		out.push(lang === 'mr' && c.tw.changeMr ? c.tw.changeMr : c.tw.change);
		return out;
	}
	if (c.hy) {
		if (c.kind === 'public_advisory_draft') return [L('ai_s_what_adv')];
		out.push(L('ai_s_what_hy', c.road ?? c.place, c.hy.risk, c.hy.band));
		if (c.kind === 'ambulance_window' && c.hy.passableMin != null) out.push(L('ai_s_what_amb', c.hy.passableMin));
		else if (c.hy.deepMin != null) out.push(c.hy.deepMin === 0 ? L('ai_s_what_hy_now') : L('ai_s_what_hy_deep', c.hy.deepMin));
		if (c.kind === 'waterlogging_reroute') out.push(c.viaNames.length ? L('ai_s_what_reroute', via(c)) : L('ai_s_what_noroute'));
		if (c.kind === 'live_wire_hazard') out.push(L('ai_s_what_wire'));
	}
	return out;
}

export interface ChangeRowVM {
	object: string;
	now: string;
	after: string | null;
	writes?: readonly string[];
}

/** What approving changes: the record (with where it is kept), then the separate step that follows — never an action. */
export function cardChanges(c: AiCard, where: 'platform' | 'console' | 'exercise', L: L): ChangeRowVM[] {
	const rows: ChangeRowVM[] = [
		{ object: L('ai_c_obj'), now: L('ai_c_now'), after: L(where === 'platform' ? 'ai_c_after_platform' : where === 'exercise' ? 'ai_c_after_exercise' : 'ai_c_after_console'), writes: ['ai-proposals'] },
	];
	const next = (object: string, after: string) => rows.push({ object, now: L('ai_c_none'), after, writes: [] });
	if (c.tw) next(L('ai_c_signal', c.tw.junction), L('ai_c_signal_after'));
	else if (c.fc) {
		if (c.fc.detour && c.viaNames.length) next(L('ai_c_div', via(c)), L('ai_c_div_after'));
		else next(L('ai_c_watch'), L('ai_c_watch_after'));
	} else if (c.hy) {
		if (c.kind === 'public_advisory_draft') next(L('ai_c_adv'), L('ai_c_adv_after'));
		else if (c.kind === 'ambulance_window') next(L('ai_c_amb'), L('ai_c_amb_after'));
		else if (c.kind === 'live_wire_hazard') next(L('ai_c_wire'), L('ai_c_wire_after'));
		else if (c.viaNames.length) next(L('ai_c_div', via(c)), L('ai_c_div_after'));
		else next(L('ai_c_close'), L('ai_c_close_after'));
	}
	return rows;
}

/** The decision map's overlay: the subject road, its detour, the junction — and the decision dot. */
export function cardOverlay(c: AiCard, lines: ReadonlyMap<number, readonly LonLat[]>, junctions: ReadonlyMap<number, LonLat>, placeLabel: string, decided = false): ThumbOverlay | null {
	const out: { lines: { coords: readonly LonLat[]; style: 'flood' | 'dashed' | 'road' }[]; points: { at: LonLat; glyph?: string; decide?: boolean; halo?: boolean; label?: string | null }[] } = { lines: [], points: [] };
	for (const id of c.viaSegmentIds) {
		const l = lines.get(id);
		if (l && l.length >= 2) out.lines.push({ coords: l, style: 'road' });
	}
	const subj = c.segmentId != null ? lines.get(c.segmentId) : null;
	if (subj && subj.length >= 2) {
		out.lines.push({ coords: subj, style: c.source === 'hydro' ? 'flood' : 'dashed' });
		out.points.push({ at: subj[Math.floor(subj.length / 2)], glyph: c.source === 'hydro' ? 'wave' : 'graph', decide: !decided, halo: true, label: placeLabel });
	}
	for (const j of c.junctionIds) {
		const at = junctions.get(j);
		if (at && !out.points.length) out.points.push({ at, glyph: 'signal', decide: !decided, halo: true, label: placeLabel });
	}
	if (!out.points.length && c.areaSegmentIds.length) {
		// the advisory names several roads: each one the service lists, in the water style, and where it starts
		for (const id of c.areaSegmentIds) {
			const l = lines.get(id);
			if (l && l.length >= 2) out.lines.push({ coords: l, style: 'flood' });
		}
		const first = out.lines[0]?.coords;
		if (first) out.points.push({ at: first[Math.floor(first.length / 2)], glyph: 'megaphone', decide: !decided, halo: true, label: placeLabel || null });
	}
	return out.points.length || out.lines.length ? out : null;
}
