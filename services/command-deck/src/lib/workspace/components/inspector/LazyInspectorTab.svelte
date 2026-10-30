<script lang="ts">
	/** Lazy Inspector tab (plan R9): the tab's module loads on its first open (a stable, module-level loader). */
	import LazyMount from '$lib/workspace/components/lazy/LazyMount.svelte';
	import { loadInspectorTab } from './load';
	let { ...rest } = $props();
</script>

<LazyMount load={loadInspectorTab} {...rest} />
