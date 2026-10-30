<script lang="ts">
	/**
	 * A label with exactly the matched span marked (SPEC §5.3 Omnibar). With
	 * `mono` the label is an identifier: each run goes through the formatter's
	 * Id (the mono face lives only in ui/format), and adjacent runs read as one
	 * identifier.
	 */
	import { Id } from '$lib/ui';
	import { highlight } from '../../search';

	let { text, words, mono = false }: { text: string; words: readonly string[]; mono?: boolean } = $props();

	const spans = $derived(highlight(text, words));
</script>

{#each spans as s, i (i)}{#if s.mark}<mark class="hl">{#if mono}<Id value={s.text} />{:else}{s.text}{/if}</mark>{:else if mono}<Id value={s.text} />{:else}{s.text}{/if}{/each}

<style>
	.hl {
		background: none;
		color: var(--v-ink-1);
		font-weight: 600;
		text-decoration: underline;
		text-decoration-color: var(--v-line-select);
		text-underline-offset: 3px;
	}
</style>
