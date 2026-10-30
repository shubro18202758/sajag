<script lang="ts" generics="V extends string">
	/**
	 * Tabs — a row of tabs with a 3 px underline in --v-primary-text under the
	 * selected one (Blueprint: an inset shadow, not a fill). 20 px apart (12 px
	 * below 1440 px wide). Each tab may carry an icon and a count; a count can
	 * take the warning intent (a decision waits). Arrow keys move the
	 * selection; Home and End jump.
	 *
	 * `value` is bindable; onchange fires on a user choice. Tabs render the
	 * tab list only — the caller renders the panel for `value`
	 * (aria-controls via `panelId(value)` when it needs the link).
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import type { IconName } from '$lib/design/icons';
	import Icon from './Icon.svelte';

	interface TabItem {
		id: V;
		label: string;
		count?: number | string | null;
		countIntent?: 'none' | 'warning' | 'danger';
		icon?: IconName;
		disabled?: boolean;
		/** Extra attributes for this tab's button (data-* hooks for tests). */
		attrs?: Record<string, string>;
	}

	interface Props extends Omit<HTMLAttributes<HTMLDivElement>, 'onchange'> {
		items: readonly TabItem[];
		value?: V;
		onchange?: (id: V) => void;
		/** Tab height in px (30 by default; dock headers use 39). */
		height?: number;
		fill?: boolean;
		label?: string;
		/** id prefix for aria-controls / the panel's id. */
		idPrefix?: string;
	}

	let {
		items,
		value = $bindable(),
		onchange,
		height = 30,
		fill = false,
		label,
		idPrefix,
		class: cls = '',
		...rest
	}: Props = $props();

	const uid = $props.id();
	const prefix = $derived(idPrefix ?? uid);
	let list: HTMLDivElement | undefined = $state();

	function choose(id: V) {
		if (id === value) return;
		value = id;
		onchange?.(id);
	}

	function onKey(e: KeyboardEvent) {
		const enabled = items.filter((t) => !t.disabled);
		const i = enabled.findIndex((t) => t.id === value);
		let next = -1;
		if (e.key === 'ArrowRight') next = (i + 1) % enabled.length;
		else if (e.key === 'ArrowLeft') next = (i - 1 + enabled.length) % enabled.length;
		else if (e.key === 'Home') next = 0;
		else if (e.key === 'End') next = enabled.length - 1;
		if (next < 0 || !enabled.length) return;
		e.preventDefault();
		choose(enabled[next].id);
		queueMicrotask(() => list?.querySelector<HTMLButtonElement>('[aria-selected="true"]')?.focus());
	}
</script>

<div
	data-ui="tabs"
	role="tablist"
	aria-label={label}
	class={['tabs', fill && 'fill', cls]}
	style:--tab-h="{height}px"
	bind:this={list}
	onkeydown={onKey}
	{...rest}
>
	{#each items as tab (tab.id)}
		<button
			type="button"
			role="tab"
			id="{prefix}-tab-{tab.id}"
			aria-selected={tab.id === value}
			aria-controls="{prefix}-panel-{tab.id}"
			tabindex={tab.id === value || (value === undefined && tab === items[0]) ? 0 : -1}
			disabled={tab.disabled || undefined}
			class={['tab', tab.id === value && 'on']}
			onclick={() => choose(tab.id)}
			{...tab.attrs}
		>
			{#if tab.icon}<Icon name={tab.icon} size={16} />{/if}
			<span class="lbl">{tab.label}</span>
			{#if tab.count != null && tab.count !== ''}
				<span class={['count', tab.countIntent && tab.countIntent !== 'none' && `c-${tab.countIntent}`]}>{tab.count}</span>
			{/if}
		</button>
	{/each}
</div>

<style>
	.tabs {
		display: flex;
		align-items: stretch;
		gap: 20px;
		min-width: 0;
	}

	@media (max-width: 1439px) {
		.tabs {
			gap: 12px;
		}
	}

	.tab {
		position: relative;
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		gap: 6px;
		height: var(--tab-h, 30px);
		margin: 0;
		padding: 0;
		border: 0;
		border-radius: 0;
		background: transparent;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
		white-space: nowrap;
		cursor: pointer;
	}

	.tab :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.tab:hover {
		color: var(--v-primary-text);
	}

	.tab.on {
		color: var(--v-primary-text);
		box-shadow: inset 0 -3px 0 var(--v-primary-text);
	}

	.tab.on :global([data-ui='icon']) {
		color: var(--v-primary-text);
	}

	.tab:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	.tab:disabled {
		color: var(--v-ink-disabled);
		cursor: not-allowed;
	}

	.count {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 20px;
		height: 20px;
		padding: 0 6px;
		border-radius: var(--v-radius-pill);
		background: var(--v-neutral-veil);
		color: var(--v-ink-1);
		font-size: var(--v-text-xs);
		line-height: 1;
		font-variant-numeric: tabular-nums;
	}

	/* the selected tab's count takes the tab's ink; its veil never changes
	 * (the underline is the tabs' only active state) */
	.tab.on .count:not(.c-warning):not(.c-danger) {
		color: var(--v-primary-text);
	}

	.count.c-warning {
		background: var(--v-warning-veil);
		color: var(--v-warning-text);
	}

	.count.c-danger {
		background: var(--v-danger-veil);
		color: var(--v-danger-text);
	}

	.fill .tab {
		flex: 1 1 0;
		justify-content: center;
	}
</style>
