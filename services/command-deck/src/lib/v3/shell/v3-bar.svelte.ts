/**
 * The V3 top bar's page-owned fields (V3-SPEC §3.1): the screen title and its one-line status. Everything
 * else the V3 shell shows comes through the v2 shell↔page contract it reuses unchanged
 * ($lib/shell/command-bar.svelte: lang, onLangChange, onSearch, officer, exercise, inboxCount, live), so a
 * page talks to the V3 shell exactly the way it talked to the v2 CommandShell (retired in P6B). The shell never imports a store.
 *
 * V3Shell clears these on every route change, before the next page mounts (as the v2 shell cleared
 * commandBar).
 */
export interface V3BarState {
	/** The screen title ("Good evening", "Decide"); null shows the product name. */
	title: string | null;
	/** One line under it ("Mumbai · Friday 30 Oct · 19:42 IST"). */
	sub: string | null;
	/** The rail item this page belongs to (home | map | decide | assistant | advisories | analyst). */
	active: string | null;
	/** Decisions as the page counts them for the alert list: key → masked title, href, emulated flag. */
	decisions: { key: string; title: string; href: string; emulated: boolean }[] | null;
}

export const v3Bar = $state<V3BarState>({ title: null, sub: null, active: null, decisions: null });

export function resetV3Bar(): void {
	v3Bar.title = null;
	v3Bar.sub = null;
	v3Bar.active = null;
	v3Bar.decisions = null;
}
