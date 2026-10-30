/**
 * The few AI rules the canvas layers need on first paint (the God's-eye registry is eager on /gods-eye, /ops and
 * /analyst): a road's forecast band at chosen leads and a replay road's class at a moment. Kept apart from model.ts so
 * the canvas never carries the decision cards, the replay timeline or the Home summary; model.ts re-exports them.
 */
import type { Band3, ForecastSegment, ReplaySegment } from './types';

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const ms = (iso: string | null | undefined): number | null => {
	const t = iso ? Date.parse(iso) : NaN;
	return Number.isFinite(t) ? t : null;
};

export const FORECAST_LEADS = [30, 60, 120] as const;

export interface LeadPoint {
	lead: number;
	t: number | null;
	vc: Band3;
	speed: Band3 | null;
}

/** The steps at the asked leads (the exact step, else the last one before it); a lead past the horizon is null. */
export function forecastPoints(seg: Pick<ForecastSegment, 'steps'> | null | undefined, leads: readonly number[] = FORECAST_LEADS): (LeadPoint | null)[] {
	const steps = (seg?.steps ?? []).filter((s) => num(s?.lead_min) != null && num(s?.vc?.p50) != null);
	return leads.map((lead) => {
		const at = steps.filter((s) => s.lead_min <= lead).sort((a, b) => b.lead_min - a.lead_min)[0];
		if (!at || lead - at.lead_min >= 15) return null;
		return { lead, t: ms(at.t), vc: at.vc, speed: at.speed_kmh ?? null };
	});
}

/** "2025-08-19 06:20" (IST, as the replay writes it) or an ISO time → epoch ms. */
export function istMs(s: string | null | undefined): number | null {
	if (!s) return null;
	const iso = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(s) ? `${s.replace(' ', 'T')}:00+05:30` : s;
	return ms(iso);
}

/** A road's class at `t` on the rising limb (first-reached times; never past the modelled peak). */
export function replayClassAt(s: Pick<ReplaySegment, 'first_class1_ist' | 'first_class2_ist' | 'first_class3_ist'>, t: number): number {
	const c3 = istMs(s.first_class3_ist);
	const c2 = istMs(s.first_class2_ist);
	const c1 = istMs(s.first_class1_ist);
	if (c3 != null && c3 <= t) return 3;
	if (c2 != null && c2 <= t) return 2;
	if (c1 != null && c1 <= t) return 1;
	return 0;
}

