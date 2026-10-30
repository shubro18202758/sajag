<script lang="ts">
	/**
	 * Tag — a 20 px label in sentence case (SPEC §5.1). Minimal by default: a
	 * veil of the intent's hue with the intent's text ink; `none` is the
	 * neutral veil. `ai` is the indigo of AI attribution and nothing else.
	 *
	 * - icon / rightIcon: Blueprint glyphs;
	 * - removable: an ✕ button (aria-label "Remove") that calls onremove;
	 * - interactive: hover feedback and a pointer (pass onclick);
	 * - round: a pill, used for counts;
	 * - tooltip: hover text (provenance and state tags explain themselves).
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
		intent?: TagIntent;
		icon?: IconName;
		rightIcon?: IconName;
		removable?: boolean;
		onremove?: (e: MouseEvent) => void;
		interactive?: boolean;
		round?: boolean;
		large?: boolean;
		tooltip?: string | null;
		lang?: string;
		children?: Snippet;
	}

	let {
		intent = 'none',
		icon,
		rightIcon,
		removable = false,
		onremove,
		interactive = false,
		round = false,
		large = false,
		tooltip = null,
		lang,
		children,
		class: cls = '',
		...rest
	}: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());

	/** Enter and Space activate an interactive tag like a button (not when they reach it from its ✕). */
	function activate(e: KeyboardEvent) {
		if (e.target !== e.currentTarget) return;
		if (e.key !== 'Enter' && e.key !== ' ') return;
		e.preventDefault();
		(e.currentTarget as HTMLElement).click();
	}
</script>

{#snippet tag()}
	<!-- svelte-ignore a11y_no_noninteractive_tabindex (role is "button" whenever tabindex is set) -->
	<span
		data-ui="tag"
		data-intent={intent}
		class={['tag', `i-${intent}`, interactive && 'interactive', round && 'round', large && 'large', cls]}
		role={interactive ? 'button' : undefined}
		tabindex={interactive ? 0 : undefined}
		onkeydown={interactive ? activate : undefined}
		{...rest}
	>
		{#if icon}<Icon name={icon} size={large ? 16 : 12} />{/if}
		{#if children}<span class="text">{@render children()}</span>{/if}
		{#if rightIcon}<Icon name={rightIcon} size={large ? 16 : 12} />{/if}
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
{/snippet}

{#if tooltip}
	<Tooltip content={tooltip}>{@render tag()}</Tooltip>
{:else}
	{@render tag()}
{/if}

<style>
	.tag {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: center;
		gap: 4px;
		box-sizing: border-box;
		max-width: 100%;
		min-height: 20px;
		min-width: 20px;
		padding: 2px 6px;
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		font-weight: 400;
		line-height: calc(var(--v-text-xs) + 4px);
		white-space: nowrap;
		vertical-align: middle;
	}

	.tag :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	/* the label is the tag's baseline (not the glyph's synthesized bottom edge),
	   so in a baseline row (a PropertyTable value) the tag's text sits on the
	   key's baseline and the row keeps its 30 px; in a 20 px tag with 2 px
	   padding the 16 px label line lands exactly where centring put it */
	.text {
		align-self: baseline;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		font-variant-numeric: tabular-nums;
	}

	/* round and large tags have other padding: their label stays centred */
	.round .text,
	.large .text {
		align-self: center;
	}

	.i-primary {
		background: var(--v-primary-veil);
		color: var(--v-primary-text);
	}

	.i-success {
		background: var(--v-success-veil);
		color: var(--v-success-text);
	}

	.i-warning {
		background: var(--v-warning-veil);
		color: var(--v-warning-text);
	}

	.i-danger {
		background: var(--v-danger-veil);
		color: var(--v-danger-text);
	}

	.i-ai {
		background: var(--v-ai-veil);
		color: var(--v-ai-text);
	}

	.i-primary :global([data-ui='icon']),
	.i-success :global([data-ui='icon']),
	.i-warning :global([data-ui='icon']),
	.i-danger :global([data-ui='icon']),
	.i-ai :global([data-ui='icon']) {
		color: inherit;
	}

	.round {
		justify-content: center;
		padding: 0 6px;
		border-radius: var(--v-radius-pill);
	}

	.large {
		min-height: var(--v-ctl-md);
		padding: 4px 8px;
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
	}

	.interactive {
		cursor: pointer;
	}

	.interactive:hover {
		box-shadow: inset 0 0 0 999px var(--v-neutral-veil);
	}

	.interactive:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 1px;
	}

	.x {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		margin: 0 -4px 0 -2px;
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
