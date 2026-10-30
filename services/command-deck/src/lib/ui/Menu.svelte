<script lang="ts">
	/**
	 * Menu — a list of commands (in a Popover, or inline). Items are 30 px:
	 * a glyph, a label, a right-aligned hint (a shortcut or a count). A
	 * `danger` item uses the danger ink; a disabled item says why through a
	 * tooltip; a `selected` item is a current choice (.is-selected,
	 * aria-checked). Headers and dividers group items.
	 *
	 * Keyboard: one tab stop (roving tabindex: the focused item, else the
	 * current choice, else the first enabled item), so an inline menu is
	 * reachable with Tab; Up/Down move between enabled items, Home/End jump,
	 * Enter or Space activates. onselect fires for every activated item (a
	 * Popover's content snippet passes its `close` here; the Popover then
	 * hands focus back to its target).
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import Icon from './Icon.svelte';
	import Tooltip from './Tooltip.svelte';
	import type { MenuItemSpec } from './types';

	interface Props extends Omit<HTMLAttributes<HTMLUListElement>, 'onselect'> {
		items: readonly MenuItemSpec[];
		onselect?: (item: MenuItemSpec) => void;
		label?: string;
		/** Focus the tab stop on mount (menus opened from a button): the current choice, else the first enabled item. */
		autofocus?: boolean;
	}

	let { items, onselect, label, autofocus = false, class: cls = '', ...rest }: Props = $props();

	let root: HTMLUListElement | undefined = $state();
	let focusedId = $state<string | null>(null);

	const isItem = (i: MenuItemSpec) => i.kind !== 'divider' && i.kind !== 'header';
	/** The one item with tabindex 0. */
	const tabStop = $derived.by(() => {
		const enabled = items.filter((i) => isItem(i) && !i.disabled);
		if (focusedId && enabled.some((i) => i.id === focusedId)) return focusedId;
		return (enabled.find((i) => i.selected) ?? enabled[0])?.id ?? null;
	});

	function enabledEls(): HTMLElement[] {
		return root ? Array.from(root.querySelectorAll<HTMLElement>('[data-menu-item]:not([aria-disabled="true"])')) : [];
	}

	function onKey(e: KeyboardEvent) {
		const list = enabledEls();
		if (!list.length) return;
		const i = list.indexOf(document.activeElement as HTMLElement);
		let next = -1;
		if (e.key === 'ArrowDown') next = i < 0 ? 0 : (i + 1) % list.length;
		else if (e.key === 'ArrowUp') next = i < 0 ? list.length - 1 : (i - 1 + list.length) % list.length;
		else if (e.key === 'Home') next = 0;
		else if (e.key === 'End') next = list.length - 1;
		if (next < 0) return;
		e.preventDefault();
		list[next].focus();
	}

	function activate(item: MenuItemSpec, e: MouseEvent) {
		if (item.disabled) {
			e.preventDefault();
			return;
		}
		item.onclick?.(e);
		onselect?.(item);
	}

	$effect(() => {
		// focus the tab stop: the current choice when there is one, else the first enabled item
		if (!autofocus) return;
		let raf = 0;
		let tries = 0;
		const attempt = () => {
			if (!root?.isConnected || root.contains(document.activeElement)) return;
			const el = root.querySelector<HTMLElement>('[data-menu-item][tabindex="0"]') ?? enabledEls()[0];
			el?.focus();
			// a menu in a Popover is visibility:hidden until placed, and a hidden
			// element drops focus: try again on the next frames (the Popover also
			// moves focus to this tab stop once it shows)
			if (el && document.activeElement !== el && ++tries < 5) raf = requestAnimationFrame(attempt);
		};
		queueMicrotask(attempt);
		return () => cancelAnimationFrame(raf);
	});
</script>

<ul data-ui="menu" role="menu" aria-label={label} class={['menu', cls]} bind:this={root} onkeydown={onKey} {...rest}>
	{#each items as item (item.id)}
		{#if item.kind === 'divider'}
			<li role="separator" class="divider"></li>
		{:else if item.kind === 'header'}
			<li role="presentation" class="header">{item.label}</li>
		{:else}
			{#snippet entry()}
				{@const choice = item.selected !== undefined}
				<svelte:element
					this={item.href && !item.disabled ? 'a' : 'button'}
					href={item.href && !item.disabled ? item.href : undefined}
					type={item.href && !item.disabled ? undefined : 'button'}
					role={choice ? 'menuitemradio' : 'menuitem'}
					aria-checked={choice ? item.selected : undefined}
					aria-disabled={item.disabled ? 'true' : undefined}
					tabindex={item.id === tabStop ? 0 : -1}
					data-menu-item={item.id}
					onfocus={() => (focusedId = item.id)}
					class={[
						'item',
						item.intent === 'danger' && 'danger',
						item.intent === 'primary' && 'primary',
						item.disabled && 'disabled',
						item.selected && 'is-selected'
					]}
					onclick={(e: MouseEvent) => activate(item, e)}
					{...item.attrs}
				>
					{#if item.icon}<Icon name={item.icon} size={16} />{/if}
					<span class="label">{item.label}</span>
					{#if item.rightLabel}<span class="hint">{item.rightLabel}</span>{/if}
				</svelte:element>
			{/snippet}
			<li role="none">
				{#if item.disabled && item.disabledReason}
					<Tooltip content={item.disabledReason} placement="right">{@render entry()}</Tooltip>
				{:else}
					{@render entry()}
				{/if}
			</li>
		{/if}
	{/each}
</ul>

<style>
	.menu {
		min-width: 180px;
		margin: 0;
		padding: 4px;
		list-style: none;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
	}

	.item {
		display: flex;
		align-items: center;
		gap: 8px;
		box-sizing: border-box;
		width: 100%;
		min-height: 30px;
		margin: 0;
		padding: 4px 8px;
		border: 0;
		border-radius: var(--v-radius-btn);
		background: transparent;
		color: inherit;
		font: inherit;
		text-align: left;
		text-decoration: none;
		white-space: nowrap;
		cursor: pointer;
		outline: 0;
	}

	.item :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.item:hover,
	.item:focus-visible,
	.item:focus {
		background: var(--v-hover);
	}

	.label {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.hint {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		gap: 4px;
		padding-left: 16px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-variant-numeric: tabular-nums;
	}

	.danger,
	.danger :global([data-ui='icon']) {
		color: var(--v-danger-text);
	}

	.danger:hover,
	.danger:focus {
		background: var(--v-danger-veil);
	}

	.primary,
	.primary :global([data-ui='icon']) {
		color: var(--v-primary-text);
	}

	.item.is-selected {
		background: var(--v-primary-veil);
		box-shadow: inset 2px 0 0 var(--v-primary-text);
		color: var(--v-primary-text);
	}

	.item.is-selected :global([data-ui='icon']),
	.item.is-selected .hint {
		color: var(--v-primary-text);
	}

	.disabled,
	.disabled :global([data-ui='icon']),
	.disabled .hint {
		color: var(--v-ink-disabled);
		cursor: not-allowed;
	}

	.disabled:hover,
	.disabled:focus {
		background: transparent;
	}

	.header {
		padding: 8px 8px 4px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-weight: 600;
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.divider {
		height: 1px;
		margin: 4px -4px;
		background: var(--v-line-2);
	}
</style>
