<script lang="ts" module>
	/** Module-level, so every mount passes LazyMount the same loader: a dock tab switch back to the Assistant renders the loaded panel in the same frame. */
	const load = () => import('./AssistantPanel.svelte');
</script>

<script lang="ts">
	/** Lazy Assistant tab (plan R9): the AssistantPanel loads on its tab's first open. */
	import LazyMount from '$lib/workspace/components/lazy/LazyMount.svelte';
	let { ...rest } = $props();
</script>

<LazyMount {load} {...rest} />
