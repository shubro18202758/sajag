<script lang="ts">
	/**
	 * Plate — a registration mark (SPEC §3.3, §9.3). `inline-flex`: the mark
	 * in the identifier face, a 4 px gap, then a 12 px lock directly after a
	 * MASKED mark. Class `plate` and `data-masked` are pinned by tests, and
	 * the root's textContent is exactly the mark (the lock adds no text).
	 *
	 * Masking is the caller's job (ops.plate / plates.ts): this component
	 * renders what it is given and says honestly whether it is masked. A
	 * masked mark explains itself in a tooltip.
	 *
	 * Defence in depth: `masked` (the default) with a mark that carries no
	 * mask (•) re-masks it here (maskMark, the oracle's rule), so a lock and a
	 * "masked" tooltip can never sit beside a full mark. Pass masked={false}
	 * only for the officer-named console.
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import { ACTION_ICON } from '$lib/design/icons';
	import Icon from '../Icon.svelte';
	import Tooltip from '../Tooltip.svelte';
	import { uiLang, ut } from '../lang';
	import { isMaskedMark, maskMark } from './format';

	interface Props extends HTMLAttributes<HTMLSpanElement> {
		/** The mark as it may be shown (already masked unless an officer is named). */
		mark: string | null | undefined;
		/** True when the mark is masked (e.g. MH01XX•••7); a mark without the mask is masked here. */
		masked?: boolean;
		lang?: string;
	}

	let { mark, masked = true, lang, class: cls = '', ...rest }: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	const shown = $derived.by(() => {
		if (mark == null || mark.trim() === '') return '—';
		// a placeholder ('—') has nothing to mask; a mark without the mask is masked here
		if (!masked || isMaskedMark(mark) || !/[A-Za-z0-9]/.test(mark)) return mark;
		return maskMark(mark);
	});
</script>

{#snippet plate()}
	<span data-ui="plate" class={['plate', cls]} data-masked={masked ? 'true' : 'false'} {...rest}
		><span class="mark">{shown}</span>{#if masked}<Icon
				name={ACTION_ICON.masked}
				size={12}
				class="lock"
				title={ut(L, 'ui_masked')}
			/>{/if}</span
	>
{/snippet}

{#if masked}
	<Tooltip content={ut(L, 'ui_masked_tip')}>{@render plate()}</Tooltip>
{:else}
	{@render plate()}
{/if}

<style>
	.plate {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		white-space: nowrap;
		vertical-align: baseline;
	}

	.mark {
		font-family: var(--v-font-mono);
		font-size: max(12px, 0.9em);
		font-variant-numeric: tabular-nums;
	}

	.plate :global(.lock) {
		color: var(--v-ink-2);
	}
</style>
