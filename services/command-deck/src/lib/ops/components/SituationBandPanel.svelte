<script lang="ts">
	/**
	 * City band (SPEC §6.3 col 3, §5.3; ownership UI-S5B): the city's posture
	 * now — the one `band-masthead` of the wall: "Now · Green · since 03:12",
	 * BLACK with its hairline, the simulated-feed glyph when the band is
	 * computed on a simulated feed, "Unknown" (never a guessed Green) while
	 * the engine poll fails — and the band over the chosen range as a step
	 * chart on the ladder (BandHistoryChart).
	 *
	 * The chart is the city band as this console saw it (its entry time, then
	 * every change; nothing is drawn before the first known reading). The band
	 * row speaks for the band's subject (the store's rule, unchanged): the
	 * selected event's own situation log when it has one, else the city band. `band-row` carries the committed band
	 * (`data-band`, UNKNOWN when none), `band-held` the time it has held
	 * since its last commit (the log's transitioned flag), and
	 * `band-candidate` a reading awaiting hysteresis confirmation as a
	 * hollow chip with its tick count (ops.bandCandidate, never recomputed).
	 */
	import { untrack } from 'svelte';
	import BandChip from '$lib/primitives/BandChip.svelte';
	import { ACTION_ICON } from '$lib/design/icons';
	import { Icon, Section, Tooltip } from '$lib/ui';
	import { fmtDuration, fmtTime } from '$lib/ui/format/format';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';
	import { ops } from '$lib/ops/store.svelte';
	import { displayTitle } from '$lib/workspace/display';
	import BandHistoryChart from '$lib/decisions/wall/BandHistoryChart.svelte';
	import Age from '$lib/decisions/wall/Age.svelte';
	import { wallData } from '$lib/decisions/wall/wall-data.svelte';
	import type { BandCode } from '$lib/ops/types';

	interface Props {
		/** The wall's range: the chart's time axis. */
		window: readonly [number, number];
	}

	let { window: range }: Props = $props();

	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	let clock = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (clock = Date.now()), 1000);
		return () => clearInterval(id);
	});

	/** The city band now (the masthead): the adaptive city band, else the subject's when no city doc answered. */
	const city = $derived(ops.cityBand);
	const nowBand = $derived<BandCode | null>(city ? (city.stale ? null : city.band) : ops.bandSourceKind === 'city-band' ? ops.band : null);
	const nowSince = $derived(city && !city.stale ? city.since : null);
	const nowSimulated = $derived(city?.simulatedFeed === true);
	const staleTip = $derived(city?.stale ? ops.bandSource : null);

	/** The chart: the city band as this console saw it (its entry time, then every change). */
	$effect(() => {
		const band = nowBand;
		const since = nowSince;
		untrack(() => wallData.noteCityBand(band, since));
	});
	const readings = $derived(wallData.cityBandSeries);
	const current = $derived(nowBand ? { band: nowBand, since: nowSince } : null);

	/** The band row's subject (the store's rule): the selected event's own log, else the city. */
	const scopeEvent = $derived(ops.bandSourceKind === 'situation_log' ? ops.selectedEvent : null);
	const scope = $derived(scopeEvent ? displayTitle(ops.text(scopeEvent.name), lang) : L('wall_band_scope_city'));
	const candidate = $derived(ops.bandCandidate);
</script>

{#snippet right()}
	<Age at={ops.bandPolledAt || null} {lang} />
	<Tooltip content={staleTip ?? (nowSimulated ? L('wall_band_simulated_tip') : null)}>
		<span class="masthead" data-prim="band-masthead" data-band={nowBand ?? 'UNKNOWN'}>
			<span class="k">{L('wall_band_now')}</span>
			<span class="v">
				{#if nowBand}
					<BandChip band={nowBand} size="sm" {lang} />
					{#if nowSince}<span class="since">{L('wall_band_since', fmtTime(nowSince))}</span>{/if}
				{:else}
					<span class="unknown">{L('wall_band_unknown')}</span>
				{/if}
				{#if nowSimulated}<Icon name={ACTION_ICON.simulated} size={12} />{/if}
			</span>
		</span>
	</Tooltip>
{/snippet}

<Section title={L('wall_band')} icon="timeline-area-chart" level={2} {right} data-prim="panel" data-wall="city-band">
	<div class="body">
		<BandHistoryChart {readings} window={range} {current} {lang} scope={L('wall_band_scope_city')} />
		<div class="band-row" data-testid="band-row" data-band={ops.band ?? 'UNKNOWN'}>
			<span class="scope" title={scope}>{scope}</span>
			{#if ops.band}
				<BandChip band={ops.band as BandCode} size="sm" {lang} />
			{:else}
				<span class="unknown" data-testid="band-unknown-why" title={ops.bandStaleSince != null ? ops.bandSource : undefined}>{L('wall_band_unknown')}</span>
			{/if}
			{#if ops.bandCommittedAt}
				<span class="held" data-testid="band-held">{L('wall_band_held', fmtDuration((clock - ops.bandCommittedAt) / 1000, lang), fmtTime(ops.bandCommittedAt))}</span>
			{:else if ops.band && ops.bandSourceKind === 'situation_log'}
				<span class="held">{L('wall_band_held_window')}</span>
			{/if}
			{#if candidate}
				<Tooltip content={L('wall_band_candidate_tip')}>
					<span class="cand" data-testid="band-candidate">
						<BandChip band={candidate.band as BandCode} hollow size="sm" {lang} />
						<span class="tn">{L('wall_band_candidate', candidate.ticks, candidate.required)}</span>
					</span>
				</Tooltip>
			{/if}
		</div>
	</div>
</Section>

<style>
	.body {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 10px 12px 10px 16px;
	}

	.masthead {
		display: inline-flex;
		align-items: stretch;
		min-height: 20px;
		overflow: hidden;
		border-radius: var(--v-radius-chip);
		font-size: var(--v-text-xs);
		line-height: 16px;
		white-space: nowrap;
	}

	.masthead .k {
		display: inline-flex;
		align-items: center;
		padding: 2px 6px;
		background: var(--v-minimal-active);
		color: var(--v-ink-2);
	}

	.masthead .v {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 0 6px 0 2px;
		background: var(--v-neutral-veil);
		color: var(--v-ink-1);
	}

	.masthead .v :global([data-prim='band-chip']) {
		background: transparent;
	}

	.masthead :global([data-ui='icon']) {
		color: var(--v-ink-2);
	}

	.since {
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
	}

	.unknown {
		padding: 0 4px;
		color: var(--v-ink-2);
	}

	.band-row {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 6px 10px;
		min-width: 0;
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.scope {
		max-width: 46%;
		overflow: hidden;
		color: var(--v-ink-2);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.held {
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
	}

	.cand {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		color: var(--v-ink-2);
	}

	.tn {
		font-variant-numeric: tabular-nums;
	}
</style>
