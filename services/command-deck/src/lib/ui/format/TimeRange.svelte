<script lang="ts">
	/**
	 * TimeRange — a window at one precision: "01:20–01:42" on the anchor's
	 * IST day, else "23 Oct 23:52–00:04"; an open range is one stamp.
	 * Inter, tabular figures; `suffix` appends " IST".
	 */
	import type { HTMLAttributes } from 'svelte/elements';
	import { uiLang, ut } from '../lang';
	import { fmtRange, type Moment } from './format';

	interface Props extends HTMLAttributes<HTMLSpanElement> {
		start: Moment;
		end?: Moment;
		anchor?: Moment;
		suffix?: boolean;
		lang?: string;
	}

	let { start, end = null, anchor = undefined, suffix = false, lang, class: cls = '', ...rest }: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	const text = $derived(fmtRange(start, end, anchor ?? Date.now()));
</script>

<span data-ui="time-range" class={['tr', cls]} {...rest}
	>{text}{#if suffix}{' '}<span class="sfx">{ut(L, 'ui_time_ist')}</span>{/if}</span
>

<style>
	.tr {
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	/* never under the 12 px operator floor (SPEC §3.2), as in Time */
	.sfx {
		color: var(--v-ink-2);
		font-size: max(12px, 0.86em);
	}
</style>
