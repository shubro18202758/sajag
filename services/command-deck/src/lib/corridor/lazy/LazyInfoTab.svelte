<script lang="ts" module>
	// module-level: every mount passes the SAME loader, so a remount renders the loaded panel in the same frame (LazyMount)
	const load = () => import('$lib/gods-eye/hud/CityVitals.svelte');
</script>

<script lang="ts">
	/** Lazy Info tab (plan R9): the full City vitals load on first open. */
	import LazyTab from './LazyTab.svelte';
</script>

<LazyTab {load} />
