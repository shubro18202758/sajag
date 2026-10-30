<script lang="ts" module>
	// module-level: every mount passes the SAME loader, so a remount renders the loaded panel in the same frame (LazyMount)
	const load = () => import('./OsintReportSection.svelte');
</script>

<script lang="ts">
	/** Lazy OSINT report section (plan R9): the report and its model load on the inspector's first render of it. */
	import LazyMount from '$lib/workspace/components/lazy/LazyMount.svelte';
	let { ...rest } = $props();
</script>

<LazyMount {load} {...rest} />
