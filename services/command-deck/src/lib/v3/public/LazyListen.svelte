<script lang="ts">
	/** The Listen button, loaded after the page's first paint (the speech client and its strings stay out of the first load). */
	import { onMount, type Component } from 'svelte';

	let { text, lang, compact = false }: { text: string; lang: string; compact?: boolean } = $props();
	let Btn = $state<Component<{ text: string; lang: string; compact?: boolean }> | null>(null);

	onMount(() => {
		let gone = false;
		void import('./ListenButton.svelte').then((m) => {
			if (!gone) Btn = m.default as unknown as Component<{ text: string; lang: string; compact?: boolean }>;
		});
		return () => {
			gone = true;
		};
	});
</script>

{#if Btn}<Btn {text} {lang} {compact} />{/if}
