<script lang="ts" generics="V extends string">
	/**
	 * SegmentedControl — one choice among a few (view, time window, theme).
	 * The chosen option uses .is-pressed (the controls' active-state rule).
	 * Radio semantics: role="radiogroup", options role="radio" with
	 * aria-checked; Left/Right (and Up/Down) move the choice.
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import type { IconName } from '$lib/design/icons';
	import Icon from './Icon.svelte';
	import Tooltip from './Tooltip.svelte';

	interface Option {
		value: V;
		label?: string;
		icon?: IconName;
		disabled?: boolean;
		/** Accessible name / tooltip text for an icon-only option. */
		title?: string;
		/** Extra attributes for this option's button (data-* hooks). */
		attrs?: Record<string, string>;
	}

	interface Props extends Omit<HTMLAttributes<HTMLDivElement>, 'onchange'> {
		options: readonly Option[];
		value?: V;
		onchange?: (value: V) => void;
		small?: boolean;
		fill?: boolean;
		label?: string;
	}

	let {
		options,
		value = $bindable(),
		onchange,
		small = false,
		fill = false,
		label,
		class: cls = '',
		...rest
	}: Props = $props();

	let root: HTMLDivElement | undefined = $state();

	function choose(v: V) {
		if (v === value) return;
		value = v;
		onchange?.(v);
	}

	function onKey(e: KeyboardEvent) {
		const enabled = options.filter((o) => !o.disabled);
		const i = enabled.findIndex((o) => o.value === value);
		let next = -1;
		if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (i + 1) % enabled.length;
		else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (i - 1 + enabled.length) % enabled.length;
		else if (e.key === 'Home') next = 0;
		else if (e.key === 'End') next = enabled.length - 1;
		if (next < 0 || !enabled.length) return;
		e.preventDefault();
		choose(enabled[next].value);
		queueMicrotask(() => root?.querySelector<HTMLButtonElement>('[aria-checked="true"]')?.focus());
	}
</script>

<div
	data-ui="segmented-control"
	role="radiogroup"
	aria-label={label}
	class={['seg', small && 'small', fill && 'fill', cls]}
	bind:this={root}
	onkeydown={onKey}
	{...rest}
>
	{#each options as o (o.value)}
		{#snippet opt()}
			<button
				type="button"
				role="radio"
				aria-checked={o.value === value}
				aria-label={o.label ? undefined : o.title}
				tabindex={o.value === value || (value === undefined && o === options[0]) ? 0 : -1}
				disabled={o.disabled || undefined}
				class={['opt', o.value === value && 'is-pressed']}
				onclick={() => choose(o.value)}
				{...o.attrs}
			>
				{#if o.icon}<Icon name={o.icon} size={16} />{/if}
				{#if o.label}<span>{o.label}</span>{/if}
			</button>
		{/snippet}
		{#if !o.label && o.title}
			<Tooltip content={o.title}>{@render opt()}</Tooltip>
		{:else}
			{@render opt()}
		{/if}
	{/each}
</div>

<style>
	.seg {
		display: inline-flex;
		flex: 0 0 auto;
		gap: 2px;
		padding: 2px;
		border-radius: var(--v-radius-btn);
		background: var(--v-surface-sink);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
		vertical-align: middle;
	}

	.opt {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		justify-content: center;
		gap: 4px;
		min-height: calc(var(--v-ctl-md) - 6px);
		min-width: calc(var(--v-ctl-md) - 6px);
		padding: 0 8px;
		border: 0;
		border-radius: calc(var(--v-radius-btn) - 1px);
		background: transparent;
		color: var(--v-ink-2);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
		white-space: nowrap;
		cursor: pointer;
		transition: color var(--v-dur-out) var(--v-ease);
	}

	.opt :global([data-ui='icon']) {
		color: inherit;
	}

	.opt:hover {
		color: var(--v-ink-1);
	}

	.opt:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 0;
	}

	.opt:disabled {
		color: var(--v-ink-disabled);
		cursor: not-allowed;
	}

	.opt.is-pressed {
		background: var(--v-surface-4);
		color: var(--v-ink-1);
		box-shadow:
			inset 0 0 0 1px var(--v-line-1),
			0 1px 2px color-mix(in srgb, var(--v-backdrop) 30%, transparent);
	}

	.small .opt {
		min-height: calc(var(--v-ctl-sm) - 4px);
		min-width: calc(var(--v-ctl-sm) - 4px);
		padding: 0 4px;
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.fill {
		display: flex;
		width: 100%;
	}

	.fill .opt {
		flex: 1 1 0;
	}
</style>
