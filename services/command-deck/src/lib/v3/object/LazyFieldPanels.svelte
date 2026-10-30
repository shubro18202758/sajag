<script lang="ts" module>
	// module-level: every mount passes the SAME loader, so a remount renders the loaded panels in the same frame (LazyMount)
	const load = () => import('./FieldPanels.svelte');
</script>

<script lang="ts">
	/** Lazy on-premises AI panels (camera road state; a road's forecast and waterlogging): loaded on the page's first render of them. */
	import LazyMount from '$lib/workspace/components/lazy/LazyMount.svelte';
	let { ...rest } = $props();
</script>

<LazyMount {load} spinner={false} {...rest} />
