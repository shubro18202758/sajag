<script lang="ts">
	/**
	 * ObjectInspector (SPEC §5.3, §8.2) — ONE inspector for every kind: the
	 * eleven city kinds, OSINT reports and places (through the generic
	 * adapter), and events, recommendations and dispatches known only from
	 * history. Root `entity-dossier` with `data-urn` and `data-state`.
	 *
	 *   breadcrumbs (Alt+← / Alt+→), pins as tabs (≤ 6), "+n selected"
	 *   EntityTitle: the kind glyph (ringed red for a watchlisted vehicle), the
	 *     title (a vehicle's masked mark: `dossier-plate` holding `.plate`),
	 *     state, alert, provenance and Test tags
	 *   the actions row (never overflows; `dossier-explain-btn` always shown,
	 *     the streamed answer in `dossier-explain-answer`)
	 *   2–4 key figures, at most one rule Note, the line picked on the map
	 *   the sections providers register for this kind (registerInspectorSection)
	 *   tabs: Properties (grouped; "Show system fields"), Links n, Activity n,
	 *     Actions (non-decision actions; a link card to each decision's home)
	 *   the legacy `dossier-officer` prompt, only while the page has no navbar
	 *     officer (plan R10/X12)
	 *
	 * Masking (C6): every mark is masked unless a duty officer is named
	 * (ops.officerOn), and then only through ops.plate; free text (an
	 * activity row, the explain answer) through the workspace mask, which
	 * also catches a mark typed in lower case or with dots (mask.ts). A
	 * sighting the oracle may not show (its dossier answers 404) reads
	 * "Withheld: no lawful basis to show individual reads" (SPEC §16.6).
	 */
	import { onDestroy, untrack } from 'svelte';
	import { page } from '$app/stores';
	import { ACTION_ICON, ACTOR_ICON, eventKindIcon, kindIcon } from '$lib/design/icons';
	import {
		Breadcrumbs,
		Button,
		EntityTitle,
		Icon,
		Menu,
		MetricCard,
		NonIdealState,
		Note,
		Popover,
		ProvenanceTag,
		Spinner,
		Tabs,
		Tag,
		Time,
		provideUiLang,
	} from '$lib/ui';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.workspace';
	import { commandBar } from '$lib/shell/command-bar.svelte';
	import { ops } from '$lib/ops/store.svelte';
	import { streamChat } from '$lib/api/client';
	import { fmtWindowIst } from '$lib/ops/format';
	import { isPublicKind } from '$lib/citizen/holds';
	import { canvasBus } from '$lib/gods-eye/canvas-bus.svelte';
	import { selection } from '$lib/gods-eye/entities/selection.svelte';
	import { dossier } from '$lib/gods-eye/entities/dossier.svelte';
	import { cityRegistry } from '$lib/gods-eye/entities/registry.svelte';
	import { parseUrn } from '$lib/gods-eye/city-api';
	import { workspaceActions } from '../../actions';
	import { maskMarks } from '../../mask';
	import { adapterFor, rowOf } from '../../kinds';
	import { kindMany } from '../../kinds/generic';
	import { localTitle } from '../../display';
	import { actionsFor, inspectorSectionsFor, ownedUnitKinds } from '../../registry';
	import { liveWorld, selectors } from '../../world.svelte';
	import { workspace } from '../../workspace.svelte';
	import type { DecisionUnitSummary, ObjectAction, ObjectRow, TabRoute } from '../../types';
	import { frameContext } from '../frame/context';
	import ActionsTab from './ActionsTab.svelte';
	import ActivityTab from './ActivityTab.svelte';
	import LinksTab from './LinksTab.svelte';
	import PropertyGroups from './PropertyGroups.svelte';
	import RunsText from './RunsText.svelte';
	import { inspectorHistory } from './history.svelte';
	import { figureDay, linkCards } from './model';
	import { showLegacyOfficer } from './officer';

	let { urn: urnProp = undefined, ...rest }: { urn?: string | null; [k: string]: unknown } = $props();

	provideUiLang(() => commandBar.lang);
	const lang = $derived(commandBar.lang);
	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const frame = frameContext();

	const urn = $derived(urnProp === undefined ? selection.current : urnProp);

	/** The route, for decision homes (the frame says; else the URL). */
	const route = $derived.by((): TabRoute => {
		if (frame) return frame.route();
		const p = $page.url.pathname;
		return p.startsWith('/gods-eye') ? '/gods-eye' : p.startsWith('/ops') ? '/ops' : p.startsWith('/chat') ? '/chat' : '/';
	});
	const views = $derived(frame ? frame.views() : []);

	// the dossier follows the inspected object; the history records it
	$effect(() => {
		const u = urn;
		untrack(() => {
			dossier.open(u ?? null);
			inspectorHistory.visit(u ?? null);
		});
	});
	onDestroy(() => {
		if (dossier.urn === untrack(() => urn)) dossier.close();
		explainCtrl?.abort();
	});

	const now = $derived.by(() => {
		void liveWorld.tick;
		void cityRegistry.version;
		return Date.now();
	});
	const officer = $derived(ops.officerOn);
	const graph = $derived(liveWorld.graph());
	const current = $derived(!!urn && dossier.urn === urn);
	const data = $derived(current ? dossier.data : null);
	const dState = $derived(!urn ? 'idle' : current ? dossier.state : 'loading');
	const row = $derived.by((): ObjectRow | null => {
		if (!urn) return null;
		const g = graph.get(urn);
		if (g) return g;
		// the dossier's own entity, before the model has merged it
		return data?.entity && data.entity.urn === urn ? rowOf(data.entity) : null;
	});
	const parsed = $derived(parseUrn(urn));
	const links = $derived(row ? graph.links(row.urn) : []);
	const view = $derived.by(() => {
		if (!row) return null;
		return adapterFor(row.kind).view(row, {
			lang,
			now,
			officer,
			plate: (raw) => ops.plate(raw),
			graph,
			links,
			dossier: data,
			phases: (id) => {
				const ev = ops.events.find((e) => e.eventId === id);
				return ev ? ev.phases.map((ph) => ({ label: ph.label, window: fmtWindowIst(ph.startTime, ph.endTime, now) })) : null;
			},
			publicKind: (k) => isPublicKind(k),
		});
	});
	const sections = $derived(row ? inspectorSectionsFor(row.kind) : []);
	const units = $derived(row ? linkCards(row.urn, selectors.decisionUnits(), ownedUnitKinds(row.kind)) : []);
	const activity = $derived(data?.audit ?? []);
	const pick = $derived(selection.pick && selection.current === urn ? selection.pick : null);

	// ── tabs ───────────────────────────────────────────────────────────────

	type TabId = 'properties' | 'links' | 'activity' | 'actions';
	let tab = $state<TabId>('properties');
	let system = $state(false);
	const tabs = $derived([
		{ id: 'properties' as const, label: L('ws_tab_properties') },
		{ id: 'links' as const, label: L('ws_tab_links'), count: links.length, attrs: { 'data-tab': 'links' } },
		{ id: 'activity' as const, label: L('ws_tab_activity'), count: activity.length, attrs: { 'data-tab': 'activity' } },
		{ id: 'actions' as const, label: L('ws_tab_actions'), count: units.length || null, countIntent: units.length ? ('warning' as const) : ('none' as const) },
	]);

	// ── actions ────────────────────────────────────────────────────────────

	const allActions = $derived.by((): ObjectAction[] => {
		if (!row) return [];
		const own = workspaceActions(row, { lang, views, explain: explainThis });
		const seen = new Set(own.map((a) => a.id));
		return [...own, ...actionsFor(row).filter((a) => !seen.has(a.id))];
	});
	const act = (id: string) => allActions.find((a) => a.id === id);

	function select(u: string, add = false) {
		selection.select(u, { source: 'dossier', mode: add ? 'add' : 'replace' });
	}

	function openHome(u: DecisionUnitSummary) {
		workspace.openDecisionHome(u, route === '/chat' ? '/' : route);
	}

	/**
	 * Open `urns` in the table under a filter that says what they are ("Vehicles",
	 * "Lawful reads · MH47EM•••1"). A filter label reaches share links: the store
	 * masks it, and it is kept within a label's 80 characters (never the bare field).
	 */
	function toTable(urns: string[], label: string) {
		const text = label.length > 80 ? `${label.slice(0, 79).trimEnd()}…` : label;
		workspace.addFilter({ field: 'urns', values: urns, label: text });
		if (views.includes('table')) workspace.view = 'table';
	}

	function toGraph(urns: string[]) {
		selection.selectMany([...(row ? [row.urn] : []), ...urns], { source: 'graph', primary: row?.urn ?? null });
		workspace.view = views.includes('split') ? 'split' : 'graph';
	}

	// ── keyboard: Alt+← back, Alt+→ forward ────────────────────────────────

	function onKey(e: KeyboardEvent) {
		if (!e.altKey || e.defaultPrevented) return;
		const tgt = e.target as HTMLElement | null;
		if (tgt && (tgt.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(tgt.tagName))) return;
		const to = e.key === 'ArrowLeft' ? inspectorHistory.back() : e.key === 'ArrowRight' ? inspectorHistory.forward() : null;
		if (!to) return;
		e.preventDefault();
		selection.select(to, { source: 'dossier' });
	}

	function go(dir: 'back' | 'forward') {
		const to = dir === 'back' ? inspectorHistory.back() : inspectorHistory.forward();
		if (to) selection.select(to, { source: 'dossier' });
	}

	// ── explain (the agent, grounded in this object: C-D2) ─────────────────

	type Explain = { urn: string; text: string; status: 'streaming' | 'done' | 'error'; note: string | null };
	let explain = $state<Explain | null>(null);
	let explainCtrl: AbortController | null = null;
	let explainSession: string | null = null;

	$effect(() => {
		const u = urn;
		untrack(() => {
			if (explain && explain.urn !== u) {
				explainCtrl?.abort();
				explainCtrl = null;
				explain = null;
			}
		});
	});

	function explainThis() {
		const u = urn;
		if (!u) return;
		explainCtrl?.abort();
		const ctrl = new AbortController();
		explainCtrl = ctrl;
		explain = { urn: u, text: '', status: 'streaming', note: null };
		const ev = parseUrn(u)?.kind === 'event' ? (parseUrn(u)?.id ?? null) : null;
		void streamChat(
			'Explain this entity for the duty officer: what it is, its current state and source, ' +
				'what the city picture links it to, and what (if anything) waits on a named officer. ' +
				'Use names and labels, never ids.',
			null,
			null,
			{
				onToken: (tok) => {
					if (explain && explain.urn === u) explain.text += tok;
				},
				onThought: () => {},
				onToolCall: () => {},
				onToolResult: () => {},
				// a proposal queues on the map as "AI suggests"; a human applies it
				onDirective: (d) => canvasBus.offer(d, null),
				onDone: (d) => {
					if (d.sessionId) explainSession = d.sessionId;
					if (explain && explain.urn === u) explain.status = 'done';
				},
				onError: (e) => {
					if (ctrl.signal.aborted || !explain || explain.urn !== u) return;
					explain.status = 'error';
					explain.note = e.message;
				},
			},
			{ sessionId: explainSession, signal: ctrl.signal, contextUrn: u, eventId: ev },
		).catch((e) => {
			if (ctrl.signal.aborted || !explain || explain.urn !== u) return;
			explain.status = 'error';
			explain.note = e instanceof Error ? e.message : String(e);
		});
	}

	function stopExplain() {
		explainCtrl?.abort();
		explainCtrl = null;
		if (explain) {
			explain.status = 'done';
			if (!explain.text) explain = null;
		}
	}

	// ── the legacy officer prompt (plan R10/X12) ────────────────────────────

	const legacyOfficer = $derived(showLegacyOfficer());
	let officerDraft = $state('');
	function nameOfficer() {
		const name = officerDraft.trim();
		if (name.length >= 2) ops.setDutyOfficer(name);
	}

	// ── header bits ────────────────────────────────────────────────────────

	const icon = $derived(row ? (row.kind === 'event' ? eventKindIcon(typeof row.props.event_kind === 'string' ? row.props.event_kind : null) : kindIcon(row.kind)) : kindIcon(parsed?.kind));
	const prov = $derived(row && (row.source === 'emulated' || row.source === 'simulated' || row.source === 'osint') ? row.source : null);
	const verif = $derived(
		row && (row.verification === 'UNVERIFIED-OSINT' || row.verification === 'NEWS-REPORTED' || row.verification === 'OFFICIAL-VERIFIED' || row.verification === 'CONFIRMED')
			? row.verification
			: null,
	);
	const crumbs = $derived([
		{ label: L('ws_insp_context') },
		{ label: row ? kindMany(row.kind, lang) : parsed ? kindMany(parsed.kind, lang) : '—', onclick: row ? () => toTable(graph.byKind(row.kind).map((r) => r.urn), kindMany(row.kind, lang)) : undefined },
		{ label: row ? localTitle(row.label, lang) : (urn ?? ''), current: true },
	]);
	const pins = $derived(workspace.pinned.map((u) => graph.get(u) ?? null).filter((r): r is ObjectRow => !!r));
	const more = $derived(Math.max(0, selection.items.length - 1));
	const moreItems = $derived(
		['ws.copy-link', 'ws.copy-urn', 'ws.open-in-table']
			.map((id) => act(id))
			.filter((a): a is ObjectAction => !!a)
			.map((a) => ({ id: a.id, label: a.label, icon: a.icon, disabled: a.disabled, disabledReason: a.disabledReason ?? null, onclick: () => void a.run() })),
	);
	/**
	 * Free text as this console may show it: raw only for a named duty officer, else every registration
	 * mark masked in any case or spelling (SPEC §9.3). The mask changes nothing but a real mark (mask.ts:
	 * a date or a time is never one), so an officer's note or the Explain answer is otherwise shown
	 * exactly as received (SPEC §3.4).
	 */
	const mask = (s: string) => (officer ? s : maskMarks(s));
</script>

<svelte:window onkeydown={onKey} />

{#if urn}
	<div class="insp" data-testid="entity-dossier" data-urn={urn} data-state={dState} data-kind={row?.kind ?? parsed?.kind ?? ''} {...rest}>
		<header class="head">
			{#if pins.length}
				<div class="pins" role="tablist" aria-label={L('ws_insp_pin')}>
					{#each pins as p (p.urn)}
						<span class="pin" class:is-selected={p.urn === urn}>
							<button type="button" role="tab" aria-selected={p.urn === urn} class="pin-go" onclick={() => select(p.urn)}>
								<Icon name={kindIcon(p.kind)} size={12} /><span class="pin-lbl">{localTitle(p.label, lang)}</span>
							</button>
							<button type="button" class="pin-x" aria-label={L('ws_insp_unpin')} onclick={() => workspace.unpin(p.urn)}><Icon name="small-cross" size={12} /></button>
						</span>
					{/each}
				</div>
			{/if}
			<div class="crumbs">
				{#snippet crumbNow()}<span class="crumb-now" title={row ? localTitle(row.label, lang) : (urn ?? '')}>{row ? localTitle(row.label, lang) : (urn ?? '')}</span>{/snippet}
				<Breadcrumbs items={crumbs} current={crumbNow} class="bc" />
				{#if more}<Tag round>{L('ws_insp_more_selected', more)}</Tag>{/if}
				<span class="nav">
					<Button minimal small icon="arrow-left" tooltip={L('ws_insp_back')} aria-label={L('ws_insp_back')} disabled={!inspectorHistory.canBack} onclick={() => go('back')} />
					<Button
						minimal
						small
						icon={workspace.pinned.includes(urn) ? 'unpin' : 'pin'}
						tooltip={workspace.pinned.includes(urn) ? L('ws_insp_unpin') : L('ws_insp_pin')}
						aria-label={workspace.pinned.includes(urn) ? L('ws_insp_unpin') : L('ws_insp_pin')}
						pressed={workspace.pinned.includes(urn)}
						onclick={() => workspace.togglePin(urn)}
					/>
					<Button minimal small icon="cross" tooltip={L('ws_insp_close')} aria-label={L('ws_insp_close')} onclick={() => selection.clear()} />
				</span>
			</div>

			{#if view && row}
				<EntityTitle icon={icon} alert={view.alert} class="et">
					{#snippet title()}<RunsText runs={view.title} plateHook={view.plateTitle} anchor={now} />{/snippet}
					{#snippet subtitle()}
						{#each view.subtitle as seg, i (i)}{#if i > 0}<span class="dot">{' · '}</span>{/if}<RunsText runs={seg} plateHook={!view.plateTitle && i === view.subtitle.findIndex((s) => s.some((r) => 'plate' in r))} anchor={now} />{/each}
					{/snippet}
					{#snippet tags()}
						{#each view.tags as tg, i (i)}<Tag intent={tg.intent} icon={tg.icon} tooltip={tg.tooltip ?? null}>{tg.text}</Tag>{/each}
						{#if prov}<ProvenanceTag source={prov} verification={verif} data-testid="dossier-source" />{/if}
						{#if row.test}<ProvenanceTag source="test" data-testid="dossier-test" />{/if}
					{/snippet}
				</EntityTitle>
			{:else}
				<EntityTitle icon={icon} class="et">
					{#snippet title()}<span class="urn">{urn}</span>{/snippet}
					{#snippet subtitle()}{#if dState === 'loading'}<span class="loading"><Spinner size={16} />{L('ws_insp_loading')}</span>{/if}{/snippet}
				</EntityTitle>
			{/if}

			<div class="actions">
				{#if act('ws.show-on-map')}
					{@const a = act('ws.show-on-map')!}
					<Button small icon={a.icon} tooltip={a.label} aria-label={a.label} class="opt-lbl" onclick={() => void a.run()}><span class="lbl-opt">{a.label}</span></Button>
				{/if}
				{#if act('ws.search-around')}
					{@const a = act('ws.search-around')!}
					<Button small icon={a.icon} disabled={a.disabled} disabledReason={a.disabledReason ?? null} onclick={() => void a.run()}>{a.label}</Button>
				{/if}
				{#if act('ws.add-to-graph')}
					{@const a = act('ws.add-to-graph')!}
					<Button small icon={a.icon} tooltip={a.disabled ? null : a.label} aria-label={a.label} disabled={a.disabled} disabledReason={a.disabledReason ?? null} onclick={() => void a.run()} />
				{/if}
				<Button
					small
					icon={ACTION_ICON.explain}
					tooltip={L('ws_insp_explain_tip')}
					aria-label={L('ws_insp_explain')}
					loading={explain?.status === 'streaming'}
					data-testid="dossier-explain-btn"
					onclick={explainThis}
				/>
				<Popover placement="bottom-end">
					<Button small icon="more" tooltip={L('ws_insp_more')} aria-label={L('ws_insp_more')} />
					{#snippet content({ close })}<Menu items={moreItems} onselect={close} />{/snippet}
				</Popover>
			</div>

			{#if explain && (explain.text || explain.status !== 'streaming')}
				<div class="explain" data-testid="dossier-explain">
					<div class="ex-head">
						<Icon name={ACTOR_ICON.ai} size={16} class="ai" /><span class="ex-by">{L('ws_insp_explain_by')}</span>
						{#if explain.status === 'streaming'}<Button minimal small onclick={stopExplain}>{L('ws_insp_explain_stop')}</Button>{/if}
					</div>
					<p class="ex-text" data-testid="dossier-explain-answer" data-status={explain.status}>
						{explain.text ? mask(explain.text) : explain.status === 'error' ? L('ws_insp_explain_failed') : '…'}
					</p>
					{#if !officer}<p class="ex-note">{L('ws_insp_explain_masked')}</p>{/if}
				</div>
			{:else if explain}
				<div class="explain" data-testid="dossier-explain">
					<p class="ex-text" data-testid="dossier-explain-answer" data-status="streaming">{L('ws_insp_explaining')}</p>
				</div>
			{/if}
		</header>

		{#if dState === 'withheld'}
			<div class="state"><NonIdealState icon={ACTION_ICON.masked} iconSize={32} title={L('ws_insp_withheld')} /></div>
		{:else if dState === 'not-found' && !row}
			<div class="state"><NonIdealState icon="search" iconSize={32} title={L('ws_insp_not_found')} description={L('ws_insp_not_found_hint')} /></div>
		{:else if view && row}
			{#if view.figures.length}
				<div class="metrics" style:--n={view.figures.length}>
					{#each view.figures as f, i (i)}
						{@const day = f.time != null ? figureDay(f.time, now) : null}
						<div class="metric" title={f.hint ?? (typeof f.value === 'string' && f.value !== '—' ? f.value : undefined)}>
							<div class="cap">{f.caption}</div>
							<div class="val" class:word={f.time == null && typeof f.value === 'string' && /\p{L}/u.test(f.value)} class:zero={f.time == null && f.value === 0}>
								{#if f.time != null}<Time value={f.time} />{:else}{f.value ?? '—'}{/if}{#if f.unit}<span class="u">{f.unit}</span>{/if}
							</div>
							{#if day}<div class="day" data-figure-day>{day}</div>{/if}
							<!-- a figure's `sub` reads as a visible second line (the way the day reads): the OSINT
							     context note. `hint` stays the cell's tooltip — vehicle/camera prose is long -->
							{#if f.sub}<div class="day" data-figure-sub>{f.sub}</div>{/if}
						</div>
					{/each}
				</div>
			{/if}
			{#if view.note}
				<div class="rule"><Note icon={view.note.icon} title={view.note.title}>{view.note.text}</Note></div>
			{/if}
			{#if pick}
				<details class="map-pick" data-pick-layer={pick.layer}>
					<summary><Icon name={ACTION_ICON.show_on_map} size={12} />{L('ws_insp_from_map')}</summary>
					<p class="pick-text">{mask(pick.text)}</p>
				</details>
			{/if}
			{#if dState === 'down' && dossier.note}<p class="down">{L('ws_insp_down')}</p>{/if}

			<div class="tabs"><Tabs items={tabs} bind:value={tab} height={39} label={L('ws_insp_label')} /></div>
			<div class="body">
				{#if tab === 'properties'}
					<!-- the providers' sections read FIRST in the Properties tab, under the tabs (the
					     prototype's shape: tabs sit right after the header, figures and note, so they
					     are above the fold at every console size — fix round 2, item 7) -->
					{#each sections as s (s.id)}
						<div class="section" data-section={s.id}><s.component {row} dossier={data} /></div>
					{/each}
					<PropertyGroups groups={view.groups} {now} onselect={(u) => select(u)} />
					{#if system}
						<PropertyGroups groups={[{ title: L('ws_grp_system'), rows: view.system }]} {now} onselect={(u) => select(u)} />
					{/if}
					<div class="sys"><Button minimal small icon="code" onclick={() => (system = !system)}>{system ? L('ws_hide_system') : L('ws_show_system')}</Button></div>
				{:else if tab === 'links'}
					<LinksTab {links} {lang} {now} onselect={(u, add) => select(u, add)} ongraph={toGraph} ontable={(urns, group) => toTable(urns, `${group} · ${localTitle(row.label, lang)}`)} />
				{:else if tab === 'activity'}
					<ActivityTab rows={activity} {row} dossier={data} {lang} {now} {mask} />
				{:else}
					<ActionsTab actions={allActions} {units} {route} {lang} {now} onhome={openHome} {mask} />
				{/if}
			</div>
		{:else if dState === 'down'}
			<div class="state"><NonIdealState icon="offline" iconSize={32} title={L('ws_insp_down')} /></div>
		{/if}

		{#if legacyOfficer}
			<footer class="officer">
				{#if ops.dutyOfficerFromSession}
					<span class="who"><Icon name={ACTOR_ICON.officer} size={16} />{L('ws_officer_session', ops.dutyOfficer.trim())}</span>
				{:else}
					<form
						onsubmit={(e) => {
							e.preventDefault();
							nameOfficer();
						}}
					>
						<label class="who" for="ws-officer-{urn}"><Icon name={ACTOR_ICON.officer} size={16} />{L('ws_officer_label')}</label>
						<input
							id="ws-officer-{urn}"
							type="text"
							bind:value={officerDraft}
							placeholder={ops.officerOn ? ops.dutyOfficer.trim() : L('ws_officer_placeholder')}
							title={L('ws_officer_helper')}
							aria-label={L('ws_officer_label')}
							data-testid="dossier-officer"
							maxlength="64"
						/>
						<Button small type="submit" disabled={officerDraft.trim().length < 2}>{L('ws_officer_set')}</Button>
					</form>
				{/if}
			</footer>
		{/if}
	</div>
{/if}

<style>
	.insp {
		display: flex;
		flex-direction: column;
		min-height: 0;
		color: var(--v-ink-1);
		font-size: 14px;
		line-height: 18px;
	}

	.head {
		padding: 12px 16px;
		border-bottom: 1px solid var(--v-line-2);
	}

	.pins {
		display: flex;
		gap: 4px;
		margin-bottom: 8px;
		overflow-x: auto;
	}

	.pin {
		display: inline-flex;
		align-items: center;
		height: 24px;
		border-radius: var(--v-radius-chip);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
		font-size: 12px;
	}

	.pin.is-selected {
		background: var(--v-primary-veil);
		box-shadow: inset 2px 0 0 var(--v-primary-text);
	}

	.pin-go,
	.pin-x {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		height: 24px;
		padding: 0 4px 0 8px;
		border: 0;
		background: transparent;
		color: inherit;
		font: inherit;
		cursor: pointer;
	}

	.pin-x {
		padding: 0 4px;
		color: var(--v-ink-2);
	}

	.pin-lbl {
		max-width: 120px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.crumbs {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		margin-bottom: 8px;
	}

	/* the current crumb ends in an ellipsis ("Pursuit of MH47EM•…"), never a hard clip: a block box
	   inside the crumb's flex row, so text-overflow applies (its title says it whole) */
	.crumb-now {
		display: block;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.crumbs :global(.bc) {
		flex: 1 1 auto;
		min-width: 0;
	}

	.nav {
		display: inline-flex;
		gap: 4px;
		margin-left: auto;
		flex: 0 0 auto;
	}

	.dot {
		color: var(--v-ink-2);
	}

	.urn,
	.loading {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		overflow-wrap: anywhere;
	}

	.actions {
		display: flex;
		flex-wrap: nowrap;
		gap: 4px;
		margin-top: 12px;
		min-width: 0;
	}

	/* below 1680 px "Show on map" is icon-only, so the row never overflows (SPEC §3.7) */
	@media (max-width: 1679px) {
		.lbl-opt {
			display: none;
		}
	}

	.explain {
		margin-top: 12px;
		padding: 8px 12px;
		border-radius: var(--v-radius-chip);
		background: var(--v-ai-veil);
	}

	.ex-head {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 12px;
		color: var(--v-ai-text);
	}

	.ex-head :global(.ai) {
		color: var(--v-ai-text);
	}

	.ex-by {
		flex: 1 1 auto;
		font-weight: 600;
	}

	.ex-text {
		margin: 4px 0 0;
		font-size: 14px;
		line-height: 21px;
		white-space: pre-wrap;
		max-height: 12rem;
		overflow-y: auto;
	}

	.ex-note {
		margin: 4px 0 0;
		font-size: 12px;
		color: var(--v-ink-2);
	}

	.state {
		padding: 24px 16px;
	}

	/* equal columns while every figure fits; a number or a time never clips (it widens its column, the others give way) */
	.metrics {
		display: grid;
		grid-template-columns: repeat(var(--n, 4), minmax(min-content, 1fr));
		border-bottom: 1px solid var(--v-line-2);
	}

	.metric {
		min-width: 0;
		padding: 8px 4px 8px 16px;
	}

	.metric + .metric {
		padding-left: 12px;
		border-left: 1px solid var(--v-line-1);
	}

	.cap {
		overflow: hidden;
		font-size: 12px;
		line-height: 16px;
		color: var(--v-ink-2);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.val {
		font-size: 18px;
		font-weight: 600;
		line-height: 24px;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	/* a word figure never paints into its neighbour: one that does not fit ends in an ellipsis (its title says it whole) */
	.val.word {
		overflow: hidden;
		text-overflow: ellipsis;
	}

	/* a caption and a word figure fill their cell but never widen it: only numbers and times size a column */
	.cap,
	.val.word {
		width: 0;
		min-width: 100%;
	}

	/* a zero recedes (SPEC §3.2 metric type) */
	.val.zero {
		color: var(--v-ink-2);
		font-weight: 400;
	}

	.u {
		margin-left: 4px;
		font-size: 12px;
		font-weight: 400;
		color: var(--v-ink-2);
	}

	/* the day of a time figure off the anchor's IST day, under its clock */
	.day {
		overflow: hidden;
		font-size: 12px;
		line-height: 16px;
		color: var(--v-ink-2);
		text-overflow: ellipsis;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}

	.rule {
		padding: 8px 16px;
		border-bottom: 1px solid var(--v-line-2);
	}

	.map-pick {
		padding: 8px 16px;
		border-bottom: 1px solid var(--v-line-1);
		font-size: 12px;
		color: var(--v-ink-2);
	}

	.map-pick summary {
		display: flex;
		align-items: center;
		gap: 8px;
		cursor: pointer;
		list-style: none;
	}

	.map-pick summary::-webkit-details-marker {
		display: none;
	}

	.pick-text {
		margin: 4px 0 0;
		color: var(--v-ink-1);
		white-space: pre-line;
	}

	.down {
		margin: 0;
		padding: 8px 16px;
		font-size: 12px;
		color: var(--v-ink-2);
	}

	.section {
		border-bottom: 1px solid var(--v-line-2);
	}

	/* inside the tab body (16 px padding) a section keeps its own 16 px gutter, not 32 */
	.body > .section {
		margin: 0 -16px;
	}

	.tabs {
		padding: 0 16px;
		border-bottom: 1px solid var(--v-line-2);
	}

	.body {
		padding: 4px 16px 16px;
	}

	.sys {
		margin-top: 8px;
	}

	.officer {
		margin-top: auto;
		padding: 8px 16px;
		border-top: 1px solid var(--v-line-2);
		font-size: 12px;
	}

	.officer form {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.who {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		color: var(--v-ink-2);
		white-space: nowrap;
	}

	.officer input {
		flex: 1 1 auto;
		min-width: 0;
		height: 24px;
		padding: 0 8px;
		border: 0;
		border-radius: var(--v-radius-chip);
		box-shadow: inset 0 0 0 1px var(--v-line-2);
		background: var(--v-surface-sink);
		color: var(--v-ink-1);
		font: inherit;
	}

	.officer input:focus-visible {
		outline: 2px solid var(--v-focus);
		outline-offset: 0;
	}
</style>
