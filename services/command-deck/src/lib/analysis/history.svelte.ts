/**
 * The event history the analysis views read (history-api.ts): one GET of
 * /api/v1/events?limit=200 when the first view mounts, then once a minute
 * while any view holds it (reference-counted, in-flight guarded, paused
 * while the page is hidden). A failed read keeps the last good rows and
 * says so in `note`; a 404 is "not deployed", never a crash.
 *
 * `seed()` serves fixture rows with no request at all (the /design
 * harness); `unseed()` forgets them.
 */
import { createPollGate } from '$lib/ops/client';
import { NotDeployed } from '$lib/gods-eye/data';
import { EVENT_HISTORY_POLL_MS, fetchEventHistory, type EventHistoryRow } from './history-api';

class EventHistory {
	rows = $state.raw<readonly EventHistoryRow[]>([]);
	status = $state<'idle' | 'ok' | 'not-deployed' | 'down'>('idle');
	note = $state<string | null>(null);
	updatedAt = $state(0);

	#holders = 0;
	#timer: ReturnType<typeof setInterval> | null = null;
	#gate = createPollGate();
	#seeded = false;

	/** Hold the history (a view mounted): the first holder starts the minute poll. */
	start(): void {
		this.#holders++;
		if (this.#timer || this.#seeded || typeof window === 'undefined') return;
		void this.#gate('history', () => this.#poll());
		this.#timer = setInterval(() => void this.#gate('history', () => this.#poll()), EVENT_HISTORY_POLL_MS);
	}

	/** Release it (a view unmounted): the last holder stops the poll. */
	stop(): void {
		this.#holders = Math.max(0, this.#holders - 1);
		if (this.#holders > 0) return;
		if (this.#timer) clearInterval(this.#timer);
		this.#timer = null;
	}

	/** Fixture rows, no request (the /design harness). */
	seed(rows: readonly EventHistoryRow[]): void {
		this.#seeded = true;
		if (this.#timer) clearInterval(this.#timer);
		this.#timer = null;
		this.rows = rows;
		this.status = 'ok';
		this.note = 'design harness: fixture history';
		this.updatedAt = Date.now();
	}

	unseed(): void {
		if (!this.#seeded) return;
		this.#seeded = false;
		this.rows = [];
		this.status = 'idle';
		this.note = null;
	}

	async #poll(): Promise<void> {
		try {
			const rows = await fetchEventHistory(AbortSignal.timeout(10_000));
			if (this.#seeded) return;
			this.rows = rows;
			this.status = 'ok';
			this.note = null;
			this.updatedAt = Date.now();
		} catch (err) {
			if (this.#seeded) return;
			if (err instanceof NotDeployed) {
				this.status = 'not-deployed';
				this.note = 'event history not deployed (404)';
			} else {
				this.status = 'down';
				this.note = `event history unreachable (${err instanceof Error ? err.message : String(err)}), last good rows kept`;
			}
		}
	}
}

export const eventHistory = new EventHistory();
