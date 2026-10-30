<script lang="ts">
	/**
	 * Note — THE rule note (SPEC §5.1, §9): one neutral 12 px line with the
	 * rule's glyph in ink-2, an optional title in 600. It replaces the old
	 * orange "Evidence only" callout: rules are quiet and never orange. At
	 * most one per surface.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import type { IconName } from '$lib/design/icons';
	import Icon from './Icon.svelte';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		icon: IconName;
		title?: string | null;
		text?: string | null;
		children?: Snippet;
	}

	let { icon, title = null, text = null, children, class: cls = '', ...rest }: Props = $props();
</script>

<div data-ui="note" class={['note', cls]} {...rest}>
	<Icon name={icon} size={16} />
	<span class="body">
		{#if title}<b>{title}</b>{' '}{/if}{#if children}{@render children()}{:else}{text}{/if}
	</span>
</div>

<style>
	.note {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		min-width: 0;
		color: var(--v-ink-2);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.note :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.body {
		min-width: 0;
	}

	b {
		color: var(--v-ink-1);
		font-weight: 600;
	}
</style>
