<script lang="ts" module>
	// module-level: every mount passes the SAME loader, so a remount renders the loaded panel in the same frame (LazyMount)
	const load = () => import('$lib/corridor/ExplorerTab.svelte');
</script>

<script lang="ts">
	/** Lazy Explorer tab (plan R9): the S2X Explorer + the corridor's Active events load on first open. */
	import LazyTab from './LazyTab.svelte';
</script>

<LazyTab {load} />
