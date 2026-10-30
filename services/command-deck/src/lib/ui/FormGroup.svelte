<script lang="ts">
	/**
	 * FormGroup — a label above a control, an optional label info
	 * ("(required)"), and a 12 px helper line under it; `intent` tints the
	 * helper (an error explains itself there). `inline` puts the label
	 * beside the control.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import type { Intent } from './types';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		label?: string | null;
		labelFor?: string;
		labelInfo?: string | null;
		helperText?: string | null;
		intent?: Intent;
		inline?: boolean;
		disabled?: boolean;
		children?: Snippet;
	}

	let {
		label = null,
		labelFor,
		labelInfo = null,
		helperText = null,
		intent = 'none',
		inline = false,
		disabled = false,
		children,
		class: cls = '',
		...rest
	}: Props = $props();
</script>

<div
	data-ui="form-group"
	class={['fg', inline && 'inline', disabled && 'disabled', intent !== 'none' && `i-${intent}`, cls]}
	{...rest}
>
	{#if label}
		<label class="label" for={labelFor}>{label}{#if labelInfo}<span class="info">{labelInfo}</span>{/if}</label>
	{/if}
	<div class="content">
		{@render children?.()}
		{#if helperText}<div class="helper">{helperText}</div>{/if}
	</div>
</div>

<style>
	.fg {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 0 0 12px;
		font-family: var(--v-font-ui);
		color: var(--v-ink-1);
	}

	.inline {
		flex-direction: row;
		align-items: flex-start;
		gap: 12px;
	}

	.inline .label {
		line-height: var(--v-ctl-md);
	}

	.label {
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
	}

	.info {
		margin-left: 4px;
		color: var(--v-ink-2);
	}

	.content {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}

	.helper {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.i-primary .helper {
		color: var(--v-primary-text);
	}

	.i-success .helper {
		color: var(--v-success-text);
	}

	.i-warning .helper {
		color: var(--v-warning-text);
	}

	.i-danger .helper {
		color: var(--v-danger-text);
	}

	.disabled .label,
	.disabled .helper {
		color: var(--v-ink-disabled);
	}
</style>
