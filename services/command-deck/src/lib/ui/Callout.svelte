<script lang="ts">
	/**
	 * Callout — a non-rule notice (the sample-answer notice, the Exercise data
	 * popover). Neutral by default; an intent tints the veil and the title.
	 * Rules use Note, never a Callout.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import { INTENT_ICON, type IconName } from '$lib/design/icons';
	import Icon from './Icon.svelte';
	import type { Intent } from './types';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		intent?: Intent;
		/** A glyph; defaults to the intent's glyph when an intent is set; `null` hides it. */
		icon?: IconName | null;
		title?: string | null;
		compact?: boolean;
		children?: Snippet;
	}

	let { intent = 'none', icon = undefined, title = null, compact = false, children, class: cls = '', ...rest }: Props =
		$props();

	const glyph = $derived(icon === null ? null : (icon ?? (intent !== 'none' ? INTENT_ICON[intent] : null)));
</script>

<div
	data-ui="callout"
	data-intent={intent}
	role={intent === 'danger' || intent === 'warning' ? 'alert' : 'note'}
	class={['callout', `i-${intent}`, compact && 'compact', glyph && 'has-icon', cls]}
	{...rest}
>
	{#if glyph}<Icon name={glyph} size={16} />{/if}
	<div class="content">
		{#if title}<div class="title">{title}</div>{/if}
		{#if children}<div class="text">{@render children()}</div>{/if}
	</div>
</div>

<style>
	.callout {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		padding: 8px 12px;
		border-radius: var(--v-radius-chip);
		background: var(--v-hover);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.callout :global([data-ui='icon']) {
		margin-top: 1px;
		color: var(--v-ink-2);
	}

	.content {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.title {
		font-size: var(--v-text-base);
		font-weight: 600;
		line-height: calc(var(--v-text-base) + 4px);
	}

	.has-icon .title {
		margin-top: -1px;
	}

	.text :global(p) {
		margin: 0;
	}

	.compact {
		padding: 4px 8px;
	}

	.i-primary {
		background: var(--v-primary-veil);
	}

	.i-success {
		background: var(--v-success-veil);
	}

	.i-warning {
		background: var(--v-warning-veil);
	}

	.i-danger {
		background: var(--v-danger-veil);
	}

	.i-primary .title,
	.i-primary :global([data-ui='icon']) {
		color: var(--v-primary-text);
	}

	.i-success .title,
	.i-success :global([data-ui='icon']) {
		color: var(--v-success-text);
	}

	.i-warning .title,
	.i-warning :global([data-ui='icon']) {
		color: var(--v-warning-text);
	}

	.i-danger .title,
	.i-danger :global([data-ui='icon']) {
		color: var(--v-danger-text);
	}
</style>
