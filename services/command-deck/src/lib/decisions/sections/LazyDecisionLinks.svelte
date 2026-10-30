<script lang="ts" module>
	// module-level: every mount passes the SAME loader, so a remount renders the loaded panel in the same frame (LazyMount)
	const load = () => import('./DecisionLinks.svelte');
</script>

<script lang="ts">
	/** Lazy decision-links section (plan R9): the link cards load on the inspector's first render of them. */
	import LazyMount from '$lib/workspace/components/lazy/LazyMount.svelte';
	let { ...rest } = $props();
</script>

<LazyMount {load} {...rest} />
