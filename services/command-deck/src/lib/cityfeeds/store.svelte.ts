/**
 * The city-feeds summary, shared by every surface that shows the City chip row (the map and Home): one poller
 * (every 5 minutes, with the AI services' back-off) while at least one surface uses it, none otherwise.
 */
import { createPoller, type Poller } from '$lib/ai/poll';
import { getSummary } from './client';
import type { FeedSummary } from './types';

export type FeedStatus = 'idle' | 'loading' | 'ok' | 'down' | 'not-deployed' | 'signin';

class CityFeedsStore {
	summary = $state<FeedSummary | null>(null);
	status = $state<FeedStatus>('idle');
	#users = 0;
	#poller: Poller | null = null;

	/** Start polling for one surface; the returned function releases it. */
	use(): () => void {
		this.#users++;
		if (!this.#poller) {
			if (this.status === 'idle') this.status = 'loading';
			this.#poller = createPoller(
				async () => {
					try {
						this.summary = await getSummary();
						this.status = 'ok';
					} catch (err) {
						const name = err instanceof Error ? err.name : '';
						this.status = name === 'AiNotDeployed' ? 'not-deployed' : name === 'AiSignIn' ? 'signin' : 'down';
						throw err;
					}
				},
				{ baseMs: 300_000 },
			);
			this.#poller.start();
		}
		let released = false;
		return () => {
			if (released) return;
			released = true;
			this.#users = Math.max(0, this.#users - 1);
			if (this.#users === 0) {
				this.#poller?.stop();
				this.#poller = null;
			}
		};
	}
}

export const cityFeeds = new CityFeedsStore();
