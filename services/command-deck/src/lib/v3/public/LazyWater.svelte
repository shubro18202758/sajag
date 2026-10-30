<script lang="ts">
	/**
	 * The waterlogging card, loaded after the page's first paint (its strings, the hydro reads and the Listen button stay
	 * out of the public route's first load — the route-JS budget). Holds its place with a quiet block of the same rhythm.
	 */
	import { onMount, type Component } from 'svelte';

	let { lang }: { lang: string } = $props();
	let Card = $state<Component<{ lang: string }> | null>(null);

	onMount(() => {
		let gone = false;
		void import('./WaterOnYourRoad.svelte').then((m) => {
			if (!gone) Card = m.default as unknown as Component<{ lang: string }>;
		});
		return () => {
			gone = true;
		};
	});
</script>

{#if Card}<Card {lang} />{:else}<div class="hold" aria-hidden="true"></div>{/if}

<style>
	.hold {
		min-height: 220px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-xl);
		background: var(--v3-s1);
	}
</style>
