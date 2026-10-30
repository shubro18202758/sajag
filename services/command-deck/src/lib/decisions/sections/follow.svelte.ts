/**
 * The pursuit plan follows the vehicle (SPEC §5.4, review B8): while a
 * vehicle is the selection, the ops store follows its open pursuit
 * (ops.followVehicle), so the interception plan loads and polls (6 s, the
 * same token guard) and `ops.interception` — the canvas overlay's source —
 * is that pursuit's plan whether the vehicle or the pursuit event is
 * selected. Selecting anything else stops following, and so does an event
 * pick on the board (ops.selectEvent: the most recent intent wins). Picking
 * the same vehicle again (a new `selectedAt`) follows it again. A pursuit
 * EVENT pick already reaches the store through the selection's board sync.
 *
 * Started once by decisions/register.ts in the browser; idempotent.
 */
import { untrack } from 'svelte';
import { ops } from '$lib/ops/store.svelte';
import { selection } from '$lib/gods-eye/entities/selection.svelte';
import { parseUrn } from '$lib/gods-eye/city-api';

let stop: (() => void) | null = null;

/** The vehicle id of a selected URN, or null. */
export function followedVehicleOf(urn: string | null | undefined): string | null {
	const p = urn ? parseUrn(urn) : null;
	return p?.kind === 'vehicle' ? p.id : null;
}

export function startFollow(): void {
	if (stop || typeof window === 'undefined') return;
	stop = $effect.root(() => {
		$effect(() => {
			const id = followedVehicleOf(selection.current);
			void selection.selectedAt; // re-picking the same vehicle is a new intent
			untrack(() => ops.followVehicle(id));
		});
	});
}

/** Stop following (tests, the harness on leave). */
export function stopFollow(): void {
	stop?.();
	stop = null;
}
