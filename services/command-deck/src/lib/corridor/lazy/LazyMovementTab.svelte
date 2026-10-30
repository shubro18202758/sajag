<script lang="ts" module>
	// module-level: every mount passes the SAME loader, so a remount renders the loaded panel in the same frame (LazyMount)
	const load = () => import('$lib/corridor/ConvoyCard.svelte');
</script>

<script lang="ts">
	/** Lazy Movement tab (plan R9): the ConvoyCard loads on first open. */
	import LazyTab from './LazyTab.svelte';
</script>

<LazyTab {load} />
