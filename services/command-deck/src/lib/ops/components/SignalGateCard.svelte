<script lang="ts">
	/**
	 * City signal plans (SPEC §6.3 col 3; ownership UI-S5B): the gated
	 * signal-plan writer as the city band drives it.
	 *
	 *   header   "Writer off" (or on) as a tag whose tooltip says what that
	 *            means; the old caption chain is gone (SPEC §3.5)
	 *   table    Band · Corridor priority · Cross-street green · Writes, the
	 *            city's band row marked (BLACK with its hairline, BandChip)
	 *   gate     twin shadow-evaluations in flight as a COUNT (`gate-twin`
	 *            data-count) and the writer's live state
	 *   actions  Apply plan, Restore (the selected LIVE event's junctions:
	 *            `gate-restore`, disabled for a preview fixture, which has no
	 *            signal history and an id the writer cannot cast), Restore all
	 *            (city-wide: the first click only arms it — `gate-restore-all`
	 *            data-armed 1 — the second commits ONE POST), History.
	 *            Every write is under the named duty officer; one at a time.
	 *   refusal  a 409 renders inline as "Held at baseline" with the reason
	 *            and the report behind a disclosure — never a modal. An
	 *            UNKNOWN city band is never applied as a Green default: the
	 *            officer picks the band, explicitly.
	 */
	import BandChip from '$lib/primitives/BandChip.svelte';
	import { kindIcon } from '$lib/design/icons';
	import { Button, Reason, Section, Tag, Tooltip } from '$lib/ui';
	import { fmtTime } from '$lib/ui/format/format';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';
	import { ops, isLiveUuidEvent } from '$lib/ops/store.svelte';
	import Age from '$lib/decisions/wall/Age.svelte';
	import type { BandCode } from '$lib/ops/types';

	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	const plans = $derived(ops.signalPlans);
	const outcome = $derived(ops.signalApply);
	const gate = $derived(plans?.gate ?? null);
	const restorable = $derived(isLiveUuidEvent(ops.selectedEvent));
	const busy = $derived(ops.signalRestoring !== null || ops.signalApplying);

	let detailOpen = $state(false);
	let historyOpen = $state(false);
	/** Restore all is city-wide: the first click arms it, the second commits. */
	let armed = $state(false);

	// An armed Restore all never outlives the officer who armed it.
	$effect(() => {
		if (!ops.officerOn) armed = false;
	});

	async function restoreAll() {
		if (!armed) {
			armed = true;
			return;
		}
		armed = false;
		await ops.restorePrograms(true);
	}

	/** The writer refused for want of a band (409), or the city band is stale: the officer names one. */
	const bandUnknown = $derived(
		(!!outcome && !outcome.applied && outcome.status === 409 && /city band unknown/i.test(outcome.refusalReason ?? '')) ||
			ops.cityBand?.stale === true,
	);
	const BANDS: readonly BandCode[] = ['GREEN', 'AMBER', 'RED', 'BLACK'];

	const writerWord = $derived.by(() => {
		if (!gate) return null;
		if (gate.writerActive) return L('wall_sp_writer_active');
		if ((gate.writerWaiters ?? 0) > 0) return L('wall_sp_writer_queued', gate.writerWaiters);
		return L('wall_sp_writer_idle');
	});

	const officerReason = $derived(ops.officerOn ? null : L('wall_sp_needs_officer'));
	const restoreReason = $derived(!restorable ? L('wall_sp_restore_needs_live') : officerReason);
</script>

{#snippet right()}
	<Age at={ops.signalPlansUpdated || null} {lang} />
	{#if plans}
		{#if plans.writerEnabled}
			<Tag intent="success" icon="unlock" tooltip={L('wall_sp_writer_on_tip')}>{L('wall_sp_writer_on')}</Tag>
		{:else}
			<Tag icon="lock" tooltip={L('wall_sp_writer_off_tip')} data-testid="gate-posture">{L('wall_sp_writer_off')}</Tag>
		{/if}
	{/if}
{/snippet}

<Section title={L('wall_signals')} icon={kindIcon('junction')} level={2} {right} data-prim="panel" data-wall="signal-plans">
	{#if plans}
		<table class="wdt plans">
			<colgroup><col style:width="88px" /><col /><col /><col style:width="104px" /></colgroup>
			<thead>
				<tr>
					<th scope="col">{L('wall_sp_band')}</th>
					<th scope="col" class="num">{L('wall_sp_priority')}</th>
					<th scope="col" class="num">{L('wall_sp_floor')}</th>
					<th scope="col">{L('wall_sp_writes')}</th>
				</tr>
			</thead>
			<tbody>
				{#each plans.bandPlanTable as row (row.band)}
					<tr class:is-selected={plans.cityBand === row.band} data-band={row.band}>
						<td><div class="c"><BandChip band={row.band} size="sm" {lang} /></div></td>
						<td class="num"><div class="c">{row.priorityShare != null ? `${Math.round(row.priorityShare * 100)}%` : '—'}</div></td>
						<td class="num"><div class="c">{row.crossGreenFloorSec != null ? L('wall_sp_seconds', row.crossGreenFloorSec) : '—'}</div></td>
						<td><div class="c"><span class:muted={row.writes !== 'writes'}>{row.writes === 'writes' ? L('wall_sp_writes_yes') : L('wall_sp_writes_no')}</span></div></td>
					</tr>
				{/each}
			</tbody>
		</table>

		<div class="gate">
			<span class="tn" data-testid="gate-twin" data-count={gate?.twinInFlight ?? ''} title={L('wall_sp_twin_tip')}>{L('wall_sp_twin', gate?.twinInFlight ?? 0)}</span>
			{#if writerWord}<span class="sep" aria-hidden="true"></span><span>{writerWord}</span>{/if}
			{#if plans.lastPlan}
				<span class="sep" aria-hidden="true"></span>
				<span class="ell" title={plans.lastPlan.reason ? ops.text(plans.lastPlan.reason) : undefined}>
					{plans.lastPlan.applied === false ? L('wall_sp_last_held') : L('wall_sp_last_plan', plans.lastPlan.plannedJunctions.length)}
				</span>
			{/if}
		</div>

		<div class="actions">
			<Button small disabled={busy || !ops.officerOn} disabledReason={officerReason} loading={ops.signalApplying} onclick={() => void ops.applyCityPlan()}>
				{L('wall_sp_apply')}
			</Button>
			<Button
				small
				data-testid="gate-restore"
				disabled={!restorable || !ops.officerOn || busy}
				disabledReason={restoreReason}
				loading={ops.signalRestoring === 'event'}
				onclick={() => void ops.restorePrograms(false)}
			>
				{L('wall_sp_restore')}
			</Button>
			<Button
				small
				data-testid="gate-restore-all"
				data-armed={armed ? '1' : '0'}
				disabled={!ops.officerOn || busy}
				disabledReason={officerReason}
				loading={ops.signalRestoring === 'all'}
				onclick={() => void restoreAll()}
			>
				{armed ? L('wall_sp_restore_all_confirm') : L('wall_sp_restore_all')}
			</Button>
			{#if armed}<Button small minimal onclick={() => (armed = false)}>{L('wall_sp_keep')}</Button>{/if}
			<span class="grow"></span>
			<Button
				small
				minimal
				icon="history"
				pressed={historyOpen}
				onclick={() => {
					historyOpen = !historyOpen;
					if (historyOpen) void ops.loadSignalHistory();
				}}
			>
				{L('wall_sp_history')}
			</Button>
		</div>
		{#if armed}<div class="reason"><Reason text={L('wall_sp_restore_all_armed')} /></div>{/if}

		{#if bandUnknown}
			<div class="band-pick" data-testid="gate-band-unknown">
				<Reason text={L('wall_sp_band_unknown')} />
				<div class="picks">
					{#each BANDS as b (b)}
						<Tooltip content={L('wall_sp_apply_band', L(`shell_band_word_${b}`))}>
							<button
								type="button"
								class="pick-band"
								data-testid="gate-apply-band"
								data-band={b}
								disabled={!ops.officerOn || ops.signalApplying}
								onclick={() => void ops.applyCityPlan(b)}
							>
								<BandChip band={b} size="sm" {lang} />
							</button>
						</Tooltip>
					{/each}
				</div>
			</div>
		{/if}

		{#if outcome}
			<div class="outcome" class:held={!outcome.applied} role="status" data-testid="gate-outcome" data-applied={outcome.applied ? '1' : '0'}>
				<div class="o-line">
					<span class="o-word">{outcome.applied ? L('wall_sp_applied') : L('wall_sp_held')}</span>
					{#if !outcome.applied && outcome.refusalReason}<span class="ell">{ops.text(outcome.refusalReason)}</span>{/if}
					<span class="grow"></span>
					<span class="muted tn">{fmtTime(outcome.at, { seconds: true })} · {outcome.status}</span>
				</div>
				{#if !outcome.applied && outcome.detail}
					<button type="button" class="o-toggle" aria-expanded={detailOpen} onclick={() => (detailOpen = !detailOpen)}>
						{detailOpen ? L('wall_sp_hide_report') : L('wall_sp_show_report')}
					</button>
					{#if detailOpen}<pre class="o-detail">{JSON.stringify(ops.detail(outcome.detail), null, 2)}</pre>{/if}
				{/if}
			</div>
		{/if}

		{#if historyOpen}
			<div class="history" data-testid="gate-history">
				{#if ops.signalHistory.length === 0}
					<p class="muted small">{ops.signalHistoryNote ?? L('wall_sp_history_empty')}</p>
				{:else}
					<table class="wdt">
						<colgroup><col style:width="76px" /><col style:width="76px" /><col /><col /></colgroup>
						<tbody>
							{#each ops.signalHistory as h (h.historyId)}
								<tr>
									<td><div class="c tn">{h.capturedAt ? fmtTime(h.capturedAt) : '—'}</div></td>
									<td><div class="c">{L(`wall_sp_hist_${h.kind}`) === `wall_sp_hist_${h.kind}` ? h.kind : L(`wall_sp_hist_${h.kind}`)}</div></td>
									<td><div class="c"><span class="ell">J{h.junctionId ?? '—'}{ops.junctionName(h.junctionId) ? ` ${ops.junctionName(h.junctionId)}` : ''}</span></div></td>
									<td><div class="c"><span class="ell muted" title={h.reason ? ops.text(h.reason) : undefined}>{h.actor ?? L('wall_sp_unattributed')}</span></div></td>
								</tr>
							{/each}
						</tbody>
					</table>
				{/if}
			</div>
		{/if}
	{:else}
		<p class="empty muted">{ops.signalPlansNote ?? L('wall_sp_waiting')}</p>
	{/if}
</Section>

<style>
	.gate {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		padding: 8px 16px 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: 16px;
		white-space: nowrap;
	}

	.sep {
		width: 1px;
		height: 12px;
		background: var(--v-line-2);
	}

	.actions {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 8px;
		padding: 8px 16px 12px;
	}

	.reason {
		padding: 0 16px 10px;
	}

	.grow {
		flex: 1 1 auto;
	}

	.ell {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.muted {
		color: var(--v-ink-2);
	}

	.small {
		margin: 0;
		font-size: var(--v-text-xs);
	}

	.tn {
		font-variant-numeric: tabular-nums;
	}

	/* a narrow column wraps its header onto a second line rather than cutting it */
	.plans th {
		white-space: normal;
		line-height: 14px;
		text-overflow: clip;
	}

	.band-pick {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 0 16px 12px;
	}

	.picks {
		display: flex;
		gap: 6px;
	}

	.pick-band {
		display: inline-flex;
		padding: 2px;
		border: 1px solid var(--v-line-2);
		border-radius: var(--v-radius-btn);
		background: transparent;
		cursor: pointer;
	}

	.pick-band:disabled {
		cursor: not-allowed;
		opacity: 0.5;
	}

	.outcome {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 0 16px 12px;
		padding: 8px 12px;
		border-radius: var(--v-radius-panel);
		box-shadow: inset 0 0 0 1px var(--v-line-2);
		font-size: var(--v-text-xs);
	}

	.outcome.held {
		box-shadow:
			inset 0 0 0 1px var(--v-line-2),
			inset 2px 0 0 var(--v-ink-2);
	}

	.o-line {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}

	.o-word {
		font-weight: 600;
		white-space: nowrap;
	}

	.o-toggle {
		align-self: flex-start;
		padding: 0;
		border: 0;
		background: transparent;
		color: var(--v-primary-text);
		font: inherit;
		cursor: pointer;
	}

	.o-detail {
		max-height: 200px;
		margin: 0;
		overflow: auto;
		color: var(--v-ink-2);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		white-space: pre-wrap;
	}

	.history {
		padding: 0 0 8px;
		border-top: 1px solid var(--v-line-1);
	}

	.history p {
		padding: 8px 16px;
	}

	.empty {
		margin: 0;
		padding: 12px 16px;
		font-size: var(--v-text-xs);
	}
</style>
