<script lang="ts" module>
	// module-level: every mount passes the SAME loader, so a remount renders the loaded panel in the same frame (LazyMount)
	const load = () => import('$lib/workspace/components/histogram/Histogram.svelte');
</script>

<script lang="ts">
	/** Lazy Histogram tab (plan R9): the S2X Histogram loads on first open. */
	import LazyTab from './LazyTab.svelte';
</script>

<LazyTab {load} />
