/**
 * What the situation wall reads beyond the ops store (read-only GETs through
 * the deck's origin proxy; nothing here writes):
 *
 *   history   GET /api/v1/events?limit=200 — the event history (C-F), every
 *             event with closed ones included; Corridor operations' Completed
 *             and Cancelled tabs and the "in history" count read it. Each row
 *             through the ops client's own mapper (mapEventRow), plus the
 *             wire's update and actual-window instants.
 *   summary   GET /api/v1/corridor/summary — mean corridor speed, congested
 *             and critical roads, provenance; every answer appends one speed
 *             sample (the metric strip's sparkline: this console's readings
 *             since it opened, said so in its tooltip).
 *
 * Reference-counted start/stop, one read in flight per source, paused while
 * the page is hidden (one catch-up round on return). A failed read keeps the
 * last-good answer and says why (`*Note`), never a blank.
 */
import { getCorridorSummary } from '$lib/api/client';
import { createPollGate, mapEventRow } from '$lib/ops/client';
import { ORACLE_V1 } from '$lib/ops/endpoints';
import type { BandCode, CorridorEvent } from '$lib/ops/types';

export const HISTORY_POLL_MS = 30_000;
export const SUMMARY_POLL_MS = 10_000;
/** Speed samples kept (10 s apart: the last 20 min). */
export const SPEED_SAMPLES_MAX = 120;

export interface HistoryEvent {
	event: CorridorEvent;
	/** Epoch ms of the row's last change (wire updated_at), or null. */
	updatedAt: number | null;
	/** Epoch ms the event actually started / ended (wire actual_start / actual_end), or null. */
	actualStart: number | null;
	actualEnd: number | null;
}

export type CorridorSummary = Awaited<ReturnType<typeof getCorridorSummary>>;

const ms = (v: unknown): number | null => {
	const n = typeof v === 'string' ? Date.parse(v) : NaN;
	return Number.isFinite(n) ? n : null;
};

/** Pure: one history row (null when it is not an event). Exported for tests. */
export function historyRow(row: Record<string, unknown>): HistoryEvent | null {
	const event = mapEventRow(row, 'live-events-api');
	if (!event) return null;
	return { event, updatedAt: ms(row.updated_at), actualStart: ms(row.actual_start), actualEnd: ms(row.actual_end) };
}

/** Pure: the history document → rows, newest change first. Exported for tests. */
export function parseHistory(doc: unknown): HistoryEvent[] {
	const rows = Array.isArray(doc)
		? doc
		: doc && typeof doc === 'object' && Array.isArray((doc as Record<string, unknown>).events)
			? ((doc as Record<string, unknown>).events as unknown[])
			: [];
	return rows
		.filter((r): r is Record<string, unknown> => !!r && typeof r === 'object')
		.map(historyRow)
		.filter((r): r is HistoryEvent => r !== null)
		.sort((a, b) => (b.updatedAt ?? 0) - (a.updatedAt ?? 0));
}

class WallData {
	history = $state.raw<HistoryEvent[]>([]);
	historyUpdated = $state(0);
	historyNote = $state<string | null>(null);

	summary = $state.raw<CorridorSummary | null>(null);
	summaryUpdated = $state(0);
	summaryNote = $state<string | null>(null);
	/** Mean corridor speed per answer, oldest first. */
	speedSamples = $state.raw<number[]>([]);
	/**
	 * The city band as this console saw it: its entry time (the engine's
	 * `since`) and every change after it, oldest first. There is no city band
	 * history endpoint, so nothing before the first `since` is known (and
	 * nothing is drawn there).
	 */
	cityBandSeries = $state.raw<Array<{ ts: number; band: BandCode }>>([]);

	private holders = 0;
	private timers: ReturnType<typeof setInterval>[] = [];
	private gate = createPollGate();
	private onVisibility: (() => void) | null = null;

	start() {
		this.holders++;
		if (this.timers.length) return;
		this.refresh();
		this.timers.push(setInterval(() => void this.gate('wall-history', () => this.pollHistory()), HISTORY_POLL_MS));
		this.timers.push(setInterval(() => void this.gate('wall-summary', () => this.pollSummary()), SUMMARY_POLL_MS));
		if (typeof document !== 'undefined') {
			this.onVisibility = () => {
				if (!document.hidden) this.refresh();
			};
			document.addEventListener('visibilitychange', this.onVisibility);
		}
	}

	stop() {
		this.holders = Math.max(0, this.holders - 1);
		if (this.holders > 0) return;
		for (const t of this.timers) clearInterval(t);
		this.timers = [];
		if (this.onVisibility && typeof document !== 'undefined') document.removeEventListener('visibilitychange', this.onVisibility);
		this.onVisibility = null;
	}

	/** The city band now (null: unknown or stale); a change appends a point, a repeat does not. */
	noteCityBand(band: BandCode | null, since: number | null, at = Date.now()) {
		if (!band) return;
		const last = this.cityBandSeries[this.cityBandSeries.length - 1];
		if (last && last.band === band) return;
		const ts = since != null && Number.isFinite(since) && (!last || since > last.ts) ? since : at;
		this.cityBandSeries = [...this.cityBandSeries, { ts, band }].slice(-500);
	}

	/** One read of each source now (in-flight guarded). */
	refresh() {
		void this.gate('wall-history', () => this.pollHistory());
		void this.gate('wall-summary', () => this.pollSummary());
	}

	private async pollHistory() {
		try {
			const res = await fetch(`${ORACLE_V1}/events?limit=200`, { signal: AbortSignal.timeout(8000) });
			if (!res.ok) throw new Error(res.status === 404 ? 'event history not deployed (404)' : `HTTP ${res.status}`);
			this.history = parseHistory(await res.json());
			this.historyUpdated = Date.now();
			this.historyNote = null;
		} catch (err) {
			this.historyNote = `event history unavailable: ${err instanceof Error ? err.message : String(err)}`;
		}
	}

	private async pollSummary() {
		try {
			const s = await getCorridorSummary();
			this.summary = s;
			this.summaryUpdated = Date.now();
			this.summaryNote = null;
			if (Number.isFinite(s.avgSpeedKmh)) this.speedSamples = [...this.speedSamples, s.avgSpeedKmh].slice(-SPEED_SAMPLES_MAX);
		} catch (err) {
			this.summaryNote = `corridor summary unavailable: ${err instanceof Error ? err.message : String(err)}`;
		}
	}
}

export const wallData = new WallData();
