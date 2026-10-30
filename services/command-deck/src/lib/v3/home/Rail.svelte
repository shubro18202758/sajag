<script lang="ts">
	/**
	 * Rail (V3-SPEC §5.2, §7.7) — a titled, horizontally scrolling list of cards: title, count (orange when
	 * it counts decisions), a sub-line, a "see all" link, scroll buttons, snap scrolling that peeks the
	 * next card. A `<section aria-labelledby>` holding a list; ← / → move focus card to card (roving),
	 * Home / End jump to the ends. The page renders the `<li>` items.
	 */
	import type { Snippet } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import '../packs.v3';
	import Glyph from '../Glyph.svelte';

	let {
		id,
		title,
		count = null,
		decide = false,
		sub = null,
		more = null,
		lang,
		empty = null,
		children,
	}: {
		id: string;
		title: string;
		count?: number | null;
		decide?: boolean;
		sub?: string | null;
		more?: { href: string; text: string; glyph?: string } | null;
		lang: string;
		empty?: string | null;
		children?: Snippet;
	} = $props();

	let track = $state<HTMLUListElement | null>(null);
	let atStart = $state(true);
	let atEnd = $state(true);

	function measure() {
		const el = track;
		if (!el) return;
		atStart = el.scrollLeft <= 2;
		atEnd = el.scrollLeft + el.clientWidth >= el.scrollWidth - 2;
	}

	/** The officer scrolled this rail (wheel, drag, keys, the arrows): a reorder then leaves it where it is. */
	let touched = false;

	$effect(() => {
		const el = track;
		if (!el) return;
		measure();
		const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
		ro?.observe(el);
		// CSS scroll snap follows the element it last snapped to: when the list reorders (a new soonest
		// deadline moves to the front) the browser would scroll after the old first card. An untouched rail
		// stays at its start, soonest first.
		const mo =
			typeof MutationObserver !== 'undefined'
				? new MutationObserver(() => {
						if (!touched && el.scrollLeft !== 0) el.scrollLeft = 0;
						measure();
					})
				: null;
		mo?.observe(el, { childList: true });
		const touch = () => (touched = true);
		el.addEventListener('wheel', touch, { passive: true });
		el.addEventListener('pointerdown', touch, { passive: true });
		el.addEventListener('keydown', touch);
		return () => {
			ro?.disconnect();
			mo?.disconnect();
			el.removeEventListener('wheel', touch);
			el.removeEventListener('pointerdown', touch);
			el.removeEventListener('keydown', touch);
		};
	});

	function page(dir: 1 | -1) {
		const el = track;
		if (!el) return;
		touched = true;
		el.scrollBy({ left: dir * el.clientWidth * 0.9, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
	}

	function onKey(e: KeyboardEvent) {
		if (!track || !['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(e.key)) return;
		const cards = [...track.querySelectorAll<HTMLElement>(':scope > li > a, :scope > li > [data-card]')];
		const at = cards.findIndex((c) => c === document.activeElement || c.contains(document.activeElement));
		if (at < 0) return;
		const next = e.key === 'Home' ? 0 : e.key === 'End' ? cards.length - 1 : Math.max(0, Math.min(cards.length - 1, at + (e.key === 'ArrowRight' ? 1 : -1)));
		e.preventDefault();
		cards[next]?.focus();
		cards[next]?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
	}
</script>

<section class="rail-sec" aria-labelledby="{id}-h" data-v3-rail={id}>
	<div class="rail-head">
		<h2 class="h" id="{id}-h">{title}</h2>
		{#if count != null}<span class={['count', decide && count > 0 && 'decide']} data-v3-count={count}>{count}</span>{/if}
		{#if sub}<span class="sub">{sub}</span>{/if}
		<span class="grow"></span>
		{#if more}<a class="more" href={more.href}>{#if more.glyph}<Glyph name={more.glyph} size={16} />{/if}{more.text}{#if !more.glyph}<Glyph name="chevR" size={16} />{/if}</a>{/if}
		{#if !(atStart && atEnd)}
			<span class="arrows">
				<button type="button" aria-label={t(lang, 'v3_rail_prev')} disabled={atStart} onclick={() => page(-1)}><Glyph name="chevL" size={18} /></button>
				<button type="button" aria-label={t(lang, 'v3_rail_next')} disabled={atEnd} onclick={() => page(1)}><Glyph name="chevR" size={18} /></button>
			</span>
		{/if}
	</div>
	{#if empty}
		<p class="empty">{empty}</p>
	{:else}
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions (the list delegates ← / → / Home / End to its card links: roving focus, §7.7) -->
		<ul class="track" bind:this={track} onscroll={measure} onkeydown={onKey}>
			{@render children?.()}
		</ul>
	{/if}
</section>

<style>
	.rail-sec {
		display: flex;
		flex-direction: column;
		gap: 14px;
		min-width: 0;
	}

	.rail-head {
		display: flex;
		align-items: baseline;
		gap: 12px;
		min-width: 0;
	}

	.h {
		margin: 0;
		font-size: var(--v3-text-heading);
		line-height: var(--v3-lh-heading);
		font-weight: 640;
		white-space: nowrap;
	}

	.count {
		color: var(--v3-t2);
		font-size: var(--v3-text-body);
		font-weight: 700;
	}

	.count.decide {
		color: var(--v3-decide-text);
	}

	.sub {
		min-width: 0;
		overflow: hidden;
		color: var(--v3-t3);
		font-size: 14px;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.grow {
		flex: 1;
	}

	.more {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		flex: none;
		color: var(--v3-brand-text);
		font-size: var(--v3-text-body);
		font-weight: 600;
		text-decoration: none;
		white-space: nowrap;
	}

	.more:hover {
		text-decoration: underline;
	}

	.arrows {
		display: inline-flex;
		gap: 6px;
		align-self: center;
		flex: none;
	}

	.arrows button {
		display: grid;
		place-items: center;
		width: 34px;
		height: 34px;
		border: 0;
		border-radius: 17px;
		background: var(--v3-s2);
		color: var(--v3-t2);
		cursor: pointer;
	}

	.arrows button:hover:not(:disabled) {
		background: var(--v3-s3);
		color: var(--v3-t1);
	}

	.arrows button:disabled {
		opacity: 0.4;
		cursor: default;
	}

	.track {
		display: grid;
		grid-auto-flow: column;
		grid-auto-columns: calc((100% - 3 * 18px) / 4.15);
		gap: 18px;
		margin: -4px 0 0;
		padding: 4px 2px 8px;
		scroll-padding-inline: 2px;
		list-style: none;
		overflow-x: auto;
		scroll-snap-type: x mandatory;
		scrollbar-width: none;
	}

	.track::-webkit-scrollbar {
		display: none;
	}

	.track > :global(li) {
		display: flex;
		min-width: 0;
		scroll-snap-align: start;
	}

	.empty {
		margin: 0;
		padding: 18px 20px;
		border: 1px dashed var(--v3-line-2);
		border-radius: var(--v3-radius-l);
		color: var(--v3-t2);
	}

	.more:focus-visible,
	.arrows button:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	@media (max-width: 1500px) {
		.track {
			grid-auto-columns: calc((100% - 2 * 16px) / 3.2);
			gap: 16px;
		}
	}
</style>
