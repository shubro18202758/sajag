<script lang="ts">
	/**
	 * DecisionQueue — the /ops Decisions column (SPEC §6.3 col 1, §5.4; review
	 * A9, B1–B3; prototype ops.js decisions()). One item per decision UNIT
	 * (decisions/units.ts): a stolen vehicle with N pending sightings is ONE
	 * item; an escort's open proposal, a 108 corridor request, a pending
	 * e-challan and a pursuit opening are one item each. Sorted by deadline,
	 * then severity.
	 *
	 *   - an optional `top` snippet (UI-S6A's ConvoyCard, wave D). While it is
	 *     supplied, escort proposals are decided there and not listed here;
	 *   - tabs Needs decision n · Approved · Rejected · Expired, and a view
	 *     options menu (hide emulated items: the hidden count is said);
	 *   - collapsed items are two-line rows; the expanded item shows the
	 *     ProposalCard INSIDE the same item, one open at a time, J/K;
	 *   - deep links #evt=, #rec=, #dsp= (and #unit=<kind>:<id>) select,
	 *     expand and flash (`.deep-link-hit`) the item, retried until the
	 *     first polls render it (20 s at most); a hostile id is ignored;
	 *   - EVERY `queue-card` element is always in the DOM with its data-*
	 *     (UNIT_KINDS dataHooks): a collapsed item keeps its card in a
	 *     `hidden` body (the rule note, the refusal, step 2 of a stolen
	 *     vehicle — `queue-card[data-kind=pursuit][data-refusal]` inside the
	 *     same item); only the footer (the officer field and the buttons)
	 *     mounts on expand. The row toggle is a `button[data-row-toggle]`
	 *     with `aria-expanded`;
	 *   - decided tabs: two-line rows with one date format per column; an
	 *     expanded row is the record. Rejected recommendations are read only
	 *     while that tab is open.
	 *
	 * Kept test ids: queue-card, decision-refusal, escort-outcome,
	 * stolen-authorised, stolen-note, stolen-warning. Import path and props
	 * are today's (no required prop), so the current /ops page and UI-S5B's
	 * rebuilt one mount it unchanged.
	 */
	import { onMount, tick, untrack, type Snippet } from 'svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { safePathId } from '$lib/ops/endpoints';
	import { workspace } from '$lib/workspace/workspace.svelte';
	import { useShellClock, shellClock } from '$lib/shell/clock.svelte';
	import { ACTION_ICON, ACTOR_ICON, PROVENANCE_ICON, kindIcon } from '$lib/design/icons';
	import { Button, Icon, Menu, NonIdealState, Note, Plate, Popover, ProvenanceTag, Tabs, Tag } from '$lib/ui';
	import { colStamp, fmtDuration, fmtStamp } from '$lib/ui/format/format';
	import { t } from '$lib/i18n/strings';
	import { tOps } from '$lib/i18n/strings.ops';
	import '$lib/i18n/packs.decisions';
	import { STOLEN_RULE, UNIT_KINDS, decisionUnits, echallanOf, escortOf, stolenOf, unitEmulated, unitTitle, type Unit } from '$lib/decisions/units';
	import { homeOf, parseUnitKey } from '$lib/decisions/homes';
	import { actorIcon, ageOf, rowMeta, unitPlate } from '$lib/decisions/cards/meta';
	import { decisionOutcomes } from '$lib/decisions/cards/outcomes.svelte';
	import ProposalCard from '$lib/decisions/ProposalCard.svelte';
	import type { EnforcementRecommendation, EscortProposalOutcome } from '$lib/ops/types';

	let { top }: { top?: Snippet } = $props();

	const lang = $derived(ops.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	$effect(() => useShellClock());
	const now = $derived(shellClock.now);

	/** A collapsed item's card ticks once a minute (its row carries the live age); open and time-boxed cards tick every second. */
	const slowNow = $derived(Math.floor(now / 60_000) * 60_000);

	type TabId = 'needs' | 'approved' | 'rejected' | 'expired';
	let tab = $state<TabId>('needs');

	// ── the units ──────────────────────────────────────────────────────────

	const keyOf = (u: Unit) => `${u.kind}:${u.id}`;
	const all = $derived(decisionUnits());
	/** With a ConvoyCard on top (UI-S6A), escort proposals are decided there: never listed twice. */
	const units = $derived(top ? all.filter((u) => u.kind !== 'escort-proposal') : all);
	const visible = $derived(units.filter((u) => !(ops.hideEmulated && unitEmulated(u))));
	const hiddenCount = $derived(units.length - visible.length);
	const anyEmulated = $derived(units.some(unitEmulated));

	let openKey = $state<string | null>(null);
	let flashKey = $state<string | null>(null);
	let flashTimer: ReturnType<typeof setTimeout> | null = null;

	function toggle(key: string) {
		openKey = openKey === key ? null : key;
	}

	/** A time-boxed proposal opens itself when it arrives and nothing else is open. */
	const seenTimeBoxed = new Set<string>();
	$effect(() => {
		for (const u of visible) {
			if (!UNIT_KINDS[u.kind]?.timeBoxed) continue;
			const k = keyOf(u);
			if (seenTimeBoxed.has(k)) continue;
			seenTimeBoxed.add(k);
			untrack(() => {
				if (!openKey) openKey = k;
			});
		}
	});

	function flash(key: string) {
		flashKey = key;
		if (flashTimer) clearTimeout(flashTimer);
		flashTimer = setTimeout(() => (flashKey = null), 3000);
	}

	async function reveal(key: string) {
		tab = 'needs';
		openKey = key;
		flash(key);
		await tick();
		const el = root?.querySelector<HTMLElement>(`[data-dq-key="${CSS.escape(key)}"]`);
		el?.scrollIntoView({ block: 'center', behavior: 'smooth' });
	}

	// ── deep links: #evt= / #rec= / #dsp= / #unit= ─────────────────────────

	let root: HTMLDivElement | undefined = $state();
	let deepTimer: ReturnType<typeof setTimeout> | null = null;
	let deepToken = 0;

	function parseDeepLink(hash: string): { kind: 'evt' | 'rec' | 'dsp' | 'unit'; id: string } | null {
		let params: URLSearchParams;
		try {
			params = new URLSearchParams(hash.replace(/^#/, ''));
		} catch {
			return null;
		}
		for (const kind of ['rec', 'dsp', 'evt'] as const) {
			const id = safePathId(params.get(kind));
			if (id) return { kind, id };
		}
		const u = parseUnitKey(params.get('unit'));
		return u ? { kind: 'unit', id: `${u.kind}:${u.id}` } : null;
	}

	function unitFor(link: { kind: string; id: string }): Unit | null {
		if (link.kind === 'unit') return units.find((u) => keyOf(u) === link.id) ?? null;
		if (link.kind === 'rec') {
			return (
				units.find((u) => u.kind === 'echallan' && u.id === link.id) ??
				units.find((u) => u.kind === 'stolen-sighting' && stolenOf(u).recs.some((r) => r.recommendationId === link.id)) ??
				null
			);
		}
		if (link.kind === 'dsp') return units.find((u) => u.kind === 'corridor-request' && u.id === link.id) ?? null;
		return units.find((u) => u.kind === 'escort-proposal' && escortOf(u).proposal.eventId === link.id) ?? null;
	}

	function followDeepLink(started = Date.now(), token = ++deepToken) {
		if (deepTimer) clearTimeout(deepTimer);
		deepTimer = null;
		if (token !== deepToken || typeof location === 'undefined') return;
		const link = parseDeepLink(location.hash);
		if (!link) return;
		const u = unitFor(link);
		if (u) {
			if (ops.hideEmulated && unitEmulated(u)) ops.hideEmulated = false;
			void reveal(keyOf(u));
			return;
		}
		// an #evt= link selects the event (the board's own deep link); nothing to expand here
		if (link.kind === 'evt' && ops.events.some((e) => e.eventId === link.id)) return;
		if (Date.now() - started < 20_000) deepTimer = setTimeout(() => followDeepLink(started, token), 500);
	}

	const onHash = () => followDeepLink();

	// a link card's click on this route (workspace.openDecisionHome) opens its item
	let seenFocus = 0;
	$effect(() => {
		const f = workspace.focusDecision;
		if (!f || f.seq === seenFocus) return;
		seenFocus = f.seq;
		untrack(() => {
			if (homeOf(f.kind, '/ops') === 'decisions') void reveal(`${f.kind}:${f.id}`);
		});
	});

	onMount(() => {
		window.addEventListener('hashchange', onHash);
		void tick().then(() => followDeepLink());
		return () => {
			window.removeEventListener('hashchange', onHash);
			if (deepTimer) clearTimeout(deepTimer);
			if (flashTimer) clearTimeout(flashTimer);
			deepToken++;
		};
	});

	// ── keys: J/K move the open item ───────────────────────────────────────

	function onKey(e: KeyboardEvent) {
		if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey || tab !== 'needs' || !visible.length) return;
		const el = e.target as HTMLElement | null;
		if (el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName))) return;
		if (workspace.omnibar.open || !root || root.offsetParent === null) return;
		// J/K act from the page body or inside this column, never while another control has focus
		if (el && el !== document.body && el !== document.documentElement && !root.contains(el)) return;
		const k = e.key.toLowerCase();
		if (k !== 'j' && k !== 'k') return;
		const i = visible.findIndex((u) => keyOf(u) === openKey);
		const next = k === 'j' ? Math.min(visible.length - 1, i + 1) : Math.max(0, i < 0 ? 0 : i - 1);
		e.preventDefault();
		void reveal(keyOf(visible[next]));
	}

	// ── outcome receipts (escort lanes; this console's decisions) ──────────

	const ESCORT_RECEIPT_MS = 90_000;
	const escortReceipts = $derived(
		ops.escorts
			.flatMap((lane) => lane.outcomes.filter((o) => o.decidedAt != null && now - o.decidedAt < ESCORT_RECEIPT_MS).map((o) => ({ o, eventId: lane.eventId })))
			.sort((a, b) => (b.o.decidedAt ?? 0) - (a.o.decidedAt ?? 0))
			.slice(0, 3),
	);
	const ownReceipts = $derived(decisionOutcomes.recent(now).filter((o) => o.kind !== 'escort-proposal' && !units.some((u) => keyOf(u) === `${o.kind}:${o.id}`)).slice(0, 3));

	function escortName(eventId: string | null, movementId: string): string {
		const ev = ops.eventById(eventId);
		const name = ev ? ops.text(ev.name) : movementId.slice(0, 8);
		const head = name.split(' · ')[0];
		return head.length > 44 ? `${head.slice(0, 43)}…` : head;
	}

	// ── decided tabs ───────────────────────────────────────────────────────

	interface Decided {
		key: string;
		icon: import('$lib/design/icons').IconName;
		title: string;
		plate: string | null;
		who: string;
		where: string | null;
		at: number | null;
		test: boolean;
		rec: EnforcementRecommendation | null;
		escort: EscortProposalOutcome | null;
		note: string | null;
	}

	const str = (v: unknown) => (typeof v === 'string' && v.trim() ? v : null);
	const toMs = (iso: string | null | undefined) => {
		const v = iso ? Date.parse(iso) : NaN;
		return Number.isFinite(v) ? v : null;
	};

	function recRow(r: EnforcementRecommendation, approved: boolean): Decided {
		const stolenRule = r.ruleId === STOLEN_RULE;
		return {
			key: `rec:${r.recommendationId}`,
			icon: kindIcon('recommendation'),
			title: L(stolenRule ? (approved ? 'dec_decided_pursuit' : 'dec_decided_sighting_dismissed') : approved ? 'dec_decided_echallan_approved' : 'dec_decided_echallan_rejected'),
			plate: r.plate,
			who: ops.text(r.decidedBy) || '—',
			where: ops.text(str(r.evidence?.road_name) ?? str(r.evidence?.camera_id) ?? '') || null,
			at: toMs(r.decidedAt),
			// only the evidence's own provenance marks a test row (never a guess from a name)
			test: str(r.evidence?.source) === 'test',
			rec: r,
			escort: null,
			note: !stolenRule && approved && ops.stolenVehicle(r.vehicleId) ? L('dec_note_since_stolen') : null,
		};
	}

	function escortRow(o: EscortProposalOutcome): Decided {
		return {
			key: `esc:${o.approvalId}:${o.status}`,
			icon: ACTOR_ICON.ai,
			title: ops.escortOutcomeText(o),
			plate: null,
			who: o.decidedBy ? ops.text(o.decidedBy) : L('dec_no_officer'),
			where: ops.text(o.summary) || null,
			at: o.decidedAt,
			test: false,
			rec: null,
			escort: o,
			note: null,
		};
	}

	const escortOutcomes = $derived(ops.escorts.flatMap((l) => l.outcomes));
	const approvedRows = $derived(
		[...ops.approvedRecommendations.map((r) => recRow(r, true)), ...escortOutcomes.filter((o) => o.status === 'approved').map(escortRow)].sort(
			(a, b) => (b.at ?? 0) - (a.at ?? 0),
		),
	);
	const rejectedRows = $derived(
		[...ops.rejectedRecommendations.map((r) => recRow(r, false)), ...escortOutcomes.filter((o) => o.status === 'rejected').map(escortRow)].sort(
			(a, b) => (b.at ?? 0) - (a.at ?? 0),
		),
	);
	const expiredRows = $derived(escortOutcomes.filter((o) => o.status === 'expired' || o.status === 'superseded').map(escortRow).sort((a, b) => (b.at ?? 0) - (a.at ?? 0)));
	const decidedRows = $derived(tab === 'approved' ? approvedRows : tab === 'rejected' ? rejectedRows : tab === 'expired' ? expiredRows : []);
	/** One date format per column (colStamp): hh:mm when every row is today (IST), else "23 Oct 23:52". */
	const decidedStamps = $derived(colStamp(decidedRows.map((r) => r.at ?? NaN), now));
	let openDecided = $state<string | null>(null);

	// rejected recommendations: one read when the column mounts (the tab's count), then
	// every 15 s only while their tab is open (no global poller)
	onMount(() => {
		if (!ops.rejectedUpdated) void ops.pollRejected();
	});
	$effect(() => {
		if (tab !== 'rejected') return;
		void ops.pollRejected();
		const id = setInterval(() => void ops.pollRejected(), 15_000);
		return () => clearInterval(id);
	});

	const tabs = $derived([
		{ id: 'needs' as const, label: L('dec_tab_needs'), count: visible.length, countIntent: visible.length ? ('warning' as const) : ('none' as const) },
		// a decided tab shows its count when it has rows (the column stays one line at 1366 px)
		{ id: 'approved' as const, label: L('dec_tab_approved'), count: approvedRows.length || null },
		// rejected recommendations are read on demand: a dash until the first read, then the count
		{ id: 'rejected' as const, label: L('dec_tab_rejected'), count: rejectedRows.length || (ops.rejectedUpdated ? null : '–') },
		{ id: 'expired' as const, label: L('dec_tab_expired'), count: expiredRows.length || null },
	]);

	/** Unit requests other than 108 corridors wait in Dispatch: an empty list says where they are. */
	const tileRequests = $derived(ops.openDispatches.filter((d) => d.status === 'requested' && d.agency !== 'ambulance').length);

	const hooksOf = (u: Unit): Record<string, string> => {
		const h = UNIT_KINDS[u.kind]?.dataHooks(u) ?? { kind: u.kind, id: u.id };
		return Object.fromEntries(Object.entries(h).map(([k, v]) => [`data-${k}`, v]));
	};
</script>

<svelte:window onkeydown={onKey} />

<div class="dq" data-testid="decision-queue" bind:this={root}>
	{#if top}<div class="top">{@render top()}</div>{/if}

	<div class="head">
		<div class="tabs-wrap"><Tabs items={tabs} bind:value={tab} label={L('dec_queue_tabs')} /></div>
		<Popover placement="bottom-end">
			<Button minimal small icon="filter-list" tooltip={L('dec_view_options')} aria-label={L('dec_view_options')} pressed={ops.hideEmulated ? true : undefined} />
			{#snippet content({ close })}
				<Menu
					label={L('dec_view_options')}
					items={[
						{ id: 'h', kind: 'header', label: L('dec_view_options') },
						{
							id: 'hide-emulated',
							label: L('dec_hide_emulated'),
							icon: PROVENANCE_ICON.emulated,
							selected: ops.hideEmulated,
							disabled: !anyEmulated && !ops.hideEmulated,
							disabledReason: L('dec_no_emulated'),
							onclick: () => (ops.hideEmulated = !ops.hideEmulated),
						},
						{ id: 'sort', label: L('dec_sorted_by_deadline'), icon: 'sort', disabled: true, disabledReason: L('dec_sort_fixed') },
					]}
					onselect={close}
				/>
			{/snippet}
		</Popover>
	</div>

	{#if hiddenCount}
		<div class="hidden-note" data-testid="queue-emulated-hidden">
			<span>{L('dec_hidden_emulated', hiddenCount)}</span>
			<Button minimal small onclick={() => (ops.hideEmulated = false)}>{L('dec_show')}</Button>
		</div>
	{/if}

	<div class="list" hidden={tab !== 'needs'} data-list="needs">
		{#each escortReceipts as { o, eventId } (`${o.approvalId}:${o.status}`)}
			{@const mine = ops.escortDecisions[o.approvalId]}
			<p
				class="receipt"
				class:ok={o.status === 'approved' && o.applied !== false}
				data-testid="escort-outcome"
				data-approval-id={o.approvalId}
				data-status={o.status}
				data-refused={mine && !mine.ok ? '1' : undefined}
				title={mine && !mine.ok ? (mine.detail ?? undefined) : (o.summary ? ops.text(o.summary) : undefined)}
			>
				<Icon name={o.status === 'approved' ? 'tick-circle' : 'time'} size={16} />
				<span class="r-what">{tOps(lang, 'escQueueEvent', escortName(eventId, o.movementId))}</span>
				<span class="r-how">{ops.escortOutcomeText(o)}</span>
			</p>
		{/each}
		{#each ownReceipts as o (`${o.kind}:${o.id}:${o.verb}`)}
			<p class="receipt ok" data-testid="decision-outcome" data-kind={o.kind} data-id={o.id}>
				<Icon name="tick-circle" size={16} />
				<span class="r-what">{o.title}</span>
				<span class="r-how">{L('dec_outcome', o.verb, o.officer, fmtStamp(o.at, now, { seconds: true }))}</span>
			</p>
		{/each}

		{#each visible as u (keyOf(u))}
			{@const key = keyOf(u)}
			{@const open = openKey === key}
			{@const age = ageOf(u, lang, now)}
			{@const title = unitTitle(u, lang)}
			{@const plate = unitPlate(u)}
			{@const shown = plate ? ops.plate(plate) : null}
			{@const at = shown ? title.indexOf(shown) : -1}
			<div
				class="item"
				class:is-open={open}
				class:deep-link-hit={flashKey === key}
				data-testid="queue-card"
				{...hooksOf(u)}
				data-open={open ? 'true' : 'false'}
				data-dq-key={key}
			>
				<div
					class="row"
					class:is-selected={open}
					role="button"
					tabindex="0"
					onclick={() => toggle(key)}
					onkeydown={(e) => {
						if (e.key === 'Enter' || e.key === ' ') {
							e.preventDefault();
							toggle(key);
						}
					}}
				>
					<span class="ic"><Icon name={kindIcon('recommendation')} size={16} /></span>
					<span class="two">
						<!-- line 1 is the title alone: the text around the mark gives way first; the mark is never cut -->
						<span class="l1">
							<span class="ell">{#if shown && at >= 0}<span class="t-pre">{title.slice(0, at)}</span><span class="t-mark"><Plate mark={shown} masked={!ops.officerOn} /></span><span class="t-post">{title.slice(at + shown.length)}</span>{:else}<span class="t-pre">{title}</span>{/if}</span>
							{#if unitEmulated(u)}<ProvenanceTag source="emulated" compact {lang} />{/if}
						</span>
						<span class="l2">{#if u.kind === 'echallan' && echallanOf(u).stolen}<Tag intent="danger" role="alert">{L('dec_tag_reported_stolen')}</Tag>{/if}<Icon name={actorIcon(u)} size={12} /><span class="ell">{rowMeta(u, lang, now)}</span></span>
					</span>
					<span class="age">
						<span class="al">{age.label}</span>
						<span class="av" class:due={age.countdown} class:urgent={age.urgent}>{age.value}</span>
					</span>
				</div>
				<button
					type="button"
					class="chev"
					data-row-toggle
					aria-expanded={open}
					aria-controls="dq-body-{u.kind}-{u.id}"
					aria-label={open ? L('dec_collapse') : L('dec_expand')}
					onclick={() => toggle(key)}
				>
					<Icon name={open ? 'chevron-up' : 'chevron-down'} size={16} />
				</button>
				<div class="body" id="dq-body-{u.kind}-{u.id}" hidden={!open}>
					<ProposalCard unit={u} {lang} item sticky footer={open} now={open || UNIT_KINDS[u.kind]?.timeBoxed ? now : slowNow} />
				</div>
			</div>
		{:else}
			<div class="empty">
				<NonIdealState
					icon={ACTION_ICON.inbox}
					iconSize={32}
					title={ops.recommendationsNote ?? L('dec_none_waiting')}
					description={tileRequests ? tOps(lang, 'queueEmptyTileRequests', tileRequests) : L('dec_none_waiting_hint')}
				/>
			</div>
		{/each}
	</div>

	{#if tab !== 'needs'}
		<div class="list" data-list={tab}>
			{#each decidedRows as r, i (r.key)}
				{@const open = openDecided === r.key}
				<div class="decided" class:is-open={open} data-testid="decided-row" data-key={r.key}>
					<div
						class="row"
						class:is-selected={open}
						role="button"
						tabindex="0"
						aria-expanded={open}
						onclick={() => (openDecided = open ? null : r.key)}
						onkeydown={(e) => {
							if (e.key === 'Enter' || e.key === ' ') {
								e.preventDefault();
								openDecided = open ? null : r.key;
							}
						}}
					>
						<span class="ic"><Icon name={r.icon} size={16} /></span>
						<span class="two">
							<span class="l1">
								<span class="ell"><span class="t-pre">{r.title}{#if r.plate}{' ·'}{/if}</span>{#if r.plate}<span class="t-mark"><Plate mark={ops.plate(r.plate)} masked={!ops.officerOn} /></span>{/if}</span>
								{#if r.test}<ProvenanceTag source="test" compact {lang} />{/if}
							</span>
							<span class="l2"><span class="ell">{[r.who, r.where].filter(Boolean).join(' · ')}</span></span>
						</span>
						<span class="age">
							<span class="al stamp">{decidedStamps[i]}</span>
							<span class="av">{r.at != null ? L('dec_ago', fmtDuration((now - r.at) / 1000, lang)) : '—'}</span>
						</span>
					</div>
					{#if open}
						<div class="record">
							{#if r.note}<Note icon={ACTION_ICON.rule_no_fine} title={L('dec_note_since_stolen_title')}>{r.note}</Note>{/if}
							<table class="props">
								<tbody>
									<tr><td class="k">{L('dec_rec_decided_by')}</td><td>{r.who}</td></tr>
									<tr><td class="k">{L('dec_rec_decided')}</td><td>{r.at != null ? `${fmtStamp(r.at, now, { seconds: true })} IST` : '—'}</td></tr>
									{#if r.where}<tr><td class="k">{r.escort ? L('dec_rec_proposal') : L('dec_rec_road')}</td><td>{r.where}</td></tr>{/if}
									{#if r.rec}
										<tr>
											<td class="k">{L('dec_rec_pursuit')}</td>
											<td>{r.rec.pursuit ? L('dec_rec_pursuit_state', r.rec.pursuit.status ?? '—') : L('dec_rec_not_opened')}</td>
										</tr>
										<tr><td class="k">{L('dec_rec_audit')}</td><td>{L('dec_rec_entries', r.rec.auditTail.length)}</td></tr>
									{/if}
								</tbody>
							</table>
						</div>
					{/if}
				</div>
			{:else}
				<div class="empty">
					<NonIdealState icon={ACTION_ICON.inbox} iconSize={32} title={L(`dec_empty_${tab}`)} />
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.dq {
		display: flex;
		flex-direction: column;
		min-height: 0;
		min-width: 0;
		color: var(--v-ink-1);
		font-family: var(--v-font-ui);
		container-type: inline-size;
	}

	.top {
		border-bottom: 1px solid var(--v-line-2);
	}

	.head {
		display: flex;
		align-items: center;
		gap: 4px;
		padding: 0 4px 0 12px;
		border-bottom: 1px solid var(--v-line-1);
		flex: 0 0 auto;
	}

	/* the tabs take the room there is; the view-options button never shrinks. In a narrow
	   column the tabs sit closer and scroll sideways, so the last tab is never cut under the button. */
	.tabs-wrap {
		flex: 1 1 auto;
		min-width: 0;
		overflow-x: auto;
		overflow-y: hidden;
		scrollbar-width: none;
	}

	.tabs-wrap::-webkit-scrollbar {
		display: none;
	}

	@container (max-width: 479px) {
		.tabs-wrap :global([data-ui='tabs']) {
			gap: 10px;
		}
	}

	@container (max-width: 409px) {
		.head {
			padding-left: 8px;
		}

		.tabs-wrap :global([data-ui='tabs']) {
			gap: 8px;
		}
	}

	.head > :global(:not(.tabs-wrap)) {
		flex: 0 0 auto;
	}

	.grow {
		flex: 1 1 auto;
	}

	.hidden-note {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 4px 8px 4px 12px;
		font-size: var(--v-text-xs);
		color: var(--v-ink-2);
		border-bottom: 1px solid var(--v-line-1);
	}

	.list {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.receipt {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0;
		padding: 6px 12px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
		border-bottom: 1px solid var(--v-line-1);
		background: var(--v-neutral-veil);
	}

	.receipt.ok {
		color: var(--v-ink-1);
		background: var(--v-success-veil);
	}

	.receipt :global(svg) {
		flex: 0 0 auto;
	}

	.receipt.ok :global(svg) {
		color: var(--v-success-text);
	}

	.r-what {
		color: var(--v-ink-2);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 45%;
	}

	.r-how {
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.item,
	.decided {
		position: relative;
		border-bottom: 1px solid var(--v-line-1);
	}

	.item.is-open {
		border-bottom: 1px solid var(--v-line-2);
	}

	.row {
		display: grid;
		grid-template-columns: var(--v-ws-icon-col) minmax(0, 1fr) auto 28px;
		align-items: center;
		min-height: var(--v-ws-row-2);
		padding: 0 0 0 0;
		cursor: pointer;
		outline: none;
	}

	.decided .row {
		grid-template-columns: var(--v-ws-icon-col) minmax(0, 1fr) auto;
		padding-right: 8px;
	}

	.row:hover {
		background: var(--v-row-hover);
	}

	.row:focus-visible {
		box-shadow: inset 0 0 0 2px var(--v-focus);
	}

	.row.is-selected {
		background: var(--v-primary-veil);
		box-shadow: inset 2px 0 0 var(--v-primary-text);
	}

	.ic {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		color: var(--v-ink-2);
		padding-left: 4px;
	}

	.item .ic {
		color: var(--v-warning-text);
	}

	.two {
		display: flex;
		flex-direction: column;
		justify-content: center;
		min-width: 0;
		padding: 5px 0;
	}

	.l1,
	.l2 {
		display: flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
		white-space: nowrap;
		overflow: hidden;
	}

	.l1 {
		font-size: var(--v-text-base);
		line-height: 18px;
	}

	.l2 {
		margin-top: 2px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
	}

	.l2 :global(svg) {
		flex: 0 0 auto;
	}

	.ell {
		display: inline-flex;
		align-items: center;
		gap: 0 4px;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* a title with a mark: the text after it gives way first, then the text before it; the mark never shrinks */
	.t-pre,
	.t-post {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.t-pre {
		flex: 0 1 auto;
	}

	.t-post {
		flex: 0 100 auto;
	}

	.t-mark {
		display: inline-flex;
		flex: 0 0 auto;
	}

	.l2 > :global([data-ui='tag']) {
		flex: 0 0 auto;
	}

	.age {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		padding: 0 4px 0 8px;
		font-size: var(--v-text-xs);
		line-height: 16px;
		color: var(--v-ink-2);
		white-space: nowrap;
	}

	.av {
		color: var(--v-ink-1);
		font-variant-numeric: tabular-nums;
	}

	.av.due {
		color: var(--v-warning-text);
		font-weight: 600;
	}

	.av.urgent {
		color: var(--v-danger-text);
	}

	.stamp {
		font-variant-numeric: tabular-nums;
	}

	.chev {
		position: absolute;
		top: 8px;
		right: 2px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 24px;
		height: 28px;
		padding: 0;
		border: 0;
		border-radius: var(--v-radius-btn);
		background: transparent;
		color: var(--v-ink-2);
		cursor: pointer;
	}

	.chev:hover {
		background: var(--v-minimal-hover);
		color: var(--v-ink-1);
	}

	.chev:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: -2px;
	}

	.body {
		border-top: 1px solid var(--v-line-1);
	}

	.body[hidden] {
		display: none;
	}

	/* a deep link (#rec= #dsp= #evt= #unit=) flashes its item for 3 s */
	.item.deep-link-hit {
		box-shadow: inset 0 0 0 2px var(--v-primary-text);
		transition: box-shadow var(--v-dur-out) var(--v-ease);
	}

	.empty {
		padding: 24px 16px;
	}

	.record {
		padding: 8px 16px 12px 40px;
		display: flex;
		flex-direction: column;
		gap: 8px;
		background: var(--v-surface-1);
	}

	.props {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	.props td {
		padding: 6px 8px 6px 0;
		border-bottom: 1px solid var(--v-line-1);
		vertical-align: top;
	}

	.props td.k {
		width: 34%;
		color: var(--v-ink-2);
	}
</style>
