<script lang="ts">
	/**
	 * Skeleton — the placeholder of content that is loading: static blocks
	 * (no shimmer: no ambient motion), `lines` text lines of decreasing
	 * width, or one block of `width` × `height`. role="status", aria-busy.
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import { uiLang, ut } from './lang';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		lines?: number;
		width?: string;
		height?: string;
		lang?: string;
	}

	let { lines = 0, width = '100%', height = '16px', lang, class: cls = '', ...rest }: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	const WIDTHS = ['100%', '92%', '76%', '84%', '64%'];
</script>

<div data-ui="skeleton" role="status" aria-busy="true" aria-label={ut(L, 'ui_loading')} class={['sk', cls]} {...rest}>
	{#if lines > 0}
		{#each Array.from({ length: lines }, (_, i) => i) as i (i)}
			<span class="bar" style:width={i === lines - 1 && lines > 1 ? '56%' : WIDTHS[i % WIDTHS.length]}></span>
		{/each}
	{:else}
		<span class="bar" style:width style:height></span>
	{/if}
</div>

<style>
	.sk {
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-width: 0;
	}

	.bar {
		display: block;
		height: 12px;
		border-radius: var(--v-radius-chip);
		background: var(--v-hover);
	}
</style>
