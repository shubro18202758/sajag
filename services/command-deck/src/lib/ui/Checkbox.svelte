<script lang="ts">
	/**
	 * Checkbox — a 16 px box: a 1 px line when off, the primary fill with a
	 * tick when on, a bar when indeterminate. A native checkbox underneath.
	 * `checked` and `indeterminate` are bindable; `...rest` goes on the
	 * <input>.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLInputAttributes } from 'svelte/elements';
	import Icon from './Icon.svelte';

	interface Props extends Omit<HTMLInputAttributes, 'onchange' | 'size'> {
		checked?: boolean;
		indeterminate?: boolean;
		label?: string | null;
		onchange?: (checked: boolean) => void;
		children?: Snippet;
	}

	let {
		checked = $bindable(false),
		indeterminate = $bindable(false),
		label = null,
		disabled = false,
		onchange,
		children,
		class: cls = '',
		...rest
	}: Props = $props();
</script>

<label data-ui="checkbox" class={['cb', disabled && 'disabled', cls]}>
	<input
		type="checkbox"
		class="native"
		bind:checked
		bind:indeterminate
		{disabled}
		onchange={() => onchange?.(checked)}
		{...rest}
	/>
	<span class="box" aria-hidden="true">
		{#if indeterminate}<Icon name="minus" size={12} />{:else if checked}<Icon name="small-tick" size={16} />{/if}
	</span>
	{#if label || children}<span class="text">{#if children}{@render children()}{:else}{label}{/if}</span>{/if}
</label>

<style>
	.cb {
		position: relative;
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: 20px;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
		cursor: pointer;
		user-select: none;
		vertical-align: middle;
	}

	.native {
		position: absolute;
		width: 1px;
		height: 1px;
		margin: 0;
		opacity: 0;
		pointer-events: none;
	}

	.box {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		justify-content: center;
		width: 16px;
		height: 16px;
		border-radius: calc(var(--v-radius-chip) - 1px);
		background: color-mix(in srgb, var(--v-surface-sink) 30%, transparent);
		box-shadow: inset 0 0 0 1px var(--v-line-strong);
		color: var(--v-on-fill);
	}

	.cb:hover .box {
		box-shadow: inset 0 0 0 1px var(--v-ink-2);
	}

	.native:checked + .box,
	.native:indeterminate + .box {
		background: var(--v-primary);
		box-shadow: none;
	}

	.native:focus-visible + .box {
		outline: 2px solid var(--v-focus);
		outline-offset: 2px;
	}

	.box :global([data-ui='icon']) {
		color: var(--v-on-fill);
	}

	.disabled {
		color: var(--v-ink-disabled);
		cursor: not-allowed;
	}

	.disabled .box {
		box-shadow: inset 0 0 0 1px var(--v-line-1);
		background: transparent;
	}

	.disabled .native:checked + .box,
	.disabled .native:indeterminate + .box {
		background: color-mix(in srgb, var(--v-primary) 50%, transparent);
	}
</style>
