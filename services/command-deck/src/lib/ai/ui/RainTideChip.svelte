<script lang="ts">
	/**
	 * Rain · Tide (the map's chip): what the waterlogging nowcast stands on, each part labelled —
	 *
	 *   rain   the city-mean Open-Meteo nowcast now and the next hour (Live: a model nowcast, not a gauge)
	 *   tide   the Arabian Sea level at Apollo Bunder, rising or falling, the outfall gates and the next high water (Modelled)
	 *   pumps  BMC storm-water pumping stations available (Emulated: the pump adapter stand-in)
	 *   risk   roads at risk within 2 hours (Modelled)
	 *
	 * and the way into the 18–19 Aug 2025 replay on the map: hindsight, IMD's observed rain through the same ponding
	 * model, a few moments of that night to step through, and "Back to live". A feed that does not answer says so —
	 * never a zero. Each row's honest label is a quiet word at its end (ProvWord), not a chip per row.
	 */
	import { t } from '$lib/i18n/strings';
	import { fmtTime } from '$lib/ui/format/format';
	import Glyph from '$lib/v3/Glyph.svelte';
	import ProvTag from './ProvTag.svelte';
	import ProvWord from './ProvWord.svelte';
	import { rainNextHour, rainNow, riskCounts, tideState } from '../model';
	import type { HydroNowcast, HydroRain, HydroTide } from '../types';
	import '../packs.ai';

	let {
		lang,
		now,
		nowcast,
		tide,
		rain,
		hydroDown = false,
		tideDown = false,
		hindsightOn = false,
		steps = [],
		at = null,
		counts = null,
		replayBusy = false,
		replayFailed = false,
		onhindsight,
		onstep,
	}: {
		lang: string;
		now: number;
		nowcast: HydroNowcast | null;
		tide: HydroTide | null;
		rain: HydroRain | null;
		hydroDown?: boolean;
		tideDown?: boolean;
		hindsightOn?: boolean;
		steps?: readonly number[];
		at?: number | null;
		counts?: { deep: number; impassable: number } | null;
		replayBusy?: boolean;
		replayFailed?: boolean;
		onhindsight: (on: boolean) => void;
		onstep: (at: number) => void;
	} = $props();

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
	const n1 = (v: number) => v.toFixed(1);

	const mmNow = $derived(rainNow(rain, now));
	const mmNext = $derived(rainNextHour(rain, now));
	const td = $derived(tideState(tide, now));
	const risk = $derived(riskCounts(nowcast));
	const atRisk = $derived(risk ? risk.shallow + risk.deep + risk.impassable : null);
	const pumps = $derived.by(() => {
		const seen = new Map<string, { a: number; t: number }>();
		for (const s of nowcast?.segments ?? []) {
			const p = s.drivers?.pumps;
			if (p?.station && typeof p.pumps_total === 'number') seen.set(p.station, { a: p.pumps_available ?? 0, t: p.pumps_total });
		}
		if (!seen.size) return null;
		let a = 0;
		let tt = 0;
		for (const v of seen.values()) {
			a += v.a;
			tt += v.t;
		}
		return { a, t: tt };
	});
</script>

<section class="rt v3-glass" aria-label={L('ai_rt_aria')} data-testid="ai-rain-tide" data-hindsight={hindsightOn ? 'on' : 'off'} data-ge-keepout>
	{#if hindsightOn}
		<div class="hs-head">
			<Glyph name="history" size={17} />
			<b>{L('ai_rt_hs_title')}</b>
			<ProvTag prov="hindsight" {lang} />
		</div>
		<p class="note">{L('ai_rt_hs_note')}</p>
		{#if steps.length}
			<div class="steps" role="group" aria-label={L('ai_rt_hs_step')}>
				{#each steps as s (s)}
					<button type="button" class={['st', at === s && 'is-pressed']} aria-pressed={at === s} data-testid="ai-hs-step" onclick={() => onstep(s)}>{fmtTime(s)}</button>
				{/each}
			</div>
		{/if}
		{#if at != null && counts}
			<p class="line" data-testid="ai-hs-counts"><span class="sw c3" aria-hidden="true"></span>{L('ai_rt_hs_at', fmtTime(at))}: <b>{L('ai_rt_hs_counts', counts.deep, counts.impassable)}</b></p>
		{/if}
		<button type="button" class="go" data-testid="ai-hs-live" onclick={() => onhindsight(false)}><Glyph name="arrowL" size={16} />{L('ai_rt_live')}</button>
	{:else}
		<div class="grid">
			<span class="k"><Glyph name="wave" size={16} /></span>
			<span class="v" data-testid="ai-rain">
				{#if mmNow != null}<b>{L('ai_rt_rain', n1(mmNow))}</b>{#if mmNext != null}<span class="dim"> · {L('ai_rt_rain_next', n1(mmNext))}</span>{/if}{:else}<span class="dim">{L('ai_rt_rain_none')}</span>{/if}
			</span>
			<ProvWord label={mmNow != null ? (rain?.label ?? 'LIVE') : 'UNAVAILABLE'} {lang} />

			<span class="k"><Glyph name="timeline" size={16} /></span>
			<span class="v" data-testid="ai-tide">
				{#if td}
					<b>{L('ai_rt_tide', td.level.toFixed(2))}</b>, {L(td.rising ? 'ai_rt_rising' : 'ai_rt_falling')}
					<span class={['gate', td.gateClosed && 'shut']}>· {L(td.gateClosed ? 'ai_rt_gates_shut' : 'ai_rt_gates_open')}</span>
					{#if td.nextHigh}<span class="dim"> · {L('ai_rt_high', fmtTime(td.nextHigh.at), td.nextHigh.level.toFixed(2))}</span>{/if}
				{:else}<span class="dim">{L(tideDown ? 'ai_rt_tide_down' : 'ai_fc_loading')}</span>{/if}
			</span>
			<ProvWord prov={td ? 'modelled' : tideDown ? 'unavailable' : null} {lang} />

			{#if pumps}
				<span class="k"><Glyph name="building" size={16} /></span>
				<span class="v" data-testid="ai-pumps">{L('ai_rt_pumps', pumps.a, pumps.t)}</span>
				<ProvWord prov="emulated" {lang} />
			{/if}

			<span class="k"><Glyph name="alert" size={16} /></span>
			<span class="v" data-testid="ai-risk">
				{#if atRisk != null}
					{#if atRisk > 0}<span class="sw c{risk && risk.impassable ? 3 : risk && risk.deep ? 2 : 1}" aria-hidden="true"></span><b>{L('ai_rt_risk', atRisk)}</b>{:else}{L('ai_rt_risk_none')}{/if}
				{:else}<span class="dim">{L(hydroDown ? 'ai_rt_hydro_down' : 'ai_fc_loading')}</span>{/if}
			</span>
			<ProvWord prov={atRisk != null ? 'modelled' : hydroDown ? 'unavailable' : null} {lang} />
		</div>
		<button type="button" class="go" title={L('ai_rt_hindsight_tip')} aria-busy={replayBusy} data-testid="ai-hs-open" onclick={() => onhindsight(true)}>
			<Glyph name="history" size={16} />{replayBusy ? L('ai_rt_loading') : L('ai_rt_hindsight')}
		</button>
		{#if replayFailed}<p class="note">{L('ai_rt_failed')}</p>{/if}
	{/if}
</section>

<style>
	.rt {
		display: flex;
		flex-direction: column;
		gap: 8px;
		width: 380px;
		max-width: 100%;
		padding: 12px 14px;
		border: 1px solid var(--v3-glass-border);
		border-radius: var(--v3-radius-l);
		background: var(--v3-glass-surface);
		box-shadow: var(--v3-elev-1);
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		pointer-events: auto;
	}

	.grid {
		display: grid;
		grid-template-columns: 18px minmax(0, 1fr) auto;
		align-items: center;
		gap: 6px 10px;
		font-variant-numeric: tabular-nums;
	}

	.k {
		display: inline-flex;
		color: var(--v3-t3);
	}

	.v {
		min-width: 0;
	}

	b {
		color: var(--v3-t1);
		font-weight: 650;
	}

	.dim {
		color: var(--v3-t3);
	}

	.gate.shut {
		color: var(--v3-t1);
		font-weight: 650;
	}

	.sw {
		display: inline-block;
		width: 14px;
		height: 4px;
		margin-right: 6px;
		vertical-align: middle;
		border-radius: 2px;
		background: var(--v-map-water);
	}

	.sw.c1 {
		opacity: 0.5;
	}

	.go {
		display: inline-flex;
		align-items: center;
		align-self: flex-start;
		gap: 8px;
		height: 32px;
		padding: 0 14px;
		border: 1px solid var(--v3-line-2);
		border-radius: 16px;
		background: var(--v3-s2);
		color: var(--v3-t1);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}

	.go:hover {
		border-color: var(--v3-line-3);
	}

	.go:focus-visible,
	.st:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.hs-head {
		display: flex;
		align-items: center;
		gap: 8px;
		color: var(--v3-t1);
	}

	.note {
		margin: 0;
		color: var(--v3-t3);
	}

	.line {
		margin: 0;
	}

	.steps {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}

	.st {
		height: 28px;
		padding: 0 10px;
		border: 1px solid var(--v3-line-2);
		border-radius: 14px;
		background: none;
		color: var(--v3-t2);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}

	.st.is-pressed {
		border-color: var(--v3-t1);
		background: var(--v3-s3);
		color: var(--v3-t1);
	}
</style>
