/**
 * The City band chart's geometry (SPEC §5.3 "BandHistoryChart", §6.3): a
 * step chart on the band ladder with a real time axis. Pure, so the unit
 * test (tests/wall.unit.mjs) checks the axis and the BLACK hairline without
 * a browser.
 *
 *   rows      the ladder, top to bottom: Black, Red, Amber, Green (a row
 *             per band, its label in the left gutter)
 *   segments  one bar per held band: a reading holds until the next one;
 *             the newest holds until the end of the window. Before the
 *             first reading nothing is drawn: an unknown stretch is never
 *             painted as Green.
 *   BLACK     a translucent dark fill with a 1 px hairline in the band's
 *             red (--v-band-black-fill / --v-band-black-hairline), the one
 *             rule for BLACK everywhere (SPEC §2.4); never an opaque void
 *   joins     a neutral hairline where the band changes
 *   ticks     IST-aligned (5 min … 1 d steps, at most one per 64 px), labelled
 *             hh:mm, or "24 Oct" for day steps; the axis is the window, so
 *             1 h / 6 h / 24 h / 7 d each read true
 */
import { fmtDay, fmtTime } from '$lib/ui/format/format';
import type { BandCode } from '$lib/ops/types';

/** The ladder, top to bottom (the most severe band on top). */
export const BAND_LADDER: readonly BandCode[] = ['BLACK', 'RED', 'AMBER', 'GREEN'];

/** Fill of a band's bar (the band ladder's own tokens). */
export const BAND_FILL: Readonly<Record<BandCode, string>> = {
	GREEN: 'var(--v-band-green)',
	AMBER: 'var(--v-band-amber)',
	RED: 'var(--v-band-red)',
	BLACK: 'var(--v-band-black-fill)',
};

/** BLACK's hairline: a 1 px stroke in the band's red, so a black bar never reads as a hole. */
export const BLACK_HAIRLINE = 'var(--v-band-black-hairline)';

/** Left gutter for the ladder's labels, px. */
export const GUTTER = 52;
/** Height of one ladder row, px. */
export const ROW_H = 17;
/** Bar thickness, px. */
export const BAR_H = 10;
/** Room under the plot for the axis labels, px. */
export const AXIS_H = 18;
/** The narrowest a tick may sit from the next, px. */
export const TICK_MIN_PX = 64;

const IST_OFFSET_MS = 330 * 60_000;
const MIN = 60_000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;
const STEPS = [5 * MIN, 10 * MIN, 15 * MIN, 30 * MIN, HOUR, 2 * HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR, DAY];

export interface BandReading {
	ts: number;
	band: BandCode;
}

export interface BandRow {
	band: BandCode;
	/** Centre line of the row. */
	y: number;
}

export interface BandSegment {
	band: BandCode;
	t0: number;
	t1: number;
	x: number;
	y: number;
	w: number;
	h: number;
	fill: string;
	/** The hairline (BLACK only), else null. */
	stroke: string | null;
}

export interface BandJoin {
	x: number;
	y0: number;
	y1: number;
}

export interface AxisTick {
	t: number;
	x: number;
	label: string;
}

export interface BandChartModel {
	width: number;
	height: number;
	plot: { x0: number; x1: number; top: number; bottom: number };
	rows: BandRow[];
	segments: BandSegment[];
	joins: BandJoin[];
	ticks: AxisTick[];
	/** True when no reading falls in (or holds into) the window. */
	empty: boolean;
}

/** Centre line of a band's row. */
export function rowY(band: BandCode): number {
	return 4 + BAND_LADDER.indexOf(band) * ROW_H + ROW_H / 2;
}

/**
 * IST-aligned ticks across [a, b] mapped onto [x0, x1]: the smallest step
 * that keeps ticks at least TICK_MIN_PX apart. Day steps label the day.
 */
export function axisTicks(a: number, b: number, x0: number, x1: number, minPx = TICK_MIN_PX): AxisTick[] {
	if (!(b > a) || !(x1 > x0)) return [];
	const span = b - a;
	const room = Math.max(1, Math.floor((x1 - x0) / minPx));
	const step = STEPS.find((s) => span / s <= room) ?? STEPS[STEPS.length - 1];
	const X = (t: number) => x0 + ((t - a) / span) * (x1 - x0);
	const out: AxisTick[] = [];
	// the first IST-aligned instant at or after a (IST = UTC + 5:30)
	let t = Math.ceil((a + IST_OFFSET_MS) / step) * step - IST_OFFSET_MS;
	for (; t <= b && out.length < 64; t += step) {
		out.push({ t, x: Math.round(X(t) * 10) / 10, label: step >= DAY ? fmtDay(t) : fmtTime(t) });
	}
	return out;
}

/**
 * The chart for `readings` over `window`. `current` (the committed band and
 * since when) extends the series when the readings start later than it.
 */
export function bandChart(
	readings: readonly BandReading[],
	window: readonly [number, number],
	opts: { width: number; current?: { band: BandCode; since: number | null } | null } = { width: 400 },
): BandChartModel {
	const width = Math.max(GUTTER + 40, Math.round(opts.width));
	const [a, b] = window;
	const plotH = BAND_LADDER.length * ROW_H + 8;
	const height = plotH + AXIS_H;
	const x0 = GUTTER;
	const x1 = width - 8;
	const span = Math.max(1, b - a);
	const X = (t: number) => x0 + ((Math.min(b, Math.max(a, t)) - a) / span) * (x1 - x0);
	const rows = BAND_LADDER.map((band) => ({ band, y: rowY(band) }));

	const pts = readings
		.filter((p) => Number.isFinite(p.ts) && BAND_LADDER.includes(p.band))
		.slice()
		.sort((p, q) => p.ts - q.ts);
	const cur = opts.current;
	if (cur && BAND_LADDER.includes(cur.band) && cur.since != null && Number.isFinite(cur.since)) {
		if (!pts.length || cur.since < pts[0].ts) pts.unshift({ ts: cur.since, band: cur.band });
	}

	// collapse repeats: a step chart changes only where the band does
	const steps: BandReading[] = [];
	for (const p of pts) if (!steps.length || steps[steps.length - 1].band !== p.band) steps.push(p);

	const segments: BandSegment[] = [];
	const joins: BandJoin[] = [];
	for (let i = 0; i < steps.length; i++) {
		const s = steps[i];
		const t0 = s.ts;
		const t1 = i + 1 < steps.length ? steps[i + 1].ts : b;
		if (t1 <= a || t0 >= b) continue;
		const xa = X(t0);
		const xb = X(t1);
		segments.push({
			band: s.band,
			t0: Math.max(t0, a),
			t1: Math.min(t1, b),
			x: round1(xa),
			y: round1(rowY(s.band) - BAR_H / 2),
			w: round1(Math.max(1.5, xb - xa)),
			h: BAR_H,
			fill: BAND_FILL[s.band],
			stroke: s.band === 'BLACK' ? BLACK_HAIRLINE : null,
		});
		const next = steps[i + 1];
		if (next && next.ts > a && next.ts < b) {
			const y0 = rowY(s.band);
			const y1 = rowY(next.band);
			joins.push({ x: round1(X(next.ts)), y0: Math.min(y0, y1), y1: Math.max(y0, y1) });
		}
	}

	return {
		width,
		height,
		plot: { x0, x1, top: 4, bottom: plotH },
		rows,
		segments,
		joins,
		ticks: axisTicks(a, b, x0, x1),
		empty: segments.length === 0,
	};
}

function round1(n: number): number {
	return Math.round(n * 10) / 10;
}
