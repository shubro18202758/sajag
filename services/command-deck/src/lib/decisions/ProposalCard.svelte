<script lang="ts">
	/**
	 * ProposalCard (SPEC §5.3; review B2, B4; prototype review.js) — ONE
	 * anatomy for every decision kind (`data-prim="decision-card"`,
	 * `data-testid="proposal-card"`, `data-kind`, `data-id`). Top to bottom:
	 *
	 *   1. a 2 px expiry bar (time-boxed kinds only: the escort's countdown);
	 *   2. the header: the proposer's glyph (ACTOR_ICON: rules engine, Sajag AI
	 *      in its indigo), an imperative title, the subtitle (who proposed it,
	 *      how long it waited), the tags (Needs decision, the count, the
	 *      countdown, provenance);
	 *   3. What changes — rows of Object | Now | After you decide GENERATED
	 *      from WRITERS (the primary action's writer, else the secondary's);
	 *      "No change" in ink-2; what the writer leaves alone said once;
	 *   4. Why — the kind's body (cards/index.ts) with its ONE rule Note;
	 *   5. Next step — the writer's next, separate decision. For a stolen
	 *      vehicle it is step 2 (Open pursuit), the element
	 *      `[data-kind=pursuit][data-id][data-refusal]` inside the same unit
	 *      (a `queue-card` inside an /ops item);
	 *   6. the evidence mini-table;
	 *   7. DecisionFooter: the officer, the reason, `.ap-actions`.
	 *
	 * After a decision: an outcome row (officer, time), a toast, and the audit
	 * row lands (the store re-polls). Time-boxed kinds are never confirmed
	 * through a modal: the countdown is the constraint (SPEC §5.4).
	 */
	import { ops } from '$lib/ops/store.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { toasts } from '$lib/shell/toast.svelte';
	import { useShellClock, shellClock } from '$lib/shell/clock.svelte';
	import { PROVENANCE_ICON, eventKindIcon, type IconName } from '$lib/design/icons';
	import { Icon, Plate, ProvenanceTag, Tag } from '$lib/ui';
	import { fmtCountdown, fmtTime } from '$lib/ui/format/format';
	import { maskPlatesInText } from '$lib/ops/format';
	import { t } from '$lib/i18n/strings';
	import { tOps } from '$lib/i18n/strings.ops';
	import '$lib/i18n/packs.decisions';
	import { NO_HOST_PROVENANCE, type HostProvenance } from './cards';
	import { UNIT_KINDS, corridorOf, echallanOf, escortOf, pursuitOf, stolenOf, unitTitle, type Unit } from './units';
	import { ACTIONS, writerFor, type ChangeRow, type WriterResult } from './writers';
	import { CARD_BODIES } from './cards';
	import { actorIcon, escortRule, proposerLine, unitPlate } from './cards/meta';
	import { decisionOutcomes } from './cards/outcomes.svelte';
	import DecisionFooter, { type FooterAct } from './DecisionFooter.svelte';
	import BestBlockedBanner from '$lib/dss/BestBlockedBanner.svelte';

	let {
		unit,
		lang = ops.lang,
		item = false,
		sticky = true,
		ondecided,
		officerTestId = 'decision-officer',
		footer = true,
		now: nowProp = null,
		hostProvenance = NO_HOST_PROVENANCE,
	}: {
		unit: Unit;
		lang?: string;
		/** Rendered inside an /ops Decisions item: step 2 carries its `queue-card` hooks. */
		item?: boolean;
		sticky?: boolean;
		ondecided?: (r: WriterResult & { action: string }) => void;
		officerTestId?: string;
		/** Render the decision footer (an /ops item renders it only while expanded: one officer field on the page). */
		footer?: boolean;
		/** The host's clock (epoch ms); the card subscribes to the shell's 1 Hz clock only without one. */
		now?: number | null;
		/** The escort provenance its HOST already states in its own header (the ConvoyCard's Simulated feed /
		 *  Emulated GPS tags): the card leaves those out, so each reads ONCE per card. */
		hostProvenance?: HostProvenance;
	} = $props();

	$effect(() => {
		if (nowProp == null) return useShellClock();
	});
	const now = $derived(nowProp ?? shellClock.now);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	const spec = $derived(UNIT_KINDS[unit.kind]);
	const Body = $derived(CARD_BODIES[unit.kind] ?? null);
	const officerOn = $derived(ops.officerOn);

	// ── the actions this unit offers now ───────────────────────────────────

	const primaryKey = $derived.by((): string | null => {
		switch (unit.kind) {
			case 'stolen-sighting': {
				const d = stolenOf(unit);
				if (d.refusal) return null;
				// once authorised, the next step (open the pursuit) is the one primary
				return d.approved ? (d.step.state === 'open' ? null : 'open') : 'authorise';
			}
			case 'echallan': {
				const d = echallanOf(unit);
				return d.stolen || d.refusal ? null : 'approve';
			}
			default:
				return ACTIONS[unit.kind]?.primary ?? null;
		}
	});
	const secondaryKey = $derived(ACTIONS[unit.kind]?.secondary ?? null);
	/** The writer kind of an action: Open pursuit is the pursuit writer, whatever the unit. */
	const writerKind = (action: string | null) => (action === 'open' ? 'pursuit' : unit.kind);
	const primaryWriter = $derived(writerFor(writerKind(primaryKey), primaryKey));
	const secondaryWriter = $derived(writerFor(writerKind(secondaryKey), secondaryKey));
	const shown = $derived(primaryWriter ?? secondaryWriter);

	let rows = $state<ChangeRow[]>([]);
	let unchanged = $state<string[]>([]);
	$effect(() => {
		// rows read the store (plates through ops.plate): rebuilt when it changes
		void ops.officerOn;
		void lang;
		const w = shown;
		try {
			rows = w ? w.changes(unit) : [];
			unchanged = w ? w.unchanged(unit) : [];
		} catch {
			rows = [];
			unchanged = [];
		}
	});

	// ── header ─────────────────────────────────────────────────────────────

	const title = $derived(unitTitle(unit, lang));
	const plate = $derived(unitPlate(unit));
	const shownPlate = $derived(plate ? ops.plate(plate) : null);
	/** The title with its mark split out (the Plate renders the mark with its lock). */
	const titleParts = $derived.by(() => {
		if (!shownPlate) return { before: title, after: '' };
		const i = title.indexOf(shownPlate);
		return i < 0 ? { before: title, after: '' } : { before: title.slice(0, i), after: title.slice(i + shownPlate.length) };
	});
	const subtitle = $derived(proposerLine(unit, lang, now));
	const ai = $derived(unit.kind === 'escort-proposal' && !escortRule(unit));
	const left = $derived(unit.deadline != null ? (unit.deadline - now) / 1000 : null);
	const timeout = $derived(unit.kind === 'escort-proposal' ? (escortOf(unit).proposal.timeoutSec ?? 90) : null);
	const expiryPct = $derived(left != null && timeout ? Math.max(0, Math.min(100, (left / timeout) * 100)) : null);
	const expired = $derived(spec?.timeBoxed && left != null && left <= 0);

	// ── deciding ───────────────────────────────────────────────────────────

	let reason = $state('');
	let busy = $state(false);
	const storeBusy = $derived(
		ops.recommendationBusy !== null || ops.escortDecisionBusy !== null || ops.dispatchBusy !== null || ops.pursuitBusy !== null,
	);
	const outcomeRow = $derived(decisionOutcomes.of(unit.kind, unit.id, now));

	/** The outcome's words: dec_done_<action>_<group> (a stolen vehicle's steps read as the pursuit's). */
	const doneGroup = (kind: string) =>
		kind === 'escort-proposal' ? 'escort' : kind === 'corridor-request' ? 'corridor' : kind === 'echallan' ? 'echallan' : 'pursuit';

	async function decide(action: string | null) {
		const w = writerFor(writerKind(action), action);
		if (!w || !action || busy) return;
		busy = true;
		const officer = ops.dutyOfficer.trim();
		const masked = maskPlatesInText(unit.title);
		try {
			const res = (await w.run(unit, officer, { note: reason })) as WriterResult;
			if (res.ok) {
				const verb = L(`dec_done_${action}_${doneGroup(unit.kind)}`);
				decisionOutcomes.push({ kind: unit.kind, id: unit.id, title: masked, verb, officer, at: Date.now(), ok: true, detail: null });
				toasts.push({ kind: 'act', title: verb, body: `${masked} · ${officer}` });
				reason = '';
			}
			ondecided?.({ ...res, action });
		} finally {
			busy = false;
		}
	}

	// ── the footer's buttons ───────────────────────────────────────────────

	const needOfficer = $derived(officerOn ? null : L('dec_reason_officer'));

	const primaryAct = $derived.by((): FooterAct | null => {
		if (!primaryKey) return null;
		let label = L('dec_btn_approve');
		let icon: IconName | undefined;
		let block: string | null = needOfficer;
		if (primaryKey === 'authorise') {
			label = tOps(lang, 'queueAuthorisePursuit');
			icon = eventKindIcon('vehicle_pursuit');
		} else if (primaryKey === 'open') {
			label = L('dec_btn_open_pursuit');
			icon = eventKindIcon('vehicle_pursuit');
			const refusal = unit.kind === 'stolen-sighting' ? stolenOf(unit).step.refusal : pursuitOf(unit).refusal;
			if (refusal) block = refusal === 'no-anchor' ? L('dec_refuse_no_anchor') : L('dec_refuse_no_approval');
		}
		if (expired) block = L('dec_reason_expired');
		return { label, icon, disabled: !!block, reason: block, run: () => void decide(primaryKey) };
	});

	const secondaryAct = $derived.by((): FooterAct | null => {
		if (!secondaryKey) return null;
		const needsReason = secondaryKey === 'dismiss' || (secondaryKey === 'reject' && unit.kind !== 'escort-proposal');
		let label = L(`dec_btn_${secondaryKey}`);
		if (secondaryKey === 'dismiss') {
			const n = stolenOf(unit).recs.length;
			label = n > 1 ? L('dec_btn_dismiss_all', n) : L('dec_btn_dismiss');
		}
		let block: string | null = needOfficer;
		if (!block && needsReason && !reason.trim()) block = L(secondaryKey === 'dismiss' ? 'dec_reason_dismiss' : 'dec_reason_reject');
		if (expired) block = L('dec_reason_expired');
		return { label, disabled: !!block, reason: block, run: () => void decide(secondaryKey) };
	});

	const reasonMode = $derived.by((): 'none' | 'required' | 'optional' => {
		if (unit.kind === 'escort-proposal' || unit.kind === 'pursuit') return 'none';
		if (unit.kind === 'corridor-request') return 'optional';
		return 'required';
	});
	/**
	 * The reason field's own copy, per kind (FIX-E-DSSCARD: a dss proposal's
	 * reject AND defer both need the note — the old deferral-only hint was
	 * false for it).
	 */
	const reasonHint = $derived.by(() => {
		if (unit.kind === 'stolen-sighting') return L('dec_reason_info_dismiss');
		if (unit.kind === 'echallan') return L('dec_reason_info_reject');
		if (unit.kind === 'dss') return L('dec_reason_info_dss');
		return L('dec_reason_info_defer');
	});
	/** Each kind's own example reason (a 108 deferral is not a duplicate read). */
	const reasonPlaceholder = $derived.by(() => {
		if (unit.kind === 'echallan') return L('dec_reason_placeholder_echallan');
		if (unit.kind === 'corridor-request') return L('dec_reason_placeholder_corridor');
		if (unit.kind === 'dss') return L('dec_reason_placeholder_dss');
		return L('dec_reason_placeholder');
	});

	const outcomeText = $derived(outcomeRow ? L('dec_outcome', outcomeRow.verb, outcomeRow.officer, fmtTime(outcomeRow.at)) : null);

	function showEvidence() {
		selection.select(unit.subjectUrn, { fly: true, source: 'inbox' });
	}

	// ── step 2 of a stolen vehicle (the pursuit opening, inside this unit) ─

	const step = $derived(unit.kind === 'stolen-sighting' ? stolenOf(unit).step : null);
	const stepRoad = $derived(step?.candidate?.anchor?.roadName ?? null);
	const nextText = $derived(unit.kind === 'stolen-sighting' ? null : (shown?.nextStep?.(unit) ?? null));

	const tags = $derived.by(() => {
		const out: { text: string; intent?: 'warning' | 'danger'; icon?: IconName; testid?: string; alert?: boolean }[] = [];
		out.push({ text: L('dec_tag_needs_decision'), intent: 'warning' });
		if (unit.kind === 'stolen-sighting') out.push({ text: L('dec_tag_sightings', stolenOf(unit).recs.length) });
		if (unit.kind === 'echallan' && echallanOf(unit).stolen)
			out.push({ text: L('dec_tag_reported_stolen'), intent: 'danger', testid: 'stolen-warning', alert: true });
		if (unit.kind === 'corridor-request' && corridorOf(unit).dispatch.requestedBy === '108-driver') out.push({ text: tOps(lang, 'dispatch108') });
		if (unit.kind === 'escort-proposal' && left != null) out.push({ text: L('dec_tag_expires_in', fmtCountdown(left)), intent: 'warning', icon: 'time' });
		return out;
	});
	const emulated = $derived(unit.data.emulated === true && unit.kind !== 'escort-proposal');
	const escortSimulated = $derived(unit.kind === 'escort-proposal' && escortOf(unit).proposal.simulated);
	const escortGps = $derived(unit.kind === 'escort-proposal' && escortOf(unit).lane?.gpsMode === 'emulated');
</script>

<article class="pcard" data-prim="decision-card" data-testid="proposal-card" data-kind={unit.kind} data-id={unit.id}>
	{#if expiryPct != null}
		<div class="expiry" aria-hidden="true"><i style:width="{expiryPct}%" class:urgent={left != null && left < 15}></i></div>
	{/if}

	<header class="pc-head">
		<span class="eicon" class:ai><Icon name={actorIcon(unit)} size={20} /></span>
		<div class="hgrow">
			<h3 class="ttl">
				{titleParts.before}{#if shownPlate && titleParts.before !== title}<Plate mark={shownPlate} masked={!officerOn} />{/if}{titleParts.after}
			</h3>
			<p class="sub" class:ai-sub={ai}>{subtitle}</p>
			<div class="tags">
				{#each tags as tg (tg.text)}
					<Tag intent={tg.intent ?? 'none'} icon={tg.icon} data-testid={tg.testid} role={tg.alert ? 'alert' : undefined}>{tg.text}</Tag>
				{/each}
				{#if emulated}<ProvenanceTag source="emulated" {lang} />{/if}
				{#if !hostProvenance.simulated && escortSimulated}<ProvenanceTag source="simulated" {lang} />{/if}
				{#if !hostProvenance.gps && escortGps}<Tag icon={PROVENANCE_ICON.emulated}>{tOps(lang, 'hudEmulatedGps')}</Tag>{/if}
			</div>
		</div>
	</header>

	{#if unit.kind === 'dss'}
		<!-- FIX-E-DSSCARD item 6: the resource-blocked best response sits in the card header area, above the fold -->
		<BestBlockedBanner {unit} {lang} />
	{/if}

	{#if rows.length}
		<section class="pc-sec">
			<h4 class="lbl">{L('dec_what_changes')}</h4>
			<table class="diff">
				<colgroup><col class="c-obj" /><col class="c-now" /><col /></colgroup>
				<thead><tr><th>{L('dec_col_object')}</th><th>{L('dec_col_now')}</th><th>{L('dec_col_after')}</th></tr></thead>
				<tbody>
					{#each rows as r, i (i)}
						<tr data-writes={r.writes?.join(' ') || undefined}>
							<td class="obj">{r.object}</td>
							<td class="same">{r.now}</td>
							<td class={r.after == null ? 'same' : 'after'}><span class="arrow" aria-hidden="true">→</span> {r.after ?? L('dec_no_change')}</td>
						</tr>
					{/each}
				</tbody>
			</table>
			{#if unchanged.length}<p class="unchanged">{L('dec_unchanged', unchanged.join('; '))}</p>{/if}
		</section>
	{/if}

	<section class="pc-sec">
		<h4 class="lbl">{L('dec_why')}</h4>
		{#if Body}<Body {unit} part="why" {lang} {now} reason={reason} />{/if}
	</section>

	{#if step && step.state !== 'open'}
		{@const d = stolenOf(unit)}
		<section class="pc-sec">
			<div
				class="next"
				class:ready={!!d.approved}
				data-testid={item ? 'queue-card' : 'pursuit-step'}
				data-kind="pursuit"
				data-id={d.vehicleId}
				data-refusal={step.refusal ?? ''}
				data-step="2"
			>
				<Icon name="arrow-right" size={16} />
				<span>
					<b>{d.approved ? L('dec_next_now') : L('dec_next_after_authorise')}</b>
					{' '}{stepRoad ? L('dec_next_open_pursuit_on', stepRoad) : L('dec_next_open_pursuit')}
					{#if d.approved && step.refusal}
						{' '}<span class="refused" data-testid="pursuit-refusal">{step.refusal === 'no-anchor' ? L('dec_refuse_no_anchor') : L('dec_refuse_no_approval')}</span>
					{/if}
				</span>
			</div>
		</section>
	{:else if step && step.state === 'open'}
		<section class="pc-sec"><div class="next done"><Icon name="tick-circle" size={16} /><span>{L('dec_next_pursuit_open')}</span></div></section>
	{:else if nextText}
		<section class="pc-sec"><div class="next"><Icon name="arrow-right" size={16} /><span><b>{L('dec_next_label')}</b>{' '}{nextText}</span></div></section>
	{/if}

	{#if Body}
		<section class="pc-sec ev">
			<h4 class="lbl">{unit.kind === 'stolen-sighting' ? L('dec_sightings_in_decision', stolenOf(unit).recs.length) : L('dec_evidence')}</h4>
			<Body {unit} part="evidence" {lang} {now} {hostProvenance} />
		</section>
	{/if}

	{#if footer}
	<DecisionFooter
		{lang}
		{sticky}
		{reasonMode}
		{reasonHint}
		{reasonPlaceholder}
		{officerTestId}
		reasonTestId={unit.kind === 'stolen-sighting' ? 'stolen-dismiss-reason' : 'decision-reason'}
		bind:reason
		primary={primaryAct}
		secondary={secondaryAct}
		onevidence={unit.kind === 'escort-proposal' ? undefined : showEvidence}
		busy={busy || storeBusy}
		outcome={outcomeText}
		idPrefix={unit.kind}
	/>
	{:else if outcomeText}
		<p class="outcome-line" data-testid="decision-outcome">{outcomeText}</p>
	{/if}
</article>

<style>
	.pcard {
		display: flex;
		flex-direction: column;
		min-width: 0;
		background: var(--v-surface-1);
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
	}

	.expiry {
		height: 2px;
		flex: 0 0 auto;
		background: var(--v-surface-sink);
	}

	.expiry i {
		display: block;
		height: 100%;
		background: var(--v-warning-text);
		transition: width 1s linear;
	}

	.expiry i.urgent {
		background: var(--v-danger-text);
	}

	.pc-head {
		display: flex;
		gap: 12px;
		align-items: flex-start;
		padding: 12px 16px;
		border-bottom: 1px solid var(--v-line-1);
	}

	.eicon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex: 0 0 auto;
		width: 32px;
		height: 32px;
		border-radius: var(--v-radius-btn);
		background: var(--v-surface-3);
		color: var(--v-ink-1);
	}

	.eicon.ai {
		color: var(--v-ai-text);
	}

	.hgrow {
		flex: 1 1 auto;
		min-width: 0;
	}

	.ttl {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0 6px;
		margin: 0;
		font-size: var(--v-text-md);
		font-weight: 600;
		line-height: 20px;
		overflow-wrap: anywhere;
	}

	.sub {
		margin: 4px 0 0;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
	}

	.sub.ai-sub {
		color: var(--v-ai-text);
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		margin-top: 8px;
	}

	.pc-sec {
		padding: 12px 16px 4px;
	}

	.pc-sec.ev {
		padding-bottom: 12px;
	}

	.lbl {
		margin: 0 0 6px;
		font-size: var(--v-text-xs);
		font-weight: 600;
		line-height: 16px;
		color: var(--v-ink-2);
	}

	.diff {
		width: 100%;
		border-collapse: collapse;
		table-layout: fixed;
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.diff col.c-obj {
		width: 44%;
	}

	.diff col.c-now {
		width: 22%;
	}

	.diff th {
		padding: 4px 8px 4px 0;
		text-align: left;
		font-weight: 400;
		color: var(--v-ink-2);
		border-bottom: 1px solid var(--v-line-2);
	}

	.diff td {
		padding: 6px 8px 6px 0;
		border-bottom: 1px solid var(--v-line-1);
		vertical-align: top;
		overflow-wrap: anywhere;
	}

	.diff td.obj,
	.diff td.after {
		color: var(--v-ink-1);
	}

	.diff td.same {
		color: var(--v-ink-2);
	}

	.diff .arrow {
		color: var(--v-ink-2);
	}

	.unchanged {
		margin: 6px 0 0;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
	}

	.next {
		display: flex;
		gap: 8px;
		align-items: flex-start;
		margin: 0 0 8px;
		padding: 8px 12px;
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-1);
	}

	.next :global(svg) {
		flex: 0 0 auto;
		color: var(--v-ink-2);
		margin-top: 0;
	}

	.next b {
		font-weight: 600;
	}

	.next.ready {
		box-shadow: inset 2px 0 0 var(--v-primary-text);
	}

	.next.done :global(svg) {
		color: var(--v-success-text);
	}

	.refused {
		color: var(--v-ink-2);
	}

	.outcome-line {
		margin: 0;
		padding: 8px 16px 12px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
	}
</style>
