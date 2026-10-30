<script lang="ts">
	/**
	 * Reason — the inline reason for a disabled action: an info-sign glyph and
	 * one 12 px line in ink-2 ("Name a duty officer to decide."). Pairs with
	 * Button's disabledReason, which also shows the same text as a tooltip.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import Icon from './Icon.svelte';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		text?: string;
		children?: Snippet;
	}

	let { text, children, class: cls = '', ...rest }: Props = $props();
</script>

<div data-ui="reason" class={['reason', cls]} {...rest}>
	<Icon name="info-sign" size={12} />
	<span>{#if children}{@render children()}{:else}{text}{/if}</span>
</div>

<style>
	.reason {
		display: flex;
		align-items: center;
		gap: 4px;
		min-width: 0;
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
		color: var(--v-ink-2);
	}

	.reason :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}
</style>
