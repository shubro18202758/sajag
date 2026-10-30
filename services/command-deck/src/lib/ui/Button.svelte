<script lang="ts">
	/**
	 * Button (SPEC §5.1) — Blueprint metrics: 30 px (24 small, 40 large),
	 * 14 px text, 4 px radius, an 8 px gap between glyph and label.
	 *
	 * - intent: none | primary | success | warning | danger, each only in its
	 *   SPEC §2.4 role (types.ts). At most one primary button per surface;
	 *   Reject, Dismiss and Cancel are default (neutral) buttons to its left.
	 *   A decision verb is never green or red; warning and danger appear on a
	 *   button only as states (the Inbox button: a decision waits, an unread
	 *   watchlist read).
	 * - minimal (no fill until hover), outlined, small, large, fill.
	 * - pressed: a toggle; sets .is-pressed and aria-pressed (the one
	 *   active-state rule for controls). Leave undefined for a plain button.
	 * - disabledReason: shown as a tooltip on the disabled button and, with
	 *   reasonInline, as an inline Reason line under it.
	 * - loading: a spinner over the content; the width never changes.
	 * - icon / rightIcon: Blueprint glyph names; an icon-only button needs a
	 *   `tooltip` (it becomes the accessible name) or an aria-label.
	 * - href: renders a link styled as a button.
	 *
	 * `...rest` (data-testid, aria-*, id, onclick, …) goes on the <button>.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import type { IconName } from '$lib/design/icons';
	import Icon from './Icon.svelte';
	import Reason from './Reason.svelte';
	import Spinner from './Spinner.svelte';
	import Tooltip from './Tooltip.svelte';
	import type { Intent } from './types';

	interface Props extends HTMLButtonAttributes {
		intent?: Intent;
		minimal?: boolean;
		outlined?: boolean;
		small?: boolean;
		large?: boolean;
		fill?: boolean;
		pressed?: boolean;
		disabled?: boolean;
		disabledReason?: string | null;
		reasonInline?: boolean;
		loading?: boolean;
		icon?: IconName;
		rightIcon?: IconName;
		tooltip?: string | null;
		alignText?: 'left' | 'center' | 'right';
		href?: string;
		children?: Snippet;
	}

	let {
		intent = 'none',
		minimal = false,
		outlined = false,
		small = false,
		large = false,
		fill = false,
		pressed,
		disabled = false,
		disabledReason = null,
		reasonInline = false,
		loading = false,
		icon,
		rightIcon,
		tooltip = null,
		alignText = 'center',
		href,
		type = 'button',
		children,
		class: cls = '',
		...rest
	}: Props = $props();

	const tip = $derived(disabled && disabledReason ? disabledReason : tooltip);
	const iconOnly = $derived(!children);
	const classes = $derived([
		'btn',
		intent !== 'none' && intent,
		minimal && 'minimal',
		outlined && 'outlined',
		small && 'small',
		large && 'large',
		fill && 'fill',
		iconOnly && 'icon-only',
		loading && 'loading',
		pressed === true && 'is-pressed',
		alignText !== 'center' && `align-${alignText}`,
		cls
	]);
	const ariaLabel = $derived(
		(rest['aria-label'] as string | undefined) ?? (iconOnly ? (tooltip ?? disabledReason ?? undefined) : undefined)
	);
</script>

{#snippet inner()}
	{#if loading}<span class="spin"><Spinner size={16} /></span>{/if}
	{#if icon}<Icon name={icon} size={16} />{/if}
	{#if children}<span class="label">{@render children()}</span>{/if}
	{#if rightIcon}<Icon name={rightIcon} size={16} />{/if}
{/snippet}

{#snippet control()}
	{#if href && !disabled}
		<a data-ui="button" class={classes} {href} aria-label={ariaLabel} {...rest as Record<string, unknown>}>
			{@render inner()}
		</a>
	{:else}
		<button
			data-ui="button"
			class={classes}
			{type}
			disabled={disabled || undefined}
			aria-pressed={pressed === undefined ? undefined : pressed}
			aria-busy={loading || undefined}
			aria-label={ariaLabel}
			{...rest}
		>
			{@render inner()}
		</button>
	{/if}
{/snippet}

{#snippet withTip()}
	{#if tip}
		<Tooltip content={tip}>{@render control()}</Tooltip>
	{:else}
		{@render control()}
	{/if}
{/snippet}

{#if reasonInline && disabled && disabledReason}
	<span class="with-reason" class:fill>
		{@render withTip()}
		<Reason text={disabledReason} />
	</span>
{:else}
	{@render withTip()}
{/if}

<style>
	.btn {
		position: relative;
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		justify-content: center;
		gap: 8px;
		box-sizing: border-box;
		min-height: var(--v-ctl-md);
		min-width: var(--v-ctl-md);
		margin: 0;
		padding: 0 8px;
		border: 0;
		border-radius: var(--v-radius-btn);
		background: var(--v-surface-2);
		color: var(--v-ink-1);
		box-shadow:
			inset 0 0 0 1px var(--v-line-1),
			0 1px 2px color-mix(in srgb, var(--v-backdrop) 30%, transparent);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-base);
		font-weight: 400;
		line-height: calc(var(--v-text-base) + 4px);
		text-align: left;
		text-decoration: none;
		white-space: nowrap;
		vertical-align: middle;
		cursor: pointer;
		user-select: none;
		transition:
			background-color var(--v-dur-out) var(--v-ease),
			box-shadow var(--v-dur-out) var(--v-ease);
	}

	.btn :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.btn:hover {
		background: var(--v-surface-1);
	}

	.btn:active {
		background: var(--v-canvas);
	}

	.btn:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 2px;
		z-index: 1;
	}

	.label {
		display: inline-flex;
		align-items: center;
		gap: 4px;
	}

	/* intents: a fill with the on-fill ink */
	.primary,
	.success,
	.danger {
		color: var(--v-on-fill);
	}

	.primary :global([data-ui='icon']),
	.success :global([data-ui='icon']),
	.danger :global([data-ui='icon']) {
		color: var(--v-on-fill);
	}

	.primary {
		background: var(--v-primary);
	}

	.primary:hover {
		background: var(--v-primary-hover);
	}

	.primary:active {
		background: var(--v-primary-active);
	}

	.success {
		background: var(--v-success);
	}

	.success:hover {
		background: var(--v-success-hover);
	}

	.success:active {
		background: var(--v-success-active);
	}

	.danger {
		background: var(--v-danger);
	}

	.danger:hover {
		background: var(--v-danger-hover);
	}

	.danger:active {
		background: var(--v-danger-active);
	}

	/* warning fill is the light orange with dark ink (white fails AA on orange 3) */
	.warning {
		background: var(--v-warning-text);
		color: var(--v-canvas);
	}

	.warning :global([data-ui='icon']) {
		color: var(--v-canvas);
	}

	.warning:hover {
		background: color-mix(in srgb, var(--v-warning-text) 86%, var(--v-canvas));
	}

	.warning:active {
		background: color-mix(in srgb, var(--v-warning-text) 74%, var(--v-canvas));
	}

	/* minimal and outlined: no fill until hover */
	.minimal,
	.outlined {
		background: transparent;
		box-shadow: none;
		color: var(--v-ink-1);
	}

	.outlined {
		box-shadow: inset 0 0 0 1px var(--v-line-strong);
	}

	.minimal:hover,
	.outlined:hover {
		background: var(--v-minimal-hover);
	}

	.minimal:active,
	.outlined:active {
		background: var(--v-minimal-active);
	}

	.minimal.primary,
	.outlined.primary,
	.minimal.primary :global([data-ui='icon']),
	.outlined.primary :global([data-ui='icon']) {
		color: var(--v-primary-text);
	}

	.minimal.success,
	.outlined.success,
	.minimal.success :global([data-ui='icon']),
	.outlined.success :global([data-ui='icon']) {
		color: var(--v-success-text);
	}

	.minimal.warning,
	.outlined.warning,
	.minimal.warning :global([data-ui='icon']),
	.outlined.warning :global([data-ui='icon']) {
		color: var(--v-warning-text);
	}

	.minimal.danger,
	.outlined.danger,
	.minimal.danger :global([data-ui='icon']),
	.outlined.danger :global([data-ui='icon']) {
		color: var(--v-danger-text);
	}

	.outlined.primary {
		box-shadow: inset 0 0 0 1px var(--v-primary-text);
	}

	.outlined.success {
		box-shadow: inset 0 0 0 1px var(--v-success-text);
	}

	.outlined.warning {
		box-shadow: inset 0 0 0 1px var(--v-warning-text);
	}

	.outlined.danger {
		box-shadow: inset 0 0 0 1px var(--v-danger-text);
	}

	.minimal.primary:hover,
	.outlined.primary:hover {
		background: var(--v-primary-veil);
	}

	.minimal.success:hover,
	.outlined.success:hover {
		background: var(--v-success-veil);
	}

	.minimal.warning:hover,
	.outlined.warning:hover {
		background: var(--v-warning-veil);
	}

	.minimal.danger:hover,
	.outlined.danger:hover {
		background: var(--v-danger-veil);
	}

	/* sizes */
	.small {
		min-height: var(--v-ctl-sm);
		min-width: var(--v-ctl-sm);
		gap: 4px;
	}

	.large {
		min-height: var(--v-ctl-lg);
		min-width: var(--v-ctl-lg);
		padding: 0 16px;
		font-size: var(--v-text-md);
		line-height: calc(var(--v-text-md) + 4px);
	}

	.fill {
		display: flex;
		width: 100%;
	}

	.align-left {
		justify-content: flex-start;
	}

	.align-left .label,
	.align-right .label {
		flex: 1 1 auto;
	}

	.align-right {
		justify-content: flex-end;
		text-align: right;
	}

	.icon-only {
		padding: 0;
	}

	/* the one active-state rule for controls */
	.btn.is-pressed {
		background: var(--v-surface-4);
		color: var(--v-ink-1);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
	}

	.btn.is-pressed :global([data-ui='icon']) {
		color: var(--v-ink-1);
	}

	/* disabled: quiet, says why through the tooltip / Reason */
	.btn:disabled {
		cursor: not-allowed;
		background: color-mix(in srgb, var(--v-hover) 40%, transparent);
		box-shadow: none;
		color: var(--v-ink-disabled);
	}

	.btn:disabled :global([data-ui='icon']) {
		color: var(--v-ink-disabled);
	}

	.btn.minimal:disabled,
	.btn.outlined:disabled {
		background: transparent;
	}

	.btn.outlined:disabled {
		box-shadow: inset 0 0 0 1px var(--v-line-1);
	}

	.btn.primary:not(.minimal):not(.outlined):disabled {
		background: var(--v-primary);
		color: var(--v-on-fill);
		opacity: 0.5;
	}

	.btn.success:not(.minimal):not(.outlined):disabled {
		background: var(--v-success);
		color: var(--v-on-fill);
		opacity: 0.5;
	}

	.btn.danger:not(.minimal):not(.outlined):disabled {
		background: var(--v-danger);
		color: var(--v-on-fill);
		opacity: 0.5;
	}

	.btn.warning:not(.minimal):not(.outlined):disabled {
		background: var(--v-warning-text);
		color: var(--v-canvas);
		opacity: 0.5;
	}

	.btn.primary:disabled :global([data-ui='icon']),
	.btn.success:disabled :global([data-ui='icon']),
	.btn.danger:disabled :global([data-ui='icon']) {
		color: inherit;
	}

	/* loading keeps the width: the content is hidden under the spinner */
	.loading {
		cursor: progress;
	}

	.loading > :global(:not(.spin)) {
		visibility: hidden;
	}

	.spin {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.with-reason {
		display: inline-flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 4px;
	}

	.with-reason.fill {
		display: flex;
		align-items: stretch;
	}
</style>
