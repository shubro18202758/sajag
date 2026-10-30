<script lang="ts">
	/**
	 * Section — a titled block of a dock or a wall column (SPEC §3.5: a header
	 * holds a title, a count and at most one time or state word, nothing
	 * else). Docked by default: a 40 px header and a 1 px divider below the
	 * section, no elevation. `card` gives Blueprint's raised section.
	 *
	 * - collapsible: the header toggles the body (aria-expanded); `open` is
	 *   bindable and mirrored in data-open on the root. The disclosure
	 *   pattern: the heading holds the toggle button (<hN><button>), so the
	 *   heading stays a heading and the button carries the title.
	 * - icon, sub (one muted word or count), right (a snippet for the
	 *   header's right edge: a tag, a small button, a time).
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import type { IconName } from '$lib/design/icons';
	import Icon from './Icon.svelte';

	interface Props extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
		title: string;
		icon?: IconName;
		sub?: string | number | null;
		right?: Snippet;
		collapsible?: boolean;
		open?: boolean;
		variant?: 'docked' | 'card';
		compact?: boolean;
		/** Heading level of the title (2–6). */
		level?: 2 | 3 | 4 | 5 | 6;
		onopenchange?: (open: boolean) => void;
		children?: Snippet;
	}

	let {
		title,
		icon,
		sub = null,
		right,
		collapsible = false,
		open = $bindable(true),
		variant = 'docked',
		compact = false,
		level = 3,
		onopenchange,
		children,
		class: cls = '',
		...rest
	}: Props = $props();

	const uid = $props.id();

	function toggle() {
		open = !open;
		onopenchange?.(open);
	}
</script>

{#snippet subLine()}
	{#if sub != null && sub !== ''}<span class="sub">{sub}</span>{/if}
{/snippet}

<section
	data-ui="section"
	data-open={collapsible ? (open ? 'true' : 'false') : undefined}
	class={['section', variant, compact && 'compact', cls]}
	aria-labelledby="{uid}-title"
	{...rest}
>
	<header class="head" id="{uid}-head">
		{#if collapsible}
			<svelte:element this={`h${level}`} class="hx">
				<button
					type="button"
					class="toggle"
					aria-expanded={open}
					aria-controls="{uid}-body"
					onclick={toggle}
				>
					{#if icon}<Icon name={icon} size={16} />{/if}
					<span class="title" id="{uid}-title">{title}</span>
					{@render subLine()}
					<span class="chev"><Icon name={open ? 'chevron-up' : 'chevron-down'} size={16} /></span>
				</button>
			</svelte:element>
		{:else}
			<div class="static">
				{#if icon}<Icon name={icon} size={16} />{/if}
				<svelte:element this={`h${level}`} class="title" id="{uid}-title">{title}</svelte:element>
				{@render subLine()}
			</div>
		{/if}
		{#if right}<div class="right">{@render right()}</div>{/if}
	</header>
	{#if !collapsible || open}
		<div class="body" id="{uid}-body">{@render children?.()}</div>
	{/if}
</section>

<style>
	.section {
		display: flex;
		flex-direction: column;
		min-width: 0;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
	}

	.docked {
		border-bottom: 1px solid var(--v-line-2);
	}

	.card {
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-1);
		box-shadow: var(--v-elev-0);
	}

	.head {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 40px;
		padding: 0 8px 0 16px;
	}

	.compact .head {
		min-height: 32px;
		padding-left: 12px;
	}

	.static,
	.toggle,
	.hx {
		display: flex;
		flex: 1 1 auto;
		align-items: center;
		gap: 8px;
		min-width: 0;
		align-self: stretch;
	}

	/* the heading around the toggle: no type of its own (the title span carries it) */
	.hx {
		margin: 0;
		font-size: inherit;
		font-weight: inherit;
		line-height: inherit;
	}

	.toggle {
		margin: 0;
		padding: 0;
		border: 0;
		background: transparent;
		color: inherit;
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.toggle:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	.head :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.title {
		margin: 0;
		overflow: hidden;
		font-size: var(--v-text-base);
		font-weight: 600;
		line-height: calc(var(--v-text-base) + 2px);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.sub {
		flex: 0 0 auto;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.chev {
		display: inline-flex;
		margin-left: auto;
	}

	.right {
		display: flex;
		flex: 0 0 auto;
		align-items: center;
		gap: 4px;
		margin-left: auto;
	}

	.body {
		min-width: 0;
	}

	.card .body {
		border-top: 1px solid var(--v-line-1);
	}
</style>
