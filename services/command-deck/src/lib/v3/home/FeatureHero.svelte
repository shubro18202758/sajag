<script lang="ts">
	/**
	 * FeatureHero (V3-SPEC §5.2, §6.1) — the "featured" slot, made the one thing to do now: the decision
	 * unit with the soonest deadline (model.ts pickFeatured, with the 15 s hysteresis), over the real map
	 * of its place composed so the subject sits right of the copy. Tags ("Needs you now", who proposed
	 * it, one provenance tag), the display title (the mark in a masked chip), one line of why, up to three
	 * facts (the countdown in orange, `role="timer"`, announced politely at 30 s and 10 s only), the one
	 * white button "Review now" (56 px) to the unit's home, "1 of N" pips, and the decision rule in words:
	 * "If no one answers, the current plan is kept. Nothing changes without a named officer."
	 *
	 * Nothing waiting: "Nothing needs you right now" over the all-clear city scene, and what is coming up next.
	 *
	 * V3-P7: the vehicle class's studio shot (or the kind's key art) sits over the map's top-right corner, so the
	 * featured decision shows what it is about as well as where.
	 */
	import { t } from '$lib/i18n/strings';
	import { fmtDuration } from '$lib/ui/format/format';
	import '../packs.v3';
	import Glyph from '../Glyph.svelte';
	import V3Tag from '../ui/V3Tag.svelte';
	import PlateChip from '../ui/PlateChip.svelte';
	import RedactedText from '../ui/RedactedText.svelte';
	import MapThumb from '../map/MapThumb.svelte';
	import type { LonLat } from '../map/mercator';
	import { countdownText } from './model';
	import VehicleShot from '../media/VehicleShot.svelte';
	import { sceneSrc, SCENE } from '../media/art';
	import '../media/packs.media';
	import type { DecisionVM, PlannedVM } from './view';

	let {
		vm,
		index = 1,
		total = 0,
		next = null,
		now,
		lang,
		roads = null,
	}: { vm: DecisionVM | null; index?: number; total?: number; next?: PlannedVM | null; now: number; lang: string; roads?: readonly (readonly LonLat[])[] | null } = $props();

	const leftMs = $derived(vm?.deadline != null ? vm.deadline - now : null);
	const leftText = $derived(leftMs != null ? countdownText(leftMs, lang) : null);
	const waited = $derived(vm?.since != null ? fmtDuration((now - vm.since) / 1000, lang) : null);

	// polite announcements at 30 s and 10 s only (§7.7)
	let spoken = $state('');
	let lastMark = $state<number | null>(null);
	$effect(() => {
		if (leftMs == null) return;
		const s = Math.ceil(leftMs / 1000);
		for (const mark of [30, 10]) {
			if (s <= mark && s > mark - 2 && lastMark !== mark) {
				lastMark = mark;
				spoken = `${leftText} ${t(lang, 'v3_hero_left')}`;
			}
		}
	});

	const pips = $derived(Math.min(total, 6));
</script>

<article class={['feature', !vm && 'clear']} aria-labelledby="v3-hero-title" data-testid="v3-hero" data-key={vm?.key ?? ''} data-kind={vm?.kind ?? ''}>
	{#if vm}
		<MapThumb class="art" overlay={vm.thumb.overlay} alt={vm.thumb.alt} focus={[0.74, 0.5]} maxTiles={24} markerR={17} frameOn="points" labels eager credit {roads} zoom={vm.thumb.zoom ?? 15} />
		<div class="scrim" aria-hidden="true"></div>
		{#if vm.inset}
			<div class={['hero-inset', vm.inset.kind]} data-testid="v3-hero-inset">
				{#if vm.inset.kind === 'vehicle'}<VehicleShot cls={vm.inset.cls} {lang} width={240} />{:else}<img src={vm.inset.art} alt={t(lang, 'v3i_art_alt', vm.kindLine)} width="240" height="135" loading="eager" decoding="async" />{/if}
			</div>
		{/if}
		{#key vm.key}
		<div class="copy">
			<div class="eyebrow">
				<V3Tag tone="decide" glyph="clock">{t(lang, 'v3_hero_now')}</V3Tag>
				<V3Tag tone={vm.by.ai ? 'ai' : 'neutral'} glyph={vm.by.ai ? 'spark' : vm.kind === 'dss' ? 'sliders' : 'shield'}>{vm.by.text}</V3Tag>
				{#if vm.prov}<V3Tag tone="dashed" glyph={vm.prov.glyph} title={vm.prov.title}>{vm.prov.text}</V3Tag>{/if}
			</div>
			<p class="kind">{vm.kindLine}</p>
			<h2 class="display" id="v3-hero-title">
				<span title={vm.title}>{vm.title}</span>
				{#if vm.plate}<PlateChip mark={vm.plate.mark} masked={vm.plate.masked} {lang} />{/if}
			</h2>
			<p class="why"><RedactedText text={vm.why} {lang} /></p>
			<div class="facts">
				{#if leftText != null}
					<div class="fact count">
						<b class="cd" role="timer" aria-label={`${leftText} ${t(lang, 'v3_hero_left')}`} data-testid="v3-hero-countdown">{leftText}</b>
						<span>{t(lang, 'v3_hero_left')}</span>
					</div>
				{:else if waited}
					<div class="fact count"><b class="cd">{waited}</b><span>{t(lang, 'v3_hero_waiting')}</span></div>
				{/if}
				{#each vm.facts.slice(0, 2) as f (f.label)}
					<div class="fact"><b>{f.value}</b><span>{f.label}</span></div>
				{/each}
			</div>
			<span class="sr" aria-live="polite">{spoken}</span>
			<div class="actions">
				<a class="btn-primary" href={vm.href} data-testid="v3-review-now">{t(lang, 'v3_hero_review')}<Glyph name="arrowR" size={20} /></a>
				{#if total > 1}
					<span class="stack" aria-label={t(lang, 'v3_hero_stack_aria', index, total)}>
						<span class="pips" aria-hidden="true">{#each Array(pips) as _, i (i)}<i class={[i === index - 1 && 'cur']}></i>{/each}</span>
						<span aria-hidden="true">{t(lang, 'v3_hero_stack', index, total)}</span>
					</span>
				{/if}
			</div>
			<p class="ifnot"><Glyph name="info" size={16} />{vm.ifNot}</p>
		</div>
		{/key}
	{:else}
		<img class="clear-scene" src={sceneSrc('all-clear')} alt={t(lang, 'v3i_scene_all-clear')} width={SCENE.w} height={SCENE.h} loading="eager" decoding="async" />
		<div class="scrim" aria-hidden="true"></div>
		<div class="copy">
			<div class="eyebrow"><V3Tag tone="ok" glyph="checkc">{t(lang, 'v3_hero_clear')}</V3Tag></div>
			<h2 class="display" id="v3-hero-title">{t(lang, 'v3_hero_clear')}</h2>
			<p class="why">{t(lang, 'v3_hero_clear_sub')}</p>
			{#if next}
				<a class="next" href={next.href}>
					<img src={next.art} alt="" width="56" height="56" />
					<span><small>{t(lang, 'v3_hero_next')} · {next.when}</small><b>{next.title}</b></span>
					<Glyph name="chevR" size={18} />
				</a>
			{:else}
				<p class="why">{t(lang, 'v3_hero_none_planned')}</p>
			{/if}
		</div>
	{/if}
</article>

<style>
	.feature {
		position: relative;
		display: flex;
		min-height: 340px;
		overflow: hidden;
		border-radius: var(--v3-radius-xl);
		background: var(--v3-s1);
		isolation: isolate;
	}

	.feature :global(.art) {
		position: absolute;
		inset: 0;
		z-index: 0;
	}

	.scrim {
		position: absolute;
		inset: 0;
		z-index: 1;
		pointer-events: none;
		background:
			linear-gradient(90deg, var(--v3-scrim) 0%, var(--v3-scrim-mid) 30%, var(--v3-scrim-soft) 52%, var(--v3-scrim-none) 72%),
			linear-gradient(0deg, var(--v3-scrim-soft), var(--v3-scrim-none) 35%);
	}

	.copy {
		position: relative;
		z-index: 2;
		display: flex;
		flex-direction: column;
		gap: 12px;
		max-width: 600px;
		padding: 30px 34px;
	}

	.eyebrow {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		align-items: center;
	}

	.kind {
		margin: 4px 0 -8px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 600;
	}

	.display {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 4px 14px;
		margin: 2px 0 0;
		font-size: var(--v3-text-display);
		line-height: var(--v3-lh-display);
		font-weight: 650;
	}

	.display > span {
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.display :global([data-v3='plate']) {
		font-size: 22px;
		line-height: 30px;
	}

	.why {
		max-width: 520px;
		margin: 0;
		color: var(--v3-t2);
		font-size: 16px;
		line-height: 24px;
	}

	.facts {
		display: flex;
		flex-wrap: wrap;
		gap: 10px 28px;
		margin: 6px 0 4px;
	}

	.fact {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.fact b {
		font-size: 22px;
		line-height: 28px;
		font-weight: 650;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.fact span {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.fact.count {
		flex-direction: row;
		align-items: baseline;
		gap: 6px;
	}

	.cd {
		color: var(--v3-decide-text);
		font-variant-numeric: tabular-nums;
	}

	/* the call to action follows the facts: the hero stretches to the pulse column's height (often past the fold),
	   and a button pinned to its bottom edge would sit below the first screen */
	.actions {
		display: flex;
		align-items: center;
		gap: 16px;
		padding-top: 10px;
	}

	.btn-primary {
		display: inline-flex;
		align-items: center;
		gap: 10px;
		height: var(--v3-ctl-xl);
		padding: 0 28px;
		border-radius: 28px;
		background: var(--v3-primary-bg);
		color: var(--v3-primary-ink);
		font-size: 17px;
		font-weight: 650;
		text-decoration: none;
		white-space: nowrap;
		transition:
			background var(--v3-dur-1),
			transform var(--v3-dur-1);
	}

	.btn-primary:hover {
		background: var(--v3-primary-hover);
	}

	.btn-primary:active {
		transform: scale(0.98);
	}

	.btn-primary:focus-visible,
	.next:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 3px;
	}

	.stack {
		display: flex;
		align-items: center;
		gap: 8px;
		color: var(--v3-t2);
		font-size: 14px;
		font-weight: 600;
	}

	.pips {
		display: flex;
		gap: 4px;
	}

	.pips i {
		width: 22px;
		height: 4px;
		border-radius: 2px;
		background: var(--v3-s4);
	}

	.pips i.cur {
		background: var(--v3-decide);
	}

	.ifnot {
		display: flex;
		gap: 8px;
		align-items: flex-start;
		max-width: 500px;
		margin: 0;
		color: var(--v3-t2);
		font-size: 14px;
		line-height: 22px;
	}

	.ifnot :global(.v3-glyph) {
		margin-top: 3px;
		color: var(--v3-t3);
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}

	.clear .copy {
		justify-content: center;
	}

	.clear-scene {
		position: absolute;
		inset: 0;
		z-index: 0;
		width: 100%;
		height: 100%;
		object-fit: cover;
		object-position: 70% 50%;
	}

	.hero-inset {
		position: absolute;
		top: 20px;
		right: 20px;
		z-index: 2;
		display: grid;
		place-items: center;
		width: clamp(170px, 24%, 260px);
		aspect-ratio: 16 / 10;
		overflow: hidden;
		border: 1px solid var(--v3-glass-border);
		border-radius: var(--v3-radius-l);
		background: var(--v3-glass-bg);
		-webkit-backdrop-filter: var(--v3-glass-blur);
		backdrop-filter: var(--v3-glass-blur);
		box-shadow: var(--v3-elev-2);
		pointer-events: none;
	}

	.hero-inset :global(.shot),
	.hero-inset img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.hero-inset.vehicle :global(.shot) {
		object-fit: contain;
	}

	.next {
		display: flex;
		align-items: center;
		gap: 14px;
		max-width: 460px;
		padding: 12px 16px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s2);
		color: var(--v3-t1);
		text-decoration: none;
	}

	.next img {
		border-radius: var(--v3-radius-m);
	}

	.next span {
		display: flex;
		flex: 1;
		flex-direction: column;
	}

	.next small {
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-weight: 600;
	}

	@media (max-width: 1500px) {
		.copy {
			max-width: 520px;
			padding: 26px 28px;
		}

		.facts {
			gap: 10px 22px;
		}
	}

	/* a phone: the place on top (the satellite and its marker, never under the words), the copy below; no inset picture */
	@media (max-width: 720px) {
		.feature {
			min-height: 0;
		}

		.feature:not(.clear) {
			flex-direction: column;
		}

		.feature:not(.clear) :global(.art) {
			position: relative;
			inset: auto;
			flex: none;
			height: 176px;
		}

		.feature:not(.clear) .scrim {
			inset: 0 0 auto;
			height: 176px;
			background: linear-gradient(0deg, var(--v3-s1) 0%, var(--v3-scrim-none) 45%);
		}

		.copy {
			padding: 20px 18px;
		}

		.display {
			font-size: 26px;
			line-height: 34px;
		}

		.hero-inset {
			display: none;
		}

		.actions {
			flex-wrap: wrap;
		}
	}

	/* the featured decision (and the next one, when the stack moves) enters softly: 200 ms, a fade and a small rise */
	.copy,
	.hero-inset {
		animation: v3h-enter 200ms var(--v3-ease) both;
	}

	@keyframes v3h-enter {
		from {
			opacity: 0;
			transform: translateY(6px);
		}
		to {
			opacity: 1;
			transform: none;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.btn-primary {
			transition: none;
		}

		.copy,
		.hero-inset {
			animation: none;
		}
	}
</style>
