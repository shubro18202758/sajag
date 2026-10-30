<script lang="ts">
	/**
	 * Twin comparison (ownership UI-S5B), inside the /ops Lab and system
	 * section: a candidate closure policy against a scenario's baseline on the
	 * seeded corridor twin. Behaviour unchanged (POST /simulate/twin/compare,
	 * the labelled two-arm fallback when the compare endpoint is not deployed,
	 * cached per scenario, policies and seed, run only on the operator's
	 * demand). The form opens as a popover (SPEC §6.3: create forms are
	 * popover forms); the result is a table, candidate minus baseline per
	 * metric, lower is better.
	 */
	import { Button, FormGroup, HTMLSelect, Input, NonIdealState, Popover, Tag } from '$lib/ui';
	import { fmtTime } from '$lib/ui/format/format';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';
	import { ops } from '$lib/ops/store.svelte';
	import { USE_CASES, useCaseById } from '$lib/ops/usecases';
	import type { ClosureType } from '$lib/ops/types';

	const CLOSURE_TYPES: ClosureType[] = ['full_closure', 'partial_closure', 'signal_hold'];

	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	let scenario = $state(ops.twinScenarioId);
	let advance = $state(String(ops.twinCandidate.advanceClosureSec));
	let closure = $state<string>(ops.twinCandidate.closureType);

	// the store holds the candidate the comparison runs with
	$effect(() => {
		ops.twinScenarioId = scenario;
		ops.twinCandidate = { advanceClosureSec: Math.max(0, Math.min(1800, Math.round(Number(advance) || 0))), closureType: closure as ClosureType };
	});

	const useCase = $derived(useCaseById(scenario));
	const baseline = $derived(useCase?.baselinePolicy ?? null);
	const cached = $derived(ops.twinCachedKey === ops.twinCacheKey() && ops.twinResult !== null);
	const result = $derived(ops.twinResult);

	const METRICS: ReadonlyArray<{ key: string; label: string }> = [
		{ key: 'disruptionVehicleHours', label: 'wall_twin_m_disruption' },
		{ key: 'maxQueueLengthM', label: 'wall_twin_m_queue' },
		{ key: 'avgClosureDurationSec', label: 'wall_twin_m_closure' },
		{ key: 'transitTimeSec', label: 'wall_twin_m_transit' },
		{ key: 'recoverySec', label: 'wall_twin_m_recovery' },
		{ key: 'ambulanceDelaySec', label: 'wall_twin_m_ambulance' },
	];

	function fmt(n: number | null | undefined): string {
		return n == null || !Number.isFinite(n) ? '—' : n.toFixed(1);
	}

	function delta(v: number | null | undefined): { text: string; cls: string } {
		if (v == null || !Number.isFinite(v)) return { text: '—', cls: '' };
		return { text: `${v > 0 ? '+' : ''}${v.toFixed(1)}`, cls: v === 0 ? '' : v < 0 ? 'better' : 'worse' };
	}

	function metricOf(arm: { metrics: object } | null | undefined, key: string): number | null {
		const v = arm ? (arm.metrics as Record<string, unknown>)[key] : null;
		return typeof v === 'number' ? v : null;
	}

	const scenarioOptions = USE_CASES.map((u) => ({ value: u.scenarioId, label: u.name }));
	const closureOptions = $derived(CLOSURE_TYPES.map((c) => ({ value: c, label: L(`wall_closure_${c}`) })));
</script>

<div class="twin" data-wall="twin">
	<div class="sub-head">
		<h3 class="h">{L('wall_twin')}</h3>
		{#if result}
			<Tag tooltip={result.source === 'compare-endpoint' ? null : L('wall_twin_two_arm_tip')}>{result.source === 'compare-endpoint' ? L('wall_twin_compare') : L('wall_twin_two_arm')}</Tag>
		{/if}
		<span class="grow"></span>
		<Popover placement="bottom-end">
			<Button small icon="git-merge" loading={ops.twinRunning}>{L('wall_twin_open')}</Button>
			{#snippet content({ close })}
				<form
					class="form"
					onsubmit={(e) => {
						e.preventDefault();
						void ops.runTwinCompare(true);
						close();
					}}
				>
					<div class="f-head">{L('wall_twin')}</div>
					<FormGroup label={L('wall_twin_scenario')}>
						<HTMLSelect small fill options={scenarioOptions} bind:value={scenario} />
					</FormGroup>
					<div class="f-row">
						<FormGroup label={L('wall_twin_advance')}>
							<Input small fill type="number" min="0" max="1800" step="10" bind:value={advance} />
						</FormGroup>
						<FormGroup label={L('wall_twin_closure')}>
							<HTMLSelect small fill options={closureOptions} bind:value={closure} />
						</FormGroup>
					</div>
					{#if baseline}
						<p class="f-note">{L('wall_twin_baseline_line', baseline.advanceClosureSec, L(`wall_closure_${baseline.closureType}`))}</p>
					{/if}
					<div class="f-foot">
						<Button small onclick={close}>{L('wall_cancel')}</Button>
						<Button small intent="primary" type="submit" loading={ops.twinRunning}>{L('wall_twin_run')}</Button>
					</div>
				</form>
			{/snippet}
		</Popover>
	</div>

	{#if ops.twinError}<p class="note strong">{ops.twinError}</p>{/if}

	{#if result}
		<table class="wdt">
			<colgroup><col /><col style:width="76px" /><col style:width="76px" /><col style:width="64px" /></colgroup>
			<thead>
				<tr>
					<th scope="col">{L('wall_twin_metric')}</th>
					<th scope="col" class="num">{L('wall_twin_baseline')}</th>
					<th scope="col" class="num">{L('wall_twin_candidate')}</th>
					<th scope="col" class="num">{L('wall_twin_delta')}</th>
				</tr>
			</thead>
			<tbody>
				{#each METRICS as m (m.key)}
					{@const d = delta(result.deltas[m.key])}
					<tr>
						<td><div class="c"><span class="ell">{L(m.label)}</span></div></td>
						<td class="num"><div class="c">{fmt(metricOf(result.baseline, m.key))}</div></td>
						<td class="num"><div class="c">{fmt(metricOf(result.candidate, m.key))}</div></td>
						<td class="num"><div class="c"><span class={d.cls}>{d.text}</span></div></td>
					</tr>
				{/each}
			</tbody>
		</table>
		<p class="note tn">
			{#if result.calibrated != null}{result.calibrated ? L('wall_twin_calibrated') : L('wall_twin_uncalibrated')}{' · '}{/if}{cached ? L('wall_twin_cached', fmtTime(result.fetchedAt)) : L('wall_twin_ran', fmtTime(result.fetchedAt))}
		</p>
	{:else if !ops.twinRunning}
		<div class="empty"><NonIdealState icon="git-merge" iconSize={20} layout="horizontal" description={L('wall_twin_none')} /></div>
	{/if}
</div>

<style>
	.twin {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 8px 0 12px;
		border-bottom: 1px solid var(--v-line-1);
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.sub-head {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		min-height: 28px;
		padding: 0 8px 0 16px;
	}

	.h {
		margin: 0;
		font-size: var(--v-text-base);
		font-weight: 600;
		line-height: 18px;
		white-space: nowrap;
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

	.note {
		margin: 0;
		padding: 0 16px;
		color: var(--v-ink-2);
	}

	.note.strong {
		color: var(--v-ink-1);
	}

	.tn {
		font-variant-numeric: tabular-nums;
	}

	/* a change is marked by weight, never by hue (SPEC §2.4: colour is for
	   states that ask for action); the sign says which way, the header says
	   lower is better */
	.better,
	.worse {
		color: var(--v-ink-1);
		font-weight: 600;
	}

	.empty {
		padding: 0 16px;
	}

	.form {
		display: flex;
		flex-direction: column;
		gap: 4px;
		width: 340px;
		padding: 12px 16px;
	}

	.f-head {
		margin-bottom: 4px;
		font-weight: 600;
	}

	.f-row {
		display: grid;
		grid-template-columns: 104px minmax(0, 1fr);
		gap: 8px;
	}

	.f-note {
		margin: 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.f-foot {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
		margin-top: 8px;
	}
</style>
