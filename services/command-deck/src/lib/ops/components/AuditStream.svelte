<script lang="ts">
	/**
	 * AuditStream — the /ops audit band (SPEC §6.3): the AuditTable of
	 * `$lib/analysis` over the ops ledger, a VIEW OVER SERVER DATA (contract
	 * C-C): the selected live event's GET /api/v1/events/{id}/audit, else the
	 * whole city's GET /api/v1/city/feed (ops.setAuditScope), plus this
	 * console's own local rows (a refusal before the wire, the probe's steps,
	 * an officer's echo that retires when its server row lands — and an echo
	 * about another event waits in the City view, never in this event's).
	 *
	 * Every row keeps the actor kind the oracle recorded (an oracle, twin or
	 * model reply is never shown as human), its row id and its provenance
	 * (Emulated as text in the row, not only a tooltip); the ledger is already
	 * masked under the plate rule (ops.audit), and so is the probe's answer
	 * (`audit-probe-answer`, streamed as sent). A thin wrapper: no props, so
	 * the /ops page mounts it by path.
	 */
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.analysis';
	import { ops, isLiveUuidEvent } from '$lib/ops/store.svelte';
	import AuditTable from '$lib/analysis/audit/AuditTable.svelte';
	import { itemFromEntry, type AuditFilter } from '$lib/analysis/audit/rows';
	import { displayTitle } from '$lib/workspace/display';

	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const selected = $derived(ops.selectedEvent);
	const canFollowEvent = $derived(isLiveUuidEvent(selected));
	const items = $derived(ops.audit.map((e) => itemFromEntry({ ...e, detail: ops.detail(e.detail) }, { lang, officer: ops.officerOn })));
	let filter = $state<AuditFilter>('all');

	const scope = $derived(ops.auditScope === 'city' || !canFollowEvent ? 'city' : 'event');
	const viewLabel = $derived(
		ops.auditView === 'event'
			? L('an_au_view_event', selected ? displayTitle(ops.text(selected.name), lang).slice(0, 60) : '—')
			: ops.auditView === 'city'
				? L('an_au_view_city')
				: ops.auditView === 'legacy'
					? L('an_au_view_legacy')
					: L('an_au_view_none'),
	);
	const rung = $derived(
		ops.auditRung === 'poll'
			? L('an_au_rung_poll')
			: ops.auditRung === 'connecting'
				? L('an_au_rung_connecting')
				: ops.auditRung === 'unavailable'
					? L('an_au_rung_down')
					: L('an_au_rung_ws'),
	);
</script>

{#snippet extra()}
	<span class="rung" class:down={ops.auditRung === 'unavailable'}>{L('an_au_rung', rung)}</span>
	{#if ops.auditNote}<span class="note">{ops.auditNote}</span>{/if}
{/snippet}

<section class="audit-stream" data-prim="panel" aria-label={L('an_au_title')}>
	<AuditTable
		title={L('an_au_title')}
		scope={scope}
		{filter}
		{items}
		probe
		view={ops.auditView}
		{viewLabel}
		viewExtra={extra}
		eventDisabled={canFollowEvent ? null : L('an_au_scope_event_none')}
		onscope={(s) => ops.setAuditScope(s)}
		onfilter={(f) => (filter = f)}
		officer={ops.officerOn}
		{lang}
	/>
</section>

<style>
	.audit-stream {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
		min-width: 0;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-1);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
		overflow: hidden;
	}

	/* the single-column wall (below 1500 px) gives the band no height: the table scrolls inside 480 px */
	@media (max-width: 1499px) {
		.audit-stream {
			max-height: 480px;
		}
	}

	.rung {
		color: var(--v-ink-2);
	}

	.rung.down {
		color: var(--v-warning-text);
	}

	.note {
		color: var(--v-warning-text);
		overflow: hidden;
		text-overflow: ellipsis;
	}
</style>
