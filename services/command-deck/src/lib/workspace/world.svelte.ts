/**
 * The live world the selectors, the store, the omnibar and the inspector
 * read: the city registry's snapshot, the recent dossiers, the registered
 * object and decision-unit sources, and the city feed.
 *
 * The object graph is rebuilt only when one of its inputs changes — a
 * registry poll (4 s), a dossier answer, a registration — or on the 4 s
 * tick that picks up registered sources (history) between polls. Reading
 * graph() inside a component subscribes it to exactly those signals.
 */
import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
import { dossier } from '$lib/gods-eye/entities/dossier.svelte';
import { fusionFeed } from '$lib/gods-eye/hud/feed.svelte';
import type { FeedRow } from '$lib/gods-eye/city-api';
import { EMPTY_GRAPH, buildObjectGraph } from './objects';
import { registryClock } from './registry-clock.svelte';
import { sourceRows, unitSourceRows } from './registry';
import { createSelectors, type World } from './selectors';
import type { DecisionUnitSummary, ObjectGraph, ObjectRow } from './types';

const TICK_MS = 4000;

class LiveWorld implements World {
	/** Bumped every 4 s while a page reads the world (registered sources between polls). */
	tick = $state(0);
	/**
	 * The traffic readings are simulated (the corridor summary's feed label is not 'live'): a road segment's record
	 * then says SIMULATED, never "Live feed" (kinds/common.ts baseRow). Set by the pages that read the ops store.
	 */
	simulatedFeed = $state(true);

	#graph: ObjectGraph = EMPTY_GRAPH;
	#registry: ObjectRow[] = [];
	#key = '';
	#ticker: ReturnType<typeof setInterval> | null = null;

	graph(): ObjectGraph {
		this.#startTicker();
		const key = `${cityRegistry.version}|${dossier.version}|${registryClock.value}|${this.tick}|${this.simulatedFeed}`;
		if (key !== this.#key) {
			const entities = cityRegistry.entities();
			const graph = buildObjectGraph({ entities, dossiers: dossier.recent(), rows: sourceRows(), ctx: { simulatedFeed: this.simulatedFeed } });
			this.#registry = entities.map((e) => graph.get(e.urn)).filter((r): r is ObjectRow => !!r);
			this.#graph = graph;
			this.#key = key;
		}
		return this.#graph;
	}

	registry(): readonly ObjectRow[] {
		this.graph();
		return this.#registry;
	}

	feed(): readonly FeedRow[] {
		return fusionFeed.rows;
	}

	units(): readonly DecisionUnitSummary[] {
		return unitSourceRows();
	}

	now(): number {
		return Date.now();
	}

	#startTicker() {
		if (this.#ticker || typeof window === 'undefined') return;
		this.#ticker = setInterval(() => {
			if (typeof document !== 'undefined' && document.hidden) return;
			this.tick++;
		}, TICK_MS);
	}
}

export const liveWorld = new LiveWorld();

/** The canonical selectors over the live world (SPEC §7.4). */
export const selectors = createSelectors(() => liveWorld);
