/**
 * City vitals — the health surfaces CITY VITALS fuses beside the registry
 * and the ops store (which already carry posture, decisions, units, ANPR
 * and the signal writer):
 *
 *   ingest     10 s  GET /gods-eye/feeds         oracle ingest msgs/min + last age
 *   brain      15 s  GET /api/convoy/health      decider (loaded/loading/p95) + Gemma
 *   retention  30 s  GET /api/v1/vehicles/retention   the C6 reaper's health
 *   emulator   15 s  GET /api/emulator/…/runs + …/living-city (C-G; 404 tolerated)
 *
 * Every rung keeps its own honest state ('ok' | 'not-deployed' | 'down' |
 * 'idle') and its last-good value; nothing here is derived client-side.
 * Reference-counted, in-flight guarded, paused while hidden.
 *
 * seed()/unseed(): the /design harnesses only (fictional values, like
 * cityRegistry.seed): a seeded store stops its timers and its visibility
 * listener, starts no poller, and drops any answer still in flight, so a
 * harness's fixtures are never replaced by a backend's answer; unseed()
 * drops the values and, if a page still holds the store, polls again (one
 * listener, never a second).
 *
 * `shown` is what the mounted City vitals variant (the map-mode card or the
 * Info tab, CityVitals.svelte — one at a time) publishes for the canvas
 * test snapshot, window.__GODS_EYE__.vitals: the same shape either way.
 * Variants attach()/detach(): `shown` is cleared only when the last one
 * unmounts, and attach() returns how many are mounted (a page that mounts
 * two at once breaks SPEC §12.1.2; the component warns in dev).
 */

import { createPollGate } from '$lib/ops/client';
import {
	NotDeployed,
	fetchBrainHealth,
	fetchEmulatorRuns,
	fetchIngestHealth,
	fetchLivingCity,
	fetchRetention,
	type BrainHealth,
	type EmulatorRunRow,
	type IngestHealth,
	type LivingCityStatus,
	type RetentionHealth,
} from '../city-api';

export type RungState = 'idle' | 'ok' | 'not-deployed' | 'down';

export interface Rung<T> {
	state: RungState;
	value: T | null;
	updatedAt: number;
	note: string | null;
}

function idle<T>(): Rung<T> {
	return { state: 'idle', value: null, updatedAt: 0, note: null };
}

const CADENCE = { ingest: 10_000, brain: 15_000, retention: 30_000, emulator: 15_000 } as const;

/**
 * The values CITY VITALS renders right now, published by the rail itself
 * (CityVitals.svelte) and mirrored onto the canvas test snapshot
 * (window.__GODS_EYE__.vitals) — what the operator reads, not a re-derivation.
 */
export interface VitalsShown {
	/** band null = UNKNOWN (a stale city band — never shown as GREEN). */
	posture: { band: string | null; ageSec: number | null; heldSec?: number | null; basis: string; stale: boolean; source: string; urn: string | null; simulated?: boolean } | null;
	events: { total: number; active: number; emulated: number; kinds: Record<string, number> };
	decisions: { total: number; echallans: number; dispatchRequests: number; ambulance: number };
	units: { out: number; enRoute: number; onScene: number };
	anpr: { hits15m: number; reads15m: number; reporting: number; cameras: number };
	signals: { writerOn: boolean | null; twinInFlight: number | null; programs: number; green: number; amber: number; red: number };
	feeds: {
		ingestPerMin: number | null;
		ingestAgeSec: number | null;
		simulated: boolean;
		registryEntities: number;
		registryAgeSec: number | null;
		sightingAgeSec: number | null;
		emulatorRun: number | null;
		livingCity: string;
	};
	ai: { decider: string; p95Ms: number | null; gemma: string; degraded: boolean } | null;
	ethics: { reaper: string; consecutiveFailures: number | null; lawfulBasis: Record<string, number>; platesMasked: boolean };
}

class CityVitals {
	ingest = $state.raw<Rung<IngestHealth>>(idle());
	brain = $state.raw<Rung<BrainHealth>>(idle());
	retention = $state.raw<Rung<RetentionHealth>>(idle());
	runs = $state.raw<Rung<EmulatorRunRow[]>>(idle());
	livingCity = $state.raw<Rung<LivingCityStatus>>(idle());
	/** What the mounted CITY VITALS rail shows (null when no rail is mounted). */
	shown = $state.raw<VitalsShown | null>(null);

	/** True while a /design harness has seeded the rungs: no poller starts. */
	seeded = $state(false);

	private holders = 0;
	private timers: ReturnType<typeof setInterval>[] = [];
	private gate = createPollGate();
	private onVisibility: (() => void) | null = null;
	/** The mounted City vitals variants (one at a time on a page: SPEC §12.1.2). */
	private variants = new Set<symbol>();

	start() {
		this.holders++;
		this.begin();
	}

	stop() {
		this.holders = Math.max(0, this.holders - 1);
		if (this.holders > 0) return;
		this.halt();
	}

	/** Timers and the visibility listener, once (never while seeded). */
	private begin() {
		if (this.timers.length || this.seeded) return;
		this.pollAll();
		this.timers.push(setInterval(() => void this.gate('ingest', () => this.pollIngest()), CADENCE.ingest));
		this.timers.push(setInterval(() => void this.gate('brain', () => this.pollBrain()), CADENCE.brain));
		this.timers.push(setInterval(() => void this.gate('retention', () => this.pollRetention()), CADENCE.retention));
		this.timers.push(setInterval(() => void this.gate('emulator', () => this.pollEmulator()), CADENCE.emulator));
		if (typeof document !== 'undefined' && !this.onVisibility) {
			this.onVisibility = () => {
				if (!document.hidden && !this.seeded) this.pollAll();
			};
			document.addEventListener('visibilitychange', this.onVisibility);
		}
	}

	/** Stop the timers and drop the visibility listener (the holders stay counted). */
	private halt() {
		for (const t of this.timers) clearInterval(t);
		this.timers = [];
		if (this.onVisibility && typeof document !== 'undefined') {
			document.removeEventListener('visibilitychange', this.onVisibility);
		}
		this.onVisibility = null;
	}

	/** A City vitals variant mounts; returns how many are mounted now (more than one is a page bug). */
	attach(id: symbol): number {
		this.variants.add(id);
		return this.variants.size;
	}

	/** A City vitals variant unmounts; `shown` is cleared only when none is left. */
	detach(id: symbol) {
		this.variants.delete(id);
		if (!this.variants.size) this.shown = null;
	}

	/**
	 * Set the rungs from fictional values without polling — the /design
	 * harnesses only. Rungs left out stay idle.
	 */
	seed(values: { ingest?: IngestHealth; brain?: BrainHealth; retention?: RetentionHealth; runs?: EmulatorRunRow[]; livingCity?: LivingCityStatus }) {
		const at = Date.now();
		const ok = <T>(v: T | undefined): Rung<T> => (v === undefined ? idle<T>() : { state: 'ok', value: v, updatedAt: at, note: null });
		// no timer, no listener, and (pollX checks `seeded`) no answer still in flight replaces a fixture
		this.halt();
		this.seeded = true;
		this.ingest = ok(values.ingest);
		this.brain = ok(values.brain);
		this.retention = ok(values.retention);
		this.runs = ok(values.runs);
		this.livingCity = ok(values.livingCity);
	}

	/** Drop seeded values (a harness unmounting): idle again; polls again if a page still holds the store. */
	unseed() {
		if (!this.seeded) return;
		this.seeded = false;
		this.ingest = idle();
		this.brain = idle();
		this.retention = idle();
		this.runs = idle();
		this.livingCity = idle();
		if (this.holders > 0) this.begin();
	}

	private pollAll() {
		void this.gate('ingest', () => this.pollIngest());
		void this.gate('brain', () => this.pollBrain());
		void this.gate('retention', () => this.pollRetention());
		void this.gate('emulator', () => this.pollEmulator());
	}

	private async run<T>(prev: Rung<T>, read: () => Promise<T>): Promise<Rung<T>> {
		try {
			return { state: 'ok', value: await read(), updatedAt: Date.now(), note: null };
		} catch (err) {
			if (err instanceof NotDeployed) {
				return { state: 'not-deployed', value: null, updatedAt: prev.updatedAt, note: 'not deployed (404)' };
			}
			return {
				state: 'down',
				value: prev.value,
				updatedAt: prev.updatedAt,
				note: err instanceof Error ? err.message.slice(0, 140) : String(err),
			};
		}
	}

	// every answer is dropped when a harness seeded the store while it was in flight

	private async pollIngest() {
		const next = await this.run(this.ingest, async () => {
			const v = await fetchIngestHealth(AbortSignal.timeout(6000));
			if (!v) throw new Error('oracle /health carried no ingest block');
			return v;
		});
		if (!this.seeded) this.ingest = next;
	}

	private async pollBrain() {
		const next = await this.run(this.brain, () => fetchBrainHealth(AbortSignal.timeout(6000)));
		if (!this.seeded) this.brain = next;
	}

	private async pollRetention() {
		const next = await this.run(this.retention, () => fetchRetention(AbortSignal.timeout(6000)));
		if (!this.seeded) this.retention = next;
	}

	private async pollEmulator() {
		const runs = await this.run(this.runs, () => fetchEmulatorRuns(6, AbortSignal.timeout(8000)));
		if (this.seeded) return;
		this.runs = runs;
		const living = await this.run(this.livingCity, () => fetchLivingCity(AbortSignal.timeout(6000)));
		if (!this.seeded) this.livingCity = living;
	}
}

export const cityVitals = new CityVitals();
