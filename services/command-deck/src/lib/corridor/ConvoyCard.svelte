<script lang="ts">
	/**
	 * ConvoyCard (SPEC §5.3 ConvoyCard [S6], §5.4 homes) — the HOME of escort
	 * proposals, and the live movement's readout:
	 *
	 *   on /        the Movement right-dock tab (the default while a movement
	 *               is live); the escort proposal's root is `convoy-hud-proposal`
	 *   on /ops     the first block of the Decisions column (DecisionQueue's
	 *               `top` snippet); its root is
	 *               `queue-card[data-kind="escort-proposal"][data-id][data-movement-id]`
	 *
 * Header: the movement's title, class and start time, and the provenance
 * tags (`convoy-hud-emulated` "Emulated GPS", `convoy-hud-simulated`) — the
 * ONLY place the convoy feed's provenance states (the footer copy of it is
 * gone: once per card, never a stack of pills). Key figures: speed,
 * progress, ETA (`convoy-hud-eta`), hold; "Next junction <name> · in 1 min
 * 35 s". The escort proposal is S5A's ProposalCard + EscortBody (the
 * imperative title, What changes generated from WRITERS, the ONE rule note,
 * the evidence) with the ConvoyCard's own pinned header (proposer tag,
 * decider line, countdown, the decider's why) and decision footer (officer
 * field, Reject, Approve, outcome). Holds read "Holding on <roads>
 * (officer …)" (`convoy-hud-hold`). The legacy referred-actions list
 * (`convoy-hud-approvals` / `convoy-hud-approval`) renders ONLY when the
 * escort reports no proposals (an older brain).
 *
 * On /ops the wall block reads the LANES (`ops.escortsDeployed`, audit C
 * S2): it never adopts the escort nor starts the shared follower — its
 * liveness and phase come from the lanes, its provenance tags from the
 * lane's gpsMode/trafficSimulated, and its figures from whatever this
 * console already follows or the convoy registry carries; where neither
 * has anything it says so plainly instead of a row of dashes (audit E
 * item 2). The proposal names its proposer and decider once (the pinned
 * tag/countdown stay on the Movement tab; the wall's live in the
 * ProposalCard), and a hold the followed document reports renders here
 * too. The AI proposes; a named officer decides (ethics 6):
 * Approve and Reject stay locked until an officer is named, one POST per
 * click (the store's busy guard, shared with the /ops queue), and the
 * outcome row names the officer. Nothing is ever auto-applied.
 */
	import { ops } from '$lib/ops/store.svelte';
	import { displayTitle } from '$lib/workspace/display';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { escortFollower } from '$lib/ops/components/template/escort.svelte';
	import { corridor } from '$lib/ops/components/template/corridor.svelte';
	import { decisionUnits, escortOf, type DecisionState, type Unit } from '$lib/decisions/units';
	import { escortLifecycle, laneRunning, legacyApprovals } from './escort-state.svelte';
	import { escortRule } from '$lib/decisions/cards/meta';
	import ProposalCard from '$lib/decisions/ProposalCard.svelte';
	import DecisionFooter, { type FooterAct } from '$lib/decisions/DecisionFooter.svelte';
	import { ACTOR_ICON, KIND_ICON, PROVENANCE_ICON } from '$lib/design/icons';
	import { Button, Icon, Reason, Tag, provideUiLang } from '$lib/ui';
	import { fmtStamp } from '$lib/ui/format/format';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { t } from '$lib/i18n/strings';
	import { tOps } from '$lib/i18n/strings.ops';
	import '$lib/i18n/packs.corridor';
	import type { EscortApproval, EscortStatus } from '$lib/gods-eye/city-api';
	import type { EscortProposalOutcome } from '$lib/ops/types';

	provideUiLang(() => commandBar.lang);
	let {
		variant = 'movement',
		lang = ops.lang,
		now = null,
	}: {
		/** 'movement' = the / Movement tab (the full card); 'wall' = the /ops Decisions block. */
		variant?: 'movement' | 'wall';
		lang?: string;
		/** The host's clock (epoch ms); the card subscribes to the shell's 1 Hz clock only without one. */
		now?: number | null;
	} = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const wall = $derived(variant === 'wall');

	// ── the live movement ───────────────────────────────────────────────────
	const movement = $derived(
		ops.events.find((e) => e.source !== 'offline-fixture' && e.eventKind === 'protected_movement' && e.state === 'active') ?? null,
	);
	const movementId = $derived(movement?.movementId ?? null);
	const followed = $derived(!!movementId && escortFollower.movementId === movementId);
	const status = $derived<EscortStatus | null>(followed ? escortFollower.status : null);
	const convoy = $derived(movementId ? cityRegistry.get(`convoy:${movementId}`) : null);
	/** The lanes know this escort as running (the wall's live read — the movement tab's is the follower's). */
	const laneLive = $derived(wall && laneRunning(ops.escortsDeployed, ops.escorts, movementId));
	const live = $derived((!!status && (status.status === 'running' || status.status === 'waiting_for_gps')) || laneLive);
	/** The escort's lane on this console (audit E item 2): the wall's provenance
	 * comes from it when the shared follower has no document to ask. */
	const lane = $derived(wall && movementId ? (ops.escorts.find((l) => l.movementId === movementId) ?? null) : null);

	// ── the escort proposals (the units decisionUnits collects) ─────────────
	const units = $derived(decisionUnits(ops as DecisionState).filter((u) => u.kind === 'escort-proposal'));

	// the lifecycle follows the board — on the corridor only (the Movement tab).
	// The /ops wall block never STARTS the shared follower (audit C S2): its own
	// liveness comes from the LANES (`ops.escortsDeployed`, laneRunning), its
	// provenance from the lane (gpsMode/trafficSimulated) and its figures from
	// whatever the console already follows or the convoy registry carries —
	// a wall that started per-movement polls of its own would fan them out
	// beside the lifecycle's and keep polling a movement it cannot see.
	$effect(() => {
		if (wall) return;
		void ops.events.length;
		void ops.escortsDeployed; // adoption waits for the lanes' first answer
		escortLifecycle.sync();
	});

	// ── the figures (every readout from the stack, never a timer) ───────────
	let clock = $state(Date.now());
	$effect(() => {
		if (now != null) return;
		const id = setInterval(() => (clock = Date.now()), 1000);
		return () => clearInterval(id);
	});
	const t0 = $derived(now ?? clock);

	function num(v: unknown): number | null {
		return typeof v === 'number' && Number.isFinite(v) ? v : null;
	}

	const fixSpeed = $derived(status?.position?.speedKmh ?? num(convoy?.props.speed_kmh));
	const gpsEmulated = $derived(
		status?.gpsMode === 'emulated' ||
			lane?.gpsMode === 'emulated' ||
			(typeof convoy?.props.position_source === 'string' && convoy.props.position_source === 'emulated_gps'),
	);
	const progress = $derived(status?.progress ?? num(convoy?.props.progress));
	const etaSec = $derived(status?.etaSec ?? null);
	/** The brain's terminal status (completed / stopped / failed), while it holds. */
	const endedStatus = $derived(followed ? escortFollower.terminal : null);
	const hudPhase = $derived(live ? 'escorting' : endedStatus ? 'ended' : 'planned');
	const etaAttr = $derived(etaSec ?? '');
	const nextName = $derived(typeof convoy?.props.next_junction_name === 'string' ? (convoy.props.next_junction_name as string) : null);
	const nextInSec = $derived(nextName ? num(convoy?.props.next_junction_in_sec) : null);
	const startedAt = $derived(status?.startedAt ?? null);
	const hold = $derived(status?.hold ?? null);
	/** Speed: the convoy's own, else the corridor average (labelled; never zeros as live). */
	const corridorDark = $derived(fixSpeed == null && (corridor.noLiveFeed || !corridor.row));
	const speed = $derived(fixSpeed ?? (corridorDark ? null : (corridor.row?.avgSpeedKmh ?? null)));
	const feedSimulated = $derived(status?.trafficSimulated === true || lane?.trafficSimulated === true || corridor.simulated);
	/** The wall has no live figures for THIS escort on this console (no follower status and no convoy fix of its own):
	 *  say so, never a corridor average, "Hold None" or "planned" standing in for an escorting convoy's readout. */
	const noFigures = $derived(wall && status == null && fixSpeed == null && progress == null && etaSec == null);

	function etaText(sec: number | null): string {
		if (sec == null || !Number.isFinite(sec) || sec <= 0) return '—';
		return sec < 90 ? L('cor_hud_sec', Math.round(sec)) : L('cor_hud_min', Math.round(sec / 60));
	}

	function inText(sec: number | null): string {
		return sec != null && sec > 0 ? (sec < 90 ? L('cor_hud_sec', Math.round(sec)) : L('cor_hud_min', Math.round(sec / 60))) : '—';
	}

	/** Road names of segment ids (the signage name, else the id). */
	function roads(ids: number[]): string {
		const names: string[] = [];
		for (const id of ids) {
			const nm = ops.roadName(id) ?? `seg ${id}`;
			if (!names.includes(nm)) names.push(nm);
		}
		return names.length > 3 ? `${names.slice(0, 3).join(', ')} +${names.length - 3}` : names.join(', ') || '—';
	}

	// ── deciding (the store's guard: one POST per click, officer-gated) ─────
	const officerOn = $derived(ops.officerOn);
	const needOfficer = $derived(officerOn ? null : L('dec_reason_officer'));

	async function decide(p: { movementId: string; approvalId: string }, decision: 'approve' | 'reject') {
		if (ops.escortDecisionBusy || ops.escortAnswered(p.approvalId)) return;
		await ops.decideEscortProposal(p as never, decision);
		escortFollower.refresh();
	}

	/** A legacy referred action rides its movement's approval route. */
	function decideLegacy(a: EscortApproval, decision: 'approve' | 'reject') {
		return decide({ movementId: movementId ?? '', approvalId: a.approvalId }, decision);
	}

	function footerFor(u: Unit): { primary: FooterAct; secondary: FooterAct } {
		const p = escortOf(u).proposal;
		// expiry is the brain's ruling (its 409 arrives verbatim): a late
		// answer is SENT and refused — never pre-refused on the client countdown.
		// An answer the brain accepted is final: the buttons stay locked until
		// the next escorts poll closes the proposal (one POST per decision).
		const block = ops.escortAnswered(p.approvalId) ? L('dec_refuse_decided') : needOfficer;
		return {
			primary: {
				label: L('dec_btn_approve'),
				disabled: !!block,
				reason: block,
				run: () => void decide(p, 'approve'),
				testid: 'convoy-hud-proposal-approve',
			},
			secondary: {
				label: L('dec_btn_reject'),
				disabled: !!block,
				reason: block,
				run: () => void decide(p, 'reject'),
				testid: 'convoy-hud-proposal-reject',
			},
		};
	}

	/** How a closed proposal ended (the brain's record, in its own words). */
	function outcomeOf(u: Unit): EscortProposalOutcome | null {
		const p = escortOf(u).proposal;
		return ops.escortOutcomeFor(p.movementId, escortFollower.movementId === p.movementId ? escortFollower.status : null);
	}

	/** The legacy referred actions (an older brain), ONLY when no proposal is reported. */
	const legacy = $derived.by((): EscortApproval[] => {
		if (wall) return [];
		return legacyApprovals(ops.escortsDeployed, followed ? status : null, live);
	});

	/** This console's answer per legacy approval (the inline failure line). */
	function legacyAnswer(id: string) {
		return ops.escortDecisions[id] ?? null;
	}

</script>

{#snippet proposalCard(u: Unit)}
	{@const p = escortOf(u).proposal}
	{@const left = p.expiresAt != null ? Math.max(0, Math.round((p.expiresAt - t0) / 1000)) : null}
	{@const rule = escortRule(u)}
	{@const why = ops.escortProposalWhy(p)}
	{@const answer = ops.escortDecisions[p.approvalId] ?? null}
	{@const outcome = outcomeOf(u)}
	{@const foot = footerFor(u)}
	<section
		class="proposal"
		data-testid={wall ? 'queue-card' : 'convoy-hud-proposal'}
		data-kind={wall ? 'escort-proposal' : p.kind}
		data-id={p.approvalId}
		data-movement-id={p.movementId}
		data-approval-id={p.approvalId}
		data-expires-sec={left ?? ''}
		aria-live="polite"
	>
		<!-- the pinned header on the Movement tab only (audit E item 2): on the
		     wall the ProposalCard's own proposer line and expiry countdown are
		     the ONE attribution and the ONE countdown — a pinned header beside
		     them said it all twice -->
		{#if !wall}
			<header class="pr-head">
				<span class="pr-tag" class:ai={!rule} data-testid="convoy-hud-proposal-tag">
					<Icon name={rule ? ACTOR_ICON.rules : ACTOR_ICON.ai} size={14} />
					{t(lang, rule ? 'dec_by_rule' : 'dec_by_ai')}
				</span>
				{#if left != null}
					<span class="pr-count" class:urgent={left < 15} data-testid="convoy-hud-proposal-countdown">
						{left > 0 ? `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}` : tOps(lang, 'escExpiring')}
					</span>
				{/if}
			</header>
		{/if}
		<p class="pr-decider" data-testid="convoy-hud-proposal-decider">{ops.escortDeciderText(p)}</p>

		<!-- the ProposalCard: imperative title, tags (countdown, provenance — on the Movement tab the header above
		     states the escort's provenance, so the card leaves those tags out; the wall's proposal is its own /ops
		     queue card and keeps them),
		     What changes from WRITERS, the why body, the evidence — no second footer -->
		<ProposalCard unit={u} {lang} footer={false} sticky={false} {now} hostProvenance={wall ? undefined : { simulated: feedSimulated, gps: gpsEmulated }} />

		{#if !wall && why}<p class="pr-why" data-testid="convoy-hud-proposal-why">{ops.text(why)}</p>{/if}
		{#if answer && !answer.ok}
			<p class="refused" data-testid="convoy-hud-proposal-refused">{answer.detail ?? `HTTP ${answer.httpStatus}`}</p>
		{/if}

		<DecisionFooter
			{lang}
			sticky={false}
			reasonMode="none"
			primary={foot.primary}
			secondary={foot.secondary}
			busy={!!ops.escortDecisionBusy}
			officerTestId={wall ? 'decision-officer' : 'convoy-hud-proposal-officer'}
			idPrefix={`escort-${p.approvalId}`}
		/>

		{#if outcome && !wall}
			<p
				class="outcome"
				class:ok={outcome.status === 'approved'}
				data-testid="convoy-hud-proposal-outcome"
				data-approval-id={outcome.approvalId}
				data-status={outcome.status}
				title={outcome.summary ? ops.text(outcome.summary) : undefined}
			>
				<Icon name={outcome.status === 'approved' ? 'tick-circle' : 'time'} size={16} />
				{ops.escortOutcomeText(outcome)}
			</p>
		{/if}
	</section>
{/snippet}

{#if wall}
	<!-- /ops: the first block of the Decisions column (the queue's `top` snippet);
	     the receipts (escort-outcome rows) are the queue's own. The block reads
	     the LANES (`ops.escortsDeployed`) for its liveness and provenance — a
	     running escort is never shown as a 'planned' shell (audit C S2) — and
	     says so plainly when this console has no live figures for it -->
	<div
		class="wallcard"
		data-template="convoy-hud"
		data-phase={hudPhase}
		data-ended={endedStatus ?? ''}
		data-eta-sec={etaAttr}
		data-movement-id={movementId ?? ''}
	>
		<div class="wall-head">
			<Icon name={KIND_ICON.convoy} size={16} />
			<span class="w-title">{movement ? ops.text(displayTitle(movement.name, lang)) : tOps(lang, 'escQueueEvent', movementId?.slice(0, 8) ?? '—')}</span>
			<span class="grow"></span>
			{#if gpsEmulated}<span class="provtag" data-testid="convoy-hud-emulated"><Icon name={PROVENANCE_ICON.emulated} size={12} />{tOps(lang, 'hudEmulatedGps')}</span>{/if}
			{#if feedSimulated}<span class="provtag" data-testid="convoy-hud-simulated"><Icon name={PROVENANCE_ICON.simulated} size={12} />{tOps(lang, 'hudSimulatedFeed')}</span>{/if}
		</div>
		{#if noFigures}
			<!-- no follower and no convoy fix on this console: the honest line,
			     never a row of dashes pretending to be a readout (audit E item 2) -->
			<p class="nofigures" data-testid="convoy-hud-nofigures">{L('cor_hud_nofigures')}</p>
		{:else}
			<div class="figures">
				<div class="fig" data-testid="convoy-hud-speed">
					<span class="k">{fixSpeed != null ? L('cor_hud_speed') : L('cor_hud_speed_corridor')}</span>
					<span class="v" class:zero={speed == null}>{speed != null ? Math.round(speed) : '—'}</span>
				</div>
				<div class="fig" data-testid="convoy-hud-progress">
					<span class="k">{L('cor_hud_progress')}</span>
					<span class="v" class:zero={progress == null}>{progress != null ? `${Math.round(progress * 100)}%` : '—'}</span>
				</div>
				<div class="fig" data-testid="convoy-hud-eta">
					<span class="k">{L('cor_hud_eta')}{etaSec == null && !live ? ` · ${L('cor_hud_eta_planned')}` : ''}</span>
					<span class="v" class:zero={etaSec == null}>{etaText(etaSec)}</span>
				</div>
				{#if status}
					<!-- the hold is known only from the escort's own status (the follower): without it, no "None" claim -->
					<div class="fig" data-testid="convoy-hud-hold-state">
						<span class="k">{L('cor_hud_hold')}</span>
						<span class="v" class:zero={!hold}>{hold ? L('cor_hud_hold_yes') : L('cor_hud_hold_none')}</span>
					</div>
				{/if}
			</div>
		{/if}
		{#if hold && live}
			<p class="hold" data-testid="convoy-hud-hold" data-ordered-by={hold.orderedBy ?? ''} title={hold.reason ?? undefined}>
				{tOps(lang, 'hudHolding', roads(hold.segmentIds), hold.orderedBy ?? '—')}
				{#if hold.peakCongestion != null}<span class="dim"> · {tOps(lang, 'hudPeak', Math.round(hold.peakCongestion * 100))}</span>{/if}
			</p>
		{/if}
		{#each units as u (u.id)}
			{@render proposalCard(u)}
		{/each}
	</div>
{:else if movement}
	<!-- /: the Movement right-dock tab -->
	<aside
		class="hud"
		data-template="convoy-hud"
		data-phase={hudPhase}
		data-ended={endedStatus ?? ''}
		data-eta-sec={etaAttr}
		data-movement-id={movementId ?? ''}
	>
		<header class="hud-head">
			<div class="title-wrap">
				<h3 class="title">{ops.text(movement.name)}</h3>
				<p class="sub">
					{#if movement.protectionClass && movement.protectionClass !== 'none'}<span class="cls">{movement.protectionClass}</span>{/if}
					{#if startedAt}{' · '}{fmtStamp(startedAt, t0)}{/if}
					{#if movementId}{' · '}{movementId.slice(0, 8)}{/if}
				</p>
			</div>
		</header>
		<div class="tags">
			{#if live}<Tag icon={KIND_ICON.convoy}>{L('cor_hud_escort_live')}</Tag>{/if}
			{#if gpsEmulated}<span class="provtag" data-testid="convoy-hud-emulated"><Icon name={PROVENANCE_ICON.emulated} size={12} />{tOps(lang, 'hudEmulatedGps')}</span>{/if}
			{#if feedSimulated}<span class="provtag" data-testid="convoy-hud-simulated"><Icon name={PROVENANCE_ICON.simulated} size={12} />{tOps(lang, 'hudSimulatedFeed')}</span>{/if}
		</div>

		<!-- key figures: speed, progress, ETA, hold -->
		<div class="figures">
			<div class="fig" data-testid="convoy-hud-speed">
				<span class="k">{fixSpeed != null ? L('cor_hud_speed') : L('cor_hud_speed_corridor')}</span>
				<span class="v" class:zero={speed == null}>{speed != null ? Math.round(speed) : '—'}</span>
			</div>
			<div class="fig" data-testid="convoy-hud-progress">
				<span class="k">{L('cor_hud_progress')}</span>
				<span class="v" class:zero={progress == null}>{progress != null ? `${Math.round(progress * 100)}%` : '—'}</span>
			</div>
			<div class="fig" data-testid="convoy-hud-eta">
				<span class="k">{L('cor_hud_eta')}{etaSec == null && live ? ` · ${L('cor_hud_eta_planned')}` : ''}</span>
				<span class="v" class:zero={etaSec == null}>{etaText(etaSec)}</span>
			</div>
			<div class="fig" data-testid="convoy-hud-hold-state">
				<span class="k">{L('cor_hud_hold')}</span>
				<span class="v" class:zero={!hold}>{hold ? L('cor_hud_hold_yes') : L('cor_hud_hold_none')}</span>
			</div>
		</div>

		{#if nextName}
			<p class="next-junction" data-testid="convoy-hud-next">
				{L('cor_hud_next_junction', nextName, inText(nextInSec))}
			</p>
		{:else if live}
			<p class="next-junction dim">{L('cor_hud_awaiting_gps')}</p>
		{/if}

		{#if hold && live}
			<p class="hold" data-testid="convoy-hud-hold" data-ordered-by={hold.orderedBy ?? ''} title={hold.reason ?? undefined}>
				{tOps(lang, 'hudHolding', roads(hold.segmentIds), hold.orderedBy ?? '—')}
				{#if hold.peakCongestion != null}<span class="dim"> · {tOps(lang, 'hudPeak', Math.round(hold.peakCongestion * 100))}</span>{/if}
			</p>
		{/if}

		{#each units as u (u.id)}
			{@render proposalCard(u)}
		{/each}

		{#if live && !units.length}
			{@const outcome = movementId ? ops.escortOutcomeFor(movementId, followed ? status : null) : null}
			{#if outcome}
				<p
					class="outcome"
					class:ok={outcome.status === 'approved'}
					data-testid="convoy-hud-proposal-outcome"
					data-approval-id={outcome.approvalId}
					data-status={outcome.status}
					title={outcome.summary ? ops.text(outcome.summary) : undefined}
				>
					<Icon name={outcome.status === 'approved' ? 'tick-circle' : 'time'} size={16} />
					{ops.escortOutcomeText(outcome)}
				</p>
			{/if}
		{/if}

		<!-- the legacy referred actions, ONLY when the escort reports no proposals -->
		{#if legacy.length}
			<section class="approvals" data-testid="convoy-hud-approvals">
				<h4>{tOps(lang, 'hudApprovalsTitle')}</h4>
				{#each legacy as a (a.approvalId)}
					{@const out = legacyAnswer(a.approvalId)}
					<article class="approval" data-testid="convoy-hud-approval" data-approval-id={a.approvalId}>
						<p class="ap-what">
							<b>{a.action.replace(/_/g, ' ')}</b>
							{#if a.simulated}<span class="provtag">{tOps(lang, 'hudSimulatedFeed')}</span>{/if}
						</p>
						{#if a.reason}<p class="ap-why">{a.reason}</p>{/if}
						{#if out}
							<p class="ap-out" class:err={!out.ok} data-testid="convoy-hud-approval-outcome">
								{out.ok
									? tOps(lang, 'hudApprovalDone', out.status ?? '—')
									: tOps(lang, 'hudApprovalFailed', out.detail ?? `HTTP ${out.httpStatus}`)}
							</p>
						{/if}
						{#if !out?.ok}
							<div class="ap-actions">
								<Button small intent="primary" disabled={!!ops.escortDecisionBusy || !officerOn} onclick={() => void decideLegacy(a, 'approve')}>
									<span data-testid="convoy-hud-approve">{tOps(lang, 'hudApprove')}</span>
								</Button>
								<Button small disabled={!!ops.escortDecisionBusy || !officerOn} onclick={() => void decideLegacy(a, 'reject')}>
									<span data-testid="convoy-hud-reject">{tOps(lang, 'hudReject')}</span>
								</Button>
							</div>
						{/if}
					</article>
				{/each}
				<p class="note dim">{tOps(lang, 'hudApprovalsNote')}</p>
			</section>
		{/if}

		<!-- the convoy feed's provenance states ONCE, in the header tags
		     (audit C S3): the footer copy of the same pills is gone -->

		{#if escortFollower.note && followed}<p class="note dim">{escortFollower.note}</p>{/if}
	</aside>
{:else if units.length}
	<!-- a proposal whose movement is not on the board: still its home -->
	<div class="hud" data-template="convoy-hud" data-phase="planned">
		{#each units as u (u.id)}
			{@render proposalCard(u)}
		{/each}
	</div>
{/if}

<style>
	.hud,
	.wallcard {
		display: flex;
		flex-direction: column;
		gap: 10px;
		min-width: 0;
		padding: 12px 16px;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.wallcard {
		padding: 0;
		gap: 8px;
	}

	/* the wall block's figures and hold line up with the head's 16 px inset */
	.wallcard .figures {
		padding: 2px 16px 0;
	}

	.wallcard .hold {
		margin: 0 16px;
	}

	.hud-head,
	.wall-head {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		min-width: 0;
	}

	.wall-head :global(svg) {
		flex: 0 0 auto;
		color: var(--v-map-route);
		margin-top: 2px;
	}

	.grow {
		flex: 1 1 auto;
	}

	.title-wrap {
		min-width: 0;
	}

	.title {
		margin: 0;
		font-size: var(--v-text-md);
		font-weight: 600;
		line-height: 20px;
		overflow-wrap: anywhere;
	}

	.w-title {
		font-size: var(--v-text-sm);
		font-weight: 600;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.sub {
		margin: 2px 0 0;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	/* the protection class is a fact of the console, not a warning: neutral ink
	   (SPEC §2.4 — orange is only ever a waiting decision) */
	.cls {
		color: var(--v-ink-2);
		font-weight: 600;
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
	}

	.provtag {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		height: 20px;
		padding: 2px 6px;
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		white-space: nowrap;
	}

	.figures {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 8px;
	}

	.fig {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.fig .k {
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.fig .v {
		font-size: var(--v-text-md);
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}

	.fig .v.zero {
		color: var(--v-ink-2);
		font-weight: 400;
	}

	.next-junction {
		margin: 0;
		font-size: var(--v-text-xs);
		color: var(--v-ink-1);
		line-height: 16px;
	}

	.next-junction.dim,
	.note.dim {
		color: var(--v-ink-2);
	}

	/* a hold already in force is a fact of the console, not a waiting decision:
	   a quiet neutral line (SPEC §2.4 — orange is only ever a waiting decision) */
	.hold {
		margin: 0;
		padding: 6px 8px;
		border: 1px solid var(--v-line-2);
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		color: var(--v-ink-1);
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.nofigures {
		margin: 0 16px;
		padding: 6px 8px;
		border: 1px solid var(--v-line-2);
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.hold .dim {
		color: var(--v-ink-2);
	}

	/* ── the escort proposal ─────────────────────────────────────────────── */
	.proposal {
		display: flex;
		flex-direction: column;
		border: 1px solid var(--v-act);
		border-left-width: 3px;
		border-radius: var(--v-radius-btn);
		background: var(--v-surface-2);
		overflow: hidden;
	}

	.pr-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 8px;
		padding: 10px 12px 0;
	}

	.pr-tag {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-size: var(--v-text-xs);
		font-weight: 600;
		color: var(--v-act-text);
		white-space: nowrap;
	}

	.pr-tag.ai {
		color: var(--v-ai-text);
	}

	.pr-count {
		font-size: var(--v-text-xs);
		font-variant-numeric: tabular-nums;
		color: var(--v-ink-2);
		white-space: nowrap;
	}

	/* a countdown under 15 s draws the eye with weight, never with red:
	   red is only ever a watchlisted or stolen vehicle (SPEC §2.4) */
	.pr-count.urgent {
		color: var(--v-ink-1);
		font-weight: 600;
	}

	.pr-decider {
		margin: 2px 12px 0;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.pr-why {
		margin: 8px 12px 0;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-1);
	}

	/* a refused POST is the brain's verbatim answer: a quiet line, never red
	   (red is only ever a watchlisted or stolen vehicle, SPEC §2.4) */
	.refused {
		margin: 8px 12px 0;
		padding: 6px 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-1);
		background: var(--v-neutral-veil);
		border-radius: var(--v-radius-chip);
		overflow-wrap: anywhere;
	}

	.outcome {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0;
		padding: 8px 12px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
		border-top: 1px solid var(--v-line-1);
	}

	.outcome.ok {
		color: var(--v-success-text);
	}

	.outcome :global(svg) {
		flex: 0 0 auto;
	}

	/* ── the legacy referred actions ─────────────────────────────────────── */
	.approvals {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 10px 12px;
		border: 1px solid var(--v-line-2);
		border-radius: var(--v-radius-btn);
	}

	.approvals h4 {
		margin: 0;
		font-size: var(--v-text-xs);
		font-weight: 600;
		color: var(--v-ink-2);
	}

	.approval {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.ap-what {
		margin: 0;
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}

	.ap-why {
		margin: 0;
		color: var(--v-ink-2);
		line-height: 16px;
	}

	.ap-out {
		margin: 0;
		font-size: var(--v-text-xs);
		color: var(--v-success-text);
	}

	.ap-out.err {
		color: var(--v-ink-1);
	}

	.ap-actions {
		display: flex;
		gap: 8px;
	}

	.ap-actions :global(button) {
		min-width: 0;
	}
</style>
