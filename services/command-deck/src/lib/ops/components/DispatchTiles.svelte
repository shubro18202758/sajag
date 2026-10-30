<script lang="ts">
	/**
	 * Dispatch (SPEC §6.3 col 3, §5.4; ownership UI-S5B): agency units on the
	 * city's corridor events, as a dense table, and the request form.
	 *
	 *   request   for the selected LIVE event (`dispatch-request`): the agency
	 *             from the closed registry (`dispatch-agency`; its suggested
	 *             unit pre-fills `dispatch-unit` until the officer types one),
	 *             the waypoint (`dispatch-waypoint`: the pursuit's chokes
	 *             from its interception plan, a likely-passed choke after the
	 *             live ones, else the junctions nearest the event's route),
	 *             a note, and Request unit (`dispatch-request-btn`), which
	 *             stays disabled with its reason until a duty officer is named.
	 *             Without an open live event the section says, inline:
	 *             "Requesting a unit needs an open event and a named duty
	 *             officer." The form is rendered in the section (not a
	 *             popover) so its controls stay addressable.
	 *   table     one `dispatch-tile` per dispatch (`data-dispatch-id`,
	 *             `data-status`, `data-waypoint`): unit, agency, waypoint,
	 *             status, requested time (one format per column). A unit
	 *             whose event has closed is labelled (`dispatch-event-closed`)
	 *             and never counted. The audit tail (`.audit-toggle`) lists
	 *             each transition with its actor; notes print under the plate
	 *             rule. Terminal dispatches older than 30 min fold behind
	 *             `dispatch-history` ("History (n)").
	 *   decisions a requested unit is decided (Approve / Defer) in its one
	 *             home, the Decisions column (SPEC §5.4); this table offers
	 *             only the unit's own progress (en route, on scene, complete)
	 *             and Cancel, each under the named officer.
	 */
	import { kindIcon, type IconName } from '$lib/design/icons';
	import { Button, HTMLSelect, Icon, Id, Input, ProvenanceTag, Reason, Section, Tag } from '$lib/ui';
	import { colStamp, fmtTime } from '$lib/ui/format/format';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';
	import '$lib/i18n/packs.dss';
	import { tOps } from '$lib/i18n/strings.ops';
	import { ops, isLiveUuidEvent, actorKindOfName } from '$lib/ops/store.svelte';
	import { isEmulatedActor } from '$lib/ops/client';
	import { AGENCIES, DEFAULT_UNIT_ID, DISPATCH_TRANSITIONS, type AgencyCode, type DispatchState } from '$lib/ops/endpoints';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { displayActor, displayTitle } from '$lib/workspace/display';
	import Age from '$lib/decisions/wall/Age.svelte';
	import type { DispatchRecord, WaypointOption } from '$lib/ops/types';

	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	/** The agency in the reader's language (the DSS pack's word for a known agency), else the server's label. */
	const agencyWord = (code: string, label: string) => {
		const key = `dss_agency_${code}`;
		const v = t(lang, key);
		return lang !== 'en' && v !== key ? v : label;
	};

	/** Agency → glyph (a named map; the unit kind's glyph for the rest). */
	const AGENCY_ICON: Readonly<Record<string, IconName>> = { ambulance: 'pulse', fire: 'flash' };

	let clock = $state(Date.now());
	$effect(() => {
		const id = setInterval(() => (clock = Date.now()), 1000);
		return () => clearInterval(id);
	});

	// ── the request form ──────────────────────────────────────────────────
	let agency = $state<AgencyCode>('jan_rakshak');
	let unitId = $state(DEFAULT_UNIT_ID.jan_rakshak);
	let unitTouched = $state(false);
	/** '' = the first offered waypoint; 'none' = no waypoint; else a junction id. */
	let waypointChoice = $state('');
	let note = $state('');

	const selected = $derived(ops.selectedEvent);
	const canRequest = $derived(isLiveUuidEvent(selected));
	const waypoints = $derived(ops.waypointOptions(selected));
	const waypoint = $derived.by((): WaypointOption | null => {
		if (waypointChoice === 'none') return null;
		if (waypointChoice) return waypoints.find((w) => String(w.junctionId) === waypointChoice) ?? waypoints[0] ?? null;
		return waypoints[0] ?? null;
	});

	// a new subject starts from its first (best) waypoint; a board re-poll keeps the officer's pick
	$effect(() => {
		void ops.selectedEventId;
		waypointChoice = '';
	});

	// the agency's suggested unit, until the officer types their own
	$effect(() => {
		const a = agency;
		if (!unitTouched) unitId = DEFAULT_UNIT_ID[a] ?? unitId;
	});

	function waypointText(w: WaypointOption): string {
		return w.source === 'interception'
			? tOps(lang, 'dispatchToChoke', w.rank, w.name) + (w.likelyPassed ? ` · ${L('wall_dispatch_passed')}` : '')
			: L('wall_dispatch_near', w.junctionId, w.name, Math.round(w.distanceM ?? 0));
	}

	const agencyOptions = $derived(Object.entries(AGENCIES).map(([code, a]) => ({ value: code, label: a.label })));
	const waypointOptions = $derived([
		...waypoints.map((w) => ({ value: String(w.junctionId), label: waypointText(w) })),
		{ value: 'none', label: L('wall_dispatch_no_waypoint') },
	]);

	const requestReason = $derived(!canRequest || !ops.officerOn ? L('wall_dispatch_reason') : null);

	async function requestUnit() {
		const ev = ops.selectedEvent;
		if (!isLiveUuidEvent(ev)) return;
		const sent = await ops.requestDispatchUnit(ev.eventId, {
			agency,
			unitId: unitId.trim() || DEFAULT_UNIT_ID[agency],
			waypointJunction: waypoint?.junctionId ?? null,
			note: note.trim() || undefined,
		});
		// the note belonged to THAT request: the next one starts blank
		if (sent) note = '';
	}

	// ── the table ─────────────────────────────────────────────────────────
	const HISTORY_AFTER_MS = 30 * 60_000;
	const TERMINAL = new Set(['completed', 'cancelled', 'deferred']);
	const LIVE = new Set(['requested', 'approved', 'en_route', 'on_scene']);
	let historyOpen = $state(false);
	let openAudit = $state<string | null>(null);

	function emulatedDispatch(d: DispatchRecord): boolean {
		return !!ops.eventById(d.eventId)?.emulated || isEmulatedActor(d.requestedBy);
	}

	function isHistory(d: DispatchRecord): boolean {
		if (!TERMINAL.has(d.status)) return false;
		const at = Date.parse(d.updatedAt ?? d.createdAt ?? '');
		return !Number.isFinite(at) || clock - at > HISTORY_AFTER_MS;
	}

	/** 108-driver requests first, then other open requests, units out, then the rest. */
	function rank(d: DispatchRecord): number {
		if (d.status === 'requested' && d.agency === 'ambulance' && d.requestedBy === '108-driver') return 0;
		if (d.status === 'requested') return 1;
		if (LIVE.has(d.status)) return 2;
		return 3;
	}

	const sorted = $derived(
		[...ops.dispatches]
			.filter((d) => !(ops.hideEmulated && emulatedDispatch(d)))
			.sort((a, b) => rank(a) - rank(b) || Date.parse(b.updatedAt ?? b.createdAt ?? '') - Date.parse(a.updatedAt ?? a.createdAt ?? '')),
	);
	const history = $derived(sorted.filter(isHistory));
	const current = $derived(sorted.filter((d) => !isHistory(d)).slice(0, 10));
	const shown = $derived([...current, ...(historyOpen ? history : [])]);
	const openCount = $derived(ops.dispatches.filter((d) => LIVE.has(d.status) && !ops.dispatchEventClosed(d)).length);
	const anyEmulated = $derived(ops.dispatches.some(emulatedDispatch));
	const stamps = $derived(colStamp(shown.map((d) => d.createdAt ?? d.updatedAt), clock));

	function statusWord(s: string): string {
		const key = `wall_dispatch_st_${s}`;
		const w = L(key);
		return w === key ? s : w;
	}

	/** The unit's own progress (never Approve / Defer: those are decisions, decided in the Decisions column). */
	function progressVerbs(status: string): DispatchState[] {
		return (DISPATCH_TRANSITIONS[status as DispatchState] ?? []).filter((v) => v !== 'approved' && v !== 'deferred');
	}

	async function fire(id: string, v: DispatchState) {
		await ops.advanceDispatchStatus(id, v as 'en_route' | 'on_scene' | 'completed' | 'cancelled');
	}

	function pick(d: DispatchRecord) {
		selection.select(`dispatch:${d.dispatchId}`, { source: 'table' });
	}

	function onKey(e: KeyboardEvent, d: DispatchRecord) {
		if (e.target !== e.currentTarget) return;
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			pick(d);
		}
	}

	function eventTitle(id: string | null): string | null {
		const ev = ops.eventById(id);
		return ev ? displayTitle(ops.text(ev.name), lang) : null;
	}
</script>

{#snippet right()}
	<Age at={ops.dispatchesUpdated || null} {lang} />
{/snippet}

<Section title={L('wall_dispatch')} icon={kindIcon('dispatch')} level={2} sub={L('wall_dispatch_open', openCount)} {right} data-prim="panel" data-wall="dispatch">
	{#if requestReason}
		<div class="reason"><Reason text={requestReason} /></div>
	{/if}

	{#if canRequest && selected}
		<div class="req" data-testid="dispatch-request">
			<div class="req-for"><span class="muted">{L('wall_dispatch_for')}</span><span class="ell">{displayTitle(ops.text(selected.name), lang)}</span></div>
			<div class="req-grid">
				<label class="field">
					<span class="lbl">{L('wall_dispatch_agency')}</span>
					<HTMLSelect small fill options={agencyOptions} bind:value={agency} data-testid="dispatch-agency" />
				</label>
				<label class="field">
					<span class="lbl">{L('wall_dispatch_unit')}</span>
					<Input small fill bind:value={unitId} oninput={() => (unitTouched = true)} spellcheck="false" maxlength={64} placeholder={L('wall_dispatch_unit_ph')} data-testid="dispatch-unit" />
				</label>
				<label class="field wide">
					<span class="lbl">{L('wall_dispatch_waypoint')}</span>
					<HTMLSelect
						small
						fill
						options={waypointOptions}
						value={waypoint ? String(waypoint.junctionId) : 'none'}
						onchange={(e: Event) => (waypointChoice = (e.currentTarget as HTMLSelectElement).value)}
						data-testid="dispatch-waypoint"
					/>
				</label>
				{#if !waypoints.length}<p class="hint wide">{ops.geometryNote ?? L('wall_dispatch_no_waypoint_hint')}</p>{/if}
				<div class="field wide row">
					<Input small fill bind:value={note} maxlength={500} placeholder={L('wall_dispatch_note_ph')} aria-label={L('wall_dispatch_note')} />
					<Button
						small
						intent="primary"
						icon={kindIcon('dispatch')}
						disabled={!ops.officerOn || ops.dispatchBusy !== null}
						disabledReason={ops.officerOn ? null : L('wall_dispatch_reason')}
						loading={ops.dispatchBusy === selected.eventId}
						onclick={() => void requestUnit()}
						data-testid="dispatch-request-btn"
					>
						{L('wall_dispatch_request')}
					</Button>
				</div>
			</div>
			{#if ops.dispatchRequestNote}
				<p class="result" class:bad={!ops.dispatchRequestNote.ok} role="status">{ops.text(ops.dispatchRequestNote.text)}</p>
			{/if}
		</div>
	{/if}

	{#if shown.length}
		<table class="wdt disp">
			<colgroup><col style:width="32px" /><col /><col style:width="72px" /><col style:width="96px" /><col style:width="76px" /><col style:width="44px" /></colgroup>
			<thead>
				<tr>
					<th class="ic-col" aria-hidden="true"></th>
					<th scope="col">{L('wall_dispatch_col_unit')}</th>
					<th scope="col">{L('wall_dispatch_col_to')}</th>
					<th scope="col">{L('wall_dispatch_col_status')}</th>
					<th scope="col" class="num">{L('wall_dispatch_col_requested')}</th>
					<th aria-hidden="true"></th>
				</tr>
			</thead>
			{#each shown as d, i (d.dispatchId)}
				{@const sel = selection.current === `dispatch:${d.dispatchId}`}
				{@const closedEvent = ops.dispatchEventClosed(d) && LIVE.has(d.status)}
				<tbody
					class={['pick', sel && 'is-selected']}
					data-testid="dispatch-tile"
					data-dispatch-id={d.dispatchId}
					data-status={d.status}
					data-waypoint={d.waypointJunction ?? ''}
				>
					<tr class="main two" tabindex="0" aria-selected={sel} onclick={() => pick(d)} onkeydown={(e) => onKey(e, d)}>
						<td class="ic-col"><div class="c"><Icon name={AGENCY_ICON[d.agency] ?? kindIcon('unit')} size={16} /></div></td>
						<td>
							<div class="c l1">
								<span class="ell"><Id value={d.unitId ?? '—'} /></span>
								{#if emulatedDispatch(d)}<ProvenanceTag source="emulated" compact {lang} />{/if}
								{#if d.requestedBy === '108-driver' && d.status === 'requested'}<Tag intent="warning">{L('wall_dispatch_108')}</Tag>{/if}
							</div>
							<div class="c l2"><span class="ell muted" title={eventTitle(d.eventId) ?? undefined}>{agencyWord(d.agency, d.agencyLabel ?? AGENCIES[d.agency as AgencyCode]?.label ?? d.agency)}</span></div>
						</td>
						<td><div class="c"><span class="ell" title={ops.junctionName(d.waypointJunction) ?? undefined}>{d.waypointJunction != null ? `J${d.waypointJunction}` : '—'}</span></div></td>
						<td>
							<div class="c l1"><Tag intent={d.status === 'completed' ? 'success' : 'none'}>{statusWord(d.status)}</Tag></div>
							{#if closedEvent}
								<div class="c l2"><span data-testid="dispatch-event-closed" class="muted" title={L('wall_dispatch_event_closed_tip')}>{L('wall_dispatch_event_closed')}</span></div>
							{/if}
						</td>
						<td class="num"><div class="c"><span class="tn">{stamps[i]}</span></div></td>
						<td class="num">
							<div class="c" role="presentation" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
								<Button
									minimal
									small
									icon="history"
									class="audit-toggle"
									pressed={openAudit === d.dispatchId}
									tooltip={L('wall_dispatch_audit', d.audit.length)}
									aria-label={L('wall_dispatch_audit', d.audit.length)}
									onclick={() => (openAudit = openAudit === d.dispatchId ? null : d.dispatchId)}
								/>
							</div>
						</td>
					</tr>
					{#if openAudit === d.dispatchId}
						<tr class="detail">
							<td></td>
							<td colspan="5">
								<ul class="audit">
									{#each [...d.audit].reverse() as a, j (j)}
										<li>
											<span class="tn muted">{a.at ? fmtTime(a.at) : '—'}</span>
											<span class="who" class:system={actorKindOfName(a.actor) !== 'human'}>{displayActor(a.actor, lang)}</span>
											<span class="ell">{statusWord(a.fromStatus ?? '—')} → {statusWord(a.toStatus)}{a.note ? ` · ${ops.text(a.note)}` : ''}</span>
										</li>
									{:else}
										<li class="muted">{L('wall_dispatch_audit_none')}</li>
									{/each}
								</ul>
								{#if progressVerbs(d.status).length}
									<div class="verbs">
										{#each progressVerbs(d.status) as v (v)}
											<Button
												small
												disabled={!ops.officerOn || ops.dispatchBusy !== null}
												disabledReason={ops.officerOn ? null : L('wall_dispatch_needs_officer')}
												data-verb={v}
												onclick={() => void fire(d.dispatchId, v)}
											>
												{L(`wall_dispatch_verb_${v}`)}
											</Button>
										{/each}
									</div>
								{/if}
							</td>
						</tr>
					{/if}
				</tbody>
			{/each}
		</table>
	{:else}
		<p class="empty">{ops.dispatchesNote ?? (history.length ? L('wall_dispatch_none_live') : L('wall_dispatch_none'))}</p>
	{/if}

	{#if history.length || anyEmulated || ops.hideEmulated}
		<div class="foot">
			{#if history.length}
				<Button
					minimal
					small
					icon={historyOpen ? 'chevron-down' : 'chevron-right'}
					aria-expanded={historyOpen}
					data-testid="dispatch-history"
					data-count={history.length}
					tooltip={L('wall_dispatch_history_tip')}
					onclick={() => (historyOpen = !historyOpen)}
				>
					{L('wall_dispatch_history', history.length)}
				</Button>
			{/if}
			<span class="grow"></span>
			{#if anyEmulated || ops.hideEmulated}
				<Button minimal small pressed={ops.hideEmulated} data-testid="tiles-emulated-filter" tooltip={L('wall_dispatch_hide_emulated_tip')} onclick={() => (ops.hideEmulated = !ops.hideEmulated)}>
					{L('wall_dispatch_hide_emulated')}
				</Button>
			{/if}
		</div>
	{/if}
</Section>

<style>
	.reason {
		padding: 8px 16px 4px;
	}

	.req {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 8px 16px 12px;
		border-bottom: 1px solid var(--v-line-1);
	}

	.req-for {
		display: flex;
		align-items: baseline;
		gap: 6px;
		min-width: 0;
		font-size: var(--v-text-xs);
	}

	.req-grid {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 8px;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}

	.field.wide,
	.hint.wide {
		grid-column: 1 / -1;
	}

	.field.row {
		flex-direction: row;
		align-items: center;
	}

	.lbl {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.hint {
		margin: 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.result {
		margin: 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		overflow-wrap: anywhere;
	}

	.result.bad {
		color: var(--v-ink-1);
	}

	.ell {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.muted {
		color: var(--v-ink-2);
	}

	.tn {
		font-variant-numeric: tabular-nums;
	}

	.disp tr.two > td {
		height: 44px;
		padding-top: 4px;
		padding-bottom: 4px;
	}

	.disp tr.two .l2 {
		margin-top: 2px;
	}

	.disp tr.two .ic-col {
		vertical-align: top;
		padding-top: 7px;
	}

	.disp tbody > tr:not(:last-child) > td {
		border-bottom-color: transparent;
	}

	.audit {
		display: flex;
		flex-direction: column;
		gap: 2px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.audit li {
		display: flex;
		align-items: baseline;
		gap: 8px;
		min-width: 0;
		line-height: 18px;
	}

	.who {
		flex: 0 0 auto;
		max-width: 40%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.who.system {
		color: var(--v-ink-2);
	}

	.verbs {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-top: 8px;
	}

	.empty {
		margin: 0;
		padding: 10px 16px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.foot {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 4px 8px 6px;
	}

	.grow {
		flex: 1 1 auto;
	}
</style>
