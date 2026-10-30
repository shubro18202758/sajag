<script lang="ts">
	/**
	 * The pursuit-opening ProposalCard body (SPEC §5.4 Writers "Pursuit · Open
	 * pursuit"). part="why": the latest read and the road anchor the pursuit
	 * would open on, the ONE rule note (a named officer opens it; one approval
	 * opens one pursuit), and the refusal inline (`pursuit-refusal`): no road
	 * anchor, or no human-approved recommendation — a stolen vehicle's basis
	 * is its approved sighting, never an e-challan approved before the theft.
	 * part="evidence": the approval it would open from.
	 */
	import { ops } from '$lib/ops/store.svelte';
	import { ACTION_ICON } from '$lib/design/icons';
	import { Id, Note, Plate } from '$lib/ui';
	import { fmtAgo } from '$lib/ui/format/format';
	import { compass } from '$lib/workspace/kinds/common';
	import { useShellClock, shellClock } from '$lib/shell/clock.svelte';
	import { t } from '$lib/i18n/strings';
	import { tOps } from '$lib/i18n/strings.ops';
	import '$lib/i18n/packs.decisions';
	import { pursuitOf, type Unit } from '../units';

	let { unit, part = 'why', lang = ops.lang, now: nowProp = null }: { unit: Unit; part?: 'why' | 'evidence'; lang?: string; now?: number | null } = $props();

	// "last read 2 min ago" ticks with the host card's clock, else the shell's 1 Hz clock
	$effect(() => {
		if (nowProp == null) return useShellClock();
	});
	const now = $derived(nowProp ?? shellClock.now);

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const d = $derived(pursuitOf(unit));
	const s = $derived(d.candidate.vehicle.lastSighting);
	const a = $derived(d.candidate.anchor);
	const note = $derived(ops.pursuitNote?.vehicleId === d.vehicleId ? ops.pursuitNote.text : null);
	/** The earmark's own words, closed as a sentence. */
	const reason = $derived.by(() => {
		const r = ops.text(d.candidate.vehicle.earmarkReason).trim();
		if (!r) return L('dec_why_watchlisted');
		return /[.!?)]$/.test(r) ? r : `${r}.`;
	});
</script>

{#if part === 'why'}
	<p class="why">
		{reason}
		{#if s?.t}{' '}{L('dec_why_last_read', fmtAgo(s.t, now, lang))}{#if s.speedKmh != null}{` · ${L('dec_kmh', Math.round(s.speedKmh))}`}{/if}{#if s.heading != null}{` · ${L('dec_heading', compass(s.heading, lang))}`}{/if}.{/if}
		{#if a}{' '}{L('dec_why_anchor', a.roadName ?? `#${a.segmentId}`, a.distanceM)}{/if}
	</p>
	<Note icon={ACTION_ICON.rule_no_fine} title={L('dec_note_one_pursuit_title')}>{L('dec_note_one_pursuit')}</Note>
	{#if d.refusal}
		<p class="refusal" data-testid="pursuit-refusal">
			{d.refusal === 'no-anchor' ? tOps(lang, 'queuePursuitNoAnchor') : tOps(lang, 'queuePursuitNoApproval')}
		</p>
	{:else if note}
		<p class="refusal" data-testid="pursuit-refusal">{ops.text(note)}</p>
	{/if}
{:else}
	<table class="mini">
		<tbody>
			<tr><td class="k">{L('dec_registration_mark')}</td><td><Plate mark={ops.plate(d.plate)} masked={!ops.officerOn} /></td></tr>
			<tr><td class="k">{L('dec_ev_basis')}</td><td>{d.candidate.recommendationId ? L('dec_ev_approved_rec') : L('dec_ev_none')}{#if d.candidate.recommendationId}{' '}<Id value={d.candidate.recommendationId.slice(0, 8)} />{/if}</td></tr>
			<tr><td class="k">{L('dec_ev_anchor')}</td><td>{a ? `${a.roadName ?? '—'} · #${a.segmentId}` : L('dec_ev_none')}</td></tr>
		</tbody>
	</table>
{/if}

<style>
	.why {
		margin: 0 0 8px;
		font-size: var(--v-text-base);
		line-height: 21px;
		color: var(--v-ink-1);
	}

	.refusal {
		margin: 8px 0 0;
		padding: 6px 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-1);
		background: var(--v-neutral-veil);
		border-radius: var(--v-radius-chip);
	}

	.mini {
		width: 100%;
		border-collapse: collapse;
		table-layout: fixed;
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.mini td {
		height: 26px;
		padding: 0 8px 0 0;
		border-bottom: 1px solid var(--v-line-1);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		color: var(--v-ink-1);
	}

	.mini td.k {
		width: 36%;
		color: var(--v-ink-2);
	}
</style>
