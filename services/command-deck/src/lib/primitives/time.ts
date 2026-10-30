/**
 * IST clock — the legacy wall-time helpers, kept by name for their callers
 * (ops/format.ts, the ops store, /comms) and DELEGATING to THE formatter,
 * src/lib/ui/format/format.ts (SPEC §3.3, §5.2): one implementation, so
 * equal instants render as equal strings on every surface whatever the
 * browser's own zone (every helper pins Asia/Kolkata, 24-hour).
 */
import { IST_ZONE as FORMAT_IST_ZONE, fmtStamp, fmtTime, istDay as formatIstDay, toMs } from '$lib/ui/format/format';

export const IST_ZONE = FORMAT_IST_ZONE;

/** Epoch ms of a number or an ISO string; NaN when neither parses. */
export function toEpochMs(v: number | string | null | undefined): number {
	return toMs(v);
}

/** HH:MM:SS in IST (24 h); '—' for an unparseable moment. */
export function istClock(v: number | string | null | undefined): string {
	return fmtTime(v, { seconds: true });
}

/** HH:MM in IST (24 h); '—' for an unparseable moment. */
export function istHm(v: number | string | null | undefined): string {
	return fmtTime(v);
}

/** The IST calendar day of a moment as YYYY-MM-DD ('' when unparseable). */
export function istDay(v: number | string | null | undefined): string {
	return formatIstDay(v);
}

/**
 * HH:MM in IST, prefixed with the IST date ('27 Jun 09:20') when the moment
 * is not on the IST day of `now` — a window three days out must not read as
 * this morning.
 */
export function istHmDated(v: number | string | null | undefined, now = Date.now()): string {
	return fmtStamp(v, now);
}
