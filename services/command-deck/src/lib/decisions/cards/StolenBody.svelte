<script lang="ts">
	/**
	 * The stolen-vehicle ProposalCard body (SPEC §5.4, §9.3; prototype
	 * review.js stolenCard). part="why": the reads in plain words and the ONE
	 * rule note, verbatim — "Evidence only: e-challan withheld (vehicle
	 * reported stolen, FIR …). One approval opens one pursuit." — which stays
	 * in the item's DOM while it is collapsed (ops-wall-smoke:1056); then the
	 * authorisation already given (`stolen-authorised`) and the oracle's
	 * refusal, verbatim (`decision-refusal`). part="evidence": the sightings
	 * in this decision, newest first.
	 */
	import { ops } from '$lib/ops/store.svelte';
	import { ACTION_ICON, kindIcon } from '$lib/design/icons';
	import { Icon, Id, Note, Plate } from '$lib/ui';
	import { fmtRange, fmtStamp } from '$lib/ui/format/format';
	import { t } from '$lib/i18n/strings';
	import { tOps } from '$lib/i18n/strings.ops';
	import '$lib/i18n/packs.decisions';
	import { stolenOf, type Unit } from '../units';

	let { unit, part = 'why', lang = ops.lang }: { unit: Unit; part?: 'why' | 'evidence'; lang?: string } = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const d = $derived(stolenOf(unit));
	const str = (v: unknown) => (typeof v === 'string' && v.trim() ? v : null);
	const reads = $derived([...d.recs].sort((a, b) => Date.parse(a.createdAt ?? '') - Date.parse(b.createdAt ?? '')));
	const cams = $derived([...new Set(reads.map((r) => str(r.evidence?.camera_id)).filter((c): c is string => !!c))]);
	const span = $derived(reads.length ? fmtRange(reads[0].createdAt, reads[reads.length - 1].createdAt) : null);
	const speed = $derived(typeof d.newest.evidence?.speed_kmh === 'number' ? Math.round(d.newest.evidence.speed_kmh as number) : null);
</script>

{#if part === 'why'}
	<p class="why">
		{d.fir ? L(d.emulated ? 'dec_why_stolen_fir_demo' : 'dec_why_stolen_fir', d.fir) : L('dec_why_stolen')}
		{#if cams.length}
			{' '}{L('dec_why_read_by', cams.length, span ?? '—')}
			{#each cams as c, i (c)}{#if i}<span class="arrow"> → </span>{/if}<Id value={c} />{/each}.
		{/if}
		{#if speed != null}{' '}{L('dec_why_last_speed', speed)}{/if}
	</p>
	<Note icon={ACTION_ICON.rule_no_fine} title={L('dec_note_evidence_only')} data-testid="stolen-note-rule">
		{L('dec_note_stolen', d.fir)}
	</Note>
	{#if d.approved}
		<p class="done" data-testid="stolen-authorised">
			<Icon name="tick-circle" size={16} />{tOps(lang, 'queueStolenAuthorised', d.approved.decidedBy ?? '—')}{#if d.approved.decidedAt}{` · ${fmtStamp(d.approved.decidedAt)} IST`}{/if}
		</p>
	{/if}
	{#if d.refusal}
		<p class="refusal" data-testid="decision-refusal">{d.refusal.detail}</p>
	{/if}
{:else}
	<table class="mini">
		<colgroup><col class="c-cam" /><col /><col class="c-num" /><col class="c-num" /></colgroup>
		<tbody>
			{#each d.recs as r (r.recommendationId)}
				<tr data-rec-id={r.recommendationId}>
					<td><span class="c"><Icon name={kindIcon('sighting')} size={16} /><Id value={str(r.evidence?.camera_id) ?? '—'} /></span></td>
					<td class="muted">{ops.text(str(r.evidence?.road_name) ?? '') || L('dec_road_unknown')}</td>
					<td class="num">{typeof r.evidence?.speed_kmh === 'number' ? L('dec_kmh', Math.round(r.evidence.speed_kmh as number)) : '—'}</td>
					<td class="num">{r.createdAt ? fmtStamp(r.createdAt) : '—'}</td>
				</tr>
			{/each}
		</tbody>
	</table>
	{#if d.watch?.plate}
		<p class="plate-line"><span class="muted">{L('dec_registration_mark')}</span> <Plate mark={ops.plate(d.watch.plate)} masked={!ops.officerOn} /></p>
	{/if}
{/if}

<style>
	.why {
		margin: 0 0 8px;
		font-size: var(--v-text-base);
		line-height: 21px;
		color: var(--v-ink-1);
	}

	.arrow {
		color: var(--v-ink-2);
	}

	.done {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 8px 0 0;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-success-text);
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

	.mini {
		width: 100%;
		border-collapse: collapse;
		table-layout: fixed;
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.mini col.c-cam {
		width: 34%;
	}

	.mini col.c-num {
		width: 64px;
	}

	.mini td {
		height: 26px;
		padding: 0 8px 0 0;
		border-bottom: 1px solid var(--v-line-1);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		vertical-align: middle;
	}

	.mini td:last-child {
		padding-right: 0;
	}

	.mini .c {
		display: flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
		color: var(--v-ink-1);
	}

	.mini .c :global(svg) {
		color: var(--v-ink-2);
		flex: 0 0 auto;
	}

	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}

	.muted {
		color: var(--v-ink-2);
	}

	.plate-line {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 8px 0 0;
		font-size: var(--v-text-xs);
	}
</style>
