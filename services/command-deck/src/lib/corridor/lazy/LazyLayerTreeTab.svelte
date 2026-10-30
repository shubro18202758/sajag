<script lang="ts" module>
	// module-level: every mount passes the SAME loader, so a remount renders the loaded panel in the same frame (LazyMount)
	const load = () => import('$lib/gods-eye/hud/map/LayerTree.svelte');
</script>

<script lang="ts">
	/** Lazy Layers tab (plan R9): S3's LayerTree loads on first open. */
	import LazyTab from './LazyTab.svelte';
</script>

<LazyTab {load} />
