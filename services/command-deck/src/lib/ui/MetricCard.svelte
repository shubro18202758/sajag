<script lang="ts">
	/**
	 * MetricCard — one key figure (the metric strip, the inspector's
	 * metrics): a 12 px caption, the value in 18/24 600 tabular (22/28 with
	 * `large`), a unit, a 12 px sub line and an optional sparkline. A zero
	 * value recedes to ink-2 at weight 400 (SPEC §3.2), whatever the intent,
	 * so the eye goes to what is non-zero: "Decisions waiting 0" is never
	 * orange. `intent="warning"` is for "decisions waiting" only. The caption
	 * and the sub line ellipsise on one line.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import { uiLang, ut } from './lang';
	import type { Intent } from './types';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		caption: string;
		value: number | string | null | undefined;
		unit?: string | null;
		sub?: string | Snippet | null;
		intent?: Intent;
		spark?: readonly number[] | null;
		large?: boolean;
		/** Force (or forbid) the receding zero style; by default value === 0. */
		zero?: boolean;
		lang?: string;
	}

	let {
		caption,
		value,
		unit = null,
		sub = null,
		intent = 'none',
		spark = null,
		large = false,
		zero = undefined,
		lang,
		class: cls = '',
		...rest
	}: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	const isZero = $derived(zero ?? (value === 0 || value === '0'));
	const W = 64;
	const H = 24;
	const path = $derived.by(() => {
		const pts = (spark ?? []).filter((v) => Number.isFinite(v));
		if (pts.length < 2) return null;
		const min = Math.min(...pts);
		const max = Math.max(...pts);
		const span = max - min || 1;
		const xy = pts.map((v, i) => [(i / (pts.length - 1)) * W, H - 2 - ((v - min) / span) * (H - 4)] as const);
		const line = xy.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
		return { line, area: `${line} L${W} ${H} L0 ${H} Z` };
	});
</script>

<div
	data-ui="metric-card"
	data-zero={isZero ? 'true' : undefined}
	class={['mc', large && 'large', isZero && 'zero', intent !== 'none' && `i-${intent}`, path && 'has-spark', cls]}
	{...rest}
>
	<div class="cap">{caption}</div>
	<div class="val">{value ?? '—'}{#if unit}<span class="u">{unit}</span>{/if}</div>
	{#if sub}
		<!-- the text sits in its own span: an ellipsis needs a block box, and .sub is a flex row (glyphs in a snippet) -->
		<div class="sub"><span class="st">{#if typeof sub === 'function'}{@render sub()}{:else}{sub}{/if}</span></div>
	{/if}
	{#if path}
		<svg class="spark" width={W} height={H} viewBox="0 0 {W} {H}" role="img" aria-label={ut(L, 'ui_trend')}>
			<path class="area" d={path.area} />
			<path class="line" d={path.line} />
		</svg>
	{/if}
</div>

<style>
	.mc {
		position: relative;
		min-width: 0;
		padding: 8px 12px 8px 16px;
		overflow: hidden;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.cap,
	.sub {
		overflow: hidden;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.sub {
		display: flex;
		align-items: center;
		gap: 4px;
	}

	.st {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.val {
		font-size: var(--v-text-lg);
		font-weight: 600;
		line-height: calc(var(--v-text-lg) + 6px);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.large .val {
		font-size: var(--v-text-xl);
		line-height: calc(var(--v-text-xl) + 6px);
	}

	.u {
		margin-left: 4px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-weight: 400;
	}

	.i-warning .val {
		color: var(--v-warning-text);
	}

	.i-danger .val {
		color: var(--v-danger-text);
	}

	.i-success .val {
		color: var(--v-success-text);
	}

	.i-primary .val {
		color: var(--v-primary-text);
	}

	/* a zero recedes whatever the intent: after the intent rules and one class
	   more specific, so "Decisions waiting 0" is ink-2 at 400, never orange */
	.mc.zero .val {
		color: var(--v-ink-2);
		font-weight: 400;
	}

	.has-spark .val {
		padding-right: 72px;
	}

	.spark {
		position: absolute;
		top: 24px;
		right: 12px;
	}

	.spark .line {
		fill: none;
		stroke: var(--v-ink-2);
		stroke-width: 1.25;
		stroke-linejoin: round;
	}

	.spark .area {
		fill: var(--v-neutral-veil);
		stroke: none;
	}
</style>
