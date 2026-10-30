<script lang="ts">
	/**
	 * HTMLSelect — a native <select> styled as a Blueprint button with a
	 * caret. `options` are strings or {value, label, disabled}. `value` is
	 * bindable; `...rest` goes on the <select>.
	 */
	import type { HTMLSelectAttributes } from 'svelte/elements';
	import Icon from './Icon.svelte';

	type Opt = string | { value: string; label?: string; disabled?: boolean };

	interface Props extends Omit<HTMLSelectAttributes, 'value'> {
		value?: string;
		options: readonly Opt[];
		minimal?: boolean;
		small?: boolean;
		large?: boolean;
		fill?: boolean;
	}

	let {
		value = $bindable(),
		options,
		minimal = false,
		small = false,
		large = false,
		fill = false,
		disabled = false,
		class: cls = '',
		...rest
	}: Props = $props();

	const norm = $derived(options.map((o) => (typeof o === 'string' ? { value: o, label: o, disabled: false } : o)));
</script>

<span
	data-ui="html-select"
	class={['sel', minimal && 'minimal', small && 'small', large && 'large', fill && 'fill', disabled && 'disabled', cls]}
>
	<select bind:value {disabled} {...rest}>
		{#each norm as o (o.value)}
			<option value={o.value} disabled={o.disabled}>{o.label ?? o.value}</option>
		{/each}
	</select>
	<Icon name="caret-down" size={16} class="caret" />
</span>

<style>
	.sel {
		position: relative;
		display: inline-flex;
		align-items: center;
		vertical-align: middle;
	}

	.fill {
		display: flex;
		width: 100%;
	}

	select {
		box-sizing: border-box;
		width: 100%;
		height: var(--v-ctl-md);
		margin: 0;
		padding: 0 28px 0 8px;
		border: 0;
		border-radius: var(--v-radius-btn);
		appearance: none;
		background: var(--v-surface-2);
		color: var(--v-ink-1);
		box-shadow:
			inset 0 0 0 1px var(--v-line-1),
			0 1px 2px color-mix(in srgb, var(--v-backdrop) 30%, transparent);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		cursor: pointer;
	}

	select:hover {
		background: var(--v-surface-1);
	}

	select:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 2px;
	}

	select:disabled {
		background: color-mix(in srgb, var(--v-hover) 40%, transparent);
		box-shadow: none;
		color: var(--v-ink-disabled);
		cursor: not-allowed;
	}

	.sel :global(.caret) {
		position: absolute;
		right: 6px;
		color: var(--v-ink-2);
		pointer-events: none;
	}

	.disabled :global(.caret) {
		color: var(--v-ink-disabled);
	}

	.minimal select {
		background: transparent;
		box-shadow: none;
	}

	.minimal select:hover {
		background: var(--v-minimal-hover);
	}

	.small select {
		height: var(--v-ctl-sm);
		font-size: var(--v-text-xs);
		padding-right: 24px;
	}

	.large select {
		height: var(--v-ctl-lg);
		font-size: var(--v-text-md);
	}

	option {
		background: var(--v-surface-2);
		color: var(--v-ink-1);
	}
</style>
