<script lang="ts">
	/**
	 * A road's waterlogging outlook (PLAN §2.4 B) on its object page: the hydro nowcast's depth-risk class 0–3 for the
	 * next two hours, the expected depth band, the lead time to the peak and to deep water, and the four drivers each with
	 * its own honest label — rain (Open-Meteo nowcast, LIVE as a model product, not a gauge), the Arabian Sea tide at Apollo Bunder (MODELLED,
	 * approximate), ground and drains (MODELLED) and the BMC storm-water pumps (EMULATED until access is granted). The whole reading is
	 * MODELLED; reroutes it proposes wait for an officer on Decide.
	 */
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import Glyph from '../Glyph.svelte';
	import '../field/packs.field';
	import { fetchReplay } from '../field/api';
	import { labelKey, type SegmentWater, type StormReplay } from '../field/model';
	import { fx, istClock, nowcast } from '../field/reads';
	import Panel from './Panel.svelte';

	let { segmentId, lang }: { segmentId: number; lang: string } = $props();
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	let seg = $state<SegmentWater | null>(null);
	let phase = $state<'loading' | 'ready' | 'none' | 'down'>('loading');

	onMount(() => {
		let gone = false;
		nowcast()
			.then((n) => {
				if (gone) return;
				seg = n.segments.find((s) => s.segmentId === segmentId) ?? null;
				phase = seg ? 'ready' : 'none';
			})
			.catch(() => {
				if (!gone) phase = 'down';
			});
		return () => {
			gone = true;
		};
	});

	// the 22–23 Sep 2025 storm, replayed on this road (hindsight: IMD's observed rain, the same depth model)
	let replay = $state<StormReplay | null>(null);
	let replayState = $state<'idle' | 'loading' | 'ready' | 'down'>('idle');
	async function loadReplay() {
		if (replayState === 'loading') return;
		if (replay) {
			replay = null;
			replayState = 'idle';
			return;
		}
		replayState = 'loading';
		try {
			replay = await fetchReplay(segmentId);
			replayState = 'ready';
		} catch {
			replayState = 'down';
		}
	}

	/** "Deep water from 02:45, peak at 05:30 IST" (whichever the replay has), sentence-cased. */
	function replayWhen(r: StormReplay): string {
		const parts = [r.segment?.firstDeep ? L('fld_wl_replay_deep', r.segment.firstDeep) : null, r.segment?.peakAt ? L('fld_wl_replay_peak', r.segment.peakAt) : null].filter(Boolean) as string[];
		const text = parts.join(', ');
		return text.charAt(0).toLocaleUpperCase(lang) + text.slice(1);
	}

	const km = (m: number | null) => (m === null ? '—' : (m / 1000).toFixed(1));
	const lbl = (raw: string | null | undefined) => L(`fld_lbl_${labelKey(raw)}`);
	const nextHigh = $derived(seg?.drivers.tide?.nextHighAt ? Date.parse(seg.drivers.tide.nextHighAt) : null);
</script>

<Panel title={L('fld_wl_title')} testid="obj-water" data-state={phase} data-risk={seg?.risk ?? ''}>
	{#if phase === 'ready' && seg}
		<div class="head">
			<div class={['risk', `r${seg.risk}`]}>
				<span class="gauge" aria-hidden="true">{#each [1, 2, 3] as i (i)}<i class={[seg.risk >= i && 'lit']}></i>{/each}</span>
				<div>
					<b class="rn">{L(`fld_risk_${seg.risk}`)}</b>
					<span class="rs">{L(`fld_risk_${seg.risk}_sub`)}</span>
				</div>
			</div>
			<span class="tag" data-label="MODELLED"><Glyph name="graph" size={14} />{L('fld_tag_modelled')}</span>
		</div>

		<div class="facts">
			{#if seg.depthBand}<span class="fact fig">{L('fld_wl_depth', seg.depthBand)}</span>{/if}
			{#if seg.risk >= 2 && seg.deepLeadMin !== null && seg.deepLeadMin > 0}
				<span class="fact fig"><Glyph name="clock" size={15} />{L('fld_wl_deep_in', Math.round(seg.deepLeadMin))}</span>
			{:else if seg.risk >= 1 && seg.leadMin !== null && seg.leadMin > 0}
				<span class="fact fig"><Glyph name="clock" size={15} />{L('fld_wl_peak_in', Math.round(seg.leadMin))}</span>
			{:else if seg.risk >= 1}
				<span class="fact">{L('fld_wl_now')}</span>
			{/if}
			{#if seg.elevated}<span class="fact">{L('fld_wl_elevated')}</span>{/if}
		</div>

		<h3 class="dh">{L('fld_wl_drivers')}</h3>
		<ul class="drivers">
			{#if seg.drivers.rain}
				<li>
					<span class="dk"><Glyph name="wave" size={16} />{L('fld_drv_rain')}<em>{lbl(seg.drivers.rain.label)}</em></span>
					<span class="dv fig">{L('fld_drv_rain_v', fx(seg.drivers.rain.past1h, 1), fx(seg.drivers.rain.next2h, 1))}</span>
				</li>
			{/if}
			{#if seg.drivers.tide}
				<li>
					<span class="dk"><Glyph name="timeline" size={16} />{L('fld_drv_tide')}<em>{lbl(seg.drivers.tide.label)}</em></span>
					<span class="dv fig">{L('fld_drv_tide_v', fx(seg.drivers.tide.levelM))} · {seg.drivers.tide.gateClosed ? L('fld_drv_gates_shut') : L('fld_drv_gates_open')}</span>
					{#if nextHigh !== null && seg.drivers.tide.nextHighM !== null}<span class="dm fig">{L('fld_drv_tide_next', istClock(nextHigh), fx(seg.drivers.tide.nextHighM))}</span>{/if}
				</li>
			{/if}
			{#if seg.drivers.ground}
				<li>
					<span class="dk"><Glyph name="layers" size={16} />{L('fld_drv_ground')}<em>{lbl(seg.drivers.ground.label)}</em></span>
					<span class="dv fig">{L('fld_drv_ground_v', fx(seg.drivers.ground.score), km(seg.drivers.ground.drainM))}</span>
					{#if seg.drivers.ground.hotspotM !== null}<span class="dm fig">{L('fld_drv_hotspot', km(seg.drivers.ground.hotspotM))}</span>{/if}
				</li>
			{/if}
			{#if seg.drivers.pumps}
				<li>
					<span class="dk"><Glyph name="building" size={16} />{L('fld_drv_pumps')}<em class="dash">{lbl(seg.drivers.pumps.label)}</em></span>
					<span class="dv fig">{L('fld_drv_pumps_v', seg.drivers.pumps.available ?? '—', seg.drivers.pumps.total ?? '—')}</span>
					{#if seg.drivers.pumps.station}<span class="dm">{seg.drivers.pumps.station}</span>{/if}
				</li>
			{/if}
		</ul>

		<div class="replay" data-testid="obj-water-replay" data-state={replayState}>
			<button type="button" class={['rb', replay && 'is-pressed']} aria-pressed={!!replay} onclick={() => void loadReplay()} disabled={replayState === 'loading'}>
				<Glyph name="history" size={18} />{replayState === 'loading' ? L('fld_wl_replaying') : L('fld_wl_replay')}
			</button>
			{#if replay}
				<div class="rcard">
					<div class="rhead">
						<b>{L('fld_wl_replay_h')}</b>
						<span class="tag" data-label="HINDSIGHT"><Glyph name="history" size={14} />{L('fld_wl_replay_label')}</span>
					</div>
					{#if replay.segment && !replay.segment.elevated && replay.segment.peakClass > 0}
						<div class="rrow">
							<span class={['rgauge', `r${replay.segment.peakClass}`]} aria-hidden="true">{#each [1, 2, 3] as i (i)}<i class={[replay.segment.peakClass >= i && 'lit']}></i>{/each}</span>
							<div>
								<b class="rpk">{L(`fld_risk_${replay.segment.peakClass}`)}{#if replay.segment.peakBand}<span class="fig">{' · '}{replay.segment.peakBand}</span>{/if}</b>
								<span class="rsub fig">{replayWhen(replay)}</span>
							</div>
						</div>
					{:else}
						<p class="rsub">{L('fld_wl_replay_dry')}</p>
					{/if}
					<p class="rsub fig">
						{#if replay.segment?.rainMm != null}{L('fld_wl_replay_rain', Math.round(replay.segment.rainMm))}{/if}
						{#if replay.reportedOnNetwork}{' '}{L('fld_wl_replay_news', replay.reportedFlagged ?? 0, replay.reportedOnNetwork)}{/if}
					</p>
				</div>
			{:else if replayState === 'down'}
				<p class="quiet">{L('fld_wl_down')}</p>
			{/if}
		</div>
	{:else if phase === 'loading'}
		<div class="skel" aria-busy="true"><i></i><i></i></div>
	{:else}
		<p class="quiet">{phase === 'none' ? L('fld_wl_none') : L('fld_wl_down')}</p>
	{/if}
</Panel>

<style>
	.head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 14px;
	}

	.risk {
		display: flex;
		align-items: center;
		gap: 16px;
	}

	.gauge {
		display: flex;
		align-items: flex-end;
		gap: 4px;
		height: 44px;
	}

	.gauge i {
		display: block;
		width: 10px;
		border-radius: 3px;
		background: var(--v3-s3);
	}

	.gauge i:nth-child(1) {
		height: 16px;
	}

	.gauge i:nth-child(2) {
		height: 28px;
	}

	.gauge i:nth-child(3) {
		height: 42px;
	}

	.gauge i.lit {
		background: var(--v3-brand);
	}

	.r3 .gauge i.lit {
		background: var(--v3-brand-strong);
	}

	.rn {
		display: block;
		font-size: var(--v3-text-title);
		line-height: var(--v3-lh-title);
		font-weight: 700;
	}

	.r2 .rn,
	.r3 .rn {
		color: var(--v3-brand-text);
	}

	.rs {
		color: var(--v3-t2);
		font-size: 14px;
	}

	.tag {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		height: 26px;
		padding: 0 10px;
		border: 1px dashed var(--v3-dashed);
		border-radius: 13px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 650;
		white-space: nowrap;
	}

	.facts {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.fact {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		min-height: 30px;
		padding: 0 12px;
		border-radius: 15px;
		background: var(--v3-s2);
		color: var(--v3-t1);
		font-size: 14px;
	}

	.fig {
		font-variant-numeric: tabular-nums;
	}

	.dh {
		margin: 4px 0 0;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 700;
	}

	.drivers {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 10px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.drivers li {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 12px 14px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
	}

	.dk {
		display: flex;
		align-items: center;
		gap: 8px;
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		font-weight: 700;
	}

	.dk em {
		margin-left: auto;
		padding: 1px 8px;
		border: 1px solid var(--v3-line-2);
		border-radius: 10px;
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		font-style: normal;
		font-weight: 600;
	}

	.dk em.dash {
		border-style: dashed;
	}

	.dv {
		color: var(--v3-t1);
		font-size: 14px;
		line-height: 20px;
	}

	.dm {
		color: var(--v3-t3);
		font-size: var(--v3-text-meta);
	}

	.quiet {
		margin: 0;
		color: var(--v3-t2);
		font-size: 14px;
	}

	.replay {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 12px;
		padding-top: 6px;
		border-top: 1px solid var(--v3-line-1);
	}

	.rb {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: var(--v3-ctl-lg);
		margin-top: 8px;
		padding: 0 18px 0 14px;
		border: 1px solid var(--v3-line-3);
		border-radius: 22px;
		background: none;
		color: var(--v3-t1);
		font: inherit;
		font-size: 14px;
		font-weight: 650;
		cursor: pointer;
	}

	.rb:hover:not(:disabled) {
		background: var(--v3-s3);
	}

	.rb.is-pressed {
		border-color: var(--v3-brand);
		background: var(--v3-brand-veil);
	}

	.rb:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.rcard {
		display: flex;
		flex-direction: column;
		gap: 10px;
		width: 100%;
		box-sizing: border-box;
		padding: 16px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
		animation: rise var(--v3-dur-3) var(--v3-ease);
	}

	@keyframes rise {
		from {
			transform: translateY(6px);
			opacity: 0;
		}
	}

	.rhead {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
	}

	.rrow {
		display: flex;
		align-items: center;
		gap: 14px;
	}

	.rgauge {
		display: flex;
		align-items: flex-end;
		gap: 3px;
		height: 34px;
	}

	.rgauge i {
		display: block;
		width: 8px;
		border-radius: 2px;
		background: var(--v3-s4);
	}

	.rgauge i:nth-child(1) {
		height: 12px;
	}

	.rgauge i:nth-child(2) {
		height: 22px;
	}

	.rgauge i:nth-child(3) {
		height: 32px;
	}

	.rgauge i.lit {
		background: var(--v3-brand);
	}

	.rpk {
		display: block;
		color: var(--v3-brand-text);
		font-size: var(--v3-text-sub);
		line-height: var(--v3-lh-sub);
	}

	.rsub {
		margin: 0;
		color: var(--v3-t2);
		font-size: 14px;
		line-height: 20px;
	}

	.skel {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.skel i {
		display: block;
		height: 44px;
		border-radius: 8px;
		background: var(--v3-s2);
		animation: pulse 1.2s ease-in-out infinite;
	}

	@keyframes pulse {
		50% {
			opacity: 0.5;
		}
	}

	@media (max-width: 760px) {
		.drivers {
			grid-template-columns: minmax(0, 1fr);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.skel i,
		.rcard {
			animation: none;
		}
	}
</style>
