<script lang="ts">
	/**
	 * NonIdealState — an empty, loading-failed or not-found pane: a muted
	 * glyph, a title, one line that says what to do, and an optional action.
	 * Empty states say what to do (SPEC §11), never just "No data".
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import type { IconName } from '$lib/design/icons';
	import Icon from './Icon.svelte';

	interface Props extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
		icon?: IconName;
		title?: string | null;
		description?: string | Snippet | null;
		action?: Snippet;
		layout?: 'vertical' | 'horizontal';
		/** Glyph size: 48 (pane), 32 (section), 20 (row). */
		iconSize?: 20 | 32 | 48;
	}

	let {
		icon,
		title = null,
		description = null,
		action,
		layout = 'vertical',
		iconSize = 48,
		class: cls = '',
		...rest
	}: Props = $props();
</script>

<div data-ui="non-ideal-state" class={['nis', layout, `s${iconSize}`, cls]} {...rest}>
	{#if icon}<span class="glyph"><Icon name={icon} size={iconSize} /></span>{/if}
	<div class="text">
		{#if title}<div class="title">{title}</div>{/if}
		{#if description}
			<div class="desc">{#if typeof description === 'function'}{@render description()}{:else}{description}{/if}</div>
		{/if}
		{#if action}<div class="action">{@render action()}</div>{/if}
	</div>
</div>

<style>
	.nis {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 12px;
		padding: 24px;
		color: var(--v-ink-2);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
		text-align: center;
	}

	.horizontal {
		flex-direction: row;
		gap: 16px;
		text-align: left;
	}

	.s20 {
		gap: 8px;
		padding: 12px;
	}

	.glyph {
		display: inline-flex;
		color: var(--v-ink-4);
	}

	.text {
		display: flex;
		flex-direction: column;
		align-items: inherit;
		gap: 4px;
		max-width: 400px;
	}

	.vertical .text {
		align-items: center;
	}

	.title {
		color: var(--v-ink-2);
		font-size: var(--v-text-md);
		font-weight: 600;
		line-height: calc(var(--v-text-md) + 4px);
	}

	.s20 .title {
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
	}

	.desc {
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.action {
		margin-top: 8px;
	}
</style>
