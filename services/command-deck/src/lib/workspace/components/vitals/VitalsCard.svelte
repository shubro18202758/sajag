<script lang="ts">
	/**
	 * The City vitals card (SPEC §6.2; prototype shot 07): map mode's
	 * floating card, top right. Six figures and the traffic feed's
	 * provenance; no band (the navbar carries it). The page (or the frame's
	 * overlay slot) positions it; the card only sizes itself.
	 *
	 *   Open events · Decisions waiting (units, orange while one waits) ·
	 *   Watchlisted vehicles (the registry count, as the Explorer) · Cameras
	 *   answering · Feed anomalies, 15 min · Reported events (only when there
	 *   are any) · Traffic feed (`vitals-feeds`, the `.sim` tag when simulated)
	 *
	 * A zero recedes to ink-2; every figure explains its scope in a tooltip.
	 */
	import { ACTION_ICON } from '$lib/design/icons';
	import { Icon, ProvenanceTag, Time, Tooltip } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.views';
	import type { VitalsView } from './types';

	let { view, lang }: { view: VitalsView; lang: string } = $props();
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	const c = $derived(view.card);
</script>

{#snippet figure(key: string, label: string, hint: string, value: number, extra: string | null, warn: boolean)}
	<Tooltip content={hint} placement="left">
		<div class="vrow" data-vital={key} data-value={value}>
			<span class="k">{label}</span>
			<span class={['v', value === 0 && 'zero', warn && value > 0 && 'warn']}>{value}{#if extra}<span class="of">{extra}</span>{/if}</span>
		</div>
	</Tooltip>
{/snippet}

<section class="card" data-testid="city-vitals" data-variant="card" aria-label={L('vw_v_title')}>
	<header class="head">
		<span class="title">{L('vw_v_title')}</span>
		<span class="asof">{L('vw_v_as_of')} <Time value={view.now} /></span>
	</header>
	{#if c}
		{@render figure('open-events', L('vw_v_open_events'), L('vw_v_open_events_hint'), c.openEvents, null, false)}
		{@render figure('decisions', L('vw_v_decisions'), c.decisionsFromUnits ? L('vw_v_decisions_hint') : L('vw_v_decisions_hint_registry'), c.decisions, null, true)}
		{@render figure('watchlisted', L('vw_v_watchlisted'), L('vw_v_watchlisted_hint'), c.watchlisted, null, false)}
		{@render figure('cameras', L('vw_v_cameras'), L('vw_v_cameras_hint'), c.cameras.answering, ` / ${c.cameras.total}`, false)}
		{@render figure('anomalies', L('vw_v_anomalies'), L('vw_v_anomalies_hint'), c.anomalies, null, false)}
		{#if c.reported > 0}
			<Tooltip content={L('vw_v_reported_hint')} placement="left">
				<div class="vrow" data-vital="reported" data-value={c.reported}>
					<span class="k">{L('vw_v_reported')}</span>
					<ProvenanceTag source="osint" compact />
					<span class="v">{c.reported}</span>
				</div>
			</Tooltip>
		{/if}
		<div class="vrow" data-testid="vitals-feeds" data-simulated={c.trafficSimulated}>
			<span class="k">{L('vw_v_traffic_feed')}</span>
			{#if c.trafficSimulated}
				<ProvenanceTag source="simulated" class="sim" />
			{:else}
				<span class="v live">{L('vw_v_live')}</span>
			{/if}
		</div>
	{/if}
	{#if view.replay}
		<p class="note" data-testid="vitals-replay-note"><Icon name={ACTION_ICON.return_to_live} size={12} />{L('vw_v_replay_note')}</p>
	{/if}
</section>

<style>
	.card {
		box-sizing: border-box;
		width: 252px;
		padding: 8px 12px 8px;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-1);
		box-shadow: var(--v-elev-2);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.head {
		display: flex;
		align-items: center;
		gap: 8px;
		height: 28px;
	}

	.title {
		flex: 1 1 auto;
		font-size: var(--v-text-base);
		font-weight: 600;
		line-height: 16px;
	}

	.asof {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.vrow {
		display: flex;
		align-items: center;
		gap: 8px;
		height: 24px;
		font-size: var(--v-text-xs);
		outline: 0;
	}

	.k {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		color: var(--v-ink-2);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.v {
		color: var(--v-ink-1);
		font-size: var(--v-text-base);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.v.zero {
		color: var(--v-ink-2);
	}

	.v.warn {
		color: var(--v-warning-text);
		font-weight: 600;
	}

	.v.live {
		font-size: var(--v-text-xs);
	}

	.of {
		color: var(--v-ink-2);
	}

	.note {
		display: flex;
		align-items: center;
		gap: 6px;
		margin: 4px 0 0;
		padding-top: 6px;
		border-top: 1px solid var(--v-line-1);
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: 16px;
	}
</style>
