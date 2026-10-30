<script lang="ts">
	/**
	 * The escort-proposal ProposalCard body (SPEC §5.3 ConvoyCard, §5.4).
	 * Exported for UI-S6A's ConvoyCard (the home of escort proposals on `/`
	 * and the top of the /ops Decisions column). part="why": what the escort
	 * saw (the congestion ahead on the route), the decider's own reason when
	 * it says more than the decider line, and the ONE rule note "Unanswered
	 * when the countdown ends, the current plan is held."; this console's
	 * refused answer, verbatim. part="evidence": the escort it belongs to and
	 * its provenance (simulated feed, emulated GPS).
	 *
	 * Optional `ids` let a host keep its own pinned test ids on the parts
	 * (the ConvoyCard's `convoy-hud-proposal-why`).
	 */
	import { ops } from '$lib/ops/store.svelte';
	import { PROVENANCE_ICON } from '$lib/design/icons';
	import { Note, ProvenanceTag, Tag } from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import { tOps } from '$lib/i18n/strings.ops';
	import '$lib/i18n/packs.decisions';
	import { escortOf, escortSentence, type Unit } from '../units';

	let {
		unit,
		part = 'why',
		lang = ops.lang,
		ids = {},
		hostProvenance = {},
	}: { unit: Unit; part?: 'why' | 'evidence'; lang?: string; ids?: { why?: string; refused?: string }; hostProvenance?: { simulated?: boolean; gps?: boolean } } = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const d = $derived(escortOf(unit));
	const p = $derived(d.proposal);
	const pct = $derived(p.peakCongestion != null ? Math.round(p.peakCongestion * 100) : null);
	const roads = $derived(
		[...new Set(p.segmentIds.map((id) => ops.roadName(id) ?? `#${id}`))].slice(0, 3).join(', '),
	);
	const why = $derived(ops.escortProposalWhy(p));
	const answer = $derived(ops.escortDecisions[p.approvalId] ?? null);
	const eventName = $derived(d.event ? ops.text(d.event.name) : p.movementId.slice(0, 8));
</script>

{#if part === 'why'}
	<p class="why" title={p.summary ? ops.text(p.summary) : undefined}>
		{#if pct != null && roads}{L(p.trigger === 'phase_transition' ? 'dec_why_escort_departure' : 'dec_why_escort', pct, roads)}{:else}{L('dec_why_escort_plain')}{/if}
	</p>
	<p class="proposal" data-part="proposal">{L('dec_why_escort_proposal', ops.text(escortSentence(p)))}</p>
	{#if why}<p class="decider" data-testid={ids.why ?? 'escort-proposal-why'}>{ops.text(why)}</p>{/if}
	<Note icon="time" text={L('dec_note_escort')} />
	{#if answer && !answer.ok}
		<p class="refusal" data-testid={ids.refused ?? 'escort-proposal-refused'}>{answer.detail ?? `HTTP ${answer.httpStatus}`}</p>
	{/if}
{:else}
	<div class="prov">
		<span class="lbl">{tOps(lang, 'escQueueEvent', eventName)}</span>
		<span class="tags">
			{#if !hostProvenance.simulated && p.simulated}<ProvenanceTag source="simulated" {lang} />{/if}
			{#if !hostProvenance.gps && d.lane?.gpsMode === 'emulated'}<Tag icon={PROVENANCE_ICON.emulated} tooltip={L('dec_emulated_gps_tip')}>{tOps(lang, 'hudEmulatedGps')}</Tag>{/if}
		</span>
	</div>
{/if}

<style>
	.why {
		margin: 0 0 8px;
		font-size: var(--v-text-base);
		line-height: 21px;
		color: var(--v-ink-1);
	}

	.proposal {
		margin: 0 0 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-1);
	}

	.decider {
		margin: 0 0 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
	}

	.refusal {
		margin: 8px 0 0;
		padding: 6px 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-1);
		background: var(--v-danger-veil);
		border-radius: var(--v-radius-chip);
	}

	.prov {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.prov .lbl {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.tags {
		display: inline-flex;
		gap: 4px;
		flex-wrap: wrap;
	}
</style>
