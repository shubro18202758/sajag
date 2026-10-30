<script lang="ts">
	/**
	 * The navbar band tag (SPEC §5.3): a compound tag "Band | Green" with the
	 * band's swatch. `data-testid="band-tag"`, `data-band` (the code, or
	 * 'pending' while no page reports one: the hollow "Band —" tag, never a
	 * guessed GREEN) and `data-age-sec`, the seconds since the band's newest
	 * reading. The age ticks at 1 Hz from the value the page supplied; it is
	 * absent while the page supplies none (a legacy page's own age chip is then
	 * the only `[data-age-sec]` band clock on screen).
	 *
	 * Colours are the band ladder's (SPEC §2.4): BLACK is a dark fill with a
	 * hairline, everywhere. A `random` glyph marks a band computed on a
	 * simulated feed. The key's word (`.kt`) is what the navbar folds to its
	 * glyph when the bar is short of width; the value never folds.
	 */
	import type { Band } from '$lib/design/tokens';
	import { t } from '$lib/i18n/strings';
	import { DASHBOARD_ICON, SIMULATED_ICON } from './icons';
	import Icon from '$lib/ui/Icon.svelte';
	import Tooltip from '$lib/ui/Tooltip.svelte';
	import { fmtDuration } from '$lib/ui/format/format';
	import { shellClock, useShellClock } from './clock.svelte';

	interface Props {
		band: Band | null;
		bandSource: string | null;
		bandAgeSec: number | null;
		lang: string;
	}

	let { band, bandSource, bandAgeSec, lang }: Props = $props();

	// The age the page supplied, and when: the tag adds the seconds since.
	let base = $state<{ age: number; at: number } | null>(null);
	$effect(() => {
		const a = bandAgeSec;
		base = a == null || !Number.isFinite(a) ? null : { age: Math.max(0, Math.round(a)), at: Date.now() };
	});
	$effect(() => {
		if (!base) return;
		return useShellClock();
	});
	const age = $derived(base ? base.age + Math.max(0, Math.floor((shellClock.now - base.at) / 1000)) : null);

	const simulated = $derived(!!bandSource && /simulated/i.test(bandSource));
	const word = $derived(band ? t(lang, `shell_band_word_${band}`) : '—');
	const tip = $derived.by(() => {
		if (!band) return t(lang, 'shell_band_none');
		const parts: string[] = [];
		if (age != null) parts.push(t(lang, 'shell_band_age', fmtDuration(age, lang)));
		if (bandSource) parts.push(t(lang, 'shell_band_source', bandSource));
		if (simulated) parts.push(t(lang, 'shell_band_simulated'));
		return parts.join('. ');
	});
</script>

<Tooltip content={tip} placement="bottom">
	<span
		class="band-tag"
		class:pending={!band}
		data-testid="band-tag"
		data-band={band ?? 'pending'}
		data-age-sec={band && age != null ? age : undefined}
	>
		<span class="k"><Icon name={DASHBOARD_ICON} size={12} /><span class="kt">{t(lang, 'shell_band')}</span></span>
		<span class="v">
			{#if band}<i class="sw b-{band}" aria-hidden="true"></i>{/if}
			<span class="w">{word}</span>
			{#if simulated}<Icon name={SIMULATED_ICON} size={12} />{/if}
		</span>
	</span>
</Tooltip>

<style>
	.band-tag {
		display: inline-flex;
		flex: 0 0 auto;
		align-items: stretch;
		min-height: var(--v-ws-tag);
		overflow: hidden;
		border-radius: var(--v-radius-chip);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
		white-space: nowrap;
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
		background: color-mix(in srgb, var(--v-neutral-veil) 55%, transparent);
		color: var(--v-ink-1);
		font-variant-numeric: tabular-nums;
	}

	.band-tag :global([data-ui='icon']) {
		color: inherit;
	}

	/* the hollow tag: no band reported — an outline, never a guessed colour */
	.pending .k,
	.pending .v {
		background: transparent;
		box-shadow: inset 0 0 0 1px var(--v-line-2);
	}

	.pending .k {
		box-shadow:
			inset 1px 0 0 var(--v-line-2),
			inset 0 1px 0 var(--v-line-2),
			inset 0 -1px 0 var(--v-line-2);
	}

	.pending .v {
		color: var(--v-ink-2);
	}

	.sw {
		display: inline-block;
		width: 10px;
		height: 10px;
		border-radius: 2px;
		flex: 0 0 auto;
	}

	.b-GREEN {
		background: var(--v-band-green);
	}

	.b-AMBER {
		background: var(--v-band-amber);
	}

	.b-RED {
		background: var(--v-band-red);
	}

	/* BLACK: a dark fill with a 1 px red hairline, everywhere a band is drawn */
	.b-BLACK {
		background: var(--v-band-black-fill);
		box-shadow: inset 0 0 0 1px var(--v-band-black-hairline);
	}
</style>
