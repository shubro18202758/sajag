<script lang="ts">
	/**
	 * Corridor operations (SPEC §6.3 col 2, §9.2; ownership UI-S5B): the
	 * city's corridor events in three tabs, Open · Completed · Cancelled.
	 *
	 *   Open       the live board (GET /events/active, planning → active),
	 *              plus the labelled use-case fixtures while the Fixtures
	 *              switch is on (`preview-toggle`; rows keep `.fixture`).
	 *              Each row: the kind's glyph, the title (plate-masked
	 *              unless a duty officer is named, then through the display
	 *              layer), its provenance marks (RowProvenance: a uniform list
 *              states its provenance once in the header, a mixed list marks
 *              each emulated row with the compact glyph, a test row ALWAYS
 *              shows a visible "Test" tag), the window in IST, the
	 *              kind, class and state, and the C-F lifecycle verbs
	 *              (EventLifecycleVerbs: one POST per click under the named
	 *              officer; CANCEL keeps its inline confirmation,
	 *              `.cancel-row input`). The selected row also lists its
	 *              phases (`phase-window`, the dossier's formatter, so the two
	 *              always agree) and its route.
	 *   Completed  the event history (GET /events?limit=200) within the
	 *   Cancelled  wall's range, newest change first.
	 *
	 * Selecting is a row click: the event is selected everywhere (the board,
	 * the band, the audit scope, the map) and the inspector opens on it; a
	 * fixture only moves the board's selection (it is not a city object).
	 * Rows keep `event-card` with `data-event-id` and `data-status`, and
	 * `.selected` on the selected one. A promoted OSINT event shows its
	 * verification tag WITH its visible label, and its credibility
	 * (decisions/wall/EventProvenance; SPEC §9.2, ethics rule 7).
	 */
	import { eventKindIcon } from '$lib/design/icons';
	import { Icon, NonIdealState, ProvenanceTag, Section, Switch, Tabs, Tooltip } from '$lib/ui';
	import { fmtRange } from '$lib/ui/format/format';
	import { kindLabel, t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';
	import EventLifecycleVerbs from './EventLifecycleVerbs.svelte';
	import { ops, eventVerbs } from '$lib/ops/store.svelte';
	import { fmtWindowIst } from '$lib/ops/format';
	import { displayTitle } from '$lib/workspace/display';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { wallData, type HistoryEvent } from '$lib/decisions/wall/wall-data.svelte';
	import Age from '$lib/decisions/wall/Age.svelte';
	import RowProvenance from '$lib/decisions/wall/RowProvenance.svelte';
	import { countable, uniformLabel, uniformProvenance } from '$lib/decisions/wall/provenance';
	import type { CorridorEvent } from '$lib/ops/types';

	interface Props {
		/** The wall's range: the closed tabs list what changed within it. */
		window: readonly [number, number];
	}

	let { window: range }: Props = $props();

	type Tab = 'open' | 'completed' | 'cancelled';

	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);

	let clock = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (clock = Date.now()), 1000);
		return () => clearInterval(id);
	});

	const open = $derived(ops.events.filter((e) => e.state !== 'completed' && e.state !== 'cancelled'));
	const inRange = (h: HistoryEvent) => (h.updatedAt ?? h.actualEnd ?? 0) >= range[0];
	const closed = $derived(wallData.history.filter((h) => !ops.events.some((e) => e.eventId === h.event.eventId)));
	const completed = $derived(closed.filter((h) => h.event.state === 'completed' && inRange(h)));
	const cancelled = $derived(closed.filter((h) => h.event.state === 'cancelled' && inRange(h)));

	/** The operator's tab; until they choose, Open when anything is open, else Completed. */
	let chosen = $state<Tab | null>(null);
	const tab = $derived<Tab>(chosen ?? (open.length || !wallData.historyUpdated ? 'open' : 'completed'));

	// test and rehearsal rows are listed (and tagged) but kept out of the counts (SPEC §9.2)
	const tabs = $derived([
		{ id: 'open' as const, label: L('wall_ops_open'), count: countable(open).length },
		{ id: 'completed' as const, label: L('wall_ops_completed'), count: countable(completed.map((h) => h.event)).length },
		{ id: 'cancelled' as const, label: L('wall_ops_cancelled'), count: countable(cancelled.map((h) => h.event)).length },
	]);

	/** Title as shown: masked unless an officer is named, then the display layer. */
	function title(ev: CorridorEvent): string {
		return displayTitle(ops.text(ev.name), lang) || ev.eventId.slice(0, 8);
	}

	/** The event's window: its phases' span, else the planned window. */
	function windowOf(ev: CorridorEvent, h?: HistoryEvent): [string | number | null, string | number | null] {
		const starts = ev.phases.map((p) => p.startTime).filter((x): x is string => !!x);
		const ends = ev.phases.map((p) => p.endTime).filter((x): x is string => !!x);
		const a = h?.actualStart ?? ev.windowStart ?? starts.sort()[0] ?? null;
		const b = h?.actualEnd ?? ev.windowEnd ?? ends.sort().at(-1) ?? null;
		return [a, b];
	}

	function windowText(ev: CorridorEvent, h?: HistoryEvent): string {
		const [a, b] = windowOf(ev, h);
		if (a == null) return '—';
		return b == null ? L('wall_ops_from', fmtRange(a, null, clock)) : fmtRange(a, b, clock);
	}

	function stateWord(ev: CorridorEvent): string {
		const raw = ev.status ?? ev.state;
		const key = `wall_state_${raw}`;
		const w = L(key);
		return w === key ? raw : w;
	}

	function classWord(ev: CorridorEvent): string | null {
		return ev.protectionClass && ev.protectionClass !== 'none' ? ev.protectionClass : null;
	}

	function roads(ev: CorridorEvent): string {
		const names: string[] = [];
		for (const id of ev.routeSegmentIds) {
			const n = ops.roadName(id) ?? `#${id}`;
			if (!names.includes(n)) names.push(n);
		}
		return names.length > 4 ? `${names.slice(0, 4).join(', ')} +${names.length - 4}` : names.join(', ');
	}

	function pick(ev: CorridorEvent) {
		if (ev.source === 'offline-fixture') {
			selection.clear();
			ops.selectEvent(ev.eventId);
			return;
		}
		if (ops.selectedEventId !== ev.eventId) ops.selectEvent(ev.eventId);
		selection.select(`event:${ev.eventId}`, { source: 'table' });
	}

	function pickHistory(h: HistoryEvent) {
		selection.select(`event:${h.event.eventId}`, { source: 'table' });
	}

	function onKey(e: KeyboardEvent, fn: () => void) {
		if (e.target !== e.currentTarget) return;
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			fn();
		}
	}

	const historyRows = $derived(tab === 'completed' ? completed : tab === 'cancelled' ? cancelled : []);

	/** The rows on screen: a uniform list states its provenance once, in the header (SPEC §9.2). */
	const shown = $derived(tab === 'open' ? open : historyRows.map((h) => h.event));
	const uniform = $derived(uniformProvenance(shown));
</script>

{#snippet glyphs(ev: CorridorEvent)}
	<RowProvenance event={ev} {lang} uniform={uniform === 'emulated'} />
{/snippet}

{#snippet right()}
	{#if uniform === 'emulated'}
		<Tooltip content={L('wall_ops_uniform_tip')}>
			<span class="uniform" data-testid="ops-uniform-provenance" data-source="emulated">
				{#if shown.length > 1}
					<ProvenanceTag source="emulated" compact {lang} /><span class="all">{uniformLabel(shown.length, lang)}</span>
				{:else}
					<ProvenanceTag source="emulated" {lang} />
				{/if}
			</span>
		</Tooltip>
	{/if}
	<Age at={ops.boardUpdated || null} {lang} />
	<Tooltip content={L('wall_ops_preview_tip')}>
		<span class="preview">
			<Switch small checked={ops.previewFixtures} onchange={(c) => ops.setPreviewFixtures(c)} data-testid="preview-toggle" label={L('wall_ops_preview')} />
		</span>
	</Tooltip>
{/snippet}

<Section title={L('wall_ops')} icon={eventKindIcon(null)} level={2} {right} data-prim="panel" data-wall="corridor-operations">
	<div class="tabs"><Tabs items={tabs} value={tab} onchange={(id) => (chosen = id)} height={36} label={L('wall_ops')} /></div>
	{#if ops.boardNote && tab === 'open'}<p class="note">{ops.boardNote}</p>{/if}

	{#if tab === 'open'}
		{#if open.length === 0}
			<div class="empty"><NonIdealState icon={eventKindIcon(null)} iconSize={32} title={L('wall_ops_none_open')} description={L('wall_ops_none_open_hint')} /></div>
		{:else}
			<table class="wdt ev">
				<colgroup><col style:width="32px" /><col /><col style:width="132px" /></colgroup>
				<thead>
					<tr><th class="ic-col" aria-hidden="true"></th><th scope="col">{L('wall_ops_col_event')}</th><th scope="col" class="num">{L('wall_ops_col_window')}</th></tr>
				</thead>
				{#each open as ev (ev.eventId)}
					{@const sel = ops.selectedEventId === ev.eventId}
					{@const verbs = ev.source !== 'offline-fixture' && (eventVerbs(ev).length > 0 || ops.eventOutcome?.eventId === ev.eventId)}
					<tbody
						class={['pick', sel && 'selected is-selected', ev.source === 'offline-fixture' && 'fixture']}
						data-testid="event-card"
						data-event-id={ev.eventId}
						data-status={ev.status ?? ev.state}
						data-kind={ev.eventKind}
					>
						<tr class="main two" tabindex="0" aria-selected={sel} onclick={() => pick(ev)} onkeydown={(e) => onKey(e, () => pick(ev))}>
							<td class="ic-col"><div class="c"><Icon name={eventKindIcon(ev.eventKind)} size={16} /></div></td>
							<td>
								<div class="c l1"><span class="ell ttl" title={title(ev)}>{title(ev)}</span>{@render glyphs(ev)}</div>
								<div class="c l2"><span class="ell muted">{kindLabel(lang, ev.eventKind)}{classWord(ev) ? ` · ${classWord(ev)}` : ''}</span></div>
							</td>
							<td class="num">
								<div class="c l1"><span class="tn">{windowText(ev)}</span></div>
								<div class="c l2"><span class="state st-{ev.state}">{stateWord(ev)}</span></div>
							</td>
						</tr>
						{#if verbs}
							<tr class="acts">
								<td></td>
								<td colspan="2">
									<!-- the verbs act on this event only: a click here never re-selects the row -->
									<div class="verbs" role="presentation" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
										<EventLifecycleVerbs event={ev} compact />
									</div>
								</td>
							</tr>
						{/if}
						{#if sel && (ev.phases.length || ev.routeSegmentIds.length)}
							<tr class="detail">
								<td></td>
								<td colspan="2">
									{#if ev.phases.length}
										<div class="phases">
											{#each ev.phases as ph, i (i)}
												<div class="phase">
													<span class="ph-label">{ph.label}</span>
													<span class="tn" data-testid="phase-window" data-phase-index={i}>{fmtWindowIst(ph.startTime, ph.endTime, clock)}</span>
													{#if ph.closurePolicy?.closureType}
														<span class="muted">{L(`wall_closure_${ph.closurePolicy.closureType}`)}{ph.closurePolicy.advanceClosureSec != null ? ` · ${L('wall_ops_advance', ph.closurePolicy.advanceClosureSec)}` : ''}</span>
													{/if}
												</div>
											{/each}
										</div>
									{/if}
									{#if ev.routeSegmentIds.length}
										<div class="route"><span class="muted">{L('wall_ops_route')}</span><span class="ell" title={roads(ev)}>{roads(ev)}</span></div>
									{/if}
								</td>
							</tr>
						{/if}
					</tbody>
				{/each}
			</table>
		{/if}
	{:else if historyRows.length === 0}
		<div class="empty">
			<NonIdealState
				icon="history"
				iconSize={32}
				title={wallData.historyNote && !wallData.historyUpdated ? L('wall_ops_history_down') : L(tab === 'completed' ? 'wall_ops_none_completed' : 'wall_ops_none_cancelled')}
				description={wallData.historyNote ?? L('wall_ops_none_closed_hint')}
			/>
		</div>
	{:else}
		<table class="wdt ev">
			<colgroup><col style:width="32px" /><col /><col style:width="120px" /><col style:width="132px" /></colgroup>
			<thead>
				<tr>
					<th class="ic-col" aria-hidden="true"></th>
					<th scope="col">{L('wall_ops_col_event')}</th>
					<th scope="col">{L('wall_ops_col_kind')}</th>
					<th scope="col" class="num">{L('wall_ops_col_window')}</th>
				</tr>
			</thead>
			{#each historyRows as h (h.event.eventId)}
				{@const sel = selection.current === `event:${h.event.eventId}`}
				<tbody class={['pick', sel && 'is-selected']} data-testid="event-card" data-event-id={h.event.eventId} data-status={h.event.status ?? h.event.state} data-kind={h.event.eventKind}>
					<tr class="main" tabindex="0" aria-selected={sel} onclick={() => pickHistory(h)} onkeydown={(e) => onKey(e, () => pickHistory(h))}>
						<td class="ic-col"><div class="c"><Icon name={eventKindIcon(h.event.eventKind)} size={16} /></div></td>
						<td><div class="c"><span class="ell" title={title(h.event)}>{title(h.event)}</span>{@render glyphs(h.event)}</div></td>
						<td><div class="c"><span class="ell muted">{kindLabel(lang, h.event.eventKind)}</span></div></td>
						<td class="num"><div class="c"><span class="tn">{windowText(h.event, h)}</span></div></td>
					</tr>
				</tbody>
			{/each}
		</table>
	{/if}
</Section>

<style>
	.tabs {
		padding: 0 8px 0 16px;
		border-bottom: 1px solid var(--v-line-1);
	}

	.uniform {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		margin-right: 8px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		white-space: nowrap;
	}

	.preview {
		display: inline-flex;
		margin-left: 8px;
	}

	.preview :global([data-ui='switch']) {
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
	}

	.note {
		margin: 0;
		padding: 6px 16px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		border-bottom: 1px solid var(--v-line-1);
	}

	.empty {
		padding: 20px 16px 24px;
	}

	.ev tr.two > td {
		height: 44px;
		padding-top: 4px;
		padding-bottom: 4px;
		vertical-align: middle;
	}

	.ev tr.two .l1 {
		font-size: var(--v-text-base);
		line-height: 18px;
	}

	.ev tr.two .l2 {
		margin-top: 2px;
		font-size: var(--v-text-xs);
	}

	.ev tr.two .ic-col {
		vertical-align: top;
		padding-top: 7px;
	}

	.ttl {
		flex: 0 1 auto;
	}

	.state {
		color: var(--v-ink-2);
	}

	.state.st-active {
		color: var(--v-ink-1);
	}

	.ev tr.acts > td {
		height: auto;
		padding-top: 0;
		padding-bottom: 8px;
		overflow: visible;
		white-space: normal;
	}

	.ev tbody.pick > tr.main + tr > td {
		border-top: 0;
	}

	/* a row's lines read as one row: only its last line draws the divider */
	.ev tbody > tr:not(:last-child) > td {
		border-bottom-color: transparent;
	}

	.verbs {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}

	.phases {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.phase {
		display: flex;
		align-items: baseline;
		gap: 8px;
		min-width: 0;
		line-height: 18px;
	}

	.ph-label {
		min-width: 72px;
		color: var(--v-ink-1);
	}

	.route {
		display: flex;
		align-items: baseline;
		gap: 8px;
		min-width: 0;
		margin-top: 4px;
		line-height: 18px;
	}

	.muted {
		color: var(--v-ink-2);
	}

	.tn {
		font-variant-numeric: tabular-nums;
	}

	.fixture .ttl {
		color: var(--v-ink-2);
	}
</style>
