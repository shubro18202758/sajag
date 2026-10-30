/**
 * The map's "updated hh:mm:ss" clock: each live layer marks the moment ITS feed last answered (a real poll, on that
 * feed's own cadence), and the legend shows the newest one. Nothing ticks by itself: a quiet feed leaves its time where
 * it was. A plain module (no runes): the page re-reads it on its own one-second clock.
 */

class LiveClock {
	/** source id → epoch ms of its last good answer. */
	sources: Record<string, number> = {};
	updatedAt: number | null = null;

	mark(source: string, at = Date.now()) {
		this.sources[source] = at;
		if (this.updatedAt == null || at > this.updatedAt) this.updatedAt = at;
	}
}

export const liveClock = new LiveClock();
