<script lang="ts">
	/**
	 * The 108 corridor-request ProposalCard body (SPEC §5.4 "Corridor request
	 * · Approve / Defer"). part="why": who asked, for which event, where, and
	 * the golden hour counting honestly past 60 min; ONE rule note: deciding
	 * changes this dispatch's status only. part="evidence": the request's own
	 * fields.
	 */
	import { ops } from '$lib/ops/store.svelte';
	import { ACTION_ICON } from '$lib/design/icons';
	import { Id, Note } from '$lib/ui';
	import { fmtStamp } from '$lib/ui/format/format';
	import { fmtGoldenHour } from '$lib/ops/format';
	import { useShellClock, shellClock } from '$lib/shell/clock.svelte';
	import { t } from '$lib/i18n/strings';
	import { tOps } from '$lib/i18n/strings.ops';
	import '$lib/i18n/packs.decisions';
	import { corridorOf, type Unit } from '../units';

	let { unit, part = 'why', lang = ops.lang, now: nowProp = null }: { unit: Unit; part?: 'why' | 'evidence'; lang?: string; now?: number | null } = $props();

	// the golden hour ticks with the host card's clock, else the shell's 1 Hz clock
	$effect(() => {
		if (nowProp == null) return useShellClock();
	});
	const now = $derived(nowProp ?? shellClock.now);

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const d = $derived(corridorOf(unit).dispatch);
	const ev = $derived(corridorOf(unit).event);
	const by = $derived(d.requestedBy === '108-driver' ? tOps(lang, 'dispatch108') : ops.text(d.requestedBy) || '—');
	const wp = $derived(d.waypointJunction != null ? `J${d.waypointJunction}${ops.junctionName(d.waypointJunction) ? ` ${ops.junctionName(d.waypointJunction)}` : ''}` : null);
</script>

{#if part === 'why'}
	<p class="why">
		{L('dec_why_corridor', d.agencyLabel ?? d.agency, d.unitId ?? '—', by, d.createdAt ? fmtStamp(d.createdAt, now) : '—')}
		{#if ev}{' '}{L('dec_why_corridor_event', ops.text(ev.name))}{/if}
		{#if wp}{' '}{L('dec_why_corridor_waypoint', wp)}{/if}
		{' '}{L('dec_why_golden_hour', fmtGoldenHour(d.createdAt, now))}
	</p>
	<Note icon={ACTION_ICON.policies} text={L('dec_note_corridor')} />
{:else}
	<table class="mini">
		<tbody>
			<tr><td class="k">{L('dec_ev_dispatch')}</td><td><Id value={d.dispatchId.slice(0, 8)} /></td></tr>
			<tr><td class="k">{L('dec_ev_unit')}</td><td><Id value={d.unitId ?? '—'} /></td></tr>
			<tr><td class="k">{L('dec_ev_requested_by')}</td><td>{by}</td></tr>
			{#if d.decisionNote}<tr><td class="k">{L('dec_ev_note')}</td><td>{ops.text(d.decisionNote)}</td></tr>{/if}
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
