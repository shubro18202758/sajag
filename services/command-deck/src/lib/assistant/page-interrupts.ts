/**
 * The canvas-less operator pages' navbar interrupts (SPEC §5.3, §7.3; plan
 * X21): /chat and /comms keep the same live strip and inbox the canvas
 * pages carry, and their inbox button routes to the workspace's inbox deep
 * link — these pages have no dock of their own to open. The count comes
 * from the same decision units the canvas pages read, so an interrupt
 * never depends on which page the operator is reading.
 */
import { goto } from '$app/navigation';
import { commandBar } from '$lib/shell/command-bar.svelte';
import { liveStripFeed } from '$lib/decisions/live';
import { WORKSPACE_URL } from '$lib/shell/root-flip';
import type { DecisionUnitSummary } from '$lib/workspace/types';

/** Wire the live strip and the inbox hand-off for a canvas-less page. */
export function wireInterrupts(route: string): void {
	// the pursuit segment opens the vehicle on the workspace: this page has no map (F-06)
	commandBar.live = liveStripFeed({ route, navigate: (url) => void goto(url) });
	commandBar.onInbox = () => void goto(`${WORKSPACE_URL}#inbox`);
}

/** The navbar's inbox count and intent, from the page's decision units. */
export function inboxFromUnits(units: readonly DecisionUnitSummary[]): void {
	commandBar.inboxCount = units.length;
	commandBar.inboxIntent = units.length > 0 ? 'warning' : 'none';
}
