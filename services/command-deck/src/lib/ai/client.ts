/**
 * Typed clients for the on-prem AI services, through the deck origin only (the same-origin proxy prefixes in
 * hooks.server.ts and vite.config.ts — fixed constants, never a URL built from data or operator input):
 *
 *   /api/forecast → services/forecast   /api/hydro → services/hydro   /api/twin → services/twin
 *   /api/v1/ai-proposals → traffic-oracle (the decision record; .orchestration patch int-ops-oracle-ai-proposals)
 *
 * Every read has a timeout and a typed failure: AiNotDeployed (404: the service or route is not there),
 * AiSignIn (401/403: the operator gate wants a session), AiDown (anything else). Bodies are parsed tolerantly
 * (a missing list is an empty list, a missing number is null) and never invented.
 */
import type { ForecastDoc, ForecastSegment, HydroNowcast, HydroPumps, HydroRain, HydroReplay, HydroTide, TwinResult } from './types';

export const AI_PATHS = Object.freeze({
	forecast: '/api/forecast',
	hydro: '/api/hydro',
	twin: '/api/twin',
	decisions: '/api/v1/ai-proposals',
});

export class AiDown extends Error {
	constructor(message: string) {
		super(message);
		this.name = 'AiDown';
	}
}

export class AiNotDeployed extends Error {
	constructor(message: string) {
		super(message);
		this.name = 'AiNotDeployed';
	}
}

export class AiSignIn extends Error {
	constructor(message: string) {
		super(message);
		this.name = 'AiSignIn';
	}
}

/** One JSON request with a timeout; maps the status to the typed failures above. */
export async function aiJson<T>(url: string, init: RequestInit = {}, timeoutMs = 15_000): Promise<T> {
	let res: Response;
	try {
		res = await fetch(url, { ...init, signal: AbortSignal.timeout(timeoutMs), headers: { accept: 'application/json', ...(init.headers ?? {}) } });
	} catch (err) {
		throw new AiDown(err instanceof DOMException && err.name === 'TimeoutError' ? `no answer within ${Math.round(timeoutMs / 1000)} s` : err instanceof Error ? err.message : String(err));
	}
	if (res.status === 404) throw new AiNotDeployed(`${url.split('?')[0]}: not deployed (404)`);
	if (res.status === 401 || res.status === 403) throw new AiSignIn(`${res.status}`);
	if (!res.ok) {
		const text = await res.text().catch(() => '');
		throw new AiDown(`${res.status}${text ? `: ${text.slice(0, 160)}` : ''}`);
	}
	return (await res.json()) as T;
}

const arr = <T>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);

// ── hydro ────────────────────────────────────────────────────────────────

export async function getNowcast(): Promise<HydroNowcast> {
	const d = await aiJson<HydroNowcast>(`${AI_PATHS.hydro}/hydro/nowcast`, {}, 30_000);
	return { ...d, segments: arr(d.segments), proposals: arr(d.proposals), flagged: arr(d.flagged), counts_by_class: d.counts_by_class ?? {}, labels: d.labels ?? {} };
}

export async function getTide(hours = 24): Promise<HydroTide> {
	const d = await aiJson<HydroTide>(`${AI_PATHS.hydro}/hydro/tide?hours=${Math.max(1, Math.min(72, Math.round(hours)))}`);
	return { ...d, series: arr(d.series), extremes: arr(d.extremes) };
}

export async function getRain(): Promise<HydroRain> {
	const d = await aiJson<HydroRain>(`${AI_PATHS.hydro}/hydro/rain`, {}, 30_000);
	return { ...d, city: { series: arr(d.city?.series) } };
}

export async function getPumps(): Promise<HydroPumps> {
	const d = await aiJson<HydroPumps>(`${AI_PATHS.hydro}/hydro/pumps`);
	return { ...d, stations: arr(d.stations) };
}

/** The 18–19 Aug 2025 Mumbai replay (the service caches it; the first run takes a moment). */
export async function postReplay(event = '2025-08-19'): Promise<HydroReplay> {
	if (!/^\d{4}-\d{2}-\d{2}$/.test(event)) throw new AiDown('invalid replay event');
	return aiJson<HydroReplay>(`${AI_PATHS.hydro}/hydro/replay?event=${event}`, { method: 'POST' }, 120_000);
}

// ── forecast ─────────────────────────────────────────────────────────────

export async function getForecast(horizonMin = 120): Promise<ForecastDoc> {
	const h = Math.max(15, Math.min(120, Math.round(horizonMin / 15) * 15));
	const d = await aiJson<ForecastDoc>(`${AI_PATHS.forecast}/forecast/segments?horizon_min=${h}`, {}, 90_000);
	return { ...d, segments: arr<ForecastSegment>(d.segments).map((s) => ({ ...s, steps: arr(s.steps) })), proposals: arr(d.proposals), data_labels: arr(d.data_labels) };
}

// ── twin ─────────────────────────────────────────────────────────────────

export interface TwinAsk {
	junction_ids?: number[];
	forecast?: { vc: number; in_min: number; junction?: number; segment_ids?: number[] } | null;
	horizon_min?: number;
}

/** POST /twin/propose: compute only (the twin never writes a signal). */
export async function postTwinPropose(ask: TwinAsk = {}): Promise<TwinResult> {
	const body: Record<string, unknown> = { horizon_min: ask.horizon_min ?? 45, series: false, explain: true };
	if (ask.junction_ids?.length) body.junction_ids = ask.junction_ids.filter((j) => Number.isInteger(j)).slice(0, 4);
	if (ask.forecast) body.forecast = { source: 'forecast', ...ask.forecast, vc: Math.min(1.6, Math.max(0.01, ask.forecast.vc)) };
	return aiJson<TwinResult>(`${AI_PATHS.twin}/twin/propose`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }, 45_000);
}
