<script lang="ts">
	/**
	 * BandMasthead — the city's posture in one line (SPEC §5.2), rebuilt on
	 * the tokens of src/lib/ui: the band's swatch and word ("Amber"), the
	 * one-sentence posture in ink-2, and — during hysteresis — the candidate
	 * band as a hollow BandChip beside its dwell count. A band change commits
	 * with the 600 ms wipe (the reduced-motion block turns it into a static
	 * change). Below the line runs the `.hairline`; BLACK draws it in the
	 * band's red and alone breathes on it (--v-dur-breathe; static without
	 * motion). `data-prim="band-masthead"` and `data-band` stay on the root.
	 */
	import type { Band } from '$lib/design/tokens';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import { uiLang } from '$lib/ui/lang';
	import BandChip from './BandChip.svelte';

	interface Props {
		band: Band | null;
		/** One sentence, e.g. 'Amber: visarjan corridor active, 1 pursuit'. */
		posture?: string;
		/** Hysteresis candidate: { band, ticks, required } — hollow chip + count. */
		candidate?: { band: Band; ticks: number; required: number } | null;
		bandSource?: string | null;
		lang?: string;
	}

	let { band, posture = '', candidate = null, bandSource = null, lang }: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());
	const word = $derived(band ? t(L, `shell_band_word_${band}`) : '—');
</script>

<header class="masthead" data-prim="band-masthead" data-band={band ?? 'none'}>
	<div class="line">
		{#key band}
			<span class="band-word bw-{band ?? 'none'}">
				<span class="wipe" aria-hidden="true"></span>
				<i class="sw" aria-hidden="true"></i>
				<span class="w">{word}</span>
			</span>
		{/key}
		<span class="posture">{posture || t(L, 'masthead_posture_none')}</span>
		<span class="spacer"></span>
		{#if candidate}
			<span class="dwell" title={t(L, 'masthead_dwell_hint')}>
				<BandChip band={candidate.band} hollow size="sm" lang={L} />
				<span class="dwell-count"
					>{t(L, 'masthead_held')} · {t(L, 'masthead_tick')} {candidate.ticks}/{candidate.required}</span
				>
			</span>
		{/if}
		{#if bandSource}<span class="source">{bandSource}</span>{/if}
	</div>
	<div class="hairline" class:breathing={band === 'BLACK'} aria-hidden="true"></div>
</header>

<style>
	.masthead {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 12px 16px;
		background: var(--v-surface-1);
		border-radius: var(--v-radius-panel);
		box-shadow: var(--v-elev-0);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.line {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px 12px;
		min-width: 0;
	}

	.band-word {
		position: relative;
		display: inline-flex;
		align-items: center;
		gap: 8px;
		font-size: var(--v-text-lg);
		font-weight: 600;
		line-height: 24px;
	}

	.sw {
		display: inline-block;
		width: 12px;
		height: 12px;
		border-radius: 2px;
		background: var(--v-ink-4);
	}

	.bw-GREEN .sw {
		background: var(--v-band-green);
	}

	.bw-AMBER .sw {
		background: var(--v-band-amber);
	}

	.bw-RED .sw {
		background: var(--v-band-red);
	}

	/* BLACK: a dark fill with a 1 px red hairline */
	.bw-BLACK .sw {
		background: var(--v-band-black-fill);
		box-shadow: inset 0 0 0 1px var(--v-band-black-hairline);
	}

	.bw-none {
		color: var(--v-ink-2);
	}

	.bw-none .sw {
		background: transparent;
		box-shadow: inset 0 0 0 1px var(--v-line-strong);
	}

	/* the 600 ms commit wipe — replays on every band change ({#key}) */
	.wipe {
		position: absolute;
		inset: -2px -4px;
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		transform-origin: left;
		animation: wipe var(--v-dur-wipe) var(--v-ease) 1 forwards;
		pointer-events: none;
	}

	@keyframes wipe {
		from {
			transform: scaleX(1);
		}
		to {
			transform: scaleX(0);
		}
	}

	.posture {
		min-width: 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-base);
	}

	.spacer {
		flex: 1;
	}

	.dwell {
		display: inline-flex;
		align-items: center;
		gap: 8px;
	}

	.dwell-count,
	.source {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-variant-numeric: tabular-nums;
	}

	/* the masthead hairline; BLACK breathes on it (the deck's only breathing element) */
	.hairline {
		height: 1px;
		background: var(--v-line-1);
	}

	.breathing {
		background: var(--v-band-black-hairline);
		animation: breathe var(--v-dur-breathe) var(--v-ease) infinite;
	}

	@keyframes breathe {
		0%,
		100% {
			opacity: 0.25;
		}
		50% {
			opacity: 1;
		}
	}

	/* reduced motion: the wipe becomes a static change, the hairline static */
	@media (prefers-reduced-motion: reduce) {
		.wipe {
			animation: none;
			opacity: 0;
		}

		.breathing {
			animation: none;
			opacity: 0.6;
		}
	}
</style>
