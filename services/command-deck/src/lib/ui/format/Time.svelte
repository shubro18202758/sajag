<script lang="ts">
	/**
	 * Time — a moment in IST through the formatter, Inter with tabular
	 * figures (never mono). With `anchor` it is a stamp (hh:mm on the
	 * anchor's day, else "23 Oct 23:52"); with `ago` a relative age; else a
	 * clock. `suffix` appends " IST"; `fullTip` adds a tooltip with the full
	 * IST stamp. The <time> carries the ISO instant.
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import Tooltip from '../Tooltip.svelte';
	import { uiLang, ut } from '../lang';
	import { fmtAgo, fmtFull, fmtStamp, fmtTime, toMs, type Moment } from './format';

	interface Props extends HTMLAttributes<HTMLTimeElement> {
		value: Moment;
		anchor?: Moment;
		seconds?: boolean;
		ago?: boolean;
		now?: Moment;
		suffix?: boolean;
		fullTip?: boolean;
		lang?: string;
	}

	let {
		value,
		anchor = undefined,
		seconds = false,
		ago = false,
		now = undefined,
		suffix = false,
		fullTip = false,
		lang,
		class: cls = '',
		...rest
	}: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	const ms = $derived(toMs(value));
	const text = $derived(
		ago
			? fmtAgo(ms, now ?? Date.now(), L)
			: anchor !== undefined
				? fmtStamp(ms, anchor, { seconds })
				: fmtTime(ms, { seconds })
	);
	const iso = $derived(Number.isFinite(ms) ? new Date(ms).toISOString() : undefined);
</script>

{#snippet time()}
	<time data-ui="time" class={['t', cls]} datetime={iso} {...rest}
		>{text}{#if suffix && Number.isFinite(ms) && !ago}{' '}<span class="sfx">{ut(L, 'ui_time_ist')}</span>{/if}</time
	>
{/snippet}

{#if fullTip && Number.isFinite(ms)}
	<Tooltip content={fmtFull(ms)}>{@render time()}</Tooltip>
{:else}
	{@render time()}
{/if}

<style>
	.t {
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	/* the suffix recedes inside 14 px prose but never falls under the 12 px
	   operator floor in a 12 px cell, tag or meta line (SPEC §3.2) */
	.sfx {
		color: var(--v-ink-2);
		font-size: max(12px, 0.86em);
	}
</style>
