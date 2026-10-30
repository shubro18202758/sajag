/**
 * Timeline binning, range presets and axis ticks (SPEC §5.3), pure.
 *
 *   binRows      rows → histogram bins over [start, end] (all, and linked to
 *                the selection); a row on `end` falls in the last bin
 *   RANGES       1 h · 6 h · 24 h · 7 d, plus "Fit to the data" (fitRange)
 *   olderNotLoaded  /city/feed returns at most the newest 500 rows and has no
 *                `until`: a range that starts before the oldest loaded row
 *                of a capped feed is marked "older rows not loaded"
 *   axisTicks    IST ticks at a step that keeps labels apart (00:00 carries
 *                its day: "00:00 24 Oct"); the replay axis is TAPE time
 *                (t+mm:ss), never IST
 */
import { fmtDay, fmtTime, istDay } from '$lib/ui/format/format';

export const MIN = 60_000;
export const HOUR = 60 * MIN;
export const DAY = 24 * HOUR;

/** Bins of the histogram (one per 3.75 min over 6 h, as the prototype draws). */
export const DEFAULT_BINS = 96;

/** The loaded-feed cap (`/city/feed` returns at most this many newest rows). */
export const FEED_CAP = 500;

export type RangeId = '1h' | '6h' | '24h' | '7d';

export const RANGES: readonly { id: RangeId; ms: number }[] = [
	{ id: '1h', ms: HOUR },
	{ id: '6h', ms: 6 * HOUR },
	{ id: '24h', ms: DAY },
	{ id: '7d', ms: 7 * DAY },
];

export const DEFAULT_RANGE: RangeId = '6h';

export function rangeMs(id: RangeId | string): number {
	return RANGES.find((r) => r.id === id)?.ms ?? 6 * HOUR;
}

/** The bin of moment `t` over [start, end] in `bins` bins, or -1 outside. A row on `end` is in the last bin. */
export function binIndex(t: number, start: number, end: number, bins = DEFAULT_BINS): number {
	if (!(end > start) || !Number.isFinite(t) || t < start || t > end) return -1;
	return Math.min(bins - 1, Math.floor(((t - start) / (end - start)) * bins));
}

export interface Histogram {
	bins: number;
	start: number;
	end: number;
	all: number[];
	linked: number[];
	/** The tallest bin (≥ 1). */
	max: number;
	/** Rows inside [start, end]. */
	total: number;
	/** Of them, rows that name the selection or one of its linked objects. */
	linkedTotal: number;
}

/** Bin `rows` over [start, end]; `related` marks the rows linked to the selection. */
export function binRows(
	rows: readonly { t: number; urns: readonly string[] }[],
	start: number,
	end: number,
	related?: ReadonlySet<string> | null,
	bins = DEFAULT_BINS,
): Histogram {
	const all = new Array<number>(bins).fill(0);
	const linked = new Array<number>(bins).fill(0);
	let total = 0;
	let linkedTotal = 0;
	for (const r of rows) {
		const i = binIndex(r.t, start, end, bins);
		if (i < 0) continue;
		all[i]++;
		total++;
		if (related && related.size && r.urns.some((u) => related.has(u))) {
			linked[i]++;
			linkedTotal++;
		}
	}
	return { bins, start, end, all, linked, max: Math.max(1, ...all), total, linkedTotal };
}

/** The [t0, t1] a bin covers. */
export function binSpan(h: Pick<Histogram, 'bins' | 'start' | 'end'>, i: number): [number, number] {
	const w = (h.end - h.start) / h.bins;
	return [h.start + i * w, h.start + (i + 1) * w];
}

/**
 * True when the range starts before the oldest loaded row of a CAPPED feed
 * (the feed holds `loaded` rows, at least `cap`): rows older than that exist
 * on the server but were never read.
 */
export function olderNotLoaded(start: number, oldestLoaded: number | null, loaded: number, cap = FEED_CAP): boolean {
	return oldestLoaded != null && loaded >= cap && start < oldestLoaded;
}

/** The oldest time in rows (null when empty). */
export function oldestOf(rows: readonly { t: number }[]): number | null {
	let m = Infinity;
	for (const r of rows) if (r.t < m) m = r.t;
	return Number.isFinite(m) ? m : null;
}

/**
 * "Fit to the data": the span of the loaded rows and event spans, ending at
 * `now`, at least 15 min, padded by 2 % on the left.
 */
export function fitRange(rows: readonly { t: number }[], spans: readonly { start: number; end: number | null }[], now: number): [number, number] {
	let a = oldestOf(rows) ?? Infinity;
	for (const s of spans) if (s.start < a && now - s.start <= 30 * DAY) a = s.start;
	if (!Number.isFinite(a) || a >= now) return [now - 15 * MIN, now];
	const span = Math.max(15 * MIN, now - a);
	return [now - span * 1.02, now];
}

/** The tick step that keeps labels at least `minPx` apart over `widthPx`. */
export function tickStep(spanMs: number, widthPx: number, minPx = 72): number {
	const steps = [5 * MIN, 10 * MIN, 15 * MIN, 30 * MIN, HOUR, 2 * HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR, DAY, 2 * DAY];
	const per = widthPx > 0 ? spanMs / widthPx : spanMs;
	return steps.find((s) => s / per >= minPx) ?? 2 * DAY;
}

/** IST offset from UTC (ms): ticks fall on IST clock boundaries. */
const IST_OFFSET = 5.5 * HOUR;

export interface AxisTick {
	t: number;
	label: string;
	/** A day boundary (the label carries the day). */
	major: boolean;
}

/** IST ticks over [start, end]: "22:00", "00:00 24 Oct" (a day step: "24 Oct"). */
export function axisTicks(start: number, end: number, widthPx: number): AxisTick[] {
	if (!(end > start)) return [];
	const step = tickStep(end - start, widthPx);
	const out: AxisTick[] = [];
	let t = Math.ceil((start + IST_OFFSET) / step) * step - IST_OFFSET;
	for (let n = 0; t <= end && n < 400; t += step, n++) {
		const hm = fmtTime(t);
		const dayStart = hm === '00:00';
		out.push({ t, label: step >= DAY ? fmtDay(t) : dayStart ? `${hm} ${fmtDay(t)}` : hm, major: dayStart });
	}
	return out;
}

/** "t+mm:ss" (or "t+h:mm:ss") — the replay axis is tape time, never IST. */
export function tapeLabel(sec: number): string {
	const s = Math.max(0, Math.round(sec));
	const h = Math.floor(s / 3600);
	const m = Math.floor((s % 3600) / 60);
	const r = String(s % 60).padStart(2, '0');
	return h ? `t+${h}:${String(m).padStart(2, '0')}:${r}` : `t+${String(m).padStart(2, '0')}:${r}`;
}

/** Tape-time ticks over [0, duration] seconds. */
export function tapeTicks(durationSec: number, widthPx: number): AxisTick[] {
	if (!(durationSec > 0)) return [];
	const steps = [10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200];
	const per = widthPx > 0 ? durationSec / widthPx : durationSec;
	const step = steps.find((s) => s / per >= 72) ?? 7200;
	const out: AxisTick[] = [];
	for (let s = 0; s <= durationSec && out.length < 400; s += step) out.push({ t: s, label: tapeLabel(s), major: false });
	return out;
}

/** The two ends of a range fall on different IST days. */
export function spansDays(start: number, end: number): boolean {
	return istDay(start) !== istDay(end);
}
