<script lang="ts">
	/**
	 * Switch — an on/off setting with an immediate effect. The blue track is
	 * the on state (SPEC §5.1: switches use the blue track). A native
	 * checkbox with role="switch" underneath, so it is keyboard- and
	 * screen-reader-correct. `checked` is bindable; `...rest` goes on the
	 * <input>.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLInputAttributes } from 'svelte/elements';

	interface Props extends Omit<HTMLInputAttributes, 'onchange' | 'size'> {
		checked?: boolean;
		label?: string | null;
		alignIndicator?: 'left' | 'right';
		small?: boolean;
		onchange?: (checked: boolean) => void;
		children?: Snippet;
	}

	let {
		checked = $bindable(false),
		label = null,
		alignIndicator = 'left',
		small = false,
		disabled = false,
		onchange,
		children,
		class: cls = '',
		...rest
	}: Props = $props();
</script>

<label
	data-ui="switch"
	class={['sw', alignIndicator === 'right' && 'right', small && 'small', disabled && 'disabled', cls]}
>
	<input
		type="checkbox"
		role="switch"
		class="native"
		bind:checked
		{disabled}
		onchange={() => onchange?.(checked)}
		{...rest}
	/>
	<span class="track" aria-hidden="true"><span class="knob"></span></span>
	{#if label || children}<span class="text">{#if children}{@render children()}{:else}{label}{/if}</span>{/if}
</label>

<style>
	.sw {
		position: relative;
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: 20px;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
		white-space: nowrap;
		cursor: pointer;
		user-select: none;
		vertical-align: middle;
	}

	.right {
		flex-direction: row-reverse;
		justify-content: space-between;
	}

	.native {
		position: absolute;
		width: 1px;
		height: 1px;
		margin: 0;
		opacity: 0;
		pointer-events: none;
	}

	.track {
		position: relative;
		flex: 0 0 auto;
		width: 28px;
		height: 16px;
		border-radius: var(--v-radius-pill);
		background: var(--v-minimal-active);
		transition: background-color var(--v-dur-out) var(--v-ease);
	}

	.knob {
		position: absolute;
		top: 2px;
		left: 2px;
		width: 12px;
		height: 12px;
		border-radius: 50%;
		background: var(--v-on-fill);
		box-shadow: 0 1px 2px color-mix(in srgb, var(--v-backdrop) 50%, transparent);
		transition: left var(--v-dur-out) var(--v-ease);
	}

	.sw:hover .track {
		background: color-mix(in srgb, var(--v-ink-4) 80%, transparent);
	}

	.native:checked + .track {
		background: var(--v-primary);
	}

	.sw:hover .native:checked + .track {
		background: var(--v-primary-hover);
	}

	.native:checked + .track .knob {
		left: 14px;
	}

	.native:focus-visible + .track {
		outline: 2px solid var(--v-focus);
		outline-offset: 2px;
	}

	.small .track {
		width: 22px;
		height: 12px;
	}

	.small .knob {
		width: 8px;
		height: 8px;
	}

	.small .native:checked + .track .knob {
		left: 12px;
	}

	.small {
		font-size: var(--v-text-xs);
	}

	.disabled {
		color: var(--v-ink-disabled);
		cursor: not-allowed;
	}

	.disabled .track,
	.sw.disabled:hover .track {
		background: color-mix(in srgb, var(--v-minimal-active) 50%, transparent);
	}

	.disabled .native:checked + .track {
		background: color-mix(in srgb, var(--v-primary) 50%, transparent);
	}
</style>
