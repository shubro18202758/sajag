<script lang="ts">
	/**
	 * The e-challan ProposalCard body (SPEC §5.4, §9.3). part="why": what the
	 * rule read (masked), then ONE rule note — on a vehicle reported stolen
	 * (C-N) it is the owner-is-the-victim rule (`stolen-note`): Reject only,
	 * never Approve; and the oracle's 409 verbatim (`decision-refusal`), never
	 * retried. part="evidence": the evidence the rule filed, masked.
	 */
	import { ops } from '$lib/ops/store.svelte';
	import { ACTION_ICON, ACTOR_ICON } from '$lib/design/icons';
	import { Id, Note } from '$lib/ui';
	import { fmtStamp } from '$lib/ui/format/format';
	import { t } from '$lib/i18n/strings';
	import { tOps } from '$lib/i18n/strings.ops';
	import '$lib/i18n/packs.decisions';
	import { echallanOf, type Unit } from '../units';
	import { ruleLabel } from './meta';

	let { unit, part = 'why', lang = ops.lang }: { unit: Unit; part?: 'why' | 'evidence'; lang?: string } = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const d = $derived(echallanOf(unit));
	const ev = $derived(d.rec.evidence ?? {});
	const str = (v: unknown) => (typeof v === 'string' && v.trim() ? v : null);
	const rows = $derived(
		[
			[L('dec_ev_camera'), str(ev.camera_id), 'id'],
			[L('dec_ev_road'), str(ev.road_name), 'text'],
			[L('dec_ev_speed'), typeof ev.speed_kmh === 'number' ? L('dec_kmh', Math.round(ev.speed_kmh)) : null, 'text'],
			[L('dec_ev_limit'), typeof ev.limit_kmh === 'number' ? L('dec_kmh', Math.round(ev.limit_kmh)) : null, 'text'],
			[L('dec_ev_read'), str(ev.t) ? `${fmtStamp(ev.t as string)} IST` : null, 'text'],
			[L('dec_ev_rule'), ruleLabel(d.rec.ruleId, lang), 'text'],
		].filter((r) => r[1] != null) as Array<[string, string, 'id' | 'text']>,
	);
</script>

{#if part === 'why'}
	<p class="why">{ops.text(d.rec.recommendation) || L('dec_why_echallan')}</p>
	{#if d.stolen}
		<Note icon={ACTION_ICON.rule_no_fine} title={L('dec_note_no_fine')} data-testid="stolen-note">{tOps(lang, 'queueStolenOwnerVictim')}</Note>
	{:else}
		<Note icon={ACTOR_ICON.rules} title={L('dec_note_rule_proposes')}>{L('dec_note_echallan')}</Note>
	{/if}
	{#if d.refusal}
		<p class="refusal" data-testid="decision-refusal">{d.refusal.detail}</p>
	{/if}
{:else}
	<table class="mini">
		<tbody>
			{#each rows as [k, v, kind] (k)}
				<tr>
					<td class="k">{k}</td>
					<td>{#if kind === 'id'}<Id value={v} />{:else}{ops.text(v)}{/if}</td>
				</tr>
			{/each}
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
