<script lang="ts">
	/**
	 * The decision-support ProposalCard body (plan X22; osint SPEC §1.7, §3.4)
	 * — a COA review, inside UI-S5A's ProposalCard. part="why" carries the
	 * decision material: the public-safety floor line (why the do-nothing
	 * baseline sits below a lower-closeness response; FIX-E-DSSCARD), Sajag
	 * AI's pick in indigo when the decider gave one, the COA list (one radio
	 * per COA, the top feasible pre-selected; vetoed and infeasible COAs
	 * disabled with their reason, stated once — never hidden, never
	 * selectable for approval), the EVOI sentence and the dissent behind a
	 * disclosure, the criteria and AHP weights (CR shown) behind another, the
	 * X22 rule note verbatim, and the officer-gated Defer beside them (the
	 * shell's footer carries Reject and Approve). The resource-blocked best
	 * response moved to the card header (BestBlockedBanner, FIX-E-DSSCARD
	 * item 6). part="evidence" carries the provenance (feeds, publishers, the
	 * wargame method labelled "Simulated outcomes") and the honest tags.
	 *
	 * The full C-U object loads from GET /decision-support/{id} when the card
	 * is visible (IntersectionObserver — a hidden /ops item fetches nothing;
	 * plan R11/X13: never a polled GET; the header banner shares the same
	 * once-per-id fetch). The /design harness seeds the object instead.
	 * Nothing here approves on its own: Approve is the shell's footer button,
	 * disabled by the named-officer gate, and the radios make a vetoed or
	 * infeasible COA unselectable. Defer takes the FOOTER'S reason (the
	 * ProposalCard's field) and is gated only on the officer and that note —
	 * never on Approve's own rules (FIX-E-DSSCARD item 1: it sent an empty
	 * note and the writer refused it, dead).
	 */
	import { ops } from '$lib/ops/store.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { toasts } from '$lib/shell/toast.svelte';
	import { ACTION_ICON, ACTOR_ICON, INTENT_ICON } from '$lib/design/icons';
	import { Button, Icon, Id, Note, ProvenanceTag, Reason, Tag } from '$lib/ui';
	import { fmtDuration, fmtStamp } from '$lib/ui/format/format';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.dss';
	import { WRITERS } from '$lib/decisions/writers';
	import { decisionOutcomes } from '$lib/decisions/cards/outcomes.svelte';
	import { dssOf, unitTitle, type Unit } from '$lib/decisions/units';
	import {
		ambulanceDelayOf,
		approveBlocked,
		coaBlockReason,
		coaById,
		coaSelectable,
		defaultCoaId,
		deferBlocked,
		feasibilityLine,
		floorLine,
		nextStepLine,
		rankedRows,
		strategyPriorLine,
	} from '$lib/dss/dss-data';
	import { dssState, ensureDssObject, forgetDssObject, recordDssRefusal, selectCoa } from '$lib/dss/dss-store.svelte';

	let {
		unit,
		part = 'why',
		lang = ops.lang,
		now = null,
		reason = '',
	}: { unit: Unit; part?: 'why' | 'evidence'; lang?: string; now?: number | null; reason?: string } = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const d = $derived(dssOf(unit));
	const clock = $derived(now ?? Date.now());

	// ── the C-U object: seeded by the harness, else fetched when visible ──

	let root = $state<HTMLDivElement | null>(null);

	async function load() {
		if (dssState.objects[unit.id]) return;
		await ensureDssObject(unit.id);
	}

	$effect(() => {
		if (typeof IntersectionObserver === 'undefined') return;
		if (!root) return;
		const io = new IntersectionObserver((entries) => {
			if (entries.some((e) => e.isIntersecting)) void load();
		});
		io.observe(root);
		return () => io.disconnect();
	});

	const dss = $derived(dssState.objects[unit.id] ?? null);
	const loading = $derived(dssState.loading[unit.id] === true);
	const failed = $derived(dssState.failed[unit.id] ?? null);
	const rows = $derived(rankedRows(dss));
	const selectedId = $derived(dssState.selected[unit.id] ?? (dss ? defaultCoaId(dss) : null));
	const selected = $derived(coaById(dss, selectedId));
	const refusal = $derived(dssState.refusals[unit.id] ?? null);

	// ── the footer's verbs, through the same writers the shell uses ───────

	const officer = $derived((commandBar.officer ? commandBar.officer.value : ops.dutyOfficer).trim());
	const block = $derived(approveBlocked(lang, officer, selected));
	const deferBlock = $derived(deferBlocked(lang, officer, reason));
	const busy = $derived(ops.recommendationBusy !== null);

	function choose(coaId: string) {
		selectCoa(unit.id, coaId);
		delete dssState.refusals[unit.id];
	}

	/** The body's own verb (Defer; Reject and Approve are the shell's footer buttons, with their own outcome rows). */
	async function deferNow() {
		const w = WRITERS['dss.defer'];
		const note = reason.trim();
		if (!w || busy || deferBlock) return;
		try {
			const res = (await w.run(unit, officer, { note })) as { ok: boolean; refusal?: string };
			if (res.ok) {
				const verb = L('dec_done_defer_pursuit');
				decisionOutcomes.push({ kind: unit.kind, id: unit.id, title: unitTitle(unit, lang), verb, officer, at: Date.now(), ok: true, detail: null });
				toasts.push({ kind: 'act', title: verb, body: officer });
			}
		} catch (err) {
			// a 5xx must not die as an unhandled rejection the officer never sees:
			// it lands in the same refusal line a 409 does (fix round 2, audit item 9)
			recordDssRefusal(unit.id, 'failed', err instanceof Error ? err.message : String(err));
		}
	}

	const generated = $derived.by(() => {
		const at = dss?.generatedAt ? Date.parse(dss.generatedAt) : NaN;
		if (!Number.isFinite(at)) return null;
		return clock - at > 3600_000 ? L('dss_generated_at', fmtStamp(at, clock)) : L('dss_generated', fmtDuration((clock - at) / 1000, lang));
	});
	const mismatch = $derived(
		!!dss && selectedId !== null && dss.recommendation.topCoaId !== null && selectedId !== dss.recommendation.topCoaId
			? L('dss_pick_mismatch', coaById(dss, dss.recommendation.topCoaId)?.label ?? dss.recommendation.topCoaId)
			: '',
	);
	/** The X2 verification tag accepts the four OSINT labels (never EMULATED/SIMULATED). */
	const verifTag = $derived(
		dss?.verificationState === 'UNVERIFIED-OSINT' || dss?.verificationState === 'NEWS-REPORTED' || dss?.verificationState === 'OFFICIAL-VERIFIED' || dss?.verificationState === 'CONFIRMED'
			? dss.verificationState
			: null,
	);
	const num = (v: number | null, digits = 0) => (v == null ? '—' : digits ? v.toFixed(digits) : String(Math.round(v)));
	const agencyName = (a: { params: Record<string, unknown> }) => {
		const key = `dss_agency_${typeof a.params.agency === 'string' ? a.params.agency : ''}`;
		const v = L(key);
		return v === key ? String(a.params.agency ?? '—') : v;
	};
	const verbLabel = (verb: string) => {
		const v = L(`dss_verb_${verb}`);
		return v === `dss_verb_${verb}` ? verb : v;
	};
</script>

<div bind:this={root}>
	{#if part === 'why'}
		{#if failed}
			<p class="load" data-testid="dss-load-failed"><Icon name={INTENT_ICON.danger} size={16} /> {L('dss_load_failed')} <Id value={failed} /> <Button small onclick={() => ((void forgetDssObject(unit.id)), load())}>{L('dss_retry')}</Button></p>
		{:else if loading && !dss}
			<p class="load"><Icon name="time" size={16} /> {L('dss_loading')}</p>
		{:else if dss}
			{#if floorLine(lang, dss)}
				<p class="floor" data-testid="dss-safety-floor"><Icon name="shield" size={16} />{floorLine(lang, dss)}</p>
			{/if}
			{#if strategyPriorLine(lang, dss)}
				<p class="ai-pick" data-testid="dss-strategy-prior">{strategyPriorLine(lang, dss)}</p>
			{/if}
			{#if mismatch}
				<p class="mismatch">{mismatch}</p>
			{/if}

			<div class="coas" data-testid="dss-coa-list" role="radiogroup" aria-label={L('dss_coa_list')}>
				{#each rows as c (c.coaId)}
					{@const ok = coaSelectable(c)}
					<label class="coa" class:is-selected={selectedId === c.coaId} data-testid="dss-coa" data-coa-id={c.coaId} data-selectable={ok ? '1' : '0'}>
						<input type="radio" name="dss-coa-{unit.id}" value={c.coaId} checked={selectedId === c.coaId} disabled={!ok} onchange={() => choose(c.coaId)} />
						<span class="c-head">
							<span class="c-kind"><Tag>{c.kind}</Tag></span>
							<span class="c-label">{c.label}</span>
							{#if !ok}<span class="c-block">{coaBlockReason(lang, c)}</span>{/if}
						</span>
						<span class="c-line">
							{#if feasibilityLine(lang, c)}<span class="c-feas">{feasibilityLine(lang, c)}</span>{/if}
							<span class="c-num">{#if c.responseToSceneSec != null}{L('dss_coa_time_to_scene', num(c.responseToSceneSec))} · {/if}{L('dss_coa_disruption', num(c.disruption?.mean ?? null, 1), num(c.disruption?.p90 ?? null, 1))}{#if c.spillover?.mean} · {L('dss_coa_spillover', num(c.spillover.mean, 1))}{/if}</span>
							<span class="c-num">{#if ambulanceDelayOf(c) != null}{L('dss_coa_ambulance', ambulanceDelayOf(c))} · {/if}{L('dss_coa_closeness', c.closeness == null ? '—' : c.closeness.toFixed(2))}{#if c.rank != null} · {L('dss_coa_rank', c.rank)}{/if}</span>
						</span>
						{#if c.actions.some((a) => a.requiresOfficer)}<span class="c-officer"><Icon name={ACTOR_ICON.officer} size={12} />{L('dss_coa_officer_gesture')}</span>{/if}
					</label>
				{/each}
			</div>

			<p class="why">{dss.summary}{#if generated}{` · ${generated}`}{/if}</p>

			{#if dss.recommendation.evoiWhy}
				<p class="evoi">{L('dss_why_evoi', dss.recommendation.evoiWhy)}</p>
			{/if}
			{#if dss.recommendation.dissent}
				<details class="disclose">
					<summary>{L('dss_why_dissent')}</summary>
					<p class="dissent">{dss.recommendation.dissent}</p>
				</details>
			{/if}
			{#if dss.criteria.length}
				<details class="disclose">
					<summary>{L('dss_why_criteria')}</summary>
					<p class="dissent">{L('dss_why_criteria_ahp', dss.ahpCr == null ? '—' : dss.ahpCr.toFixed(3))}</p>
					<table class="crit">
						<tbody>
							{#each dss.criteria as c (c.id)}
								<tr data-criterion={c.id}>
									<td>{c.label}</td>
									<td class="num">{c.weight == null ? '—' : c.weight.toFixed(3)}</td>
									<td class="muted">{c.role ?? c.direction ?? ''}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</details>
			{/if}

			<Note icon={ACTION_ICON.decision_support} data-testid="dss-rule-note">{L('dss_rule_note')}</Note>

			{#if nextStepLine(lang, selected)}
				<p class="next">{nextStepLine(lang, selected)}</p>
			{/if}

			<div class="defer-row">
				<Button small icon="time" disabled={deferBlock != null || busy} disabledReason={deferBlock ?? null} tooltip={deferBlock ?? L('dss_defer_hint')} onclick={() => void deferNow()}>{L('dss_defer')}</Button>
			</div>
			{#if block}<Reason text={block} />{/if}
			{#if refusal}
				<!-- a transport failure states the localized sentence; the raw HTTP/JSON error is only the tooltip -->
				<p class="refusal" data-testid="decision-refusal" title={refusal.refusal === 'failed' ? (refusal.detail ?? undefined) : undefined}>{refusal.refusal !== 'failed' && refusal.detail && refusal.detail !== refusal.refusal ? refusal.detail : L(`dss_refuse_${refusal.refusal}`)}</p>
			{/if}
		{:else}
			<p class="load"><Icon name="time" size={16} /> {L('dss_loading')}</p>
		{/if}
	{:else}
		{#if dss}
			<div class="prov" data-testid="dss-provenance">
				<p class="p-line">
					<ProvenanceTag source="osint" verification={verifTag} {lang} />
					<ProvenanceTag source="simulated" {lang} />
				</p>
				<p class="p-line muted">{L('dss_provenance_feeds', dss.provenance.feeds.join(', ') || '—')}</p>
				<p class="p-line muted">{L('dss_provenance_publishers', dss.provenance.publishers.join(', ') || '—')}</p>
				<p class="p-line muted">{L('dss_provenance_wargame')}{#if dss.provenance.wargameMethod}{` · `}<Id value={dss.provenance.wargameMethod} />{/if}{#if generated}{` · ${generated}`}{/if}</p>
				{#if dss.labels.length}
					<p class="p-line">
						{#each dss.labels as lb (lb)}<Tag>{lb}</Tag>{/each}
					</p>
				{/if}
			</div>
		{:else if loading}
			<p class="load">{L('dss_loading')}</p>
		{/if}
	{/if}
</div>

<style>
	.load {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0 0 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
	}

	.floor {
		display: flex;
		align-items: baseline;
		gap: 8px;
		margin: 0 0 8px;
		padding: 8px 12px;
		border-radius: var(--v-radius-chip);
		background: var(--v-neutral-veil);
		font-size: var(--v-text-xs);
		line-height: 18px;
		color: var(--v-ink-1);
		overflow-wrap: anywhere;
	}

	.ai-pick {
		margin: 0 0 4px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ai-text);
	}

	.mismatch {
		margin: 0 0 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
	}

	.coas {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 0 0 10px;
	}

	.coa {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 8px 12px;
		border: 1px solid var(--v-line-1);
		border-radius: var(--v-radius-chip);
		cursor: pointer;
	}

	.coa.is-selected {
		border-color: var(--v-primary-text);
		box-shadow: inset 2px 0 0 var(--v-primary-text);
	}

	.coa:has(input:disabled) {
		cursor: not-allowed;
		color: var(--v-ink-2);
	}

	.coa input {
		position: absolute;
		opacity: 0;
		pointer-events: none;
	}

	.c-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
	}

	.c-label {
		font-weight: 600;
		font-size: var(--v-text-xs);
		line-height: 16px;
		overflow-wrap: anywhere;
	}

	.c-block {
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
		overflow-wrap: anywhere;
	}

	.c-line {
		display: flex;
		flex-wrap: wrap;
		gap: 0 10px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
	}

	.c-feas {
		color: var(--v-ink-1);
	}

	.c-num {
		font-variant-numeric: tabular-nums;
	}

	.c-officer {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.why {
		margin: 0 0 8px;
		font-size: var(--v-text-base);
		line-height: 21px;
		color: var(--v-ink-1);
	}

	.evoi {
		margin: 0 0 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-1);
	}

	.disclose {
		margin: 0 0 8px;
	}

	.disclose summary {
		cursor: pointer;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
	}

	.dissent {
		margin: 6px 0 0;
		font-size: var(--v-text-xs);
		line-height: 18px;
		color: var(--v-ink-1);
		overflow-wrap: anywhere;
	}

	.crit {
		width: 100%;
		margin: 6px 0 0;
		border-collapse: collapse;
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.crit td {
		padding: 2px 8px 2px 0;
		border-bottom: 1px solid var(--v-line-1);
	}

	.crit .num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}

	.muted {
		color: var(--v-ink-2);
	}

	.next {
		margin: 8px 0;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-1);
	}

	.defer-row {
		display: flex;
		margin: 4px 0 0;
	}

	.refusal {
		margin: 8px 0 0;
		padding: 6px 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-1);
		background: var(--v-danger-veil);
		border-radius: var(--v-radius-chip);
		overflow-wrap: anywhere;
	}

	.p-line {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
		margin: 0 0 6px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-1);
	}

	.prov .p-line.muted {
		color: var(--v-ink-2);
	}
</style>
