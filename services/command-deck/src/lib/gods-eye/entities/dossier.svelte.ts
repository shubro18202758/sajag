/**
 * Dossier loader — GET /api/v1/city/entity/{kind}/{id} for the selected
 * entity, kept fresh while it stays selected.
 *
 * One request token per selection (an answer for a selection that moved on
 * is dropped), a short per-URN cache so re-selecting or flying to a recent
 * entity costs nothing, and a 6 s refresh while the dossier is open (the
 * audit trail and the related list are live). A 404 is an honest "not in
 * the city picture" state (an entity that left the snapshot, or a URN the
 * oracle does not resolve yet), never an error toast.
 *
 * Privacy rail (C6): the oracle answers 404 for a sighting whose read it
 * may not show (no active earmark and not the evidence of a recommendation).
 * A sighting's 404 is therefore the 'withheld' state — "Withheld: no lawful
 * basis to show individual reads" (SPEC §16.6) — never an error.
 *
 * The recent dossiers (≤ 64, newest last) feed the workspace's object model:
 * their relations name links from both ends. `version` bumps on every new
 * answer so the model rebuilds. `seed()` serves fixtures offline (the
 * /design harnesses): no request is ever made while seeded.
 */

import { pageHidden } from '$lib/ops/client';
import { NotDeployed, fetchDossier, parseUrn, type Dossier } from '../city-api';

const CACHE_TTL_MS = 15_000;
const REFRESH_MS = 6000;
const CACHE_MAX = 64;

export type DossierState = 'idle' | 'loading' | 'ok' | 'not-found' | 'withheld' | 'down';

class DossierLoader {
	urn = $state<string | null>(null);
	state = $state<DossierState>('idle');
	data = $state.raw<Dossier | null>(null);
	note = $state<string | null>(null);
	/** Bumped on every remembered answer (the object model's dependency). */
	version = $state(0);

	private cache = new Map<string, Dossier>();
	private token = 0;
	private timer: ReturnType<typeof setInterval> | null = null;
	/** Seeded (fixtures): answers come from the cache only, nothing is fetched. */
	private offline = false;

	/** Show `urn` (null closes): cached answer first, then a fresh read. */
	open(urn: string | null) {
		if (urn === this.urn) return;
		this.urn = urn;
		this.token++;
		if (this.timer) clearInterval(this.timer);
		this.timer = null;
		if (!urn) {
			this.state = 'idle';
			this.data = null;
			this.note = null;
			return;
		}
		const cached = this.cache.get(urn);
		this.data = cached ?? null;
		this.note = null;
		if (this.offline) {
			this.state = cached ? 'ok' : notFoundState(urn);
			return;
		}
		this.state = cached ? 'ok' : 'loading';
		void this.load(urn, this.token);
		this.timer = setInterval(() => {
			if (!pageHidden() && this.urn === urn) void this.load(urn, this.token);
		}, REFRESH_MS);
	}

	close() {
		this.open(null);
	}

	/** Force a re-read of the open dossier (after an operator action). */
	reload() {
		if (this.urn && !this.offline) void this.load(this.urn, this.token);
	}

	/**
	 * A cached (≤ 15 s) or freshly read dossier for any URN — the canvas
	 * uses it to find the position of an entity the snapshot does not carry
	 * (a completed event, a camera hit older than the snapshot window).
	 */
	async peek(urn: string): Promise<Dossier | null> {
		const hit = this.cache.get(urn);
		if (hit && (this.offline || Date.now() - hit.fetchedAt < CACHE_TTL_MS)) return hit;
		if (this.offline) return null;
		try {
			const d = await fetchDossier(urn, AbortSignal.timeout(8000));
			this.remember(urn, d);
			return d;
		} catch {
			return null;
		}
	}

	/** The recent dossiers, oldest first (≤ 64): the object model's relation source. */
	recent(): readonly Dossier[] {
		void this.version;
		return [...this.cache.values()];
	}

	/**
	 * Serve `dossiers` offline — the /design harnesses only (fictional or
	 * sandbox data). From now on nothing is fetched; an unknown URN is
	 * 'not-found' (a sighting's is 'withheld').
	 */
	seed(dossiers: readonly Dossier[]) {
		this.offline = true;
		if (this.timer) clearInterval(this.timer);
		this.timer = null;
		for (const d of dossiers) this.remember(d.entity.urn, d);
		const urn = this.urn;
		if (urn) {
			const hit = this.cache.get(urn);
			this.data = hit ?? null;
			this.state = hit ? 'ok' : notFoundState(urn);
		}
	}

	/**
	 * Leave seeded mode (a harness unmounting): the fixtures are forgotten and
	 * the loader reads the oracle again, so an SPA navigation away never keeps
	 * a route offline. A no-op when nothing was seeded.
	 */
	unseed() {
		if (!this.offline) return;
		this.close();
		this.offline = false;
		this.cache.clear();
		this.version++;
	}

	private remember(urn: string, d: Dossier) {
		this.cache.delete(urn);
		this.cache.set(urn, d);
		if (this.cache.size > CACHE_MAX) {
			const oldest = this.cache.keys().next().value;
			if (oldest) this.cache.delete(oldest);
		}
		this.version++;
	}

	private async load(urn: string, token: number) {
		try {
			const d = await fetchDossier(urn, AbortSignal.timeout(10_000));
			this.remember(urn, d);
			if (token !== this.token) return;
			this.data = d;
			this.state = 'ok';
			this.note = null;
		} catch (err) {
			if (token !== this.token) return;
			if (err instanceof NotDeployed) {
				this.state = notFoundState(urn);
				this.note =
					this.state === 'withheld'
						? 'no lawful basis to show this read (C6)'
						: 'not in the city picture (404) — the oracle has no dossier for this entity';
			} else {
				this.state = this.data ? 'ok' : 'down';
				this.note = `dossier read failed (${err instanceof Error ? err.message : String(err)})${this.data ? ' — showing last-good' : ''}`;
			}
		}
	}
}

/** A 404's honest state: a sighting the oracle may not show is withheld (C6), anything else not found. */
function notFoundState(urn: string): DossierState {
	return parseUrn(urn)?.kind === 'sighting' ? 'withheld' : 'not-found';
}

export const dossier = new DossierLoader();
