<script lang="ts">
	/**
	 * The pursuit plan (SPEC §5.3 ObjectInspector "Pursuit section", §5.4
	 * "the pursuit plan follows the vehicle"; review B8; prototype
	 * ui-core.js pursuitSection). The core of the inspector's Pursuit
	 * section (PursuitSection, for a vehicle with an open pursuit and for the
	 * pursuit event) and of the legacy PursuitPanel wrapper.
	 *
	 *   - who opened it and when, the anchor road, the heading and its basis;
	 *   - the last read (`pursuit-sighting[data-stale]`, stale after the
	 *     plan's staleAfterSec, 600 s): the masked mark, the time, the camera;
	 *   - the direction flag (`pursuit-direction[data-basis][data-against]`):
	 *     a vehicle read driving AGAINST a one-way is projected as the camera
	 *     saw it, and the section says so;
	 *   - the ranked chokes (`pursuit-choke[data-rank][data-junction]
	 *     [data-likely-passed]`): ETA, hold cost, signal control, "likely
	 *     passed" dimmed, and "Request unit" (`pursuit-request-unit`), which
	 *     opens the dispatch request with the waypoint pre-filled — disabled
	 *     until an officer is named and the event is open, with the reason
	 *     as a line under the list (`pursuit-request-reason`), not only as a
	 *     tooltip.
	 *
	 * The plan is the store's `ops.interception` for this pursuit (loaded and
	 * polled every 6 s while the vehicle or the pursuit event is selected).
	 * When the operator has since picked another pursuit, the store follows
	 * that one (the most recent intent wins) and this section says so, with
	 * "Show this plan" to follow this pursuit again. It assists the
	 * operator; it never dispatches on its own.
	 */
	import { ops, isLivePursuit } from '$lib/ops/store.svelte';
	import { INTENT_ICON, eventKindIcon, kindIcon } from '$lib/design/icons';
	import { Button, Icon, Id, Note, Plate, Reason, Tag } from '$lib/ui';
	import { fmtAgo, fmtDuration, fmtStamp } from '$lib/ui/format/format';
	import { compass } from '$lib/workspace/kinds/common';
	import { useShellClock, shellClock } from '$lib/shell/clock.svelte';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.decisions';
	import { displayActor } from '$lib/workspace/display';
	import RequestUnit from './RequestUnit.svelte';

	let {
		eventId = null,
		vehicleId = null,
		lang = ops.lang,
		testid = 'pursuit-section',
	}: { eventId?: string | null; vehicleId?: string | null; lang?: string; testid?: string } = $props();

	$effect(() => useShellClock());
	const now = $derived(shellClock.now);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	const ev = $derived(eventId ? ops.eventById(eventId) : vehicleId ? ops.pursuitFor(vehicleId) : null);
	const vid = $derived(vehicleId ?? ev?.metadata?.vehicleId ?? null);
	const plan = $derived(ev && ops.interception && ops.interception.eventId === ev.eventId ? ops.interception : null);
	const open = $derived(!!ev && isLivePursuit(ev) && ev.state !== 'completed' && ev.state !== 'cancelled');

	/** Who opened it: the creation note's officer ("Opened by … from …"), else the approval it cites. */
	const openedBy = $derived.by(() => {
		if (!ev) return null;
		const m = /^Opened by (.+?) from /.exec(ev.description ?? '');
		if (m) return m[1];
		const rec = ev.metadata?.recommendationId ? ops.approvedRecommendations.find((r) => r.recommendationId === ev.metadata?.recommendationId) : null;
		return rec?.decidedBy ?? null;
	});
	const since = $derived(ev ? (ev.phases[0]?.startTime ?? ev.windowStart) : null);
	const seed = $derived(plan?.seedSegmentId ?? ev?.routeSegmentIds[0] ?? null);
	const anchorRoad = $derived(seed != null ? (ops.roadName(seed) ?? `#${seed}`) : null);
	const read = $derived(plan?.latestSighting ?? null);
	const readMs = $derived(read?.t ? Date.parse(read.t) : NaN);
	const staleAfter = $derived(plan?.staleAfterSec ?? 600);
	const stale = $derived(!!plan && (plan.stale === true || (Number.isFinite(readMs) && (now - readMs) / 1000 > staleAfter)));
	const heading = $derived(read?.heading != null ? compass(read.heading, lang) : null);
	const basis = $derived(plan?.direction?.basis ?? null);
	const against = $derived(plan?.direction?.againstOneway === true);
	/** The store follows another pursuit's plan now (a later pick): offer to show this one. */
	const elsewhere = $derived(!!ev && !plan && open && !!ops.planEventId && ops.planEventId !== ev.eventId);

	const chokes = $derived(
		(plan?.chokes ?? []).map((c) => ({
			junctionId: c.junctionId,
			rank: c.rank,
			name: c.name ?? ops.junctionName(c.junctionId) ?? `J${c.junctionId}`,
			likelyPassed: c.likelyPassed === true,
			etaSec: c.graphCostSec != null ? Math.round(c.graphCostSec) : null,
			// hold cost = the choke score as a percentage (the honest proxy; the old panel's rule)
			hold: c.score != null && c.chokeWeight != null ? (c.score * 100).toFixed(1) : null,
			signal: c.signalControl === true,
			downstream: c.downstream === true,
		})),
	);

	let requestAt = $state<number | null>(null);

	/** Why no choke can be requested right now (no officer, or the event is closed), else null. */
	const commonBlock = $derived(!ops.officerOn ? L('dec_reason_officer_request') : !open ? L('dec_refuse_event_closed') : null);

	function chokeBlock(c: { likelyPassed: boolean }): string | null {
		if (commonBlock) return commonBlock;
		if (c.likelyPassed) return L('dec_reason_passed');
		return null;
	}

	function chokeLine(c: (typeof chokes)[number]): string {
		return [
			c.etaSec != null ? L('dec_eta_s', c.etaSec) : L('dec_eta_none'),
			c.hold != null ? L('dec_hold', c.hold) : null,
			c.signal ? L('dec_signal_controlled') : null,
			c.downstream ? L('dec_downstream') : null,
			c.likelyPassed ? L('dec_likely_passed') : null,
		]
			.filter(Boolean)
			.join(' · ');
	}

	function showThisPlan() {
		if (!ev) return;
		if (vehicleId) ops.followVehicle(vehicleId);
		else ops.selectEvent(ev.eventId);
	}
</script>

{#if ev}
	<section class="pursuit" data-testid={testid} data-event-id={ev.eventId} data-vehicle-id={vid ?? ''}>
		<div class="head">
			<Icon name={eventKindIcon('vehicle_pursuit')} size={16} />
			<span class="title">{L('dec_pursuit')}</span>
			<Tag intent={open ? 'primary' : 'none'}>{open ? L('dec_pursuit_open') : L(`dec_pursuit_state_${ev.state}`)}</Tag>
			{#if since || openedBy}
				<!-- F-19: the officer as a person, never with the demo scenario's name after it -->
				<span class="sub">{[since ? L('dec_since', fmtStamp(since, now)) : null, openedBy ? ops.text(displayActor(openedBy, lang)) : null].filter(Boolean).join(' · ')}</span>
			{/if}
		</div>

		<div class="facts">
			{#if anchorRoad}<span><span class="k">{L('dec_anchor')}</span> {anchorRoad}</span>{/if}
			{#if heading || basis}
				<span data-testid="pursuit-direction" data-basis={basis ?? ''} data-against={against ? '1' : '0'}><span class="k">{L('dec_heading_k')}</span> {heading ?? '—'}{#if basis}{' '}<span class="k">· {L(`dec_basis_${basis}`) !== `dec_basis_${basis}` ? L(`dec_basis_${basis}`) : basis}</span>{/if}</span>
			{/if}
			{#if against}
				<span class="against" data-testid="pursuit-against-oneway"><Tag intent="warning" icon={INTENT_ICON.warning}>{L('dec_against_oneway_tag')}</Tag> {L('dec_against_oneway')}</span>
			{/if}
		</div>

		{#if plan && read}
			<div class="read" data-testid="pursuit-sighting" data-stale={stale ? '1' : '0'}>
				<span class="k">{L('dec_last_read')}</span>{' '}
				<Plate mark={ops.plate(read.plate) ?? '—'} masked={!ops.officerOn} />{' '}
				<span>{read.t ? `${fmtStamp(read.t, now, { seconds: true })} IST` : '—'}</span>
				{#if read.cameraId}{' '}<span class="k">{L('dec_at')}</span>{' '}<Id value={read.cameraId} />{/if}
				{#if read.t}{' '}<span class="k">· {fmtAgo(read.t, now, lang)}</span>{/if}
				{#if read.speedKmh != null}{' '}<span class="k">· {L('dec_kmh', Math.round(read.speedKmh))}</span>{/if}
			</div>
			{#if stale}
				<div class="stale"><Note icon="time" text={L('dec_stale', fmtDuration(staleAfter, lang))} data-testid="pursuit-stale" /></div>
			{/if}

			{#if chokes.length}
				<div class="cap">{L('dec_chokes_ranked')}</div>
				<ol class="chokes">
					{#each chokes as c (c.junctionId)}
						{@const block = chokeBlock(c)}
						<li
							class="choke"
							class:passed={c.likelyPassed}
							data-testid="pursuit-choke"
							data-rank={c.rank}
							data-junction={c.junctionId}
							data-likely-passed={c.likelyPassed ? '1' : '0'}
						>
							<span class="rk">{c.rank}</span>
							<span class="nm">
								<span class="nm1" title={c.name}>{c.name}</span>
								<span class="nm2" data-testid="pursuit-choke-line">{chokeLine(c)}</span>
							</span>
							<Button
								small
								minimal={!!block}
								data-testid="pursuit-request-unit"
								icon={kindIcon('dispatch')}
								disabled={!!block}
								disabledReason={block}
								pressed={requestAt === c.junctionId ? true : undefined}
								onclick={() => (requestAt = requestAt === c.junctionId ? null : c.junctionId)}
							>
								{L('dec_btn_request_unit')}
							</Button>
						</li>
						{#if requestAt === c.junctionId && !block}
							<li class="form-row">
								<RequestUnit eventId={ev.eventId} vehicleId={vid} {chokes} junctionId={c.junctionId} {open} {lang} onclose={() => (requestAt = null)} />
							</li>
						{/if}
					{/each}
				</ol>
				{#if commonBlock}
					<div class="why"><Reason text={commonBlock} data-testid="pursuit-request-reason" /></div>
				{/if}
			{:else}
				<p class="empty">{L('dec_no_chokes')}</p>
			{/if}
			<!-- F-17: the plan's standing note in this console's words — never the oracle's English with an
			     internal contract code ("(C6)"); staleness and a one-way read have their own lines above -->
			<p class="cap foot" data-testid="pursuit-plan-note">{L('dec_plan_note')}</p>
		{:else if elsewhere}
			<div class="elsewhere" data-testid="pursuit-plan-elsewhere">
				<span>{L('dec_plan_elsewhere')}</span>
				<Button small onclick={showThisPlan}>{L('dec_btn_show_plan')}</Button>
			</div>
		{:else}
			<p class="empty">{ops.interceptionNote ?? (open ? L('dec_plan_loading') : L('dec_plan_none'))}</p>
		{/if}
	</section>
{/if}

<style>
	.pursuit {
		margin: 0;
		padding: 0 0 8px;
		border-bottom: 1px solid var(--v-line-2);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.head {
		display: flex;
		align-items: center;
		gap: 8px;
		min-height: 40px;
		padding: 0 12px 0 16px;
	}

	.head :global(svg) {
		color: var(--v-ink-2);
		flex: 0 0 auto;
	}

	.title {
		font-size: var(--v-text-base);
		font-weight: 600;
		white-space: nowrap;
	}

	.sub {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.facts,
	.read {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 4px 16px;
		padding: 0 16px 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.read {
		gap: 4px 6px;
	}

	.k {
		color: var(--v-ink-2);
	}

	.stale {
		padding: 0 16px 8px;
	}

	.against {
		display: inline-flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
		color: var(--v-ink-2);
	}

	.why {
		padding: 8px 16px 0;
		border-top: 1px solid var(--v-line-1);
	}

	.elsewhere {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
		padding: 0 16px 8px;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.cap {
		padding: 4px 16px 6px;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.cap.foot {
		padding-top: 8px;
	}

	.chokes {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.choke {
		display: grid;
		grid-template-columns: 24px minmax(0, 1fr) auto;
		gap: 8px;
		align-items: center;
		min-height: 44px;
		padding: 4px 16px;
		border-top: 1px solid var(--v-line-1);
		font-size: var(--v-text-xs);
	}

	.rk {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 20px;
		height: 20px;
		border-radius: 50%;
		background: var(--v-surface-3);
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}

	.choke.passed {
		color: var(--v-ink-2);
	}

	.choke.passed .rk {
		background: transparent;
		box-shadow: inset 0 0 0 1px var(--v-line-2);
	}

	.nm {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.nm1 {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: var(--v-text-sm);
		color: var(--v-ink-1);
	}

	.choke.passed .nm1 {
		color: var(--v-ink-2);
	}

	.nm2 {
		color: var(--v-ink-2);
		font-variant-numeric: tabular-nums;
		overflow-wrap: anywhere;
	}

	.form-row {
		list-style: none;
	}

	.empty {
		margin: 0;
		padding: 0 16px 8px;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}
</style>
