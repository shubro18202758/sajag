/**
 * The decision-support client state (plan X22) — one rune store for the
 * fetched C-U objects, the officer's COA selection, the refusals the card
 * prints verbatim, and the promote dialog's request. Plain modules
 * (decisions/writers.ts, the section) read and write these fields; only this
 * file holds `$state`.
 *
 * `objects` is filled when a unit's card opens (never polled, plan R11/X13)
 * and seeded by the /design harness with its synthetic fixture. `selected`
 * maps a dss id to the COA the officer's radio chose; the writers read it,
 * the shell's What-changes table follows it.
 *
 * `loadDecisionSupport` GETs the object through the deck's ops client
 * (`getDecisionSupport` → `request()`: the 404 not-deployed back-off, the
 * error-body snippet and the shared in-flight GET — fix round 2 put the raw
 * duplicate fetch away). The public-safety floor needs no merge: the client's
 * parser carries the recommendation field natively.
 */
import { getDecisionSupport, type DecisionSupport } from '$lib/ops/client';

export const dssState = $state({
	/** dss_id → the parsed C-U object (fetched on open, or harness-seeded). */
	objects: {} as Record<string, DecisionSupport>,
	/** dss_id → a GET is in flight. */
	loading: {} as Record<string, boolean>,
	/** dss_id → why the oracle did not answer (shown honestly, retry offered). */
	failed: {} as Record<string, string>,
	/** dss_id → the COA the officer selected in the card's radio list. */
	selected: {} as Record<string, string>,
	/** dss_id → the last refusal (code + the server's own sentence, verbatim). */
	refusals: {} as Record<string, { refusal: string; detail: string | null }>,
	/** The osint urn whose Promote dialog is open (the section hosts it). */
	promoteUrn: null as string | null,
});

/**
 * GET /api/v1/decision-support/{id} — the card's ONE fetch (the body and the
 * card-header banner share it through `ensureDssObject`), through the deck's
 * ops client so the 404 back-off and the honest error bodies apply.
 */
export function loadDecisionSupport(dssId: string): Promise<DecisionSupport> {
	return getDecisionSupport(dssId);
}

const requested = new Set<string>();

/** Fetch the object once per id — the body's observer and the header banner share it. */
export async function ensureDssObject(id: string): Promise<void> {
	if (requested.has(id) || dssState.objects[id] || dssState.loading[id]) return;
	requested.add(id);
	dssState.loading[id] = true;
	delete dssState.failed[id];
	try {
		dssState.objects[id] = await loadDecisionSupport(id);
	} catch (err) {
		dssState.failed[id] = err instanceof Error ? err.message : String(err);
		// a failed GET does not stick: the id leaves the once-per-id guard, so a
		// remount retries as it did before the guard (fix round 2)
		requested.delete(id);
	} finally {
		delete dssState.loading[id];
	}
}

/** Forget the once-per-id guard (the card's Retry asks the oracle again). */
export function forgetDssObject(id: string): void {
	requested.delete(id);
}

/** Seed a fetched (or fixture) object — the /design harness and tests. */
export function seedDssObject(obj: DecisionSupport): void {
	dssState.objects[obj.dssId] = obj;
}

/** The officer's chosen COA for `dssId`, or null. */
export function selectionOf(dssId: string): string | null {
	return dssState.selected[dssId] ?? null;
}

export function selectCoa(dssId: string, coaId: string): void {
	dssState.selected[dssId] = coaId;
}

export function recordDssRefusal(dssId: string, refusal: string, detail: string | null): void {
	dssState.refusals[dssId] = { refusal, detail };
}

/** Drop everything (tests and the harness unmount). */
export function resetDssState(): void {
	for (const k of Object.keys(dssState.objects)) delete dssState.objects[k];
	for (const k of Object.keys(dssState.loading)) delete dssState.loading[k];
	for (const k of Object.keys(dssState.failed)) delete dssState.failed[k];
	for (const k of Object.keys(dssState.selected)) delete dssState.selected[k];
	for (const k of Object.keys(dssState.refusals)) delete dssState.refusals[k];
	dssState.promoteUrn = null;
	requested.clear();
}
