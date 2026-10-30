<script lang="ts" module>
	// module-level: every mount passes the SAME loader, so a remount renders the loaded panel in the same frame (LazyMount)
	const load = () => import('./AuditTab.svelte');
</script>

<script lang="ts">
	/** Lazy Audit tab (plan R9): the analysis dock loads on the tab's first mount. */
	import LazyMount from '$lib/workspace/components/lazy/LazyMount.svelte';
	let { ...rest } = $props();
</script>

<LazyMount {load} {...rest} />
