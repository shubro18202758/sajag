<script lang="ts">
	/**
	 * Input — a 30 px text field (24 small, 40 large) on a sunk veil with a
	 * 1 px line, a blue focus ring, an optional left glyph and a right
	 * element (a key hint, a unit tag, a button). `clearable` adds a clear
	 * button while there is text. `intent` tints the outline (danger also
	 * sets aria-invalid); the colour roles of SPEC §2.4 decide where an
	 * intent may appear, so a required field says so in its label and helper.
	 *
	 * `value` is bindable. `...rest` (data-testid, name, aria-*, oninput, …)
	 * goes on the native <input>, the element tests type into; `class` goes on
	 * the group wrapper.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLInputAttributes } from 'svelte/elements';
	import type { IconName } from '$lib/design/icons';
	import Icon from './Icon.svelte';
	import { uiLang, ut } from './lang';
	import type { Intent } from './types';

	interface Props extends Omit<HTMLInputAttributes, 'value' | 'size'> {
		value?: string | null;
		leftIcon?: IconName;
		rightElement?: Snippet;
		small?: boolean;
		large?: boolean;
		fill?: boolean;
		intent?: Intent;
		clearable?: boolean;
		round?: boolean;
		inputEl?: HTMLInputElement | null;
		lang?: string;
	}

	let {
		value = $bindable(''),
		leftIcon,
		rightElement,
		small = false,
		large = false,
		fill = false,
		intent = 'none',
		clearable = false,
		round = false,
		inputEl = $bindable(null),
		disabled = false,
		readonly = false,
		lang,
		class: cls = '',
		...rest
	}: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	let rightWidth = $state(0);
	const showClear = $derived(clearable && !!value && !disabled && !readonly);

	function clear() {
		value = '';
		inputEl?.dispatchEvent(new Event('input', { bubbles: true }));
		inputEl?.focus();
	}
</script>

<span
	data-ui="input"
	class={[
		'group',
		small && 'small',
		large && 'large',
		fill && 'fill',
		round && 'round',
		intent !== 'none' && `i-${intent}`,
		leftIcon && 'has-left',
		disabled && 'disabled',
		cls
	]}
>
	{#if leftIcon}<Icon name={leftIcon} size={16} class="left" />{/if}
	<input
		class="input"
		bind:value
		bind:this={inputEl}
		{disabled}
		{readonly}
		aria-invalid={intent === 'danger' ? 'true' : undefined}
		style:padding-right={showClear || rightElement ? `${rightWidth + 8}px` : undefined}
		{...rest}
	/>
	{#if showClear || rightElement}
		<span class="right" bind:offsetWidth={rightWidth}>
			{#if showClear}
				<button type="button" class="clear" aria-label={ut(L, 'ui_clear')} onclick={clear}>
					<Icon name="small-cross" size={16} />
				</button>
			{/if}
			{@render rightElement?.()}
		</span>
	{/if}
</span>

<style>
	.group {
		position: relative;
		display: inline-flex;
		align-items: center;
		min-width: 0;
		vertical-align: middle;
	}

	.fill {
		display: flex;
		width: 100%;
	}

	.input {
		box-sizing: border-box;
		width: 100%;
		min-width: 0;
		height: var(--v-ctl-md);
		margin: 0;
		padding: 0 8px;
		border: 0;
		border-radius: var(--v-radius-btn);
		outline: 0;
		background: color-mix(in srgb, var(--v-surface-sink) 30%, transparent);
		color: var(--v-ink-1);
		box-shadow:
			inset 0 0 0 1px var(--v-line-2),
			inset 0 -1px 1px 0 var(--v-line-strong);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		line-height: var(--v-ctl-md);
		transition: box-shadow var(--v-dur-out) var(--v-ease);
	}

	.input::placeholder {
		color: var(--v-ink-2);
		opacity: 1;
	}

	.input:focus {
		box-shadow:
			inset 0 0 0 1px var(--v-focus),
			0 0 0 1px var(--v-focus);
	}

	.input:disabled {
		background: color-mix(in srgb, var(--v-hover) 50%, transparent);
		box-shadow: none;
		color: var(--v-ink-disabled);
		cursor: not-allowed;
	}

	.input[readonly] {
		box-shadow: inset 0 0 0 1px var(--v-line-1);
	}

	.round .input {
		border-radius: var(--v-radius-pill);
		padding-left: 12px;
	}

	.has-left .input {
		padding-left: 32px;
	}

	.group :global(.left) {
		position: absolute;
		left: 8px;
		color: var(--v-ink-2);
		pointer-events: none;
	}

	.right {
		position: absolute;
		right: 4px;
		display: flex;
		align-items: center;
		gap: 4px;
	}

	.clear {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
		padding: 0;
		border: 0;
		border-radius: var(--v-radius-chip);
		background: transparent;
		color: var(--v-ink-2);
		cursor: pointer;
	}

	.clear:hover {
		background: var(--v-minimal-hover);
		color: var(--v-ink-1);
	}

	.clear:focus-visible {
		outline: 2px solid var(--v-focus);
	}

	.small .input {
		height: var(--v-ctl-sm);
		font-size: var(--v-text-xs);
		line-height: var(--v-ctl-sm);
	}

	.large .input {
		height: var(--v-ctl-lg);
		font-size: var(--v-text-md);
		line-height: var(--v-ctl-lg);
	}

	.i-primary .input {
		box-shadow: inset 0 0 0 1px var(--v-primary-text);
	}

	.i-success .input {
		box-shadow: inset 0 0 0 1px var(--v-success-text);
	}

	.i-warning .input {
		box-shadow: inset 0 0 0 1px var(--v-warning-text);
	}

	.i-danger .input {
		box-shadow: inset 0 0 0 1px var(--v-danger-text);
	}

	.disabled :global(.left) {
		color: var(--v-ink-disabled);
	}
</style>
