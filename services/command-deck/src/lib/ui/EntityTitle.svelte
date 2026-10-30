<script lang="ts">
	/**
	 * EntityTitle — an object's header (the inspector, a proposal): a 32 px
	 * glyph tile, the title in 16/20 600 (identifiers through the formatter
	 * via the `title` snippet), a 12 px subtitle and a row of tags. An
	 * `alert` object (watchlisted or stolen) rings its tile in the alert red;
	 * an `ai` proposer tints the glyph indigo.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import type { IconName } from '$lib/design/icons';
	import Icon from './Icon.svelte';

	interface Props extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
		title?: string | Snippet;
		subtitle?: string | Snippet | null;
		icon?: IconName;
		alert?: boolean;
		ai?: boolean;
		tags?: Snippet;
		/** Heading level of the title. */
		level?: 1 | 2 | 3 | 4 | 5 | 6;
		ellipsize?: boolean;
	}

	let {
		title = '',
		subtitle = null,
		icon,
		alert = false,
		ai = false,
		tags,
		level = 2,
		ellipsize = false,
		class: cls = '',
		...rest
	}: Props = $props();
</script>

<div data-ui="entity-title" class={['et', ellipsize && 'ellipsize', cls]} {...rest}>
	{#if icon}
		<span class={['tile', alert && 'alert', ai && 'ai']}><Icon name={icon} size={20} /></span>
	{/if}
	<div class="text">
		<svelte:element this={`h${level}`} class="title">
			{#if typeof title === 'function'}{@render title()}{:else}{title}{/if}
		</svelte:element>
		{#if subtitle}
			<div class="sub">{#if typeof subtitle === 'function'}{@render subtitle()}{:else}{subtitle}{/if}</div>
		{/if}
		{#if tags}<div class="tags">{@render tags()}</div>{/if}
	</div>
</div>

<style>
	.et {
		display: flex;
		align-items: flex-start;
		gap: 12px;
		min-width: 0;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.tile {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		justify-content: center;
		width: 32px;
		height: 32px;
		border-radius: var(--v-radius-chip);
		background: var(--v-surface-3);
		color: var(--v-ink-1);
	}

	.tile.alert {
		box-shadow: inset 0 0 0 2px var(--v-map-alert);
	}

	.tile.ai {
		color: var(--v-ai-text);
	}

	.text {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.title {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
		margin: 0;
		font-size: var(--v-text-md);
		font-weight: 600;
		line-height: calc(var(--v-text-md) + 4px);
	}

	.ellipsize .title {
		display: block;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.sub {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 4px;
		margin-top: 4px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		margin-top: 8px;
	}
</style>
