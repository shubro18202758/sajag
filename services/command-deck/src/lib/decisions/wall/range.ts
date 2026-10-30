/**
 * The /ops range presets (SPEC §6.3 header): 1 h, 6 h, 24 h, 7 d. The range
 * is the band chart's time axis and the window of the closed-event lists;
 * live operations, decisions and the metric counters are never windowed
 * (SPEC §7.3: live operations are never hidden by a time window).
 */
export const RANGES = ['1h', '6h', '24h', '7d'] as const;
export type WallRange = (typeof RANGES)[number];

export const RANGE_MS: Readonly<Record<WallRange, number>> = {
	'1h': 3_600_000,
	'6h': 6 * 3_600_000,
	'24h': 24 * 3_600_000,
	'7d': 7 * 24 * 3_600_000,
};

export const DEFAULT_RANGE: WallRange = '6h';

/** A preset from untrusted input (a stored choice), else the default. */
export function asRange(v: unknown): WallRange {
	return typeof v === 'string' && (RANGES as readonly string[]).includes(v) ? (v as WallRange) : DEFAULT_RANGE;
}

/** The [from, to] window of a preset ending at `now`. */
export function rangeWindow(r: WallRange, now: number): readonly [number, number] {
	return [now - RANGE_MS[r], now];
}
