<script lang="ts">
	/**
	 * PlanPanel (SPEC §5.3 PlanPanel [S6], §6.1) — the left dock's "Plan" tab
	 * (`[data-rail=plan]`), the corridor's planning surface. The REAL Blue
	 * Book lifecycle on the live two-tier brain, through the shared escort
	 * lifecycle (corridor/escort-planState.svelte.ts):
	 *
	 *   inputs       From / To (`planner-origin`, `planner-destination`), the
	 *                class pills (`.class-pill`), a departure `TimeField`
	 *                (IST), the rehearsal label (`planner-label`), the duty
	 *                officer (`planner-officer`) and Plan corridor (primary,
	 *                never wraps)
	 *   states       all in `planner-status`:
	 *                · Approved — "Security compliant";
	 *                · CONDITIONAL — the lane-floor violations listed, the
	 *                  waiver (`planner-waiver`) stamped with the officer;
	 *                  LAUNCH locked until the waiver is accepted AND an
	 *                  officer is named, the inline Reason saying which;
	 *                · HOLD — `planner-hold` "Re-plan after hh:mm"; Launch
	 *                  locked;
	 *                · NO ROUTE — Launch hidden; the reason and the next
	 *                  action shown;
	 *   candidates   `planner-candidates` of `planner-candidate` (rank;
	 *                primary or alternate; "adds <roads>"; figures only for
	 *                what the plan reports)
	 *   escort       Launch (criteria and Reason), Stop, Clear
	 *                (`planner-clear`, `planner-clear-outcome`)
	 *   proposal     `planner-proposal` is a LINK ROW to the Movement tab —
	 *                the escort proposal is never decided here
	 *
	 * Ethics (§9.1): the officer field's helper says exactly what naming an
	 * officer does. The AI or a rule proposes; a named officer decides.
	 */
	import { onDestroy } from 'svelte';
	import { Button, Checkbox, FormGroup, Icon, Input, NonIdealState, Reason, Tag, TimeField, Tooltip, provideUiLang } from '$lib/ui';
	import { fmtStamp, istTimeToMs } from '$lib/ui/format/format';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { t } from '$lib/i18n/strings';
	import { tOps } from '$lib/i18n/strings.ops';
	import '$lib/i18n/packs.corridor';
	import { ops } from '$lib/ops/store.svelte';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { PLAN_POIS, escortLifecycle } from './escort-state.svelte';
	import { KIND_ICON } from '$lib/design/icons';
	import { addsText, candidateAdds, launchGate, planStateOf, planViolations, routeCandidates } from './plan';
	import type { PlanRouteCandidate } from '$lib/api/client';

	const CLASSES: readonly ('Z+' | 'Z' | 'Y' | 'X')[] = ['Z+', 'Z', 'Y', 'X'];

	provideUiLang(() => commandBar.lang);
	const lang = $derived(commandBar.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	// ── the form ────────────────────────────────────────────────────────────
	let originIdx = $state(1);
	let destIdx = $state(12);
	let vvipClass = $state<'Z+' | 'Z' | 'Y' | 'X'>('Z');
	/** Departure as an IST "HH:MM" (the TimeField's value); empty = +30 min. */
	let departure = $state<string | null>(null);
	let label = $state('');
	/** CONDITIONAL plans: the duty officer accepted the listed violations (reset per plan). */
	let waiverAccepted = $state(false);
	/** The movement id the waiver was given on (a new plan resets it). */
	let waiverFor = $state<string | null>(null);

	const lc = $derived(escortLifecycle);
	const doc = $derived(lc.doc);
	const planning = $derived(lc.phase === 'planning');
	const escortRunning = $derived(lc.escortRunning);

	$effect(() => {
		// a new plan document resets its waiver (CONDITIONAL capability 15)
		const id = lc.doc?.movement_id ?? null;
		if (waiverFor !== id) {
			waiverFor = id;
			waiverAccepted = false;
		}
	});

	// the lifecycle closes when the brain reports the escort ended, and adopts
	// one this console did not launch
	$effect(() => {
		void lc.phase;
		lc.sync();
	});
	onDestroy(() => {
		if (!escortLifecycle.escortRunning) escortLifecycle.reset();
	});

	// ── the plan's planState (the machine in plan.ts) ──────────────────────────
	const gate = $derived(
		launchGate(doc, { waiverAccepted, officerNamed: ops.officerOn }, {
			waiverNeeded: L('cor_launch_locked_waiver'),
			holdLocked: L('cor_launch_locked_hold'),
			officerNeeded: L('cor_launch_locked_officer'),
			noPlan: L('cor_launch_locked_no_plan'),
		}),
	);
	const planState = $derived(gate.state);
	/* the state tag's intent (SPEC §2.4): NO ROUTE is a fact in ink, never red —
	   red is only ever a watchlisted or stolen vehicle */
	const stateIntent = $derived<'success' | 'danger' | 'warning' | 'none'>(
		planState === 'approved' ? 'success' : planState === 'conditional' || planState === 'hold' ? 'warning' : 'none',
	);
	const stateWord = $derived(
		planState === 'approved'
			? L('cor_status_approved')
			: planState === 'conditional'
				? L('cor_status_conditional')
				: planState === 'hold'
					? L('cor_status_hold')
					: planState === 'no_route'
						? L('cor_status_no_route')
						: L('cor_status_unknown'),
	);
	const holdAt = $derived.by(() => {
		if (planState !== 'hold') return null;
		// the document names no re-plan time: the plan's own departure, else +15 min (stated)
		const dep = lc.plannedDepartureMs ?? Date.now() + 15 * 60_000;
		return fmtStamp(dep);
	});
	const violations = $derived(planViolations(doc));
	const waiverStamped = $derived(ops.officerOn ? ops.dutyOfficer.trim() : '');
	const candidates = $derived(routeCandidates(doc));
	const recommendedId = $derived(lc.recommendedId);
	const recommendedBy = $derived(lc.recommendedBy);

	function addsFor(route: PlanRouteCandidate, primary: PlanRouteCandidate | null | undefined): string {
		const roads = candidateAdds(route, primary);
		return roads.length ? L('cor_cand_adds', addsText(roads)) : L('cor_cand_adds_none');
	}

	function distanceKm(r: PlanRouteCandidate): string | null {
		const m = r.distance_m ?? r.total_distance_m;
		return m != null && Number.isFinite(m) ? (m / 1000).toFixed(1) : null;
	}

	// ── actions ─────────────────────────────────────────────────────────────
	async function plan() {
		const ms = departure ? istTimeToMs(departure) : NaN;
		const departureIso = Number.isFinite(ms) ? new Date(ms).toISOString() : defaultDepartureIso();
		await escortLifecycle.plan({ originIdx, destIdx, vvipClass, departureIso, label });
	}

	/** The default departure: +30 min (ISO). */
	function defaultDepartureIso(): string {
		return new Date(Date.now() + 30 * 60_000).toISOString();
	}

	function openMovement() {
		workspace.rightTab = 'movement';
		workspace.setDock('right', true);
	}

	// ── the escort's open proposal: a LINK ROW to its home (the Movement tab) ─
	let clock = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (clock = Date.now()), 1000);
		return () => clearInterval(id);
	});
	const proposal = $derived(escortRunning ? ops.escortProposalFor(lc.movementId, lc.followedDoc) : null);
	const proposalTitle = $derived(proposal ? ops.escortProposalText(proposal) : null);
	const proposalLeft = $derived(proposal?.expiresAt != null ? Math.max(0, Math.round((proposal.expiresAt - clock) / 1000)) : null);
</script>

<div class="plan">
	<form class="form" aria-label={L('cor_plan_section')} onsubmit={(e) => e.preventDefault()}>
		<FormGroup label={L('cor_plan_from')} labelFor="planner-origin">
			<select class="sel" id="planner-origin" data-testid="planner-origin" bind:value={originIdx} disabled={planning || escortRunning}>
				{#each PLAN_POIS as p, i (p.name)}
					<option value={i}>{p.name}</option>
				{/each}
			</select>
		</FormGroup>
		<FormGroup label={L('cor_plan_to')} labelFor="planner-destination">
			<select class="sel" id="planner-destination" data-testid="planner-destination" bind:value={destIdx} disabled={planning || escortRunning}>
				{#each PLAN_POIS as p, i (p.name)}
					<option value={i}>{p.name}</option>
				{/each}
			</select>
		</FormGroup>
		<FormGroup label={L('cor_plan_class')}>
			<div class="pills" role="radiogroup" aria-label={L('cor_plan_class')}>
				{#each CLASSES as c (c)}
					<button
						type="button"
						role="radio"
						class="class-pill"
						class:is-pressed={vvipClass === c}
						aria-checked={vvipClass === c}
						aria-label={`${L('cor_plan_class')} ${c}`}
						onclick={() => (vvipClass = c)}
						disabled={escortRunning}
					>
						{c}
					</button>
				{/each}
			</div>
		</FormGroup>
		<FormGroup label={L('cor_plan_departure')} labelFor="planner-departure">
			<TimeField id="planner-departure" bind:value={departure} {lang} />
		</FormGroup>
		<FormGroup label={L('cor_plan_label')} helperText={L('cor_plan_label_hint')} labelFor="planner-label">
			<Input
				id="planner-label"
				data-testid="planner-label"
				fill
				maxlength={120}
				placeholder={t(lang, 'cor_label_placeholder')}
				title={L('cor_plan_label_hint')}
				autocomplete="off"
				bind:value={label}
				disabled={planning || escortRunning}
			/>
		</FormGroup>
		<FormGroup label={L('cor_plan_officer')} helperText={L('ws_officer_helper')} labelFor="planner-officer">
			<Input
				id="planner-officer"
				data-testid="planner-officer"
				class="officer-input"
				fill
				value={ops.dutyOfficer}
				readonly={ops.dutyOfficerFromSession}
				placeholder={t(lang, 'shell_officer_roster')}
				title={ops.dutyOfficerFromSession ? tOps(lang, 'officerFromSession') : L('ws_officer_helper')}
				autocomplete="off"
				spellcheck={false}
				maxlength={64}
				oninput={(e: Event) => ops.setDutyOfficer((e.currentTarget as HTMLInputElement).value)}
			/>
		</FormGroup>

		<div class="actions">
			<!-- the page's one primary action: full width (the prototype's bar) -->
			<Button class="plan-btn" intent="primary" fill loading={planning} disabled={planning || escortRunning} onclick={() => void plan()}>
				{planning ? L('cor_plan_btn_busy') : L('cor_plan_btn')}
			</Button>
		</div>

		{#if lc.error}<p class="error" role="alert">{lc.error}</p>{/if}
		{#if lc.note}<p class="note">{lc.note}</p>{/if}

	{#if doc && candidates.length}
		<div class="candidates" data-testid="planner-candidates" data-status={doc.status ?? ''}>
			<header class="cand-head">
				<h3 class="lbl">{t(lang, 'tpl_candidates')}</h3>
				<Tag intent={stateIntent} data-testid="planner-status">{stateWord}</Tag>
			</header>

			{#if doc.overall_reasoning}<p class="reasoning">{doc.overall_reasoning}</p>{/if}

			{#each candidates as route, idx (route.route_id)}
				<article
					class="cand"
					class:recommended={route.route_id === recommendedId}
					data-testid="planner-candidate"
					data-rank={idx === 0 ? 'primary' : 'alternate'}
					data-route-id={route.route_id}
				>
					<header class="cand-row">
						<span class="rank">
							<Icon name={idx === 0 ? 'star' : 'chevron-right'} size={14} />
							{idx === 0 ? L('cor_cand_primary') : L('cor_cand_alternate', String.fromCharCode(64 + idx))}
						</span>
					{#if route.route_id === recommendedId}
						<!-- the pick states itself (audit C S3): a plain visible line,
						     never a tooltip, and no native title repeating it -->
						{@const pickTip =
							recommendedBy === 'decider' ? L('cor_cand_ai_pick', doc.decider_pick?.confidence?.toFixed(2) ?? '—') : L('cor_cand_tactical_pick')}
						<Tag icon={KIND_ICON.recommendation} class="pick">{pickTip}</Tag>
					{/if}
				</header>
				{#if idx > 0}<p class="adds">{addsFor(route, candidates[0])}</p>{/if}
				<div class="figures">
					{#if distanceKm(route) != null}<span>{distanceKm(route)} km</span>{/if}
					{#if route.estimated_time_sec != null && route.estimated_time_sec > 0}
						<span>{Math.max(1, Math.round(route.estimated_time_sec / 60))} min</span>
					{/if}
					{#if route.road_names?.length}<span>{L('cor_cand_roads', route.road_names.length)}</span>{/if}
				</div>
					{#if route.route_tier === 'compliant'}
						<p class="tier ok"><Icon name="tick-circle" size={14} />{L('cor_cand_compliant')}</p>
					{:else if route.route_tier}
						<p class="tier warn">
							<Icon name={KIND_ICON.anomaly} size={14} />
							{L('cor_cand_violations', route.lane_violations?.length ?? 0)}
						</p>
					{/if}
					{#if route.reason}<p class="why">{route.reason}</p>{/if}
				</article>
			{/each}

			{#if doc.rejected_routes?.length}
				<div class="rejected">
					<h4 class="lbl">{L('cor_cand_rejected', doc.rejected_routes.length)}</h4>
					<ul>
						{#each doc.rejected_routes as r (r.route_id)}
							<li>{r.route_id}: {r.reason ?? '—'}</li>
						{/each}
					</ul>
				</div>
			{/if}
		</div>
	{:else if doc && planState === 'no_route'}
		<!-- NO ROUTE: Launch hidden; the reason and the next action shown (capability 16);
		     the state is a fact in ink, never red (SPEC §2.4) -->
		<div class="candidates" data-testid="planner-candidates" data-status="no_route">
			<div class="cand-head">
				<Tag intent="none" data-testid="planner-status">{stateWord}</Tag>
			</div>
			{#if doc.overall_reasoning}<p class="reasoning">{doc.overall_reasoning}</p>{/if}
			<p class="note">{L('cor_no_route_note')}</p>
			<p class="note">{L('cor_no_route_next')}</p>
		</div>
	{:else if !doc && !lc.error && lc.phase === 'idle'}
		<!-- the empty state is a quiet helper line (audit C S3), never a 17 px bold heading -->
		<NonIdealState icon={KIND_ICON.convoy} iconSize={20} layout="horizontal" title={L('cor_plan_none')} />
	{/if}

	{#if planState === 'conditional' && candidates.length}
		<section class="violations">
			<h4 class="lbl">{L('cor_status_conditional')}</h4>
			<ul>
				{#each violations.slice(0, 6) as v, vi (vi)}
					<li>{v.segmentId != null ? `seg ${v.segmentId}: ` : ''}{v.detail}</li>
				{/each}
			</ul>
			<Checkbox data-testid="planner-waiver" bind:checked={waiverAccepted} disabled={lc.phase === 'starting'}>
				<span class="waiver-text">
					{L('cor_waiver')}
					{#if waiverStamped && waiverAccepted}<span class="stamp">{L('cor_waiver_stamped', waiverStamped)}</span>{/if}
				</span>
			</Checkbox>
		</section>
	{/if}

	{#if planState === 'hold' && doc}
		<p class="note hold" data-testid="planner-hold">{holdAt ? L('cor_hold_replan', holdAt) : L('cor_hold_note')}</p>
	{/if}

	<!-- escort controls: Launch (criteria and Reason), Stop, Clear -->
	<div class="actions">
		{#if escortRunning}
			<Button
				intent="danger"
				loading={lc.phase === 'stopping'}
				disabled={!ops.officerOn}
				disabledReason={L('cor_launch_locked_officer')}
				onclick={() => void lc.stop()}
			>
				{lc.phase === 'stopping' ? L('cor_stopping') : L('cor_stop')}
			</Button>
			{#if lc.note}<Button onclick={() => lc.reset()}>{t(lang, 'btn_close')}</Button>{/if}
		{:else}
			{#if gate.escortOffered && (lc.phase === 'planned' || lc.phase === 'starting')}
				<Tooltip content={L('cor_launch_criteria', vvipClass, PLAN_POIS[destIdx].name)}>
					<Button intent="primary" style="white-space: nowrap" loading={lc.phase === 'starting'} disabled={gate.launchLocked} onclick={() => void lc.launch()}>
						{lc.phase === 'starting' ? L('cor_launch_starting') : L('cor_launch')}
					</Button>
				</Tooltip>
			{/if}
			{#if lc.movementId && (lc.phase === 'ended' || (lc.phase === 'planned' && doc)) && !lc.clearOutcome?.ok}
				<Tooltip content={L('cor_clear_hint')}>
					<Button loading={lc.clearing} disabled={!ops.officerOn} disabledReason={L('cor_launch_locked_officer')} onclick={() => void lc.clear()}>
						<span data-testid="planner-clear">{lc.clearing ? L('cor_clearing') : L('cor_clear')}</span>
					</Button>
				</Tooltip>
			{/if}
			{#if lc.phase === 'ended'}
				<Button onclick={() => lc.reset()}>{t(lang, 'btn_close')}</Button>
			{/if}
		{/if}
	</div>
	{#if gate.launchLockReason && planState !== 'no_route' && planState !== 'none'}
		<Reason text={gate.launchLockReason} />
	{/if}

	{#if lc.clearOutcome}
		<p
			class="note clear-outcome"
			data-testid="planner-clear-outcome"
			data-to-status={lc.clearOutcome.toStatus ?? ''}
			data-ok={lc.clearOutcome.ok}
		>
			{lc.clearOutcome.ok
				? `${tOps(lang, 'escortClearOutcome', lc.clearOutcome.toStatus ?? '—')}${lc.clearOutcome.detail ? ` · ${lc.clearOutcome.detail}` : ''}`
				: tOps(lang, 'escortClearFailed', lc.clearOutcome.detail ?? '—')}
		</p>
	{/if}

	{#if proposal && proposalTitle}
		<!-- the proposal is NEVER decided here: a link row to its home; its
		     title sits on its own line (audit C S3), never cut to fit one row -->
		<button
			type="button"
			class="proposal-link"
			data-testid="planner-proposal"
			data-approval-id={proposal.approvalId}
			data-kind={proposal.kind}
			onclick={openMovement}
		>
			<span class="pl-top">
				<Icon name="arrow-right" size={16} />
				<span class="pl-what">{L('cor_proposal_link', proposalTitle)}</span>
				{#if proposalLeft != null}
					<span class="pl-left" class:urgent={proposalLeft < 15}>
						{proposalLeft > 0 ? `${Math.floor(proposalLeft / 60)}:${String(proposalLeft % 60).padStart(2, '0')}` : tOps(lang, 'escExpiring')}
					</span>
				{/if}
			</span>
			<span class="pl-go">{L('cor_proposal_open')}</span>
		</button>
	{/if}
	</form>
</div>

<style>
	.plan {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding: 12px 16px 16px;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
	}

	.form {
		display: flex;
		flex-direction: column;
		gap: 10px;
		min-width: 0;
	}

	.sel {
		height: 30px;
		width: 100%;
		padding: 0 8px;
		border: 1px solid var(--v-line-2);
		border-radius: var(--v-radius-btn);
		background: var(--v-surface-sink);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
	}

	.sel:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 0;
	}

	.pills {
		display: flex;
		gap: 4px;
	}

	.class-pill {
		flex: 1;
		height: 24px;
		border: 1px solid var(--v-line-2);
		border-radius: var(--v-radius-pill);
		background: transparent;
		color: var(--v-ink-2);
		font-family: var(--v-font-ui);
		font-size: var(--v-text-xs);
		font-variant-numeric: tabular-nums;
		cursor: pointer;
	}

	.class-pill.is-pressed {
		background: var(--v-surface-4);
		color: var(--v-ink-1);
		box-shadow: inset 0 0 0 1px var(--v-line-strong);
	}

	.class-pill:focus-visible {
		outline: 2px solid var(--v-focus);
	}

	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	/* (the Button's own `fill` gives "Plan corridor" its full width) */

	/* the empty state is a quiet helper line (audit C S3): small, not bold */
	.plan :global([data-ui='non-ideal-state']) {
		justify-content: flex-start;
		padding: 8px 0;
		text-align: left;
	}

	.plan :global([data-ui='non-ideal-state'] .title) {
		font-size: var(--v-text-base);
		font-weight: 400;
		line-height: calc(var(--v-text-base) + 4px);
		color: var(--v-ink-2);
	}

	.error {
		margin: 0;
		padding: 2px 0 2px 8px;
		/* a refusal is the brain's answer in ink (SPEC §2.4) — never red */
		border-left: 2px solid var(--v-line-strong);
		color: var(--v-ink-1);
		line-height: 16px;
		overflow-wrap: anywhere;
	}

	.note {
		margin: 0;
		color: var(--v-ink-2);
		line-height: 16px;
		overflow-wrap: anywhere;
	}

	.note.hold {
		color: var(--v-warning-text);
	}

	.clear-outcome {
		border-left: 2px solid var(--v-line-2);
		padding-left: 8px;
	}

	.candidates {
		display: flex;
		flex-direction: column;
		gap: 8px;
		border-top: 1px solid var(--v-line-1);
		padding-top: 10px;
	}

	.lbl {
		margin: 0;
		font-size: var(--v-text-xs);
		font-weight: 600;
		color: var(--v-ink-2);
	}

	.cand-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
	}

	.reasoning {
		margin: 0;
		color: var(--v-ink-2);
		line-height: 16px;
	}

	.cand {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 8px 10px;
		border: 1px solid var(--v-line-1);
		border-radius: var(--v-radius-btn);
		background: var(--v-surface-2);
	}

	.cand.recommended {
		border-color: var(--v-primary-text);
		box-shadow: inset 2px 0 0 var(--v-primary-text);
	}

	.cand-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		min-height: 20px;
	}

	.rank {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-weight: 600;
		color: var(--v-ink-1);
	}

	.adds {
		margin: 0;
		color: var(--v-ink-2);
		line-height: 16px;
	}

	.figures {
		display: flex;
		gap: 12px;
		font-variant-numeric: tabular-nums;
		color: var(--v-ink-1);
	}

	.tier {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		margin: 0;
	}

	.tier.ok {
		color: var(--v-success-text);
	}

	.tier.warn {
		color: var(--v-warning-text);
	}

	.why {
		margin: 0;
		color: var(--v-ink-2);
		line-height: 16px;
	}

	.rejected ul,
	.violations ul {
		margin: 4px 0 0;
		padding-left: 16px;
		color: var(--v-ink-2);
		line-height: 16px;
	}

	.violations {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 8px 10px;
		border-left: 2px solid var(--v-warning-text);
		background: var(--v-warning-veil);
		border-radius: var(--v-radius-btn);
	}

	.waiver-text {
		display: block;
	}

	.waiver-text .stamp {
		display: block;
		color: var(--v-ink-2);
	}

	.proposal-link {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 8px 10px;
		border: 1px solid var(--v-line-2);
		border-left: 2px solid var(--v-act);
		border-radius: var(--v-radius-btn);
		background: var(--v-surface-2);
		color: var(--v-ink-1);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.proposal-link:hover {
		border-color: var(--v-line-strong);
	}

	.pl-top {
		display: flex;
		align-items: baseline;
		gap: 8px;
		min-width: 0;
	}

	.proposal-link :global(svg) {
		flex: 0 0 auto;
		color: var(--v-act-text);
		align-self: center;
	}

	.pl-what {
		flex: 1 1 auto;
		min-width: 0;
		/* the title sits on its own line and wraps (audit C S3) — never cut to fit */
		white-space: normal;
		overflow-wrap: anywhere;
		line-height: 16px;
	}

	.pl-left {
		flex: 0 0 auto;
		font-variant-numeric: tabular-nums;
		color: var(--v-ink-2);
	}

	/* under 15 s the countdown gains weight, never red (SPEC §2.4) */
	.pl-left.urgent {
		color: var(--v-ink-1);
		font-weight: 600;
	}

	.pl-go {
		flex: 0 0 auto;
		padding-left: 24px;
		color: var(--v-primary-text);
		font-weight: 600;
		white-space: nowrap;
	}
</style>
