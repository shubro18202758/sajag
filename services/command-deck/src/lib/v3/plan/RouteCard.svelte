<script lang="ts">
	/**
	 * RouteCard — one candidate route, like a ride-type row (V3-SPEC §6.6): its rank, the recommendation (violet when
	 * Sajag AI picked it, else the planner's own order), the figures the plan reports and nothing invented (time,
	 * distance, roads), the lane-floor line, what an alternate adds, and the planner's reason. The card is a radio:
	 * choosing it PREVIEWS it on the map. The escort always runs the recommended route (the launch call carries no
	 * route), so the card says which one runs and which are for comparison.
	 */
	import type { PlanRouteCandidate } from '$lib/api/client';
	import { t } from '$lib/i18n/strings';
	import Glyph from '../Glyph.svelte';
	import { routeFigures } from './model';
	import VehicleShot from '../media/VehicleShot.svelte';
	import './packs.plan';

	let {
		route,
		rank,
		recommended,
		pickedBy,
		confidence,
		adds,
		reason,
		checked,
		lang,
		onpick,
		shot = null,
	}: {
		/** The protection class's convoy composition (ride-type picture); null draws none. */
		shot?: string | null;
		route: PlanRouteCandidate;
		/** 0 = primary, 1.. = alternates A, B, … */
		rank: number;
		recommended: boolean;
		pickedBy: 'decider' | 'tactical';
		confidence: number | null;
		/** The "adds …" sentence (alternates), already worded. */
		adds: string | null;
		/** The planner's reason, already masked. */
		reason: string | null;
		checked: boolean;
		lang: string;
		onpick: () => void;
	} = $props();

	const L = (key: string, ...a: unknown[]) => t(lang, key, ...a);
	const f = $derived(routeFigures(route));
	const violations = $derived(route.lane_violations?.length ?? 0);
</script>

<button
	type="button"
	role="radio"
	aria-checked={checked}
	class={['card', checked && 'is-selected', recommended && 'rec', shot && 'has-shot']}
	data-testid="v3-plan-route"
	data-route-id={route.route_id}
	data-rank={rank === 0 ? 'primary' : 'alternate'}
	data-recommended={recommended ? 'true' : 'false'}
	onclick={onpick}
>
	<span class="top">
		<span class="rank"><span class="dot" aria-hidden="true"></span>{rank === 0 ? L('v3p_rank_primary') : L('v3p_rank_alt', String.fromCharCode(64 + rank))}</span>
		{#if recommended}
			<span class={['tag', pickedBy === 'decider' ? 'ai' : 'brand']} data-testid="v3-plan-pick" data-by={pickedBy}>
				<Glyph name={pickedBy === 'decider' ? 'spark' : 'check'} size={14} />
				{pickedBy === 'decider' && confidence != null ? L('v3p_pick_ai_conf', confidence.toFixed(2)) : pickedBy === 'decider' ? L('v3p_pick_ai') : L('v3p_pick_tactical')}
			</span>
		{/if}
	</span>

	{#if shot}<span class="shot-wrap" aria-hidden="true"><VehicleShot cls={shot} {lang} width={150} decorative /></span>{/if}
	<span class="figs">
		{#if f.minutes != null}<span class="fig" data-fig="min"><b>{f.minutes}</b><small>{L('v3p_fig_min')}</small></span>{/if}
		{#if f.km != null}<span class="fig" data-fig="km"><b>{f.km}</b><small>{L('v3p_fig_km')}</small></span>{/if}
		{#if f.roads != null}<span class="fig" data-fig="roads"><b>{f.roads}</b><small>{L('v3p_fig_roads', f.roads)}</small></span>{/if}
	</span>

	{#if route.route_tier === 'compliant'}
		<span class="tier ok"><Glyph name="checkc" size={15} />{L('v3p_tier_ok')}</span>
	{:else if route.route_tier}
		<span class="tier warn" data-violations={violations}><Glyph name="alert" size={15} />{L('v3p_tier_bad', violations)}</span>
	{/if}
	{#if adds}<span class="adds">{adds}</span>{/if}
	{#if reason}<span class="why">{reason}</span>{/if}
	<span class={['runs', recommended && 'yes']}>{recommended ? L('v3p_runs') : L('v3p_compare')}</span>
</button>

<style>
	.card {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 8px;
		width: 100%;
		padding: 14px 16px;
		border: 1px solid var(--v3-line-2);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
		color: var(--v3-t1);
		font: inherit;
		text-align: left;
		cursor: pointer;
		transition:
			border-color var(--v3-dur-1) var(--v3-ease),
			background var(--v3-dur-1) var(--v3-ease),
			transform var(--v3-dur-2) var(--v3-ease);
	}

	.card:hover {
		border-color: var(--v3-line-3);
		transform: translateY(-1px);
	}

	.card.is-selected {
		border-color: var(--v3-route);
		background: var(--v3-s2);
		box-shadow: inset 3px 0 0 var(--v3-route);
	}

	.card:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.card.has-shot {
		padding-right: 152px;
	}

	.card.has-shot .top {
		margin-right: -136px;
	}

	.shot-wrap {
		position: absolute;
		top: 34px;
		right: 10px;
		width: 132px;
		pointer-events: none;
	}

	.shot-wrap :global(.shot) {
		width: 100%;
		height: auto;
	}

	.top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
		min-height: 26px;
	}

	.rank {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		font-size: var(--v3-text-body);
		font-weight: 650;
	}

	.dot {
		width: 10px;
		height: 10px;
		border: 2px solid var(--v3-t3);
		border-radius: 50%;
	}

	.is-selected .dot {
		border-color: var(--v3-route);
		background: var(--v3-route);
	}

	.tag {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		height: 26px;
		padding: 0 10px;
		border-radius: 13px;
		font-size: var(--v3-text-micro);
		font-weight: 650;
		white-space: nowrap;
	}

	.tag.ai {
		background: var(--v3-ai-veil);
		color: var(--v3-ai-text);
	}

	.tag.brand {
		background: var(--v3-brand-veil);
		color: var(--v3-brand-text);
	}

	.figs {
		display: flex;
		gap: 22px;
	}

	.fig {
		display: inline-flex;
		align-items: baseline;
		gap: 5px;
	}

	.fig b {
		font-size: var(--v3-text-heading);
		line-height: var(--v3-lh-heading);
		font-weight: 650;
		font-variant-numeric: tabular-nums;
	}

	.fig small {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
	}

	.tier {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		font-weight: 600;
	}

	.tier.ok {
		color: var(--v3-ok-text);
	}

	.tier.warn {
		color: var(--v3-decide-text);
	}

	.adds,
	.why {
		color: var(--v3-t2);
		font-size: var(--v3-text-meta);
		line-height: var(--v3-lh-meta);
		overflow-wrap: anywhere;
	}

	.runs {
		padding-top: 8px;
		border-top: 1px solid var(--v3-line-1);
		color: var(--v3-t3);
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		font-weight: 600;
	}

	.runs.yes {
		color: var(--v3-route-text);
	}

	@media (prefers-reduced-motion: reduce) {
		.card,
		.card:hover {
			transition: none;
			transform: none;
		}
	}
</style>
