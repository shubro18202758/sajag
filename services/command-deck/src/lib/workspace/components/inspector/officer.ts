/**
 * The navbar officer (plan X12): UI-S1B adds `officer` to the commandBar in
 * the same wave, so this WP reads it ONLY through this one sanctioned typed
 * read. It type-checks with and without S1B's field, and commandBar is a
 * $state proxy, so the read stays reactive.
 *
 * The inspector keeps its legacy `dossier-officer` prompt only while this is
 * null (no navbar officer on the page, plan R10); it writes through today's
 * path, ops.setDutyOfficer.
 */
import { commandBar } from '$lib/shell/command-bar.svelte';

export const navbarOfficer = () => (commandBar as unknown as { officer?: { value: string } | null }).officer ?? null;

/** True when the inspector shows its legacy officer prompt (no navbar officer on this page). */
export function showLegacyOfficer(): boolean {
	return navbarOfficer() === null;
}
