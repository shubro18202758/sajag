/**
 * Shared, short-lived reads of the hydro service (one nowcast answer serves every panel and card on a page for 60 s;
 * tide and rain the same). A failed read is forgotten at once, so the next ask retries. Formatting helpers for the
 * console (IST clock, Latin digits) live here too.
 */
import { fetchNowcast, fetchRain, fetchTide } from './api';
import type { Nowcast, RainNow, TideNow } from './model';

const TTL = 60_000;

function memo<T>(load: () => Promise<T>): () => Promise<T> {
	let at = 0;
	let flight: Promise<T> | null = null;
	return () => {
		if (flight && Date.now() - at < TTL) return flight;
		at = Date.now();
		flight = load().catch((err) => {
			flight = null;
			throw err;
		});
		return flight;
	};
}

export const nowcast: () => Promise<Nowcast> = memo(() => fetchNowcast());
export const tide: () => Promise<TideNow> = memo(() => fetchTide());
export const rain: () => Promise<RainNow> = memo(() => fetchRain());

const HM = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: 'Asia/Kolkata' });

/** HH:MM IST in Latin digits (the console's one clock format). */
export function istClock(ms: number | null): string {
	return ms !== null && Number.isFinite(ms) ? HM.format(ms) : '—';
}

/** A number for the console: fixed decimals, Latin digits, a dash for none. */
export function fx(v: number | null | undefined, digits = 2): string {
	return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—';
}
