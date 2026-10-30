<script lang="ts">
	/**
	 * NavButton — a minimal navbar control (Blueprint `bp6-button bp6-minimal`
	 * metrics: 30 px high, 4 px radius, ink-2 glyph). Its tooltip sits INSIDE
	 * the button, around a box that fills it, so the button itself stays the
	 * direct target of a Popover (a Tooltip around a Popover target, or a
	 * Popover around a Tooltip, would hand one of them a display:contents box
	 * to place against). `pressed` is the one active-state rule (.is-pressed,
	 * aria-pressed). `...rest` (data-testid, data-*, aria-*, onclick) goes on
	 * the <button>.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import type { IconName } from '$lib/design/icons';
	import Icon from '$lib/ui/Icon.svelte';
	import Tooltip from '$lib/ui/Tooltip.svelte';

	interface Props extends HTMLButtonAttributes {
		icon?: IconName;
		tip?: string | null;
		pressed?: boolean;
		iconOnly?: boolean;
		children?: Snippet;
	}

	let { icon, tip = null, pressed, iconOnly = false, children, class: cls = '', ...rest }: Props = $props();
</script>

<button
	type="button"
	class={['nav-btn', iconOnly && 'icon-only', pressed === true && 'is-pressed', cls]}
	aria-pressed={pressed === undefined ? undefined : pressed}
	{...rest}
>
	<Tooltip content={tip} placement="bottom">
		<span class="in">
			{#if icon}<Icon name={icon} size={16} />{/if}
			{@render children?.()}
		</span>
	</Tooltip>
</button>

<style>
	.nav-btn {
		position: relative;
		display: inline-flex;
		flex: 0 0 auto;
		align-items: stretch;
		box-sizing: border-box;
		min-width: var(--v-ctl-md);
		height: var(--v-ctl-md);
		margin: 0;
		padding: 0;
		border: 0;
		border-radius: var(--v-radius-btn);
		background: transparent;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
		white-space: nowrap;
		cursor: pointer;
		transition: background-color var(--v-dur-out) var(--v-ease);
	}

	.nav-btn:hover {
		background: var(--v-minimal-hover);
	}

	.nav-btn:active {
		background: var(--v-minimal-active);
	}

	.nav-btn:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 2px;
		z-index: 1;
	}

	.in {
		display: inline-flex;
		flex: 1 1 auto;
		align-items: center;
		justify-content: center;
		gap: 8px;
		padding: 0 8px;
	}

	.icon-only .in {
		padding: 0;
	}

	.in :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.nav-btn.is-pressed .in :global([data-ui='icon']) {
		color: var(--v-ink-1);
	}

	.nav-btn:disabled {
		cursor: not-allowed;
		color: var(--v-ink-disabled);
	}
</style>
