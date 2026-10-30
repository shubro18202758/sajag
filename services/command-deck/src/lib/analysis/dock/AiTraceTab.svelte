<script lang="ts">
	/**
	 * The workspace frame's "ai" bottom tab (registered by analysis/register.ts):
	 * the analysis dock in its tab variant — the frame draws the tabs and owns
	 * the size. Replay is blocked on `/` while a movement or pursuit is live.
	 */
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { frameContext } from '$lib/workspace/components/frame/context';
	import { liveWorld } from '$lib/workspace/world.svelte';
	import AnalysisDock from './AnalysisDock.svelte';
	// the table this tab shows rides in with the tab's own chunk (one round trip, not two):
	// the dock imports it on demand (FIX-E-PERF2), and this static import warms that import
	import '../audit/AuditTable.svelte';
	import { replayBlockReason } from './replay-guard';

	const frame = frameContext();
	const blocked = $derived(replayBlockReason(frame ? frame.route() : null, liveWorld.graph(), commandBar.lang));
</script>

<AnalysisDock variant="tab" tab="ai" replayBlocked={blocked} lang={commandBar.lang} />
