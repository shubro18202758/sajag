<script lang="ts">
	/**
	 * CompoundTag — a key and a value in one 20 px tag ("Band │ Green").
	 * The key half sits on a darker veil in ink-2; the value half in ink-1,
	 * or in the intent's text ink. SPEC §5.1: `intent, icon, removable,
	 * interactive`, as Tag.
	 *
	 * - removable: an ✕ button at the end of the value half (aria-label
	 *   "Remove", in the provided language) that calls onremove; the click
	 *   never reaches the tag (a workspace filter chip: "Kind │ Vehicles ✕");
	 * - interactive: hover feedback, a pointer, Enter/Space act like a click.
	 *
	 * `...rest` goes on the tag's root span.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import type { IconName } from '$lib/design/icons';
	import Icon from './Icon.svelte';
	import Tooltip from './Tooltip.svelte';
	import { uiLang, ut } from './lang';
	import type { TagIntent } from './types';

	interface Props extends HTMLAttributes<HTMLSpanElement> {
		/** The key (left) half. */
		left: string;
		/** The value (right) half; or pass children. */
		value?: string | number | null;
		intent?: TagIntent;
		icon?: IconName;
		removable?: boolean;
		onremove?: (e: MouseEvent) => void;
		interactive?: boolean;
		tooltip?: string | null;
		lang?: string;
		children?: Snippet;
	}

	let {
		left,
		value = null,
		intent = 'none',
		icon,
		removable = false,
		onremove,
		interactive = false,
		tooltip = null,
		lang,
		children,
		class: cls = '',
		...rest
	}: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());

	/** Enter and Space activate an interactive tag like a button. */
	function activate(e: KeyboardEvent) {
		if (e.target !== e.currentTarget) return;
		if (e.key !== 'Enter' && e.key !== ' ') return;
		e.preventDefault();
		(e.currentTarget as HTMLElement).click();
	}
</script>

{#snippet ctag()}
	<!-- svelte-ignore a11y_no_noninteractive_tabindex (role is "button" whenever tabindex is set) -->
	<span
		data-ui="compound-tag"
		data-intent={intent}
		class={['ctag', `i-${intent}`, interactive && 'interactive', removable && 'removable', cls]}
		role={interactive ? 'button' : undefined}
		tabindex={interactive ? 0 : undefined}
		onkeydown={interactive ? activate : undefined}
		{...rest}
	>
		<span class="k">{#if icon}<Icon name={icon} size={12} />{/if}{left}</span>
		<!-- .v is an inline-flex row: the whitespace between its children never renders -->
		<span class="v">
			{#if children}{@render children()}{:else}{value ?? '—'}{/if}
			{#if removable}
				<button
					type="button"
					class="x"
					aria-label={ut(L, 'ui_remove')}
					onclick={(e) => {
						e.stopPropagation();
						onremove?.(e);
					}}
				>
					<Icon name="small-cross" size={16} />
				</button>
			{/if}
		</span>
	</span>
{/snippet}

{#if tooltip}
	<Tooltip content={tooltip}>{@render ctag()}</Tooltip>
{:else}
	{@render ctag()}
{/if}

<style>
	.ctag {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: stretch;
		min-height: 20px;
		overflow: hidden;
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
		white-space: nowrap;
		vertical-align: middle;
	}

	.k,
	.v {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 2px 6px;
	}

	.k {
		background: var(--v-neutral-veil);
		color: var(--v-ink-2);
	}

	.v {
		color: var(--v-ink-1);
		font-variant-numeric: tabular-nums;
	}

	.k :global([data-ui='icon']) {
		color: inherit;
	}

	.i-primary .v {
		color: var(--v-primary-text);
	}

	.i-success .v {
		color: var(--v-success-text);
	}

	.i-warning .v {
		color: var(--v-warning-text);
	}

	.i-danger .v {
		color: var(--v-danger-text);
	}

	.i-ai .v {
		color: var(--v-ai-text);
	}

	.interactive {
		cursor: pointer;
	}

	.interactive:hover .v {
		background: var(--v-hover);
	}

	.interactive:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 1px;
	}

	/* the remove cross: Tag's 16 px small-cross, tucked into the value half's end padding */
	.removable .v {
		padding-right: 2px;
	}

	.x {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		margin: 0 0 0 -2px;
		padding: 0;
		border: 0;
		border-radius: 2px;
		background: transparent;
		color: inherit;
		cursor: pointer;
	}

	.x:hover {
		background: var(--v-hover);
	}

	.x:focus-visible {
		outline: 2px solid var(--v-focus);
	}
</style>
