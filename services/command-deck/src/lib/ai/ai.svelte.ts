/**
 * The console's AI state (runes): what the forecast, hydro and twin services last said, polled with back-off
 * (poll.ts) while a page that shows them is mounted, and the officers' decisions on their proposals.
 *
 *   ai.use('hydro', 'tide', 'rain', 'forecast', 'twin', 'decisions')  → a release function (reference-counted:
 *   Home, Map and Decide each ask for what they show; the last one out stops the pollers)
 *
 * Cadences: nowcast 2 min (the service caches the rain 10 min), tide 10 min, rain 5 min, forecast 5 min (the
 * service caches 5 min; always the full 120 min horizon so every surface shares one computation), twin 10 min
 * (asked about the two soonest forecast crossings at signalised junctions, plus its own most stressed signal —
 * only once a forecast has answered: with nothing to ask, no compute POST leaves the page),
 * decisions 30 s. A feed that fails says so in `feeds[name]` — never a zero.
 */
import { operatorSession } from '$lib/shell/session.svelte';
import { getForecast, getNowcast, getRain, getTide, postReplay, postTwinPropose, AiNotDeployed, AiSignIn } from './client';
import { createPoller, type Poller } from './poll';
import { aiCards, replayProposals, twinAsks, type AiCard } from './model';
import type { AiDecisionInput, AiDecisionResult } from './writer';
import type { AiDecisionRow, ForecastDoc, HydroNowcast, HydroRain, HydroReplay, HydroTide, TwinResult } from './types';

export type FeedName = 'hydro' | 'tide' | 'rain' | 'forecast' | 'twin' | 'decisions';

export interface FeedState {
	status: 'idle' | 'ok' | 'down' | 'not-deployed' | 'sign-in';
	error: string | null;
	at: number | null;
}

const idle = (): FeedState => ({ status: 'idle', error: null, at: null });

function failure(err: unknown): FeedState {
	return {
		status: err instanceof AiNotDeployed ? 'not-deployed' : err instanceof AiSignIn ? 'sign-in' : 'down',
		error: err instanceof Error ? err.message : String(err),
		at: Date.now(),
	};
}

const BASE_MS: Record<FeedName, number> = { hydro: 120_000, tide: 600_000, rain: 300_000, forecast: 300_000, twin: 600_000, decisions: 30_000 };

class AiState {
	nowcast = $state<HydroNowcast | null>(null);
	tide = $state<HydroTide | null>(null);
	rain = $state<HydroRain | null>(null);
	forecast = $state<ForecastDoc | null>(null);
	twins = $state<TwinResult[]>([]);
	replay = $state<HydroReplay | null>(null);
	replayState = $state<FeedState>(idle());
	feeds = $state<Record<FeedName, FeedState>>({ hydro: idle(), tide: idle(), rain: idle(), forecast: idle(), twin: idle(), decisions: idle() });
	/** Decisions by proposal id: the platform's record, and any kept on this console. */
	decisions = $state<Record<string, AiDecisionRow>>({});
	/** The platform's record answered (false: not deployed yet — decisions stay on this console and say so). */
	platformLog = $state<boolean | null>(null);
	/** The decisions taken on THIS console this session (Decide's "Decided on this console" counts them). */
	decidedHere = $state<Record<string, 'approve' | 'reject'>>({});
	/** Decide's hindsight exercise (the 18–19 Aug 2025 replay's proposals) is shown. */
	exercise = $state(false);

	#pollers = new Map<FeedName, Poller>();
	#users = new Map<FeedName, number>();

	/** A feed's turn; 'skip' when it has nothing to ask yet (the twin waits for a forecast). */
	#run: Record<FeedName, () => Promise<void | 'skip'>> = {
		hydro: async () => {
			this.nowcast = await getNowcast();
		},
		tide: async () => {
			this.tide = await getTide(36);
		},
		rain: async () => {
			this.rain = await getRain();
		},
		forecast: async () => {
			this.forecast = await getForecast(120);
			this.#pollers.get('twin')?.kick();
		},
		twin: async () => {
			// the twin is asked about the forecast's stress (its crossings, then its own most stressed signal): no
			// forecast yet, no question — a compute-only POST is never sent on a page that has nothing to ask
			if (!this.forecast) return 'skip';
			const asks = twinAsks(this.forecast, 2);
			const out: TwinResult[] = [];
			let lastErr: unknown = null;
			for (const a of asks) {
				try {
					const r = await postTwinPropose({ junction_ids: [a.junction], forecast: { vc: a.vc, in_min: a.inMin, junction: a.junction, segment_ids: a.segmentId != null ? [a.segmentId] : [] } });
					out.push({ ...r, asked_for: a.proposalId });
				} catch (err) {
					lastErr = err; // a crossing at a junction the twin has no signal for (422) is skipped
				}
			}
			try {
				out.push(await postTwinPropose({}));
			} catch (err) {
				lastErr = err;
			}
			if (!out.length && lastErr) throw lastErr;
			this.twins = out;
		},
		decisions: async () => {
			// the decision record is an operator read: nothing while the gate waits for a sign-in (no 403 to the console)
			if (operatorSession.gate === true && !operatorSession.officer) return;
			// the writer (and its decision record reads) load with the first page that decides: Decide
			const { fetchDecisions } = await import('./writer');
			const rows = await fetchDecisions();
			this.platformLog = rows !== null;
			if (!rows) return;
			const next = { ...this.decisions };
			for (const r of rows) next[r.proposal_id] = r;
			this.decisions = next;
		},
	};

	/** Start the named feeds for one page; the returned function releases them. */
	use(...names: FeedName[]): () => void {
		if (typeof window === 'undefined') return () => {};
		for (const n of names) {
			this.#users.set(n, (this.#users.get(n) ?? 0) + 1);
			let p = this.#pollers.get(n);
			if (!p) {
				const run = this.#run[n];
				p = createPoller(
					async () => {
						if ((await run()) === 'skip') return;
						this.feeds = { ...this.feeds, [n]: { status: 'ok', error: null, at: Date.now() } };
					},
					{ baseMs: BASE_MS[n], maxMs: Math.max(BASE_MS[n], 300_000), onError: (err) => (this.feeds = { ...this.feeds, [n]: failure(err) }) },
				);
				this.#pollers.set(n, p);
			}
			p.start();
		}
		let released = false;
		return () => {
			if (released) return;
			released = true;
			for (const n of names) {
				const left = (this.#users.get(n) ?? 1) - 1;
				this.#users.set(n, left);
				if (left <= 0) this.#pollers.get(n)?.stop();
			}
		};
	}

	/** Ask a feed again now (Retry). */
	refresh(name: FeedName): void {
		this.#pollers.get(name)?.kick();
	}

	/** The 18–19 Aug 2025 Mumbai replay (POST /hydro/replay; the service caches it). */
	async loadReplay(): Promise<HydroReplay | null> {
		if (this.replay) return this.replay;
		if (this.replayState.status === 'idle' || this.replayState.status === 'down') {
			this.replayState = { status: 'idle', error: null, at: Date.now() };
			try {
				this.replay = await postReplay('2025-08-19');
				this.replayState = { status: 'ok', error: null, at: Date.now() };
			} catch (err) {
				this.replayState = failure(err);
			}
		}
		return this.replay;
	}

	/** Every waiting decision card (decided ones left out; the exercise only while it is shown). */
	get cards(): AiCard[] {
		return aiCards({
			forecast: this.forecast,
			nowcast: this.nowcast,
			exercise: this.exercise ? replayProposals(this.replay) : null,
			twins: this.twins,
			decided: new Set(Object.keys(this.decisions)),
		});
	}

	/** Decide a card as the named officer; the outcome lands in `decisions` (platform or console). */
	async decide(card: AiCard, input: AiDecisionInput): Promise<AiDecisionResult> {
		const { decideAiCard } = await import('./writer');
		const res = await decideAiCard(card, input);
		if (res.ok) {
			this.decisions = { ...this.decisions, [card.id]: res.row };
			this.decidedHere = { ...this.decidedHere, [card.id]: res.row.decision };
		}
		else if (res.refusal === 'already-decided' && res.row) this.decisions = { ...this.decisions, [card.id]: res.row };
		return res;
	}
}

export const ai = new AiState();
