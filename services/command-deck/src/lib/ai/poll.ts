/**
 * Polling with back-off for the AI services (plain TypeScript, no runes: the canvas layers use it too).
 *
 * One poller = one fetch on a cadence. A failure doubles the wait (up to `maxMs`); a "not deployed" answer
 * (404) backs off to the maximum at once — the service is not there, asking every few seconds helps no one; a
 * success returns to the base cadence. A hidden tab skips its turn (and asks again when it is shown), and a
 * fetch never overlaps itself.
 */
import { AiNotDeployed } from './client';

/** The wait after `failures` failures in a row: base × 2^failures, capped at `maxMs`. */
export function backoffMs(baseMs: number, failures: number, maxMs = 5 * 60_000): number {
	if (failures <= 0) return baseMs;
	return Math.min(maxMs, baseMs * 2 ** Math.min(failures, 16));
}

export interface Poller {
	start(): void;
	stop(): void;
	/** Fetch now (still never overlapping a fetch in flight). */
	kick(): void;
	readonly failures: number;
}

const hidden = () => typeof document !== 'undefined' && document.hidden === true;

export function createPoller(run: () => Promise<unknown>, opts: { baseMs: number; maxMs?: number; onError?: (err: unknown) => void }): Poller {
	let timer: ReturnType<typeof setTimeout> | null = null;
	let running = false;
	let busy = false;
	let failures = 0;

	const schedule = (ms: number) => {
		if (!running) return;
		if (timer) clearTimeout(timer);
		timer = setTimeout(tickOnce, ms);
	};

	async function tickOnce() {
		timer = null;
		if (!running) return;
		if (busy || hidden()) {
			schedule(Math.min(opts.baseMs, 5_000));
			return;
		}
		busy = true;
		try {
			await run();
			failures = 0;
		} catch (err) {
			failures = err instanceof AiNotDeployed ? 16 : failures + 1;
			opts.onError?.(err);
		} finally {
			busy = false;
		}
		schedule(backoffMs(opts.baseMs, failures, opts.maxMs));
	}

	return {
		start() {
			if (running) return;
			running = true;
			schedule(0);
		},
		stop() {
			running = false;
			if (timer) clearTimeout(timer);
			timer = null;
		},
		kick() {
			if (!running) return;
			schedule(0);
		},
		get failures() {
			return failures;
		},
	};
}
