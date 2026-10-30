<script lang="ts">
	/**
	 * Scenario emulator (contract C-G; ownership UI-S5B), inside the /ops Lab
	 * and system section, through the deck's same-origin /api/emulator proxy.
	 * Every cause it injects is emulated and labelled so; the decision stack
	 * plans, classifies and shadow-evaluates on its own. Behaviour unchanged:
	 *
	 *   · the library is the emulator's own (GET /use-cases, all ten tapes,
	 *     `emu-library-count`), not the deck's fixture list;
	 *   · Launch is async: C-G answers 202 {run_id} and the run's progress is
	 *     followed (`emu-launch-state` data-phase / data-run-id / data-contract,
	 *     a determinate progressbar); an older build that holds the POST is
	 *     never awaited: its run is found in the ledger and followed the same way;
	 *   · flagship tapes are capped at ×10 (`emu-clock` marks the faster clock
	 *     disabled) and the engine's effective sampling is stated (`emu-sampling`);
	 *   · Stop and Replay on each run row (`emu-run` data-run-id / data-status);
	 *     a run whose corridor event is still planning says so
	 *     (`emu-event-pending`); a failed run shows the emulator's own reason;
	 *   · the living city's status, slots and counters, with Start / Stop
	 *     (`living-city` data-supported / data-status, `living-city-toggle`),
	 *     only when the build's /health says it serves it;
	 *   · a stolen-vehicle sweep's scenario premise (C-N) shows on its run,
	 *     the FIR-named mark masked without an officer.
	 */
	import { Button, HTMLSelect, Id, ProgressBar, ProvenanceTag, Tag } from '$lib/ui';
	import { fmtTime } from '$lib/ui/format/format';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';
	import { tOps } from '$lib/i18n/strings.ops';
	import { ops } from '$lib/ops/store.svelte';
	import { EMULATOR_CLOCKS, EMULATOR_HERO_CLOCK_CAP } from '$lib/ops/endpoints';
	import { FLAGSHIP_USE_CASE } from '$lib/ops/usecases';
	import { fmtAgeSince, samplingOf } from '$lib/ops/format';
	import type { EmulatorRunPremise, EmulatorRunRow } from '$lib/ops/types';

	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	// the library's flagship until the emulator's own list answers (then its first tape if this one is missing)
	let useCase = $state(FLAGSHIP_USE_CASE?.id ?? 'vvip_convoy_base');
	let clockChoice = $state('10');
	let replayClock = $state('10');

	let clock = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (clock = Date.now()), 1000);
		return () => clearInterval(id);
	});

	const library = $derived(ops.emulatorLibrary);
	const info = $derived(ops.useCaseInfo(useCase));
	const hero = $derived(info?.hero === true);
	const chosenClock = $derived(Number(clockChoice) || 10);
	const effectiveClock = $derived(ops.launchClock(useCase, chosenClock));
	const sampling = $derived(samplingOf(effectiveClock));
	const inLibrary = $derived(library.some((u) => u.id === useCase));
	const launch = $derived(ops.emulatorLaunch);

	// the library answered and the chosen tape is not in it: pick its first tape
	$effect(() => {
		if (library.length && !library.some((u) => u.id === useCase)) useCase = library[0].id;
	});

	// a flagship tape never offers more than ×10
	$effect(() => {
		if (hero && chosenClock > EMULATOR_HERO_CLOCK_CAP) clockChoice = String(EMULATOR_HERO_CLOCK_CAP);
	});

	const useCaseOptions = $derived(
		library.length
			? library.map((u) => ({ value: u.id, label: `${u.name}${u.hero ? ` (${L('wall_emu_flagship')})` : ''}` }))
			: [{ value: useCase, label: L('wall_emu_library_waiting', useCase) }],
	);
	const clockOptions = $derived(
		EMULATOR_CLOCKS.map((c) => ({ value: String(c), label: `×${c}`, disabled: hero && c > EMULATOR_HERO_CLOCK_CAP })),
	);
	const replayOptions = EMULATOR_CLOCKS.map((c) => ({ value: String(c), label: `×${c}` }));

	function phaseIntent(phase: string): 'none' | 'success' {
		return phase === 'completed' ? 'success' : 'none';
	}

	function progress(r: EmulatorRunRow | null | undefined): number | null {
		const p = r?.progress;
		if (!p || !p.total) return null;
		return Math.max(0, Math.min(1, p.frame / p.total));
	}

	const trackedRun = $derived(launch?.runId != null ? (ops.emulatorRuns.find((r) => r.runId === launch.runId) ?? null) : null);
	const lc = $derived(ops.livingCity);

	/** One scenario-premise entry as this console may print it (C-N): the FIR-named mark masked without an officer. */
	function premiseText(p: EmulatorRunPremise): string {
		const plate = ops.plate(p.plate) ?? '—';
		const text =
			p.result === 'delivered'
				? tOps(lang, p.earmark === 'created' ? 'emuPremise_created' : 'emuPremise_already_active', plate, p.firRef)
				: p.result === 'failed'
					? tOps(lang, 'emuPremise_failed', plate, p.reason ? ops.text(p.reason) : null)
					: tOps(lang, 'emuPremise_skipped', plate);
		return `${tOps(lang, 'emuPremiseTitle')}: ${text}`;
	}

	function runStatus(r: EmulatorRunRow): string {
		const key = `emuPhase_${r.status}`;
		const w = tOps(lang, key);
		return w === key ? r.status : w;
	}
</script>

<div class="emu" data-wall="emulator">
	<div class="sub-head">
		<h3 class="h">{L('wall_emu')}</h3>
		<Tag intent={ops.emulator.online ? 'success' : 'none'} icon={ops.emulator.online ? undefined : 'offline'}>{ops.emulator.online ? L('wall_emu_online') : L('wall_emu_offline')}</Tag>
		<ProvenanceTag source="emulated" {lang} />
		<span class="grow"></span>
		<span class="muted tn" data-testid="emu-library-count" data-count={library.length}>{L('wall_emu_library', library.length)}</span>
		<Button minimal small icon="refresh" tooltip={L('wall_emu_check')} aria-label={L('wall_emu_check')} onclick={() => void ops.pollEmulator()} />
	</div>
	{#if ops.emulator.lastChecked && !ops.emulator.online}
		<p class="note">{(ops.emulator.healthDetail ?? L('wall_emu_unreachable')).slice(0, 120)}</p>
	{/if}

	<div class="launch" data-testid="emu-launch">
		<label class="field grow">
			<span class="lbl">{L('wall_emu_tape')}</span>
			<HTMLSelect small fill options={useCaseOptions} bind:value={useCase} data-testid="emu-use-case" />
		</label>
		<label class="field clock">
			<span class="lbl">{L('wall_emu_clock')}</span>
			<HTMLSelect small fill options={clockOptions} bind:value={clockChoice} data-testid="emu-clock" />
		</label>
		<Button
			small
			icon="play"
			disabled={!ops.emulator.online || !inLibrary || ops.emulatorBusy !== null}
			loading={ops.emulatorBusy === 'launch'}
			onclick={() => void ops.launchUseCase(useCase, chosenClock)}
			data-testid="emu-launch-btn"
		>
			{L('wall_emu_launch')}
		</Button>
	</div>
	<p class="note" data-testid="emu-sampling">
		{tOps(lang, 'emuSampling', effectiveClock, tOps(lang, 'emuSamplingNote', sampling.value, sampling.unit))}{#if hero}{` · ${L('wall_emu_hero_cap', EMULATOR_HERO_CLOCK_CAP)}`}{/if}
	</p>

	{#if launch}
		<div class="launch-state" data-testid="emu-launch-state" data-phase={launch.phase} data-run-id={launch.runId ?? ''} data-contract={launch.contract ?? ''}>
			<div class="ls-head">
				<Tag intent={phaseIntent(launch.phase)}>{tOps(lang, `emuPhase_${launch.phase}`)}</Tag>
				<span class="ell">{launch.kind === 'replay' ? L('wall_emu_replay_of') : ''}<Id value={launch.useCaseId} /> ×{launch.clockScale}{launch.runId != null ? ` · ${L('wall_emu_run', launch.runId)}` : ''}</span>
				<span class="grow"></span>
				<span class="muted tn">{fmtAgeSince(launch.at, clock)}</span>
			</div>
			{#if trackedRun?.progress}
				<ProgressBar value={progress(trackedRun)} stripes={false} label={L('wall_emu_progress')} />
				<p class="note tn">{tOps(lang, 'emuProgress', trackedRun.progress.frame, trackedRun.progress.total, trackedRun.progress.delivered, trackedRun.progress.failed)}</p>
			{/if}
			{#if trackedRun && trackedRun.status === 'running' && trackedRun.eventStatus === 'planning'}
				<p class="note" data-testid="emu-event-pending">{tOps(lang, 'emuEventNotLive')}</p>
			{/if}
			{#each trackedRun?.premises ?? [] as p, i (i)}
				<p class="note premise" data-testid="emu-premise" data-result={p.result} data-earmark={p.earmark ?? ''}>
					<ProvenanceTag source="emulated" compact {lang} /><span>{premiseText(p)}</span>
				</p>
			{/each}
			{#if trackedRun && (trackedRun.status === 'failed' || trackedRun.status === 'interrupted') && trackedRun.failReason}
				<p class="note strong" data-testid="emu-fail-reason">{tOps(lang, 'emuFailReason', trackedRun.failReason)}</p>
			{/if}
			{#if launch.detail}<p class="note">{launch.detail}</p>{/if}
			{#if launch.contract === 'sync' && launch.phase === 'running'}<p class="note">{tOps(lang, 'emuSyncNote')}</p>{/if}
		</div>
	{/if}
	{#if ops.emulatorActionNote}<p class="note">{ops.emulatorActionNote}</p>{/if}

	{#if ops.emulatorRuns.length}
		<div class="runs">
			<div class="runs-head">
				<span class="runs-title">{L('wall_emu_runs')}</span>
				<span class="grow"></span>
				<label class="replay-clock"><span class="lbl">{L('wall_emu_replay_at')}</span><HTMLSelect small minimal options={replayOptions} bind:value={replayClock} /></label>
			</div>
			<table class="wdt">
				<colgroup><col style:width="56px" /><col /><col style:width="96px" /><col style:width="44px" /><col style:width="72px" /><col style:width="80px" /></colgroup>
				<thead>
					<tr>
						<th scope="col" class="num">{L('wall_emu_col_run')}</th>
						<th scope="col">{L('wall_emu_tape')}</th>
						<th scope="col">{L('wall_emu_col_status')}</th>
						<th scope="col" class="num">×</th>
						<th scope="col" class="num">{L('wall_emu_col_started')}</th>
						<th aria-hidden="true"></th>
					</tr>
				</thead>
				<tbody>
					{#each ops.emulatorRuns as r (r.runId)}
						<tr data-testid="emu-run" data-run-id={r.runId} data-status={r.status}>
							<td class="num"><div class="c tn">{r.runId}{r.isReplay ? ' ↻' : ''}</div></td>
							<td><div class="c"><span class="ell" title={r.useCaseId}><Id value={r.useCaseId} /></span></div></td>
							<td>
								<div class="c" title={r.failReason ?? (r.status === 'running' && r.eventStatus === 'planning' ? tOps(lang, 'emuEventNotLive') : undefined)} data-event-status={r.eventStatus ?? ''}>
									<span class="ell">{runStatus(r)}{#if r.status === 'running' && progress(r) != null}{` ${Math.round((progress(r) ?? 0) * 100)}%`}{/if}</span>
								</div>
							</td>
							<td class="num"><div class="c tn">{r.clockScale ?? '—'}</div></td>
							<td class="num"><div class="c tn">{r.createdAt ? fmtTime(r.createdAt) : '—'}</div></td>
							<td class="num">
								<div class="c">
									{#if r.status === 'running'}
										<Button small minimal disabled={ops.emulatorBusy !== null} loading={ops.emulatorBusy === `stop:${r.runId}`} onclick={() => void ops.stopRun(r.runId)} data-testid="emu-stop">
											{tOps(lang, 'emuStop')}
										</Button>
									{:else}
										<Button
											small
											minimal
											disabled={ops.emulatorBusy !== null || !ops.emulator.online}
											loading={ops.emulatorBusy === `replay:${r.runId}`}
											onclick={() => void ops.replayRun(r.runId, Number(replayClock) || 10)}
											data-testid="emu-replay"
										>
											{tOps(lang, 'emuReplay')}
										</Button>
									{/if}
								</div>
							</td>
						</tr>
						{#if r.premises?.length}
							<tr class="detail" data-testid="emu-run-premise" data-run-id={r.runId}>
								<td></td>
								<td colspan="5">
									{#each r.premises as p, i (i)}
										<span class="premise" data-result={p.result} data-earmark={p.earmark ?? ''}>{premiseText(p)}</span>
									{/each}
								</td>
							</tr>
						{/if}
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	<section class="living" data-testid="living-city" data-supported={ops.emulator.livingCitySupported ? '1' : '0'} data-status={lc?.status ?? ''}>
		<div class="sub-head">
			<h3 class="h">{L('wall_emu_living')}</h3>
			{#if ops.emulator.livingCitySupported && lc}
				<Tag intent={lc.status === 'running' ? 'success' : 'none'}>{L(`wall_emu_living_${lc.status === 'running' ? 'running' : 'stopped'}`)}</Tag>
				<span class="grow"></span>
				<Button small loading={ops.livingCityBusy} onclick={() => void ops.setLivingCity(lc.status === 'running' ? 'stop' : 'start')} data-testid="living-city-toggle">
					{lc.status === 'running' ? tOps(lang, 'emuLivingStop') : tOps(lang, 'emuLivingStart')}
				</Button>
			{:else}
				<span class="muted">{ops.emulator.online ? L('wall_emu_living_absent') : L('wall_emu_offline')}</span>
			{/if}
		</div>
		{#if lc}
			<p class="note tn">
				{lc.dateIst ?? '—'}{lc.daySeed != null ? ` · ${L('wall_emu_seed', lc.daySeed)}` : ''}{` · ${tOps(lang, 'emuLivingSlots', lc.activeSlots.length)}`}{lc.units.length ? ` · ${tOps(lang, 'emuLivingUnits', lc.units.length)}` : ''}
			</p>
			{#if lc.activeSlots.length}
				<ul class="slots">
					{#each lc.activeSlots.slice(0, 4) as s (s.slotId)}
						<li data-slot-status={s.eventStatus ?? ''}>
							<span class="ell">{ops.text(s.title)}</span>
							<span class="muted tn">{s.startsAt ? fmtTime(s.startsAt) : '—'}–{s.endsAt ? fmtTime(s.endsAt) : '—'}</span>
							{#if s.eventStatus}<span class="muted">{s.eventStatus === 'planning' ? tOps(lang, 'emuEventPendingShort') : s.eventStatus}</span>{/if}
						</li>
					{/each}
				</ul>
			{/if}
			{#if lc.counters && Object.keys(lc.counters).length}
				<p class="note" data-testid="living-city-counters">
					{Object.entries(lc.counters).slice(0, 6).map(([k, n]) => `${k.replace(/_/g, ' ')} ${n}`).join(', ')}{lc.preempted ? `, ${tOps(lang, 'emuLivingPreempted', lc.preempted)}` : ''}{lc.refiling ? `, ${tOps(lang, 'emuLivingRefiling', lc.refiling)}` : ''}{lc.violators === false ? `, ${tOps(lang, 'emuLivingNoViolators')}` : ''}
				</p>
			{/if}
			{#if lc.detail}<p class="note">{lc.detail}</p>{/if}
			{#if lc.nextCauses.length}
				<p class="note">{tOps(lang, 'emuLivingNext')}: {ops.text(lc.nextCauses.slice(0, 2).map((c) => `${c.at ? fmtTime(c.at) : '—'} ${c.title}`).join(', '))}</p>
			{/if}
		{/if}
		{#if ops.livingCityNote}<p class="note strong">{ops.livingCityNote}</p>{/if}
	</section>

	<p class="note rule">{L('wall_emu_causes_only')}</p>
</div>

<style>
	.emu {
		display: flex;
		flex-direction: column;
		gap: 8px;
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
		min-width: 0;
	}

	.muted {
		color: var(--v-ink-2);
	}

	.tn {
		font-variant-numeric: tabular-nums;
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
		overflow-wrap: anywhere;
	}

	.note.strong {
		color: var(--v-ink-1);
	}

	.note.rule {
		padding-top: 4px;
	}

	.launch {
		display: flex;
		align-items: flex-end;
		gap: 8px;
		padding: 0 16px;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}

	.field.grow {
		flex: 1 1 auto;
	}

	.field.clock {
		flex: 0 0 80px;
	}

	.lbl {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.launch-state {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0 16px;
		padding: 8px 0 0;
		border-top: 1px solid var(--v-line-1);
	}

	.launch-state .note {
		padding: 0;
	}

	.ls-head {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}

	.premise {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.runs {
		display: flex;
		flex-direction: column;
	}

	.runs-head {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 4px 8px 4px 16px;
	}

	.runs-title {
		font-weight: 600;
	}

	.replay-clock {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}

	.living {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding-top: 4px;
		border-top: 1px solid var(--v-line-1);
	}

	.slots {
		display: flex;
		flex-direction: column;
		gap: 2px;
		margin: 0;
		padding: 0 16px;
		list-style: none;
	}

	.slots li {
		display: flex;
		align-items: baseline;
		gap: 8px;
		min-width: 0;
	}
</style>
