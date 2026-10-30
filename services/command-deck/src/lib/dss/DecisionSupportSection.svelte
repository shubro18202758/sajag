<script lang="ts">
	/**
	 * The inspector's "Decision support" section (plan X22) for `osint_event`
	 * and `event` objects — a LINK to the proposal's ONE approval home, never
	 * a second Approve (ownsUnitKinds: ['dss'] keeps the Actions tab from
	 * adding its own link card, so an object carries exactly one per DSS):
	 *
	 *   with a proposed DSS   its summary (top COA, generated time, state)
	 *                         and the link card — "Approve a response · in the
	 *                         Inbox" (on /ops: "· in Decisions");
	 *   with none, decided or expired
	 *                         Generate decision support (dss-generate) — a
	 *                         COMPUTE call (R2), no officer, nothing written;
	 *                         disabled with its reason when the event is
	 *                         closed. On success the new unit appears in its
	 *                         home within one registry poll (a refresh is
	 *                         asked for).
	 *
	 * The section also hosts the Promote dialog (the registered action only
	 * sets the request — a verb button must never carry a modal itself) and
	 * the promoted-event link once promoted_event_id is set.
	 */
	import { ops } from '$lib/ops/store.svelte';
	import { toasts } from '$lib/shell/toast.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { ACTION_ICON } from '$lib/design/icons';
	import { Alert, Button, Icon, Reason } from '$lib/ui';
	import { fmtStamp } from '$lib/ui/format/format';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.dss';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { generateDecisionSupport, type DecisionSupport } from '$lib/ops/client';
	import { coaById, dssHomeSummary, isWaiting, parseDssSummary } from '$lib/dss/dss-data';
	import type { InspectorSectionProps } from '$lib/workspace/types';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { frameContext } from '$lib/workspace/components/frame/context';
	import { homeOf } from '$lib/decisions/homes';
	import { dssState } from '$lib/dss/dss-store.svelte';
	import { promoteDialogCopy, promoteOfficer, runPromote } from '$lib/dss/promote';

	let { row, dossier }: InspectorSectionProps = $props();

	const L = (key: string, ...args: unknown[]) => t(ops.lang, key, ...args);
	/** The label of the proposal's top course of action ("top …" in the summary line). */
	const coaLabelOf = (dss: DecisionSupport | null) => coaById(dss, dss?.recommendation.topCoaId ?? null)?.label ?? null;
	const summary = $derived(parseDssSummary(row.props.dss));
	const waiting = $derived(isWaiting(summary, Date.now()));
	const closed = $derived(row.state === 'completed' || row.state === 'cancelled');
	const promotedId = $derived(typeof row.props.promoted_event_id === 'string' && row.props.promoted_event_id ? (row.props.promoted_event_id as string) : null);
	// the enclosing frame names the route (as DecisionLinks reads it); outside any frame — the
	// /ops inspector, the legacy City Command drawer, a harness — the page's own path does
	// (falling back to '/'): /ops has no Inbox, so its home is Decisions
	const frame = frameContext();
	const route = $derived.by((): '/' | '/gods-eye' | '/ops' => {
		const r = frame?.route() ?? (typeof location !== 'undefined' ? location.pathname : '/');
		return r === '/gods-eye' || r === '/ops' ? r : '/';
	});
	const home = $derived(homeOf('dss', route));

	// ── generate (compute only) ────────────────────────────────────────────

	let generating = $state(false);
	let generateFailed = $state<string | null>(null);

	async function generate() {
		if (generating) return;
		generating = true;
		generateFailed = null;
		try {
			const dss = await generateDecisionSupport(row.urn, { horizonMin: 120 });
			toasts.push({ kind: 'act', title: L('dss_generate_hint'), body: coaLabelOf(dss) ?? dss.dssId });
			await cityRegistry.refresh();
		} catch (err) {
			generateFailed = err instanceof Error ? err.message : String(err);
		} finally {
			generating = false;
		}
	}

	// ── the promote dialog this section hosts ──────────────────────────────

	let promoteNote = $state('');
	let promoting = $state(false);
	let promoteBlock = $state<string | null>(null);
	const promoteOpen = $derived(dssState.promoteUrn === row.urn);
	const officer = $derived(promoteOfficer());
	const promoteRefusal = $derived(dssState.refusals[`promote:${row.urn}`] ?? null);

	async function confirmPromote() {
		if (promoting) return;
		promoting = true;
		promoteBlock = null;
		try {
			const ok = await runPromote(row, promoteNote);
			if (ok) {
				toasts.push({ kind: 'act', title: L('dss_promote_label'), body: officer });
				promoteNote = '';
				await cityRegistry.refresh();
			}
		} catch (err) {
			promoteBlock = err instanceof Error ? err.message : String(err);
		} finally {
			promoting = false;
		}
	}

	function cancelPromote() {
		dssState.promoteUrn = null;
		promoteBlock = null;
	}

	const generatedAt = $derived.by(() => {
		const at = summary?.generatedAt ? Date.parse(summary.generatedAt) : NaN;
		return Number.isFinite(at) ? fmtStamp(at) : null;
	});
</script>

<div class="dss-sec" data-testid="dss-section">
	{#if waiting && summary}
		<div class="sum">
			<Icon name={ACTION_ICON.decision_support} size={16} />
			<span class="sum-body">
				<b>{L('dss_section_proposed', summary.topCoaLabel ?? '—')}</b>
				{#if generatedAt}{` · ${generatedAt} IST`}{/if}
				{` · ${summary.state}`}
			</span>
		</div>
		<button
			type="button"
			class="link"
			data-testid="dss-link"
			onclick={() => {
				// FIX-E-DSSCARD item 2: the home opens through the workspace's one-home
				// rule (a raw `/#inbox=…` href opened nothing on / and navigated away
				// from /gods-eye); never a second Approve here.
				const s = dssHomeSummary(summary, row.urn);
				if (s) workspace.openDecisionHome(s, route);
			}}
		>
			<Icon name="arrow-right" size={16} />
			<span>{home === 'decisions' ? L('dss_link_decisions') : L('dss_link_inbox')}</span>
		</button>
	{:else}
		{#if summary && !waiting}
			<p class="quiet">
				{L('dss_decided_line', summary.state)}{#if promotedId}
					{` · `}
					<button type="button" class="evlink" onclick={() => selection.select(`event:${promotedId}`, { fly: true, source: 'dossier' })}>{L('dss_promoted_line')}</button>
				{/if}
			</p>
		{/if}
		<Button
			small
			icon={ACTION_ICON.decision_support}
			loading={generating}
			disabled={closed || generating}
			disabledReason={closed ? L('dss_generate_closed') : null}
			data-testid="dss-generate"
			onclick={() => void generate()}
		>
			{generating ? L('dss_generate_working') : L('dss_generate')}
		</Button>
		<p class="hint">{L('dss_generate_hint')}</p>
		{#if generateFailed}
			<Reason text={generateFailed} />
		{/if}
	{/if}

	{#if promoteOpen}
		<Alert
			open={promoteOpen}
			icon={ACTION_ICON.promote}
			confirmLabel={promoting ? L('dss_promote_busy') : L('dss_promote_confirm')}
			loading={promoting}
			canEscapeKeyClose={false}
			onconfirm={() => void confirmPromote()}
			oncancel={cancelPromote}
		>
			<div class="dlg" data-testid="dss-promote-dialog">
				<p class="dlg-copy">{promoteDialogCopy(row, ops.lang)}</p>
				<input class="dlg-note" placeholder={L('dss_promote_note')} maxlength={500} bind:value={promoteNote} disabled={promoting} />
				{#if promoteBlock}<Reason text={promoteBlock} />{/if}
				{#if promoteRefusal && !promoteBlock}
					<p class="refusal" data-testid="promote-refusal">{promoteRefusal.detail ?? promoteRefusal.refusal}</p>
				{/if}
			</div>
		</Alert>
	{/if}
</div>

<style>
	.dss-sec {
		display: flex;
		flex-direction: column;
		gap: 8px;
		/* the section host is full-bleed: the 16 px gutter is the section's own (fix round 2) */
		padding: 2px 16px 4px;
	}

	.sum {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-1);
	}

	.sum :global(svg) {
		color: var(--v-ink-2);
		flex: 0 0 auto;
		margin-top: 0;
	}

	.sum-body {
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.link {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0 0 0 4px;
		padding: 8px 12px;
		border: 1px solid var(--v-line-1);
		border-radius: var(--v-radius-chip);
		background: none;
		color: var(--v-ink-1);
		font: inherit;
		font-size: var(--v-text-xs);
		line-height: 16px;
		text-align: left;
		text-decoration: none;
		cursor: pointer;
	}

	.link :global(svg) {
		color: var(--v-ink-2);
	}

	.link:hover {
		border-color: var(--v-line-2);
	}

	.quiet {
		display: flex;
		flex-wrap: wrap;
		gap: 0 6px;
		margin: 0;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
	}

	.evlink {
		padding: 0;
		border: 0;
		background: none;
		font: inherit;
		color: var(--v-ink-1);
		text-decoration: underline;
		cursor: pointer;
	}

	.hint {
		margin: 0;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
	}

	.dlg {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.dlg-copy {
		margin: 0;
		font-size: var(--v-text-base);
		line-height: 21px;
		color: var(--v-ink-1);
	}

	.dlg-note {
		padding: 6px 8px;
		border: 1px solid var(--v-line-2);
		border-radius: var(--v-radius-chip);
		background: var(--v-surface-1);
		color: var(--v-ink-1);
		font: inherit;
		font-size: var(--v-text-sm);
	}

	.refusal {
		margin: 0;
		padding: 6px 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-1);
		background: var(--v-danger-veil);
		border-radius: var(--v-radius-chip);
		overflow-wrap: anywhere;
	}
</style>
